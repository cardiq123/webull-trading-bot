"""Per-stock dip and rip tendencies. Research only.

Event definitions, horizons, and the trade template are frozen. The holdout
is not used to add or drop an event. Nothing here places an order.
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
from webull_bot.indicators import rsi, sma
from webull_bot.options.fees import option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price

TRAIN_START = date(2018, 1, 1)
TRAIN_END = date(2026, 7, 6)
HOLDOUT_START = date(2026, 7, 7)
HOLDOUT_END = date(2026, 10, 6)
FDR_Q = 0.10
MIN_EVENTS = 30
HOLDOUT_MIN_EVENTS = 10
RANDOM_SEED = 17
DAILY_CAP = 3
COSTS = CostModel()

SYMBOLS = (
    "UNH",
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
    "JPM",
    "LLY",
    "COST",
    "XOM",
    "NFLX",
)
# Only these intraday tapes reach 2018. Yahoo's 5-minute file is a short sample.
INTRADAY_GATE = ("SPY", "QQQ")
INTRADAY_HORIZONS = ("m30", "m60", "eod", "d1", "d3", "d5")
DAILY_HORIZONS = ("d1", "d3", "d5")
DAILY_EVENTS = ("vwap_dip", "vwap_rip", "rsi_dip", "rsi_rip", "gap_dip", "gap_rip", "multi_dip", "multi_rip")
INTRADAY_EVENTS = (
    "vwap_dip",
    "vwap_rip",
    "rsi_dip",
    "rsi_rip",
    "atr1_dip",
    "atr1_rip",
    "atr15_dip",
    "atr15_rip",
    "gap_dip",
    "gap_rip",
)


def frozen_rules() -> dict:
    return {
        "train": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
        "holdout": [HOLDOUT_START.isoformat(), HOLDOUT_END.isoformat()],
        "symbols": list(SYMBOLS),
        "intraday_gate": list(INTRADAY_GATE),
        "fdr_q": FDR_Q,
        "min_events": MIN_EVENTS,
        "events": {
            "vwap": "Close outside a 2 SD band. Intraday band is the session VWAP. Daily band is the 20-day volume-weighted average.",
            "rsi": "RSI(14) below 30 or above 70.",
            "atr": "Intraday only. Close is at least 1.0 or 1.5 prior-day ATRs off the session high or low.",
            "gap": "Open is at least 1 prior-day ATR through the prior close.",
            "multi": "Daily only. Three-session move of at least 1.5 prior ATRs.",
        },
        "horizons": {"intraday": list(INTRADAY_HORIZONS), "daily": list(DAILY_HORIZONS)},
        "trade": "Next-bar confirmation, stop beyond the event extreme, target the mean, flat at the session close or after 3 daily bars.",
    }


def assert_window_visible(end: date, allow_holdout: bool = False) -> None:
    if not allow_holdout and end >= HOLDOUT_START:
        raise RuntimeError(f"window reaches the holdout {end.isoformat()}")


def n_trials(intraday_symbols: tuple[str, ...] = INTRADAY_GATE) -> int:
    daily = len(SYMBOLS) * len(DAILY_EVENTS) * len(DAILY_HORIZONS)
    intraday = len(intraday_symbols) * 2 * len(INTRADAY_EVENTS) * len(INTRADAY_HORIZONS)
    return daily + intraday


def _as_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, pd.Timestamp):
        return value
    return pd.Timestamp(value).date()


def _edge(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    out[1:] &= ~mask[:-1]
    return out


def _session_vwap(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    vwap = np.full(len(frame), np.nan)
    width = np.full(len(frame), np.nan)
    if frame.empty:
        return vwap, width
    typical = ((frame["high"] + frame["low"] + frame["close"]) / 3.0).to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float)
    volume = np.where(np.isfinite(volume) & (volume > 0), volume, 1.0)
    dates = frame.index.date
    start = 0
    while start < len(frame):
        stop = start + 1
        while stop < len(frame) and dates[stop] == dates[start]:
            stop += 1
        tp = typical[start:stop]
        vol = volume[start:stop]
        total = np.cumsum(vol)
        average = np.cumsum(tp * vol) / total
        # Population second moment, known at this bar's close.
        mean = np.cumsum(tp) / np.arange(1, len(tp) + 1)
        second = np.cumsum(tp * tp) / np.arange(1, len(tp) + 1)
        var = np.maximum(second - mean * mean, 0.0)
        band = np.sqrt(var)
        band[:4] = np.nan
        average[:4] = np.nan
        vwap[start:stop] = average
        width[start:stop] = band
        start = stop
    return vwap, width


def prepare(frame: pd.DataFrame, daily: pd.DataFrame, timeframe: str) -> pd.DataFrame | None:
    """Columns on each bar are known at that bar's close. The fill, if any, is the next bar."""
    if frame is None or frame.empty or daily is None or daily.empty:
        return None
    out = frame.sort_index().copy()
    out = out[~out.index.duplicated(keep="last")]
    daily_frame = daily.sort_index().copy()
    daily_frame.index = [_as_date(value) for value in daily_frame.index]
    daily_frame = daily_frame[~daily_frame.index.duplicated(keep="last")]
    close = out["close"].astype(float)
    out["rsi"] = rsi(close, 14).to_numpy(dtype=float)
    out["sma20"] = sma(close, 20).to_numpy(dtype=float)
    out.attrs["timeframe"] = timeframe
    if timeframe == "1d":
        volume = out["volume"].astype(float)
        out["vwap"] = ((close * volume).rolling(20, min_periods=20).sum() / volume.rolling(20, min_periods=20).sum()).to_numpy()
        out["band"] = close.rolling(20, min_periods=20).std(ddof=0).to_numpy()
    else:
        vwap, width = _session_vwap(out)
        out["vwap"] = vwap
        out["band"] = width
    atr_values = wilder_atr(daily_frame, 14)
    prior_atr = atr_values.shift(1)
    prior_close = daily_frame["close"].astype(float).shift(1)
    session_dates = [_as_date(value) for value in out.index]
    out["session"] = session_dates
    out["prior_atr"] = prior_atr.reindex(session_dates).to_numpy(dtype=float)
    out["prior_close"] = prior_close.reindex(session_dates).to_numpy(dtype=float)
    if timeframe == "1d":
        out["run_high"] = out["high"].to_numpy(dtype=float)
        out["run_low"] = out["low"].to_numpy(dtype=float)
        out["is_first"] = np.ones(len(out), dtype=bool)
    else:
        high = out["high"].to_numpy(dtype=float)
        low = out["low"].to_numpy(dtype=float)
        run_high = np.empty(len(out))
        run_low = np.empty(len(out))
        first = np.zeros(len(out), dtype=bool)
        start = 0
        dates = out.index.date
        while start < len(out):
            stop = start + 1
            while stop < len(out) and dates[stop] == dates[start]:
                stop += 1
            run_high[start:stop] = np.maximum.accumulate(high[start:stop])
            run_low[start:stop] = np.minimum.accumulate(low[start:stop])
            first[start] = True
            start = stop
        out["run_high"] = run_high
        out["run_low"] = run_low
        out["is_first"] = first
    move3 = close.to_numpy(dtype=float) - close.shift(3).to_numpy(dtype=float)
    out["move3"] = move3
    return out


