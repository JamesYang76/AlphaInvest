from typing import Any, Dict, List


# ==========================================================
# ⚠️ [MOCK DATA] 나중에 실제 유저 DB 연동으로 교체되어야 합니다.
# ==========================================================
def get_portfolio() -> List[Dict[str, Any]]:
    """테스트를 위한 더미 유저 포트폴리오 데이터를 반환합니다."""
    return [{"ticker": "005930.KS", "avg_price": 85000}, {"ticker": "036570.KS", "avg_price": 850000}]
