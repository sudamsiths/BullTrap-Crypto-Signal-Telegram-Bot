"""
Sends a performance summary (real logged trades, not backtest) to Telegram.

Run manually any time:
    python3 send_performance_summary.py        # last 7 days
    python3 send_performance_summary.py 30      # last 30 days

Or schedule it (Windows Task Scheduler / cron) to run weekly for an
automatic recap in your Telegram chat.
"""

import asyncio
import sys

from telegram_bot import send_text
import performance_tracker


async def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    message = performance_tracker.format_summary_message(days)
    print(message.replace("*", "").replace("`", ""))
    await send_text(message, markdown=True)


if __name__ == "__main__":
    asyncio.run(main())