def event_mask(frame: pd.DataFrame, name: str) -> np.ndarray:
    close = frame["close"].to_numpy(dtype=float)
    vwap = frame["vwap"].to_numpy(dtype=float)
    band = frame["band"].to_numpy(dtype=float)
    rsi_values = frame["rsi"].to_numpy(dtype=float)
    prior_atr = frame["prior_atr"].to_numpy(dtype=float)
    prior_close = frame["prior_close"].to_numpy(dtype=float)
    opened = frame["open"].to_numpy(dtype=float)
    finite_band = np.isfinite(vwap) & np.isfinite(band) & (band > 0)
    if name == "vwap_dip":
        raw = finite_band & (close < vwap - 2.0 * band)
    elif name == "vwap_rip":
        raw = finite_band & (close > vwap + 2.0 * band)
    elif name == "rsi_dip":
        raw = np.isfinite(rsi_values) & (rsi_values < 30.0)
    elif name == "rsi_rip":
        raw = np.isfinite(rsi_values) & (rsi_values > 70.0)
    elif name in {"atr1_dip", "atr15_dip"}:
        multiple = 1.0 if name == "atr1_dip" else 1.5
        raw = np.isfinite(prior_atr) & (prior_atr > 0) & ((frame["run_high"].to_numpy(dtype=float) - close) >= multiple * prior_atr)
    elif name in {"atr1_rip", "atr15_rip"}:
        multiple = 1.0 if name == "atr1_rip" else 1.5
        raw = np.isfinite(prior_atr) & (prior_atr > 0) & ((close - frame["run_low"].to_numpy(dtype=float)) >= multiple * prior_atr)
    elif name == "gap_dip":
        raw = frame["is_first"].to_numpy(dtype=bool) & np.isfinite(prior_atr) & np.isfinite(prior_close) & ((opened - prior_close) <= -prior_atr)
    elif name == "gap_rip":
        raw = frame["is_first"].to_numpy(dtype=bool) & np.isfinite(prior_atr) & np.isfinite(prior_close) & ((opened - prior_close) >= prior_atr)
    elif name == "multi_dip":
        raw = np.isfinite(frame["move3"].to_numpy(dtype=float)) & np.isfinite(prior_atr) & (frame["move3"].to_numpy(dtype=float) <= -1.5 * prior_atr)
    elif name == "multi_rip":
        raw = np.isfinite(frame["move3"].to_numpy(dtype=float)) & np.isfinite(prior_atr) & (frame["move3"].to_numpy(dtype=float) >= 1.5 * prior_atr)
    else:
        raise KeyError(name)
    return _edge(raw)


