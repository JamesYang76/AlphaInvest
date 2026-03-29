"""
횡단면(cross-section) 표준화 기반 복합 점수 — Chart·벤치마크 랭킹용.

수익·변동성·낙폭·RSI·MA 괴리를 가중 합산해 100점 만점으로 환산한다.
동일 유니버스(예: 섹터 ETF 묶음) 안에서만 min-max 정규화한다.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def _safe_normalize(series: pd.Series) -> pd.Series:
    """0~1 min-max. 분산이 없으면 0.5로 고정."""
    mn = series.min()
    mx = series.max()
    if pd.isna(mn) or pd.isna(mx) or mx == mn:
        return pd.Series(0.5, index=series.index, dtype=float)
    return (series.astype(float) - mn) / (mx - mn)


def calculate_composite_score(df: pd.DataFrame) -> pd.Series:
    """
    컬럼: return_20d, return_5d, volatility_20d, drawdown_3m, rsi_14, ma5_divergence
    가중치 합 1.0, 결과는 0~100 스케일.
    """
    required = ["return_20d", "return_5d", "volatility_20d", "drawdown_3m", "rsi_14", "ma5_divergence"]
    for c in required:
        if c not in df.columns:
            raise KeyError(f"composite_score: missing column {c}")

    s_ret20 = _safe_normalize(df["return_20d"])
    s_ret5 = _safe_normalize(df["return_5d"])
    s_vol = 1.0 - _safe_normalize(df["volatility_20d"])
    s_dd = 1.0 - _safe_normalize(df["drawdown_3m"].abs())

    rsi_n = _safe_normalize(df["rsi_14"])
    s_rsi = 1.0 - ((rsi_n - 0.5).abs() * 2.0)
    s_div = 1.0 - _safe_normalize(df["ma5_divergence"].abs())

    composite = (
        s_ret20 * 0.30
        + s_ret5 * 0.10
        + s_vol * 0.15
        + s_dd * 0.15
        + s_rsi * 0.15
        + s_div * 0.15
    ) * 100.0
    return composite


def compute_composite_scores_for_signals(signals: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """
    ticker -> signal 딕셔너리에서 error 없는 행만 모아 유니버스 단위 복합 점수를 계산한다.
    행이 1개뿐이면 표준화가 불가하므로 50.0을 부여한다.
    """
    rows: list[dict[str, Any]] = []
    for ticker, s in signals.items():
        if s.get("error"):
            continue
        try:
            rows.append(
                {
                    "ticker": ticker,
                    "return_20d": float(s["return_20d"]),
                    "return_5d": float(s["return_5d"]),
                    "volatility_20d": float(s["volatility_20d"]),
                    "drawdown_3m": float(s["drawdown_3m"]),
                    "rsi_14": float(s["rsi_14"]),
                    "ma5_divergence": float(s["ma5_divergence"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue

    if not rows:
        return {}

    df = pd.DataFrame(rows)
    if len(df) == 1:
        t = str(df["ticker"].iloc[0])
        return {t: 50.0}

    df = df.set_index("ticker")
    scores = calculate_composite_score(df)
    out: Dict[str, float] = {}
    for t in scores.index:
        out[str(t)] = round(float(scores.loc[t]), 2)
    return out
