"""API-free strict ChatGPT v2.0 compliance and simulator regression tests.

Run: python3 v2/tests/test_historical_compliance.py
No pandas, yfinance, OpenAI, Claude, network or paid credentials required.
"""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC))
from historical_compliance import approved_equity, buy_rejection, _regime
from portfolio_simulator import PortfolioSimulator, Position, PendingOrder, TradeAction, OrderType

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn

def rules():
    return SimpleNamespace(min_stock_price=3.0, max_stock_price=50.0,
                           max_position_pct=.25, min_position_pct=.05,
                           max_positions=15, max_daily_buys=3,
                           slippage_pct=.001, fractional_shares=True,
                           long_only=True, stop_loss_required=True)

def sim(agent="chatgpt_aggressive"):
    return PortfolioSimulator(agent, 10000, rules(), Path(tempfile.mkdtemp()))

def row(ticker="PLTR", **kw):
    base = dict(Tkr=ticker, Price=20.0, SMA_20_Dist=2.0, SMA_50_Dist=4.0,
                RS_1M_vs_SPY=4.0, RSI=60.0, RVOL_Z=0.8,
                ATR_Pct=4.0)
    base.update(kw)
    return base

def snap(ticker="PLTR", regime="RISK_ON", **override):
    ctx = dict(date="2024-03-04", spy_sma200_dist_pct=2.0,
               vix=18.0, vix_date="2024-03-04")
    if regime == "NEUTRAL":
        ctx.update(vix=26.0)
    elif regime == "RISK_OFF":
        ctx.update(vix=32.0)
    elif regime == "UNKNOWN":
        ctx.update(vix=None)
    ctx.update(override)
    return dict(metadata={"date": "2024-03-04"}, watchlist=[row(ticker)],
                regime_context=ctx)

def buy(ticker="PLTR", allocation=10, stop=6, target=15):
    return dict(action="BUY", ticker=ticker, allocation_pct=allocation,
                stop_loss_pct=stop, take_profit_pct=target,
                reason="Documented momentum breakout, price invalidation and risk")

def strict(fn):
    def wrapper():
        prev = os.environ.get("BACKTEST_STRICT_PRICES")
        os.environ["BACKTEST_STRICT_PRICES"] = "1"
        try:
            fn()
        finally:
            if prev is None: os.environ.pop("BACKTEST_STRICT_PRICES", None)
            else: os.environ["BACKTEST_STRICT_PRICES"] = prev
    return wrapper

@test
@strict
def t_stock_only_fails_closed_for_geared_unknown_and_nonstock_symbols():
    p = sim()
    for ticker in ("TNA", "SRTY", "SOXL", "LABU", "TSLL", "BITO",
                   "SPXL", "TQQQ", "QQQ", "UNKNOWN"):
        assert not approved_equity(ticker), ticker
        outcome = p.submit_orders([buy(ticker)], "2024-03-04",
                                  market_snapshot=snap(ticker))
        assert outcome[0]["status"] == "REJECTED", outcome
    assert p.pending_orders == []
    assert approved_equity("PLTR") and approved_equity("DKNG")

@test
@strict
def t_valid_stocks_queue_and_fill_next_open():
    p = sim()
    results = p.submit_orders([buy()], "2024-03-04",
                              market_snapshot=snap())
    assert results[0]["status"] == "ACCEPTED", results
    assert len(p.pending_orders) == 1
    fills = p.execute_pending_orders({"PLTR": 20}, "2024-03-05")
    assert len(fills) == 1 and fills[0].ticker == "PLTR"
    assert "PLTR" in p.positions
    assert p.positions["PLTR"].stop_loss_price < 20

@test
@strict
def t_pending_ineligible_buy_cannot_bypass_fill_firewall():
    p = sim()
    p.pending_orders = [PendingOrder(TradeAction.BUY, "TNA", 0, 10,
                                     OrderType.MARKET, stop_loss_pct=6,
                                     take_profit_pct=15)]
    assert p.execute_pending_orders({"TNA": 20.0}, "2024-03-05") == []
    assert "TNA" not in p.positions and p.cash == 10000

