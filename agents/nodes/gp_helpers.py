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

# 💡 3. 수정용(Repair) 시스템 프롬프트 (최소한의 필수 정보로 단순화)
REPAIR_SYSTEM_PROMPT = dedent("""
    당신은 수석 애널리스트의 지시를 받아 보고서를 완벽하게 수정하는 전문 교정 편집자입니다.
    전달받은 [심사 피드백]을 바탕으로, 원본 보고서의 오류를 수정하고 품질을 높여 최종본을 작성하세요.

    [지침]
    1. 수석 애널리스트의 피드백을 100% 반영하되, 기존 리포트의 전문적인 톤은 유지하세요.
    2. 피드백에서 지적된 팩트나 논리가 올바르게 수정되었는지 신중히 검토하세요.
    3. 다른 불필요한 서술 없이 수정된 리포트 본문만 출력하세요.
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
                    [수정 지시]
                    다음 보고서의 지적사항을 반영하여 최종 수정본을 작성해 주세요.

                    1. 원본 보고서:
                    {target_result}

                    2. 반려 사유(피드백):
                    {reason}
                """).strip(),
            ),
        ]
    )
    chain = prompt | llm
    response = chain.invoke({"target_result": target_result, "reason": reason})
    return response.content
