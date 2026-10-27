"""
Offline test for fred_server.execute point-in-time windowing — stdlib only.

Injects a fake Fred client (no network, no fredapi/pandas) that records the
(start, end) passed to get_series and returns a tiny fake series. Asserts that
`as_of` ends the window at that date, and that the live path ends ~now.

Run:  python3 v2/tests/test_fred_asof.py
"""

import importlib.util
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

# Load fred_server.py directly by path. Importing it via the mcp_servers package
# would run the package __init__, which imports sibling servers that need httpx
# (not available in the offline test env). fred_server has no relative imports,
# so loading it standalone is safe.
_FRED_PATH = Path(__file__).resolve().parent.parent / "mcp_servers" / "fred_server.py"
_spec = importlib.util.spec_from_file_location("fred_server_standalone", _FRED_PATH)
fred = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fred)


class _FakeIndex(list):
    def __getitem__(self, i):
        v = super().__getitem__(i)
        return v


class FakeSeries:
    """Minimal stand-in for a pandas Series as execute() uses it."""
    def __init__(self, value, idx_date):
        self._value = value
        self._idx_date = idx_date
    def __len__(self):
        return 1
    def dropna(self):
        return self
    @property
    def iloc(self):
        return [self._value]  # iloc[-1] -> value
    @property
    def index(self):
        class _Idx:
            def __init__(self, d): self._d = d
            def __getitem__(self, i): return self
            def strftime(self, fmt): return self._d.strftime(fmt)
        return _Idx(self._idx_date)


class FakeFred:
    def __init__(self):
        self.calls = []
    def get_series(self, series_id, start, end):
        self.calls.append({"series_id": series_id, "start": start, "end": end})
        return FakeSeries(4.25, end if isinstance(end, datetime) else datetime(2026, 4, 7))


TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


@test
def t_asof_date_sets_end():
    fred._fred = FakeFred()
    fred.execute(["DGS10"], as_of=date(2026, 4, 7))
    call = fred._fred.calls[0]
    assert call["end"] == datetime(2026, 4, 7), call["end"]
    assert call["start"] == datetime(2026, 4, 7) - fred.timedelta(days=45), call["start"]


@test
def t_asof_isostring_accepted():
    fred._fred = FakeFred()
    fred.execute(["DGS10"], as_of="2026-04-07")
    assert fred._fred.calls[0]["end"] == datetime(2026, 4, 7)


@test
def t_live_ends_near_now():
    fred._fred = FakeFred()
    fred.execute(["DGS10"], as_of=None)
    end = fred._fred.calls[0]["end"]
    assert abs((datetime.now() - end).total_seconds()) < 5


@test
def t_result_shape():
    fred._fred = FakeFred()
    out = fred.execute(["DGS10"], as_of=date(2026, 4, 7))
    assert "indicators" in out and "summary" in out
    assert out["indicators"]["DGS10"]["value"] == 4.25


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
