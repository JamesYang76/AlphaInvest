# ============================================================
# Alpha Recommendation Module (Standalone MVP Version)
# ------------------------------------------------------------
# 목적:
# - AlphaInvest 프로젝트의 알파(추천) 모듈 하드코딩 버전
# - 앞선 3개 모듈(개인 포트폴리오 / 매크로 분석 / Risk Alert)의
#   결과를 "대표 시나리오" 형태로 입력받아 추천 결과를 생성
# - 발표용 / MVP 검증용으로 바로 실행 가능한 형태
# ============================================================

from typing import Dict, List


# ============================================================
# 1. 대표 시나리오 입력값 (하드코딩)
# ------------------------------------------------------------
# 목적:
# - 실제 프로젝트에서는 앞선 3개 모듈의 결과를 입력받지만,
#   현재 MVP 단계에서는 대표 시나리오를 하드코딩하여 알파 추천 흐름을 먼저 검증
# - 포트폴리오 분석, 매크로 분석, 리스크 경고 결과를 가정한 입력값을 구성
# - 이후 다른 agent와 연결될 때 실제 출력값으로 교체 가능한 형태로 설계
# ============================================================

portfolio = {
    "risk_tolerance": "medium",
    "investment_horizon": "mid_long",
    "objective": "balanced_growth",
    "current_holdings": ["AAPL", "TSLA", "QQQ"],
    "tech_weight": 0.70,
    "cash_ratio": 0.20,
}

macro = {
    "market_trend": "tech_bullish",
    "interest_rate": "cut_expected",
    "inflation": "stabilizing",
    "growth_signal": "soft_landing",
    "market_leadership": ["AI", "semiconductor", "quality_growth"],
}

risk = {
    "risk_level": "medium",
    "risk_flags": [
        "기술주 편중 리스크",
        "고변동 성장주 노출",
        "포트폴리오 방어력 부족",
    ],
    "avoid_tickers": ["TSLA"],
}


# ============================================================
# 2. 추천 후보 유니버스
# ------------------------------------------------------------
# 목적:
# - 알파 추천 대상이 되는 종목 및 ETF 후보군을 정의
# - 각 자산의 섹터, 위험도, 성격(성장/방어), 테마 적합도 등을 구조화하여 저장
# - 단순 추천이 아니라 포트폴리오·매크로·리스크 결과를 반영한 비교 가능한 후보 집합 마련
# ============================================================

ASSET_UNIVERSE = [
    {
        "ticker": "SOXX",
        "name": "iShares Semiconductor ETF",
        "category": "성장",
        "sector": "technology",
        "risk_level": "medium_high",
        "theme": ["AI", "semiconductor"],
    },
    {
        "ticker": "MSFT",
        "name": "Microsoft",
        "category": "성장",
        "sector": "technology",
        "risk_level": "medium",
        "theme": ["AI", "quality_growth"],
    },
    {
        "ticker": "XLV",
        "name": "Health Care Select Sector SPDR Fund",
        "category": "방어",
        "sector": "healthcare",
        "risk_level": "low_medium",
        "theme": ["defensive", "quality"],
    },
    {
        "ticker": "IEF",
        "name": "iShares 7-10 Year Treasury Bond ETF",
        "category": "방어",
        "sector": "fixed_income",
        "risk_level": "low",
        "theme": ["bond", "defensive"],
    },
]


# ============================================================
# 3. 보조 함수
# ------------------------------------------------------------
# 목적:
# - 추천 로직에서 반복적으로 사용하는 보조 계산 및 판별 기능을 분리
# - 위험도 정규화, 주의 자산 판별, 추천 사유 생성 등 핵심 로직을 지원
# - 코드 가독성과 재사용성을 높이고, 이후 규칙 수정 및 확장을 쉽게 하기 위한 구조
# ============================================================

