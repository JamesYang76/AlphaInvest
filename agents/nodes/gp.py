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
    risk_result = state.get(StateKey.RISK_RESULT, "해당 없음")
    portfolio_result = state.get(StateKey.PORTFOLIO_RESULT, "해당 없음")

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
                    [실시간 참조 데이터 (심사 및 교차 검증 기준)]
                    1. 거시경제 지표: {macro_data_str}
                    2. 거시경제 시황: {macro_result}
                    3. 리스크 분석 결과: {risk_result}
                    4. 포트폴리오 진단 결과: {portfolio_result}

                    ---
                    [심사 지침]
                    1. **에이전트 간 논리적 모순(Cross-Agent Contradiction) 확인**:
                       - 특히 [3. 리스크 분석 결과]에서 '위험'이나 '기술적 과열'로 경고된 섹션/종목이 [알파 노드]에서 추천되고 있다면 치명적인 논리 모순으로 판정하세요.
                       - [4. 포트폴리오 진단]의 매도 의견과 [알파 노드]의 추천이 상충되는지 확인하세요.
                    2. **팩트 체크**: '거시경제 지표' 수치가 보고서 본문에 정확히 반영되어 있는지 확인하세요.
                    3. **주의**: 개별 종목의 구체적 지표(PER 등)가 참조 데이터(거시)에 없다는 이유로 반려하지 마세요. 오직 '데이터 간의 충돌'과 '내부 모순'에 집중하세요.
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
                "risk_result": risk_result,
                "portfolio_result": portfolio_result,
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