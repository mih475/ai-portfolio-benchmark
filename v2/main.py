"""
AI Portfolio Experiment V2 — Main Entrypoint

Flags:
  --day-0         Run the meta-strategy generation for all agents (setup)
  --run-date      Execute the daily loop for a specific date (YYYY-MM-DD). Defaults to today.
  --export        Export the V2 data to V1 dashboard format.
"""

import argparse
import logging
from datetime import date
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("V2_Main")

def main():
    parser = argparse.ArgumentParser(description="AI Portfolio Experiment V2")
    parser.add_argument("--day-0", action="store_true", help="Generate Day 0 Playbooks")
    parser.add_argument("--run-date", type=str, default=date.today().isoformat(), help="Simulation date YYYY-MM-DD")
    parser.add_argument("--export", action="store_true", help="Export to Dashboard format")
    parser.add_argument("--agents", type=str, default=None,
                        help="Comma-separated agent ids to run instead of the full roster "
                             "(e.g. 'chatgpt_balanced'). Useful for a single-agent smoke test.")
    parser.add_argument("--start-date", type=str, default=None,
                        help="Backtest start date YYYY-MM-DD (use with --end-date).")
    parser.add_argument("--end-date", type=str, default=None,
                        help="Backtest end date YYYY-MM-DD (inclusive; use with --start-date).")

    args = parser.parse_args()
    agent_ids = [a.strip() for a in args.agents.split(",")] if args.agents else None
    
    # Needs dotenv to load keys
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")
    except ImportError:
        logger.warning("python-dotenv not installed. Using system environment variables.")

    if args.day_0:
        logger.info("Running Day 0 Meta Strategy generation...")
        from v2.meta_strategy import generate_playbooks
        generate_playbooks()
        
    # Multi-day backtest: iterate the date range in order (state carries across days).
    if args.start_date and args.end_date:
        logger.info(f"Running backtest {args.start_date}..{args.end_date}...")
        from v2.backtest import run_backtest
        run_backtest(args.start_date, args.end_date, agent_ids=agent_ids)
        args.export = True
    # Single-day run (default) unless only export or Day 0 was intended.
    elif not args.day_0 and not args.export:
        logger.info(f"Running daily loop for {args.run_date}...")
        from v2.agent_runner import run_all_agents
        run_all_agents(args.run_date, agent_ids=agent_ids)
        # Auto-export after a run
        args.export = True
        
    if args.export:
        logger.info("Exporting to Dashboard...")
        from v2.dashboard_exporter import export_for_dashboard
        data_dir = Path(__file__).parent / "data"
        out_dir = Path(__file__).parent.parent / "v1" / "logs"
        export_for_dashboard(data_dir, out_dir)

if __name__ == "__main__":
    main()
