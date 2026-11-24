# No Free Alpha: Benchmarking Autonomous LLM Trading Agents Against Passive Indexing

*Working paper · revised 2026-11-23 (first draft 2026-10-29)*

> Across model families, hand-tuned strategy playbooks, and a regime-switching
> meta-agent (2020–2025), no autonomous LLM trading agent produced a *dependable*
> edge over passive indexing. Run-to-run model decision noise — 30–60 return-points
> on the *identical* configuration — dominates any edge, most apparent "beating
> SPY" is small-cap beta, and the one durable, useful property we isolated is a
> single agent's **bear-market capital preservation**, now being validated live.

## Abstract

We test whether autonomous large-language-model (LLM) trading agents can beat a
passive benchmark in US equities, and — when one appears to — whether the edge is
real, reproducible, and improvable. Agents built on Google Gemini, OpenAI, and
Anthropic models trade a rules-enforced, point-in-time simulator (long-only
$3–$50 universe, T+1 execution, mandatory stops) against a passive SPY benchmark,
a small-cap IWM benchmark, and a random-trading control. In the primary study
(Gemini, 2024–2025, eight quarters) no persona beat SPY on a risk-adjusted basis
and a random control matched or beat all of them. Extending the study exposes a
deeper result: (i) the single agent that stood out, Anthropic Claude Haiku 5.5
(aggressive), decayed from a 71% to a pooled 60% beat-rate over repeated runs;
(ii) apparent SPY-beating was largely small-cap beta that reversed against IWM and
in a large-cap-led year (2021); (iii) two hand-tuned playbook variants were
statistically indistinguishable from the baseline, with the *ranking inverting
between runs of the same year*; and (iv) a 200-day-MA regime-switching meta-agent
whipsawed and underperformed both of its components. The common cause is
**LLM run-to-run decision variance that exceeds any edge** — the only stable lines
in the entire study are the ones with no model in them. The lone durable, useful
property is the baseline agent's bear-market capital preservation (near-flat
across ~5 runs of 2022 while SPY fell 22%, by going to cash), now under live
paper-trading validation. We release the full benchmark, tests, and reproduction
workflows. The result is a clean negative on "LLMs as a dependable trading
strategy," with one narrow, real capital-preservation property worth watching.

## 1. Introduction

LLMs can now call tools, read market data, and emit structured decisions,
prompting a natural question: can an LLM run a portfolio and beat the market?
Public demonstrations tend to report a single impressive run, which is exactly the
setup most vulnerable to look-ahead bias, survivorship bias, and small-sample luck.

This project asks the question under conditions designed to make a positive result
hard to fake: a deterministic simulator that enforces trading rules in code; strict
point-in-time data so a historical agent cannot see the future; passive SPY *and*
small-cap IWM benchmarks; a random-trading control to calibrate luck; and a paired
bootstrap over pooled quarters so the verdict carries statistical weight. When a
candidate edge did appear, we then did what the single-run demonstrations never do:
we tried to *break it* — repeating runs, testing other model families, correcting
the benchmark, hand-tuning the strategy, and building a regime-switcher to combine
the best behaviors.

**Research question.** Does an autonomous LLM agent beat passive indexing on a
risk-adjusted basis; if so, is the edge reproducible; and can it be engineered into
something dependable?

**Contribution.** (1) An open, rules-enforced, look-ahead-free benchmark with
passive (SPY), like-for-like (IWM), and random controls. (2) A statistical protocol
— daily-return risk metrics plus a pooled paired bootstrap — that reports the
*probability* an agent beats the market rather than a single return. (3) A clean
negative result that survives three independent attempts to engineer an edge
(more capable models, hand-tuned playbooks, regime-switching), all defeated by the
same cause: model decision noise larger than any signal. (4) One isolated, durable,
income-relevant property (bear-market capital preservation) and a live forward test
of it.

**Headline finding.** No LLM agent produced a dependable edge. The identical
configuration swings 30–60 return-points between runs; the only stable performers
are the deterministic benchmark lines. Most "wins" over SPY were small-cap beta.
The one real, reproducible property is defensive: the baseline agent preserves
capital in bear markets by moving to cash.

## 2. Background & Related Work

