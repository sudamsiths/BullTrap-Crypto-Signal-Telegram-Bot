"""
BTC market bias - altcoins usually follow BTC's overall direction. A long
signal on an altcoin while BTC itself is trending down is a much lower
quality setup, so we compute BTC's bias once per scan cycle and use it to
gate (or just annotate) other signals.
"""

import config
from data_fetch import fetch_ohlcv
from indicators import add_ema, price_above_ema


def get_btc_bias(exchange) -> dict:
    """
    Returns {"bias": "bullish"|"bearish"|"neutral", "1h_above_ema": bool, "4h_above_ema": bool}
    based on BTC/USDT price vs EMA20 on 1H and 4H.
    """
    result = {"bias": "neutral", "1h_above_ema": None, "4h_above_ema": None}
    try:
        df_1h = fetch_ohlcv(exchange, "BTC/USDT", timeframe="1h", limit=config.MTF_EMA_PERIOD + 30)
        df_4h = fetch_ohlcv(exchange, "BTC/USDT", timeframe="4h", limit=config.MTF_EMA_PERIOD + 30)
        above_1h = price_above_ema(add_ema(df_1h, config.MTF_EMA_PERIOD), config.MTF_EMA_PERIOD)
        above_4h = price_above_ema(add_ema(df_4h, config.MTF_EMA_PERIOD), config.MTF_EMA_PERIOD)

        result["1h_above_ema"] = above_1h
        result["4h_above_ema"] = above_4h

        if above_1h and above_4h:
            result["bias"] = "bullish"
        elif not above_1h and not above_4h:
            result["bias"] = "bearish"
        else:
            result["bias"] = "neutral"
    except Exception as e:
        print(f"[btc_bias] Could not determine BTC bias ({e}), defaulting to neutral")

    return result


def bias_allows_longs(btc_bias: dict) -> bool:
    """
    Used as a gate: when config.BLOCK_SIGNALS_ON_BEARISH_BTC is True, no new
    long signals fire while BTC itself is bearish on both 1H and 4H.
    """
    if not config.USE_BTC_BIAS_FILTER:
        return True
    if not config.BLOCK_SIGNALS_ON_BEARISH_BTC:
        return True
    return btc_bias.get("bias") != "bearish"
