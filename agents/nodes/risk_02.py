import json
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agents.constants import AgentName, ModelConfig, StateKey
from agents.state import AgentState

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import yfinance as yf
except ImportError:
    yf = None

if load_dotenv is not None:
    load_dotenv()

# ─── System Prompt (유저 요청에 의해 수정 금지) ─────────────────────
RISK_SYSTEM_PROMPT = (
    "[Role]\n"
    "너는 기관 자금의 하방 리스크를 먼저 차단하는 수석 리스크 매니저다.\n\n"
    "[Instruction]\n"
    "아래 제공되는 실시간 데이터(FRED 매크로 지표, 뉴스, Yahoo Finance 주가 흐름)를 "
    "직접 분석하여 지금 가장 위험한 섹터를 스스로 선정하라.\n"
    "고정된 섹터 목록은 없다. 데이터가 가리키는 곳을 따라가라.\n\n"
    "[Output Format]\n"
    "1. 반드시 5문장 이내로 작성한다.\n"
    "2. 위험 섹터의 하락 배경을 논리적으로 설명한다.\n"
    "3. 절대 피해야 할 대표 종목 2~3개를 티커(Ticker)와 함께강한 어조로 경고한다.\n"
    "4. 티커는 반드시 본문에 등장한 데이터에서 근거가 있는 종목만 사용한다.\n"
    "[Context]\n"
    "아래 제공된 첨부파일 3개를 꼭 읽고 내 지시를 완벽히 따라줘.\n"
    "1. TASKS.md: 전체 시스템 중 너의 역할과 목표는 "
    "[ 본인 태스크 번호 및 제목, 예: 4번. Risk Alert ] 야. "
    "다른 시스템은 신경 쓰지 말고 지정된 태스크에만 집중해.\n"
    "2. STYLE_GUIDE.md: 네가 코딩할 때 무조건 지켜야 할 파이썬 코딩 룰이야. "
    "(함수 100줄 이하, 선언적 코드 작성, 타입 힌팅 필수)\n"
    "3. state.py: 우리가 주고받을 LangGraph의 핵심 데이터(State) 인터페이스야. "
    "너의 입력과 출력은 반드시 이 스키마를 준수해야 해. "
    "절대 무단으로 키값을 수정하거나 새로 만들지 마.\n"
    "[Action]\n"
    "자, 이제 숙지했으면 TASKS.md에 명시된 내 파트를 구현하기 위한 "
    "최적의 파이썬 코드를 작성해 줘.\n\n"
)

# ─── 엔티티 추출 전용 프롬프트 ──────────────────────────────────
ENTITY_EXTRACTION_PROMPT = (
    "아래 뉴스 기사들을 분석하여 각 기사에서 위험 신호를 추출하라.\n"
    "각 기사마다 아래 JSON 형식으로 추출하고, 전체를 JSON 배열로 반환하라.\n"
    "JSON 배열 외에 다른 텍스트는 절대 포함하지 마라.\n\n"
    "{\n"
    '  "title": "기사 제목 요약",\n'
    '  "tickers": ["관련 티커"],\n'
    '  "companies": ["회사명"],\n'
    '  "industry_terms": ["산업/섹터 키워드"],\n'
    '  "risk_keywords": ["리스크 키워드"],\n'
    '  "event_type": "이벤트 유형 (실적악화/구조조정/차환위기 등)",\n'
    '  "sentiment_score": -0.8\n'
    "}\n\n"
    "sentiment_score 범위: -1.0(매우 부정) ~ 1.0(매우 긍정)\n"
    "ticker가 불명확하면 tickers를 빈 배열로 두어라.\n"
    "반드시 유효한 JSON만 출력하라."
)

# ─── 테마 추출 전용 프롬프트 ──────────────────────────────────
THEME_DETECTION_PROMPT = (
    "아래 뉴스 기사들을 분석하여 현재 시장에서 주목받는 '투자 테마'를 추출하라.\n"
    "투자 테마란 개별 기업이 아닌, 구조적 변화(법안 통과, 기술 혁신, 공급망 재편, "
    "전쟁, 인구구조 변화 등)에 의해 형성된 산업/섹터 단위의 트렌드를 말한다.\n\n"
    "각 테마마다 아래 JSON 형식으로 추출하고, 전체를 JSON 배열로 반환하라.\n"
    "JSON 배열 외에 다른 텍스트는 절대 포함하지 마라.\n\n"
    "{\n"
    '  "theme_name": "테마명 (예: AI 인프라, 비만치료제, 전력망 인프라)",\n'
    '  "theme_type": "growth | defensive | cyclical | speculative",\n'
    '  "representative_etfs": ["관련 테마 ETF 티커 1~2개, 실제 존재하는 것만"],\n'
    '  "leader_stocks": ["대장주 티커 2~3개"],\n'
    '  "structural_driver": "구조적 변화 요인 1문장",\n'
    '  "sentiment": "positive | negative | mixed"\n'
    "}\n\n"
    "규칙:\n"
    "1. 단순 언급량이 아닌 구조적 변화를 동반한 테마만 추출하라.\n"
    "2. ETF 티커는 실제 존재하는 것만 사용하라. 불확실하면 빈 배열로 두어라.\n"
    "3. 최소 2개, 최대 5개의 테마를 추출하라.\n"
    "4. 반드시 유효한 JSON만 출력하라."
)

