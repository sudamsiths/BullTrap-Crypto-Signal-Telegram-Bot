"""
Quick standalone test - sends one plain message to confirm
TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set up correctly.

Run with: python test_telegram.py
"""

import asyncio
from telegram_bot import send_text


async def main():
    await send_text("✅ Test message - your bot is connected correctly!")
    print("Message sent! Check your Telegram chat now.")


if __name__ == "__main__":
    asyncio.run(main())
