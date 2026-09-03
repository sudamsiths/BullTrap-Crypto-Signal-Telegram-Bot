"""
Combines 5m indicators + multi-timeframe confirmation + open interest +
Fibonacci extension targets into a single scored signal dict, similar in
spirit to the original signal-format screenshot but backed by real
calculations instead of placeholder numbers.
"""

import pandas as pd
import config
from indicators import add_ema, volume_spike_ratio, price_above_ema
from multi_timeframe import get_mtf_confirmations, mtf_all_bullish
from open_interest import get_oi_change_pct
from fibonacci import fibonacci_extension_targets
from candlestick_patterns import detect_bullish_pattern
from data_fetch import fetch_ohlcv
from adx import current_adx
from btc_bias import bias_allows_longs
from daily_trend import get_daily_trend
from rsi import is_overbought, has_bullish_divergence
from support_resistance import has_room_to_target
from atr import current_atr
from funding_rate import funding_rate_ok


def build_signal(exchange, symbol: str, df_5m: pd.DataFrame, futures_exchange=None,
                  btc_bias: dict = None) -> dict | None:
    """
    Returns a fully-scored signal dict if enough confirmations line up,
    otherwise None. `futures_exchange` is optional - pass a futures-mode
    ccxt instance to enable open-interest confirmation; without it OI is
    simply skipped (not counted as a confirmation). `btc_bias` is the dict
    from btc_bias.get_btc_bias(), computed once per scan cycle by main.py.
    """
    # ---- Hard gate: BTC market bias ----
    if btc_bias is not None and not bias_allows_longs(btc_bias):
        return None  # BTC itself is bearish - suppress new altcoin longs

    if len(df_5m) < config.EMA_PERIOD + config.FIB_LOOKBACK:
        return None

    # ---- Hard gate: trend strength (ADX) ----
    if config.USE_ADX_FILTER:
        try:
            df_adx = fetch_ohlcv(exchange, symbol, timeframe=config.ADX_TIMEFRAME,
                                  limit=config.ADX_PERIOD * 3)
            adx_value = current_adx(df_adx)
        except Exception:
            adx_value = 0.0
        if adx_value < config.ADX_MIN_THRESHOLD:
            return None  # ranging/choppy market - don't trade this symbol right now
    else:
        adx_value = None

    # ---- Hard gate: daily trend ----
    daily_trend = get_daily_trend(exchange, symbol) if config.USE_DAILY_TREND_FILTER else {}
    if config.USE_DAILY_TREND_FILTER and config.REQUIRE_DAILY_UPTREND:
        if not daily_trend.get("above_ema_slow", False):
            return None  # price below daily EMA200 - macro downtrend, skip

    df_5m = add_ema(df_5m, config.EMA_PERIOD)

    # ---- Hard gate: RSI overbought ----
    if config.USE_RSI_OVERBOUGHT_FILTER and is_overbought(df_5m):
        return None  # already extended - lower probability of further upside

    vol_ratio_5m = volume_spike_ratio(df_5m)
    above_ema_5m = price_above_ema(df_5m, config.EMA_PERIOD)
    last_close = float(df_5m["close"].iloc[-1])

    # ---- Multi-timeframe confirmation ----
    mtf = get_mtf_confirmations(exchange, symbol)

    # ---- Open interest confirmation (futures only) ----
    oi_change_pct = None
    if futures_exchange is not None:
        oi_change_pct = get_oi_change_pct(futures_exchange, symbol)

    # ---- Hard gate: funding rate (crowded longs) ----
    if futures_exchange is not None and not funding_rate_ok(futures_exchange, symbol):
        return None  # funding too positive - longs already crowded, skip

    # ---- 1m candlestick pattern (entry timing) ----
    pattern_name = None
    try:
        df_1m = fetch_ohlcv(exchange, symbol, timeframe=config.PATTERN_TIMEFRAME,
                             limit=config.PATTERN_CANDLE_LIMIT)
        pattern_name = detect_bullish_pattern(df_1m)
    except Exception:
        pattern_name = None

    if config.REQUIRE_PATTERN_CONFIRMATION and pattern_name is None:
        return None  # hard gate: no valid 1m pattern, don't fire regardless of score

    # ---- Support/Resistance confluence ----
    sr_room = True
    if config.USE_SR_FILTER:
        try:
            df_sr = fetch_ohlcv(exchange, symbol, timeframe=config.SR_TIMEFRAME,
                                 limit=config.SR_LOOKBACK + 30)
            sr_room = has_room_to_target(df_sr, last_close)
        except Exception:
            sr_room = True  # fail open - don't block a signal on a data hiccup

    # ---- RSI bullish divergence (bonus confirmation, not a gate) ----
    rsi_divergence = has_bullish_divergence(df_5m)

    # ---- Score confirmations (max 9) ----
    confirmations = {
        "5m_volume_spike": vol_ratio_5m >= config.VOLUME_SPIKE_MULTIPLIER,
        "5m_above_ema": above_ema_5m,
        "1h_above_ema": mtf.get("1h", {}).get("above_ema", False),
        "4h_above_ema": mtf.get("4h", {}).get("above_ema", False),
        "oi_inflow": (oi_change_pct is not None and oi_change_pct >= config.OI_CHANGE_THRESHOLD_PCT),
        "1m_pattern": pattern_name is not None,
        "daily_golden_cross": daily_trend.get("golden_cross", False),
        "rsi_bullish_divergence": rsi_divergence,
        "sr_room_to_target": sr_room,
    }
    confirmation_count = sum(1 for v in confirmations.values() if v)
    score = int((confirmation_count / len(confirmations)) * 100)

    if confirmation_count < config.MIN_CONFIRMATIONS:
        return None  # not enough alignment across timeframes/OI - skip

    # ---- Targets: ATR-based (volatility-adaptive) or Fibonacci-based ----
    entry = last_close
    if config.USE_ATR_STOPS:
        atr_val = current_atr(df_5m, config.ATR_PERIOD)
        if atr_val <= 0:
            atr_val = entry * 0.01  # fallback for too-little-data cases
        sl = entry - atr_val * config.ATR_SL_MULTIPLIER
        tp1 = entry + atr_val * config.ATR_TP1_MULTIPLIER
        tp2 = entry + atr_val * config.ATR_TP2_MULTIPLIER
        tp3 = entry + atr_val * config.ATR_TP3_MULTIPLIER
        swing_low = swing_high = None
    else:
        fib = fibonacci_extension_targets(df_5m, last_close)
        sl = entry * (1 - config.SL_PCT)
        tp1, tp2, tp3 = fib["tp1"], fib["tp2"], fib["tp3"]
        swing_low, swing_high = fib["swing_low"], fib["swing_high"]

    signal = {
        "symbol": symbol,
        "entry": entry,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "sl": sl,
        "swing_low": swing_low,
        "swing_high": swing_high,
        "volume_ratio": round(vol_ratio_5m, 2),
        "above_ema20": above_ema_5m,
        "mtf": mtf,
        "oi_change_pct": oi_change_pct,
        "pattern_name": pattern_name,
        "adx": adx_value,
        "btc_bias": btc_bias.get("bias") if btc_bias else None,
        "daily_golden_cross": daily_trend.get("golden_cross"),
        "rsi_divergence": rsi_divergence,
        "sr_room_to_target": sr_room,
        "confirmations": confirmations,
        "confirmation_count": confirmation_count,
        "score": score,
    }
    return signal
