"""
Formats and sends the signal message to Telegram.
"""

from telegram import Bot
from telegram.constants import ParseMode
import config
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Active Status", callback_data='status')],
        [InlineKeyboardButton("📈 Latest Signals", callback_data='signals')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("BullTrap Crypto Bot Active! 🚀 Choice an option:", reply_markup=reply_markup)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot is running smoothly and scanning markets.")

# Telegram Bot app initialize කරන්න
def setup_telegram_bot(token):
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_command))
    return app

def format_signal_message(signal: dict) -> str:
    entry = signal["entry"]

    def pct(target):
        return (target / entry - 1) * 100

    mtf = signal.get("mtf", {})
    mtf_lines = "\n".join(
        f"▫️ {tf}: {'✅ above EMA' if v.get('above_ema') else '❌ below EMA'}"
        for tf, v in mtf.items()
    )

    oi = signal.get("oi_change_pct")
    oi_line = f"`{oi:+.2f}%`" if oi is not None else "`n/a`"

    pattern = signal.get("pattern_name")
    pattern_line = f"`{pattern}`" if pattern else "`none detected`"

    adx = signal.get("adx")
    adx_line = f"`{adx:.1f}`" if adx is not None else "`n/a`"

    btc_bias = signal.get("btc_bias")
    btc_bias_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}.get(btc_bias, "🟡")

    mode_note = "🧪 DRY_RUN (paper only)" if config.DRY_RUN else (
        "🧪 TESTNET" if config.USE_TESTNET else "🔴 LIVE"
    )

    return (
        f"🚀 *CRYPTO BUY SIGNAL (LONG)*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🪙 Coin: `{signal['symbol']}`\n"
        f"🏦 Exchange: `{config.EXCHANGE_ID.upper()}`\n"
        f"💰 Price: `{entry:.6f}`\n"
        f"🔧 Mode: {mode_note}\n\n"
        f"🎯 *TARGET SETUP (FIBONACCI EXTENSIONS)*\n"
        f"🟢 Entry: `{entry:.6f}`\n"
        f"🎯 TP1: `{signal['tp1']:.6f}` (+{pct(signal['tp1']):.1f}%)\n"
        f"🚀 TP2: `{signal['tp2']:.6f}` (+{pct(signal['tp2']):.1f}%)\n"
        f"🌕 TP3: `{signal['tp3']:.6f}` (+{pct(signal['tp3']):.1f}%)\n"
        f"🛡️ Stop Loss: `{signal['sl']:.6f}` (-{config.SL_PCT*100:.1f}%, moves to BE after TP1)\n\n"
        f"📊 *CONFIRMATIONS ({signal['confirmation_count']}/6)*\n"
        f"▫️ 5m volume spike: `{signal['volume_ratio']}x`\n"
        f"▫️ 5m above EMA{config.EMA_PERIOD}: `{signal['above_ema20']}`\n"
        f"{mtf_lines}\n"
        f"▫️ Open Interest change: {oi_line}\n"
        f"▫️ 1m pattern: {pattern_line}\n"
        f"▫️ ADX (trend strength, {config.ADX_TIMEFRAME}): {adx_line}\n\n"
        f"⚡ BTC MARKET BIAS: {btc_bias_emoji} `{(btc_bias or 'n/a').upper()}`\n\n"
        f"🎯 Score: `{signal['score']}/100`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Not financial advice. DYOR."
    )


async def send_signal(signal):
    # Special characters වලින් error එන එක නවත්වන්න html.escape පාවිච්චි කරන්න
    symbol = html.escape(str(signal.get('symbol', 'N/A')))
    score = signal.get('score', 0)
    confirmations = signal.get('confirmations', 0)
    price = signal.get('price', 0)
    sl = signal.get('stop_loss', 0)
    tp = signal.get('take_profit', 0)

    # HTML tags භාවිතයෙන් ලස්සනට format කරගන්න
    message = (
        f"<b>🚨 CRYPTO SIGNAL DETECTED</b>\n\n"
        f"<b>Pair:</b> {symbol}\n"
        f"<b>Score:</b> {score}\n"
        f"<b>Confirmations:</b> {confirmations}\n"
        f"<b>Entry Price:</b> ${price}\n"
        f"<b>Stop Loss:</b> ${sl}\n"
        f"<b>Take Profit:</b> ${tp}\n"
    )

    await bot.send_message(
        chat_id=config.TELEGRAM_CHAT_ID,
        text=message,
        parse_mode='HTML' # Markdown වෙනුවට HTML දාන්න
    )

async def send_text(text: str):
    """Utility for sending plain status/error messages."""
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
