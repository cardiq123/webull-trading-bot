"""Monday, Wednesday, and Friday SPY opening-range breakout.

The rule is frozen before any score. Nothing here places an order or imports
the sandbox forward test.

The range is only the 09:30-09:35 ET candle. Later bars in the open do not
move it. A session is tradable only on Monday, Wednesday, and Friday, only
when that weekday has a real SPY expiration, and only when it is not a CPI
day, an Employment Situation day, or an FOMC decision day.

The break is the first later bar that trades through the high or the low.
A print equal to the level is not a break. One break per session. If that
bar trades through both sides, the session is skipped because the path
inside the bar is unknown. The default fill assumes the underlying at the
level, worsened by stock slippage, then buys the at-the-money option at the
ask. A bar that opens already through the level fills at that open. The
next bar's open is a sensitivity.

The option is the listed strike nearest the spot, expiring the same day.
Risk is a fixed dollar budget that can be lost in full. Contracts are
floor(budget / debit of one contract). A debit above the budget is skipped.
There is no stop. A call is sold at +100% of the entry ask. A put is sold
at +50% of the entry ask. Anything still open is sold at the 15:30 ET bid,
which can be near zero. A target fills at the target. No adds and no rolls.

The price is Black-Scholes with minutes left until 16:00 ET. That model is
the uncertainty in the result. There is no historical option chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.calendar import is_trading_day, next_trading_day
from webull_bot.chart_reads.event_days import CALENDAR_YEARS, event_kind
from webull_bot.costs import CostModel
from webull_bot.mtf_vwap.detect import rth
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price
from webull_bot.risk.pdt import check_day_trade

# Friday short-term SPY series were already listed when Wednesday expirations
# were added (CBOE SR-CBOE-2016-062, August 24, 2016). Wednesday series were
# listed effective August 30, 2016, so the first Wednesday expiration is
# August 31, 2016 (CBOE RG16-147). Monday series were listed effective
# February 16, 2018 (CBOE notice, February 15, 2018). February 19, 2018 was
# a holiday, and a holiday Monday expiration moves to the next business day,
# so the first Monday session with a Monday expiration is February 26, 2018.
# Tuesday and Thursday expirations began November 14 and 16, 2022. This study
# does not trade them. A quarterly series that lands on Monday or Wednesday
# still expires that day, so those sessions stay in the set.
FRIDAY_0DTE = date(2016, 1, 8)
WEDNESDAY_0DTE = date(2016, 8, 31)
MONDAY_0DTE = date(2018, 2, 26)

RATE = 0.02
DIVIDEND = 0.018
HALF_SPREAD_PCT = 0.015
HALF_SPREAD_FLOOR = 0.01
VOL_FLOOR = 0.05
VOL_CAP = 1.50
CALL_TARGET = 2.0
PUT_TARGET = 1.5
FLAT = time(15, 30)
_OPEN = time(9, 30)
_FIVE = time(9, 35)
STARTING_EQUITY = 1_000.0
RISK_PRIMARY = 100.0
RISK_SENSITIVITIES = (200.0, 500.0)
IV_PRIMARY = 1.0
IV_SENSITIVITY = 1.3
FILL_PRIMARY = "level"
SEED = 17

NY = "America/New_York"


def frozen_rules() -> dict:
    """Written down before the result is scored. The score does not edit this."""
    return {
        "range": "09:30-09:35 ET only. 5-minute: the 09:30 bar. 1-minute: 09:30 through 09:34.",
        "days": "Monday, Wednesday, Friday only.",
        "skip": "CPI release, Employment Situation, FOMC decision day. 2017-2026 BLS and Fed calendars.",
        "break": "First later bar that trades strictly through the high or the low. Equal is not a break.",
        "both_sides": "A bar through both sides is skipped.",
        "one_trade": "First break only, one option per session.",
        "fill": "Default: underlying at the broken level plus stock slippage, option at the ask. Gap open fills at the open. Next-bar open is a sensitivity.",
        "right": "Break of the high buys the ATM call. Break of the low buys the ATM put. ATM is the nearest listed strike.",
        "dte": 0,
        "expiry": "Only sessions with a real SPY expiration on that weekday.",
        "risk": RISK_PRIMARY,
        "risk_sensitivities": list(RISK_SENSITIVITIES),
        "sizing": "contracts = floor(min(risk, equity) / one-contract debit). Skip when one contract costs more than that budget.",
        "exit": "No stop. Calls take profit at +100% of the entry ask. Puts take profit at +50% of the entry ask. Otherwise sell the 15:30 ET bid, which can be near zero. No adds and no rolls.",
        "target_fill": "A target fills at the limit. A 15:30 open already through the target fills at the limit. There is no stop, so an adverse wick is held.",
        "iv": "Prior session VIX1D close, else prior VIX close, divided by 100. 1.3x is a sensitivity.",
        "spread": "Half-spread is the greater of $0.01 and 1.5% of the model mid.",
        "account": "Default is a $1,000 cash account. Sale proceeds settle the next session (T+1). A margin account under $25,000 is reported for the pattern-day-trader count and is not the default, because $1,000 is under the $2,000 margin minimum.",
        "model": "Intraday Black-Scholes. No listed chain. The model is the main uncertainty.",
    }


def has_spy_0dte(day: date) -> bool:
    """True when that weekday's SPY expiration was already listed and the session is open."""
    if not is_trading_day(day):
        return False
    if day.weekday() == 4:
        return day >= FRIDAY_0DTE
    if day.weekday() == 2:
        return day >= WEDNESDAY_0DTE
    if day.weekday() == 0:
        return day >= MONDAY_0DTE
    return False


