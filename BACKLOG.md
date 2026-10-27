# Backlog

Tracked work not yet applied, with enough detail to pick up directly. Items
here touch the **live execution path**, which can't be run in the cloud dev
sandbox (no provider API keys; network egress is limited to package registries
+ GitHub, so Yahoo Finance / FRED / Brave / the LLM APIs are unreachable). They
need a smoke test against real data — in GitHub Actions (which has the secrets)
or on a local machine — before being trusted.

---

## 1. Historical backtest support (needs a decision)

**Problem.** `v2/snapshot_engine.fetch_watchlist_data()` and the OHLC fetch in
`v2/agent_runner.run_agent()` both call `yfinance` with `period="1d"`, which
returns the *latest* bar and ignores the `--run-date` passed on the CLI. So
`--run-date 2026-04-07` builds a snapshot *labelled* April 7 but priced with
today's data. The system can therefore only run **forward, live, one real day at
a time** (which is how the GitHub Actions cron uses it). Reproducible historical
backtests are not possible as written.

**Decision needed from you — the data source:**
- **A. `yfinance` history (free).** Fetch the specific date's OHLC via
  `yf.download(tickers, start=date, end=date+1d)`. Zero cost, but rate-limited
  and occasionally gappy; fine for modest backtests.
- **B. A paid data vendor** (Polygon, Tiingo, Alpaca market data, etc.). More
  reliable and point-in-time correct, but adds a key + cost.
- **C. Keep it live-only** and drop the `--run-date` pretense (make the CLI
  reflect that it always runs "today").

**Sketch once a source is chosen:** introduce a small `PriceProvider` interface
with `get_ohlc(tickers, date) -> {ticker: {open,high,low,close}}` and
`get_prices(tickers, date) -> {ticker: price}`; implement `LivePriceProvider`
(current behaviour) and `HistoricalPriceProvider` (date-aware). `snapshot_engine`
and `agent_runner` take a provider instead of calling `yfinance` inline. This
also removes the duplicated fetch logic.

> Note: a genuine point-in-time snapshot also needs the *watchlist membership*,
> catalysts, and macro series as-of the date — not just prices. True historical
> replay is a larger effort than just swapping the price call; scope accordingly.

## 2. Fairness: freeze one price set per trading day (ready to apply)

**Problem.** Each agent fetches prices live inside its own `run_agent()` call,
and the roster runs sequentially with a 5–15s jitter. Agents later in the roster
can see slightly different data. For a post-close run this is minor, but it
breaks the "all agents see identical data" guarantee.

**Fix.** Fetch the day's OHLC **once** in `run_all_agents()` for the union of all
agents' held + pending tickers, then pass that shared `ohlc_data` into
`run_agent(ohlc_data=...)`. Give `run_agent` an optional `ohlc_data` param that
falls back to the current per-agent fetch when not provided (keeps call sites
working). Requires: build all simulators first, union their
`position_tickers + pending order tickers`, one `yf.download`, then loop.

**Why not already committed:** it changes the live execution path and can't be
verified in the sandbox. Apply + smoke-test together.

## 3. Stop vs take-profit same-bar ambiguity

If a single daily bar's range hits **both** the stop and the take-profit, the
simulator currently resolves stop-first (conservative). That's a defensible
default, but it's an assumption worth making explicit and configurable (e.g., a
`pessimistic_fills` flag), and worth a note in the methodology write-up.

## 4. Smaller cleanups

- `submit_orders` cash check (#8) uses `self.portfolio_value`, which reflects the
  *previous* mark, before the day's open MTM. Minor; revisit if sizing looks off.
- Price-universe is enforced at execution (correct), but not surfaced back to the
  agent as a rejection reason the way `submit_orders` validations are. Consider
  echoing skipped buys into the day's decision log.
- Leftover `perplexity` references (V1 model, `api_type` comment in config) — V2
  doesn't use it. Harmless, but remove for tidiness.
- `v2/smoke_test_phase1.py` / `phase2.py` require live keys/network; they are not
  part of the offline suite. Consider gating them behind an env check.
