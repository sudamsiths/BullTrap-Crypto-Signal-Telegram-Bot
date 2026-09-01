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
]  # coins to watch
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
CHECK_INTERVAL_SECONDS = 300     # how often to scan (5 minutes)

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
MIN_CONFIRMATIONS = 5             # out of: 5m vol spike, 5m EMA, 1h EMA, 4h EMA, OI inflow, 1m pattern (max 6)

# ---- 1m candlestick pattern (entry timing) ----
PATTERN_TIMEFRAME = "1m"
PATTERN_CANDLE_LIMIT = 20         # only need a handful of recent 1m candles
REQUIRE_PATTERN_CONFIRMATION = False  # if True, a signal CANNOT fire without a 1m pattern match

# ---- State persistence ----
STATE_FILE = "positions_state.json"
