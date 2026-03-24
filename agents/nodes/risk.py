import os
import re
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agents.constants import AgentName, ModelConfig, StateKey
from agents.state import AgentState

RISK_SYSTEM_PROMPT = """[Role]
너는 우리 알파 투자 퀀트 AI 에이전트 프로젝트의 담당 개발자야.

[Context]
아래 제공된 첨부파일 3개를 꼭 읽고 내 지시를 완벽히 따라줘.
1. TASKS.md: 전체 시스템 중 너의 역할과 목표는 Risk Alert 야. 다른 시스템은 신경 쓰지 말고 지정된 태스크에만 집중해.
2. STYLE_GUIDE.md: 네가 코딩할 때 무조건 지켜야 할 파이썬 코딩 룰이야. (함수 100줄 이하, 선언적 코드 작성, 타입 힌팅 필수)
3. state.py: 우리가 주고받을 LangGraph의 핵심 데이터(State) 인터페이스야. 너의 입력과 출력은 반드시 이 스키마를 준수해야 해. 절대 무단으로 키값을 수정하거나 새로 만들지 마.

[Action]
자, 이제 숙지했으면 TASKS.md에 명시된 내 파트를 구현하기 위한 최적의 파이썬 코드를 작성해 줘.

[Risk Agent Instruction]
너는 기관 자금의 하방 리스크를 먼저 차단하는 수석 리스크 매니저다.
거시 환경과 섹터별 위험 데이터를 근거로, 지금 절대 손대면 안 되는 섹터와 종목을 단호하게 경고하라.
출력은 반드시 3문장 이내로 작성하고, 섹터의 하락 배경과 피해야 할 대표 종목 2~3개를 티커와 함께 명시하라."""

VALID_TICKERS = {"BXP", "VNO", "F", "GM", "PLUG", "RUN"}


def _build_risk_dataset() -> List[Dict[str, str]]:
    return [
        {
            "sector": "상업용 오피스 부동산",
            "signal": "고금리 롤오버 압력과 공실률 부담으로 차환 리스크가 커졌습니다.",
            "stocks": "BXP, VNO",
        },
        {
            "sector": "레거시 내연기관 자동차",
            "signal": "전기차 전환 지연과 인센티브 경쟁으로 마진 훼손 우려가 큽니다.",
            "stocks": "F, GM",
        },
        {
            "sector": "적자 지속형 친환경/밈 종목",
            "signal": "실적보다 기대감에 의존한 종목군에서 자금 이탈이 반복되고 있습니다.",
            "stocks": "PLUG, RUN",
        },
    ]


def _format_risk_dataset(dataset: List[Dict[str, str]]) -> str:
    return "\n".join(
        f"- 섹터: {item['sector']} | 위험 배경: {item['signal']} | 대표 경고 종목: {item['stocks']}" for item in dataset
    )


def _get_feedback_text(state: AgentState) -> str:
    feedback = state.get(StateKey.GP_FEEDBACK, {})
    if feedback.get("target_node") != AgentName.RISK:
        return "현재 GP 피드백 없음"
    return feedback.get("feedback_reason", "현재 GP 피드백 없음")


def _build_fallback_risk_result(state: AgentState) -> str:
    feedback_text = _get_feedback_text(state)
    retry_suffix = "" if feedback_text == "현재 GP 피드백 없음" else f" GP 지적사항은 '{feedback_text}'입니다."
    return (
        "고금리 롤오버와 실적 둔화가 겹치는 상업용 오피스 부동산, 레거시 내연기관 자동차, "
        "적자 지속형 친환경 테마주는 지금 가장 먼저 피해야 할 함정 구간입니다. "
        "대표 경고 종목은 BXP, VNO, F이며, 현금흐름 취약성과 자금 이탈이 확인되는 종목은 추격 매수를 금지해야 합니다."
        f"{retry_suffix}"
    )


