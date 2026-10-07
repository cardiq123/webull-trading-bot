"""First-candle opening range. The rule is frozen before any score.

Nothing in this module places an order or imports the sandbox forward test.

The opening range is only the first regular-session candle. On a 5-minute
chart that is the 09:30 bar, which covers 09:30-09:35 ET. On a 1-minute
chart it is the five bars from 09:30 through 09:34. Later bars in the open
do not move the high or the low. A session whose 09:30 bar is missing is
skipped.

The primary entry is the first later bar that closes above that high (long)
or below that low (short). The fill is the next bar's open. One signal per
symbol per session. Two variants are reported and do not replace this entry.
``confirm`` adds a candle in the breakout direction: the close is beyond
the open and beyond the prior close. ``retest`` waits until a later bar
tags the broken level, holds it, does not break the other side, and closes
back outside with that same confirming candle. The first close beyond the
range sets the side. The variant does not flip.

The primary share stop is the other side of the range. The midpoint is a
sensitivity. The primary share target is 1R from the fill, then the session
close if neither the stop nor the target has traded. 2R and a session-close
exit with no R target are sensitivities. A gap through the stop fills at
the open. A target fills at the target, not the wick. The stop is checked
before the target on the same bar.

The primary option is the listed strike nearest the spot, 0 DTE, exited at
+15% and -30% of the entry ask. 1 DTE and 7 DTE are sensitivities. The
five-contract ladder sells 2 at +15%, 1 at +20%, and 1 at +30%, and leaves
a runner at +100%, with the initial stop at -30%. Break-even applies only
to the runner, and only after the +15% tier. The $1,000 book is a margin
account under the legacy pattern-day-trader count: 3 day trades in 5
sessions. The sample is inside the 2026-2027 phase-in, so that count is on.
"""

from __future__ import annotations

from datetime import date, time
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.premium_scale import SCALE_CONTRACTS, _flatten, apply_scale_bar, new_state
from webull_bot.options.fees import CONTRACT_MULTIPLIER
from webull_bot.chart_reads.pullback import (
    PRIMARY_STOP,
    PRIMARY_TARGET,
    PremiumPath,
    after_cost_breakeven,
    lot_debit,
    theoretical_breakeven,
)
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.mtf_vwap.detect import rth
from webull_bot.risk.pdt import check_day_trade

ENTRY_PRIMARY = "close"
ENTRY_VARIANTS = ("close", "retest", "confirm")
STOP_PRIMARY = "opposite"
STOPS = ("opposite", "mid")
SHARE_R_PRIMARY = 1.0
SHARE_TARGETS = (1.0, 2.0, None)
DTE_PRIMARY = 0
DTE_LIST = (0, 1, 7)
CASH_ACCOUNT = 1_000.0
SEED = 17
LADDER_STOP = -0.30
NY = "America/New_York"
_OPEN = time(9, 30)
_FIVE = time(9, 35)


def frozen_rules() -> dict:
    """Written down before the holdout is scored. The score does not edit this."""
    return {
        "range": "09:30-09:35 ET only. 5-minute: the 09:30 bar. 1-minute: 09:30 through 09:34.",
        "entry": ENTRY_PRIMARY,
        "variants": list(ENTRY_VARIANTS),
        "stop": STOP_PRIMARY,
        "stops": list(STOPS),
        "share_r": SHARE_R_PRIMARY,
        "share_targets": ["1R", "2R", "session close"],
        "dte": DTE_PRIMARY,
        "dte_list": list(DTE_LIST),
        "premium_target": PRIMARY_TARGET,
        "premium_stop": PRIMARY_STOP,
        "breakeven_before_costs": theoretical_breakeven(PRIMARY_TARGET, PRIMARY_STOP),
        "ladder": "5 contracts, 2 at +15%, 1 at +20%, 1 at +30%, runner at +100%, initial stop -30%",
        "cash_account": CASH_ACCOUNT,
        "seed": SEED,
        "pdt": "legacy 3 day trades in 5 sessions on a margin account under $25,000",
    }


def range_stop(setup: Setup, kind: str) -> float:
    """Opposite side of the first candle, or the midpoint. Kind is frozen."""
    high = float(setup.reference)
    low = float(setup.reversal)
    if kind == "mid":
        return (high + low) / 2.0
    if kind != "opposite":
        raise ValueError("stop must be opposite or mid")
    if setup.direction == "long":
        return low
    return high


def opening_bounds(day: pd.DataFrame, clock: str) -> Optional[tuple[float, float, pd.Timestamp]]:
    """High and low of the first candle, and the timestamp of its last bar.

    Returns None when the 09:30 bar is missing or the 1-minute window is short.
    """
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


def _side(close: float, high: float, low: float) -> Optional[str]:
    if close > high:
        return "long"
    if close < low:
        return "short"
    return None


