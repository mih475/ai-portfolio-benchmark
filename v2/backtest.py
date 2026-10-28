"""
Multi-day backtest driver.

Runs the daily loop over a date range *in order, in one process*, so each day's
persisted portfolio state carries into the next (pending orders fill the next
market day, stops/marks accumulate). Non-market days are skipped by
run_all_agents itself, so we can just iterate calendar days.

`iter_dates` is kept import-light (stdlib only) so it's unit-testable without
pulling in the heavy runner.
"""

import json
import logging
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def buy_hold_metrics(closes, capital: float = 10000.0) -> dict:
    """Buy-and-hold metrics from a list of daily closes (pure, stdlib).

    Returns final value, cumulative return, max drawdown (peak-to-trough on the
    equity curve) and the daily returns series — the same fields the summarizer
    reads from an agent's state, so a benchmark renders as just another row.
    """
    closes = [float(c) for c in closes if c is not None and float(c) > 0]
    if len(closes) < 2:
        return {"final": capital, "cum": 0.0, "mdd": 0.0, "daily_returns": []}
    shares = capital / closes[0]
    equity = [shares * c for c in closes]
    daily = [(equity[i] - equity[i - 1]) / equity[i - 1] for i in range(1, len(equity))]
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak if peak > 0 else 0.0)
    final = equity[-1]
    return {"final": final, "cum": (final - capital) / capital,
            "mdd": mdd, "daily_returns": daily}


def write_benchmark(start_iso: str, end_iso: str, out_dir, ticker: str = "SPY",
                    capital: float = 10000.0):
    """Fetch `ticker` closes over [start, end] and write a buy-and-hold row the
    summarizer will include. Best-effort: on any failure, writes nothing."""
    try:
        import pandas as pd  # noqa: F401
        from .price_provider import window_download

        start = date.fromisoformat(start_iso)
        end = date.fromisoformat(end_iso)
        data = window_download([ticker], as_of=end, period="3mo")
        if data is None or getattr(data, "empty", True):
            logger.warning(f"benchmark {ticker}: no data, skipping")
            return
        close = data["Close"]
        if hasattr(close, "columns"):           # multi-index frame
            close = close[ticker]
        close = close[(close.index.date >= start) & (close.index.date <= end)]
        closes = [float(x) for x in close.dropna().tolist()]
        m = buy_hold_metrics(closes, capital)
        state = {
            "agent_id": f"{ticker.lower()}_buy_hold",
            "starting_capital": capital,
            "cash": round(m["final"], 2),       # final value as cash => summarizer values it correctly
            "positions": {},
            "max_drawdown": m["mdd"],
            "daily_returns": [round(r, 6) for r in m["daily_returns"]],
        }
        out = Path(out_dir) / f"{ticker.lower()}_buy_hold.json"
        out.write_text(json.dumps(state, indent=2))
        logger.info(f"benchmark {ticker} buy&hold: {m['cum']*100:+.2f}% over {start}..{end}")
    except Exception as e:
        logger.warning(f"benchmark {ticker} computation failed: {e}")


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

    # Write a SPY buy-and-hold benchmark row for the same window so the
    # leaderboard answers "beat the market?" not just "beat the random control?".
    from .config import PORTFOLIOS_DIR, STARTING_CAPITAL
    write_benchmark(start_iso, end_iso, PORTFOLIOS_DIR, ticker="SPY",
                    capital=STARTING_CAPITAL)
    logger.info("=== BACKTEST COMPLETE ===")
