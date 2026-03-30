from dotenv import load_dotenv

from agents.constants import StateKey
from agents.state import get_initial_state
from agents.workflow import build_skeleton
from data.mock_data import get_portfolio

# from utils.helpers import export_graph_visualization
from utils.logger import get_logger

logger = get_logger("main")


# 시나리오: 사용자가 CLI로 파이프라인을 실행할 때의 진입점 — LangGraph를 스트림하며 Macro→Publish까지 상태를 누적하고 주요 결과 키별로 로그를 남긴다.
def main():
    load_dotenv()  # .env 파일 로드
    logger.info("🚀 AlphaInvest 에이전트 실행을 시작합니다...")

    # 1. 그래프 빌드 및 시각화
    app = build_skeleton()

    # 그래프 시각화는 주석 처리
    # export_graph_visualization(app)

    # 2. 파이프라인 구동 (Streaming Mode)
    initial_state = get_initial_state(user_portfolio=get_portfolio())

    # 📌 선언형 로깅 매핑 (절차적 분기문 제거)
    log_actions = {
        StateKey.MACRO_RESULT: lambda v: logger.info(f"🔍 시황 요약: {v[:50]}..."),
        StateKey.RISK_RESULT: lambda v: logger.info(f"🛑 리스크 알림: {v[:50]}..."),
        StateKey.PORTFOLIO_RESULT: lambda v: logger.info(f"💼 포트폴리오 진단 완료: {v[:50]}..."),
        StateKey.FINAL_REPORT: lambda _: logger.info("📝 최종 리포트 작성이 완료되었습니다."),
        StateKey.NOTION_PAGE_URL: lambda v: logger.info(f"📰 Notion 발행 완료: {v}") if v else None,
    }

    final_state = initial_state
    for step in app.stream(initial_state, stream_mode="updates"):
        for node_name, updated_values in step.items():
            if updated_values is None:
                continue

            logger.info(f"--- [ {node_name} ] 작업 완료 ---")
            final_state.update(updated_values)  # 상태 누적 업데이트

            # 실시간 진행 상황 요약 (for문 없이 리스트 내포와 왈러스 연산자를 이용한 완전 선언적 처리)
            [action(val) for key, val in updated_values.items() if (action := log_actions.get(key))]

    # 3. 결과 출력
    logger.info("✅ 모든 분석 생중계가 완료되었습니다!")


if __name__ == "__main__":
    main()
