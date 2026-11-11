"""
Multi-day backtest driver.

Runs the daily loop over a date range *in order, in one process*, so each day's
persisted portfolio state carries into the next (pending orders fill the next
NYSE session, stops/marks accumulate). The historical simulation MUST iterate
only exchange sessions; invoking the snapshot on a Saturday or market holiday
would fail exact-date data checks after wasting model API calls.

`iter_dates` remains a stdlib-only inclusive calendar-range helper for existing
callers. `iter_market_dates` uses the authoritative NYSE exchange calendar
lazily and is injection-testable without pandas installed in offline CI.
"""

import json
import logging
import os
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
                    capital: float = 10000.0, period: str = "3mo"):
    """Fetch `ticker` closes over [start, end] and write a buy-and-hold row the
    summarizer will include. Best-effort: on any failure, writes nothing.

    `period` is the yfinance lookback window to pull before slicing to
    [start, end]; it must comfortably cover that span (a single backtest quarter
    fits in 3mo; the live runner passes a longer period as the paper-trade grows).
    """
    try:
        import pandas as pd  # noqa: F401
        from .price_provider import window_download

        start = date.fromisoformat(start_iso)
        end = date.fromisoformat(end_iso)
        data = window_download([ticker], as_of=end, period=period)
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


def iter_market_dates(start_iso: str, end_iso: str, _schedule=None):
    """Yield only NYSE sessions within an inclusive date range.

    Uses pandas_market_calendars on actual runs (including Good Friday and
    irregular market closures), never a weekday-only approximation. Tests
    inject a fake schedule to keep the ordinary CI suite dependency-free.
    A missing exchange calendar is an explicit failure; never fall back to
    calendar days or silently include closed-market dates.
    """
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    if end < start:
        raise ValueError(f"end_date {end_iso} is before start_date {start_iso}")
    if _schedule is None:
        import pandas_market_calendars as mcal
        nyse = mcal.get_calendar("NYSE")
        sessions = nyse.schedule(start_date=start_iso, end_date=end_iso).index
    else:
        sessions = _schedule(start_iso, end_iso)
    last = None
    for session in sessions:
        day = session.date() if hasattr(session, "date") else date.fromisoformat(str(session))
        if not start <= day <= end:
            raise ValueError(f"NYSE calendar returned out-of-range date {day}")
        iso = day.isoformat()
        if last is not None and iso <= last:
            raise ValueError(f"NYSE calendar returned duplicate/unsorted session {iso}")
        last = iso
        yield iso


def run_backtest(start_iso: str, end_iso: str, agent_ids=None):
    """Run the roster across [start, end] inclusive, one NYSE session at a time."""
    from .agent_runner import run_all_agents

    dates = list(iter_market_dates(start_iso, end_iso))
    if not dates:
        raise ValueError(f"No NYSE trading sessions in range {start_iso}..{end_iso}")
    logger.info(f"=== BACKTEST {start_iso}..{end_iso} "
                f"({len(dates)} NYSE trading sessions) agents={agent_ids or 'ALL'} ===")
    failures = 0
    for i, d in enumerate(dates, 1):
        logger.info(f"--- Backtest day {i}/{len(dates)}: {d} ---")
        try:
            run_all_agents(d, agent_ids=agent_ids)
        except Exception as e:
            # In strict mode, a missing mark/stop/open invalidates the whole
            # result. Fail the GitHub job instead of publishing false returns.
            if os.getenv("BACKTEST_STRICT_PRICES") == "1":
                logger.exception("Backtest invalid on %s; stopping without a verdict", d)
                raise
            failures += 1
            logger.error(f"Day {d} failed, continuing: {e}")
    if failures:
        logger.warning(f"{failures}/{len(dates)} day(s) errored during the backtest.")

    # Write buy-and-hold benchmark rows for the same window. SPY (large-cap) is
    # the headline "beat the market?" line; IWM (Russell 2000) is the honest
    # like-for-like benchmark, since the agents trade a $3-$50 small-cap universe
    # and much of any "edge" vs SPY is just small-cap beta.
    from .config import PORTFOLIOS_DIR, STARTING_CAPITAL
    write_benchmark(start_iso, end_iso, PORTFOLIOS_DIR, ticker="SPY",
                    capital=STARTING_CAPITAL)
    write_benchmark(start_iso, end_iso, PORTFOLIOS_DIR, ticker="IWM",
                    capital=STARTING_CAPITAL)
    logger.info("=== BACKTEST COMPLETE ===")
