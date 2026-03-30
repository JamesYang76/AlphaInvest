from textwrap import dedent
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

from agents.constants import AgentName, StateKey
from agents.nodes.runtime_status import notify_runtime_progress
from agents.state import AgentState
from data.fetchers import (
    fetch_macro_data,
    fetch_news_with_sources,
    get_llm,
    macro_numeric_source_links,
    merge_report_source_links,
)
from utils.logger import get_logger

logger = get_logger("agents.nodes.macro")

# .env 파일에서 환경 변수 로드
load_dotenv()

# ==========================================
# 🧠 시스템 프롬프트 (페르소나 및 역할 정의)
# ==========================================
MACRO_SYSTEM_PROMPT = dedent("""
    당신은 3개월 자산배분을 담당하는 글로벌 거시 전략가입니다.
    제공된 거시 지표와 최신 뉴스를 바탕으로, 앞으로 약 3개월 동안 투자 판단에 직접 필요한 내용만 압축해 작성하세요.

    규칙:
    1. 금리, 물가, 고용, 변동성, 달러 환경이 위험자산에 어떤 방향성 압력을 주는지 인과관계로 설명하세요.
    2. 뉴스에 없는 주장이나 과장된 전망을 추가하지 마세요.
    3. 단기 시황 브리핑이 아니라 3개월 관점의 포지셔닝 메모처럼 쓰세요.
    4. 문장은 짧고 단정하게 쓰고, 추상적 표현보다 데이터 해석을 우선하세요.

    출력 형식:
    ## 거시경제 환경 요약
    1. **현재 상황**: 2~3문장
    2. **3개월 투자 시사점**: 2~3문장
    3. **주요 리스크 요인**: 불릿 3개
""").strip()


# 시나리오: 파이프라인 최초 노드(START→Macro) — FRED·yfinance·Tavily로 거시 데이터를 모으고
# LLM 요약을 macro_result·macro_data·GP 검수용 current_report에 넣는다.
def macro_node(state: AgentState) -> Dict[str, Any]:
    # ① 실시간 데이터 수집 (지표 및 뉴스)
    notify_runtime_progress(state, "macro_fetch_data")
    macro_data = fetch_macro_data()
    # 쿼리에 팩트체크용 최신 맥락을 강화
    notify_runtime_progress(state, "macro_fetch_news")
    news, tavily_links = fetch_news_with_sources(
        "Current Federal Reserve inflation economic outlook and global market trends",
        link_prefix="[거시 뉴스]",
    )
    source_links = merge_report_source_links(
        state.get(StateKey.REPORT_SOURCE_LINKS),
        macro_numeric_source_links() + tavily_links,
    )

    # ② LLM 설정 (분석의 일관성을 위해 온도는 낮게 설정)
    llm = get_llm(temperature=0.3)

    # ③ 프롬프트 조립 (retry_hint를 유저 메세지에 동적으로 주입)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", MACRO_SYSTEM_PROMPT),
            (
                "user",
                dedent("""
                    아래 경제 지표와 뉴스를 분석하여 3개월 투자 관점의 거시 환경을 요약해주세요.

                    [거시경제 지표 (FRED & yfinance)]
                    - 기준금리: {fed_rate}
                    - CPI (인플레이션): {cpi}
                    - 실업률: {unemployment}
                    - 달러 인덱스: {dxy}
                    - VIX (공포지수): {vix}
                    - S&P500 추세: {sp500_trend}

                    [최신 뉴스 (Tavily)]
                    {news_data}

                    추가 지시:
                    - 섹터나 종목 추천까지 내려가지 말고, 거시 환경과 자산배분 시사점까지만 정리하세요.
                    - '관망이 필요합니다' 같은 일반론만 쓰지 말고 왜 그런지 지표와 연결해 설명하세요.
                """).strip(),
            ),
        ]
    )

    # ④ 체인 구축 및 실행
    chain = prompt | llm

    try:
        # LLM에게 추론(invoke) 지시 및 결과 받기
        notify_runtime_progress(state, "macro_write_report")
        response = chain.invoke(
            {
                "fed_rate": macro_data.get("fed_rate", "N/A"),
                "cpi": macro_data.get("cpi", "N/A"),
                "unemployment": macro_data.get("unemployment", "N/A"),
                "dxy": macro_data.get("dxy", "N/A"),
                "vix": macro_data.get("vix", "N/A"),
                "sp500_trend": macro_data.get("sp500_trend", "N/A"),
                "news_data": news,
            }
        )
        result_text = response.content

    except Exception as e:
        # 장애가 나도 파이프라인이 죽지 않도록 방어
        logger.error(f"LLM 연결 중 오류 발생: {e}")
        result_text = f"LLM 연결 중 오류 발생: {str(e)}"

    return {
        StateKey.MACRO_RESULT: result_text,
        StateKey.CURRENT_REPORT: result_text,  # 💡 GP 검수용 공통 리포트 필드 추가
        StateKey.MACRO_DATA: macro_data,  # 💡 후속 노드(Risk 등)에서 재사용할 수 있도록 원시 데이터 보관
        StateKey.MARKET_NEWS_SNIPPET: news,
        StateKey.REPORT_SOURCE_LINKS: source_links,
        "last_node": AgentName.MACRO,
    }


if __name__ == "__main__":
    # 포트폴리오 정보 없이, 빈 상태(state)로 테스트 (거시 경제 전문 분석 컨셉)
    test_state = {}
    logger.info("\n🚀 [단독 테스트] 거시 경제 전문 분석 실행 중...")
    result = macro_node(test_state)

    logger.info("\n" + "=" * 50)
    logger.info("📊 최종 거시 경제 분석 결과")
    logger.info("-" * 50)
    logger.info(result.get(StateKey.MACRO_RESULT))
    logger.info("=" * 50)
