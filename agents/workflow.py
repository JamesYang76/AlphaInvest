from langgraph.graph import END, START, StateGraph

from agents.constants import AgentName, StateKey
from agents.nodes.alpha import alpha_node
from agents.nodes.cio import cio_node
from agents.nodes.gp import gp_node
from agents.nodes.macro import macro_node
from agents.nodes.portfolio import portfolio_node
from agents.nodes.risk import risk_node
from agents.state import AgentState
from utils.logger import get_logger

logger = get_logger("agents.workflow")


def gp_router(state: AgentState) -> str:
    """
    GP 판단에 따라 다음 노드를 결정합니다 (Sequential Phase Controller).
    📌 최종 확정 순서: Macro -> Portfolio -> Risk -> Alpha -> CIO
    """
    feedback = state.get(StateKey.GP_FEEDBACK, {})
    retry_count = state.get(StateKey.RETRY_COUNT, 0)
    last_node = state.get("last_node")

    # 1. 반려된 경우 해당 에이전트로 유턴 (최대 1회 리트라이 허용)
    if not feedback.get("is_pass", True) and retry_count < 2:
        logger.warning(f"  ↪️ [반려 발생] {last_node}로 돌아갑니다. (현재 리트라이: {retry_count}회)")
        return last_node

    # 2. 통과 시 다음 단계(Phase) 노드 결정 (중앙 집중 관리)
    phase_order = [
        AgentName.MACRO,  # 1단계: 거시 환경 판세 읽기
        AgentName.PORTFOLIO,  # 2단계: 최신 판세 기반 계좌 진단
        AgentName.RISK,  # 3단계: 리스크 정밀 스캔
        AgentName.ALPHA,  # 4단계: 최종 유망 섹터(기회) 발굴
    ]

    try:
        current_idx = phase_order.index(last_node)
        if current_idx + 1 < len(phase_order):
            next_node = phase_order[current_idx + 1]
            logger.info(f"  ➡️ {last_node} 단계 통과! -> {next_node}로 이동합니다.")
            return next_node
    except (ValueError, IndexError):
        pass

    # 마지막 단계(Alpha)까지 통과하면 CIO 리포트 합성으로 이동
    logger.info("  🏁 [최종 관문 통과] 모든 검수 완료. 최종 리포트를 합성합니다.")
    return AgentName.CIO


def build_skeleton() -> StateGraph:
    """
    ==========================================================
    📌 AlphaInvest 파이프라인 흐름도 (Sequential Flow)
    ==========================================================
    순서: Macro -> Portfolio -> Risk -> Alpha -> CIO
    각 단계 완료 후 GP의 논리 검수를 통과해야만 다음 단계로 진행합니다.
    """
    builder = StateGraph(AgentState)

    # 1. 노드 부착
    builder.add_node(AgentName.MACRO, macro_node)
    builder.add_node(AgentName.RISK, risk_node)
    builder.add_node(AgentName.ALPHA, alpha_node)
    builder.add_node(AgentName.PORTFOLIO, portfolio_node)
    builder.add_node(AgentName.GP, gp_node)
    builder.add_node(AgentName.CIO, cio_node)

    # 2. 시작점 설정
    builder.add_edge(START, AgentName.MACRO)

    # 3. 각 에이전트 완료 후 GP 검수대로 이동
    agents = [AgentName.MACRO, AgentName.PORTFOLIO, AgentName.RISK, AgentName.ALPHA]
    for agent in agents:
        builder.add_edge(agent, AgentName.GP)

    # 4. GP 분기 로직 (최신 시퀀스 기반 매핑)
    builder.add_conditional_edges(
        AgentName.GP,
        gp_router,
        {
            AgentName.MACRO: AgentName.MACRO,  # Macro 반려 시 재실행
            AgentName.PORTFOLIO: AgentName.PORTFOLIO,  # Macro 통과 OR Portfolio 반려 시
            AgentName.RISK: AgentName.RISK,  # Portfolio 통과 OR Risk 반려 시
            AgentName.ALPHA: AgentName.ALPHA,  # Risk 통과 OR Alpha 반려 시
            AgentName.CIO: AgentName.CIO,  # Alpha 통합 통과 시 최종 리포트 작성
        },
    )

    # 5. 최종 리포트 합성이 끝나면 종료
    builder.add_edge(AgentName.CIO, END)

    return builder.compile()
