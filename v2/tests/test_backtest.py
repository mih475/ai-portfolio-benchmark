"""
Offline tests for backtest date iteration and the results summary — stdlib only.

Both modules are loaded by path to avoid the package __init__ (which pulls in
network deps). iter_dates and the summarizer use only the stdlib.

Run:  python3 v2/tests/test_backtest.py
"""

import importlib.util
import json
import sys
import tempfile
import traceback
from pathlib import Path

V2 = Path(__file__).resolve().parent.parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bt = _load(V2 / "backtest.py", "backtest_standalone")
summ = _load(V2 / "scripts" / "summarize_backtest.py", "summarize_standalone")

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


@test
def t_iter_dates_inclusive():
    out = list(bt.iter_dates("2026-04-06", "2026-04-10"))
    assert out == ["2026-04-06", "2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10"], out


@test
def t_iter_dates_single_day():
    assert list(bt.iter_dates("2026-04-07", "2026-04-07")) == ["2026-04-07"]


@test
def t_iter_dates_rejects_reversed():
    try:
        list(bt.iter_dates("2026-04-10", "2026-04-06"))
        assert False, "should have raised"
    except ValueError:
        pass


@test
def t_agent_metrics_computes_value_and_return():
    state = {
        "agent_id": "gemini_balanced",
        "starting_capital": 10000.0,
        "cash": 5000.0,
        "max_drawdown": 0.08,
        "daily_returns": [0.0, 0.01, -0.02, 0.03, 0.0],
        "positions": {
            "ABC": {"shares": 100, "current_price": 40.0},  # 4000
            "XYZ": {"shares": 50, "current_price": 30.0},   # 1500
        },
    }
    m = summ.agent_metrics(state)
    assert m["value"] == 10500.0, m          # 5000 + 4000 + 1500
    assert m["cum_return_pct"] == 5.0, m     # (10500-10000)/10000
    assert m["max_drawdown_pct"] == 8.0, m
    assert m["days"] == 5 and m["positions"] == 2, m


@test
def t_summarize_sorts_and_skips_history():
    d = Path(tempfile.mkdtemp())
    (d / "a.json").write_text(json.dumps({
        "agent_id": "winner", "starting_capital": 10000, "cash": 12000, "positions": {}}))
    (d / "b.json").write_text(json.dumps({
        "agent_id": "loser", "starting_capital": 10000, "cash": 9000, "positions": {}}))
    (d / "a_history.json").write_text(json.dumps([{"x": 1}]))  # must be ignored
    rows = summ.summarize(str(d))
    assert [r["agent"] for r in rows] == ["winner", "loser"], rows
    md = summ.render(rows)
    assert "Leaderboard" in md and "winner" in md


@test
def t_buy_hold_metrics():
    # Up 10% then down to +5% overall, with a dip in the middle.
    closes = [100.0, 110.0, 99.0, 105.0]
    m = bt.buy_hold_metrics(closes, capital=10000.0)
    assert round(m["final"], 2) == 10500.0, m          # 105/100 * 10000
    assert round(m["cum"] * 100, 2) == 5.0, m
    # peak 11000 -> trough 9900 => max drawdown 10%
    assert round(m["mdd"] * 100, 2) == 10.0, m
    assert len(m["daily_returns"]) == 3


@test
def t_buy_hold_handles_degenerate():
    assert bt.buy_hold_metrics([], 10000)["cum"] == 0.0
    assert bt.buy_hold_metrics([100.0], 10000)["final"] == 10000


@test
def t_benchmark_row_renders_in_summary():
    # A written benchmark state is picked up and ranked like any agent.
    d = Path(tempfile.mkdtemp())
    (d / "spy_buy_hold.json").write_text(json.dumps({
        "agent_id": "spy_buy_hold", "starting_capital": 10000, "cash": 10400,
        "positions": {}, "max_drawdown": 0.03, "daily_returns": [0.01, -0.005, 0.02]}))
    (d / "agent.json").write_text(json.dumps({
        "agent_id": "gemini_balanced", "starting_capital": 10000, "cash": 10200,
        "positions": {}, "max_drawdown": 0.015, "daily_returns": [0.01, 0.01]}))
    rows = summ.summarize(str(d))
    assert rows[0]["agent"] == "spy_buy_hold", rows   # higher return ranks first
    md = summ.render(rows)
    assert "spy_buy_hold" in md


@test
def t_no_activity_flagged():
    # An agent that ran days but never moved / held nothing is flagged.
    flat = {"agent": "stuck", "value": 10000.0, "cum_return_pct": 0.0,
            "max_drawdown_pct": 0.0, "days": 5, "positions": 0}
    live = {"agent": "active", "value": 10100.0, "cum_return_pct": 1.0,
            "max_drawdown_pct": 0.5, "days": 5, "positions": 2}
    assert summ._no_activity(flat) is True
    assert summ._no_activity(live) is False
    md = summ.render([live, flat])
    assert "no activity" in md


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