def risk_to_num(level: str) -> int:
    mapping = {
        "low": 1,
        "low_medium": 2,
        "medium": 3,
        "medium_high": 4,
        "high": 5,
    }
    return mapping.get(level, 3)


def score_asset(asset: Dict, portfolio: Dict, macro: Dict, risk: Dict) -> Dict:
    score = 50
    drivers: List[str] = []

    # 1) 매크로 반영
    if macro["market_trend"] == "tech_bullish" and asset["sector"] == "technology":
        score += 15
        drivers.append("AI 및 기술주 중심의 시장 강세 반영(+15)")

    if macro["interest_rate"] == "cut_expected" and asset["category"] == "성장":
        score += 8
        drivers.append("금리 인하 기대 환경에서 성장 자산 선호(+8)")

    if macro["interest_rate"] == "cut_expected" and asset["sector"] == "fixed_income":
        score += 8
        drivers.append("금리 인하 기대 환경에서 채권 자산 우호(+8)")

    # 2) 포트폴리오 보완성 반영
    if portfolio["tech_weight"] > 0.60 and asset["sector"] != "technology":
        score += 14
        drivers.append("기술주 편중 완화 및 분산 효과(+14)")

    if asset["ticker"] in portfolio["current_holdings"]:
        score -= 8
        drivers.append("기존 보유 자산과 중복(-8)")

    # 3) 리스크 반영
    portfolio_risk = risk_to_num(portfolio["risk_tolerance"])
    asset_risk = risk_to_num(asset["risk_level"])
    overall_risk = risk_to_num(risk["risk_level"])

    if asset_risk - portfolio_risk >= 2:
        score -= 12
        drivers.append("투자 성향 대비 과도한 위험도(-12)")
    elif asset_risk - portfolio_risk == 1:
        score -= 5
        drivers.append("투자 성향 대비 다소 높은 위험도(-5)")

    if overall_risk >= 3 and asset_risk >= 4:
        score -= 7
        drivers.append("현재 리스크 환경에서 고위험 자산 감점(-7)")

    if "포트폴리오 방어력 부족" in risk["risk_flags"] and asset["category"] == "방어":
        score += 10
        drivers.append("방어력 보강 목적에 부합(+10)")

    score = max(0, min(score, 100))

    return {
        "ticker": asset["ticker"],
        "name": asset["name"],
        "category": asset["category"],
        "sector": asset["sector"],
        "score": score,
        "drivers": drivers,
    }


def generate_reason(asset: Dict, portfolio: Dict, macro: Dict, risk: Dict) -> str:
    reasons = []

    if asset["sector"] == "technology":
        reasons.append("현재 시장 주도 테마인 AI·반도체 흐름과 정합성이 높습니다")

    if asset["category"] == "성장" and macro["interest_rate"] == "cut_expected":
        reasons.append("금리 인하 기대 구간에서 성장 자산 선호 흐름의 수혜가 기대됩니다")

    if portfolio["tech_weight"] > 0.60 and asset["sector"] != "technology":
        reasons.append("기존 기술주 편중 포트폴리오의 분산 효과를 기대할 수 있습니다")

    if "포트폴리오 방어력 부족" in risk["risk_flags"] and asset["category"] == "방어":
        reasons.append("현재 포트폴리오의 방어력 보완에 적합합니다")

    if not reasons:
        reasons.append("포트폴리오와 시장 환경을 종합했을 때 보완적 역할이 가능합니다")

    return " / ".join(reasons)


# ============================================================
# 4. 핵심 추천 로직
# ------------------------------------------------------------
# 목적:
# - 앞선 분석 결과를 종합하여 추천 자산을 점수화하고 최종 추천안을 생성
# - 매크로 적합도, 포트폴리오 보완성, 리스크 적합성을 함께 반영해 우선순위를 결정
# - AlphaInvest의 alpha agent가 실제 투자 아이디어를 도출하는 핵심 의사결정 단계
# ============================================================

