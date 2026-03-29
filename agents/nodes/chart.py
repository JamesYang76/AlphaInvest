from __future__ import annotations

from typing import Any, Dict, List

from agents.constants import AgentName, StateKey
from agents.state import AgentState
from data.composite_score import compute_composite_scores_for_signals
from data.fetchers import fetch_market_signals
from data.sector_momentum_universe import label_for_symbol, sector_momentum_symbols
from utils.logger import get_logger

logger = get_logger("agents.nodes.chart")


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


def _momentum_label(return_20d: Any) -> str:
    try:
        r = float(return_20d)
    except (TypeError, ValueError):
        return "-"
    if r >= 0:
        return "중기 상승 모멘텀"
    return "중기 약세/하락 모멘텀"


def _format_signal_line(
    ticker: str,
    s: Dict[str, Any],
    label: str | None = None,
    composite: float | None = None,
) -> str:
    rsi = s.get("rsi_14")
    rsi_label = _classify_rsi(rsi)
    ret20 = s.get("return_20d")
    mom = _momentum_label(ret20)
    head = f"{ticker}" + (f" ({label})" if label else "")
    score_part = f", 복합점수={composite:.1f}" if composite is not None else ""
    return (
        f"- {head}: RSI14={rsi} ({rsi_label}), 5D={s.get('return_5d')}, 20D={s.get('return_20d')} ({mom}), "
        f"변동성20D={s.get('volatility_20d')}, 3M DD={s.get('drawdown_3m')}, MA5 괴리={s.get('ma5_divergence')}"
        f"{score_part}"
    )


def chart_node(state: AgentState) -> Dict[str, Any]:
    """
    기술적 차트 요약 노드.

    - LLM 없이 yfinance 기반 지표(`fetch_market_signals`)로 간단한 텍스트 증거를 생성합니다.
    - 보유 종목 + `data/sector_momentum_universe` 고정 벤치마크(섹터·지역·자산군 ETF) 모멘텀을 함께 봅니다.
    - Risk/Alpha 프롬프트에 근거로 넣기 위해 `chart_result`와 `current_report`를 채웁니다.
    """
    user_portfolio = state.get(StateKey.USER_PORTFOLIO, [])
    tickers: List[str] = [item.get("ticker") for item in user_portfolio if item.get("ticker")]
    bench = sector_momentum_symbols()

    logger.info("[Chart] 보유 티커·섹터 벤치마크 기술 신호 수집 중...")
    port_signals = fetch_market_signals(tickers) if tickers else {}
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
            ret20 = s.get("return_20d")
            mom = _momentum_label(ret20)
            if mom.startswith("중기 상승"):
                up += 1
            elif mom.startswith("중기 약세"):
                down += 1
            lines.append(_format_signal_line(t, s, composite=port_scores.get(t)))
        lines.append("")
        lines.append(
            f"보유 요약: 과열 {overbought}개 / 과매도 {oversold}개, 중기 상승 모멘텀 {up}개 / 약세 모멘텀 {down}개"
        )
        lines.append("")

    lines.append("[섹터·자산군 ETF 모멘텀 (yfinance 벤치마크)]")
    lines.append(
        "랭킹: 동일 유니버스 횡단면 min-max 표준화 후 가중합 복합점수(100점 만점) 기준 내림차순 "
        "(20D 30%, 5D 10%, 변동성 역 15%, 낙폭 역 15%, RSI 중간 선호 15%, MA5 괴리 역 15%)."
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
