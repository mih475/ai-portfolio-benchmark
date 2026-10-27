"""
Offline tests for price_provider date logic — stdlib only.

We can't hit yfinance in CI/sandbox, so we inject a fake downloader that records
the kwargs it was called with, and assert the live-vs-historical decision and
the date-window math. The DataFrame-parsing in day_ohlc needs pandas and is
validated by a live/historical smoke run instead.

Run:  python3 v2/tests/test_price_provider.py
"""

import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import price_provider as pp  # noqa: E402


class Recorder:
    """Fake yf.download: records call kwargs, returns a sentinel."""
    def __init__(self):
        self.calls = []
    def __call__(self, tickers, **kw):
        self.calls.append({"tickers": tickers, **kw})
        return "DATAFRAME_SENTINEL"


TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


@test
def t_is_live_rules():
    assert pp.is_live(None) is True
    assert pp.is_live(date.today()) is True
    assert pp.is_live(date.today() + timedelta(days=5)) is True
    assert pp.is_live(date(2020, 1, 2)) is False


@test
def t_live_uses_period_not_dates():
    rec = Recorder()
    pp.window_download(["SPY", "XLK"], as_of=None, period="6mo", _downloader=rec)
    call = rec.calls[0]
    assert call.get("period") == "6mo", call
    assert "start" not in call and "end" not in call, call


@test
def t_today_is_live():
    rec = Recorder()
    pp.window_download(["SPY"], as_of=date.today(), period="5d", _downloader=rec)
    assert rec.calls[0].get("period") == "5d"
    assert "start" not in rec.calls[0]


@test
def t_past_uses_start_end_window():
    rec = Recorder()
    as_of = date(2026, 4, 7)
    pp.window_download(["SPY"], as_of=as_of, period="6mo", _downloader=rec)
    call = rec.calls[0]
    assert "period" not in call, call
    # end is exclusive -> as_of + 1 day
    assert call["end"] == (as_of + timedelta(days=1)).isoformat(), call
    # start = as_of - lookback(6mo = 190d)
    assert call["start"] == (as_of - timedelta(days=190)).isoformat(), call


@test
def t_past_lookback_varies_by_period():
    rec = Recorder()
    as_of = date(2026, 4, 7)
    pp.window_download(["SPY"], as_of=as_of, period="5d", _downloader=rec)
    assert rec.calls[0]["start"] == (as_of - timedelta(days=10)).isoformat()


@test
def t_day_ohlc_empty_tickers():
    assert pp.day_ohlc([], as_of=date(2026, 4, 7)) == {}


# ── retry / backoff ────────────────────────────────────────────────────────

class FlakyDownloader:
    """Raises `fails` times, then returns the sentinel."""
    def __init__(self, fails):
        self.fails = fails
        self.calls = 0
    def __call__(self, tickers, **kw):
        self.calls += 1
        if self.calls <= self.fails:
            raise RuntimeError("rate limited")
        return "DATAFRAME_SENTINEL"


@test
def t_retry_recovers_after_transient_failures():
    flaky = FlakyDownloader(fails=2)
    out = pp.window_download(["SPY"], as_of=None, period="6mo",
                             _downloader=flaky, _sleep=lambda *_: None)
    assert out == "DATAFRAME_SENTINEL"
    assert flaky.calls == 3, flaky.calls   # 2 failures + 1 success


@test
def t_retry_exhausts_and_returns_last():
    always = FlakyDownloader(fails=99)
    out = pp.window_download(["SPY"], as_of=None, period="6mo",
                             _downloader=always, _sleep=lambda *_: None)
    assert out is None                      # all attempts raised -> last is None
    assert always.calls == pp._RETRIES + 1  # first try + retries


# ── cache key ──────────────────────────────────────────────────────────────

@test
def t_cache_key_order_independent():
    k1 = pp._cache_key(["A", "B", "C"], date(2026, 4, 7), "6mo", "1d")
    k2 = pp._cache_key(["C", "A", "B"], date(2026, 4, 7), "6mo", "1d")
    assert k1 == k2


@test
def t_cache_key_varies_by_date_and_period():
    base = pp._cache_key(["A"], date(2026, 4, 7), "6mo", "1d")
    assert base != pp._cache_key(["A"], date(2026, 4, 8), "6mo", "1d")
    assert base != pp._cache_key(["A"], date(2026, 4, 7), "5d", "1d")


@test
def t_live_window_never_cached(tmp=None):
    # A live (today) call must not touch the cache at all.
    import tempfile
    from pathlib import Path as _P
    orig = pp.CACHE_DIR
    pp.CACHE_DIR = _P(tempfile.mkdtemp()) / "pc"
    try:
        rec = Recorder()
        pp.window_download(["SPY"], as_of=date.today(), period="5d",
                           _downloader=rec, _sleep=lambda *_: None)
        assert not pp.CACHE_DIR.exists(), "live path created a cache dir"
    finally:
        pp.CACHE_DIR = orig


def main():
    passed = failed = 0
    for fn in TESTS:
        try:
            fn(); passed += 1; print(f"  PASS  {fn.__name__}")
        except Exception:
            failed += 1; print(f"  FAIL  {fn.__name__}"); traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed, {len(TESTS)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