**LLM agents in finance.** A growing body of demonstrations wires LLMs to market
data and tools and reports trading performance. Most share two weaknesses: they
evaluate over short windows, and they do not rigorously prevent the model from
accessing information unavailable at the simulated decision time. A third, which
this study foregrounds, is **nondeterminism**: a single reported run says little
when the same agent's output varies widely between runs.

**Backtesting pitfalls.** The standard hazards are well known: *look-ahead bias*,
*survivorship bias*, *data-snooping*, and *ignoring costs*. An LLM adds a subtler
channel: a model trained through some cutoff may "remember" how a past period
resolved, so a backtest must also deny it live tools that would reveal the future.
And because LLM output is stochastic, a backtest must be *repeated*, not run once.

**Efficient markets as the null.** The efficient-market hypothesis predicts that,
net of risk and costs, active strategies should not reliably beat a passive
benchmark. The interesting outcome is not "the agent made money" (a rising market
does that) but "the agent beat buy-and-hold on a risk-adjusted basis, *repeatably*."
This motivates our reference points — passive SPY, like-for-like IWM, and a random
control — and our focus on pooled, risk-adjusted statistics over single-run returns.

## 3. Experimental Design

### 3.1 Simulation environment ("Code is Law")

A deterministic simulator executes and scores trades; the LLM only *proposes* them.
Rules are enforced in code, not by prompt:

| Rule | Value |
| --- | --- |
| Universe | Long-only US equities, $3–$50 (enforced at fill) |
| Execution | Decide after close, fill at next open (T+1), 0.1% slippage |
| Stops / targets | Checked vs daily High/Low; gap-throughs fill at the open |
| Position sizing | 5–25% per position, max 15 positions, max 3 new buys/day |
| Risk | Every buy must carry a stop-loss |
| Fairness | One frozen OHLC set per day shared by all agents |

### 3.2 Agents and personas

