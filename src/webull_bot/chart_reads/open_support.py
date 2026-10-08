"""Open-versus-support study. Research only.

The catalog, the windows, and the exits below are frozen. The holdout is
not an input to the search. Nothing here places an order or edits a
sandbox book.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, time

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.atm_exit import deflated_sharpe
from webull_bot.chart_reads.vwap_band import metrics_from
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.indicators import atr as wilder_atr
from webull_bot.indicators import ema
from webull_bot.options.fees import option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price

TRAIN_START = date(2018, 1, 1)
TRAIN_END = date(2026, 7, 6)
HOLDOUT_START = date(2026, 7, 7)
HOLDOUT_END = date(2026, 10, 6)
# Dukascopy's cached feed ends here. A later print is a chart, not a score.
DATA_END = date(2026, 10, 6)

GATE_MIN_TRADES = 80
GATE_PF = 1.10
GATE_SHARPE = 0.40
GATE_DRAWDOWN = -0.30
FDR_Q = 0.10
DSR_MIN = 0.95
DAILY_CAP = 3
RANDOM_SEED = 17
SLOPE_LAG = 5
STRUCTURE_PIVOT = 5
ATR_WINDOW = 14
FALLBACK_HOLD_BARS = 6

# The long Dukascopy cache is the gate. The other names have only a short
# Yahoo 5-minute file and are scored once, on the cell the train already picked.
GATE_SYMBOLS = ("SPY", "QQQ")
CONTEXT_SYMBOLS = (
    "SPY",
    "QQQ",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "PLTR",
    "MSTR",
    "HOOD",
    "MU",
    "AMD",
    "AVGO",
    "INTC",
)

LEVELS = ("prior_day", "swing3", "swing5", "swing10")
TRENDS = ("ema20", "ema50", "structure")
STOPS = ("level", "candle")
EXITS = ("r1", "r2", "prior_close", "vwap", "eod")
OPEN_MINUTE = 9 * 60 + 30
ENTRY_MINUTE = 9 * 60 + 35
CLOSE_MINUTE = 16 * 60

COSTS = CostModel()
OPTION_RATE = 0.02
OPTION_DIVIDEND = 0.0


@dataclass(frozen=True)
class Cell:
    id: str
    mode: str
    level: str
    trend: str
    stop: str
    exit: str
    cap: int


@dataclass
class DayView:
    symbol: str
    day: date
    first_open: float
    first_high: float
    first_low: float
    first_close: float
    entry_open: float
    bars_open: np.ndarray
    bars_high: np.ndarray
    bars_low: np.ndarray
    bars_close: np.ndarray
    bar_minutes: np.ndarray
    support: dict[str, float]
    resistance: dict[str, float]
    trend: dict[str, str]
    prior_close: float
    prior_vwap: float
    atr: float
    dollar_volume: float


def _catalog() -> tuple[Cell, ...]:
    cells: list[Cell] = []
    for level in LEVELS:
        for trend in TRENDS:
            for stop in STOPS:
                for exit_name in EXITS:
                    cells.append(
                        Cell(
                            id=f"both_{level}_{trend}_{stop}_{exit_name}",
                            mode="both_support",
                            level=level,
                            trend=trend,
                            stop=stop,
                            exit=exit_name,
                            cap=DAILY_CAP,
                        )
                    )
    for level in LEVELS:
        for exit_name in EXITS:
            cells.append(
                Cell(
                    id=f"longres_{level}_ema20_level_{exit_name}",
                    mode="long_resistance",
                    level=level,
                    trend="ema20",
                    stop="level",
                    exit=exit_name,
                    cap=DAILY_CAP,
                )
            )
    cells.append(
        Cell(
            id="both_prior_day_ema20_level_r1_cap5",
            mode="both_support",
            level="prior_day",
            trend="ema20",
            stop="level",
            exit="r1",
            cap=5,
        )
    )
    return tuple(cells)


CATALOG: tuple[Cell, ...] = _catalog()
CATALOG_BY_ID: dict[str, Cell] = {cell.id: cell for cell in CATALOG}
HEADLINE_ID = "both_prior_day_ema20_level_r1"


def frozen_rules() -> dict:
    return {
        "train": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
        "holdout": [HOLDOUT_START.isoformat(), HOLDOUT_END.isoformat()],
        "gate_symbols": list(GATE_SYMBOLS),
        "context_symbols": list(CONTEXT_SYMBOLS),
        "levels": list(LEVELS),
        "trends": list(TRENDS),
        "stops": list(STOPS),
        "exits": list(EXITS),
        "cells": len(CATALOG),
        "cap": DAILY_CAP,
        "gate": {
            "min_trades": GATE_MIN_TRADES,
            "profit_factor": GATE_PF,
            "sharpe": GATE_SHARPE,
            "max_drawdown": GATE_DRAWDOWN,
            "fdr_q": FDR_Q,
            "deflated_sharpe": DSR_MIN,
        },
        "entry": "First 5-minute bar is 09:30-09:35. Fill is the 09:35 open.",
        "flat": "15:55 bar close, or the last bar of a short session.",
        "random": {"seed": RANDOM_SEED, "matched_count": True, "matched_hold": True},
    }


def assert_window_visible(end: date, allow_holdout: bool = False) -> None:
    if not allow_holdout and end >= HOLDOUT_START:
        raise RuntimeError(f"window reaches the holdout {end.isoformat()}")


def _shift(values: np.ndarray, lag: int) -> np.ndarray:
    out = np.full(len(values), np.nan)
    if 0 < lag < len(values):
        out[lag:] = values[:-lag]
    return out


def _swing_points(values: np.ndarray, width: int, kind: str) -> list[tuple[int, float]]:
    points: list[tuple[int, float]] = []
    for j in range(width, len(values) - width):
        left = values[j - width : j]
        right = values[j + 1 : j + width + 1]
        price = float(values[j])
        if not np.isfinite(price) or not np.isfinite(left).all() or not np.isfinite(right).all():
            continue
        if kind == "low" and price < float(left.min()) and price < float(right.min()):
            points.append((j + width + 1, price))
        elif kind == "high" and price > float(left.max()) and price > float(right.max()):
            points.append((j + width + 1, price))
    return points


def _known_swing(values: np.ndarray, width: int, kind: str) -> np.ndarray:
    """Most recent confirmed swing, known at the open of each row."""
    out = np.full(len(values), np.nan)
    points = _swing_points(values, width, kind)
    last = np.nan
    cursor = 0
    for index in range(len(values)):
        while cursor < len(points) and points[cursor][0] <= index:
            last = points[cursor][1]
            cursor += 1
        out[index] = last
    return out


def _trend_from_ema(close: np.ndarray, window: int) -> np.ndarray:
    line = ema(pd.Series(close), window).to_numpy(dtype=float)
    known = _shift(line, 1)
    lagged = _shift(line, 1 + SLOPE_LAG)
    price = _shift(close, 1)
    labels = np.array(["flat"] * len(close), dtype=object)
    up = (price > known) & (known > lagged)
    down = (price < known) & (known < lagged)
    labels[up] = "up"
    labels[down] = "down"
    labels[~np.isfinite(known) | ~np.isfinite(lagged) | ~np.isfinite(price)] = "flat"
    return labels


def _trend_structure(high: np.ndarray, low: np.ndarray) -> np.ndarray:
    last_high = np.full(len(high), np.nan)
    prev_high = np.full(len(high), np.nan)
    last_low = np.full(len(low), np.nan)
    prev_low = np.full(len(low), np.nan)
    highs = _swing_points(high, STRUCTURE_PIVOT, "high")
    lows = _swing_points(low, STRUCTURE_PIVOT, "low")
    labels = np.array(["flat"] * len(high), dtype=object)

    def _fill(points: list[tuple[int, float]], last: np.ndarray, prev: np.ndarray) -> None:
        cursor = 0
        recent = np.nan
        older = np.nan
        for index in range(len(last)):
            while cursor < len(points) and points[cursor][0] <= index:
                older = recent
                recent = points[cursor][1]
                cursor += 1
            last[index] = recent
            prev[index] = older

    _fill(highs, last_high, prev_high)
    _fill(lows, last_low, prev_low)
    up = (last_high > prev_high) & (last_low > prev_low)
    down = (last_high < prev_high) & (last_low < prev_low)
    finite = np.isfinite(last_high) & np.isfinite(prev_high) & np.isfinite(last_low) & np.isfinite(prev_low)
    labels[finite & up] = "up"
    labels[finite & down] = "down"
    return labels


def feature_frame(daily: pd.DataFrame) -> pd.DataFrame:
    """Columns are known at the open. Row i does not use row i's own high, low, or close."""
    frame = daily.sort_index().copy()
    frame.index = [_as_date(value) for value in frame.index]
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    vwap = frame["vwap"].to_numpy(dtype=float) if "vwap" in frame.columns else np.full(len(frame), np.nan)
    atr_values = wilder_atr(frame, ATR_WINDOW).to_numpy(dtype=float)
    out = pd.DataFrame(index=frame.index)
    out["prior_low"] = _shift(low, 1)
    out["prior_high"] = _shift(high, 1)
    out["prior_close"] = _shift(close, 1)
    out["prior_vwap"] = _shift(vwap, 1)
    out["atr"] = _shift(atr_values, 1)
    out["trend_ema20"] = _trend_from_ema(close, 20)
    out["trend_ema50"] = _trend_from_ema(close, 50)
    out["trend_structure"] = _trend_structure(high, low)
    for width, name in ((3, "swing3"), (5, "swing5"), (10, "swing10")):
        out[f"{name}_low"] = _known_swing(low, width, "low")
        out[f"{name}_high"] = _known_swing(high, width, "high")
    return out


