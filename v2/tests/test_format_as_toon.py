"""
Regression test for snapshot_engine.format_as_toon — stdlib only.

format_as_toon() lives in snapshot_engine.py, which imports pandas/numpy at
module load, so we can't import the module in a no-deps environment. The
function body itself uses only builtins, so we extract and exec just that
function in isolation. This pins the fix for the crash where a failed
fetch_sector_rotation() (returning {"error": ...}) made format_as_toon call
.get() on a string and raise AttributeError, killing the whole snapshot build.

Run:  python3 v2/tests/test_format_as_toon.py
"""

import ast
import sys
import traceback
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "snapshot_engine.py"


def _load_format_as_toon():
    tree = ast.parse(ENGINE.read_text())
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "format_as_toon")
    ns = {"List": list, "Dict": dict, "Any": object}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<fn>", "exec"), ns)
    return ns["format_as_toon"]


TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


WATCHLIST = [{"Tkr": "ABC", "Price": 12.3, "RSI": 55}]


@test
def t_error_dict_sectors_no_crash():
    f = _load_format_as_toon()
    out = f(WATCHLIST, {"error": "Failed to download Sector ETF data."})
    assert "No sector rotation data available" in out
    assert "Failed to download" in out


@test
def t_valid_sectors_render():
    f = _load_format_as_toon()
    sec = {"Technology": {"ticker": "XLK", "rs_ratio": 101.2,
                          "rs_momentum": 100.5, "quadrant": "LEADING"}}
    out = f(WATCHLIST, sec)
    assert "XLK" in out and "LEADING" in out


@test
def t_empty_sectors_placeholder():
    f = _load_format_as_toon()
    assert "No sector rotation data available" in f(WATCHLIST, {})


@test
def t_none_sectors_placeholder():
    f = _load_format_as_toon()
    assert "No sector rotation data available" in f(WATCHLIST, None)


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
