"""Score setup D. Backtests only. Does not rewrite the A/B or C results.

Descending triangles break down, ascending triangles break up, and a
horizontal range can break either way. The rules were frozen to the
three-pattern diagram before this score.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from webull_bot.backtest.assessment import fragile_grid, is_selectable, overfit_flags
from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.chart_reads.breakouts import find_breakout_setups, pattern_at
from webull_bot.chart_reads.detect import rth
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, breakout_grid
from webull_bot.chart_reads.research import (
    END,
    SYMBOLS,
    _book as intra_book,
    _slice as intra_slice,
    _window_book as intra_window,
    random_setups,
)
from webull_bot.chart_reads.research_daily import (
    IS_END,
    MIN_CONCLUSION,
    NAMED,
    OOS_START,
    SAMPLE_END,
    SCORE_FROM,
    STARTING,
    _hold,
    _money,
    _pf,
    _row,
    _table,
    _walk,
    _window_book as daily_window,
    load_daily,
)
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.universe_dow import all_dow_tickers, is_member

KIND_NAME = {
    "Dd": "lower highs + flat support, breakdown",
    "Da": "higher lows + flat resistance, breakout",
    "Dr": "horizontal range",
}


def _day(ts) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York")
    return stamp.date()


def _cell_label(cell: dict) -> str:
    changes = []
    if cell.get("pivot_left") != BREAKOUT_DEFAULTS["pivot_left"]:
        changes.append(f"pivot {cell['pivot_left']}/{cell['pivot_right']}")
    if cell.get("touch_atr") != BREAKOUT_DEFAULTS["touch_atr"]:
        changes.append(f"touch {cell['touch_atr']}")
    if cell.get("break_buffer_atr") != BREAKOUT_DEFAULTS["break_buffer_atr"]:
        changes.append(f"buffer {cell['break_buffer_atr']}")
    if cell.get("min_flat_touches") != BREAKOUT_DEFAULTS["min_flat_touches"]:
        changes.append(f"{cell['min_flat_touches']} flat touches")
    if cell.get("min_span") != BREAKOUT_DEFAULTS["min_span"]:
        changes.append(f"span {cell['min_span']}")
    if cell.get("require_retest"):
        changes.append("retest")
    return "default" if not changes else ", ".join(changes)


def _collect(frames: dict[str, pd.DataFrame], symbols: list[str], params: dict, *, pit: bool, earliest: date | None) -> list:
    found = []
    for symbol in symbols:
        frame = frames.get(symbol)
        if frame is None or len(frame) < 80:
            continue
        setups = find_breakout_setups(frame, params, symbol=symbol)
        if pit:
            setups = [setup for setup in setups if is_member(symbol, _day(setup.signal_time))]
        if earliest is not None:
            setups = [setup for setup in setups if _day(setup.fill_time) >= earliest]
        found.extend(setups)
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.kind))
    return found


def _clock(params: dict, execution: str) -> dict:
    chosen = dict(params)
    if execution == "15m":
        chosen.update(flatten_eod=True, max_hold_sessions=1, pdt_prospective=True)
    elif execution == "60m":
        chosen.update(flatten_eod=False, max_hold_sessions=5, pdt_prospective=True)
    return chosen


def _flags(oos: dict, walk: dict, train_sharpes: list[float], *, survivorship: bool, short_sample: bool) -> tuple[list[str], bool]:
    trades = int(oos.get("trades") or 0)
    flags = overfit_flags(
        default_oos=oos,
        walk_forward=walk,
        train_sharpes=train_sharpes,
        survivorship_sensitive=survivorship,
        short_sample=short_sample,
        min_trades=20,
    )
    if trades < MIN_CONCLUSION:
        flags.append("anecdotal_sample")
    selectable = is_selectable(flags, oos, min_trades=MIN_CONCLUSION) and trades >= MIN_CONCLUSION
    return flags, selectable


def _empty_walk() -> dict:
    metrics = compute_metrics(BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()), STARTING)
    return {"metrics": metrics, "pdt_blocked": 0, "premium_skipped": 0, "bust": False, "folds": 0}


def score_daily(name: str, frames, symbols, *, pit: bool, survivorship: bool) -> dict:
    cells = breakout_grid()
    print(f"detect {name}", flush=True)
    by_cell = []
    for cell in cells:
        found = _collect(frames, symbols, cell, pit=pit, earliest=SCORE_FROM)
        by_cell.append((cell, found))
        print(f"  {_cell_label(cell)} signals {len(found)}", flush=True)
    setups = by_cell[0][1]
    present = [symbol for symbol in symbols if symbol in frames]
    books = {}
    from webull_bot.chart_reads.research_daily import _slice

    oos_frames = _slice(frames, OOS_START, SAMPLE_END)
    shuffled = random_setups([setup for setup in setups if OOS_START <= _day(setup.fill_time) <= SAMPLE_END], oos_frames, seed=17)
    for expression in ("stock", "single", "spread"):
        print(f"  book {expression}", flush=True)
        books[f"full_{expression}"] = daily_window(setups, frames, frames, cells[0], expression, SCORE_FROM, SAMPLE_END)
        books[f"is_{expression}"] = daily_window(setups, frames, frames, cells[0], expression, SCORE_FROM, IS_END)
        books[f"oos_{expression}"] = daily_window(setups, frames, frames, cells[0], expression, OOS_START, SAMPLE_END)
        books[f"oos_random_{expression}"] = daily_window(shuffled, frames, frames, cells[0], expression, OOS_START, SAMPLE_END)
    print("  walk-forward", flush=True)
    walks = {expression: _walk(frames, frames, by_cell, expression) for expression in ("stock", "single", "spread")}
    grid_rows = []
    is_sharpes = []
    for cell, found in by_cell:
        stats = daily_window(found, frames, frames, cell, "stock", SCORE_FROM, IS_END)
        is_sharpes.append(float(stats.metrics.get("sharpe") or 0.0))
        grid_rows.append((_cell_label(cell), stats))
    flags = {}
    selectable = {}
    for expression in ("stock", "single", "spread"):
        flags[expression], selectable[expression] = _flags(
            books[f"oos_{expression}"].metrics,
            walks[expression]["metrics"],
            is_sharpes,
            survivorship=survivorship and expression != "spread",
            short_sample=False,
        )
    counts = Counter(setup.kind for setup in setups)
    return {
        "name": name,
        "symbols": present,
        "signals": len(setups),
        "longs": sum(1 for setup in setups if setup.direction == "long"),
        "shorts": sum(1 for setup in setups if setup.direction == "short"),
        "kinds": dict(counts),
        "books": books,
        "walks": walks,
        "flags": flags,
        "selectable": selectable,
        "fragile": fragile_grid(is_sharpes),
        "grid_rows": grid_rows,
        "setups": setups,
    }


def _split_days(frames) -> tuple[date, date, date, date, int]:
    days = sorted({_day(ts) for frame in frames.values() for ts in frame.index})
    if len(days) < 4:
        return days[0], days[-1], days[0], days[-1], len(days)
    cut = max(1, int(len(days) * 0.60))
    return days[0], days[cut - 1], days[cut], days[-1], len(days)


def score_intraday(name: str, frames, daily, execution: str) -> dict:
    print(f"detect {name}", flush=True)
    if not frames:
        raise SystemExit(f"{name} has no bars. Not scoring.")
    params = _clock(BREAKOUT_DEFAULTS, execution)
    setups = _collect(frames, list(frames), BREAKOUT_DEFAULTS, pit=False, earliest=None)
    print(f"  signals {len(setups)}", flush=True)
    start, is_end, oos_start, end, sessions = _split_days(frames)
    books = {}
    oos_frames = intra_slice(frames, oos_start, end)
    oos_setups = [setup for setup in setups if oos_start <= _day(setup.fill_time) <= end]
    shuffled = random_setups(oos_setups, oos_frames, seed=17)
    for expression in ("stock", "single", "spread"):
        print(f"  book {expression}", flush=True)
        books[f"full_{expression}"] = intra_book(setups, frames, daily, params, expression)
        books[f"is_{expression}"] = intra_window(setups, frames, daily, params, expression, start, is_end)
        books[f"oos_{expression}"] = intra_window(setups, frames, daily, params, expression, oos_start, end)
        books[f"oos_random_{expression}"] = intra_book(shuffled, oos_frames, daily, params, expression)
    walks = {expression: _empty_walk() for expression in ("stock", "single", "spread")}
    flags = {}
    selectable = {}
    for expression in ("stock", "single", "spread"):
        flags[expression], selectable[expression] = _flags(
            books[f"oos_{expression}"].metrics,
            walks[expression]["metrics"],
            [],
            survivorship=expression != "spread",
            short_sample=True,
        )
    counts = Counter(setup.kind for setup in setups)
    return {
        "name": name,
        "execution": execution,
        "symbols": list(frames),
        "sessions": sessions,
        "is": (start, is_end),
        "oos": (oos_start, end),
        "signals": len(setups),
        "longs": sum(1 for setup in setups if setup.direction == "long"),
        "shorts": sum(1 for setup in setups if setup.direction == "short"),
        "kinds": dict(counts),
        "books": books,
        "walks": walks,
        "flags": flags,
        "selectable": selectable,
        "fragile": False,
        "grid_rows": [],
        "setups": setups,
    }


def _candles(ax, window: pd.DataFrame) -> None:
    for i, (_ts, row) in enumerate(window.iterrows()):
        color = "#3dcc6d" if row["close"] >= row["open"] else "#e24b4b"
        ax.plot([i, i], [row["low"], row["high"]], color=color, linewidth=0.8)
        ax.plot([i, i], [min(row["open"], row["close"]), max(row["open"], row["close"])], color=color, linewidth=3.2, solid_capstyle="butt")


def _save_one(frame: pd.DataFrame, setup, path: Path, *, note: str) -> None:
    bars = frame.sort_index()
    loc = int(bars.index.get_indexer([setup.signal_time])[0])
    pattern = None
    for step in range(0, 8):
        if loc - step < 0:
            break
        candidate = pattern_at(bars, BREAKOUT_DEFAULTS, bars.index[loc - step])
        if candidate is not None and candidate.kind == setup.kind:
            pattern = candidate
            break
    if pattern is None:
        start = max(0, loc - 40)
    else:
        start = max(0, pattern.start - 4)
    stop = min(len(bars), loc + 12)
    window = bars.iloc[start:stop]
    fig, ax = plt.subplots(figsize=(12.2, 6.0))
    ax.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    _candles(ax, window)
    if pattern is not None:
        ax.axhline(pattern.support, color="#d0d0d0", linewidth=1.0, linestyle="--")
        ax.axhline(pattern.resistance, color="#d0d0d0", linewidth=1.0, linestyle="--")
        if pattern.x1 >= 0 and pattern.x2 > pattern.x1:
            xs = []
            ys = []
            for index in (pattern.x1, min(pattern.x2, loc)):
                ts = bars.index[index]
                if ts in window.index:
                    xs.append(int(window.index.get_loc(ts)))
                    ys.append(pattern.y1 if index == pattern.x1 else pattern.y2)
            if len(xs) == 2:
                ax.plot(xs, ys, color="#ffe14a", linewidth=1.5)
    mark = int(window.index.get_loc(setup.signal_time))
    price = float(window.iloc[mark]["high"] if setup.direction == "short" else window.iloc[mark]["low"])
    ax.scatter([mark], [price], s=46, facecolors="none", edgecolors="#ffd24a", linewidths=1.3, zorder=4)
    title = f"{setup.symbol} {note}  {KIND_NAME.get(setup.kind, setup.kind)}  {setup.direction} {_day(setup.signal_time).isoformat()}"
    ax.set_title(title, color="#f2f2f2", fontsize=10)
    ax.tick_params(colors="#cccccc")
    for spine in ax.spines.values():
        spine.set_color("#444444")
    step = max(1, len(window) // 8)
    xs = np.arange(len(window))
    ax.set_xticks(xs[::step])
    labels = []
    for ts in window.index[::step]:
        stamp = pd.Timestamp(ts)
        labels.append(stamp.strftime("%m-%d %H:%M") if stamp.hour or stamp.minute else stamp.strftime("%Y-%m-%d"))
    ax.set_xticklabels(labels, color="#cccccc")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    artifact = Path("/opt/cursor/artifacts/setups")
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / path.name).write_bytes(path.read_bytes())


def _prefer(setups, kind: str):
    rows = [setup for setup in setups if setup.kind == kind and _day(setup.fill_time) >= OOS_START]
    if not rows:
        rows = [setup for setup in setups if setup.kind == kind]
    if not rows:
        return None
    return max(rows, key=lambda setup: pd.Timestamp(setup.signal_time))


def save_examples(frames, setups, directory: Path, *, prefix: str, note: str) -> list[Path]:
    paths = []
    for kind in ("Dd", "Da", "Dr"):
        setup = _prefer(setups, kind)
        if setup is None or setup.symbol not in frames:
            continue
        path = directory / f"{prefix}_{kind}_{setup.symbol}_{_day(setup.signal_time).isoformat()}.png"
        _save_one(frames[setup.symbol], setup, path, note=note)
        paths.append(path)
        print(f"  chart {path.name}", flush=True)
    return paths


def _sensitivities(frames, setups) -> list[tuple[str, object]]:
    patches = {
        "stock": [
            ("risk 10%", {"risk_fraction": 0.10}),
            ("risk 25%", {"risk_fraction": 0.25}),
            ("target 1.5R", {"reward_r": 1.5}),
            ("no EMA trail", {"trail": "none"}),
            ("target 2R only", {"target_mode": "r"}),
            ("cash account, T+1", {"account": "cash_t1"}),
        ],
        "single": [
            ("30 DTE", {"dte": 30}),
            ("60 DTE", {"dte": 60}),
            ("delta 0.40", {"delta": 0.40}),
            ("delta 0.50", {"delta": 0.50}),
            ("IV 1.00x realized", {"iv_premium": 1.0}),
            ("IV 1.30x realized", {"iv_premium": 1.3}),
            ("doubled bid/ask", {"spread_multiplier": 2.0}),
            ("cash account, T+1", {"account": "cash_t1"}),
        ],
        "spread": [
            ("$2 wide", {"spread_width": 2.0}),
            ("$10 wide", {"spread_width": 10.0}),
            ("30 DTE", {"spread_dte": 30}),
            ("60 DTE", {"spread_dte": 60}),
            ("IV 1.00x realized", {"iv_premium": 1.0}),
            ("IV 1.30x realized", {"iv_premium": 1.3}),
            ("doubled bid/ask", {"spread_multiplier": 2.0}),
            ("cash account, T+1", {"account": "cash_t1"}),
        ],
    }
    rows = []
    for expression, items in patches.items():
        for label, patch in items:
            params = dict(BREAKOUT_DEFAULTS)
            params.update(patch)
            stats = daily_window(setups, frames, frames, params, expression, OOS_START, SAMPLE_END)
            rows.append((f"{expression}: {label}", stats))
    return rows


def _study_lines(study: dict, *, intraday: bool) -> list[str]:
    books = study["books"]
    kinds = ", ".join(f"{KIND_NAME.get(kind, kind)} {study['kinds'].get(kind, 0)}" for kind in ("Dd", "Da", "Dr"))
    if intraday:
        span = (
            f"{study['sessions']} sessions, {study['is'][0].isoformat()} through {study['oos'][1].isoformat()}. "
            f"In sample through {study['is'][1].isoformat()}. Out of sample {study['oos'][0].isoformat()} through {study['oos'][1].isoformat()}."
        )
    else:
        span = (
            f"In sample {SCORE_FROM.isoformat()} through {IS_END.isoformat()}. "
            f"Out of sample {OOS_START.isoformat()} through {SAMPLE_END.isoformat()}."
        )
    lines = [
        f"### {study['name']}",
        "",
        (
            f"{len(study['symbols'])} symbols, {study['signals']} signals "
            f"({study['longs']} long, {study['shorts']} short; {kinds}). {span}"
        ),
        "",
        "Flags, out of sample: "
        + ", ".join(f"{name} [{', '.join(study['flags'][name]) or 'none'}]" for name in ("stock", "single", "spread"))
        + f". In-sample stock grid fragile: {study['fragile']}.",
        "",
    ]
    rows = [
        ("Stock, full sample", books["full_stock"]),
        ("Stock, in sample", books["is_stock"]),
        ("Stock, out of sample", books["oos_stock"]),
        ("Stock, random entries, out of sample", books["oos_random_stock"]),
        ("30-60 DTE single, full sample", books["full_single"]),
        ("30-60 DTE single, in sample", books["is_single"]),
        ("30-60 DTE single, out of sample", books["oos_single"]),
        ("30-60 DTE single, random entries, out of sample", books["oos_random_single"]),
        ("Debit spread, full sample", books["full_spread"]),
        ("Debit spread, in sample", books["is_spread"]),
        ("Debit spread, out of sample", books["oos_spread"]),
        ("Debit spread, random entries, out of sample", books["oos_random_spread"]),
    ]
    if not intraday:
        rows.extend(
            [
                ("Stock, walk-forward", study["walks"]["stock"]),
                ("30-60 DTE single, walk-forward", study["walks"]["single"]),
                ("Debit spread, walk-forward", study["walks"]["spread"]),
            ]
        )
    lines.extend(_table(rows))
    lines.append("")
    if study["grid_rows"]:
        lines.append("Signal grid, in-sample fractional stock:")
        lines.append("")
        lines.extend(_table(study["grid_rows"]))
        lines.append("")
    return lines


def _verdict(dow: dict, named: dict) -> str:
    stock = dow["books"]["oos_stock"]
    single = dow["books"]["oos_single"]
    named_stock = named["books"]["oos_stock"]
    named_spread = named["books"]["oos_spread"]
    passed = bool(dow["selectable"]["stock"] and named["selectable"]["spread"])
    word = "PASSES" if passed else "DOES NOT PASS"
    return (
        f"{word}. Dow point-in-time stock, out of sample, ended at {_money(stock.metrics.get('ending_equity'))} "
        f"on {int(stock.metrics.get('trades') or 0)} trades "
        f"(profit factor {_pf(stock.metrics)}, Sharpe {float(stock.metrics.get('sharpe') or 0):.2f}). "
        f"The same signals as 45 DTE calls ended at {_money(single.metrics.get('ending_equity'))} "
        f"with {single.premium_skipped} skipped because the contract did not fit the risk cap. "
        f"The named large-cap list is a survivorship diagnostic: stock ended at "
        f"{_money(named_stock.metrics.get('ending_equity'))}, and SPY/QQQ debit spreads ended at "
        f"{_money(named_spread.metrics.get('ending_equity'))}. "
        "The 15-minute and 60-minute books are inside the free Yahoo intraday cap, so they are anecdotal. "
        "It is not optional and not the default book."
    )


def write_report(text_body: str, results_path: Path) -> None:
    start = "<!-- CHART_READS_D_START -->"
    end = "<!-- CHART_READS_D_END -->"
    block = f"{start}\n{text_body.rstrip()}\n{end}\n"
    text = results_path.read_text() if results_path.exists() else ""
    if start in text and end in text:
        text = text[: text.index(start)] + block + text[text.index(end) + len(end) :]
    else:
        marker = "<!-- CHART_READS_C_END -->"
        if marker not in text:
            raise SystemExit("setup C marker is missing. Not writing setup D over the earlier results.")
        at = text.index(marker) + len(marker)
        text = text[:at] + "\n\n" + block + text[at:]
    results_path.write_text(text if text.endswith("\n") else text + "\n")


def _pack(study: dict) -> dict:
    def one(stats):
        if isinstance(stats, dict) and "metrics" in stats:
            metrics = stats["metrics"]
            return {
                "metrics": {key: (None if isinstance(value, float) and not np.isfinite(value) else value) for key, value in metrics.items()},
                "pdt_blocked": stats.get("pdt_blocked", 0),
                "premium_skipped": stats.get("premium_skipped", 0),
                "bust": stats.get("bust", False),
            }
        metrics = {
            key: (None if isinstance(value, float) and not np.isfinite(value) else value)
            for key, value in stats.metrics.items()
        }
        return {
            "metrics": metrics,
            "pdt_blocked": stats.pdt_blocked,
            "premium_skipped": stats.premium_skipped,
            "bust": stats.bust,
            "ending_equity": stats.ending_equity,
        }

    return {
        "name": study["name"],
        "signals": study["signals"],
        "kinds": study["kinds"],
        "flags": study["flags"],
        "selectable": study["selectable"],
        "fragile": study["fragile"],
        "books": {key: one(value) for key, value in study["books"].items()},
        "walks": {key: one(value) for key, value in study["walks"].items()},
    }


def _load_intraday() -> tuple[dict, dict]:
    provider = YFinanceProvider("data/cache")
    end = pd.Timestamp(END)
    print("downloading 60m", flush=True)
    hourly = provider.history(SYMBOLS, (end - pd.Timedelta(days=720)).date().isoformat(), END, interval="60m")
    print("downloading 15m", flush=True)
    m15 = provider.history(SYMBOLS, (end - pd.Timedelta(days=55)).date().isoformat(), END, interval="15m")
    return (
        {symbol: rth(frame) for symbol, frame in hourly.items() if frame is not None and len(frame) > 80},
        {symbol: rth(frame) for symbol, frame in m15.items() if frame is not None and len(frame) > 80},
    )


def main() -> None:
    print("download daily", flush=True)
    frames, missing = load_daily()
    dow_symbols = [symbol for symbol in all_dow_tickers() if symbol in frames]
    dow = score_daily("Dow point-in-time, three breakout types", frames, dow_symbols, pit=True, survivorship=False)
    named = score_daily(
        "Named large caps plus SPY and QQQ, survivorship diagnostic",
        frames,
        NAMED,
        pit=False,
        survivorship=True,
    )
    print("charts", flush=True)
    charts = save_examples(frames, dow["setups"] + named["setups"], Path("reports/setups"), prefix="readD_1d", note="daily")
    print("sensitivities", flush=True)
    dow_sens = _sensitivities(frames, dow["setups"])
    named_sens = _sensitivities(frames, named["setups"])
    hourly, m15 = _load_intraday()
    intra60 = score_intraday("60-minute, anecdotal", hourly, frames, "60m")
    intra15 = score_intraday("15-minute, anecdotal", m15, frames, "15m")
    charts.extend(save_examples(hourly, intra60["setups"], Path("reports/setups"), prefix="readD_60m", note="60-minute"))
    charts.extend(save_examples(m15, intra15["setups"], Path("reports/setups"), prefix="readD_15m", note="15-minute"))
    hold = _hold(frames["SPY"]) if "SPY" in frames else {}
    verdict = _verdict(dow, named)
    lines = [
        "## Setup D: three breakout types",
        "",
        verdict,
        "",
        (
            "Rules, frozen before this score. A descending triangle is a flat support with at least two "
            "confirmed pivot lows and at least two lower highs. It is a short only, through the support. "
            "An ascending triangle is a flat resistance and higher lows. It is a long only, through the "
            "resistance. A range has both sides flat, at least two touches each, and may break either way. "
            "Pivots are 4 bars on each side. The pattern is 15 to 80 bars long and must still be open "
            "(the sloped side has not crossed the flat side). The flat side's prices sit within 0.50 ATR. "
            "The sloped side rises or falls at least 0.75 ATR, which is what separates it from a second "
            "flat side. Three touches on the flat side is a grid cell. The trigger is a close at least "
            "0.25 ATR beyond the level on a confirming candle (body at least half the range, close in the "
            "outer third), or that same candle within the next 3 bars if the first close through is not "
            "itself confirming. A retest that holds is the other grid cell, not the default. The fill is "
            "the next open. The stop is the signal bar's high on a short and its low on a long. The "
            "retest variant uses the retest extreme instead. The target is the pattern height measured "
            "from the broken level when that distance is at least 0.5R, otherwise 2R. Daily holds trail "
            "the 20 EMA for up to 30 sessions and do not flatten at the close. A close the other way "
            "through the sloped side cancels the triangle. Nothing was sent to a broker."
        ),
        "",
        (
            "Dow membership follows the point-in-time list. Yahoo returned no usable daily history for: "
            + (", ".join(missing) if missing else "none")
            + ". The named book (SPY, QQQ, IWM, UNH, AAPL, AMD, NVDA, TSLA, MSFT, META) is a survivorship "
            "diagnostic. SPY and QQQ debit spreads are the options expression that can fit a $1,000 account. "
            "Singles are 45 DTE, delta 0.45, whole contracts, skipped when the debit is above 20% of equity. "
            "Prices are Black-Scholes on trailing realized volatility times 1.15. They are not quotes. "
            "The 15-minute and 60-minute runs use the same pivot rules on the named list. Fifteen-minute "
            "trades flatten the same session. Sixty-minute trades can be held for 5 sessions. Both clocks "
            "are short samples."
        ),
        "",
    ]
    lines.extend(_study_lines(dow, intraday=False))
    lines.extend(_study_lines(named, intraday=False))
    lines.append("Sensitivities on the Dow out-of-sample window. These were not used to pick the default.")
    lines.append("")
    lines.extend(_table(dow_sens))
    lines.append("")
    lines.append("Sensitivities on the named-list out-of-sample window, same rule.")
    lines.append("")
    lines.extend(_table(named_sens))
    lines.append("")
    lines.extend(_study_lines(intra60, intraday=True))
    lines.extend(_study_lines(intra15, intraday=True))
    lines.append(
        "Charts: "
        + ", ".join(f"`reports/setups/{path.name}`" for path in charts)
        + "."
    )
    lines.append("")
    if hold:
        lines.append(
            f"SPY buy and hold, whole shares that fit in $1,000, {OOS_START.isoformat()} through {SAMPLE_END.isoformat()}: "
            f"{int(hold.get('shares') or 0)} shares, ending {_money(hold.get('ending_equity'))}, "
            f"Sharpe {float(hold.get('sharpe') or 0):.2f}, max drawdown {float(hold.get('max_drawdown') or 0):.1%}."
        )
        lines.append("")
    lines.append(
        "Profit factor gate 1.10, Sharpe gate 0.40, drawdown no worse than -30%, and at least 300 trades. "
        "The named list carries survivorship_bias, which blocks it. The Dow stock book and the named-list "
        "spread book would both have to clear the gates. The intraday clocks carry short_sample. "
        "Under 300 trades the sample is anecdotal. This does not join the optional list or the registry."
    )
    body = "\n".join(lines)
    write_report(body, Path("RESULTS.md"))
    summary = {
        "verdict": verdict,
        "missing": missing,
        "charts": [path.name for path in charts],
        "dow": _pack(dow),
        "named": _pack(named),
        "m60": _pack(intra60),
        "m15": _pack(intra15),
        "hold": {key: (None if isinstance(value, float) and not np.isfinite(value) else value) for key, value in hold.items()},
    }
    Path("/tmp/chart_reads_d_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(verdict, flush=True)
    print("charts", ", ".join(path.name for path in charts), flush=True)


if __name__ == "__main__":
    main()
