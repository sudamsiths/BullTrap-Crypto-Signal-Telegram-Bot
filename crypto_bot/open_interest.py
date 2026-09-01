"""
Open Interest (OI) tracking for Binance USDT-M futures.
Rising OI alongside rising price suggests new money entering (not just
short-covering), which is the "fresh inflow" concept from the original signal format.
"""

import config


def get_oi_change_pct(exchange, symbol: str) -> float | None:
    """
    Returns the % change in open interest over the last
    config.OI_CHANGE_LOOKBACK snapshots, or None if unavailable
    (e.g. exchange/market doesn't support OI history, or a spot-only symbol).
    """
    try:
        # ccxt uses the futures-style symbol here (same "BASE/QUOTE" works
        # once the exchange instance is configured for defaultType=future)
        history = exchange.fetch_open_interest_history(
            symbol, timeframe="5m", limit=config.OI_CHANGE_LOOKBACK
        )
        if not history or len(history) < 2:
            return None
        oldest = history[0].get("openInterestAmount") or history[0].get("openInterestValue")
        newest = history[-1].get("openInterestAmount") or history[-1].get("openInterestValue")
        if not oldest:
            return None
        return round(((newest - oldest) / oldest) * 100, 2)
    except Exception:
        # Not all symbols / exchange configs support this endpoint - treat as unknown
        return None
