"""
Combines 5m indicators + multi-timeframe confirmation + open interest +
Fibonacci extension targets into a single scored signal dict, similar in
spirit to the original signal-format screenshot but backed by real
calculations instead of placeholder numbers.
"""

import pandas as pd
import config
from indicators import add_ema, volume_spike_ratio, price_above_ema
from multi_timeframe import get_mtf_confirmations, mtf_all_bullish
from open_interest import get_oi_change_pct
from fibonacci import fibonacci_extension_targets


def build_signal(exchange, symbol: str, df_5m: pd.DataFrame, futures_exchange=None) -> dict | None:
    """
    Returns a fully-scored signal dict if enough confirmations line up,
    otherwise None. `futures_exchange` is optional - pass a futures-mode
    ccxt instance to enable open-interest confirmation; without it OI is
    simply skipped (not counted as a confirmation).
    """
    if len(df_5m) < config.EMA_PERIOD + config.FIB_LOOKBACK:
        return None

    df_5m = add_ema(df_5m, config.EMA_PERIOD)

    vol_ratio_5m = volume_spike_ratio(df_5m)
    above_ema_5m = price_above_ema(df_5m, config.EMA_PERIOD)
    last_close = float(df_5m["close"].iloc[-1])

    # ---- Multi-timeframe confirmation ----
    mtf = get_mtf_confirmations(exchange, symbol)

    # ---- Open interest confirmation (futures only) ----
    oi_change_pct = None
    if futures_exchange is not None:
        oi_change_pct = get_oi_change_pct(futures_exchange, symbol)

    # ---- Score confirmations (max 5) ----
    confirmations = {
        "5m_volume_spike": vol_ratio_5m >= config.VOLUME_SPIKE_MULTIPLIER,
        "5m_above_ema": above_ema_5m,
        "1h_above_ema": mtf.get("1h", {}).get("above_ema", False),
        "4h_above_ema": mtf.get("4h", {}).get("above_ema", False),
        "oi_inflow": (oi_change_pct is not None and oi_change_pct >= config.OI_CHANGE_THRESHOLD_PCT),
    }
    confirmation_count = sum(1 for v in confirmations.values() if v)
    score = int((confirmation_count / len(confirmations)) * 100)

    if confirmation_count < config.MIN_CONFIRMATIONS:
        return None  # not enough alignment across timeframes/OI - skip

    # ---- Fibonacci-based targets ----
    fib = fibonacci_extension_targets(df_5m, last_close)
    entry = last_close
    sl = entry * (1 - config.SL_PCT)

    signal = {
        "symbol": symbol,
        "entry": entry,
        "tp1": fib["tp1"],
        "tp2": fib["tp2"],
        "tp3": fib["tp3"],
        "sl": sl,
        "swing_low": fib["swing_low"],
        "swing_high": fib["swing_high"],
        "volume_ratio": round(vol_ratio_5m, 2),
        "above_ema20": above_ema_5m,
        "mtf": mtf,
        "oi_change_pct": oi_change_pct,
        "confirmations": confirmations,
        "confirmation_count": confirmation_count,
        "score": score,
    }
    return signal
