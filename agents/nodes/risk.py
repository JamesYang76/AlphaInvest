from __future__ import annotations

import datetime
import os
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agents.constants import AgentName, ModelConfig, StateKey
from agents.nodes.risk_fetchers import (
    article_source_links,
    attach_market_signals,
    build_macro_context,
    enrich_theme_signals,
    fetch_news_articles,
    fetch_theme_news,
)
from agents.nodes.risk_logic import (
    build_fallback_result,
    cluster_entities,
    format_clusters_evidence,
    format_theme_evidence,
    has_enough_tickers,
    has_required_risk_format,
    normalize_theme_name,
    parse_llm_json,
    score_cluster,
    score_themes,
)
from agents.nodes.risk_prompts import ENTITY_EXTRACTION_PROMPT, RISK_SYSTEM_PROMPT, THEME_DETECTION_PROMPT
from agents.nodes.runtime_status import notify_runtime_progress
from agents.state import AgentState
from data.fetchers import merge_report_source_links


def _extract_risk_entities(articles: List[Dict[str, str]], llm: Any) -> List[Dict[str, Any]]:
    if not articles:
        return []

    text = "\n\n".join(f"[기사 {index + 1}] {article['title']}\n{article['content']}" for index, article in enumerate(articles))
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ENTITY_EXTRACTION_PROMPT),
            ("user", "{articles}"),
        ]
    )
    try:
        response = (prompt | llm).invoke({"articles": text})
        entities = parse_llm_json(response.content)
        for entity in entities:
            entity.setdefault("tickers", [])
            entity.setdefault("companies", [])
            entity.setdefault("industry_terms", [])
            entity.setdefault("risk_keywords", [])
            entity.setdefault("event_type", "unknown")
            entity.setdefault("sentiment_score", 0.0)
        return entities
    except Exception:
        return []


def _extract_themes(articles: List[Dict[str, str]], llm: Any) -> List[Dict[str, Any]]:
    if not articles:
        return []

    text = "\n\n".join(f"[기사 {index + 1}] {article['title']}\n{article['content']}" for index, article in enumerate(articles))
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", THEME_DETECTION_PROMPT),
            ("user", "{articles}"),
        ]
    )
    try:
        response = (prompt | llm).invoke({"articles": text})
        themes = parse_llm_json(response.content)
        for theme in themes:
            theme.setdefault("theme_name", "Unknown")
            theme.setdefault("theme_type", "growth")
            theme.setdefault("theme_keywords", [])
            theme.setdefault("representative_etfs", [])
            theme.setdefault("leader_stocks", [])
            theme.setdefault("structural_driver", "")
            theme.setdefault("sentiment", "mixed")
            theme["theme_name"] = normalize_theme_name(theme)
        return themes[:5]
    except Exception:
        return []


def _generate_risk_text(
    chain: Any,
    evidence: str,
    macro_result: str,
    retry_hint: str,
) -> str:
    response = chain.invoke(
        {
            "evidence": evidence,
            "macro_result": macro_result,
            "retry_hint": retry_hint,
            "today": datetime.datetime.now().strftime("%Y-%m-%d"),
        }
    )
    return response.content


