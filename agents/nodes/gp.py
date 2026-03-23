from typing import Any, Dict

from agents.constants import AgentName, StateKey
from agents.state import AgentState


def gp_node(state: AgentState) -> Dict[str, Any]:
    # 무한 루프 방지: 1회 이상 재시도 시 무조건 Pass 시킴
    retry_count = state.get(StateKey.RETRY_COUNT, 0)
    if retry_count < 1:
        # 처음 진입 시 Risk Agent를 지목하여 고의로 반려(Fail)시킴 (테스트 목적)
        return {
            StateKey.GP_FEEDBACK: {
                "target_node": AgentName.RISK,
                "feedback_reason": "위험 관리 지표 논리가 부실합니다.",
            },
            StateKey.RETRY_COUNT: retry_count + 1,
        }
    return {StateKey.GP_FEEDBACK: {}, StateKey.RETRY_COUNT: retry_count}


def gp_router(state: AgentState) -> str:
    """GP 판단(State의 gp_feedback 존부)에 따라 다음 이동할 노드를 문자열로 반환합니다."""
    gp_feedback = state.get(StateKey.GP_FEEDBACK, {})
    if not gp_feedback:
        return AgentName.CIO  # 반려 내용이 없으면 CIO(편집장)로 PASS

    # 반려 내용이 있다면 해당 오류를 낸 타겟 에이전트로 명시적 되돌림(Re-run)
    return gp_feedback.get("target_node", AgentName.CIO)
