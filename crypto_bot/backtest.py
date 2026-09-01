"""
Backtesting engine.

Downloads historical 5m OHLCV data, resamples it into 1h/4h for
multi-timeframe confirmation, and walks forward candle-by-candle applying
a backtest-safe version of the signal logic (EMA, volume spike, MTF, ADX,
Fibonacci targets). For each signal generated, it simulates the outcome by
looking at what price actually did afterward: did it hit TP1/TP2/TP3 or the
stop loss first?

LIMITATIONS (be aware of these when reading results):
- Open Interest history and 1m candlestick patterns are NOT included here -
  OI history isn't available far enough back for most symbols, and 1m data
  for long backtest windows is a lot of extra data to pull. Live trading
  will therefore require slightly MORE confirmations to fire than this
  backtest simulates, so live win-rate could differ from backtest results.
- No fees or slippage are modeled - real returns will be a bit lower.
- Swing-high/low detection for Fibonacci targets is the same simple
  min/max-over-lookback approach used live, not "true" pivot detection.

Run with: python3 backtest.py BTC/USDT 60
(symbol optional, defaults to BTC/USDT; days optional, defaults to 30)
"""

import sys
import time
import pandas as pd

import config
from data_fetch import get_exchange
from indicators import add_ema, volume_spike_ratio, price_above_ema
from fibonacci import fibonacci_extension_targets
from adx import compute_adx


