# Pooled backtest verdict — cross-model, 8 quarters (2024–2025)

Three model families (Gemini 3.8 Flash, OpenAI `gpt-6-luna`, Anthropic
`claude-haiku-5-5`) + a random control, over the identical eight quarters. Each
agent is paired against the SPY buy-and-hold from its own run (SPY median 1-yr
+21.8–22.4%). ~500 day-pairs per single-run agent.

> **Reproducibility.** `claude_aggressive` was run **three times** on the same 8
> quarters to separate signal from LLM run-to-run noise; its row below is the
> **pooled 3-run estimate** (1,482 day-pairs). The single-run OpenAI and Gemini
> numbers have **not** been repeated, so they carry single-draw uncertainty too
> (Claude's first run alone read 71% — see the spread note). The Anthropic data
> is post-fix (thinking-block bug, `FINDINGS.md` §3.3).

## Does the agent beat SPY? (252d ≈ 1.0y, paired bootstrap)

Near 50% = coin-flip (no edge).

| Agent | Prob. beat SPY | Median margin vs SPY | 90% band (p5…p95) |
|---|---|---|---|
| claude_aggressive (3-run pooled) | 60% | +4.4% | -21.4% … +39.7% |
| random_control | 14% | -22.6% | -47.3% … +15.9% |
| gemini_balanced | 40% | -4.0% | -26.1% … +24.9% |
| gemini_aggressive | 27% | -17.6% | -50.9% … +38.0% |
| chatgpt_balanced | 25% | -9.7% | -29.8% … +15.1% |
| chatgpt_aggressive | 13% | -20.8% | -43.3% … +11.0% |
| claude_balanced | 13% | -16.0% | -35.7% … +8.5% |
| gemini_conservative | 12% | -17.0% | -36.3% … +7.1% |

**`claude_aggressive` run-to-run spread (same 8 quarters):**

| Run | Prob. beat SPY | Median margin | 2-yr compounded | Qtrs beat SPY |
|---|---|---|---|---|
| Original | 71% | +11.2% | +84.1% | 5/8 |
| Repeat 1 | 61% | +4.7% | +61.9% | 4/8 |
| Repeat 2 | 45% | −2.0% | +43.8% | 3/8 |
| **Pooled** | **60%** | **+4.4%** | — | — |

## Return distribution (252d ≈ 1.0y, IID bootstrap of daily returns)

| Agent | Median ret | 90% band (p5…p95) | Median $10k→ | Prob. loss |
|---|---|---|---|---|
| claude_aggressive (3-run) | +28.0% | -2.5% … +67.4% | $12,802 ($9,750–$16,743) | 7% |
| spy_buy_hold | +22.4% | -6.0% … +60.3% | $12,241 ($9,400–$16,034) | 11% |
| gemini_balanced | +17.5% | -11.1% … +56.3% | $11,747 ($8,887–$15,628) | 16% |
| chatgpt_balanced | +10.1% | -2.2% … +24.9% | $11,015 ($9,778–$12,493) | 10% |
| claude_balanced | +2.4% | -14.2% … +21.5% | $10,237 ($8,578–$12,151) | 41% |
| gemini_conservative | +1.4% | -12.9% … +18.0% | $10,139 ($8,708–$11,796) | 44% |
| gemini_aggressive | +0.8% | -44.6% … +82.3% | $10,078 ($5,540–$18,232) | 49% |
| random_control | -5.6% | -41.6% … +52.7% | $9,435 ($5,839–$15,272) | 57% |
| chatgpt_aggressive | -2.8% | -30.7% … +36.0% | $9,724 ($6,933–$13,603) | 56% |

## Bear-market regime test — 2022 (SPY −21.8%), 3 runs pooled

The decisive test. Where the bull edge is modest and noisy, the bear result is
large and **stable across repeats**:

| Agent | Prob. beat SPY | Median margin | 2022 return (per run) |
|---|---|---|---|
| claude_aggressive (3-run pooled) | 86% | +25.8% | −0.0% / −4.3% / −2.4% |
| random_control (pooled) | 3% | −40.8% | ≈ −53% |
| spy_buy_hold | — | — | −21.8% |

All three runs beat SPY in **every** quarter, finished ≈flat while SPY fell ~22%,
and held **single-digit drawdowns** (2–8% vs SPY 13–20%) — by **going to cash**
(54–100% cash, sitting out the worst quarters). This did not decay on repetition.

**Takeaway:** Across three model families only `claude_aggressive` stands out, and
its nature is now clear. The bull-market edge is **modest and noisy** (pooled 60%
/ +4.4%, one of three runs below SPY) — but its **bear-market capital
preservation is large and reproducible** (86% beat-rate, ≈flat vs SPY −22%, tiny
drawdowns, via cash). It is a **defensive, drawdown-averse** agent — value in
avoiding losses, not chasing gains. Income-relevant asymmetry, but still one
model / one bear episode in a backtest with upward biases; warrants a forward
paper-trade test, not capital. Full detail in `FINDINGS.md`.
