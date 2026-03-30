from __future__ import annotations

from typing import Any

from utils.timeout import call_with_timeout
from utils.ttl_cache import ttl_cache

MARKET_SIGNALS_CACHE_TTL_SECONDS = 120
SIGNAL_HISTORY_PERIOD = "9mo"
SIGNAL_MIN_OBSERVATIONS = 126
EXTERNAL_CALL_TIMEOUT_SECONDS = 12


def fetch_stock_data(tickers: list) -> dict:
    import yfinance as yf

    result = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            result[ticker] = {
                "price": info.get("currentPrice", "N/A"),
                "pe_ratio": info.get("trailingPE", "N/A"),
                "market_cap": info.get("marketCap", "N/A"),
                "dividend_yield": info.get("dividendYield", "N/A"),
                "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
            }
        except Exception as exc:
            result[ticker] = {"error": str(exc)}
    return result


def _normalize_tickers(tickers: list[Any]) -> tuple[str, ...]:
    normalized = {str(ticker).strip() for ticker in tickers if str(ticker).strip()}
    return tuple(sorted(normalized))


@ttl_cache(ttl_seconds=MARKET_SIGNALS_CACHE_TTL_SECONDS, maxsize=128)
def _fetch_market_signals_cached(tickers: tuple[str, ...]) -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    import yfinance as yf

    def _fetch_one(ticker: str) -> dict:
        base = {"ticker": ticker}
        try:
            tkr = yf.Ticker(ticker)
            hist = call_with_timeout(
                lambda: tkr.history(period=SIGNAL_HISTORY_PERIOD, interval="1d"),
                timeout_seconds=EXTERNAL_CALL_TIMEOUT_SECONDS,
                timeout_message=f"yfinance timeout: {ticker} history",
            )
            closes = hist["Close"].dropna()
            if len(closes) < SIGNAL_MIN_OBSERVATIONS:
                return {**base, "error": "insufficient data"}

            r1 = (closes.iloc[-1] / closes.iloc[-2] - 1) * 100 if len(closes) >= 2 else 0.0
            r20 = (closes.iloc[-1] / closes.iloc[-20] - 1) * 100
            r60 = (closes.iloc[-1] / closes.iloc[-60] - 1) * 100
            vol = closes.pct_change().dropna().iloc[-60:].std() * (252**0.5) * 100
            trailing = closes.iloc[-126:]
            dd = ((trailing - trailing.cummax()) / trailing.cummax() * 100).min()

            delta = closes.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 100
            rsi = round(100 - (100 / (1 + rs)), 1)

            ma20 = closes.rolling(20).mean().iloc[-1]
            ma20_div = round((closes.iloc[-1] / ma20 - 1) * 100, 1) if ma20 != 0 else 0
            market_cap = None
            try:
                fast_info = getattr(tkr, "fast_info", None)
                market_cap = getattr(fast_info, "market_cap", None) if fast_info is not None else None
            except Exception:
                market_cap = None
            if not isinstance(market_cap, (int, float)) or market_cap <= 0:
                try:
                    info = call_with_timeout(
                        lambda: tkr.info or {},
                        timeout_seconds=EXTERNAL_CALL_TIMEOUT_SECONDS,
                        timeout_message=f"yfinance timeout: {ticker} info",
                    )
                    mc = info.get("marketCap")
                    market_cap = mc if isinstance(mc, (int, float)) and mc > 0 else None
                except Exception:
                    market_cap = None

            return {
                **base,
                "return_1d": round(r1, 2),
                "return_20d": round(r20, 1),
                "return_60d": round(r60, 1),
                "market_cap_change_3m": round(r60, 1),
                "volatility_60d": round(vol, 1),
                "drawdown_6m": round(float(dd), 1),
                "rsi_14": rsi,
                "ma20_divergence": ma20_div,
                "market_cap": market_cap if isinstance(market_cap, (int, float)) else None,
            }
        except Exception as exc:
            return {**base, "error": str(exc)}

    results = {}
    with ThreadPoolExecutor(max_workers=min(len(tickers), 10)) as pool:
        future_to_ticker = {pool.submit(_fetch_one, ticker): ticker for ticker in tickers}
        for future in as_completed(future_to_ticker):
            result = future.result()
            results[result["ticker"]] = result
    return results


def fetch_market_signals(tickers: list) -> dict:
    normalized_tickers = _normalize_tickers(tickers)
    if not normalized_tickers:
        return {}
    return _fetch_market_signals_cached(normalized_tickers)