def fetch_full_history(exchange, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
    """Paginated historical OHLCV fetch - ccxt only returns ~500-1000 candles per call."""
    tf_minutes = {"5m": 5, "1h": 60, "4h": 240}[timeframe]
    total_candles_needed = int((days * 24 * 60) / tf_minutes)
    limit = 1000

    now_ms = exchange.milliseconds()
    since = now_ms - days * 24 * 60 * 60 * 1000

    all_candles = []
    while True:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
        if not batch:
            break
        all_candles.extend(batch)
        since = batch[-1][0] + 1
        if len(batch) < limit or len(all_candles) >= total_candles_needed:
            break
        time.sleep(exchange.rateLimit / 1000)

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.drop_duplicates(subset="timestamp").reset_index(drop=True)
    return df


def resample_ohlcv(df_5m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Builds 1H/4H candles from 5m data via pandas resample."""
    df = df_5m.set_index("timestamp")
    resampled = df.resample(rule).agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
    }).dropna()
    return resampled.reset_index()


def mtf_above_ema_at(df_htf: pd.DataFrame, ts: pd.Timestamp, period: int) -> bool:
    """Was price above EMA on the higher timeframe as of the last CLOSED htf candle before ts?"""
    visible = df_htf[df_htf["timestamp"] < ts]
    if len(visible) < period + 5:
        return False
    visible = add_ema(visible.copy(), period)
    return bool(visible["close"].iloc[-1] > visible[f"ema{period}"].iloc[-1])


def simulate_trade(df_5m: pd.DataFrame, entry_idx: int, entry: float, tp1: float,
                    tp2: float, tp3: float, sl: float, max_lookahead: int = 500) -> dict:
    """
    Walks forward from entry_idx candle-by-candle to see what got hit first.
    Uses a simple 50/25/25 partial-close model matching trade_executor's split.
    """
    remaining = 1.0
    realized_pct = 0.0
    tp1_hit = tp2_hit = tp3_hit = False
    current_sl = sl

    end_idx = min(entry_idx + max_lookahead, len(df_5m))
    for i in range(entry_idx + 1, end_idx):
        candle = df_5m.iloc[i]
        low, high = candle["low"], candle["high"]

        if low <= current_sl:
            realized_pct += remaining * ((current_sl / entry) - 1)
            return {"outcome": "SL", "return_pct": realized_pct * 100,
                     "tp1_hit": tp1_hit, "tp2_hit": tp2_hit, "tp3_hit": tp3_hit}

        if not tp1_hit and high >= tp1:
            tp1_hit = True
            realized_pct += 0.5 * ((tp1 / entry) - 1)
            remaining -= 0.5
            current_sl = entry  # move to breakeven, matching trade_executor behavior

        if tp1_hit and not tp2_hit and high >= tp2:
            tp2_hit = True
            realized_pct += 0.25 * ((tp2 / entry) - 1)
            remaining -= 0.25

        if tp2_hit and not tp3_hit and high >= tp3:
            tp3_hit = True
            realized_pct += 0.25 * ((tp3 / entry) - 1)
            remaining -= 0.25
            return {"outcome": "TP3", "return_pct": realized_pct * 100,
                     "tp1_hit": tp1_hit, "tp2_hit": tp2_hit, "tp3_hit": tp3_hit}

    # ran out of lookahead candles - close remaining at last known price
    last_price = df_5m.iloc[end_idx - 1]["close"]
    realized_pct += remaining * ((last_price / entry) - 1)
    outcome = "TP1" if tp1_hit else ("OPEN_TIMEOUT" if not tp1_hit else "PARTIAL")
    return {"outcome": outcome, "return_pct": realized_pct * 100,
            "tp1_hit": tp1_hit, "tp2_hit": tp2_hit, "tp3_hit": tp3_hit}


def run_backtest(symbol: str = "BTC/USDT", days: int = 30) -> dict:
    exchange = get_exchange()

    print(f"Fetching {days} days of 5m history for {symbol}...")
    df_5m = fetch_full_history(exchange, symbol, "5m", days)
    print(f"Got {len(df_5m)} 5m candles")

    df_1h = resample_ohlcv(df_5m, "1h")
    df_4h = resample_ohlcv(df_5m, "4h")

    df_5m = add_ema(df_5m, config.EMA_PERIOD)
    df_5m["adx_1h_proxy"] = None  # placeholder, computed per-signal below for the 1h series once
    adx_1h_series = compute_adx(df_1h, config.ADX_PERIOD)
    df_1h = df_1h.assign(adx=adx_1h_series)

    trades = []
    min_lookback = config.EMA_PERIOD + config.FIB_LOOKBACK + 5

    for i in range(min_lookback, len(df_5m) - 1):
        window = df_5m.iloc[: i + 1]
        row = window.iloc[-1]
        ts = row["timestamp"]

        vol_ratio = volume_spike_ratio(window)
        above_ema = bool(row["close"] > row[f"ema{config.EMA_PERIOD}"])

        if not (vol_ratio >= config.VOLUME_SPIKE_MULTIPLIER and above_ema):
            continue

        above_1h = mtf_above_ema_at(df_1h, ts, config.MTF_EMA_PERIOD)
        above_4h = mtf_above_ema_at(df_4h, ts, config.MTF_EMA_PERIOD)

        if config.USE_ADX_FILTER:
            visible_1h = df_1h[df_1h["timestamp"] < ts]
            if visible_1h.empty or pd.isna(visible_1h["adx"].iloc[-1]) or \
                    visible_1h["adx"].iloc[-1] < config.ADX_MIN_THRESHOLD:
                continue

        confirmations = {
            "5m_volume_spike": True,
            "5m_above_ema": True,
            "1h_above_ema": above_1h,
            "4h_above_ema": above_4h,
        }
        confirmation_count = sum(confirmations.values())
        # OI + 1m pattern aren't simulated here, so scale MIN_CONFIRMATIONS
        # down proportionally to the 4 confirmations actually available.
        min_needed = max(2, round(config.MIN_CONFIRMATIONS * (4 / 6)))
        if confirmation_count < min_needed:
            continue

        entry = float(row["close"])
        fib = fibonacci_extension_targets(window, entry)
        sl = entry * (1 - config.SL_PCT)

        result = simulate_trade(df_5m, i, entry, fib["tp1"], fib["tp2"], fib["tp3"], sl)
        result.update({"symbol": symbol, "timestamp": ts, "entry": entry})
        trades.append(result)

    return summarize(trades, symbol, days)


def summarize(trades: list[dict], symbol: str, days: int) -> dict:
    if not trades:
        print("No signals generated in this window - try more days or looser settings.")
        return {"trades": [], "count": 0}

    df = pd.DataFrame(trades)
    wins = df[df["return_pct"] > 0]
    losses = df[df["return_pct"] <= 0]
    win_rate = len(wins) / len(df) * 100
    avg_return = df["return_pct"].mean()
    total_return = df["return_pct"].sum()
    max_win = df["return_pct"].max()
    max_loss = df["return_pct"].min()

    cum = df["return_pct"].cumsum()
    running_max = cum.cummax()
    drawdown = (cum - running_max).min()

    print("\n" + "=" * 50)
    print(f"BACKTEST RESULTS: {symbol} - last {days} days")
    print("=" * 50)
    print(f"Total signals:     {len(df)}")
    print(f"Win rate:          {win_rate:.1f}%  ({len(wins)} wins / {len(losses)} losses)")
    print(f"Avg return/trade:  {avg_return:+.2f}%")
    print(f"Total return sum:  {total_return:+.2f}%  (naive sum, NOT compounded)")
    print(f"Best trade:        {max_win:+.2f}%")
    print(f"Worst trade:       {max_loss:+.2f}%")
    print(f"Max drawdown:      {drawdown:.2f}% (cumulative, naive)")
    print(f"TP3 full hits:     {(df['outcome'] == 'TP3').sum()}")
    print(f"SL hits:           {(df['outcome'] == 'SL').sum()}")
    print("=" * 50)
    print("NOTE: no fees/slippage modeled. OI + 1m pattern confirmations not")
    print("simulated (live bot needs slightly more confirmation to fire).")
    print("=" * 50 + "\n")

    return {
        "trades": trades, "count": len(df), "win_rate": win_rate,
        "avg_return": avg_return, "total_return": total_return, "max_drawdown": drawdown,
    }


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT"
    n_days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    run_backtest(sym, n_days)