def daily_from_intraday(five: pd.DataFrame) -> pd.DataFrame:
    rows = []
    grouped = five.groupby(five.index.date)
    for day, chunk in grouped:
        rth = chunk.between_time(time(9, 30), time(15, 55))
        if rth.empty:
            continue
        typical = (rth["high"] + rth["low"] + rth["close"]) / 3.0
        volume = rth["volume"].astype(float)
        total = float(volume.sum())
        vwap = float((typical * volume).sum() / total) if total > 0 else float(typical.mean())
        rows.append(
            {
                "date": day,
                "open": float(rth["open"].iloc[0]),
                "high": float(rth["high"].max()),
                "low": float(rth["low"].min()),
                "close": float(rth["close"].iloc[-1]),
                "volume": total,
                "vwap": vwap,
            }
        )
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "vwap"])
    return pd.DataFrame(rows).set_index("date").sort_index()


def _as_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, pd.Timestamp):
        return value
    return pd.Timestamp(value).date()


def build_views(
    symbol: str,
    five: pd.DataFrame,
    daily: pd.DataFrame | None = None,
    dollar_volume: pd.Series | None = None,
) -> list[DayView]:
    """One view per session that has both the 09:30 and the 09:35 bars."""
    if five is None or five.empty:
        return []
    frame = five.sort_index()
    if daily is None:
        daily = daily_from_intraday(frame)
    if daily.empty:
        return []
    features = feature_frame(daily)
    volume_map = {}
    if dollar_volume is not None and len(dollar_volume):
        for key, value in dollar_volume.items():
            if np.isfinite(value):
                volume_map[_as_date(key)] = float(value)
    views: list[DayView] = []
    for day, chunk in frame.groupby(frame.index.date):
        session = _as_date(day)
        if session not in features.index:
            continue
        rth = chunk.between_time(time(9, 30), time(15, 55))
        if rth.empty:
            continue
        minutes = np.array([stamp.hour * 60 + stamp.minute for stamp in rth.index], dtype=int)
        if int(minutes[0]) != OPEN_MINUTE or ENTRY_MINUTE not in set(minutes.tolist()):
            continue
        first = rth.iloc[0]
        entry_at = int(np.where(minutes == ENTRY_MINUTE)[0][0])
        path = rth.iloc[entry_at:]
        path_minutes = minutes[entry_at:]
        row = features.loc[session]
        support = {
            "prior_day": float(row["prior_low"]),
            "swing3": float(row["swing3_low"]),
            "swing5": float(row["swing5_low"]),
            "swing10": float(row["swing10_low"]),
        }
        resistance = {
            "prior_day": float(row["prior_high"]),
            "swing3": float(row["swing3_high"]),
            "swing5": float(row["swing5_high"]),
            "swing10": float(row["swing10_high"]),
        }
        views.append(
            DayView(
                symbol=symbol,
                day=session,
                first_open=float(first["open"]),
                first_high=float(first["high"]),
                first_low=float(first["low"]),
                first_close=float(first["close"]),
                entry_open=float(path["open"].iloc[0]),
                bars_open=path["open"].to_numpy(dtype=float),
                bars_high=path["high"].to_numpy(dtype=float),
                bars_low=path["low"].to_numpy(dtype=float),
                bars_close=path["close"].to_numpy(dtype=float),
                bar_minutes=path_minutes,
                support=support,
                resistance=resistance,
                trend={
                    "ema20": str(row["trend_ema20"]),
                    "ema50": str(row["trend_ema50"]),
                    "structure": str(row["trend_structure"]),
                },
                prior_close=float(row["prior_close"]),
                prior_vwap=float(row["prior_vwap"]),
                atr=float(row["atr"]),
                dollar_volume=float(volume_map.get(session, 0.0)),
            )
        )
    return views


