"""
Funding rate check (Binance USDT-M futures). Persistently high positive
funding means longs are paying shorts a lot to stay open - a sign the long
side is crowded, which raises the odds of a long-squeeze/reversal.
"""

import config
from open_interest import _resolve_futures_symbol

_warned_symbols = set()


def get_funding_rate_pct(exchange, symbol: str) -> float | None:
    """
    Returns the current funding rate as a percentage (e.g. 0.03 = 0.03%),
    or None if it can't be fetched (spot-only symbol, API error, etc.).
    """
    resolved = _resolve_futures_symbol(exchange, symbol)
    if resolved is None:
        return None  # not on futures - open_interest.py already logs this once

    try:
        funding = exchange.fetch_funding_rate(resolved)
        rate = funding.get("fundingRate")
        if rate is None:
            return None
        return float(rate) * 100
    except Exception as e:
        if symbol not in _warned_symbols:
            print(f"[funding_rate] {symbol}: fetch failed ({type(e).__name__}: {e})")
            _warned_symbols.add(symbol)
        return None


def funding_rate_ok(exchange, symbol: str) -> bool:
    """
    True if funding is missing/unavailable (fail-open) or within an
    acceptable range. False if it's crowded-positive above the configured
    threshold - a signal for "everyone is already long this."
    """
    if not config.USE_FUNDING_RATE_FILTER:
        return True
    rate = get_funding_rate_pct(exchange, symbol)
    if rate is None:
        return True
    return rate < config.FUNDING_RATE_MAX_THRESHOLD
