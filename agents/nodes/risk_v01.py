import json
import os
import re
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

RISK_SYSTEM_PROMPT = (
    "[Role]\n"
    "너는 기관 자금의 하방 리스크를 먼저 차단하는 수석 리스크 매니저다.\n\n"
    "[Instruction]\n"
    "아래 제공되는 실시간 데이터(FRED 매크로 지표, 뉴스, Yahoo Finance 주가 흐름)를 "
    "직접 분석하여 지금 가장 위험한 섹터를 스스로 선정하라.\n"
    "고정된 섹터 목록은 없다. 데이터가 가리키는 곳을 따라가라.\n\n"
    "[Output Format]\n"
    "1. 반드시 3문장 이내로 작성한다.\n"
    "2. 위험 섹터의 하락 배경을 논리적으로 설명한다.\n"
    "3. 절대 피해야 할 대표 종목 2~3개를 티커(Ticker)와 함께강한 어조로 경고한다.\n"
    "4. 티커는 반드시 본문에 등장한 데이터에서 근거가 있는 종목만 사용한다."
    
    "[Context]\n"
    "아래 제공된 첨부파일 3개를 꼭 읽고 내 지시를 완벽히 따라줘.\n"
    "1. TASKS.md: 전체 시스템 중 너의 역할과 목표는 [ 본인 태스크 번호 및 제목, 예: 4번. Risk Alert ] 야. 다른 시스템은 신경 쓰지 말고 지정된 태스크에만 집중해.\n"
    "2. STYLE_GUIDE.md: 네가 코딩할 때 무조건 지켜야 할 파이썬 코딩 룰이야. (함수 100줄 이하, 선언적 코드 작성, 타입 힌팅 필수)\n"
    "3. state.py: 우리가 주고받을 LangGraph의 핵심 데이터(State) 인터페이스야. 너의 입력과 출력은 반드시 이 스키마를 준수해야 해. 절대 무단으로 키값을 수정하거나 새로 만들지 마.\n"

    "[Action]\n"
    "자, 이제 숙지했으면 TASKS.md에 명시된 내 파트를 구현하기 위한 최적의 파이썬 코드를 작성해 줘.\n\n"
)

# 시나리오: 조달비용과 신용 리스크를 함께 보기 위해
# DFF(정책금리), DGS10(장기금리), BAMLH0A0HYM2(HY 스프레드)를 핵심 지표로 사용한다.
FRED_SERIES = {
    "fed_funds_rate": "DFF",
    "ten_year_yield": "DGS10",
    "high_yield_spread": "BAMLH0A0HYM2",
}

# 시나리오: 전체 시장의 섹터별 모멘텀을 비교해 약세 섹터를 자동 탐지하기 위해
# S&P 500 주요 섹터 ETF를 모니터링 대상으로 사용한다.
SECTOR_ETFS = {
    "XLF": "금융",
    "XLRE": "부동산",
    "XLE": "에너지",
    "XLV": "헬스케어",
    "XLK": "기술",
    "XLY": "경기소비재",
    "XLP": "필수소비재",
    "XLI": "산업재",
    "XLU": "유틸리티",
    "XLB": "소재",
    "XLC": "커뮤니케이션",
}

T = TypeVar("T")


# 시나리오: 외부 시세/지표 API를 조회할 때 공통으로 GET 호출을 수행한다.
# 성공 시 JSON dict를 반환하고, 실패/타임아웃은 상위 호출부에서 일괄 처리한다.
def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    request = Request(url=url, headers=headers or {}, method="GET")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


