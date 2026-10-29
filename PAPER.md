# No Free Alpha: Benchmarking Autonomous LLM Trading Agents Against Passive Indexing

*Working paper · 2026-10-29*

> Across eight quarters of point-in-time backtests (2024–2025), no Gemini-based trading agent — conservative, balanced, or aggressive — beat a passive S&P 500 buy-and-hold on a risk-adjusted basis, and a random control matched or beat all of them.

## Abstract

We test whether autonomous large-language-model (LLM) trading agents can beat a passive S&P 500 buy-and-hold benchmark (SPY) in US equities. Three risk personas (conservative, balanced, aggressive) built on Google's Gemini 3.8 Flash trade a rules-enforced simulator over eight quarters (2024–2025), with a random-trading control and a passive SPY benchmark. The simulator enforces trading rules in code (long-only $3–$50 universe, T+1 execution, mandatory stops), and all historical data is served point-in-time to eliminate look-ahead. We evaluate with return, maximum drawdown, annualized volatility, Sharpe ratio, and a paired bootstrap that estimates each agent's probability of beating SPY. Over two years, SPY returned +48.6%; the best agent (balanced) returned +37.8% and beat SPY in only 40% of bootstrapped paths, while aggressive (+1.6%) and conservative (+3.2%) fared far worse. A random control returned +67.1% — by taking the most risk, not by skill. No persona showed risk-adjusted skill versus passive indexing. We release the full benchmark, tests, and reproduction workflows.

## 1. Introduction

LLMs can now call tools, read market data, and emit structured decisions, prompting a natural question: can an LLM run a portfolio and beat the market? Public demonstrations tend to report a single impressive run, which is exactly the setup most vulnerable to look-ahead bias, survivorship bias, and small-sample luck.

This project asks the question under conditions designed to make a positive result hard to fake: a deterministic simulator that enforces trading rules in code; strict point-in-time data so a historical agent cannot see the future; a passive SPY benchmark; a random-trading control to calibrate luck; and a paired bootstrap over pooled quarters so the verdict carries statistical weight rather than resting on one window.

**Research question.** Does an autonomous LLM agent beat passive S&P 500 buy-and-hold on a risk-adjusted basis, and if so, by a margin large enough to matter?

**Contribution.** (1) An open, rules-enforced, look-ahead-free benchmark for LLM trading agents with a passive benchmark and a random control. (2) A statistical protocol — daily-return risk metrics plus a pooled paired bootstrap — that reports the *probability* an agent beats the market rather than a single return. (3) A clean negative result across three personas and eight quarters, corroborated out-of-sample.

**Headline finding.** No persona beat SPY. Over 2024–2025 SPY compounded to +48.6%; the best agent (balanced) reached +37.8% with a 40% beat-probability, and the others trailed badly. A dart-throwing control matched or beat every agent, which is the clearest evidence that observed agent performance reflects risk-taking and luck, not skill.

## 2. Background & Related Work

**LLM agents in finance.** A growing body of demonstrations wires LLMs to market data and tools and reports trading performance. Most share two weaknesses: they evaluate over short windows, and they do not rigorously prevent the model from accessing information unavailable at the simulated decision time. Both inflate apparent skill.

**Backtesting pitfalls.** The standard hazards are well known in quantitative finance: *look-ahead bias* (using data not yet available), *survivorship bias* (a universe that silently excludes delisted names), *data-snooping* (selecting a strategy that fit one window), and *ignoring costs* (slippage, fills). An LLM adds a subtler channel: a model trained on data through some cutoff may "remember" how a past period resolved, so a backtest must also deny it live tools that would reveal the future.

**Efficient markets as the null.** The efficient-market hypothesis predicts that, net of risk and costs, active strategies should not reliably beat a passive benchmark. A rigorous LLM-trading study is therefore a test against a strong null: the interesting outcome is not "the agent made money" (a rising market does that) but "the agent beat buy-and-hold on a risk-adjusted basis, repeatably." This framing motivates our two reference points — a passive SPY benchmark and a random control — and our focus on risk-adjusted, pooled statistics rather than single-run returns.

## 3. Experimental Design

### 3.1 Simulation environment ("Code is Law")

A deterministic simulator executes and scores trades; the LLM only *proposes* them. Rules are enforced in code, not by prompt, so a model cannot talk its way around them:

| Rule | Value |
| --- | --- |
| Universe | Long-only US equities, $3–$50 (enforced at fill) |
| Execution | Decide after close, fill at next open (T+1), 0.1% slippage |
| Stops / targets | Checked vs daily High/Low; gap-throughs fill at the open |
| Position sizing | 5–25% per position, max 15 positions, max 3 new buys/day |
| Risk | Every buy must carry a stop-loss |
| Fairness | One frozen OHLC set per day shared by all agents |

### 3.2 Agents and personas

Each agent is a model × persona. Personas (conservative / balanced / aggressive) differ only in a system-prompt risk mandate. The study model is **Gemini 3.8 Flash** at temperature 0. A **random control** (no LLM) trades randomly within the same rules and the same daily watchlist — the skill-versus-luck baseline.

### 3.3 Data

Prices from Yahoo Finance (yfinance); macro indicators (yields, VIX, Fed funds) from FRED. Both free. Historical prices are cached on disk and retried with backoff for reproducibility.

### 3.4 Point-in-time integrity (no look-ahead)

A backtest for a past date must not see the future. Enforced: (a) prices come from a window *ending at* the simulation date, never the latest bar; (b) FRED series are fetched as-of that date; (c) LLM tools are gated by a run-level date context — date-aware tools receive the as-of date, while tools that can only return the present (web search, news, fundamentals, URL fetch) are **disabled** on a past date; (d) the live market narrative and catalyst watchlist are **suppressed** for historical snapshots. The honest cost: historical agents trade on a leaner information set (prices + macro + technicals, no news) than a live agent would — the correct trade-off, since fabricated as-of news would be worse.

### 3.5 Benchmarks

Two reference points are computed over the identical window: **SPY buy-and-hold** (the passive benchmark) and the **random control** (the luck baseline).

### 3.6 Statistical method

Per run we report return, maximum drawdown, annualized volatility, and Sharpe (rf = 0) from the daily-return series. To answer "beats SPY?" we use a **paired bootstrap**: the same resampled trading days are applied to the agent and to SPY together, terminal wealth is compared, and we report the probability the agent beats SPY and the margin distribution (5th/50th/95th percentiles). For a verdict with weight, per-day (agent, SPY) pairs are **pooled across all eight quarters** (≈500 observations) before bootstrapping. The simulator is covered by 67 offline unit tests run in CI; LLM calls are stochastic even at temperature 0, so conclusions come from the pooled distribution, not any single path.

## 4. Results

All eight quarters ran cleanly (every agent traded; no failed or flat quarters). Headline: **no persona beat SPY buy-and-hold**, and a random control beat all three.

### 4.1 Per-quarter total return (2024–2025)

| Quarter | Conservative | Balanced | Aggressive | Random | SPY |
| --- | --- | --- | --- | --- | --- |
| 2024 Q1 | +2.73% | +11.39% | +18.76% | +7.89% | +11.01% |
| 2024 Q2 | −3.83% | +4.93% | −16.79% | −3.73% | +4.56% |
| 2024 Q3 | +8.92% | +8.31% | +13.65% | +6.65% | +5.53% |
| 2024 Q4 | −2.42% | +5.77% | +19.08% | +22.86% | +3.42% |
| 2025 Q1 | −0.67% | −1.93% | −23.77% | −11.62% | −4.03% |
| 2025 Q2 | −0.87% | +7.84% | +8.56% | +36.44% | +10.47% |
| 2025 Q3 | +1.28% | −1.63% | −10.38% | +16.45% | +8.16% |
| 2025 Q4 | −1.43% | −1.06% | +2.42% | −12.54% | +2.32% |

### 4.2 Two-year compounded ($10,000 start)

| Agent | 2-yr total | Ending value | Qtrs beating SPY | Quarterly vol |
| --- | --- | --- | --- | --- |
| random_control | +67.1% | $16,714 | 4 / 8 | 16.0% |
| **spy_buy_hold** | **+48.6%** | **$14,863** | — | **4.6%** |
| gemini_balanced | +37.8% | $13,782 | 5 / 8 | 4.8% |
| gemini_conservative | +3.2% | $10,322 | 2 / 8 | 3.7% |
| gemini_aggressive | +1.6% | $10,159 | 4 / 8 | 15.5% |

### 4.3 Pooled paired bootstrap vs SPY

≈500 agent–SPY day-pairs per agent, 1-year horizon. "Prob. beat SPY" near 50% = coin-flip / no edge.

