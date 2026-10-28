"""
Monte-Carlo (bootstrap) return distribution for each agent.

Instead of reporting one point return (which two quarters can't support), this
resamples an agent's observed DAILY returns with replacement to build many
simulated forward paths, and reports the resulting distribution: median, a 90%
confidence band (5th–95th percentile), mean, and probability of loss.

Method: IID bootstrap of daily returns. This is the honest first-order answer to
"what return does the observed daily behaviour imply, with what uncertainty?" —
NOT a forecast. Caveats (stated in the output): it assumes daily returns are
independent and identically distributed (ignores volatility clustering, fat
tails beyond the sample, and regime change), and it's only as good as the input
sample — a short backtest gives wide, unreliable bands.

Pure stdlib so it runs anywhere and is unit-testable.

Usage:  python3 v2/scripts/monte_carlo.py [portfolios_dir] [horizon_days] [n_sims]
"""

import json
import random
import sys
from pathlib import Path

DEFAULT_HORIZON = 252   # ~1 trading year
DEFAULT_SIMS = 5000
CAPITAL = 10000.0


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def bootstrap_finals(daily, horizon=DEFAULT_HORIZON, n_sims=DEFAULT_SIMS, seed=0):
    """Return a sorted list of final growth multipliers over `horizon` days,
    each path built by sampling `horizon` daily returns with replacement."""
    if len(daily) < 2:
        return []
    rng = random.Random(seed)
    finals = []
    for _ in range(n_sims):
        mult = 1.0
        for r in rng.choices(daily, k=horizon):
            mult *= (1.0 + r)
        finals.append(mult)
    finals.sort()
    return finals


def distribution_stats(daily, horizon=DEFAULT_HORIZON, n_sims=DEFAULT_SIMS, seed=0,
                       capital=CAPITAL):
    finals = bootstrap_finals(daily, horizon, n_sims, seed)
    if not finals:
        return None
    mean = sum(finals) / len(finals)
    p5, p25, p50, p75, p95 = (_percentile(finals, p) for p in (0.05, 0.25, 0.5, 0.75, 0.95))
    prob_loss = sum(1 for m in finals if m < 1.0) / len(finals)
    to_pct = lambda m: (m - 1) * 100
    to_dollar = lambda m: capital * m
    return {
        "n_days": len(daily),
        "ret_p5": to_pct(p5), "ret_p50": to_pct(p50), "ret_p95": to_pct(p95),
        "ret_mean": to_pct(mean),
        "usd_p5": to_dollar(p5), "usd_p50": to_dollar(p50), "usd_p95": to_dollar(p95),
        "prob_loss": prob_loss * 100,
    }


def vs_spy_stats(agent_daily, spy_daily, horizon=DEFAULT_HORIZON,
                n_sims=DEFAULT_SIMS, seed=0):
    """Paired bootstrap: does the agent beat SPY, and by how much?

    Resamples the SAME day indices for agent and SPY together (so both see the
    same bootstrapped market), compounds each over `horizon`, and compares
    terminal wealth. Returns probability the agent beats SPY and the
    distribution of the win/loss margin (agent_wealth/spy_wealth - 1).
    Needs aligned daily series; trims both to their common length from the end.
    """
    L = min(len(agent_daily), len(spy_daily))
    if L < 2:
        return None
    a = agent_daily[-L:]
    s = spy_daily[-L:]
    rng = random.Random(seed)
    margins = []
    wins = 0
    for _ in range(n_sims):
        am = sm = 1.0
        for _ in range(horizon):
            i = rng.randrange(L)         # same day index applied to both
            am *= (1.0 + a[i])
            sm *= (1.0 + s[i])
        ratio = am / sm if sm > 0 else 0.0
        margins.append((ratio - 1) * 100)
        if ratio > 1.0:
            wins += 1
    margins.sort()
    return {
        "prob_beat": wins / n_sims * 100,
        "margin_p5": _percentile(margins, 0.05),
        "margin_p50": _percentile(margins, 0.5),
        "margin_p95": _percentile(margins, 0.95),
        "n_days": L,
    }


