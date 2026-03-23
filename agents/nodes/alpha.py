from typing import Any, Dict

from agents.constants import StateKey
from agents.state import AgentState


def alpha_node(state: AgentState) -> Dict[str, Any]:
    return {StateKey.ALPHA_RESULT: "상대적으로 저평가된 헬스케어 및 K-뷰티 수출주로 자금 이동이 관찰됩니다."}
