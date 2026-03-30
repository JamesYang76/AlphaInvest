import os

import pytest


def test_risk_node_manual_smoke() -> None:
    if os.getenv("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("manual smoke test; set RUN_LIVE_LLM_TESTS=1 to run")

    from agents.constants import StateKey
    from agents.nodes.macro import macro_node
    from agents.nodes.risk import risk_node
    from agents.state import get_initial_state
    from data.mock_data import get_portfolio

    state = get_initial_state(user_portfolio=get_portfolio())
    macro_output = macro_node(state)
    state[StateKey.MACRO_RESULT] = str(macro_output.get(StateKey.MACRO_RESULT, "")).strip()

    result = risk_node(state)

    assert StateKey.RISK_RESULT in result
    assert isinstance(result.get(StateKey.RISK_RESULT, ""), str)
