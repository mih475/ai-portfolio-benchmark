"""
Offline test for the NaN-price guards in portfolio_simulator — stdlib only.

A delisted ticker that yfinance returns as NaN once poisoned a live account:
the NaN mark flowed market_value -> portfolio value -> buy sizing -> cash, and
once cash was NaN every later day loaded NaN and stayed NaN. Two guards stop it:
Position.update_price rejects non-finite/≤0 marks (carry last good forward), and
_portfolio_value_at_price falls back to the last good mark. portfolio_simulator
imports pandas, so we AST-extract just these two methods and exercise them.

Run:  python3 v2/tests/test_nan_guard.py
"""

import ast
import math
import sys
import traceback
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "portfolio_simulator.py"
_cls = next(n for n in ast.parse(SRC.read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == "PortfolioSimulator")
_pos = next(n for n in ast.parse(SRC.read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == "Position")

def _extract(classnode, name):
    fn = next(n for n in classnode.body
              if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {"math": math}
    exec(compile(ast.Module([fn], []), "<f>", "exec"), ns)
    return ns[name]

update_price = _extract(_pos, "update_price")
pv_at = _extract(_cls, "_portfolio_value_at_price")

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


class Box:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _pos_obj(cp):
    return Box(current_price=cp, entry_price=8.0, shares=5.0,
              unrealized_pnl=0.0, unrealized_pnl_pct=0.0)


@test
def t_update_price_rejects_bad_marks():
    for bad in (float("nan"), float("inf"), -float("inf"), 0, -5.0):
        o = _pos_obj(10.0)
        update_price(o, bad)
        assert o.current_price == 10.0, f"{bad} should be rejected, got {o.current_price}"


@test
def t_update_price_accepts_good_mark():
    o = _pos_obj(10.0)
    update_price(o, 12.5)
    assert o.current_price == 12.5
    assert o.unrealized_pnl == (12.5 - 8.0) * 5.0


@test
def t_portfolio_value_normal():
    s = Box(cash=1000.0, positions={"A": _pos_obj(5.0), "B": _pos_obj(20.0)})
    assert pv_at(s, {"A": 5.0, "B": 20.0}) == 1000 + 5*5 + 5*20


@test
def t_portfolio_value_nan_price_falls_back():
    s = Box(cash=1000.0, positions={"A": _pos_obj(5.0), "B": _pos_obj(20.0)})
    v = pv_at(s, {"A": float("nan"), "B": 20.0})   # A NaN -> use A.current_price (5.0)
    assert math.isfinite(v) and v == 1000 + 5*5 + 5*20


@test
def t_portfolio_value_missing_price_uses_last_mark():
    s = Box(cash=1000.0, positions={"A": _pos_obj(5.0), "B": _pos_obj(20.0)})
    v = pv_at(s, {"A": 5.0})                        # B missing -> use B.current_price
    assert v == 1000 + 5*5 + 5*20


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
