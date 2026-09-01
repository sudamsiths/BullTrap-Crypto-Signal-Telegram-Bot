"""
Simple candlestick pattern detection, meant to run on a lower timeframe
(1m by default) to time entries more precisely once the higher-timeframe
trend/volume/OI confirmations already agree.

All functions look at the LAST completed candle (and a few before it where
needed) in a DataFrame with columns: open, high, low, close, volume.
"""

import pandas as pd


def _body(row) -> float:
    return abs(row["close"] - row["open"])


def _range(row) -> float:
    return row["high"] - row["low"]


def _upper_wick(row) -> float:
    return row["high"] - max(row["close"], row["open"])


def _lower_wick(row) -> float:
    return min(row["close"], row["open"]) - row["low"]


def is_bullish_engulfing(df: pd.DataFrame) -> bool:
    """Current candle's body fully engulfs the previous (red) candle's body."""
    if len(df) < 2:
        return False
    prev, curr = df.iloc[-2], df.iloc[-1]
    prev_bearish = prev["close"] < prev["open"]
    curr_bullish = curr["close"] > curr["open"]
    engulfs = curr["open"] <= prev["close"] and curr["close"] >= prev["open"]
    return bool(prev_bearish and curr_bullish and engulfs)


def is_hammer(df: pd.DataFrame) -> bool:
    """Small body near the top of the range, long lower wick (>=2x body), small/no upper wick."""
    if len(df) < 1:
        return False
    row = df.iloc[-1]
    rng = _range(row)
    if rng <= 0:
        return False
    body = _body(row)
    lower = _lower_wick(row)
    upper = _upper_wick(row)
    return bool(
        body > 0
        and lower >= body * 2
        and upper <= body * 0.5
        and body / rng < 0.4
    )


def is_bullish_pin_bar(df: pd.DataFrame) -> bool:
    """Similar to hammer but with a stricter long-lower-wick requirement (rejection candle)."""
    if len(df) < 1:
        return False
    row = df.iloc[-1]
    rng = _range(row)
    if rng <= 0:
        return False
    lower = _lower_wick(row)
    return bool(lower / rng >= 0.6)


def is_three_white_soldiers(df: pd.DataFrame) -> bool:
    """Three consecutive bullish candles, each closing higher than the last, small wicks."""
    if len(df) < 3:
        return False
    last3 = df.iloc[-3:]
    all_bullish = all(last3["close"] > last3["open"])
    higher_closes = last3["close"].is_monotonic_increasing
    return bool(all_bullish and higher_closes)


def detect_bullish_pattern(df: pd.DataFrame) -> str | None:
    """
    Checks patterns in priority order and returns the name of the first
    match, or None if nothing bullish is detected on the latest candle(s).
    """
    if is_bullish_engulfing(df):
        return "Bullish Engulfing"
    if is_three_white_soldiers(df):
        return "Three White Soldiers"
    if is_hammer(df):
        return "Hammer"
    if is_bullish_pin_bar(df):
        return "Bullish Pin Bar"
    return None
