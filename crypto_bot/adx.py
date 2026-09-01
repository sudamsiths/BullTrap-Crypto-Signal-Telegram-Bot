"""
ADX (Average Directional Index) - measures trend STRENGTH, not direction.
Low ADX = ranging/choppy market (signals are unreliable here).
High ADX = a real trend is underway (signals are more trustworthy).

Standard Wilder's smoothing implementation, no external TA library needed.
"""

import pandas as pd
import config


def compute_adx(df: pd.DataFrame, period: int = None) -> pd.Series:
    """
    Returns a pandas Series of ADX values aligned to df's index.
    First `period*2`-ish values will be NaN (not enough data to smooth yet).
    """
    period = period or config.ADX_PERIOD
    high, low, close = df["high"], df["low"], df["close"]

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(0.0, index=df.index)
    minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up_move > down_move) & (up_move > 0)] = up_move[(up_move > down_move) & (up_move > 0)]
    minus_dm[(down_move > up_move) & (down_move > 0)] = down_move[(down_move > up_move) & (down_move > 0)]

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx


def current_adx(df: pd.DataFrame, period: int = None) -> float:
    series = compute_adx(df, period)
    value = series.iloc[-1]
    return float(value) if pd.notna(value) else 0.0


def is_trending(df: pd.DataFrame, period: int = None, threshold: float = None) -> bool:
    threshold = threshold if threshold is not None else config.ADX_MIN_THRESHOLD
    return current_adx(df, period) >= threshold
