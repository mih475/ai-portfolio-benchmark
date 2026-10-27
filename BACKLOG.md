# Backlog

Tracked work not yet applied, with enough detail to pick up directly. Items
here touch the **live execution path**, which can't be run in the cloud dev
sandbox (no provider API keys; network egress is limited to package registries
+ GitHub, so Yahoo Finance / FRED / Brave / the LLM APIs are unreachable). They
need a smoke test against real data — in GitHub Actions (which has the secrets)
or on a local machine — before being trusted.

---

## 1. Historical backtest support — DONE for prices (chose: A, free yfinance)

**Status.** Implemented in `v2/price_provider.py`. `--run-date` now fetches a
point-in-time price window ending at that date (past dates only; today/future
stay on the live path). Chosen data source: **A — free yfinance history.**

**Still open under this item:**
- **FRED macro — DONE** for the snapshot path (`as_of` observation-date window).
  Remaining FRED nuance: uses current data vintage, not ALFRED point-in-time
  vintages, so revised series (CPI, UNRATE) show later revisions. Upgrade to
  `get_series_as_of_date` if revision accuracy matters.
- **Tool look-ahead — DONE.** Run-level `as_of` context in `mcp_servers`:
  date-aware tools (`get_macro`, `get_technicals`) get `as_of` injected;
  present-only tools (`web_search`, `get_market_news`, `fetch_url`,
  `get_fundamentals`) are disabled on a past date. The MIH snapshot's *narrative*
  (Brave) and *catalyst watchlist* are also suppressed for a historical snapshot.
  So a backtest now has point-in-time prices + FRED macro and **no** news/catalyst
  look-ahead. Remaining: yfinance caching/retry (next item) for reproducibility.
- **yfinance reliability.** Shared CI IPs get rate-limited (this is what broke
  the first smoke run). Consider retry/backoff + a local on-disk price cache so
  a backtest is reproducible and not re-hitting Yahoo.
- **Survivorship/accuracy caveats of free yfinance** (adjusted vs raw prices,
  delisted tickers) — document in the methodology before trusting results.

## 2. Fairness: freeze one price set per trading day — DONE

Implemented. `run_all_agents` pre-builds all simulators, fetches the day's OHLC
once via `price_provider.day_ohlc` for the union of held/queued tickers, and
passes that frozen set to every `run_agent(ohlc_data=...)`. `run_agent` still
fetches its own bars when called standalone (ohlc_data=None). Validated by smoke
run.

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
