from __future__ import annotations

import json
import os
from textwrap import dedent
from typing import Any, Dict, List

from dotenv import load_dotenv

from agents.constants import AgentName, StateKey
from agents.nodes.runtime_status import notify_runtime_progress
from agents.state import AgentState
from data.composite_score import compute_composite_scores_for_signals
from data.fetchers import fetch_market_signals, get_llm
from data.sector_momentum_universe import label_for_symbol, sector_momentum_symbols
from utils.logger import get_logger

logger = get_logger("agents.nodes.chart")

load_dotenv()


def _classify_rsi(rsi: Any) -> str:
    try:
        r = float(rsi)
    except (TypeError, ValueError):
        return "-"
    if r >= 70:
        return "과열(매수과다)"
    if r <= 30:
        return "과매도(매도과다)"
    return "중립(레인지)"


def _momentum_label(return_60d: Any) -> str:
    try:
        r = float(return_60d)
    except (TypeError, ValueError):
        return "-"
    if r >= 0:
        return "3개월 상승 모멘텀"
    return "3개월 약세/하락 모멘텀"


def _format_signal_line(
    ticker: str,
    s: Dict[str, Any],
    label: str | None = None,
    composite: float | None = None,
) -> str:
    rsi = s.get("rsi_14")
    rsi_label = _classify_rsi(rsi)
    ret60 = s.get("return_60d")
    mom = _momentum_label(ret60)
    head = f"{ticker}" + (f" ({label})" if label else "")
    score_part = f", 복합점수={composite:.1f}" if composite is not None else ""
    return (
        f"- {head}: RSI14={rsi} ({rsi_label}), 1M={s.get('return_20d')}, 3M={s.get('return_60d')} ({mom}), "
        f"변동성3M={s.get('volatility_60d')}, 6M DD={s.get('drawdown_6m')}, MA20 괴리={s.get('ma20_divergence')}"
        f"{score_part}"
    )


