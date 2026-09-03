"""
Bot configuration.
Fill these in before running.
"""

import os

# ---- Telegram settings ----
# Get this from @BotFather on Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# The chat/group/channel ID where signals will be sent
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---- Exchange / market settings ----
EXCHANGE_ID = "binance"          # ccxt exchange id
SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "TRX/USDT", "MATIC/USDT", "TON/USDT", "SHIB/USDT", "LTC/USDT",
    "BCH/USDT", "NEAR/USDT", "UNI/USDT", "APT/USDT", "ARB/USDT",
    "OP/USDT", "SUI/USDT", "INJ/USDT", "SEI/USDT", "TIA/USDT",
    "PEPE/USDT", "WIF/USDT", "FLOKI/USDT", "BONK/USDT", "BERA/USDT",
]  # only used when USE_ALL_USDT_PAIRS = False

# ---- Scan universe ----
# True: ignore the SYMBOLS list above and auto-fetch every liquid USDT pair
# from Binance at startup instead. Much less maintenance, but scan cycles
# take longer - tune MIN_24H_VOLUME_USDT / MAX_SYMBOLS_TO_SCAN below.
USE_ALL_USDT_PAIRS = True
MIN_24H_VOLUME_USDT = 10_000_000   # skip illiquid/low-volume coins (10M+ 24h volume)
MAX_SYMBOLS_TO_SCAN = 120          # hard cap even after volume filtering, to protect rate limits

TIMEFRAME = "5m"                 # candle timeframe to scan
CANDLE_LIMIT = 200               # how many candles to pull each check

# ---- Signal logic settings ----
EMA_PERIOD = 20
VOLUME_SPIKE_MULTIPLIER = 2.0    # volume must be X times the recent average
TP1_PCT = 0.025                  # +2.5%
TP2_PCT = 0.05                   # +5.0%
TP3_PCT = 0.085                  # +8.5%
SL_PCT = 0.025                   # -2.5%

# ---- Scheduler settings ----
CHECK_INTERVAL_SECONDS = 600     # how often to scan (10 min - raised because scanning ~120 symbols x 4 timeframes takes a while)

# =====================================================================
# REAL TRADING SETTINGS - read the README before touching DRY_RUN / USE_TESTNET
# =====================================================================

# Binance API credentials - create these in Binance account settings.
# IMPORTANT: only enable "Futures Trading" permission, NEVER "Withdrawals".
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Safety switches - both must be deliberately changed to go live.
# DRY_RUN=True: signals are logged and "paper" positions are tracked, but
#               NO real orders are ever sent to the exchange.
# USE_TESTNET=True: orders go to Binance's Futures Testnet (fake money,
#               real order flow) instead of the real exchange.
DRY_RUN = True
USE_TESTNET = True

MARKET_TYPE = "future"           # Binance USDT-M futures (needed for OI data + easy SL/TP orders)

# ---- Risk management ----
RISK_PER_TRADE_PCT = 1.0         # % of account balance risked per trade (distance entry->SL)
MAX_OPEN_POSITIONS = 3           # don't open more than this many trades at once
LEVERAGE = 2                     # keep this LOW; higher leverage = faster liquidation
MIN_NOTIONAL_USDT = 5             # Binance's exchange minimum order size (varies per symbol)

# ---- Multi-timeframe confirmation ----
CONFIRM_TIMEFRAMES = ["1h", "4h"]   # signal must also show trend agreement on these
MTF_EMA_PERIOD = 20

# ---- Fibonacci extension settings ----
FIB_LOOKBACK = 50                 # candles to look back for swing high/low
FIB_TP1_RATIO = 0.618
FIB_TP2_RATIO = 1.0
FIB_TP3_RATIO = 1.618

# ---- Open interest settings ----
OI_CHANGE_LOOKBACK = 6            # number of OI snapshots to compare (5m each ~30min)
OI_CHANGE_THRESHOLD_PCT = 3.0     # OI must have grown at least this % to confirm "fresh inflow"

# ---- Confidence scoring ----
MIN_CONFIRMATIONS = 4             # out of 9 total: 5m vol, 5m EMA, 1h EMA, 4h EMA, OI inflow, 1m pattern, daily golden cross, RSI divergence, S/R room

# ---- 1m candlestick pattern (entry timing) ----
PATTERN_TIMEFRAME = "1m"
PATTERN_CANDLE_LIMIT = 20         # only need a handful of recent 1m candles
REQUIRE_PATTERN_CONFIRMATION = False  # if True, a signal CANNOT fire without a 1m pattern match

# ---- Trend strength filter (ADX) ----
USE_ADX_FILTER = True             # hard gate: skip symbols in a ranging/choppy market
ADX_PERIOD = 14
ADX_MIN_THRESHOLD = 25            # below this = ranging, no trade regardless of other confirmations
ADX_TIMEFRAME = "1h"              # measure trend strength on 1H (less noisy than 5m)

# ---- BTC market bias filter ----
USE_BTC_BIAS_FILTER = True        # compute BTC 1H/4H bias once per scan cycle (still shown in alerts)
BLOCK_SIGNALS_ON_BEARISH_BTC = False   # if True, suppress new altcoin longs while BTC itself is bearish

# ---- Daily trend filter ----
USE_DAILY_TREND_FILTER = True
DAILY_EMA_FAST = 50
DAILY_EMA_SLOW = 200
REQUIRE_DAILY_UPTREND = True      # hard gate: skip if price is below the daily EMA200

# ---- RSI settings ----
RSI_PERIOD = 14
RSI_OVERBOUGHT_THRESHOLD = 65
USE_RSI_OVERBOUGHT_FILTER = True  # hard gate: skip if 5m RSI is already overbought
RSI_DIVERGENCE_LOOKBACK = 40

# ---- Support/Resistance confluence ----
USE_SR_FILTER = True
SR_TIMEFRAME = "1h"
SR_LOOKBACK = 150
SR_PIVOT_WINDOW = 5
SR_CLUSTER_PCT = 0.5
SR_MIN_TOUCHES = 2
SR_MIN_ROOM_PCT = 1.5             # entry must be at least this % below the nearest resistance zone

# ---- Correlation-aware position sizing ----
USE_CORRELATION_FILTER = True
CORRELATION_LOOKBACK = 100
CORRELATION_THRESHOLD = 0.75      # skip a new position this correlated with an already-open one

# ---- ATR-based dynamic stops & targets ----
USE_ATR_STOPS = True              # True: both SL and TP1/2/3 adapt to each coin's own volatility
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.5           # SL = entry - (ATR * this)
ATR_TP1_MULTIPLIER = 1.5          # TP1 = entry + (ATR * this)
ATR_TP2_MULTIPLIER = 3.0          # TP2 = entry + (ATR * this)
ATR_TP3_MULTIPLIER = 5.0          # TP3 = entry + (ATR * this)

# ---- Funding rate filter (futures) ----
USE_FUNDING_RATE_FILTER = True
FUNDING_RATE_MAX_THRESHOLD = 0.05  # % - skip if funding is this crowded/positive (longs overcrowded)

# ---- Fear & Greed Index (whole-market sentiment) ----
USE_FEAR_GREED_FILTER = True
FEAR_GREED_EXTREME_GREED_THRESHOLD = 75   # informational by default; see BLOCK_ON_EXTREME_GREED
BLOCK_ON_EXTREME_GREED = False    # True: hard-skip ALL signals when market-wide sentiment is euphoric

# ---- Performance tracking ----
PERFORMANCE_LOG_FILE = "trade_log.jsonl"

# ---- State persistence ----
STATE_FILE = "positions_state.json"
