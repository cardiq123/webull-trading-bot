"""Chop v2, the longer swing list, and the bounce trail with a regime filter.

The rule and the grid were frozen from the description before this score.
Charts are a check, not a reason to change a threshold. Daily books are
scored on 2023-01-01 through 2026-10-06. The cell, when one is chosen, is
chosen on earlier data. Hourly books use a walk-forward on the second half
of the Yahoo sample. Nothing here places an order.

Run: ``python -m webull_bot.chart_reads.research_chop_v2``
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from webull_bot.backtest.assessment import pick_params
from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.chart_reads.bounce import find_bounces, partial_params
from webull_bot.chart_reads.breakouts import find_breakout_setups
from webull_bot.chart_reads.chop import filter_helps
from webull_bot.chart_reads.chop_v2 import (
    DEFAULTS,
    cell_label,
    components,
    find_chop_breakouts,
    grid,
    mask_from,
    scan_holds,
)
from webull_bot.chart_reads.detect import rth
from webull_bot.chart_reads.levels import merged_swings
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DAILY_DEFAULTS
from webull_bot.chart_reads.research import (
    END,
    STARTING,
    SYMBOLS,
    _cells,
    _sessions,
    _split,
    _stitch,
    _window_book as intraday_window,
    detect_all,
    load_yahoo,
    random_setups,
)
from webull_bot.chart_reads.research_chop import _collect_daily, _precursor_params
from webull_bot.chart_reads.research_daily import (
    IS_END,
    OOS_START,
    SAMPLE_END,
    SCORE_FROM,
    _window_book as daily_window,
    load_daily,
)
from webull_bot.chart_reads.trendline import find_trend_setups
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.indicators import atr, ema, sma
from webull_bot.universe_dow import all_dow_tickers, is_member

START = "<!-- CHART_READS_CHOP_V2_START -->"
END_MARK = "<!-- CHART_READS_CHOP_V2_END -->"
ARTIFACT_DIR = Path("/opt/cursor/artifacts/setups")
HOLDOUT_START = date(2023, 1, 1)
TRAIN_END = date(2022, 12, 31)
AS_OF = date(2026, 10, 6)
SPY_FROM = date(2026, 8, 1)
SPY_TO = date(2026, 10, 5)
SPY_ZONE = (755.0, 775.0)
NVDA_PRICE = 241.37
NVDA_HIGH = 243.37
NVDA_LINES = (234.0, 232.5, 227.5, 221.5)
NVDA_PULLBACK = (232.5, 235.0)
NVDA_FRIDAY = date(2026, 10, 2)
NVDA_SESSIONS = 20
DRAWN = (781, 768, 760, 752, 737.5, 700, 690, 683, 675, 655, 632)
DRAWN_LABEL = {
    781: "781",
    768: "768",
    760: "760",
    752: "752",
    737.5: "740/735",
    700: "700",
    690: "690",
    683: "683",
    675: "675",
    655: "655",
    632: "632",
}
REGIME_DEFAULT = "stock"
REGIMES = ("stock", "spy", "both")
PUBLISHED_TRAIL = (2608.44, 118)
PUBLISHED_AB = {"A, 60-minute": (886.97, 131), "B, 60-minute": (921.86, 85)}
GATE_TRADES = 300
GATE_PF = 1.10
GATE_SHARPE = 0.40
GATE_DD = -0.30
SMA_WINDOW = 200


def _day(ts) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York")
    return stamp.date()


def _money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"${float(value):,.2f}"


def _pct(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _num(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _dd(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _pf(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _metrics_bits(metrics: dict) -> str:
    return (
        f"{int(metrics.get('trades') or 0)} trades, win {_pct(metrics.get('win_rate'))}, "
        f"expectancy {_money(metrics.get('expectancy'))}, profit factor {_pf(metrics.get('profit_factor'))}, "
        f"Sharpe {_num(metrics.get('sharpe'))}, max drawdown {_dd(metrics.get('max_drawdown'))}, "
        f"ending {_money(metrics.get('ending_equity'))}"
    )


def _gate(metrics: dict) -> bool:
    trades = int(metrics.get("trades") or 0)
    pf = metrics.get("profit_factor")
    sharpe = float(metrics.get("sharpe") or 0.0)
    dd = float(metrics.get("max_drawdown") or 0.0)
    pf_ok = pf is not None and np.isfinite(float(pf)) and float(pf) >= GATE_PF
    return trades >= GATE_TRADES and pf_ok and sharpe >= GATE_SHARPE and dd >= GATE_DD


def _beats(candidate: dict, baseline: dict) -> bool:
    """Risk-adjusted label. Sharpe is higher and the drawdown is not worse."""
    if int(candidate.get("trades") or 0) < 20 or int(baseline.get("trades") or 0) < 1:
        return False
    if float(candidate.get("sharpe") or 0.0) <= float(baseline.get("sharpe") or 0.0):
        return False
    return float(candidate.get("max_drawdown") or 0.0) >= float(baseline.get("max_drawdown") or 0.0)


def _same_cell(left: dict, right: dict) -> bool:
    return all(left.get(key) == right.get(key) for key in DEFAULTS)


def _level_params(base: dict) -> dict:
    cell = dict(base)
    cell.pop("exit_style", None)
    cell["trail"] = "none"
    cell["target_mode"] = "level"
    cell["level_source"] = "reference"
    cell["expression"] = "stock"
    return cell


def _trail_params(base: dict) -> dict:
    cell = dict(base)
    cell["exit_style"] = "trail_pct"
    cell["trail_pct"] = 0.15
    cell["trail"] = "none"
    cell["expression"] = "stock"
    return cell


def _bracket_params(base: dict) -> dict:
    cell = dict(base)
    cell.pop("exit_style", None)
    cell["trail"] = "none"
    cell["target_mode"] = "r"
    cell["reward_r"] = 2.0
    cell["expression"] = "stock"
    return cell


def _cache(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    built = {}
    for symbol, frame in frames.items():
        if frame is None or len(frame) < 80:
            continue
        built[symbol] = components(frame)
    return built


def _masks(cache: dict[str, pd.DataFrame], cell: dict | None = None) -> dict[str, pd.Series]:
    return {symbol: mask_from(comp, cell) for symbol, comp in cache.items()}


def _breakouts(frames, cache, cell, *, pit: bool, earliest: date | None) -> list:
    found = []
    for symbol, comp in cache.items():
        frame = frames[symbol]
        feat = comp.copy()
        feat["chop"] = mask_from(comp, cell)
        setups = find_chop_breakouts(frame, symbol=symbol, cell=cell, feat=feat)
        if pit:
            setups = [setup for setup in setups if is_member(symbol, _day(setup.signal_time))]
        if earliest is not None:
            setups = [setup for setup in setups if _day(setup.fill_time) >= earliest]
        found.extend(setups)
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    return found


def _holds(frames, cell=None) -> tuple[list, dict]:
    marks = []
    counts = {"breakouts": 0, "rejected": 0, "chop_runs": 0, "hold_breaks": 0, "signals": 0}
    for symbol, frame in frames.items():
        if frame is None or len(frame) < 80:
            continue
        local = {"breakouts": 0, "rejected": 0, "chop_runs": 0, "hold_breaks": 0, "signals": 0}
        marks.extend(scan_holds(frame, symbol=symbol, counts=local, cell=cell))
        for key, value in local.items():
            counts[key] = counts.get(key, 0) + int(value)
    marks.sort(key=lambda mark: (pd.Timestamp(mark.setup.fill_time), mark.setup.symbol))
    return marks, counts


def _score(setups, frames, daily, params, window, start: date, end: date):
    return window(setups, frames, daily, params, "stock", start, end)


def _row(label: str, stats) -> dict:
    metrics = stats.metrics if hasattr(stats, "metrics") else stats
    return {"label": label, "metrics": metrics}


def _time_table(frames, masks, start: date | None, end: date | None) -> list[dict]:
    rows = []
    for symbol in sorted(masks):
        flag = masks[symbol]
        if start is None:
            usable = flag
        else:
            keep = np.array([start <= _day(ts) <= end for ts in flag.index])
            usable = flag.loc[keep]
        bars = int(len(usable))
        if bars == 0:
            continue
        chop_bars = int(usable.sum())
        rows.append({"symbol": symbol, "bars": bars, "chop_bars": chop_bars, "share": chop_bars / bars})
    return rows


def _share_line(rows: list[dict]) -> str:
    if not rows:
        return "no bars"
    shares = sorted(row["share"] for row in rows)
    mid = shares[len(shares) // 2]
    return f"median {mid * 100:.1f}% of bars, {len(rows)} symbols"


def _lookup(series: pd.Series | None, ts) -> bool | None:
    if series is None or len(series) == 0:
        return None
    stamp = pd.Timestamp(ts)
    if series.index.tz is not None and stamp.tzinfo is None:
        stamp = stamp.tz_localize(series.index.tz)
    elif series.index.tz is None and stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York").tz_localize(None)
    if stamp not in series.index:
        pos = series.index.get_indexer([stamp])
        if len(pos) == 0 or int(pos[0]) < 0:
            return None
        value = series.iloc[int(pos[0])]
    else:
        value = series.loc[stamp]
    if isinstance(value, pd.Series):
        value = value.iloc[-1]
    if pd.isna(value):
        return None
    return bool(value)


def _above_sma(frame: pd.DataFrame) -> pd.Series:
    close = frame["close"].astype(float)
    average = sma(close, SMA_WINDOW)
    return close > average


def _spy_map(frame: pd.DataFrame) -> dict[date, bool]:
    above = _above_sma(frame)
    return {_day(ts): bool(value) for ts, value in above.items() if pd.notna(value)}


def _regime_keep(setup, frames, above, spy_up, chop, mode: str) -> bool:
    if _lookup(chop.get(setup.symbol), setup.signal_time) is True:
        return False
    stock = _lookup(above.get(setup.symbol), setup.signal_time)
    market = spy_up.get(_day(setup.signal_time))
    if mode == "stock":
        return stock is True
    if mode == "spy":
        return market is True
    return stock is True and market is True


def _filter_keep(setup, chop) -> bool:
    return _lookup(chop.get(setup.symbol), setup.signal_time) is not True


def _spy_check(frame: pd.DataFrame, flag: pd.Series) -> dict:
    mask = np.array([SPY_FROM <= _day(ts) <= SPY_TO for ts in frame.index])
    window = frame.loc[mask]
    part = flag.loc[mask]
    closes = window["close"].astype(float)
    in_zone = (closes >= SPY_ZONE[0]) & (closes <= SPY_ZONE[1])
    chop = part.fillna(False).astype(bool)
    zone_chop = int((chop & in_zone).sum())
    run = _longest(chop.to_numpy(dtype=bool))
    levels = merged_swings(frame)
    width = float(atr(frame).iloc[-1])
    hits = []
    for price in DRAWN:
        nearest = min(levels, key=lambda row: abs(row["price"] - price)) if levels else None
        distance = None if nearest is None else abs(nearest["price"] - price)
        hits.append(
            {
                "drawn": price,
                "label": DRAWN_LABEL[price],
                "nearest": None if nearest is None else nearest["price"],
                "touches": 0 if nearest is None else nearest["touches"],
                "distance": distance,
                "hit": distance is not None and np.isfinite(width) and distance <= 0.5 * width,
            }
        )
    return {
        "bars": int(len(window)),
        "chop_bars": int(chop.sum()),
        "zone_chop": zone_chop,
        "longest": run,
        "high": float(window["high"].max()) if len(window) else float("nan"),
        "low": float(window["low"].min()) if len(window) else float("nan"),
        "last": float(frame["close"].iloc[-1]),
        "atr": width,
        "levels": levels,
        "hits": hits,
        "marks": zone_chop >= 6 and run >= 6,
    }


def _longest(flags: np.ndarray) -> int:
    best = 0
    run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best


def _nvda_check(frame: pd.DataFrame, flag: pd.Series, marks: list) -> dict:
    days = []
    for ts in frame.index:
        day = _day(ts)
        if day not in days:
            days.append(day)
    keep_days = set(days[-NVDA_SESSIONS:])
    mask = np.array([_day(ts) in keep_days for ts in frame.index])
    window = frame.loc[mask]
    part = flag.reindex(window.index).fillna(False).astype(bool)
    low_line, high_line = NVDA_PULLBACK
    overlaps = (window["low"].astype(float) <= high_line) & (window["high"].astype(float) >= low_line)
    after = np.array([_day(ts) >= NVDA_FRIDAY for ts in window.index])
    pullback = part.to_numpy(dtype=bool) & overlaps.to_numpy(dtype=bool) & after
    before = part.to_numpy(dtype=bool) & ~after
    window_marks = [mark for mark in marks if mark.setup.symbol == "NVDA" and _day(mark.setup.signal_time) in keep_days]
    return {
        "bars": int(len(window)),
        "chop_bars": int(part.sum()),
        "before": int(before.sum()),
        "pullback_bars": int(pullback.sum()),
        "pullback_run": _longest(pullback),
        "high": float(window["high"].max()) if len(window) else float("nan"),
        "low": float(window["low"].min()) if len(window) else float("nan"),
        "last": float(window["close"].iloc[-1]) if len(window) else float("nan"),
        "friday": _friday(window),
        "marks": window_marks,
        "marks_zone": _longest(pullback) >= 6,
        "start": min(keep_days).isoformat() if keep_days else "",
        "end": max(keep_days).isoformat() if keep_days else "",
        "window": window,
        "flag": part,
    }


def _friday(window: pd.DataFrame) -> dict:
    day = window.loc[[_day(ts) == NVDA_FRIDAY for ts in window.index]]
    if day.empty:
        return {}
    return {
        "low": float(day["low"].min()),
        "high": float(day["high"].max()),
        "close": float(day["close"].iloc[-1]),
    }


def _hold_buy(frame: pd.DataFrame, start: date, end: date) -> dict:
    window = frame.loc[(frame.index.date >= start) & (frame.index.date <= end)]
    empty = compute_metrics(BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()), STARTING)
    if window.empty:
        return empty
    entry = float(window.iloc[0]["open"]) * (1.0 + 6.0 / 10_000.0)
    exit_ = float(window.iloc[-1]["close"]) * (1.0 - 6.0 / 10_000.0)
    shares = int(np.floor(STARTING / entry)) if entry > 0 else 0
    if shares < 1:
        empty["shares"] = 0
        return empty
    cash = STARTING - shares * entry
    equity = window["close"].astype(float) * shares + cash
    equity.iloc[0] = cash + shares * entry
    equity.iloc[-1] = cash + shares * exit_
    trades = pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "strategy": "buy_and_hold",
                "quantity": shares,
                "entry_time": window.index[0],
                "entry_price": entry,
                "exit_time": window.index[-1],
                "exit_price": exit_,
                "pnl": (exit_ - entry) * shares,
                "fees": 0.0,
                "reason": "window_end",
                "bars_held": len(window),
            }
        ]
    )
    result = BacktestResult(
        equity=equity,
        exposure=pd.Series(0.0, index=equity.index),
        trades=trades,
        ending_equity=float(equity.iloc[-1]),
    )
    metrics = compute_metrics(result, STARTING)
    metrics["shares"] = shares
    return metrics


def _walk(frames, daily, books: list[tuple[dict, list]], params: dict, start_days: list[date]) -> dict:
    """Pick a chop cell on the bars before each test fold. Score only the fold."""
    if len(start_days) < 40:
        empty = compute_metrics(BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()), STARTING)
        return {"metrics": empty, "folds": 0, "chosen": []}
    half = len(start_days) // 2
    test_days = start_days[half:]
    width = max(1, len(test_days) // 3)
    folds = []
    chosen_labels = []
    for fold in range(3):
        start_i = fold * width
        end_i = len(test_days) if fold == 2 else min(len(test_days), (fold + 1) * width)
        if start_i >= len(test_days):
            break
        test = test_days[start_i:end_i]
        if not test:
            continue
        train_cut = pd.Timestamp(test[0]) - pd.Timedelta(days=180)
        train = [day for day in start_days if train_cut.date() <= day < test[0]]
        if len(train) < 5:
            continue
        rows = []
        for cell, setups in books:
            stats = _score(setups, frames, daily, params, intraday_window, train[0], train[-1])
            rows.append({"params": cell, **stats.metrics})
        chosen = pick_params(rows, books[0][0], min_trades=15)
        chosen_setups = books[0][1]
        for cell, setups in books:
            if _same_cell(cell, chosen):
                chosen_setups = setups
                break
        stats = _score(chosen_setups, frames, daily, params, intraday_window, test[0], test[-1])
        folds.append(stats)
        chosen_labels.append(cell_label(chosen))
        print(
            f"    fold {fold + 1} {test[0]}..{test[-1]} {cell_label(chosen)} "
            f"trades {stats.metrics.get('trades')}",
            flush=True,
        )
    return {"metrics": _stitch(folds), "folds": len(folds), "chosen": chosen_labels}


def _exit_block(name, setups, frames, daily, base, window, start, end, *, random_frame=None) -> dict:
    print(f"  exits {name} signals {len(setups)}", flush=True)
    rows = []
    for label, params in (
        ("level target", _level_params(base)),
        ("trail 15%", _trail_params(base)),
        ("bracket 2R", _bracket_params(base)),
    ):
        stats = _score(setups, frames, daily, params, window, start, end)
        rows.append(_row(label, stats))
        print(f"    {label} {_metrics_bits(stats.metrics)}", flush=True)
    shuffled = None
    if random_frame is not None and setups:
        shuffled_setups = random_setups(setups, random_frame, seed=17)
        shuffled = _score(shuffled_setups, frames, daily, _level_params(base), window, start, end).metrics
        trail_random = _score(shuffled_setups, frames, daily, _trail_params(base), window, start, end).metrics
    else:
        trail_random = None
    return {"name": name, "signals": len(setups), "rows": rows, "random_level": shuffled, "random_trail": trail_random}


def _save_spy(frame, flag, check, path: Path) -> None:
    window = frame.iloc[-260:]
    part = flag.reindex(window.index).fillna(False).astype(bool)
    fig, ax = plt.subplots(figsize=(13.5, 7.2))
    ax.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    xs = np.arange(len(window))
    flags = part.to_numpy(dtype=bool)
    for pos, on in enumerate(flags):
        if on:
            ax.axvspan(pos - 0.5, pos + 0.5, color="#f2d16b", alpha=0.35, linewidth=0)
    band = [pos for pos, ts in enumerate(window.index) if SPY_FROM <= _day(ts) <= SPY_TO]
    if band:
        ax.axvspan(band[0] - 0.5, band[-1] + 0.5, color="#4ea3ff", alpha=0.08, label="Aug-Oct")
    ax.axhspan(SPY_ZONE[0], SPY_ZONE[1], color="#f2d16b", alpha=0.08, label="755-775")
    for pos, (_, row) in enumerate(window.iterrows()):
        color = "#3d9e57" if row["close"] >= row["open"] else "#d64545"
        ax.plot([pos, pos], [row["low"], row["high"]], color=color, linewidth=0.8)
        ax.plot([pos, pos], [min(row["open"], row["close"]), max(row["open"], row["close"])], color=color, linewidth=2.2)
    close = frame["close"].astype(float)
    ax.plot(xs, ema(close, 9).reindex(window.index), color="#4ea3ff", linewidth=1.0, label="EMA 9")
    ax.plot(xs, ema(close, 20).reindex(window.index), color="#e0a100", linewidth=1.0, label="EMA 20")
    for row in check["levels"]:
        ax.axhline(row["price"], color="#d0d0d0", linewidth=0.6 + min(row["touches"], 8) * 0.05, alpha=0.7)
    for price in DRAWN:
        ax.axhline(price, color="#888888", linewidth=0.6, linestyle=":")
    ax.set_title(
        f"SPY daily through {AS_OF.isoformat()}, chop v2 {check['chop_bars']}/{check['bars']} in Aug-Oct",
        color="white",
    )
    ax.tick_params(colors="#cccccc")
    for spine in ax.spines.values():
        spine.set_color("#333333")
    ax.legend(facecolor="#161616", edgecolor="#333333", labelcolor="white", loc="upper left")
    step = max(1, len(window) // 6)
    ticks = list(range(0, len(window), step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(window.index[pos]).strftime("%Y-%m-%d") for pos in ticks], rotation=30, ha="right")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _save_nvda(hourly, flag, check, levels, path: Path) -> None:
    window = check["window"]
    part = check["flag"]
    fig, (ax, vol) = plt.subplots(2, 1, figsize=(13.5, 7.4), sharex=True, gridspec_kw={"height_ratios": [3.2, 1.0]})
    ax.set_facecolor("#161616")
    vol.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    flags = part.fillna(False).to_numpy(dtype=bool)
    for pos, on in enumerate(flags):
        if on:
            ax.axvspan(pos - 0.5, pos + 0.5, color="#f2d16b", alpha=0.35, linewidth=0)
            vol.axvspan(pos - 0.5, pos + 0.5, color="#f2d16b", alpha=0.35, linewidth=0)
    low_line, high_line = NVDA_PULLBACK
    ax.axhspan(low_line, high_line, color="#f2d16b", alpha=0.08, label="annotated pullback")
    for price in NVDA_LINES:
        ax.axhline(price, color="#888888", linewidth=0.7, linestyle=":")
    for row in levels:
        if window["low"].min() - 5 <= row["price"] <= window["high"].max() + 5:
            ax.axhline(row["price"], color="#d0d0d0", linewidth=0.5, alpha=0.5)
    friday = [pos for pos, ts in enumerate(window.index) if _day(ts) == NVDA_FRIDAY]
    if friday:
        ax.axvline(friday[0], color="#d0d0d0", linewidth=0.8, linestyle="--")
    for pos, (_, row) in enumerate(window.iterrows()):
        color = "#3d9e57" if row["close"] >= row["open"] else "#d64545"
        ax.plot([pos, pos], [row["low"], row["high"]], color=color, linewidth=0.8)
        ax.plot([pos, pos], [min(row["open"], row["close"]), max(row["open"], row["close"])], color=color, linewidth=2.4)
    xs = np.arange(len(window))
    close = hourly["close"].astype(float)
    ax.plot(xs, ema(close, 9).reindex(window.index), color="#4ea3ff", linewidth=1.0, label="EMA 9")
    ax.plot(xs, ema(close, 20).reindex(window.index), color="#e0a100", linewidth=1.0, label="EMA 20")
    vol.bar(
        xs,
        window["volume"].to_numpy(dtype=float),
        color=["#3d9e57" if row.close >= row.open else "#d64545" for row in window.itertuples()],
        width=0.7,
    )
    entry = "no hold entry" if not check["marks"] else f"{len(check['marks'])} hold entries"
    ax.set_title(f"NVDA 60-minute {check['start']} through {check['end']}, chop v2, {entry}", color="white")
    ax.tick_params(colors="#cccccc")
    vol.tick_params(colors="#cccccc")
    for spine in (*ax.spines.values(), *vol.spines.values()):
        spine.set_color("#333333")
    ax.legend(facecolor="#161616", edgecolor="#333333", labelcolor="white", loc="upper left")
    step = max(1, len(window) // 6)
    ticks = list(range(0, len(window), step))
    vol.set_xticks(ticks)
    vol.set_xticklabels(
        [pd.Timestamp(window.index[pos]).strftime("%m-%d %H:%M") for pos in ticks],
        rotation=30,
        ha="right",
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _hit_table(hits: list[dict]) -> str:
    lines = [
        "| Drawn | Nearest merged swing | Touches | Distance | Within 0.5 ATR |",
        "|---|---:|---:|---:|---|",
    ]
    for row in hits:
        nearest = "n/a" if row["nearest"] is None else f"{row['nearest']:.2f}"
        distance = "n/a" if row["distance"] is None else f"{row['distance']:.2f}"
        lines.append(
            f"| {row['label']} | {nearest} | {row['touches']} | {distance} | {'yes' if row['hit'] else 'no'} |"
        )
    return "\n".join(lines)


def _time_md(rows: list[dict]) -> str:
    lines = ["| Symbol | Bars | Chop bars | Share |", "|---|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['symbol']} | {row['bars']} | {row['chop_bars']} | {row['share'] * 100:.1f}% |")
    return "\n".join(lines)


def _exit_md(block: dict) -> str:
    lines = [
        f"**{block['name']}.** {block['signals']} signals.",
        "",
        "| Exit | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in block["rows"]:
        metrics = row["metrics"]
        lines.append(
            "| {label} | {trades} | {win} | {exp} | {pf} | {sharpe} | {dd} | {ending} |".format(
                label=row["label"],
                trades=int(metrics.get("trades") or 0),
                win=_pct(metrics.get("win_rate")),
                exp=_money(metrics.get("expectancy")),
                pf=_pf(metrics.get("profit_factor")),
                sharpe=_num(metrics.get("sharpe")),
                dd=_dd(metrics.get("max_drawdown")),
                ending=_money(metrics.get("ending_equity")),
            )
        )
    if block.get("random_level") is not None:
        lines.append("")
        lines.append(f"Random entries, same level-target exit: {_metrics_bits(block['random_level'])}.")
    if block.get("random_trail") is not None:
        lines.append(f"Random entries, same 15% trail: {_metrics_bits(block['random_trail'])}.")
    primary = block["rows"][0]["metrics"]
    lines.append(
        f"The gate reads the level-target row. It {'clears' if _gate(primary) else 'does not clear'} "
        "profit factor 1.10, Sharpe 0.40, drawdown no worse than -30%, and 300 trades."
    )
    return "\n".join(lines)


def render(payload: dict) -> str:
    spy = payload["spy"]
    nvda = payload["nvda"]
    lines = [
        "## Chop v2",
        "",
        "DOES NOT CHANGE THE GATE. The v1 chop flag is unchanged. This flag drops the tangled-EMA requirement. "
        "Quiet volume is relative volume under 0.85, or a declining 20-bar average versus the 60-bar average "
        "while the bar is still at most 1.20 times its own average. Narrow range is ATR at or under 0.85 times "
        "its prior 120-bar average, or Bollinger bandwidth in the bottom 20% of 120 bars, or a 10-bar box inside "
        "1.5 ATR. Rotation is three crosses of VWAP or of that box midpoint in 20 bars, or a stacked 9/20 EMA "
        "flag within 0.75 ATR and 1.5 ATR of price. The grid changes one of those round numbers at a time. "
        "The default above is the gated cell. A cell chosen on earlier data is a sensitivity. "
        "Nothing was sent to a broker. Live trading stays off.",
        "",
        (
            f"SPY daily, {SPY_FROM.isoformat()} through {SPY_TO.isoformat()}, the 755-775 stretch. "
            f"Chop v2 is on for {spy['chop_bars']} of {spy['bars']} bars. {spy['zone_chop']} of those closes "
            f"sit inside 755-775. The longest run is {spy['longest']} bars. "
            + (
                "That is enough of a run inside the band to call the stretch marked."
                if spy["marks"]
                else "That is not a six-bar chop zone inside the band, so the stretch is not marked."
            )
            + " The threshold was not moved after this check."
        ),
        "",
        (
            f"NVDA 60-minute, {nvda['start']} through {nvda['end']}. The window high is {_money(nvda['high'])} "
            f"against the annotated {_money(NVDA_HIGH)}. The last close is {_money(nvda['last'])} against "
            f"{_money(NVDA_PRICE)}. Friday trades {_money(nvda['friday'].get('low'))} to {_money(nvda['friday'].get('high'))} "
            f"and closes {_money(nvda['friday'].get('close'))}. Chop v2 is on for {nvda['chop_bars']} of {nvda['bars']} bars, "
            f"{nvda['before']} of them before Friday and {nvda['pullback_bars']} on or after Friday inside 232.5-235. "
            f"The longest such pullback run is {nvda['pullback_run']} bars. "
            + (
                "The annotated pullback is marked."
                if nvda["marks_zone"]
                else "The annotated pullback is not marked as a six-bar chop zone."
            )
            + f" Hold entries in the window: {len(nvda['marks'])}. The rule was not retuned."
        ),
        "",
        "Merged swings keep every confirmed pivot in the last 250 daily bars and collapse prices within 0.5 ATR, "
        "weighted by touches. The old 120-bar set of six highs and six lows is unchanged.",
        "",
        _hit_table(spy["hits"]),
        "",
        f"SPY ATR on the last bar is {_money(spy['atr'])}. A hit is a merged swing within 0.5 ATR of the drawn line.",
        "",
        "Time in chop, default cell, named list, daily bars from 2023-01-01 through 2026-10-06.",
        "",
        _time_md(payload["time_daily"]),
        "",
        f"Dow daily holdout, {_share_line(payload['time_dow'])}.",
        "",
        "Named list, 60-minute regular hours, the whole Yahoo window.",
        "",
        _time_md(payload["time_hourly"]),
        "",
        "### Breakout, chop pullback, hold, resume",
        "",
        payload["hold_text"],
        "",
        "### Chop-box breakout, relative volume above 1.5",
        "",
        payload["breakout_text"],
        "",
        "### No-trade filter on A-D and the bounce",
        "",
        payload["filter_text"],
        "",
        "### Bounce, 15% trail, regime and chop v2",
        "",
        payload["bounce_text"],
        "",
        "Charts: `reports/setups/readCHOPv2_SPY_1d.png` and `reports/setups/readCHOPv2_NVDA_60m.png`.",
        "",
        "Not added to `config/optional_strategies.json`. The published A-D books, the v1 chop flag, the 120-bar "
        "level set, and the bounce's published trail are unchanged. The default book is still dual momentum.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _hold_text(books: list[dict], walks: list[dict]) -> str:
    parts = []
    for book, walk in zip(books, walks):
        parts.append(_exit_md(book))
        if walk is not None:
            parts.append(
                f"Walk-forward on the level target, cell chosen inside each training fold: "
                f"{_metrics_bits(walk['metrics'])}. Cells: {', '.join(walk['chosen']) or 'none'}."
            )
        parts.append("")
    return "\n".join(parts).rstrip()


def _breakout_text(daily_block, daily_choice, hourly_block, hourly_walk, slow_block, hold) -> str:
    choice = (
        f"The training window {SCORE_FROM.isoformat()} through {TRAIN_END.isoformat()} chose "
        f"{daily_choice['label']} ({_metrics_bits(daily_choice['train'])}). "
        f"On the holdout that cell is {_metrics_bits(daily_choice['holdout'])}. "
        "It does not replace the default."
    )
    buy = (
        f"SPY buy and hold, whole shares that fit in $1,000, {HOLDOUT_START.isoformat()} through "
        f"{SAMPLE_END.isoformat()}: {int(hold.get('shares') or 0)} shares, {_metrics_bits(hold)}."
    )
    return "\n\n".join(
        [
            f"Daily Dow, default cell, {HOLDOUT_START.isoformat()} through {SAMPLE_END.isoformat()}.",
            _exit_md(daily_block),
            choice,
            buy,
            "Hourly named list, default cell, the second half of the Yahoo sample.",
            _exit_md(hourly_block),
            (
                f"Hourly walk-forward, level target: {_metrics_bits(hourly_walk['metrics'])}. "
                f"Cells: {', '.join(hourly_walk['chosen']) or 'none'}."
            ),
            "15-minute named list, default cell, the whole short Yahoo window. Anecdotal.",
            _exit_md(slow_block),
        ]
    )


def _filter_text(rows: list[dict]) -> str:
    lines = [
        "Skip a signal when the default chop-v2 flag is on at the signal close. "
        "The flag helps only when out-of-sample expectancy is higher, losing trades are fewer, "
        "and at least 20 trades remain. That label does not change the gate. "
        "Daily rows are the 2023-2026 holdout. Hourly rows are the second half of the Yahoo sample.",
        "",
        "| Book | Window | Baseline | Skip chop v2 | Inside | Helps |",
        "|---|---|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['name']} | {row['window']} | {_metrics_bits(row['base'])} | {_metrics_bits(row['skip'])} | "
            f"{row['inside']} | {'yes' if row['helps'] else 'no'} |"
        )
    notes = [row["note"] for row in rows if row.get("note")]
    return "\n".join(lines + ([""] + notes if notes else []))


def _bounce_text(payload: dict) -> str:
    lines = [
        "The exit is the 15% trail, the bounce row that led the earlier exit study. "
        f"Replaying that published window ({OOS_START.isoformat()} through {SAMPLE_END.isoformat()}) "
        f"produced {_metrics_bits(payload['published_replay'])}. "
        f"The gated writeup is {_money(PUBLISHED_TRAIL[0])} on {PUBLISHED_TRAIL[1]} trades. "
        + (
            "This replay matches."
            if payload["published_match"]
            else "This replay does not replace that writeup. The new test below uses the 2023-2026 holdout."
        ),
        "",
        "The new test keeps the 15% trail and adds two filters: the default chop-v2 flag is off, and the regime "
        "cell is the stock above its own 200-day average. SPY above its 200-day average, and both together, "
        "are the grid. The choice, if one is reported, comes from 2010 through 2022. The gate reads the "
        "stock-above-200 default on 2023-2026, not the best holdout row.",
        "",
        "| Book | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["rows"]:
        metrics = row["metrics"]
        lines.append(
            "| {label} | {trades} | {win} | {exp} | {pf} | {sharpe} | {dd} | {ending} |".format(
                label=row["label"],
                trades=int(metrics.get("trades") or 0),
                win=_pct(metrics.get("win_rate")),
                exp=_money(metrics.get("expectancy")),
                pf=_pf(metrics.get("profit_factor")),
                sharpe=_num(metrics.get("sharpe")),
                dd=_dd(metrics.get("max_drawdown")),
                ending=_money(metrics.get("ending_equity")),
            )
        )
    default = payload["default"]
    lines.extend(
        [
            "",
            f"Training chose `{payload['chosen']}` "
            f"({_metrics_bits(payload['chosen_train'])} in sample). "
            f"That cell on the holdout is {_metrics_bits(payload['chosen_holdout'])}.",
            "",
            f"Random entries with the same 15% trail, matched to the default filtered signals: "
            f"{_metrics_bits(payload['random'])}.",
            f"SPY buy and hold over the holdout: {int(payload['hold'].get('shares') or 0)} shares, "
            f"{_metrics_bits(payload['hold'])}.",
            (
                f"Against those random entries the default book {'beats' if payload['beats_random'] else 'does not beat'} "
                "them on Sharpe with a drawdown that is not worse. "
                f"Against SPY buy and hold it {'beats' if payload['beats_hold'] else 'does not beat'} "
                "that comparison. "
                f"The gate {'clears' if _gate(default) else 'does not clear'}."
            ),
        ]
    )
    return "\n".join(lines)


def write_report(text: str, path: Path) -> None:
    body = path.read_text() if path.exists() else ""
    block = f"{START}\n{text.rstrip()}\n{END_MARK}\n"
    if START in body and END_MARK in body:
        pre, rest = body.split(START, 1)
        _, post = rest.split(END_MARK, 1)
        path.write_text(pre.rstrip() + "\n\n" + block + post.lstrip("\n"))
        return
    marker = "<!-- CHART_READS_HOLD_END -->"
    if marker in body:
        pre, post = body.split(marker, 1)
        path.write_text(pre + marker + "\n\n" + block + post.lstrip("\n"))
        return
    path.write_text(body.rstrip() + "\n\n" + block)


def write_readme(text: str, path: Path) -> None:
    body = path.read_text()
    paragraph = text.strip() + "\n\n"
    key = "**Chop v2:"
    if key in body:
        start = body.index(key)
        nxt = body.find("\n**", start + len(key))
        if nxt < 0:
            nxt = len(body)
        path.write_text(body[:start] + paragraph + body[nxt:].lstrip("\n"))
        return
    anchor = "**Chart Fanatics specs:"
    if anchor not in body:
        raise SystemExit("README has no Chart Fanatics paragraph to insert before")
    path.write_text(body.replace(anchor, paragraph + anchor, 1))


def _readme(payload: dict) -> str:
    spy = payload["spy"]
    nvda = payload["nvda"]
    default = payload["bounce"]["default"]
    return (
        "**Chop v2: does not pass.** The tangled-EMA leg is gone. Chop is quiet volume, a narrow range, "
        "and either several crosses of VWAP or the box midpoint, or a stacked EMA flag. "
        f"On SPY from {SPY_FROM.isoformat()} through {SPY_TO.isoformat()} the flag is on for "
        f"{spy['chop_bars']} of {spy['bars']} bars"
        f"{' and marks the 755-775 stretch' if spy['marks'] else ' and does not mark the 755-775 stretch'}. "
        f"On the NVDA hourly window it is on for {nvda['chop_bars']} of {nvda['bars']} bars, with "
        f"{nvda['pullback_bars']} on or after Friday inside 232.5-235"
        f"{' so the pullback is marked' if nvda['marks_zone'] else ' so the annotated pullback is not marked'}. "
        f"The bounce with the 15% trail, the stock above its 200-day average, and chop v2 off "
        f"is {_metrics_bits(default)} on the 2023-2026 holdout. "
        "The longer swing list keeps 250 daily bars and merges levels within 0.5 ATR. "
        "Nothing was added to the optional list. The default book is still dual momentum. "
        "Full table in [RESULTS.md](RESULTS.md)."
    )


def _jsonable(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _rth_map(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    kept = {}
    for symbol, frame in frames.items():
        if frame is None or len(frame) < 30:
            continue
        bars = rth(frame)
        if bars is not None and len(bars) > 30:
            kept[symbol] = bars
    return kept


def _half(frames) -> tuple[date, date]:
    days = _sessions(frames)
    _train, test = _split(days, 0.50)
    return test[0], test[-1]


def _losers(stats) -> int:
    trades = getattr(stats, "trades", None)
    if trades is None or len(trades) == 0 or "pnl" not in trades.columns:
        return 0
    return int((trades["pnl"].astype(float) < 0).sum())


def main() -> None:
    print("loading daily history", flush=True)
    daily_frames, missing = load_daily()
    print(f"  {len(daily_frames)} symbols, missing {missing}", flush=True)
    print("chop v2 components, daily", flush=True)
    daily_cache = _cache(daily_frames)
    daily_flag = _masks(daily_cache)

    spy_frame = daily_frames["SPY"]
    spy = _spy_check(spy_frame, daily_flag["SPY"])
    print(
        f"  SPY Aug-Oct chop {spy['chop_bars']}/{spy['bars']} zone {spy['zone_chop']} longest {spy['longest']}",
        flush=True,
    )
    report_dir = Path("reports/setups")
    spy_path = report_dir / "readCHOPv2_SPY_1d.png"
    _save_spy(spy_frame, daily_flag["SPY"], spy, spy_path)

    print("loading intraday", flush=True)
    provider = YFinanceProvider("data/cache")
    daily_short, hourly, m15, _m5 = load_yahoo(provider)
    del _m5
    present = [symbol for symbol in SYMBOLS if symbol in hourly and symbol in daily_short]
    hourly = {symbol: hourly[symbol] for symbol in present}
    m15 = {symbol: m15[symbol] for symbol in present if symbol in m15}
    daily_short = {symbol: daily_short[symbol] for symbol in present}
    hourly_rth = _rth_map(hourly)
    m15_rth = _rth_map(m15)
    print("chop v2 components, hourly", flush=True)
    hourly_cache = _cache(hourly_rth)
    hourly_flag = _masks(hourly_cache)
    nvda_flag = mask_from(components(hourly_rth["NVDA"]))
    nvda_marks, _nvda_counts = _holds({"NVDA": hourly["NVDA"]})
    nvda = _nvda_check(hourly_rth["NVDA"], nvda_flag, nvda_marks)
    print(
        f"  NVDA chop {nvda['chop_bars']}/{nvda['bars']} pullback {nvda['pullback_bars']} "
        f"run {nvda['pullback_run']} entries {len(nvda['marks'])}",
        flush=True,
    )
    nvda_levels = merged_swings(daily_frames["NVDA"]) if "NVDA" in daily_frames else []
    nvda_path = report_dir / "readCHOPv2_NVDA_60m.png"
    _save_nvda(hourly_rth["NVDA"], nvda_flag, nvda, nvda_levels, nvda_path)
    for path in (spy_path, nvda_path):
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, ARTIFACT_DIR / path.name)

    named_daily = {symbol: daily_frames[symbol] for symbol in SYMBOLS if symbol in daily_flag}
    time_daily = _time_table(named_daily, {symbol: daily_flag[symbol] for symbol in named_daily}, HOLDOUT_START, SAMPLE_END)
    dow_symbols = [symbol for symbol in all_dow_tickers() if symbol in daily_flag]
    time_dow = _time_table(
        daily_frames,
        {symbol: daily_flag[symbol] for symbol in dow_symbols},
        HOLDOUT_START,
        SAMPLE_END,
    )
    time_hourly = _time_table(hourly_rth, hourly_flag, None, None)

    print("hold scans", flush=True)
    hold_60_marks, hold_60_counts = _holds(hourly)
    hold_15_marks, hold_15_counts = _holds(m15)
    print(f"  60m {len(hold_60_marks)} {hold_60_counts}", flush=True)
    print(f"  15m {len(hold_15_marks)} {hold_15_counts}", flush=True)
    hold_start, hold_end = _half(hourly_rth)
    base_60 = _cells("60m")[0]
    base_15 = _cells("15m")[0]
    hold_books = []
    hold_walks = []
    setups_60 = [mark.setup for mark in hold_60_marks]
    hold_books.append(
        _exit_block(
            f"Chop-hold v2, 60-minute, {hold_start.isoformat()} through {hold_end.isoformat()}",
            [setup for setup in setups_60 if hold_start <= _day(setup.fill_time) <= hold_end],
            hourly,
            daily_short,
            base_60,
            intraday_window,
            hold_start,
            hold_end,
            random_frame=_slice_intraday(hourly, hold_start, hold_end),
        )
    )
    print("  walk-forward hold", flush=True)
    hold_cells = []
    for cell in grid():
        marks, _counts = _holds(hourly, cell)
        hold_cells.append((cell, [mark.setup for mark in marks]))
        print(f"    {cell_label(cell)} signals {len(marks)}", flush=True)
    hold_walks.append(_walk(hourly, daily_short, hold_cells, _level_params(base_60), _sessions(hourly_rth)))
    slow_days = _sessions(m15_rth)
    slow_start, slow_end = (slow_days[0], slow_days[-1]) if slow_days else (AS_OF, AS_OF)
    setups_15 = [mark.setup for mark in hold_15_marks]
    hold_books.append(
        _exit_block(
            f"Chop-hold v2, 15-minute, {slow_start.isoformat()} through {slow_end.isoformat()}",
            setups_15,
            m15,
            daily_short,
            base_15,
            intraday_window,
            slow_start,
            slow_end,
        )
    )
    hold_walks.append(None)

    print("chop breakouts", flush=True)
    cells = grid()
    daily_books = []
    for cell in cells:
        setups = _breakouts(daily_frames, daily_cache, cell, pit=True, earliest=SCORE_FROM)
        daily_books.append((cell, setups))
        print(f"  daily {cell_label(cell)} {len(setups)}", flush=True)
    default_daily = daily_books[0][1]
    train_rows = []
    for cell, setups in daily_books:
        stats = _score(setups, daily_frames, daily_frames, _level_params(_precursor_params("1d")), daily_window, SCORE_FROM, TRAIN_END)
        train_rows.append({"params": cell, **stats.metrics, "stats": stats})
        print(f"    train {cell_label(cell)} trades {stats.metrics.get('trades')}", flush=True)
    chosen_cell = pick_params(train_rows, cells[0], min_trades=15)
    chosen_setups = daily_books[0][1]
    chosen_train = train_rows[0]["stats"].metrics
    for (cell, setups), row in zip(daily_books, train_rows):
        if _same_cell(cell, chosen_cell):
            chosen_setups = setups
            chosen_train = row["stats"].metrics
            break
    chosen_holdout = _score(
        chosen_setups,
        daily_frames,
        daily_frames,
        _level_params(_precursor_params("1d")),
        daily_window,
        HOLDOUT_START,
        SAMPLE_END,
    ).metrics
    oos_frames = {
        symbol: frame.loc[(frame.index.date >= HOLDOUT_START) & (frame.index.date <= SAMPLE_END)]
        for symbol, frame in daily_frames.items()
        if frame is not None and not frame.empty
    }
    daily_block = _exit_block(
        "Daily Dow chop-v2 breakout, 2023-01-01 through 2026-10-06",
        [setup for setup in default_daily if HOLDOUT_START <= _day(setup.fill_time) <= SAMPLE_END],
        daily_frames,
        daily_frames,
        _precursor_params("1d"),
        daily_window,
        HOLDOUT_START,
        SAMPLE_END,
        random_frame=oos_frames,
    )
    print("hourly breakouts", flush=True)
    hourly_break_books = []
    for cell in cells:
        setups = _breakouts(hourly_rth, hourly_cache, cell, pit=False, earliest=None)
        hourly_break_books.append((cell, setups))
        print(f"  hourly {cell_label(cell)} {len(setups)}", flush=True)
    hourly_block = _exit_block(
        f"60-minute chop-v2 breakout, {hold_start.isoformat()} through {hold_end.isoformat()}",
        [setup for setup in hourly_break_books[0][1] if hold_start <= _day(setup.fill_time) <= hold_end],
        hourly,
        daily_short,
        _precursor_params("60m"),
        intraday_window,
        hold_start,
        hold_end,
        random_frame=_slice_intraday(hourly, hold_start, hold_end),
    )
    print("  walk-forward breakout", flush=True)
    hourly_walk = _walk(
        hourly,
        daily_short,
        hourly_break_books,
        _level_params(_precursor_params("60m")),
        _sessions(hourly_rth),
    )
    print("15m breakouts", flush=True)
    m15_cache = _cache(m15_rth)
    slow_setups = _breakouts(m15_rth, m15_cache, cells[0], pit=False, earliest=None)
    slow_block = _exit_block(
        f"15-minute chop-v2 breakout, {slow_start.isoformat()} through {slow_end.isoformat()}",
        slow_setups,
        m15,
        daily_short,
        _precursor_params("15m"),
        intraday_window,
        slow_start,
        slow_end,
    )
    buy_hold = _hold_buy(spy_frame, HOLDOUT_START, SAMPLE_END)

    print("filters", flush=True)
    filter_rows = _filters(
        hourly,
        hourly_rth,
        daily_short,
        daily_frames,
        daily_flag,
        hold_start,
        hold_end,
    )

    print("bounce regime", flush=True)
    bounce = _bounce(daily_frames, daily_flag, spy_frame)
    bounce["hold"] = buy_hold
    bounce["beats_random"] = _beats(bounce["default"], bounce["random"])
    bounce["beats_hold"] = _beats(bounce["default"], buy_hold)

    payload = {
        "spy": spy,
        "nvda": {key: value for key, value in nvda.items() if key not in ("window", "flag")},
        "time_daily": time_daily,
        "time_dow": time_dow,
        "time_hourly": time_hourly,
        "hold_text": _hold_text(hold_books, hold_walks)
        + f"\n\n60-minute counts on the full sample: {hold_60_counts}. 15-minute counts: {hold_15_counts}.",
        "breakout_text": _breakout_text(
            daily_block,
            {"label": cell_label(chosen_cell), "train": chosen_train, "holdout": chosen_holdout},
            hourly_block,
            hourly_walk,
            slow_block,
            buy_hold,
        ),
        "filter_text": _filter_text(filter_rows),
        "bounce_text": "",
        "bounce": bounce,
    }
    payload["bounce_text"] = _bounce_text(bounce)
    text = render(payload)
    write_report(text, Path("RESULTS.md"))
    write_readme(_readme(payload), Path("README.md"))
    Path("reports/chart_reads_chop_v2.json").write_text(json.dumps(_jsonable(_slim(payload)), indent=2) + "\n")
    print(text)
    print("RESEARCH CHOP V2 END", flush=True)


def _slice_intraday(frames, start: date, end: date):
    from webull_bot.chart_reads.research import _slice

    return _slice(frames, start, end)


def _filters(hourly, hourly_rth, daily_short, daily_frames, daily_flag, hold_start, hold_end) -> list[dict]:
    rows = []
    params = _cells("60m")[0]
    detected = detect_all(hourly, daily_short, {}, params)
    hourly_cache = _cache(hourly_rth)
    hourly_flag = _masks(hourly_cache)
    for kind, name, expected in (("A", "A, 60-minute", PUBLISHED_AB["A, 60-minute"]), ("B", "B, 60-minute", PUBLISHED_AB["B, 60-minute"])):
        setups = [setup for setup in detected if setup.kind == kind]
        oos = [setup for setup in setups if hold_start <= _day(setup.fill_time) <= hold_end]
        base = intraday_window(setups, hourly, daily_short, params, "stock", hold_start, hold_end)
        skipped = [setup for setup in setups if _filter_keep(setup, hourly_flag)]
        skip = intraday_window(skipped, hourly, daily_short, params, "stock", hold_start, hold_end)
        inside = sum(1 for setup in oos if not _filter_keep(setup, hourly_flag))
        ending = float(base.metrics.get("ending_equity") or 0.0)
        trades = int(base.metrics.get("trades") or 0)
        match = abs(ending - expected[0]) <= 0.02 and trades == expected[1]
        rows.append(
            {
                "name": name,
                "window": f"{hold_start.isoformat()} through {hold_end.isoformat()}",
                "base": base.metrics,
                "skip": skip.metrics,
                "inside": inside,
                "helps": filter_helps(base.metrics, skip.metrics, _losers(base), _losers(skip)),
                "note": (
                    f"{name} unfiltered still matches {_money(expected[0])} on {expected[1]} trades."
                    if match
                    else (
                        f"{name} unfiltered in this run is {_money(ending)} on {trades} trades. "
                        f"The gated writeup is {_money(expected[0])} on {expected[1]}. The filter uses this paired book."
                    )
                ),
            }
        )
        print(f"  {name} inside {inside} helps {rows[-1]['helps']}", flush=True)
    trend = _collect_daily(daily_frames, find_trend_setups, DAILY_DEFAULTS)
    breaks = _collect_daily(daily_frames, find_breakout_setups, BREAKOUT_DEFAULTS)
    bounces = _collect_bounces(daily_frames)
    for name, setups, params in (
        ("C, daily Dow", trend, DAILY_DEFAULTS),
        ("D, daily Dow", breaks, BREAKOUT_DEFAULTS),
        ("Bounce, level target", bounces, partial_params()),
    ):
        base = daily_window(setups, daily_frames, daily_frames, params, "stock", HOLDOUT_START, SAMPLE_END)
        skipped = [setup for setup in setups if _filter_keep(setup, daily_flag)]
        skip = daily_window(skipped, daily_frames, daily_frames, params, "stock", HOLDOUT_START, SAMPLE_END)
        oos = [setup for setup in setups if HOLDOUT_START <= _day(setup.fill_time) <= SAMPLE_END]
        inside = sum(1 for setup in oos if not _filter_keep(setup, daily_flag))
        rows.append(
            {
                "name": name,
                "window": f"{HOLDOUT_START.isoformat()} through {SAMPLE_END.isoformat()}",
                "base": base.metrics,
                "skip": skip.metrics,
                "inside": inside,
                "helps": filter_helps(base.metrics, skip.metrics, _losers(base), _losers(skip)),
                "note": "",
            }
        )
        print(f"  {name} inside {inside} helps {rows[-1]['helps']}", flush=True)
    return rows


def _collect_bounces(frames) -> list:
    found = []
    for symbol in sorted(all_dow_tickers()):
        frame = frames.get(symbol)
        if frame is None or len(frame) < 80:
            continue
        setups = find_bounces(frame, symbol)
        setups = [
            setup
            for setup in setups
            if _day(setup.fill_time) >= SCORE_FROM and is_member(symbol, _day(setup.signal_time))
        ]
        found.extend(setups)
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol))
    return found


def _bounce(frames, chop, spy_frame) -> dict:
    bounces = _collect_bounces(frames)
    above = {symbol: _above_sma(frame) for symbol, frame in frames.items() if frame is not None and len(frame) >= SMA_WINDOW}
    spy_up = _spy_map(spy_frame)
    trail = _trail_params(partial_params())
    published = daily_window(bounces, frames, frames, trail, "stock", OOS_START, SAMPLE_END)
    match = (
        abs(float(published.metrics.get("ending_equity") or 0.0) - PUBLISHED_TRAIL[0]) <= 0.02
        and int(published.metrics.get("trades") or 0) == PUBLISHED_TRAIL[1]
    )
    print(f"  published trail replay {_metrics_bits(published.metrics)} match {match}", flush=True)
    groups = {mode: [setup for setup in bounces if _regime_keep(setup, frames, above, spy_up, chop, mode)] for mode in REGIMES}
    train_rows = []
    for mode, setups in groups.items():
        stats = daily_window(setups, frames, frames, trail, "stock", SCORE_FROM, TRAIN_END)
        train_rows.append({"params": {"mode": mode}, **stats.metrics})
        print(f"  train {mode} {_metrics_bits(stats.metrics)}", flush=True)
    chosen = pick_params(train_rows, {"mode": REGIME_DEFAULT}, min_trades=15)
    chosen_mode = str(chosen.get("mode", REGIME_DEFAULT))
    rows = []
    plain = daily_window(bounces, frames, frames, trail, "stock", HOLDOUT_START, SAMPLE_END)
    rows.append({"label": "15% trail, no new filter", "metrics": plain.metrics})
    held = {}
    for mode, setups in groups.items():
        stats = daily_window(setups, frames, frames, trail, "stock", HOLDOUT_START, SAMPLE_END)
        held[mode] = stats.metrics
        rows.append({"label": f"15% trail, {mode} above 200-day, chop v2 off", "metrics": stats.metrics})
        print(f"  holdout {mode} {_metrics_bits(stats.metrics)}", flush=True)
    default_setups = [
        setup
        for setup in groups[REGIME_DEFAULT]
        if HOLDOUT_START <= _day(setup.fill_time) <= SAMPLE_END
    ]
    random_frames = {
        symbol: frame.loc[(frame.index.date >= HOLDOUT_START) & (frame.index.date <= SAMPLE_END)]
        for symbol, frame in frames.items()
    }
    shuffled = random_setups(default_setups, random_frames, seed=17)
    random_stats = daily_window(shuffled, frames, frames, trail, "stock", HOLDOUT_START, SAMPLE_END)
    rows.append({"label": "random entries, same 15% trail", "metrics": random_stats.metrics})
    chosen_train = next(row for row in train_rows if row["params"]["mode"] == chosen_mode)
    return {
        "published_replay": published.metrics,
        "published_match": match,
        "rows": rows,
        "default": held[REGIME_DEFAULT],
        "chosen": chosen_mode,
        "chosen_train": chosen_train,
        "chosen_holdout": held[chosen_mode],
        "random": random_stats.metrics,
    }


def _slim(payload: dict) -> dict:
    spy = payload["spy"]
    return {
        "spy": {key: spy[key] for key in ("bars", "chop_bars", "zone_chop", "longest", "marks", "atr", "hits")},
        "nvda": {
            key: payload["nvda"][key]
            for key in (
                "bars",
                "chop_bars",
                "before",
                "pullback_bars",
                "pullback_run",
                "high",
                "low",
                "last",
                "friday",
                "marks_zone",
                "start",
                "end",
            )
        },
        "nvda_entries": len(payload["nvda"]["marks"]),
        "time_daily": payload["time_daily"],
        "time_hourly": payload["time_hourly"],
        "time_dow_median": _share_line(payload["time_dow"]),
        "bounce_default": payload["bounce"]["default"],
        "bounce_match": payload["bounce"]["published_match"],
    }


if __name__ == "__main__":
    main()
