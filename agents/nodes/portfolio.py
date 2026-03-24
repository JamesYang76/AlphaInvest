import os
from textwrap import dedent
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agents.constants import AgentName, ModelConfig, StateKey
from agents.state import AgentState
from utils.logger import get_logger
from utils.macro_data import get_sector_context
from utils.stock_data import enrich_portfolio_data

logger = get_logger("agents.nodes.portfolio")

# ==========================================
# 🧠 시스템 프롬프트 (PB 페르소나 및 역할 정의)
# ==========================================
PORTFOLIO_SYSTEM_PROMPT = dedent("""
    당신은 상위 0.1% 초고액 자산가들을 전담 관리하는
    VIP 웰스 매니저이자 프라이빗 뱅커(PB)입니다.
    고객님이 보유한 종목 정보를 바탕으로 맞춤형 자산 진단 및 리밸런싱 전략을 제안하세요.

    분석 및 출력 가이드라인:
    1. 보유/교체(Hold or Switch) 우선 판단: 현재 포트폴리오가 기회 요인(AI, 에너지 등)에 잘 부합하고
       펀더멘털이 우수하다면, 무리한 교체 대신 보유(HOLD) 전략을 강력히 권고하고 그 이유를 설명하세요.
    2. 진정한 다각화(True Diversification) 필수: 현재 보유 종목과 동일한 산업군 및 리스크 요인
       (예: 삼성전자 보유 시 SK하이닉스 추천 금지)을 가진 종목의 추천을 지양하십시오.
       리밸런싱은 반드시 상관관계가 낮은 섹터를 제안하여 리스크를 분산시켜야 합니다.
    3. 정밀 종목 진단: 보유 종목의 내재가치와 현재 '단기간 과열(Overheated)' 여부,
       그리고 고객의 수익률(Profit Rate)에 따른 매수/매도 적절성을 진단하세요.
    4. 시황 및 섹터 로테이션: 교체 매매를 제안한다면, 현재 가장 강력한 모멘텀을 가진 대안 섹터
       (예: 원자재, 에너지 인프라 등)를 우선 고려하세요. 만약 같은 섹터 내에서의 이동을 제안한다면,
       왜 가지고 있는 종목 보다 제안 종목이 지금 시점에서
       더 유리한지 명확한 차별성을 근거로 제시하십시오.
    5. 전문적 소통: 단호하고 품격 있는 PB의 어조로 마크다운 리포트 형태로 작성하세요.
""").strip()


def portfolio_node(state: AgentState) -> Dict[str, Any]:
    """
    유저의 포트폴리오를 진단하여 실시간 시황(Tavily, FRED 연동)에 맞는 전략을 생성하는 에이전트 노드입니다.
    """
    # 💡 1. OpenAI API 키 검증 (가드 클로즈)
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("LLM 연결 실패: .env 파일에 OPENAI_API_KEY를 먼저 설정해주세요.")
        return {StateKey.PORTFOLIO_RESULT: "LLM 연결 실패: .env 파일에 OPENAI_API_KEY를 먼저 설정해주세요."}

    # 💡 2. 모델 세팅 (일관성 있는 진단을 위해 온도 0)
    llm = ChatOpenAI(model=ModelConfig.DEFAULT_LLM_MODEL, temperature=ModelConfig.DEFAULT_TEMPERATURE)

    # 💡 3. 데이터 보강 (포트폴리오 개별 종목 정밀 데이터 및 이전 에이전트 결과 활용)
    user_portfolio = state.get(StateKey.USER_PORTFOLIO, [])
    enriched_portfolio = enrich_portfolio_data(user_portfolio)

    # 💡 4. 현재 확보된 데이터: Macro 분석 결과만 활용 (순차 단계상 Risk, Alpha 전)
    macro_info = state.get(StateKey.MACRO_RESULT, "거시 경제 분석 데이터가 아직 확보되지 않았습니다.")

    # 보유 종목의 섹터 컨텍스트(현황 뉴스) 참고
    tickers = [s.get("ticker") for s in user_portfolio if "ticker" in s]
    sector_info = get_sector_context(tickers=tickers)

    # 💡 5. 프롬프트 조립 (진단형 마크다운 포맷)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PORTFOLIO_SYSTEM_PROMPT),
            (
                "user",
                dedent("""
                    ### 1. 고객 포트폴리오 현황 (Individual Assets)
                    {enriched_portfolio_str}

                    ### 2. 최신 거시 환경 분석 리포트 (Macro Intelligence)
                    {macro_info}

                    ### 3. 보유 종목 섹터 뉴스 (Sector Context)
                    {sector_info}

                    ---
                    **거시 환경에 비추어 본 현재 자산 상태의 적절성**을 수석 PB의 관점에서 냉철하게 평가하십시오.
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
