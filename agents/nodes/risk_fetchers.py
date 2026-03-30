from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from utils.timeout import call_with_timeout

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import yfinance as yf
except ImportError:
    yf = None

if load_dotenv is not None:
    load_dotenv()

FRED_SERIES = {
    "fed_funds_rate": "DFF",
    "ten_year_yield": "DGS10",
    "high_yield_spread": "BAMLH0A0HYM2",
}

RISK_SIGNAL_TIMEOUT_SECONDS = 12
T = TypeVar("T")


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    req = Request(url=url, headers=headers or {}, method="GET")
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    merged = {"Content-Type": "application/json", **(headers or {})}
    req = Request(
        url=url,
        headers=merged,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _safe_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parallel_map_dict(
    items: Dict[str, T],
    worker: Callable[[T], Any],
    max_workers: int,
) -> Dict[str, Any]:
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(worker, value): key for key, value in items.items()}
        return {future_map[future]: future.result() for future in as_completed(future_map)}


def parallel_map_list(
    items: List[T],
    worker: Callable[[T], Any],
    max_workers: int,
) -> List[Any]:
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        index_map = {pool.submit(worker, item): index for index, item in enumerate(items)}
        results: List[Any] = [None] * len(items)
        for future in as_completed(index_map):
            results[index_map[future]] = future.result()
    return results


def _fetch_fred_series(series_id: str, api_key: str) -> List[float]:
    query = urlencode(
        {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 4,
        }
    )
    url = f"https://api.stlouisfed.org/fred/series/observations?{query}"
    data = _http_get_json(url)
    values = [_safe_float(observation.get("value")) for observation in data.get("observations", [])]
    return [value for value in values if value is not None]


def build_macro_context() -> Dict[str, Any]:
    api_key = os.getenv("FRED_API_KEY", "").strip()
    if not api_key:
        return {"summary": "FRED_API_KEY 미설정", "values": {}}

    try:
        series_values = parallel_map_dict(
            items=FRED_SERIES,
            worker=lambda series_id: _fetch_fred_series(series_id, api_key),
            max_workers=len(FRED_SERIES),
        )
    except (HTTPError, URLError, TimeoutError, ValueError) as err:
        return {"summary": f"FRED 조회 실패: {err}", "values": {}}

    values: Dict[str, Optional[float]] = {key: (series_values[key][0] if series_values[key] else None) for key in FRED_SERIES}
    parts = [
        f"연방기금금리 {values['fed_funds_rate']:.2f}%" if values["fed_funds_rate"] else "연방기금금리 데이터 없음",
        f"미국채 10년물 {values['ten_year_yield']:.2f}%" if values["ten_year_yield"] else "10년물 데이터 없음",
        f"하이일드 스프레드 {values['high_yield_spread']:.2f}" if values["high_yield_spread"] else "HY스프레드 데이터 없음",
    ]
    return {"summary": ", ".join(parts), "values": values}


def fetch_news_articles(query: str, max_results: int = 15) -> List[Dict[str, str]]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []

    body = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_answer": False,
    }
    try:
        response = _http_post_json("https://api.tavily.com/search", body)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return []

    return [
        {
            "title": item.get("title", ""),
            "content": item.get("content", "")[:300],
            "url": (item.get("url") or "").strip(),
        }
        for item in response.get("results", [])
        if item.get("title")
    ]


