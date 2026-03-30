from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Optional

from dashboard.reporting import build_portfolio_report
from data.composite_score import compute_composite_scores_for_signals
from data.fetchers import fetch_macro_data, fetch_market_signals, fetch_news_with_sources
from data.mock_data import get_portfolio, save_portfolio_for_cli
from data.portfolio_resolver import portfolio_rows_to_state, resolve_holdings_text
from data.sector_momentum_universe import label_for_symbol, sector_momentum_symbols, treemap_group_for_symbol
from utils.logger import get_logger
from utils.timing import format_elapsed_ms, start_timer

logger = get_logger("dashboard.data")


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
            "return_20d": signal.get("return_20d", "N/A"),
            "return_60d": signal.get("return_60d", "N/A"),
            "volatility_60d": signal.get("volatility_60d", "N/A"),
            "rsi_14": signal.get("rsi_14", "N/A"),
            "risk_flag": "Watch" if _to_float(signal.get("rsi_14")) and _to_float(signal.get("rsi_14")) >= 70 else "-",
        }
        for item in portfolio
        if (signal := signals.get(item["ticker"], {})) is not None
    ]


def _display_macro_value(macro_data: Dict[str, Any], key: str) -> str:
    """거시 dict에서 카드용 문자열 (없거나 비면 대시)."""
    v = macro_data.get(key)
    if v is None:
        return "—"
    s = str(v).strip()
    return s if s else "—"


def _build_kpis(rows: List[Dict[str, Any]], macro_data: Dict[str, Any]) -> List[Dict[str, str]]:
    returns_60d = [value for row in rows if (value := _to_float(row["return_60d"])) is not None]
    flagged = sum(1 for row in rows if row["risk_flag"] != "-")
    if not rows:
        avg_60 = "보유 없음"
    elif returns_60d:
        avg_60 = f"{mean(returns_60d):.1f}%"
    else:
        avg_60 = "—"
    return [
        {"label": "Tracked Holdings", "value": str(len(rows)), "tone": "neutral"},
        {
            "label": "Avg 3M Return",
            "value": avg_60,
            "tone": "positive" if returns_60d and mean(returns_60d) >= 0 else "negative",
        },
        {"label": "Fed Rate", "value": _display_macro_value(macro_data, "fed_rate"), "tone": "neutral"},
        {"label": "Risk Flags", "value": str(flagged), "tone": "negative" if flagged else "positive"},
    ]


def parse_holdings_input(raw_holdings: str) -> List[Dict[str, Any]]:
    try:
        rows, _ = resolve_holdings_text(raw_holdings)
    except Exception:
        return []
    return portfolio_rows_to_state(rows)


def serialize_holdings_input(portfolio: List[Dict[str, Any]]) -> str:
    return "\n".join(f"{item['ticker']},{item.get('avg_price', 0)}" for item in portfolio if item.get("ticker"))


def _etf_heatmap_rows(
    syms: List[str],
    signals: Dict[str, Dict[str, Any]],
    scores: Dict[str, float],
) -> List[Dict[str, Any]]:
    """벤치마크 ETF 전체에 대한 히트맵용 수치(열: 1D·1M·3M·복합·RSI)."""
    out: List[Dict[str, Any]] = []
    for t in syms:
        s = signals.get(t) or {}
        if s.get("error"):
            continue
        sc = scores.get(t)
        out.append(
            {
                "ticker": t,
                "label": label_for_symbol(t),
                "group": treemap_group_for_symbol(t),
                "r1": _to_float(s.get("return_1d")),
                "r20": _to_float(s.get("return_20d")),
                "r60": _to_float(s.get("return_60d")),
                "mcap3m": _to_float(s.get("market_cap_change_3m")) or _to_float(s.get("return_60d")),
                "score": float(sc) if sc is not None else None,
                "rsi": _to_float(s.get("rsi_14")),
                "market_cap": _to_float(s.get("market_cap")),
            }
        )
    return out


