"""
Detects resistance zones from historical swing highs (local pivots), then
checks whether an entry price has "room to run" before hitting the nearest
one - a breakout right underneath strong overhead resistance is a much
lower-probability trade than one with clear air above it.
"""

import pandas as pd
import config


def find_pivot_highs(df: pd.DataFrame, window: int = None) -> list[float]:
    """
    A candle is a pivot high if its high is the max within `window` candles
    on both sides. Simple and effective for retail-style S/R levels.
    """
    window = window or config.SR_PIVOT_WINDOW
    highs = df["high"].values
    pivots = []
    for i in range(window, len(highs) - window):
        segment = highs[i - window: i + window + 1]
        if highs[i] == segment.max():
            pivots.append(float(highs[i]))
    return pivots


def cluster_into_zones(pivots: list[float], cluster_pct: float = None) -> list[dict]:
    """
    Groups nearby pivot prices into zones (within cluster_pct % of each
    other) and counts touches - more touches = stronger resistance.
    """
    cluster_pct = cluster_pct if cluster_pct is not None else config.SR_CLUSTER_PCT
    if not pivots:
        return []

    pivots = sorted(pivots)
    zones = []
    current_zone = [pivots[0]]

    for price in pivots[1:]:
        if (price - current_zone[-1]) / current_zone[-1] * 100 <= cluster_pct:
            current_zone.append(price)
        else:
            zones.append({"price": sum(current_zone) / len(current_zone), "touches": len(current_zone)})
            current_zone = [price]
    zones.append({"price": sum(current_zone) / len(current_zone), "touches": len(current_zone)})
    return zones


def nearest_resistance_above(df: pd.DataFrame, entry_price: float) -> dict | None:
    """
    Returns the nearest qualifying (>= SR_MIN_TOUCHES) resistance zone above
    entry_price within the lookback window, or None if there isn't one
    (e.g. price is already at/near a fresh all-time-high on this window).
    """
    window = df.iloc[-config.SR_LOOKBACK:] if len(df) > config.SR_LOOKBACK else df
    pivots = find_pivot_highs(window)
    zones = cluster_into_zones(pivots)

    candidates = [z for z in zones if z["price"] > entry_price and z["touches"] >= config.SR_MIN_TOUCHES]
    if not candidates:
        return None
    return min(candidates, key=lambda z: z["price"])


def has_room_to_target(df: pd.DataFrame, entry_price: float, min_room_pct: float = None) -> bool:
    """
    True if there's no significant resistance zone within min_room_pct% above
    entry, OR there simply isn't a qualifying resistance zone nearby at all.
    """
    min_room_pct = min_room_pct if min_room_pct is not None else config.SR_MIN_ROOM_PCT
    resistance = nearest_resistance_above(df, entry_price)
    if resistance is None:
        return True  # no overhead resistance detected - clear air
    distance_pct = (resistance["price"] - entry_price) / entry_price * 100
    return distance_pct >= min_room_pct
