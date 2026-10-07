"""Three fully invested books for a $1,000 to $5,000 account.

The rules below were written down before the score. Neighbors of the
lookback are reported later and are not allowed to replace them.

Conservative: Mebane Faber, A Quantitative Approach to Tactical Asset
Allocation (2007). Each available sleeve is one equal slice. The slice
holds the ETF when the month-end close is above its 10-month average,
and otherwise holds cash.

Moderate: Gary Antonacci, Dual Momentum Investing (2014), calendar
months. Relative momentum is the 12-1 month return. Absolute momentum
is the full 12-month return against BIL, or against zero when BIL does
not have 12 months yet. The account holds the single winner, or cash.

High risk: the same 10-month average, applied to TQQQ. The account is
all in or all cash. TQQQ did not exist in 2008.

Cash earns zero in the default book. A cash account sells on the first
session after the signal and buys on the session after that, because
sale proceeds are not settled the same day. A $1,000 account is under
the $2,000 margin minimum, so that lag is the default. The wired bot is
a different book: it still risk-sizes dual momentum at 0.75 percent of
equity with a 20 percent trail. This file does not change that.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.strategies.signals import month_end_mask

SAMPLE_START = pd.Timestamp("2005-01-01")
HOLDOUT_START = pd.Timestamp("2017-01-01")
SAMPLE_END = pd.Timestamp("2026-10-06")
GTAA_SYMBOLS = ("SPY", "EFA", "IEF", "GLD")
DUAL_SYMBOLS = ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD")
HURDLE_SYMBOL = "BIL"
HIGH_SYMBOL = "TQQQ"
SMA_MONTHS = 10
DUAL_LOOKBACK = 12
DUAL_SKIP = 1
RANDOM_SEED = 17
SIMILAR_CAGR_GAP = 0.03
MILDER_DRAWDOWN = 0.10
MIN_HOLDOUT_YEARS = 8.0
MIN_TRAIN_YEARS = 5.0


def frozen_rules() -> dict[str, Any]:
    """The pre-registered books. No measured return belongs in this dict."""
    return {
        "sample_start": str(SAMPLE_START.date()),
        "holdout_start": str(HOLDOUT_START.date()),
        "sample_end": str(SAMPLE_END.date()),
        "costs": "Webull commission 0. SEC fee on sells. FINRA TAF on sells. 5 bps slippage and 1 bp half-spread per side.",
        "cash": "Earns zero. Cash account: sell the next session, buy the session after that.",
        "fractional": "Fractional shares. These ETFs do not fit a $1,000 account in whole shares at recent prices.",
        "taxes": "Ignored. Monthly turnover realizes short-term gains. A buy-and-hold of SPY defers them.",
        "conservative": (
            "Equal slice of SPY, EFA, IEF, and GLD once each has a 10-month average. "
            "Hold that slice when the month-end close is strictly above the average, else cash. "
            "A fund that is not listed yet is not in that month's count."
        ),
        "moderate": (
            "SPY, QQQ, IWM, EFA, EEM, TLT, GLD. Hold the one with the best 12-1 month return "
            "if its full 12-month return is strictly above BIL's 12-month return. Otherwise cash. "
            "Before BIL has 12 months the hurdle is zero. No trailing stop."
        ),
        "high_risk": (
            "Hold TQQQ when its month-end close is strictly above its 10-month average, else cash. "
            "The same filter on QQQ is a labeled unlevered check, not the pick."
        ),
        "winner": (
            "Holdout from 2017-01-01, fresh $1,000, after costs. Training CAGR must be positive "
            "over at least five years. Holdout CAGR must be positive over at least eight years. "
            "A SPY win is a higher Sharpe and a higher Calmar than SPY, or a CAGR within three "
            "points of SPY with a max drawdown at least ten points milder. A benchmark win, used "
            "for the high-risk book against TQQQ buy-and-hold, is a higher Sharpe and a milder "
            "max drawdown than that benchmark. Neighbors do not replace the frozen lookback."
        ),
        "recommend": (
            "Among books that beat SPY on that test, recommend the highest holdout Calmar. "
            "A book that only beats its own benchmark is not the one to fund ahead of SPY."
        ),
    }


def month_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    mask = month_end_mask(pd.DatetimeIndex(index))
    return pd.DatetimeIndex(index[mask.to_numpy()])


def weights_from_monthly_gtaa(monthly: pd.DataFrame, months: int = SMA_MONTHS) -> pd.DataFrame:
    """Equal sleeve. Weight is zero until that column has ``months`` closes."""
    if months < 2:
        raise ValueError("months must be at least 2")
    average = monthly.rolling(months, min_periods=months).mean()
    valid = average.notna()
    count = valid.sum(axis=1).astype(float)
    on = (monthly > average) & valid
    weights = on.astype(float).div(count.replace(0.0, np.nan), axis=0).fillna(0.0)
    return weights


def weights_from_monthly_dual(
    monthly: pd.DataFrame,
    hurdle: pd.Series | None = None,
    lookback: int = DUAL_LOOKBACK,
    skip: int = DUAL_SKIP,
) -> pd.DataFrame:
    """One-hot weight of the 12-1 winner that also clears the absolute hurdle."""
    if lookback <= skip or skip < 0:
        raise ValueError("lookback must be longer than the skipped month")
    absolute = monthly / monthly.shift(lookback) - 1.0
    relative = monthly.shift(skip) / monthly.shift(lookback) - 1.0
    if hurdle is None:
        hurdle_row = pd.Series(0.0, index=monthly.index)
    else:
        hurdle_row = hurdle.reindex(monthly.index)
        # A missing bill return is a zero hurdle, not a reason to drop the month.
        hurdle_row = hurdle_row.where(hurdle_row.notna(), 0.0)
    weights = pd.DataFrame(0.0, index=monthly.index, columns=monthly.columns)
    for ts in monthly.index:
        ranked: list[tuple[float, str]] = []
        for symbol in monthly.columns:
            rel = relative.at[ts, symbol]
            abs_ret = absolute.at[ts, symbol]
            if pd.isna(rel) or pd.isna(abs_ret):
                continue
            if float(abs_ret) <= float(hurdle_row.at[ts]):
                continue
            ranked.append((float(rel), str(symbol)))
        if not ranked:
            continue
        ranked.sort(key=lambda item: (-item[0], item[1]))
        weights.at[ts, ranked[0][1]] = 1.0
    return weights


def weights_from_monthly_trend(monthly: pd.Series, months: int = SMA_MONTHS) -> pd.DataFrame:
    """All-or-cash trend filter. The column name is the series name."""
    name = str(monthly.name or "asset")
    frame = monthly.to_frame(name)
    average = frame[name].rolling(months, min_periods=months).mean()
    on = (frame[name] > average) & average.notna()
    return on.astype(float).to_frame(name)


def shuffle_weights(weights: pd.DataFrame, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Keep each month's date. Move the weight rows. This breaks the timing."""
    if weights.empty:
        return weights.copy()
    order = np.random.default_rng(seed).permutation(len(weights))
    shuffled = pd.DataFrame(
        weights.to_numpy()[order],
        index=weights.index,
        columns=weights.columns,
    )
    return shuffled


