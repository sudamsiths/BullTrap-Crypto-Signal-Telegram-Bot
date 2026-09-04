"""
Logs every signal fired (and later, its outcome) to a JSONL file so you can
build a REAL track record from live/paper trading - not just the backtest.
Each line is one JSON object; read with pandas.read_json(path, lines=True)
or via the summary functions below.
"""

import json
import os
from datetime import datetime, timezone
import config


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_signal_opened(signal: dict, mode: str):
    """Called right after a signal fires and a (paper/testnet/live) position opens."""
    record = {
        "event": "OPEN",
        "timestamp": _now_iso(),
        "symbol": signal["symbol"],
        "entry": signal["entry"],
        "sl": signal["sl"],
        "tp1": signal["tp1"], "tp2": signal["tp2"], "tp3": signal["tp3"],
        "score": signal.get("score"),
        "confirmation_count": signal.get("confirmation_count"),
        "confirmations": signal.get("confirmations", {}),  # individual flags, for later correlation analysis
        "mode": mode,
    }
    _append(record)


def log_signal_closed(symbol: str, outcome: str, exit_price: float, return_pct: float, mode: str):
    """Called when a position closes (SL hit, or manually closed)."""
    record = {
        "event": "CLOSE",
        "timestamp": _now_iso(),
        "symbol": symbol,
        "outcome": outcome,       # "SL", "TP1", "TP2", "TP3", etc.
        "exit_price": exit_price,
        "return_pct": return_pct,
        "mode": mode,
    }
    _append(record)


def _append(record: dict):
    with open(config.PERFORMANCE_LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def read_all_records() -> list[dict]:
    if not os.path.exists(config.PERFORMANCE_LOG_FILE):
        return []
    records = []
    with open(config.PERFORMANCE_LOG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def summarize_performance(days: int = None) -> dict:
    """
    Summarizes CLOSE events, optionally limited to the last `days` days.
    Returns totals, win rate, and average return - the real, live-verified
    numbers (as opposed to the backtest's historical simulation).
    """
    records = [r for r in read_all_records() if r.get("event") == "CLOSE"]

    if days:
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        records = [r for r in records
                   if datetime.fromisoformat(r["timestamp"]).timestamp() >= cutoff]

    if not records:
        return {"count": 0}

    returns = [r["return_pct"] for r in records]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    return {
        "count": len(records),
        "win_rate": len(wins) / len(records) * 100,
        "avg_return": sum(returns) / len(returns),
        "total_return": sum(returns),
        "wins": len(wins),
        "losses": len(losses),
        "best": max(returns),
        "worst": min(returns),
    }


def format_summary_message(days: int = 7) -> str:
    stats = summarize_performance(days)
    if stats["count"] == 0:
        return f"📊 No closed trades in the last {days} days yet."

    return (
        f"📊 *PERFORMANCE SUMMARY (last {days} days)*\n"
        f"Trades closed: `{stats['count']}`\n"
        f"Win rate: `{stats['win_rate']:.1f}%`  ({stats['wins']}W / {stats['losses']}L)\n"
        f"Avg return/trade: `{stats['avg_return']:+.2f}%`\n"
        f"Total return (naive sum): `{stats['total_return']:+.2f}%`\n"
        f"Best trade: `{stats['best']:+.2f}%`\n"
        f"Worst trade: `{stats['worst']:+.2f}%`"
    )
