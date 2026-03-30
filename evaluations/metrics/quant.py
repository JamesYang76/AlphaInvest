from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# =========================================================
# 동의어 매핑 테이블: entity → [한글/영어 동의어 리스트]
# 영어 entity를 한글 리포트에서도 인식하기 위한 매핑입니다.
# =========================================================
ENTITY_SYNONYMS: Dict[str, List[str]] = {
    "FED": ["fed", "연준", "연방준비제도", "federal reserve"],
    "Inflation": ["inflation", "인플레이션", "물가상승", "물가"],
    "CPI": ["cpi", "소비자물가지수", "소비자물가"],
    "GDP": ["gdp", "국내총생산"],
    "VIX": ["vix", "변동성지수", "공포지수"],
    "S&P500": ["s&p500", "s&p 500", "spx", "s&p"],
    "NVIDIA": ["nvidia", "엔비디아", "nvda"],
    "Apple": ["apple", "애플", "aapl"],
    "Samsung": ["samsung", "삼성전자", "005930"],
    "Rate": ["rate", "금리", "기준금리", "연방기금금리"],
    "Bond": ["bond", "채권", "국채"],
    "Dollar": ["dollar", "달러", "dxy"],
}

# 섹션당 최소 단어 수 기준 (이 이상이면 "충실"로 판단)
MIN_WORDS_PER_SECTION = 100

# 1000단어당 숫자 데이터가 이 개수 이상이면 만점
NUMERIC_DENSITY_BASELINE = 20

# 4대 카테고리 가중치 (합계 = 1.0)
COMPOSITE_WEIGHTS = {
    "completeness": 0.25,  # 완성도 = 섹션 구조 + 섹션 충실도
    "accuracy": 0.25,  # 정확도 = 수치 정확도 (환각 탐지)
    "coverage": 0.25,  # 커버리지 = 핵심 시장 지표 언급
    "relevance": 0.25,  # 관련성 = 포트폴리오 티커 + entity 검출
}

# 티커 → 한글/영어 별칭 매핑
TICKER_ALIASES: Dict[str, List[str]] = {
    "005930.ks": ["삼성전자", "samsung", "005930"],
    "000660.ks": ["sk하이닉스", "sk hynix", "000660", "hynix"],
    "035420.ks": ["naver", "네이버", "035420"],
    "051910.ks": ["lg화학", "lg chem", "051910"],
    "aapl": ["apple", "애플", "aapl"],
    "msft": ["microsoft", "마이크로소프트", "msft"],
    "nvda": ["nvidia", "엔비디아", "nvda"],
}


# =========================================================
# 내부 헬퍼
# =========================================================


# 시나리오: 벤치마크에서 기대 entity가 리포트에 있는지 볼 때 — 본문+동의어 매칭으로 한 항목을 판별한다.
def _resolve_entity(entity: str, report_lower: str) -> bool:
    """entity 또는 그 동의어 중 하나라도 리포트에 있으면 True."""
    base = [entity.lower()]
    synonyms = ENTITY_SYNONYMS.get(entity, [])
    for candidate in base + synonyms:
        if candidate.lower() in report_lower:
            return True
    return False


# =========================================================
# 1. Entity 검출률 (동의어 매핑 포함)
# =========================================================


# 시나리오: 평가 스크립트가 CIO 리포트 품질을 셀 때 — 골든 샘플의 기대 엔티티가 얼마나 등장했는지 비율로 낸다.
def calculate_extraction_score(actual_report: str, expected_entities: List[str]) -> float:
    """
    기대했던 주요 경제 지표(Entity)들이 CIO 최종 리포트에 포함되었는지 점수화합니다.
    동의어 매핑을 통해 한글/영어 표현 모두 인식합니다.

    예) "FED" → ["fed", "연준", "연방준비제도", "federal reserve"] 중 하나라도 있으면 검출로 처리
    """
    if not expected_entities:
        return 1.0
    report_lower = actual_report.lower()
    found = [1 for entity in expected_entities if _resolve_entity(entity, report_lower)]
    return round(sum(found) / len(expected_entities), 4)


