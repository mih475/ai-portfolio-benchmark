"""
Offline tests for combine_backtests pooling — stdlib only.

Run:  python3 v2/tests/test_combine.py
"""

import importlib.util
import json
import sys
import tempfile
import traceback
from pathlib import Path

V2 = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("combine_standalone", V2 / "scripts" / "combine_backtests.py")
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


def _make_quarter(agent_daily, spy_daily):
    d = Path(tempfile.mkdtemp())
    (d / "gemini_aggressive.json").write_text(json.dumps({
        "agent_id": "gemini_aggressive", "daily_returns": agent_daily,
        "starting_capital": 10000, "cash": 10000, "positions": {}}))
    (d / "spy_buy_hold.json").write_text(json.dumps({
        "agent_id": "spy_buy_hold", "daily_returns": spy_daily,
        "starting_capital": 10000, "cash": 10000, "positions": {}}))
    return str(d)


@test
def t_pool_concatenates_across_quarters():
    q1 = _make_quarter([0.01, 0.02], [0.005, 0.006])
    q2 = _make_quarter([0.03], [0.007])
    pooled_daily, pooled_pairs, nq = cb.pool([q1, q2])
    assert nq == 2
    assert pooled_daily["gemini_aggressive"] == [0.01, 0.02, 0.03]
    a, s = pooled_pairs["gemini_aggressive"]
    assert len(a) == 3 and len(s) == 3        # paired with SPY each quarter


@test
def t_analyze_reports_beat_spy():
    # Agent strictly dominates SPY in both quarters => should beat ~100%.
    q1 = _make_quarter([0.004] * 40, [0.001] * 40)
    q2 = _make_quarter([0.004] * 40, [0.001] * 40)
    abs_rows, vs_rows, nq = cb.analyze([q1, q2], horizon=252, n_sims=300)
    assert nq == 2
    agg = next(r for r in vs_rows if r["agent"] == "gemini_aggressive")
    assert agg["prob_beat"] > 99.0, agg
    assert agg["n_days"] == 80, agg            # 40 + 40 pooled pairs


@test
def t_render_mentions_quarters():
    q1 = _make_quarter([0.01, -0.01] * 20, [0.005, -0.004] * 20)
    abs_rows, vs_rows, nq = cb.analyze([q1], horizon=252, n_sims=200)
    out = cb.render(abs_rows, vs_rows, nq)
    assert "1 quarter(s) combined" in out


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
