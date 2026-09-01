"""
Fetches OHLCV candle data from the exchange using ccxt.
"""

import ccxt
import pandas as pd
import config


def get_exchange():
    exchange_class = getattr(ccxt, config.EXCHANGE_ID)
    return exchange_class({"enableRateLimit": True})


def fetch_ohlcv(exchange, symbol: str, timeframe: str = None, limit: int = None) -> pd.DataFrame:
    """
    Returns a DataFrame with columns: timestamp, open, high, low, close, volume
    """
    timeframe = timeframe or config.TIMEFRAME
    limit = limit or config.CANDLE_LIMIT

    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


if __name__ == "__main__":
    # quick manual test: python3 data_fetch.py
    ex = get_exchange()
    for sym in config.SYMBOLS:
        try:
            df = fetch_ohlcv(ex, sym)
            print(f"{sym}: last close = {df['close'].iloc[-1]}, rows = {len(df)}")
        except Exception as e:
            print(f"{sym}: ERROR - {e}")
