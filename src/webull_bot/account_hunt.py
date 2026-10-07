"""A second search for a small-account book. Rules were written down first.

The earlier 10-month sleeve, the fully invested dual-momentum book, and the
monthly TQQQ filter are not re-tuned here. Connors RSI(2) and sector
rotation were already scored inside the risk-sized engine. The variants
below drop that sizer and that trail. They are a different test.

Cash earns zero. A cash account sells on the next open and buys the
session after that. Nothing in this file is added to the strategy list.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from webull_bot.account_winners import HOLDOUT_START, SAMPLE_END, SAMPLE_START
from webull_bot.calendar import nyse_holidays
from webull_bot.indicators import rsi, sma
from webull_bot.options.fees import option_leg_fees
from webull_bot.options.pricing import (
    listed_strike,
    option_price,
    realized_vol,
    strike_for_put_delta,
)
from webull_bot.universe_dow import is_member, members_on

MEAN_REVERSION_SYMBOLS = (
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLY",
    "XLP",
    "XLI",
    "XLB",
    "XLU",
)
SECTOR_SYMBOLS = ("XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU")
RSI_ENTRY = 10.0
IBS_ENTRY = 0.2
IBS_EXIT = 0.8
SMA_TREND = 200
SMA_EXIT = 5
DOWN_DAYS = 3
BAND = 0.03
VOL_TARGET = 0.15
LEV_VOL_TARGET = 0.20
MOM_LOOKBACK = 12
MOM_SKIP = 1
MOM_TOP = 5
SECTOR_TOP = 3
PUT_DELTA = 0.30
OPTION_DTE = 30
IV_PREMIUM = 1.15
RATE = 0.02
# OTM half-spread used by the option overlay. A 0.30-delta strike is below 0.50.
OTM_HALF_SPREAD = 0.08
RANDOM_SEED = 17
CONSERVATIVE_DRAWDOWN = -0.15
MODERATE_DRAWDOWN = -0.35


def frozen_rules() -> dict[str, Any]:
    """No measured return belongs in this dict."""
    return {
        "sample_start": str(SAMPLE_START.date()),
        "holdout_start": str(HOLDOUT_START.date()),
        "sample_end": str(SAMPLE_END.date()),
        "costs": "Webull stock schedule. Option books add the option ORF, OCC, CAT, and the sell-side TAF and SEC fee. Option bids are 8 percent under the Black-Scholes mid.",
        "cash": "Earns zero. Cash account: sell the next session, buy the session after that.",
        "already_scored": (
            "The risk-sized Connors RSI(2) book and the risk-sized sector rotation stay as published. "
            "The 10-month sleeve, fully invested dual momentum, and the monthly TQQQ filter stay as published. "
            "This file does not replace those numbers."
        ),
        "mean_reversion": (
            "Liquid ETFs: SPY, QQQ, IWM, DIA, and the nine original sector SPDRs. "
            "RSI(2) below 10 and the close strictly above the 200-day average, exit when the close is above the 5-day average. "
            "IBS below 0.2 with the same 200-day filter, exit when IBS is above 0.8. "
            "Three lower closes in a row with the same 200-day filter, exit when the close is above the 5-day average. "
            "Each book equal-weights the names that are on, otherwise cash. "
            "The QQQ overlay holds those RSI(2) names when any are on, and otherwise holds QQQ."
        ),
        "levered_trend": (
            "TQQQ is on when QQQ's close is strictly above its 200-day average, else cash. "
            "The 3 percent band enters only above the average times 1.03 and exits only below the average times 0.97. "
            "UPRO uses SPY the same way, with no band. "
            "Volatility targeting multiplies the on/off weight by min(1, 0.20 / 20-day realized vol). "
            "The half book is 50 percent TQQQ when the plain filter is on. "
            "The blend is 50 percent QQQ and 50 percent TQQQ when that filter is on, else cash."
        ),
        "vol_target": (
            "Weekly book. Weight is min(1, 0.15 / 20-day realized vol), never above 1. "
            "The 200-day variant is that weight only while the close is strictly above the average. "
            "SPY and QQQ are separate books. A daily rebalance is a neighbor, not the pick."
        ),
        "stock_momentum": (
            "Top 5 of the point-in-time Dow by 12-1 month return, equal weight, monthly. "
            "A name is eligible only on dates it was in the Dow. "
            "The book is cash unless SPY's close is strictly above its 200-day average. "
            "This is not the S&P 100. A current-member book is a survivor diagnostic and cannot be a finalist. "
            "Top 10 is a neighbor."
        ),
        "sector_rotation": (
            "Nine sector SPDRs. Each month the three with the best 12-month return are candidates. "
            "A candidate is held at one third only when its own 12-month return is strictly positive, else that slice is cash. "
            "Top 2 and the 3-month and 6-month lookbacks are neighbors."
        ),
        "calendar": (
            "Long the last trading session of the month and the first three trading sessions. "
            "Pre-holiday is the session before an NYSE weekday holiday. "
            "The combined book is long when either window is on. "
            "The add-on keeps half in the ETF all the time and adds the other half only in the combined window. "
            "SPY and QQQ are both scored. The signal is the next session's calendar, not a future price."
        ),
        "earnings": (
            "Post-earnings drift is scored only when a free point-in-time earnings calendar covers the training years. "
            "A short or survivor-only calendar is a skip, not a book."
        ),
        "income": (
            "Wheel on F, one contract, 30 days, about 0.30 delta. Cash-secured put while flat. "
            "If assigned, hold the shares and sell a 0.30-delta covered call until called away. "
            "Black-Scholes on adjusted prices, IV is 20-day realized vol times 1.15, no early assignment, no second dividend. "
            "A separate covered-call book buys 100 shares when they fit. "
            "QQQM and SPLG are fit checks. A name that cannot place 100 shares inside $5,000 is not a book."
        ),
        "tiers": (
            "Conservative: among eligible books that beat SPY on the frozen risk-adjusted test and whose "
            "holdout max drawdown is milder than 15 percent, the highest holdout Calmar. "
            "Moderate: the same SPY test, drawdown milder than 35 percent, not the conservative name, highest Calmar. "
            "High risk: among eligible books with a positive training CAGR that beat SPY on raw holdout CAGR, "
            "excluding the two names above, the highest holdout Calmar. "
            "QQQ buy-and-hold is reported on the same dates. Beating QQQ on raw return is stated and is not a separate gate. "
            "Neighbors, survivor lists, and the daily vol rebalance cannot take a tier."
        ),
    }


def change_rows(weights: pd.DataFrame) -> pd.DataFrame:
    """Keep the first row and every later row whose weights actually change."""
    if weights.empty:
        return weights
    values = weights.to_numpy(dtype=float)
    keep = [0]
    prev = values[0]
    for i in range(1, len(values)):
        if np.any(np.abs(values[i] - prev) > 1e-8):
            keep.append(i)
            prev = values[i]
    return weights.iloc[keep]


def _positions(entry: np.ndarray, exit_: np.ndarray) -> np.ndarray:
    """Held at the close. An entry cannot also exit on the same close."""
    held = np.zeros(entry.shape, dtype=bool)
    state = np.zeros(entry.shape[1], dtype=bool)
    for i in range(len(entry)):
        was = state.copy()
        state = was & ~exit_[i]
        state = state | (~was & entry[i])
        held[i] = state
    return held


def _equal(held: pd.DataFrame) -> pd.DataFrame:
    count = held.sum(axis=1).astype(float)
    weights = held.astype(float).div(count.replace(0.0, np.nan), axis=0).fillna(0.0)
    return weights


def _panel(frames: dict[str, pd.DataFrame], symbols: tuple[str, ...] | list[str], column: str) -> pd.DataFrame:
    series = []
    for symbol in symbols:
        frame = frames[symbol]
        series.append(frame[column].astype(float).rename(symbol))
    panel = pd.concat(series, axis=1).sort_index()
    panel = panel[~panel.index.duplicated(keep="last")]
    return panel


def mean_reversion_weights(
    frames: dict[str, pd.DataFrame],
    kind: str,
    *,
    symbols: tuple[str, ...] = MEAN_REVERSION_SYMBOLS,
    rsi_entry: float = RSI_ENTRY,
) -> pd.DataFrame:
    """Equal weight of the names whose rule is on at the close. Else cash."""
    close = _panel(frames, symbols, "close")
    high = _panel(frames, symbols, "high")
    low = _panel(frames, symbols, "low")
    trend = close > sma(close, SMA_TREND)
    if kind == "rsi2":
        entry = (rsi(close, 2) < rsi_entry) & trend
        exit_ = close > sma(close, SMA_EXIT)
    elif kind == "ibs":
        span = high - low
        ibs = (close - low) / span.where(span > 0)
        ibs = ibs.fillna(0.5)
        entry = (ibs < IBS_ENTRY) & trend
        exit_ = ibs > IBS_EXIT
    elif kind == "three_down":
        down = close < close.shift(1)
        entry = down & down.shift(1).fillna(False) & down.shift(2).fillna(False) & trend
        exit_ = close > sma(close, SMA_EXIT)
    else:
        raise ValueError(f"unknown mean-reversion kind {kind}")
    entry_np = entry.fillna(False).to_numpy(dtype=bool)
    exit_np = exit_.fillna(False).to_numpy(dtype=bool)
    held = pd.DataFrame(_positions(entry_np, exit_np), index=close.index, columns=close.columns)
    return _equal(held)


def qqq_overlay_weights(
    frames: dict[str, pd.DataFrame],
    rsi_entry: float = RSI_ENTRY,
    symbols: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """RSI(2) sleeve when any name is on. Otherwise the whole account is QQQ."""
    names = symbols if symbols is not None else tuple(symbol for symbol in MEAN_REVERSION_SYMBOLS if symbol in frames)
    sleeve = mean_reversion_weights(frames, "rsi2", symbols=names, rsi_entry=rsi_entry)
    weights = sleeve.copy()
    idle = sleeve.sum(axis=1) <= 1e-9
    if "QQQ" not in weights.columns:
        weights["QQQ"] = 0.0
    weights.loc[idle, :] = 0.0
    weights.loc[idle, "QQQ"] = 1.0
    return weights


def hysteresis(close: pd.Series, average: pd.Series, band: float) -> pd.Series:
    """On/off at the close. Equality keeps the prior state. A missing average is off."""
    state = False
    out = np.zeros(len(close), dtype=bool)
    closes = close.to_numpy(dtype=float)
    averages = average.to_numpy(dtype=float)
    upper = 1.0 + band
    lower = 1.0 - band
    for i, (price, level) in enumerate(zip(closes, averages)):
        if not np.isfinite(price) or not np.isfinite(level):
            state = False
        elif not state and price > level * upper:
            state = True
        elif state and price < level * lower:
            state = False
        out[i] = state
    return pd.Series(out, index=close.index)


def trend_weight(
    traded_close: pd.Series,
    signal_close: pd.Series,
    *,
    band: float,
    name: str,
) -> pd.DataFrame:
    """All-or-cash. ``name`` is the fund that is bought. The signal can be another fund."""
    average = sma(signal_close.astype(float), SMA_TREND)
    on = hysteresis(signal_close.astype(float), average, band)
    # No traded price that day means the weight cannot turn on.
    tradable = traded_close.reindex(on.index).notna()
    return (on & tradable).astype(float).rename(name).to_frame()


def scaled_weight(on: pd.Series, vol: pd.Series, target: float, name: str) -> pd.DataFrame:
    """min(1, target / vol) while ``on`` is true. Never levered above 1."""
    rv = vol.reindex(on.index).astype(float)
    raw = target / rv.where(rv > 0)
    capped = raw.clip(upper=1.0).fillna(0.0)
    weight = capped.where(on.astype(bool), 0.0)
    return weight.rename(name).to_frame()


def weekly_rows(weights: pd.DataFrame) -> pd.DataFrame:
    """Last session of each ISO week. The weight then stays until the next week."""
    if weights.empty:
        return weights
    stamps = pd.DatetimeIndex(weights.index)
    keys = pd.Series(list(zip(stamps.isocalendar().year, stamps.isocalendar().week)), index=weights.index)
    last = keys.groupby(keys).tail(1).index
    return weights.loc[last]


def month_end_index(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    from webull_bot.account_winners import month_end_dates

    return month_end_dates(pd.DatetimeIndex(index))


def sector_weights(
    monthly: pd.DataFrame,
    *,
    lookback: int = MOM_LOOKBACK,
    top_n: int = SECTOR_TOP,
) -> pd.DataFrame:
    """One-third slices. A losing 12-month return leaves that slice in cash."""
    momentum = monthly / monthly.shift(lookback) - 1.0
    weights = pd.DataFrame(0.0, index=monthly.index, columns=monthly.columns)
    slot = 1.0 / float(top_n)
    for ts in monthly.index:
        ranked: list[tuple[float, str]] = []
        for symbol in monthly.columns:
            value = momentum.at[ts, symbol]
            if pd.isna(value):
                continue
            ranked.append((float(value), str(symbol)))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        for _, symbol in ranked[:top_n]:
            if float(momentum.at[ts, symbol]) > 0:
                weights.at[ts, symbol] = slot
    return weights


def stock_momentum_weights(
    monthly: pd.DataFrame,
    spy_above: pd.Series,
    *,
    point_in_time: bool,
    top_n: int = MOM_TOP,
    lookback: int = MOM_LOOKBACK,
    skip: int = MOM_SKIP,
    survivor_asof: date | None = None,
) -> pd.DataFrame:
    """Top N by 12-1. Cash when SPY is not above its 200-day average.

    Point-in-time membership uses the Dow on the signal date. The survivor
    diagnostic keeps only the names that were members on ``survivor_asof``
    and lets them compete before they joined.
    """
    relative = monthly.shift(skip) / monthly.shift(lookback) - 1.0
    survivors = set(members_on(survivor_asof)) if survivor_asof is not None else set()
    weights = pd.DataFrame(0.0, index=monthly.index, columns=monthly.columns)
    gate = spy_above.reindex(monthly.index).fillna(False)
    for ts in monthly.index:
        if not bool(gate.loc[ts]):
            continue
        day = pd.Timestamp(ts).date()
        ranked: list[tuple[float, str]] = []
        for symbol in monthly.columns:
            if point_in_time and not is_member(symbol, day):
                continue
            if not point_in_time and symbol not in survivors:
                continue
            value = relative.at[ts, symbol]
            if pd.isna(value):
                continue
            ranked.append((float(value), str(symbol)))
        if len(ranked) < top_n:
            continue
        ranked.sort(key=lambda item: (-item[0], item[1]))
        slot = 1.0 / float(top_n)
        for _, symbol in ranked[:top_n]:
            weights.at[ts, symbol] = slot
    return weights


def _weekday_holiday_between(start: date, stop: date) -> bool:
    cursor = start + timedelta(days=1)
    while cursor < stop:
        if cursor.weekday() < 5 and cursor in nyse_holidays(cursor.year):
            return True
        cursor += timedelta(days=1)
    return False


def session_flags(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Calendar flags for this session. The next row is the next session, not a price."""
    dates = [pd.Timestamp(ts).date() for ts in index]
    tom = np.zeros(len(dates), dtype=bool)
    # Group positions by calendar month, in session order.
    buckets: dict[tuple[int, int], list[int]] = {}
    for i, day in enumerate(dates):
        buckets.setdefault((day.year, day.month), []).append(i)
    for positions in buckets.values():
        for pos in positions[:3]:
            tom[pos] = True
        tom[positions[-1]] = True
    pre = np.zeros(len(dates), dtype=bool)
    for i, day in enumerate(dates[:-1]):
        if _weekday_holiday_between(day, dates[i + 1]):
            pre[i] = True
    return pd.DataFrame({"tom": tom, "pre_holiday": pre}, index=index)