def session_status(day: date) -> str:
    """Why a calendar day is or is not eligible, before looking at prices."""
    if not is_trading_day(day):
        return "closed"
    if day.weekday() not in (0, 2, 4):
        return "weekday"
    if day.year not in CALENDAR_YEARS:
        return "calendar_uncovered"
    kind = event_kind(day)
    if kind is not None:
        return "event"
    if not has_spy_0dte(day):
        return "no_0dte"
    return "trade"


def years_left(stamp: pd.Timestamp) -> float:
    """Calendar minutes until 16:00 ET, as a year fraction. One minute is the floor."""
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    minutes = (16 * 60) - (clock.hour * 60 + clock.minute)
    minutes = max(1, int(minutes))
    return minutes / (365.0 * 24.0 * 60.0)


def half_spread(mid: float) -> float:
    return max(HALF_SPREAD_FLOOR, HALF_SPREAD_PCT * max(mid, 0.0))


def bid_ask(mid: float) -> tuple[float, float]:
    half = half_spread(mid)
    return max(0.0, mid - half), mid + half


def model_mid(right: str, spot: float, strike: float, when: pd.Timestamp, iv: float) -> float:
    if spot <= 0 or strike <= 0 or iv <= 0:
        return 0.0
    return float(option_price(right, spot, strike, years_left(when), iv, RATE, DIVIDEND))