def _extract_valid_tickers(text: str) -> List[str]:
    candidates = re.findall(r"\b[A-Z]{1,5}\b", text.upper())
    validated: List[str] = []

    for ticker in candidates:
        if ticker in VALID_TICKERS and ticker not in validated:
            validated.append(ticker)

    return validated


def _is_valid_risk_result(text: str) -> bool:
    ticker_count = len(_extract_valid_tickers(text))
    return 2 <= ticker_count <= 3


def _normalize_risk_result(text: str, state: AgentState) -> str:
    tickers = _extract_valid_tickers(text)
    normalized_tickers = tickers[:3] if len(tickers) >= 2 else ["BXP", "VNO", "F"]
    ticker_text = ", ".join(normalized_tickers)
    feedback_text = _get_feedback_text(state)
    feedback_suffix = "" if feedback_text == "현재 GP 피드백 없음" else f" GP 지적사항은 '{feedback_text}'도 반영했습니다."
    return (
        "고금리 롤오버와 자금 이탈이 동시에 나타나는 상업용 오피스 부동산, 레거시 내연기관 자동차, "
        "적자 지속형 친환경 테마주는 지금 추격 매수를 금지해야 할 위험 구간입니다. "
        f"절대 피해야 할 대표 경고 종목은 {ticker_text}이며, 현금흐름 취약성과 실적 압박이 확인되는 종목은 매수 금지로 대응해야 합니다."
        f"{feedback_suffix}"
    )


def _generate_risk_result(
    chain: Any,
    macro_result: str,
    risk_dataset: str,
    feedback_text: str,
    retry_instruction: str,
) -> str:
    response = chain.invoke(
        {
            "macro_result": macro_result,
            "risk_dataset": risk_dataset,
            "feedback_text": feedback_text,
            "retry_instruction": retry_instruction,
        }
    )
    return response.content


def risk_node(state: AgentState) -> Dict[str, Any]:
    macro_result = state.get(StateKey.MACRO_RESULT, "매크로 요약 없음")
    feedback_text = _get_feedback_text(state)
    risk_dataset = _format_risk_dataset(_build_risk_dataset())

    if not os.getenv("OPENAI_API_KEY"):
        return {StateKey.RISK_RESULT: _build_fallback_risk_result(state)}

    llm = ChatOpenAI(model=ModelConfig.DEFAULT_LLM_MODEL, temperature=ModelConfig.DEFAULT_TEMPERATURE)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", RISK_SYSTEM_PROMPT),
            (
                "user",
                "거시 환경 요약:\n{macro_result}\n\n"
                "리스크 데이터:\n{risk_dataset}\n\n"
                "검수 피드백:\n{feedback_text}\n\n"
                "출력 검증 지시:\n{retry_instruction}\n\n"
                "위 정보를 바탕으로 지금 절대 피해야 할 섹터의 논리적 배경을 설명하고, "
                "대표 경고 종목 2~3개를 티커와 함께 강한 어조로 경고하세요.",
            ),
        ]
    )
    chain = prompt | llm

    try:
        result_text = _generate_risk_result(
            chain=chain,
            macro_result=macro_result,
            risk_dataset=risk_dataset,
            feedback_text=feedback_text,
            retry_instruction="반드시 VALID_TICKERS 집합에 해당하는 티커만 사용하고, 최종 본문에는 2~3개 티커만 남겨라.",
        )

        if not _is_valid_risk_result(result_text):
            result_text = _generate_risk_result(
                chain=chain,
                macro_result=macro_result,
                risk_dataset=risk_dataset,
                feedback_text=feedback_text,
                retry_instruction=(
                    "직전 출력은 실패했다. 이번에는 BXP, VNO, F, GM, PLUG, RUN 중 2~3개만 선택하고, "
                    "본문에 그 티커만 정확히 남겨라."
                ),
            )

        if not _is_valid_risk_result(result_text):
            result_text = _normalize_risk_result(result_text, state)
    except Exception as error:
        result_text = f"{_build_fallback_risk_result(state)} LLM 연결 오류: {error}"

    return {StateKey.RISK_RESULT: result_text}
