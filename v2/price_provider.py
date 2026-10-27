"""
Date-aware price access for the MIH snapshot and the simulator.

The original V2 code always called `yf.download(..., period=...)`, which returns
the *latest* bar regardless of the requested simulation date — so `--run-date`
was cosmetic and historical replay was impossible (see BACKLOG.md #1).

This module centralizes price fetching behind two helpers that understand an
`as_of` date:

- `window_download(...)` — a lookback window of bars *ending at* `as_of`.
- `day_ohlc(...)`        — the single O/H/L/C bar *on* `as_of`.

Safety: when `as_of` is None or today/future, both fall back to the exact
`period=`-based live behaviour that the production daily cron already uses and
that we validated with a live smoke run. Only a *past* `as_of` takes the new
historical (`start`/`end`) path. So enabling backtests cannot change how the
live run behaves.

yfinance / pandas are imported lazily so importing this module never requires
them (keeps the offline test suite dependency-free). The downloader is
injectable (`_downloader`) purely so the date logic can be unit-tested without
network access.
"""

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# Approximate calendar-day lookback for each yfinance `period` string we use.
# Generous on the long end so rolling windows (e.g. SMA-200) have enough bars.
_PERIOD_DAYS = {
    "1d": 6, "2d": 7, "5d": 10, "1mo": 35,
    "3mo": 100, "6mo": 190, "1y": 372,
}


def is_live(as_of) -> bool:
    """True when we should use the live 'latest bar' path.

    None, today, or a future date => live. A past date => historical replay.
    """
    return as_of is None or as_of >= date.today()


def _resolve_downloader(_downloader):
    if _downloader is not None:
        return _downloader
    import yfinance as yf  # lazy; only needed for real fetches
    return yf.download


def window_download(tickers, as_of=None, period="6mo", interval="1d", _downloader=None):
    """Return a yfinance DataFrame of bars for `tickers`.

    Live (`as_of` None/today/future): the last `period` of data.
    Historical (past `as_of`): a window of comparable length ending at `as_of`
    (inclusive). Callers that take `.iloc[-1]` then get the as-of bar for free.
    """
    download = _resolve_downloader(_downloader)
    if is_live(as_of):
        return download(tickers, period=period, interval=interval, progress=False)

    lookback = _PERIOD_DAYS.get(period, 190)
    start = (as_of - timedelta(days=lookback)).isoformat()
    end = (as_of + timedelta(days=1)).isoformat()   # yfinance `end` is exclusive
    logger.info(f"Historical window {start}..{as_of} ({interval}) for "
                f"{len(tickers) if hasattr(tickers, '__len__') else '?'} tickers")
    return download(tickers, start=start, end=end, interval=interval, progress=False)


def day_ohlc(tickers, as_of=None, _downloader=None) -> dict:
    """Return {ticker: {open, high, low, close}} for the bar on `as_of`.

    Live: today's (latest) bar. Historical: the bar on `as_of`. Non-trading
    `as_of` dates resolve to the last available bar in the small surrounding
    window. Returns {} for no tickers or on failure (never raises).
    """
    tickers = list(tickers)
    if not tickers:
        return {}
    try:
        import pandas as pd  # noqa: F401  (used indirectly via DataFrame API)
        # A short window guarantees at least one bar even if as_of is a holiday.
        data = window_download(tickers, as_of=as_of, period="5d", _downloader=_downloader)
        if data is None or getattr(data, "empty", True):
            return {}

        out = {}
        multi = len(tickers) > 1
        for tkr in tickers:
            try:
                if multi:
                    row = data.xs(tkr, level=1, axis=1).iloc[-1]
                else:
                    row = data.iloc[-1]
                out[tkr] = {
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                }
            except Exception:
                continue
        return out
    except Exception as e:
        logger.error(f"day_ohlc failed: {e}")
        return {}
