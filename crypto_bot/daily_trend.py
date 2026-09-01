"""
Daily-timeframe trend filter. 1H/4H confirmations catch the medium-term
trend, but a coin can still be in a macro downtrend on the daily chart -
this checks that the bigger picture agrees too.
"""

import config
from data_fetch import fetch_ohlcv
from indicators import add_ema


def get_daily_trend(exchange, symbol: str) -> dict:
    """
    Returns {"above_ema_fast": bool, "above_ema_slow": bool, "golden_cross": bool}
    based on the daily chart. golden_cross = EMA50 > EMA200 (classic bull-market signal).
    """
    result = {"above_ema_fast": False, "above_ema_slow": False, "golden_cross": False}
    try:
        df = fetch_ohlcv(exchange, symbol, timeframe="1d",
                          limit=config.DAILY_EMA_SLOW + 30)
        if len(df) < config.DAILY_EMA_SLOW + 5:
            return result  # not enough daily history yet (new listing etc.)

        df = add_ema(df, config.DAILY_EMA_FAST)
        df = add_ema(df, config.DAILY_EMA_SLOW)
        last_close = df["close"].iloc[-1]
        ema_fast = df[f"ema{config.DAILY_EMA_FAST}"].iloc[-1]
        ema_slow = df[f"ema{config.DAILY_EMA_SLOW}"].iloc[-1]

        result["above_ema_fast"] = bool(last_close > ema_fast)
        result["above_ema_slow"] = bool(last_close > ema_slow)
        result["golden_cross"] = bool(ema_fast > ema_slow)
    except Exception as e:
        print(f"[daily_trend] {symbol}: could not compute ({e})")
    return result
