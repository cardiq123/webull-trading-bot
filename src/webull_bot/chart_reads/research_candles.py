"""Score the frozen candlestick definitions. Backtests only.

Writes the rules file before any price is loaded. Does not place an order,
does not edit the sandbox forward test, and does not add a strategy to the
live list.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from webull_bot.chart_reads.candles import (
    CATALOG,
    HOLDOUT_START,
    RANDOM_SEED,
    SAMPLE_END,
    TRAIN_END,
    catalog_markdown,
    confirms,
    detect,
    draw_reference,
    forward_returns,
    frozen_rules,
    pattern_ids,
)
from webull_bot.chart_reads.ema_reject import find_signals as ema_find_signals
from webull_bot.chart_reads.ema_reject import simulate as ema_simulate
from webull_bot.chart_reads.ema_reject import to_five_minute
from webull_bot.chart_reads.liquid import LIQUID_BLUE_CHIPS
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.vwap_band import find_signals as vwap_find_signals
from webull_bot.chart_reads.vwap_band import passes_gate
from webull_bot.chart_reads.vwap_band import simulate as vwap_simulate
from webull_bot.chart_reads.vwap_band_data import load_minutes, to_fifteen_minute
from webull_bot.data.yfinance_provider import YFinanceProvider

START_MARK = "<!-- CANDLES_START -->"
END_MARK = "<!-- CANDLES_END -->"
RULES_PATH = Path("reports/candles_rules.json")
JSON_PATH = Path("reports/candles.json")
SHEET_PATH = Path("reports/candlestick_patterns.png")
DOC_PATH = Path("docs/CANDLESTICK_PATTERNS.md")
FAMILY_BOOKS = ("SPY_5m", "SPY_15m", "SPY_1d", "LIQUID_1d")
HORIZONS = (1, 3, 6)

# Published unfiltered holdout and training accounts. These are cited, not resimulated.
PUBLISHED = {
    ("ema", "shares", 1000): {"trades": 101, "ending": 879.0, "pf": 0.11, "dd": -0.121, "train_ending": 953.0, "train_trades": 49, "train_pf": 0.26, "train_dd": -0.048},
    ("ema", "shares", 5000): {"trades": 101, "ending": 4396.0, "pf": 0.11, "dd": -0.121, "train_ending": 4765.0, "train_trades": 49, "train_pf": 0.26, "train_dd": -0.048},
    ("ema", "0dte", 1000): {"trades": 242, "ending": 75.0, "pf": 0.65, "dd": -0.958, "train_ending": 823.0, "train_trades": 106, "train_pf": 0.81, "train_dd": -0.258},
    ("ema", "0dte", 5000): {"trades": 283, "ending": 3725.0, "pf": 0.64, "dd": -0.261, "train_ending": 4823.0, "train_trades": 106, "train_pf": 0.81, "train_dd": -0.258},
    ("vwap_reversal", "shares", 1000): {"trades": 908, "ending": 297.0, "pf": 0.11, "dd": -0.703, "train_ending": 308.0, "train_trades": 935, "train_pf": 0.10, "train_dd": -0.692},
    ("vwap_reversal", "shares", 5000): {"trades": 908, "ending": 1487.0, "pf": 0.11, "dd": -0.703, "train_ending": 1538.0, "train_trades": 935, "train_pf": 0.10, "train_dd": -0.692},
    ("vwap_reversal", "0dte", 1000): {"trades": 396, "ending": 2.0, "pf": 0.87, "dd": -0.999, "train_ending": 0.0, "train_trades": 446, "train_pf": 0.54, "train_dd": -1.0},
    ("vwap_reversal", "0dte", 5000): {"trades": 396, "ending": 13.0, "pf": 0.87, "dd": -0.999, "train_ending": 0.0, "train_trades": 446, "train_pf": 0.54, "train_dd": -1.0},
    ("vwap_extension", "shares", 1000): {"trades": 812, "ending": 393.0, "pf": 0.39, "dd": -0.608, "train_ending": 384.0, "train_trades": 813, "train_pf": 0.29, "train_dd": -0.618},
    ("vwap_extension", "shares", 5000): {"trades": 812, "ending": 1963.0, "pf": 0.39, "dd": -0.608, "train_ending": 1918.0, "train_trades": 813, "train_pf": 0.29, "train_dd": -0.618},
    ("vwap_extension", "0dte", 1000): {"trades": 2355, "ending": 32844.0, "pf": 1.55, "dd": -0.162, "train_ending": 1.0, "train_trades": 255, "train_pf": 0.56, "train_dd": -0.999},
    ("vwap_extension", "0dte", 5000): {"trades": 2355, "ending": 36844.0, "pf": 1.55, "dd": -0.162, "train_ending": 7554.0, "train_trades": 255, "train_pf": 0.56, "train_dd": -0.999},
}


def _assert_rules(rules: dict) -> None:
    if rules != frozen_rules():
        raise SystemExit("rules file does not match frozen_rules()")
    literals = {
        "doji_body": 0.10,
        "doji_range": 0.20,
        "hammer_body_min_exclusive": 0.10,
        "hammer_body_max": 0.40,
        "hammer_wick_body": 2.0,
        "hammer_wick_atr": 0.30,
        "spin_body_max": 0.25,
        "long_legged_wick": 0.30,
        "dragon_wick": 0.40,
        "marubozu_body": 0.60,
        "marubozu_wick": 0.05,
        "engulf_body": 0.30,
        "engulf_prior": 0.25,
        "harami_prior": 0.40,
        "pierce_prior": 0.40,
        "pierce_body": 0.30,
        "tweezer_match": 0.10,
        "kicker_body": 0.40,
        "star_prior": 0.40,
        "star_middle": 0.25,
        "star_body": 0.30,
        "star_doji": 0.10,
        "soldier_body": 0.30,
        "methods_first": 0.50,
        "methods_middle": 0.25,
        "methods_last": 0.40,
        "tasuki_first": 0.40,
        "tasuki_second": 0.30,
        "tasuki_gap": 0.02,
        "trend_bars": 5,
        "trend_atr": 0.50,
        "near_atr": 0.25,
        "swing_width": 2,
        "holdout_start": "2022-01-01",
        "train_end": "2021-12-31",
        "sample_end": "2026-10-06",
        "seed": 17,
    }
    for key, value in literals.items():
        if rules[key] != value:
            raise SystemExit(f"frozen {key} is {rules[key]}, expected {value}")
    edge = rules["edge"]
    if edge["min_n"] != 300 or edge["fdr_q"] != 0.10 or edge["min_cell_n"] != 30:
        raise SystemExit("edge rule does not match the freeze")
    if edge["family_books"] != list(FAMILY_BOOKS) or edge["horizons"] != [1, 3, 6]:
        raise SystemExit("edge family does not match the freeze")
    if edge["neutral_can_pass"] or "three_white_soldiers" not in rules["reversal_long"]:
        raise SystemExit("family split does not match the freeze")
    if "marubozu_bull" not in rules["continuation_long"] or "doji" not in rules["indecision"]:
        raise SystemExit("family split does not match the freeze")
    if HOLDOUT_START != date(2022, 1, 1) or TRAIN_END != date(2021, 12, 31) or SAMPLE_END != date(2026, 10, 6):
        raise SystemExit("split dates drifted")
    if RANDOM_SEED != 17:
        raise SystemExit("seed drifted")


def _dates(index: pd.Index) -> np.ndarray:
    clock = pd.DatetimeIndex(index)
    if clock.tz is not None:
        clock = clock.tz_convert("America/New_York")
    return np.asarray(clock.date)


def _moments(values: np.ndarray) -> dict:
    clean = np.asarray(values, dtype=float)
    clean = clean[np.isfinite(clean)]
    count = int(clean.size)
    if count == 0:
        return {"n": 0, "mean": None, "hit": None, "t": None, "pf": None}
    mean = float(clean.mean())
    hit = float(np.mean(clean > 0.0))
    wins = float(clean[clean > 0.0].sum())
    losses = float(clean[clean < 0.0].sum())
    if losses < 0.0:
        profit = wins / abs(losses)
    elif wins > 0.0:
        profit = None
    else:
        profit = None
    if count < 2:
        stat = None
    else:
        scale = float(clean.std(ddof=1))
        if scale == 0.0:
            stat = None if mean == 0.0 else (math.inf if mean > 0.0 else -math.inf)
        else:
            stat = mean / (scale / math.sqrt(count))
    return {"n": count, "mean": mean, "hit": hit, "t": stat, "pf": profit}


def _random_moments(pool: np.ndarray, count: int) -> dict:
    if count <= 0 or pool.size < count:
        return {"n": 0, "mean": None, "hit": None, "t": None, "pf": None}
    draw = np.random.default_rng(RANDOM_SEED).choice(pool, size=count, replace=False)
    return _moments(draw)


def _score_book(book: str, frames: list[tuple[str, pd.DataFrame]], intraday: bool, in_family: bool) -> dict:
    prepared = []
    for symbol, frame in frames:
        if frame is None or frame.empty:
            continue
        flags = detect(frame)
        days = _dates(frame.index)
        horizons = {horizon: forward_returns(frame, horizon, intraday) for horizon in HORIZONS}
        prepared.append((symbol, flags, days, horizons))
        print(f"DETECT {book} {symbol} bars {len(frame)}", flush=True)
    cells = []
    counts = []
    for item in CATALOG:
        directions = ("long", "short") if item.bias == "neutral" else (("long",) if item.bias == "bullish" else ("short",))
        raw = 0
        for _symbol, flags, _days, _horizons in prepared:
            raw += int(flags[item.id].sum())
        counts.append({"pattern": item.id, "bias": item.bias, "raw": raw})
        for context in ("off", "on"):
            column = item.id if context == "off" else f"context_{item.id}"
            for horizon in HORIZONS:
                for direction in directions:
                    hold_parts = []
                    train_parts = []
                    pool_parts = []
                    for _symbol, flags, days, horizons in prepared:
                        side = 0 if direction == "long" else 1
                        returns = horizons[horizon][side]
                        mask = flags[column].to_numpy(dtype=bool) & np.isfinite(returns)
                        hold = mask & (days >= HOLDOUT_START) & (days <= SAMPLE_END)
                        train = mask & (days <= TRAIN_END)
                        eligible = np.isfinite(returns) & (days >= HOLDOUT_START) & (days <= SAMPLE_END)
                        if hold.any():
                            hold_parts.append(returns[hold])
                        if train.any():
                            train_parts.append(returns[train])
                        if eligible.any():
                            pool_parts.append(returns[eligible])
                    hold_values = np.concatenate(hold_parts) if hold_parts else np.array([])
                    train_values = np.concatenate(train_parts) if train_parts else np.array([])
                    pool = np.concatenate(pool_parts) if pool_parts else np.array([])
                    hold_stats = _moments(hold_values)
                    train_stats = _moments(train_values)
                    random_stats = _random_moments(pool, hold_stats["n"])
                    cells.append(
                        {
                            "book": book,
                            "pattern": item.id,
                            "name": item.name,
                            "bias": item.bias,
                            "family": item.family,
                            "neutral": item.bias == "neutral",
                            "in_family": in_family and item.bias != "neutral",
                            "context": context,
                            "horizon": horizon,
                            "direction": direction,
                            "n": hold_stats["n"],
                            "mean": hold_stats["mean"],
                            "hit": hold_stats["hit"],
                            "t": hold_stats["t"],
                            "pf": hold_stats["pf"],
                            "train_n": train_stats["n"],
                            "train_mean": train_stats["mean"],
                            "random_n": random_stats["n"],
                            "random_mean": random_stats["mean"],
                            "random_hit": random_stats["hit"],
                        }
                    )
    return {"book": book, "in_family": in_family, "counts": counts, "cells": cells}


def _p_value(stat: float | None) -> float | None:
    if stat is None:
        return None
    if stat == math.inf:
        return 0.0
    if stat == -math.inf:
        return 1.0
    return 0.5 * math.erfc(stat / math.sqrt(2.0))


def _bh(p_values: list[float]) -> np.ndarray:
    count = len(p_values)
    order = np.argsort(np.asarray(p_values, dtype=float))
    ranked = np.asarray(p_values, dtype=float)[order]
    adjusted = np.empty(count)
    running = 1.0
    for index in range(count - 1, -1, -1):
        running = min(running, ranked[index] * count / (index + 1))
        adjusted[index] = running
    out = np.empty(count)
    out[order] = adjusted
    return out


def _spy_daily_positive(cells: list[dict], pattern: str, horizon: int, context: str) -> bool:
    for cell in cells:
        if cell["book"] == "SPY_1d" and cell["pattern"] == pattern and cell["horizon"] == horizon and cell["context"] == context:
            train = cell["train_mean"]
            hold = cell["mean"]
            return train is not None and hold is not None and train > 0.0 and hold > 0.0
    return False


def _mark_edges(cells: list[dict]) -> dict:
    tested = [cell for cell in cells if cell["in_family"] and cell["n"] >= 30 and cell["t"] is not None and _p_value(cell["t"]) is not None]
    hurdle = None
    if tested:
        p_values = [_p_value(cell["t"]) for cell in tested]
        adjusted = _bh(p_values)
        hurdle = NormalDist().inv_cdf(1.0 - 1.0 / len(tested))
        for cell, q_value in zip(tested, adjusted):
            cell["q"] = float(q_value)
            cell["tested"] = True
    for cell in cells:
        cell.setdefault("q", None)
        cell.setdefault("tested", False)
        cell["hurdle"] = hurdle
        cell["edge"] = _edge(cell, cells, hurdle)
    return {"m": len(tested), "hurdle": hurdle}


def _edge(cell: dict, cells: list[dict], hurdle: float | None) -> bool:
    if not cell["in_family"] or cell["neutral"] or cell["n"] < 300:
        return False
    if cell["mean"] is None or cell["train_mean"] is None or cell["mean"] <= 0.0 or cell["train_mean"] <= 0.0:
        return False
    if cell["random_mean"] is None or cell["random_hit"] is None or cell["hit"] is None:
        return False
    if not (cell["mean"] > cell["random_mean"] and cell["hit"] > cell["random_hit"]):
        return False
    if cell["q"] is None or cell["q"] > 0.10:
        return False
    if hurdle is None or cell["t"] is None or not (cell["t"] > hurdle):
        return False
    if cell["book"] == "LIQUID_1d" and not _spy_daily_positive(cells, cell["pattern"], cell["horizon"], cell["context"]):
        return False
    return True


def _reason(cell: dict) -> str:
    if cell["n"] < 30:
        return "fewer than 30 holdout trades, left out of the false-discovery set"
    if cell["n"] < 300:
        return "fewer than 300 holdout trades"
    if cell["mean"] is None or cell["mean"] <= 0.0:
        return "holdout mean is not positive after costs"
    if cell["train_mean"] is None or cell["train_mean"] <= 0.0:
        return "training mean is not positive"
    if cell["random_mean"] is None or not (cell["mean"] > cell["random_mean"]):
        return "holdout mean does not beat the seed-17 draw"
    if cell["random_hit"] is None or cell["hit"] is None or not (cell["hit"] > cell["random_hit"]):
        return "hit rate does not beat the seed-17 draw"
    if cell["q"] is None or cell["q"] > 0.10:
        return "Benjamini-Hochberg q is above 0.10"
    if cell["hurdle"] is None or cell["t"] is None or not (cell["t"] > cell["hurdle"]):
        return "t-stat does not clear the expected-max bar"
    if cell["book"] == "LIQUID_1d" and not cell["edge"]:
        return "the same SPY daily cell is not positive in both windows"
    if cell["edge"]:
        return "clears the frozen edge rule"
    return "does not clear the frozen edge rule"


def _prepare_iv() -> dict:
    provider = YFinanceProvider(cache_dir="data/cache/vwap_band/yahoo")
    daily = provider.history(["^VIX", "^VIX1D", "SPY", "QQQ"], "2016-01-01", "2026-10-08", interval="1d")
    closes = {}
    for symbol, frame in daily.items():
        if frame is None or frame.empty or "close" not in frame.columns:
            continue
        series = frame["close"].astype(float).copy()
        index = pd.to_datetime(series.index)
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert("America/New_York").tz_localize(None)
        series.index = index
        closes[symbol] = series[~series.index.duplicated(keep="last")].sort_index()
    return prior_iv(closes.get("^VIX1D", pd.Series(dtype=float)), closes.get("^VIX", pd.Series(dtype=float)))


def _stamp_set(flags: pd.DataFrame, direction: str, kind: str, require_location: bool) -> set:
    mask = confirms(flags, direction, kind, require_location)
    return set(mask.index[mask.to_numpy(dtype=bool)])


def _filter_signals(signals: list, flags: pd.DataFrame, kind: str, require_location: bool) -> list:
    allowed = {
        "long": _stamp_set(flags, "long", kind, require_location),
        "short": _stamp_set(flags, "short", kind, require_location),
    }
    return [signal for signal in signals if signal.signal_time in allowed[signal.direction]]


def _pack_metrics(book: dict) -> dict:
    metrics = dict(book["metrics"])
    return {
        "trades": int(metrics.get("trades") or 0),
        "ending_equity": metrics.get("ending_equity"),
        "profit_factor": metrics.get("profit_factor"),
        "max_drawdown": metrics.get("max_drawdown"),
        "sharpe": metrics.get("sharpe"),
        "win_rate": metrics.get("win_rate"),
        "passes_gate": bool(passes_gate(metrics)),
    }


def _improves(filtered: dict, published: dict) -> bool:
    if int(filtered["trades"]) < 20:
        return False
    ending = filtered["ending_equity"]
    profit = filtered["profit_factor"]
    drawdown = filtered["max_drawdown"]
    if ending is None or drawdown is None:
        return False
    if profit is None:
        if float(filtered.get("win_rate") or 0.0) == 1.0 and int(filtered["trades"]) > 0:
            profit = float("inf")
        else:
            return False
    if float(ending) <= float(published["ending"]):
        return False
    if float(profit) < float(published["pf"]):
        return False
    if float(drawdown) < float(published["dd"]) - 0.05:
        return False
    return True


def _run_filters(five: pd.DataFrame, fifteen: pd.DataFrame, iv: dict) -> list[dict]:
    print("FILTER detect", flush=True)
    five_flags = detect(five)
    fifteen_flags = detect(fifteen)
    ema_rows = [signal for signal in ema_find_signals(five, "SPY") if signal.variant == "vwap"]
    vwap_rows = vwap_find_signals(fifteen, "SPY", outer=2.0)
    extension = [signal for signal in vwap_rows if signal.mode == "extension"]
    reversal = [signal for signal in vwap_rows if signal.mode == "reversal"]
    print(f"FILTER base ema {len(ema_rows)} extension {len(extension)} reversal {len(reversal)}", flush=True)
    specs = (
        ("ema", "reversal", ema_rows, five, ema_simulate, {"stop": "reject", "target": "swing"}),
        ("vwap_reversal", "reversal", reversal, fifteen, vwap_simulate, {"target": "vwap"}),
        ("vwap_extension", "continuation", extension, fifteen, vwap_simulate, {"target": "r"}),
    )
    rows = []
    for name, kind, signals, frame, runner, extra in specs:
        flags = five_flags if name == "ema" else fifteen_flags
        for context in (False, True):
            kept = _filter_signals(signals, flags, kind, context)
            for kind_name, long_only in (("shares", True), ("0dte", False)):
                for stake in (1000.0, 5000.0):
                    print(f"FILTER {name} {kind_name} stake {stake:.0f} context {context} kept {len(kept)}", flush=True)
                    train = runner(frame, kept, kind=kind_name, stake=stake, long_only=long_only, iv_points=iv, end=TRAIN_END, **extra)
                    hold = runner(frame, kept, kind=kind_name, stake=stake, long_only=long_only, iv_points=iv, start=HOLDOUT_START, **extra)
                    published = PUBLISHED[(name, kind_name, int(stake))]
                    packed = _pack_metrics(hold)
                    rows.append(
                        {
                            "setup": name,
                            "filter": kind,
                            "context": "on" if context else "off",
                            "kind": kind_name,
                            "stake": int(stake),
                            "signals": len(kept),
                            "holdout": packed,
                            "train": _pack_metrics(train),
                            "published": published,
                            "improves": _improves(packed, published),
                        }
                    )
    return rows


def _qqq_note(count: int) -> str:
    return (
        f"Dukascopy publishes QQQUSUSD, but this cache has {count} day files, short of the 2017+ file. "
        "Yahoo 5-minute and 15-minute rows are about 60 days. They are not in the false-discovery family."
    )


def _yahoo_intraday(symbol: str, interval: str) -> pd.DataFrame | None:
    provider = YFinanceProvider(cache_dir="data/cache/candles/yahoo")
    frames = provider.history([symbol], "2026-08-01", "2026-10-08", interval=interval)
    frame = frames.get(symbol)
    if frame is None or frame.empty:
        return None
    return frame


def _load_daily() -> tuple[dict[str, pd.DataFrame], list[str]]:
    provider = YFinanceProvider(cache_dir="data/cache/candles/yahoo")
    raw = provider.history(list(LIQUID_BLUE_CHIPS), "2016-01-01", "2026-10-08", interval="1d")
    frames = {}
    missing = []
    for symbol in LIQUID_BLUE_CHIPS:
        frame = raw.get(symbol)
        if frame is None or frame.empty:
            missing.append(symbol)
            continue
        frames[symbol] = frame
    return frames, missing


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _bps(value) -> str:
    if value is None:
        return "n/a"
    return f"{value * 10_000:.1f} bp"


def _pct(value) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _num(value) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _money(value) -> str:
    if value is None:
        return "n/a"
    number = float(value)
    sign = "-" if number < 0 else ""
    return f"{sign}${abs(number):,.0f}"


def _pf(value) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _results_text(payload: dict) -> str:
    edges = payload["edges"]
    tested = payload["multiple_testing"]
    lines = [
        START_MARK,
        "## Candlestick patterns",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox forward test was not changed. "
        "The shape rules were written to `reports/candles_rules.json` and `docs/CANDLESTICK_PATTERNS.md` before any forward return was measured. "
        "A pattern is not in the live list.",
        "",
        payload["data_text"],
        "",
        "Each pattern is entered at the next bar's open and closed at the close 1, 3, or 6 bars later. "
        "On 5-minute and 15-minute bars the entry and the exit have to be in the same session as the signal, so a late-day pattern with no room is skipped. "
        "Costs are one share on the repo schedule: 5 bps slippage and 1 bp half-spread on each side, plus the 2026 SEC and FINRA sell fees. "
        "That is about 12 bps before the regulatory fee, so a one-bar scalp has to clear that friction. "
        "The random baseline is one seed-17 draw of the same number of holdout-eligible bars, in the pattern's direction. "
        "Neutral patterns are measured both ways and cannot be labeled an edge.",
        "",
        "The false-discovery family is every directional pattern, on SPY 5-minute, SPY 15-minute, SPY daily, and the pooled liquid daily basket, "
        "at 1, 3, and 6 bars, with the context filter off and on. A cell needs 30 holdout trades to enter that test. "
        f"This run tested {tested['m']} cells. The Benjamini-Hochberg q line is 0.10. "
        f"The independent expected-max t bar is {_num(tested['hurdle'])}. "
        "Patterns overlap, so the tests are not independent. Treating them as independent raises that bar, which makes a pass harder, not easier. "
        "An edge also needs 300 holdout trades, a positive training mean, a positive holdout mean, a holdout mean and hit rate above the seed-17 draw, "
        "and, for the pooled basket, a positive SPY daily mean in both windows. The basket is the 2026 liquid list and is survivorship-biased. "
        "QQQ intraday is not in the family. Per-name daily rows are in `reports/candles.json` and are not the family.",
        "",
        payload["edge_text"],
        "",
        "### Highest holdout t-stats in the family",
        "",
        "Ranked by the holdout t-stat among cells with at least 30 trades. A high rank with a failed reason is not an edge.",
        "",
        "| Pattern | Book | Bars | Context | Trades | Mean | Hit | t | Random mean | q | Why it stands here |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for cell in payload["ranked"]:
        lines.append(
            f"| {cell['name']} | {cell['book']} | {cell['horizon']} | {cell['context']} | {cell['n']} | "
            f"{_bps(cell['mean'])} | {_pct(cell['hit'])} | {_num(cell['t'])} | {_bps(cell['random_mean'])} | "
            f"{_num(cell['q'])} | {cell['reason']} |"
        )
    if not payload["ranked"]:
        lines.append("| none | | | | | | | | | | no cell reached 30 holdout trades |")
    lines += [
        "",
        "### How often the shapes print on SPY",
        "",
        "Raw rows are every completion. Traded rows are the ones with a same-session 1-bar exit in the holdout. A gap pattern can print and still have almost no trades.",
        "",
        "| Pattern | 5-minute raw | 5-minute traded, context off | 5-minute traded, context on | Daily raw | Daily traded, context off |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["frequency"]:
        lines.append(
            f"| {row['name']} | {row['spy5_raw']} | {row['spy5_off']} | {row['spy5_on']} | {row['spy1_raw']} | {row['spy1_off']} |"
        )
    lines += [
        "",
        "### Optional confirmation on the published VWAP and EMA books",
        "",
        "One filter was registered for each setup, before this score. The EMA book (VWAP confluence, rejection stop, swing target) and the VWAP 2 SD reversal keep a signal only when a reversal pattern of the same direction completes on the signal bar. "
        "The VWAP 2 SD extension keeps a signal only when a continuation pattern of the same direction completes on that bar. "
        "Context off is the shape. Context on also requires that pattern's trend and location. "
        "Shares stay long only. The 0 DTE books still take both directions. "
        "The unfiltered endings below are the published ones. They were not resimulated. "
        "A filter improves a book only when the holdout has at least 20 trades, ending equity is higher, profit factor is not lower, "
        "and max drawdown is not worse by more than 5 percentage points. Clearing that line does not add the book to the live list. "
        "It still has to pass the numeric gate, and this study does not promote it.",
        "",
        "| Setup | Stake | Context | Trades | PF | Max DD | Ending | Published trades | Published PF | Published DD | Published ending | Improves | Gate |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in payload["filters"]:
        hold = row["holdout"]
        published = row["published"]
        lines.append(
            f"| {row['setup']} {row['kind']} | ${row['stake']:,} | {row['context']} | {hold['trades']} | {_pf(hold['profit_factor'])} | "
            f"{_pct(hold['max_drawdown'])} | {_money(hold['ending_equity'])} | {published['trades']} | {published['pf']:.2f} | "
            f"{_pct(published['dd'])} | {_money(published['ending'])} | {'yes' if row['improves'] else 'no'} | "
            f"{'yes' if hold['passes_gate'] else 'no'} |"
        )
    lines += [
        "",
        payload["filter_text"],
        "",
        "Training accounts, from the same filtered signal list, are in `reports/candles.json`. "
        "The published training accounts are the ones already in the VWAP and EMA sections above. They were not replaced.",
        "",
        "The drawing of the shapes is `reports/candlestick_patterns.png`. The guide is `docs/CANDLESTICK_PATTERNS.md`.",
        "",
        "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.",
        "",
        "```",
        "python3 -m webull_bot.chart_reads.research_candles",
        "```",
        END_MARK,
        "",
    ]
    return "\n".join(lines)


def _write_results(block: str) -> None:
    path = Path("RESULTS.md")
    text = path.read_text()
    if START_MARK in text and END_MARK in text:
        before = text.split(START_MARK)[0]
        after = text.split(END_MARK)[1]
        path.write_text(before + block + after.lstrip("\n"))
        return
    anchor = "<!-- EMA_REJECT_END -->"
    if anchor not in text:
        raise SystemExit("RESULTS.md is missing the EMA section anchor")
    before, after = text.split(anchor, 1)
    path.write_text(before + anchor + "\n\n" + block + after)


def _write_readme(paragraph: str) -> None:
    path = Path("README.md")
    text = path.read_text()
    marker = "**Chart Fanatics specs: none joins the book.**"
    if marker not in text:
        raise SystemExit("README is missing the Chart Fanatics paragraph")
    start = "**Candlestick patterns.**"
    if start in text:
        before = text.split(start)[0]
        after = marker + text.split(marker, 1)[1]
        path.write_text(before.rstrip() + "\n\n" + paragraph.strip() + "\n\n" + after)
        return
    before, after = text.split(marker, 1)
    path.write_text(before.rstrip() + "\n\n" + paragraph.strip() + "\n\n" + marker + after)


def _readme_paragraph(payload: dict) -> str:
    return (
        f"**Candlestick patterns.** {payload['readme']} "
        "Nothing was added to the live list. The sandbox forward test was not changed. "
        "Full table in [RESULTS.md](RESULTS.md)."
    )


def _frequency(books: dict) -> list[dict]:
    spy5 = {row["pattern"]: row for row in books["SPY_5m"]["counts"]}
    spy1 = {row["pattern"]: row for row in books["SPY_1d"]["counts"]}
    traded = {}
    for cell in books["SPY_5m"]["cells"] + books["SPY_1d"]["cells"]:
        if cell["horizon"] != 1 or cell["bias"] == "neutral" and cell["direction"] != "long":
            if not (cell["horizon"] == 1 and (cell["bias"] != "neutral" or cell["direction"] == "long")):
                continue
        traded[(cell["book"], cell["pattern"], cell["context"])] = cell["n"]
    rows = []
    for item in CATALOG:
        rows.append(
            {
                "name": item.name,
                "spy5_raw": spy5[item.id]["raw"],
                "spy5_off": traded.get(("SPY_5m", item.id, "off"), 0),
                "spy5_on": traded.get(("SPY_5m", item.id, "on"), 0),
                "spy1_raw": spy1.get(item.id, {}).get("raw", 0),
                "spy1_off": traded.get(("SPY_1d", item.id, "off"), 0),
            }
        )
    return rows


def _edge_sentence(edges: list[dict]) -> str:
    if not edges:
        return (
            "No cell cleared the frozen edge rule. The table below is the highest holdout t-stats, including the ones that lost money. "
            "A positive t on a short sample is not a pass."
        )
    names = ", ".join(f"{cell['name']} on {cell['book']} at {cell['horizon']} bars, context {cell['context']}" for cell in edges)
    return (
        f"These cells cleared the frozen edge rule: {names}. "
        "Clearing it labels a forward-return cell. It does not add a book to the live list."
    )


def _filter_sentence(rows: list[dict]) -> str:
    improved = [row for row in rows if row["improves"]]
    if not improved:
        return (
            "No filtered book improved its published holdout on the frozen line. "
            "A filter that only loses less money on fewer than 20 trades is not an improvement."
        )
    bits = []
    for row in improved:
        hold = row["holdout"]
        gate = "and it clears the numeric gate" if hold["passes_gate"] else "and it does not clear the numeric gate"
        bits.append(
            f"{row['setup']} {row['kind']} at ${row['stake']:,} with context {row['context']} "
            f"finished at {_money(hold['ending_equity'])} ({hold['trades']} trades, profit factor {_pf(hold['profit_factor'])}) {gate}"
        )
    return "Filtered books that beat the published holdout on the frozen line: " + "; ".join(bits) + ". None was added to the live list."


def _readme_bits(payload: dict) -> str:
    edges = payload["edges"]
    if edges:
        lead = _edge_sentence(edges)
    else:
        top = payload["ranked"][0] if payload["ranked"] else None
        if top is None:
            lead = "No directional cell had 30 holdout trades."
        else:
            lead = (
                f"No pattern cleared the frozen edge rule on SPY 5-minute, SPY 15-minute, SPY daily, or the pooled liquid daily basket. "
                f"The highest holdout t-stat with at least 30 trades was {top['name']} on {top['book']}, "
                f"{top['horizon']} bars, context {top['context']}: {top['n']} trades, mean {_bps(top['mean'])}, t {_num(top['t'])}. "
                f"{top['reason'][0].upper() + top['reason'][1:]}."
            )
    return (
        "Thirty-nine candlestick shapes, pure Python, no TA-Lib. "
        "SPY 5-minute and 15-minute bars are the Dukascopy bid file from 2017. Daily bars are Yahoo for SPY, QQQ, and the liquid list. "
        + lead
        + " "
        + payload["filter_text"]
    )


def main() -> None:
    rules = frozen_rules()
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(rules, indent=2) + "\n")
    written = json.loads(RULES_PATH.read_text())
    _assert_rules(written)
    if DOC_PATH.read_text() != catalog_markdown():
        raise SystemExit("docs/CANDLESTICK_PATTERNS.md does not match the catalog")
    draw_reference(SHEET_PATH)
    print("RULES frozen", flush=True)

    minutes, info = load_minutes("SPY")
    if minutes is None or minutes.empty:
        raise SystemExit("SPY Dukascopy minutes are missing")
    five = to_five_minute(minutes)
    fifteen = to_fifteen_minute(minutes)
    print(
        f"SPY {info.get('first')} {info.get('last')} sessions {info.get('sessions')} missing {info.get('missing')} "
        f"five {len(five)} fifteen {len(fifteen)}",
        flush=True,
    )
    qqq_cache = Path("data/cache/vwap_band/dukascopy/QQQ")
    qqq_count = len(list(qqq_cache.glob("*.csv"))) if qqq_cache.exists() else 0
    qqq_family = False
    qqq_five = None
    qqq_fifteen = None
    if qqq_count >= 2000:
        qqq_minutes, qqq_info = load_minutes("QQQ")
        sessions = int(qqq_info.get("sessions") or 0)
        missing = int(qqq_info.get("missing") or 9999)
        if qqq_minutes is not None and sessions >= 2000 and missing <= 80:
            qqq_family = True
            qqq_five = to_five_minute(qqq_minutes)
            qqq_fifteen = to_fifteen_minute(qqq_minutes)
            qqq_text = (
                f"QQQ is the same Dukascopy bid feed, {qqq_info.get('first')} through {qqq_info.get('last')}, "
                f"{sessions} sessions, {missing} days missing."
            )
        else:
            qqq_text = _qqq_note(qqq_count)
    else:
        qqq_text = _qqq_note(qqq_count)
    if not qqq_family:
        qqq_five = _yahoo_intraday("QQQ", "5m")
        qqq_fifteen = _yahoo_intraday("QQQ", "15m")
    daily, missing_daily = _load_daily()
    if "SPY" not in daily:
        raise SystemExit("SPY daily bars are missing")
    print(f"DAILY {len(daily)} missing {missing_daily}", flush=True)

    books = {}
    books["SPY_5m"] = _score_book("SPY_5m", [("SPY", five)], True, True)
    books["SPY_15m"] = _score_book("SPY_15m", [("SPY", fifteen)], True, True)
    books["SPY_1d"] = _score_book("SPY_1d", [("SPY", daily["SPY"])], False, True)
    if "QQQ" in daily:
        books["QQQ_1d"] = _score_book("QQQ_1d", [("QQQ", daily["QQQ"])], False, False)
    if qqq_five is not None and not qqq_five.empty:
        books["QQQ_5m"] = _score_book("QQQ_5m", [("QQQ", qqq_five)], True, qqq_family)
    if qqq_fifteen is not None and not qqq_fifteen.empty:
        books["QQQ_15m"] = _score_book("QQQ_15m", [("QQQ", qqq_fifteen)], True, qqq_family)
    liquid_frames = [(symbol, daily[symbol]) for symbol in LIQUID_BLUE_CHIPS if symbol in daily]
    books["LIQUID_1d"] = _score_book("LIQUID_1d", liquid_frames, False, True)
    symbol_books = {}
    for symbol, frame in liquid_frames:
        if symbol in ("SPY", "QQQ"):
            continue
        symbol_books[symbol] = _score_book(symbol, [(symbol, frame)], False, False)

    cells = []
    for book in books.values():
        cells.extend(book["cells"])
    multiple = _mark_edges(cells)
    edges = [cell for cell in cells if cell["edge"]]
    ranked_pool = [cell for cell in cells if cell["in_family"] and cell["n"] >= 30 and cell["t"] is not None]
    ranked_pool.sort(key=lambda cell: cell["t"], reverse=True)
    for cell in ranked_pool:
        cell["reason"] = _reason(cell)
    for cell in edges:
        cell["reason"] = _reason(cell)

    print("FILTERS", flush=True)
    for cell in ranked_pool[:8]:
        print(
            f"RANK {cell['name']} {cell['book']} h{cell['horizon']} {cell['context']} n={cell['n']} "
            f"mean={cell['mean']} t={cell['t']} reason={_reason(cell)}",
            flush=True,
        )
    filters = _run_filters(five, fifteen, _prepare_iv())
    data_text = (
        f"SPY is Dukascopy 1-minute bids resampled to 5 and 15 minutes, {info.get('first')} through {info.get('last')}, "
        f"{info.get('sessions')} sessions, {info.get('missing')} days missing, {len(five)} five-minute bars, {len(fifteen)} fifteen-minute bars. "
        "Volume is a bid-tick count. Prices are bids. "
        f"{qqq_text} "
        "Daily bars are Yahoo adjusted prices from 2016-01-01 through 2026-10-06 for "
        + ", ".join(symbol for symbol in LIQUID_BLUE_CHIPS if symbol in daily)
        + (f". Missing: {', '.join(missing_daily)}." if missing_daily else ".")
        + " The pooled daily book weights each signal equally. A 1% NVDA day counts the same as a 1% SPY day. "
        "The list is a 2026 snapshot, so names that failed earlier are absent."
    )
    payload = {
        "data_text": data_text,
        "multiple_testing": multiple,
        "edges": edges,
        "ranked": ranked_pool[:15],
        "frequency": _frequency(books),
        "filters": filters,
        "edge_text": "",
        "filter_text": "",
        "readme": "",
    }
    payload["edge_text"] = _edge_sentence(edges)
    payload["filter_text"] = _filter_sentence(filters)
    payload["readme"] = _readme_bits(payload)
    public = {
        "rules": "reports/candles_rules.json",
        "doc": "docs/CANDLESTICK_PATTERNS.md",
        "sheet": "reports/candlestick_patterns.png",
        "data": {
            "spy_sessions": info.get("sessions"),
            "spy_first": info.get("first"),
            "spy_last": info.get("last"),
            "spy_missing": info.get("missing"),
            "five_bars": len(five),
            "fifteen_bars": len(fifteen),
            "qqq_day_files": qqq_count,
            "qqq_in_family": qqq_family,
            "daily_missing": missing_daily,
        },
        "multiple_testing": multiple,
        "edges": [_jsonable(cell) for cell in edges],
        "ranked": [_jsonable(cell) for cell in ranked_pool[:15]],
        "books": {
            name: {"counts": book["counts"], "cells": [_jsonable(cell) for cell in book["cells"]]}
            for name, book in books.items()
        },
        "daily_symbols": {
            symbol: [_jsonable(cell) for cell in book["cells"] if cell["n"] > 0]
            for symbol, book in symbol_books.items()
        },
        "filters": _jsonable(filters),
        "edge_text": payload["edge_text"],
        "filter_text": payload["filter_text"],
    }
    JSON_PATH.write_text(json.dumps(public, indent=2) + "\n")
    _write_results(_results_text(payload))
    _write_readme(_readme_paragraph(payload))
    print("EDGES", len(edges), flush=True)
    print(payload["filter_text"], flush=True)
    print("WROTE", JSON_PATH, flush=True)


if __name__ == "__main__":
    main()
