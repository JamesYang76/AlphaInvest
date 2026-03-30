"""사용자 입력(티커·종목명·6자리 코드 등)을 Yahoo Finance 티커로 정규화합니다."""

from __future__ import annotations

import functools
import re
from typing import Any, Dict, List, Tuple

import FinanceDataReader
import yfinance as yf

# 시나리오: 대시보드·CLI가 동일한 규칙으로 — 한 줄 입력을 ticker·평단으로 풀고 KRX/야후 심볼로 맞춘다.

_US_TICKER = re.compile(r"^[A-Z]{1,5}(?:\.[A-Z]{1,4})?$")
_KR_CODE = re.compile(r"^\d{6}$")
_HANGUL = re.compile(r"[\uAC00-\uD7A3]")


def _to_float(value: str) -> float | None:
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_avg_price(value: float | int | None) -> float | int:
    if value is None:
        return 0
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


@functools.lru_cache(maxsize=1)
def _krx_df():
    try:
        return FinanceDataReader.StockListing("KRX")
    except Exception:
        return None


def _kr_suffix_for_market(market: str) -> str:
    m = (market or "").upper()
    return ".KQ" if "KOSDAQ" in m else ".KS"


def _lookup_krx_name(name: str) -> str | None:
    """한글/한국 종목명 → Code + .KS/.KQ"""
    df = _krx_df()
    if df is None or df.empty:
        return None
    name = name.strip()
    if not name:
        return None
    exact = df[df["Name"] == name]
    if not exact.empty:
        r = exact.iloc[0]
        return f"{r['Code']}{_kr_suffix_for_market(str(r['Market']))}"
    sub = df[df["Name"].str.contains(re.escape(name), na=False, case=False)]
    if not sub.empty:
        r = sub.iloc[0]
        return f"{r['Code']}{_kr_suffix_for_market(str(r['Market']))}"
    return None


def _lookup_krx_code(code: str) -> str | None:
    df = _krx_df()
    row = df[df["Code"] == code]
    if row.empty:
        return None
    r = row.iloc[0]
    return f"{r['Code']}{_kr_suffix_for_market(str(r['Market']))}"


def _yf_first_equity_symbol(query: str) -> str | None:
    try:
        s = yf.Search(query)
        quotes = getattr(s, "quotes", None) or []
        for q in quotes:
            if q.get("quoteType") != "EQUITY":
                continue
            sym = q.get("symbol")
            if sym:
                return sym
        for q in quotes:
            sym = q.get("symbol")
            if sym:
                return sym
    except Exception:
        return None
    return None


def _ticker_has_price(sym: str) -> bool:
    try:
        t = yf.Ticker(sym)
        lp = t.fast_info.get("lastPrice")
        return lp is not None and lp > 0
    except Exception:
        return False


def resolve_symbol_to_ticker(symbol: str) -> str | None:
    """
    티커/종목명/6자리 코드를 Yahoo Finance 심볼로 변환합니다.
    """
    raw = symbol.strip()
    if not raw:
        return None

    upper = raw.upper()

    if _KR_CODE.match(raw):
        yahoo = _lookup_krx_code(raw)
        if yahoo:
            return yahoo
        for suf in (".KS", ".KQ"):
            cand = f"{raw}{suf}"
            if _ticker_has_price(cand):
                return cand
        return f"{raw}.KS"

    if ".KS" in upper or ".KQ" in upper or upper.endswith(".TW") or "^" in raw:
        return raw

    if _US_TICKER.match(upper) and _ticker_has_price(upper):
        return upper

    if _HANGUL.search(raw):
        hit = _lookup_krx_name(raw)
        if hit:
            return hit

    hit = _lookup_krx_name(raw)
    if hit:
        return hit

    sym = _yf_first_equity_symbol(raw)
    if sym:
        return sym

    sym = _yf_first_equity_symbol(f"{raw} stock")
    if sym:
        return sym

    if _US_TICKER.match(upper):
        return upper

    return None


def _split_line(line: str) -> Tuple[str, float | None]:
    """
    한 줄에서 종목 부분과 평단을 분리합니다.
    지원: 'AAPL,180', '삼성전자 70000', '삼성전자,70000', 'MSFT' (평단 없음)
    """
    line = line.strip()
    if not line:
        return "", None

    if "," in line:
        left, right = line.rsplit(",", 1)
        price = _to_float(right)
        if price is not None:
            return left.strip(), price
        return line, None

    parts = line.split()
    if len(parts) >= 2 and _to_float(parts[-1]) is not None:
        price = _to_float(parts[-1])
        return " ".join(parts[:-1]).strip(), price

    return line, None


def resolve_holdings_text(raw: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    여러 줄 입력을 [{'ticker','avg_price','input','resolved'}...] 로 변환합니다.
    실패한 줄은 errors에 메시지로 담습니다.
    """
    rows: List[Dict[str, Any]] = []
    errors: List[str] = []

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        sym_part, price = _split_line(line)
        if not sym_part:
            continue

        try:
            ticker = resolve_symbol_to_ticker(sym_part)
        except Exception as exc:
            errors.append(f"종목 해석 중 오류가 발생했습니다: {sym_part!r} ({exc})")
            continue
        if not ticker:
            errors.append(f"종목을 찾지 못했습니다: {sym_part!r}")
            continue

        rows.append(
            {
                "ticker": ticker,
                "avg_price": _normalize_avg_price(price),
                "input": line,
                "resolved_from": sym_part,
            }
        )

    return rows, errors


def portfolio_rows_to_state(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """그래프 state용 최소 필드만 유지합니다."""
    return [{"ticker": r["ticker"], "avg_price": r["avg_price"]} for r in rows]
