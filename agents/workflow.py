from langgraph.graph import END, START, StateGraph

from agents.constants import AgentName
from agents.nodes.alpha import alpha_node
from agents.nodes.cio import cio_node
from agents.nodes.gp import gp_node, gp_router
from agents.nodes.macro import macro_node
from agents.nodes.portfolio import portfolio_node
from agents.nodes.risk import risk_node
from agents.state import AgentState


def build_skeleton() -> StateGraph:
    """
    ==========================================================
    📌 AlphaInvest 파이프라인 흐름도 (Graph Builder)
    ==========================================================
    """
    builder = StateGraph(AgentState)

    # 1. 노드 부착
    builder.add_node(AgentName.MACRO, macro_node)
    builder.add_node(AgentName.RISK, risk_node)
    builder.add_node(AgentName.ALPHA, alpha_node)
    builder.add_node(AgentName.PORTFOLIO, portfolio_node)
    builder.add_node(AgentName.GP, gp_node)
    builder.add_node(AgentName.CIO, cio_node)

    # 2. 엣지 연결 (병렬 진행 방식 - Fan-out & Fan-in)
    # START에서 4명의 에이전트가 동시에 출발합니다.
    parallel_agents = [AgentName.MACRO, AgentName.RISK, AgentName.ALPHA, AgentName.PORTFOLIO]
    for agent in parallel_agents:
        builder.add_edge(START, agent)  # 동시 시작!
        builder.add_edge(agent, AgentName.GP)  # 작업 완료 시 GP로 집결 (대기)

    # 3. GP 분기
    builder.add_conditional_edges(
        AgentName.GP,
        gp_router,
        {
            AgentName.CIO: AgentName.CIO,
            AgentName.MACRO: AgentName.MACRO,
            AgentName.RISK: AgentName.RISK,
            AgentName.ALPHA: AgentName.ALPHA,
            AgentName.PORTFOLIO: AgentName.PORTFOLIO,
        },
    )

    builder.add_edge(AgentName.CIO, END)

    return builder.compile()