@test
@strict
def t_protective_exit_sells_even_if_old_asset_is_ineligible():
    p = sim()
    p.positions["TNA"] = Position("TNA", 10, 20, "2024-03-01", 18,
                                  current_price=20)
    p.cash = 9800
    outcome = p.submit_orders([dict(action="SELL", ticker="TNA",
                                     allocation_pct=100)], "2024-03-04")
    assert outcome[0]["status"] == "ACCEPTED"
    exits = p.execute_pending_orders({"TNA": 19}, "2024-03-05")
    assert len(exits) == 1 and exits[0].action == "SELL"

@test
@strict
def t_no_snapshot_or_wrong_date_fails_closed():
    p = sim()
    for snapshot in (None, {}, dict(metadata={"date":"2024-03-05"},
                                     watchlist=[row()], regime_context={})):
        outcome = p.submit_orders([buy()], "2024-03-04",
                                  market_snapshot=snapshot)
        assert outcome[0]["status"] == "REJECTED", outcome
    assert not p.pending_orders

@test
@strict
def t_regime_gate_blocks_risk_off_unknown_stale_future():
    p = sim()
    for s in (snap(regime="RISK_OFF"), snap(regime="UNKNOWN"),
              snap(vix=19, vix_date="2024-02-20"),
              snap(vix=19, vix_date="2024-03-05"),
              snap(spy_sma200_dist_pct=-2)):
        o = p.submit_orders([buy()], "2024-03-04", market_snapshot=s)
        assert o[0]["status"] == "REJECTED", o
    assert _regime(snap(regime="NEUTRAL"), "2024-03-04") == "NEUTRAL"
    assert _regime(snap(), "2024-03-04") == "RISK_ON"

@test
@strict
def t_trend_relative_strength_volume_rsi_and_missing_data():
    variants = (
        {"SMA_20_Dist": -2}, {"SMA_50_Dist": -1},
        {"SMA_20_Dist": 5}, {"RS_1M_vs_SPY": -0.1},
        {"RSI": 75}, {"RSI": 40}, {"RVOL_Z": -0.5},
        {"RVOL_Z": None}, {"ATR_Pct": float("nan")}, {"Price": 55},
    )
    for kw in variants:
        p = sim()
        ss = snap()
        ss["watchlist"] = [row(**kw)]
        o = p.submit_orders([buy()], "2024-03-04", market_snapshot=ss)
        assert o[0]["status"] == "REJECTED", (kw,o)
    assert sim().submit_orders([buy()], "2024-03-04",
                               market_snapshot=snap())[0]["status"] == "ACCEPTED"

@test
@strict
def t_sma20_above_sma50_is_bullish_not_reversed():
    """Price/SMA percent distances reverse ordering of SMA levels."""
    # Price $20; $19 SMA20 > $18 SMA50 => d20 5.26% < d50 11.11%.
    p = sim()
    context = snap()
    context["watchlist"] = [row(SMA_20_Dist=round((20/19 - 1)*100, 1),
                                SMA_50_Dist=round((20/18 - 1)*100, 1))]
    result = p.submit_orders([buy()], "2024-03-04", market_snapshot=context)
    assert result[0]["status"] == "ACCEPTED", result

    # Price above BOTH SMAs but fast SMA20 below SMA50 is not bullish.
    p = sim()
    context["watchlist"] = [row(SMA_20_Dist=round((20/18 - 1)*100, 1),
                                SMA_50_Dist=round((20/19 - 1)*100, 1))]
    result = p.submit_orders([buy()], "2024-03-04", market_snapshot=context)
    assert result[0]["status"] == "REJECTED", result
    assert "trend" in result[0]["reason"], result


@test
@strict
def t_stop_target_reward_budget_and_per_regime_limits():
    proposals = (buy(stop=4), buy(stop=10), buy(target=12),
                 buy(target=None), buy(allocation=15),
                 buy(allocation=5, stop=6, target=12))
    for proposal in proposals:
        p = sim()
        o = p.submit_orders([proposal], "2024-03-04", market_snapshot=snap())
        assert o[0]["status"] == "REJECTED", (proposal,o)
    p = sim()
    ss = snap(regime="NEUTRAL")
    assert p.submit_orders([buy(allocation=8)], "2024-03-04",
                           market_snapshot=ss)[0]["status"] == "REJECTED"
    assert p.submit_orders([buy(allocation=7)], "2024-03-04",
                           market_snapshot=ss)[0]["status"] == "ACCEPTED"

