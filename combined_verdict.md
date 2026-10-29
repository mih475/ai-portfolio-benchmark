# Pooled backtest verdict — 16 quarter(s) combined

Pooled paired sample: 494 agent/SPY day-pairs.
# Does the model beat SPY? (252d ≈ 1.0y, paired bootstrap)

Same bootstrapped days applied to agent and SPY together, then terminal wealth compared. **Prob. beat SPY** near 50% = coin-flip (no edge); the margin band shows how big the win/loss typically is.

| Agent | Prob. beat SPY | Median margin vs SPY | 90% band (p5…p95) |
|---|---|---|---|
| random_control | 59% | +5.7% | -27.8% … +63.3% |
| gemini_balanced | 40% | -4.0% | -26.1% … +24.9% |
| gemini_aggressive | 27% | -17.6% | -50.9% … +38.0% |
| gemini_conservative | 12% | -17.0% | -36.3% … +7.1% |

# Return distribution (252d ≈ 1.0y, IID bootstrap of daily returns)

Resampled forward paths from each agent's observed daily returns. **Not a forecast** — it shows the spread the observed daily behaviour implies if it persisted. Bands are only as reliable as the input sample.

| Agent | Sample days | Median ret | 90% band (p5…p95) | Median $10k→ | Prob. loss |
|---|---|---|---|---|---|
| random_control | 502 | +29.6% | -22.4% … +111.6% | $12,962 ($7,757–$21,156) | 20% |
| spy_buy_hold | 988 | +21.8% | -5.8% … +59.6% | $12,178 ($9,424–$15,960) | 10% |
| gemini_balanced | 502 | +17.5% | -11.1% … +56.3% | $11,747 ($8,887–$15,628) | 16% |
| gemini_conservative | 502 | +1.4% | -12.9% … +18.0% | $10,139 ($8,708–$11,796) | 44% |
| gemini_aggressive | 502 | +0.8% | -44.6% … +82.3% | $10,078 ($5,540–$18,232) | 49% |