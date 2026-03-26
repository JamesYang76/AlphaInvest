from __future__ import annotations

import html
from typing import Any, Dict, List


def _format_percent(value: Any) -> str:
    return f"{value}%" if value not in ("N/A", "TODO", None, "") else "N/A"


def _sparkline(value: Any, floor: float = -10.0, ceiling: float = 10.0) -> str:
    number = 0.0 if value in ("N/A", "TODO", None, "") else float(value)
    clamped = max(floor, min(ceiling, number))
    x = 50 + (clamped / max(abs(floor), abs(ceiling))) * 40
    color = "#1d4ed8" if number >= 0 else "#dc2626"
    return (
        "<svg viewBox='0 0 100 24' class='sparkline' aria-hidden='true'>"
        "<line x1='10' y1='12' x2='90' y2='12'></line>"
        f"<circle cx='{x:.1f}' cy='12' r='5' fill='{color}'></circle>"
        "</svg>"
    )


def _render_kpis(kpis: List[Dict[str, str]]) -> str:
    return "".join(
        f"<article class='card kpi {html.escape(item['tone'])}'>"
        f"<p class='eyebrow'>{html.escape(item['label'])}</p>"
        f"<strong>{html.escape(item['value'])}</strong>"
        "</article>"
        for item in kpis
    )


def _render_macro_cards(items: List[Dict[str, str]]) -> str:
    return "".join(
        f"<article class='card macro'>"
        f"<p class='eyebrow'>{html.escape(item['label'])}</p>"
        f"<strong>{html.escape(item['value'])}</strong>"
        "</article>"
        for item in items
    )


def _render_trends(rows: List[Dict[str, Any]]) -> str:
    return "".join(
        "<article class='card trend'>"
        f"<div><p class='eyebrow'>{html.escape(str(row['ticker']))}</p><strong>{html.escape(_format_percent(row['return_20d']))}</strong></div>"
        f"{_sparkline(row['return_20d'])}"
        "</article>"
        for row in rows
    )


