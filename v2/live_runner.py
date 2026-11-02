"""
AI Portfolio Experiment V2 — Live paper-trading runner.

Runs the daily loop on *live, unseen* market data and persists one portfolio
across days, so a strategy can be forward-tested with fake money before any real
capital is risked. This is the test that strips out every backtest bias at once
(survivorship, hindsight watchlist, look-ahead): the agent only ever sees today.

How it differs from a backtest:
  - The run date is TODAY, so mcp_servers._is_historical() is False and the
    live-only tools (news, web, fundamentals) are enabled — no point-in-time
    gating. The agent trades with the same information a live trader would have.
  - State lives in its own committed directory (PORTFOLIOS_DIR env, pointed at
    v2/data/paper/portfolios by the workflow), accumulating day over day. Pending
    orders submitted after today's close fill at the NEXT run's open (real T+1).
  - A persistent ledger (ledger.json + ledger.md) appends one row per market day
    — value, day/cum return, cash %, positions, today's fills and tomorrow's
    queued orders, plus a SPY buy-and-hold benchmark since inception. The
    simulator's own *_history.json is overwritten each single-day process, so the
    ledger (not that file) is the durable track record.

Usage:
    python -m v2.live_runner                      # trade today, default roster
    python -m v2.live_runner --date 2026-11-03    # force a date (testing)
    python -m v2.live_runner --agents claude_aggressive,random_control

The default roster is the agent under test plus a free random control and the
SPY benchmark, so every day is logged against both luck and the market.
"""

import argparse
import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger("V2_Live")

DEFAULT_AGENTS = ["claude_aggressive", "random_control"]
META_FILE = "paper_meta.json"
LEDGER_JSON = "ledger.json"
LEDGER_MD = "ledger.md"


# ─────────────────────────────────────────────
# Pure helpers (no network / no LLM) — unit-tested
# ─────────────────────────────────────────────

def load_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def init_meta(meta: dict, today_iso: str, agents: list) -> dict:
    """Return meta with inception/agents filled on first run, unchanged after."""
    meta = dict(meta or {})
    meta.setdefault("inception", today_iso)
    meta.setdefault("agents", agents)
    meta["last_run"] = today_iso
    return meta


def _cum_from_state(state: dict) -> float:
    sc = state.get("starting_capital") or 10000.0
    lv = state.get("last_value")
    if lv is None:
        lv = state.get("cash", sc)
    return lv / sc - 1.0 if sc else 0.0


def build_row(today_iso: str, agent_states: dict, histories: dict,
              spy_state: dict | None) -> dict:
    """Assemble one ledger row from already-loaded JSON (pure).

    agent_states: {agent_id: state.json dict}
    histories:    {agent_id: the single DailySnapshot dict for today, or None}
    spy_state:    spy_buy_hold.json dict, or None
    """
    row = {"date": today_iso, "agents": {}}
    for aid, st in agent_states.items():
        sc = st.get("starting_capital") or 10000.0
        lv = st.get("last_value")
        if lv is None:
            lv = st.get("cash", sc)
        drs = st.get("daily_returns") or []
        hist = histories.get(aid) or {}
        fills = [
            {"action": t.get("action"), "ticker": t.get("ticker"),
             "shares": round(float(t.get("shares", 0)), 4), "price": t.get("price"),
             "trigger": t.get("trigger", "")}
            for t in hist.get("transactions_today", [])
        ]
        pending = [
            {"action": o.get("action"), "ticker": o.get("ticker"),
             "allocation_pct": o.get("allocation_pct")}
            for o in st.get("pending_orders", [])
        ]
        row["agents"][aid] = {
            "value": round(float(lv), 2),
            "day_ret": round(float(drs[-1]), 6) if drs else 0.0,
            "cum_ret": round(_cum_from_state(st), 6),
            "cash_pct": round(100.0 * st.get("cash", 0.0) / lv, 1) if lv else 0.0,
            "n_positions": len(st.get("positions", {}) or {}),
            "positions": sorted((st.get("positions", {}) or {}).keys()),
            "max_drawdown": round(float(st.get("max_drawdown", 0.0)), 6),
            "fills_today": fills,
            "pending_next_open": pending,
        }
    if spy_state is not None:
        row["spy"] = {"value": round(float(spy_state.get("cash", 0.0)), 2),
                      "cum_ret": round(_cum_from_state(spy_state), 6)}
    return row


