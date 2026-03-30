from __future__ import annotations

import html
import math
from typing import Any, Dict, List

from data.sector_momentum_universe import TREEMAP_GROUP_ORDER


def format_percent(value: Any) -> str:
    return f"{value}%" if value not in ("N/A", "TODO", None, "") else "N/A"


def sparkline(value: Any, floor: float = -10.0, ceiling: float = 10.0) -> str:
    try:
        number = 0.0 if value in ("N/A", "TODO", None, "") else float(value)
    except (TypeError, ValueError):
        number = 0.0
    clamped = max(floor, min(ceiling, number))
    span = max(abs(floor), abs(ceiling)) or 1.0
    x = 50 + (clamped / span) * 40
    color = "#2E7D32" if number >= 0 else "#BA1A1A"
    return (
        "<svg viewBox='0 0 100 24' class='sparkline' aria-hidden='true'>"
        "<line x1='10' y1='12' x2='90' y2='12'></line>"
        f"<circle cx='{x:.1f}' cy='12' r='5' fill='{color}'></circle>"
        "</svg>"
    )


def pn_class(val: Any) -> str:
    s = str(val).strip()
    if not s or s == "N/A":
        return "cell-muted"
    if s.startswith("-"):
        return "cell-neg"
    return "cell-pos"


def render_kpis(kpis: List[Dict[str, str]]) -> str:
    return "".join(
        f"<article class='kpi-pill {html.escape(item['tone'])}'>"
        f"<span class='kpi-pill__label'>{html.escape(item['label'])}</span>"
        f"<span class='kpi-pill__value'>{html.escape(item['value'])}</span>"
        "</article>"
        for item in kpis
    )


def render_trends(rows: List[Dict[str, Any]]) -> str:
    return "".join(
        "<article class='trend-card'>"
        f"<div class='trend-card__head'><span class='trend-ticker'>{html.escape(str(row['ticker']))}</span>"
        f"<strong class='trend-ret'>{html.escape(format_percent(row['return_60d']))}</strong></div>"
        f"{sparkline(row['return_60d'])}"
        "</article>"
        for row in rows
    )


def render_news_block(text: str) -> str:
    if not (text or "").strip():
        return (
            "<div class='news-panel news-panel--empty'>"
            "<p class='muted'>Tavily 키가 없거나 검색에 실패하면 뉴스 스니펫이 비어 있을 수 있습니다.</p>"
            "</div>"
        )
    return f"<pre class='news-panel'>{html.escape(text)}</pre>"


def render_macro_cards(items: List[Dict[str, str]]) -> str:
    return "".join(
        f"<article class='macro-card ink-shadow'>"
        f"<p class='macro-label'>{html.escape(item['label'])}</p>"
        f"<p class='macro-value serif'>{html.escape(item['value'])}</p>"
        "</article>"
        for item in items
    )


def render_macro_meta(source: str, error: str) -> str:
    if not (source or error):
        return ""
    parts = []
    if source:
        parts.append(f"출처: {html.escape(source)}")
    if error:
        parts.append(f"참고: {html.escape(error[:280])}")
    return f"<p class='meta-line muted'>{' · '.join(parts)}</p>"


def _rsi_width(val: Any) -> int:
    try:
        v = float(str(val).replace("%", "").strip())
        return max(0, min(100, int(round(v))))
    except (TypeError, ValueError):
        return 0