Each agent is a model × persona; personas (conservative / balanced / aggressive)
differ only in a system-prompt risk mandate. The primary study uses **Gemini 3.8
Flash** (temperature 0); it was later extended to **OpenAI `gpt-6-luna`** and
**Anthropic Claude Haiku 5.5** on the balanced and aggressive personas. The tuning
arc (§4.7) adds three Claude-Haiku **variants** sharing the same model: `robust`
(ATR-based stops, volatility-targeted sizing, earlier de-risk), `return`
(trailing-only profit-taking, a re-entry rule), and `switch` (a meta-agent that
each day picks the robust or baseline playbook by SPY's 200-day MA). Because a
standing playbook is just the agent's system prompt, a "variant" is the same model
reading different instructions. A **random control** (no LLM) trades randomly within
the same rules and daily watchlist — the skill-versus-luck baseline.

### 3.3 Data

Prices from Yahoo Finance (yfinance); macro indicators from FRED. Both free.
Historical prices are cached on disk and retried with backoff; non-finite marks
are rejected and carried forward so a single bad price cannot corrupt an account.

### 3.4 Point-in-time integrity (no look-ahead)

A backtest for a past date must not see the future. Enforced: (a) prices come from
a window *ending at* the simulation date; (b) FRED series are fetched as-of that
date; (c) date-aware tools receive the as-of date, while tools that can only return
the present (web search, news, fundamentals) are **disabled** on a past date; (d)
the live market narrative and catalyst watchlist are **suppressed** for historical
snapshots; (e) the regime signal (§4.7d) uses only closes up to the decision date.
The honest cost: historical agents trade on a leaner information set than a live
agent would — the correct trade-off, since fabricated as-of news would be worse.

### 3.5 Benchmarks

Three reference points over the identical window: **SPY buy-and-hold** (passive,
large-cap), **IWM buy-and-hold** (Russell 2000, small-cap — the *like-for-like*
benchmark, since the agents trade a $3–$50 small-cap universe and SPY flatters
them), and the **random control** (luck baseline).

### 3.6 Statistical method

Per run we report return, maximum drawdown, annualized volatility, and Sharpe
(rf = 0). To answer "beats SPY?" we use a **paired bootstrap**: the same resampled
days are applied to agent and SPY together, terminal wealth compared, and we report
the probability the agent beats SPY and the margin distribution. Per-day pairs are
**pooled across quarters** before bootstrapping. Critically, because LLM calls are
stochastic even at temperature 0, we **repeat** each configuration and read
conclusions from the *spread across runs*, not any single path. The simulator and
analysis scripts are covered by stdlib-only unit tests in CI.

## 4. Results

### 4.1 Primary study (Gemini, 2024–2025): no persona beat SPY

All eight quarters ran cleanly. Two-year compounded ($10,000 start):

| Agent | 2-yr total | Qtrs beating SPY | Quarterly vol |
| --- | --- | --- | --- |
| random_control | +67.1% | 4 / 8 | 16.0% |
| **spy_buy_hold** | **+48.6%** | — | **4.6%** |
| gemini_balanced | +37.8% | 5 / 8 | 4.8% |
| gemini_conservative | +3.2% | 2 / 8 | 3.7% |
| gemini_aggressive | +1.6% | 4 / 8 | 15.5% |

Pooled paired bootstrap (≈500 day-pairs, 1-yr horizon; near 50% = no edge):
random 59%, **balanced 40%**, aggressive 27%, conservative 12%. No agent reaches a
coin-flip; the dart-throwing control beats all three. A separate 2026 Q2 run
reproduced the ordering (no persona beat SPY on return or Sharpe). §5 explains why
the random control "won" (lottery-ticket concentration + buy-and-hold beta), and
why it is still not skill.

### 4.2 Cross-model extension: one standout, then it decays

Adding OpenAI and Anthropic (balanced + aggressive, same eight quarters): both
OpenAI personas trailed SPY (`gpt-6-luna` balanced 25% / aggressive 13% beat-rate),
and Claude's balanced trailed (13%). The one exception, **Claude Haiku 5.5
aggressive**, looked spectacular on its first run — +84% over two years, a 71%
beat-rate. But repeating the identical run three times showed the edge decaying
every time — **71% → 61% → 45%** beat-rate; **+84% → +62% → +44%** compounded, the
third run landing *below* SPY. Pooled, the honest estimate is a **modest 60%
beat-rate / +4.4% median margin**, not the market-beater it first appeared. (A
notable null: handing this exact playbook to `gpt-6-luna` did *not* reproduce the
behavior — it lost −24% in a 2022 bear — so the property is model-specific, not
prompt-portable.)

### 4.3 The one durable property: bear-market capital preservation

Where the bull-market edge is noisy, the baseline `claude_aggressive` in a **bear
market** is the project's most reproducible good result. Across runs of 2022 (SPY
−21.8%) it ended near **flat** — −0.0 / −4.3 / −2.4 / +0.0 / +0.8%, with one −10.0%
bad-draw tail — beating SPY by ~20 points each time, with single-digit drawdowns,
by **going to cash** (up to 100% cash, sitting out the worst quarters). This is
capital preservation, not profit, but for a drawdown-averse objective it is exactly
the right shape, and it does not decay on repetition the way the bull edge does.

### 4.4 Benchmark correction: "beating SPY" was mostly small-cap beta

The agents trade a $3–$50 **small-cap** universe; SPY is large-cap. Against the
like-for-like **IWM** benchmark the apparent edge largely vanishes, and in **2021**
— a large-cap-led bull — *every* agent and IWM itself trailed SPY badly:

| 2021 (SPY +26.9%) | return |
| --- | --- |
| SPY | +26.9% |
| claude_robust | +12% to +24% (noisy) |
| IWM | +11.8% |
| claude_aggressive | −5% to +4% |
| random_control | +2% to −21% |

So the agents were never beating "the market"; they were long small-caps, which
beat SPY in 2020 (crash-recovery) and 2022 (bear) and lost to it in 2021. The
2020/2022 "wins" were the universe, not skill.

### 4.5 Tuning adds no edge — only reshuffled noise

Two hand-tuned playbook variants (`robust`, `return`) were run head-to-head with
the baseline on identical data. On a cherry-picked 2-quarter probe `robust` looked
spectacular; on a full held-out year it did not reproduce, and repeated full-year
runs **inverted the ranking**:

| Full-year return | 2020 run 1 | 2020 run 2 |
| --- | --- | --- |
| claude_aggressive | **+79.2%** (best) | **+20.8%** (worst) |
| claude_return | +70.1% | +31.9% |
| claude_robust | +56.2% (worst) | **+35.1%** (best) |

The baseline went from best to worst between two runs of the *same* year. The
between-agent gaps (~10–20 pts) are smaller than the within-agent run-to-run spread
(~40–60 pts): tuning the playbook does not add a detectable edge.