def _confirms(direction: str, open_: float, close: float, prev_close: float) -> bool:
    if direction == "long":
        return close > open_ and close > prev_close
    return close < open_ and close < prev_close


def _setup(
    symbol: str,
    variant: str,
    direction: str,
    or_high: float,
    or_low: float,
    anchor: pd.Timestamp,
    signal: pd.Timestamp,
    fill: pd.Timestamp,
) -> Setup:
    stop = or_low if direction == "long" else or_high
    return Setup(
        symbol=symbol,
        direction=direction,
        kind=f"orb5_{variant}",
        signal_time=signal,
        fill_time=fill,
        anchor_time=anchor,
        stop=float(stop),
        atr=float(or_high - or_low),
        reference=float(or_high),
        reversal=float(or_low),
    )


def find_orb(frame: pd.DataFrame, symbol: str, clock: str, variant: str = ENTRY_PRIMARY) -> list[Setup]:
    """Causal signals. Bar t uses only the first candle and bars through t."""
    if variant not in ENTRY_VARIANTS:
        raise ValueError("variant must be close, retest, or confirm")
    bars = rth(frame)
    if bars.empty:
        return []
    found: list[Setup] = []
    days = pd.Series([ts.date() for ts in bars.index], index=bars.index)
    for _, day in bars.groupby(days, sort=True):
        bounds = opening_bounds(day, clock)
        if bounds is None:
            continue
        or_high, or_low, anchor = bounds
        after = day.loc[day.index > anchor]
        if after.empty:
            continue
        prior_close = float(day.loc[anchor, "close"]) if clock == "5m" else float(day.loc[:anchor, "close"].iloc[-1])
        broke: Optional[str] = None
        for ts, bar in after.iterrows():
            try:
                open_ = float(bar["open"])
                high = float(bar["high"])
                low = float(bar["low"])
                close = float(bar["close"])
            except (TypeError, ValueError, KeyError):
                prior_close = np.nan
                continue
            if not all(np.isfinite(value) for value in (open_, high, low, close)):
                prior_close = close
                continue
            side = _side(close, or_high, or_low)
            take = False
            direction = side
            if variant == "close":
                take = side is not None
            elif variant == "confirm":
                take = side is not None and _confirms(side, open_, close, prior_close)
            else:
                if broke is None:
                    if side is not None:
                        broke = side
                    prior_close = close
                    continue
                direction = broke
                if broke == "long":
                    take = low <= or_high and low >= or_low and close > or_high and close > open_
                else:
                    take = high >= or_low and high <= or_high and close < or_low and close < open_
            prior_close = close
            if not take or direction is None:
                continue
            loc = day.index.get_loc(ts)
            if isinstance(loc, slice):
                loc = loc.start
            if isinstance(loc, np.ndarray):
                loc = int(loc[0])
            nxt = int(loc) + 1
            if nxt >= len(day.index):
                break
            if day.index[nxt].date() != ts.date():
                break
            found.append(
                _setup(symbol, variant, direction, or_high, or_low, anchor, pd.Timestamp(ts), pd.Timestamp(day.index[nxt]))
            )
            break
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol))
    return found


def _day(stamp) -> date:
    ts = pd.Timestamp(stamp)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(NY)
    return ts.date()


def _pack(metrics, before, trades, skipped, blocked, overlapped, reasons, starting) -> dict:
    after = after_cost_breakeven(float(metrics.get("avg_win") or 0.0), float(metrics.get("avg_loss") or 0.0))
    trades_n = int(metrics.get("trades") or 0)
    win_rate = float(metrics.get("win_rate") or 0.0)
    clears = bool(trades_n > 0 and after is not None and win_rate > after)
    ending = float(metrics.get("ending_equity") or starting)
    expectancy = float(metrics.get("expectancy") or 0.0)
    return {
        "metrics": metrics,
        "breakeven_before": before,
        "breakeven_after": after,
        "clears_breakeven": clears,
        "profitable": bool(trades_n > 0 and expectancy > 0.0 and ending > float(starting)),
        "skipped": int(skipped),
        "pdt_blocked": int(blocked),
        "overlapped": int(overlapped),
        "reasons": reasons,
        "trades": trades,
        "starting_equity": float(starting),
    }


def _empty(starting: float, before: Optional[float]) -> dict:
    metrics = compute_metrics(
        BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
        starting,
    )
    return _pack(metrics, before, [], 0, 0, 0, {}, starting)


def _pdt_block(cash: float, day_trades: list[date], day: date) -> bool:
    decision = check_day_trade(
        as_of=day,
        equity=cash,
        trade_days=day_trades,
        opening_same_day=True,
        account_type="margin",
        mode="auto",
    )
    return not decision.allowed


