"""
Tracks open "positions" (real or paper/dry-run) across bot restarts using a
simple JSON file. Helps manage active trades, prevents hitting API limits,
and enforces signal cooldowns to stop repeat trades after Stop Loss (SL).
"""

import json
import os
import asyncio
import time
import logging
import config

logger = logging.getLogger(__name__)

# In-memory store for closed positions cooldown
# Format: {"BTC/USDT": timestamp_when_closed}
CLOSED_COOLDOWNS = {}

# Cooldown time in seconds (e.g., 1800 seconds = 30 minutes)
COOLDOWN_SECONDS = getattr(config, "SIGNAL_COOLDOWN_SECONDS", 1800)


def _load() -> dict:
    if not os.path.exists(config.STATE_FILE):
        return {}
    try:
        with open(config.STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Error loading state file: {e}")
        return {}


def _save(state: dict):
    try:
        with open(config.STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        logger.error(f"Error saving state file: {e}")


def get_open_positions() -> dict:
    return _load()


def has_open_position(symbol: str) -> bool:
    return symbol in _load()


def open_position_count() -> int:
    return len(_load())


def add_position(symbol: str, position: dict):
    state = _load()
    state[symbol] = position
    _save(state)
    logger.info(f"Opened position for {symbol}")


def update_position(symbol: str, updates: dict):
    state = _load()
    if symbol in state:
        state[symbol].update(updates)
        _save(state)


def close_position(symbol: str):
    state = _load()
    if symbol in state:
        del state[symbol]
        _save(state)
        # Position එක close කළ සැනින් cooldown list එකට එකතු කරයි
        CLOSED_COOLDOWNS[symbol] = time.time()
        logger.info(f"Closed position for {symbol}. Cooldown started for {COOLDOWN_SECONDS}s.")


def is_in_cooldown(symbol: str) -> bool:
    """Check if the symbol was recently closed and is in cooldown period."""
    if symbol not in CLOSED_COOLDOWNS:
        return False

    elapsed = time.time() - CLOSED_COOLDOWNS[symbol]
    if elapsed < COOLDOWN_SECONDS:
        return True
    else:
        del CLOSED_COOLDOWNS[symbol]  # Clean up expired cooldowns
        return False


def clear_all_positions():
    """Reset all stuck open positions to fix 'Max open positions reached'."""
    _save({})
    logger.info("Cleared all active positions from state file.")


async def safe_position_delay(seconds: float = 0.5):
    """
    Helper delay to prevent Binance API 418 Rate Limit (IP Ban)
    when iterating through multiple requests.
    """
    await asyncio.sleep(seconds)