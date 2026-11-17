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

**Short answer: not as a dependable strategy — LLM decision noise dominates any
edge.** We tested this three ways — more model families, hand-tuned playbook
variants, and a regime-switching meta-agent — and every path ran into the same
wall: **the same configuration's yearly return swings 30–60 points from one run
to the next**, purely from the LLM's run-to-run variance, which is larger than
any edge the tuning produced. You cannot build a dependable strategy, let alone
an income stream, on an engine whose output is that noisy. The one genuinely
useful property that survives is narrow: the baseline agent's **bear-market
capital preservation** — and that is the agent now in live forward testing (§3.7).

The longer story, in the order we learned it:

1. **Primary study (2024–2025, §3.1–3.4):** across three model families (Gemini,
   OpenAI, Anthropic) and nine agents, eight of nine failed to beat SPY. The lone
   exception, **Claude Haiku 5.5 aggressive**, looked spectacular on its first
   run (+84% / 71% beat-rate) but decayed to a pooled **60% / +4.4% margin** over
   three repeats — a modest, noisy tilt, not the market-beater it first seemed.
2. **"Beating SPY" was mostly small-cap beta (§3.6).** The agents trade a $3–$50
   **small-cap** universe; SPY is large-cap. Benchmarked against the honest
   like-for-like index, **IWM (Russell 2000)**, the edge largely vanishes — and
   in **2021**, a large-cap-led bull, **every agent trailed SPY badly** (SPY
   +27%; best agent ~+14%; baseline actually *lost* money). So the agents never
   beat "the market"; they were long small-caps, which sometimes wins and
   sometimes loses to SPY by a lot.
3. **Playbook tuning didn't help — it just moved the noise around (§3.6).** Two
   hand-built variants (`claude_robust`: ATR stops, vol-targeting, earlier
   de-risk; `claude_return`: trailing profits, re-entry) were **indistinguishable
   from the baseline and from each other**: across repeated full-year runs the
   *ranking inverted* (robust best in one 2020 run, worst in another; baseline
   best in one, worst in another). The between-agent gap is swamped by the
   within-agent run-to-run spread.
4. **Regime-switching whipsawed (§3.6).** A meta-agent (`claude_switch`) that ran
   the robust playbook when SPY was above its 200-DMA and the cash-defensive
   baseline when below flipped correctly at the regime boundary — but **whipsawed
   7+ times in two months** when 2022 oscillated around the average, and ended
   the bear **worse than *either* component** (−18% vs baseline +1% / robust
   −11%). The market-timing lag was a net cost, as predicted.

**The one durable, useful property.** Through all of it, the baseline
`claude_aggressive` in a **bear market** is the most reproducible good result in
the project: in 2022 (SPY −21.8%) it clustered near **flat** across ~five runs
(−0.0 / −4.3 / −2.4 / +0.0 / +0.8%, with one −10% bad-draw tail), beating SPY by
~20 points each time, by **going to cash**. That capital-preservation asymmetry —
participate modestly up, step aside down — is real, is the drawdown-averse shape
an income strategy would want, and is why the **live forward test runs this
baseline agent** (§3.7). But it is still *one model, in a backtest with upward
biases, with a noisy tail* — a promising property, not a proven income strategy.

