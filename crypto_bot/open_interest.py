"""
Open Interest (OI) tracking for Binance USDT-M futures.
Rising OI alongside rising price suggests new money entering (not just
short-covering), which is the "fresh inflow" concept from the original signal format.
"""

import config

_warned_symbols = set()  # avoid spamming the same warning every scan cycle


def _resolve_futures_symbol(exchange, symbol: str) -> str | None:
    """
    Binance USDT-M futures markets in ccxt's unified symbol format are
    typically 'BASE/USDT:USDT', not the spot-style 'BASE/USDT'. Passing the
    spot symbol straight to a futures-only endpoint fails silently on some
    ccxt versions. Try to find the correct market id.
    """
    try:
        markets = exchange.markets or exchange.load_markets()
    except Exception:
        return symbol  # can't check - just try the original symbol

    if symbol in markets:
        return symbol

    futures_symbol = f"{symbol}:USDT"
    if futures_symbol in markets:
        return futures_symbol

    return None  # this symbol genuinely isn't listed on futures


def get_oi_change_pct(exchange, symbol: str) -> float | None:
    """
    Returns the % change in open interest over the last
    config.OI_CHANGE_LOOKBACK snapshots, or None if unavailable
    (e.g. exchange/market doesn't support OI history, or a spot-only symbol).
    """
    resolved = _resolve_futures_symbol(exchange, symbol)
    if resolved is None:
        if symbol not in _warned_symbols:
            print(f"[open_interest] {symbol}: not listed on futures - OI unavailable (will not retry-log this symbol)")
            _warned_symbols.add(symbol)
        return None

    try:
        history = exchange.fetch_open_interest_history(
            resolved, timeframe="5m", limit=config.OI_CHANGE_LOOKBACK
        )
        if not history or len(history) < 2:
            return None
        oldest = history[0].get("openInterestAmount") or history[0].get("openInterestValue")
        newest = history[-1].get("openInterestAmount") or history[-1].get("openInterestValue")
        if not oldest:
            return None
        return round(((newest - oldest) / oldest) * 100, 2)
    except Exception as e:
        if symbol not in _warned_symbols:
            print(f"[open_interest] {symbol}: fetch failed ({type(e).__name__}: {e})")
            _warned_symbols.add(symbol)
        return None
