"""
Offline test for the Anthropic thinking-block fix in api_adapters.

Reasoning models (claude-haiku-5-5) return signed `thinking` blocks whose
signature is bound to the exact tools list they were created with. The
batch backtest showed 8,469 "forced propose failed" 400s — every Claude
trading decision on budget-exhaustion days — caused by replaying those
blocks under a one-tool list in the forced-propose fallback. The fix keeps
the full tools list and, as a safety net, can strip thinking blocks.

This test extracts UnifiedLLMClient._strip_thinking via AST (so we don't
import the provider SDKs) and checks it removes thinking / redacted_thinking
blocks from assistant turns while preserving everything the simulator needs.

Run:  python3 v2/tests/test_anthropic_thinking.py
"""

import ast
import sys
import traceback
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "api_adapters.py"
_cls = next(n for n in ast.parse(SRC.read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == "UnifiedLLMClient")
_fn = next(n for n in _cls.body
           if isinstance(n, ast.FunctionDef) and n.name == "_strip_thinking")
_ns = {}
exec(compile(ast.Module([_fn], []), "<f>", "exec"), _ns)
strip_thinking = _ns["_strip_thinking"]  # plain function (staticmethod body)

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


class Block:
    """Stand-in for an SDK content block with a .type attribute."""
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)
    def __repr__(self):
        return f"Block({self.type})"


@test
def t_removes_thinking_keeps_tool_use_and_text():
    think = Block("thinking", thinking="...", signature="sig")
    text = Block("text", text="I'll research")
    tu = Block("tool_use", name="get_macro", id="t1", input={})
    msgs = [
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": [think, text, tu]},
    ]
    out = strip_thinking(msgs)
    kept = out[1]["content"]
    types = [b.type for b in kept]
    assert types == ["text", "tool_use"], types
    # original list is not mutated
    assert len(msgs[1]["content"]) == 3


@test
def t_removes_redacted_thinking():
    msgs = [{"role": "assistant", "content": [
        Block("redacted_thinking", data="xx"), Block("text", text="hi")]}]
    out = strip_thinking(msgs)
    assert [b.type for b in out[0]["content"]] == ["text"]


@test
def t_leaves_string_content_untouched():
    msgs = [{"role": "assistant", "content": "plain string answer"}]
    out = strip_thinking(msgs)
    assert out[0]["content"] == "plain string answer"


@test
def t_leaves_user_turns_untouched():
    tr = Block("tool_result", tool_use_id="t1", content="{}")
    msgs = [{"role": "user", "content": [tr]}]
    out = strip_thinking(msgs)
    assert out[0]["content"] == [tr]


@test
def t_all_thinking_collapses_to_empty():
    msgs = [{"role": "assistant", "content": [
        Block("thinking", signature="s"), Block("redacted_thinking")]}]
    out = strip_thinking(msgs)
    assert out[0]["content"] == []


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
