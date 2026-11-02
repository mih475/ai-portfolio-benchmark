"""
Offline tests for the live paper-trading runner's pure logic — stdlib only.

The ledger/meta/row helpers in live_runner.py do the bookkeeping that must stay
correct across separate daily processes (inception is set once; rows are
idempotent per date; a row reads the persisted state the same way the simulator
wrote it). They touch no network or LLM, so we load the module by path and
exercise them directly. The network parts (market-day check, run_all_agents,
SPY fetch) are not tested here.

Run:  python3 v2/tests/test_live_runner.py
"""

import importlib.util
import sys
import traceback
from pathlib import Path

V2 = Path(__file__).resolve().parent.parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lr = _load(V2 / "live_runner.py", "live_runner_standalone")

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


def _state(**kw):
    base = {"starting_capital": 10000.0, "last_value": 10000.0, "cash": 10000.0,
            "daily_returns": [], "max_drawdown": 0.0, "positions": {},
            "pending_orders": []}
    base.update(kw)
    return base


@test
def t_inception_set_once():
    m = lr.init_meta({}, "2026-11-03", ["claude_aggressive"])
    assert m["inception"] == "2026-11-03" and m["last_run"] == "2026-11-03"
    m2 = lr.init_meta(m, "2026-11-10", ["other"])
    # inception + agents are sticky; last_run advances
    assert m2["inception"] == "2026-11-03"
    assert m2["agents"] == ["claude_aggressive"]
    assert m2["last_run"] == "2026-11-10"


@test
def t_build_row_basic_and_cum():
    st = _state(last_value=10250.0, cash=5125.0,
                daily_returns=[0.01, 0.005], max_drawdown=0.02,
                positions={"ABC": {}, "XYZ": {}},
                pending_orders=[{"action": "BUY", "ticker": "DEF", "allocation_pct": 15}])
    hist = {"ca": {"transactions_today": [
        {"action": "BUY", "ticker": "ABC", "shares": 10.5, "price": 12.3, "trigger": "AGENT"}]}}
    row = lr.build_row("2026-11-04", {"ca": st}, hist, {"starting_capital": 10000, "cash": 10110.0})
    a = row["agents"]["ca"]
    assert a["value"] == 10250.0
    assert a["cum_ret"] == round(10250.0 / 10000.0 - 1, 6)
    assert a["day_ret"] == 0.005
    assert a["cash_pct"] == round(100 * 5125.0 / 10250.0, 1)
    assert a["n_positions"] == 2 and a["positions"] == ["ABC", "XYZ"]
    assert a["fills_today"][0]["ticker"] == "ABC"
    assert a["pending_next_open"][0]["ticker"] == "DEF"
    assert row["spy"]["cum_ret"] == round(10110.0 / 10000.0 - 1, 6)


@test
def t_build_row_missing_last_value_falls_back_to_cash():
    st = _state(cash=9900.0)
    st.pop("last_value")
    row = lr.build_row("2026-11-04", {"ca": st}, {}, None)
    a = row["agents"]["ca"]
    assert a["value"] == 9900.0           # cash used as value
    assert a["cash_pct"] == 100.0
    assert "spy" not in row               # no spy state => no spy key


@test
def t_cash_pct_zero_value_guarded():
    st = _state(last_value=0.0, cash=0.0)
    row = lr.build_row("2026-11-04", {"ca": st}, {}, None)
    assert row["agents"]["ca"]["cash_pct"] == 0.0   # no ZeroDivisionError


@test
def t_upsert_idempotent_and_sorted():
    r1 = lr.build_row("2026-11-04", {"ca": _state()}, {}, None)
    r1b = lr.build_row("2026-11-04", {"ca": _state(last_value=12345.0)}, {}, None)
    r2 = lr.build_row("2026-11-03", {"ca": _state()}, {}, None)
    rows = lr.upsert_row([], r1)
    rows = lr.upsert_row(rows, r1b)       # same date -> replace, not duplicate
    assert len(rows) == 1 and rows[0]["agents"]["ca"]["value"] == 12345.0
    rows = lr.upsert_row(rows, r2)        # earlier date -> sorted ahead
    assert [r["date"] for r in rows] == ["2026-11-03", "2026-11-04"]


@test
def t_render_markdown_with_and_without_spy():
    meta = lr.init_meta({}, "2026-11-03", ["ca", "random_control"])
    rows = [
        lr.build_row("2026-11-03", {"ca": _state(last_value=10100.0, daily_returns=[0.01])},
                     {}, {"starting_capital": 10000, "cash": 10050.0}),
        lr.build_row("2026-11-04", {"ca": _state(last_value=10000.0, daily_returns=[-0.0099])},
                     {}, None),   # a day with no SPY state still renders
    ]
    md = lr.render_markdown(meta, rows, "ca")
    assert "Live paper-trading ledger" in md
    assert "Inception: 2026-11-03" in md
    assert "vs SPY" in md
    assert "Latest run — 2026-11-04" in md
    # row with SPY shows a vs-SPY number; row without shows a dash
    assert "| —" in md


@test
def t_load_json_missing_returns_default():
    assert lr.load_json(V2 / "does_not_exist_xyz.json", []) == []
    assert lr.load_json(V2 / "does_not_exist_xyz.json", {}) == {}


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
