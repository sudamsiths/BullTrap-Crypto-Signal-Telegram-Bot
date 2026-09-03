# Crypto Telegram Signal Bot — Setup Guide

## 1. Create a Telegram Bot
1. On Telegram, search for `@BotFather`
2. Type `/newbot` and give your bot a name and a username
3. Save the **token** you receive (something like `123456:ABC-xyz...`)

## 2. Find Your Chat ID
1. Send a message to your bot on Telegram (private chat, group, or channel)
2. Open this URL in your browser (replace YOUR_TOKEN):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. In the JSON response you'll see something like `"chat":{"id": -1001234567890, ...}` — that number is your Chat ID

## 3. Local Setup
```bash
cd crypto_bot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Configure
Open the `config.py` file and set:
```python
TELEGRAM_BOT_TOKEN = "your token here"
TELEGRAM_CHAT_ID = "your chat id here"
SYMBOLS = ["BTC/USDT", "ETH/USDT", "BERA/USDT"]  # add the coins you want
```

You can also pass the token/chat id as environment variables (safer than hardcoding them in the config file):
```bash
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

## 5. Test It
First check that you can pull data from Binance:
```bash
python3 data_fetch.py
```
If a closing price prints for each coin, data fetching is working.

## 6. Run the Bot
```bash
python3 main.py
```
This runs a continuous loop — it scans your coins once per `CHECK_INTERVAL_SECONDS` in `config.py` (default 5 minutes), and sends a Telegram message whenever a signal condition is met.

## 7. Current Signal Logic (Simple Version)
- Is price above EMA20?
- Is volume 2x or more above the recent 20-candle average?

If both conditions are true, a signal fires. **This is just a starting point** — a production-quality bot would add:
- Multiple timeframe confirmation (1H + 4H)
- Fibonacci extension calculation
- Open Interest data (a separate Binance futures API endpoint)
- Backtesting to calculate a real win rate

Let me know if you'd like any of these added.

## 8. Deploy 24/7
If you run this on your local computer, the bot stops when you close your laptop. To run it 24/7:
- **Railway.app** / **Render.com** — both have free tiers, deployable via git push
- **VPS** (DigitalOcean, Linode, AWS EC2) — run it as a `tmux`/`systemd` service
- On a **VPS**, use `nohup python3 main.py &` or a `screen`/`tmux` session

## ⚠️ Important Notes
- The signal logic here is just a **simple EMA + volume rule** — the "AI Pattern Recognition" and "Win Rate %" style numbers from the original screenshot would require building a separate backtesting engine (not trivial, takes real time)
- **Paper trade before ever testing with real money**
- Never commit API keys/tokens to a public repo — add `config.py` to `.gitignore`, use environment variables instead
