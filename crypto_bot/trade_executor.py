"""
Order execution for Binance USDT-M Futures via ccxt.

SAFETY MODEL:
- config.DRY_RUN = True (default): no network calls that place orders are made.
  Everything is logged/printed and tracked in position_tracker as a "paper" trade.
- config.USE_TESTNET = True (default): even when DRY_RUN is False, orders go to
  Binance's Futures Testnet (fake balance) instead of your real account.
- Both DRY_RUN=False AND USE_TESTNET=False are required before any real money moves.
"""

import ccxt
import config
import position_tracker


def get_trading_exchange():
    """
    Returns a ccxt exchange instance configured for USDT-M futures trading,
    with API keys attached. Only call this when you actually intend to
    place/check real or testnet orders.
    """
    exchange = ccxt.binance({
        "apiKey": config.BINANCE_API_KEY,
        "secret": config.BINANCE_API_SECRET,
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })
    if config.USE_TESTNET:
        exchange.set_sandbox_mode(True)
    return exchange


def get_account_balance_usdt(exchange) -> float:
    balance = exchange.fetch_balance()
    return float(balance.get("USDT", {}).get("free", 0))


def calculate_position_size(entry: float, sl: float, balance_usdt: float) -> float:
    """
    Position sizing based on % risk of account balance, not a fixed dollar
    amount - this way risk stays consistent as the account grows/shrinks.
    Returns quantity in base asset units (e.g. BTC amount, not USDT amount).
    """
    risk_amount_usdt = balance_usdt * (config.RISK_PER_TRADE_PCT / 100)
    stop_distance = abs(entry - sl)
    if stop_distance <= 0:
        return 0.0
    qty = risk_amount_usdt / stop_distance
    return qty


def open_long_position(exchange, symbol: str, signal: dict) -> dict:
    """
    Opens a long position with entry (market order), stop loss, and three
    take-profit orders (50/25/25 split). Returns a position record suitable
    for position_tracker.

    In DRY_RUN mode, no exchange calls are made - a simulated record is
    returned/logged instead, so you can watch the bot's decisions safely
    before ever risking real or even testnet funds.
    """
    entry = signal["entry"]
    sl = signal["sl"]
    tp1, tp2, tp3 = signal["tp1"], signal["tp2"], signal["tp3"]

    if config.DRY_RUN:
        print(f"[DRY_RUN] Would open LONG {symbol}: entry={entry} sl={sl} "
              f"tp1={tp1} tp2={tp2} tp3={tp3}")
        position = {
            "symbol": symbol, "entry": entry, "sl": sl,
            "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "tp1_hit": False, "qty": None, "mode": "dry_run",
        }
        position_tracker.add_position(symbol, position)
        return position

    # ---- Real (or testnet) order placement below ----
    balance = get_account_balance_usdt(exchange)
    qty = calculate_position_size(entry, sl, balance)
    qty = float(exchange.amount_to_precision(symbol, qty))

    if qty * entry < config.MIN_NOTIONAL_USDT:
        print(f"[SKIP] {symbol}: position size too small ({qty}) for min notional")
        return {}

    exchange.set_leverage(config.LEVERAGE, symbol)

    entry_order = exchange.create_order(symbol, "market", "buy", qty)

    # Split take-profit quantity 50/25/25 across three reduce-only limit orders
    tp1_qty = float(exchange.amount_to_precision(symbol, qty * 0.5))
    tp2_qty = float(exchange.amount_to_precision(symbol, qty * 0.25))
    tp3_qty = float(exchange.amount_to_precision(symbol, qty - tp1_qty - tp2_qty))

    tp_orders = []
    for tp_price, tp_qty in [(tp1, tp1_qty), (tp2, tp2_qty), (tp3, tp3_qty)]:
        if tp_qty <= 0:
            continue
        order = exchange.create_order(
            symbol, "limit", "sell", tp_qty, tp_price,
            params={"reduceOnly": True},
        )
        tp_orders.append(order["id"])

    sl_order = exchange.create_order(
        symbol, "stop_market", "sell", qty, None,
        params={"stopPrice": sl, "reduceOnly": True},
    )

    position = {
        "symbol": symbol, "entry": entry, "sl": sl,
        "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "tp1_hit": False, "qty": qty, "mode": "testnet" if config.USE_TESTNET else "live",
        "entry_order_id": entry_order.get("id"),
        "sl_order_id": sl_order.get("id"),
        "tp_order_ids": tp_orders,
    }
    position_tracker.add_position(symbol, position)
    return position


def move_stop_to_breakeven(exchange, symbol: str, position: dict):
    """
    Cancels the existing stop-loss order and replaces it at the entry price.
    Called once TP1 has been filled.
    """
    if config.DRY_RUN:
        print(f"[DRY_RUN] Would move SL to breakeven for {symbol} at {position['entry']}")
        position_tracker.update_position(symbol, {"sl": position["entry"], "tp1_hit": True})
        return

    try:
        exchange.cancel_order(position["sl_order_id"], symbol)
    except Exception as e:
        print(f"[WARN] Could not cancel old SL order for {symbol}: {e}")

    remaining_qty = position["qty"] * 0.5  # roughly what's left after TP1
    new_sl_order = exchange.create_order(
        symbol, "stop_market", "sell", remaining_qty, None,
        params={"stopPrice": position["entry"], "reduceOnly": True},
    )
    position_tracker.update_position(symbol, {
        "sl": position["entry"], "tp1_hit": True, "sl_order_id": new_sl_order.get("id"),
    })


def check_tp1_and_update(exchange, symbol: str, position: dict, current_price: float):
    """
    Called each scan cycle for open positions. If price has reached TP1 and
    we haven't already moved SL to breakeven, do it now.
    """
    if position.get("tp1_hit"):
        return
    if current_price >= position["tp1"]:
        move_stop_to_breakeven(exchange, symbol, position)


def check_sl_hit_dry_run(position: dict, current_price: float) -> bool:
    """DRY_RUN only: since there are no real orders, we simulate SL/TP fills
    by comparing current price - use this to decide when to clear a paper position."""
    return current_price <= position["sl"]