### 4.6 The noise, laid bare

Every full-year return recorded, by agent (deterministic benchmarks for contrast):

| Agent | 2020 | 2021 | 2022 |
| --- | --- | --- | --- |
| claude_aggressive | +79.2, +20.8 | −5.2, +4.0, −4.4, −7.1 | −0.0, −4.3, −2.4, +0.0, −10.0, +0.8 |
| claude_robust | +56.2, +35.1 | +12.0, +14.3, +23.8, −8.4 | −22.0, −3.1, −10.7 |
| claude_return | +70.1, +31.9 | — | — |
| claude_switch | — | +27.1 | −10.3, −18.1 |
| random_control | +140.6, +77.8 | +4.4, −20.8, +1.8, −0.9 | −58.5, −47.2, −53.1, −53.4, −44.1 |
| *SPY (deterministic)* | *+21.1* | *+26.9* | *−21.8* |
| *IWM (deterministic)* | *—* | *+11.8* | *−25.3* |

The only stable lines are the ones with no LLM in them.

### 4.7 Regime-switching made it worse

Since `robust` won bulls and the baseline won bears, we built `claude_switch`:
each day, point-in-time, it runs the robust playbook when SPY is above its 200-day
MA (risk-on) and the cash-defensive baseline when below (risk-off). The mechanism
worked — risk-on through 2021, flipping risk-off when SPY broke its 200-DMA on
2022-01-21 — but then **whipsawed seven times in two months** as 2022 oscillated
around the average, and ended the bear **below both of its components**:

| 2022 (bear) | return |
| --- | --- |
| claude_aggressive (baseline) | +0.8% |
| claude_robust | −10.7% |
| **claude_switch** | **−18.1%** |

A switch that lands below both parts is the signature of the switching itself
destroying value. Naïve 200-DMA regime-timing added a new failure mode (whipsaw and
lag) without a reliable benefit.

### 4.8 Live forward test (in progress)

Backtests carry upward biases (survivorship, hindsight-built watchlist, idealized
fills). A daily paper-trade harness trades the baseline `claude_aggressive` — the
agent the evidence favors — plus a random control, on live, unseen days with fake
money (from Nov 2026). Early days confirm the mechanics and, encouragingly, the
same defensive character seen in backtests: it holds one small position at ~90%
cash rather than churning, and on a down day fell far less than the market. It is
too early for a performance read; the real test is a live drawdown. This is the only
part of the study still accumulating, and it is the honest arbiter of everything
above.

## 5. Case Analysis: Why the Random Control "Won"

The control's high returns are not evidence that randomness trades well; they show
how misleading raw return is without a risk and luck lens. **Lottery-ticket
concentration:** its best quarters were carried by one or two high-beta small-caps
that happened to multiply. **Buy-and-hold beta vs agent churn:** all agents draw
from the same volatile $3–$50 watchlist; the random agent mostly buys and holds,
and in windows where those small-caps ran, passively holding high-beta names beat
both SPY and the LLM agents, who traded the *same* names actively — selling winners
early and getting stopped out on noise. **Why it is still not skill:** the control
is the riskiest participant (high volatility, deep drawdowns, and in 2022 it lost
~50%). Its high-variance mean swung from +140% (2020) to −53% (2022). The lesson is
not "random is good" but "the window favored high-beta buy-and-hold, and the agents
were beaten by a dart-thrower" — the sharpest evidence of no alpha.

## 6. Discussion

**Decision noise dominates.** The central empirical fact is that the *same*
configuration swings 30–60 return-points between runs. This is larger than any
edge we could find or engineer, and it is why every improvement attempt failed:
more capable models (§4.2), hand-tuned playbooks (§4.5), and regime-switching
(§4.7) each tried to tune a signal smaller than the noise. The only stable
performers in the entire study are the deterministic benchmark lines.

**Beta, not alpha.** Correcting the benchmark (§4.4) dissolves most of the apparent
skill: the agents were long small-caps, and "beating SPY" tracked when small-caps
beat large-caps, reversing in 2021. Against the like-for-like IWM the edge is
negligible.

**Active churn is a tax in a trending market.** As in the primary study, agents
repeatedly traded out of names that then ran, paying slippage and stop-outs. LLMs
reproduce this familiar failure rather than escape it.

