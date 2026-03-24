"""
Phase 3 — Portfolio Diagnosis (개인 계좌 진단)
담당 팀원이 이 파일을 작업합니다.

노드 구성:
  portfolio_diagnosis_node  : 보유 종목별 액션 플랜 제시
  critic_node_3             : 진단 실용성 검증
  should_retry_portfolio    : 재실행 여부 결정 (Conditional Edge)
"""
from typing import Literal
from langchain_core.messages import HumanMessage
from agent.state import InvestmentState
from data.fetchers import get_llm, fetch_stock_data


def portfolio_diagnosis_node(state: InvestmentState) -> dict:
    """Phase 3: 보유 종목 현재 환경 적합성 진단 + Hold/Switch/Reduce 제시"""
    print("\n👤 [Phase 3] 개인 계좌 진단 시작...")
    user_portfolio = state.get("user_portfolio", {})
    llm = get_llm(temperature=0.5)

    # 미국 주식 티커만 실시간 데이터 수집
    us_tickers = [
        k for k in user_portfolio.keys()
        if k.isupper() and len(k) <= 5 and not k.startswith("KODEX")
    ]
    stock_data = fetch_stock_data(us_tickers) if us_tickers else {}

    prompt = f"""
당신은 개인 포트폴리오 전문 어드바이저입니다.

[사용자 현재 보유 종목]
{user_portfolio}

[실시간 시장 데이터]
{stock_data if stock_data else "데이터 없음 (한국 ETF 위주)"}

[현재 거시경제 환경]
{state.get('macro_analysis', '')[:400]}

[절대 피해야 할 위험 섹터]
{state.get('risk_report', '')[:400]}

각 보유 종목에 대해 분석해주세요:

## 📊 계좌 진단 리포트

각 종목별:
### 종목명
- **현재 환경 적합성**: 상/중/하
- **추천 액션**: Hold(홀딩) / Switch(교체) / Reduce(비중 축소)
- **Switch라면**: 교체 대상 ETF/종목명 구체 제시
- **근거**: 2줄 설명
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    print("  ✅ Phase 3 진단 완료")
    return {
        "portfolio_diagnosis": response.content,
        "current_phase":       "portfolio_diagnosis",
        "retry_count":         0,
    }


def critic_node_3(state: InvestmentState) -> dict:
    """Critic 3: 계좌 진단 결과의 실용성 검증"""
    print("  🧠 [Critic 3] 계좌 진단 전략 검증 중...")
    llm = get_llm(temperature=0.1)

    prompt = f"""
포트폴리오 진단 결과의 실용성을 검증하세요.

[포트폴리오 진단 결과]
{state.get('portfolio_diagnosis', '')}

평가:
- 모든 보유 종목에 대해 액션 플랜이 있는가?
- 위험 섹터와 상충되는 추천이 없는가?
- 투자자가 실제로 실행할 수 있는 구체적 조언인가?

VERDICT: PASS 또는 VERDICT: FAIL
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    passed = "VERDICT: PASS" in response.content
    print(f"  {'✅ 검증 통과!' if passed else '❌ 검증 실패 → 재실행 예정'}")
    return {
        "critique":        response.content,
        "critique_passed": passed,
        "retry_count":     state.get("retry_count", 0) + (0 if passed else 1),
    }


def should_retry_portfolio(state: InvestmentState) -> Literal["retry", "next"]:
    """Conditional Edge: 검증 실패 시 portfolio_diagnosis_node 재실행"""
    if not state.get("critique_passed", False) and \
       state.get("retry_count", 0) < state.get("max_retries", 3):
        return "retry"
    return "next"
