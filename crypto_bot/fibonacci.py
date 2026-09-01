"""
Fibonacci extension levels calculated from the most recent swing low -> swing high
move on the 5m chart. This replaces the earlier "flat % target" placeholders
with levels derived from actual recent price structure.
"""

import pandas as pd
import config


def find_swing_low_high(df: pd.DataFrame, lookback: int = None) -> tuple[float, float]:
    """
    Very simple swing detection: lowest low and highest high within the
    lookback window. Good enough for a retail-style extension target;
    swap in a proper pivot-detection algorithm later if you want more precision.
    """
    lookback = lookback or config.FIB_LOOKBACK
    window = df.iloc[-lookback:]
    swing_low = float(window["low"].min())
    swing_high = float(window["high"].max())
    return swing_low, swing_high


def fibonacci_extension_targets(df: pd.DataFrame, entry: float) -> dict:
    """
    Projects extension targets above the current swing high, using the
    swing_low -> swing_high leg as the base measured move.
    """
    swing_low, swing_high = find_swing_low_high(df)
    leg = swing_high - swing_low

    if leg <= 0:
        # degenerate case (flat range) - fall back to a tiny leg based on entry
        leg = entry * 0.01

    tp1 = swing_high + leg * config.FIB_TP1_RATIO
    tp2 = swing_high + leg * config.FIB_TP2_RATIO
    tp3 = swing_high + leg * config.FIB_TP3_RATIO

    # Fibonacci targets should still make sense relative to entry - if the
    # swing high is far below entry (stale data), don't emit inverted targets.
    tp1 = max(tp1, entry * 1.01)
    tp2 = max(tp2, entry * 1.02)
    tp3 = max(tp3, entry * 1.03)

    return {
        "swing_low": swing_low,
        "swing_high": swing_high,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
    }