# =========================================================
# 2. 4대 섹션 구조 검증 (기존 유지)
# =========================================================


# 시나리오: 파이프라인 산출물 QA — 거시·포트·리스크·알파 네 섹션 제목/키워드가 모두 있는지 체크한다.
def evaluate_cio_report_structure(report: str) -> Dict[str, bool]:
    """
    CIO 최종 리포트가 요구된 4대 핵심 섹션을 모두 포함하고 있는지 검증합니다.
    1. 거시경제 시황
    2. 포트폴리오 진단
    3. 리스크 경고
    4. 투자 기회
    """
    sections = {
        "macro": "거시경제 시황",
        "portfolio": "포트폴리오 진단",
        "risk": "리스크 경고",
        "alpha": "투자 기회",
    }
    return {key: name in report for key, name in sections.items()}


# =========================================================
# 3. VIX ↔ 리스크 스코어 수치 일관성 검증 (기존 유지)
# =========================================================


# 시나리오: (선택) 거시 VIX와 별도 리스크 점수 필드가 함께 있을 때 — 극단적 모순이 없는지 본다.
def evaluate_numeric_consistency(macro_data: Dict[str, Any], risk_data: Dict[str, Any]) -> bool:
    """거시 지표(VIX 등)와 리스크 스코어 간의 논리적 모순 여부를 검증합니다."""
    vix = float(macro_data.get("vix", 20))
    risk_score = float(risk_data.get("risk_score", 50))
    # VIX가 30 이상(공포)인데 리스크 스코어가 30 미만(매우 안전)이면 일관성 오류
    return not (vix > 30 and risk_score < 30)


# =========================================================
# 4. 섹션별 내용 충실도 (단어 수 기반)
# =========================================================


# 시나리오: CIO 리포트가 형식만 갖춘 빈 껍데인지 — 섹션별 단어 수로 충실도 점수를 낸다.
def calculate_section_depth_score(report: str) -> Dict[str, Any]:
    """
    섹션별 단어 수를 측정하여 내용 충실도를 점수화합니다.
    MIN_WORDS_PER_SECTION(100단어) 이상이면 해당 섹션 '충실'로 판단합니다.

    Returns:
        각 섹션의 word_count, sufficient 여부, 전체 score(0.0~1.0) 포함 dict
    """
    section_patterns = {
        "macro": r"(?:## I\.|거시경제 시황)(.*?)(?=## II\.|포트폴리오 진단|$)",
        "portfolio": r"(?:## II\.|포트폴리오 진단)(.*?)(?=## III\.|리스크 경고|$)",
        "risk": r"(?:## III\.|리스크 경고)(.*?)(?=## IV\.|투자 기회|$)",
        "alpha": r"(?:## IV\.|투자 기회)(.*?)$",
    }

    result: Dict[str, Any] = {}
    for key, pattern in section_patterns.items():
        match = re.search(pattern, report, re.DOTALL)
        word_count = len(match.group(1).split()) if match else 0
        result[key] = {
            "word_count": word_count,
            "sufficient": word_count >= MIN_WORDS_PER_SECTION,
        }

    sufficient_count = sum(1 for v in result.values() if isinstance(v, dict) and v["sufficient"])
    result["score"] = round(sufficient_count / len(section_patterns), 4)
    return result


# =========================================================
# 5. 포트폴리오 티커 언급률
# =========================================================


