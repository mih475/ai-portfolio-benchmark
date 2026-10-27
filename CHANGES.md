# Changes in this fork

Running log of substantive changes made on top of the upstream baseline
(`Seve1995/ai-portfolio-experiment`). Newest first.

## Unreleased

### Added
- Offline test suite for the simulator (`v2/tests/test_portfolio_simulator.py`),
  stdlib-only, runnable anywhere. Now 18 tests covering execution, validation,
  stops/TPs, price universe, gap fills, and persistence.

### Changed
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