def _overlay_macro_values(
    macro_values: Dict[str, Optional[float]],
    macro_data: Dict[str, Any],
) -> Dict[str, Optional[float]]:
    def _as_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace("%", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    overlaid = dict(macro_values)
    fed_rate = _as_float(macro_data.get("d_fed_rate")) or _as_float(macro_data.get("fed_rate"))
    ten_year = _as_float(macro_data.get("ten_year_yield"))
    hy_spread = _as_float(macro_data.get("high_yield_spread"))

    if fed_rate is not None:
        overlaid["fed_funds_rate"] = fed_rate
    if ten_year is not None:
        overlaid["ten_year_yield"] = ten_year
    if hy_spread is not None:
        overlaid["high_yield_spread"] = hy_spread
    return overlaid


def risk_node(state: AgentState) -> Dict[str, Any]:
    macro_result = state.get(StateKey.MACRO_RESULT, "매크로 요약 없음")

    if not os.getenv("OPENAI_API_KEY"):
        fallback = build_fallback_result()
        return {
            StateKey.RISK_RESULT: fallback,
            StateKey.CURRENT_REPORT: fallback,
            "last_node": AgentName.RISK,
        }

    llm = ChatOpenAI(
        model=ModelConfig.DEFAULT_LLM_MODEL,
        temperature=ModelConfig.DEFAULT_TEMPERATURE,
        timeout=25,
        max_retries=1,
    )

    notify_runtime_progress(state, "risk_build_macro_context")
    macro = build_macro_context()
    if isinstance(macro_result, str) and macro_result.strip() and macro_result != "매크로 요약 없음":
        macro["summary"] = macro_result

    macro_values = macro.get("values", {})
    macro_data = state.get(StateKey.MACRO_DATA, {})
    if isinstance(macro_data, dict) and macro_data:
        macro_values = _overlay_macro_values(macro_values, macro_data)
        macro["values"] = macro_values

    notify_runtime_progress(state, "risk_fetch_news")
    articles = fetch_news_articles(
        "US stock market sector risk downgrade credit default earnings miss refinancing pressure 2026"
    )
    theme_articles = fetch_theme_news()

    notify_runtime_progress(state, "risk_extract_entities")
    entities = _extract_risk_entities(articles, llm)
    themes = _extract_themes(theme_articles, llm)

    notify_runtime_progress(state, "risk_fetch_signals")
    market_signals = attach_market_signals(entities)
    theme_signals = enrich_theme_signals(themes)

    notify_runtime_progress(state, "risk_score_clusters")
    clusters = cluster_entities(entities)
    for cluster in clusters:
        cluster["risk_score"] = score_cluster(cluster, market_signals, macro_values)
    clusters.sort(key=lambda item: item["risk_score"], reverse=True)
    clusters = [
        cluster
        for cluster in clusters
        if cluster.get("news_count", 0) >= 2 or len(cluster.get("tickers", [])) >= 2
    ]

    scored_themes = score_themes(themes, theme_signals, macro_values)

    cluster_evidence = format_clusters_evidence(clusters, market_signals, macro.get("summary", ""))
    theme_evidence = format_theme_evidence(scored_themes, theme_signals)
    combined_evidence = f"{cluster_evidence}\n\n{theme_evidence}" if theme_evidence else cluster_evidence

    chart_result = state.get(StateKey.CHART_RESULT, "")
    if isinstance(chart_result, str) and chart_result.strip():
        combined_evidence = f"{combined_evidence}\n\n[기술적 차트 요약]\n{chart_result}"

    notify_runtime_progress(state, "risk_write_report")
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", RISK_SYSTEM_PROMPT),
            (
                "user",
                "작성 기준일: {today}\n\n"
                "기존 매크로 요약:\n{macro_result}\n\n"
                "위험 군집 + 테마 분석 결과:\n{evidence}\n\n"
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
                "- 각 순위의 관련종목은 정확히 2개만 작성할 것(ETF 금지).\n"
                "- 리스크 근거는 각 순위 블록의 마지막(3번)에 배치할 것.\n"
                "- 각 순위의 리스크 근거는 줄바꿈 기준 최소 5줄로 작성할 것.\n"
                "- 각 순위의 리스크 근거 5줄 중 최소 1줄은 기술적 차트(RSI, 3개월 모멘텀, 3개월 변동성, 6개월 Drawdown 등)를 직접 언급할 것.\n"
                "- 위험섹터/테마명은 ETF 티커명 대신 산업/서사 중심 이름으로 작성할 것.\n"
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
            retry_hint=(
                "1위~3위 반복 형식을 엄격히 지켜라. "
                "각 순위는 1.위험섹터/테마 2.관련종목 3.리스크 근거 순서를 따르라. "
                "관련종목은 종목명(티커) 2개만 작성하라. "
                "리스크 근거는 각 순위별로 최소 5줄을 작성하라. "
                "각 순위마다 최소 1줄은 RSI/3개월 모멘텀/3개월 변동성/6개월 Drawdown 등 차트 지표를 직접 언급하라."
            ),
        )

        if not (has_enough_tickers(result) and has_required_risk_format(result)):
            result = _generate_risk_text(
                chain=chain,
                evidence=combined_evidence,
                macro_result=macro_result,
                retry_hint=(
                    "직전 출력이 형식 기준을 만족하지 않았다. "
                    "반드시 1위/2위/3위 세 블록을 작성하고, "
                    "각 블록에서 1.위험섹터/테마 2.관련종목 3.리스크 근거 순서를 지켜라. "
                    "관련종목은 종목명(티커) 2개만 허용된다. "
                    "각 블록의 리스크 근거는 줄바꿈 포함 최소 5줄이어야 한다. "
                    "각 블록의 근거 5줄 중 최소 1줄은 RSI/3개월 모멘텀/3개월 변동성/6개월 Drawdown 등 차트 지표를 직접 포함하라."
                ),
            )

        if not (has_enough_tickers(result) and has_required_risk_format(result)):
            result = build_fallback_result()
    except Exception as err:
        result = f"{build_fallback_result()} LLM 연결 오류: {err}"

    risk_sources = article_source_links(articles, "[리스크 뉴스]") + article_source_links(
        theme_articles,
        "[리스크·테마 뉴스]",
    )
    merged_sources = merge_report_source_links(state.get(StateKey.REPORT_SOURCE_LINKS), risk_sources)

    return {
        StateKey.RISK_RESULT: result,
        StateKey.CURRENT_REPORT: result,
        StateKey.REPORT_SOURCE_LINKS: merged_sources,
        "last_node": AgentName.RISK,
    }