def _session_window(frame: pd.DataFrame, fill: pd.Timestamp) -> pd.DataFrame:
    start = frame.index.get_loc(fill)
    if isinstance(start, slice):
        start = start.start
    if isinstance(start, np.ndarray):
        start = int(start[0])
    start = int(start)
    day = _day(frame.index[start])
    end = start
    while end + 1 < len(frame.index) and _day(frame.index[end + 1]) == day:
        end += 1
    return frame.iloc[start : end + 1]


def simulate_shares(
    setups: list[Setup],
    frames: dict[str, pd.DataFrame],
    *,
    target_r: Optional[float],
    starting_equity: float,
    pdt: bool,
    costs: CostModel | None = None,
) -> dict:
    """One position. Stop at ``setup.stop``. Target at ``target_r``, or the session close."""
    model = costs or CostModel()
    before = theoretical_breakeven(float(target_r), -1.0) if target_r is not None else None
    if starting_equity <= 0.0:
        return _empty(starting_equity, before)
    ordered = sorted(setups, key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    cash = float(starting_equity)
    busy: Optional[pd.Timestamp] = None
    day_trades: list[date] = []
    trades: list[dict] = []
    skipped = 0
    blocked = 0
    overlapped = 0
    reasons: dict[str, int] = {}
    curve_stamps: list[pd.Timestamp] = []
    curve_eq: list[float] = []
    for setup in ordered:
        fill = pd.Timestamp(setup.fill_time)
        if busy is not None and fill <= busy:
            overlapped += 1
            continue
        frame = frames.get(setup.symbol)
        if frame is None or fill not in frame.index:
            skipped += 1
            continue
        window = _session_window(frame, fill)
        if window.empty:
            skipped += 1
            continue
        raw_open = float(window.iloc[0]["open"])
        stop = float(setup.stop)
        if not np.isfinite(raw_open) or raw_open <= 0.0 or not np.isfinite(stop) or stop <= 0.0:
            skipped += 1
            continue
        fill_date = _day(fill)
        if pdt and _pdt_block(cash, day_trades, fill_date):
            blocked += 1
            continue
        long = setup.direction == "long"
        gap = (long and raw_open <= stop) or ((not long) and raw_open >= stop)
        risk = abs(raw_open - stop)
        if long:
            entry_px = buy_price(raw_open, model)
            target = None if target_r is None or gap else raw_open + float(target_r) * risk
            risk_per = max(entry_px - sell_price(min(stop, raw_open), model), raw_open * 0.002)
        else:
            entry_px = sell_price(raw_open, model)
            target = None if target_r is None or gap else raw_open - float(target_r) * risk
            risk_per = max(buy_price(max(stop, raw_open), model) - entry_px, raw_open * 0.002)
        quantity = (cash * 0.02) / risk_per
        if entry_px * quantity > cash:
            quantity = cash / entry_px
        if quantity < 0.01 or entry_px * quantity > cash + 1e-6:
            skipped += 1
            continue
        exit_raw = raw_open if gap else None
        reason = "stop" if gap else "eod"
        exit_time = pd.Timestamp(window.index[0])
        if not gap:
            for ts, bar in window.iterrows():
                opened = float(bar["open"])
                high_px = float(bar["high"])
                low_px = float(bar["low"])
                closed = float(bar["close"])
                last = ts == window.index[-1]
                if long:
                    if opened <= stop:
                        exit_raw, reason, exit_time = opened, "stop", pd.Timestamp(ts)
                        break
                    if low_px <= stop:
                        exit_raw, reason, exit_time = stop, "stop", pd.Timestamp(ts)
                        break
                    if target is not None and high_px >= target:
                        exit_raw, reason, exit_time = target, "target", pd.Timestamp(ts)
                        break
                else:
                    if opened >= stop:
                        exit_raw, reason, exit_time = opened, "stop", pd.Timestamp(ts)
                        break
                    if high_px >= stop:
                        exit_raw, reason, exit_time = stop, "stop", pd.Timestamp(ts)
                        break
                    if target is not None and low_px <= target:
                        exit_raw, reason, exit_time = target, "target", pd.Timestamp(ts)
                        break
                if last:
                    exit_raw, reason, exit_time = closed, "eod", pd.Timestamp(ts)
                    break
        if exit_raw is None:
            skipped += 1
            continue
        if long:
            debit = quantity * entry_px + buy_fees(model)
            sold = sell_price(float(exit_raw), model)
            credit = quantity * sold - sell_regulatory_fees(sold, quantity, model)
            pnl = credit - debit
        else:
            credit_open = quantity * entry_px - sell_regulatory_fees(entry_px, quantity, model)
            cover = quantity * buy_price(float(exit_raw), model) + buy_fees(model)
            pnl = credit_open - cover
        cash += pnl
        curve_stamps.append(exit_time)
        curve_eq.append(cash)
        busy = exit_time
        if _day(exit_time) == fill_date:
            day_trades.append(fill_date)
        reasons[reason] = reasons.get(reason, 0) + 1
        trades.append(
            {
                "symbol": setup.symbol,
                "direction": setup.direction,
                "pnl": pnl,
                "reason": reason,
                "exit": float(exit_raw),
                "fill": fill_date.isoformat(),
            }
        )
    equity = pd.Series(curve_eq, index=pd.DatetimeIndex(curve_stamps)) if curve_eq else pd.Series(dtype=float)
    exposure = pd.Series(np.ones(len(equity)), index=equity.index) if len(equity) else pd.Series(dtype=float)
    metrics = compute_metrics(
        BacktestResult(equity, exposure, pd.DataFrame(trades)),
        float(starting_equity),
    )
    return _pack(metrics, before, trades, skipped, blocked, overlapped, reasons, float(starting_equity))


def simulate_ladder(
    paths: list[PremiumPath],
    *,
    starting_equity: float,
    mode: str,
    pdt: bool,
) -> dict:
    """Five contracts. The published ladder, with the initial stop at -30%."""
    if mode not in {"cash", "sized"}:
        raise ValueError("mode must be cash or sized")
    if starting_equity <= 0.0:
        return _empty(starting_equity, None)
    ordered = sorted(paths, key=lambda path: (path.fill, path.symbol, path.direction))
    cash = float(starting_equity)
    busy: Optional[pd.Timestamp] = None
    day_trades: list[date] = []
    trades: list[dict] = []
    skipped = 0
    blocked = 0
    overlapped = 0
    reasons: dict[str, int] = {}
    curve_stamps: list[pd.Timestamp] = []
    curve_eq: list[float] = []
    for path in ordered:
        if busy is not None and path.fill <= busy:
            overlapped += 1
            continue
        if not path.ok or path.adverse_bid is None or path.ask <= 0.0:
            skipped += 1
            continue
        debit = lot_debit(path.ask, SCALE_CONTRACTS)
        cap = min(cash, CASH_ACCOUNT) if mode == "cash" else cash
        if debit > cap + 1e-9:
            skipped += 1
            continue
        if pdt and _pdt_block(cash, day_trades, path.fill_date):
            blocked += 1
            continue
        state = new_state(float(path.ask), "scale", "premium", LADDER_STOP)
        cash -= debit
        stamps = path.stamps or [path.fill]
        reason = None
        exit_time = path.fill
        for index in range(len(path.adverse_bid)):
            exit_time = pd.Timestamp(stamps[min(index, len(stamps) - 1)])
            terminal = "expiry" if path.expired is not None and bool(path.expired[index]) else None
            quotes = {
                "open_bid": float(path.open_bid[index]),
                "adverse_bid": float(path.adverse_bid[index]),
                "favorable_bid": float(path.favorable_bid[index]),
                "close_bid": float(path.close_bid[index]),
            }
            reason = apply_scale_bar(state, quotes, entry_bar=index == 0, terminal=terminal)
            marked = state["credit"] + state["remaining"] * quotes["close_bid"] * CONTRACT_MULTIPLIER
            curve_stamps.append(exit_time)
            curve_eq.append(cash + (state["credit"] if reason else marked))
            if reason:
                break
        if not state["done"]:
            last = len(path.adverse_bid) - 1
            _flatten(state, float(path.close_bid[last]), "window")
            reason = "window"
            exit_time = pd.Timestamp(stamps[min(last, len(stamps) - 1)])
            curve_stamps.append(exit_time)
            curve_eq.append(cash + state["credit"])
        cash += state["credit"]
        busy = exit_time
        pnl = state["credit"] - debit
        if _day(exit_time) == path.fill_date:
            day_trades.append(path.fill_date)
        reasons[reason or "window"] = reasons.get(reason or "window", 0) + 1
        trades.append(
            {
                "symbol": path.symbol,
                "direction": path.direction,
                "pnl": pnl,
                "reason": reason,
                "delta": abs(float(path.delta)),
                "fill": path.fill_date.isoformat(),
            }
        )
    equity = pd.Series(curve_eq, index=pd.DatetimeIndex(curve_stamps)) if curve_eq else pd.Series(dtype=float)
    if len(equity):
        equity = equity[~equity.index.duplicated(keep="last")]
    exposure = pd.Series(np.ones(len(equity)), index=equity.index) if len(equity) else pd.Series(dtype=float)
    metrics = compute_metrics(
        BacktestResult(equity, exposure, pd.DataFrame(trades)),
        float(starting_equity),
    )
    packed = _pack(metrics, None, trades, skipped, blocked, overlapped, reasons, float(starting_equity))
    deltas = [float(row["delta"]) for row in trades if np.isfinite(row.get("delta", np.nan))]
    packed["median_delta"] = float(np.median(deltas)) if deltas else float("nan")
    return packed