| Agent | Prob. beat SPY | Median margin vs SPY | 90% band (p5…p95) | Median 1-yr return | Prob. of loss |
| --- | --- | --- | --- | --- | --- |
| random_control | 59% | +5.7% | −27.8% … +63.3% | +29.6% | 20% |
| spy_buy_hold | — | — | — | +21.8% | 10% |
| gemini_balanced | 40% | −4.0% | −26.1% … +24.9% | +17.5% | 16% |
| gemini_aggressive | 27% | −17.6% | −50.9% … +38.0% | +0.8% | 49% |
| gemini_conservative | 12% | −17.0% | −36.3% … +7.1% | +1.4% | 44% |

No agent reaches a 50% beat-probability; balanced is closest at 40% but with a negative median margin. (Aggressive + random and conservative + balanced were run as two batches; SPY buy-and-hold is deterministic over identical dates, so it anchors both consistently.)

### 4.4 Out-of-sample corroboration (2026 Q2)

A separate single-quarter run in 2026 with all personas together reproduces the ordering:

| Agent | Return | Max DD | Ann Vol | Sharpe |
| --- | --- | --- | --- | --- |
| **spy_buy_hold** | **+14.26%** | 4.49% | 13.9% | **+4.03** |
| gemini_aggressive | +13.33% | 16.03% | 39.0% | +1.50 |
| random_control | +11.31% | 9.82% | 23.4% | +1.98 |
| gemini_balanced | +4.77% | 7.28% | 16.7% | +1.22 |
| gemini_conservative | −3.09% | 3.83% | 9.2% | −1.34 |

No persona beat SPY on return or Sharpe; conservative *lost money in a +14% quarter* by being too timid.

## 5. Case Analysis: Why the Random Control Won

The random control's +67.1% is not evidence that randomness trades well; it is evidence of how misleading raw return is without a risk and luck lens. Two mechanisms explain it.

**Lottery-ticket concentration.** The control's best quarter, 2024 Q4 (+22.9%), was essentially one position: it bought QUBT at $6.45 and held to $16.55 (+157%), while its other holdings were flat or down. One random dart hit a 2.5-bagger and carried the quarter. Its other blowout, 2025 Q2 (+36.4%), came from staying ~78% invested across ten high-beta small-caps during a rally.

**Buy-and-hold beta vs agent churn.** All agents draw from the same deliberately volatile $3–$50 catalyst watchlist. The random agent mostly buys and holds; in a 2024–25 window where those small-caps ran, passively holding high-beta names beat both SPY (large-cap, lower beta) and the LLM agents, who traded the *same* names actively — selling winners early, getting stopped out on normal small-cap volatility, and sitting in cash. The agents churned themselves out of the very rallies the control rode.

**Why it is still not skill.** The control is the riskiest participant (16.0% quarterly volatility, a 20% bootstrap probability of loss, a p5 of −22%). Its high mean is a right-tail outcome of a high-variance bet: it beat SPY in only 4 of 8 quarters, and in an earlier 2026 Q3 run the same strategy *lost 13.7%*. The takeaway is not "random is good" but "the window favored high-beta buy-and-hold, the control blundered into it, and the agents were beaten by a dart-thrower" — the sharpest possible evidence of no alpha. On a risk-adjusted basis SPY still wins cleanly: +48.6% at 4.6% volatility versus the control's +67.1% at 16.0% with a fat downside tail.

## 6. Discussion

**Personas move risk, not return.** The three personas produced exactly the volatility ordering their mandates imply — conservative 3.7%, balanced 4.8%, aggressive 15.5% quarterly — but none converted that into a return edge over SPY. Aggressive took large risk for no reward; conservative was so defensive it lost money in up quarters. Balanced was the only one that behaved like a sane index-tracker (near-SPY volatility, 5/8 quarters beating SPY) yet still trailed and sits at a 40% beat-probability — i.e. a slightly *worse* index fund, not a market-beater.

**Active churn is a tax in a trending market.** Section 5 shows the agents repeatedly traded out of names that then ran, paying slippage and getting stopped out on noise. In a momentum regime, discretionary trading of high-beta names underperformed simply holding them — a familiar result that LLMs reproduce rather than escape.

**Consistency with the null.** The findings are what the efficient-market hypothesis predicts: net of risk, active LLM strategies did not beat a passive benchmark, and a random strategy was statistically indistinguishable from — or better than — the "intelligent" ones. Nothing here suggests the agents extracted information the market had not already priced.

**On single runs.** Aggressive beat SPY in 4 of 8 quarters and, in isolation, 2024 Q1 looked like a triumph (+19%, a 98% single-quarter beat-probability in the bootstrap). Pooling dissolves that illusion. Any claim built on one or two quarters — the usual format for "my AI beats the market" demonstrations — would here have been noise.

