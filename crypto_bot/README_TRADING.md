# Real Trading Setup — Read This Before Touching DRY_RUN / USE_TESTNET

## What's new in this version

| File | What it does |
|---|---|
| `multi_timeframe.py` | Checks 1H + 4H trend agreement (price vs EMA20) |
| `fibonacci.py` | Calculates real TP1/TP2/TP3 from swing low→high + Fibonacci extension ratios |
| `open_interest.py` | Pulls Binance Futures open interest change to confirm "fresh inflow" |
| `position_tracker.py` | Saves open positions to `positions_state.json` so the bot remembers state across restarts |
| `trade_executor.py` | Places real/testnet orders on Binance Futures - entry, 3-way TP split, SL, and breakeven-move after TP1 |
| `signal_logic.py` | Now scores signals out of 5 confirmations (5m volume, 5m EMA, 1H EMA, 4H EMA, OI inflow) and requires `MIN_CONFIRMATIONS` to fire |

## The two safety switches (in `config.py`)

```python
DRY_RUN = True        # True = no orders sent anywhere, just simulated + logged
USE_TESTNET = True     # True = orders go to Binance's fake-money Futures Testnet
```

**Both default to the safest setting.** To ever place a real order with real money, you must deliberately set BOTH to `False`. Nothing in this codebase does that for you.

## Recommended path to going live

1. **Run with `DRY_RUN=True` for at least 1-2 weeks.** Watch the Telegram alerts and the `positions_state.json` file. Confirm the signals make sense to you before trusting the logic with any money.
2. **Get Binance Futures Testnet keys**: https://testnet.binancefuture.com — separate account, fake $ balance, real order-matching engine. Set `DRY_RUN=False`, keep `USE_TESTNET=True`, and add these testnet keys to `config.py` or as environment variables:
   ```powershell
   $env:BINANCE_API_KEY="your_testnet_key"
   $env:BINANCE_API_SECRET="your_testnet_secret"
   ```
3. **Only after that runs cleanly for a while**, create real Binance API keys:
   - Binance → Account → API Management → Create API
   - Enable **only** "Enable Futures" — never enable withdrawals
   - Restrict the key to your IP address if your bot runs on a fixed server
   - Set `USE_TESTNET=False`, `DRY_RUN=False`

## Risk settings to review before going live

In `config.py`:
- `RISK_PER_TRADE_PCT` — % of account balance risked per trade (position size is calculated from this, not a fixed dollar amount)
- `MAX_OPEN_POSITIONS` — hard cap on simultaneous trades
- `LEVERAGE` — keep this low; higher leverage = your SL distance can get liquidated before it's even hit
- `MIN_CONFIRMATIONS` — how many of the 5 confirmation checks must pass (5m volume spike, 5m EMA, 1H EMA, 4H EMA, OI inflow)

## What this bot does NOT do (be aware)

- No slippage modeling — real fills will differ slightly from the signal's `entry` price
- No exchange fee accounting in position sizing
- Swing high/low detection for Fibonacci levels is a simple min/max over a lookback window, not proper pivot detection
- No portfolio-level drawdown circuit breaker (e.g. "stop trading after -10% for the day") - consider adding one before going live
- `check_sl_hit_dry_run` only simulates SL fills in DRY_RUN mode; in testnet/live mode, the exchange's own stop-market order handles this, and you should build order-status polling if you want Telegram alerts on real fills

## Standard disclaimer

This code has no track record and comes with no guarantee of profitability. Crypto futures trading with leverage can lose more than your initial deposit. Nothing here is financial advice - test thoroughly, size positions you can afford to lose, and understand every line before running it with real funds.
