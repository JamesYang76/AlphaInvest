from __future__ import annotations

from typing import Any, Dict, Optional

from utils.timeout import call_with_timeout
from utils.ttl_cache import ttl_cache

MACRO_CACHE_TTL_SECONDS = 300
EXTERNAL_CALL_TIMEOUT_SECONDS = 12


def _yf_last_close(ticker: str, period: str = "5d") -> Optional[float]:
    try:
        import yfinance as yf

        hist = call_with_timeout(
            lambda: yf.Ticker(ticker).history(period=period),
            timeout_seconds=EXTERNAL_CALL_TIMEOUT_SECONDS,
            timeout_message=f"yfinance timeout: {ticker} {period}",
        )
        if hist.empty or "Close" not in hist.columns:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


def _yf_sp500_trend() -> str:
    try:
        import yfinance as yf

        sp500 = call_with_timeout(
            lambda: yf.Ticker("^GSPC").history(period="5d"),
            timeout_seconds=EXTERNAL_CALL_TIMEOUT_SECONDS,
            timeout_message="yfinance timeout: ^GSPC 5d",
        )
        if sp500.empty or "Close" not in sp500.columns:
            return "N/A"
        closes = sp500["Close"]
        return "상승세" if closes.iloc[-1] > closes.iloc[0] else "조정/하락세"
    except Exception:
        return "N/A"


def _yf_market_layer() -> Dict[str, Any]:
    vix = _yf_last_close("^VIX", "5d")
    dxy_val = None
    for symbol in ("DX-Y.NYB", "USDX=X", "UUP"):
        dxy_val = _yf_last_close(symbol, "10d")
        if dxy_val is not None:
            break
    return {
        "vix": f"{vix:.2f}" if vix is not None else "N/A",
        "dxy": f"{dxy_val:.2f}" if dxy_val is not None else "N/A",
        "sp500_trend": _yf_sp500_trend(),
    }


@ttl_cache(ttl_seconds=MACRO_CACHE_TTL_SECONDS, maxsize=8)
def fetch_macro_data() -> dict:
    """FRED + yfinance 기반 거시 데이터 수집."""
    import os

    yf_layer = _yf_market_layer()
    fred_api_key = os.getenv("FRED_API_KEY", "").strip()

    if not fred_api_key:
        return {
            "fed_rate": "N/A (FRED 키 없음)",
            "cpi": "N/A (FRED 키 없음)",
            "unemployment": "N/A (FRED 키 없음)",
            "vix": yf_layer["vix"],
            "dxy": yf_layer["dxy"],
            "sp500_trend": yf_layer["sp500_trend"],
            "source": "yfinance only",
        }

    raw_data: Dict[str, Any] = {}
    try:
        from fredapi import Fred

        fred = Fred(api_key=fred_api_key)
        indicators = {
            "fed_rate": "FEDFUNDS",
            "d_fed_rate": "DFF",
            "cpi": "CPIAUCSL",
            "unrate": "UNRATE",
            "ten_year": "DGS10",
            "hy_spread": "BAMLH0A0HYM2",
        }

        for key, series_id in indicators.items():
            try:
                series = call_with_timeout(
                    lambda sid=series_id: fred.get_series(sid),
                    timeout_seconds=EXTERNAL_CALL_TIMEOUT_SECONDS,
                    timeout_message=f"FRED timeout: {series_id}",
                )
                raw_data[key] = float(series.iloc[-1]) if not series.empty else None
            except Exception:
                raw_data[key] = None

        cpi_yoy = None
        try:
            cpi_series = call_with_timeout(
                lambda: fred.get_series("CPIAUCSL"),
                timeout_seconds=EXTERNAL_CALL_TIMEOUT_SECONDS,
                timeout_message="FRED timeout: CPIAUCSL",
            )
            if len(cpi_series) >= 13:
                cpi_yoy = ((cpi_series.iloc[-1] / cpi_series.iloc[-13]) - 1) * 100
        except Exception:
            pass

        return {
            "fed_rate": f"{raw_data['fed_rate']:.2f}%" if raw_data.get("fed_rate") is not None else "N/A",
            "d_fed_rate": raw_data.get("d_fed_rate"),
            "cpi": f"{cpi_yoy:.2f}%" if cpi_yoy is not None else "N/A",
            "unemployment": f"{raw_data['unrate']:.2f}%" if raw_data.get("unrate") is not None else "N/A",
            "vix": yf_layer["vix"],
            "dxy": yf_layer["dxy"],
            "sp500_trend": yf_layer["sp500_trend"],
            "ten_year_yield": raw_data.get("ten_year"),
            "high_yield_spread": raw_data.get("hy_spread"),
            "source": "FRED & yfinance",
        }
    except Exception as exc:
        return {
            "fed_rate": "N/A",
            "cpi": "N/A",
            "unemployment": "N/A",
            "vix": yf_layer["vix"],
            "dxy": yf_layer["dxy"],
            "sp500_trend": yf_layer["sp500_trend"],
            "error": str(exc),
            "source": "yfinance + FRED 오류",
        }


def macro_numeric_source_links() -> list[dict[str, str]]:
    return [
        {"label": "FRED — St. Louis Fed (경제 데이터 포털)", "url": "https://fred.stlouisfed.org/"},
        {"label": "FRED — Effective Federal Funds Rate (DFF)", "url": "https://fred.stlouisfed.org/series/DFF"},
        {"label": "FRED — Consumer Price Index (CPIAUCSL)", "url": "https://fred.stlouisfed.org/series/CPIAUCSL"},
        {"label": "FRED — Unemployment Rate (UNRATE)", "url": "https://fred.stlouisfed.org/series/UNRATE"},
        {"label": "FRED — Market Yield on U.S. Treasury 10Y (DGS10)", "url": "https://fred.stlouisfed.org/series/DGS10"},
        {"label": "FRED — ICE BofA US High Yield Option-Adjusted Spread", "url": "https://fred.stlouisfed.org/series/BAMLH0A0HYM2"},
        {"label": "Yahoo Finance — VIX", "url": "https://finance.yahoo.com/quote/%5EVIX/"},
        {"label": "Yahoo Finance — S&P 500", "url": "https://finance.yahoo.com/quote/%5EGSPC/"},
        {"label": "Yahoo Finance — US Dollar Index", "url": "https://finance.yahoo.com/quote/DX-Y.NYB/"},
    ]
