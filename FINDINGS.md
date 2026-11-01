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

**Short answer: mostly no — with one modest, bull-market-only exception.** Across
three model families (Google Gemini, OpenAI, Anthropic) and nine LLM agents run
over the same eight quarters (2024–2025), **eight of nine failed to beat SPY
buy-and-hold** (+48.6% / ≈+22% median 1-yr). The only agent that beats it is
**Anthropic Claude Haiku 5.5 on the *aggressive* persona** — but the edge is
**small and noisy**, not the headline it first looked like.

Run once, Claude-aggressive looked spectacular: +84% over two years, 71%
bootstrap beat-rate, +11.2% median margin. But repeating the *identical* run
three times (to separate signal from LLM run-to-run noise) showed the edge
decaying each time — **71% → 61% → 45%** beat-rate; **+84% → +62% → +44%**
compounded — with the third run landing *below* SPY. **Pooled across all three
runs (1,482 day-pairs), the honest estimate is a 60% beat-rate and a +4.4% median
margin**: a real but modest tilt, with a −21% downside tail and a ~40% chance of
simply trailing SPY in any given year. The original 71% was the lucky draw, not
the truth.

Every other agent trailed outright: Claude's own *balanced* persona (13%
beat-rate), both OpenAI personas (`gpt-6-luna` balanced 25% / aggressive 13%),
and all three Gemini personas (≤40%). A dart-throwing **random control** is pure
noise — 59% beat-rate in one draw, 11–18% in two others, averaging well below SPY
— confirming the baseline has no persistent edge (and that Claude's staying
*above* a coin-flip across three draws is itself the signal).

Two caveats keep even the modest Claude edge from being a usable result: it is
**entirely a bull-market** finding (2024–25 SPY +49%), and an aggressive long-only
agent amplifying an uptrend can look good purely through beta. Whether the tilt
survives a **bear regime (2022)** is untested and decisive — and the single-run
OpenAI/Gemini numbers carry the same single-draw uncertainty that inflated
Claude's first run. See §3.3–§3.4.

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
The original study used **Gemini 3.8 Flash** (`gemini-3.8-flash`, all three
personas); it was later extended to two more small/fast-tier models —
**OpenAI `gpt-6-luna`** and **Anthropic Claude Haiku 5.5** (`claude-haiku-5-5`) —
on the balanced and aggressive personas, over the identical eight quarters, for a
cross-model view (§3.3).

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

### 3.3 Cross-model extension — OpenAI & Anthropic, same 8 quarters (2024–2025)

The benchmark was then run for two more model families on the balanced and
aggressive personas (conservative was dropped — it failed everywhere), over the
identical 2024–2025 quarters, so all three families are directly comparable.

> **Data-integrity note.** The first Anthropic batch was discarded: `claude-haiku-5-5`
> returns signed *thinking* blocks, and a bug in the forced-propose fallback
> replayed them under a mismatched tools list, producing 8,469 API 400s that
> silently flat-lined the Claude agents. The fix (keep the full tools list;
> fall back to auto tool-choice / thinking-strip) is covered by a CI test, and
> the numbers below are from the clean re-run (0 propose failures, 0 flags).
> OpenAI was unaffected.

Two-year compounded ($10,000 start), all nine agents + controls, ranked:

| Agent | Model family | 2-yr total | Ending value | Qtrs beating SPY |
|---|---|---|---|---|
| **claude_aggressive** | Anthropic | **+84.1%** | **$18,414** | **5/8** |
| random_control | — (luck) | +67.1% | $16,714 | 4/8 |
| **spy_buy_hold** | — | **+48.6%** | **$14,863** | — |
| gemini_balanced | Gemini | +37.8% | $13,782 | 5/8 |
| chatgpt_balanced | OpenAI | +21.5% | $12,148 | 2/8 |
| claude_balanced | Anthropic | +5.1% | $10,510 | 1/8 |
| gemini_conservative | Gemini | +3.2% | $10,322 | 2/8 |
| gemini_aggressive | Gemini | +1.6% | $10,159 | 4/8 |
| chatgpt_aggressive | OpenAI | −5.5% | $9,454 | 1/8 |

Pooled paired bootstrap vs SPY (≈500 agent–SPY day-pairs each, 1-yr horizon;
each agent paired against the SPY from its own run — SPY's median 1-yr return is
+21.8% across all runs). "Prob. beat SPY" near 50% = coin-flip:

| Agent | Prob. beat SPY | Median margin vs SPY | 90% band | Median 1-yr return | Prob. of loss |
|---|---|---|---|---|---|
| **claude_aggressive** | **71%** | **+11.2%** | −17.8% … +52.3% | +36.0% | 4% |
| random_control | 59% | +5.7% | −27.8% … +63.3% | +29.6% | 20% |
| spy_buy_hold | — | — | — | +21.8% | 10% |
| gemini_balanced | 40% | −4.0% | −26.1% … +24.9% | +17.5% | 16% |
| gemini_aggressive | 27% | −17.6% | −50.9% … +38.0% | +0.8% | 49% |
| chatgpt_balanced | 25% | −9.7% | −29.8% … +15.1% | +10.1% | 10% |
| chatgpt_aggressive | 13% | −20.8% | −43.3% … +11.0% | −2.8% | 56% |
| claude_balanced | 13% | −16.0% | −35.7% … +8.5% | +2.4% | 41% |
| gemini_conservative | 12% | −17.0% | −36.3% … +7.1% | +1.4% | 44% |

`claude_aggressive` is the **only agent above a coin-flip**. **These tables are
each from a single run; the Claude-aggressive row is its *first* run and later
proved to be the high draw** — see §3.4 for the three-run reproducibility result
that revises it down to a 60% beat-rate / +4.4% margin. The single-run OpenAI and
Gemini rows have not been repeated and carry the same single-draw uncertainty.

### 3.4 Reproducibility of the Claude-aggressive result — 3 runs, same 8 quarters

LLM output is stochastic even at temperature 0, so the headline run was repeated
twice more on the identical quarters. The edge decayed each time:

| Run | Prob. beat SPY | Median margin | 2-yr compounded | Qtrs beat SPY |
|---|---|---|---|---|
| Original | 71% | +11.2% | +84.1% | 5/8 |
| Repeat 1 | 61% | +4.7% | +61.9% | 4/8 |
| Repeat 2 | 45% | −2.0% | +43.8% | 3/8 |
| **Pooled (1,482 day-pairs)** | **60%** | **+4.4%** | — | — |

Two things stand out. First, the **per-quarter wins don't reproduce**: the
original won big on 2025 Q2–Q3, Repeat 1 on 2024 Q1 and 2025 Q4, Repeat 2 on
2024 Q4 — the agent trades very differently each run, so the edge can't be
pinned to specific quarters. It is a **diffuse, noisy, mildly positive tilt**, not
a repeatable playbook. Second, the **direction is consistent** (all three runs
cluster around or above SPY; none collapsed) while the **random control swung
59% → 11% → 18%** across its draws — so Claude staying near/above a coin-flip
every time, against a baseline that flip-flops, is the actual signal. But at a
pooled **60% / +4.4%** with a −21% tail, it is a weak edge, not a dependable one.

---

## 4. Findings

1. **No Gemini persona beat the market** (primary study, §3.1). All three trailed
   SPY's +48.6% over two years, and none wins more than ~40% of bootstrapped
   paths vs SPY. (Findings 1–5 concern the Gemini roster; the cross-model result
   is in 6–7.)
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

6. **One model broke the pattern — but modestly. Claude Haiku 5.5, aggressive.**
   Extending to OpenAI and Anthropic, every persona kept losing to SPY *except*
   Claude's aggressive agent. Its first run looked spectacular (71% beat-rate,
   +84% / 2yr), but three runs on identical quarters decayed 71% → 61% → 45%
   (one run below SPY). **Pooled, the real edge is 60% beat-rate / +4.4% median
   margin** — above a coin-flip, but small, with a −21% downside tail. Still, it
   is the only agent to stay above 50% across repeats, while the random control
   swung 59/11/18% — so the tilt is real, just not large.
7. **The same discipline that sank "aggressive looks great" applies here too.**
   The headline 71% was the lucky draw; the per-quarter wins don't reproduce
   (§3.4); Claude *balanced* failed like everyone else (13%); and — decisively —
   the whole result is **bull-market only** (2024–25 SPY +49%). An aggressive
   long-only agent amplifying a rising market can post a small edge through beta
   alone. The bear-regime test (2022) is untested and will likely be decisive.

**Bottom line:** within a rigorous benchmark, **eight of nine LLM agents showed
no edge versus passive indexing** — most trailed SPY outright, and a random
control confirmed the baseline has none. The one exception, **Claude Haiku 5.5
(aggressive)**, has a **real but modest tilt** (pooled 60% beat-rate, +4.4%
margin over three runs) — not the market-beater its first run suggested, not yet
tested in a down market, and nowhere near the consistency a usable/income-grade
strategy would need. The honest headline: **mostly negative, with one small,
fragile, bull-market-only positive that still needs a bear-market test before it
means anything.**

---

## 5. Limitations

- **Three model families now** (Gemini 3.8 Flash full roster; OpenAI `gpt-6-luna`
  and Claude Haiku 5.5 on balanced + aggressive). Still small/fast-tier only —
  frontier/reasoning-tier models and other personas may differ.
- **Claude-aggressive is reproducible only in direction, not magnitude.** Three
  runs gave 71% / 61% / 45% beat-rates (pooled 60%), so any single run's headline
  is unreliable; the OpenAI and Gemini numbers are single runs and carry the same
  risk. The **bear-market test (2022) is not yet run** and is the decisive open
  question — the entire positive result is from a bull market.
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
