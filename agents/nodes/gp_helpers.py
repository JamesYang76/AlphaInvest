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

    [심사 원칙]
    1. **무죄 추정의 원칙:** 명백한 팩트 오류(예: 리포트 숫자가 참조 데이터와 다름)나 심각한 논리적 결함이 없다면 기분 좋게 'is_pass: true'를 부여하세요.
    2. **억지 반려 금지:** "문장이 좀 더 예뻤으면 좋겠다"거나 "근거가 더 풍부했으면 좋겠다" 같은 주관적인 아쉬움은 반려 사유가 될 수 없습니다. 오직 '틀린 사실'이 있을 때만 반려하세요.

    [심사 기준 - 반드시 통과해야 할 관문]
    1. 논리적 일관성 (가장 중요): 문장 간의 인과관계가 맞는가?
    2. 수치 문맥 파악: 해당 수치가 실제 위험한 수준인가?
    3. 팩트 데이터 일치: 제공된 [실시간 참조 데이터]의 수치와 보고서 본문의 수치가 정확히 일치하는가?


    [출력 형식]
    반드시 아래와 같은 JSON 형식으로만 답변해야 합니다:
    {{
        "is_pass": true 또는 false,
        "feedback_reason": "반려 시에는 모순된 지점이나 오류를 아주 구체적이고 매섭게 지적하십시오."
    }}
""").strip()

# 💡 3. 수정용(Repair) 시스템 프롬프트 (최종 리포트 작가 페르소나 강화)
REPAIR_SYSTEM_PROMPT = dedent("""
    당신은 수석 애널리스트의 피드백을 바탕으로 투자 리포트를 교정하는 전문 편집자입니다.

    [핵심 원칙]
    1. 원본 유지: 반드시 원본 보고서의 마크다운 구조와 형식을 그대로 유지합니다.
    2. 데이터 정정: 피드백에 명시된 수치와 팩트만을 정확하게 반영하여 본문을 수정합니다.
    3. 출력 제한: 인사말이나 설명 없이 오직 수정된 리포트 본문만 출력하십시오.
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
                    [원본 보고서]
                    {target_result}

                    [수정 피드백]
                    {reason}
                    ---

                    지시: 위의 피드백을 반영하여 원본 리포트를 재작성하세요. 
                    피드백 내용 자체를 언급하거나 복사하지 말고, 이미 수정이 완료된 '최종 결과물'만 반환하세요.
                """).strip()
            ),
        ]
    )
    chain = prompt | llm
    response = chain.invoke({"target_result": target_result, "reason": reason})
    return response.content