def static_equal_weights(monthly: pd.DataFrame, months: int = SMA_MONTHS) -> pd.DataFrame:
    """Always hold the sleeves that already have a formed average. No timing."""
    average = monthly.rolling(months, min_periods=months).mean()
    valid = average.notna()
    count = valid.sum(axis=1).astype(float)
    return valid.astype(float).div(count.replace(0.0, np.nan), axis=0).fillna(0.0)


@dataclass
class BookResult:
    equity: pd.Series
    fills: int
    entries: int
    exits: int
    rebalances: int
    turnover: float
    invested_days: int
    days: int

    @property
    def exposure(self) -> float:
        if self.days <= 0:
            return 0.0
        return self.invested_days / self.days


def _finite(value: float) -> bool:
    return bool(np.isfinite(value)) and value > 0


def simulate_weights(
    clock: pd.DatetimeIndex,
    opens: dict[str, pd.Series],
    closes: dict[str, pd.Series],
    signals: pd.DataFrame,
    *,
    starting_equity: float,
    trade_start: pd.Timestamp,
    trade_end: pd.Timestamp,
    costs: CostModel | None = None,
    same_day_buys: bool = False,
    cash_level: pd.Series | None = None,
) -> BookResult:
    """Turn month-end weights into a daily equity curve.

    ``signals`` is indexed by the session whose close formed the decision.
    The sell is the next session's open. On a cash account the buy is the
    session after the sell. ``same_day_buys`` spends sale proceeds immediately.
    """
    model = costs or CostModel()
    index = pd.DatetimeIndex(clock).sort_values()
    start = pd.Timestamp(trade_start)
    end = pd.Timestamp(trade_end)
    symbols = [str(column) for column in signals.columns]
    open_np = {symbol: opens[symbol].reindex(index).to_numpy(dtype=float) for symbol in symbols}
    close_np = {symbol: closes[symbol].reindex(index).to_numpy(dtype=float) for symbol in symbols}
    fill_at: dict[int, dict[str, float]] = {}
    for ts, row in signals.iterrows():
        pos = int(index.searchsorted(pd.Timestamp(ts), side="right"))
        if pos >= len(index):
            continue
        fill_day = pd.Timestamp(index[pos])
        if fill_day < start or fill_day > end:
            continue
        fill_at[pos] = {symbol: float(row[symbol]) for symbol in symbols}

    cash = float(starting_equity)
    unsettled: list[tuple[int, float]] = []
    shares = {symbol: 0.0 for symbol in symbols}
    pending: dict[str, float] | None = None
    last_weights = {symbol: 0.0 for symbol in symbols}
    equity_idx: list[pd.Timestamp] = []
    equity_val: list[float] = []
    fills = 0
    entries = 0
    exits = 0
    rebalances = 0
    traded_notional = 0.0
    invested_days = 0
    growth = None if cash_level is None else cash_level.reindex(index).to_numpy(dtype=float)

    def price_at(store: dict[str, np.ndarray], symbol: str, pos: int) -> float:
        value = float(store[symbol][pos])
        return value if _finite(value) else float("nan")

    def portfolio_open(pos: int) -> float:
        invested = 0.0
        for symbol, qty in shares.items():
            raw = price_at(open_np, symbol, pos)
            if qty > 0 and _finite(raw):
                invested += qty * raw
        return cash + sum(amount for _, amount in unsettled) + invested

    for pos, ts in enumerate(index):
        stamp = pd.Timestamp(ts)
        if stamp < start or stamp > end:
            continue
        still: list[tuple[int, float]] = []
        for due, amount in unsettled:
            if due <= pos:
                cash += amount
            else:
                still.append((due, amount))
        unsettled = still

        if pos in fill_at or pending is not None:
            if pos in fill_at:
                weights = fill_at[pos]
                if any(abs(weights.get(symbol, 0.0) - last_weights.get(symbol, 0.0)) > 1e-9 for symbol in symbols):
                    rebalances += 1
                for symbol in symbols:
                    before = last_weights.get(symbol, 0.0)
                    after = weights.get(symbol, 0.0)
                    if before <= 1e-9 and after > 1e-9:
                        entries += 1
                    elif before > 1e-9 and after <= 1e-9:
                        exits += 1
                last_weights = dict(weights)
                equity_open = portfolio_open(pos)
                pending = {}
                for symbol in symbols:
                    raw = price_at(open_np, symbol, pos)
                    weight = weights.get(symbol, 0.0)
                    if weight <= 0 or not _finite(raw):
                        pending[symbol] = 0.0
                    else:
                        pending[symbol] = weight * equity_open / raw
            assert pending is not None
            for symbol, target in pending.items():
                held = shares.get(symbol, 0.0)
                raw = price_at(open_np, symbol, pos)
                if held <= target + 1e-8 or not _finite(raw):
                    continue
                qty = held - target
                fill = sell_price(raw, model)
                fee = sell_regulatory_fees(fill, qty, model)
                proceeds = qty * fill - fee
                if proceeds <= 0:
                    continue
                shares[symbol] = target
                traded_notional += qty * fill
                fills += 1
                if same_day_buys:
                    cash += proceeds
                else:
                    unsettled.append((pos + 1, proceeds))
            for symbol in sorted(pending):
                target = pending[symbol]
                held = shares.get(symbol, 0.0)
                raw = price_at(open_np, symbol, pos)
                if held + 1e-8 >= target or not _finite(raw):
                    continue
                fill = buy_price(raw, model)
                fee = buy_fees(model)
                room = (cash - fee) / fill if cash > fee else 0.0
                qty = min(target - held, max(room, 0.0))
                if qty * raw < 0.50:
                    continue
                cash -= qty * fill + fee
                shares[symbol] = held + qty
                traded_notional += qty * fill
                fills += 1
            leftover = 0.0
            for symbol, target in pending.items():
                raw = price_at(close_np, symbol, pos)
                if not _finite(raw):
                    raw = price_at(open_np, symbol, pos)
                if _finite(raw):
                    leftover += abs(shares.get(symbol, 0.0) - target) * raw
            if leftover < 1.0:
                pending = None

        if growth is not None and pos > 0 and _finite(float(growth[pos])) and _finite(float(growth[pos - 1])):
            cash *= float(growth[pos]) / float(growth[pos - 1])

        invested = 0.0
        marked = False
        for symbol, qty in shares.items():
            raw = price_at(close_np, symbol, pos)
            if qty > 0 and _finite(raw):
                invested += qty * raw
                marked = True
        if invested > 1.0:
            invested_days += 1
        if shares and any(qty > 0 for qty in shares.values()) and not marked:
            # A held name with no close keeps yesterday's value out of the curve.
            continue
        equity_idx.append(stamp)
        equity_val.append(cash + sum(amount for _, amount in unsettled) + invested)

    equity = pd.Series(equity_val, index=pd.DatetimeIndex(equity_idx), dtype=float)
    years = 0.0
    if len(equity) >= 2:
        years = max((equity.index[-1] - equity.index[0]).days, 1) / 365.25
    average_equity = float(equity.mean()) if len(equity) else float(starting_equity)
    turnover = 0.0
    if years > 0 and average_equity > 0:
        turnover = traded_notional / average_equity / years
    return BookResult(
        equity=equity,
        fills=fills,
        entries=entries,
        exits=exits,
        rebalances=rebalances,
        turnover=turnover,
        invested_days=invested_days,
        days=int(len(equity)),
    )


