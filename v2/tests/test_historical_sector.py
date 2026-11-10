"""In-memory regression tests for historical sector and ticker eligibility.

Requires pandas/numpy (the API-free Historical Price Preflight job installs them).
Data are synthetic; no Yahoo, OpenAI, or other network calls are made here.
"""
import ast
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from v2 import snapshot_engine as engine

SRC = Path(__file__).resolve().parent.parent / "snapshot_engine.py"


def t_historical_candidate_filters_missing_or_nonfinite_indicators():
    tree = ast.parse(SRC.read_text())
    fn = next(x for x in tree.body
              if isinstance(x, ast.FunctionDef)
              and x.name == "_has_complete_historical_indicators")
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<fn>", "exec"), ns)
    eligible = ns["_has_complete_historical_indicators"]
    good = {"SMA_200_Dist": 0.0, "RS_3M_vs_SPY": -5.0, "ATR_Pct": 3.2}
    assert eligible({"Tkr": "ABC"}, {"ABC": good})
    assert not eligible({"Tkr": "NEW"}, {"ABC": good})
    for key in good:
        bad = dict(good, **{key: None})
        assert not eligible({"Tkr": "ABC"}, {"ABC": bad}), key
        bad[key] = float("nan")
        assert not eligible({"Tkr": "ABC"}, {"ABC": bad}), key
    assert not eligible({"Tkr": "ABC"}, {"ABC": dict(good, ATR_Pct=0)})


def test_recovery_then_sector_rotation():
    dates = pd.bdate_range("2024-02-01", periods=25)
    as_of = dates[-1].date()
    values = np.linspace(90, 110, len(dates))
    batch = pd.DataFrame({
        ("Close", "SPY"): values,
        ("Close", "XLK"): values * 1.15 * np.linspace(0.95, 1.05, len(dates)),
        ("Close", "XLF"): [np.nan] * len(dates),
    }, index=dates)
    batch.columns = pd.MultiIndex.from_tuples(batch.columns)
    xlf = pd.DataFrame({"Close": values * np.linspace(1.08, 1.12, len(dates))},
                       index=dates)
    calls = []

    def downloader(tickers, **kwargs):
        calls.append((tuple(tickers), kwargs))
        if set(tickers) == {"SPY", "XLK", "XLF"}:
            return batch
        if tickers == ["XLF"]:
            return xlf
        raise AssertionError(f"unexpected recovery call: {tickers}")

    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        with patch.object(engine, "SECTOR_ETFS", {"Tech": "XLK", "Finance": "XLF"}), \
             patch.object(engine, "RRG_WINDOW", 5), \
             patch("v2.price_provider.window_download", side_effect=downloader):
            result = engine.fetch_sector_rotation(as_of=as_of)
        assert "error" not in result, result
        assert set(result) == {"Tech", "Finance"}, result
        assert result["Finance"]["ticker"] == "XLF"
        assert calls[0][0] == ("XLK", "XLF", "SPY"), calls
        assert calls[1][0] == ("XLF",), calls
        assert all(kwargs.get("threads") is False for _, kwargs in calls)
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


def test_unrecoverable_sector_missing_is_reported_not_fabricated():
    dates = pd.bdate_range("2024-02-01", periods=25)
    as_of = dates[-1].date()
    batch = pd.DataFrame({
        ("Close", "SPY"): [100.0] * len(dates),
        ("Close", "XLK"): [110.0] * len(dates),
        ("Close", "XLF"): [np.nan] * len(dates),
    }, index=dates)
    batch.columns = pd.MultiIndex.from_tuples(batch.columns)

    def downloader(tickers, **kwargs):
        return batch if len(tickers) > 1 else pd.DataFrame()

    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        with patch.object(engine, "SECTOR_ETFS", {"Tech": "XLK", "Finance": "XLF"}), \
             patch.object(engine, "RRG_WINDOW", 5), \
             patch("v2.price_provider.window_download", side_effect=downloader):
            result = engine.fetch_sector_rotation(as_of=as_of)
        assert "error" in result and "XLF" in result["error"], result
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


def test_historical_watchlist_excludes_ipo_with_no_asof_bar():
    dates = pd.bdate_range("2022-06-01", periods=5)
    as_of = dates[-1].date()
    closes = pd.DataFrame({"PLTR": [8.0, 8.1, 8.2, 8.3, 8.4],
                           "MBLY": [np.nan] * 5}, index=dates)
    volumes = pd.DataFrame({"PLTR": [3_000_000] * 5,
                            "MBLY": [np.nan] * 5}, index=dates)
    data = pd.concat({"Close": closes, "Volume": volumes}, axis=1)
    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        with patch("v2.price_provider.window_download", return_value=data):
            out = engine.fetch_watchlist_data(["PLTR", "MBLY"], as_of=as_of)
        assert [x["Tkr"] for x in out] == ["PLTR"], out
        with patch("v2.price_provider.window_download", return_value=data.iloc[:-1]):
            try:
                engine.fetch_watchlist_data(["PLTR"], as_of=as_of)
                assert False, "stale market date must fail"
            except ValueError:
                pass
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


def test_historical_snapshot_fails_closed_on_missing_sector_history():
    old = os.environ.get("BACKTEST_STRICT_PRICES")
    os.environ["BACKTEST_STRICT_PRICES"] = "1"
    try:
        with patch.object(engine, "fetch_macro_data", return_value={}), \
             patch.object(engine, "fetch_sector_rotation",
                          return_value={"error": "XLF unavailable"}):
            try:
                engine.build_mih_snapshot(snapshot_date=date(2024, 3, 4))
                assert False, "historical snapshot should fail closed"
            except ValueError as exc:
                assert "XLF unavailable" in str(exc), exc
    finally:
        if old is None:
            os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else:
            os.environ["BACKTEST_STRICT_PRICES"] = old


def main():
    tests = [
        t_historical_candidate_filters_missing_or_nonfinite_indicators,
        test_recovery_then_sector_rotation,
        test_unrecoverable_sector_missing_is_reported_not_fabricated,
        test_historical_watchlist_excludes_ipo_with_no_asof_bar,
        test_historical_snapshot_fails_closed_on_missing_sector_history,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} historical integrity tests; no API calls")


if __name__ == "__main__":
    main()