def _forward_indexes(frame: pd.DataFrame, horizon: str, timeframe: str) -> np.ndarray:
    """Bar index used for the forward close. -1 when the horizon leaves the series or the session."""
    count = len(frame)
    out = np.full(count, -1, dtype=int)
    dates = [_as_date(value) for value in frame.index]
    by_date: dict[date, list[int]] = defaultdict(list)
    for index, session in enumerate(dates):
        by_date[session].append(index)
    sessions = list(by_date.keys())
    position = {session: index for index, session in enumerate(sessions)}
    if horizon in {"m30", "m60"}:
        step = (6 if horizon == "m30" else 12) if timeframe == "5m" else (2 if horizon == "m30" else 4)
        for index in range(count):
            nxt = index + step
            if nxt < count and dates[nxt] == dates[index]:
                out[index] = nxt
        return out
    if horizon == "eod":
        for indexes in by_date.values():
            last = indexes[-1]
            for index in indexes:
                if index != last:
                    out[index] = last
        return out
    step = {"d1": 1, "d3": 3, "d5": 5}[horizon]
    for session, indexes in by_date.items():
        nxt = position[session] + step
        if nxt >= len(sessions):
            continue
        target = by_date[sessions[nxt]][-1]
        for index in indexes:
            out[index] = target
    return out


def _excursions(frame: pd.DataFrame, event_at: int, destination: int, side: str) -> tuple[float, float, int | None]:
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    vwap = frame["vwap"].to_numpy(dtype=float)
    window_high = float(np.nanmax(high[event_at : destination + 1]))
    window_low = float(np.nanmin(low[event_at : destination + 1]))
    anchor = float(close[event_at])
    if side == "dip":
        favorable = window_high - anchor
        adverse = anchor - window_low
    else:
        favorable = anchor - window_low
        adverse = window_high - anchor
    touched = None
    level = float(vwap[event_at]) if np.isfinite(vwap[event_at]) else float("nan")
    if np.isfinite(level):
        for step in range(event_at + 1, destination + 1):
            if side == "dip" and high[step] >= level:
                touched = step - event_at
                break
            if side == "rip" and low[step] <= level:
                touched = step - event_at
                break
    return favorable, adverse, touched


def _side(name: str) -> str:
    return "dip" if name.endswith("_dip") else "rip"


def _window_indexes(frame: pd.DataFrame, mask: np.ndarray, horizon: str, start: date, end: date) -> tuple[np.ndarray, np.ndarray]:
    """Events whose signal and horizon both sit inside the window."""
    forward = _forward_indexes(frame, horizon, frame.attrs.get("timeframe", "1d"))
    dates = [_as_date(value) for value in frame.index]
    chosen = []
    destinations = []
    for index in np.flatnonzero(mask):
        destination = int(forward[index])
        if destination < 0:
            continue
        signal_day = dates[index]
        horizon_day = dates[destination]
        if signal_day < start or horizon_day > end:
            continue
        chosen.append(int(index))
        destinations.append(destination)
    return np.asarray(chosen, dtype=int), np.asarray(destinations, dtype=int)


