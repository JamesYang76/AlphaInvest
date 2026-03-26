from textwrap import dedent

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.constants import AgentName, StateKey


# 💡 1. 출력 데이터 모델 정의
class GPFeedback(BaseModel):
    is_pass: bool = Field(description="심사 통과 여부 (True/False)")
    feedback_reason: str = Field(description="심사 결과에 대한 아주 구체적이고 전문적인 이유")


# 💡 2. 시스템 프롬프트: 심사 및 수정 역할 정의
GP_SYSTEM_PROMPT = dedent("""
    당신은 아주 까다로운 수석 애널리스트이자 팩트체크 전문가입니다.
    보고서의 '논리적 자기모순'과 '데이터 해석 오류'를 찾아내어 엄격히 심사하세요.

    [심사 기준 - 반드시 통과해야 할 관문]
    1. 논리적 일관성 (가장 중요): 문장 간의 인과관계가 맞는가?
       (예: 유가 하락을 리스크로 본다면, 그로 인한 '에너지 비용 상승'을 경고하는 것은 인과관계에 어긋나는 모순임)
    2. 수치 문맥 파악: 해당 수치가 실제 위험한 수준인가?
       (예: 하이일드 스프레드 3.19는 역사적으로 낮은 수준임에도 '자금 조달 비용 급증'으로 해석하는 것은 과잉 리스크임)
    3. 팩트 데이터 일치: 제공된 [실시간 참조 데이터]의 수치와 보고서 본문의 수치가 정확히 일치하는가?
    4. 전문성: 주장의 근거가 명확하며, 불필요한 공포를 조작하거나 모호한 표현을 쓰지 않았는가?

    [출력 형식]
    반드시 아래와 같은 JSON 형식으로만 답변해야 합니다:
    {{
        "is_pass": true 또는 false,
        "feedback_reason": "반려 시에는 모순된 지점이나 오류를 아주 구체적이고 매섭게 지적하십시오."
    }}
""").strip()

# 💡 3. 수정용(Repair) 시스템 프롬프트 (최종 리포트 작가 페르소나 강화)
REPAIR_SYSTEM_PROMPT = dedent("""
    당신은 수석 애널리스트의 비판적 피드백을 바탕으로 투자 리포트를 완벽하게 재작성하는 전문 데이터 편집자입니다.

    [지역 사항 반영 가이드]
    1. 비판적 어조 제거: '보고서는 ~라고 주장했으나' 또는 '상충됩니다'와 같은 평가적 표현은 절대 사용하지 마세요.
    2. 데이터 정정: 피드백에 명시된 올바른 수치와 팩트를 사용하여 리포트 본문을 완전히 다시 쓰세요.
    3. 독립적 완결성: 수정된 내용은 피드백 자체를 보여주는 것이 아니라, 그 피드백이 이미 반영된 '최종 결과물'이어야 합니다.
    4. 전문적인 톤: '~입니다', '~할 것으로 전망됩니다' 등 리포트의 신뢰감을 주는 문어체를 사용하세요.
    5. 오직 수정된 리포트 본문만 출력하고 다른 설명은 하지 마세요.
""").strip()


# 시나리오: GP가 반려 후 수정본을 state에 쓸 때 — last_node에 따라 macro_result/risk_result 등 올바른 StateKey를 고른다.
def get_target_key(last_node: str) -> str:
    """에이전트 이름에 따른 결과 저장 키값을 반환합니다."""
    mapping = {
        AgentName.MACRO: StateKey.MACRO_RESULT,
        AgentName.RISK: StateKey.RISK_RESULT,
        AgentName.ALPHA: StateKey.ALPHA_RESULT,
        AgentName.PORTFOLIO: StateKey.PORTFOLIO_RESULT,
    }
    return mapping.get(last_node, StateKey.CURRENT_REPORT)


# 시나리오: GP 심사에서 반려됐을 때 — 피드백만 반영한 최종 리포트 본문을 LLM으로 재작성한다.
def run_repair_chain(llm, target_result, reason):
    """지시받은 피드백에 따라 보고서를 직접 교정하여 반환합니다."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", REPAIR_SYSTEM_PROMPT),
            (
                "user",
                dedent("""
                    [보고서 수정 가이드라인]
                    아래 제공된 '원본 보고서'의 오류를 '비판적 피드백'에 따라 즉시 정정하여 최종 리포트 본문을 다시 작성해 주세요.
                    - '피드백'은 참고용일 뿐이며, 그 내용 자체가 보고서 본문에 포함(복사)되어서는 안 됩니다.
                    - 오직 데이터가 정정된 '최종 결과물'로서의 리포트 본문만 출력하십시오.

                    1. 원본 보고서:
                    {target_result}

                    2. 비판적 피드백 (수정 가이드):
                    {reason}
                """).strip(),
            ),
        ]
    )
    chain = prompt | llm
    response = chain.invoke({"target_result": target_result, "reason": reason})
    return response.content
