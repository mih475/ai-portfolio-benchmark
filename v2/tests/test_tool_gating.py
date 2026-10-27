"""
Offline test for the MCP registry's point-in-time gating — stdlib only.

The mcp_servers package imports siblings that need httpx/bs4, which aren't in
the offline env, so we stub those modules, import the package, then replace its
TOOLS registry with a recorder. We assert:
  - past date  -> date-aware tool gets `as_of` injected
  - past date  -> live-only tool is disabled (execute never called)
  - live (None)-> no injection, tool called normally

Run:  python3 v2/tests/test_tool_gating.py
"""

import sys
import types
import traceback
from datetime import date, timedelta
from pathlib import Path

# --- stub heavy deps so the package imports in a bare env ---
for name in ("httpx",):
    sys.modules.setdefault(name, types.ModuleType(name))
if "bs4" not in sys.modules:
    bs4 = types.ModuleType("bs4")
    bs4.BeautifulSoup = object  # only the name needs to exist at import time
    sys.modules["bs4"] = bs4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mcp_servers as reg  # noqa: E402


class Recorder:
    def __init__(self):
        self.calls = []
    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return {"ok": True, **kwargs}


def install_fake_tools():
    rec = Recorder()
    reg.TOOLS = {
        "get_macro": {"definition": {}, "execute": rec},      # in _ASOF_TOOLS
        "get_technicals": {"definition": {}, "execute": rec},  # in _ASOF_TOOLS
        "web_search": {"definition": {}, "execute": rec},      # in _LIVE_ONLY_TOOLS
    }
    return rec


TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn

PAST = date(2026, 4, 7)


@test
def t_past_injects_as_of_for_asof_tool():
    rec = install_fake_tools()
    reg.set_run_context(PAST)
    out = reg.execute_tool("get_macro", {"indicators": ["DGS10"]})
    reg.set_run_context(None)
    assert rec.calls and rec.calls[0].get("as_of") == PAST.isoformat(), rec.calls
    assert out.get("as_of") == PAST.isoformat()


@test
def t_past_disables_live_only_tool():
    rec = install_fake_tools()
    reg.set_run_context(PAST)
    out = reg.execute_tool("web_search", {"query": "anything"})
    reg.set_run_context(None)
    assert "disabled" in out, out
    assert rec.calls == [], "live-only tool must not execute on a past date"


@test
def t_live_no_injection():
    rec = install_fake_tools()
    reg.set_run_context(None)
    reg.execute_tool("get_macro", {"indicators": ["DGS10"]})
    assert rec.calls and "as_of" not in rec.calls[0], rec.calls


@test
def t_future_date_is_live():
    rec = install_fake_tools()
    reg.set_run_context(date.today() + timedelta(days=3))
    out = reg.execute_tool("web_search", {"query": "x"})   # not disabled when live
    reg.set_run_context(None)
    assert "disabled" not in out and rec.calls, out


@test
def t_active_definitions_hide_live_only_when_historical():
    # Fake registry with named definitions, incl. a live-only and an as-of tool.
    reg.TOOLS = {
        "get_technicals": {"definition": {"name": "get_technicals"}, "execute": None},
        "web_search": {"definition": {"name": "web_search"}, "execute": None},
        "get_fundamentals": {"definition": {"name": "get_fundamentals"}, "execute": None},
    }
    reg.set_run_context(PAST)
    names_hist = {d["name"] for d in reg.get_active_tool_definitions()}
    reg.set_run_context(None)
    names_live = {d["name"] for d in reg.get_active_tool_definitions()}
    # Historical: live-only tools hidden; as-of/neutral tools kept.
    assert "web_search" not in names_hist and "get_fundamentals" not in names_hist, names_hist
    assert "get_technicals" in names_hist
    # Live: everything exposed.
    assert {"get_technicals", "web_search", "get_fundamentals"} <= names_live, names_live


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