def _returns(frame: pd.DataFrame, indexes: np.ndarray, destinations: np.ndarray) -> np.ndarray:
    close = frame["close"].to_numpy(dtype=float)
    if len(indexes) == 0:
        return np.array([])
    base = close[indexes]
    future = close[destinations]
    with np.errstate(divide="ignore", invalid="ignore"):
        returns = future / base - 1.0
    return returns[np.isfinite(returns)]


def _matched_random(frame: pd.DataFrame, indexes: np.ndarray, horizon: str, start: date, end: date, side: str) -> np.ndarray:
    if len(indexes) == 0:
        return np.array([])
    forward = _forward_indexes(frame, horizon, frame.attrs.get("timeframe", "1d"))
    dates = [_as_date(value) for value in frame.index]
    minutes = np.array([stamp.hour * 60 + stamp.minute for stamp in frame.index], dtype=int)
    eligible = []
    for index in range(len(frame)):
        destination = int(forward[index])
        if destination < 0:
            continue
        if dates[index] < start or dates[destination] > end:
            continue
        eligible.append(index)
    if len(eligible) < MIN_EVENTS:
        return np.array([])
    eligible = np.asarray(eligible, dtype=int)
    rng = np.random.default_rng(RANDOM_SEED)
    # Match the clock. Daily bars share one bucket.
    buckets: dict[int, list[int]] = defaultdict(list)
    for index in eligible:
        buckets[int(minutes[index])].append(int(index))
    picked = []
    for index in indexes:
        pool = buckets.get(int(minutes[index]), [])
        if not pool:
            pool = eligible.tolist()
        picked.append(int(pool[int(rng.integers(0, len(pool)))]))
    picked_arr = np.asarray(picked, dtype=int)
    destinations = forward[picked_arr]
    returns = _returns(frame, picked_arr, destinations)
    if side == "rip":
        returns = -returns
    return returns


def welch_p(event_returns: np.ndarray, random_returns: np.ndarray) -> float:
    left = np.asarray(event_returns, dtype=float)
    right = np.asarray(random_returns, dtype=float)
    left = left[np.isfinite(left)]
    right = right[np.isfinite(right)]
    if len(left) < MIN_EVENTS or len(right) < MIN_EVENTS:
        return 1.0
    left_var = float(left.var(ddof=1))
    right_var = float(right.var(ddof=1))
    scale = left_var / len(left) + right_var / len(right)
    if scale <= 0 or not math.isfinite(scale):
        return 1.0
    stat = (float(left.mean()) - float(right.mean())) / math.sqrt(scale)
    if not math.isfinite(stat):
        return 1.0
    return float(math.erfc(abs(stat) / math.sqrt(2.0)))


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


def _summarize(frame: pd.DataFrame, name: str, horizon: str, start: date, end: date) -> dict:
    side = _side(name)
    mask = event_mask(frame, name)
    indexes, destinations = _window_indexes(frame, mask, horizon, start, end)
    raw = _returns(frame, indexes, destinations)
    signed = raw if side == "dip" else -raw
    random_signed = _matched_random(frame, indexes, horizon, start, end, side)
    reversal = float(np.mean(signed > 0)) if len(signed) else 0.0
    random_reversal = float(np.mean(random_signed > 0)) if len(random_signed) else 0.0
    favorable = []
    adverse = []
    touches = []
    for index, destination in zip(indexes, destinations):
        mfe, mae, touched = _excursions(frame, int(index), int(destination), side)
        favorable.append(mfe)
        adverse.append(mae)
        if touched is not None:
            touches.append(touched)
    return {
        "n": int(len(signed)),
        "mean_signed": float(np.mean(signed)) if len(signed) else 0.0,
        "reversal": reversal,
        "random_reversal": random_reversal,
        "random_mean": float(np.mean(random_signed)) if len(random_signed) else 0.0,
        "p": welch_p(signed, random_signed),
        "mfe": float(np.mean(favorable)) if favorable else 0.0,
        "mae": float(np.mean(adverse)) if adverse else 0.0,
        "touch_rate": float(len(touches) / len(signed)) if len(signed) else 0.0,
        "median_touch": float(np.median(touches)) if touches else None,
    }


