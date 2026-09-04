"""
Smart Money Concepts (SMC) / ICT-style market structure detection.

Bullish setup sequence (mirrors the user's chart, which showed the bearish
version - this implements the LONG/bullish equivalent since the bot is
long-only):

1. Price is in a downtrend (series of lower-highs / lower-lows).
2. CHOCH (Change of Character): price breaks back ABOVE the most recent
   swing high (a "lower high") - first sign the downtrend may be reversing.
3. After the CHOCH, price should form a HIGHER LOW (holding above the low
   that started the CHOCH leg) - this confirms the reversal isn't just a
   fakeout.
4. MS (Market Structure) break: price then breaks ABOVE the swing high that
   followed the CHOCH - this confirms a new uptrend has started (higher
   high after a higher low).
5. Entry zone: draw a Fibonacci retracement from the higher-low (step 3) to
   the MS breakout high (step 4). The 0.5-0.618 zone is the entry area -
   the idea being smart money re-accumulates here before continuing up.

This is inherently a "wait for structure, then wait for a pullback into a
zone" strategy - it will not fire on every candle, only when the full
sequence has actually formed.
"""

import pandas as pd
import config


def find_pivots(df: pd.DataFrame, window: int = None) -> tuple[list[dict], list[dict]]:
    """
    Returns (pivot_highs, pivot_lows), each a list of {"index": i, "price": float}
    sorted by index (time order). A pivot is a local max/min within `window`
    candles on both sides.
    """
    window = window or config.SMC_PIVOT_WINDOW
    highs, lows = df["high"].values, df["low"].values
    pivot_highs, pivot_lows = [], []

    for i in range(window, len(df) - window):
        high_segment = highs[i - window: i + window + 1]
        if highs[i] == high_segment.max():
            pivot_highs.append({"index": i, "price": float(highs[i])})

        low_segment = lows[i - window: i + window + 1]
        if lows[i] == low_segment.min():
            pivot_lows.append({"index": i, "price": float(lows[i])})

    return pivot_highs, pivot_lows


def detect_bullish_smc_setup(df: pd.DataFrame, window: int = None) -> dict | None:
    """
    Scans for the most recent complete CHOCH -> higher-low -> MS-break
    sequence and checks whether price is currently sitting in the
    resulting Fibonacci entry zone. Returns None if no complete, still-valid
    setup is found.

    Returned dict (when found):
        {
          "choch_index", "choch_price"      - the swing high that got broken (CHOCH)
          "higher_low_index", "higher_low_price"
          "ms_index", "ms_price"            - the swing high whose break confirmed MS
          "fib_zone_low", "fib_zone_high"   - the 0.5-0.618 retracement zone
          "in_entry_zone": bool             - is the CURRENT close inside that zone
          "structure_invalidated": bool     - has price broken back below the higher-low
        }
    """
    window = window or config.SMC_PIVOT_WINDOW
    pivot_highs, pivot_lows = find_pivots(df, window)

    if len(pivot_highs) < 2 or len(pivot_lows) < 2:
        return None

    # Walk backward through swing highs looking for one that price has
    # broken above AFTER a preceding downtrend leg (i.e. a CHOCH candidate),
    # then verify the higher-low + MS-break sequence that should follow it.
    last_close_idx = len(df) - 1
    last_close = float(df["close"].iloc[-1])

    # Consider swing highs as CHOCH candidates, most recent first, but must
    # leave room for a higher-low and an MS swing high afterward.
    for choch in reversed(pivot_highs[:-1]):  # exclude the very last pivot high (need one after it)
        choch_idx, choch_price = choch["index"], choch["price"]

        # Did price close above choch_price at some point after choch_idx? (the actual CHOCH break)
        after_choch = df.iloc[choch_idx + 1:]
        break_candidates = after_choch[after_choch["close"] > choch_price]
        if break_candidates.empty:
            continue
        choch_break_idx = break_candidates.index[0]

        # The "structure low" is the DEEPEST swing low that formed any time
        # before the CHOCH break confirms - this is the true bottom of the
        # down-leg being reversed, whether it formed before or after the
        # CHOCH swing high itself.
        lows_before_break = [p for p in pivot_lows if p["index"] < choch_break_idx]
        if not lows_before_break:
            continue
        pre_choch_low = min(lows_before_break, key=lambda p: p["price"])

        # Find the swing low that formed AFTER the CHOCH break (the "higher low")
        higher_lows = [p for p in pivot_lows if p["index"] > choch_break_idx]
        if not higher_lows:
            continue
        higher_low = higher_lows[0]

        # It must actually be HIGHER than the structure low - otherwise this
        # isn't a real higher low and the reversal isn't confirmed.
        if higher_low["price"] <= pre_choch_low["price"]:
            continue

        # Find the swing high that formed after the higher low (MS candidate)
        ms_candidates = [p for p in pivot_highs if p["index"] > higher_low["index"]]
        if not ms_candidates:
            continue
        ms_swing = ms_candidates[0]

        # MS break: has price closed above ms_swing's price after it formed?
        after_ms = df.iloc[ms_swing["index"] + 1:]
        ms_break_candidates = after_ms[after_ms["close"] > ms_swing["price"]]
        if ms_break_candidates.empty:
            continue  # MS not confirmed yet - structure incomplete

        ms_break_idx = ms_break_candidates.index[0]

        # ---- We have a complete setup: build the Fibonacci zone ----
        leg_low = higher_low["price"]
        leg_high = ms_swing["price"]
        leg_range = leg_high - leg_low
        if leg_range <= 0:
            continue

        fib_zone_high = leg_high - leg_range * config.SMC_FIB_ZONE_START  # e.g. 0.5
        fib_zone_low = leg_high - leg_range * config.SMC_FIB_ZONE_END    # e.g. 0.618

        structure_invalidated = last_close < higher_low["price"]
        in_entry_zone = (
            not structure_invalidated
            and fib_zone_low <= last_close <= fib_zone_high
            and last_close_idx > ms_break_idx  # only look for entries AFTER the MS break confirmed
        )

        return {
            "choch_index": choch_idx, "choch_price": choch_price,
            "higher_low_index": higher_low["index"], "higher_low_price": higher_low["price"],
            "ms_index": ms_swing["index"], "ms_price": ms_swing["price"],
            "fib_zone_low": fib_zone_low, "fib_zone_high": fib_zone_high,
            "in_entry_zone": in_entry_zone,
            "structure_invalidated": structure_invalidated,
        }

    return None
