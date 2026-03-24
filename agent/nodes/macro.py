"""
Phase 1 — Macro Analysis (거시경제 분석)
담당 팀원이 이 파일을 작업합니다.

노드 구성:
  macro_context_node  : 거시 지표 + 뉴스 → LLM 분석
  critic_node_1       : 분석 품질 검증
  should_retry_macro  : 재실행 여부 결정 (Conditional Edge)
"""
from typing import Literal
from langchain_core.messages import HumanMessage
from agent.state import InvestmentState
from data.fetchers import get_llm, fetch_macro_data, fetch_news


def macro_context_node(state: InvestmentState) -> dict:
    """Phase 1: 거시경제 지표와 뉴스를 분석하여 투자 환경 요약"""
    print("\n🌐 [Phase 1] 거시경제 분석 시작...")

    macro_data = fetch_macro_data()
    news = fetch_news("Federal Reserve interest rate inflation economic outlook 2025")
    llm = get_llm(temperature=0.3)

    prompt = f"""
당신은 글로벌 거시경제 전문 애널리스트입니다.
아래 경제 지표와 뉴스를 분석하여 투자 환경을 간결하게 요약해주세요.

[거시경제 지표]
- 기준금리 (Fed Rate): {macro_data['fed_rate']}
- 소비자물가 (CPI): {macro_data['cpi']}
- 달러 인덱스 (DXY): {macro_data['dxy']}
- 시장 심리: {macro_data['market_trend']}
- VIX (공포지수): {macro_data['vix']}
- S&P500 추세: {macro_data['sp500_trend']}

[최신 뉴스]
{news}

다음 형식으로 분석해주세요:
## 거시경제 환경 요약
1. **현재 상황**: (2-3줄)
2. **투자자에게 시사하는 점**: (2-3줄)
3. **주요 리스크 요인**: (불릿 포인트 3개)
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    print("  ✅ Phase 1 분석 완료")
    return {
        "macro_analysis": response.content,
        "current_phase":  "macro_analysis",
        "retry_count":    0,
    }


def critic_node_1(state: InvestmentState) -> dict:
    """Critic 1: 거시경제 분석 품질 검증"""
    print("  🧠 [Critic 1] 거시경제 분석 검증 중...")
    llm = get_llm(temperature=0.1)

    prompt = f"""
당신은 엄격한 금융 리서치 품질 관리자입니다.
아래 거시경제 분석 결과를 검토하고 품질을 평가하세요.

[분석 결과]
{state.get('macro_analysis', '')}

평가 기준:
1. 데이터 기반 근거가 명확한가?
2. 투자자에게 실질적으로 도움이 되는 인사이트가 있는가?
3. 논리적 모순이나 오류가 없는가?
4. 리스크 요인이 구체적으로 언급되었는가?

⚠️ 반드시 마지막 줄에 아래 중 하나로 끝내세요:
VERDICT: PASS
VERDICT: FAIL
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    passed = "VERDICT: PASS" in response.content
    print(f"  {'✅ 검증 통과!' if passed else '❌ 검증 실패 → 재실행 예정'}")
    return {
        "critique":        response.content,
        "critique_passed": passed,
        "retry_count":     state.get("retry_count", 0) + (0 if passed else 1),
    }


def should_retry_macro(state: InvestmentState) -> Literal["retry", "next"]:
    """Conditional Edge: 검증 실패 시 macro_context_node 재실행"""
    if not state.get("critique_passed", False) and \
       state.get("retry_count", 0) < state.get("max_retries", 3):
        print(f"  🔄 재실행 ({state.get('retry_count')}/{state.get('max_retries', 3)}회)")
        return "retry"
    return "next"