def _cells(intraday_symbols: tuple[str, ...]) -> list[tuple[str, str, str, str]]:
    cells = []
    for symbol in SYMBOLS:
        for event in DAILY_EVENTS:
            for horizon in DAILY_HORIZONS:
                cells.append((symbol, "1d", event, horizon))
    for symbol in intraday_symbols:
        for timeframe in ("5m", "15m"):
            for event in INTRADAY_EVENTS:
                for horizon in INTRADAY_HORIZONS:
                    cells.append((symbol, timeframe, event, horizon))
    return cells


def run_search(prepared: dict[str, dict[str, pd.DataFrame]], intraday_symbols: tuple[str, ...] = INTRADAY_GATE) -> dict:
    """Train statistics only. ``prepared`` maps symbol to timeframe to frame."""
    assert_window_visible(TRAIN_END, allow_holdout=False)
    cells = _cells(intraday_symbols)
    rows = []
    for number, (symbol, timeframe, event, horizon) in enumerate(cells, start=1):
        if number == 1 or number % 100 == 0:
            print(f"train {number}/{len(cells)} {symbol} {timeframe} {event} {horizon}", flush=True)
        frame = prepared.get(symbol, {}).get(timeframe)
        if frame is None:
            summary = {"n": 0, "mean_signed": 0.0, "reversal": 0.0, "random_reversal": 0.0, "random_mean": 0.0, "p": 1.0, "mfe": 0.0, "mae": 0.0, "touch_rate": 0.0, "median_touch": None}
        else:
            summary = _summarize(frame, event, horizon, TRAIN_START, TRAIN_END)
        rows.append(
            {
                "id": f"{symbol}_{timeframe}_{event}_{horizon}",
                "symbol": symbol,
                "timeframe": timeframe,
                "event": event,
                "horizon": horizon,
                "side": _side(event),
                **summary,
                "q": None,
                "label": "inconsistent",
            }
        )
    q_values = benjamini_hochberg([row["p"] for row in rows])
    for row, q_value in zip(rows, q_values):
        row["q"] = float(q_value)
        enough = row["n"] >= MIN_EVENTS and row["q"] <= FDR_Q
        beats = row["mean_signed"] > row["random_mean"] and row["reversal"] > row["random_reversal"]
        fades = row["mean_signed"] < row["random_mean"] and (1.0 - row["reversal"]) > (1.0 - row["random_reversal"])
        if enough and row["mean_signed"] > 0 and beats:
            row["label"] = "mean-reverting"
        elif enough and row["mean_signed"] < 0 and fades:
            row["label"] = "trending"
        else:
            row["label"] = "inconsistent"
    return {"n_combos": len(rows), "cells": rows}


def score_holdout(prepared: dict[str, dict[str, pd.DataFrame]], search: dict) -> dict:
    """One confirmation pass. The label is not refit."""
    confirmed = []
    for row in search["cells"]:
        if row["label"] == "inconsistent":
            row["holdout_n"] = None
            row["holdout_mean_signed"] = None
            row["confirmed"] = False
            continue
        frame = prepared.get(row["symbol"], {}).get(row["timeframe"])
        if frame is None:
            summary = {"n": 0, "mean_signed": 0.0}
        else:
            summary = _summarize(frame, row["event"], row["horizon"], HOLDOUT_START, HOLDOUT_END)
        row["holdout_n"] = summary["n"]
        row["holdout_mean_signed"] = summary["mean_signed"]
        same_sign = summary["n"] >= HOLDOUT_MIN_EVENTS and summary["mean_signed"] * row["mean_signed"] > 0
        row["confirmed"] = bool(same_sign)
        if row["confirmed"]:
            confirmed.append(row["id"])
    return {"confirmed_ids": confirmed}


