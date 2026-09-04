"""
Backtesting engine.

Downloads historical 5m OHLCV data, resamples it into 1h/4h/1d for
multi-timeframe + daily-trend confirmation, and walks forward candle-by-candle
applying a backtest-safe version of the full signal logic (EMA, volume spike,
MTF, ADX, daily golden cross, RSI overbought gate + divergence, S/R room,
Fibonacci targets, and optionally ATR-based stops).

LIMITATIONS (be aware of these when reading results):
- Open Interest history and 1m candlestick patterns are NOT simulated - OI
  history isn't available far enough back for most symbols, and 1m data for
  long backtest windows is a lot of extra data to pull. The live bot
  therefore has 2 MORE possible confirmations (OI inflow, 1m pattern) than
  this backtest can simulate, so live win-rate could differ.
- No fees or slippage are modeled - real returns will be a bit lower.
- Funding rate / Fear-Greed filters are NOT simulated (live-only, no clean
  historical data source wired up here).
- Swing-high/low detection for Fibonacci and S/R zones uses simple
  min/max-over-lookback and pivot clustering, not "true" pivot detection.

Run with: python3 backtest.py BTC/USDT 60
(symbol optional, defaults to BTC/USDT; days optional, defaults to 30)
"""

import sys
import time
import pandas as pd

import config
from data_fetch import get_exchange
from indicators import add_ema, volume_spike_ratio
from fibonacci import fibonacci_extension_targets
from adx import compute_adx
from rsi import compute_rsi
from atr import compute_atr
from support_resistance import find_pivot_highs, cluster_into_zones