def calendar_weights(index: pd.DatetimeIndex, symbol: str, kind: str) -> pd.DataFrame:
    """Weight known at the close, for the next session's calendar window."""
    flags = session_flags(index)
    if kind == "tom":
        window = flags["tom"]
    elif kind == "pre_holiday":
        window = flags["pre_holiday"]
    elif kind == "both":
        window = flags["tom"] | flags["pre_holiday"]
    else:
        raise ValueError(kind)
    # The buy has to be placed before the window session. shift(-1) reads the
    # next session's calendar flag, which is known without that session's price.
    nxt = window.shift(-1)
    nxt = nxt.where(nxt.notna(), False).astype(bool)
    if kind == "blend":
        raise ValueError("blend is not a window kind")
    return nxt.astype(float).rename(symbol).to_frame()


def calendar_blend_weights(index: pd.DatetimeIndex, symbol: str) -> pd.DataFrame:
    """Half always invested. The other half only in the combined window."""
    both = calendar_weights(index, symbol, "both")[symbol]
    return (0.5 + 0.5 * both).rename(symbol).to_frame()


def _bs_strike(spot: float, sigma: float, years: float, right: str) -> float:
    if right == "put":
        raw = strike_for_put_delta(spot, years, sigma, PUT_DELTA, RATE, 0.0)
    else:
        # A 0.30-delta call is the same distance method as a 0.30-delta put, mirrored.
        from webull_bot.options.pricing import strike_for_delta

        raw = strike_for_delta(spot, years, sigma, PUT_DELTA, RATE, 0.0)
    return listed_strike(spot, raw)


