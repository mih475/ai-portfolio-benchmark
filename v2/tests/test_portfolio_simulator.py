"""
Offline tests for PortfolioSimulator — stdlib only, no network, no pip deps.

Run:  python3 v2/tests/test_portfolio_simulator.py
Exit code 0 = all passed. Used by CI (.github/workflows/tests.yml).

The simulator is the "Code is Law" firewall; these tests pin its behaviour so
future changes can't silently break T+1 execution, slippage, sizing caps,
validation, stop/TP triggers, or state persistence.
"""

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