# 시나리오: 맞춤 리포트인지 확인 — 입력 포트폴리오 티커(별칭 포함)가 본문에 얼마나 등장하는지 측정한다.
def calculate_ticker_mention_score(report: str, portfolio: List[Dict[str, Any]]) -> float:
    """
    포트폴리오의 각 티커(종목)가 리포트에 언급되었는지 측정합니다.
    TICKER_ALIASES 매핑을 통해 한글 회사명도 인식합니다.

    Args:
        portfolio: [{"ticker": "005930.KS", ...}, ...] 형태의 포트폴리오 리스트
    """
    if not portfolio:
        return 1.0

    report_lower = report.lower()
    found = 0
    for item in portfolio:
        ticker = item.get("ticker", "").lower()
        aliases = TICKER_ALIASES.get(ticker, [ticker])
        if any(alias.lower() in report_lower for alias in aliases):
            found += 1

    return round(found / len(portfolio), 4)


# =========================================================
# 6. 숫자 데이터 밀도 (%, 금리, 지수 등)
# =========================================================


# 시나리오: 리포트에 정량 근거가 충분한지 — 숫자·단위 패턴 밀도로 스코어를 낸다.
def calculate_numeric_density_score(report: str) -> float:
    """
    리포트 내 숫자 데이터(%, 금리, 지수 등) 밀도를 측정합니다.
    1000단어당 NUMERIC_DENSITY_BASELINE(20)개 이상이면 1.0(만점)을 반환합니다.
    """
    numeric_pattern = r"[\+\-]?\d+\.?\d*\s*(?:%|bp|원|달러|포인트|배|억|조|만)?"
    matches = re.findall(numeric_pattern, report)

    word_count = len(report.split())
    if word_count == 0:
        return 0.0

    density = len(matches) / word_count * 1000
    return round(min(density / NUMERIC_DENSITY_BASELINE, 1.0), 4)


# =========================================================
# 7. 종합 점수 (Composite Score)
# =========================================================

# =========================================================
# 8. Coverage Completeness Score (핵심 시장 지표 커버리지)
# =========================================================

# 전문 투자 리포트에서 반드시 다뤄야 할 12개 핵심 시장 지표 체크리스트
MARKET_INDICATORS_CHECKLIST: Dict[str, List[str]] = {
    "fed_rate": ["연방기금금리", "기준금리", "연준", "fed rate", "federal reserve"],
    "treasury_10y": ["10년물", "국채 10년", "treasury", "ten year", "10y"],
    "cpi": ["cpi", "소비자물가지수", "소비자물가"],
    "inflation": ["인플레이션", "inflation", "물가상승", "물가"],
    "sp500": ["s&p500", "s&p 500", "spx", "s&p"],
    "vix": ["vix", "변동성지수", "변동성", "공포지수"],
    "gdp": ["gdp", "국내총생산", "경제성장"],
    "unemployment": ["실업률", "unemployment", "고용"],
    "dxy": ["dxy", "달러인덱스", "달러 인덱스", "달러"],
    "exchange_rate": ["환율", "원달러", "usd/krw", "원/달러"],
    "high_yield": ["하이일드", "high yield", "hy spread"],
    "credit_spread": ["크레딧 스프레드", "credit spread", "스프레드"],
}


# 시나리오: 기관 리포트 수준의 시장 지표 커버리지 — 12개 체크리스트 키워드가 얼마나 들어갔는지 센다.
def calculate_coverage_completeness_score(report: str) -> Dict[str, Any]:
    """
    전문 투자 리포트가 12개 핵심 시장 지표를 얼마나 커버하는지 측정합니다.
    JP Morgan, Goldman Sachs 등 기관 리포트 QA에서 사용하는 방식입니다.

    Returns:
        각 지표 포함 여부(covered), 커버된 지표 수, score(0.0~1.0) 포함 dict
    """
    report_lower = report.lower()
    result: Dict[str, Any] = {}

    for indicator, keywords in MARKET_INDICATORS_CHECKLIST.items():
        covered = any(kw.lower() in report_lower for kw in keywords)
        result[indicator] = covered

    covered_count = sum(1 for v in result.values() if isinstance(v, bool) and v)
    result["covered_count"] = covered_count
    result["total"] = len(MARKET_INDICATORS_CHECKLIST)
    result["score"] = round(covered_count / len(MARKET_INDICATORS_CHECKLIST), 4)
    return result