def short_sample(frame: pd.DataFrame, symbol: str, timeframe: str) -> list[dict]:
    """Yahoo intraday has no 2018 train. These rows are not trials."""
    if frame is None or frame.empty:
        return []
    days = sorted({_as_date(value) for value in frame.index})
    if not days:
        return []
    start, end = days[0], min(days[-1], HOLDOUT_END)
    rows = []
    events = INTRADAY_EVENTS if timeframe != "1d" else DAILY_EVENTS
    horizons = INTRADAY_HORIZONS if timeframe != "1d" else DAILY_HORIZONS
    for event in events:
        for horizon in horizons:
            summary = _summarize(frame, event, horizon, start, end)
            rows.append(
                {
                    "id": f"{symbol}_{timeframe}_{event}_{horizon}",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "event": event,
                    "horizon": horizon,
                    "side": _side(event),
                    "label": "short-sample",
                    "q": None,
                    "confirmed": False,
                    **summary,
                }
            )
    return rows


@dataclass
class _Order:
    day: date
    fill_index: int
    side: str
    fill: float
    stop: float
    target: float


def _trade_orders(frame: pd.DataFrame, event: str) -> list[_Order]:
    """Confirmation candle, then the next open. Stop is the event extreme."""
    mask = event_mask(frame, event)
    side = _side(event)
    close = frame["close"].to_numpy(dtype=float)
    opened = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    mean = frame["vwap"].to_numpy(dtype=float)
    sma20 = frame["sma20"].to_numpy(dtype=float)
    dates = [_as_date(value) for value in frame.index]
    orders = []
    for index in np.flatnonzero(mask):
        confirm = int(index) + 1
        fill_index = int(index) + 2
        if fill_index >= len(frame):
            continue
        if frame.attrs.get("timeframe") != "1d" and (dates[confirm] != dates[index] or dates[fill_index] != dates[index]):
            continue
        if side == "dip":
            if not (close[confirm] > opened[confirm] and close[confirm] > close[index]):
                continue
            stop = float(low[index])
            if opened[fill_index] <= stop:
                continue
        else:
            if not (close[confirm] < opened[confirm] and close[confirm] < close[index]):
                continue
            stop = float(high[index])
            if opened[fill_index] >= stop:
                continue
        target = float(mean[index]) if np.isfinite(mean[index]) else float(sma20[index])
        fill = float(opened[fill_index])
        if not np.isfinite(target) or target <= 0 or fill <= 0:
            continue
        if side == "dip" and target <= fill:
            continue
        if side == "rip" and target >= fill:
            continue
        orders.append(_Order(dates[fill_index], fill_index, "long" if side == "dip" else "short", fill, stop, target))
    return orders