# ─── 상수 ─────────────────────────────────────────────────────
# DFF(정책금리), DGS10(장기금리), BAMLH0A0HYM2(HY 스프레드)
FRED_SERIES = {
    "fed_funds_rate": "DFF",
    "ten_year_yield": "DGS10",
    "high_yield_spread": "BAMLH0A0HYM2",
}

# 군집 키워드 → 거시 민감도 매핑 (아키텍처 §9)
MACRO_SENSITIVITY = {
    "rate_sensitive": [
        "refinancing",
        "debt",
        "leverage",
        "real estate",
        "unprofitable",
        "capital raise",
        "mortgage",
        "reit",
    ],
    "cycle_sensitive": [
        "auto",
        "industrial",
        "consumer demand",
        "freight",
        "retail",
        "manufacturing",
        "construction",
    ],
    "credit_sensitive": [
        "high yield",
        "spread",
        "default",
        "distressed",
        "bankruptcy",
        "downgrade",
        "junk",
    ],
}

# 티커 추출 시 제외할 일반 약어
_TICKER_NOISE = {
    "FRED",
    "API",
    "ETF",
    "LLM",
    "GDP",
    "CPI",
    "PPI",
    "PMI",
    "CEO",
    "CFO",
    "CIO",
    "IPO",
    "SEC",
    "FED",
    "USD",
    "USA",
    "THE",
    "AND",
    "FOR",
    "NOT",
    "BUT",
    "ARE",
    "THIS",
    "THAT",
    "WITH",
    "FROM",
    "RISK",
    "ALERT",
    "TEXT",
    "DATA",
    "NEWS",
    "JSON",
    "ROLE",
    "ACTION",
    "FORMAT",
    "CONTEXT",
}

T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════
# HTTP 유틸리티
# ═══════════════════════════════════════════════════════════════
def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    req = Request(url=url, headers=headers or {}, method="GET")
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    merged = {"Content-Type": "application/json", **(headers or {})}
    req = Request(
        url=url,
        headers=merged,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _safe_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ═══════════════════════════════════════════════════════════════
# 병렬 처리 유틸리티
# ═══════════════════════════════════════════════════════════════
def _parallel_map_dict(
    items: Dict[str, T],
    worker: Callable[[T], Any],
    max_workers: int,
) -> Dict[str, Any]:
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fmap = {pool.submit(worker, v): k for k, v in items.items()}
        return {fmap[f]: f.result() for f in as_completed(fmap)}


def _parallel_map_list(
    items: List[T],
    worker: Callable[[T], Any],
    max_workers: int,
) -> List[Any]:
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        idx_map = {pool.submit(worker, it): i for i, it in enumerate(items)}
        results: List[Any] = [None] * len(items)
        for f in as_completed(idx_map):
            results[idx_map[f]] = f.result()
    return results


# ═══════════════════════════════════════════════════════════════
# Step 1: 데이터 수집 (FRED / Tavily / yfinance)
# ═══════════════════════════════════════════════════════════════


# FRED 단일 시계열 최근 관측치(최대 4개) 조회
def _fetch_fred_series(series_id: str, api_key: str) -> List[float]:
    q = urlencode(
        {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 4,
        }
    )
    url = f"https://api.stlouisfed.org/fred/series/observations?{q}"
    data = _http_get_json(url)
    vals = [_safe_float(o.get("value")) for o in data.get("observations", [])]
    return [v for v in vals if v is not None]


# FRED 금리/스프레드 지표를 요약 문자열 + 원시 값 dict로 반환
def _build_macro_context() -> Dict[str, Any]:
    api_key = os.getenv("FRED_API_KEY", "").strip()
    if not api_key:
        return {"summary": "FRED_API_KEY 미설정", "values": {}}

    try:
        sv = _parallel_map_dict(
            items=FRED_SERIES,
            worker=lambda sid: _fetch_fred_series(sid, api_key),
            max_workers=len(FRED_SERIES),
        )
    except (HTTPError, URLError, TimeoutError, ValueError) as err:
        return {"summary": f"FRED 조회 실패: {err}", "values": {}}

    values: Dict[str, Optional[float]] = {k: (sv[k][0] if sv[k] else None) for k in FRED_SERIES}
    parts = [
        f"연방기금금리 {values['fed_funds_rate']:.2f}%" if values["fed_funds_rate"] else "연방기금금리 데이터 없음",
        f"미국채 10년물 {values['ten_year_yield']:.2f}%" if values["ten_year_yield"] else "10년물 데이터 없음",
        f"하이일드 스프레드 {values['high_yield_spread']:.2f}"
        if values["high_yield_spread"]
        else "HY스프레드 데이터 없음",
    ]
    return {"summary": ", ".join(parts), "values": values}


# Tavily 뉴스 원문(title + content) 수집
def _fetch_news_articles(query: str, max_results: int = 15) -> List[Dict[str, str]]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []

    body = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_answer": False,
    }
    try:
        resp = _http_post_json("https://api.tavily.com/search", body)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return []

    return [
        {
            "title": it.get("title", ""),
            "content": it.get("content", "")[:300],
        }
        for it in resp.get("results", [])
        if it.get("title")
    ]


