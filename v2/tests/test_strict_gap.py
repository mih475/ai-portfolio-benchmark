"""
Offline test for portfolio_simulator.is_systematic_price_gap — stdlib only.

Strict backtests used to abort a whole quarter if any held/queued ticker was
missing its exact-session OHLC. Historical Yahoo data has occasional one-session
holes for liquid names (e.g. HPQ on 2020-08-07), so that threw away valid
backtests. The gap classifier draws the line: abort only on a *systematic*
failure (feed broken), carry an isolated gap forward. portfolio_simulator.py
imports pandas, so we AST-extract just this function and exercise it.

Run:  python3 v2/tests/test_strict_gap.py
"""

import ast
import sys
import traceback
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "portfolio_simulator.py"
_fn = next(n for n in ast.parse(SRC.read_text()).body
           if isinstance(n, ast.FunctionDef) and n.name == "is_systematic_price_gap")
_ns = {}
exec(compile(ast.Module([_fn], []), "<f>", "exec"), _ns)
is_systematic = _ns["is_systematic_price_gap"]

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


@test
def t_isolated_single_gap_tolerated():
    # The real HPQ-on-2020-08-07 shape: one name missing out of several.
    assert is_systematic(1, 10) is False
    assert is_systematic(1, 2) is False
    assert is_systematic(2, 20) is False


@test
def t_everything_missing_is_systematic():
    assert is_systematic(1, 1) is True       # the one ticker we needed is gone
    assert is_systematic(3, 3) is True
    assert is_systematic(10, 10) is True


@test
def t_half_or_more_is_systematic():
    assert is_systematic(5, 10) is True
    assert is_systematic(10, 20) is True
    assert is_systematic(4, 10) is False     # under both the 5 and the 50% bars


@test
def t_small_universe_floor_of_five():
    # With a tiny universe, up to 4 isolated gaps are still tolerated.
    assert is_systematic(4, 8) is False
    assert is_systematic(5, 8) is True


@test
def t_degenerate_inputs():
    assert is_systematic(0, 0) is False
    assert is_systematic(0, 10) is False


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