def upsert_row(rows: list, row: dict) -> list:
    """Append row, or replace an existing row for the same date (idempotent
    re-runs of the same day don't create duplicates)."""
    out = [r for r in (rows or []) if r.get("date") != row["date"]]
    out.append(row)
    out.sort(key=lambda r: r["date"])
    return out


def render_markdown(meta: dict, rows: list, primary: str) -> str:
    """Human-readable ledger: a value/return table + today's decision detail."""
    inception = meta.get("inception", "?")
    lines = [
        "# Live paper-trading ledger",
        "",
        f"*Inception: {inception} · Agents: {', '.join(meta.get('agents', []))} · "
        f"Primary: {primary} · Fake money, no capital at risk.*",
        "",
        "| Date | " + f"{primary} $ | day % | cum % | cash % | #pos | "
        "SPY cum % | vs SPY |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        a = r.get("agents", {}).get(primary, {})
        spy = r.get("spy", {})
        spy_cum = spy.get("cum_ret")
        vs = (a.get("cum_ret", 0.0) - spy_cum) if spy_cum is not None else None
        lines.append(
            f"| {r['date']} | {a.get('value', 0):,.0f} | "
            f"{a.get('day_ret', 0)*100:+.2f} | {a.get('cum_ret', 0)*100:+.2f} | "
            f"{a.get('cash_pct', 0):.0f} | {a.get('n_positions', 0)} | "
            f"{spy_cum*100:+.2f} | {vs*100:+.2f} |"
            if spy_cum is not None else
            f"| {r['date']} | {a.get('value', 0):,.0f} | "
            f"{a.get('day_ret', 0)*100:+.2f} | {a.get('cum_ret', 0)*100:+.2f} | "
            f"{a.get('cash_pct', 0):.0f} | {a.get('n_positions', 0)} | — | — |"
        )
    # Latest-day decision detail for every agent
    if rows:
        last = rows[-1]
        lines += ["", f"## Latest run — {last['date']}", ""]
        for aid, a in last.get("agents", {}).items():
            fills = a.get("fills_today", [])
            pend = a.get("pending_next_open", [])
            fills_s = ", ".join(f"{f['action']} {f['ticker']}×{f['shares']:g}@{f['price']}"
                                for f in fills) or "none"
            pend_s = ", ".join(f"{p['action']} {p['ticker']} ({p['allocation_pct']}%)"
                               for p in pend) or "none"
            held = ", ".join(a.get("positions", [])) or "all cash"
            lines.append(
                f"- **{aid}** — ${a.get('value', 0):,.0f} "
                f"({a.get('cum_ret', 0)*100:+.2f}% cum), {a.get('cash_pct', 0):.0f}% cash. "
                f"Holds: {held}. Filled today: {fills_s}. Queued for next open: {pend_s}."
            )
    lines += ["", "*Generated by `v2/live_runner.py`.*"]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Network-touching orchestration
# ─────────────────────────────────────────────

def latest_trading_date(as_of: date):
    """Date of the most recent SPY bar at/under `as_of` (None on failure).

    Used to tell a real market day from a weekend/holiday without a calendar
    dependency: it's a market day iff the latest SPY bar is dated `as_of`.
    """
    try:
        import pandas as pd  # noqa: F401
        from .price_provider import window_download
        data = window_download(["SPY"], as_of=as_of, period="5d")
        if data is None or getattr(data, "empty", True):
            return None
        idx = data.index[-1]
        return idx.date() if hasattr(idx, "date") else None
    except Exception as e:
        logger.warning(f"market-day check failed: {e}")
        return None


def update_spy_benchmark(inception_iso: str, today_iso: str, out_dir: Path):
    """Refresh spy_buy_hold.json for inception..today (best-effort)."""
    try:
        from .backtest import write_benchmark
        from .config import STARTING_CAPITAL
        # Pick a yfinance period that comfortably covers inception..today.
        days = (date.fromisoformat(today_iso) - date.fromisoformat(inception_iso)).days
        period = "1mo" if days <= 25 else "3mo" if days <= 85 else \
                 "6mo" if days <= 175 else "1y" if days <= 360 else "2y"
        write_benchmark(inception_iso, today_iso, out_dir,
                        ticker="SPY", capital=STARTING_CAPITAL, period=period)
    except Exception as e:
        logger.warning(f"SPY benchmark update failed: {e}")


def run_live(today: date | None = None, agents: list | None = None) -> int:
    """Run one live paper-trading day. Returns an exit code (0 ok, 2 skipped)."""
    from .config import PORTFOLIOS_DIR
    out_dir = Path(PORTFOLIOS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    today = today or date.today()
    today_iso = today.isoformat()
    agents = agents or DEFAULT_AGENTS
    llm_agents = [a for a in agents if a != "random_control"]

    meta = init_meta(load_json(out_dir / META_FILE, {}), today_iso, agents)

    # Market-day guard: only trade/log on a real trading day.
    ltd = latest_trading_date(today)
    if ltd is None:
        logger.warning("Could not verify market day (price fetch failed); aborting.")
        return 2
    if ltd != today:
        logger.info(f"{today_iso} is not a market day (latest SPY bar {ltd}); skipping.")
        return 2

    logger.info(f"=== LIVE paper-trade {today_iso} · agents={agents} ===")
    from .agent_runner import run_all_agents
    run_all_agents(today_iso, agent_ids=agents)

    # Refresh the SPY benchmark since inception.
    update_spy_benchmark(meta["inception"], today_iso, out_dir)

    # Assemble today's ledger row from the freshly persisted JSON.
    agent_states, histories = {}, {}
    for aid in agents:
        agent_states[aid] = load_json(out_dir / f"{aid}.json", {})
        hist = load_json(out_dir / f"{aid}_history.json", [])
        histories[aid] = hist[-1] if isinstance(hist, list) and hist else {}
    spy_state = load_json(out_dir / "spy_buy_hold.json", None)

    row = build_row(today_iso, agent_states, histories, spy_state)
    rows = upsert_row(load_json(out_dir / LEDGER_JSON, []), row)

    (out_dir / LEDGER_JSON).write_text(json.dumps(rows, indent=2))
    primary = llm_agents[0] if llm_agents else agents[0]
    (out_dir / LEDGER_MD).write_text(render_markdown(meta, rows, primary))
    (out_dir / META_FILE).write_text(json.dumps(meta, indent=2))

    a = row["agents"].get(primary, {})
    spy = row.get("spy", {})
    logger.info(f"{today_iso} {primary}: ${a.get('value', 0):,.0f} "
                f"({a.get('cum_ret', 0)*100:+.2f}% cum) vs SPY "
                f"{spy.get('cum_ret', 0)*100:+.2f}% — ledger rows: {len(rows)}")
    return 0


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    p = argparse.ArgumentParser(description="Live paper-trading runner")
    p.add_argument("--date", default=None, help="Force run date YYYY-MM-DD (default: today)")
    p.add_argument("--agents", default=None, help="Comma-separated agent ids")
    args = p.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")
    except ImportError:
        pass

    d = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    agents = [a.strip() for a in args.agents.split(",")] if args.agents else None
    raise SystemExit(run_live(d, agents))


if __name__ == "__main__":
    main()
