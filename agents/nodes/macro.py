from textwrap import dedent
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

from agents.constants import AgentName, StateKey
from agents.state import AgentState
from data.fetchers import fetch_macro_data, fetch_news, get_llm
from utils.logger import get_logger

logger = get_logger("agents.nodes.macro")

# .env 파일에서 환경 변수 로드
load_dotenv()

# ==========================================
# 🧠 시스템 프롬프트 (페르소나 및 역할 정의)
# ==========================================
MACRO_SYSTEM_PROMPT = dedent("""
    당신은 글로벌 거시경제 전문 애널리스트입니다.
    제공된 거시경제 지표와 최신 뉴스를 분석하여 현재 투자 환경을 날카롭게 진단해 주세요.
    절대 장황하게 쓰지 말고, 전문가다운 통찰력을 담아 분석 내용을 요약해야 합니다.

    분석은 다음 형식을 반드시 지켜주세요:
    ## 거시경제 환경 요약
    1. **현재 상황**: (2~3줄)
    2. **투자자에게 시사하는 점**: (2~3줄)
    3. **주요 리스크 요인**: (불릿 3개)
""").strip()


def macro_node(state: AgentState) -> Dict[str, Any]:
    # ① 실시간 데이터 수집 (지표 및 뉴스)
    macro_data = fetch_macro_data()
    # 쿼리에 팩트체크용 최신 맥락을 강화
    news = fetch_news("Current Federal Reserve inflation economic outlook and global market trends")

    # ② LLM 설정 (분석의 일관성을 위해 온도는 낮게 설정)
    llm = get_llm(temperature=0.3)

    # ③ 프롬프트 조립 (retry_hint를 유저 메세지에 동적으로 주입)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", MACRO_SYSTEM_PROMPT),
            (
                "user",
                dedent("""
                    아래 경제 지표와 뉴스를 분석하여 투자 환경을 요약해주세요.

                    [거시경제 지표 (FRED & yfinance)]
                    - 기준금리: {fed_rate}
                    - CPI (인플레이션): {cpi}
                    - 실업률: {unemployment}
                    - 달러 인덱스: {dxy}
                    - VIX (공포지수): {vix}
                    - S&P500 추세: {sp500_trend}

                    [최신 뉴스 (Tavily)]
                    {news_data}
                """).strip(),
            ),
        ]
    )

    # ④ 체인 구축 및 실행
    chain = prompt | llm

    try:
        # LLM에게 추론(invoke) 지시 및 결과 받기
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
