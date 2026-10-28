# AI Portfolio Benchmark — Methodology & Findings

*Independent fork of `Seve1995/ai-portfolio-experiment`. This document reports
how the benchmark works and what it found. See `README.md` for setup and
`CHANGES.md` for the full change history.*

---

## 1. Question

Can an autonomous LLM trading agent **beat a passive S&P 500 buy-and-hold
(SPY)** — and if so, by a **noticeably large margin** — once the experiment is
run rigorously (no look-ahead, enforced rules, a real benchmark, and enough
data to separate skill from luck)?

**Short answer: no.** Over eight quarters (2024–2025, 502 trading days) the
aggressive Gemini agent returned **+1.6%** while SPY returned **+48.6%**, beat
SPY in only **27%** of bootstrapped forward paths, and had a **~49% chance of
losing money**. Its returns came from taking ~3× the market's volatility, not
from skill — a dart-throwing random control matched or beat it.

---

## 2. Methodology

### 2.1 The simulation ("Code is Law")
A deterministic simulator executes and scores trades; the LLM only *proposes*.
Rules enforced in code (not by prompt):

- **Universe:** long-only US equities priced **$3–$50** (enforced at fill — buys
  outside the band are rejected). No shorts, no leverage.
- **Execution:** decisions are made after close and filled at the **next
  session's open** (T+1) with 0.1% slippage. Stops/take-profits are checked
  against the day's High/Low; **gap-throughs fill at the open**, not the trigger
  price (no optimistic fills).
- **Sizing:** 5–25% per position, max 15 positions, max 3 new buys/day, every
  buy must carry a stop-loss.
- **Fairness:** all agents in a run are priced off **one frozen OHLC set per
  day**, so roster order can't advantage anyone.

### 2.2 Agents
Each agent is a model × persona. Personas (conservative / balanced / aggressive)
differ only in their system-prompt risk mandate. A **random control** (no LLM)
trades randomly within the same rules and universe — the skill-vs-luck baseline.
The headline study uses **Gemini 3.8 Flash** (`gemini-3.8-flash`).

### 2.3 Data
- **Prices:** Yahoo Finance (yfinance), free.
- **Macro:** FRED (yields, VIX, Fed funds), free.
- Both are fetched **point-in-time** for historical runs (see 2.4). Prices are
  cached on disk and retried with backoff for reproducibility.

### 2.4 Point-in-time integrity (no look-ahead)
A backtest for a past date must not see the future. Enforced:

- **Prices** come from a window *ending at* the simulation date, never the
  latest bar.
- **FRED macro** is fetched as-of the simulation date.
- **LLM tools** are gated by a run-level date context: date-aware tools
  (`get_macro`, `get_technicals`) get the as-of date injected; tools that can
  only return the present (`web_search`, `get_market_news`, `get_fundamentals`,
  `fetch_url`) are **disabled** on a past date.
- The market **narrative and catalyst watchlist** (live web search) are
  **suppressed** for historical snapshots — they have no point-in-time mode.

Consequence (stated honestly): historical agents trade on a **leaner
information set** (prices + macro + technicals, no news) than a live agent
would. This is the correct trade-off — fabricated "as-of" news would be worse.

### 2.5 Benchmarks & statistics
- **SPY buy-and-hold** over the identical window is computed and ranked
  alongside the agents (return, max drawdown, daily series).
- Reported per run: return, **max drawdown**, **annualized volatility**, and
  **Sharpe** (rf=0) from the (corrected) daily-return series.
- **"Beat SPY?"** uses a **paired bootstrap**: the same resampled days are
  applied to the agent and SPY together, terminal wealth is compared, and we
  report the **probability the agent beats SPY** and the **margin
  distribution** (p5/median/p95). Near 50% = coin-flip (no edge).
- For a statistically meaningful verdict, per-day (agent, SPY) pairs are
  **pooled across all eight quarters** (≈500 observations) before bootstrapping.

### 2.6 Reproducibility
Deterministic simulator with 67 offline unit tests run in CI. Backtests run via
GitHub Actions (`backtest.yml` single range; `batch_backtest.yml` multi-quarter
matrix + pooled verdict). LLM calls are inherently stochastic, so exact returns
vary run-to-run; conclusions are drawn from the pooled distribution, not a
single path.

---

## 3. Results

### 3.1 Primary study — 8 quarters, 2024–2025 (aggressive vs SPY vs random)

Per-quarter total return:

| Quarter | gemini_aggressive | random_control | spy_buy_hold | Agg beat SPY? |
|---|---|---|---|---|
| 2024 Q1 | +18.76% | +7.89% | +11.01% | ✅ |
| 2024 Q2 | −16.79% | −3.73% | +4.56% | ❌ |
| 2024 Q3 | +13.65% | +6.65% | +5.53% | ✅ |
| 2024 Q4 | +19.08% | +22.86% | +3.42% | ✅ |
| 2025 Q1 | −23.77% | −11.62% | −4.03% | ❌ |
| 2025 Q2 | +8.56% | +36.44% | +10.47% | ❌ |
| 2025 Q3 | −10.38% | +16.45% | +8.16% | ❌ |
| 2025 Q4 | +2.42% | −12.54% | +2.32% | ✅ |

