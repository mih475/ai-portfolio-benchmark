"""
Offline tests for PortfolioSimulator — stdlib only, no network, no pip deps.

Run:  python3 v2/tests/test_portfolio_simulator.py
Exit code 0 = all passed. Used by CI (.github/workflows/tests.yml).

The simulator is the "Code is Law" firewall; these tests pin its behaviour so
future changes can't silently break T+1 execution, slippage, sizing caps,
validation, stop/TP triggers, or state persistence.
"""

import os
import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

# Import the simulator directly (it depends only on the stdlib).
V2_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_DIR))
from portfolio_simulator import PortfolioSimulator, Position  # noqa: E402


def make_rules(**overrides):
    """A fixed rules object so tests don't drift when config.py changes."""
    base = dict(
        min_stock_price=3.00,
        max_stock_price=50.00,
        max_position_pct=0.25,
        min_position_pct=0.05,
        max_positions=15,
        max_daily_buys=3,
        slippage_pct=0.001,
        fractional_shares=True,
        long_only=True,
        stop_loss_required=True,
        execution_model="T+1_OPEN",
        stop_trigger_model="OHLC",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def new_sim(capital=10_000.0, rules=None):
    d = Path(tempfile.mkdtemp())
    return PortfolioSimulator("test_agent", capital, rules or make_rules(), d)


# ─────────────────────────────────────────────────────────────────────────
# Test registry
# ─────────────────────────────────────────────────────────────────────────
TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn

def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


# ── Execution & slippage ──────────────────────────────────────────────────

@test
def t_buy_fills_at_open_with_slippage():
    sim = new_sim()
    sim.submit_orders([{"action": "BUY", "ticker": "ABC", "allocation_pct": 20,
                        "stop_loss_pct": 10}], "2026-07-01")
    assert len(sim.pending_orders) == 1
    sim.execute_pending_orders({"ABC": 10.00}, "2026-07-02")
    assert "ABC" in sim.positions
    pos = sim.positions["ABC"]
    assert approx(pos.entry_price, 10.00 * 1.001), pos.entry_price      # buy slippage up
    # 20% of 10k target / fill price
    assert approx(pos.shares, 2000.0 / (10.00 * 1.001), tol=1e-4), pos.shares
    assert approx(pos.stop_loss_price, round(10.00 * 1.001 * 0.90, 4)), pos.stop_loss_price
    assert sim.cash < 10_000 and sim.cash > 7_900


@test
def t_sell_receives_open_minus_slippage():
    sim = new_sim()
    sim.positions["XYZ"] = Position("XYZ", shares=100, entry_price=10.0,
                                    entry_date="2026-07-01", stop_loss_price=9.0,
                                    current_price=10.0)
    sim.cash = 0.0
    sim.submit_orders([{"action": "SELL", "ticker": "XYZ", "allocation_pct": 100}], "2026-07-01")
    sim.execute_pending_orders({"XYZ": 12.00}, "2026-07-02")
    assert "XYZ" not in sim.positions
    assert approx(sim.cash, 100 * 12.00 * (1 - 0.001)), sim.cash          # sell slippage down


# ── Validation firewall ───────────────────────────────────────────────────

@test
def t_reject_below_min_allocation():
    sim = new_sim()
    res = sim.submit_orders([{"action": "BUY", "ticker": "ABC", "allocation_pct": 2,
                              "stop_loss_pct": 10}], "2026-07-01")
    assert res[0]["status"] == "REJECTED"
    assert sim.pending_orders == []


@test
def t_cap_above_max_allocation():
    sim = new_sim()
    sim.submit_orders([{"action": "BUY", "ticker": "ABC", "allocation_pct": 80,
                        "stop_loss_pct": 10}], "2026-07-01")
    assert sim.pending_orders[0].allocation_pct == 25        # capped, not rejected


@test
def t_max_daily_buys():
    sim = new_sim()
    trades = [{"action": "BUY", "ticker": f"T{i}", "allocation_pct": 6,
               "stop_loss_pct": 10} for i in range(4)]
    res = sim.submit_orders(trades, "2026-07-01")
    accepted = [r for r in res if r["status"] == "ACCEPTED"]
    assert len(accepted) == 3, len(accepted)
    assert res[3]["status"] == "REJECTED"


@test
def t_max_positions():
    sim = new_sim()
    for i in range(15):
        sim.positions[f"P{i}"] = Position(f"P{i}", 1, 10, "2026-07-01", 9.0, current_price=10)
    res = sim.submit_orders([{"action": "BUY", "ticker": "NEW", "allocation_pct": 6,
                              "stop_loss_pct": 10}], "2026-07-01")
    assert res[0]["status"] == "REJECTED"


@test
def t_long_only_sell_requires_position():
    sim = new_sim()
    res = sim.submit_orders([{"action": "SELL", "ticker": "NONE", "allocation_pct": 100}],
                            "2026-07-01")
    assert res[0]["status"] == "REJECTED"


@test
def t_stop_loss_mandatory():
    sim = new_sim()
    res = sim.submit_orders([{"action": "BUY", "ticker": "ABC", "allocation_pct": 10,
                              "stop_loss_pct": 0}], "2026-07-01")
    assert res[0]["status"] == "REJECTED"


# ── Stops & take-profits (OHLC) ───────────────────────────────────────────

@test
def t_stop_loss_triggers_on_low():
    sim = new_sim()
    sim.positions["ABC"] = Position("ABC", 100, 10.0, "2026-07-01", stop_loss_price=9.0,
                                    current_price=10.0)
    txns = sim.check_stops_and_targets({"ABC": {"open": 9.5, "high": 9.6, "low": 8.5,
                                                 "close": 8.7}}, "2026-07-02")
    assert len(txns) == 1 and txns[0].trigger == "STOP_LOSS"
    assert "ABC" not in sim.positions


@test
def t_take_profit_triggers_on_high():
    sim = new_sim()
    sim.positions["ABC"] = Position("ABC", 100, 10.0, "2026-07-01", stop_loss_price=9.0,
                                    take_profit_price=12.0, current_price=10.0)
    txns = sim.check_stops_and_targets({"ABC": {"open": 11.0, "high": 12.5, "low": 10.9,
                                                 "close": 12.2}}, "2026-07-02")
    assert len(txns) == 1 and txns[0].trigger == "TAKE_PROFIT"


@test
def t_no_trigger_inside_range():
    sim = new_sim()
    sim.positions["ABC"] = Position("ABC", 100, 10.0, "2026-07-01", stop_loss_price=9.0,
                                    take_profit_price=12.0, current_price=10.0)
    txns = sim.check_stops_and_targets({"ABC": {"open": 10.1, "high": 11.0, "low": 9.5,
                                                 "close": 10.5}}, "2026-07-02")
    assert txns == []
    assert "ABC" in sim.positions


# ── Mark-to-market, drawdown, persistence ─────────────────────────────────

@test
def t_mark_to_market_and_drawdown():
    sim = new_sim()
    sim.positions["ABC"] = Position("ABC", 100, 10.0, "2026-07-01", stop_loss_price=9.0,
                                    current_price=10.0)
    sim.cash = 9_000.0
    snap = sim.mark_to_market({"ABC": 8.0}, "2026-07-02")           # 100*8 + 9000 = 9800
    assert approx(snap.portfolio_value, 9_800.0), snap.portfolio_value
    assert sim.max_drawdown > 0


@test
def t_daily_returns_are_day_over_day_across_rebuilds():
    # Simulate the backtest pattern: a fresh simulator each day, loading the
    # prior day's persisted state. daily_returns must be day-over-day, not
    # cumulative-since-start.
    import tempfile
    from pathlib import Path
    d = Path(tempfile.mkdtemp())
    rules = make_rules()

    # Day 1: hold 100 sh ABC @ $100 + $0 cash => value 10000 (flat vs start).
    s1 = PortfolioSimulator("agent", 10000.0, rules, d)
    s1.cash = 0.0
    s1.positions["ABC"] = Position("ABC", 100, 100.0, "2026-07-01", 90.0, current_price=100.0)
    s1.mark_to_market({"ABC": 100.0}, "2026-07-01")   # value 10000, day_ret 0
    s1.save_state()

    # Day 2: ABC -> $110 => value 11000. Day-over-day = +10%.
    s2 = PortfolioSimulator("agent", 10000.0, rules, d)   # reloads prior state
    s2.mark_to_market({"ABC": 110.0}, "2026-07-02")
    s2.save_state()
    assert approx(s2.daily_returns[-1], 0.10, tol=1e-6), s2.daily_returns

    # Day 3: ABC -> $110 (unchanged) => value 11000. Day-over-day = 0%.
    s3 = PortfolioSimulator("agent", 10000.0, rules, d)
    s3.mark_to_market({"ABC": 110.0}, "2026-07-03")
    assert approx(s3.daily_returns[-1], 0.0, tol=1e-6), s3.daily_returns
    # (Under the old bug day 3 would have been +10% again — cumulative vs $10k.)
    # (Under the old bug this would have been +10% again — cumulative vs $10k.)


@test
def t_state_roundtrip():
    sim = new_sim()
    sim.submit_orders([{"action": "BUY", "ticker": "ABC", "allocation_pct": 10,
                        "stop_loss_pct": 10}], "2026-07-01")
    sim.execute_pending_orders({"ABC": 10.0}, "2026-07-02")
    sim.save_state()
    sim2 = PortfolioSimulator("test_agent", 10_000.0, sim.rules, sim.data_dir)
    assert approx(sim2.cash, sim.cash), (sim2.cash, sim.cash)
    assert "ABC" in sim2.positions
    assert approx(sim2.positions["ABC"].shares, sim.positions["ABC"].shares)


# ── Price universe firewall ($3-$50) ──────────────────────────────────────

@test
def t_reject_buy_below_min_price():
    sim = new_sim()
    sim.submit_orders([{"action": "BUY", "ticker": "PENNY", "allocation_pct": 10,
                        "stop_loss_pct": 10}], "2026-07-01")
    sim.execute_pending_orders({"PENNY": 2.50}, "2026-07-02")     # below $3
    assert "PENNY" not in sim.positions
    assert approx(sim.cash, 10_000.0)                            # no cash spent


@test
def t_reject_buy_above_max_price():
    sim = new_sim()
    sim.submit_orders([{"action": "BUY", "ticker": "PRICEY", "allocation_pct": 10,
                        "stop_loss_pct": 10}], "2026-07-01")
    sim.execute_pending_orders({"PRICEY": 75.00}, "2026-07-02")  # above $50
    assert "PRICEY" not in sim.positions
    assert approx(sim.cash, 10_000.0)


@test
def t_allow_buy_inside_universe():
    sim = new_sim()
    sim.submit_orders([{"action": "BUY", "ticker": "OK", "allocation_pct": 10,
                        "stop_loss_pct": 10}], "2026-07-01")
    sim.execute_pending_orders({"OK": 25.00}, "2026-07-02")      # inside band
    assert "OK" in sim.positions


# ── Gap-fill realism ──────────────────────────────────────────────────────

@test
def t_stop_fills_at_open_on_gap_down():
    sim = new_sim()
    sim.positions["ABC"] = Position("ABC", 100, 10.0, "2026-07-01", stop_loss_price=9.0,
                                    current_price=10.0)
    # Gapped below the stop: open 8.0 < stop 9.0. Fill should be ~open, not the stop.
    txns = sim.check_stops_and_targets({"ABC": {"open": 8.0, "high": 8.2, "low": 7.5,
                                                 "close": 7.8}}, "2026-07-02")
    assert len(txns) == 1
    assert approx(txns[0].price, round(8.0 * (1 - 0.001), 4)), txns[0].price
    assert txns[0].price < 9.0                                    # worse than the stop


@test
def t_tp_fills_at_open_on_gap_up():
    sim = new_sim()
    sim.positions["ABC"] = Position("ABC", 100, 10.0, "2026-07-01", stop_loss_price=9.0,
                                    take_profit_price=12.0, current_price=10.0)
    # Gapped above the target: open 13.0 > tp 12.0. Fill should be ~open (better).
    txns = sim.check_stops_and_targets({"ABC": {"open": 13.0, "high": 13.4, "low": 12.8,
                                                 "close": 13.1}}, "2026-07-02")
    assert len(txns) == 1
    assert approx(txns[0].price, round(13.0 * (1 - 0.001), 4)), txns[0].price
    assert txns[0].price > 12.0                                   # better than the target


@test
def t_strict_backtest_rejects_missing_close_without_changing_equity():
    sim = new_sim()
    sim.positions["ABC"] = Position("ABC", 10, 12.0, "2022-06-01", 10.0,
                                    current_price=12.0)
    sim.cash = 9_880.0
    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        try:
            sim.mark_to_market({}, "2022-06-02")
            assert False, "missing bar must halt a historical valuation"
        except ValueError as exc:
            assert "ABC" in str(exc)
        assert sim.daily_returns == []
        assert sim.positions["ABC"].current_price == 12.0
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


@test
def t_strict_backtest_rejects_invalid_close():
    sim = new_sim()
    sim.positions["ABC"] = Position("ABC", 10, 12.0, "2022-06-01", 10.0,
                                    current_price=12.0)
    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        for value in (0, -4, float("nan"), float("inf")):
            try:
                sim.mark_to_market({"ABC": value}, "2022-06-02")
                assert False, f"invalid mark {value} accepted"
            except ValueError:
                pass
        assert sim.daily_returns == []
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


@test
def t_historical_snapshot_history_survives_daily_rebuilds():
    import os
    import json
    d = Path(tempfile.mkdtemp())
    rules = make_rules()
    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        one = PortfolioSimulator("agent", 10000.0, rules, d)
        one.mark_to_market({}, "2022-06-13")
        one.save_state()
        one.save_snapshot_history()

        two = PortfolioSimulator("agent", 10000.0, rules, d)
        two.mark_to_market({}, "2022-06-14")
        two.save_state()
        two.save_snapshot_history()
        two.save_snapshot_history()  # idempotent within the same trading day

        records = json.loads((d / "agent_history.json").read_text())
        assert [s["date"] for s in records] == ["2022-06-13", "2022-06-14"], records
        assert len(records) == len(two.daily_returns) == 2

        three = PortfolioSimulator("agent", 10000.0, rules, d)
        three.mark_to_market({}, "2022-06-15")
        three.save_state()
        three.save_snapshot_history()
        records = json.loads((d / "agent_history.json").read_text())
        assert len(records) == len(three.daily_returns) == 3, records
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


@test
def t_strict_history_fails_closed_if_existing_json_corrupt():
    import os
    d = Path(tempfile.mkdtemp())
    (d / "agent_history.json").write_text("{corrupt")
    sim = PortfolioSimulator("agent", 10000.0, make_rules(), d)
    sim.mark_to_market({}, "2022-06-13")
    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        try:
            sim.save_snapshot_history()
            assert False, "corrupt historical state must not be silently reset"
        except ValueError:
            pass
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


# ── End-to-end strict historical lifecycle (no market or model API calls) ───

@test
def t_strict_buy_then_agent_sell_across_rebuilt_sessions():
    """Decision after close -> next-open BUY -> next-open discretionary SELL."""
    import json
    from contextlib import contextmanager

    @contextmanager
    def strict():
        old = os.environ.get("BACKTEST_STRICT_PRICES")
        os.environ["BACKTEST_STRICT_PRICES"] = "1"
        try:
            yield
        finally:
            if old is None:
                os.environ.pop("BACKTEST_STRICT_PRICES", None)
            else:
                os.environ["BACKTEST_STRICT_PRICES"] = old

    with strict():
        d = Path(tempfile.mkdtemp())
        rules = make_rules()
        day1 = PortfolioSimulator("agent", 10000.0, rules, d)
        assert day1.submit_orders([{"action": "BUY", "ticker": "ABC",
                                    "allocation_pct": 10,
                                    "stop_loss_pct": 10,
                                    "take_profit_pct": 30}], "2024-03-04")[0]["status"] == "ACCEPTED"
        day1.mark_to_market({}, "2024-03-04")
        day1.save_state()
        day1.save_snapshot_history()

        day2 = PortfolioSimulator("agent", 10000.0, rules, d)
        buys = day2.execute_pending_orders({"ABC": 20.0}, "2024-03-05")
        assert len(buys) == 1 and buys[0].action == "BUY"
        assert approx(buys[0].price, 20.0 * 1.001)
        assert day2.check_stops_and_targets(
            {"ABC": {"open": 20.0, "high": 21.0, "low": 19.0, "close": 20.5}},
            "2024-03-05") == []
        day2.mark_to_market({"ABC": 20.5}, "2024-03-05")
        result = day2.submit_orders([{"action": "SELL", "ticker": "ABC",
                                      "allocation_pct": 100}], "2024-03-05")
        assert result[0]["status"] == "ACCEPTED"
        day2.save_state()
        day2.save_snapshot_history()

        day3 = PortfolioSimulator("agent", 10000.0, rules, d)
        sells = day3.execute_pending_orders({"ABC": 21.0}, "2024-03-06")
        assert len(sells) == 1 and sells[0].action == "SELL"
        assert sells[0].trigger == "AGENT"
        assert approx(sells[0].price, 21.0 * 0.999)
        assert "ABC" not in day3.positions
        assert not day3.pending_orders
        day3.check_stops_and_targets({}, "2024-03-06")
        day3.mark_to_market({}, "2024-03-06")
        day3.save_state()
        day3.save_snapshot_history()

        entries = json.loads((d / "agent_history.json").read_text())
        assert [e["date"] for e in entries] == [
            "2024-03-04", "2024-03-05", "2024-03-06"]
        assert [e["transactions_today"][0]["action"] for e in entries[1:]] == [
            "BUY", "SELL"]
        assert approx(day3.portfolio_value, 10000 - buys[0].total + sells[0].total, tol=1e-3)


@test
def t_strict_entry_day_stop_after_next_open_fill():
    """A freshly filled order is subject to that session's intraday stop."""
    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        sim = new_sim()
        sim.submit_orders([{"action": "BUY", "ticker": "ABC",
                            "allocation_pct": 10,
                            "stop_loss_pct": 10}], "2024-03-04")
        buys = sim.execute_pending_orders({"ABC": 10.0}, "2024-03-05")
        assert len(buys) == 1 and "ABC" in sim.positions
        stop = sim.positions["ABC"].stop_loss_price
        assert stop < 10.0
        exits = sim.check_stops_and_targets(
            {"ABC": {"open": 10.0, "high": 10.5, "low": 8.0, "close": 8.5}},
            "2024-03-05")
        assert len(exits) == 1 and exits[0].trigger == "STOP_LOSS"
        assert approx(exits[0].price, round(stop * .999, 4))
        assert "ABC" not in sim.positions
        snap = sim.mark_to_market({}, "2024-03-05")
        assert [t["action"] for t in snap.transactions_today] == ["BUY", "SELL"]
        assert snap.portfolio_value < 10000
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


@test
def t_strict_gap_up_target_precedes_later_stop_low():
    """An opening target wins even if the day's later low crosses the stop."""
    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        sim = new_sim()
        sim.positions["ABC"] = Position("ABC", 100, 10.0, "2024-03-04",
                                        stop_loss_price=9.0,
                                        take_profit_price=12.0,
                                        current_price=10.0)
        txns = sim.check_stops_and_targets(
            {"ABC": {"open": 13.0, "high": 13.5, "low": 8.0, "close": 10.0}},
            "2024-03-05")
        assert len(txns) == 1
        assert txns[0].trigger == "TAKE_PROFIT"
        assert approx(txns[0].price, 13.0 * .999, tol=1e-5)
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


@test
def t_strict_ambiguous_intraday_both_stop_and_target_is_conservative():
    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        sim = new_sim()
        sim.positions["ABC"] = Position("ABC", 100, 10.0, "2024-03-04",
                                        stop_loss_price=9.0,
                                        take_profit_price=12.0,
                                        current_price=10.0)
        txns = sim.check_stops_and_targets(
            {"ABC": {"open": 10.0, "high": 13.0, "low": 8.0, "close": 11.0}},
            "2024-03-05")
        assert len(txns) == 1 and txns[0].trigger == "STOP_LOSS"
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


@test
def t_strict_invalid_sell_allocation_and_missing_execution_bars():
    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        sim = new_sim()
        sim.positions["ABC"] = Position("ABC", 100, 10.0, "2024-03-04",
                                        stop_loss_price=9.0, current_price=10.0)
        for pct in (-25, 0, 101, float("nan")):
            result = sim.submit_orders([{"action": "SELL", "ticker": "ABC",
                                         "allocation_pct": pct}], "2024-03-04")
            assert result[0]["status"] == "REJECTED", result
        assert sim.pending_orders == []
        try:
            sim.check_stops_and_targets({}, "2024-03-05")
            assert False, "missing historical stop bar must fail"
        except ValueError:
            pass
        assert sim.submit_orders([{"action": "SELL", "ticker": "ABC",
                                   "allocation_pct": 100}], "2024-03-04")[0]["status"] == "ACCEPTED"
        for opens in ({}, {"ABC": 0}, {"ABC": float("nan")}):
            try:
                sim.execute_pending_orders(opens, "2024-03-05")
                assert False, "missing/invalid historical open must fail"
            except ValueError:
                pass
        assert "ABC" in sim.positions
        assert len(sim.pending_orders) == 1
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


# ─────────────────────────────────────────────────────────────────────────
def main():
    passed = failed = 0
    for fn in TESTS:
        try:
            fn()
            passed += 1
            print(f"  PASS  {fn.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed, {len(TESTS)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
