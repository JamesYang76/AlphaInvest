from agents.constants import StateKey
from agents.state import get_initial_state
from agents.workflow import build_skeleton
from data.mock_data import get_portfolio
from utils.logger import get_logger

logger = get_logger("main")


def main():
    logger.info("🚀 AlphaInvest 에이전트 실행을 시작합니다...")

    # 1. 그래프 빌드 및 시각화
    app = build_skeleton()

    # 그래프 시각화는 주석 처리
    # export_graph_visualization(app)

    # 2. 파이프라인 구동 (Streaming Mode)
    logger.info("📡 AlphaInvest 분석 엔진 실시간 스트리밍 시작...")

    initial_state = get_initial_state(user_portfolio=get_portfolio())

    final_state = initial_state
    for step in app.stream(initial_state, stream_mode="updates"):
        for node_name, updated_values in step.items():
            logger.info(f"--- [ {node_name} ] 작업 완료 ---")
            final_state.update(updated_values)  # 상태 누적 업데이트

            # 실시간 진행 상황 요약
            for key, val in updated_values.items():
                match key:
                    case StateKey.MACRO_RESULT:
                        logger.info(f"🔍 시황 요약: {val[:50]}...")
                    case StateKey.RISK_RESULT:
                        logger.info(f"🛑 리스크 알림: {val[:50]}...")
                    case StateKey.PORTFOLIO_RESULT:
                        logger.info(f"💼 포트폴리오 진단 완료: {val[:50]}...")
                    case StateKey.FINAL_REPORT:
                        logger.info("📝 최종 리포트 작성이 완료되었습니다.")

    # 3. 결과 출력
    logger.info("✅ 모든 분석 생중계가 완료되었습니다!")
    logger.info(f"최종 투입 포트폴리오: {final_state.get('user_portfolio', [])}")
    logger.info(f"[CIO 최종 리포트 초안]:\n{final_state.get('final_report', '')}")
    logger.info(f"[GP 검수 루프 횟수]: {final_state.get('retry_count', 0)}회")


if __name__ == "__main__":
    main()
