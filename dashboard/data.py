from __future__ import annotations

from statistics import mean
from typing import Any, Dict, List

from data.fetchers import fetch_macro_data, fetch_market_signals
from data.mock_data import get_portfolio
from dashboard.reporting import build_portfolio_report


def _to_float(value: Any) -> float | None:
    if value in (None, "", "N/A"):
        return None
    text = str(value).replace("%", "").replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _build_breakdown_rows(portfolio: List[Dict[str, Any]], signals: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "ticker": item["ticker"],
            "avg_price": item.get("avg_price", "N/A"),
            "return_5d": signal.get("return_5d", "N/A"),
            "return_20d": signal.get("return_20d", "N/A"),
            "volatility_20d": signal.get("volatility_20d", "N/A"),
            "rsi_14": signal.get("rsi_14", "N/A"),
            "risk_flag": "Watch" if _to_float(signal.get("rsi_14")) and _to_float(signal.get("rsi_14")) >= 70 else "-",
        }
        for item in portfolio
        if (signal := signals.get(item["ticker"], {})) is not None
    ]


def _build_kpis(rows: List[Dict[str, Any]], macro_data: Dict[str, Any]) -> List[Dict[str, str]]:
    returns_20d = [value for row in rows if (value := _to_float(row["return_20d"])) is not None]
    flagged = sum(1 for row in rows if row["risk_flag"] != "-")
    return [
        {"label": "Tracked Holdings", "value": str(len(rows)), "tone": "neutral"},
        {"label": "Avg 20D Return", "value": f"{mean(returns_20d):.1f}%" if returns_20d else "TODO", "tone": "positive" if returns_20d and mean(returns_20d) >= 0 else "negative"},
        {"label": "Fed Rate", "value": str(macro_data.get("fed_rate", "TODO")), "tone": "neutral"},
        {"label": "Risk Flags", "value": str(flagged), "tone": "negative" if flagged else "positive"},
    ]


def _normalize_avg_price(value: str) -> float | int:
    parsed = _to_float(value)
    if parsed is None:
        return 0
    return int(parsed) if parsed.is_integer() else parsed


def parse_holdings_input(raw_holdings: str) -> List[Dict[str, Any]]:
    lines = [line.strip() for line in raw_holdings.splitlines() if line.strip()]
    return [
        {
            "ticker": parts[0].strip().upper(),
            "avg_price": _normalize_avg_price(parts[1]) if len(parts) > 1 else 0,
        }
        for line in lines
        if (parts := [part.strip() for part in line.split(",", 1)]) and parts[0].strip()
    ]


def serialize_holdings_input(portfolio: List[Dict[str, Any]]) -> str:
    return "\n".join(f"{item['ticker']},{item.get('avg_price', 0)}" for item in portfolio if item.get("ticker"))


def build_dashboard_payload(holdings: str = "") -> Dict[str, Any]:
    custom_portfolio = parse_holdings_input(holdings)
    portfolio = custom_portfolio or get_portfolio()
    tickers = [item["ticker"] for item in portfolio]
    macro_data = fetch_macro_data()
    signals = fetch_market_signals(tickers) if tickers else {}
    rows = _build_breakdown_rows(portfolio, signals)
    report_payload = build_portfolio_report(custom_portfolio) if custom_portfolio else {"portfolio_label": "", "report": "", "error": ""}
    assumptions = [
        "Exact dashboard metrics were not specified, so this shell shows the simplest AlphaInvest overview.",
        "Portfolio data defaults to the existing mock portfolio when no holdings are entered.",
        "Charts are implemented as lightweight inline visuals because the repo has no existing web chart library.",
        "Holdings report generation reuses the existing agent nodes up to CIO and skips Notion publishing.",
    ]
    return {
        "title": "AlphaInvest Dashboard",
        "subtitle": "Headline KPIs, trend snapshots, and a holdings breakdown wired to current project data sources.",
        "assumptions": assumptions,
        "holdings_input": holdings if holdings.strip() else serialize_holdings_input(portfolio),
        "portfolio_label": report_payload["portfolio_label"],
        "portfolio_report": report_payload["report"],
        "portfolio_report_error": report_payload["error"],
        "kpis": _build_kpis(rows, macro_data),
        "macro": [
            {"label": "CPI YoY", "value": str(macro_data.get("cpi", "TODO"))},
            {"label": "Unemployment", "value": str(macro_data.get("unemployment", "TODO"))},
            {"label": "VIX", "value": str(macro_data.get("vix", "TODO"))},
            {"label": "S&P 500 Trend", "value": str(macro_data.get("sp500_trend", "TODO"))},
        ],
        "trends": rows,
        "breakdown": rows,
    }
