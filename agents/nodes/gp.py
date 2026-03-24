from textwrap import dedent
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.constants import StateKey
from agents.state import AgentState
from data.fetchers import get_llm
from utils.logger import get_logger

# 로거 설정
logger = get_logger("agents.nodes.gp")
load_dotenv()


# 💡 1. 출력 데이터 모델 정의 (후처리를 위한 스키마)
class GPFeedback(BaseModel):
    is_pass: bool = Field(description="심사 통과 여부 (True/False)")
    feedback_reason: str = Field(description="심사 결과에 대한 아주 구체적이고 전문적인 이유")


# 💡 2. 시스템 프롬프트: '수석 애널리스트' 역할과 'JSON 형식' 직접 명시
GP_SYSTEM_PROMPT = dedent("""
    당신은 아주 유능한 수석 애널리스트입니다.
    방금 제출된 보고서의 품질과 논리적 완결성을 심사하여 '통과' 여부를 결정하세요.

    [심사 기준]
    1. 전문성: 주장의 논거가 명확하며, 제공된 [실시간 참조 데이터]와 상충되는 치명적 오류가 없는가?
    2. 품질: 요약 형식이 부실하거나 근거 없는 주장만 나열되어 있지는 않은가?

    [심사 가이드]
    - 치명적인 논리 도약 팩트 오류가 있을 때는 반려하세요.
    - 리포트가 다서 짧더라도 핵심 데이터에 기반한 결론이 있다면 '합격'입니다.

    [출력 형식]
    반드시 아래와 같은 JSON 형식으로만 답변해야 합니다:
    {{
        "is_pass": true 또는 false,
        "feedback_reason": "반려 시에는 아주 구체적인 사유를, 승인 시에는 null을 반환하세요."
    }}
""").strip()


def gp_node(state: AgentState) -> Dict[str, Any]:
    """
    제출된 분석 리포트를 전문가의 관점에서 심사/검수합니다.
    (실시간 거시 데이터 및 시황 정보를 팩트체크 기준으로 활용합니다.)
    """
    llm = get_llm(temperature=0.0)
    last_node = state.get("last_node", "알 수 없음")

    # [심사 대상 리포트 본문 가져오기]
    target_result = state.get(StateKey.CURRENT_REPORT, "분석 내용 누락")

    # 💡 팩트체크용 실시간 참조 데이터 확보
    macro_result = state.get(StateKey.MACRO_RESULT, "분석되지 않음")
    macro_data = state.get(StateKey.MACRO_DATA, {})

    # 원시 데이터 포맷팅
    macro_data_str = ", ".join([f"{k}: {v}" for k, v in macro_data.items()]) if macro_data else "정보 없음"

    # 💡 3. 파서 준비 (결과 파싱을 위해 사용)
    parser = JsonOutputParser(pydantic_object=GPFeedback)

    # 💡 4. 프롬프트 구성 (실시간 참조 데이터를 유저 메세지에 포함)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", GP_SYSTEM_PROMPT),
            (
                "user",
                dedent("""
            심사 대상: **[{last_node}]** 보고서

            [제출된 보고서 내용]
            {target_result}

            ---
            [실시간 참조 데이터 (심사 팩트체크 기준)]
            - 주요 지표 수치: {macro_data_str}
            - 거시경제 시황 요약: {macro_result}

            ---
            지침: 위 '실시간 참조 데이터'와 상충되는 치명적인 팩트 오류가 있는지 확인하고,
            보고서의 전문성과 논리적 깊이를 심사하여 JSON으로 답변하세요.
        """).strip(),
            ),
        ]
    )

    try:
        # 💡 5. 실행 및 결과 처리
        chain = prompt | llm | parser
        feedback = chain.invoke(
            {
                "last_node": last_node,
                "target_result": target_result,
                "macro_result": macro_result,
                "macro_data_str": macro_data_str,
            }
        )

        is_pass = feedback.get("is_pass", False)
        reason = feedback.get("feedback_reason") or "심사 기준 미달"

        if is_pass:
            logger.info(f"  ✅ [{last_node}] 품질 검수 통과!")
            return {StateKey.GP_FEEDBACK: {"is_pass": True}, StateKey.RETRY_COUNT: 0}
        else:
            logger.warning(f"  ❌ [{last_node}] 반려: {reason}")
            # 리트라이 횟수 증가 및 상태 업데이트
            current_retry = state.get(StateKey.RETRY_COUNT, 0) + 1
            return {
                StateKey.GP_FEEDBACK: {"is_pass": False, "target_node": last_node, "feedback_reason": reason},
                StateKey.RETRY_COUNT: current_retry,
            }

    except Exception as e:
        logger.error(f"  ⚠️ GP 내부 오류 (폴백 통과): {str(e)}")
        return {StateKey.GP_FEEDBACK: {"is_pass": True}}