**The one real property is defensive.** The exception to all of the above is the
baseline's bear-market cash-defense (§4.3) — reproducible, model-specific, and
income-relevant in *shape*. It is not alpha (it preserves, it does not generate),
but it is the one behavior that survived every robustness check, which is why it is
the one we are testing live.

**On single runs.** A single Claude-aggressive run looked like a market-beater
(+84%, 71%); a single robust probe looked spectacular (+30.9%). Both dissolved on
repetition. Any claim built on one or two runs — the usual format for "my AI beats
the market" demonstrations — would here have been noise.

## 7. Limitations

These bound the claim to *"in this setup, these agents did not beat the market
dependably."* They do not establish that LLMs cannot trade.

- **Run-to-run noise is the dominant limitation.** Single-run numbers (including
  the single-run OpenAI/Gemini results) are unreliable; conclusions rest on
  repeated runs and on the deterministic benchmark lines.
- **Regimes span 2020–2025** (crash-recovery, bull, bear) but each regime-and-agent
  cell is only 1–3 runs — enough to show noise dominates, not to pin small effects.
- **The durable positive is one model, with a bad-draw tail**, and awaits live
  confirmation (§4.8).
- **Ensembling is untested.** Averaging many runs per day would shrink the noise
  ~1/√N; cost precluded testing it, so "tuning cannot fix the noise" is shown for
  the model/playbook/regime-switch levers but not for ensembling.
- **Lean historical information set** (no as-of news), **free-data caveats**
  (yfinance survivorship and adjusted-price quirks; a watchlist of *current*
  small-caps), **FRED vintage** (observation-date filtering, not ALFRED), and
  **no explicit transaction costs beyond slippage** — as in the primary study.

## 8. Conclusion and Future Work

Within a rigorous benchmark — rules enforced in code, strictly point-in-time data,
passive and like-for-like benchmarks, a random control, and repeated runs — **no
LLM agent produced a dependable edge over passive indexing**, and the three main
ways to engineer one (more capable models, hand-tuned playbooks, regime-switching)
all failed to the same cause: **the model's run-to-run decision variance is larger
than any edge.** Most apparent SPY-beating was small-cap beta that reversed against
the right benchmark. The one durable, useful property is the baseline agent's
**bear-market capital preservation**, now under live validation. This is a clean
negative result on "LLMs as a dependable trading strategy," with one narrow, real
capital-preservation property worth watching — arguably more useful than a noisy
positive.

**The decisive open question is variance, not strategy.** The untested lever is
**ensembling** — averaging many runs per day to shrink decision noise ~1/√N — which
is the only avenue not closed here and the natural next study, alongside
point-in-time vendor data, explicit transaction costs, and a longer live forward
test. The code, tests, and one-click reproduction workflows are released so these
extensions can be run directly.

## Appendix

### A. Reproducibility

The benchmark runs via GitHub Actions. *Backtest (date range)* runs a single
window; *Batch Backtest (multi-quarter)* runs quarters as a matrix and pools them
into a combined verdict. Inputs: `agents`, `max_tool_calls`, `quarters`, and
`strict_prices` (strict price-integrity on for a final audited run, off for
iterative exploration). A live paper-trade workflow runs the baseline daily and
commits a ledger. The simulator and analysis scripts are covered by stdlib-only
unit tests in CI.

### B. Enforced constraints

Long-only; $3–$50 price band at fill; T+1 at the next open with 0.1% slippage;
stops/targets vs daily High/Low with gap-throughs filling at the open; 5–25% per
position; ≤15 positions; ≤3 new buys/day; mandatory stop-loss on every buy; one
frozen daily OHLC set shared across agents; non-finite prices rejected and carried
forward. Starting capital $10,000 per agent per run.

### C. AI-assistance disclosure

This benchmark's code, test suite, and the drafting of this document were produced
with substantial assistance from an AI coding assistant (Anthropic's Claude), under
the direction of the human author, who defined the research questions, reviewed the
methodology and code, directed each design decision, verified the results, and takes
full responsibility for the work. No AI system is an author. Any venue submission
should follow that venue's specific AI-disclosure requirements.

### D. Availability

Source, tests, workflows, and the `FINDINGS.md` summary are in the project
repository. Results artifacts are produced by the workflows above and can be
regenerated.