def _render_table(rows: List[Dict[str, Any]]) -> str:
    body = "".join(
        "<tr>"
        f"<td>{html.escape(str(row['ticker']))}</td>"
        f"<td>{html.escape(str(row['avg_price']))}</td>"
        f"<td>{html.escape(_format_percent(row['return_5d']))}</td>"
        f"<td>{html.escape(_format_percent(row['return_20d']))}</td>"
        f"<td>{html.escape(_format_percent(row['volatility_20d']))}</td>"
        f"<td>{html.escape(str(row['rsi_14']))}</td>"
        f"<td>{html.escape(str(row['risk_flag']))}</td>"
        "</tr>"
        for row in rows
    )
    return (
        "<table><thead><tr><th>Ticker</th><th>Avg Price</th><th>5D</th><th>20D</th><th>Vol 20D</th><th>RSI 14</th><th>Flag</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def _render_report_section(payload: Dict[str, Any]) -> str:
    holdings_input = html.escape(payload.get("holdings_input", ""))
    portfolio_label = html.escape(payload.get("portfolio_label", ""))
    report = html.escape(payload.get("portfolio_report", ""))
    error = html.escape(payload.get("portfolio_report_error", ""))
    report_body = f"<pre class='report'>{report}</pre>" if report else "<p class='empty'>보유 종목을 입력하면 CIO까지 연결된 투자 리포트를 생성합니다.</p>"
    error_block = f"<p class='error'>{error}</p>" if error else ""
    summary = f"<p class='summary'>입력된 보유 종목: {portfolio_label}</p>" if portfolio_label else ""
    return f"""
    <section>
      <h2>Portfolio Report</h2>
      <form class="card form-card" method="get" action="/">
        <label class="eyebrow" for="holdings">Holdings Input</label>
        <p class="helper">한 줄에 하나씩 `티커,평단가` 형식으로 입력합니다. 예: `AAPL,185` 또는 `005930.KS,85000`</p>
        <textarea id="holdings" name="holdings" rows="6" placeholder="AAPL,185&#10;MSFT,410&#10;005930.KS,85000">{holdings_input}</textarea>
        <button type="submit">Generate Report</button>
      </form>
      {summary}
      {error_block}
      {report_body}
    </section>
    """


def render_dashboard(payload: Dict[str, Any]) -> str:
    assumptions = "".join(f"<li>{html.escape(item)}</li>" for item in payload["assumptions"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(payload["title"])}</title>
  <style>
    :root {{ --bg:#f5efe4; --panel:#fffaf2; --ink:#1f2937; --muted:#6b7280; --line:#d6c7ad; --blue:#1d4ed8; --red:#dc2626; --green:#15803d; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Georgia, "Times New Roman", serif; background:radial-gradient(circle at top, #fff8ee 0%, var(--bg) 48%, #eadfc8 100%); color:var(--ink); }}
    main {{ max-width:1200px; margin:0 auto; padding:40px 20px 64px; }}
    h1, h2 {{ margin:0; font-weight:700; }}
    p, li, td, th {{ line-height:1.5; }}
    .hero {{ display:grid; gap:16px; margin-bottom:28px; }}
    .subtitle, .eyebrow {{ color:var(--muted); margin:0; text-transform:uppercase; letter-spacing:.08em; font-size:.78rem; }}
    .assumptions {{ margin:0; padding-left:18px; }}
    .grid {{ display:grid; gap:16px; }}
    .kpi-grid {{ grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); margin:24px 0; }}
    .macro-grid, .trend-grid {{ grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); }}
    .card {{ background:rgba(255,250,242,.9); border:1px solid var(--line); border-radius:20px; padding:18px; box-shadow:0 12px 32px rgba(107,114,128,.08); }}
    .card strong {{ display:block; font-size:2rem; margin-top:8px; }}
    .kpi.positive strong {{ color:var(--green); }}
    .kpi.negative strong {{ color:var(--red); }}
    .trend {{ display:flex; justify-content:space-between; align-items:center; gap:12px; }}
    .sparkline {{ width:110px; height:28px; }}
    .sparkline line {{ stroke:var(--line); stroke-width:2; }}
    section {{ margin-top:28px; }}
    table {{ width:100%; border-collapse:collapse; background:rgba(255,250,242,.9); border:1px solid var(--line); border-radius:20px; overflow:hidden; }}
    th, td {{ padding:14px 16px; border-bottom:1px solid var(--line); text-align:left; }}
    th {{ font-size:.82rem; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }}
    tr:last-child td {{ border-bottom:none; }}
    .form-card {{ display:grid; gap:12px; }}
    .form-row {{ display:flex; gap:12px; }}
    input, textarea {{ flex:1; min-width:0; border:1px solid var(--line); border-radius:14px; padding:14px 16px; font:inherit; background:#fffdf8; }}
    textarea {{ resize:vertical; }}
    button {{ border:none; border-radius:14px; padding:14px 18px; background:#1f2937; color:#fffdf8; font:inherit; cursor:pointer; }}
    .report {{ margin:16px 0 0; padding:20px; white-space:pre-wrap; background:rgba(255,250,242,.9); border:1px solid var(--line); border-radius:20px; overflow:auto; }}
    .error, .empty {{ margin:16px 0 0; padding:16px 18px; border-radius:16px; background:rgba(255,250,242,.9); border:1px solid var(--line); }}
    .error {{ color:var(--red); }}
    .helper, .summary {{ margin:0; color:var(--muted); }}
    @media (max-width: 700px) {{
      .trend {{ align-items:flex-start; flex-direction:column; }}
      .card strong {{ font-size:1.6rem; }}
      th, td {{ padding:10px 12px; font-size:.92rem; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <p class="eyebrow">Dashboard Shell</p>
      <h1>{html.escape(payload["title"])}</h1>
      <p class="subtitle">{html.escape(payload["subtitle"])}</p>
      <div class="card">
        <p class="eyebrow">Assumptions</p>
        <ul class="assumptions">{assumptions}</ul>
      </div>
    </section>
    <section>
      <h2>Headline KPIs</h2>
      <div class="grid kpi-grid">{_render_kpis(payload["kpis"])}</div>
    </section>
    <section>
      <h2>Trend Snapshots</h2>
      <div class="grid macro-grid">{_render_macro_cards(payload["macro"])}</div>
      <div class="grid trend-grid" style="margin-top:16px;">{_render_trends(payload["trends"])}</div>
    </section>
    {_render_report_section(payload)}
    <section>
      <h2>Holdings Breakdown</h2>
      {_render_table(payload["breakdown"])}
    </section>
  </main>
</body>
</html>
"""
