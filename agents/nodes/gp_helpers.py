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
    당신은 아주 유능한 수석 애널리스트입니다.
    방금 제출된 보고서의 품질과 논리적 완결성을 심사하여 '통과' 여부를 결정하세요.

    [심사 기준]
    1. 전문성: 주장의 논거가 명확하며, 제공된 [실시간 참조 데이터]와 상충되는 치명적 오류가 없는가?
    2. 품질: 요약 형식이 부실하거나 근거 없는 주장만 나열되어 있지는 않은가?

    [출력 형식]
    반드시 아래와 같은 JSON 형식으로만 답변해야 합니다:
    {{
        "is_pass": true 또는 false,
        "feedback_reason": "반려 시에는 아주 구체적인 사유를, 승인 시에는 null을 반환하세요."
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


def get_target_key(last_node: str) -> str:
    """에이전트 이름에 따른 결과 저장 키값을 반환합니다."""
    mapping = {
        AgentName.MACRO: StateKey.MACRO_RESULT,
        AgentName.RISK: StateKey.RISK_RESULT,
        AgentName.ALPHA: StateKey.ALPHA_RESULT,
        AgentName.PORTFOLIO: StateKey.PORTFOLIO_RESULT,
    }
    return mapping.get(last_node, StateKey.CURRENT_REPORT)


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
