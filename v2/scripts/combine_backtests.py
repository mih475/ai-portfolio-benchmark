"""
Combine several quarter backtests into one pooled "beat SPY?" verdict.

Each quarter is an independent $10k run with its own daily-return series. To get
a statistically meaningful answer we pool the per-day (agent, SPY) pairs across
all quarters and run the paired bootstrap on the pooled sample — many more
observations => tighter, more reliable bands than any single quarter.

Takes a list of result directories (each a portfolios/ folder from one quarter's
artifact). Reuses the Monte-Carlo machinery.

Usage:  python3 v2/scripts/combine_backtests.py DIR1 DIR2 [DIR3 ...]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import monte_carlo as mc  # noqa: E402


def _load_dir(d):
    """Return {agent_id: daily_returns} for one quarter's portfolios dir."""
    out = {}
    for f in sorted(Path(d).glob("*.json")):
        if f.name.endswith("_history.json") or f.name in ("summary.json",):
            continue
        try:
            s = json.loads(f.read_text())
        except Exception:
            continue
        aid = s.get("agent_id")
        if aid:
            out[aid] = s.get("daily_returns", []) or []
    return out


def pool(dirs):
    """Pool across quarters. Returns:
      pooled_daily[agent] = concatenated daily returns (absolute distribution)
      pooled_pairs[agent] = (agent_list, spy_list) aligned day-pairs vs SPY
    """
    pooled_daily, pa, ps = {}, {}, {}
    n_quarters = 0
    for d in dirs:
        q = _load_dir(d)
        if not q:
            continue
        n_quarters += 1
        spy_name = next((a for a in q if "spy" in a.lower()), None)
        spy = q.get(spy_name, []) if spy_name else []
        for aid, daily in q.items():
            pooled_daily.setdefault(aid, []).extend(daily)
            if spy_name and aid != spy_name:
                L = min(len(daily), len(spy))
                if L >= 1:
                    pa.setdefault(aid, []).extend(daily[-L:])
                    ps.setdefault(aid, []).extend(spy[-L:])
    pooled_pairs = {aid: (pa[aid], ps[aid]) for aid in pa}
    return pooled_daily, pooled_pairs, n_quarters


def analyze(dirs, horizon=mc.DEFAULT_HORIZON, n_sims=mc.DEFAULT_SIMS):
    pooled_daily, pooled_pairs, n_quarters = pool(dirs)
    abs_rows = []
    for aid, daily in pooled_daily.items():
        st = mc.distribution_stats(daily, horizon, n_sims)
        if st:
            st["agent"] = aid
            abs_rows.append(st)
    abs_rows.sort(key=lambda r: r["ret_p50"], reverse=True)

    vs_rows = []
    for aid, (a, s) in pooled_pairs.items():
        v = mc.vs_spy_stats(a, s, horizon, n_sims)
        if v:
            v["agent"] = aid
            vs_rows.append(v)
    vs_rows.sort(key=lambda r: r["prob_beat"], reverse=True)
    return abs_rows, vs_rows, n_quarters


def render(abs_rows, vs_rows, n_quarters, horizon=mc.DEFAULT_HORIZON) -> str:
    header = [f"# Pooled backtest verdict — {n_quarters} quarter(s) combined", ""]
    if vs_rows:
        total_days = vs_rows[0]["n_days"]
        header.append(f"Pooled paired sample: {total_days} agent/SPY day-pairs.")
    body = mc.render(abs_rows, vs_rows, horizon)
    return "\n".join(header) + "\n" + body


def main():
    dirs = sys.argv[1:]
    if not dirs:
        print("usage: combine_backtests.py DIR1 DIR2 ...", file=sys.stderr)
        return 2
    abs_rows, vs_rows, n_quarters = analyze(dirs)
    out = render(abs_rows, vs_rows, n_quarters)
    print(out)
    try:
        Path("combined_verdict.md").write_text(out)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
