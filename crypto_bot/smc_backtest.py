"""
Standalone backtest for the SMC (CHOCH -> higher-low -> MS break -> Fib
zone) strategy, tested IN ISOLATION from the bot's other 9 confirmations -
this answers "does this specific strategy make money on its own?" cleanly,
without other filters muddying the result.

Entry:  price closes inside the 0.5-0.618 Fibonacci retracement zone of the
        (higher-low -> MS-break-high) leg, with structure still valid.
Stop:   just below the higher-low (the structure would be invalidated below it).
Targets: Fibonacci extensions of the (higher-low -> MS-high) leg projected
        upward from the MS high - 0.272, 0.618, and 1.0 (measured move).

Run with: python3 smc_backtest.py BTC/USDT 60
"""

import sys
import pandas as pd

import config
from data_fetch import get_exchange
from backtest import fetch_full_history, simulate_trade, summarize
from smc_structure import detect_bullish_smc_setup


def run_smc_backtest(symbol: str = "BTC/USDT", days: int = 60, timeframe: str = "1h") -> dict:
    exchange = get_exchange()
    print(f"Fetching {days} days of {timeframe} history for {symbol}...")
    df = fetch_full_history(exchange, symbol, timeframe, days)
    print(f"Got {len(df)} {timeframe} candles")

    trades = []
    min_lookback = config.SMC_PIVOT_WINDOW * 6  # need enough candles for a few pivots to have formed
    last_ms_index_traded = None  # avoid re-triggering the same setup on every subsequent candle

    for i in range(min_lookback, len(df) - 1):
        window = df.iloc[: i + 1].reset_index(drop=True)
        setup = detect_bullish_smc_setup(window)

        if not setup or not setup["in_entry_zone"] or setup["structure_invalidated"]:
            continue

        if setup["ms_index"] == last_ms_index_traded:
            continue  # already took this exact setup
        last_ms_index_traded = setup["ms_index"]

        entry = float(window["close"].iloc[-1])
        higher_low_price = setup["higher_low_price"]
        ms_price = setup["ms_price"]
        leg_range = ms_price - higher_low_price

        sl = higher_low_price * 0.995  # small buffer below the structure low
        tp1 = ms_price + leg_range * 0.272
        tp2 = ms_price + leg_range * 0.618
        tp3 = ms_price + leg_range * 1.0  # measured move

        result = simulate_trade(df, i, entry, tp1, tp2, tp3, sl, max_lookahead=200)
        result.update({"symbol": symbol, "timestamp": window["timestamp"].iloc[-1], "entry": entry})
        trades.append(result)

    return summarize(trades, symbol, days, strategy_label="SMC CHOCH+MS+Fib")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT"
    n_days = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    tf = sys.argv[3] if len(sys.argv) > 3 else "1h"
    run_smc_backtest(sym, n_days, tf)