def performance(equity: pd.Series, starting_equity: float) -> dict[str, Any]:
    """Match the daily Sharpe, drawdown, and CAGR used by the other books."""
    empty = {
        "starting_equity": starting_equity,
        "ending_equity": starting_equity,
        "total_return": 0.0,
        "cagr": 0.0,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
        "calmar": 0.0,
        "years": 0.0,
        "positive_months": 0.0,
        "months": 0,
    }
    if equity is None or len(equity) == 0:
        return empty
    curve = pd.concat(
        [pd.Series([starting_equity], index=[equity.index[0] - pd.Timedelta(days=1)]), equity.astype(float)]
    )
    ending = float(curve.iloc[-1])
    elapsed = max((curve.index[-1] - curve.index[0]).days, 1)
    years = elapsed / 365.25
    total_return = ending / starting_equity - 1.0
    cagr = (ending / starting_equity) ** (1.0 / years) - 1.0 if ending > 0 else -1.0
    rets = curve.pct_change().dropna()
    std = float(rets.std(ddof=0)) if len(rets) else 0.0
    sharpe = float(rets.mean() / std * math.sqrt(252)) if std > 0 else 0.0
    drawdown = curve / curve.cummax() - 1.0
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else (math.inf if cagr > 0 else 0.0)
    monthly = _month_end_levels(equity, starting_equity)
    month_rets = monthly.pct_change().dropna()
    positive = float((month_rets > 0).mean()) if len(month_rets) else 0.0
    return {
        "starting_equity": starting_equity,
        "ending_equity": ending,
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "years": years,
        "positive_months": positive,
        "months": int(len(month_rets)),
    }


