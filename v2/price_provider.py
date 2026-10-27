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

import hashlib
import logging
import os
import random
import time
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Approximate calendar-day lookback for each yfinance `period` string we use.
# Generous on the long end so rolling windows (e.g. SMA-200) have enough bars.
_PERIOD_DAYS = {
    "1d": 6, "2d": 7, "5d": 10, "1mo": 35,
    "3mo": 100, "6mo": 190, "1y": 372,
}

# On-disk cache for HISTORICAL price windows. Historical bars never change, so
# caching makes backtests reproducible and stops repeated runs from re-hitting
# (and getting rate-limited by) Yahoo. Live/today windows are never cached.
CACHE_DIR = Path(__file__).parent / "data" / "price_cache"
_RETRIES = 3           # extra attempts after the first on transient failures
_RETRY_BASE_DELAY = 2.0  # seconds; exponential backoff with jitter


def _cache_enabled() -> bool:
    # Opt-out via PRICE_CACHE=0/false/no.
    return os.getenv("PRICE_CACHE", "1").lower() not in ("0", "false", "no")


def _cache_key(tickers, as_of, period, interval) -> str:
    norm = ",".join(sorted(set(tickers)))
    raw = f"{norm}|{as_of}|{period}|{interval}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.pkl"


def _cache_load(key: str):
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        import pandas as pd
        return pd.read_pickle(path)
    except Exception as e:
        logger.warning(f"price cache read failed ({key}): {e}")
        return None


def _cache_store(key: str, data) -> None:
    # Only persist real DataFrames (anything with to_pickle); never create the
    # cache dir for sentinels/None (keeps tests and failures clean).
    if not hasattr(data, "to_pickle"):
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data.to_pickle(_cache_path(key))
    except Exception as e:
        logger.warning(f"price cache write failed ({key}): {e}")


def _download_with_retry(download, tickers, kwargs, retries=_RETRIES, sleep=None):
    """Call `download(tickers, **kwargs)` with retry/backoff on transient failures.

    Treats an exception OR an empty/None result as transient (Yahoo frequently
    rate-limits shared IPs, returning empty). Returns the last result (possibly
    empty) after exhausting retries so callers' existing empty-guards still work.
    """
    sleep = sleep or time.sleep
    last = None
    for attempt in range(retries + 1):
        try:
            data = download(tickers, **kwargs)
            if data is not None and not getattr(data, "empty", False):
                return data
            last = data
            logger.warning(f"price download empty (attempt {attempt + 1}/{retries + 1})")
        except Exception as e:
            last = None
            logger.warning(f"price download error (attempt {attempt + 1}/{retries + 1}): {e}")
        if attempt < retries:
            sleep(_RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1))
    return last


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


def window_download(tickers, as_of=None, period="6mo", interval="1d",
                    _downloader=None, _sleep=None):
    """Return a yfinance DataFrame of bars for `tickers`.

    Live (`as_of` None/today/future): the last `period` of data.
    Historical (past `as_of`): a window of comparable length ending at `as_of`
    (inclusive). Callers that take `.iloc[-1]` then get the as-of bar for free.

    Transient Yahoo failures are retried with backoff. Historical windows are
    read from / written to an on-disk cache (never live windows).
    """
    download = _resolve_downloader(_downloader)
    live = is_live(as_of)

    if live:
        kwargs = dict(period=period, interval=interval, progress=False)
        return _download_with_retry(download, tickers, kwargs, sleep=_sleep)

    # Historical: try cache first, then fetch + store.
    key = _cache_key(tickers, as_of, period, interval) if _cache_enabled() else None
    if key is not None:
        cached = _cache_load(key)
        if cached is not None:
            logger.info(f"price cache hit ({key}) for {as_of} {period}")
            return cached

    lookback = _PERIOD_DAYS.get(period, 190)
    start = (as_of - timedelta(days=lookback)).isoformat()
    end = (as_of + timedelta(days=1)).isoformat()   # yfinance `end` is exclusive
    logger.info(f"Historical window {start}..{as_of} ({interval}) for "
                f"{len(tickers) if hasattr(tickers, '__len__') else '?'} tickers")
    kwargs = dict(start=start, end=end, interval=interval, progress=False)
    data = _download_with_retry(download, tickers, kwargs, sleep=_sleep)
    if key is not None:
        _cache_store(key, data)
    return data


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
