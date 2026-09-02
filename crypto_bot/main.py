"""
Main entry point. Each scan cycle:
1. Monitors any open positions - checks for TP1 hits (moves SL to breakeven)
   and SL hits (closes the paper/real position).
2. For symbols with no open position (and under MAX_OPEN_POSITIONS), scans
   for a new signal using 5m + multi-timeframe + OI confirmation.
3. Sends a Telegram alert and opens a position (real, testnet, or dry-run
   depending on config) when a signal clears the confirmation bar.

Run with: python3 main.py
"""

import asyncio
import os
import traceback

from dotenv import load_dotenv

import config
import position_tracker
from data_fetch import get_exchange, fetch_ohlcv
from signal_logic import build_signal
from telegram_bot import send_signal, send_text
from symbols import get_symbols
from btc_bias import get_btc_bias
from correlation import is_too_correlated_with_open_positions
from trade_executor import (
    get_trading_exchange, open_long_position,
    check_tp1_and_update, check_sl_hit_dry_run, move_stop_to_breakeven,
)

# Load environment variables from .env file
load_dotenv()


async def monitor_open_positions(spot_exchange, futures_exchange):
    positions = position_tracker.get_open_positions()
    for symbol, position in positions.items():
        try:
            df = fetch_ohlcv(spot_exchange, symbol, timeframe="5m", limit=5)
            current_price = float(df["close"].iloc[-1])
        except Exception as e:
            print(f"[MONITOR ERROR] {symbol}: {e}")
            continue

        # TP1 -> move SL to breakeven
        check_tp1_and_update(futures_exchange, symbol, position, current_price)

        # SL hit -> close out (DRY_RUN paper simulation only; real SL orders
        # fill on the exchange itself and you'd reconcile via order status)
        if config.DRY_RUN and check_sl_hit_dry_run(position, current_price):
            print(f"[DRY_RUN] {symbol} hit SL at {current_price} - closing paper position")
            await send_text(f"🛑 {symbol} stopped out (paper) at {current_price:.6f}")
            position_tracker.close_position(symbol)


async def scan_for_signals(spot_exchange, futures_exchange, symbols: list[str]):
    if position_tracker.open_position_count() >= config.MAX_OPEN_POSITIONS:
        print(f"[SKIP SCAN] Max open positions ({config.MAX_OPEN_POSITIONS}) reached")
        return

    btc_bias = get_btc_bias(spot_exchange) if config.USE_BTC_BIAS_FILTER else None
    if btc_bias:
        print(f"[BTC BIAS] {btc_bias['bias']} (1h_above_ema={btc_bias['1h_above_ema']}, "
              f"4h_above_ema={btc_bias['4h_above_ema']})")
        if config.BLOCK_SIGNALS_ON_BEARISH_BTC and btc_bias["bias"] == "bearish":
            print("[SKIP SCAN] BTC is bearish - suppressing new long signals this cycle")
            return

    for symbol in symbols:
        if position_tracker.has_open_position(symbol):
            continue
        try:
            df = fetch_ohlcv(spot_exchange, symbol)
            signal = build_signal(spot_exchange, symbol, df, futures_exchange=futures_exchange,
                                   btc_bias=btc_bias)
            if signal:
                open_symbols = list(position_tracker.get_open_positions().keys())
                if is_too_correlated_with_open_positions(spot_exchange, symbol, open_symbols):
                    print(f"[SKIP] {symbol}: too correlated with an already-open position")
                    continue

                print(f"[SIGNAL] {symbol} score={signal['score']} "
                      f"confirmations={signal['confirmation_count']}/9")
                await send_signal(signal)
                open_long_position(futures_exchange, symbol, signal)
            else:
                print(f"[no signal] {symbol}")
        except Exception as e:
            print(f"[ERROR] {symbol}: {e}")
            traceback.print_exc()

        if position_tracker.open_position_count() >= config.MAX_OPEN_POSITIONS:
            print(f"[STOP SCAN] Max open positions reached mid-scan")
            break


async def main_loop():
    spot_exchange = get_exchange()
    futures_exchange = get_trading_exchange()
    symbols = get_symbols(spot_exchange)  # loaded once at startup; restart the bot to pick up new listings

    mode = "DRY_RUN (paper)" if config.DRY_RUN else ("TESTNET" if config.USE_TESTNET else "LIVE - REAL MONEY")
    print(f"Bot started in {mode} mode. Watching {len(symbols)} symbols "
          f"every {config.CHECK_INTERVAL_SECONDS}s")

    if not config.DRY_RUN and not config.USE_TESTNET:
        print("=" * 60)
        print("WARNING: LIVE mode - real orders with real money will be placed.")
        print("=" * 60)

    while True:
        await monitor_open_positions(spot_exchange, futures_exchange)
        await scan_for_signals(spot_exchange, futures_exchange, symbols)
        await asyncio.sleep(config.CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    # Example usage of environment variables
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    print(f"Telegram Bot Token: {telegram_token}")

    asyncio.run(main_loop())
