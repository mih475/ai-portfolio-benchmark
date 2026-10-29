# AI Portfolio Experiment (V2): Automated Agentic LLM Study

> **Fork notice.** This is an independent, modified continuation of
> [Seve1995/ai-portfolio-experiment](https://github.com/Seve1995/ai-portfolio-experiment)
> (MIT). It is **not** affiliated with or endorsed by the original author.
> See [`ATTRIBUTION.md`](ATTRIBUTION.md) for credit and [`CHANGES.md`](CHANGES.md)
> for what this fork changes. Some claims below are inherited from upstream and
> are being corrected — treat the README as aspirational until `CHANGES.md` says a
> feature is verified.
>
> **📊 Results & methodology: see [`FINDINGS.md`](FINDINGS.md).** Headline: over
> 8 quarters (2024–2025), no Gemini persona beat SPY buy-and-hold (+48.6% / 2yr).
> Best was balanced (+37.8%, 40% beat-rate); aggressive (+1.6%) and conservative
> (+3.2%) failed badly; a random control matched or beat all three. No
> risk-adjusted edge.

A high-fidelity project for benchmarking the financial decision-making of **18 autonomous AI agents** (6 models × 3 personas) in a deterministic, rules-based trading simulation.

## 🚀 The 2026 Architectural Evolution: "Institutional Intelligence"

In contrast to the reactive "V1" (Deep Search) system, the **V2 Framework** pivots to a **deterministic, pre-computed intelligence engine**. We replaced thin 7KB data snapshots with a **150KB Market Intelligence Hub (MIH)** to eliminate LLM arithmetic errors and provide high-alpha context.

### 1. Market Intelligence Hub (MIH)
The MIH acts as the agents' "Bloomberg Terminal," delivering a machine-readable payload that includes:
- **Macro Narrative (300 Words)**: Synthesized global context via Brave Search (Freshness: PD).
- **Macro Indicators (FRED)**: Real-time 10Y/2Y Yields, Fed Funds, VIX, and Credit Spreads.
- **Dynamic Sector Discovery**: The MIH automatically identifies the Top 3 sectors by RS-Ratio (momentum strength) and injects their current 'Champion' holdings into the catalyst scanner. This ensures the portfolio reacts to macro shifts (e.g., Energy during geopolitical conflict) without human bias.
- **Catalyst Watchlist (100 Tickers)**: A $3-$50 scanning universe focused on high-volatility catalysts like FDA/PDUFA dates, Earnings Drift, and Short Squeezes.
- **Technical/Risk Normalization**: Pre-computed ATR (14d), RSI (14d), and Relative Volume (RVOL) Z-scores, providing agents with "alpha-ready" signals.

### 2. TOON Visualization (Token-Oriented Object Notation)
To maximize context window efficiency, MIH data is serialized into **Markdown Tables (TOON)** rather than JSON. This reduces token overhead by **60%**, allowing larger data payloads without exceeding provider limits.

### 3. The Agent Roster (18 LLM agents + 1 random control = 19)
 benchmarked across:
- **Providers (6)**, as configured in `v2/config.py`: OpenAI (`gpt-6-luna`), Google (`gemini-3.8-flash`), Anthropic (`claude-haiku-5-5`), Mistral (`mistral-large-latest`), DeepSeek (`deepseek-chat`), and Qwen (`qwen-max`). Model ids drift as providers retire versions — if an agent 404s, update its `model_id` here or set `MODEL_ID_<PROVIDER>` at run time.
- **Risk Profiles (3)**: Conservative, Balanced, and Aggressive (Persona-driven logic).
- **Control**: one `random_control` agent that trades randomly, as a skill-vs-luck baseline.
- **Automation**: Fully autonomous daily execution via **GitHub Actions** at 21:00 UTC (Market Close), with automated state persistence via `git-auto-commit`.

---

## 🛠 Project Structure

- `v2/snapshot_engine.py`: The MIH Core. Fetches FRED, RRG, and 100-ticker watchlist data.
- `v2/agent_runner.py`: The daily orchestrator. Injects playbooks/MIH and runs the LLM tool-calling loop.
- `v2/portfolio_simulator.py`: **"Code is Law" Firewall**. Validates trades, enforces stop-losses, and calculates T+1 execution.
- `v2/api_adapters.py`: Robust retry logic with exponential backoff (handles 429/503 errors across providers).
- `v2/mcp_servers/`: Custom tools for Technicals, Fundamentals, and Web Search.

---

## ⚖️ "Code is Law" - Simulator Constraints

LLMs operate within a strict sandbox:
- **Universe**: Long-only US Equities $3-$50. No Penny Stocks, No Shorts, No Crypto.
- **Execution**: T+1 opening prices ONLY (pre-computed slippage).
- **Sizing**: Max 25% ($2,500 on a $10k base) per position.
- **Mandatory Stops**: Every trade MUST specify a stop-loss (1.5x-2.0x ATR recommended).
- **Tool Cap**: Max 8 tool calls per turn (`MAX_TOOL_CALLS_PER_AGENT` in `v2/config.py`) before `propose_trades`.

---

## 📅 Usage

### 1. Reset & Setup (Day 0)
Generate the 6-month playbooks for all 18 agents:
```bash
python -m v2.main --day-0
```

### 2. Daily Simulation Run
Generate the MIH snapshot and execute all agents for a specific date:
```bash
python -m v2.main --run-date 2026-04-07
```

### 3. Dashboard Integration
The framework automatically exports data to the static web dashboard in `v1/logs/`.

---

## 📜 License
MIT
