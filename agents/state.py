from typing import Annotated, Any, Dict, List, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from agents.constants import StateKey


class AgentState(TypedDict):
    """
    AlphaInvest LangGraph 전체 워크플로우에서 사용되는 기본 상태(State) 스키마입니다.
    여러 에이전트가 동시에 동작하더라도 상호 프롬프트가 오염되지 않도록
    메모리(messages)와 결과물(result)을 에이전트 단위로 철저히 독립/격리합니다.
    """

    # 1. 공통 입력 제원
    user_portfolio: List[Dict[str, Any]]

    # 2. 에이전트별 독립된 메모리 컨텍스트 (환각/오염 방지)
    macro_messages: Annotated[List[BaseMessage], add_messages]
    risk_messages: Annotated[List[BaseMessage], add_messages]
    alpha_messages: Annotated[List[BaseMessage], add_messages]
    portfolio_messages: Annotated[List[BaseMessage], add_messages]

    # 3. 에이전트 파편별 최종 요약 결과 (CIO 편집 및 GP 검수용)
    macro_result: str
    risk_result: str
    alpha_result: str
    portfolio_result: str

    # 4. GP(품질 검수자)의 라우팅 및 피드백용 상태
    # 예: {"target_node": "risk_agent", "feedback_reason": "금리 하방 압력 누락됨"}
    gp_feedback: Dict[str, Any]
    retry_count: int

    # 5. CIO(총괄 편집장)가 병합한 최종 퍼블리시 리포트
    final_report: str


def get_initial_state(user_portfolio: List[Dict[str, Any]]) -> AgentState:
    """
    실행 진입점(main)에서 생성하는 최초의 텅 빈 상태입니다.
    이 빈 상자가 각 노드(에이전트)를 돌아다니며 데이터로 채워지게 됩니다.
    """
    return {
        StateKey.USER_PORTFOLIO: user_portfolio,
        StateKey.MACRO_MESSAGES: [],
        StateKey.RISK_MESSAGES: [],
        StateKey.ALPHA_MESSAGES: [],
        StateKey.PORTFOLIO_MESSAGES: [],
        StateKey.MACRO_RESULT: "",
        StateKey.RISK_RESULT: "",
        StateKey.ALPHA_RESULT: "",
        StateKey.PORTFOLIO_RESULT: "",
        StateKey.GP_FEEDBACK: {},
        StateKey.RETRY_COUNT: 0,
        StateKey.FINAL_REPORT: "",
    }
