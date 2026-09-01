"""
Tracks open "positions" (real or paper/dry-run) across bot restarts using a
simple JSON file. This is what lets the bot remember "TP1 already hit, move
SL to breakeven" between scan cycles.
"""

import json
import os
import config


def _load() -> dict:
    if not os.path.exists(config.STATE_FILE):
        return {}
    try:
        with open(config.STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(state: dict):
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


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