# =========================================================
# 9. Factual Grounding Score (수치 정확도 / 환각 탐지)
# =========================================================

# 리포트에서 각 지표 수치를 추출하기 위한 정규식 패턴
INDICATOR_EXTRACT_PATTERNS: Dict[str, List[str]] = {
    "fed_rate": [r"(?:연방기금금리|기준금리|연준.*?금리|금리)[^0-9]*([0-9]+\.?[0-9]*)\s*%"],
    "cpi": [r"CPI[^0-9]*([0-9]+\.?[0-9]*)\s*%", r"소비자물가(?:지수)?[^0-9]*([0-9]+\.?[0-9]*)\s*%"],
    "vix": [r"VIX\s*(?:지수|는|가|은|:)?\s*([0-9]+\.?[0-9]*)(?!\s*%)", r"변동성지수\s*(?:는|가|은|:)?\s*([0-9]+\.?[0-9]*)(?!\s*%)"],
    "unemployment": [r"실업률[^0-9]*([0-9]+\.?[0-9]*)\s*%", r"unemployment[^0-9]*([0-9]+\.?[0-9]*)\s*%"],
    "ten_year_yield": [r"(?:10년물|국채\s*10년)[^0-9]*([0-9]+\.?[0-9]*)\s*%", r"treasury[^0-9]*([0-9]+\.?[0-9]*)\s*%"],
}

# 허용 오차 기준 (상대 오차 5% 이내면 정확으로 판정)
FACTUAL_TOLERANCE = 0.05


# 시나리오: factual 점수 계산 시 — fetch_macro_data 문자열/숫자 혼합 값을 float으로 정규화한다.
def _parse_macro_value(raw: Any) -> Optional[float]:
    """fetch_macro_data() 반환값("3.64%" 또는 3.64)을 float으로 변환."""
    if raw is None or raw == "N/A":
        return None
    try:
        return float(str(raw).replace("%", "").strip())
    except ValueError:
        return None


