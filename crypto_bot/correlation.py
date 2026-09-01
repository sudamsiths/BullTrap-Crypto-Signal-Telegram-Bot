"""
Correlation-aware position management. Opening 3 "different" altcoin longs
that are all 90% correlated with each other isn't real diversification -
if the shared driver (usually BTC, or a sector like L1s/memecoins) turns,
all three lose together. This checks correlation against already-open
positions before adding a new one.
"""

import pandas as pd
import config
from data_fetch import fetch_ohlcv


def get_returns_series(exchange, symbol: str, timeframe: str = "1h", limit: int = None) -> pd.Series:
    limit = limit or config.CORRELATION_LOOKBACK
    df = fetch_ohlcv(exchange, symbol, timeframe=timeframe, limit=limit)
    return df["close"].pct_change().dropna()


def correlation_between(exchange, symbol_a: str, symbol_b: str) -> float:
    """
    Pearson correlation of hourly returns between two symbols over
    config.CORRELATION_LOOKBACK candles. Returns 0.0 if it can't be computed
    (treated as "not correlated" - fails open rather than blocking trades
    on a data hiccup).
    """
    try:
        ret_a = get_returns_series(exchange, symbol_a)
        ret_b = get_returns_series(exchange, symbol_b)
        aligned = pd.concat([ret_a, ret_b], axis=1, keys=["a", "b"]).dropna()
        if len(aligned) < 10:
            return 0.0
        return float(aligned["a"].corr(aligned["b"]))
    except Exception as e:
        print(f"[correlation] Could not compute {symbol_a} vs {symbol_b}: {e}")
        return 0.0


def is_too_correlated_with_open_positions(exchange, candidate_symbol: str, open_symbols: list[str]) -> bool:
    """
    True if candidate_symbol is highly correlated (>= CORRELATION_THRESHOLD)
    with any currently open position - i.e. adding it wouldn't really
    diversify risk.
    """
    if not config.USE_CORRELATION_FILTER or not open_symbols:
        return False

    for open_symbol in open_symbols:
        if open_symbol == candidate_symbol:
            continue
        corr = correlation_between(exchange, candidate_symbol, open_symbol)
        if corr >= config.CORRELATION_THRESHOLD:
            print(f"[correlation] Skipping {candidate_symbol}: {corr:.2f} correlated with open {open_symbol}")
            return True
    return False
