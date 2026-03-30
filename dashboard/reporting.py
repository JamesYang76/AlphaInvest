from __future__ import annotations

from collections.abc import Callable
from typing import Any, Dict, List

from dotenv import load_dotenv

from agents.constants import StateKey
from agents.nodes.alpha import alpha_node
from agents.nodes.chart import chart_node
from agents.nodes.cio import build_final_report, cio_node
from agents.nodes.gp import gp_node
from agents.nodes.macro import macro_node
from agents.nodes.portfolio import portfolio_node
from agents.nodes.risk import risk_node
from agents.state import AgentState, get_initial_state
from utils.logger import get_logger
from utils.timing import elapsed_ms, format_elapsed_ms, start_timer

load_dotenv()
logger = get_logger("dashboard.reporting")


def _merge_state(state: AgentState, updates: Dict[str, Any]) -> AgentState:
    state.update(updates)
    return state


def _build_execution_chain(fast_mode: bool, include_portfolio: bool) -> List[Any]:
    if fast_mode:
        chain: List[Any] = [macro_node]
        if include_portfolio:
            chain.append(portfolio_node)
        chain.extend([chart_node, risk_node, alpha_node])
        return chain

    chain = [macro_node, gp_node]
    if include_portfolio:
        chain.extend([portfolio_node, gp_node])
    chain.extend([chart_node, gp_node, risk_node, gp_node, alpha_node, gp_node, cio_node])
    return chain


def _run_full_pipeline(
    user_portfolio: List[Dict[str, Any]],
    portfolio_label: str,
    fast_mode: bool = True,
    include_portfolio: bool = True,
    progress_callback: Callable[[str], None] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> Dict[str, Any]:
    """거시 → 포트폴리오(또는 빈 보유) → 차트 → 리스크 → 알파 → CIO."""
    pipeline_started_at = start_timer()
    state = get_initial_state(user_portfolio=user_portfolio)
    state[StateKey.FAST_MODE] = fast_mode
    state[StateKey.RUNTIME_PROGRESS_CALLBACK] = progress_callback
    state[StateKey.RUNTIME_CANCEL_CHECK] = cancel_check
    execution_chain = _build_execution_chain(fast_mode=fast_mode, include_portfolio=include_portfolio)

    try:
        final_state: AgentState = state
        step_timings: List[tuple[str, float]] = []
        for node in execution_chain:
            if progress_callback is not None:
                progress_callback(node.__name__)
            step_started_at = start_timer()
            final_state = _merge_state(state, node(state))
            duration_ms = elapsed_ms(step_started_at)
            step_timings.append((node.__name__, duration_ms))
            logger.info("[Timing] pipeline step=%s mode=%s duration=%.1fms", node.__name__, "fast" if fast_mode else "full", duration_ms)
        if fast_mode:
            if progress_callback is not None:
                progress_callback("build_final_report")
            refine_started_at = start_timer()
            final_state = _merge_state(state, {StateKey.FINAL_REPORT: build_final_report(state, refine=False)})
            duration_ms = elapsed_ms(refine_started_at)
            step_timings.append(("build_final_report", duration_ms))
            logger.info("[Timing] pipeline step=build_final_report mode=fast duration=%.1fms", duration_ms)
        summary = ", ".join(f"{name}={duration:.1f}ms" for name, duration in step_timings)
        logger.info(
            "[Timing] pipeline total mode=%s holdings=%d duration=%s steps=[%s]",
            "fast" if fast_mode else "full",
            len(user_portfolio),
            format_elapsed_ms(pipeline_started_at),
            summary,
        )
        return {
            "portfolio_label": portfolio_label,
            "report": str(final_state.get(StateKey.FINAL_REPORT, "")).strip(),
            "error": "",
            "mode": "fast" if fast_mode else "full",
            "pipeline_snapshot": {
                "macro_data": final_state.get(StateKey.MACRO_DATA, {}),
                "chart_data": final_state.get(StateKey.CHART_DATA, {}),
                "news_snippet": str(final_state.get(StateKey.MARKET_NEWS_SNIPPET, "")).strip(),
            },
        }
    except Exception as exc:
        logger.exception(
            "[Timing] pipeline failed mode=%s holdings=%d duration=%s error=%s",
            "fast" if fast_mode else "full",
            len(user_portfolio),
            format_elapsed_ms(pipeline_started_at),
            exc,
        )
        return {
            "portfolio_label": portfolio_label,
            "report": "",
            "error": f"리포트 생성 중 오류가 발생했습니다: {exc}",
            "mode": "fast" if fast_mode else "full",
            "pipeline_snapshot": {},
        }


def build_market_report(
    fast_mode: bool = True,
    progress_callback: Callable[[str], None] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> Dict[str, Any]:
    """
    보유 종목 없이 시장 전체 리포트.
    거시 지표 → 섹터·차트(yfinance 벤치마크) → 뉴스(에이전트 경로) → 위험/추천 섹터(CIO 최종본).
    """
    label = "시장 전체 (보유 종목 없음)"
    return _run_full_pipeline(
        [],
        label,
        fast_mode=fast_mode,
        include_portfolio=False,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )


def build_portfolio_report(
    user_portfolio: List[Dict[str, Any]],
    fast_mode: bool = True,
    progress_callback: Callable[[str], None] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> Dict[str, Any]:
    if not user_portfolio:
        return {
            "portfolio_label": "",
            "report": "",
            "error": "보유 종목을 입력해주세요.",
            "mode": "fast" if fast_mode else "full",
            "pipeline_snapshot": {},
        }

    portfolio_label = ", ".join(str(item.get("ticker", "")).upper() for item in user_portfolio if item.get("ticker"))
    return _run_full_pipeline(
        user_portfolio,
        portfolio_label,
        fast_mode=fast_mode,
        include_portfolio=True,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