**Bottom line for the practical goal (a dependable income source): no.** The
decision variance is too large, and the three main levers to reduce it (better
model, better playbook, regime-switching) did not work. What remains is a
genuinely valuable **negative result** plus one narrow, real capital-preservation
property worth watching live. See §3.6 for the tuning arc, §3.7 for the live
test, §4 for the consolidated findings.

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
cross-model view (§3.3). The tuning arc (§3.6) adds three Claude-Haiku variants
sharing the same model: `claude_robust` and `claude_return` (hand-tuned
playbooks) and `claude_switch` (a regime meta-agent that picks the robust or
baseline playbook each day by SPY's 200-DMA). A standing playbook is just the
agent's system prompt, so a "variant" is the same model reading different
instructions.

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
- **SPY buy-and-hold** (large-cap) over the identical window is computed and
  ranked alongside the agents (return, max drawdown, daily series).
- **IWM buy-and-hold** (Russell 2000, small-cap) is also written as the honest
  *like-for-like* benchmark: the agents trade a $3–$50 small-cap universe, so
  SPY flatters them and much of any "beat SPY" is small-cap beta (§3.6a).
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

### 3.5 Bear-market regime test — 2022 (SPY −21.8%), 3 runs

The 2024–25 study is all bull market, where an aggressive long-only agent can
look good through beta alone. The decisive test is a down market. 2022 was run
three times (`claude_aggressive` + random control), same discipline as §3.4:

| Run | Prob. beat SPY | Median margin | 2022 compounded | Qtrs beat SPY |
|---|---|---|---|---|
| 2022 run 1 | 87% | +28.7% | −0.0% | 4/4 |
| 2022 run 2 | 84% | +23.5% | −4.3% | 4/4 |
| 2022 run 3 | 84% | +25.4% | −2.4% | 4/4 |
| **Pooled (741 pairs)** | **86%** | **+25.8%** | — | — |
| *SPY, same window* | — | — | *−21.8%* | — |
| *random control (pooled)* | *3%* | *−40.8%* | *≈ −53%* | *—* |

Unlike the bull edge, **this does not decay** — all three runs cluster at 84–87%,
all beat SPY in every quarter, and all finish roughly flat while SPY loses ~22%
and the random control is destroyed (−53%). Drawdowns were **single-digit**
(2–8%) versus SPY's 13–20%.

**Mechanism — it goes to cash.** Quarter-end cash across the runs ranged 54–100%,
and the agent sat out the worst quarters entirely (100% cash in 2022 Q2 or Q3,
depending on run). It chose *no trade* on the large majority of days. So the
"aggressive" agent is, in practice, **drawdown-averse**: when macro/technical
conditions deteriorate it stops buying and holds cash, which costs upside in a
bull (hence the modest, noisy §3.4 edge) but preserves capital in a bear.

Note this is **capital preservation, not profit** — it ended 2022 ≈flat, not up.
For a passive investor that still dominates a −22% index year, and the asymmetry
(modest up, defensive down) is the genuinely income-relevant property. Caveat: it
is still one model family, one bear episode, inside a backtest with upward biases
(§5); the signal warrants a live/paper-traded forward test, not capital yet.

---

### 3.6 The tuning arc — can the agent be *improved* into a dependable edge?

§3.1–3.5 identified `claude_aggressive` (Claude Haiku 5.5) as the only standout.
This section asks the follow-on question — can it be tuned into something
dependable? — and answers it: **no.** Every lever we pulled hit the same wall,
LLM run-to-run decision noise, which turned out to be larger than any edge.

**(a) The benchmark was wrong — "beating SPY" was largely small-cap beta.**
The agents trade a **$3–$50 small-cap** universe; SPY is large-cap. We added an
**IWM (Russell 2000)** buy-and-hold row as the honest like-for-like benchmark.
Against IWM the apparent edge shrinks sharply, and in **2021** — a large-cap-led
bull — *every* agent and IWM itself **trailed SPY** badly:

| 2021 (SPY +26.9%) | return |
|---|---|
| SPY | +26.9% |
| claude_robust | +12–24% (noisy) |
| IWM | +11.8% |
| claude_aggressive | −5 to +4% |
| random_control | +2 to −21% |

So the agents were never beating "the market"; they were long small-caps, which
beat large-cap SPY in 2020 (crash-recovery) and 2022 (bear) and lost to it in
2021. The 2020/2022 "wins" were the universe, not skill.

**(b) Two hand-tuned playbook variants were indistinguishable from the baseline.**
`claude_robust` (ATR-based stops, volatility-targeted sizing, earlier de-risk)
and `claude_return` (trailing-only profits, a re-entry rule) were run head-to-head
with the baseline on identical data. On a cherry-picked 2-quarter probe, robust
looked spectacular (+30.9% in a bull quarter); on a full held-out year it did
not reproduce, and **repeated full-year runs inverted the ranking**:

| Full-year return | 2020 run 1 | 2020 run 2 |
|---|---|---|
| claude_aggressive | **+79.2%** (best) | **+20.8%** (worst) |
| claude_return | +70.1% | +31.9% |
| claude_robust | +56.2% (worst) | **+35.1%** (best) |

The baseline went from best to worst between two runs of the *same* year; robust
went from worst to best. The between-agent differences (~10–20 pts) are **smaller
than the within-agent run-to-run spread** (~40–60 pts). Playbook tuning doesn't
add a detectable edge — it just reshuffles noise.

**(c) The run-to-run noise, laid out.** Every full-year return we recorded, by
agent (deterministic benchmarks shown for contrast):

| Agent | 2020 | 2021 | 2022 |
|---|---|---|---|
| claude_aggressive | +79.2, +20.8 | −5.2, +4.0, −4.4, −7.1 | −0.0, −4.3, −2.4, +0.0, −10.0, +0.8 |
| claude_robust | +56.2, +35.1 | +12.0, +14.3, +23.8, −8.4 | −22.0, −3.1, −10.7 |
| claude_return | +70.1, +31.9 | — | — |
| claude_switch | — | +27.1 | −10.3, −18.1 |
| random_control | +140.6, +77.8 | +4.4, −20.8, +1.8, −0.9 | −58.5, −47.2, −53.1, −53.4, −44.1 |
| *SPY (deterministic)* | *+21.1* | *+26.9* | *−21.8* |
| *IWM (deterministic)* | *—* | *+11.8* | *−25.3* |

The only stable lines are the ones with no LLM in them. Note even the baseline's
bear-defense (2022 column) — the project's most reproducible good property —
clusters near flat but carries a −10% bad-draw tail.

**(d) Regime-switching whipsawed.** Since robust won bulls and the baseline won
bears, we built `claude_switch`: each day, point-in-time, it runs the robust
playbook when SPY is above its 200-day MA (risk-on) and the cash-defensive
baseline when below (risk-off). The mechanism worked — it stayed risk-on all of
2021 and flipped risk-off when SPY broke its 200-DMA on 2022-01-21 — **but then
whipsawed**: in choppy early-2022 it flipped risk-off↔risk-on **seven times in
two months**, churning the book. Result in the bear:

| 2022 (bear) | return |
|---|---|
| claude_aggressive (baseline) | +0.8% |
| claude_robust | −10.7% |
| **claude_switch** | **−18.1%** (worse than both) |

A switch that lands below *both* of its components is the signature of the
switching itself destroying value. Naïve 200-DMA regime-timing added a new
failure mode (whipsaw/lag) without a reliable benefit.

**Conclusion of the arc:** three independent attempts to turn the agent into a
dependable edge — more models (§3.3), playbook variants (b), regime-switching (d)
— all failed for the same reason: **the LLM's decision variance dominates.** The
untested remaining lever is ensembling (averaging many runs per day to shrink
variance ~1/√N), which is expensive and, given the magnitude of the noise,
unlikely to clear the bar — but it is the only avenue not yet closed.

### 3.7 Live forward test (in progress)

Backtests carry upward biases (survivorship, a hindsight-built watchlist,
idealized fills). The only way to know whether the baseline's behavior survives
contact with reality is to trade it on **live, unseen days with fake money**. A
daily paper-trade harness (`v2/live_runner.py`, a scheduled GitHub Actions job,
and a committed ledger) runs the **baseline `claude_aggressive`** — the agent the
evidence favors — plus a random control, forward from Nov 2026. Early days confirm
the mechanics (T+1 fills, daily marks, SPY benchmark) and, encouragingly, the same
**defensive character** seen in backtests: it holds one small position at ~90%
cash rather than churning. It is far too early for a performance read; the real
test is how it behaves through a live drawdown. This is the only part of the study
still accumulating, and it is the honest arbiter of everything above.

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
7. **…but its real strength is defense, not offense (§3.5).** In three runs of
   the 2022 bear market it ended ≈flat (−0.0 / −4.3 / −2.4%) while SPY fell 22%,
   beat SPY in all 12 quarter-runs, held single-digit drawdowns, and pooled to an
   **86% beat-rate that did *not* decay** — by going to cash (54–100%) and sitting
   out the worst quarters. So the headline number people would quote (the bull
   "+84%") is the least reliable thing about it; the durable, reproducible
   property is **capital preservation in down markets**. The weak-but-real bull
   edge and the strong-stable bear defense are the same trait — a drawdown-averse
   agent that participates modestly up and steps aside down.

8. **"Beating SPY" was mostly small-cap beta, not skill (§3.6a).** Benchmarked
   against the honest like-for-like index — **IWM (Russell 2000)**, matching the
   agents' $3–$50 universe — the apparent edge largely vanishes, and in the 2021
   large-cap bull *every* agent trailed SPY (SPY +27%; baseline *lost* money).
   The agents were long small-caps, not beating the market.
9. **Playbook tuning added no detectable edge (§3.6b–c).** Two hand-built variants
   (robust, return) were indistinguishable from the baseline and from each other:
   across repeated full-year runs the ranking *inverted* (e.g. baseline best →
   worst between two runs of the same 2020). The between-agent gap (~10–20 pts) is
   smaller than the within-agent run-to-run spread (~40–60 pts).
10. **Regime-switching made it worse (§3.6d).** A 200-DMA switch between robust
    (risk-on) and the cash baseline (risk-off) flipped correctly at the regime
    boundary but **whipsawed 7× in two months** in choppy 2022 and ended the bear
    **below both components** (−18% vs baseline +1% / robust −11%). Market-timing
    lag was a net cost.
11. **The common cause is LLM decision noise, and it dominates.** The *same*
    configuration swings 30–60 return-points run-to-run (the one stable thing in
    the whole study is the benchmark lines, which contain no LLM). Every attempt
    to engineer a dependable edge — more models, better playbook, regime-switching
    — failed because the signal being tuned is smaller than this variance.

**Bottom line:** within a rigorous benchmark, **no LLM agent produced a
dependable edge over passive indexing**, and the three main ways to engineer one
(more capable models, hand-tuned playbooks, regime-switching) all failed to the
*same* cause: **the model's run-to-run decision variance is larger than any edge**
(the identical configuration swings 30–60 points year-to-year). Most "wins"
against SPY were small-cap beta that reversed against the right benchmark (IWM)
and in a large-cap year (2021). The **one durable, useful property** is the
baseline `claude_aggressive`'s **bear-market capital preservation** — near-flat
across ~five 2022 runs while SPY fell 22%, by going to cash — which is real,
income-relevant in shape, and the reason it is the agent in **live forward
testing** (§3.7). The honest headline: **a clean negative result on
"LLMs as a dependable trading strategy," with one narrow, real capital-preservation
property worth watching live.** For the practical goal of a *dependable income
source*, the answer is **no** — the decision noise is disqualifying, and tuning
does not fix it. This bounds the claim to *"in this setup, these agents did not
beat the market dependably,"* not *"LLMs cannot trade."*

---

## 5. Limitations

- **Three model families now** (Gemini 3.8 Flash full roster; OpenAI `gpt-6-luna`
  and Claude Haiku 5.5 on balanced + aggressive). Still small/fast-tier only —
  frontier/reasoning-tier models and other personas may differ.
- **Run-to-run noise is the dominant limitation.** The same configuration swings
  30–60 return-points between identical runs (§3.6c), so any single-run number —
  including the single-run OpenAI/Gemini results — is unreliable. Conclusions here
  rest on *repeated* runs and on the deterministic benchmark lines; magnitudes for
  the LLM agents are indicative, not precise.
- **Regimes now span 2020–2025** (added 2020 crash-recovery, 2021 bull, 2022 bear
  for the variant/switch work), but each regime-and-agent cell is still only 1–3
  runs — enough to see that noise dominates, not enough to pin small effects.
- **The durable positive (baseline bear-defense) is one model, with a bad-draw
  tail.** Reproduced near-flat across ~five 2022 runs, but with one −10% outlier;
  it is a promising property, not a proven strategy, and remains to be confirmed
  live (§3.7).
- **Ensembling is untested.** Averaging many runs/day would shrink the noise
  ~1/√N; we did not test it (cost), so "tuning cannot fix the noise" is shown for
  model/playbook/regime-switch levers but not for ensembling.
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
