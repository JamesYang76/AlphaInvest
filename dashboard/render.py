from __future__ import annotations

import html
import json
from typing import Any, Dict

from dashboard.render_sections import (
    render_etf_treemap,
    render_kpis,
    render_macro_cards,
    render_macro_meta,
    render_news_block,
    render_portfolio_intelligence_section,
    render_sector_flow,
    render_trends,
)


def render_dashboard(payload: Dict[str, Any]) -> str:
    assumptions = "".join(f"<li>{html.escape(item)}</li>" for item in payload["assumptions"])
    trends_rows = payload.get("trends") or []
    kpi_block = (
        f'<div class="kpi-strip">{render_kpis(payload["kpis"])}</div>'
        f'<div class="trend-strip">{render_trends(trends_rows)}</div>'
        if trends_rows
        else f'<div class="kpi-strip">{render_kpis(payload["kpis"])}</div>'
    )
    dash_time = html.escape(str(payload.get("dashboard_time", "")))
    pending_job_json = json.dumps(payload.get("pending_job") or {}, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(payload["title"])} | Editorial Intelligence</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link
    href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,400;0,700;0,800;1,400&family=Work+Sans:wght@300;400;500;600;700&display=swap"
    rel="stylesheet"
  >
  <style>
    :root {{
      --paper: #fdf9ee;
      --ink: #1c1c15;
      --primary: #040d17;
      --primary-container: #1a232e;
      --on-primary: #ffffff;
      --surface-low: #f7f3e8;
      --surface-lowest: #ffffff;
      --surface-high: #ece8dd;
      --muted: #44474b;
      --outline: rgba(117, 119, 124, 0.15);
      --error: #ba1a1a;
      --pos: #2e7d32;
      --neg: #ba1a1a;
      --ink-shadow: 0 12px 32px rgba(28, 28, 21, 0.04);
      --radius: 2px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Work Sans", system-ui, sans-serif;
      background: var(--paper);
      color: var(--ink);
      font-size: 15px;
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
    }}
    .serif {{ font-family: "Newsreader", Georgia, serif; }}
    .muted {{ color: var(--muted); }}
    .small {{ font-size: 0.85rem; }}
    code {{
      font-size: 0.88em;
      padding: 2px 6px;
      background: var(--surface-low);
      border-radius: 2px;
    }}
    a {{ color: inherit; text-decoration: none; }}

    .site-header {{
      position: sticky;
      top: 0;
      z-index: 50;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 16px 32px;
      background: var(--paper);
    }}
    .brand {{
      font-family: "Newsreader", Georgia, serif;
      font-weight: 800;
      font-size: 1.5rem;
      letter-spacing: -0.02em;
      color: var(--primary);
    }}
    .nav {{
      display: none;
      gap: 32px;
      align-items: center;
    }}
    @media (min-width: 768px) {{
      .nav {{ display: flex; }}
    }}
    .nav a {{
      font-family: "Newsreader", Georgia, serif;
      font-weight: 700;
      font-size: 1.05rem;
      color: #64748b;
      padding-bottom: 4px;
      border-bottom: 2px solid transparent;
    }}
    .nav a.is-active {{ color: var(--primary); border-color: var(--primary); }}
    .nav a:hover {{ color: var(--primary); }}
    .header-actions {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .search-wrap {{
      display: none;
      position: relative;
    }}
    @media (min-width: 640px) {{
      .search-wrap {{ display: block; }}
    }}
    .search-wrap input {{
      width: 260px;
      padding: 8px 12px 8px 36px;
      border: none;
      border-radius: var(--radius);
      background: var(--surface-low);
      font: inherit;
      font-size: 0.88rem;
    }}
    .search-wrap input:focus {{
      outline: 2px solid rgba(4, 13, 23, 0.2);
      outline-offset: 0;
    }}
    .search-wrap::before {{
      content: "⌕";
      position: absolute;
      left: 10px;
      top: 50%;
      transform: translateY(-50%);
      opacity: 0.45;
      font-size: 14px;
    }}
    .btn-top {{
      display: inline-block;
      border: none;
      border-radius: var(--radius);
      padding: 10px 18px;
      font: inherit;
      font-weight: 600;
      font-size: 0.88rem;
      cursor: pointer;
      background: var(--primary);
      color: var(--on-primary);
    }}
    .btn-top:hover {{ opacity: 0.92; }}

    .hairline {{
      height: 1px;
      width: 100%;
      background: var(--surface-low);
    }}

    .wrap {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 32px 32px 80px;
    }}

    .intro {{
      margin-bottom: 40px;
    }}
    .intro .eyebrow {{
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      margin: 0 0 8px;
    }}
    .intro h1 {{
      font-family: "Newsreader", Georgia, serif;
      font-size: clamp(1.75rem, 2.5vw, 2.25rem);
      font-weight: 700;
      margin: 0 0 8px;
      color: var(--primary);
    }}
    .intro .lede {{
      color: var(--muted);
      max-width: 62ch;
      margin: 0;
    }}
    .assumptions-panel {{
      margin-top: 20px;
      padding: 20px 24px;
      background: var(--surface-low);
      border-radius: var(--radius);
    }}
    .assumptions-panel ul {{ margin: 8px 0 0; padding-left: 20px; color: var(--ink); }}
    .assumptions-panel li {{ margin: 6px 0; font-size: 0.92rem; }}

    #snapshot {{ scroll-margin-top: 72px; }}
    .pulse-head {{
      display: flex;
      flex-wrap: wrap;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 24px;
    }}
    .pulse-head h2 {{
      font-family: "Newsreader", Georgia, serif;
      font-size: clamp(2.5rem, 5vw, 3rem);
      font-weight: 800;
      margin: 0;
      letter-spacing: -0.03em;
    }}
    .pulse-meta {{
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--muted);
      margin: 0 0 8px;
    }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.62rem;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .badge--soft {{ background: var(--surface-high); color: var(--muted); }}
    .badge--ink {{ background: var(--primary); color: var(--on-primary); }}

    .macro-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 20px;
    }}
    .market-pulse-actions {{
      margin-top: 18px;
      display: flex;
      justify-content: flex-start;
    }}
    .macro-card {{
      background: var(--surface-lowest);
      padding: 28px 20px;
      border-radius: var(--radius);
    }}
    .macro-label {{
      margin: 0 0 12px;
      font-size: 0.65rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .macro-value {{
      margin: 0;
      font-size: 2.25rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--primary);
    }}
    .ink-shadow {{ box-shadow: var(--ink-shadow); }}

    .meta-line {{ margin: 12px 0 0; font-size: 0.85rem; color: var(--muted); }}

    .kpi-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 28px 0 12px;
    }}
    .kpi-pill {{
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 12px 16px;
      background: var(--surface-lowest);
      border-radius: var(--radius);
      min-width: 140px;
      box-shadow: var(--ink-shadow);
    }}
    .kpi-pill__label {{
      font-size: 0.62rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .kpi-pill__value {{ font-size: 1.25rem; font-weight: 600; color: var(--primary); }}
    .kpi-pill.positive .kpi-pill__value {{ color: var(--pos); }}
    .kpi-pill.negative .kpi-pill__value {{ color: var(--neg); }}

    .trend-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      margin-top: 4px;
    }}
    .trend-card {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      background: var(--surface-lowest);
      border-radius: var(--radius);
      box-shadow: var(--ink-shadow);
    }}
    .trend-ticker {{ font-size: 0.65rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }}
    .trend-ret {{ font-size: 1.1rem; font-weight: 600; }}
    .sparkline {{ width: 100px; height: 26px; flex-shrink: 0; }}
    .sparkline line {{ stroke: rgba(28,28,21,0.12); stroke-width: 2; }}

    .section-heading {{
      margin: 48px 0 0;
      font-family: "Newsreader", Georgia, serif;
      font-size: 1.35rem;
      font-weight: 700;
      color: var(--primary);
    }}
    .section-sub {{
      margin: 6px 0 16px;
      font-size: 0.92rem;
      color: var(--muted);
      max-width: 62ch;
    }}

    .news-panel {{
      margin: 0;
      padding: 18px 22px;
      white-space: pre-wrap;
      font-size: 0.88rem;
      line-height: 1.55;
      background: var(--surface-lowest);
      border-radius: var(--radius);
      box-shadow: var(--ink-shadow);
      max-height: 280px;
      overflow: auto;
    }}
    .news-panel--empty {{ background: var(--surface-low); }}

    .section-rule {{
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 20px;
    }}
    .section-rule__title {{ margin: 0; font-size: 1.35rem; font-weight: 800; }}
    .section-rule__line {{
      flex: 1;
      height: 1px;
      background: rgba(197, 198, 204, 0.35);
    }}

    .sector-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 40px;
    }}
    @media (min-width: 1024px) {{
      .sector-grid {{ grid-template-columns: 1fr 1fr; gap: 48px; }}
    }}

    .treemap-wrap {{
      margin-top: 40px;
      background: var(--surface-lowest);
      border-radius: var(--radius);
      overflow: hidden;
    }}
    .treemap-head {{
      padding: 18px 20px 8px;
      border-bottom: 1px solid rgba(197, 198, 204, 0.15);
    }}
    .treemap-title {{ margin: 0 0 6px; font-size: 1.2rem; font-weight: 800; }}
    .treemap-desc {{ margin: 0; }}
    .treemap-groups {{
      display: grid;
      gap: 14px;
      padding: 14px;
    }}
    .treemap-section {{
      background: var(--surface-low);
      border-radius: var(--radius);
      overflow: hidden;
    }}
    .treemap-group-head {{
      padding: 10px 12px;
      border-bottom: 1px solid rgba(28, 28, 21, 0.08);
      background: rgba(255, 255, 255, 0.35);
    }}
    .treemap-group-title {{
      margin: 0;
      font-size: 1rem;
      font-weight: 700;
    }}
    .treemap-grid {{
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      grid-auto-flow: dense;
      grid-auto-rows: 30px;
      gap: 6px;
      padding: 10px;
    }}
    .treemap-tile {{
      border-radius: var(--radius);
      padding: 8px 10px;
      min-height: 72px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18);
    }}
    .treemap-ticker {{
      margin: 0;
      font-size: 1.25rem;
      font-weight: 800;
      letter-spacing: -0.01em;
    }}
    .treemap-label {{
      margin: 0;
      font-size: 0.64rem;
      font-weight: 600;
      opacity: 0.8;
      line-height: 1.25;
      text-transform: uppercase;
    }}
    .treemap-center {{
      display: flex;
      flex: 1;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      gap: 4px;
    }}
    .treemap-change {{
      margin: 0;
      font-size: 1.05rem;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }}
    .treemap-stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 2px 8px;
      font-size: 0.68rem;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
    }}
    .treemap-tile--compact {{
      padding: 6px 7px;
    }}
    .treemap-tile--compact .treemap-label,
    .treemap-tile--compact .treemap-stats {{
      display: none;
    }}
    .treemap-tile--compact .treemap-ticker {{
      font-size: 0.9rem;
    }}
    .treemap-tile--compact .treemap-change {{
      font-size: 0.78rem;
    }}
    @media (max-width: 1100px) {{
      .treemap-grid {{ grid-template-columns: repeat(8, minmax(0, 1fr)); }}
    }}
    @media (max-width: 720px) {{
      .treemap-grid {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
      .treemap-tile {{
        grid-column: span 2 !important;
        grid-row: span 2 !important;
      }}
    }}

    .table-wrap {{
      background: var(--surface-lowest);
      border-radius: var(--radius);
      overflow: hidden;
    }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }}
    .data-table thead tr {{
      background: var(--surface-low);
    }}
    .data-table th {{
      padding: 14px 18px;
      text-align: left;
      font-size: 0.62rem;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .data-table td {{
      padding: 14px 18px;
      border-top: 1px solid rgba(197, 198, 204, 0.12);
    }}
    .hover-row:hover {{ background: rgba(247, 243, 232, 0.8); }}
    .th-right, .td-right {{ text-align: right; }}
    .mono {{ font-variant-numeric: tabular-nums; }}
    .cell-pos {{ color: var(--pos); font-weight: 600; }}
    .cell-neg {{ color: var(--neg); font-weight: 600; }}
    .cell-muted {{ color: var(--muted); }}

    .intel-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 32px;
      margin-top: 8px;
    }}
    @media (min-width: 1024px) {{
      .intel-grid {{ grid-template-columns: minmax(280px, 1fr) minmax(0, 2fr); gap: 48px; }}
    }}
    .panel-elevated {{
      background: var(--surface-low);
      padding: 24px;
      border-radius: var(--radius);
    }}
    .panel-elevated--table {{ padding: 0; overflow: hidden; }}
    .table-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 20px;
      background: var(--surface-low);
      border-bottom: 1px solid rgba(197, 198, 204, 0.12);
    }}
    .terminal-label {{
      display: block;
      font-size: 0.62rem;
      font-weight: 800;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .stack {{ display: flex; flex-direction: column; gap: 12px; }}
    .terminal-input {{
      width: 100%;
      border: none;
      border-radius: var(--radius);
      padding: 14px 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
      font-size: 0.82rem;
      resize: vertical;
      min-height: 160px;
      background: var(--surface-lowest);
      color: var(--ink);
    }}
    .terminal-input:focus {{
      outline: none;
      box-shadow: inset 0 -2px 0 0 var(--primary);
    }}
    .btn {{
      border-radius: var(--radius);
      padding: 14px 16px;
      font: inherit;
      font-size: 0.7rem;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      cursor: pointer;
      border: none;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}
    .btn-ink {{
      background: linear-gradient(to bottom, var(--primary), var(--primary-container));
      color: var(--on-primary);
    }}
    .btn-ink:hover {{ opacity: 0.92; }}
    .btn-ghost {{
      background: var(--surface-high);
      color: var(--primary);
      border: 1px solid rgba(117, 119, 124, 0.2);
    }}
    .btn-ghost:hover {{ background: var(--surface-low); }}

    .quote-panel {{
      margin-top: 20px;
      padding: 20px 22px;
      border-radius: var(--radius);
      background: linear-gradient(135deg, var(--primary) 0%, #0f1720 100%);
      min-height: 140px;
      display: flex;
      align-items: flex-end;
    }}
    .quote {{
      margin: 0;
      font-family: "Newsreader", Georgia, serif;
      font-style: italic;
      font-size: 1.05rem;
      line-height: 1.45;
      color: #f4f1e6;
    }}

    .rsi-cell {{ display: flex; align-items: center; gap: 8px; }}
    .rsi-bar {{
      width: 48px;
      height: 4px;
      border-radius: 999px;
      background: var(--surface-high);
      overflow: hidden;
    }}
    .rsi-bar__fill {{
      height: 100%;
      background: var(--primary);
      border-radius: 999px;
    }}
    .rsi-bar__fill--warn {{ background: var(--error); }}

    .report-stack {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 20px;
      margin-top: 32px;
    }}
    @media (min-width: 900px) {{
      .report-stack {{ grid-template-columns: 1fr 1fr; }}
    }}
    .report-card {{
      padding: 20px 22px;
      background: var(--surface-low);
      border-radius: var(--radius);
    }}
    .report-card__title {{ margin: 0 0 12px; font-size: 1.1rem; font-weight: 800; }}
    .report-block {{
      margin: 0;
      padding: 16px 18px;
      white-space: pre-wrap;
      font-size: 0.82rem;
      line-height: 1.55;
      background: var(--surface-lowest);
      border-radius: var(--radius);
      max-height: 320px;
      overflow: auto;
    }}
    .empty-state {{ margin: 0; font-size: 0.88rem; }}
    .alert {{ margin: 8px 0 0; font-size: 0.88rem; }}
    .alert--err {{ color: var(--error); }}

    .site-footer {{
      margin-top: 64px;
      padding: 40px 32px 48px;
      border-top: 1px solid rgba(197, 198, 204, 0.2);
      max-width: 1440px;
      margin-left: auto;
      margin-right: auto;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 32px;
    }}
    .site-footer .brand {{ font-size: 1.25rem; margin-bottom: 8px; display: block; }}
    .footer-links h4 {{
      margin: 0 0 12px;
      font-size: 0.62rem;
      font-weight: 800;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--primary);
    }}
    .footer-links ul {{
      list-style: none;
      margin: 0;
      padding: 0;
      font-size: 0.72rem;
      font-weight: 500;
      color: var(--muted);
      line-height: 1.8;
    }}

    @media (max-width: 700px) {{
      .site-header {{ flex-wrap: wrap; }}
      .brand {{ width: 100%; }}
    }}

    .editorial-section {{ margin-top: 56px; }}

    /* Report generation progress overlay */
    #report-progress-overlay {{
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.22);
      backdrop-filter: blur(4px);
      z-index: 1000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 18px;
    }}
    #report-progress-overlay .progress-card {{
      width: min(720px, 100%);
      background: var(--surface-lowest);
      border-radius: var(--radius);
      box-shadow: var(--ink-shadow);
      padding: 20px 22px;
    }}
    #report-progress-overlay .progress-top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }}
    #report-progress-overlay .progress-title {{
      font-family: "Newsreader", Georgia, serif;
      font-weight: 800;
      font-size: 1.15rem;
    }}
    #report-progress-overlay .progress-helper {{
      color: var(--muted);
      font-size: 0.92rem;
      margin-top: 4px;
    }}
    #report-progress-overlay .progress-step {{
      margin-top: 10px;
      color: var(--ink);
      font-weight: 500;
      font-size: 0.95rem;
    }}
    #report-progress-overlay .progress-actions {{
      margin-top: 16px;
      display: flex;
      justify-content: flex-end;
    }}
    #report-progress-overlay .btn-cancel {{
      border: 1px solid rgba(4, 13, 23, 0.18);
      background: var(--surface-lowest);
      color: var(--primary);
      padding: 9px 14px;
      border-radius: var(--radius);
      font: inherit;
      font-weight: 600;
      cursor: pointer;
    }}
    #report-progress-overlay .btn-cancel[disabled] {{
      opacity: 0.55;
      cursor: not-allowed;
    }}
    #report-progress-overlay .progress-bar {{
      height: 12px;
      width: 100%;
      background: var(--surface-high);
      border-radius: 999px;
      overflow: hidden;
      margin-top: 12px;
    }}
    #report-progress-overlay .progress-bar-fill {{
      height: 100%;
      width: 0%;
      background: var(--primary);
      transition: width 180ms ease;
    }}
    #report-progress-overlay .progress-spinner {{
      width: 18px;
      height: 18px;
      border-radius: 50%;
      border: 2px solid rgba(4, 13, 23, 0.2);
      border-top-color: var(--primary);
      animation: spin 900ms linear infinite;
    }}
    @keyframes spin {{
      from {{ transform: rotate(0deg); }}
      to {{ transform: rotate(360deg); }}
    }}
  </style>
