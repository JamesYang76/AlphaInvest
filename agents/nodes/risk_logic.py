from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from agents.nodes.risk_fetchers import fetch_news_articles, parallel_map_list

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

TICKER_NOISE = {
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

NARRATIVE_NEGATIVE_KEYWORDS = frozenset(
    {
        "risk",
        "crash",
        "bubble",
        "overvalued",
        "regulation",
        "ban",
        "failure",
        "miss",
        "downgrade",
        "default",
        "fraud",
        "investigation",
        "decline",
        "slump",
        "plunge",
        "collapse",
        "warning",
        "concern",
    }
)

KNOWN_ETF_TICKERS = frozenset(
    {
        "SPY",
        "QQQ",
        "DIA",
        "IWM",
        "XLF",
        "XLK",
        "XLE",
        "XLI",
        "XLV",
        "XLY",
        "XLP",
        "XLU",
        "XLB",
        "XLRE",
        "SMH",
        "SOXX",
        "ARKK",
        "TAN",
        "ICLN",
        "BOTZ",
        "LIT",
        "HYG",
        "JNK",
        "TLT",
        "GLD",
        "SLV",
    }
)


def parse_llm_json(text: str) -> List[Dict[str, Any]]:
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


def normalize_theme_name(theme: Dict[str, Any]) -> str:
    name = str(theme.get("theme_name", "")).strip()
    if not name:
        return "Unknown"
    upper = name.upper()
    if upper in KNOWN_ETF_TICKERS or re.fullmatch(r"[A-Z]{2,5}", upper):
        keywords = theme.get("theme_keywords", [])
        if keywords:
            return " / ".join(keywords[:3])
    return name


def cluster_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not entities:
        return []

    count = len(entities)
    parent = list(range(count))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    ticker_index: Dict[str, List[int]] = defaultdict(list)
    for index, entity in enumerate(entities):
        for ticker in entity.get("tickers", []):
            ticker_index[ticker.upper()].append(index)

    for indices in ticker_index.values():
        for index in range(1, len(indices)):
            union(indices[0], indices[index])

    for i in range(count):
        terms_i = {term.lower() for term in entities[i].get("industry_terms", [])}
        for j in range(i + 1, count):
            terms_j = {term.lower() for term in entities[j].get("industry_terms", [])}
            if len(terms_i & terms_j) >= 2:
                union(i, j)

    groups: Dict[int, List[int]] = defaultdict(list)
    for index in range(count):
        groups[find(index)].append(index)

    clusters: List[Dict[str, Any]] = []
    for cluster_id, indices in enumerate(groups.values()):
        cluster_entities_list = [entities[index] for index in indices]
        avg_sentiment = sum(entity.get("sentiment_score", 0) for entity in cluster_entities_list) / max(len(cluster_entities_list), 1)
        clusters.append(
            {
                "cluster_id": f"cluster_{cluster_id:02d}",
                "tickers": list({ticker for entity in cluster_entities_list for ticker in entity.get("tickers", [])}),
                "companies": list({company for entity in cluster_entities_list for company in entity.get("companies", [])}),
                "industry_terms": list({term for entity in cluster_entities_list for term in entity.get("industry_terms", [])}),
                "risk_keywords": list({keyword for entity in cluster_entities_list for keyword in entity.get("risk_keywords", [])}),
                "event_types": list({entity.get("event_type", "") for entity in cluster_entities_list}),
                "news_count": len(cluster_entities_list),
                "avg_sentiment": avg_sentiment,
            }
        )
    return clusters


def _map_macro_exposure(keywords: List[str]) -> List[str]:
    joined = " ".join(keyword.lower() for keyword in keywords)
    exposures = [category for category, terms in MACRO_SENSITIVITY.items() if any(term in joined for term in terms)]
    return exposures or ["general"]


def score_cluster(
    cluster: Dict[str, Any],
    market_signals: Dict[str, Dict[str, Any]],
    macro_values: Dict[str, Optional[float]],
) -> float:
    negative_sentiment = max(-cluster.get("avg_sentiment", 0), 0)
    count_factor = min(cluster.get("news_count", 0) / 3.0, 1.0)
    news_score = negative_sentiment * 60 + count_factor * 40

    returns = [
        market_signals[ticker].get("return_60d", 0)
        for ticker in cluster.get("tickers", [])
        if ticker in market_signals and "error" not in market_signals[ticker]
    ]
    market_score = min(max(-sum(returns) / max(len(returns), 1) * 5, 0), 100) if returns else 30

    keywords = cluster.get("risk_keywords", []) + cluster.get("industry_terms", [])
    exposures = _map_macro_exposure(keywords)
    macro_score = 30.0
    fed_rate = macro_values.get("fed_funds_rate")
    spread = macro_values.get("high_yield_spread")
    if "rate_sensitive" in exposures and fed_rate and fed_rate > 4.0:
        macro_score += 35
    if "credit_sensitive" in exposures and spread and spread > 4.0:
        macro_score += 35
    if "cycle_sensitive" in exposures:
        macro_score += 15
    macro_score = min(macro_score, 100)

    return round(macro_score * 0.35 + market_score * 0.35 + news_score * 0.30, 1)


def format_clusters_evidence(
    clusters: List[Dict[str, Any]],
    market_signals: Dict[str, Dict[str, Any]],
    macro_summary: str,
) -> str:
    lines = [f"[FRED 매크로 지표]\n{macro_summary}\n"]

    for cluster in clusters[:3]:
        ticker_details = []
        for ticker in cluster.get("tickers", []):
            signal = market_signals.get(ticker, {})
            if "error" not in signal:
                detail = f"  {ticker}: 1개월 {signal.get('return_20d', '?')}%, 3개월 {signal.get('return_60d', '?')}%"
                if signal.get("drawdown_6m") is not None:
                    detail += f", 6개월 최대낙폭 {signal['drawdown_6m']}%"
                if signal.get("volatility_60d") is not None:
                    detail += f", 3개월 변동성 {signal['volatility_60d']}%"
                if signal.get("rsi_14") is not None:
                    detail += f", RSI {signal['rsi_14']}"
                if signal.get("ma20_divergence") is not None:
                    detail += f", 20MA이격 {signal['ma20_divergence']}%"
                ticker_details.append(detail)
            else:
                ticker_details.append(f"  {ticker}: 데이터 없음")

        lines.append(
            f"[위험 군집: {cluster['cluster_id']}] "
            f"(위험점수 {cluster.get('risk_score', 0)})\n"
            f"  종목: {', '.join(cluster.get('tickers', []))}\n"
            f"  산업: {', '.join(cluster.get('industry_terms', []))}\n"
            f"  리스크: {', '.join(cluster.get('risk_keywords', []))}\n"
            f"  이벤트: {', '.join(cluster.get('event_types', []))}\n"
            f"  뉴스 {cluster.get('news_count', 0)}건 | "
            f"감성 {cluster.get('avg_sentiment', 0):.2f}\n"
            f"  주가 흐름:\n" + "\n".join(ticker_details)
        )
    return "\n\n".join(lines)


def check_narrative_damage(theme_name: str) -> bool:
    query = f"{theme_name} risk regulation failure concerns setback 2026"
    articles = fetch_news_articles(query, max_results=5)
    if not articles:
        return False
    hit_count = 0
    for article in articles:
        text_lower = f"{article.get('title', '')} {article.get('content', '')}".lower()
        if any(keyword in text_lower for keyword in NARRATIVE_NEGATIVE_KEYWORDS):
            hit_count += 1
    return hit_count >= 3


def _is_technically_overheated(
    theme: Dict[str, Any],
    signals: Dict[str, Dict[str, Any]],
) -> bool:
    tickers = theme.get("leader_stocks", []) or theme.get("representative_etfs", [])
    for ticker in tickers:
        signal = signals.get(ticker, {})
        if "error" in signal:
            continue
        rsi = signal.get("rsi_14")
        ma_div = signal.get("ma20_divergence")
        if (rsi is not None and rsi > 75) or (ma_div is not None and ma_div > 10):
            return True
    return False


def _assess_macro_headwind(
    theme: Dict[str, Any],
    macro_values: Dict[str, Optional[float]],
) -> bool:
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


def score_themes(
    themes: List[Dict[str, Any]],
    signals: Dict[str, Dict[str, Any]],
    macro_values: Dict[str, Optional[float]],
) -> List[Dict[str, Any]]:
    if not themes:
        return []

    damage_results = parallel_map_list(
        items=[theme.get("theme_name", "") for theme in themes],
        worker=check_narrative_damage,
        max_workers=min(len(themes), 5),
    )

    scored: List[Dict[str, Any]] = []
    for index, theme in enumerate(themes):
        flags: List[str] = []
        if _is_technically_overheated(theme, signals):
            flags.append("기술적 과열")
        if _assess_macro_headwind(theme, macro_values):
            flags.append("매크로 역행")
        if index < len(damage_results) and damage_results[index]:
            flags.append("내러티브 훼손")

        flag_count = len(flags)
        if flag_count >= 2:
            decision = "CRITICAL"
        elif flag_count == 1:
            decision = "CAUTION"
        else:
            decision = "WATCH"

        scored.append({**theme, "risk_flags": flags, "decision": decision})

    scored.sort(key=lambda item: len(item["risk_flags"]), reverse=True)
    return scored


def format_theme_evidence(
    themes: List[Dict[str, Any]],
    signals: Dict[str, Dict[str, Any]],
) -> str:
    if not themes:
        return ""

    lines = ["\n[테마 기반 하방 리스크 분석]"]
    for theme in themes:
        decision = theme.get("decision", "WATCH")
        flags = ", ".join(theme.get("risk_flags", [])) or "없음"
        keywords = ", ".join(theme.get("theme_keywords", [])) or "N/A"
        etfs = ", ".join(theme.get("representative_etfs", [])) or "N/A"
        leaders = ", ".join(theme.get("leader_stocks", [])) or "N/A"

        ticker_details: List[str] = []
        for ticker in theme.get("representative_etfs", []) + theme.get("leader_stocks", []):
            signal = signals.get(ticker, {})
            if "error" not in signal:
                detail = f"    {ticker}: RSI {signal.get('rsi_14', '?')}"
                detail += f", 20MA이격 {signal.get('ma20_divergence', '?')}%"
                detail += f", 1개월 {signal.get('return_20d', '?')}%"
                detail += f", 3개월 {signal.get('return_60d', '?')}%"
                ticker_details.append(detail)

        lines.append(
            f"\n  테마: {theme.get('theme_name', '?')} [{decision}]\n"
            f"  유형: {theme.get('theme_type', '?')}\n"
            f"  키워드: {keywords}\n"
            f"  구조적 동인: {theme.get('structural_driver', '?')}\n"
            f"  위험 플래그: {flags}\n"
            f"  대표 ETF: {etfs}\n"
            f"  대장주: {leaders}\n"
            f"  기술적 지표:\n" + "\n".join(ticker_details)
        )
    return "\n".join(lines)


def build_fallback_result() -> str:
    return "현재 FRED 금리 환경과 시장 데이터를 종합하면 고금리 부담이 큰 섹터부터 우선 회피해야 합니다. 구체적 데이터 확보 후 재분석이 필요합니다."


def extract_tickers(text: str) -> List[str]:
    candidates = re.findall(r"\b[A-Z]{1,5}\b", text.upper())
    seen: List[str] = []
    for token in candidates:
        if token not in TICKER_NOISE and token not in seen:
            seen.append(token)
    return seen


def has_enough_tickers(text: str) -> bool:
    return len(extract_tickers(text)) >= 2


def has_required_risk_format(text: str) -> bool:
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

    seen_ranks = {match.group(1) for match in matches}
    if seen_ranks != {"1", "2", "3"}:
        return False

    for match in matches:
        related = match.group(3)
        if "ETF" in related.upper():
            return False
        if len(extract_tickers(related)) < 2:
            return False
        reason = match.group(4).strip()
        reason_lines = [line for line in reason.splitlines() if line.strip()]
        if len(reason_lines) < 5:
            return False
    return True
