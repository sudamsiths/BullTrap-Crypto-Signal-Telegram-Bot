"""
Simple indicator calculations (no external TA library needed).
"""

import pandas as pd


def add_ema(df: pd.DataFrame, period: int, col: str = "close") -> pd.DataFrame:
    df[f"ema{period}"] = df[col].ewm(span=period, adjust=False).mean()
    return df


def volume_spike_ratio(df: pd.DataFrame, lookback: int = 20) -> float:
    """
    Returns how many times the latest volume is above the average
    of the previous `lookback` candles (excluding the latest one).
    """
    if len(df) < lookback + 1:
        return 0.0
    recent_avg = df["volume"].iloc[-(lookback + 1):-1].mean()
    latest_vol = df["volume"].iloc[-1]
    if recent_avg == 0:
        return 0.0
    return latest_vol / recent_avg


def price_above_ema(df: pd.DataFrame, period: int) -> bool:
    ema_col = f"ema{period}"
    if ema_col not in df.columns:
        df = add_ema(df, period)
    return bool(df["close"].iloc[-1] > df[ema_col].iloc[-1])
