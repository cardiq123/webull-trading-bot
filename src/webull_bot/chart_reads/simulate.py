"""$1,000 books for the chart-read setups.

Three expressions, scored separately:

* a single option, 0-7 DTE, delta about 0.45, whole contracts
* a debit spread, 7-14 DTE, on SPY and QQQ only
* fractional shares sized off the stop, notional capped by cash

One contract or spread is skipped when its debit is above the pre-registered
fraction of equity. The default account is margin under $25,000, so a fourth
day trade in five sessions is blocked. A cash variant does not reuse a sale
until the next session. Option prices are Black-Scholes. 0-7 DTE prices are
rough. Nothing here calls a broker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.detect import Setup, rth, session_bands
from webull_bot.costs import CostModel, buy_price, sell_price
from webull_bot.indicators import ema
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import (
    listed_strike,
    option_delta,
    option_price,
    realized_vol,
    strike_for_delta,
    strike_for_put_delta,
)
from webull_bot.risk.pdt import check_day_trade

RATE = 0.02
DIVIDEND = 0.018
HALF_SPREAD_ATM = 0.04
HALF_SPREAD_OTM = 0.08
HALF_SPREAD_CHEAP = 0.12
CHEAP_MID = 1.00
MIN_MID = 0.05
VOL_FLOOR = 0.10
VOL_CAP = 1.50
BUST_FLOOR = 100.0
SPREAD_UNDERLYINGS = frozenset({"SPY", "QQQ"})
MIN_SHARES = 0.01


@dataclass
class BookStats:
    metrics: dict[str, Any]
    trades: pd.DataFrame
    equity: pd.Series
    pdt_blocked: int = 0
    premium_skipped: int = 0
    bust: bool = False
    min_equity: float = 0.0
    ruin_estimate: Optional[float] = None
    ending_equity: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def _half_spread(delta: float, mid: float, multiplier: float) -> float:
    if mid < CHEAP_MID:
        base = HALF_SPREAD_CHEAP
    elif abs(delta) >= 0.50:
        base = HALF_SPREAD_ATM
    else:
        base = HALF_SPREAD_OTM
    return base * multiplier


def _buy(mid: float, delta: float, multiplier: float) -> float:
    return max(MIN_MID, mid) * (1.0 + _half_spread(delta, mid, multiplier))


def _sell(mid: float, delta: float, multiplier: float) -> float:
    return max(0.0, mid * (1.0 - _half_spread(delta, mid, multiplier)))


def _years(dte: int, stamp: pd.Timestamp) -> float:
    """Time left. One minute is the floor so a 0 DTE formula does not divide by zero.

    Prices inside a week are still a sketch.
    """
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert("America/New_York")
    minutes_left = max(0, (16 * 60) - (clock.hour * 60 + clock.minute))
    return max(1.0 / (365.0 * 24.0 * 60.0), (int(dte) + minutes_left / (24.0 * 60.0)) / 365.0)


def _session(stamp: pd.Timestamp) -> date:
    ts = pd.Timestamp(stamp)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("America/New_York")
    return ts.date()


def _vol(rv: pd.Series, day: date, iv_premium: float) -> Optional[float]:
    if rv.empty:
        return None
    value = rv.asof(pd.Timestamp(day))
    if value is None or pd.isna(value):
        return None
    scaled = float(value) * iv_premium
    if not np.isfinite(scaled):
        return None
    return min(VOL_CAP, max(VOL_FLOOR, scaled))


def simulate(
    setups: list[Setup],
    execution: dict[str, pd.DataFrame],
    daily: dict[str, pd.DataFrame],
    params: dict,
    *,
    starting_equity: float = 1_000.0,
    costs: CostModel | None = None,
) -> BookStats:
    return _simulate(
        setups,
        execution,
        daily,
        params,
        starting_equity=starting_equity,
        costs=costs or CostModel(),
    )


def _simulate(
    setups: list[Setup],
    execution: dict[str, pd.DataFrame],
    daily: dict[str, pd.DataFrame],
    params: dict,
    *,
    starting_equity: float,
    costs: CostModel,
) -> BookStats:
    frames = {symbol: rth(frame) for symbol, frame in execution.items() if frame is not None and len(frame)}
    if not frames:
        return _empty(starting_equity)
    clock = pd.DatetimeIndex(sorted(set().union(*[set(frame.index) for frame in frames.values()])))
    trails: dict[str, dict[str, pd.Series]] = {}
    bands: dict[str, pd.DataFrame] = {}
    priors: dict[str, dict[date, tuple[float, float]]] = {}
    for symbol, frame in frames.items():
        close = frame["close"].astype(float)
        trails[symbol] = {"ema9": ema(close, 9), "ema20": ema(close, 20)}
        bands[symbol] = session_bands(frame, float(params.get("band_std", 2.0)))
        priors[symbol] = _prior_extremes(frame)
    rv = _realized(daily)
    by_fill: dict[pd.Timestamp, list[Setup]] = {}
    for setup in setups:
        if setup.symbol not in frames:
            continue
        by_fill.setdefault(pd.Timestamp(setup.fill_time), []).append(setup)

    cash = float(starting_equity)
    settled = float(starting_equity)
    unsettled: list[tuple[date, float]] = []
    positions: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    day_trades: list[date] = []
    equity_values: list[float] = []
    exposure_values: list[float] = []
    index: list[pd.Timestamp] = []
    pdt_blocked = 0
    premium_skipped = 0
    account = str(params.get("account", "margin_pdt"))
    max_positions = int(params.get("max_positions", 1))
    flatten_eod = bool(params.get("flatten_eod", True))
    max_sessions = int(params.get("max_hold_sessions", 1))

    for ts in clock:
        ts = pd.Timestamp(ts)
        session = _session(ts)
        if account == "cash_t1":
            still_cash = []
            for available_on, amount in unsettled:
                if available_on <= session:
                    settled += amount
                else:
                    still_cash.append((available_on, amount))
            unsettled = still_cash
        equity_now = cash + _mark(positions, frames, ts, params, field="open")
        for setup in by_fill.get(ts, []):
            if len(positions) >= max_positions:
                break
            if any(pos["symbol"] == setup.symbol for pos in positions):
                continue
            if account == "margin_pdt":
                decision = check_day_trade(
                    as_of=session,
                    equity=equity_now,
                    trade_days=day_trades,
                    opening_same_day=True,
                    account_type="margin",
                    mode="on",
                )
                if not decision.allowed:
                    pdt_blocked += 1
                    continue
            buying = settled if account == "cash_t1" else cash
            opened = _open(setup, ts, frames, rv, bands, priors, equity_now, buying, params, costs)
            if opened is None:
                premium_skipped += 1
                continue
            cash -= opened["debit"]
            if account == "cash_t1":
                settled -= opened["debit"]
            positions.append(opened)
            equity_now = cash + _mark(positions, frames, ts, params, field="open")

        last_bar = _is_last_rth(ts, clock)
        still = []
        for pos in positions:
            held = _sessions_held(pos["opened_on"], session)
            reason = _exit_reason(pos, ts, frames, trails, params, last_bar, held, max_sessions, flatten_eod)
            if reason is None:
                still.append(pos)
                continue
            credit = _credit(pos, ts, frames, params, reason, costs)
            cash += credit
            if account == "cash_t1":
                unsettled.append((next_trading_day(session), credit))
            if pos["opened_on"] == session:
                day_trades.append(session)
            closed.append(_row(pos, ts, credit, reason))
        positions = still
        equity_now = cash + _mark(positions, frames, ts, params, field="close")
        at_risk = sum(float(pos["debit"]) for pos in positions)
        equity_values.append(equity_now)
        exposure_values.append(at_risk / equity_now if equity_now else 0.0)
        index.append(ts)

    if positions and index:
        ts = index[-1]
        for pos in positions:
            credit = _credit(pos, ts, frames, params, "window_end", costs)
            cash += credit
            closed.append(_row(pos, ts, credit, "window_end"))
        equity_values[-1] = cash
        exposure_values[-1] = 0.0

    equity = pd.Series(equity_values, index=pd.DatetimeIndex(index), name="equity")
    exposure = pd.Series(exposure_values, index=equity.index, name="exposure") if len(equity) else pd.Series(dtype=float)
    trades = pd.DataFrame(closed)
    result = BacktestResult(
        equity=equity,
        exposure=exposure,
        trades=trades,
        ending_equity=float(equity.iloc[-1]) if len(equity) else starting_equity,
    )
    metrics = compute_metrics(result, starting_equity)
    min_equity = float(equity.min()) if len(equity) else starting_equity
    bust = bool(len(equity) and (equity < BUST_FLOOR).any())
    return BookStats(
        metrics=metrics,
        trades=trades,
        equity=equity,
        pdt_blocked=pdt_blocked,
        premium_skipped=premium_skipped,
        bust=bust,
        min_equity=min_equity,
        ruin_estimate=_ruin(trades, starting_equity),
        ending_equity=float(metrics["ending_equity"]),
    )


def _realized(daily: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    rv: dict[str, pd.Series] = {}
    for symbol, frame in daily.items():
        if frame is None or frame.empty:
            continue
        series = realized_vol(frame["close"].astype(float)).shift(1)
        index = pd.DatetimeIndex(series.index)
        if index.tz is not None:
            index = index.tz_convert("America/New_York").tz_localize(None)
        series.index = index.normalize()
        rv[symbol] = series
    return rv


def _prior_extremes(frame: pd.DataFrame) -> dict[date, tuple[float, float]]:
    days = pd.Series([ts.date() for ts in frame.index], index=frame.index)
    grouped = frame.groupby(days).agg(high=("high", "max"), low=("low", "min"))
    prior_high = grouped["high"].shift(1)
    prior_low = grouped["low"].shift(1)
    out: dict[date, tuple[float, float]] = {}
    for day in grouped.index:
        high = prior_high.loc[day]
        low = prior_low.loc[day]
        out[day] = (
            float(high) if pd.notna(high) else np.nan,
            float(low) if pd.notna(low) else np.nan,
        )
    return out


def _open(setup, ts, frames, rv, bands, priors, equity, buying_cash, params, costs) -> Optional[dict]:
    frame = frames.get(setup.symbol)
    if frame is None or ts not in frame.index:
        return None
    spot = float(frame.loc[ts, "open"])
    if not np.isfinite(spot) or spot <= 0:
        return None
    stop = float(setup.stop)
    if setup.direction == "long" and spot <= stop:
        return None
    if setup.direction == "short" and spot >= stop:
        return None
    risk_budget = equity * float(params["risk_fraction"])
    budget = min(risk_budget, buying_cash)
    if budget <= 0:
        return None
    expression = str(params.get("expression", "single"))
    band, prior = _context(setup, ts, bands, priors)
    if expression == "stock":
        return _open_stock(setup, ts, spot, stop, risk_budget, buying_cash, params, costs, band, prior)
    if expression == "spread":
        return _open_spread(setup, ts, spot, stop, budget, rv, params, band, prior)
    return _open_single(setup, ts, spot, stop, budget, rv, params, band, prior)


def _context(setup, ts, bands, priors) -> tuple[float, float]:
    band = np.nan
    table = bands.get(setup.symbol)
    if table is not None and ts in table.index:
        column = "upper" if setup.direction == "long" else "lower"
        band = float(table.loc[ts, column])
    pair = priors.get(setup.symbol, {}).get(_session(ts), (np.nan, np.nan))
    prior = pair[0] if setup.direction == "long" else pair[1]
    return band, prior


def _target(direction: str, fill: float, stop: float, params: dict, band: float, prior: float) -> float:
    risk = abs(fill - stop)
    r_multiple = fill + float(params["reward_r"]) * risk if direction == "long" else fill - float(params["reward_r"]) * risk
    if str(params.get("target_mode", "r")) != "level":
        return float(r_multiple)
    if direction == "long":
        candidates = [value for value in (band, prior) if np.isfinite(value) and value >= fill + 0.5 * risk]
        return float(min(candidates) if candidates else r_multiple)
    candidates = [value for value in (band, prior) if np.isfinite(value) and value <= fill - 0.5 * risk]
    return float(max(candidates) if candidates else r_multiple)


def _base(setup, ts, fill: float, stop: float, quantity: float, debit: float, expression: str, params, band, prior) -> dict:
    return {
        "symbol": setup.symbol,
        "direction": setup.direction,
        "expression": expression,
        "quantity": float(quantity),
        "debit": float(debit),
        "entry": float(fill),
        "opened_on": _session(ts),
        "entry_time": ts,
        "stop": float(stop),
        "target": _target(setup.direction, fill, stop, params, band, prior),
        "bars": 0,
    }


def _open_stock(setup, ts, spot, stop, risk_budget, buying_cash, params, costs, band, prior) -> Optional[dict]:
    fill = buy_price(spot, costs) if setup.direction == "long" else sell_price(spot, costs)
    if setup.direction == "long" and fill <= stop:
        return None
    if setup.direction == "short" and fill >= stop:
        return None
    distance = abs(fill - stop)
    if distance <= 0 or buying_cash <= 0:
        return None
    shares = min(risk_budget / distance, buying_cash / fill)
    if shares < MIN_SHARES:
        return None
    position = _base(setup, ts, fill, stop, shares, shares * fill, "stock", params, band, prior)
    return position


def _dte(params: dict, expression: str) -> int:
    if expression == "spread":
        return int(params.get("spread_dte", params.get("dte", 10)))
    return int(params.get("dte", 3))


def _right_strike(direction: str, spot: float, years: float, sigma: float, delta: float) -> tuple[str, float, float, float]:
    right = "call" if direction == "long" else "put"
    raw = (
        strike_for_delta(spot, years, sigma, delta, RATE, DIVIDEND)
        if right == "call"
        else strike_for_put_delta(spot, years, sigma, delta, RATE, DIVIDEND)
    )
    strike = listed_strike(spot, raw)
    return right, strike, raw, years


def _open_single(setup, ts, spot, stop, budget, rv, params, band, prior) -> Optional[dict]:
    sigma = _vol(rv.get(setup.symbol, pd.Series(dtype=float)), _session(ts), float(params["iv_premium"]))
    if sigma is None:
        return None
    years = _years(_dte(params, "single"), ts)
    right, strike, _raw, years = _right_strike(setup.direction, spot, years, sigma, float(params["delta"]))
    mid = option_price(right, spot, strike, years, sigma, RATE, DIVIDEND)
    delta = option_delta(right, spot, strike, years, sigma, RATE, DIVIDEND)
    ask = _buy(mid, delta, float(params["spread_multiplier"]))
    one = ask * CONTRACT_MULTIPLIER + option_leg_fees(1, ask, sell=False)
    if one > budget or one <= 0:
        return None
    contracts = int(np.floor(budget / one))
    if contracts < 1:
        return None
    fees = option_leg_fees(contracts, ask, sell=False)
    debit = contracts * ask * CONTRACT_MULTIPLIER + fees
    position = _base(setup, ts, ask, stop, contracts, debit, "single", params, band, prior)
    position.update({"right": right, "strike": strike, "sigma": sigma, "expiry_years": years, "delta": delta})
    return position


def _open_spread(setup, ts, spot, stop, budget, rv, params, band, prior) -> Optional[dict]:
    if setup.symbol not in SPREAD_UNDERLYINGS:
        return None
    sigma = _vol(rv.get(setup.symbol, pd.Series(dtype=float)), _session(ts), float(params["iv_premium"]))
    if sigma is None:
        return None
    years = _years(_dte(params, "spread"), ts)
    width = float(params.get("spread_width", 2.0))
    right, long_strike, _raw, years = _right_strike(setup.direction, spot, years, sigma, float(params["delta"]))
    if right == "call":
        short_strike = listed_strike(spot, long_strike + width)
        if short_strike <= long_strike:
            short_strike = long_strike + width
    else:
        short_strike = listed_strike(spot, long_strike - width)
        if short_strike >= long_strike:
            short_strike = max(0.5, long_strike - width)
    long_mid = option_price(right, spot, long_strike, years, sigma, RATE, DIVIDEND)
    short_mid = option_price(right, spot, short_strike, years, sigma, RATE, DIVIDEND)
    long_delta = option_delta(right, spot, long_strike, years, sigma, RATE, DIVIDEND)
    short_delta = option_delta(right, spot, short_strike, years, sigma, RATE, DIVIDEND)
    long_ask = _buy(long_mid, long_delta, float(params["spread_multiplier"]))
    short_bid = _sell(short_mid, short_delta, float(params["spread_multiplier"]))
    debit_ps = long_ask - short_bid
    if debit_ps <= 0.05 or debit_ps >= width - 0.01:
        return None
    fees_one = option_leg_fees(1, long_ask, sell=False) + option_leg_fees(1, short_bid, sell=True)
    one = debit_ps * CONTRACT_MULTIPLIER + fees_one
    if one > budget or one <= 0:
        return None
    contracts = int(np.floor(budget / one))
    if contracts < 1:
        return None
    fees = option_leg_fees(contracts, long_ask, sell=False) + option_leg_fees(contracts, short_bid, sell=True)
    debit = contracts * debit_ps * CONTRACT_MULTIPLIER + fees
    position = _base(setup, ts, debit_ps, stop, contracts, debit, "spread", params, band, prior)
    position.update(
        {
            "right": right,
            "strike": long_strike,
            "short_strike": short_strike,
            "sigma": sigma,
            "expiry_years": years,
            "delta": long_delta,
            "short_delta": short_delta,
            "width": width,
        }
    )
    return position


def _exit_reason(pos, ts, frames, trails, params, last_bar, sessions_held, max_sessions, flatten_eod) -> Optional[str]:
    frame = frames[pos["symbol"]]
    if ts not in frame.index:
        return None
    row = frame.loc[ts]
    high = float(row["high"])
    low = float(row["low"])
    close = float(row["close"])
    opened = float(row["open"])
    pos["bars"] = int(pos["bars"]) + 1
    if pos["direction"] == "long":
        if opened <= pos["stop"] or low <= pos["stop"]:
            return "invalidation"
        if high >= float(pos["target"]):
            return "target"
    else:
        if opened >= pos["stop"] or high >= pos["stop"]:
            return "invalidation"
        if low <= float(pos["target"]):
            return "target"
    trail = str(params.get("trail", "ema20"))
    if trail in {"ema9", "ema20"}:
        series = trails[pos["symbol"]][trail]
        if ts in series.index and np.isfinite(series.loc[ts]):
            level = float(series.loc[ts])
            if pos["direction"] == "long" and close < level:
                return "ema_trail"
            if pos["direction"] == "short" and close > level:
                return "ema_trail"
    if sessions_held >= max_sessions and last_bar:
        return "time_stop"
    if flatten_eod and last_bar:
        return "session_flat"
    return None


def _bar_at(frame: pd.DataFrame, ts: pd.Timestamp):
    """Last bar at or before ``ts``. The shared clock can end on another symbol."""
    if ts in frame.index:
        return frame.loc[ts]
    prior = frame.loc[:ts]
    if prior.empty:
        return frame.iloc[0]
    return prior.iloc[-1]


def _spot_for(pos, ts, frames, reason: str) -> float:
    row = _bar_at(frames[pos["symbol"]], ts)
    opened = float(row["open"])
    if reason == "invalidation":
        if pos["direction"] == "long" and opened <= pos["stop"]:
            return opened
        if pos["direction"] == "short" and opened >= pos["stop"]:
            return opened
        return float(pos["stop"])
    if reason == "target":
        return float(pos["target"])
    return float(row["close"])


def _option_bid(pos, ts, spot: float, params) -> float:
    years = _years_left(pos, ts)
    mid = option_price(pos["right"], spot, pos["strike"], years, pos["sigma"], RATE, DIVIDEND)
    delta = option_delta(pos["right"], spot, pos["strike"], years, pos["sigma"], RATE, DIVIDEND)
    return _sell(mid, delta, float(params["spread_multiplier"]))


def _spread_value(pos, ts, spot: float, params) -> float:
    """Cash received to close one spread. The short leg is bought back at the ask."""
    years = _years_left(pos, ts)
    long_mid = option_price(pos["right"], spot, pos["strike"], years, pos["sigma"], RATE, DIVIDEND)
    short_mid = option_price(pos["right"], spot, pos["short_strike"], years, pos["sigma"], RATE, DIVIDEND)
    long_delta = option_delta(pos["right"], spot, pos["strike"], years, pos["sigma"], RATE, DIVIDEND)
    short_delta = option_delta(pos["right"], spot, pos["short_strike"], years, pos["sigma"], RATE, DIVIDEND)
    long_bid = _sell(long_mid, long_delta, float(params["spread_multiplier"]))
    short_ask = _buy(short_mid, short_delta, float(params["spread_multiplier"]))
    return max(0.0, long_bid - short_ask)


def _years_left(pos, ts) -> float:
    opened = pd.Timestamp(pos["entry_time"])
    now = pd.Timestamp(ts)
    elapsed = max(0.0, (now - opened).total_seconds() / (365.0 * 24 * 3600))
    return max(1.0 / (365.0 * 24.0 * 60.0), float(pos["expiry_years"]) - elapsed)


def _credit(pos, ts, frames, params, reason, costs) -> float:
    if pos["expression"] == "stock":
        raw = _spot_for(pos, ts, frames, reason)
        quantity = float(pos["quantity"])
        if pos["direction"] == "long":
            return quantity * sell_price(raw, costs)
        cover = buy_price(raw, costs)
        return float(pos["debit"]) + (float(pos["entry"]) - cover) * quantity
    spot = _spot_for(pos, ts, frames, reason)
    contracts = int(pos["quantity"])
    if pos["expression"] == "spread":
        value = _spread_value(pos, ts, spot, params)
        # The close is one package. Charging both legs on that package is a few cents high.
        fees = option_leg_fees(contracts, value, sell=True) + option_leg_fees(contracts, value, sell=False)
        return max(0.0, contracts * value * CONTRACT_MULTIPLIER - fees)
    bid = _option_bid(pos, ts, spot, params)
    fees = option_leg_fees(contracts, bid, sell=True)
    return max(0.0, contracts * bid * CONTRACT_MULTIPLIER - fees)


def _mark(positions, frames, ts, params, field: str) -> float:
    marked = 0.0
    for pos in positions:
        frame = frames.get(pos["symbol"])
        if frame is None or ts not in frame.index:
            marked += float(pos["debit"])
            continue
        spot = float(frame.loc[ts, field if field in frame.columns else "close"])
        if pos["expression"] == "stock":
            if pos["direction"] == "long":
                marked += float(pos["quantity"]) * spot
            else:
                marked += float(pos["debit"]) + (float(pos["entry"]) - spot) * float(pos["quantity"])
        elif pos["expression"] == "spread":
            marked += float(pos["quantity"]) * _spread_value(pos, ts, spot, params) * CONTRACT_MULTIPLIER
        else:
            marked += float(pos["quantity"]) * _option_bid(pos, ts, spot, params) * CONTRACT_MULTIPLIER
    return marked


def _row(pos, ts, credit, reason) -> dict:
    quantity = float(pos["quantity"])
    return {
        "symbol": pos["symbol"],
        "strategy": f"{pos['direction']}_{pos['expression']}",
        "quantity": quantity,
        "entry_time": pos["entry_time"],
        "entry_price": pos["entry"],
        "exit_time": ts,
        "exit_price": credit / quantity if quantity else 0.0,
        "pnl": credit - float(pos["debit"]),
        "fees": 0.0,
        "reason": reason,
        "bars_held": pos["bars"],
    }


def _sessions_held(opened: date, today: date) -> int:
    if today <= opened:
        return 1
    cursor = opened
    count = 1
    while cursor < today and count < 12:
        cursor = next_trading_day(cursor)
        count += 1
    return count


def _is_last_rth(ts: pd.Timestamp, clock: pd.DatetimeIndex) -> bool:
    loc = clock.get_loc(ts)
    if isinstance(loc, slice):
        loc = loc.start
    if isinstance(loc, np.ndarray):
        loc = int(loc[0])
    if loc >= len(clock) - 1:
        return True
    return _session(clock[loc + 1]) != _session(ts)


def _ruin(trades: pd.DataFrame, starting: float) -> Optional[float]:
    """Chance of eventually going broke if these payoffs repeated. An estimate."""
    if trades is None or trades.empty or len(trades) < 5:
        return None
    pnl = trades["pnl"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    if len(wins) == 0 or len(losses) == 0:
        return 0.0 if len(losses) == 0 else 1.0
    probability = float(len(wins) / len(pnl))
    average_win = float(wins.mean())
    average_loss = float(-losses.mean())
    edge = probability * average_win - (1.0 - probability) * average_loss
    if edge <= 0:
        return 1.0
    ratio = ((1.0 - probability) * average_loss) / (probability * average_win)
    units = starting / average_loss
    if ratio >= 1:
        return 1.0
    return float(min(1.0, ratio ** units))


def _empty(starting: float) -> BookStats:
    metrics = compute_metrics(
        BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
        starting,
    )
    return BookStats(
        metrics=metrics,
        trades=pd.DataFrame(),
        equity=pd.Series(dtype=float),
        min_equity=starting,
        ending_equity=starting,
        ruin_estimate=None,
    )
