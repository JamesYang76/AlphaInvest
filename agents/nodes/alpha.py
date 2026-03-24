import os
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agents.constants import ModelConfig, StateKey
from agents.state import AgentState

# TODO: 반드시 아래내용 싹다 지우고 수정할것...

# ==========================================
# 🧠 시스템 프롬프트 (Alpha Strategist 페르소나 및 역할 정의)
# ==========================================
ALPHA_SYSTEM_PROMPT = """당신은 초과 수익(Alpha)을 창출하는 전문 투자 전략가입니다.
앞선 분석(포트폴리오, 매크로, 리스크) 결과를 종합하여, 고객의 수익을 극대화할 수 있는
가장 정교한 '알파 종목' 및 '섹터 투자 아이디어'를 제안해 주세요.

분석 및 출력 가이드라인:
1. **정교한 추천**: 단순히 우량주를 나열하는 것이 아니라, 현재 매크로가 가리키는 주도 섹터와 리스크 환경에서
   가장 매력적인 2~3개 종목 혹은 ETF를 강력하게 추천하세요.
2. **논리적 연결**: 포트폴리오의 약점(예: 기술주 편중)과 매크로 강점(예: 에너지 주도주 부상)을 연결하여
   왜 이 추천이 '지금' 필요한지 논리적으로 설명해야 합니다.
3. **리스크 필터링**: 리스크 에이전트가 경고한 종목이나 섹터는 반드시 배제하거나 특별한 주의를 기울이십시오.
4. **전문적 소통**: 단호하고 신뢰감 있는 전략가의 어조로 마크다운 리포트 형태로 작성하세요.
"""


def alpha_node(state: AgentState) -> Dict[str, Any]:
    """
    최종 알파 추천 결과를 생성하는 에이전트 노드입니다.
    매크로, 리스크, 포트폴리오 분석 결과를 종합하여 최적의 투자 후보를 도출합니다.
    """
    # 💡 0. OpenAI API 키 검증
    if not os.getenv("OPENAI_API_KEY"):
        return {StateKey.ALPHA_RESULT: "LLM 연결 실패: .env 파일에 OPENAI_API_KEY를 먼저 설정해주세요."}

    # 💡 1. 모델 세팅 (일관성 있는 진단을 위해 온도 낮게 설정)
    llm = ChatOpenAI(model=ModelConfig.DEFAULT_LLM_MODEL, temperature=0.2)

    # 💡 2. 분석 결과 가져오기 (이전 단계 노드들이 작성한 결과물)
    portfolio_diag = state.get(StateKey.PORTFOLIO_RESULT, "포트폴리오 분석 결과 없음")
    macro_env = state.get(StateKey.MACRO_RESULT, "거시경제 분석 결과 없음")
    risk_alert = state.get(StateKey.RISK_RESULT, "리스크 분석 결과 없음")

    # 💡 3. 프롬프트 조립
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ALPHA_SYSTEM_PROMPT),
            (
                "user",
                "### 📈 거시경제 환경 분석\n"
                "{macro_env}\n\n"
                "### 🛑 리스크 경고 현황\n"
                "{risk_alert}\n\n"
                "### 💼 현재 포트폴리오 진단\n"
                "{portfolio_diag}\n\n"
                "--- \n"
                "**지침**: 위 분석 결과들을 종합하여, 지금 당장 매수하거나 포트폴리오에 추가할 만한 "
                "최고의 알파(초익 수익) 투자 아이디어 2~3개를 추천하고 구체적인 근거를 제시하세요.",
            ),
        ]
    )

    # 💡 4. 체인 실행
    chain = prompt | llm

    try:
        response = chain.invoke(
            {
                "macro_env": macro_env,
                "risk_alert": risk_alert,
                "portfolio_diag": portfolio_diag,
            }
        )
        result_text = response.content
    except Exception as e:
        result_text = f"알파 추천 엔진 가동 중 오류 발생: {str(e)}"

    # 💡 5. 상태(State) 반환
    return {StateKey.ALPHA_RESULT: result_text}