@test
@strict
def t_atr_stop_over_12_or_insufficient_cash_fails():
    p = sim()
    ss = snap()
    ss["watchlist"] = [row(ATR_Pct=9)]
    assert p.submit_orders([buy(stop=13.5, target=35)], "2024-03-04",
                           market_snapshot=ss)[0]["status"] == "REJECTED"
    # Cash must be evaluated relative to current equity, not starting capital:
    # with $100 total equity, a valid 10% allocation costs only $10.
    p.cash = 100
    assert p.submit_orders([buy()], "2024-03-04",
                           market_snapshot=snap())[0]["status"] == "ACCEPTED"

@test
@strict
def t_duplicate_and_capped_exposure():
    p = sim()
    assert p.submit_orders([buy()], "2024-03-04",
                           market_snapshot=snap())[0]["status"] == "ACCEPTED"
    assert p.submit_orders([buy()], "2024-03-04",
                           market_snapshot=snap())[0]["status"] == "REJECTED"
    p = sim()
    p.positions["PLTR"] = Position("PLTR", 10, 20, "2024-03-01", 18,
                                   current_price=20)
    assert p.submit_orders([buy()], "2024-03-04",
                           market_snapshot=snap())[0]["status"] == "REJECTED"

@test
@strict
def t_at_most_two_new_buys_and_eight_positions():
    p = sim()
    ss = snap()
    ss["watchlist"] = [row(k) for k in ("PLTR", "DKNG", "SOFI")]
    proposals = [buy(k, allocation=5) for k in ("PLTR", "DKNG", "SOFI")]
    outcome = p.submit_orders(proposals, "2024-03-04", market_snapshot=ss)
    assert [x["status"] for x in outcome] == ["ACCEPTED", "ACCEPTED", "REJECTED"], outcome
    assert len(p.pending_orders) == 2
    p = sim()
    for i in range(8):
        p.positions[f"P{i}"] = Position(f"P{i}", 1, 20, "2024-03-01",
                                         18, current_price=20)
    assert p.submit_orders([buy()], "2024-03-04",
                           market_snapshot=snap())[0]["status"] == "REJECTED"


@test
@strict
def t_total_exposure_and_aggregate_stop_risk_rejected():
    # 80% already invested leaves only 5% room under the risk-on 85% ceiling.
    p = sim()
    p.positions["OLD"] = Position("OLD", 800, 10, "2024-03-01",
                                  9.5, current_price=10)
    p.cash = 2000
    outcome = p.submit_orders([buy(allocation=10)], "2024-03-04",
                              market_snapshot=snap())
    assert "exposure" in outcome[0]["reason"], outcome

    # 2.88% stop exposure on an existing holding + 0.6% new risk >3% total.
    p = sim()
    p.positions["OLD"] = Position("OLD", 400, 10, "2024-03-01",
                                  9.28, current_price=10)
    p.cash = 6000
    outcome = p.submit_orders([buy()], "2024-03-04", market_snapshot=snap())
    assert "stop-risk" in outcome[0]["reason"], outcome


@test
def t_claude_and_live_chatgpt_paths_unchanged():
    old = os.environ.get("BACKTEST_STRICT_PRICES")
    try:
        os.environ["BACKTEST_STRICT_PRICES"] = "1"
        other = sim("claude_aggressive")
        assert other.submit_orders([buy("TNA")], "2024-03-04")[0]["status"] == "ACCEPTED"
        os.environ.pop("BACKTEST_STRICT_PRICES", None)
        live = sim()
        assert live.submit_orders([buy("TNA")], "2024-03-04")[0]["status"] == "ACCEPTED"
    finally:
        if old is None: os.environ.pop("BACKTEST_STRICT_PRICES", None)
        else: os.environ["BACKTEST_STRICT_PRICES"] = old

def main():
    fail = 0
    for fn in TESTS:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("FAIL", fn.__name__, e)
            fail += 1
    print(f"{len(TESTS)-fail} passed, {fail} failed")
    return fail == 0

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
