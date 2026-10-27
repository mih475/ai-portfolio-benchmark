"""
Multi-day backtest driver.

Runs the daily loop over a date range *in order, in one process*, so each day's
persisted portfolio state carries into the next (pending orders fill the next
market day, stops/marks accumulate). Non-market days are skipped by
run_all_agents itself, so we can just iterate calendar days.

`iter_dates` is kept import-light (stdlib only) so it's unit-testable without
pulling in the heavy runner.
"""

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def iter_dates(start_iso: str, end_iso: str):
    """Yield ISO date strings from start to end inclusive (all calendar days)."""
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    if end < start:
        raise ValueError(f"end_date {end_iso} is before start_date {start_iso}")
    d = start
    while d <= end:
        yield d.isoformat()
        d += timedelta(days=1)


def run_backtest(start_iso: str, end_iso: str, agent_ids=None):
    """Run the roster across [start, end] inclusive, one market day at a time."""
    from .agent_runner import run_all_agents

    dates = list(iter_dates(start_iso, end_iso))
    logger.info(f"=== BACKTEST {start_iso}..{end_iso} "
                f"({len(dates)} calendar days) agents={agent_ids or 'ALL'} ===")
    for i, d in enumerate(dates, 1):
        logger.info(f"--- Backtest day {i}/{len(dates)}: {d} ---")
        run_all_agents(d, agent_ids=agent_ids)
    logger.info("=== BACKTEST COMPLETE ===")