def fetch_full_history(exchange, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
    """Paginated historical OHLCV fetch - ccxt only returns ~500-1000 candles per call."""
    tf_minutes = {"5m": 5, "1h": 60, "4h": 240, "1d": 1440}[timeframe]
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
    """Builds 1H/4H/1D candles from 5m data via pandas resample."""
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


def daily_trend_at(df_1d: pd.DataFrame, ts: pd.Timestamp) -> dict:
    visible = df_1d[df_1d["timestamp"] < ts]
    if len(visible) < config.DAILY_EMA_SLOW + 5:
        return {"above_ema_slow": False, "golden_cross": False}
    visible = add_ema(visible.copy(), config.DAILY_EMA_FAST)
    visible = add_ema(visible, config.DAILY_EMA_SLOW)
    last_close = visible["close"].iloc[-1]
    ema_fast = visible[f"ema{config.DAILY_EMA_FAST}"].iloc[-1]
    ema_slow = visible[f"ema{config.DAILY_EMA_SLOW}"].iloc[-1]
    return {
        "above_ema_slow": bool(last_close > ema_slow),
        "golden_cross": bool(ema_fast > ema_slow),
    }


def sr_room_at(df_1h: pd.DataFrame, ts: pd.Timestamp, entry_price: float) -> bool:
    visible = df_1h[df_1h["timestamp"] < ts]
    if len(visible) < config.SR_LOOKBACK:
        return True  # not enough history yet - fail open
    window = visible.iloc[-config.SR_LOOKBACK:]
    pivots = find_pivot_highs(window)
    zones = cluster_into_zones(pivots)
    candidates = [z for z in zones if z["price"] > entry_price and z["touches"] >= config.SR_MIN_TOUCHES]
    if not candidates:
        return True
    nearest = min(candidates, key=lambda z: z["price"])
    distance_pct = (nearest["price"] - entry_price) / entry_price * 100
    return distance_pct >= config.SR_MIN_ROOM_PCT


def simulate_trade(df_5m: pd.DataFrame, entry_idx: int, entry: float, tp1: float,
                    tp2: float, tp3: float, sl: float, max_lookahead: int = 500) -> dict:
    """Walks forward from entry_idx candle-by-candle; 50/25/25 partial-close model."""
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
            current_sl = entry

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

    last_price = df_5m.iloc[end_idx - 1]["close"]
    realized_pct += remaining * ((last_price / entry) - 1)
    outcome = "TP1" if tp1_hit else "OPEN_TIMEOUT"
    return {"outcome": outcome, "return_pct": realized_pct * 100,
            "tp1_hit": tp1_hit, "tp2_hit": tp2_hit, "tp3_hit": tp3_hit}


def run_backtest(symbol: str = "BTC/USDT", days: int = 30) -> dict:
    exchange = get_exchange()

    print(f"Fetching {days} days of 5m history for {symbol}...")
    df_5m = fetch_full_history(exchange, symbol, "5m", days)
    print(f"Got {len(df_5m)} 5m candles")

    print(f"Fetching daily history for {symbol} (for EMA{config.DAILY_EMA_SLOW})...")
    daily_days_needed = config.DAILY_EMA_SLOW + 60 + days  # extra runway before AND through the window
    df_1d = fetch_full_history(exchange, symbol, "1d", daily_days_needed) if config.USE_DAILY_TREND_FILTER else pd.DataFrame()

    df_1h = resample_ohlcv(df_5m, "1h")
    df_4h = resample_ohlcv(df_5m, "4h")

    df_5m = add_ema(df_5m, config.EMA_PERIOD)
    adx_1h_series = compute_adx(df_1h, config.ADX_PERIOD)
    df_1h = df_1h.assign(adx=adx_1h_series)
    df_5m = df_5m.assign(rsi=compute_rsi(df_5m, config.RSI_PERIOD))
    if config.USE_ATR_STOPS:
        atr_1h_series = compute_atr(df_1h, config.ATR_PERIOD)
        df_1h = df_1h.assign(atr=atr_1h_series)

    trades = []
    min_lookback = max(config.EMA_PERIOD + config.FIB_LOOKBACK + 5, config.RSI_DIVERGENCE_LOOKBACK + 5)

    # how many of the 9 live confirmations this backtest can actually check
    SIMULATED_CONFIRMATIONS = 7  # 5m_vol, 5m_ema, 1h_ema, 4h_ema, daily_golden_cross, rsi_divergence, sr_room
    min_needed = max(2, round(config.MIN_CONFIRMATIONS * (SIMULATED_CONFIRMATIONS / 9)))

    for i in range(min_lookback, len(df_5m) - 1):
        window = df_5m.iloc[: i + 1]
        row = window.iloc[-1]
        ts = row["timestamp"]

        vol_ratio = volume_spike_ratio(window)
        above_ema = bool(row["close"] > row[f"ema{config.EMA_PERIOD}"])
        if not (vol_ratio >= config.VOLUME_SPIKE_MULTIPLIER and above_ema):
            continue

        # ---- Hard gate: ADX (1h trend strength) ----
        if config.USE_ADX_FILTER:
            visible_1h = df_1h[df_1h["timestamp"] < ts]
            if visible_1h.empty or pd.isna(visible_1h["adx"].iloc[-1]) or \
                    visible_1h["adx"].iloc[-1] < config.ADX_MIN_THRESHOLD:
                continue

        # ---- Hard gate: daily uptrend ----
        daily = daily_trend_at(df_1d, ts) if config.USE_DAILY_TREND_FILTER else {"above_ema_slow": True, "golden_cross": False}
        if config.USE_DAILY_TREND_FILTER and config.REQUIRE_DAILY_UPTREND:
            if not daily["above_ema_slow"]:
                continue

        # ---- Hard gate: RSI overbought ----
        current_rsi_val = row["rsi"]
        if config.USE_RSI_OVERBOUGHT_FILTER and current_rsi_val >= config.RSI_OVERBOUGHT_THRESHOLD:
            continue

        entry = float(row["close"])

        # ---- Confirmations ----
        above_1h = mtf_above_ema_at(df_1h, ts, config.MTF_EMA_PERIOD)
        above_4h = mtf_above_ema_at(df_4h, ts, config.MTF_EMA_PERIOD)
        rsi_window = window.iloc[-config.RSI_DIVERGENCE_LOOKBACK:] if len(window) >= config.RSI_DIVERGENCE_LOOKBACK else window
        half = len(rsi_window) // 2
        rsi_divergence = False
        if half > 3:
            first_half, second_half = rsi_window.iloc[:half], rsi_window.iloc[half:]
            price_low_1, price_low_2 = first_half["close"].min(), second_half["close"].min()
            rsi_low_1, rsi_low_2 = first_half["rsi"].min(), second_half["rsi"].min()
            rsi_divergence = bool(price_low_2 < price_low_1 and rsi_low_2 > rsi_low_1)
        sr_room = sr_room_at(df_1h, ts, entry) if config.USE_SR_FILTER else True

        confirmation_count = sum([
            True, True,  # 5m vol + ema already required to reach here
            above_1h, above_4h, daily["golden_cross"], rsi_divergence, sr_room,
        ])
        if confirmation_count < min_needed:
            continue

        # ---- Targets: ATR-based or Fibonacci-based ----
        if config.USE_ATR_STOPS:
            visible_1h = df_1h[df_1h["timestamp"] < ts]
            atr_val = visible_1h["atr"].iloc[-1] if not visible_1h.empty and not pd.isna(visible_1h["atr"].iloc[-1]) else entry * 0.01
            sl = entry - atr_val * config.ATR_SL_MULTIPLIER
            tp1 = entry + atr_val * config.ATR_TP1_MULTIPLIER
            tp2 = entry + atr_val * config.ATR_TP2_MULTIPLIER
            tp3 = entry + atr_val * config.ATR_TP3_MULTIPLIER
        else:
            fib = fibonacci_extension_targets(window, entry)
            sl = entry * (1 - config.SL_PCT)
            tp1, tp2, tp3 = fib["tp1"], fib["tp2"], fib["tp3"]

        result = simulate_trade(df_5m, i, entry, tp1, tp2, tp3, sl)
        result.update({"symbol": symbol, "timestamp": ts, "entry": entry})
        trades.append(result)

    return summarize(trades, symbol, days)


def summarize(trades: list[dict], symbol: str, days: int, strategy_label: str = None) -> dict:
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

    stops_label = strategy_label or ("ATR-based" if config.USE_ATR_STOPS else "Fibonacci-based")
    print("\n" + "=" * 50)
    print(f"BACKTEST RESULTS: {symbol} - last {days} days ({stops_label} stops)")
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
    print("NOTE: no fees/slippage modeled. OI, 1m pattern, funding rate, and")
    print("Fear/Greed filters are NOT simulated (live bot needs slightly more")
    print("confirmation to fire / has extra gates this doesn't test).")
    print("=" * 50 + "\n")

    return {
        "trades": trades, "count": len(df), "win_rate": win_rate,
        "avg_return": avg_return, "total_return": total_return, "max_drawdown": drawdown,
    }


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT"
    n_days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    run_backtest(sym, n_days)