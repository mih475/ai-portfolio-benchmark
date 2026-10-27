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
