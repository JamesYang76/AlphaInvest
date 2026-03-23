import os
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agents.constants import ModelConfig, StateKey
from agents.state import AgentState

# ==========================================
# 🧠 시스템 프롬프트 (페르소나 및 역할 정의)
# ==========================================
MACRO_SYSTEM_PROMPT = """당신은 월스트리트 20년 경력의 수석 거시 경제 분석가입니다.
입수된 경제 데이터와 뉴스를 융합하여, 투자 전략에 즉시 반영할 수 있는 '핵심 시황 요약'을 3문장 이내로 작성하세요.
절대 장황하게 쓰지 말고, 단호하고 확신에 찬 전문가의 어조를 유지해야 합니다."""


def macro_node(state: AgentState) -> Dict[str, Any]:
    # API 키 여부 사전 체크 (장애 원천 차단)
    if not os.getenv("OPENAI_API_KEY"):
        return {StateKey.MACRO_RESULT: "LLM 연결 실패: .env 파일에 OPENAI_API_KEY를 먼저 설정해주세요."}

    # 💡 1. 모델 세팅 (분석의 일관성을 위해 온도는 0에 가깝게)
    llm = ChatOpenAI(model=ModelConfig.DEFAULT_LLM_MODEL, temperature=ModelConfig.DEFAULT_TEMPERATURE)

    # 💡 2. 프롬프트 조립 (System과 User 역할의 완벽한 분리)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", MACRO_SYSTEM_PROMPT),
            ("user", "오늘 분석할 경제 데이터 및 주요 속보입니다:\n{data}"),
        ]
    )

    # 💡 3. 체인 구축 (Prompt 객체와 LLM 객체 연결)
    chain = prompt | llm

    # [주의] 지금은 예제용 가짜 데이터(Dummy)를 하드코딩하지만,
    # 실제 노드 구현 시에는 Tavily API 뉴스 검색 결과나 외부 경제 API 지표를 주입합니다.
    dummy_input_data = (
        "어젯밤 미국 연준(Fed)이 기준 금리를 3연속 동결했으며, 점도표 상 연내 인하 가능성을 배제했습니다. "
        "동시에 엔비디아 등 대형 기술주의 3분기 가이던스가 시장 예상치를 크게 상회했습니다."
    )

    try:
        # LLM에게 추론(invoke) 지시 및 결과 받기
        response = chain.invoke({"data": dummy_input_data})
        result_text = response.content
    except Exception as e:
        # API 인증 실패나 타임아웃 방어 로직 (장애가 나도 파이프라인이 죽지 않도록 방어)
        result_text = f"LLM 연결 중 오류 발생 (환경 변수에 OPENAI_API_KEY 세팅 필요): {str(e)}"

    # 💡 4. 규칙에 따라 정확하게 상태(State) 반환
    return {StateKey.MACRO_RESULT: result_text}
