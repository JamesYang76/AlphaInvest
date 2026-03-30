"""
횡단면(cross-section) 표준화 기반 복합 점수 — Chart·벤치마크 랭킹용.

수익·변동성·낙폭·RSI·MA 괴리를 가중 합산해 100점 만점으로 환산한다.
동일 유니버스(예: 섹터 ETF 묶음) 안에서만 min-max 정규화한다.

가중치는 **약 3달(60거래일) 보유 관점**에 맞춘다.
- 60일 수익 비중을 가장 크게: 목표 보유기간과 동일한 모멘텀 축.
- 20일 수익은 보조 추세 확인: 최근 한 달의 확인 신호만 반영.
- 60일 변동성과 6개월 낙폭을 함께 반영: 3개월 보유 중 체감할 리스크와 중기 스트레스 점검.
- RSI·MA20 괴리는 과열/이격 확인용 보조 지표로 낮은 비중만 유지.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

# 3개월 보유(~60거래일) 정렬 기준 — 합 1.0
W_RET60 = 0.45
W_RET20 = 0.15
W_VOL60 = 0.15
W_DD6M = 0.15
W_RSI = 0.05
W_MA20_DIV = 0.05


def _safe_normalize(series: pd.Series) -> pd.Series:
    """0~1 min-max. 분산이 없으면 0.5로 고정."""
    mn = series.min()
    mx = series.max()
    if pd.isna(mn) or pd.isna(mx) or mx == mn:
        return pd.Series(0.5, index=series.index, dtype=float)
    return (series.astype(float) - mn) / (mx - mn)


def calculate_composite_score(df: pd.DataFrame) -> pd.Series:
    """
    컬럼: return_60d, return_20d, volatility_60d, drawdown_6m, rsi_14, ma20_divergence
    가중치(W_RET60 … W_MA20_DIV) 합 1.0, 결과는 0~100 스케일.
    """
    required = ["return_60d", "return_20d", "volatility_60d", "drawdown_6m", "rsi_14", "ma20_divergence"]
    for c in required:
        if c not in df.columns:
            raise KeyError(f"composite_score: missing column {c}")

    s_ret60 = _safe_normalize(df["return_60d"])
    s_ret20 = _safe_normalize(df["return_20d"])
    s_vol = 1.0 - _safe_normalize(df["volatility_60d"])
    s_dd = 1.0 - _safe_normalize(df["drawdown_6m"].abs())

    rsi_n = _safe_normalize(df["rsi_14"])
    s_rsi = 1.0 - ((rsi_n - 0.5).abs() * 2.0)
    s_div = 1.0 - _safe_normalize(df["ma20_divergence"].abs())

    composite = (
        s_ret60 * W_RET60
        + s_ret20 * W_RET20
        + s_vol * W_VOL60
        + s_dd * W_DD6M
        + s_rsi * W_RSI
        + s_div * W_MA20_DIV
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
                    "return_60d": float(s["return_60d"]),
                    "return_20d": float(s["return_20d"]),
                    "volatility_60d": float(s["volatility_60d"]),
                    "drawdown_6m": float(s["drawdown_6m"]),
                    "rsi_14": float(s["rsi_14"]),
                    "ma20_divergence": float(s["ma20_divergence"]),
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
