from dotenv import load_dotenv

from agents.constants import StateKey
from agents.nodes.portfolio import portfolio_node
from agents.state import get_initial_state
from data.mock_data import get_portfolio


def test_portfolio_agent():
    load_dotenv()  # .env 로드
    print("🚀 [TEST] 포트폴리오 에이전트 단독 실행 테스트를 시작합니다...\n")

    # 1. 초기 상태 세팅 (Mock 포트폴리오 사용)
    initial_state = get_initial_state(user_portfolio=get_portfolio())
    print(f"📦 입력 포트폴리오: {initial_state[StateKey.USER_PORTFOLIO]}")

    # 2. 포트폴리오 노드 단독 호출
    print("\n⏳ 에이전트가 포트폴리오를 진단 중입니다 (LLM 호출 방어선 포함)...")
    result = portfolio_node(initial_state)

    # 3. 결과 출력
    print("\n✅ [진단 결과]")
    print("=" * 60)
    print(result.get(StateKey.PORTFOLIO_RESULT, "결과가 없습니다."))
    print("=" * 60)


if __name__ == "__main__":
    test_portfolio_agent()
