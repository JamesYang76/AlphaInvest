import os

import pytest
from dotenv import load_dotenv


def test_portfolio_agent_manual_smoke() -> None:
    if os.getenv("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("manual smoke test; set RUN_LIVE_LLM_TESTS=1 to run")

    from agents.constants import StateKey
    from agents.nodes.portfolio import portfolio_node
    from agents.state import get_initial_state
    from data.mock_data import get_portfolio

    load_dotenv()
    initial_state = get_initial_state(user_portfolio=get_portfolio())
    result = portfolio_node(initial_state)

    assert StateKey.PORTFOLIO_RESULT in result
    assert isinstance(result.get(StateKey.PORTFOLIO_RESULT, ""), str)
