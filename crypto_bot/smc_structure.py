"""
SMC Strategy Module
Strategy Logic:
1. Uptrend Reversal via CHoCH (Change of Character)
2. Confirmation of Market Structure Shift (BOS/MS)
3. Entry at Fibonacci 0.5 Premium Zone
"""

import pandas as pd
import numpy as np


def detect_pivots(df: pd.DataFrame, window: int = 2) -> pd.DataFrame:
    """Swing Highs සහ Swing Lows (Pivot Points) හඳුනාගැනීම"""
    df['is_pivot_high'] = True
    df['is_pivot_low'] = True

    for i in range(1, window + 1):
        df['is_pivot_high'] &= (df['high'] > df['high'].shift(i)) & (df['high'] > df['high'].shift(-i))
        df['is_pivot_low'] &= (df['low'] < df['low'].shift(i)) & (df['low'] < df['low'].shift(-i))

    return df


def calculate_smc_signal(df: pd.DataFrame) -> dict | None:
    """
    SMC Bearish CHoCH + Fib 0.5 Strategy Indicator
    """
    if len(df) < 50:
        return None

    df = detect_pivots(df.copy(), window=2)

    # Pivot Highs & Lows වෙන් කර ගැනීම
    pivot_highs = df[df['is_pivot_high']]
    pivot_lows = df[df['is_pivot_low']]

    if len(pivot_highs) < 2 or len(pivot_lows) < 2:
        return None

    # Swing Price Levels
    last_swing_high = pivot_highs['high'].iloc[-1]
    last_swing_low = pivot_lows['low'].iloc[-1]
    prev_swing_low = pivot_lows['low'].iloc[-2]

    current_price = float(df['close'].iloc[-1])
    current_candle_body_close = float(df['close'].iloc[-1])

    # 1. CHoCH Condition (Candle Body Close below previous Swing Low)
    is_choch_valid = current_candle_body_close < prev_swing_low

    if is_choch_valid:
        # 2. Fibonacci 0.5 (50% Retracement) Level Calculation
        fib_05_zone = last_swing_high - ((last_swing_high - last_swing_low) * 0.5)

        # 3. Entry Condition: Price එක Retrace වී 0.5 Zone එකට පැමිණ තිබේද බලන්න
        if current_price >= fib_05_zone and current_price < last_swing_high:
            # Risk Management
            stop_loss = last_swing_high * 1.0025  # High එකට 0.25% කින් උඩින් SL
            risk = stop_loss - current_price

            if risk <= 0:
                return None

            tp1 = current_price - (risk * 1.5)  # 1:1.5 RR
            tp2 = current_price - (risk * 2.5)  # 1:2.5 RR

            return {
                "symbol": "",
                "signal_type": "SHORT",
                "strategy": "SMC CHoCH + Fib 0.5",
                "price": current_price,
                "stop_loss": stop_loss,
                "take_profit_1": tp1,
                "take_profit_2": tp2,
                "fib_05": fib_05_zone,
                "score": 85
            }

    return None