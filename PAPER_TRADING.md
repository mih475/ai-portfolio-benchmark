# Live Paper-Trading (Forward Test)

The backtests (`FINDINGS.md`) found one agent with a reproducible, income-relevant
property — **`claude_aggressive` preserves capital in bear markets by going to
cash**. But every backtest carries upward biases (survivorship, a hindsight-built
watchlist, idealized fills). The only way to know whether the behavior is real is
to run it on **live, unseen days with fake money**: a forward paper-trade. This
is that harness.

**No real money is involved.** Nothing here connects to a broker. It is a
simulation on live data, logged daily.

---

## What it does

Once per trading day, after the close:

1. Runs the agent(s) on **today's live data** — the run date is today, so the
   point-in-time gating is off and the live tools (news, web, fundamentals) are
   enabled. The agent sees what a live trader would.
2. Fills **yesterday's** queued orders at **today's open** (real T+1), marks the
   book to today's close, then asks the agent for tomorrow's orders.
3. Persists one portfolio across days in `v2/data/paper/portfolios/` (committed
   to the repo), and appends a row to a durable **ledger** (`ledger.md` +
   `ledger.json`) with value, day/cumulative return, cash %, positions, today's
   fills, tomorrow's queued orders, and a SPY buy-and-hold benchmark since
   inception.

The agent's own `*_history.json` is overwritten each single-day process, so the
**ledger is the track record**, not that file.

---

## Running it

### Automatically (the intended way)
The **Paper Trade (live daily)** GitHub Actions workflow runs at **22:00 UTC on
weekdays** (~5–6pm US Eastern, after the close) and commits the updated state and
ledger back to the repo. US market holidays need no handling — the runner checks
that today is a real SPY trading day and no-ops otherwise, committing nothing.

Enable it: push to the default branch, then **Actions → Paper Trade (live daily)**.
It needs the same API-key secrets as the backtests (at minimum `ANTHROPIC_API_KEY`
and `FRED_API_KEY`/`FINNHUB_API_KEY`). You can also trigger it manually with
**Run workflow** (optional `agents` and `date` inputs).

### Manually / locally
```bash
# Trade today with the default roster (claude_aggressive + random control)
PORTFOLIOS_DIR=v2/data/paper/portfolios python -m v2.live_runner

# Force a date or a different roster (for testing)
PORTFOLIOS_DIR=v2/data/paper/portfolios \
  python -m v2.live_runner --date 2026-11-03 --agents claude_aggressive,random_control
```

`PORTFOLIOS_DIR` keeps live state in its own directory so it never collides with
throwaway backtest state in `v2/data/portfolios/`.

---

## Reading the results

Open `v2/data/paper/portfolios/ledger.md`. Each row is one market day; the table
tracks the primary agent's value and cumulative return against SPY, and the
"Latest run" section lists what each agent holds, filled today, and queued for
the next open.

### What would confirm the backtest finding
Over a few months of live days, watch for the **defensive behavior** the backtest
showed — not a high return:

- In flat/up stretches: modest participation, often holding some cash.
- In any drawdown: **does it de-risk to cash and lose materially less than SPY?**
  That capital-preservation asymmetry is the whole thesis.

### What would break it
If it stays fully invested into a selloff and tracks or underperforms SPY, the
backtest's bear-market defense was an artifact and the result doesn't survive
contact with unseen data.

A few months of live behavior consistent with the backtest is the bar to clear
before a small **real-money** pilot (which would need a broker API, real
execution, and risk controls — not built here) is even worth discussing.

---

## Limitations (still true live)

- It's one model, forward-tested from one start date — a few months is a small
  sample, and one regime.
- Fills are modeled (T+1 open + slippage), not real broker fills.
- The $3–$50 watchlist is still built from *current* names (the hindsight-watchlist
  bias is reduced going forward but not fully gone until the universe is frozen
  at each date).

See `FINDINGS.md` for the full backtest methodology and results.