def analyze(portfolios_dir, horizon=DEFAULT_HORIZON, n_sims=DEFAULT_SIMS):
    """Return (absolute_rows, vs_spy_rows). vs_spy_rows is empty if no SPY row."""
    states = {}
    for f in sorted(Path(portfolios_dir).glob("*.json")):
        if f.name.endswith("_history.json") or f.name == "summary.json":
            continue
        try:
            state = json.loads(f.read_text())
        except Exception:
            continue
        aid = state.get("agent_id")
        if aid:
            states[aid] = state.get("daily_returns", []) or []

    rows = []
    for aid, daily in states.items():
        st = distribution_stats(daily, horizon, n_sims)
        if st is None:
            continue
        st["agent"] = aid
        rows.append(st)
    rows.sort(key=lambda r: r["ret_p50"], reverse=True)

    vs_rows = []
    spy = next((d for a, d in states.items() if "spy" in a.lower()), None)
    spy_name = next((a for a in states if "spy" in a.lower()), None)
    if spy is not None:
        for aid, daily in states.items():
            if aid == spy_name:
                continue
            v = vs_spy_stats(daily, spy, horizon, n_sims)
            if v is None:
                continue
            v["agent"] = aid
            vs_rows.append(v)
        vs_rows.sort(key=lambda r: r["prob_beat"], reverse=True)
    return rows, vs_rows


def render(rows, vs_rows=None, horizon=DEFAULT_HORIZON) -> str:
    yrs = horizon / 252
    lines = []

    # Headline: does each agent beat SPY, and by how much? (paired bootstrap)
    if vs_rows:
        lines += [
            f"# Does the model beat SPY? ({horizon}d ≈ {yrs:.1f}y, paired bootstrap)",
            "",
            "Same bootstrapped days applied to agent and SPY together, then "
            "terminal wealth compared. **Prob. beat SPY** near 50% = coin-flip "
            "(no edge); the margin band shows how big the win/loss typically is.",
            "",
            "| Agent | Prob. beat SPY | Median margin vs SPY | 90% band (p5…p95) |",
            "|---|---|---|---|",
        ]
        for r in vs_rows:
            lines.append(
                f"| {r['agent']} | {r['prob_beat']:.0f}% | {r['margin_p50']:+.1f}% "
                f"| {r['margin_p5']:+.1f}% … {r['margin_p95']:+.1f}% |"
            )
        lines.append("")

    lines += [
        f"# Return distribution ({horizon}d ≈ {yrs:.1f}y, IID bootstrap of daily returns)",
        "",
        "Resampled forward paths from each agent's observed daily returns. "
        "**Not a forecast** — it shows the spread the observed daily behaviour "
        "implies if it persisted. Bands are only as reliable as the input sample.",
        "",
        "| Agent | Sample days | Median ret | 90% band (p5…p95) | Median $10k→ | Prob. loss |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['agent']} | {r['n_days']} | {r['ret_p50']:+.1f}% "
            f"| {r['ret_p5']:+.1f}% … {r['ret_p95']:+.1f}% "
            f"| ${r['usd_p50']:,.0f} (${r['usd_p5']:,.0f}–${r['usd_p95']:,.0f}) "
            f"| {r['prob_loss']:.0f}% |"
        )
    if not rows:
        lines.append("| — | _no daily-return data_ |  |  |  |  |")
    if rows and min(r["n_days"] for r in rows) < 60:
        lines += ["", "> ⚠ Fewer than ~60 sample days: bands are very wide and "
                      "unreliable. Treat as illustrative only."]
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    portfolios_dir = args[0] if len(args) > 0 else str(
        Path(__file__).resolve().parent.parent / "data" / "portfolios")
    horizon = int(args[1]) if len(args) > 1 else DEFAULT_HORIZON
    n_sims = int(args[2]) if len(args) > 2 else DEFAULT_SIMS
    rows, vs_rows = analyze(portfolios_dir, horizon, n_sims)
    out = render(rows, vs_rows, horizon)
    print(out)
    try:
        (Path(portfolios_dir) / "monte_carlo.md").write_text(out)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
