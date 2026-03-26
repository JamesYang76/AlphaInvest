from __future__ import annotations

from typing import Any, Dict, List

from dotenv import load_dotenv

from agents.constants import StateKey
from agents.nodes.alpha import alpha_node
from agents.nodes.cio import cio_node
from agents.nodes.gp import gp_node
from agents.nodes.macro import macro_node
from agents.nodes.portfolio import portfolio_node
from agents.nodes.risk import risk_node
from agents.state import AgentState, get_initial_state

load_dotenv()


def _merge_state(state: AgentState, updates: Dict[str, Any]) -> AgentState:
    state.update(updates)
    return state


def build_portfolio_report(user_portfolio: List[Dict[str, Any]]) -> Dict[str, str]:
    if not user_portfolio:
        return {"portfolio_label": "", "report": "", "error": "보유 종목을 입력해주세요."}

    portfolio_label = ", ".join(str(item.get("ticker", "")).upper() for item in user_portfolio if item.get("ticker"))
    state = get_initial_state(user_portfolio=user_portfolio)
    execution_chain = [macro_node, gp_node, portfolio_node, gp_node, risk_node, gp_node, alpha_node, gp_node, cio_node]

    try:
        final_state = [_merge_state(state, node(state)) for node in execution_chain][-1]
        return {
            "portfolio_label": portfolio_label,
            "report": str(final_state.get(StateKey.FINAL_REPORT, "")).strip(),
            "error": "",
        }
    except Exception as exc:
        return {
            "portfolio_label": portfolio_label,
            "report": "",
            "error": f"리포트 생성 중 오류가 발생했습니다: {exc}",
        }
