"""
Offline tests for the Monte-Carlo (bootstrap) analysis — stdlib only.

Run:  python3 v2/tests/test_monte_carlo.py
"""

import importlib.util
import sys
import traceback
from pathlib import Path

V2 = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("mc_standalone", V2 / "scripts" / "monte_carlo.py")
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


@test
def t_percentile_basic():
    v = [0.0, 10.0, 20.0, 30.0, 40.0]
    assert mc._percentile(v, 0.5) == 20.0
    assert mc._percentile(v, 0.0) == 0.0
    assert mc._percentile(v, 1.0) == 40.0


@test
def t_bootstrap_deterministic_and_positive_drift():
    daily = [0.001] * 60                      # steady +0.1%/day
    finals = mc.bootstrap_finals(daily, horizon=252, n_sims=200, seed=1)
    assert len(finals) == 200
    # constant positive returns -> every path grows
    assert finals[0] > 1.0
    # same seed reproduces
    finals2 = mc.bootstrap_finals(daily, horizon=252, n_sims=200, seed=1)
    assert finals == finals2


@test
def t_distribution_stats_shape():
    daily = [0.01, -0.008, 0.005, -0.003, 0.012, -0.006] * 12   # 72 days
    st = mc.distribution_stats(daily, horizon=252, n_sims=300, seed=2)
    assert st["n_days"] == 72
    assert st["ret_p5"] <= st["ret_p50"] <= st["ret_p95"]
    assert 0 <= st["prob_loss"] <= 100


@test
def t_too_few_points():
    assert mc.bootstrap_finals([0.01], horizon=10, n_sims=10) == []
    assert mc.distribution_stats([], horizon=10, n_sims=10) is None


@test
def t_vs_spy_detects_clear_winner():
    # Agent returns dominate SPY every day => should beat SPY ~100% of the time.
    agent = [0.004] * 80
    spy = [0.001] * 80
    v = mc.vs_spy_stats(agent, spy, horizon=252, n_sims=300, seed=3)
    assert v["prob_beat"] > 99.0, v
    assert v["margin_p50"] > 0, v


@test
def t_vs_spy_detects_clear_loser():
    agent = [0.0005] * 80
    spy = [0.003] * 80
    v = mc.vs_spy_stats(agent, spy, horizon=252, n_sims=300, seed=4)
    assert v["prob_beat"] < 1.0, v
    assert v["margin_p50"] < 0, v


@test
def t_vs_spy_coinflip_when_identical():
    # Identical daily series => margin ~0, prob_beat ~ a coin flip (ties count as not-beat).
    series = [0.01, -0.01, 0.005, -0.004] * 20
    v = mc.vs_spy_stats(series, series, horizon=252, n_sims=400, seed=5)
    assert abs(v["margin_p50"]) < 1e-6, v      # same days => identical wealth => 0 margin


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