def render_holdings_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "<p class='empty-inline muted'>보유 종목이 없습니다. 왼쪽 터미널에 입력하거나 저장된 포트폴리오를 불러오세요.</p>"
    body = ""
    for row in rows:
        r20 = format_percent(row["return_20d"])
        r60 = format_percent(row["return_60d"])
        rsi = str(row["rsi_14"])
        w = _rsi_width(row["rsi_14"])
        flag = str(row["risk_flag"])
        bar_cls = "rsi-bar__fill rsi-bar__fill--warn" if w >= 70 else "rsi-bar__fill"
        body += (
            "<tr>"
            f"<td><strong>{html.escape(str(row['ticker']))}</strong></td>"
            f"<td class='muted'>{html.escape(str(row['avg_price']))}</td>"
            f"<td class='{pn_class(row['return_20d'])}'>{html.escape(r20)}</td>"
            f"<td class='{pn_class(row['return_60d'])}'>{html.escape(r60)}</td>"
            f"<td>{html.escape(format_percent(row['volatility_60d']))}</td>"
            f"<td><div class='rsi-cell'><span>{html.escape(rsi)}</span>"
            f"<div class='rsi-bar'><div class='{bar_cls}' style='width:{w}%'></div></div></div></td>"
            f"<td class='td-right'>{html.escape(flag)}</td>"
            "</tr>"
        )
    return (
        "<div class='table-wrap ink-shadow'>"
        "<table class='data-table'><thead><tr>"
        "<th>Ticker</th><th>Avg Price</th><th>1M Δ</th><th>3M Δ</th>"
        "<th>Vol 3M</th><th>RSI</th><th class='th-right'>Flags</th>"
        "</tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def _sector_ret_cell(val: Any) -> str:
    s = html.escape(str(val))
    cls = pn_class(val)
    return f"<td class='td-right {cls}'>{s}</td>"


def render_sector_flow(leaders: List[Dict[str, Any]], laggards: List[Dict[str, Any]]) -> str:
    def table_rows(items: List[Dict[str, Any]]) -> str:
        return "".join(
            "<tr class='hover-row'>"
            f"<td class='mono'>{idx:02d}</td>"
            f"<td><strong>{html.escape(str(it['ticker']))}</strong></td>"
            f"<td class='muted'>{html.escape(str(it.get('label', '')))}</td>"
            f"<td>{html.escape(str(it.get('score', '')))}</td>"
            f"{_sector_ret_cell(it.get('return_60d', ''))}"
            "</tr>"
            for idx, it in enumerate(items, start=1)
        )

    return f"""
    <div class="sector-grid">
      <div class="sector-col">
        <div class="section-rule">
          <h3 class="serif section-rule__title">Top Alpha Performers</h3>
          <div class="section-rule__line"></div>
        </div>
        <div class="table-wrap ink-shadow">
          <table class="data-table sector-table">
            <thead><tr>
              <th>Rank</th><th>Ticker</th><th>Category</th><th>Score</th><th class="th-right">3M Change</th>
            </tr></thead>
            <tbody>{table_rows(leaders)}</tbody>
          </table>
        </div>
      </div>
      <div class="sector-col">
        <div class="section-rule">
          <h3 class="serif section-rule__title">Market Laggards</h3>
          <div class="section-rule__line"></div>
        </div>
        <div class="table-wrap ink-shadow">
          <table class="data-table sector-table">
            <thead><tr>
              <th>Rank</th><th>Ticker</th><th>Category</th><th>Score</th><th class="th-right">3M Change</th>
            </tr></thead>
            <tbody>{table_rows(laggards)}</tbody>
          </table>
        </div>
      </div>
    </div>
    """


def _fmt_treemap_val(key: str, val: float | None) -> str:
    if val is None:
        return "—"
    if key in ("r1", "r20", "r60", "mcap3m"):
        return f"{val:+.2f}%"
    if key == "score":
        return f"{val:.1f}"
    if key == "rsi":
        return f"{val:.0f}"
    if key == "market_cap_b":
        return f"${val:.1f}B"
    return str(val)


def _treemap_tile_style(change_3m: float | None, vmin: float, vmax: float) -> str:
    if change_3m is None:
        return "background:#ece8dd;color:#44474b;"
    span = vmax - vmin
    if span < 1e-9:
        t = 0.5
    else:
        t = (change_3m - vmin) / span
    t = max(0.0, min(1.0, t))
    if change_3m >= 0:
        r = int(28 - 10 * t)
        g = int(96 + 110 * t)
        b = int(56 + 40 * t)
        return f"background:rgb({r},{g},{b});color:#f8f7f3;"
    r = int(120 + 90 * (1 - t))
    g = int(20 + 36 * t)
    b = int(28 + 24 * t)
    return f"background:rgb({r},{g},{b});color:#fff7f2;"


def _tile_dimensions(market_cap: float | None, smin: float, smax: float) -> tuple[int, int]:
    if market_cap is None or market_cap <= 0:
        return (2, 2)
    log_cap = math.log10(max(market_cap, 1.0))
    span = smax - smin
    t = 0.5 if span < 1e-9 else (log_cap - smin) / span
    t = max(0.0, min(1.0, t))
    if t >= 0.9:
        return (6, 5)
    if t >= 0.75:
        return (5, 4)
    if t >= 0.58:
        return (4, 3)
    if t >= 0.4:
        return (3, 3)
    if t >= 0.2:
        return (3, 2)
    return (2, 2)


def render_etf_treemap(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "<p class='muted small'>ETF 트리맵을 표시할 벤치마크 데이터가 없습니다.</p>"
    grouped_rows: Dict[str, List[Dict[str, Any]]] = {
        group: [row for row in rows if row.get("group") == group]
        for group in TREEMAP_GROUP_ORDER
    }
    sections = ""
    for group in TREEMAP_GROUP_ORDER:
        group_rows = grouped_rows.get(group) or []
        if not group_rows:
            continue
        vals_3m = [float(r["mcap3m"]) for r in group_rows if isinstance(r.get("mcap3m"), (int, float))]
        vals_mcap = [float(r["market_cap"]) for r in group_rows if isinstance(r.get("market_cap"), (int, float))]
        vmin, vmax = (min(vals_3m), max(vals_3m)) if vals_3m else (-1.0, 1.0)
        log_caps = [math.log10(max(v, 1.0)) for v in vals_mcap]
        smin, smax = (min(log_caps), max(log_caps)) if log_caps else (0.0, 1.0)
        cards = ""
        ranked_rows = sorted(
            group_rows,
            key=lambda item: item.get("market_cap") if isinstance(item.get("market_cap"), (int, float)) else float("-inf"),
            reverse=True,
        )
        for row in ranked_rows:
            lab = html.escape(str(row.get("label", "")))
            tk = html.escape(str(row.get("ticker", "")))
            mcap3m_val = row.get("mcap3m") if isinstance(row.get("mcap3m"), (int, float)) else None
            mc_val = row.get("market_cap") if isinstance(row.get("market_cap"), (int, float)) else None
            mcap3m = html.escape(_fmt_treemap_val("mcap3m", mcap3m_val))
            mcap_b = mc_val / 1_000_000_000 if mc_val is not None else None
            mcap_txt = html.escape(_fmt_treemap_val("market_cap_b", mcap_b))
            style = _treemap_tile_style(mcap3m_val, vmin, vmax)
            col_span, row_span = _tile_dimensions(mc_val, smin, smax)
            compact_cls = " treemap-tile--compact" if col_span <= 2 and row_span <= 2 else ""
            cards += (
                f"<article class='treemap-tile{compact_cls}' style='{style};grid-column:span {col_span};grid-row:span {row_span};'>"
                f"<p class='treemap-label'>{lab}</p>"
                "<div class='treemap-center'>"
                f"<p class='treemap-ticker'>{tk}</p>"
                f"<p class='treemap-change'>{mcap3m}</p>"
                "</div>"
                "<div class='treemap-stats'>"
                f"<span>현재 시총</span><span>{mcap_txt}</span><span>3M 시총 변화</span><span>{mcap3m}</span>"
                "</div>"
                "</article>"
            )
        sections += f"""
        <section class="treemap-section">
          <div class="treemap-group-head">
            <h5 class="serif treemap-group-title">{html.escape(group)}</h5>
          </div>
          <div class="treemap-grid">
            {cards}
          </div>
        </section>
        """
    return f"""
    <div class="treemap-wrap ink-shadow" id="treemap">
      <div class="treemap-head">
        <h4 class="serif treemap-title">Market Cap Treemap</h4>
        <p class="muted small treemap-desc">
          타일 크기: 현재 시가총액, 타일 색과 중앙 수치: 3개월 시총 변화율. 요청하신 5개 자산군으로 나눠 표시합니다.
        </p>
      </div>
      <div class="treemap-groups">
        {sections}
      </div>
    </div>
    """


def render_portfolio_intelligence_section(payload: Dict[str, Any]) -> str:
    holdings_input = html.escape(payload.get("holdings_input", ""))
    portfolio_label = html.escape(payload.get("portfolio_label", ""))
    report = html.escape(payload.get("portfolio_report", ""))
    error = html.escape(payload.get("portfolio_report_error", ""))
    market_label = html.escape(payload.get("market_report_label", "") or "")
    market_report = html.escape(payload.get("market_report", ""))
    market_err = html.escape(payload.get("market_report_error", ""))
    market_notion_url = str(payload.get("market_notion_url", "") or "").strip()
    portfolio_notion_url = str(payload.get("portfolio_notion_url", "") or "").strip()
    pending_job = payload.get("pending_job") or {}
    pending_flow = str(pending_job.get("flow", "")).strip()
    pending_status = str(pending_job.get("status", "")).strip()
    pending_step = html.escape(str(pending_job.get("current_step", "")).strip())
    market_pending = pending_flow == "market" and pending_status in {"pending", "running", "canceling"}
    portfolio_pending = pending_flow == "portfolio" and pending_status in {"pending", "running", "canceling"}

    report_m = (
        f"<pre class='report-block'>{market_report}</pre>"
        if market_report
        else "<p class='empty-state muted'>시장 리포트를 생성하면 CIO 최종본이 여기에 표시됩니다.</p>"
    )
    report_p = (
        f"<pre class='report-block'>{report}</pre>"
        if report
        else "<p class='empty-state muted'>보유 종목을 입력한 뒤 검증 리포트를 생성하면 결과가 여기에 표시됩니다.</p>"
    )
    if market_pending:
        report_m = (
            "<p class='empty-state muted'>시장 리포트를 백그라운드에서 처리 중입니다. "
            f"{pending_step or '현재 단계 확인 중'} · 완료되면 자동으로 표시됩니다.</p>"
        )
    if portfolio_pending:
        report_p = (
            "<p class='empty-state muted'>포트폴리오 검증 리포트를 백그라운드에서 처리 중입니다. "
            f"{pending_step or '현재 단계 확인 중'} · 완료되면 자동으로 표시됩니다.</p>"
        )
    err_m = f"<p class='alert alert--err'>{market_err}</p>" if market_err else ""
    err_p = f"<p class='alert alert--err'>{error}</p>" if error else ""
    cap_m = f"<p class='meta-line'>실행 라벨: {market_label}</p>" if market_label else ""
    cap_p = f"<p class='meta-line'>입력된 보유: {portfolio_label}</p>" if portfolio_label else ""
    notion_m = (
        f"<p class='meta-line'><a href='{html.escape(market_notion_url)}' target='_blank' rel='noreferrer'>Notion에서 열기</a></p>"
        if market_notion_url
        else ""
    )
    notion_p = (
        f"<p class='meta-line'><a href='{html.escape(portfolio_notion_url)}' target='_blank' rel='noreferrer'>Notion에서 열기</a></p>"
        if portfolio_notion_url
        else ""
    )

    table_html = render_holdings_table(payload.get("breakdown") or [])

    return f"""
    <section class="editorial-section" id="portfolio-intel">
      <div class="section-rule">
        <h2 class="serif section-rule__title">Portfolio Intelligence</h2>
        <div class="section-rule__line"></div>
      </div>
      <div class="intel-grid">
        <div class="intel-left">
          <div class="panel-elevated">
            <label class="terminal-label" for="holdings">Ticker Input Terminal</label>
            <p class="helper small">
              한 줄에 한 종목 · 티커·한글명·6자리 코드 · 평단은 <code>종목,가격</code>.
              기본은 빠른 모드이며 포트폴리오 제출 시 <code>data/user_portfolio.json</code>에 저장됩니다.
            </p>
            <form method="post" action="/" class="stack" data-report-form="portfolio">
              <textarea
                id="holdings"
                name="holdings"
                rows="8"
                class="terminal-input"
                placeholder="AAPL,185&#10;삼성전자,85000&#10;005930"
              >{holdings_input}</textarea>
              <button type="submit" name="flow" value="portfolio" class="btn btn-ghost" onclick="return showProgress('portfolio')">
                포트폴리오 검증 리포트 생성 (빠른 모드)
              </button>
            </form>
          </div>
          <div class="quote-panel ink-shadow">
            <p class="quote">“Intelligence is the ability to adapt to change.”</p>
          </div>
        </div>
        <div class="intel-right">
          <div class="panel-elevated panel-elevated--table">
            <div class="table-head">
              <span class="terminal-label">Current Verified Holdings</span>
              <span class="muted small">yfinance</span>
            </div>
            {table_html}
          </div>
        </div>
      </div>
      <div class="report-stack">
        <div class="report-card">
          <h4 class="serif report-card__title">시장 리포트 (CIO)</h4>
          {cap_m}
          {notion_m}
          {err_m}
          {report_m}
        </div>
        <div class="report-card">
          <h4 class="serif report-card__title">포트폴리오 검증 리포트</h4>
          {cap_p}
          {notion_p}
          {err_p}
          {report_p}
        </div>
      </div>
    </section>
    """