# 시나리오: Tavily 같은 POST 기반 API 조회 시 공통 요청 진입점으로 사용한다.
# 요청 payload를 JSON으로 직렬화하고 응답 JSON을 dict로 돌려준다.
def _http_post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    merged = {"Content-Type": "application/json", **(headers or {})}
    request = Request(
        url=url,
        headers=merged,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


# 시나리오: FRED 응답에 ".", "NaN" 등 비수치가 섞여 들어오는 경우를 흡수한다.
# 변환 성공 값만 후속 계산에 사용하도록 float 또는 None을 반환한다.
def _safe_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# 시나리오: 금리/스프레드 최신 상태를 빠르게 파악하기 위해 최근 관측치만 가져온다.
# 유효 숫자만 필터링해 후속 "최신값 요약" 단계에서 바로 쓸 수 있게 한다.
def _fetch_fred_series(series_id: str, api_key: str) -> List[float]:
    query = urlencode(
        {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 4,
        }
    )
    url = f"https://api.stlouisfed.org/fred/series/observations?{query}"
    payload = _http_get_json(url)
    values = [_safe_float(item.get("value")) for item in payload.get("observations", [])]
    return [v for v in values if v is not None]


# 시나리오: 서로 독립적인 FRED 시계열을 동시에 조회해 노드 대기 시간을 줄인다.
# 키-값 매핑을 유지해 이후 지표별로 안전하게 접근할 수 있게 한다.
def _parallel_map_dict(
    items: Dict[str, T],
    worker: Callable[[T], Any],
    max_workers: int,
) -> Dict[str, Any]:
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fmap = {pool.submit(worker, v): k for k, v in items.items()}
        return {fmap[f]: f.result() for f in as_completed(fmap)}


# 시나리오: ETF/티커 목록을 병렬 조회하되 원래 순서를 유지해야 할 때 사용한다.
# 완료 순서와 무관하게 결과를 입력 인덱스에 재배치해 deterministic 출력을 보장한다.
def _parallel_map_list(
    items: List[T],
    worker: Callable[[T], Any],
    max_workers: int,
) -> List[Any]:
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        idx_futures = {pool.submit(worker, item): i for i, item in enumerate(items)}
        results: List[Any] = [None] * len(items)
        for future in as_completed(idx_futures):
            results[idx_futures[future]] = future.result()
    return results


# 시나리오: 리스크 생성 전에 금리/스프레드 환경을 한 줄 문맥으로 먼저 고정한다.
# API 키 부재/조회 실패 시에도 대체 메시지를 반환해 파이프라인이 멈추지 않게 한다.
def _build_macro_context() -> str:
    api_key = os.getenv("FRED_API_KEY", "").strip()
    if not api_key:
        return "FRED_API_KEY 미설정으로 매크로 데이터 없음"

    try:
        sv = _parallel_map_dict(
            items=FRED_SERIES,
            worker=lambda sid: _fetch_fred_series(sid, api_key),
            max_workers=len(FRED_SERIES),
        )
    except (HTTPError, URLError, TimeoutError, ValueError) as err:
        return f"FRED 조회 실패: {err}"

    rate = sv["fed_funds_rate"][0] if sv["fed_funds_rate"] else None
    ten_y = sv["ten_year_yield"][0] if sv["ten_year_yield"] else None
    spread = sv["high_yield_spread"][0] if sv["high_yield_spread"] else None

    parts = [
        f"연방기금금리 {rate:.2f}%" if rate else "연방기금금리 데이터 없음",
        f"미국채 10년물 {ten_y:.2f}%" if ten_y else "10년물 데이터 없음",
        f"하이일드 스프레드 {spread:.2f}" if spread else "HY스프레드 데이터 없음",
    ]
    return ", ".join(parts)


# 시나리오: 최근 위험 뉴스를 프롬프트 근거로 붙이기 위해 호출한다.
# 키 미설정/조회 실패 시 설명 문자열을 반환해 "근거 없음" 상태를 명시한다.
def _fetch_tavily_news(query: str) -> List[str]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return ["TAVILY_API_KEY 미설정으로 뉴스 데이터 없음"]

    body = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": 3,
        "include_answer": False,
    }
    try:
        resp = _http_post_json("https://api.tavily.com/search", body)
    except (HTTPError, URLError, TimeoutError, ValueError) as err:
        return [f"뉴스 조회 실패: {err}"]

    items = resp.get("results", [])
    return [
        f"{it.get('title', '제목 없음')} | {it.get('content', '내용 없음')[:180]}" for it in items if it.get("title")
    ] or ["관련 뉴스 없음"]


