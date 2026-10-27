"""
Offline tests for the random control agent — stdlib only.

Pins the fix where the control could never trade because its hardcoded big-cap
universe was all outside the enforced $3-$50 price band. It should now buy from
the supplied daily watchlist and only ever name tickers from that set.

Run:  python3 v2/tests/test_random_agent.py
"""

import importlib.util
import random
import sys
import traceback
from pathlib import Path

V2 = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("random_agent_standalone", V2 / "random_agent.py")
ra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ra)

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


def empty_portfolio():
    return {"cash": 10000.0, "positions": [], "portfolio_value": 10000.0}


@test
def t_buys_only_from_supplied_universe():
    random.seed(1)
    wl = ["SOFI", "PLUG", "RIVN", "CHPT", "HOOD"]
    out = ra.execute_random_trades(empty_portfolio(), universe=wl)
    buys = [t for t in out["trades"] if t["action"] == "BUY"]
    assert buys, "expected at least one buy from a fresh portfolio with cash"
    for b in buys:
        assert b["ticker"] in wl, b


@test
def t_falls_back_when_no_universe():
    random.seed(2)
    out = ra.execute_random_trades(empty_portfolio(), universe=None)
    buys = [t for t in out["trades"] if t["action"] == "BUY"]
    assert buys
    for b in buys:
        assert b["ticker"] in ra.FALLBACK_UNIVERSE, b


@test
def t_allocations_within_bounds_and_have_stops():
    random.seed(3)
    out = ra.execute_random_trades(empty_portfolio(), universe=["SOFI", "PLUG", "RIVN"])
    for b in [t for t in out["trades"] if t["action"] == "BUY"]:
        assert 5.0 <= b["allocation_pct"] <= 25.0, b
        assert b["stop_loss_pct"] > 0, b   # every buy carries a stop


@test
def t_schema_shape():
    random.seed(4)
    out = ra.execute_random_trades(empty_portfolio(), universe=["SOFI"])
    assert set(out.keys()) >= {"trades", "daily_notes", "portfolio_review"}
    assert isinstance(out["trades"], list)


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
