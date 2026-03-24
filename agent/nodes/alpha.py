"""
Phase 4 — Alpha Hunter (알파 섹터 발굴)
담당 팀원이 이 파일을 작업합니다.

노드 구성:
  alpha_search_node  : 투자 기회 섹터 Top 2 발굴
  critic_node_4      : 전체 맥락 최종 검증
  should_retry_alpha : 재실행 여부 결정 (Conditional Edge)
"""
from typing import Literal
from langchain_core.messages import HumanMessage
from agent.state import InvestmentState
from data.fetchers import get_llm, fetch_news


def alpha_search_node(state: InvestmentState) -> dict:
    """Phase 4: 현재 환경에서 가장 확실한 투자 기회 섹터 Top 2 발굴"""
    print("\n🚀 [Phase 4] 알파 섹터 발굴 시작...")
    llm = get_llm(temperature=0.6)
    news = fetch_news("best investment sectors opportunities growth 2025 AI energy beauty")

    prompt = f"""
당신은 글로벌 투자 기회 발굴 전문가입니다.

[현재 거시경제 환경]
{state.get('macro_analysis', '')[:400]}

[반드시 피해야 할 섹터]
{state.get('risk_report', '')[:300]}

[최신 시장 트렌드]
{news}

위 정보를 종합하여 지금 가장 확실한 투자 기회 섹터 Top 2를 추천해주세요.
(피해야 할 섹터와 절대 겹치면 안 됩니다)

## 🚀 AI 추천 섹터 Top 2

### [섹터 1] 섹터명
- **투자 테마**:
- **투자 포인트**: (왜 지금인가? 2-3줄)
- **관심 종목**: 한국 2-3개, 미국 2-3개
- **투자 기간**: 단기(~3개월) / 중기(~1년) / 장기(1년+)

### [섹터 2] 섹터명
... (동일 형식)
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    print("  ✅ Phase 4 발굴 완료")
    return {
        "alpha_sectors": response.content,
        "current_phase": "alpha_search",
        "retry_count":   0,
    }


def critic_node_4(state: InvestmentState) -> dict:
    """Critic 4: 전체 분석 흐름과의 일관성 최종 검증"""
    print("  🧠 [Critic 4] 전체 맥락 최종 검증 중...")
    llm = get_llm(temperature=0.1)

    prompt = f"""
알파 섹터 추천이 전체 분석 흐름과 일관성이 있는지 최종 검증하세요.

[거시경제 요약]: {state.get('macro_analysis', '')[:250]}
[위험 섹터]:     {state.get('risk_report', '')[:250]}
[알파 섹터 추천]: {state.get('alpha_sectors', '')}

검증:
- 추천 섹터가 위험 섹터와 겹치지 않는가?
- 거시환경과 논리적으로 일치하는가?
- 구체적인 종목이 제시되어 있는가?

VERDICT: PASS 또는 VERDICT: FAIL
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    passed = "VERDICT: PASS" in response.content
    print(f"  {'✅ 최종 검증 통과!' if passed else '❌ 검증 실패 → 재실행 예정'}")
    return {
        "critique":        response.content,
        "critique_passed": passed,
        "retry_count":     state.get("retry_count", 0) + (0 if passed else 1),
    }


def should_retry_alpha(state: InvestmentState) -> Literal["retry", "next"]:
    """Conditional Edge: 검증 실패 시 alpha_search_node 재실행"""
    if not state.get("critique_passed", False) and \
       state.get("retry_count", 0) < state.get("max_retries", 3):
        return "retry"
    return "next"
