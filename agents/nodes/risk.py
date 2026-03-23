from typing import Any, Dict

from agents.constants import StateKey
from agents.state import AgentState


def risk_node(state: AgentState) -> Dict[str, Any]:
    return {
        StateKey.RISK_RESULT: (
            "엔비디아의 단기 밸류에이션 부담이 가중되고 있으며, 차익 실현 매물이 출회될 가능성이 큽니다."
        )
    }
