"""Notion 퍼블리시 에이전트 노드 — CIO 최종 리포트를 Notion 페이지로 발행"""

import datetime
from typing import Any, Dict

from agents.constants import StateKey
from agents.state import AgentState
from utils.logger import get_logger
from utils.notion_publisher import publish_to_notion

logger = get_logger("agents.nodes.publish")


# 시나리오: CIO 직후 그래프의 마지막 변환 단계 — final_report를 마크다운→Notion 블록으로 올리고 notion_page_url을 state에 남긴다.
def publish_node(state: AgentState) -> Dict[str, Any]:
    """CIO가 완성한 final_report를 Notion 데이터베이스에 신규 페이지로 발행합니다."""
    final_report = state.get(StateKey.FINAL_REPORT, "")
    if not final_report:
        logger.warning("[Publish] 발행할 리포트가 비어 있습니다.")
        return {StateKey.NOTION_PAGE_URL: ""}

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    title = f"[{today_str}] AlphaInvest 일일 투자 전략 리포트"

    try:
        page_url = publish_to_notion(title=title, markdown_text=final_report)
    except Exception as e:
        logger.error(f"[Publish] Notion 발행 실패: {e}")
        page_url = ""

    return {StateKey.NOTION_PAGE_URL: page_url}


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    mock_state: AgentState = {
        StateKey.FINAL_REPORT: (
            "# [2026-03-25] 일일 투자 전략 리포트\n\n"
            "## I. 거시경제 시황\n\n"
            "미국 연준의 금리 동결 기조가 유지되고 있으며, 인플레이션은 2.5% 수준에서 둔화되고 있습니다.\n\n"
            "## II. 포트폴리오 진단\n\n"
            "- **진단 대상:** 삼성전자 (005930.KS)\n"
            "- 반도체 대형주 중심의 비중 유지가 유리한 시점입니다.\n\n"
            "## III. 리스크 경고\n\n"
            "중국 부동산 경기 침체와 고유가 상황이 지속되고 있으니 관련 섹터 진입에 유의해야 합니다.\n\n"
            "## IV. 투자 기회\n\n"
            "AI 온디바이스 기술 고도화에 따른 팹리스 및 기판 업체들의 수혜가 예상됩니다."
        ),
    }

    logger.info("[단독 테스트] Publish 노드 실행 중...")
    result = publish_node(mock_state)
    logger.info(f"[결과] Notion URL: {result.get(StateKey.NOTION_PAGE_URL, '미발행')}")