def _build_sector_flow_preview() -> Dict[str, Any]:
    """대시보드용: 벤치마크 ETF 유니버스 횡단면 복합점수 상·하위 요약."""
    syms = sector_momentum_symbols()
    signals = fetch_market_signals(syms)
    scores = compute_composite_scores_for_signals(signals)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def row(ticker: str, score: float) -> Dict[str, Any]:
        s = signals.get(ticker) or {}
        return {
            "ticker": ticker,
            "label": label_for_symbol(ticker),
            "score": score,
            "return_60d": s.get("return_60d", "N/A"),
        }

    top = [row(t, sc) for t, sc in ranked[:10] if t in signals and not (signals.get(t) or {}).get("error")]
    bottom = [row(t, sc) for t, sc in sorted(ranked[-10:], key=lambda x: x[1]) if t in signals and not (signals.get(t) or {}).get("error")]
    heatmap = _etf_heatmap_rows(syms, signals, scores)
    return {"leaders": top, "laggards": bottom, "heatmap": heatmap}


def _build_sector_flow_preview_from_signals(signals: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    syms = sector_momentum_symbols()
    bench_signals = {
        ticker: signal
        for ticker, signal in signals.items()
        if ticker in syms and signal is not None and not (signal or {}).get("error")
    }
    if not bench_signals:
        return _build_sector_flow_preview()

    stored_scores = {
        ticker: signal.get("composite_score")
        for ticker, signal in bench_signals.items()
        if signal.get("composite_score") is not None
    }
    scores = stored_scores if len(stored_scores) == len(bench_signals) else compute_composite_scores_for_signals(bench_signals)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def row(ticker: str, score: float) -> Dict[str, Any]:
        signal = bench_signals.get(ticker) or {}
        return {
            "ticker": ticker,
            "label": label_for_symbol(ticker),
            "score": score,
            "return_60d": signal.get("return_60d", "N/A"),
        }

    top = [row(ticker, score) for ticker, score in ranked[:10]]
    bottom = [row(ticker, score) for ticker, score in sorted(ranked[-10:], key=lambda x: x[1])]
    heatmap = _etf_heatmap_rows(syms, signals, scores)
    return {"leaders": top, "laggards": bottom, "heatmap": heatmap}


def _build_news_snippet() -> str:
    try:
        text, _ = fetch_news_with_sources(
            "US stock sector rotation Fed macro earnings outlook",
            max_results=4,
            link_prefix="[뉴스]",
        )
        return (text or "").strip()
    except Exception:
        return ""


def build_dashboard_payload(
    holdings: str = "",
    market_report_override: Optional[Dict[str, str]] = None,
    portfolio_report_override: Optional[Dict[str, str]] = None,
    market_notion_url: str = "",
    portfolio_notion_url: str = "",
    persist_resolved_holdings: bool = False,
    fallback_to_saved_portfolio: bool = True,
    pipeline_snapshot: Optional[Dict[str, Any]] = None,
    defer_reports: bool = False,
    pending_job: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload_started_at = start_timer()
    resolve_errors: List[str] = []
    custom_portfolio: List[Dict[str, Any]] = []

    if holdings.strip():
        resolve_started_at = start_timer()
        resolved_rows, resolve_errors = resolve_holdings_text(holdings)
        logger.info(
            "[Timing] dashboard resolve_holdings rows=%d duration=%s",
            len(resolved_rows),
            format_elapsed_ms(resolve_started_at),
        )
        if resolved_rows:
            custom_portfolio = portfolio_rows_to_state(resolved_rows)
            if persist_resolved_holdings:
                save_portfolio_for_cli(custom_portfolio)

    if custom_portfolio:
        portfolio = custom_portfolio
    elif fallback_to_saved_portfolio:
        portfolio = get_portfolio()
    else:
        portfolio = []
    tickers = [item["ticker"] for item in portfolio]
    snapshot = pipeline_snapshot or {}
    snapshot_macro_data = snapshot.get("macro_data")
    snapshot_chart_data = snapshot.get("chart_data")
    snapshot_news_snippet = snapshot.get("news_snippet")

    macro_started_at = start_timer()
    macro_data = snapshot_macro_data if isinstance(snapshot_macro_data, dict) and snapshot_macro_data else fetch_macro_data()
    logger.info(
        "[Timing] dashboard macro_data source=%s duration=%s",
        "snapshot" if isinstance(snapshot_macro_data, dict) and snapshot_macro_data else "live",
        format_elapsed_ms(macro_started_at),
    )
    signals_started_at = start_timer()
    signals = (
        snapshot_chart_data
        if isinstance(snapshot_chart_data, dict) and snapshot_chart_data
        else fetch_market_signals(tickers)
        if tickers
        else {}
    )
    logger.info(
        "[Timing] dashboard holdings_signals source=%s tickers=%d duration=%s",
        "snapshot" if isinstance(snapshot_chart_data, dict) and snapshot_chart_data else "live",
        len(tickers),
        format_elapsed_ms(signals_started_at),
    )
    rows = _build_breakdown_rows(portfolio, signals)

    if portfolio_report_override is not None:
        report_payload = portfolio_report_override
    elif custom_portfolio and not defer_reports:
        report_started_at = start_timer()
        report_payload = build_portfolio_report(custom_portfolio)
        logger.info("[Timing] dashboard portfolio_report_inline duration=%s", format_elapsed_ms(report_started_at))
    else:
        report_payload = {"portfolio_label": "", "report": "", "error": ""}

    market_report_payload = market_report_override if market_report_override is not None else {"portfolio_label": "", "report": "", "error": ""}

    if resolve_errors:
        err_txt = " ".join(resolve_errors)
        prev_err = report_payload.get("error", "")
        report_payload = {
            **report_payload,
            "error": f"{prev_err} {err_txt}".strip() if prev_err else err_txt,
        }

    sector_started_at = start_timer()
    sector_preview = (
        _build_sector_flow_preview_from_signals(snapshot_chart_data)
        if isinstance(snapshot_chart_data, dict) and snapshot_chart_data
        else _build_sector_flow_preview()
    )
    logger.info(
        "[Timing] dashboard sector_preview source=%s duration=%s",
        "snapshot" if isinstance(snapshot_chart_data, dict) and snapshot_chart_data else "live",
        format_elapsed_ms(sector_started_at),
    )
    news_started_at = start_timer()
    news_snippet = str(snapshot_news_snippet).strip() if snapshot_news_snippet else _build_news_snippet()
    logger.info(
        "[Timing] dashboard news_snippet source=%s duration=%s",
        "snapshot" if snapshot_news_snippet else "live",
        format_elapsed_ms(news_started_at),
    )

    assumptions = [
        "기본 생성 경로는 빠른 모드이며 Macro→Portfolio→Chart→Risk→Alpha 후 즉시 종합 리포트를 조립합니다.",
        "전체 검수형(full) 경로는 GP 검수와 CIO 문체 정교화를 포함하지만 기본 대시보드 버튼에서는 생략합니다.",
        (
            "보유 입력은 티커·종목명·6자리 코드를 지원하며, 저장 시 data/user_portfolio.json에 반영되어 main.py와 동기화됩니다."
        ),
        "대시보드 상단 KPI·섹터 요약은 yfinance·FRED 기반이며, 에이전트 리포트는 OpenAI·Tavily 키가 필요할 수 있습니다.",
    ]
    payload = {
        "title": "AlphaInvest",
        "subtitle": "거시 → 섹터 흐름 → 뉴스 → 위험·추천 섹터, 그리고 보유 종목 검증까지 한 화면에서.",
        "dashboard_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "assumptions": assumptions,
        "holdings_input": holdings if holdings.strip() else serialize_holdings_input(portfolio),
        "portfolio_label": report_payload["portfolio_label"],
        "portfolio_report": report_payload["report"],
        "portfolio_report_error": report_payload["error"],
        "portfolio_notion_url": portfolio_notion_url,
        "market_report_label": market_report_payload.get("portfolio_label", ""),
        "market_report": market_report_payload.get("report", ""),
        "market_report_error": market_report_payload.get("error", ""),
        "market_notion_url": market_notion_url,
        "kpis": _build_kpis(rows, macro_data),
        "macro": [
            {"label": "기준금리(연)", "value": _display_macro_value(macro_data, "fed_rate")},
            {"label": "CPI YoY", "value": _display_macro_value(macro_data, "cpi")},
            {"label": "실업률", "value": _display_macro_value(macro_data, "unemployment")},
            {"label": "VIX", "value": _display_macro_value(macro_data, "vix")},
            {"label": "S&P500 추세", "value": _display_macro_value(macro_data, "sp500_trend")},
        ],
        "macro_source": str(macro_data.get("source", "")),
        "macro_error": str(macro_data.get("error", "")) if macro_data.get("error") else "",
        "trends": rows,
        "breakdown": rows,
        "sector_leaders": sector_preview["leaders"],
        "sector_laggards": sector_preview["laggards"],
        "etf_heatmap": sector_preview.get("heatmap") or [],
        "news_snippet": news_snippet,
        "pending_job": pending_job or {},
    }
    logger.info(
        "[Timing] dashboard payload total holdings=%d duration=%s",
        len(portfolio),
        format_elapsed_ms(payload_started_at),
    )
    return payload