def _month_end_levels(equity: pd.Series, starting_equity: float) -> pd.Series:
    if equity.empty:
        return equity
    ends = month_end_dates(pd.DatetimeIndex(equity.index))
    levels = equity.reindex(ends).dropna()
    if len(levels) == 0:
        return levels
    # The return of the first scored month needs a base. Use the starting
    # stake when the curve begins in that month, not a future close.
    base_stamp = equity.index[0] - pd.Timedelta(days=1)
    base = pd.Series([starting_equity], index=pd.DatetimeIndex([base_stamp]))
    return pd.concat([base, levels])


def buy_and_hold(
    open_: pd.Series,
    close: pd.Series,
    *,
    starting_equity: float,
    trade_start: pd.Timestamp,
    trade_end: pd.Timestamp,
    costs: CostModel | None = None,
) -> pd.Series:
    """Buy the first open in the window. Mark the closes. Do not sell at the end."""
    model = costs or CostModel()
    start = pd.Timestamp(trade_start)
    end = pd.Timestamp(trade_end)
    window_open = open_.loc[(open_.index >= start) & (open_.index <= end)].dropna()
    window_close = close.loc[(close.index >= start) & (close.index <= end)].dropna()
    if window_open.empty or window_close.empty:
        return pd.Series(dtype=float)
    first = window_open.index[0]
    entry = buy_price(float(window_open.loc[first]), model)
    shares = starting_equity / entry
    cash = starting_equity - shares * entry - buy_fees(model)
    marks = window_close.loc[window_close.index >= first].astype(float)
    equity = marks * shares + cash
    equity.iloc[0] = cash + shares * entry
    return equity


