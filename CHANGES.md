# Changes in this fork

Running log of substantive changes made on top of the upstream baseline
(`Seve1995/ai-portfolio-experiment`). Newest first.

## Unreleased

### Fixed
- **V2 no longer crashes on every run.** `v2/agent_runner.run_agent()` referenced
  an undefined variable `ohlc_raw` on a line that always executed, raising
  `NameError` before any agent could trade. Open prices for T+1 fills are now
  sourced from the MIH snapshot's watchlist, which the snapshot now exposes.
- **MIH snapshot exposes machine-readable watchlist/price data** (`watchlist`
  key in `build_mih_snapshot`), not only the serialized TOON prompt payload, so
  the simulator can read fill prices.

### Known issues still open (see repo issues / notes)
- No true historical backtest: the data layer pulls the latest bar and ignores
  `--run-date` for pricing. System is effectively live-forward only.
- `submit_orders` does not enforce the $3–$50 price universe ("Code is Law" gap).
- Documentation drift: agent/model counts, tool-call cap, and capital base
  disagree across README, handover, and config.
