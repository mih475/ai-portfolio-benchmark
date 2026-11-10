"""No-model preflight of actual NYSE trading dates used by backtests.

Makes sure weekend and exchange-holiday exclusions work with the installed
pandas_market_calendars dependency, not just with injected offline fixtures.
"""
from v2.backtest import iter_market_dates


def main():
    dates = list(iter_market_dates("2024-03-04", "2024-04-05"))
    assert len(dates) == 24, f"expected 24 NYSE sessions, got {len(dates)}: {dates}"
    assert dates[0] == "2024-03-04" and dates[-1] == "2024-04-05", dates
    for closed in ("2024-03-09", "2024-03-10", "2024-03-29", "2024-03-30"):
        assert closed not in dates, f"closed session was included: {closed}"

    # An exclusively closed-date range must not manufacture a session.
    assert not list(iter_market_dates("2024-03-09", "2024-03-10"))
    assert not list(iter_market_dates("2024-03-29", "2024-03-29"))
    print(f"PASS: 24 NYSE sessions in March 4–April 5, 2024, "
          "Good Friday and weekends excluded, no LLM calls")


if __name__ == "__main__":
    main()