def article_source_links(items: List[Dict[str, str]], prefix: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for item in items:
        url = (item.get("url") or "").strip()
        if not url:
            continue
        title = (item.get("title") or "기사").strip()[:120]
        out.append({"label": f"{prefix} {title}", "url": url})
    return out


def _compute_rsi(closes: Any, period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    last_loss = loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    rs = gain.iloc[-1] / last_loss
    return round(100 - (100 / (1 + rs)), 1)


def _compute_ma_divergence(closes: Any, period: int = 5) -> Optional[float]:
    if len(closes) < period:
        return None
    moving_average = closes.rolling(period).mean().iloc[-1]
    if moving_average == 0:
        return None
    return round((closes.iloc[-1] / moving_average - 1) * 100, 1)


def _compute_rsi_from_list(prices: List[float], period: int = 14) -> Optional[float]:
    if len(prices) < period + 1:
        return None
    gains: List[float] = []
    losses: List[float] = []
    for index in range(1, len(prices)):
        delta = prices[index] - prices[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    recent_gains = gains[-period:]
    recent_losses = losses[-period:]
    avg_gain = sum(recent_gains) / period
    avg_loss = sum(recent_losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _compute_ma_divergence_from_list(prices: List[float], period: int = 20) -> Optional[float]:
    if len(prices) < period:
        return None
    moving_average = sum(prices[-period:]) / period
    if moving_average == 0:
        return None
    return round((prices[-1] / moving_average - 1) * 100, 1)


def fetch_market_signal(ticker: str) -> Dict[str, Any]:
    base: Dict[str, Any] = {"ticker": ticker}

    if yf is not None:
        try:
            history = call_with_timeout(
                lambda: yf.Ticker(ticker).history(period="9mo", interval="1d"),
                timeout_seconds=RISK_SIGNAL_TIMEOUT_SECONDS,
                timeout_message=f"risk yfinance timeout: {ticker}",
            )
            closes = history["Close"].dropna()
            if len(closes) < 126:
                return {**base, "error": "insufficient data"}
            r20 = (closes.iloc[-1] / closes.iloc[-20] - 1) * 100
            r60 = (closes.iloc[-1] / closes.iloc[-60] - 1) * 100
            vol = closes.pct_change().dropna().iloc[-60:].std() * (252**0.5) * 100
            dd = ((closes.iloc[-126:] - closes.iloc[-126:].cummax()) / closes.iloc[-126:].cummax() * 100).min()
            rsi_14 = _compute_rsi(closes)
            ma20_div = _compute_ma_divergence(closes, period=20)
            return {
                **base,
                "return_20d": round(r20, 1),
                "return_60d": round(r60, 1),
                "volatility_60d": round(vol, 1),
                "drawdown_6m": round(float(dd), 1),
                "rsi_14": rsi_14,
                "ma20_divergence": ma20_div,
            }
        except Exception as err:
            return {**base, "error": str(err)}

    return _fetch_market_signal_api(ticker)


def _fetch_market_signal_api(ticker: str) -> Dict[str, Any]:
    base: Dict[str, Any] = {"ticker": ticker}
    query = urlencode({"range": "9mo", "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?{query}"
    try:
        data = _http_get_json(url)
    except (HTTPError, URLError, TimeoutError, ValueError) as err:
        return {**base, "error": str(err)}

    result = data.get("chart", {}).get("result", [])
    if not result:
        return {**base, "error": "no data"}

    raw = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
    prices = [price for price in raw if price is not None]
    if len(prices) < 126:
        return {**base, "error": "insufficient prices"}

    r20 = (prices[-1] / prices[-20] - 1) * 100
    r60 = (prices[-1] / prices[-60] - 1) * 100
    recent_returns = [(prices[index] / prices[index - 1] - 1) for index in range(len(prices) - 59, len(prices))]
    mean_ret = sum(recent_returns) / len(recent_returns)
    variance = sum((ret - mean_ret) ** 2 for ret in recent_returns) / max(len(recent_returns) - 1, 1)
    vol = (variance**0.5) * (252**0.5) * 100
    peak = prices[-126]
    dd = 0.0
    for price in prices[-126:]:
        peak = max(peak, price)
        dd = min(dd, (price - peak) / peak * 100)

    rsi_14 = _compute_rsi_from_list(prices)
    ma20_div = _compute_ma_divergence_from_list(prices, period=20)

    return {
        **base,
        "return_20d": round(r20, 1),
        "return_60d": round(r60, 1),
        "volatility_60d": round(vol, 1),
        "drawdown_6m": round(dd, 1),
        "rsi_14": rsi_14,
        "ma20_divergence": ma20_div,
    }


def attach_market_signals(entities: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    all_tickers = list({ticker for entity in entities for ticker in entity.get("tickers", [])})
    if not all_tickers:
        return {}
    tickers = all_tickers[:20]
    signals = parallel_map_list(
        items=tickers,
        worker=fetch_market_signal,
        max_workers=min(len(tickers), 10),
    )
    return {signal["ticker"]: signal for signal in signals}


def fetch_theme_news() -> List[Dict[str, str]]:
    queries = [
        "Stock Market Rising Investment Themes structural change 2026",
        "Sector Weakness bubble overvaluation risk concerns 2026",
    ]
    results = parallel_map_list(
        items=queries,
        worker=lambda query: fetch_news_articles(query, max_results=10),
        max_workers=2,
    )
    combined: List[Dict[str, str]] = []
    for batch in results:
        combined.extend(batch)
    return combined


def enrich_theme_signals(themes: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    all_tickers: List[str] = []
    for theme in themes:
        all_tickers.extend(theme.get("leader_stocks", []))
        all_tickers.extend(theme.get("representative_etfs", []))
    unique = list(dict.fromkeys(all_tickers))[:15]
    if not unique:
        return {}
    signals = parallel_map_list(
        items=unique,
        worker=fetch_market_signal,
        max_workers=min(len(unique), 8),
    )
    return {signal["ticker"]: signal for signal in signals}
