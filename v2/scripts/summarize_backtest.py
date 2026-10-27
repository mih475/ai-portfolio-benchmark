"""
Summarize backtest results into a leaderboard.

Reads each agent's persisted state JSON in the portfolios dir and reports final
portfolio value, cumulative return, max drawdown, days run, and open positions,
sorted best-to-worst. Prints a Markdown table and writes it to summary.md.

Pure-stdlib so it runs anywhere (incl. CI and offline tests).

Usage:  python3 v2/scripts/summarize_backtest.py [portfolios_dir]
"""

import json
import sys
from pathlib import Path


def agent_metrics(state: dict) -> dict:
    start = state.get("starting_capital", 10000.0) or 10000.0
    cash = state.get("cash", 0.0)
    positions = state.get("positions", {}) or {}
    pos_val = sum((p.get("shares", 0) or 0) * (p.get("current_price", 0) or 0)
                  for p in positions.values())
    value = cash + pos_val
    cum = (value - start) / start if start else 0.0
    return {
        "agent": state.get("agent_id", "?"),
        "value": round(value, 2),
        "cum_return_pct": round(cum * 100, 2),
        "max_drawdown_pct": round((state.get("max_drawdown", 0.0) or 0.0) * 100, 2),
        "days": len(state.get("daily_returns", []) or []),
        "positions": len(positions),
    }


def summarize(portfolios_dir) -> list:
    rows = []
    for f in sorted(Path(portfolios_dir).glob("*.json")):
        if f.name.endswith("_history.json") or f.name == "summary.json":
            continue
        try:
            state = json.loads(f.read_text())
        except Exception:
            continue
        if "agent_id" not in state:
            continue
        rows.append(agent_metrics(state))
    rows.sort(key=lambda r: r["cum_return_pct"], reverse=True)
    return rows


def _no_activity(r: dict) -> bool:
    """An agent that ran days but never moved value or held a position almost
    certainly errored out (e.g. API quota) or did nothing — worth flagging so a
    'green' run that didn't actually trade is obvious at a glance."""
    return (r["days"] > 0 and r["cum_return_pct"] == 0.0
            and r["max_drawdown_pct"] == 0.0 and r["positions"] == 0)


def render(rows: list) -> str:
    lines = [
        "# Backtest Leaderboard",
        "",
        "| Rank | Agent | Final $ | Return % | Max DD % | Days | Open Pos | Note |",
        "|---|---|---|---|---|---|---|---|",
    ]
    flagged = 0
    for i, r in enumerate(rows, 1):
        note = ""
        if _no_activity(r):
            note = "⚠ no activity — check logs (errors/quota?)"
            flagged += 1
        lines.append(
            f"| {i} | {r['agent']} | {r['value']:.2f} | {r['cum_return_pct']:+.2f} "
            f"| {r['max_drawdown_pct']:.2f} | {r['days']} | {r['positions']} | {note} |"
        )
    if not rows:
        lines.append("| — | _no agent state found_ |  |  |  |  |  |  |")
    if flagged:
        lines += ["", f"> ⚠ {flagged} agent(s) showed no activity across the run — "
                      f"likely API errors (e.g. rate-limit/quota) or no trades. "
                      f"Check the run log before trusting these standings."]
    return "\n".join(lines)


def main():
    default_dir = Path(__file__).resolve().parent.parent / "data" / "portfolios"
    portfolios_dir = sys.argv[1] if len(sys.argv) > 1 else str(default_dir)
    rows = summarize(portfolios_dir)
    out = render(rows)
    print(out)
    try:
        (Path(portfolios_dir) / "summary.md").write_text(out)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