def _walk_trade(frame: pd.DataFrame, order: _Order, timeframe: str) -> tuple[float, str, int] | None:
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    opened = frame["open"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    dates = [_as_date(value) for value in frame.index]
    last = len(frame) - 1
    if timeframe == "1d":
        last = min(last, order.fill_index + 2)
    else:
        for index in range(order.fill_index, len(frame)):
            if dates[index] != order.day:
                last = index - 1
                break
            last = index
    if last < order.fill_index:
        return None
    for index in range(order.fill_index, last + 1):
        if order.side == "long":
            if low[index] <= order.stop:
                raw = opened[index] if opened[index] <= order.stop else order.stop
                return float(raw), "stop", index
            if high[index] >= order.target:
                raw = opened[index] if opened[index] >= order.target else order.target
                return float(raw), "target", index
        else:
            if high[index] >= order.stop:
                raw = opened[index] if opened[index] >= order.stop else order.stop
                return float(raw), "stop", index
            if low[index] <= order.target:
                raw = opened[index] if opened[index] <= order.target else order.target
                return float(raw), "target", index
        if index == last:
            return float(close[index]), "time", index
    return None


def simulate_trades(frame: pd.DataFrame, event: str, start: date, end: date, starting: float, timeframe: str, *, allow_holdout: bool = False) -> dict:
    assert_window_visible(end, allow_holdout=allow_holdout)
    orders = [order for order in _trade_orders(frame, event) if start <= order.day <= end]
    by_day: dict[date, list[_Order]] = defaultdict(list)
    for order in orders:
        by_day[order.day].append(order)
    calendar = sorted({_as_date(value) for value in frame.index if start <= _as_date(value) <= end})
    settled = float(starting)
    pending: list[tuple[date, float]] = []
    equity_values = []
    pnls = []
    taken_days = []
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
        used = 0
        mark = settled + sum(amount for _when, amount in pending)
        for order in by_day.get(session, []):
            if used >= DAILY_CAP:
                break
            walked = _walk_trade(frame, order, timeframe)
            if walked is None:
                continue
            exit_raw, reason, _index = walked
            if order.side == "long":
                entry_px = buy_price(order.fill, COSTS)
                stop_px = sell_price(order.stop, COSTS)
                distance = entry_px - stop_px
                cash_unit = entry_px
            else:
                entry_px = sell_price(order.fill, COSTS)
                stop_px = buy_price(order.stop, COSTS)
                distance = stop_px - entry_px
                cash_unit = stop_px
            if distance <= 0 or cash_unit <= 0:
                continue
            qty = min(int(math.floor(mark * 0.01 / distance)), int(math.floor(settled / cash_unit)))
            if qty < 1:
                continue
            if order.side == "long":
                debit = entry_px * qty + buy_fees(COSTS)
                credit = sell_price(exit_raw, COSTS) * qty - sell_regulatory_fees(sell_price(exit_raw, COSTS), qty, COSTS)
                pnl = credit - debit
                locked = debit
            else:
                sale = entry_px * qty
                cover = buy_price(exit_raw, COSTS) * qty + buy_fees(COSTS)
                fees = sell_regulatory_fees(entry_px, qty, COSTS)
                pnl = sale - cover - fees
                locked = cash_unit * qty
            settled -= locked
            pending.append((next_trading_day(session), locked + pnl))
            pnls.append(pnl)
            taken_days.append(session)
            used += 1
        equity_values.append(settled + sum(amount for _when, amount in pending))
    equity = pd.Series(equity_values, index=pd.to_datetime(calendar), dtype=float) if calendar else pd.Series(dtype=float)
    return {"metrics": metrics_from(equity, pnls, starting), "pnls": pnls, "days": taken_days, "equity": equity}


def trade_books(prepared: dict[str, dict[str, pd.DataFrame]], search: dict) -> list[dict]:
    """One template per passing symbol, timeframe, and event. Horizons are not extra trades."""
    chosen: dict[tuple[str, str, str], dict] = {}
    for row in search["cells"]:
        if row["label"] != "mean-reverting":
            continue
        key = (row["symbol"], row["timeframe"], row["event"])
        current = chosen.get(key)
        if current is None or row["q"] < current["q"]:
            chosen[key] = row
    books = []
    for row in chosen.values():
        frame = prepared[row["symbol"]][row["timeframe"]]
        train = simulate_trades(frame, row["event"], TRAIN_START, TRAIN_END, 1000.0, row["timeframe"])
        train_5k = simulate_trades(frame, row["event"], TRAIN_START, TRAIN_END, 5000.0, row["timeframe"])
        hold = simulate_trades(frame, row["event"], HOLDOUT_START, HOLDOUT_END, 1000.0, row["timeframe"], allow_holdout=True)
        hold_5k = simulate_trades(frame, row["event"], HOLDOUT_START, HOLDOUT_END, 5000.0, row["timeframe"], allow_holdout=True)
        returns = []
        # p-value uses the training share returns. The holdout is the confirmation.
        debit = 1.0
        returns = [pnl / debit for pnl in train["pnls"]]
        books.append(
            {
                "id": f"{row['symbol']}_{row['timeframe']}_{row['event']}",
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "event": row["event"],
                "source_q": row["q"],
                "train": train["metrics"],
                "train_5k": train_5k["metrics"],
                "holdout": hold["metrics"],
                "holdout_5k": hold_5k["metrics"],
                "p": _trade_p(returns),
                "_train_equity": train["equity"],
                "_hold_equity": hold["equity"],
                "_hold_pnls": hold["pnls"],
                "_train_pnls": train["pnls"],
            }
        )
    if books:
        q_values = benjamini_hochberg([book["p"] for book in books])
        for book, q_value in zip(books, q_values):
            book["q"] = float(q_value)
            dsr = deflated_sharpe(_daily_returns(book["_train_equity"], 1000.0), len(books))
            book["dsr"] = dsr.get("dsr")
            metrics = book["holdout"]
            book["confirmed"] = bool(
                book["q"] <= FDR_Q
                and (book["dsr"] or 0.0) >= 0.95
                and int(metrics["trades"]) >= 20
                and (metrics["profit_factor"] or 0) >= 1.10
                and float(metrics["sharpe"]) >= 0.40
                and float(metrics["max_drawdown"]) >= -0.30
                and float(metrics["ending_equity"]) > float(metrics["starting_equity"])
            )
    return books


def _trade_p(returns: list[float]) -> float:
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 5:
        return 1.0
    std = float(values.std(ddof=1))
    if std <= 0:
        return 1.0
    stat = float(values.mean() / (std / math.sqrt(len(values))))
    return float(0.5 * math.erfc(stat / math.sqrt(2.0)))


def _daily_returns(equity: pd.Series, starting: float) -> np.ndarray:
    if equity is None or len(equity) == 0:
        return np.array([])
    curve = pd.concat([pd.Series([starting], index=[equity.index[0] - pd.Timedelta(days=1)]), equity.astype(float)])
    returns = curve.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    return returns.to_numpy(dtype=float)


def plain_personality(row: dict) -> str:
    side = "dip" if row["side"] == "dip" else "rip"
    names = {
        "vwap_dip": "a close below the 2 SD VWAP band",
        "vwap_rip": "a close above the 2 SD VWAP band",
        "rsi_dip": "RSI(14) below 30",
        "rsi_rip": "RSI(14) above 70",
        "atr1_dip": "a drop of at least 1 ATR from the session high",
        "atr1_rip": "a rise of at least 1 ATR from the session low",
        "atr15_dip": "a drop of at least 1.5 ATR from the session high",
        "atr15_rip": "a rise of at least 1.5 ATR from the session low",
        "gap_dip": "an open at least 1 ATR below the prior close",
        "gap_rip": "an open at least 1 ATR above the prior close",
        "multi_dip": "a three-session drop of at least 1.5 ATR",
        "multi_rip": "a three-session rise of at least 1.5 ATR",
    }
    horizon = {
        "m30": "30 minutes",
        "m60": "60 minutes",
        "eod": "the session close",
        "d1": "the next session",
        "d3": "three sessions",
        "d5": "five sessions",
    }[row["horizon"]]
    drift = "reverses" if row["mean_signed"] > 0 else "continues"
    return (
        f"{row['symbol']} {row['timeframe']}: after {names[row['event']]}, the move {drift} by {horizon}. "
        f"Train n={row['n']}, reversal {_pct(row['reversal'])} versus random {_pct(row['random_reversal'])}, "
        f"mean edge {_pct(row['mean_signed'])}, q={row['q']}."
    )


def _pct(value: float) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value:.1%}"


