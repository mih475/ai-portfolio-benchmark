"""No-LLM historical data preflight for the strict backtest pipeline.

Checks the bar exists on exactly the requested market date and that a full
historical technical window can be loaded. Uses yfinance only; no OpenAI,
Anthropic or other model calls. Intended for GitHub Actions manual dispatch.
"""
import argparse
import math
from datetime import date

from v2.price_provider import day_ohlc, window_download


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default="2022-06-15")
    p.add_argument("--tickers", default="SPY,PLTR,HPQ")
    args = p.parse_args()
    as_of = date.fromisoformat(args.date)
    tickers = list(dict.fromkeys(x.strip().upper()
                                for x in args.tickers.split(",") if x.strip()))
    if not tickers:
        p.error("provide at least one ticker")
    print(f"DATA-ONLY PREFLIGHT: {as_of}, {tickers}", flush=True)
    bars = day_ohlc(tickers, as_of=as_of)
    missing = sorted(set(tickers) - set(bars))
    for ticker in tickers:
        print(f"{ticker}: exact-day OHLC={bars.get(ticker)}")
    if missing:
        raise SystemExit(f"FAIL: missing exact-session prices: {missing}")

    history = window_download(tickers, as_of=as_of, period="1y")
    if history is None or history.empty:
        raise SystemExit("FAIL: one-year history unavailable")
    for ticker in tickers:
        try:
            if getattr(getattr(history, "columns", None), "nlevels", 1) > 1:
                close = history.xs(ticker, level=1, axis=1)["Close"].dropna()
            else:
                close = history["Close"].dropna()
        except (KeyError, ValueError):
            raise SystemExit(f"FAIL: no history column for {ticker}")
        if close.empty or close.index[-1].date() != as_of:
            raise SystemExit(f"FAIL: stale historical close for {ticker}")
        if not math.isfinite(float(close.iloc[-1])) or float(close.iloc[-1]) <= 0:
            raise SystemExit(f"FAIL: invalid historical price for {ticker}")
        print(f"{ticker}: {len(close)} historical sessions; 200d SMA available={len(close)>=200}")
    # Check the new backtest-only momentum feature against real SPY-aligned data.
    # Import here so the simple OHLC parser remains independently testable.
    from v2.snapshot_engine import compute_technicals
    candidates = [t for t in tickers if t != "SPY"]
    if candidates:
        technicals = compute_technicals(candidates, as_of=as_of)
        for ticker in candidates:
            row = technicals.get(ticker)
            if row is None:
                raise SystemExit(f"FAIL: no calculated technicals for {ticker}")
            for field in ("ATR_Pct", "SMA_200_Dist",
                          "RS_1M_vs_SPY", "RS_3M_vs_SPY"):
                if row.get(field) is None:
                    raise SystemExit(f"FAIL: {ticker} missing {field}")
            print(f"{ticker}: SMA200 distance={row['SMA_200_Dist']}%, "
                  f"RS1M={row['RS_1M_vs_SPY']}pp, "
                  f"RS3M={row['RS_3M_vs_SPY']}pp")

    print("PASS: exact-session prices, full history and SPY-relative momentum; no LLM API calls")


if __name__ == "__main__":
    main()
