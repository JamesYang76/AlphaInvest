import os
from textwrap import dedent
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agents.constants import AgentName, ModelConfig, StateKey
from agents.nodes.runtime_status import notify_runtime_progress
from agents.state import AgentState
from utils.logger import get_logger
from utils.macro_data import get_sector_context
from utils.stock_data import enrich_portfolio_data

logger = get_logger("agents.nodes.portfolio")

# ==========================================
# 🧠 시스템 프롬프트 (PB 페르소나 및 역할 정의)
# ==========================================
PORTFOLIO_SYSTEM_PROMPT = dedent("""
    당신은 고객 포트폴리오를 3개월 투자 관점에서 점검하는 포트폴리오 전략가입니다.
    보유 종목을 하나씩 평가하되, 단순한 종목 소개가 아니라 유지·축소·교체 판단이 바로 가능하도록 써야 합니다.

    규칙:
    1. 각 보유 종목마다 데이터와 현재 거시 환경을 연결해 판단하세요.
    2. 막연한 낙관/비관 대신 3개월 관점에서 유지(HOLD), 비중축소(REDUCE), 교체검토(SWITCH) 중 하나를 분명히 제시하세요.
    3. 교체를 제안할 때는 왜 기존 종목이 불리한지와 어떤 성격의 대안이 필요한지를 함께 설명하세요.
    4. 장황한 PB 화법보다 실무적인 운용 메모처럼 간결하게 쓰세요.

    출력 형식:
    ## 포트폴리오 진단
    - 종목별 불릿 진단: 각 종목당 2~4문장
    - 마지막에 '## 포트폴리오 차원의 액션' 섹션을 추가하고, 전체 포트폴리오에 대한 비중 조정 방향을 3개 불릿으로 정리하세요.
""").strip()


# 시나리오: Macro 이후 GP 통과 시 — 보유 종목을 시세 보강하고 거시·섹터 뉴스와 함께 PB 스타일 포트폴리오 진단문을 생성한다.
def portfolio_node(state: AgentState) -> Dict[str, Any]:
    """
    유저의 포트폴리오를 진단하여 실시간 시황(Tavily, FRED 연동)에 맞는 전략을 생성하는 에이전트 노드입니다.
    """
    # 💡 1. OpenAI API 키 검증 (가드 클로즈)
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("LLM 연결 실패: .env 파일에 OPENAI_API_KEY를 먼저 설정해주세요.")
        err_text = "LLM 연결 실패: .env 파일에 OPENAI_API_KEY를 먼저 설정해주세요."
        return {
            StateKey.PORTFOLIO_RESULT: err_text,
            StateKey.CURRENT_REPORT: err_text,
            "last_node": AgentName.PORTFOLIO,
        }

    # 💡 2. 모델 세팅 (일관성 있는 진단을 위해 온도 0)
    llm = ChatOpenAI(
        model=ModelConfig.DEFAULT_LLM_MODEL,
        temperature=ModelConfig.DEFAULT_TEMPERATURE,
        timeout=25,
        max_retries=1,
    )

    # 💡 3. 데이터 보강 (포트폴리오 개별 종목 정밀 데이터 및 이전 에이전트 결과 활용)
    user_portfolio = state.get(StateKey.USER_PORTFOLIO, [])
    notify_runtime_progress(state, "portfolio_enrich_holdings")
    enriched_portfolio = enrich_portfolio_data(user_portfolio)

    # 💡 4. 현재 확보된 데이터: Macro 분석 결과만 활용 (순차 단계상 Risk, Alpha 전)
    macro_info = state.get(StateKey.MACRO_RESULT, "거시 경제 분석 데이터가 아직 확보되지 않았습니다.")

    # 보유 종목의 섹터 컨텍스트(현황 뉴스) 참고
    tickers = [s.get("ticker") for s in user_portfolio if "ticker" in s]
    notify_runtime_progress(state, "portfolio_fetch_sector_context")
    sector_info = get_sector_context(tickers=tickers)

    # 💡 5. 프롬프트 조립 (진단형 마크다운 포맷)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PORTFOLIO_SYSTEM_PROMPT),
            (
                "user",
                dedent("""
                    ### [고객 포트폴리오 데이터]
                    {enriched_portfolio_str}

                    ### [거시경제 현황 및 섹터 뉴스]
                    - 리서치 리포트: {macro_info}
                    - 섹터 컨텍스트: {sector_info}

                    ---
                    **지시사항:**
                    - 각 종목마다 `HOLD`, `REDUCE`, `SWITCH` 중 하나를 명시하세요.
                    - 3개월 투자 기간을 기준으로 판단하고, 1개월/3개월 흐름과 업종 맥락을 함께 반영하세요.
                    - 단순 시황 복붙이 아니라 "왜 이 종목을 계속 들고 가거나 줄여야 하는지"를 써야 합니다.
                    - 마지막에는 포트폴리오 전체 차원의 액션 아이템 3개를 정리하세요.
                """).strip(),
            ),
        ]
    )

    # 포트폴리오 데이터를 가독성 좋게 변환 (YAML 형태의 문자열화)
    import yaml

    enriched_portfolio_str = yaml.dump(enriched_portfolio, allow_unicode=True, default_flow_style=False)

    # 💡 6. 체인 구축 및 실행
    input_data = {
        "enriched_portfolio_str": enriched_portfolio_str,
        "macro_info": macro_info,
        "sector_info": sector_info,
    }

    try:
        notify_runtime_progress(state, "portfolio_write_report")
        response = (prompt | llm).invoke(input_data)
        result_text = response.content
    except Exception as e:
        result_text = f"포트폴리오 진단 엔진 가동 중 오류 발생: {str(e)}"

    # 💡 7. 상태(State) 반환
    return {
        StateKey.PORTFOLIO_RESULT: result_text,
        StateKey.CURRENT_REPORT: result_text,
        "last_node": AgentName.PORTFOLIO,
    }