Two-year compounded ($10,000 start):

| Agent | 2-yr total | Ending value | Qtrs beating SPY | Quarterly vol |
|---|---|---|---|---|
| random_control | +67.1% | $16,714 | 4/8 | 16.0% |
| **spy_buy_hold** | **+48.6%** | **$14,863** | — | **4.6%** |
| gemini_aggressive | +1.6% | $10,159 | 4/8 | 15.5% |

Pooled paired bootstrap (502 days / 494 agent–SPY pairs, 1-year horizon):

| Agent | Prob. beat SPY | Median margin vs SPY | 90% band | Median 1-yr return | Prob. of loss |
|---|---|---|---|---|---|
| random_control | 59% | +5.7% | −27.8% … +63.3% | +29.6% | 20% |
| spy_buy_hold | — | — | — | +21.8% | 10% |
| **gemini_aggressive** | **27%** | **−17.6%** | −50.9% … +38.0% | +0.8% | **49%** |

### 3.2 Supporting observation — full persona roster (2026 Q2, fully instrumented)

A separate quarter run with all three personas shows the pattern isn't specific
to "aggressive":

| Agent | Return | Max DD | Ann Vol | Sharpe |
|---|---|---|---|---|
| **spy_buy_hold** | **+14.26%** | 4.49% | 13.9% | **+4.03** |
| gemini_aggressive | +13.33% | 16.03% | 39.0% | +1.50 |
| random_control | +11.31% | 9.82% | 23.4% | +1.98 |
| gemini_balanced | +4.77% | 7.28% | 16.7% | +1.22 |
| gemini_conservative | −3.09% | 3.83% | 9.2% | −1.34 |

No persona beat SPY on return or Sharpe; conservative *lost money in a +14%
quarter* by being too timid.

---

## 4. Findings

1. **The LLM agent did not beat the market.** Aggressive trailed SPY by ~47
   points over two years and wins only 27% of bootstrapped paths — i.e. SPY
   beats it ~3 times out of 4, by a median of ~18%/year.
2. **Its returns were volatility, not skill.** It ran ~3× SPY's volatility and
   its occasional big quarters were erased by catastrophic ones (−17%, −24%,
   −10%). High variance destroys compounding: +1.6% over two years despite
   several strong quarters.
3. **Personas produce coherent *risk* differences but not *return* advantages.**
   Conservative = low vol/low (even negative) return; aggressive = high vol; none
   = alpha.
4. **The random control is the cautionary tale.** It "won" some windows (and the
   2024–25 total) purely by variance, beating the "intelligent" agent — direct
   evidence that observed agent performance is not skill. Its results swing
   wildly by window (it lost 14% in one 2026 quarter, gained 36% in another).
5. **Single quarters lie.** Aggressive beat SPY in 4 of 8 quarters and looked
   excellent in isolation (e.g. 2024 Q1: +19% and a 98% single-quarter
   beat-probability). Only pooling across quarters reveals it has no edge. Any
   claim from 1–2 quarters would have been noise.

**Bottom line:** within a rigorous benchmark, this LLM agent showed **no
risk-adjusted skill versus passive indexing**, and took substantially more risk
to end up flat. This is a clean negative result.

---

## 5. Limitations

- **One model family** (Gemini 3.8 Flash). Other models may differ.
- **Two years, recent regimes.** No 2008/2020-scale crash in-sample.
- **Lean historical info set** (no point-in-time news; §2.4), so historical and
  live behavior aren't identical.
- **Free data caveats.** yfinance prices carry survivorship bias (delisted
  tickers silently absent) and adjusted-vs-raw quirks; the watchlist is a fixed
  set of *current* small-caps, some of which lacked data in older quarters. A
  point-in-time vendor (e.g. Databento/Polygon) would harden this.
- **FRED** uses current data vintage filtered by observation date, not ALFRED
  point-in-time vintages (matters only for revised series like CPI).

These bound the claim to *"in this setup, these agents did not beat the market."*
They do **not** establish "LLMs cannot trade."

---

## 6. Reproduce

```bash
# One quarter
#   Actions → "Backtest (date range)" → start/end, agents, max_tool_calls
# Eight-quarter pooled verdict
#   Actions → "Batch Backtest (multi-quarter)" → agents, max_tool_calls
```

Outputs per run: `summary.md` (leaderboard with risk metrics), `monte_carlo.md`
(beat-SPY distribution); the batch adds `combined_verdict.md` (pooled).

*Attribution and license: see `ATTRIBUTION.md` and `LICENSE`.*