# 시나리오: 환각 탐지 — 리포트에 적힌 금리·VIX 등이 실제 macro_data와 허용 오차 안에 맞는지 본다.
def calculate_factual_grounding_score(
    report: str,
    macro_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    리포트에 등장한 수치가 실제 FRED/yfinance 데이터와 얼마나 일치하는지 측정합니다.
    LLM 환각(Hallucination) 탐지에 사용됩니다.

    Args:
        report: CIO 최종 리포트 텍스트
        macro_data: fetch_macro_data() 결과 (None이면 내부에서 직접 호출)

    Returns:
        지표별 비교 결과와 score(0.0~1.0) 포함 dict
    """
    if macro_data is None:
        from data.fetchers import fetch_macro_data

        macro_data = fetch_macro_data()

    # fetch_macro_data() 키 → INDICATOR_EXTRACT_PATTERNS 키 매핑
    actual_values: Dict[str, Optional[float]] = {
        "fed_rate": _parse_macro_value(macro_data.get("d_fed_rate") or macro_data.get("fed_rate")),
        "cpi": _parse_macro_value(macro_data.get("cpi")),
        "vix": _parse_macro_value(macro_data.get("vix")),
        "unemployment": _parse_macro_value(macro_data.get("unemployment")),
        "ten_year_yield": _parse_macro_value(macro_data.get("ten_year_yield")),
    }

    result: Dict[str, Any] = {}
    checked = 0
    passed = 0

    for indicator, patterns in INDICATOR_EXTRACT_PATTERNS.items():
        actual = actual_values.get(indicator)
        if actual is None:
            result[indicator] = {"status": "skipped", "reason": "실제 데이터 없음"}
            continue

        # 리포트에서 수치 추출
        extracted: Optional[float] = None
        for pattern in patterns:
            match = re.search(pattern, report, re.IGNORECASE)
            if match:
                try:
                    extracted = float(match.group(1))
                    break
                except ValueError:
                    continue

        if extracted is None:
            result[indicator] = {"status": "not_found", "actual": actual}
            continue

        # 상대 오차 계산
        relative_error = abs(extracted - actual) / actual if actual != 0 else 0.0
        is_accurate = relative_error <= FACTUAL_TOLERANCE

        result[indicator] = {
            "status": "accurate" if is_accurate else "hallucination",
            "extracted": extracted,
            "actual": actual,
            "relative_error": round(relative_error, 4),
        }
        checked += 1
        if is_accurate:
            passed += 1

    result["score"] = round(passed / checked, 4) if checked > 0 else 1.0
    result["checked_count"] = checked
    result["passed_count"] = passed
    return result


# =========================================================
# 10. 4대 카테고리 점수
# =========================================================


# 시나리오: 종합 점수의 completeness 축 — 섹션 존재(structure)와 단어 수(depth)를 평균한다.
def calculate_completeness_score(
    structure_check: Dict[str, bool],
    section_depth: Dict[str, Any],
) -> float:
    """
    완성도 (Completeness): 필수 섹션 존재 여부 + 섹션별 내용 충실도 평균
    """
    structure_score = sum(v for v in structure_check.values() if isinstance(v, bool)) / len(structure_check)
    depth_score = section_depth.get("score", 0.0)
    return round((structure_score + depth_score) / 2, 4)


# 시나리오: 종합 점수의 accuracy 축 — factual_grounding 결과를 0~1로 반영한다.
def calculate_accuracy_score(
    factual_grounding: Optional[Dict[str, Any]] = None,
) -> float:
    """
    정확도 (Accuracy): 리포트 수치 vs 실제 API 데이터 정확도 (환각 탐지)
    """
    if not factual_grounding:
        return 1.0
    return round(factual_grounding.get("score", 1.0), 4)


# 시나리오: 종합 점수의 relevance 축 — 엔티티 검출과 티커 언급을 평균한다.
def calculate_relevance_score(
    extraction_score: float,
    ticker_score: float,
) -> float:
    """
    관련성 (Relevance): 핵심 Entity 검출률 + 포트폴리오 티커 언급률 평균
    """
    return round((extraction_score + ticker_score) / 2, 4)


# 시나리오: run_eval이 샘플별로 호출 — 4대 가중치로 completeness·accuracy·coverage·relevance를 한 번에 합산한다.
def calculate_composite_score(
    extraction_score: float,
    structure_check: Dict[str, bool],
    section_depth: Dict[str, Any],
    ticker_score: float,
    numeric_density: float,
    coverage: Optional[Dict[str, Any]] = None,
    factual_grounding: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """
    4대 카테고리 기반 종합 점수를 계산합니다.

    카테고리 구성 (각 25%):
        completeness  25% - 섹션 구조 + 섹션 충실도
        accuracy      25% - 수치 정확도 (환각 탐지)
        coverage      25% - 핵심 시장 지표 커버리지
        relevance     25% - Entity 검출 + 티커 언급률

    Returns:
        {completeness, accuracy, coverage, relevance, score} 포함 dict
    """
    completeness = calculate_completeness_score(structure_check, section_depth)
    accuracy = calculate_accuracy_score(factual_grounding)
    cov_score = coverage.get("score", 0.0) if coverage else 0.0
    relevance = calculate_relevance_score(extraction_score, ticker_score)

    score = round(
        COMPOSITE_WEIGHTS["completeness"] * completeness
        + COMPOSITE_WEIGHTS["accuracy"] * accuracy
        + COMPOSITE_WEIGHTS["coverage"] * cov_score
        + COMPOSITE_WEIGHTS["relevance"] * relevance,
        4,
    )

    return {
        "completeness": completeness,
        "accuracy": accuracy,
        "coverage": cov_score,
        "relevance": relevance,
        "score": score,
    }