# 시나리오: 티커의 최근 3개월 수익률을 조회해 요약 문자열로 반환한다.
# yfinance가 있으면 우선 사용하고, 실패하면 Yahoo 차트 API로 자동 폴백한다.
def _fetch_price_snapshot(symbol: str) -> str:
    if yf is not None:
        try:
            hist = yf.Ticker(symbol).history(period="3mo", interval="1d")
            closes = [float(v) for v in hist["Close"].dropna().tolist()]
            if len(closes) >= 2:
                pct = ((closes[-1] - closes[0]) / closes[0]) * 100
                return f"{symbol}: 3개월 수익률 {pct:.1f}%"
        except Exception as err:
            return f"{symbol}: yfinance 실패 ({err})"

    q = urlencode({"range": "3mo", "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{q}"
    try:
        data = _http_get_json(url)
    except (HTTPError, URLError, TimeoutError, ValueError) as err:
        return f"{symbol}: 가격 조회 실패 ({err})"

    result = data.get("chart", {}).get("result", [])
    if not result:
        return f"{symbol}: 가격 데이터 없음"

    raw = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
    prices = [p for p in raw if p is not None]
    if len(prices) < 2:
        return f"{symbol}: 유효 종가 부족"

    pct = ((prices[-1] - prices[0]) / prices[0]) * 100
    return f"{symbol}: 3개월 수익률 {pct:.1f}%"


# 시나리오: 전체 섹터 ETF의 가격 모멘텀을 병렬 조회해 약세 섹터를 빠르게 파악한다.
def _build_sector_snapshots() -> str:
    symbols = list(SECTOR_ETFS.keys())
    snapshots = _parallel_map_list(
        items=symbols,
        worker=_fetch_price_snapshot,
        max_workers=len(symbols),
    )
    lines = [f"- {SECTOR_ETFS[sym]} ({sym}): {snap}" for sym, snap in zip(symbols, snapshots)]
    return "\n".join(lines)


# 시나리오: 위험 뉴스를 수집해 LLM이 위험 섹터를 판단할 근거를 확보한다.
def _build_news_context() -> str:
    headlines = _fetch_tavily_news(
        "US stock market sector risk downgrade credit default margin call earnings miss 2026"
    )
    return "\n".join(f"- {h}" for h in headlines)


# 시나리오: FRED + 섹터 ETF + 뉴스를 하나의 evidence 문자열로 결합해
# LLM 프롬프트에 주입할 통합 근거 블록을 만든다.
def _build_evidence_block() -> str:
    macro = _build_macro_context()
    sectors = _build_sector_snapshots()
    news = _build_news_context()
    return f"[FRED 매크로 지표]\n{macro}\n\n[섹터 ETF 3개월 모멘텀]\n{sectors}\n\n[최신 위험 뉴스]\n{news}"


# 시나리오: GP가 risk 노드를 반려한 경우에만 수정 사유를 재생성 프롬프트에 주입한다.
# 타 노드 피드백은 무시해 컨텍스트 오염을 방지한다.
def _get_feedback_text(state: AgentState) -> str:
    feedback = state.get(StateKey.GP_FEEDBACK, {})
    if feedback.get("target_node") != AgentName.RISK:
        return "현재 GP 피드백 없음"
    return feedback.get("feedback_reason", "현재 GP 피드백 없음")


# 시나리오: API 키 없음, LLM 오류 같은 비정상 경로에서도 출력 계약을 유지한다.
# 데이터 없이도 최소한의 안전한 경고문을 반환한다.
def _build_fallback_result(state: AgentState) -> str:
    fb = _get_feedback_text(state)
    suffix = "" if fb == "현재 GP 피드백 없음" else f" GP 지적: '{fb}'"
    return (
        "현재 FRED 금리 환경과 시장 데이터를 종합하면 "
        "고금리 부담이 큰 섹터부터 우선 회피해야 합니다. "
        "구체적 데이터 확보 후 재분석이 필요합니다."
        f"{suffix}"
    )


# 시나리오: LLM 결과에서 티커 패턴을 추출해 최소 2개 이상 포함됐는지 검증한다.
# 고정 허용 목록 없이 대문자 1~5자 + 문맥 필터로 유효성을 판단한다.
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
}


# 시나리오: LLM 출력에서 실제 종목 티커를 추출한다.
# 일반 약어/노이즈를 제외하고 중복 없이 반환한다.
def _extract_tickers(text: str) -> List[str]:
    candidates = re.findall(r"\b[A-Z]{1,5}\b", text.upper())
    seen: List[str] = []
    for tok in candidates:
        if tok not in _TICKER_NOISE and tok not in seen:
            seen.append(tok)
    return seen


# 시나리오: Acceptance Criteria "대표주 2~3개" 조건을 기계적으로 확인한다.
# 검증 실패 시 재생성 분기로 라우팅한다.
def _has_enough_tickers(text: str) -> bool:
    return len(_extract_tickers(text)) >= 2


# 시나리오: 동일 프롬프트 체인으로 1차 생성과 재시도 생성을 공통 처리한다.
# 호출 시점의 evidence/피드백/재시도 지시를 주입해 본문을 생성한다.
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


# 시나리오: Risk 노드의 전체 오케스트레이션을 수행한다.
# 1) FRED/YFinance/Tavily로 evidence 수집
# 2) LLM이 데이터 기반으로 위험 섹터를 선정하고 경고문 생성
# 3) 티커 개수 검증 -> 실패 시 재생성 1회 -> 그래도 실패 시 fallback
# 4) 항상 StateKey.RISK_RESULT를 반환해 후속 노드가 안정적으로 consume
def risk_node(state: AgentState) -> Dict[str, Any]:
    macro_result = state.get(StateKey.MACRO_RESULT, "매크로 요약 없음")
    feedback_text = _get_feedback_text(state)

    if not os.getenv("OPENAI_API_KEY"):
        return {StateKey.RISK_RESULT: _build_fallback_result(state)}

    try:
        evidence = _build_evidence_block()
    except Exception:
        evidence = "데이터 수집 중 오류 발생. 가용 정보 없음."

    llm = ChatOpenAI(
        model=ModelConfig.DEFAULT_LLM_MODEL,
        temperature=ModelConfig.DEFAULT_TEMPERATURE,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", RISK_SYSTEM_PROMPT),
            (
                "user",
                "작성 기준일: {today}\n\n"
                "기존 매크로 요약:\n{macro_result}\n\n"
                "실시간 수집 데이터:\n{evidence}\n\n"
                "검수 피드백:\n{feedback_text}\n\n"
                "추가 지시:\n{retry_hint}\n\n"
                "위 데이터를 직접 분석하여 가장 위험한 섹터를 선정하고, "
                "해당 섹터의 대표 종목 2~3개를 티커와 함께 "
                "강한 어조로 경고하세요.",
            ),
        ]
    )
    chain = prompt | llm

    try:
        result = _generate_risk_text(
            chain=chain,
            evidence=evidence,
            macro_result=macro_result,
            feedback_text=feedback_text,
            retry_hint="데이터에서 근거가 확인되는 티커만 사용하라.",
        )

        if not _has_enough_tickers(result):
            result = _generate_risk_text(
                chain=chain,
                evidence=evidence,
                macro_result=macro_result,
                feedback_text=feedback_text,
                retry_hint=(
                    "직전 출력에 구체적 티커가 부족했다. "
                    "섹터 ETF 데이터와 뉴스에서 확인되는 "
                    "종목 2~3개를 반드시 티커로 명시하라."
                ),
            )

        if not _has_enough_tickers(result):
            result = _build_fallback_result(state)
    except Exception as err:
        result = f"{_build_fallback_result(state)} LLM 연결 오류: {err}"

    return {StateKey.RISK_RESULT: result}