# ─── 기술적 지표 헬퍼 (RSI, 이동평균 이격도) ────────────────
def _compute_rsi(closes: Any, period: int = 14) -> Optional[float]:
    """pandas Series 기반 RSI 계산."""
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    last_loss = loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    rs = gain.iloc[-1] / last_loss
    return round(100 - (100 / (1 + rs)), 1)


def _compute_ma_divergence(closes: Any, period: int = 5) -> Optional[float]:
    """pandas Series 기반 이동평균 이격도(%) 계산."""
    if len(closes) < period:
        return None
    ma = closes.rolling(period).mean().iloc[-1]
    if ma == 0:
        return None
    return round((closes.iloc[-1] / ma - 1) * 100, 1)


def _compute_rsi_from_list(prices: List[float], period: int = 14) -> Optional[float]:
    """순수 리스트 기반 RSI 계산 (API 폴백용)."""
    if len(prices) < period + 1:
        return None
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    recent = deltas[-period:]
    avg_gain = sum(max(d, 0) for d in recent) / period
    avg_loss = sum(max(-d, 0) for d in recent) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _compute_ma_divergence_from_list(
    prices: List[float], period: int = 5,
) -> Optional[float]:
    """순수 리스트 기반 이동평균 이격도(%) 계산 (API 폴백용)."""
    if len(prices) < period:
        return None
    ma = sum(prices[-period:]) / period
    if ma == 0:
        return None
    return round((prices[-1] / ma - 1) * 100, 1)


# 단일 티커의 시장 신호(수익률, 변동성, RSI, MA 이격도) 조회
def _fetch_market_signal(ticker: str) -> Dict[str, Any]:
    base: Dict[str, Any] = {"ticker": ticker}

    if yf is not None:
        try:
            hist = yf.Ticker(ticker).history(period="3mo", interval="1d")
            closes = hist["Close"].dropna()
            if len(closes) < 20:
                return {**base, "error": "insufficient data"}
            r5 = (closes.iloc[-1] / closes.iloc[-5] - 1) * 100
            r20 = (closes.iloc[-1] / closes.iloc[-20] - 1) * 100
            vol = closes.pct_change().dropna().iloc[-20:].std() * (252**0.5) * 100
            dd = ((closes - closes.cummax()) / closes.cummax() * 100).min()
            rsi_14 = _compute_rsi(closes)
            ma5_div = _compute_ma_divergence(closes)
            return {
                **base,
                "return_5d": round(r5, 1),
                "return_20d": round(r20, 1),
                "volatility_20d": round(vol, 1),
                "drawdown_3m": round(float(dd), 1),
                "rsi_14": rsi_14,
                "ma5_divergence": ma5_div,
            }
        except Exception as err:
            return {**base, "error": str(err)}

    return _fetch_market_signal_api(ticker)


