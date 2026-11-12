"""ChatGPT-v2 historical BUY firewall. Pure stdlib; no market/API calls.

This intentionally uses a REVIEWED STOCK-ONLY subset of the existing curated
ticker seed. It is stricter than the playbook (which also permits unlevered
ETFs): ordinary ETFs remain unapproved until a verified instrument registry is
available. No symbol not explicitly listed can be purchased in strict tests.
This is NOT proof of point-in-time constituent membership/survivorship freedom.
The rules below are applied only by chatgpt_aggressive in strict backtests.
"""

import math
from datetime import date

# Explicit stock approvals instead of a blacklist-only ETF detector:
# TSLL, SOXL, LABU, TNA, SRTY and BITO from the original seed are excluded.
APPROVED_HISTORICAL_EQUITIES = frozenset(
    "AAPL ABNB AEHR AFRM ALNY AMD AMZN ARWR ASAN AXON BE BEAM BLNK BMEA BPMC CELH CHPT CLSK COIN CPRI CPRX CRSP CRWD CVNA DASH DDOG DKNG DOCU DUOL EDIT ENPH ERAS EXEL FSLR FSLY GOOGL GTLB HOOD HPQ IMVT INTC IONQ KRTX LCID MARA MBLY MDB MELI META MSFT MSTR MU NET NTLA NU NVDA OKTA OPEN PAGS PANW PATH PENN PLTR PLUG PTON PYPL QS QUBT RBLX RGTI RIOT RIVN RUN S SE SHOP SNAP SNOW SOFI SQ STNE TEAM TSLA U UPST VERV VRTX Z ZM ZS".split()
)


def approved_equity(ticker):
    """Unknown, geared, inverse or non-equity symbols fail closed."""
    return isinstance(ticker, str) and ticker.upper() in APPROVED_HISTORICAL_EQUITIES


def _finite_number(value):
    return (isinstance(value, (int, float))
            and not isinstance(value, bool) and math.isfinite(value))


def _regime(snapshot, today):
    """Derive a conservative point-in-time regime from structured snapshot.

    A missing, stale or future VIX and missing historical SPY SMA result in
    UNKNOWN, which forbids new buys. This enforces the daily no-buy regime
    gate, not the playbook's multi-session risk-off re-entry cooldown.
    """
    ctx = snapshot.get("regime_context") if isinstance(snapshot, dict) else None
    if not isinstance(ctx, dict) or ctx.get("date") != today:
        return "UNKNOWN"
    spy = ctx.get("spy_sma200_dist_pct")
    vix = ctx.get("vix")
    obs = ctx.get("vix_date")
    if not _finite_number(spy) or not _finite_number(vix) or not isinstance(obs, str):
        return "UNKNOWN"
    try:
        age = (date.fromisoformat(today) - date.fromisoformat(obs)).days
    except ValueError:
        return "UNKNOWN"
    if age < 0 or age > 4 or vix <= 0:
        return "UNKNOWN"
    if vix >= 40 or (spy <= -5 and vix >= 30):
        return "PANIC"
    if spy < -1 or vix >= 30:
        return "RISK_OFF"
    if spy > 1 and vix < 25:
        return "RISK_ON"
    return "NEUTRAL"