def simulate_wheel(
    frame: pd.DataFrame,
    *,
    starting_equity: float,
    trade_start: pd.Timestamp,
    trade_end: pd.Timestamp,
) -> dict[str, Any]:
    """One-contract wheel. Marks the short option. This is a model, not a chain.

    Adjusted prices already contain dividends, so the yield in the formula is
    zero. Early assignment is ignored. A contract is opened only when the
    cash covers the strike times 100 before the credit.
    """
    start = pd.Timestamp(trade_start)
    end = pd.Timestamp(trade_end)
    data = frame.loc[(frame.index >= start) & (frame.index <= end)].dropna(subset=["close"])
    if data.empty:
        return _empty_option(starting_equity)
    close = data["close"].astype(float)
    rv = realized_vol(close, 20)
    cash = float(starting_equity)
    shares = 0
    option: dict[str, Any] | None = None
    equity_idx: list[pd.Timestamp] = []
    equity_val: list[float] = []
    opens = 0
    assignments = 0
    called = 0
    skips = 0
    month_key: tuple[int, int] | None = None

    def liability(spot: float, ts: pd.Timestamp) -> float:
        if option is None:
            return 0.0
        remaining = max((option["expiry"] - ts).days, 0) / 365.0
        mid = option_price(option["right"], spot, option["strike"], remaining, option["sigma"], RATE, 0.0)
        ask = mid * (1.0 + OTM_HALF_SPREAD)
        return ask * 100.0

    for ts, spot in close.items():
        stamp = pd.Timestamp(ts)
        price = float(spot)
        if option is not None and stamp >= option["expiry"]:
            if option["right"] == "put" and price < option["strike"]:
                cash -= option["strike"] * 100.0
                shares = 100
                assignments += 1
            elif option["right"] == "call" and price > option["strike"]:
                cash += option["strike"] * 100.0
                shares = 0
                called += 1
            option = None
        key = (stamp.year, stamp.month)
        if option is None and key != month_key:
            month_key = key
            sigma = float(rv.asof(stamp)) if not rv.dropna().empty else float("nan")
            if np.isfinite(sigma):
                sigma = float(np.clip(sigma * IV_PREMIUM, 0.10, 1.50))
                years = OPTION_DTE / 365.0
                right = "call" if shares >= 100 else "put"
                if right == "put":
                    strike = _bs_strike(price, sigma, years, "put")
                    if cash >= strike * 100.0:
                        mid = option_price("put", price, strike, years, sigma, RATE, 0.0)
                        credit = mid * (1.0 - OTM_HALF_SPREAD) * 100.0
                        fee = option_leg_fees(1, mid * (1.0 - OTM_HALF_SPREAD), sell=True)
                        if credit > fee:
                            cash += credit - fee
                            option = {
                                "right": "put",
                                "strike": strike,
                                "sigma": sigma,
                                "expiry": stamp + pd.Timedelta(days=OPTION_DTE),
                            }
                            opens += 1
                        else:
                            skips += 1
                    else:
                        skips += 1
                elif shares >= 100:
                    strike = _bs_strike(price, sigma, years, "call")
                    mid = option_price("call", price, strike, years, sigma, RATE, 0.0)
                    credit = mid * (1.0 - OTM_HALF_SPREAD) * 100.0
                    fee = option_leg_fees(1, mid * (1.0 - OTM_HALF_SPREAD), sell=True)
                    if credit > fee:
                        cash += credit - fee
                        option = {
                            "right": "call",
                            "strike": strike,
                            "sigma": sigma,
                            "expiry": stamp + pd.Timedelta(days=OPTION_DTE),
                        }
                        opens += 1
                    else:
                        skips += 1
        equity_idx.append(stamp)
        equity_val.append(cash + shares * price - liability(price, stamp))
    equity = pd.Series(equity_val, index=pd.DatetimeIndex(equity_idx), dtype=float)
    return {
        "equity": equity,
        "opens": opens,
        "assignments": assignments,
        "called": called,
        "skips": skips,
        "shares": shares,
    }


