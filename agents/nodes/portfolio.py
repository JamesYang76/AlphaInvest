import os
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agents.constants import ModelConfig, StateKey
from agents.state import AgentState
from utils.stock_data import get_stock_info

# ==========================================
# 🧠 시스템 프롬프트 (PB 페르소나 및 역할 정의)
# ==========================================
PORTFOLIO_SYSTEM_PROMPT = """당신은 상위 0.1% 초고액 자산가들을 전담 관리하는
VIP 웰스 매니저이자 프라이빗 뱅커(PB)입니다.
고객님이 보유한 종목 정보를 바탕으로 맞춤형 자산 진단 및 리밸런싱 전략을 제안하세요.

분석 및 출력 가이드라인:
1. 정밀 종목 진단: 보유 종목의 내재가치(PER, PBR 등)와 개별 종목의 최근 부침 분석 후 리스크를 설명하세요.
2. 시장 상황 대조: 거시 시황, 섹터 흐름, 전쟁/천재지변, 국가 부도 리스크 등
   특수 글로벌 상황이 자산에 미칠 영향을 대조하세요.
3. 교체 매매(Switching) 제안: 수익 극대화를 위해 어떤 타겟 종목(티커)이나 섹터로
   갈아타야 하는지 구체적인 대안을 제시하세요.
4. 전문적 소통: 결과는 고객에게 신뢰를 줄 수 있도록 단호하고 품격 있는 전문가의 어조를 사용하여
   요약된 리포트 형태로 작성하세요. (3~5줄 내외)"""


def portfolio_node(state: AgentState) -> Dict[str, Any]:
    """
    유저의 포트폴리오를 진단하여 다양한 외부 상황(전쟁, 천재지변 등)에 맞는 전략을 생성하는 에이전트 노드입니다.
    """
    # 💡 0. OpenAI API 키 검증 (가드 클로즈)
    if not os.getenv("OPENAI_API_KEY"):
        return {StateKey.PORTFOLIO_RESULT: "LLM 연결 실패: .env 파일에 OPENAI_API_KEY를 먼저 설정해주세요."}

    # 💡 1. 모델 세팅 (일관성 있는 진단을 위해 온도 0)
    llm = ChatOpenAI(model=ModelConfig.DEFAULT_LLM_MODEL, temperature=ModelConfig.DEFAULT_TEMPERATURE)

    # 💡 2. 데이터 보강 (포트폴리오 개별 종목 정밀 데이터 및 시황 데이터 수집)
    user_portfolio = state.get(StateKey.USER_PORTFOLIO, [])
    # 개별 종목별 상세 데이터(종가, PER, PBR, 최근 뉴스) 확보
    enriched_portfolio = [get_stock_info(stock["ticker"]) for stock in user_portfolio if "ticker" in stock]

    # 💡 3. 시황 데이터 구성 (거시 시황 내에 전쟁, 천재지변 등 특수한 전반적 상황을 통합)
    dummy_macro = (
        "- 미 연준 금리 동결 및 하반기 인하 기대감 상존\n"
        "- 지정학적 교전 고조 및 원자재 가격 변동성 확대(전쟁/천재지변 요인 포함)"
    )
    dummy_sector = (
        "- AI 반도체 밸류체인 강세 및 전력 인프라 순환매 확산\n" "- K-뷰티 수출 테마 호조 및 어닝 모멘텀 부각"
    )

    # 💡 4. 프롬프트 조립
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PORTFOLIO_SYSTEM_PROMPT),
            (
                "user",
                "고객 포트폴리오 상세: {enriched_portfolio}\n\n"
                "분석 참고 지표:\n"
                "- 글로벌 거시 시황 요약 (전쟁/특수 상황 포함): {macro_info}\n"
                "- 섹터 및 시장 시황 요약: {sector_info}\n\n"
                "지침: 위 데이터를 종합하여 포트폴리오를 진단하고 리밸런싱 플랜을 작성하세요.",
            ),
        ]
    )

    # 💡 5. 체인 구축 및 실행 (데이터 키 macro_info, sector_info 일치)
    try:
        response = (prompt | llm).invoke(
            {
                "enriched_portfolio": str(enriched_portfolio),
                "macro_info": dummy_macro,
                "sector_info": dummy_sector,
            }
        )
        result_text = response.content
    except Exception as e:
        result_text = f"포트폴리오 진단 엔진 가동 중 오류 발생: {str(e)}"

    # 💡 6. 상태(State) 반환
    return {StateKey.PORTFOLIO_RESULT: result_text}
