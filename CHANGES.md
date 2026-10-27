# Changes in this fork

Running log of substantive changes made on top of the upstream baseline
(`Seve1995/ai-portfolio-experiment`). Newest first.

## Unreleased

### Added
- **Multi-day backtest.** `v2/backtest.py` iterates a date range in order within
  one process so portfolio state carries day to day; `--start-date/--end-date`
  on `v2/main.py` drive it. `v2/scripts/summarize_backtest.py` prints a
  leaderboard (final value, cumulative return, max drawdown) from the persisted
  state and writes `summary.md`. New `.github/workflows/backtest.yml` runs a
  range on dispatch (default: 3 Gemini personas + random control, free tier) and
  uploads results as an artifact — nothing committed. Offline tests cover date
  iteration and the summary math.
- **yfinance retry + historical disk cache.** `price_provider.window_download`
  now retries transient Yahoo failures (empty frames / rate-limits — the thing
  that broke the first smoke run) with exponential backoff + jitter, and caches
  *historical* windows to `v2/data/price_cache/` keyed by (tickers, as_of,
  period, interval). Backtests become reproducible and stop re-hitting Yahoo on
  reruns; live/today windows are never cached. Opt out with `PRICE_CACHE=0`.
  Offline tests cover retry recovery/exhaustion and cache-key behaviour.
- **No tool look-ahead in backtests.** The MCP registry now has a run-level
  `as_of` context (`set_run_context`), set by the runner to the simulation date.
  On a *past* date it injects `as_of` into date-aware tools (`get_macro`,
  `get_technicals`) so they return point-in-time data, and **disables tools that
  can only return the present** (`web_search`, `get_market_news`, `fetch_url`,
  `get_fundamentals`) so an agent trading a past date can't read present/future
  news or valuations. `get_technicals` gained `as_of` bounding. Live/today runs
  are unaffected. Offline test: `test_tool_gating.py`.
- **Point-in-time macro (FRED).** `fred_server.execute` takes an `as_of` date and
  ends its observation window there, so a historical snapshot carries that date's
  yields/VIX/Fed-funds instead of today's. Threaded through
  `fetch_macro_data(as_of=...)` and `build_mih_snapshot`. (Uses current-vintage
  observation-date filtering, not ALFRED vintages — fine for market-rate series;
  revised series like CPI reflect later revisions. Noted in BACKLOG.) The LLM's
  on-demand `get_macro` tool still returns live data — that tool-path lookahead
  is handled next with news/catalysts. Offline test: `test_fred_asof.py`.
- **Historical price layer (`v2/price_provider.py`).** `--run-date` now actually
  prices off that date. A new `window_download`/`day_ohlc` pair fetches a
  point-in-time window *ending at* the run date; `snapshot_engine`
  (sector rotation, watchlist, technicals) and `agent_runner` (daily OHLC) use
  it instead of calling `yfinance` inline. **Live behaviour is unchanged for
  today/future dates** — only a *past* run date takes the historical path, so
  the production daily cron keeps the exact code path validated by the smoke
  run. Date logic covered by offline tests (`v2/tests/test_price_provider.py`).
- Offline test suite for the simulator (`v2/tests/test_portfolio_simulator.py`),
  stdlib-only, runnable anywhere. Now 18 tests covering execution, validation,
  stops/TPs, price universe, gap fills, and persistence.
- **Single-agent smoke test.** `--agents <id1,id2>` on `v2/main.py` runs a subset
  of the roster instead of all 18, and a new `.github/workflows/smoke_test.yml`
  gives a one-click (`workflow_dispatch`) single-agent run that uploads its output
  as an artifact instead of committing — cheap end-to-end validation.

### Fixed (surfaced by the first smoke run)
- **Snapshot build no longer crashes when sector rotation fails.**
  `fetch_sector_rotation()` returns `{"error": ...}` when its yfinance download
  fails (e.g. rate-limited on a CI runner); `format_as_toon()` then called
  `.get()` on that error string and raised `AttributeError`, killing the entire
  MIH build (and thus any real daily run) before saving anything. It now skips
  non-dict sector entries and renders a placeholder row. Regression test added
  (`v2/tests/test_format_as_toon.py`, wired into CI).

### Fixed (pre-run workflow bugs)
- **Gemini key mismatch:** code reads `GOOGLE_API_KEY` but the daily workflow only
  passed `GEMINI_API_KEY`. The adapter now accepts either (alias map), and the
  workflow passes both. Same alias added for `ANTHROPIC_API_KEY`/`CLAUDE_API_KEY`.
- **Missing provider keys:** the daily workflow never set `MISTRAL_API_KEY`,
  `DEEPSEEK_API_KEY`, or `QWEN_API_KEY`, so half the roster couldn't authenticate.
  Added.

### Changed
- **Fairness: one frozen price set per trading day.** `run_all_agents` now
  pre-builds all simulators, fetches the day's OHLC once for the union of every
  agent's held/queued tickers, and passes that same set to each agent. Agents
  are therefore priced off identical bars regardless of roster order or the
  5–15s jitter (previously each agent fetched its own, so later agents could see
  slightly different data). `run_agent` takes an optional `ohlc_data`; when
  omitted it still fetches its own (standalone use). Also cuts yfinance calls.
- **Price universe is now enforced in code** ("Code is Law"): BUY fills outside
  the $3-$50 band are skipped by the simulator. Added `max_stock_price` (50.00)
  and reconciled `min_stock_price` 5.00 → 3.00 to match the documented universe.
  *(Decision: standardized on the $3-$50 stated in the README/handover/MIH; flip
  in `config.py` if you intended the $5 floor.)*
- **Stop-loss / take-profit gap fills are now realistic.** A gap-down through the
  stop fills at the (worse) open rather than the stop price; a gap-up through the
  target fills at the (better) open. The old behaviour overstated performance on
  crash days.
- **Documentation drift reconciled.** Fixed the roster count (config said "21
  agents / 7 models"; it's 18 LLM agents over 6 models + 1 random control = 19),
  the tool-call cap (README said 15; code/config use 8), and README model names
  now match `config.py` exactly.

### Fixed
- **V2 no longer crashes on every run.** `v2/agent_runner.run_agent()` referenced
  an undefined variable `ohlc_raw` on a line that always executed, raising
  `NameError` before any agent could trade. Open prices for T+1 fills are now
  sourced from the MIH snapshot's watchlist, which the snapshot now exposes.
- **MIH snapshot exposes machine-readable watchlist/price data** (`watchlist`
  key in `build_mih_snapshot`), not only the serialized TOON prompt payload, so
  the simulator can read fill prices.

### Known issues still open (see BACKLOG.md)
- No true historical backtest: the data layer pulls the latest bar and ignores
  `--run-date` for pricing. System is effectively live-forward only.
- Each agent fetches prices live inside its own run; a single frozen price set
  per day would make the roster strictly fair. Specced in BACKLOG.md (#2), not
  yet applied — it touches the live path and needs a smoke test.
