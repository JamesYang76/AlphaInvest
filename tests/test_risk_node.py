import argparse
import json
from typing import Any, Dict

from agents.constants import AgentName, StateKey
from agents.nodes.macro import macro_node
from agents.nodes.risk import risk_node
from agents.state import AgentState, get_initial_state
from data.mock_data import get_portfolio


def _build_state(macro_result: str, feedback_reason: str) -> AgentState:
    state = get_initial_state(user_portfolio=get_portfolio())
    state[StateKey.MACRO_RESULT] = macro_result
    if feedback_reason:
        state[StateKey.GP_FEEDBACK] = {
            "target_node": AgentName.RISK,
            "feedback_reason": feedback_reason,
        }
    return state


def _print_result(result: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print("\n=== risk_node result ===")
    print(result.get(StateKey.RISK_RESULT, ""))


def _resolve_macro_result(macro_source: str, fallback_macro_result: str) -> str:
    if macro_source == "static":
        return fallback_macro_result

    temp_state = get_initial_state(user_portfolio=get_portfolio())
    macro_output = macro_node(temp_state)
    live_macro = str(macro_output.get(StateKey.MACRO_RESULT, "")).strip()
    return live_macro or fallback_macro_result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run risk_node in isolation for quick manual testing.",
    )
    parser.add_argument(
        "--macro-result",
        default="미국 금리 고점권 유지, 하이일드 스프레드 확대 조짐.",
        help="Fallback macro_result when --macro-source=live fails.",
    )
    parser.add_argument(
        "--macro-source",
        choices=["live", "static"],
        default="live",
        help="Macro input source: live(macro_node) or static(--macro-result).",
    )
    parser.add_argument(
        "--feedback-reason",
        default="",
        help="Optional GP feedback reason targeting risk agent.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw returned dict as JSON.",
    )
    args = parser.parse_args()

    macro_result = _resolve_macro_result(args.macro_source, args.macro_result)
    state = _build_state(macro_result=macro_result, feedback_reason=args.feedback_reason)
    result = risk_node(state)
    _print_result(result, as_json=args.json)


if __name__ == "__main__":
    main()
