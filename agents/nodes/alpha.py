from __future__ import annotations

import json
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Dict, List, Sequence

from dotenv import load_dotenv

from agents.constants import AgentName, StateKey
from agents.state import AgentState
from data.fetchers import fetch_news, get_llm
from utils.logger import get_logger

logger = get_logger("agents.nodes.alpha")

load_dotenv()


@dataclass(frozen=True)
class SectorRule:
    name: str
    thesis: str
    us_leaders: Sequence[str]
    kr_leaders: Sequence[str]
    keywords: Sequence[str]


# =========================================================
# 🧠 뉴스 기반 동적 테마 발굴 (Top 5)
# =========================================================


def _discover_current_themes(llm: Any) -> List[SectorRule]:
    """뉴스를 실시간 검색하여 가장 핫한 투자 테마 5개를 발굴합니다."""
    logger.info("🔍 실시간 뉴스에서 가장 핫한 투자 테마 TOP 5 발굴 중...")

    # 1. 최신 주도주/테마 뉴스 검색
    query = "Hottest 5 investment themes and leading sectors in US and Korea stock markets today"
    news_context = fetch_news(query)

    # 2. LLM을 통한 5개 테마 구조화
    discovery_prompt = dedent(f"""
        당신은 세계 최고의 시장 전략가입니다.
        아래 최신 뉴스를 분석하여 현재 시장을 이끄는 가장 유망한 투자 테마 **5가지**를 선정하세요.

        [뉴스 데이터]
        {news_context}

        [출력 규격 (반드시 아래 JSON 리스트 형식으로만 답변)]
        [
            {{
                "name": "테마명",
                "thesis": "투자 논거 (한 문장)",
                "us_leaders": ["미국 종목1", "미국 종목2"],
                "kr_leaders": ["한국 종목1", "한국 종목2"],
                "keywords": ["키워드1", "키워드2", "키워드3"]
            }}
        ]
    """).strip()

    try:
        response = llm.invoke(discovery_prompt)
        # JSON 파싱 (마크다운 태그 제거 등)
        clean_content = response.content.replace("```json", "").replace("```", "").strip()
        themes_data = json.loads(clean_content)

        rules = [
            SectorRule(
                name=d["name"],
                thesis=d["thesis"],
                us_leaders=d["us_leaders"],
                kr_leaders=d["kr_leaders"],
                keywords=d["keywords"],
            )
            for d in themes_data
        ][:5]  # 정확히 5개 선정

        logger.info(f"✅ {len(rules)}개의 실시간 테마 발굴 완료: {[r.name for r in rules]}")
        return rules
    except Exception as e:
        logger.error(f"❌ 테마 발굴 실패: {e}")
        # 폴백 규칙 (최소 5개 반환)
        return [
            SectorRule("AI 인프라", "AI 데이터센터 수요 지속", ["NVIDIA"], ["SK하이닉스"], ["AI", "HBM"]),
            SectorRule(
                "원자력/유틸리티",
                "데이터센터 전력 공급 부족 및 에너지 인프라",
                ["SMR"],
                ["효성중공업"],
                ["Nuclear", "Grid"],
            ),
            SectorRule("비만 치료제", "글로벌 제약 시장의 거대 테마", ["Eli Lilly"], ["한미약품"], ["GLP-1", "Pharma"]),
            SectorRule(
                "방위산업",
                "지정학적 리스크 및 재무장 국면",
                ["Lockheed Martin"],
                ["한화에어로스페이스"],
                ["Defense", "Missile"],
            ),
            SectorRule("사이버 보안", "AI 위협 증가에 따른 보안 수요 필수화", ["CrowdStrike"], ["안랩"], ["Security", "Cyber"]),
        ]


def _score_rule(rule: SectorRule, context: str) -> int:
    """컨텍스트 내 키워드 출현 횟수 합산 (강도 측정)"""
    combined = context.lower()
    return sum(combined.count(kw.lower()) for kw in rule.keywords)


def alpha_node(state: AgentState) -> Dict[str, Any]:
    """
    Alpha 섹터 추천 노드 (뉴스 기반 지능형 Top 5)
    """
    llm = get_llm(temperature=0.0)

    # 0. GP 피드백 확인
    feedback = state.get(StateKey.GP_FEEDBACK, {})
    gp_feedback = ""
    if feedback.get("target_node") == AgentName.ALPHA:
        reason = feedback.get("feedback_reason", "")
        gp_feedback = dedent(f"""
            [수석 애널리스트 피드백]
            {reason}

            이전 분석이 위와 같은 이유로 반려되었습니다.
            이번에는 이 점을 보완하여 다시 작성해 주세요.
        """).strip()

    # 1. 뉴스에서 실시간 5대 테마 발굴
    current_rules = _discover_current_themes(llm)

    # 2. 분석 결과 맥락 구성
    macro_res = state.get(StateKey.MACRO_RESULT, "")
    risk_res = state.get(StateKey.RISK_RESULT, "")
    portfolio_res = state.get(StateKey.PORTFOLIO_RESULT, "")
    score_context = f"{macro_res} {risk_res} {portfolio_res}"

    # 3. 테마 점수화 및 랭킹
    scored = []
    for rule in current_rules:
        score = _score_rule(rule, score_context)
        scored.append(
            {
                "sector": rule.name,
                "score": score,
                "thesis": rule.thesis,
                "us_leaders": rule.us_leaders,
                "kr_leaders": rule.kr_leaders,
            }
        )

    # 리포트용 상위 3개 선정
    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)
    selected = ranked[:3]

    # 4. 최종 리포트 작성
    logger.info("✍️ 알파 섹터 리포트 작성 중...")
    report_prompt = dedent(f"""
        당심은 AlphaInvest의 수석 애널리스트입니다.
        실시간 발굴된 테마 데이터를 바탕으로 [알파 섹터 추천] 파트를 작성하세요.

        [발굴된 상위 섹터]
        {json.dumps(selected, ensure_ascii=False, indent=2)}

        [배경 데이터]
        - 거시 경제: {macro_res}
        - 리스크 관리: {risk_res}

        지침:
        1. 섹션 제목은 '## 3. 🚀 AI 인사이트: 주도 섹터 및 투자 테마'로 작성하세요.
        2. 발굴된 테마들의 투자 논거와 최신 시장 상황을 정교하게 엮으세요.
        3. 미국/한국 대표 종목을 명확히 명시하세요.
        4. 정중하고 전문적인 톤(PB 리포트 스타일)을 유지하세요.
        {gp_feedback}
    """).strip()

    try:
        response = llm.invoke(report_prompt)
        report_text = response.content
    except Exception as e:
        logger.error(f"❌ 리포트 생성 오류: {e}")
        report_text = "일시적인 시스템 오류로 알파 섹터 추천 리포트 생성을 완료하지 못했습니다."

    return {StateKey.ALPHA_RESULT: report_text, StateKey.CURRENT_REPORT: report_text, "last_node": AgentName.ALPHA}


if __name__ == "__main__":
    # 단독 테스트 코드
    from agents.state import get_initial_state

    test_state = get_initial_state([])
    test_state[StateKey.MACRO_RESULT] = "AI 인프라 투자 지속 및 금리 안정화 기대감"
    test_state[StateKey.RISK_RESULT] = "지정학적 리스크 및 인플레이션 둔화 속도 우려"

    logger.info("🚀 [단독 테스트] 알파 노드 실행 중...")
    result = alpha_node(test_state)
    print("\n" + "=" * 50)
    print(result[StateKey.ALPHA_RESULT])
    print("=" * 50)