# yfinance 미설치 시 Yahoo 차트 API 폴백
def _fetch_market_signal_api(ticker: str) -> Dict[str, Any]:
    base: Dict[str, Any] = {"ticker": ticker}
    q = urlencode({"range": "3mo", "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?{q}"
    try:
        data = _http_get_json(url)
    except (HTTPError, URLError, TimeoutError, ValueError) as err:
        return {**base, "error": str(err)}

    result = data.get("chart", {}).get("result", [])
    if not result:
        return {**base, "error": "no data"}

    raw = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
    prices = [p for p in raw if p is not None]
    if len(prices) < 20:
        return {**base, "error": "insufficient prices"}

    r5 = (prices[-1] / prices[-5] - 1) * 100
    r20 = (prices[-1] / prices[-20] - 1) * 100
    peak = prices[0]
    dd = 0.0
    for p in prices:
        peak = max(peak, p)
        dd = min(dd, (p - peak) / peak * 100)

    rsi_14 = _compute_rsi_from_list(prices)
    ma5_div = _compute_ma_divergence_from_list(prices)

    return {
        **base,
        "return_5d": round(r5, 1),
        "return_20d": round(r20, 1),
        "drawdown_3m": round(dd, 1),
        "rsi_14": rsi_14,
        "ma5_divergence": ma5_div,
    }


# ═══════════════════════════════════════════════════════════════
# Step 2: 뉴스에서 위험 엔티티 추출 (LLM 구조화 출력)
# ═══════════════════════════════════════════════════════════════


# LLM 응답에서 JSON 배열을 안전하게 파싱
def _parse_llm_json(text: str) -> List[Dict[str, Any]]:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        match = re.search(r"\[.*]", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return []


# 뉴스 기사 배치를 LLM에 보내 RiskEvent 구조로 추출
def _extract_risk_entities(articles: List[Dict[str, str]], llm: Any) -> List[Dict[str, Any]]:
    if not articles:
        return []

    text = "\n\n".join(f"[기사 {i + 1}] {a['title']}\n{a['content']}" for i, a in enumerate(articles))
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ENTITY_EXTRACTION_PROMPT),
            ("user", "{articles}"),
        ]
    )
    try:
        resp = (prompt | llm).invoke({"articles": text})
        entities = _parse_llm_json(resp.content)
        for e in entities:
            e.setdefault("tickers", [])
            e.setdefault("companies", [])
            e.setdefault("industry_terms", [])
            e.setdefault("risk_keywords", [])
            e.setdefault("event_type", "unknown")
            e.setdefault("sentiment_score", 0.0)
        return entities
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# Step 3: 추출된 티커에 시장 신호 부착
# ═══════════════════════════════════════════════════════════════
def _attach_market_signals(
    entities: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    all_tickers = list({t for e in entities for t in e.get("tickers", [])})
    if not all_tickers:
        return {}
    tickers = all_tickers[:20]
    signals = _parallel_map_list(
        items=tickers,
        worker=_fetch_market_signal,
        max_workers=min(len(tickers), 10),
    )
    return {s["ticker"]: s for s in signals}


# ═══════════════════════════════════════════════════════════════
# Step 4: 키워드 기반 군집화 (Union-Find)
# ═══════════════════════════════════════════════════════════════
def _cluster_entities(
    entities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not entities:
        return []

    n = len(entities)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    ticker_idx: Dict[str, List[int]] = defaultdict(list)
    for i, e in enumerate(entities):
        for t in e.get("tickers", []):
            ticker_idx[t.upper()].append(i)

    for indices in ticker_idx.values():
        for j in range(1, len(indices)):
            union(indices[0], indices[j])

    for i in range(n):
        ti = {k.lower() for k in entities[i].get("industry_terms", [])}
        for j in range(i + 1, n):
            tj = {k.lower() for k in entities[j].get("industry_terms", [])}
            if len(ti & tj) >= 2:
                union(i, j)

    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    clusters: List[Dict[str, Any]] = []
    for cid, indices in enumerate(groups.values()):
        ce = [entities[i] for i in indices]
        avg_sent = sum(e.get("sentiment_score", 0) for e in ce) / max(len(ce), 1)
        clusters.append(
            {
                "cluster_id": f"cluster_{cid:02d}",
                "tickers": list({t for e in ce for t in e.get("tickers", [])}),
                "companies": list({c for e in ce for c in e.get("companies", [])}),
                "industry_terms": list({k for e in ce for k in e.get("industry_terms", [])}),
                "risk_keywords": list({k for e in ce for k in e.get("risk_keywords", [])}),
                "event_types": list({e.get("event_type", "") for e in ce}),
                "news_count": len(ce),
                "avg_sentiment": avg_sent,
            }
        )
    return clusters


# ═══════════════════════════════════════════════════════════════
# Step 5: 거시 민감도 매핑 + 위험 점수 계산
# ═══════════════════════════════════════════════════════════════


# 군집 키워드 → 거시 민감도 카테고리 매핑
def _map_macro_exposure(keywords: List[str]) -> List[str]:
    joined = " ".join(k.lower() for k in keywords)
    exposures = [cat for cat, terms in MACRO_SENSITIVITY.items() if any(t in joined for t in terms)]
    return exposures or ["general"]


# 군집별 복합 위험 점수(0~100) = 매크로 35% + 시장 35% + 뉴스 30%
def _score_cluster(
    cluster: Dict[str, Any],
    market_signals: Dict[str, Dict[str, Any]],
    macro_values: Dict[str, Optional[float]],
) -> float:
    neg = max(-cluster.get("avg_sentiment", 0), 0)
    cnt_factor = min(cluster.get("news_count", 0) / 3.0, 1.0)
    news_score = neg * 60 + cnt_factor * 40

    returns = [
        market_signals[t].get("return_20d", 0)
        for t in cluster.get("tickers", [])
        if t in market_signals and "error" not in market_signals[t]
    ]
    market_score = min(max(-sum(returns) / max(len(returns), 1) * 5, 0), 100) if returns else 30

    kw = cluster.get("risk_keywords", []) + cluster.get("industry_terms", [])
    exposures = _map_macro_exposure(kw)
    macro_score = 30.0
    rate = macro_values.get("fed_funds_rate")
    spread = macro_values.get("high_yield_spread")
    if "rate_sensitive" in exposures and rate and rate > 4.0:
        macro_score += 35
    if "credit_sensitive" in exposures and spread and spread > 4.0:
        macro_score += 35
    if "cycle_sensitive" in exposures:
        macro_score += 15
    macro_score = min(macro_score, 100)

    return round(
        macro_score * 0.35 + market_score * 0.35 + news_score * 0.30,
        1,
    )


# ═══════════════════════════════════════════════════════════════
# Step 6: 상위 군집을 LLM 입력용 evidence 블록으로 포맷
# ═══════════════════════════════════════════════════════════════
def _format_clusters_evidence(
    clusters: List[Dict[str, Any]],
    market_signals: Dict[str, Dict[str, Any]],
    macro_summary: str,
) -> str:
    lines = [f"[FRED 매크로 지표]\n{macro_summary}\n"]

    for c in clusters[:3]:
        ticker_details = []
        for t in c.get("tickers", []):
            sig = market_signals.get(t, {})
            if "error" not in sig:
                d = f"  {t}: 5일 {sig.get('return_5d', '?')}%, 20일 {sig.get('return_20d', '?')}%"
                if sig.get("drawdown_3m") is not None:
                    d += f", 최대낙폭 {sig['drawdown_3m']}%"
                if sig.get("rsi_14") is not None:
                    d += f", RSI {sig['rsi_14']}"
                if sig.get("ma5_divergence") is not None:
                    d += f", 5MA이격 {sig['ma5_divergence']}%"
                ticker_details.append(d)
            else:
                ticker_details.append(f"  {t}: 데이터 없음")

        lines.append(
            f"[위험 군집: {c['cluster_id']}] "
            f"(위험점수 {c.get('risk_score', 0)})\n"
            f"  종목: {', '.join(c.get('tickers', []))}\n"
            f"  산업: {', '.join(c.get('industry_terms', []))}\n"
            f"  리스크: {', '.join(c.get('risk_keywords', []))}\n"
            f"  이벤트: {', '.join(c.get('event_types', []))}\n"
            f"  뉴스 {c.get('news_count', 0)}건 | "
            f"감성 {c.get('avg_sentiment', 0):.2f}\n"
            f"  주가 흐름:\n" + "\n".join(ticker_details)
        )
    return "\n\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 동적 테마 발굴 및 하방 리스크 판정 (Thematic Risk Logic)
# ═══════════════════════════════════════════════════════════════


def _fetch_theme_news() -> List[Dict[str, str]]:
    """Tavily에서 상승 테마 + 섹터 약점 뉴스를 병렬 수집한다."""
    queries = [
        "Stock Market Rising Investment Themes structural change 2026",
        "Sector Weakness bubble overvaluation risk concerns 2026",
    ]
    results = _parallel_map_list(
        items=queries,
        worker=lambda q: _fetch_news_articles(q, max_results=10),
        max_workers=2,
    )
    combined: List[Dict[str, str]] = []
    for batch in results:
        combined.extend(batch)
    return combined


def _extract_themes(
    articles: List[Dict[str, str]], llm: Any,
) -> List[Dict[str, Any]]:
    """뉴스에서 구조적 변화를 동반한 투자 테마를 추출한다."""
    if not articles:
        return []

    text = "\n\n".join(
        f"[기사 {i + 1}] {a['title']}\n{a['content']}"
        for i, a in enumerate(articles)
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", THEME_DETECTION_PROMPT),
            ("user", "{articles}"),
        ]
    )
    try:
        resp = (prompt | llm).invoke({"articles": text})
        themes = _parse_llm_json(resp.content)
        for t in themes:
            t.setdefault("theme_name", "Unknown")
            t.setdefault("theme_type", "growth")
            t.setdefault("representative_etfs", [])
            t.setdefault("leader_stocks", [])
            t.setdefault("structural_driver", "")
            t.setdefault("sentiment", "mixed")
        return themes[:5]
    except Exception:
        return []


def _enrich_theme_signals(
    themes: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """테마별 대표 ETF/종목의 시장 신호(RSI, MA 이격도 포함)를 수집한다."""
    all_tickers: List[str] = []
    for t in themes:
        all_tickers.extend(t.get("representative_etfs", []))
        all_tickers.extend(t.get("leader_stocks", []))
    unique = list(dict.fromkeys(all_tickers))[:15]
    if not unique:
        return {}
    signals = _parallel_map_list(
        items=unique,
        worker=_fetch_market_signal,
        max_workers=min(len(unique), 8),
    )
    return {s["ticker"]: s for s in signals}


_NARRATIVE_NEGATIVE_KW = frozenset({
    "risk", "crash", "bubble", "overvalued", "regulation", "ban",
    "failure", "miss", "downgrade", "default", "fraud", "investigation",
    "decline", "slump", "plunge", "collapse", "warning", "concern",
})


def _check_narrative_damage(theme_name: str) -> bool:
    """테마에 대한 부정적 뉴스(규제, 실적 미달 등)가 상위에 노출되는지 확인한다."""
    query = f"{theme_name} risk regulation failure concerns setback 2026"
    articles = _fetch_news_articles(query, max_results=5)
    if not articles:
        return False
    hit_count = 0
    for a in articles:
        text_lower = f"{a.get('title', '')} {a.get('content', '')}".lower()
        if any(kw in text_lower for kw in _NARRATIVE_NEGATIVE_KW):
            hit_count += 1
    return hit_count >= 3


def _is_technically_overheated(
    theme: Dict[str, Any],
    signals: Dict[str, Dict[str, Any]],
) -> bool:
    """테마 대표 종목의 RSI > 75 또는 5MA 이격도 > 10% 여부를 확인한다."""
    tickers = theme.get("representative_etfs", []) + theme.get("leader_stocks", [])
    for t in tickers:
        sig = signals.get(t, {})
        if "error" in sig:
            continue
        rsi = sig.get("rsi_14")
        ma_div = sig.get("ma5_divergence")
        if (rsi is not None and rsi > 75) or (ma_div is not None and ma_div > 10):
            return True
    return False


def _assess_macro_headwind(
    theme: Dict[str, Any],
    macro_values: Dict[str, Optional[float]],
) -> bool:
    """고성장 테마에서 매크로 역행(금리 급등, 실질 금리 상승) 여부를 판단한다."""
    theme_type = theme.get("theme_type", "growth")
    ten_year = macro_values.get("ten_year_yield")
    fed_rate = macro_values.get("fed_funds_rate")

    if theme_type in ("growth", "speculative"):
        if ten_year is not None and ten_year > 4.5:
            return True
        if fed_rate is not None and fed_rate > 5.0:
            return True

    if theme_type == "cyclical":
        spread = macro_values.get("high_yield_spread")
        if spread is not None and spread > 4.5:
            return True

    return False


def _score_themes(
    themes: List[Dict[str, Any]],
    signals: Dict[str, Dict[str, Any]],
    macro_values: Dict[str, Optional[float]],
) -> List[Dict[str, Any]]:
    """각 테마에 3-기준(과열/매크로 역행/내러티브 훼손) 하방 리스크를 판정한다."""
    if not themes:
        return []

    damage_results = _parallel_map_list(
        items=[t.get("theme_name", "") for t in themes],
        worker=_check_narrative_damage,
        max_workers=min(len(themes), 5),
    )

    scored: List[Dict[str, Any]] = []
    for i, theme in enumerate(themes):
        flags: List[str] = []

        if _is_technically_overheated(theme, signals):
            flags.append("기술적 과열")
        if _assess_macro_headwind(theme, macro_values):
            flags.append("매크로 역행")
        if i < len(damage_results) and damage_results[i]:
            flags.append("내러티브 훼손")

        flag_count = len(flags)
        if flag_count >= 2:
            decision = "CRITICAL"
        elif flag_count == 1:
            decision = "CAUTION"
        else:
            decision = "WATCH"

        scored.append({**theme, "risk_flags": flags, "decision": decision})

    scored.sort(key=lambda x: len(x["risk_flags"]), reverse=True)
    return scored


def _format_theme_evidence(
    themes: List[Dict[str, Any]],
    signals: Dict[str, Dict[str, Any]],
) -> str:
    """테마 분석 결과를 LLM 입력용 evidence 블록으로 포맷한다."""
    if not themes:
        return ""

    lines = ["\n[테마 기반 하방 리스크 분석]"]
    for t in themes:
        decision = t.get("decision", "WATCH")
        flags = ", ".join(t.get("risk_flags", [])) or "없음"
        etfs = ", ".join(t.get("representative_etfs", [])) or "N/A"
        leaders = ", ".join(t.get("leader_stocks", [])) or "N/A"

        ticker_details: List[str] = []
        for ticker in t.get("representative_etfs", []) + t.get("leader_stocks", []):
            sig = signals.get(ticker, {})
            if "error" not in sig:
                detail = f"    {ticker}: RSI {sig.get('rsi_14', '?')}"
                detail += f", 5MA이격 {sig.get('ma5_divergence', '?')}%"
                detail += f", 5일 {sig.get('return_5d', '?')}%"
                detail += f", 20일 {sig.get('return_20d', '?')}%"
                ticker_details.append(detail)

        lines.append(
            f"\n  테마: {t.get('theme_name', '?')} [{decision}]\n"
            f"  유형: {t.get('theme_type', '?')}\n"
            f"  구조적 동인: {t.get('structural_driver', '?')}\n"
            f"  위험 플래그: {flags}\n"
            f"  대표 ETF: {etfs}\n"
            f"  대장주: {leaders}\n"
            f"  기술적 지표:\n" + "\n".join(ticker_details)
        )
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 피드백 / 폴백 / 검증
# ═══════════════════════════════════════════════════════════════


# GP 피드백이 risk 대상일 때만 사유를 추출
def _get_feedback_text(state: AgentState) -> str:
    feedback = state.get(StateKey.GP_FEEDBACK, {})
    if feedback.get("target_node") != AgentName.RISK:
        return "현재 GP 피드백 없음"
    return feedback.get("feedback_reason", "현재 GP 피드백 없음")


# LLM 미사용/실패 시 최소 출력 계약을 유지하는 폴백
def _build_fallback_result(state: AgentState) -> str:
    fb = _get_feedback_text(state)
    suffix = "" if fb == "현재 GP 피드백 없음" else f" GP 지적: '{fb}'"
    return (
        "현재 FRED 금리 환경과 시장 데이터를 종합하면 "
        "고금리 부담이 큰 섹터부터 우선 회피해야 합니다. "
        "구체적 데이터 확보 후 재분석이 필요합니다."
        f"{suffix}"
    )


# 최종 출력에서 티커 패턴 추출 (노이즈 제외)
def _extract_tickers(text: str) -> List[str]:
    candidates = re.findall(r"\b[A-Z]{1,5}\b", text.upper())
    seen: List[str] = []
    for tok in candidates:
        if tok not in _TICKER_NOISE and tok not in seen:
            seen.append(tok)
    return seen


# Acceptance Criteria: 대표주 2개 이상 포함 여부
def _has_enough_tickers(text: str) -> bool:
    return len(_extract_tickers(text)) >= 2


def _has_required_risk_format(text: str) -> bool:
    """요구 출력 형식(1~3위 반복 구조 + 각 2티커 + 근거 5줄)을 최소 검증한다."""
    normalized = text.replace("\r\n", "\n")
    rank_pattern = re.compile(
        r"(?ms)^\s*([1-3])위.*?"
        r"^\s*1\.\s*위험섹터/테마\s*:\s*(.+?)\n"
        r"^\s*2\.\s*관련종목\s*:\s*(.+?)\n"
        r"^\s*3\.\s*리스크 근거\s*:\s*(.+?)(?=^\s*[1-3]위|\Z)"
    )
    matches = list(rank_pattern.finditer(normalized))
    if len(matches) != 3:
        return False

    seen_ranks = {m.group(1) for m in matches}
    if seen_ranks != {"1", "2", "3"}:
        return False

    for m in matches:
        related = m.group(3)
        if len(_extract_tickers(related)) < 2:
            return False
        reason = m.group(4).strip()
        reason_lines = [ln for ln in reason.splitlines() if ln.strip()]
        if len(reason_lines) < 5:
            return False
    return True


# ═══════════════════════════════════════════════════════════════
# LLM 체인 호출
# ═══════════════════════════════════════════════════════════════
def _generate_risk_text(
    chain: Any,
    evidence: str,
    macro_result: str,
    feedback_text: str,
    retry_hint: str,
) -> str:
    resp = chain.invoke(
        {
            "evidence": evidence,
            "macro_result": macro_result,
            "feedback_text": feedback_text,
            "retry_hint": retry_hint,
            "today": datetime.now().strftime("%Y-%m-%d"),
        }
    )
    return resp.content


# ═══════════════════════════════════════════════════════════════
# Risk 노드 메인 엔트리포인트
# 흐름: 수집 → 엔티티 추출 → 시장 신호 부착 → 군집화 → 점수화
#       → LLM 경보 생성 → 검증/재시도 → state 저장
# ═══════════════════════════════════════════════════════════════
def risk_node(state: AgentState) -> Dict[str, Any]:
    macro_result = state.get(StateKey.MACRO_RESULT, "매크로 요약 없음")
    feedback_text = _get_feedback_text(state)

    if not os.getenv("OPENAI_API_KEY"):
        return {StateKey.RISK_RESULT: _build_fallback_result(state)}

    llm = ChatOpenAI(
        model=ModelConfig.DEFAULT_LLM_MODEL,
        temperature=ModelConfig.DEFAULT_TEMPERATURE,
    )

    # ── Step 1: 데이터 수집 (기존 위험 뉴스 + 테마 뉴스) ──
    macro = _build_macro_context()
    articles = _fetch_news_articles(
        "US stock market sector risk downgrade credit default earnings miss refinancing pressure 2026"
    )
    theme_articles = _fetch_theme_news()

    # ── Step 2: 위험 엔티티 추출 + 투자 테마 추출 ──
    entities = _extract_risk_entities(articles, llm)
    themes = _extract_themes(theme_articles, llm)

    # ── Step 3: 시장 신호 부착 (엔티티 + 테마 종목) ──
    market_signals = _attach_market_signals(entities)
    theme_signals = _enrich_theme_signals(themes)

    # ── Step 4: 키워드 기반 군집화 (기존 bottom-up) ──
    clusters = _cluster_entities(entities)

    # ── Step 5a: 군집 위험 점수 계산 ──
    macro_values = macro.get("values", {})
    for c in clusters:
        c["risk_score"] = _score_cluster(c, market_signals, macro_values)
    clusters.sort(key=lambda x: x["risk_score"], reverse=True)
    clusters = [
        c for c in clusters
        if c.get("news_count", 0) >= 2 or len(c.get("tickers", [])) >= 2
    ]

    # ── Step 5b: 테마 하방 리스크 판정 (3-기준 스코어링) ──
    scored_themes = _score_themes(themes, theme_signals, macro_values)

    # ── Step 6: 하이브리드 evidence 포맷 → LLM 경보 생성 ──
    cluster_evidence = _format_clusters_evidence(
        clusters, market_signals, macro.get("summary", ""),
    )
    theme_evidence = _format_theme_evidence(scored_themes, theme_signals)
    combined_evidence = (
        f"{cluster_evidence}\n\n{theme_evidence}"
        if theme_evidence
        else cluster_evidence
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", RISK_SYSTEM_PROMPT),
            (
                "user",
                "작성 기준일: {today}\n\n"
                "기존 매크로 요약:\n{macro_result}\n\n"
                "위험 군집 + 테마 분석 결과:\n{evidence}\n\n"
                "검수 피드백:\n{feedback_text}\n\n"
                "추가 지시:\n{retry_hint}\n\n"
                "위 데이터를 기반으로 아래 형식에 맞춰 리스크 경보를 작성하세요.\n"
                "형식은 반드시 1위~3위까지 반복한다:\n\n"
                "1위\n"
                "1. 위험섹터/테마 : [테마명]\n"
                "2. 관련종목 : [종목명(TICKER), 종목명(TICKER)]\n"
                "3. 리스크 근거 :\n"
                "- [근거 1]\n"
                "- [근거 2]\n"
                "- [근거 3]\n"
                "- [근거 4]\n"
                "- [근거 5]\n\n"
                "2위\n"
                "1. 위험섹터/테마 : [테마명]\n"
                "2. 관련종목 : [종목명(TICKER), 종목명(TICKER)]\n"
                "3. 리스크 근거 :\n"
                "- [근거 1]\n"
                "- [근거 2]\n"
                "- [근거 3]\n"
                "- [근거 4]\n"
                "- [근거 5]\n\n"
                "3위\n"
                "1. 위험섹터/테마 : [테마명]\n"
                "2. 관련종목 : [종목명(TICKER), 종목명(TICKER)]\n"
                "3. 리스크 근거 :\n"
                "- [근거 1]\n"
                "- [근거 2]\n"
                "- [근거 3]\n"
                "- [근거 4]\n"
                "- [근거 5]\n\n"
                "중요 제약:\n"
                "- 총 3개를 반드시 작성할 것 (1위, 2위, 3위).\n"
                "- 각 순위의 관련종목은 정확히 2개만 작성할 것.\n"
                "- 리스크 근거는 각 순위 블록의 마지막(3번)에 배치할 것.\n"
                "- 각 순위의 리스크 근거는 줄바꿈 기준 최소 5줄로 작성할 것.\n"
                "CRITICAL 판정을 받은 테마는 반드시 최우선으로 경고하세요.\n"
                "WATCH 판정 테마는 알파 헌터 노드 참고용으로만 간략 언급하세요.",
            ),
        ]
    )
    chain = prompt | llm

    try:
        result = _generate_risk_text(
            chain=chain,
            evidence=combined_evidence,
            macro_result=macro_result,
            feedback_text=feedback_text,
            retry_hint=(
                "1위~3위 반복 형식을 엄격히 지켜라. "
                "각 순위는 1.위험섹터/테마 2.관련종목 3.리스크 근거 순서를 따르라. "
                "관련종목은 종목명(티커) 2개만 작성하라. "
                "리스크 근거는 각 순위별로 최소 5줄을 작성하라."
            ),
        )

        if not (_has_enough_tickers(result) and _has_required_risk_format(result)):
            result = _generate_risk_text(
                chain=chain,
                evidence=combined_evidence,
                macro_result=macro_result,
                feedback_text=feedback_text,
                retry_hint=(
                    "직전 출력이 형식 기준을 만족하지 않았다. "
                    "반드시 1위/2위/3위 세 블록을 작성하고, "
                    "각 블록에서 1.위험섹터/테마 2.관련종목 3.리스크 근거 순서를 지켜라. "
                    "관련종목은 종목명(티커) 2개만 허용된다. "
                    "각 블록의 리스크 근거는 줄바꿈 포함 최소 5줄이어야 한다."
                ),
            )

        if not (_has_enough_tickers(result) and _has_required_risk_format(result)):
            result = _build_fallback_result(state)
    except Exception as err:
        result = f"{_build_fallback_result(state)} LLM 연결 오류: {err}"

    return {StateKey.RISK_RESULT: result}
