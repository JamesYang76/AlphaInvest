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
    macro_data: Dict[str, Any]  # 💡 원시 거시경제 지표 저장 (에이전트 간 중복 방지)
    risk_result: str
    alpha_result: str
    portfolio_result: str
    current_report: str  # 💡 GP 검수용 공통 리포트

    last_node: str  # 💡 현재 실행 중인/실행 완료된 노드를 추적합니다.

    # 5. CIO(총괄 편집장)가 병합한 최종 퍼블리시 리포트
    final_report: str

    # 6. Notion 발행 결과
    notion_page_url: str

    # 7. 리포트 하단 출처 (label + url 딕셔너리 리스트, 노드별 누적·중복 URL 제거)
    report_source_links: List[Dict[str, str]]


# 시나리오: 파이프라인 시작 직전(main·벤치마크) — user_portfolio만 채운 빈 AgentState를 만들어 이후 노드가 macro_result 등을 덧쌓을 수 있게 한다.
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
        StateKey.MACRO_DATA: {},
        StateKey.RISK_RESULT: "",
        StateKey.ALPHA_RESULT: "",
        StateKey.PORTFOLIO_RESULT: "",
        StateKey.CURRENT_REPORT: "",
        StateKey.FINAL_REPORT: "",
        StateKey.NOTION_PAGE_URL: "",
        StateKey.REPORT_SOURCE_LINKS: [],
    }
