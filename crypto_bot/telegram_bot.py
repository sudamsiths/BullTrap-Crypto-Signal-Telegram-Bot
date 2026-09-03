"""
Formats and sends the signal message to Telegram.
"""

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import BadRequest
import re
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
        f"📊 *CONFIRMATIONS ({signal['confirmation_count']}/9)*\n"
        f"▫️ 5m volume spike: `{signal['volume_ratio']}x`\n"
        f"▫️ 5m above EMA{config.EMA_PERIOD}: `{signal['above_ema20']}`\n"
        f"{mtf_lines}\n"
        f"▫️ Open Interest change: {oi_line}\n"
        f"▫️ 1m pattern: {pattern_line}\n"
        f"▫️ ADX (trend strength, {config.ADX_TIMEFRAME}): {adx_line}\n"
        f"▫️ Daily golden cross (EMA50>EMA200): `{signal.get('daily_golden_cross')}`\n"
        f"▫️ RSI bullish divergence: `{signal.get('rsi_divergence')}`\n"
        f"▫️ Room before resistance: `{signal.get('sr_room_to_target')}`\n\n"
        f"⚡ BTC MARKET BIAS: {btc_bias_emoji} `{(btc_bias or 'n/a').upper()}`\n\n"
        f"🎯 Score: `{signal['score']}/100`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Not financial advice. DYOR."
    )


def _strip_markdown(text: str) -> str:
    """Removes Markdown formatting characters so the message can be sent as plain text."""
    return re.sub(r"[*_`]", "", text)


async def _send_safe(bot: Bot, text: str, use_markdown: bool):
    """
    Sends with Markdown if requested; if Telegram rejects it due to a parse
    error (e.g. an unescaped _, *, or ` in dynamic content like a coin
    symbol), automatically retries as plain text so the alert always gets
    through instead of silently failing.
    """
    if not use_markdown:
        await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
        return
    try:
        await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text,
                                parse_mode=ParseMode.MARKDOWN)
    except BadRequest as e:
        if "can't parse entities" in str(e).lower():
            print(f"[telegram] Markdown parse error, resending as plain text: {e}")
            await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=_strip_markdown(text))
        else:
            raise


async def send_signal(signal: dict):
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    message = format_signal_message(signal)
    await _send_safe(bot, message, use_markdown=True)


async def send_text(text: str, markdown: bool = False):
    """Utility for sending plain (or optionally Markdown-formatted) status messages."""
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    await _send_safe(bot, text, use_markdown=markdown)