"""
Formats and sends the signal message to Telegram.
"""

from telegram import Bot
from telegram.constants import ParseMode
import config


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
        f"📊 *CONFIRMATIONS ({signal['confirmation_count']}/5)*\n"
        f"▫️ 5m volume spike: `{signal['volume_ratio']}x`\n"
        f"▫️ 5m above EMA{config.EMA_PERIOD}: `{signal['above_ema20']}`\n"
        f"{mtf_lines}\n"
        f"▫️ Open Interest change: {oi_line}\n\n"
        f"🎯 Score: `{signal['score']}/100`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Not financial advice. DYOR."
    )


async def send_signal(signal: dict):
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    message = format_signal_message(signal)
    await bot.send_message(
        chat_id=config.TELEGRAM_CHAT_ID,
        text=message,
        parse_mode=ParseMode.MARKDOWN,
    )


async def send_text(text: str):
    """Utility for sending plain status/error messages."""
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
