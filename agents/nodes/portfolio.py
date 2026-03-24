import os
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agents.constants import ModelConfig, StateKey
from agents.state import AgentState
from utils.macro_data import get_macro_context, get_sector_context
from utils.stock_data import get_stock_info

# ==========================================
# 🧠 시스템 프롬프트 (PB 페르소나 및 역할 정의)
# ==========================================
PORTFOLIO_SYSTEM_PROMPT = """당신은 상위 0.1% 초고액 자산가들을 전담 관리하는
VIP 웰스 매니저이자 프라이빗 뱅커(PB)입니다.
고객님이 보유한 종목 정보를 바탕으로 맞춤형 자산 진단 및 리밸런싱 전략을 제안하세요.

분석 및 출력 가이드라인:
1. 보유/교체(Hold or Switch) 우선 판단: 현재 포트폴리오가 기회 요인(AI, 에너지 등)에 잘 부합하고
   펀더멘털이 우수하다면, 무리한 교체 대신 **보유(HOLD)** 전략을 강력히 권고하고 그 이유를 설명하세요.
2. **진정한 다각화(True Diversification) 필수**: 현재 보유 종목과 동일한 산업군 및 리스크 요인
   (예: 삼성전자 보유 시 SK하이닉스 추천 금지)을 가진 종목의 추천을 지양하십시오.
   리밸런싱은 반드시 **상관관계가 낮은 섹터**를 제안하여 리스크를 분산시켜야 합니다.
3. 정밀 종목 진단: 보유 종목의 내재가치와 현재 '단기간 과열(Overheated)' 여부,
   그리고 고객의 **수익률(Profit Rate)**에 따른 매수/매도 적절성을 진단하세요.
4. 시황 및 섹터 로테이션: 교체 매매를 제안한다면, 현재 가장 강력한 모멘텀을 가진 **대안 섹터**
   (예: 원자재, 에너지 인프라 등)를 우선 고려하세요. 만약 반도체 내에서의 이동을 제안한다면,
   왜 **[레거시 메모리 사이클]**보다 제안 종목의 **[AI 구조적 성장]**이 지금 시점에서
   더 유리한지 명확한 차별성을 근거로 제시하십시오.
5. 전문적 소통: 단호하고 품격 있는 PB의 어조로 마크다운 리포트 형태로 작성하세요.
"""


def portfolio_node(state: AgentState) -> Dict[str, Any]:
    """
    유저의 포트폴리오를 진단하여 실시간 시황(Tavily, FRED 연동)에 맞는 전략을 생성하는 에이전트 노드입니다.
    """
    # 💡 0. OpenAI API 키 검증 (가드 클로즈)
    if not os.getenv("OPENAI_API_KEY"):
        return {StateKey.PORTFOLIO_RESULT: "LLM 연결 실패: .env 파일에 OPENAI_API_KEY를 먼저 설정해주세요."}

    # 💡 1. 모델 세팅 (일관성 있는 진단을 위해 온도 0)
    llm = ChatOpenAI(model=ModelConfig.DEFAULT_LLM_MODEL, temperature=ModelConfig.DEFAULT_TEMPERATURE)

    # 💡 2. 데이터 보강 (포트폴리오 개별 종목 정밀 데이터 및 시황 데이터 수집)
    user_portfolio = state.get(StateKey.USER_PORTFOLIO, [])
    # 개별 종목별 상세 데이터(종가, PER, PBR, 최근 뉴스) 실시간 확보 (pykrx/yfinance 연동)
    enriched_portfolio = []
    for stock in user_portfolio:
        ticker = stock.get("ticker")
        avg_price = stock.get("avg_price", 0)

        info = get_stock_info(ticker)

        # 수익률 계산 (현재가와 평단가 비교)
        try:
            # current_price 문자열에서 쉼표 제거 후 float 변환
            c_price = float(info.get("current_price", "0").replace(",", ""))
            if avg_price > 0:
                profit_rate = ((c_price - avg_price) / avg_price) * 100
                info["avg_price"] = f"{avg_price:,.0f}"
                info["profit_rate"] = f"{profit_rate:+.2f}%"
            else:
                info["avg_price"] = "N/A"
                info["profit_rate"] = "N/A"
        except Exception:
            info["avg_price"] = f"{avg_price:,.0f}"
            info["profit_rate"] = "계산 불가"

        enriched_portfolio.append(info)

    # 💡 3. 실시간 시황 데이터 수집 (Tavily Search 및 FRED 지표 연동)
    macro_info = get_macro_context()
    sector_info = get_sector_context()

    # 💡 4. 프롬프트 조립 (구조화된 마크다운 포맷)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PORTFOLIO_SYSTEM_PROMPT),
            (
                "user",
                "### 1. 고객 포트폴리오 현황\n"
                "{enriched_portfolio_str}\n\n"
                "### 2. 글로벌 거시 경제 상황 (Geopolitics & Macro)\n"
                "{macro_info}\n\n"
                "### 3. 주도 섹터 및 투자 테마 (Alpha & Sector Rotation)\n"
                "{sector_info}\n\n"
                "--- \n"
                "**지침**: 위 섹션의 데이터를 종합적으로 분석하여, "
                "고객의 수익을 극대화하면서도 리스크를 방어할 수 있는 "
                "PB 수준의 정교한 리밸런싱 포트폴리오 리포트를 작성하세요.",
            ),
        ]
    )

    # 포트폴리오 데이터를 가독성 좋게 변환 (YAML 형태의 문자열화)
    import yaml

    enriched_portfolio_str = yaml.dump(enriched_portfolio, allow_unicode=True, default_flow_style=False)

    # 💡 5. 체인 구축 및 실행
    input_data = {
        "enriched_portfolio_str": enriched_portfolio_str,
        "macro_info": macro_info,
        "sector_info": sector_info,
    }

    try:
        response = (prompt | llm).invoke(input_data)
        result_text = response.content
    except Exception as e:
        result_text = f"포트폴리오 진단 엔진 가동 중 오류 발생: {str(e)}"

    # 💡 6. 상태(State) 반환
    return {StateKey.PORTFOLIO_RESULT: result_text}
