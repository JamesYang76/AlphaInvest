from typing import Any, Dict, List


def calculate_extraction_score(actual_report: str, expected_entities: List[str]) -> float:
    """기대했던 주요 경제 지표(Entity)들이 CIO 최종 리포트에 포함되었는지 점수화합니다."""
    if not expected_entities:
        return 1.0
    found_count = [1 for entity in expected_entities if entity.lower() in actual_report.lower()]
    return sum(found_count) / len(expected_entities)


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


def evaluate_numeric_consistency(macro_data: Dict[str, Any], risk_data: Dict[str, Any]) -> bool:
    """거시 지표(VIX 등)와 리스크 스코어 간의 논리적 모순 여부를 검증합니다."""
    vix = float(macro_data.get("vix", 20))
    risk_score = float(risk_data.get("risk_score", 50))
    # VIX가 30 이상(공포)인데 리스크 스코어가 30 미만(매우 안전)이면 일관성 오류
    return not (vix > 30 and risk_score < 30)
