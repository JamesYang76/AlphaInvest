import datetime
from textwrap import dedent
from typing import Any, Dict

from langchain_core.messages import HumanMessage

from agents.constants import StateKey
from agents.state import AgentState
from data.fetchers import format_report_sources_markdown, get_llm
from utils.logger import get_logger

logger = get_logger("agents.nodes.cio")


def _build_report_draft(state: AgentState) -> str:
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    macro = state.get(StateKey.MACRO_RESULT, "데이터 없음")
    portfolio = state.get(StateKey.PORTFOLIO_RESULT, "데이터 없음")
    chart = state.get(StateKey.CHART_RESULT, "데이터 없음")
    risk = state.get(StateKey.RISK_RESULT, "데이터 없음")
    alpha = state.get(StateKey.ALPHA_RESULT, "데이터 없음")

    # user_portfolio(List[Dict])에서 보유 종목 티커 목록을 동적으로 생성
    portfolio_tickers = ", ".join(item.get("ticker", "") for item in state.get(StateKey.USER_PORTFOLIO, [])) or "없음"
    is_market_report = portfolio_tickers == "없음"

    if is_market_report:
        report = dedent(f"""
            # [{today_str}] 시장 전략 리포트

            ## I. 거시경제 시황

            {macro}

            ## II. 시장 포지셔닝

            보유 종목 입력 없이 생성된 시장 리포트입니다. 시장 전반의 배분 방향과 상대 강약 판단에 집중합니다.

            ## III. 기술적 차트 체크

            {chart}

            ## IV. 리스크 경고

            {risk}

            ## V. 투자 기회

            {alpha}
        """).strip()
    else:
        report = dedent(f"""
            # [{today_str}] 포트폴리오 전략 리포트

            ## I. 거시경제 시황

            {macro}

            ## II. 포트폴리오 진단

            - **진단 대상 종목:** {portfolio_tickers}

            {portfolio}

            ## III. 기술적 차트 체크

            {chart}

            ## IV. 리스크 경고

            {risk}

            ## V. 투자 기회

            {alpha}
        """).strip()
    return report


def build_final_report(state: AgentState, refine: bool = True) -> str:
    report = _build_report_draft(state)

    if refine:
        logger.info("[CIO] 최종 리포트 정교화 중...")

        llm = get_llm(temperature=0.4)

        refine_prompt = dedent(f"""
            당신은 기관 리서치 헤드입니다.
            아래 초안을 읽고, 실행 가능한 투자 리포트 문체로 다듬어 주세요.

            [규칙]
            1. 각 섹션의 핵심 내용은 절대 빠뜨리지 마세요.
            2. 종목명과 티커는 분석의 핵심이므로 생략하지 마세요.
            3. 문장은 격식 있는 문어체로 유지하되, 군더더기 없는 리서치 메모처럼 압축하세요.
            4. 섹션 제목(##)과 불릿 구조를 유지하세요.
            5. 섹션 간 자연스러운 연결 문장을 추가하세요.
            6. 문장은 자연스러운 문단 단위로 작성하고, 과도한 줄바꿈을 피하세요.
            7. 기술적 차트 분석 내용은 반드시 유지하세요.
               - RSI/3개월 모멘텀/3개월 변동성/6개월 Drawdown 중 최소 2개 이상을 최종 리포트에 명시해야 합니다.
               - 거시 시황(금리·CPI·VIX 등)과 차트 해석을 연결해 실행 전략(분할매수/관망/비중조절 등)을 제시하세요.
            8. 시장 전략 리포트와 포트폴리오 전략 리포트를 혼동하지 말고, 초안의 제목과 섹션 목적을 그대로 살리세요.

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
    else:
        final_polished_report = report

    sources_md = format_report_sources_markdown(state.get(StateKey.REPORT_SOURCE_LINKS, []))
    if sources_md:
        final_polished_report = final_polished_report.rstrip() + sources_md

    return final_polished_report


# 시나리오: Alpha까지 통과한 뒤 GP·라우터가 CIO로 보낼 때 — 네 에이전트 결과를 한 리포트로 합치고 LLM으로 문체를 다듬어 final_report를 만든다.
def cio_node(state: AgentState) -> Dict[str, Any]:
    final_polished_report = build_final_report(state, refine=True)
    return {StateKey.FINAL_REPORT: final_polished_report}


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    # [단독 테스트용 Mock 데이터]
    mock_state = {
        StateKey.MACRO_RESULT: ("미국 연준의 금리 동결 기조가 유지되고 있으며, 인플레이션은 2.5% 수준에서 둔화되고 있습니다."),
        StateKey.PORTFOLIO_RESULT: "삼성전자와 SK하이닉스 등 반도체 대형주 중심의 비중 유지가 유리한 시점입니다.",
        StateKey.RISK_RESULT: ("중국 부동산 경기 침체와 고유가 상황이 지속되고 있으니 관련 섹터 진입에 유의해야 합니다."),
        StateKey.ALPHA_RESULT: "AI 온디바이스 기술 고도화에 따른 팹리스 및 기판 업체들의 수혜가 예상됩니다.",
    }

    logger.info("[단독 테스트] CIO 노드 실행 중...")
    result = cio_node(mock_state)

    logger.info("\n" + "=" * 50)
    logger.info("CIO 최종 리포트")
    logger.info("-" * 50)
    logger.info(result.get(StateKey.FINAL_REPORT))
    logger.info("=" * 50)