def simulate_covered_call(
    frame: pd.DataFrame,
    *,
    starting_equity: float,
    trade_start: pd.Timestamp,
    trade_end: pd.Timestamp,
) -> dict[str, Any]:
    """Buy 100 shares when they fit, then sell a 30-delta call every month.

    Returns unfit when 100 shares never fit. That is not a scored book.
    """
    from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees

    start = pd.Timestamp(trade_start)
    end = pd.Timestamp(trade_end)
    data = frame.loc[(frame.index >= start) & (frame.index <= end)].dropna(subset=["close", "open"])
    if data.empty:
        return {**_empty_option(starting_equity), "unfit": True}
    model = CostModel()
    first_open = float(data["open"].iloc[0])
    entry = buy_price(first_open, model)
    if entry * 100.0 + buy_fees(model) > starting_equity:
        return {**_empty_option(starting_equity), "unfit": True, "reason": "100 shares do not fit"}
    cash = float(starting_equity) - entry * 100.0 - buy_fees(model)
    shares = 100
    # Reuse the wheel marker on a path that already owns shares by seeding it
    # is more code. Run a small dedicated loop.
    close = data["close"].astype(float)
    rv = realized_vol(close, 20)
    option: dict[str, Any] | None = None
    equity_idx: list[pd.Timestamp] = []
    equity_val: list[float] = []
    opens = 0
    called = 0
    month_key: tuple[int, int] | None = None

    def liability(spot: float, ts: pd.Timestamp) -> float:
        if option is None:
            return 0.0
        remaining = max((option["expiry"] - ts).days, 0) / 365.0
        mid = option_price("call", spot, option["strike"], remaining, option["sigma"], RATE, 0.0)
        return mid * (1.0 + OTM_HALF_SPREAD) * 100.0

    for i, (ts, spot) in enumerate(close.items()):
        stamp = pd.Timestamp(ts)
        price = float(spot)
        if option is not None and stamp >= option["expiry"]:
            if price > option["strike"]:
                fill = sell_price(option["strike"], model)
                fee = sell_regulatory_fees(fill, 100.0, model)
                cash += 100.0 * fill - fee
                shares = 0
                called += 1
            option = None
        if shares == 0:
            raw_open = float(data["open"].iloc[i])
            refill = buy_price(raw_open, model)
            cost = refill * 100.0 + buy_fees(model)
            if cash >= cost:
                cash -= cost
                shares = 100
        key = (stamp.year, stamp.month)
        if shares == 100 and option is None and key != month_key:
            month_key = key
            sigma = float(rv.asof(stamp)) if not rv.dropna().empty else float("nan")
            if np.isfinite(sigma):
                sigma = float(np.clip(sigma * IV_PREMIUM, 0.10, 1.50))
                years = OPTION_DTE / 365.0
                strike = _bs_strike(price, sigma, years, "call")
                mid = option_price("call", price, strike, years, sigma, RATE, 0.0)
                credit = mid * (1.0 - OTM_HALF_SPREAD) * 100.0
                fee = option_leg_fees(1, mid * (1.0 - OTM_HALF_SPREAD), sell=True)
                if credit > fee and strike > 0:
                    cash += credit - fee
                    option = {"strike": strike, "sigma": sigma, "expiry": stamp + pd.Timedelta(days=OPTION_DTE)}
                    opens += 1
        equity_idx.append(stamp)
        equity_val.append(cash + shares * price - liability(price, stamp))
    return {
        "equity": pd.Series(equity_val, index=pd.DatetimeIndex(equity_idx), dtype=float),
        "opens": opens,
        "called": called,
        "assignments": 0,
        "skips": 0,
        "shares": shares,
        "unfit": False,
    }


