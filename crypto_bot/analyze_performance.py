"""
Correlates individual confirmation flags (RSI divergence, golden cross,
etc.) with actual closed-trade outcomes, using the bot's own
trade_log.jsonl - no need to manually parse a Telegram chat export.

This is the same analysis originally done by hand on a chat export PDF;
run this any time you want a fresh read as more real trades close.

Run with: python3 analyze_performance.py
          python3 analyze_performance.py 30      # last 30 days only
"""

import sys
from collections import defaultdict
from datetime import datetime, timezone

import performance_tracker


def _pair_open_close_events(records: list[dict]) -> list[dict]:
    """
    FIFO-pairs each symbol's OPEN events with its next CLOSE event, in
    timestamp order - mirrors how position_tracker only allows one open
    position per symbol at a time.
    """
    records = sorted(records, key=lambda r: r["timestamp"])
    open_queue = defaultdict(list)
    pairs = []

    for r in records:
        if r["event"] == "OPEN":
            open_queue[r["symbol"]].append(r)
        elif r["event"] == "CLOSE":
            queue = open_queue[r["symbol"]]
            if queue:
                open_record = queue.pop(0)
                pairs.append({
                    "symbol": r["symbol"],
                    "confirmations": open_record.get("confirmations", {}),
                    "score": open_record.get("score"),
                    "confirmation_count": open_record.get("confirmation_count"),
                    "outcome": r["outcome"],
                    "return_pct": r["return_pct"],
                })
    return pairs


def analyze(days: int = None):
    records = performance_tracker.read_all_records()

    if days:
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        records = [r for r in records
                   if datetime.fromisoformat(r["timestamp"]).timestamp() >= cutoff]

    pairs = _pair_open_close_events(records)

    if not pairs:
        print("No paired open->close trades found yet. Keep the bot running "
              "and check back once some positions have closed.")
        return

    print(f"\nAnalyzing {len(pairs)} closed trades"
          + (f" (last {days} days)" if days else " (all time)") + "\n")

    # Overall
    wins = [p for p in pairs if p["return_pct"] > 0]
    print(f"Overall win rate: {len(wins)/len(pairs)*100:.1f}%  "
          f"({len(wins)}W / {len(pairs)-len(wins)}L)")
    print(f"Overall avg return: {sum(p['return_pct'] for p in pairs)/len(pairs):+.2f}%\n")

    # By individual confirmation flag
    all_keys = set()
    for p in pairs:
        all_keys.update(p["confirmations"].keys())

    print("=" * 60)
    print("WIN RATE BY INDIVIDUAL CONFIRMATION")
    print("=" * 60)
    for key in sorted(all_keys):
        for val in [True, False]:
            subset = [p["return_pct"] for p in pairs if p["confirmations"].get(key) == val]
            if len(subset) < 3:
                continue  # too few to be meaningful
            wins_n = sum(1 for v in subset if v > 0)
            print(f"  {key}={val}: n={len(subset)}, "
                  f"win_rate={wins_n/len(subset)*100:.1f}%, "
                  f"avg_return={sum(subset)/len(subset):+.2f}%")
        print()

    # By score bucket
    print("=" * 60)
    print("WIN RATE BY SCORE")
    print("=" * 60)
    by_score = defaultdict(list)
    for p in pairs:
        by_score[p["score"]].append(p["return_pct"])
    for score in sorted((s for s in by_score if s is not None), reverse=True):
        vals = by_score[score]
        wins_n = sum(1 for v in vals if v > 0)
        print(f"  Score {score}: n={len(vals)}, win_rate={wins_n/len(vals)*100:.1f}%, "
              f"avg_return={sum(vals)/len(vals):+.2f}%")

    print("\nNOTE: small sample sizes (under ~30 per bucket) can easily show")
    print("misleading patterns by chance. Treat single-digit-n buckets as")
    print("noise, not signal, until more trades accumulate.\n")


if __name__ == "__main__":
    n_days = int(sys.argv[1]) if len(sys.argv) > 1 else None
    analyze(n_days)