## 7. Limitations

These bound the claim to *"in this setup, these agents did not beat the market."* They do not establish that LLMs cannot trade.

- **One model family.** Only Gemini 3.8 Flash was tested. Larger or reasoning-tuned models, or other providers, may differ.
- **Two years, recent regimes.** 2024–2025 contains no 2008/2020-scale crash; behavior in a severe bear market is untested.
- **Lean historical information set.** To prevent look-ahead, historical agents trade without news or live fundamentals (§3.4), so historical and live behavior are not identical — a deliberate, disclosed trade-off.
- **Free-data caveats.** yfinance carries survivorship bias (delisted tickers silently absent) and adjusted-vs-raw price quirks; the watchlist is a fixed set of *current* small-caps, some of which lacked data in older quarters. A point-in-time vendor (e.g. Databento/Polygon/CRSP) would harden this.
- **FRED vintage.** Macro uses current data filtered by observation date, not ALFRED point-in-time vintages; this matters only for revised series (e.g. CPI).
- **LLM nondeterminism.** Even at temperature 0, provider inference is not bit-reproducible, so single-run returns vary; we mitigate by pooling and by drawing conclusions from distributions, not point estimates.
- **No explicit transaction-cost model beyond slippage.** Commissions and market impact for small-caps are not separately modeled.

## 8. Conclusion and Future Work

Within a rigorous benchmark — rules enforced in code, strictly point-in-time data, a passive SPY benchmark, a random control, and a pooled paired bootstrap — **no Gemini persona showed risk-adjusted skill versus passive indexing** over eight quarters. The best (balanced) approximated a slightly-worse index fund; aggressive and conservative destroyed value by taking too much or too little risk; and a random control was indistinguishable from, or better than, the agents. The result is consistent across two independent batches and corroborated out-of-sample. It is a clean negative result — arguably more useful than a noisy positive one.

**Toward a publishable study.** The methodology is the right shape; the gaps are scale, data, and statistical depth:

1. **More models.** Add other families (OpenAI, Anthropic, and a local open-weight model for zero-cost inference) to test whether the no-edge result generalizes.
2. **Multiple seeds per condition.** Run each configuration several times and report confidence intervals, directly addressing LLM nondeterminism.
3. **Point-in-time vendor data.** Replace free yfinance to remove survivorship and adjusted-price confounds.
4. **Longer horizon and more regimes**, including a drawdown period, for external validity.
5. **Explicit transaction costs** (commissions, impact) and a turnover analysis, since churn is a leading explanation for underperformance.
6. **A control suite** beyond SPY and random: equal-weight, simple momentum, and a watchlist buy-and-hold, to separate universe effects from agent decisions.

The code, tests, and one-click reproduction workflows are released so these extensions can be run directly.

## Appendix

### A. Reproducibility

The benchmark runs via GitHub Actions. *Backtest (date range)* runs a single window; *Batch Backtest (multi-quarter)* runs eight independent quarters as a matrix and pools them into a combined verdict. Inputs: `agents` (which personas) and `max_tool_calls` (per-agent tool-call budget; 4 for the primary study, 8 for the 2026 corroboration). Each run emits `summary.md` (leaderboard with risk metrics), `monte_carlo.md` (beat-SPY distribution), and, for the batch, `combined_verdict.md`. The simulator and analysis scripts are covered by 67 stdlib-only unit tests run in CI.

### B. Enforced constraints

Long-only; $3–$50 price band checked at fill; T+1 execution at the next open with 0.1% slippage; stops and take-profits checked against daily High/Low with gap-throughs filling at the open; 5–25% per position; ≤15 positions; ≤3 new buys/day; mandatory stop-loss on every buy; one frozen daily OHLC set shared across agents. Starting capital $10,000 per agent per run.

### C. AI-assistance disclosure

This benchmark's code, test suite, and the drafting of this document were produced with substantial assistance from an AI coding assistant (Anthropic's Claude), under the direction of the human author, who defined the research questions, reviewed the methodology and code, directed each design decision, verified the results, and takes full responsibility for the work. No AI system is an author. This disclosure is provided in line with current publisher and conference policies on AI-assisted work; any venue submission should follow that venue's specific disclosure requirements.

### D. Availability

Source, tests, workflows, and the `FINDINGS.md` summary are in the project repository. Results artifacts (`summary.md`, `monte_carlo.md`, `combined_verdict.md`, per-quarter data) are produced by the workflows above and can be regenerated.
