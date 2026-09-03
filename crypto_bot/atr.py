"""
ATR (Average True Range) - measures how much a coin typically moves per
candle. Used to set stop-loss distance relative to each coin's own
volatility instead of a flat % that's too tight for volatile coins (PEPE,
WIF) and too loose for stable ones (BTC).
"""

import pandas as pd
import config


def compute_atr(df: pd.DataFrame, period: int = None) -> pd.Series:
    period = period or config.ATR_PERIOD
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    return atr


def current_atr(df: pd.DataFrame, period: int = None) -> float:
    series = compute_atr(df, period)
    value = series.iloc[-1]
    return float(value) if pd.notna(value) else 0.0


def atr_stop_loss(df: pd.DataFrame, entry: float, period: int = None,
                   multiplier: float = None) -> float:
    """Returns an SL price = entry - (ATR * multiplier)."""
    period = period or config.ATR_PERIOD
    multiplier = multiplier if multiplier is not None else config.ATR_SL_MULTIPLIER
    atr = current_atr(df, period)
    if atr <= 0:
        # fallback to the fixed % method if ATR can't be computed (e.g. too little data)
        return entry * (1 - config.SL_PCT)
    return entry - (atr * multiplier)
