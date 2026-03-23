from typing import Any, Dict

from agents.constants import StateKey
from agents.state import AgentState


def portfolio_node(state: AgentState) -> Dict[str, Any]:
    return {
        StateKey.PORTFOLIO_RESULT: "현재 삼성전자 평단가 대비 추가 하락 방어를 위해, "
        "비중의 30%를 HBM 밸류체인(SK하이닉스 등) 및 전력기기 주도주로 리밸런싱할 것을 권고합니다."
    }
