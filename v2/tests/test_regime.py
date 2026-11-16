"""
Offline test for agent_runner.regime_from_closes — stdlib only.

The claude_switch meta-agent flips between the robust playbook (risk-on) and the
baseline aggressive playbook (risk-off) by SPY's 200-day MA. regime_from_closes
is the pure decision; agent_runner imports heavy deps, so we AST-extract just it.

Run:  python3 v2/tests/test_regime.py
"""

import ast
import sys
import traceback
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "agent_runner.py"
_fn = next(n for n in ast.parse(SRC.read_text()).body
           if isinstance(n, ast.FunctionDef) and n.name == "regime_from_closes")
_ns = {}
exec(compile(ast.Module([_fn], []), "<f>", "exec"), _ns)
regime = _ns["regime_from_closes"]

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


@test
def t_insufficient_history_defaults_risk_on():
    assert regime([]) == "risk_on"
    assert regime([100] * 50) == "risk_on"            # < 200
    assert regime(list(range(199))) == "risk_on"      # one short of the window


@test
def t_uptrend_is_risk_on():
    closes = list(range(1, 251))          # 1..250, strictly rising
    # last (250) is well above the 200-day MA of the final window
    assert regime(closes) == "risk_on"


@test
def t_downtrend_is_risk_off():
    closes = list(range(250, 0, -1))      # 250..1, strictly falling
    # last (1) is far below the trailing average
    assert regime(closes) == "risk_off"


@test
def t_last_equal_to_ma_is_risk_on():
    closes = [100.0] * 200                # flat -> last == MA -> >=, risk_on
    assert regime(closes) == "risk_on"


@test
def t_only_trailing_window_counts():
    # Ancient crash then a long steady recovery sitting above its own 200-MA.
    closes = [10.0] * 10 + [100.0] * 250  # last 200 are all 100 -> risk_on
    assert regime(closes) == "risk_on"


@test
def t_just_below_ma_is_risk_off():
    closes = [100.0] * 199 + [99.0]       # MA ~99.995, last 99 < MA
    assert regime(closes) == "risk_off"


@test
def t_custom_window():
    assert regime([100] * 5 + [1], ma_window=3) == "risk_off"   # last 3 = [100,100,1], MA=67, last<MA
    assert regime([1, 1, 100], ma_window=3) == "risk_on"        # MA=34, last 100>=MA


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
