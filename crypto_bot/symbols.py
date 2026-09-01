"""
Dynamically loads active USDT trading pairs from Binance instead of a
hardcoded list. Filters out leveraged tokens (UP/DOWN/BULL/BEAR),
stablecoin-vs-stablecoin pairs, and (optionally) low-volume/illiquid coins,
then caps the result to config.MAX_SYMBOLS_TO_SCAN to keep scan cycles and
API rate-limit usage reasonable.
"""

import config

# Leveraged token suffixes Binance uses (e.g. BTCUP/USDT, ETHBULL/USDT)
LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")

# Base assets that are themselves stablecoins - a "USDC/USDT" signal doesn't
# make sense for a directional long-signal bot
STABLECOIN_BASES = {"USDC", "BUSD", "TUSD", "DAI", "FDUSD", "USDP", "EUR", "GBP"}


def _is_leveraged_token(base: str) -> bool:
    return any(base.endswith(suffix) for suffix in LEVERAGED_SUFFIXES)


def fetch_all_usdt_symbols(exchange) -> list[str]:
    """Every active spot market quoted in USDT, minus leveraged tokens and stablecoin pairs."""
    markets = exchange.load_markets()
    symbols = []
    for symbol, market in markets.items():
        if not market.get("active", True):
            continue
        if market.get("quote") != "USDT":
            continue
        if market.get("type") not in (None, "spot"):
            continue
        base = market.get("base", "")
        if _is_leveraged_token(base) or base in STABLECOIN_BASES:
            continue
        symbols.append(symbol)
    return sorted(symbols)


def filter_by_volume(exchange, symbols: list[str], min_volume_usdt: float) -> list[str]:
    """
    Fetches 24h tickers for all symbols in one batch call and keeps only
    those with quoteVolume >= min_volume_usdt. Falls back to the unfiltered
    list if the tickers call fails for any reason.
    """
    try:
        tickers = exchange.fetch_tickers(symbols)
    except Exception as e:
        print(f"[symbols] Volume filter skipped, fetch_tickers failed: {e}")
        return symbols

    liquid = []
    for symbol in symbols:
        ticker = tickers.get(symbol)
        if not ticker:
            continue
        volume = ticker.get("quoteVolume") or 0
        if volume >= min_volume_usdt:
            liquid.append((symbol, volume))

    liquid.sort(key=lambda x: x[1], reverse=True)  # highest volume first
    return [s for s, _ in liquid]


def get_symbols(exchange) -> list[str]:
    """
    Entry point used by main.py: returns the dynamic, volume-filtered USDT
    list if config.USE_ALL_USDT_PAIRS is True, otherwise the manually
    curated config.SYMBOLS list.
    """
    if not config.USE_ALL_USDT_PAIRS:
        return config.SYMBOLS

    try:
        symbols = fetch_all_usdt_symbols(exchange)
        symbols = filter_by_volume(exchange, symbols, config.MIN_24H_VOLUME_USDT)
        if config.MAX_SYMBOLS_TO_SCAN and len(symbols) > config.MAX_SYMBOLS_TO_SCAN:
            symbols = symbols[: config.MAX_SYMBOLS_TO_SCAN]
        print(f"[symbols] Scanning {len(symbols)} liquid USDT pairs from Binance")
        return symbols
    except Exception as e:
        print(f"[symbols] Failed to load dynamic symbol list ({e}), falling back to config.SYMBOLS")
        return config.SYMBOLS


if __name__ == "__main__":
    # quick manual test: python3 symbols.py
    from data_fetch import get_exchange
    ex = get_exchange()
    syms = get_symbols(ex)
    print(f"Final scan list: {len(syms)} symbols")
    print(syms[:20], "...")