def window_stats(equity: pd.Series, spy_close: pd.Series, months: int, stake: float) -> dict[str, Any]:
    """Rolling month-end results. SPY pays the same friction at both ends of the window."""
    ends = month_end_dates(pd.DatetimeIndex(equity.index))
    level = equity.reindex(ends).dropna()
    spy = spy_close.reindex(level.index).astype(float)
    usable = level.index[months:]
    book_rets: list[float] = []
    spy_rets: list[float] = []
    model = CostModel()
    for ts in usable:
        loc = level.index.get_loc(ts)
        if isinstance(loc, slice) or not isinstance(loc, int):
            continue
        if loc - months < 0:
            continue
        prev = level.index[loc - months]
        start_eq = float(level.iloc[loc - months])
        end_eq = float(level.iloc[loc])
        if start_eq <= 0:
            continue
        spy_start = float(spy.loc[prev]) if prev in spy.index else float("nan")
        spy_end = float(spy.loc[ts]) if ts in spy.index else float("nan")
        if not _finite(spy_start) or not _finite(spy_end):
            continue
        book_rets.append(end_eq / start_eq - 1.0)
        spy_rets.append(sell_price(spy_end, model) / buy_price(spy_start, model) - 1.0)
    return _distribution(book_rets, spy_rets, stake, months)


def _distribution(book_rets: list[float], spy_rets: list[float], stake: float, months: int) -> dict[str, Any]:
    def pack(values: list[float], prefix: str) -> dict[str, Any]:
        if not values:
            return {
                f"{prefix}windows": 0,
                f"{prefix}median": None,
                f"{prefix}p10": None,
                f"{prefix}p90": None,
                f"{prefix}pct_negative": None,
                f"{prefix}ending_p10": None,
                f"{prefix}ending_median": None,
                f"{prefix}ending_p90": None,
            }
        arr = np.array(values, dtype=float)
        p10, median, p90 = (float(np.percentile(arr, q)) for q in (10, 50, 90))
        return {
            f"{prefix}windows": int(len(arr)),
            f"{prefix}median": median,
            f"{prefix}p10": p10,
            f"{prefix}p90": p90,
            f"{prefix}pct_negative": float((arr < 0).mean()),
            f"{prefix}ending_p10": stake * (1.0 + p10),
            f"{prefix}ending_median": stake * (1.0 + median),
            f"{prefix}ending_p90": stake * (1.0 + p90),
        }

    out = {"months": months, "stake": stake}
    out.update(pack(book_rets, ""))
    out.update(pack(spy_rets, "spy_"))
    return out


def calendar_year_return(equity: pd.Series, year: int, starting_equity: float) -> float | None:
    """Close-to-close across calendar years, using the stake if the book starts mid-year."""
    if equity.empty:
        return None
    levels = _month_end_levels(equity, starting_equity)
    in_year = [ts for ts in levels.index if pd.Timestamp(ts).year == year]
    before = [ts for ts in levels.index if pd.Timestamp(ts).year < year]
    if not in_year:
        return None
    end = levels.loc[in_year[-1]]
    if before:
        start = levels.loc[before[-1]]
    elif pd.Timestamp(in_year[0]).year == year and levels.index[0] == in_year[0]:
        start = float(starting_equity) if float(levels.iloc[0]) == float(starting_equity) else None
        if start is None:
            return None
    else:
        return None
    if float(start) <= 0:
        return None
    return float(end) / float(start) - 1.0