def _positive(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def _target_price(view: DayView, side: str, fill: float, stop: float, exit_name: str) -> float | None:
    risk = abs(fill - stop)
    if exit_name == "eod":
        return None
    if exit_name == "r1":
        raw = fill + risk if side == "long" else fill - risk
    elif exit_name == "r2":
        raw = fill + 2.0 * risk if side == "long" else fill - 2.0 * risk
    elif exit_name == "prior_close":
        raw = view.prior_close
    elif exit_name == "vwap":
        raw = view.prior_vwap
    else:
        return None
    if not _positive(raw):
        return None
    if side == "long" and raw <= fill:
        return None
    if side == "short" and raw >= fill:
        return None
    return float(raw)


def make_signal(view: DayView, cell: Cell) -> dict | None:
    """The open and the first 5-minute close have to agree. Otherwise there is no order."""
    trend = view.trend.get(cell.trend, "flat")
    if cell.mode == "both_support":
        level = view.support.get(cell.level, np.nan)
        if not _positive(level):
            return None
        if trend == "down" and view.first_open < level and view.first_close < view.first_open and view.first_close < level:
            side = "short"
        elif trend == "up" and view.first_open > level and view.first_close > view.first_open and view.first_close > level:
            side = "long"
        else:
            return None
    elif cell.mode == "long_resistance":
        level = view.resistance.get(cell.level, np.nan)
        if not _positive(level) or trend != "up":
            return None
        if not (view.first_open > level and view.first_close > view.first_open and view.first_close > level):
            return None
        side = "long"
    else:
        return None
    if cell.stop == "level":
        stop = float(level)
    elif cell.stop == "candle":
        stop = view.first_high if side == "short" else view.first_low
    else:
        return None
    fill = float(view.entry_open)
    if not _positive(fill) or not _positive(stop):
        return None
    if side == "short" and stop <= fill:
        return None
    if side == "long" and stop >= fill:
        return None
    target = _target_price(view, side, fill, stop, cell.exit)
    if cell.exit != "eod" and target is None:
        return None
    return {
        "symbol": view.symbol,
        "day": view.day,
        "side": side,
        "fill": fill,
        "stop": float(stop),
        "target": target,
        "priority": view.dollar_volume,
        "stop_exits": True,
        "max_bars": None,
        "view": view,
    }


def walk_exit(view: DayView, side: str, stop: float, target: float | None, stop_exits: bool, max_bars: int | None) -> tuple[float, str, int]:
    """Stop wins when a bar can reach both. A gap through the stop fills at that open."""
    last = len(view.bars_open) - 1
    if max_bars is not None:
        last = min(last, max(0, max_bars - 1))
    for index in range(last + 1):
        opened = float(view.bars_open[index])
        high = float(view.bars_high[index])
        low = float(view.bars_low[index])
        closed = float(view.bars_close[index])
        if side == "long":
            hit_stop = stop_exits and low <= stop
            hit_target = target is not None and high >= target
            if hit_stop:
                return (opened if opened <= stop else stop), "stop", index
            if hit_target:
                return (opened if opened >= target else target), "target", index
        else:
            hit_stop = stop_exits and high >= stop
            hit_target = target is not None and low <= target
            if hit_stop:
                return (opened if opened >= stop else stop), "stop", index
            if hit_target:
                return (opened if opened <= target else target), "target", index
        if index == last:
            reason = "eod" if max_bars is None or index == len(view.bars_open) - 1 else "time"
            if max_bars is not None and index < len(view.bars_open) - 1:
                reason = "time"
            return closed, reason, index
    closed = float(view.bars_close[last])
    return closed, "eod", last


def _distance(side: str, fill: float, stop: float) -> tuple[float, float, float]:
    if side == "long":
        entry_px = buy_price(fill, COSTS)
        stop_px = sell_price(stop, COSTS)
        return entry_px, stop_px, entry_px - stop_px
    entry_px = sell_price(fill, COSTS)
    stop_px = buy_price(stop, COSTS)
    return entry_px, stop_px, stop_px - entry_px


def _pnl(side: str, fill: float, exit_raw: float, qty: int) -> tuple[float, float]:
    """Cash locked at entry, and the profit that settles with the exit."""
    if side == "long":
        debit = buy_price(fill, COSTS) * qty + buy_fees(COSTS)
        credit = sell_price(exit_raw, COSTS) * qty - sell_regulatory_fees(sell_price(exit_raw, COSTS), qty, COSTS)
        return debit, credit - debit
    sale = sell_price(fill, COSTS) * qty
    cover = buy_price(exit_raw, COSTS) * qty + buy_fees(COSTS)
    fees = sell_regulatory_fees(sell_price(fill, COSTS), qty, COSTS)
    return sale, sale - cover - fees


def simulate(
    books: dict[str, list[DayView]],
    cell: Cell | None,
    start: date,
    end: date,
    starting: float = 1000.0,
    *,
    allow_holdout: bool = False,
    orders: list[dict] | None = None,
    cap: int | None = None,
) -> dict:
    assert_window_visible(end, allow_holdout=allow_holdout)
    if orders is None:
        if cell is None:
            raise ValueError("a cell or a list of orders is required")
        orders = []
        for views in books.values():
            for view in views:
                if view.day < start or view.day > end:
                    continue
                signal = make_signal(view, cell)
                if signal is not None:
                    orders.append(signal)
    limit = cell.cap if cap is None and cell is not None else (cap if cap is not None else DAILY_CAP)
    by_day: dict[date, list[dict]] = defaultdict(list)
    for order in orders:
        if order["day"] < start or order["day"] > end:
            continue
        by_day[order["day"]].append(order)
    calendar = sorted({view.day for views in books.values() for view in views if start <= view.day <= end})
    settled = float(starting)
    pending: list[tuple[date, float]] = []
    equity_values: list[float] = []
    trades: list[dict] = []
    trade_counts: list[int] = []
    by_symbol: dict[str, dict] = defaultdict(lambda: {"trades": 0, "pnl": 0.0})
    long_trades = 0
    short_trades = 0

    def _equity() -> float:
        return settled + sum(amount for _when, amount in pending)

    for session in calendar:
        still = []
        for when, amount in pending:
            if when <= session:
                settled += amount
            else:
                still.append((when, amount))
        pending = still
        if settled < 0:
            settled = 0.0
        ranked = sorted(by_day.get(session, []), key=lambda row: (-float(row["priority"]), row["symbol"]))
        taken = 0
        exits: list[tuple[float, float]] = []
        mark = _equity()
        for order in ranked:
            if taken >= limit:
                break
            view = order["view"]
            side = order["side"]
            fill = float(order["fill"])
            stop = float(order["stop"])
            entry_px, _stop_px, distance = _distance(side, fill, stop)
            if distance <= 0 or not math.isfinite(distance):
                continue
            risk_dollars = mark * 0.01
            risk_qty = int(math.floor(risk_dollars / distance))
            if side == "long":
                cash_qty = int(math.floor(settled / entry_px)) if entry_px > 0 else 0
                debit_unit = entry_px
            else:
                cover_unit = buy_price(stop, COSTS)
                cash_qty = int(math.floor(settled / cover_unit)) if cover_unit > 0 else 0
                debit_unit = cover_unit
            qty = min(risk_qty, cash_qty)
            if qty < 1:
                continue
            exit_raw, reason, exit_index = walk_exit(
                view, side, stop, order.get("target"), bool(order.get("stop_exits", True)), order.get("max_bars")
            )
            locked, pnl = _pnl(side, fill, exit_raw, qty)
            if side == "short":
                locked = debit_unit * qty
            settled -= locked
            exits.append((locked, pnl))
            taken += 1
            if side == "long":
                long_trades += 1
            else:
                short_trades += 1
            by_symbol[order["symbol"]]["trades"] += 1
            by_symbol[order["symbol"]]["pnl"] += pnl
            minute = int(view.bar_minutes[exit_index])
            trades.append(
                {
                    "symbol": order["symbol"],
                    "day": session,
                    "side": side,
                    "fill": fill,
                    "exit": float(exit_raw),
                    "stop": stop,
                    "target": order.get("target"),
                    "reason": reason,
                    "qty": qty,
                    "debit": locked,
                    "pnl": pnl,
                    "hold_bars": exit_index + 1,
                    "exit_minute": minute,
                    "entry_minute": ENTRY_MINUTE,
                }
            )
        for locked, pnl in exits:
            pending.append((next_trading_day(session), locked + pnl))
        equity_values.append(_equity())
        trade_counts.append(taken)
    if settled < 0:
        settled = 0.0
    index = pd.to_datetime(calendar) if calendar else pd.DatetimeIndex([])
    equity = pd.Series(equity_values, index=index, dtype=float)
    metrics = metrics_from(equity, [row["pnl"] for row in trades], starting)
    pdt = 0
    for index_ in range(4, len(trade_counts)):
        if sum(trade_counts[index_ - 4 : index_ + 1]) > 3:
            pdt += 1
    return {
        "metrics": metrics,
        "trades": trades,
        "equity": equity,
        "day_trades": int(sum(trade_counts)),
        "pdt_windows": pdt,
        "by_symbol": dict(by_symbol),
        "long_trades": long_trades,
        "short_trades": short_trades,
    }


def trade_p_value(returns: list[float]) -> float:
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    count = int(len(values))
    if count < 5:
        return 1.0
    std = float(values.std(ddof=1))
    if std <= 0.0 or not math.isfinite(std):
        return 1.0
    stat = float(values.mean() / (std / math.sqrt(count)))
    if not math.isfinite(stat):
        return 1.0
    return float(0.5 * math.erfc(stat / math.sqrt(2.0)))


def benjamini_hochberg(p_values: list[float]) -> np.ndarray:
    count = len(p_values)
    if count == 0:
        return np.array([])
    order = np.argsort(np.asarray(p_values, dtype=float))
    ranked = np.asarray(p_values, dtype=float)[order]
    adjusted = np.empty(count)
    running = 1.0
    for index in range(count - 1, -1, -1):
        running = min(running, ranked[index] * count / (index + 1))
        adjusted[index] = running
    out = np.empty(count)
    out[order] = np.clip(adjusted, 0.0, 1.0)
    return out


def _window_passes(metrics: dict) -> bool:
    trades = int(metrics.get("trades") or 0)
    if trades < GATE_MIN_TRADES:
        return False
    if float(metrics.get("ending_equity") or 0.0) <= float(metrics.get("starting_equity") or 0.0):
        return False
    if float(metrics.get("sharpe") or 0.0) < GATE_SHARPE:
        return False
    if float(metrics.get("max_drawdown") or 0.0) < GATE_DRAWDOWN:
        return False
    profit_factor = metrics.get("profit_factor")
    if profit_factor is None:
        return float(metrics.get("win_rate") or 0.0) == 1.0
    return float(profit_factor) >= GATE_PF


def _eligible_orders(books: dict[str, list[DayView]], start: date, end: date) -> list[dict]:
    found = []
    for views in books.values():
        for view in views:
            if view.day < start or view.day > end:
                continue
            if not _positive(view.entry_open) or not _positive(view.atr):
                continue
            found.append(view)
    return found


def random_book(books: dict[str, list[DayView]], taken: list[dict], start: date, end: date, cap: int) -> dict:
    """Seed 17, same trade count, same median hold, time exit only. The ATR stop only sizes the share."""
    count = len(taken)
    if count == 0:
        return {"metrics": metrics_from(pd.Series(dtype=float), [], 1000.0), "trades": []}
    hold = max(1, int(np.round(np.median([row["hold_bars"] for row in taken]))))
    pool = _eligible_orders(books, start, end)
    if not pool:
        return {"metrics": metrics_from(pd.Series(dtype=float), [], 1000.0), "trades": []}
    rng = np.random.default_rng(RANDOM_SEED)
    pick = rng.choice(len(pool), size=min(count, len(pool)), replace=False)
    directions = rng.integers(0, 2, size=len(np.atleast_1d(pick)))
    orders = []
    for choice, direction in zip(np.atleast_1d(pick), directions):
        view = pool[int(choice)]
        side = "long" if int(direction) == 0 else "short"
        fill = float(view.entry_open)
        stop = fill - float(view.atr) if side == "long" else fill + float(view.atr)
        if side == "long" and stop >= fill:
            continue
        if side == "short" and stop <= fill:
            continue
        orders.append(
            {
                "symbol": view.symbol,
                "day": view.day,
                "side": side,
                "fill": fill,
                "stop": float(stop),
                "target": None,
                "priority": view.dollar_volume,
                "stop_exits": False,
                "max_bars": hold,
                "view": view,
            }
        )
    return simulate(books, None, start, end, 1000.0, allow_holdout=False, orders=orders, cap=cap)


def _public(metrics: dict) -> dict:
    out = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            out[key] = None if not math.isfinite(value) else value
        else:
            out[key] = value
    return out


def plain_text(cell: Cell) -> str:
    level_name = {
        "prior_day": "the prior day's low" if cell.mode == "both_support" else "the prior day's high",
        "swing3": "the last 3-day swing low" if cell.mode == "both_support" else "the last 3-day swing high",
        "swing5": "the last 5-day swing low" if cell.mode == "both_support" else "the last 5-day swing high",
        "swing10": "the last 10-day swing low" if cell.mode == "both_support" else "the last 10-day swing high",
    }[cell.level]
    trend_name = {
        "ema20": "the daily 20 EMA is sloping that way and price is on that side of it",
        "ema50": "the daily 50 EMA is sloping that way and price is on that side of it",
        "structure": "the last two confirmed swings are higher highs and higher lows, or lower highs and lower lows",
    }[cell.trend]
    stop_name = {
        "level": "the level that was crossed",
        "candle": "the first 5-minute high for a short, or its low for a long",
    }[cell.stop]
    exit_name = {
        "r1": "1R",
        "r2": "2R",
        "prior_close": "the prior close, when that price is on the profit side",
        "vwap": "the prior session VWAP, when that price is on the profit side",
        "eod": "the session close",
    }[cell.exit]
    if cell.mode == "both_support":
        side = (
            f"Go long when the open is above {level_name} in an uptrend, and short when the open is below it in a downtrend."
        )
    else:
        side = f"Go long only when the open is above {level_name} in an uptrend."
    return (
        f"{side} Trend means {trend_name}. The first 5-minute candle has to close in that direction and beyond the level. "
        f"Buy or sell the 09:35 open. Stop is {stop_name}. Target is {exit_name}. Flat by the 15:55 close. "
        f"At most {cell.cap} new entries a day."
    )


def _score_cell(books: dict[str, list[DayView]], cell: Cell) -> dict:
    train = simulate(books, cell, TRAIN_START, TRAIN_END, 1000.0)
    train_5k = simulate(books, cell, TRAIN_START, TRAIN_END, 5000.0)
    random = random_book(books, train["trades"], TRAIN_START, TRAIN_END, cell.cap)
    returns = [row["pnl"] / row["debit"] for row in train["trades"] if row["debit"] > 0]
    return {
        "id": cell.id,
        "mode": cell.mode,
        "level": cell.level,
        "trend": cell.trend,
        "stop": cell.stop,
        "exit": cell.exit,
        "cap": cell.cap,
        "plain": plain_text(cell),
        "train": _public(train["metrics"]),
        "train_5k": _public(train_5k["metrics"]),
        "train_pass": _window_passes(train["metrics"]),
        "random_sharpe": float(random["metrics"]["sharpe"]),
        "random_trades": int(random["metrics"]["trades"]),
        "p": trade_p_value(returns),
        "q": None,
        "dsr": None,
        "survivor": False,
        "long_trades": train["long_trades"],
        "short_trades": train["short_trades"],
        "day_trades_1k": train["day_trades"],
        "pdt_windows_1k": train["pdt_windows"],
        "by_symbol": {
            symbol: {"trades": bucket["trades"], "pnl": bucket["pnl"]}
            for symbol, bucket in sorted(train["by_symbol"].items())
        },
        "_train_book": train,
        "_train_5k_book": train_5k,
    }


def run_search(books: dict[str, list[DayView]]) -> dict:
    rows = []
    for cell in CATALOG:
        print(f"train {cell.id}", flush=True)
        rows.append(_score_cell(books, cell))
    p_values = [row["p"] for row in rows]
    q_values = benjamini_hochberg(p_values)
    for row, q_value in zip(rows, q_values):
        row["q"] = float(q_value)
        book = row["_train_book"]
        dsr = deflated_sharpe(_daily_returns(book["equity"], 1000.0), len(CATALOG))
        row["dsr"] = dsr.get("dsr")
        beats = float(row["train"]["sharpe"]) > float(row["random_sharpe"])
        row["survivor"] = bool(row["train_pass"] and row["q"] <= FDR_Q and (row["dsr"] or 0.0) >= DSR_MIN and beats)
    survivors = [row["id"] for row in rows if row["survivor"]]
    return {
        "n_combos": len(CATALOG),
        "cells": rows,
        "survivor_ids": survivors,
        "rules": frozen_rules(),
    }


def _daily_returns(equity: pd.Series, starting: float) -> np.ndarray:
    if equity is None or len(equity) == 0:
        return np.array([])
    curve = pd.concat([pd.Series([starting], index=[equity.index[0] - pd.Timedelta(days=1)]), equity.astype(float)])
    returns = curve.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    return returns.to_numpy(dtype=float)


def _best_train_id(search: dict) -> str | None:
    daily = [row for row in search["cells"] if row["train"]["trades"] > 0]
    if not daily:
        daily = list(search["cells"])
    if not daily:
        return None
    ranked = sorted(
        daily,
        key=lambda row: (
            -float(row["train"]["sharpe"]),
            -float(row["train"]["profit_factor"] or 0.0),
            -int(row["train"]["trades"]),
            row["id"],
        ),
    )
    return ranked[0]["id"]


def score_holdout(books: dict[str, list[DayView]], search: dict) -> dict:
    """One look. Passers if any, otherwise the single best training Sharpe."""
    ids = list(search["survivor_ids"]) or ([chosen] if (chosen := _best_train_id(search)) else [])
    rows = []
    for cell_id in ids:
        cell = CATALOG_BY_ID[cell_id]
        book = simulate(books, cell, HOLDOUT_START, HOLDOUT_END, 1000.0, allow_holdout=True)
        book_5k = simulate(books, cell, HOLDOUT_START, HOLDOUT_END, 5000.0, allow_holdout=True)
        rows.append(
            {
                "id": cell_id,
                "metrics_1k": _public(book["metrics"]),
                "metrics_5k": _public(book_5k["metrics"]),
                "long_trades": book["long_trades"],
                "short_trades": book["short_trades"],
                "by_symbol": book["by_symbol"],
                "_book": book,
                "_book_5k": book_5k,
            }
        )
    return {
        "rows": rows,
        "labeled_non_survivor": not search["survivor_ids"],
    }


def _vix_on(vix: dict[date, float], day: date) -> float | None:
    cursor = day
    for _ in range(10):
        cursor = date.fromordinal(cursor.toordinal() - 1)
        value = vix.get(cursor)
        if value is not None and np.isfinite(value) and value > 0:
            return float(value)
    return None


def _years_left(minute: int, dte: int) -> float:
    remain = max(0, CLOSE_MINUTE - minute)
    return (dte + remain / (24.0 * 60.0)) / 365.25


def option_report(trades: list[dict], vix: dict[date, float], starting: float, dte: int) -> dict:
    """One contract. Model price, prior close of VIX, not a listed fill."""
    settled = float(starting)
    pending: list[tuple[date, float]] = []
    pnl = 0.0
    filled = 0
    skipped = 0
    last_day = None
    for trade in trades:
        session = trade["day"]
        if last_day != session:
            still = []
            for when, amount in pending:
                if when <= session:
                    settled += amount
                else:
                    still.append((when, amount))
            pending = still
            last_day = session
        sigma_points = _vix_on(vix, session)
        if sigma_points is None:
            skipped += 1
            continue
        sigma = sigma_points / 100.0
        right = "call" if trade["side"] == "long" else "put"
        strike = listed_strike(float(trade["fill"]), float(trade["fill"]))
        entry_t = _years_left(int(trade["entry_minute"]), dte)
        exit_clock = min(CLOSE_MINUTE, int(trade["exit_minute"]) + 5)
        exit_t = _years_left(exit_clock, dte)
        mid_entry = option_price(right, float(trade["fill"]), strike, entry_t, sigma, OPTION_RATE, OPTION_DIVIDEND)
        mid_exit = option_price(right, float(trade["exit"]), strike, exit_t, sigma, OPTION_RATE, OPTION_DIVIDEND)
        if not math.isfinite(mid_entry) or mid_entry <= 0:
            skipped += 1
            continue
        half_entry = max(0.01, 0.015 * mid_entry)
        half_exit = max(0.01, 0.015 * max(mid_exit, 0.0))
        ask = mid_entry + half_entry
        bid = max(0.0, mid_exit - half_exit)
        debit = ask * 100.0 + option_leg_fees(1, ask, sell=False)
        credit = bid * 100.0 - option_leg_fees(1, bid, sell=True)
        if debit > settled:
            skipped += 1
            continue
        settled -= debit
        trade_pnl = credit - debit
        pnl += trade_pnl
        filled += 1
        pending.append((next_trading_day(session), debit + trade_pnl))
    ending = settled + sum(amount for _when, amount in pending)
    return {
        "applicable": True,
        "trades": filled,
        "skipped": skipped,
        "pnl": pnl,
        "ending": ending,
        "dte": dte,
    }


def buy_and_hold(views: list[DayView], start: date, end: date, starting: float, *, allow_holdout: bool = False) -> dict:
    assert_window_visible(end, allow_holdout=allow_holdout)
    window = [view for view in views if start <= view.day <= end]
    if not window:
        return {"metrics": metrics_from(pd.Series(dtype=float), [], starting), "ending_equity": starting}
    first = window[0]
    last = window[-1]
    fill = float(first.first_open)
    exit_raw = float(last.bars_close[-1])
    entry_px = buy_price(fill, COSTS)
    qty = int(math.floor(starting / entry_px)) if entry_px > 0 else 0
    if qty < 1:
        equity = pd.Series([starting, starting], index=pd.to_datetime([first.day, last.day]))
        return {"metrics": metrics_from(equity, [], starting)}
    debit = entry_px * qty + buy_fees(COSTS)
    credit = sell_price(exit_raw, COSTS) * qty - sell_regulatory_fees(sell_price(exit_raw, COSTS), qty, COSTS)
    pnl = credit - debit
    # Mark the whole window as one position so the Sharpe is the path of the close, scaled.
    closes = []
    days = []
    cash_left = starting - debit
    for index, view in enumerate(window):
        spot = float(view.bars_close[-1])
        mark = cash_left + spot * qty
        if index == len(window) - 1:
            mark = cash_left + credit
        closes.append(mark)
        days.append(view.day)
    equity = pd.Series(closes, index=pd.to_datetime(days))
    metrics = metrics_from(equity, [pnl], starting)
    return {"metrics": metrics}


def strip_private(search: dict, holdout: dict) -> tuple[dict, dict]:
    """Drop equity curves and trade lists before writing JSON."""
    cells = []
    for row in search["cells"]:
        clean = {key: value for key, value in row.items() if not key.startswith("_")}
        cells.append(clean)
    public_search = {key: value for key, value in search.items() if key != "cells"}
    public_search["cells"] = cells
    rows = []
    for row in holdout["rows"]:
        rows.append({key: value for key, value in row.items() if not key.startswith("_")})
    public_holdout = {"rows": rows, "labeled_non_survivor": holdout["labeled_non_survivor"]}
    return public_search, public_holdout