def buy_rejection(trade, snapshot, simulator, today, accepted_buys=0):
    """Return a rejection explanation, else None.

    Fail closed on missing machine-verifiable data. Applies pre-order to the
    simulator's real state; no model text can override this function. Do not
    call for SELLs: even an ineligible old holding must remain sellable.
    """
    ticker = str(trade.get("ticker", "")).upper()
    if not approved_equity(ticker):
        return f"{ticker}: not in reviewed historical equity-only universe"

    if not isinstance(snapshot, dict) or snapshot.get("metadata", {}).get("date") != today:
        return "Missing matching-date market snapshot"
    candidates = {r.get("Tkr"): r for r in snapshot.get("watchlist", [])
                  if isinstance(r, dict)}
    row = candidates.get(ticker)
    if row is None:
        return f"{ticker}: not in the exact-date eligible watchlist"
    if ticker in simulator.positions or any(
            getattr(o, "ticker", None) == ticker and
            getattr(getattr(o, "action", None), "value", None) == "BUY"
            for o in simulator.pending_orders):
        return f"{ticker}: no averaging down or duplicate pending BUY"

    regime = _regime(snapshot, today)
    if regime not in ("RISK_ON", "NEUTRAL"):
        return f"{ticker}: regime {regime} forbids new buys"
    num_positions = len(simulator.positions) + sum(
        1 for o in simulator.pending_orders
        if getattr(getattr(o, "action", None), "value", None) == "BUY"
        and o.ticker not in simulator.positions)
    if num_positions >= 8:
        return "Maximum 8 active/pending positions"
    if accepted_buys + sum(
            1 for o in simulator.pending_orders
            if getattr(getattr(o, "action", None), "value", None) == "BUY") >= 2:
        return "Maximum 2 new BUY orders per session"

    fields = ("Price", "SMA_20_Dist", "SMA_50_Dist", "RS_1M_vs_SPY",
              "RSI", "RVOL_Z", "ATR_Pct")
    if any(not _finite_number(row.get(k)) for k in fields):
        return f"{ticker}: missing or nonfinite entry indicators"
    price, d20, d50, rs, rsi, rvol, atr = (row[k] for k in fields)
    if not (3 <= price <= 50):
        return f"{ticker}: outside price universe"
    # Since both distances use same positive price, d20>d50 iff SMA20>SMA50.
    if d20 <= 0 or d50 <= 0 or d20 <= d50:
        return f"{ticker}: price/SMA20/SMA50 trend check failed"
    if rs <= 0:
        return f"{ticker}: positive one-month SPY relative strength not confirmed"
    if not (45 <= rsi <= 70):
        return f"{ticker}: RSI outside approximately 45–70"
    if rvol <= 0:
        return f"{ticker}: positive volume participation not confirmed"

    stop = trade.get("stop_loss_pct")
    target = trade.get("take_profit_pct")
    allocation = trade.get("allocation_pct")
    if any(not _finite_number(x) for x in (stop, target, allocation)):
        return f"{ticker}: missing/nonfinite stop, reward target or allocation"
    required_stop = max(6.0, 1.5 * atr)
    if required_stop > 12:
        return f"{ticker}: ATR-based stop exceeds the 12% permitted limit"
    if not (6 <= stop <= 12) or abs(stop - required_stop) > 0.15:
        return f"{ticker}: stop must match ATR-based {required_stop:.2f}%"
    if target < 2.5 * stop:
        return f"{ticker}: target below 2.5 times the initial stop distance"

    risk_budget = 0.8 if regime == "RISK_ON" else 0.45
    single_ceiling = 12.0 if regime == "RISK_ON" else 8.0
    exposure_ceiling = 85.0 if regime == "RISK_ON" else 50.0
    if allocation < 5 or allocation > single_ceiling + 1e-9:
        return f"{ticker}: BUY allocation outside regime minimum/maximum"
    if allocation * stop / 100 > risk_budget + 1e-8:
        return f"{ticker}: proposed loss at stop exceeds {risk_budget}% risk budget"

    equity = simulator.portfolio_value
    if equity <= 0:
        return "Invalid portfolio equity"
    invested = sum(p.market_value for p in simulator.positions.values()) / equity * 100
    pending = sum(o.allocation_pct for o in simulator.pending_orders
                  if getattr(getattr(o, "action", None), "value", None) == "BUY")
    if invested + pending + allocation > exposure_ceiling + 1e-9:
        return f"{ticker}: regime total equity exposure ceiling exceeded"
    if allocation > simulator.cash / equity * 100 + 1e-9:
        return f"{ticker}: insufficient cash"

    open_stop_risk = sum(
        p.market_value * max(0.0, (p.current_price - p.stop_loss_price)
                                   / p.current_price)
        for p in simulator.positions.values() if p.current_price > 0)
    pending_stop_risk = sum(
        o.allocation_pct / 100 * equity * o.stop_loss_pct / 100
        for o in simulator.pending_orders
        if getattr(getattr(o, "action", None), "value", None) == "BUY")
    if (open_stop_risk + pending_stop_risk
            + equity * allocation / 100 * stop / 100) / equity * 100 > 3.0:
        return f"{ticker}: aggregate 3% approximate stop-risk budget exceeded"

    reason = trade.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return f"{ticker}: missing trade thesis"
    return None