def verdict(
    holdout: dict[str, Any],
    spy: dict[str, Any],
    train: dict[str, Any],
    benchmark: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the frozen winner test. Training has to have made money too."""
    train_ok = float(train.get("years") or 0) >= MIN_TRAIN_YEARS and float(train.get("cagr") or 0) > 0
    holdout_ok = float(holdout.get("years") or 0) >= MIN_HOLDOUT_YEARS and float(holdout.get("cagr") or 0) > 0
    higher_sharpe = float(holdout.get("sharpe") or 0) > float(spy.get("sharpe") or 0)
    higher_calmar = float(holdout.get("calmar") or 0) > float(spy.get("calmar") or 0)
    similar_return = float(holdout.get("cagr") or 0) >= float(spy.get("cagr") or 0) - SIMILAR_CAGR_GAP
    milder = float(holdout.get("max_drawdown") or 0) >= float(spy.get("max_drawdown") or 0) + MILDER_DRAWDOWN
    path_risk = higher_sharpe and higher_calmar
    path_similar = similar_return and milder and float(holdout.get("cagr") or 0) > 0
    winner_vs_spy = bool(train_ok and holdout_ok and (path_risk or path_similar))
    beats_raw = float(holdout.get("cagr") or 0) > float(spy.get("cagr") or 0)
    winner_vs_benchmark = False
    if benchmark is not None and train_ok and holdout_ok:
        winner_vs_benchmark = float(holdout.get("sharpe") or 0) > float(benchmark.get("sharpe") or 0) and float(
            holdout.get("max_drawdown") or 0
        ) > float(benchmark.get("max_drawdown") or -1)
    return {
        "train_ok": train_ok,
        "holdout_ok": holdout_ok,
        "path_risk": path_risk,
        "path_similar": path_similar,
        "winner_vs_spy": winner_vs_spy,
        "beats_spy_raw": beats_raw,
        "winner_vs_benchmark": winner_vs_benchmark,
    }


def recommend(books: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick one book only from those that beat SPY on the frozen test."""
    winners = [book for book in books if book["verdict"]["winner_vs_spy"]]
    pool = winners
    reason = "highest holdout Calmar among books that beat SPY on the frozen test"
    if not pool:
        return {
            "pick": None,
            "reason": (
                "No book beat SPY on the frozen out-of-sample test. "
                "Owning SPY remains the raw-growth baseline."
            ),
        }
    pool.sort(key=lambda book: float(book["holdout"]["calmar"]), reverse=True)
    return {"pick": pool[0]["name"], "reason": reason}


@dataclass
class Prepared:
    clock: pd.DatetimeIndex
    opens: dict[str, pd.Series]
    closes: dict[str, pd.Series]
    monthly: pd.DataFrame
    field_notes: list[str] = field(default_factory=list)


def prepare(bars: dict[str, pd.DataFrame], symbols: list[str]) -> Prepared:
    if "SPY" not in bars:
        raise RuntimeError("SPY daily bars are required")
    clock = pd.DatetimeIndex(bars["SPY"].index).sort_values()
    clock = clock[(clock >= pd.Timestamp("2003-01-01")) & (clock <= SAMPLE_END)]
    opens: dict[str, pd.Series] = {}
    closes: dict[str, pd.Series] = {}
    missing = [symbol for symbol in symbols if symbol not in bars]
    if missing:
        raise RuntimeError("Missing daily bars: " + ", ".join(missing))
    for symbol in symbols:
        frame = bars[symbol].reindex(clock)
        opens[symbol] = frame["open"].astype(float)
        closes[symbol] = frame["close"].astype(float)
    ends = month_end_dates(clock)
    monthly = pd.DataFrame({symbol: closes[symbol].reindex(ends) for symbol in symbols}, index=ends)
    return Prepared(clock=clock, opens=opens, closes=closes, monthly=monthly)
