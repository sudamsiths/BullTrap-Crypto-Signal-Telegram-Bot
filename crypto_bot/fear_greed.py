"""
Crypto Fear & Greed Index (from alternative.me's free public API) -
a whole-market sentiment gauge, not specific to any one coin. Extreme
greed readings often precede local tops; extreme fear often precedes
local bottoms. Used here as an informational overlay, and optionally as a
hard gate via config.BLOCK_ON_EXTREME_GREED.
"""

import requests
import config

FNG_API_URL = "https://api.alternative.me/fng/?limit=1"


def get_fear_greed_index() -> dict | None:
    """
    Returns {"value": int, "classification": str} e.g. {"value": 82, "classification": "Extreme Greed"},
    or None if the API can't be reached.
    """
    try:
        response = requests.get(FNG_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        entry = data["data"][0]
        return {"value": int(entry["value"]), "classification": entry["value_classification"]}
    except Exception as e:
        print(f"[fear_greed] Could not fetch index: {e}")
        return None


def is_extreme_greed(fng: dict | None) -> bool:
    if fng is None:
        return False
    return fng["value"] >= config.FEAR_GREED_EXTREME_GREED_THRESHOLD


def sentiment_allows_signals(fng: dict | None) -> bool:
    """Hard-gate check, only blocks when config.BLOCK_ON_EXTREME_GREED is True."""
    if not config.USE_FEAR_GREED_FILTER or not config.BLOCK_ON_EXTREME_GREED:
        return True
    return not is_extreme_greed(fng)