def contract_count(ask: float, risk: float, equity: float) -> int:
    """Whole contracts whose full debit fits in the risk budget. Zero means skip."""
    budget = min(float(risk), float(equity))
    if ask <= 0 or budget <= 0:
        return 0
    debit = ask * CONTRACT_MULTIPLIER + option_leg_fees(1, ask, sell=False)
    if debit > budget + 1e-9:
        return 0
    return int(budget // debit)


def opening_bounds(day: pd.DataFrame, clock: str) -> Optional[tuple[float, float, pd.Timestamp]]:
    """High and low of the first candle, and the timestamp of its last bar."""
    if day.empty:
        return None
    if clock == "5m":
        if day.index[0].time() != _OPEN:
            return None
        bar = day.iloc[0]
        high = float(bar["high"])
        low = float(bar["low"])
        if not np.isfinite(high) or not np.isfinite(low) or high <= low:
            return None
        return high, low, pd.Timestamp(day.index[0])
    if clock != "1m":
        raise ValueError("clock must be 5m or 1m")
    chosen = [ts for ts in day.index if _OPEN <= ts.time() < _FIVE]
    if len(chosen) < 5 or chosen[0].time() != _OPEN:
        return None
    window = day.loc[chosen[:5]]
    high = float(window["high"].max())
    low = float(window["low"].min())
    if not np.isfinite(high) or not np.isfinite(low) or high <= low:
        return None
    return high, low, pd.Timestamp(window.index[-1])


@dataclass(frozen=True)
class Break:
    day: date
    direction: str
    right: str
    break_time: pd.Timestamp
    or_high: float
    or_low: float
    level: float
    gap: bool


@dataclass
class SessionRead:
    day: date
    status: str
    event: Optional[str]
    orb: Optional[Break]
    or_high: Optional[float] = None
    or_low: Optional[float] = None


def _through(bar: pd.Series, or_high: float, or_low: float) -> Optional[str]:
    up = float(bar["high"]) > or_high
    down = float(bar["low"]) < or_low
    if up and down:
        return "both"
    if up:
        return "long"
    if down:
        return "short"
    return None


def first_break(day_bars: pd.DataFrame, clock: str) -> tuple[Optional[Break], str]:
    """First bar through the first candle, or a reason there is no trade."""
    bounds = opening_bounds(day_bars, clock)
    if bounds is None:
        return None, "no_range"
    or_high, or_low, anchor = bounds
    later = day_bars.loc[day_bars.index > anchor]
    later = later.loc[later.index.time < FLAT]
    for ts, bar in later.iterrows():
        side = _through(bar, or_high, or_low)
        if side is None:
            continue
        if side == "both":
            return None, "both_sides"
        opened = float(bar["open"])
        if side == "long":
            return (
                Break(
                    day_bars.index[0].date(),
                    "long",
                    "call",
                    pd.Timestamp(ts),
                    or_high,
                    or_low,
                    or_high,
                    opened > or_high,
                ),
                "break",
            )
        return (
            Break(
                day_bars.index[0].date(),
                "short",
                "put",
                pd.Timestamp(ts),
                or_high,
                or_low,
                or_low,
                opened < or_low,
            ),
            "break",
        )
    return None, "no_break"


def scan(frame: pd.DataFrame, clock: str) -> list[SessionRead]:
    """One row per regular session in ``frame``."""
    bars = rth(frame)
    if bars.empty:
        return []
    reads: list[SessionRead] = []
    for day, chunk in bars.groupby(bars.index.date):
        session_day = day if isinstance(day, date) else date.fromisoformat(str(day))
        status = session_status(session_day)
        bounds = opening_bounds(chunk, clock)
        high = None if bounds is None else bounds[0]
        low = None if bounds is None else bounds[1]
        found: Optional[Break] = None
        if status == "trade":
            found, why = first_break(chunk, clock)
            status = why if found is None else "break"
        elif status == "event":
            found, _why = first_break(chunk, clock)
        reads.append(
            SessionRead(session_day, status, event_kind(session_day), found, high, low)
        )
    return reads


def _bar_end(stamp: pd.Timestamp, minutes: int) -> pd.Timestamp:
    end = pd.Timestamp(stamp) + pd.Timedelta(minutes=minutes)
    cap = pd.Timestamp(stamp).normalize() + pd.Timedelta(hours=16)
    if end > cap:
        return cap
    return end


def _bid(right: str, spot: float, strike: float, when: pd.Timestamp, iv: float) -> float:
    mid = model_mid(right, spot, strike, when, iv)
    bid, _ask = bid_ask(mid)
    return bid


def target_multiple(right: str) -> float:
    """Call +100% is 2.0 times the ask. Put +50% is 1.5 times the ask."""
    if right == "call":
        return CALL_TARGET
    if right == "put":
        return PUT_TARGET
    raise ValueError("right must be call or put")


def walk_exit(
    session: pd.DataFrame,
    entry_loc: int,
    right: str,
    strike: float,
    iv: float,
    entry_ask: float,
    manage: str,
    bar_minutes: int,
) -> tuple[str, float, pd.Timestamp]:
    """Target, or the 15:30 bid. There is no stop. ``manage`` is level, gap, or next_open."""
    target = entry_ask * target_multiple(right)
    start = entry_loc if manage in ("gap", "next_open") else entry_loc + 1
    index = session.index
    for i in range(start, len(session)):
        stamp = pd.Timestamp(index[i])
        row = session.iloc[i]
        if stamp.time() >= FLAT:
            spot = float(row["open"])
            bid = _bid(right, spot, strike, stamp, iv)
            if bid + 1e-9 >= target:
                return "target", target, stamp
            return "time", bid, stamp
        end = _bar_end(stamp, bar_minutes)
        favor = float(row["high"]) if right == "call" else float(row["low"])
        if _bid(right, favor, strike, end, iv) + 1e-9 >= target:
            return "target", target, end
    last = pd.Timestamp(index[-1])
    return "time", _bid(right, float(session.iloc[-1]["close"]), strike, last, iv), last


def _slipped(raw: float, right: str, costs: CostModel) -> float:
    bump = costs.friction_bps / 10_000.0
    if right == "call":
        return raw * (1.0 + bump)
    return raw * (1.0 - bump)


def _raw_fill(
    orb: Break,
    session: pd.DataFrame,
    fill: str,
) -> Optional[tuple[float, int, str]]:
    loc = session.index.get_loc(orb.break_time)
    if isinstance(loc, slice):
        loc = loc.start
    if isinstance(loc, np.ndarray):
        loc = int(loc[0])
    loc = int(loc)
    if fill == "next_open":
        if loc + 1 >= len(session):
            return None
        nxt = pd.Timestamp(session.index[loc + 1])
        if nxt.time() >= FLAT:
            return None
        return float(session.iloc[loc + 1]["open"]), loc + 1, "next_open"
    if orb.gap:
        return float(session.iloc[loc]["open"]), loc, "gap"
    return orb.level, loc, "level"


def _losing_streak(pnls: list[float]) -> int:
    longest = 0
    run = 0
    for pnl in pnls:
        if pnl < 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return longest


def _iv_value(raw: float, scale: float) -> Optional[float]:
    if raw is None or not np.isfinite(raw) or raw <= 0:
        return None
    scaled = float(raw) / 100.0 * scale
    if not np.isfinite(scaled):
        return None
    return min(VOL_CAP, max(VOL_FLOOR, scaled))


def prior_iv(vix1d: pd.Series, vix: pd.Series) -> dict[date, tuple[float, str]]:
    """Prior-session close, VIX1D when that print exists, otherwise VIX. Points, not decimals."""
    out: dict[date, tuple[float, str]] = {}

    def _shifted(series: pd.Series, name: str) -> None:
        if series is None or len(series) == 0:
            return
        frame = series.astype(float).sort_index()
        index = pd.to_datetime(frame.index)
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert(NY).tz_localize(None)
        frame.index = index.normalize()
        frame = frame[~frame.index.duplicated(keep="last")]
        previous = frame.shift(1)
        for stamp, value in previous.items():
            if not np.isfinite(value):
                continue
            day = pd.Timestamp(stamp).date()
            if day not in out or name == "VIX1D":
                out[day] = (float(value), name)

    _shifted(vix, "VIX")
    _shifted(vix1d, "VIX1D")
    return out


def simulate(
    frame: pd.DataFrame,
    reads: list[SessionRead],
    iv_points: dict[date, tuple[float, str]],
    *,
    risk: float = RISK_PRIMARY,
    account: str = "cash",
    fill: str = FILL_PRIMARY,
    iv_scale: float = IV_PRIMARY,
    starting_equity: float = STARTING_EQUITY,
    costs: CostModel | None = None,
    clock: str = "5m",
    seed: Optional[int] = None,
) -> dict:
    """Cash is the default. ``account='margin'`` applies the legacy day-trade count."""
    if account not in ("cash", "margin"):
        raise ValueError("account must be cash or margin")
    if fill not in ("level", "next_open"):
        raise ValueError("fill must be level or next_open")
    model = costs or CostModel()
    bars = rth(frame)
    by_day: dict[date, pd.DataFrame] = {}
    for key, chunk in bars.groupby(bars.index.date):
        session_day = key if isinstance(key, date) else pd.Timestamp(key).date()
        by_day[session_day] = chunk
    rng = None if seed is None else np.random.default_rng(seed)
    bar_minutes = 1 if clock == "1m" else 5
    settled = float(starting_equity)
    unsettled: list[tuple[date, float]] = []
    equity = float(starting_equity)
    day_trades: list[date] = []
    closed: list[dict] = []
    curve: list[tuple[pd.Timestamp, float, float]] = []
    premium_skipped = 0
    settlement_skipped = 0
    pdt_blocked = 0
    iv_skipped = 0
    no_fill = 0

    for read in reads:
        day = read.day
        if account == "cash":
            still = []
            for available_on, amount in unsettled:
                if available_on <= day:
                    settled += amount
                else:
                    still.append((available_on, amount))
            unsettled = still
            equity = settled + sum(amount for _when, amount in unsettled)
        mark = pd.Timestamp(day.isoformat()).tz_localize(NY) + pd.Timedelta(hours=16)
        if read.status != "break" or read.orb is None:
            curve.append((mark, equity, 0.0))
            continue
        point = iv_points.get(day)
        iv = None if point is None else _iv_value(point[0], iv_scale)
        source = None if point is None else point[1]
        if iv is None:
            iv_skipped += 1
            curve.append((mark, equity, 0.0))
            continue
        session = by_day.get(day)
        if session is None:
            no_fill += 1
            curve.append((mark, equity, 0.0))
            continue
        placed = _raw_fill(read.orb, session, fill)
        if placed is None:
            no_fill += 1
            curve.append((mark, equity, 0.0))
            continue
        raw, loc, manage = placed
        right = read.orb.right
        if rng is not None:
            right = "call" if float(rng.random()) < 0.5 else "put"
        spot = _slipped(raw, right, model)
        strike = listed_strike(spot, spot)
        when = pd.Timestamp(session.index[loc])
        _bid_px, ask = bid_ask(model_mid(right, spot, strike, when, iv))
        if ask <= 0:
            premium_skipped += 1
            curve.append((mark, equity, 0.0))
            continue
        if account == "margin":
            decision = check_day_trade(
                as_of=day,
                equity=equity,
                trade_days=day_trades,
                opening_same_day=True,
                account_type="margin",
                mode="auto",
            )
            if not decision.allowed:
                pdt_blocked += 1
                curve.append((mark, equity, 0.0))
                continue
        count = contract_count(ask, risk, equity)
        if count < 1:
            premium_skipped += 1
            curve.append((mark, equity, 0.0))
            continue
        debit_one = ask * CONTRACT_MULTIPLIER + option_leg_fees(1, ask, sell=False)
        if account == "cash":
            affordable = int(settled // debit_one) if debit_one > 0 else 0
            if affordable < 1:
                settlement_skipped += 1
                curve.append((mark, equity, 0.0))
                continue
            count = min(count, affordable)
        debit = ask * CONTRACT_MULTIPLIER * count + option_leg_fees(count, ask, sell=False)
        reason, exit_px, exit_time = walk_exit(
            session, loc, right, strike, iv, ask, manage, bar_minutes
        )
        credit = exit_px * CONTRACT_MULTIPLIER * count - option_leg_fees(count, exit_px, sell=True)
        pnl = credit - debit
        if account == "cash":
            settled -= debit
            unsettled.append((next_trading_day(day), credit))
            equity = settled + sum(amount for _when, amount in unsettled)
        else:
            equity = equity - debit + credit
            day_trades.append(day)
        closed.append(
            {
                "day": day.isoformat(),
                "right": right,
                "direction": "long" if right == "call" else "short",
                "break_time": str(read.orb.break_time),
                "fill_time": str(when),
                "manage": manage,
                "spot": spot,
                "strike": strike,
                "iv": iv,
                "iv_source": source,
                "ask": ask,
                "contracts": count,
                "debit": debit,
                "exit": exit_px,
                "exit_time": str(exit_time),
                "reason": reason,
                "pnl": pnl,
            }
        )
        curve.append((mark, equity, 1.0))

    pnls = [float(row["pnl"]) for row in closed]
    reasons = {"target": 0, "time": 0}
    for row in closed:
        reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
    calls = [row for row in closed if row["right"] == "call"]
    puts = [row for row in closed if row["right"] == "put"]
    timed = [row for row in closed if row["reason"] == "time"]
    at_1530 = [row for row in timed if str(row["exit_time"])[11:16] == "15:30"]
    count_trades = len(closed)

    def _rate(hits: int, total: int) -> float | None:
        if total == 0:
            return None
        return hits / total
    if curve:
        index = pd.DatetimeIndex([item[0] for item in curve])
        equity_series = pd.Series([item[1] for item in curve], index=index)
        exposure = pd.Series([item[2] for item in curve], index=index)
    else:
        equity_series = pd.Series(dtype=float)
        exposure = pd.Series(dtype=float)
    trades = pd.DataFrame(closed)
    result = BacktestResult(
        equity=equity_series,
        exposure=exposure,
        trades=trades if count_trades else pd.DataFrame(columns=["pnl"]),
        ending_equity=equity,
    )
    metrics = compute_metrics(result, starting_equity)
    wins = sum(1 for pnl in pnls if pnl > 0)
    return {
        "trades": count_trades,
        "win_rate": (wins / count_trades) if count_trades else 0.0,
        "expectancy": float(metrics["expectancy"]),
        "ending": equity,
        "max_drawdown": float(metrics["max_drawdown"]),
        "sharpe": float(metrics["sharpe"]),
        "profit_factor": metrics["profit_factor"],
        "avg_win": float(metrics["avg_win"]),
        "avg_loss": float(metrics["avg_loss"]),
        "losing_streak": _losing_streak(pnls),
        "reasons": reasons,
        "call_trades": len(calls),
        "put_trades": len(puts),
        "pct_call_target": _rate(sum(1 for row in calls if row["reason"] == "target"), len(calls)),
        "pct_put_target": _rate(sum(1 for row in puts if row["reason"] == "target"), len(puts)),
        "pct_time": (len(timed) / count_trades) if count_trades else 0.0,
        "time_count": len(timed),
        "time_at_1530": len(at_1530),
        "time_avg_exit": (sum(float(row["exit"]) for row in at_1530) / len(at_1530)) if at_1530 else None,
        "time_avg_ratio": (
            sum(float(row["exit"]) / float(row["ask"]) for row in at_1530) / len(at_1530)
        ) if at_1530 else None,
        "pdt_blocked": pdt_blocked,
        "premium_skipped": premium_skipped,
        "settlement_skipped": settlement_skipped,
        "iv_skipped": iv_skipped,
        "no_fill": no_fill,
        "starting": starting_equity,
        "risk": risk,
        "account": account,
        "fill": fill,
        "iv_scale": iv_scale,
        "rows": closed,
    }
