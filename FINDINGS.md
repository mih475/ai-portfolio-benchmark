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

**Short answer: no.** Over eight quarters (2024–2025) **none of the three Gemini
personas beat SPY buy-and-hold** (+48.6% over the two years). The *balanced*
persona came closest — +37.8%, beating SPY in 5 of 8 quarters with near-SPY
volatility — but still trailed and wins only 40% of bootstrapped paths.
*Aggressive* (+1.6%) and *conservative* (+3.2%) failed badly for opposite
reasons: aggressive took ~3× the market's volatility for no payoff, conservative
was too timid to keep up. A dart-throwing **random control matched or beat all
of them** — direct evidence the agents show no persistent skill.

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

### 3.1 Primary study — 8 quarters, 2024–2025, all three personas + controls

Per-quarter total return (SPY buy-and-hold in the last column):

| Quarter | conservative | balanced | aggressive | random | SPY |
|---|---|---|---|---|---|
| 2024 Q1 | +2.73% | +11.39% | +18.76% | +7.89% | +11.01% |
| 2024 Q2 | −3.83% | +4.93% | −16.79% | −3.73% | +4.56% |
| 2024 Q3 | +8.92% | +8.31% | +13.65% | +6.65% | +5.53% |
| 2024 Q4 | −2.42% | +5.77% | +19.08% | +22.86% | +3.42% |
| 2025 Q1 | −0.67% | −1.93% | −23.77% | −11.62% | −4.03% |
| 2025 Q2 | −0.87% | +7.84% | +8.56% | +36.44% | +10.47% |
| 2025 Q3 | +1.28% | −1.63% | −10.38% | +16.45% | +8.16% |
| 2025 Q4 | −1.43% | −1.06% | +2.42% | −12.54% | +2.32% |

Two-year compounded ($10,000 start), ranked:

| Agent | 2-yr total | Ending value | Qtrs beating SPY | Quarterly vol |
|---|---|---|---|---|
| random_control | +67.1% | $16,714 | 4/8 | 16.0% |
| **spy_buy_hold** | **+48.6%** | **$14,863** | — | **4.6%** |
| gemini_balanced | +37.8% | $13,782 | 5/8 | 4.8% |
| gemini_conservative | +3.2% | $10,322 | 2/8 | 3.7% |
| gemini_aggressive | +1.6% | $10,159 | 4/8 | 15.5% |

Pooled paired bootstrap vs SPY (≈500 agent–SPY day-pairs per agent, 1-year
horizon). "Prob. beat SPY" near 50% = coin-flip / no edge:

| Agent | Prob. beat SPY | Median margin vs SPY | 90% band | Median 1-yr return | Prob. of loss |
|---|---|---|---|---|---|
| random_control | 59% | +5.7% | −27.8% … +63.3% | +29.6% | 20% |
| spy_buy_hold | — | — | — | +21.8% | 10% |
| gemini_balanced | 40% | −4.0% | −26.1% … +24.9% | +17.5% | 16% |
| gemini_aggressive | 27% | −17.6% | −50.9% … +38.0% | +0.8% | 49% |
| gemini_conservative | 12% | −17.0% | −36.3% … +7.1% | +1.4% | 44% |

(Aggressive + random and conservative + balanced were run as two separate
batches; SPY buy-and-hold is deterministic over identical dates, so it anchors
both consistently.)

### 3.2 Independent corroboration — 2026 Q2 (different year, full roster in one run)

A separate single-quarter run in 2026, all personas together, shows the same
ordering out-of-sample:

| Agent | Return | Max DD | Ann Vol | Sharpe |
|---|---|---|---|---|
| **spy_buy_hold** | **+14.26%** | 4.49% | 13.9% | **+4.03** |
| gemini_aggressive | +13.33% | 16.03% | 39.0% | +1.50 |
| random_control | +11.31% | 9.82% | 23.4% | +1.98 |
| gemini_balanced | +4.77% | 7.28% | 16.7% | +1.22 |
| gemini_conservative | −3.09% | 3.83% | 9.2% | −1.34 |

No persona beat SPY on return or Sharpe.

---

## 4. Findings

1. **No persona beat the market.** All three trailed SPY's +48.6% over two
   years, and none wins more than ~40% of bootstrapped paths vs SPY.
2. **Balanced is the only respectable one — and it still lost.** It returned
   +37.8% at near-SPY volatility (4.8% vs 4.6%) and beat SPY in 5 of 8 quarters,
   but a −4% median margin and a 40% beat-rate mean it behaves like a slightly
   *worse* index fund, not a market-beater.
3. **Aggressive and conservative fail for opposite reasons.** Aggressive ran ~3×
   SPY's volatility, and its big quarters were erased by catastrophic ones
   (−17%, −24%, −10%) → +1.6% over two years with a 49% chance of loss.
   Conservative was so timid (3.7% vol) it couldn't keep up → +3.2%, and *lost
   money in up quarters*. Persona prompts move *risk* coherently but produce no
   *return* advantage.
4. **The random control is the cautionary tale.** It "won" the 2024–25 total and
   beats SPY 59% of the time in the bootstrap — purely by taking variance, with
   no skill and a 20% loss probability. A dart-thrower matching or beating the
   "intelligent" agents is the clearest possible evidence of no alpha.
5. **Single quarters lie.** Aggressive beat SPY in 4 of 8 quarters and looked
   excellent in isolation (e.g. 2024 Q1: +19% and a 98% single-quarter
   beat-probability). Only pooling across quarters reveals it has no edge. Any
   claim from 1–2 quarters would have been noise.

**Bottom line:** within a rigorous benchmark, no Gemini persona showed
**risk-adjusted skill versus passive indexing**. The best (balanced) merely
approximated a slightly-worse index fund; the others destroyed value by taking
too much or too little risk; and a random control was indistinguishable from —
or better than — the agents. This is a clean negative result.

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