</head>
<body>
  <header class="site-header" role="banner">
    <span class="brand">{html.escape(payload["title"])}</span>
    <nav class="nav" aria-label="Primary">
      <a class="is-active" href="#snapshot">Home</a>
      <a href="#portfolio-intel">Portfolio</a>
      <a href="#movers">Markets</a>
    </nav>
    <div class="header-actions">
      <div class="search-wrap">
        <input type="search" placeholder="Search markets…" aria-label="Search markets" autocomplete="off" />
      </div>
      <a class="btn-top" href="#portfolio-intel">Generate Report</a>
    </div>
  </header>
  <div class="hairline"></div>

  <main class="wrap">
    <section class="intro">
      <p class="eyebrow">Editorial Intelligence</p>
      <h1 class="serif">Market Pulse</h1>
      <p class="lede">{html.escape(payload["subtitle"])}</p>
      <div class="assumptions-panel">
        <p class="eyebrow" style="margin:0">이 터미널에서 하는 일</p>
        <ul class="assumptions">{assumptions}</ul>
      </div>
    </section>

    <section id="snapshot">
      <div class="pulse-head">
        <div>
          <p class="pulse-meta">Updated · {dash_time}</p>
          <h2 class="serif">Market Pulse</h2>
        </div>
        <div class="badges">
          <span class="badge badge--soft">Live feed</span>
          <span class="badge badge--ink">Global terminal</span>
        </div>
      </div>
      <div class="macro-grid">{render_macro_cards(payload["macro"])}</div>
      {render_macro_meta(payload.get("macro_source", ""), payload.get("macro_error", ""))}
      <div class="market-pulse-actions">
        <form method="post" action="/" data-report-form="market">
          <button type="submit" name="flow" value="market" class="btn btn-ink" onclick="return showProgress('market')">
            시장 리포트 생성 (빠른 모드)
          </button>
        </form>
      </div>

      <h3 class="section-heading">Holdings snapshot</h3>
      <p class="section-sub">저장·입력된 포트폴리오 기준 요약 지표와 종목별 3개월 수익률 흐름입니다.</p>
      {kpi_block}
    </section>

    <section id="movers">
      <h3 class="section-heading">Sector &amp; asset flow</h3>
      <p class="section-sub">벤치마크 ETF 유니버스에서 복합 점수 상·하위 요약입니다.</p>
      {render_sector_flow(payload.get("sector_leaders", []), payload.get("sector_laggards", []))}
      {render_etf_treemap(payload.get("etf_heatmap") or [])}
    </section>

    <section>
      <h3 class="section-heading">News intelligence</h3>
      <p class="section-sub">Tavily 검색 기반 스니펫입니다.</p>
      {render_news_block(payload.get("news_snippet", ""))}
    </section>

    {render_portfolio_intelligence_section(payload)}
  </main>

  <footer class="site-footer">
    <div>
      <span class="brand serif">{html.escape(payload["title"])}</span>
      <p class="muted small" style="max-width: 28rem; margin: 0">
        Providing institutional-grade market analysis and portfolio verification for the modern strategist.
      </p>
    </div>
    <div class="footer-links">
      <h4>Intelligence</h4>
      <ul>
        <li>Daily briefings</li>
        <li>Sector rotation</li>
        <li>Risk modeling</li>
      </ul>
    </div>
    <div class="footer-links">
      <h4>Account</h4>
      <ul>
        <li>Verified terminal</li>
        <li>Portfolio sync</li>
        <li>Support</li>
      </ul>
    </div>
  </footer>

  <div id="report-progress-overlay" role="status" aria-live="polite">
    <div class="progress-card">
      <div class="progress-top">
        <div>
          <div class="progress-title">리포트 생성 진행 중</div>
          <div class="progress-helper" id="report-progress-helper">잠시만 기다려 주세요.</div>
        </div>
        <div class="progress-spinner" aria-hidden="true"></div>
      </div>
      <div class="progress-step" id="report-progress-step">준비 중…</div>
      <div class="progress-bar" aria-hidden="true">
        <div class="progress-bar-fill" id="report-progress-bar-fill"></div>
      </div>
      <div class="progress-step muted small">
        리포트는 백그라운드 job으로 처리되며, 단계 표시는 예상 타임라인입니다.
      </div>
      <div class="progress-actions">
        <button type="button" class="btn-cancel" id="report-cancel-button" onclick="cancelPendingJob()" disabled>
          취소
        </button>
      </div>
    </div>
  </div>

  <script>
    const pendingJob = {pending_job_json};
    window.__reportProgressActualStep = pendingJob && pendingJob.current_step ? pendingJob.current_step : '';

    function stopProgressAnimation() {{
      if (window.__reportProgressTimer) {{
        window.clearInterval(window.__reportProgressTimer);
        window.__reportProgressTimer = null;
      }}
    }}

    function showProgress(flow) {{
      const overlay = document.getElementById('report-progress-overlay');
      const barFill = document.getElementById('report-progress-bar-fill');
      const stepEl = document.getElementById('report-progress-step');
      const helperEl = document.getElementById('report-progress-helper');
      const cancelBtn = document.getElementById('report-cancel-button');
      if (!overlay || !barFill || !stepEl || !helperEl || !cancelBtn) return true;

      const isMarket = flow === 'market';
      helperEl.textContent = isMarket
        ? '시장 리포트를 생성하고 있습니다…'
        : '포트폴리오 검증 리포트를 생성하고 있습니다…';
      stepEl.textContent = window.__reportProgressActualStep || '준비 중…';
      barFill.style.width = '0%';
      overlay.style.display = 'flex';
      cancelBtn.disabled = !pendingJob || !pendingJob.id || !pendingJob.cancel_url;
      cancelBtn.textContent = '취소';

      const steps = [
        {{ at: 0.10, text: '거시/시장 데이터 수집' }},
        {{ at: 0.30, text: '섹터 ETF 모멘텀 계산' }},
        {{ at: 0.55, text: '뉴스/리스크/알파 분석' }},
        {{ at: 0.78, text: 'CIO 합성 리포트 정리' }},
        {{ at: 0.95, text: '리포트 마무리' }},
      ];

      const start = Date.now();
      const durationMs = 90000;
      const maxShown = 92;

      const tick = () => {{
        const elapsed = Date.now() - start;
        const p = Math.min(1, elapsed / durationMs);
        const shown = Math.round(maxShown * p);
        barFill.style.width = shown + '%';

        let currentText = steps[0].text;
        for (const s of steps) {{
          if (p >= s.at) currentText = s.text;
        }}
        stepEl.textContent = window.__reportProgressActualStep || currentText;
      }};

      stopProgressAnimation();
      tick();
      window.__reportProgressTimer = window.setInterval(tick, 280);

      document.querySelectorAll('form[data-report-form] button[type="submit"]').forEach((btn) => {{
        btn.disabled = true;
        btn.style.opacity = '0.85';
      }});

      return true;
    }}

    async function cancelPendingJob() {{
      if (!pendingJob || !pendingJob.id || !pendingJob.cancel_url) return;
      const cancelBtn = document.getElementById('report-cancel-button');
      const helperEl = document.getElementById('report-progress-helper');
      const stepEl = document.getElementById('report-progress-step');
      if (cancelBtn) {{
        cancelBtn.disabled = true;
        cancelBtn.textContent = '취소 요청 중…';
      }}
      if (helperEl) {{
        helperEl.textContent = '리포트 취소를 요청하고 있습니다…';
      }}
      if (stepEl) {{
        window.__reportProgressActualStep = '취소 처리 중';
        stepEl.textContent = '취소 처리 중';
      }}
      try {{
        const response = await fetch(pendingJob.cancel_url, {{ method: 'POST' }});
        if (!response.ok) {{
          throw new Error('job cancel failed');
        }}
        const data = await response.json();
        if (helperEl) {{
          helperEl.textContent = '리포트 취소를 처리하고 있습니다…';
        }}
        if (stepEl) {{
          window.__reportProgressActualStep = data.current_step || '취소 처리 중';
          stepEl.textContent = window.__reportProgressActualStep;
        }}
        if (cancelBtn) {{
          cancelBtn.disabled = true;
          cancelBtn.textContent = '취소 처리 중…';
        }}
      }} catch (_err) {{
        if (helperEl) {{
          helperEl.textContent = '취소 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.';
        }}
        if (cancelBtn) {{
          cancelBtn.disabled = false;
          cancelBtn.textContent = '취소';
        }}
      }}
    }}

    async function pollPendingJob() {{
      if (!pendingJob || !pendingJob.id || !pendingJob.status_url) return;
      showProgress(pendingJob.flow || 'portfolio');

      const overlay = document.getElementById('report-progress-overlay');
      const helperEl = document.getElementById('report-progress-helper');
      const stepEl = document.getElementById('report-progress-step');
      const cancelBtn = document.getElementById('report-cancel-button');

      const poll = async () => {{
        try {{
          const response = await fetch(pendingJob.status_url, {{ cache: 'no-store' }});
          if (!response.ok) {{
            throw new Error('job status fetch failed');
          }}
          const data = await response.json();
          if (data.status === 'completed' || data.status === 'failed' || data.status === 'canceled') {{
            stopProgressAnimation();
            window.location.replace(data.result_url);
            return;
          }}
          if (helperEl) {{
            helperEl.textContent = data.status === 'canceling'
              ? '리포트 취소를 처리하고 있습니다…'
              : data.flow === 'market'
                ? '시장 리포트를 백그라운드에서 생성하고 있습니다…'
                : '포트폴리오 검증 리포트를 백그라운드에서 생성하고 있습니다…';
          }}
          if (data.current_step) {{
            window.__reportProgressActualStep = data.current_step;
          }}
          if (stepEl) {{
            stepEl.textContent = window.__reportProgressActualStep || '진행 중…';
          }}
          if (cancelBtn) {{
            cancelBtn.disabled = data.status === 'canceling' || !data.cancel_url;
            cancelBtn.textContent = data.status === 'canceling' ? '취소 처리 중…' : '취소';
          }}
          if (stepEl && overlay && overlay.style.display !== 'flex') {{
            overlay.style.display = 'flex';
          }}
        }} catch (_err) {{
          if (helperEl) {{
            helperEl.textContent = '일시적으로 상태 조회에 실패했습니다. 다시 확인 중입니다…';
          }}
        }}
        window.setTimeout(poll, 1200);
      }};

      await poll();
    }}

    if (pendingJob && pendingJob.id) {{
      window.setTimeout(() => {{
        pollPendingJob();
      }}, 120);
    }}
  </script>
</body>
</html>
"""