def generate_alpha_report(portfolio: Dict, macro: Dict, risk: Dict) -> Dict:
    scored_assets = []

    for asset in ASSET_UNIVERSE:
        scored_assets.append(score_asset(asset, portfolio, macro, risk))

    scored_assets.sort(key=lambda x: x["score"], reverse=True)
    top_assets = scored_assets[:3]

    recommendations = []
    for ranked in top_assets:
        original = next(asset for asset in ASSET_UNIVERSE if asset["ticker"] == ranked["ticker"])
        recommendations.append({
            "ticker": ranked["ticker"],
            "name": ranked["name"],
            "category": ranked["category"],
            "sector": ranked["sector"],
            "score": ranked["score"],
            "reason": generate_reason(original, portfolio, macro, risk),
            "score_drivers": ranked["drivers"],
        })

    strategy_summary = (
        "현재 시장은 금리 인하 기대와 AI 중심의 기술주 강세가 동시에 나타나는 구간으로 해석됩니다. "
        "다만 기존 포트폴리오가 기술주에 편중되어 있고 방어 자산 비중이 낮아, "
        "이번 알파 추천은 성장성 유지와 포트폴리오 안정성 보완을 함께 고려하는 방향으로 설계되었습니다."
    )

    caution_note = (
        "본 추천은 MVP 검증용 대표 시나리오를 기반으로 생성된 결과이며, "
        "실제 운용 단계에서는 실시간 시장 데이터, 사용자 보유 종목, 리스크 허용 범위를 추가 반영해야 합니다."
    )

    report_text = format_report_text(recommendations, strategy_summary, caution_note)

    return {
        "module_name": "Alpha Recommendation Module",
        "validation_mode": "MVP hard-coded scenario",
        "recommended_assets": recommendations,
        "strategy_summary": strategy_summary,
        "caution_note": caution_note,
        "report_text": report_text,
    }


# ============================================================
# 5. 리포트 형식 출력 함수
# ------------------------------------------------------------
# 목적:
# - 추천 결과를 사람이 읽기 쉬운 리포트 형식으로 변환
# - 발표 및 MVP 검증 단계에서 결과를 직관적으로 확인할 수 있도록 구성
# - 이후 GP feedback 및 CIO 단계로 연결될 수 있는 자연어 기반 출력 형태를 마련
# ============================================================

def format_report_text(
    recommendations: List[Dict],
    strategy_summary: str,
    caution_note: str,
) -> str:
    lines = []

    lines.append("AlphaInvest 알파 추천 리포트")
    lines.append("=" * 50)
    lines.append("")
    lines.append("[1] 투자 전략 요약")
    lines.append(strategy_summary)
    lines.append("")
    lines.append("[2] 추천 자산")
    
    for idx, item in enumerate(recommendations, start=1):
        lines.append(f"{idx}. {item['ticker']} ({item['name']})")
        lines.append(f"   - 카테고리: {item['category']}")
        lines.append(f"   - 섹터: {item['sector']}")
        lines.append(f"   - 추천 점수: {item['score']}/100")
        lines.append(f"   - 추천 사유: {item['reason']}")
        lines.append("   - 점수 반영 요인:")
        for driver in item["score_drivers"]:
            lines.append(f"     · {driver}")
        lines.append("")

    lines.append("[3] 유의사항")
    lines.append(caution_note)

    return "\n".join(lines)


# ============================================================
# 6. 실행부
# ------------------------------------------------------------
# 목적:
# - 하드코딩된 대표 시나리오를 기반으로 alpha agent가 정상 동작하는지 최종 검증
# - 추천 결과와 리포트 출력이 실제로 생성되는지 확인
# - MVP 단계에서 "끝까지 돌아가는 최소 파이프라인"을 확인하기 위한 테스트 실행 구간
# ============================================================

if __name__ == "__main__":
    result = generate_alpha_report(portfolio, macro, risk)

    print("\n" + result["report_text"] + "\n")