def _empty_option(starting_equity: float) -> dict[str, Any]:
    return {
        "equity": pd.Series(dtype=float),
        "opens": 0,
        "assignments": 0,
        "called": 0,
        "skips": 0,
        "shares": 0,
        "unfit": False,
    }


def assign_tiers(books: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick three names from the frozen tier rule. Empty is an allowed answer."""
    eligible = [book for book in books if book.get("eligible")]

    def calmar(book: dict[str, Any]) -> float:
        return float(book["holdout"]["calmar"])

    conservative_pool = [
        book
        for book in eligible
        if book["verdict"]["winner_vs_spy"] and float(book["holdout"]["max_drawdown"]) >= CONSERVATIVE_DRAWDOWN
    ]
    conservative_pool.sort(key=calmar, reverse=True)
    conservative = conservative_pool[0]["name"] if conservative_pool else None
    moderate_pool = [
        book
        for book in eligible
        if book["verdict"]["winner_vs_spy"]
        and float(book["holdout"]["max_drawdown"]) >= MODERATE_DRAWDOWN
        and book["name"] != conservative
    ]
    moderate_pool.sort(key=calmar, reverse=True)
    moderate = moderate_pool[0]["name"] if moderate_pool else None
    high_pool = [
        book
        for book in eligible
        if book["verdict"]["beats_spy_raw"]
        and book["verdict"]["train_ok"]
        and float(book["holdout"]["cagr"]) > 0
        and book["name"] not in {conservative, moderate}
    ]
    high_pool.sort(key=calmar, reverse=True)
    high = high_pool[0]["name"] if high_pool else None
    return {
        "conservative": conservative,
        "moderate": moderate,
        "high_risk": high,
        "rule": (
            "Conservative is the best Calmar among SPY risk-adjusted winners with a drawdown milder than 15 percent. "
            "Moderate is the best remaining SPY risk-adjusted winner with a drawdown milder than 35 percent. "
            "High risk is the best Calmar among the rest that beat SPY on raw holdout return after a profitable training window."
        ),
    }


# Published holdout, fresh $1,000, from the earlier study. Not recomputed here.
PRIOR_HOLDOUT = {
    "gtaa_10m": {
        "name": "gtaa_10m",
        "eligible": True,
        "family": "prior",
        "holdout": {
            "cagr": 0.069,
            "max_drawdown": -0.105,
            "sharpe": 0.96,
            "calmar": 0.66,
            "ending_equity": 1925.0,
            "positive_months": 0.653,
            "years": 9.76,
        },
        "train": {"cagr": 0.055, "years": 12.0, "max_drawdown": -0.112, "sharpe": 0.72},
        "verdict": {
            "train_ok": True,
            "holdout_ok": True,
            "winner_vs_spy": True,
            "beats_spy_raw": False,
            "path_risk": True,
            "path_similar": False,
        },
        "beats_qqq_raw": False,
        "spy_holdout": {"cagr": 0.153, "max_drawdown": -0.337, "sharpe": 0.88, "ending_equity": 4028.0},
        "qqq_holdout": {"cagr": 0.217, "max_drawdown": -0.351, "sharpe": 0.98, "ending_equity": 6791.0},
        "note": "Published 10-month sleeve. Holdout ending $1,925. Not resimulated for the rank.",
    },
    "dual_invested": {
        "name": "dual_invested",
        "eligible": True,
        "family": "prior",
        "holdout": {
            "cagr": 0.084,
            "max_drawdown": -0.376,
            "sharpe": 0.49,
            "calmar": 0.22,
            "ending_equity": 2192.0,
            "positive_months": 0.500,
            "years": 9.76,
        },
        "train": {"cagr": 0.095, "years": 12.0, "max_drawdown": -0.398, "sharpe": 0.52},
        "verdict": {
            "train_ok": True,
            "holdout_ok": True,
            "winner_vs_spy": False,
            "beats_spy_raw": False,
            "path_risk": False,
            "path_similar": False,
        },
        "beats_qqq_raw": False,
        "spy_holdout": {"cagr": 0.153, "max_drawdown": -0.337, "sharpe": 0.88, "ending_equity": 4028.0},
        "qqq_holdout": {"cagr": 0.217, "max_drawdown": -0.351, "sharpe": 0.98, "ending_equity": 6791.0},
        "note": "Published fully invested dual momentum. Holdout ending $2,192. Drawdown was deeper than SPY.",
    },
    "tqqq_monthly": {
        "name": "tqqq_monthly",
        "eligible": True,
        "family": "prior",
        "holdout": {
            "cagr": 0.256,
            "max_drawdown": -0.699,
            "sharpe": 0.70,
            "calmar": 0.37,
            "ending_equity": 9255.0,
            "positive_months": 0.517,
            "years": 9.76,
        },
        "train": {"cagr": 0.181, "years": 6.1, "max_drawdown": -0.594, "sharpe": 0.61},
        "verdict": {
            "train_ok": True,
            "holdout_ok": True,
            "winner_vs_spy": False,
            "beats_spy_raw": True,
            "path_risk": False,
            "path_similar": False,
        },
        "beats_qqq_raw": True,
        "spy_holdout": {"cagr": 0.153, "max_drawdown": -0.337, "sharpe": 0.88, "ending_equity": 4028.0},
        "qqq_holdout": {"cagr": 0.217, "max_drawdown": -0.351, "sharpe": 0.98, "ending_equity": 6791.0},
        "note": "Published monthly TQQQ filter. Holdout ending $9,255. Sharpe and drawdown lost to SPY and to raw TQQQ.",
    },
}
