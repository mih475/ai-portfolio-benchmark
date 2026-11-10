"""API-free historical sector rotation diagnostic for GitHub Actions.

No LLM provider keys required. This validates sector ETF data, including
recovery of incomplete Yahoo Finance batch responses.
"""
import argparse
import os
from datetime import date

from v2.snapshot_engine import fetch_sector_rotation, SECTOR_ETFS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2024-03-04")
    args = parser.parse_args()
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    run_date = date.fromisoformat(args.date)
    print(f"HISTORICAL SECTOR PREFLIGHT: {run_date}", flush=True)
    rotation = fetch_sector_rotation(as_of=run_date)
    if "error" in rotation:
        raise SystemExit(f"FAIL: {rotation['error']}")
    if set(rotation) != set(SECTOR_ETFS):
        raise SystemExit(f"FAIL: incomplete rotation: {sorted(rotation)}")
    for sector, row in sorted(rotation.items()):
        print(f"{sector} {row['ticker']} "
              f"RS={row['rs_ratio']} Momentum={row['rs_momentum']} "
              f"Quadrant={row['quadrant']}")
    print("PASS: all sector ETF series valid, no model API calls")


if __name__ == "__main__":
    main()
