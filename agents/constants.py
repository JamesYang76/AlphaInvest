from typing import Final


# ==========================================================
# 📌 AlphaInvest 상태(State) 키값 상수 정의
# ==========================================================
class StateKey:
    """
    AgentState 딕셔너리에서 사용되는 모든 키값을 상수로 관리합니다.
    오타 방지 및 코드 전역의 일관된 참조를 위해 사용합니다.
    """

    # 1. 공통 데이터
    USER_PORTFOLIO: Final = "user_portfolio"

    # 2. 결과물(Result) 키
    MACRO_RESULT: Final = "macro_result"
    MACRO_DATA: Final = "macro_data"  # 💡 원시 거시 지표 데이터 저장용
    RISK_RESULT: Final = "risk_result"
    ALPHA_RESULT: Final = "alpha_result"
    PORTFOLIO_RESULT: Final = "portfolio_result"
    CURRENT_REPORT: Final = "current_report"  # 💡 GP 심사용 공통 리포트 키
    FINAL_REPORT: Final = "final_report"
    NOTION_PAGE_URL: Final = "notion_page_url"  # 💡 Notion 발행 결과 URL

    # 3. 메모리(Messages) 키
    MACRO_MESSAGES: Final = "macro_messages"
    RISK_MESSAGES: Final = "risk_messages"
    ALPHA_MESSAGES: Final = "alpha_messages"
    PORTFOLIO_MESSAGES: Final = "portfolio_messages"


# ==========================================================
# 📌 AlphaInvest 에이전트(Node) 식별자 상수
# ==========================================================
class AgentName:
    """
    LangGraph 노드 및 엣지 연결에 사용되는 에이전트 이름 상수입니다.
    """

    MACRO: Final = "macro_agent"
    RISK: Final = "risk_agent"
    ALPHA: Final = "alpha_agent"
    PORTFOLIO: Final = "portfolio_agent"
    GP: Final = "gp_agent"
    CIO: Final = "cio_agent"
    PUBLISH: Final = "publish_agent"


# ==========================================================
# 📌 AlphaInvest 모델 세부 설정 (Model Config)
# ==========================================================
class ModelConfig:
    """
    모든 에이전트가 공유하는 기본 언어 모델 및 온도 등 파라미터를 중앙에서 관리합니다.
    """

    DEFAULT_LLM_MODEL: Final = "gpt-4o"
    DEFAULT_TEMPERATURE: Final = 0.0