def option_on_trades(pnls_unused: list[dict], vix: dict[date, float], fills: list[dict], starting: float, dte: int) -> dict:
    """One contract marked from the underlying fill to the underlying exit."""
    settled = float(starting)
    pending: list[tuple[date, float]] = []
    pnl = 0.0
    filled = 0
    skipped = 0
    last = None
    for trade in fills:
        session = trade["day"]
        if last != session:
            still = []
            for when, amount in pending:
                if when <= session:
                    settled += amount
                else:
                    still.append((when, amount))
            pending = still
            last = session
        sigma_points = None
        cursor = session
        for _ in range(10):
            cursor = date.fromordinal(cursor.toordinal() - 1)
            if cursor in vix and vix[cursor] > 0:
                sigma_points = vix[cursor]
                break
        if sigma_points is None:
            skipped += 1
            continue
        sigma = sigma_points / 100.0
        right = "call" if trade["side"] == "long" else "put"
        strike = listed_strike(trade["fill"], trade["fill"])
        entry_t = max(dte, 1) / 365.25 if dte else 6.5 / 24 / 365.25
        exit_t = max(dte - (0 if dte else 1), 0) / 365.25
        mid_entry = option_price(right, trade["fill"], strike, entry_t, sigma, 0.02, 0.0)
        mid_exit = option_price(right, trade["exit"], strike, exit_t, sigma, 0.02, 0.0)
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
    return {"trades": filled, "skipped": skipped, "pnl": pnl, "ending": settled + sum(amount for _w, amount in pending)}
