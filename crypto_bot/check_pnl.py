"""
Quick PNL/status check - run this any time to see:
1. Currently OPEN paper positions with live unrealized PNL
2. CLOSED trades with realized PNL (win rate, avg return, totals)

Run with: python3 check_pnl.py
"""

import config
import position_tracker
import performance_tracker
from data_fetch import get_exchange, fetch_ohlcv


def show_open_positions():
    positions = position_tracker.get_open_positions()
    exchange = get_exchange()

    print("\n" + "=" * 55)
    print(f"OPEN POSITIONS ({len(positions)})")
    print("=" * 55)

    if not positions:
        print("No open positions right now.")
        return

    for symbol, pos in positions.items():
        try:
            df = fetch_ohlcv(exchange, symbol, timeframe="5m", limit=2)
            current_price = float(df["close"].iloc[-1])
            unrealized_pct = (current_price / pos["entry"] - 1) * 100
            tp1_status = "✅ HIT (SL moved to BE)" if pos.get("tp1_hit") else "not yet"

            print(f"\n{symbol}")
            print(f"  Entry:      {pos['entry']:.6f}")
            print(f"  Current:    {current_price:.6f}")
            print(f"  Unrealized: {unrealized_pct:+.2f}%")
            print(f"  SL:         {pos['sl']:.6f}")
            print(f"  TP1:        {pos['tp1']:.6f}  ({tp1_status})")
            print(f"  TP2 / TP3:  {pos['tp2']:.6f} / {pos['tp3']:.6f}")
            print(f"  Mode:       {pos.get('mode', 'unknown')}")
        except Exception as e:
            print(f"\n{symbol}: could not fetch current price ({e})")


def show_closed_performance():
    print("\n" + "=" * 55)
    print("CLOSED TRADES - ALL TIME")
    print("=" * 55)
    stats = performance_tracker.summarize_performance()
    _print_stats(stats)

    print("\n" + "=" * 55)
    print("CLOSED TRADES - LAST 7 DAYS")
    print("=" * 55)
    stats_7d = performance_tracker.summarize_performance(days=7)
    _print_stats(stats_7d)


def _print_stats(stats: dict):
    if stats["count"] == 0:
        print("No closed trades yet - positions still open, or none have hit SL/TP3.")
        return
    print(f"Trades closed:     {stats['count']}")
    print(f"Win rate:          {stats['win_rate']:.1f}%  ({stats['wins']}W / {stats['losses']}L)")
    print(f"Avg return/trade:  {stats['avg_return']:+.2f}%")
    print(f"Total return sum:  {stats['total_return']:+.2f}%  (naive sum, NOT compounded)")
    print(f"Best trade:        {stats['best']:+.2f}%")
    print(f"Worst trade:       {stats['worst']:+.2f}%")


if __name__ == "__main__":
    show_open_positions()
    show_closed_performance()
    print("\n" + "=" * 55)
    print("NOTE: PNL only appears under 'CLOSED TRADES' once a position")
    print("hits its SL or TP3 - the bot checks this every scan cycle")
    print("(every CHECK_INTERVAL_SECONDS) while main.py is running.")
    print("If main.py isn't running continuously, open positions won't")
    print("close and PNL won't be recorded even if price moves past them.")
    print("=" * 55 + "\n")
