"""
RSI (Relative Strength Index) - momentum oscillator used two ways here:
1. Overbought filter: skip signals where price is already "extended" (lower
   probability of further upside before a pullback).
2. Bullish divergence: price makes a lower low while RSI makes a higher low -
   a classic sign of fading downside momentum / potential reversal strength.
"""

import pandas as pd
import config


def compute_rsi(df: pd.DataFrame, period: int = None, col: str = "close") -> pd.Series:
    period = period or config.RSI_PERIOD
    delta = df[col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # avg_loss == 0: no losses in the window -> RSI is 100 (or 50 if avg_gain is also 0, i.e. flat price)
    rsi = rsi.where(avg_loss != 0, other=avg_gain.apply(lambda g: 100.0 if g > 0 else 50.0))
    return rsi.fillna(50)  # neutral value for the initial NaN row(s)


def current_rsi(df: pd.DataFrame, period: int = None) -> float:
    series = compute_rsi(df, period)
    return float(series.iloc[-1])


def is_overbought(df: pd.DataFrame, period: int = None, threshold: float = None) -> bool:
    threshold = threshold if threshold is not None else config.RSI_OVERBOUGHT_THRESHOLD
    return current_rsi(df, period) >= threshold


def has_bullish_divergence(df: pd.DataFrame, lookback: int = None) -> bool:
    """
    Splits the lookback window in half and compares the lowest close/RSI in
    each half. Bullish divergence = price's low in the second half is LOWER
    than the first half's low, but RSI's low in the second half is HIGHER.
    """
    lookback = lookback or config.RSI_DIVERGENCE_LOOKBACK
    if len(df) < lookback:
        return False

    window = df.iloc[-lookback:].copy()
    window["rsi"] = compute_rsi(window)

    half = lookback // 2
    first_half, second_half = window.iloc[:half], window.iloc[half:]

    price_low_1, price_low_2 = first_half["close"].min(), second_half["close"].min()
    rsi_low_1, rsi_low_2 = first_half["rsi"].min(), second_half["rsi"].min()

    return bool(price_low_2 < price_low_1 and rsi_low_2 > rsi_low_1)
