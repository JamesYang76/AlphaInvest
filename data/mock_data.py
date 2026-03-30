import json
import os
from pathlib import Path
from typing import Any, Dict, List

from data.portfolio_resolver import portfolio_rows_to_state, resolve_holdings_text

# ==========================================================
# ⚠️ [MOCK DATA] 나중에 실제 유저 DB 연동으로 교체되어야 합니다.
# ==========================================================
# 시나리오: 로컬·테스트 실행에서 실제 사용자 DB 없이 — main과 테스트가 동일한 샘플 포트폴리오로 파이프라인을 돌릴 때 쓴다.
# 우선순위: user_portfolio.json → ALPHAINVEST_HOLDINGS → 아래 기본값

_DEFAULT_USER_FILE = Path(__file__).resolve().parent / "user_portfolio.json"

DEFAULT_PORTFOLIO: List[Dict[str, Any]] = [
    {"ticker": "005930.KS", "avg_price": 85000},
    {"ticker": "036570.KS", "avg_price": 850000},
]


def _load_portfolio_from_file() -> List[Dict[str, Any]] | None:
    if not _DEFAULT_USER_FILE.exists():
        return None
    try:
        raw = json.loads(_DEFAULT_USER_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, list) and raw:
            return raw
    except Exception:
        return None
    return None


def _load_portfolio_from_env() -> List[Dict[str, Any]] | None:
    text = os.getenv("ALPHAINVEST_HOLDINGS", "").strip()
    if not text:
        return None
    rows, _errs = resolve_holdings_text(text)
    if not rows:
        return None
    return portfolio_rows_to_state(rows)


def get_portfolio() -> List[Dict[str, Any]]:
    """테스트를 위한 더미 유저 포트폴리오 데이터를 반환합니다."""
    from_file = _load_portfolio_from_file()
    if from_file:
        return from_file

    from_env = _load_portfolio_from_env()
    if from_env:
        return from_env

    return list(DEFAULT_PORTFOLIO)


def save_portfolio_for_cli(portfolio: List[Dict[str, Any]]) -> None:
    """대시보드 등에서 저장한 포트폴리오를 main.py가 읽을 수 있도록 JSON으로 저장합니다."""
    _DEFAULT_USER_FILE.write_text(
        json.dumps(portfolio, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
