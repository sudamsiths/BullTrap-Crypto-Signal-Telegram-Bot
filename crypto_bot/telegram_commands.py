"""
Telegram command listener - runs alongside the main scan loop so you can
check the bot's status directly from your phone/Telegram chat instead of
SSH-ing in or running check_pnl.py manually.

Commands:
  /trades  - open positions with live unrealized PNL
  /pnl     - closed-trade performance summary (7-day and all-time)
  /status  - bot mode, symbol count, next scan info
  /help    - list available commands
"""

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

import config
import position_tracker
import performance_tracker
from data_fetch import get_exchange, fetch_ohlcv


def _is_authorized(update: Update) -> bool:
    """Only respond to the configured chat - prevents strangers who somehow
    message your bot from pulling your trading data."""
    return str(update.effective_chat.id) == str(config.TELEGRAM_CHAT_ID)


async def cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return

    positions = position_tracker.get_open_positions()
    if not positions:
        await update.message.reply_text("No open positions right now.")
        return

    exchange = get_exchange()
    lines = [f"📊 OPEN POSITIONS ({len(positions)})\n"]
    for symbol, pos in positions.items():
        try:
            df = fetch_ohlcv(exchange, symbol, timeframe="5m", limit=2)
            current_price = float(df["close"].iloc[-1])
            unrealized_pct = (current_price / pos["entry"] - 1) * 100
            tp1_note = " (SL@BE)" if pos.get("tp1_hit") else ""
            lines.append(
                f"🪙 {symbol}\n"
                f"   Entry {pos['entry']:.6f} → Now {current_price:.6f}  "
                f"({unrealized_pct:+.2f}%){tp1_note}"
            )
        except Exception as e:
            lines.append(f"🪙 {symbol}: price fetch failed ({e})")

    await update.message.reply_text("\n\n".join(lines))


async def cmd_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return

    days = 7
    if context.args and context.args[0].isdigit():
        days = int(context.args[0])

    all_time = performance_tracker.summarize_performance()
    recent = performance_tracker.summarize_performance(days=days)

    def block(title: str, stats: dict) -> str:
        if stats["count"] == 0:
            return f"{title}\nNo closed trades yet."
        return (
            f"{title}\n"
            f"Trades: {stats['count']}  |  Win rate: {stats['win_rate']:.1f}% "
            f"({stats['wins']}W/{stats['losses']}L)\n"
            f"Avg return: {stats['avg_return']:+.2f}%  |  "
            f"Total (naive sum): {stats['total_return']:+.2f}%\n"
            f"Best: {stats['best']:+.2f}%  |  Worst: {stats['worst']:+.2f}%"
        )

    message = (
        f"📊 PERFORMANCE\n\n"
        f"{block(f'Last {days} days:', recent)}\n\n"
        f"{block('All time:', all_time)}"
    )
    await update.message.reply_text(message)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return

    mode = "DRY_RUN (paper)" if config.DRY_RUN else ("TESTNET" if config.USE_TESTNET else "LIVE - REAL MONEY")
    open_count = position_tracker.open_position_count()

    message = (
        f"🤖 BOT STATUS\n\n"
        f"Mode: {mode}\n"
        f"Open positions: {open_count}/{config.MAX_OPEN_POSITIONS}\n"
        f"Scan interval: {config.CHECK_INTERVAL_SECONDS}s\n"
        f"Min confirmations: {config.MIN_CONFIRMATIONS}/9"
    )
    await update.message.reply_text(message)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    await update.message.reply_text(
        "Available commands:\n"
        "/trades - open positions + live unrealized PNL\n"
        "/pnl [days] - closed-trade performance (default 7 days)\n"
        "/status - bot mode and settings\n"
        "/help - this message"
    )


def build_application() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("trades", cmd_trades))
    app.add_handler(CommandHandler("pnl", cmd_pnl))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))
    return app
