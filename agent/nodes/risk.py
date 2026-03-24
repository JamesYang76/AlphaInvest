"""
Phase 2 — Risk Detection (리스크 스캔)
담당 팀원이 이 파일을 작업합니다.

노드 구성:
  risk_scan_node    : 위험 섹터 Top 3 도출
  critic_node_2     : 거시경제 분석과 일관성 검증
  should_retry_risk : 재실행 여부 결정 (Conditional Edge)
"""
from typing import Literal
from langchain_core.messages import HumanMessage
from agent.state import InvestmentState
from data.fetchers import get_llm, fetch_news


def risk_scan_node(state: InvestmentState) -> dict:
    """Phase 2: 절대 투자해선 안 될 위험 섹터 Top 3 도출"""
    print("\n🔴 [Phase 2] 리스크 스캔 시작...")
    llm = get_llm(temperature=0.4)
    news = fetch_news("stock market risk sectors value trap avoid 2025")

    prompt = f"""
당신은 리스크 관리 전문 애널리스트입니다.

[현재 거시경제 환경]
{state.get('macro_analysis', '')}

[최신 시장 뉴스]
{news}

위 정보를 바탕으로 현재 한국/미국 증시에서
절대 투자해선 안 될 위험 섹터 및 함정 주식 Top 3를 선정해주세요.

각 항목 형식:
### [순위]. 섹터명
- **절대 피해야 할 대표 종목**: (한국 1개, 미국 1개)
- **회피 사유**: (데이터 기반으로 구체적으로 2-3줄)
- **핵심 위험 요인**: (불릿 2개)
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    print("  ✅ Phase 2 스캔 완료")
    return {
        "risk_report":   response.content,
        "current_phase": "risk_scan",
        "retry_count":   0,
    }


def critic_node_2(state: InvestmentState) -> dict:
    """Critic 2: 리스크 스캔 결과와 거시경제 분석의 일관성 검증"""
    print("  🧠 [Critic 2] 리스크-거시 일관성 검증 중...")
    llm = get_llm(temperature=0.1)

    prompt = f"""
거시경제 분석과 리스크 스캔 결과의 일관성을 검증하세요.

[거시경제 분석]
{state.get('macro_analysis', '')[:400]}

[리스크 스캔 결과]
{state.get('risk_report', '')}

검증 포인트:
- 두 분석이 서로 모순되지 않는가?
- 리스크 섹터 선정에 거시 데이터 근거가 있는가?
- 구체적인 종목이 포함되어 있는가?

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


def should_retry_risk(state: InvestmentState) -> Literal["retry", "next"]:
    """Conditional Edge: 검증 실패 시 risk_scan_node 재실행"""
    if not state.get("critique_passed", False) and \
       state.get("retry_count", 0) < state.get("max_retries", 3):
        return "retry"
    return "next"
