"""
Offline tests for api_adapters._safe_create — stdlib only.

_safe_create shields the LLM call sites from provider parameter drift. It lives
in api_adapters.py (which imports provider SDKs lazily), so we extract just the
function via AST and exercise it with fake SDK methods that raise the real
errors the providers produce.

Run:  python3 v2/tests/test_safe_create.py
"""

import ast
import sys
import traceback
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "api_adapters.py"
_fn = next(n for n in ast.parse(SRC.read_text()).body
           if isinstance(n, ast.FunctionDef) and n.name == "_safe_create")
_ns = {}
exec(compile(ast.Module([_fn], []), "<f>", "exec"), _ns)
safe_create = _ns["_safe_create"]

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


@test
def t_openai_renames_max_tokens():
    def fn(**kw):
        if "max_tokens" in kw:
            raise Exception("Error code: 400 - Unsupported parameter: 'max_tokens' "
                            "is not supported with this model. Use 'max_completion_tokens' instead.")
        return {"ok": True, **kw}
    r = safe_create(fn, model="gpt-6-luna", max_tokens=4096, temperature=0)
    assert r["ok"] and "max_completion_tokens" in r and "max_tokens" not in r, r


@test
def t_anthropic_drops_temperature():
    def fn(**kw):
        if "temperature" in kw:
            raise TypeError("Messages.create() got an unexpected keyword argument 'temperature'")
        return {"ok": True, **kw}
    r = safe_create(fn, model="claude-haiku-5-5", max_tokens=4096, temperature=0)
    assert r["ok"] and "temperature" not in r, r


@test
def t_transient_error_propagates():
    def fn(**kw):
        raise Exception("Error code: 529 - overloaded_error")
    try:
        safe_create(fn, model="x", max_tokens=1)
        assert False, "should have raised"
    except Exception as e:
        assert "529" in str(e)


@test
def t_happy_path_unchanged():
    r = safe_create(lambda **kw: {"ok": True, **kw}, model="x", temperature=0, max_tokens=10)
    assert r["ok"] and r["temperature"] == 0 and r["max_tokens"] == 10


@test
def t_unknown_param_dropped():
    def fn(**kw):
        if "parallel_tool_calls" in kw:
            raise Exception("Error code: 400 - Unknown parameter: 'parallel_tool_calls'.")
        return {"ok": True, **kw}
    r = safe_create(fn, model="x", parallel_tool_calls=False, max_tokens=10)
    assert r["ok"] and "parallel_tool_calls" not in r, r


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