def _build_benchmark_payload(
    bench_signals: Dict[str, Any], bench_scores: Dict[str, float | None]
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for sym in sector_momentum_symbols():
        s = bench_signals.get(sym) or {}
        if s.get("error"):
            continue
        rows.append(
            {
                "ticker": sym,
                "label": label_for_symbol(sym),
                "composite": bench_scores.get(sym),
                "return_1d": s.get("return_1d"),
                "return_20d": s.get("return_20d"),
                "return_60d": s.get("return_60d"),
                "rsi_14": s.get("rsi_14"),
                "volatility_60d": s.get("volatility_60d"),
                "drawdown_6m": s.get("drawdown_6m"),
                "ma20_divergence": s.get("ma20_divergence"),
                "market_cap": s.get("market_cap"),
            }
        )
    rows.sort(
        key=lambda r: r["composite"] if r["composite"] is not None else float("-inf"),
        reverse=True,
    )
    return rows


def _fallback_sector_allocation_analysis(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    top = rows[:3]
    bottom = list(reversed(rows[-3:])) if len(rows) >= 3 else list(reversed(rows))
    lines: List[str] = [
        "[3개월 자산배분 관점 — 추천·위험 섹터 (규칙 기반 요약, API 키 없음 또는 LLM 생략)]",
        "",
        "상대 추천(복합점수 상위):",
    ]
    for r in top:
        c = r.get("composite")
        c_s = f"{c:.1f}" if c is not None else "-"
        lines.append(
            f"- {r['ticker']} ({r['label']}): 복합={c_s}, 1M={r.get('return_20d')}, "
            f"3M={r.get('return_60d')}, 변동성3M={r.get('volatility_60d')}, 6M DD={r.get('drawdown_6m')}"
        )
    lines.append("")
    lines.append("상대 위험·회피(복합점수 하위):")
    for r in bottom:
        c = r.get("composite")
        c_s = f"{c:.1f}" if c is not None else "-"
        lines.append(
            f"- {r['ticker']} ({r['label']}): 복합={c_s}, 1M={r.get('return_20d')}, "
            f"3M={r.get('return_60d')}, 변동성3M={r.get('volatility_60d')}, 6M DD={r.get('drawdown_6m')}"
        )
    return "\n".join(lines)


def _sector_allocation_llm_analysis(rows: List[Dict[str, Any]]) -> str:
    """yfinance 벤치마크 지표를 바탕으로 3개월 자산배분 관점의 추천·위험 섹터를 LLM이 서술한다."""
    if not rows:
        return ""
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        return _fallback_sector_allocation_analysis(rows)
    brief = json.dumps(rows, ensure_ascii=False, indent=2)
    prompt = dedent(
        f"""
        당신은 글로벌 멀티자산 전략가입니다. 아래 JSON은 yfinance로 산출한 ETF(섹터·지역·자산군) 벤치마크 지표입니다.
        복합점수는 동일 유니버스 횡단면 min-max 표준화 후 가중합(100점 만점)입니다.

        투자 전제: 약 3개월(60~65 거래일) 보유를 가정한 자산 배분(비중을 어디에 늘리거나 줄일지) 관점으로만 작성하세요.
        단기 매매 시그널이 아닌, 상대적 선호·회피 논리에 집중하세요.

        [데이터]
        {brief}

        [출력 — 반드시 한국어]
        1) 추천 섹터·자산군 (3개월 배분 관점)
           - 불릿 3개: 데이터에 있는 ETF만 선택. 각 불릿에 티커와 한글 라벨을 쓰고,
             복합점수·1개월/3개월 수익률·3개월 변동성·6개월 낙폭 등 제공 수치만 인용해 근거를 2~3문장으로.
        2) 위험·회피 섹터·자산군 (3개월 배분 관점)
           - 불릿 3개: 동일 규칙.

        규칙: 데이터에 없는 티커를 지어내지 마세요. 수치도 위 JSON에 있는 값만 사용하세요.
        """
    ).strip()
    try:
        llm = get_llm(temperature=0.35)
        text = llm.invoke(prompt).content
        return (
            "[3개월 자산배분 관점 — 추천·위험 섹터 (LLM, yfinance 벤치마크 기반)]\n\n"
            + (text or "").strip()
        )
    except Exception as e:
        logger.warning("[Chart] LLM 섹터 분석 실패, 규칙 요약으로 대체: %s", e)
        return _fallback_sector_allocation_analysis(rows)


def chart_node(state: AgentState) -> Dict[str, Any]:
    """
    기술적 차트 요약 노드.

    - yfinance 기반 지표(`fetch_market_signals`)를 기반으로 기술적 차트 요약을 생성합니다.
    - 보유 종목 + `data/sector_momentum_universe` 고정 벤치마크(섹터·지역·자산군 ETF) 모멘텀을 함께 봅니다.
    - Risk/Alpha 프롬프트에 근거로 넣기 위해 `chart_result`와 `current_report`를 채웁니다.
    """
    user_portfolio = state.get(StateKey.USER_PORTFOLIO, [])
    tickers: List[str] = [item.get("ticker") for item in user_portfolio if item.get("ticker")]
    bench = sector_momentum_symbols()

    logger.info("[Chart] 보유 티커·섹터 벤치마크 기술 신호 수집 중...")
    notify_runtime_progress(state, "chart_fetch_portfolio_signals")
    port_signals = fetch_market_signals(tickers) if tickers else {}
    notify_runtime_progress(state, "chart_fetch_benchmark_signals")
    bench_signals = fetch_market_signals(bench)
    # 동일 심볼이 보유와 벤치에 겹치면 보유 쪽 지표를 유지
    merged: Dict[str, Any] = {**bench_signals, **port_signals}

    port_scores = compute_composite_scores_for_signals(port_signals) if tickers else {}
    bench_scores = compute_composite_scores_for_signals(bench_signals)
    # 동일 티커가 보유·벤치에 겹치면 보유 유니버스 기준 점수를 우선 저장
    combined_scores = {**bench_scores, **port_scores}
    for sym, sc in combined_scores.items():
        if sym in merged and not (merged[sym] or {}).get("error"):
            merged[sym] = {**merged[sym], "composite_score": sc}

    overbought = 0
    oversold = 0
    up = 0
    down = 0

    lines: List[str] = ["[기술적 차트 요약]", ""]

    if tickers:
        lines.append("[보유 종목]")
        for t in tickers:
            s = port_signals.get(t) or {}
            if s.get("error"):
                lines.append(f"- {t}: 지표 수집 실패({s['error']})")
                continue
            rsi = s.get("rsi_14")
            rsi_label = _classify_rsi(rsi)
            if rsi_label.startswith("과열"):
                overbought += 1
            if rsi_label.startswith("과매도"):
                oversold += 1
            ret60 = s.get("return_60d")
            mom = _momentum_label(ret60)
            if mom.startswith("3개월 상승"):
                up += 1
            elif mom.startswith("3개월 약세"):
                down += 1
            lines.append(_format_signal_line(t, s, composite=port_scores.get(t)))
        lines.append("")
        lines.append(
            f"보유 요약: 과열 {overbought}개 / 과매도 {oversold}개, 3개월 상승 모멘텀 {up}개 / 약세 모멘텀 {down}개"
        )
        lines.append("")

    lines.append("[섹터·자산군 ETF 모멘텀 (yfinance 벤치마크)]")
    lines.append(
        "랭킹: 동일 유니버스 횡단면 min-max 표준화 후 가중합 복합점수(100점 만점) 기준 내림차순 — "
        "3개월(~60거래일) 리포트 가정: 3M 수익 45%, 1M 수익 15%, 3M 변동성 역 15%, 6M 낙폭 역 15%, RSI 중간 선호 5%, MA20 괴리 역 5%. "
        "(핵심 모멘텀=3개월, 1개월 지표는 추세 확인용 보조.)"
    )
    bench_rows: List[tuple[str, Dict[str, Any], float]] = []
    for sym in bench:
        s = bench_signals.get(sym) or {}
        if s.get("error"):
            lines.append(f"- {sym} ({label_for_symbol(sym)}): 수집 실패({s['error']})")
            continue
        sc = bench_scores.get(sym)
        sort_key = sc if sc is not None else float("-inf")
        bench_rows.append((sym, s, sort_key))

    bench_rows.sort(key=lambda x: x[2], reverse=True)
    for sym, s, _ in bench_rows:
        lines.append(_format_signal_line(sym, s, label_for_symbol(sym), composite=bench_scores.get(sym)))

    bench_payload = _build_benchmark_payload(bench_signals, bench_scores)
    notify_runtime_progress(state, "chart_build_allocation_analysis")
    allocation = _sector_allocation_llm_analysis(bench_payload)
    if allocation:
        lines.append("")
        lines.append(allocation)

    chart_result = "\n".join(lines).strip()

    return {
        StateKey.CHART_RESULT: chart_result,
        StateKey.CHART_DATA: merged,
        StateKey.CURRENT_REPORT: chart_result,
        "last_node": AgentName.CHART,
    }


if __name__ == "__main__":
    # 단독 테스트: LLM 없이 동작 확인
    from agents.state import get_initial_state

    test_state = get_initial_state(user_portfolio=[{"ticker": "005930.KS", "avg_price": 85000}])
    result = chart_node(test_state)
    print(result[StateKey.CHART_RESULT])
