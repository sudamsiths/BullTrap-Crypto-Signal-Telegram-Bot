"""
Multi-timeframe confirmation.
A 5m signal is much more reliable if higher timeframes agree on direction.
This checks price vs EMA on each configured higher timeframe.
"""

import config
from data_fetch import fetch_ohlcv
from indicators import add_ema, price_above_ema, volume_spike_ratio


def get_mtf_confirmations(exchange, symbol: str) -> dict:
    """
    Returns a dict like:
    {
        "1h": {"above_ema": True, "volume_spike": 3.4},
        "4h": {"above_ema": True, "volume_spike": 4.0},
    }
    Any fetch failure for a timeframe is reported as not-confirmed rather than
    crashing the whole scan.
    """
    results = {}
    for tf in config.CONFIRM_TIMEFRAMES:
        try:
            df = fetch_ohlcv(exchange, symbol, timeframe=tf, limit=config.MTF_EMA_PERIOD + 30)
            df = add_ema(df, config.MTF_EMA_PERIOD)
            results[tf] = {
                "above_ema": price_above_ema(df, config.MTF_EMA_PERIOD),
                "volume_spike": round(volume_spike_ratio(df), 2),
            }
        except Exception as e:
            results[tf] = {"above_ema": False, "volume_spike": 0.0, "error": str(e)}
    return results


def mtf_all_bullish(mtf_results: dict) -> bool:
    """True only if every configured higher timeframe is above its EMA."""
    return all(v.get("above_ema") for v in mtf_results.values())
