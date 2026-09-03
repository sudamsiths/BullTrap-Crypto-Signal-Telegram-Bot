"""
Tracks open "positions" (real or paper/dry-run) across bot restarts using a
simple JSON file. Helps manage active trades and prevents hitting API limits.
"""

import json
import os
import asyncio
import logging
import config

logger = logging.getLogger(__name__)


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
        logger.info(f"Closed position for {symbol}")


def clear_all_positions():
    """Reset all stuck open positions to fix 'Max open positions reached'."""
    _save({})
    logger.info("Cleared all active positions from state file.")


async def safe_position_delay(seconds: float = 1.0):
    """
    Helper delay to prevent Binance API 418 Rate Limit (IP Ban)
    when iterating through multiple open positions.
    """
    await asyncio.sleep(seconds)