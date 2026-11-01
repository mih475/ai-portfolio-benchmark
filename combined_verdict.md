# Pooled backtest verdict — cross-model, 8 quarters (2024–2025)

Three model families (Gemini 3.8 Flash, OpenAI `gpt-6-luna`, Anthropic
`claude-haiku-5-5`) + a random control, each run over the identical eight
quarters. Each agent is paired against the SPY buy-and-hold from its own run
(SPY's median 1-yr return is +21.8% across all runs). ~500 agent/SPY day-pairs
per agent.

> The Anthropic numbers are from the clean re-run after fixing a thinking-block
> API bug that had flat-lined the first Claude batch (see `FINDINGS.md` §3.3).

## Does the agent beat SPY? (252d ≈ 1.0y, paired bootstrap)

Same bootstrapped days applied to agent and SPY together, then terminal wealth
compared. **Prob. beat SPY** near 50% = coin-flip (no edge).

| Agent | Prob. beat SPY | Median margin vs SPY | 90% band (p5…p95) |
|---|---|---|---|
| claude_aggressive | 71% | +11.2% | -17.8% … +52.3% |
| random_control | 59% | +5.7% | -27.8% … +63.3% |
| gemini_balanced | 40% | -4.0% | -26.1% … +24.9% |
| gemini_aggressive | 27% | -17.6% | -50.9% … +38.0% |
| chatgpt_balanced | 25% | -9.7% | -29.8% … +15.1% |
| chatgpt_aggressive | 13% | -20.8% | -43.3% … +11.0% |
| claude_balanced | 13% | -16.0% | -35.7% … +8.5% |
| gemini_conservative | 12% | -17.0% | -36.3% … +7.1% |

## Return distribution (252d ≈ 1.0y, IID bootstrap of daily returns)

Resampled forward paths from each agent's observed daily returns. **Not a
forecast** — it shows the spread the observed daily behaviour implies if it
persisted. Bands are only as reliable as the input sample.

| Agent | Median ret | 90% band (p5…p95) | Median $10k→ | Prob. loss |
|---|---|---|---|---|
| claude_aggressive | +36.0% | +2.0% … +81.5% | $13,605 ($10,205–$18,148) | 4% |
| random_control | +29.6% | -22.4% … +111.6% | $12,962 ($7,757–$21,156) | 20% |
| spy_buy_hold | +21.8% | -5.7% … +59.7% | $12,184 ($9,427–$15,966) | 10% |
| gemini_balanced | +17.5% | -11.1% … +56.3% | $11,747 ($8,887–$15,628) | 16% |
| chatgpt_balanced | +10.1% | -2.2% … +24.9% | $11,015 ($9,778–$12,493) | 10% |
| claude_balanced | +2.4% | -14.2% … +21.5% | $10,237 ($8,578–$12,151) | 41% |
| gemini_conservative | +1.4% | -12.9% … +18.0% | $10,139 ($8,708–$11,796) | 44% |
| gemini_aggressive | +0.8% | -44.6% … +82.3% | $10,078 ($5,540–$18,232) | 49% |
| chatgpt_aggressive | -2.8% | -30.7% … +36.0% | $9,724 ($6,933–$13,603) | 56% |

**Takeaway:** 8 of 9 LLM agents fail to beat SPY. The sole exception is
`claude_aggressive` — the only agent above a coin-flip on a real margin, and the
only one whose edge is risk-adjusted (the random control's +5.7% margin is pure
variance). Its edge leans on two strong 2025 quarters and has not yet been
checked against a same-quarter random control; confirm before treating as
settled. Full detail in `FINDINGS.md`.
