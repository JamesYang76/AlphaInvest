import datetime
from textwrap import dedent
from typing import Any, Dict

from langchain_core.messages import HumanMessage

from agents.constants import StateKey
from agents.state import AgentState
from data.fetchers import format_report_sources_markdown, get_llm
from utils.logger import get_logger

logger = get_logger("agents.nodes.cio")


# 시나리오: Alpha까지 통과한 뒤 GP·라우터가 CIO로 보낼 때 — 네 에이전트 결과를 한 리포트로 합치고 LLM으로 문체를 다듬어 final_report를 만든다.
def cio_node(state: AgentState) -> Dict[str, Any]:
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    macro = state.get(StateKey.MACRO_RESULT, "데이터 없음")
    portfolio = state.get(StateKey.PORTFOLIO_RESULT, "데이터 없음")
    risk = state.get(StateKey.RISK_RESULT, "데이터 없음")
    alpha = state.get(StateKey.ALPHA_RESULT, "데이터 없음")

    # user_portfolio(List[Dict])에서 보유 종목 티커 목록을 동적으로 생성
    portfolio_tickers = ", ".join(item.get("ticker", "") for item in state.get(StateKey.USER_PORTFOLIO, [])) or "없음"

    report = dedent(f"""
        # [{today_str}] 일일 투자 전략 리포트

        ## I. 거시경제 시황

        {macro}

        ## II. 포트폴리오 진단

        - **진단 대상 종목:** {portfolio_tickers}

        {portfolio}

        ## III. 리스크 경고

        {risk}

        ## IV. 투자 기회

        {alpha}
    """).strip()

    logger.info("[CIO] 최종 리포트 정교화 중...")

    llm = get_llm(temperature=0.4)

    refine_prompt = dedent(f"""
        당신은 최고의 경제 잡지 편집장입니다.
        아래 리서치 데이터를 바탕으로 작성된 리포트 초안을 읽고,
        전체적인 문맥이 매끄럽고 전문적인 투자 리포트 스타일이 되도록 다듬어 주세요.

        [규칙]
        1. 각 섹션의 핵심 내용은 절대 빠뜨리지 마세요.
        2. 특히 미국/한국의 대표 종목명과 티커(Ticker)는 분석의 핵심이므로 절대로 생략하거나 요약하지 말고 본문에 반드시 포함하세요.
        3. 문장은 격식 있는 문어체(~입니다, ~할 것으로 전망됩니다)를 사용하세요.
        4. 섹션 제목(##), 불릿포인트(-), 이모지 같은 마크다운 구조를 유지하세요.
        5. 섹션 간 자연스러운 연결 문장을 추가하세요.
        6. 문장은 자연스러운 문단 단위로 작성하고, 과도한 줄바꿈을 피하세요.

        [리포트 초안]
        {report}
    """).strip()

    try:
        response = llm.invoke([HumanMessage(content=refine_prompt)])
        final_polished_report = response.content
        logger.info("[CIO] 정교화 완료")
        logger.info(final_polished_report)
    except Exception as e:
        logger.error(f"[CIO] 오류 발생: {e}")
        final_polished_report = report

    sources_md = format_report_sources_markdown(state.get(StateKey.REPORT_SOURCE_LINKS, []))
    if sources_md:
        final_polished_report = final_polished_report.rstrip() + sources_md

    return {StateKey.FINAL_REPORT: final_polished_report}


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    # [단독 테스트용 Mock 데이터]
    mock_state = {
        StateKey.MACRO_RESULT: ("미국 연준의 금리 동결 기조가 유지되고 있으며, " "인플레이션은 2.5% 수준에서 둔화되고 있습니다."),
        StateKey.PORTFOLIO_RESULT: "삼성전자와 SK하이닉스 등 반도체 대형주 중심의 비중 유지가 유리한 시점입니다.",
        StateKey.RISK_RESULT: ("중국 부동산 경기 침체와 고유가 상황이 지속되고 있으니 " "관련 섹터 진입에 유의해야 합니다."),
        StateKey.ALPHA_RESULT: "AI 온디바이스 기술 고도화에 따른 팹리스 및 기판 업체들의 수혜가 예상됩니다.",
    }

    logger.info("[단독 테스트] CIO 노드 실행 중...")
    result = cio_node(mock_state)

    logger.info("\n" + "=" * 50)
    logger.info("CIO 최종 리포트")
    logger.info("-" * 50)
    logger.info(result.get(StateKey.FINAL_REPORT))
    logger.info("=" * 50)
