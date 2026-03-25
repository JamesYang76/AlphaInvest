from textwrap import dedent
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agents.constants import StateKey
from agents.nodes.gp_helpers import GP_SYSTEM_PROMPT, GPFeedback, get_target_key, run_repair_chain
from agents.state import AgentState
from data.fetchers import get_llm
from utils.logger import get_logger

# 로거 설정
logger = get_logger("agents.nodes.gp")
load_dotenv()


def gp_node(state: AgentState) -> Dict[str, Any]:
    """
    제출된 분석 리포트를 전문가의 관점에서 심사/검수하며,
    결함 발견 시 즉시 직접 수정(Auto-Repair)하여 최종 결과를 반환합니다.
    """
    llm = get_llm(model="gpt-5.4-mini", temperature=0.0)
    last_node = state.get("last_node", "알 수 없음")

    # 데이터 확보
    target_result = state.get(StateKey.CURRENT_REPORT, "분석 내용 누락")
    macro_result = state.get(StateKey.MACRO_RESULT, "분류되지 않음")
    macro_data = state.get(StateKey.MACRO_DATA, {})
    macro_data_str = ", ".join([f"{k}: {v}" for k, v in macro_data.items()]) if macro_data else "정보 없음"

    # 💡 [Phase 1: 심사]
    parser = JsonOutputParser(pydantic_object=GPFeedback)
    review_prompt = ChatPromptTemplate.from_messages(
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
                    - 거시경제 주요 지표 수치: {macro_data_str}
                    - 거시경제 시황 요약: {macro_result}

                    ---
                    [지침]
                    1. '실시간 참조 데이터'와 상충되는 치명적인 팩트 오류가 있는지 확인하고 JSON으로 답변하세요.
                    2. 주의:
                       - 보고서에 포함된 개별 종목의 수치(PER, ROE, 매입가, 수익률, 손실률 등)는 시스템 외부에서 실시간으로 수집된 정당한 데이터입니다. 
                       - 이 수치들이 '실시간 참조 데이터(거시)'에 없다는 이유만으로 '팩트 오류'로 판정하지 마십시오.
                """).strip(),
            ),
        ]
    )

    try:
        review_chain = review_prompt | llm | parser
        feedback = review_chain.invoke(
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
            return {}

        # 💡 [Phase 2: 자가 수정 (Auto-Repair)]
        logger.warning(f"  ❌ [{last_node}] 반려 및 직권 수정 시작: {reason}")

        repaired_content = run_repair_chain(llm=llm, target_result=target_result, reason=reason)
        logger.info(f"  ✨ [{last_node}] GP 직권 수정 완료.")

        # 에이전트별 결과 키 매핑 및 결과 반환
        target_key = get_target_key(last_node)

        return {
            target_key: repaired_content,
            StateKey.CURRENT_REPORT: repaired_content,
        }

    except Exception as e:
        logger.error(f"  ⚠️ GP 내부 오류 (폴백 통과): {str(e)}")
        return {}