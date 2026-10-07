"""Score daily setup C. Backtests only. Does not rewrite the A/B results.

The UNH line is checked before any P&L is written. If that check misses the
July 29 and September 9 anchors, scoring stops.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from webull_bot.backtest.assessment import fragile_grid, is_selectable, overfit_flags, pick_params
from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.params import DAILY_DEFAULTS, daily_grid
from webull_bot.chart_reads.research import _for_expression, _stitch, random_setups
from webull_bot.chart_reads.simulate import simulate
from webull_bot.chart_reads.trendline import describe_line, find_trend_setups
from webull_bot.costs import CostModel
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.indicators import ema
from webull_bot.universe_dow import all_dow_tickers, is_member

STARTING = 1_000.0
COSTS = CostModel()
MIN_CONCLUSION = 300
HISTORY_START = "2009-01-01"
SCORE_FROM = date(2010, 1, 1)
IS_END = date(2018, 12, 31)
OOS_START = date(2019, 1, 1)
SAMPLE_END = date(2026, 10, 6)
DOWNLOAD_END = "2026-10-07"
NAMED = ["SPY", "QQQ", "IWM", "UNH", "AAPL", "AMD", "NVDA", "TSLA", "MSFT", "META"]
# The drawing's anchors on Yahoo daily bars. The chart label Hi 461.62 is the
# July 16 wick; Yahoo prints that high at 458.79, and the line runs under it.
UNH_ANCHORS = (date(2026, 7, 29), date(2026, 9, 9))
FOLDS = (
    (date(2019, 1, 1), date(2020, 12, 31)),
    (date(2021, 1, 1), date(2022, 12, 31)),
    (date(2023, 1, 1), date(2024, 12, 31)),
    (date(2025, 1, 1), date(2026, 10, 6)),
)


def _naive(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    index = pd.DatetimeIndex(out.index)
    if index.tz is not None:
        index = index.tz_convert("America/New_York").tz_localize(None)
    out.index = index.normalize()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def _day(ts) -> date:
    return pd.Timestamp(ts).date()


def load_daily() -> tuple[dict[str, pd.DataFrame], list[str]]:
    symbols = sorted(set(all_dow_tickers()) | set(NAMED))
    provider = YFinanceProvider("data/cache/daily_long")
    raw = provider.history(symbols, HISTORY_START, DOWNLOAD_END, interval="1d")
    frames = {}
    missing = []
    for symbol in symbols:
        frame = raw.get(symbol)
        if frame is None or frame.empty:
            missing.append(symbol)
            continue
        normal = _naive(frame)
        if len(normal) < 60:
            missing.append(symbol)
            continue
        frames[symbol] = normal
    return frames, missing


def verify_unh(frame: pd.DataFrame) -> dict:
    info = describe_line(frame, as_of="2026-10-06")
    pair = info["pair"]
    if pair is None:
        raise SystemExit("UNH has no descending line on 2026-10-06. Not scoring.")
    got = (_day(pair["date1"]), _day(pair["date2"]))
    if got != UNH_ANCHORS:
        raise SystemExit(f"UNH anchors {got} are not {UNH_ANCHORS}. Not scoring.")
    july = [
        row
        for row in info["touches"]
        if date(2026, 7, 20) <= _day(row["date"]) <= date(2026, 7, 31)
    ]
    september = [
        row
        for row in info["touches"]
        if date(2026, 9, 1) <= _day(row["date"]) <= date(2026, 9, 10)
    ]
    if not july or not september:
        raise SystemExit("UNH line does not tag both the late-July and early-September tests. Not scoring.")
    info["july"] = july
    info["september"] = september
    return info


def save_unh_chart(frame: pd.DataFrame, info: dict, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    window = frame.loc["2026-06-01":"2026-10-06"]
    line = info["line"].reindex(window.index)
    fast = ema(frame["close"].astype(float), 9).reindex(window.index)
    slow = ema(frame["close"].astype(float), 20).reindex(window.index)
    fig, ax = plt.subplots(figsize=(12.5, 6.2))
    ax.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    xs = np.arange(len(window))
    for i, (_ts, row) in enumerate(window.iterrows()):
        color = "#3dcc6d" if row["close"] >= row["open"] else "#e24b4b"
        ax.plot([i, i], [row["low"], row["high"]], color=color, linewidth=0.8)
        body_low = min(row["open"], row["close"])
        body_high = max(row["open"], row["close"])
        ax.plot([i, i], [body_low, body_high], color=color, linewidth=3.2, solid_capstyle="butt")
    ax.plot(xs, fast.to_numpy(), color="#f0d060", linewidth=1.0, label="EMA 9")
    ax.plot(xs, slow.to_numpy(), color="#e09040", linewidth=1.0, label="EMA 20")
    ax.plot(xs, line.to_numpy(), color="#ffe14a", linewidth=1.6, label="descending pivots")
    touch_dates = { _day(row["date"]) for row in info["july"] + info["september"] }
    for i, ts in enumerate(window.index):
        if _day(ts) in touch_dates:
            ax.scatter([i], [window["high"].iloc[i]], s=36, facecolors="none", edgecolors="#ffd24a", linewidths=1.2, zorder=4)
    pair = info["pair"]
    ax.set_title(
        f"UNH daily  line { _day(pair['date1']).isoformat() } {pair['y1']:.2f}"
        f" to { _day(pair['date2']).isoformat() } {pair['y2']:.2f}"
        "   yellow rings: late-July and early-September tests",
        color="#f2f2f2",
        fontsize=10,
    )
    ax.tick_params(colors="#cccccc")
    for spine in ax.spines.values():
        spine.set_color("#444444")
    ax.legend(facecolor="#222222", edgecolor="#444444", labelcolor="#f2f2f2", fontsize=8)
    step = max(1, len(window) // 8)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels([_day(ts).isoformat()[5:] for ts in window.index[::step]], rotation=0, color="#cccccc")
    path = report_dir / "read1d_UNH_2026.png"
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    artifact = Path("/opt/cursor/artifacts/setups")
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / path.name).write_bytes(path.read_bytes())
    return path


def _collect(frames: dict[str, pd.DataFrame], symbols: list[str], params: dict, *, pit: bool) -> list[Setup]:
    found: list[Setup] = []
    for symbol in symbols:
        frame = frames.get(symbol)
        if frame is None or len(frame) < 60:
            continue
        setups = find_trend_setups(frame, params, symbol=symbol)
        if pit:
            setups = [setup for setup in setups if is_member(symbol, _day(setup.signal_time))]
        setups = [setup for setup in setups if _day(setup.fill_time) >= SCORE_FROM]
        found.extend(setups)
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.kind))
    return found


def _slice(frames: dict[str, pd.DataFrame], start: date, end: date) -> dict[str, pd.DataFrame]:
    out = {}
    for symbol, frame in frames.items():
        if frame is None or frame.empty:
            continue
        kept = frame.loc[(frame.index.date >= start) & (frame.index.date <= end)]
        if len(kept):
            out[symbol] = kept
    return out


def _in_window(setups: list[Setup], start: date, end: date) -> list[Setup]:
    return [setup for setup in setups if start <= _day(setup.fill_time) <= end]


def _book(setups, frames, daily, params, expression: str) -> object:
    chosen = dict(params)
    chosen["expression"] = expression
    return simulate(
        _for_expression(setups, expression),
        frames,
        daily,
        chosen,
        starting_equity=STARTING,
        costs=COSTS,
        session_filter=False,
    )


def _window_book(setups, frames, daily, params, expression, start: date, end: date):
    return _book(_in_window(setups, start, end), _slice(frames, start, end), daily, params, expression)


def _walk(frames, daily, found: list[tuple[dict, list[Setup]]], expression: str) -> dict:
    folds = []
    pdt = 0
    skipped = 0
    for start, end in FOLDS:
        train_end = (pd.Timestamp(start) - pd.Timedelta(days=1)).date()
        rows = []
        chosen_setups = found[0][1]
        chosen = found[0][0]
        for cell, setups in found:
            stats = _window_book(setups, frames, daily, cell, expression, SCORE_FROM, train_end)
            rows.append({"params": cell, **stats.metrics})
        picked = pick_params(rows, found[0][0], min_trades=15)
        for cell, setups in found:
            if cell == picked:
                chosen = cell
                chosen_setups = setups
                break
        stats = _window_book(chosen_setups, frames, daily, chosen, expression, start, end)
        folds.append(stats)
        pdt += stats.pdt_blocked
        skipped += stats.premium_skipped
        print(
            f"    walk {expression} {start}..{end} trades {stats.metrics.get('trades')}",
            flush=True,
        )
    metrics = _stitch(folds) if folds else compute_metrics(
        BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
        STARTING,
    )
    return {
        "metrics": metrics,
        "pdt_blocked": pdt,
        "premium_skipped": skipped,
        "bust": any(getattr(stats, "bust", False) for stats in folds),
        "folds": len(folds),
    }


def _score(oos: dict, walk: dict, train_sharpes: list[float], *, survivorship: bool) -> tuple[list[str], bool]:
    trades = int(oos.get("trades") or 0)
    flags = overfit_flags(
        default_oos=oos,
        walk_forward=walk,
        train_sharpes=train_sharpes,
        survivorship_sensitive=survivorship,
        short_sample=False,
        min_trades=20,
    )
    if trades < MIN_CONCLUSION:
        flags.append("anecdotal_sample")
    selectable = is_selectable(flags, oos, min_trades=MIN_CONCLUSION) and trades >= MIN_CONCLUSION
    return flags, selectable


def _hold(frame: pd.DataFrame) -> dict:
    window = frame.loc[(frame.index.date >= OOS_START) & (frame.index.date <= SAMPLE_END)]
    empty = compute_metrics(BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()), STARTING)
    if window.empty:
        return empty
    entry = float(window.iloc[0]["open"]) * (1.0 + 6.0 / 10_000.0)
    exit_ = float(window.iloc[-1]["close"]) * (1.0 - 6.0 / 10_000.0)
    shares = int(np.floor(STARTING / entry)) if entry > 0 else 0
    if shares < 1:
        empty["note"] = "one share cost more than $1,000"
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
    result = BacktestResult(equity=equity, exposure=pd.Series(0.0, index=equity.index), trades=trades, ending_equity=float(equity.iloc[-1]))
    metrics = compute_metrics(result, STARTING)
    metrics["shares"] = shares
    return metrics


def _cell_label(cell: dict) -> str:
    changes = []
    if cell.get("pivot_left") != DAILY_DEFAULTS["pivot_left"]:
        changes.append(f"pivot {cell['pivot_left']}/{cell['pivot_right']}")
    if cell.get("touch_atr") != DAILY_DEFAULTS["touch_atr"]:
        changes.append(f"touch {cell['touch_atr']}")
    if cell.get("break_buffer_atr") != DAILY_DEFAULTS["break_buffer_atr"]:
        changes.append(f"buffer {cell['break_buffer_atr']}")
    if cell.get("retest_days") != DAILY_DEFAULTS["retest_days"]:
        changes.append(f"retest {cell['retest_days']}d")
    if cell.get("require_three_touches"):
        changes.append("3 touches")
    return "default" if not changes else ", ".join(changes)


def score_universe(
    name: str,
    frames: dict[str, pd.DataFrame],
    symbols: list[str],
    *,
    pit: bool,
    survivorship: bool,
    params_list: list[dict] | None = None,
    walk: bool = True,
) -> dict:
    cells = params_list or daily_grid()
    print(f"detect {name}", flush=True)
    by_cell = []
    for cell in cells:
        found = _collect(frames, symbols, cell, pit=pit)
        by_cell.append((cell, found))
        print(f"  {_cell_label(cell)} signals {len(found)}", flush=True)
    setups = by_cell[0][1]
    present = [symbol for symbol in symbols if symbol in frames]
    print(f"  scoring {name} on {len(present)} symbols, {len(setups)} default signals", flush=True)
    books = {}
    oos_frames = _slice(frames, OOS_START, SAMPLE_END)
    shuffled = random_setups(_in_window(setups, OOS_START, SAMPLE_END), oos_frames, seed=17)
    for expression in ("stock", "single", "spread"):
        print(f"  book {expression}", flush=True)
        books[f"full_{expression}"] = _window_book(setups, frames, frames, cells[0], expression, SCORE_FROM, SAMPLE_END)
        books[f"is_{expression}"] = _window_book(setups, frames, frames, cells[0], expression, SCORE_FROM, IS_END)
        books[f"oos_{expression}"] = _window_book(setups, frames, frames, cells[0], expression, OOS_START, SAMPLE_END)
        books[f"oos_random_{expression}"] = _book(shuffled, oos_frames, frames, cells[0], expression)
    walks = {}
    if walk:
        for expression in ("stock", "single", "spread"):
            walks[expression] = _walk(frames, frames, by_cell, expression)
    else:
        empty = compute_metrics(BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()), STARTING)
        for expression in ("stock", "single", "spread"):
            walks[expression] = {"metrics": empty, "pdt_blocked": 0, "premium_skipped": 0, "bust": False, "folds": 0}
    grid_rows = []
    is_sharpes = []
    for cell, found in by_cell:
        stats = _window_book(found, frames, frames, cell, "stock", SCORE_FROM, IS_END)
        is_sharpes.append(float(stats.metrics.get("sharpe") or 0.0))
        grid_rows.append((_cell_label(cell), stats))
    flags = {}
    selectable = {}
    for expression in ("stock", "single", "spread"):
        # Debit spreads are SPY and QQQ only, so that book is not the survivor list.
        flags[expression], selectable[expression] = _score(
            books[f"oos_{expression}"].metrics,
            walks[expression]["metrics"],
            is_sharpes,
            survivorship=survivorship and expression != "spread",
        )
    return {
        "name": name,
        "symbols": present,
        "signals": len(setups),
        "longs": sum(1 for setup in setups if setup.direction == "long"),
        "shorts": sum(1 for setup in setups if setup.direction == "short"),
        "books": books,
        "walks": walks,
        "flags": flags,
        "selectable": selectable,
        "fragile": fragile_grid(is_sharpes),
        "grid_rows": grid_rows,
        "survivorship": survivorship,
    }


def _sensitivities(frames, symbols, setups, *, pit: bool) -> list[tuple[str, object]]:
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
            params = dict(DAILY_DEFAULTS)
            params.update(patch)
            stats = _window_book(setups, frames, frames, params, expression, OOS_START, SAMPLE_END)
            rows.append((f"{expression}: {label}", stats))
    return rows


def _money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"${float(value):,.2f}"


def _pf(metrics: dict) -> str:
    value = metrics.get("profit_factor")
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _row(label: str, stats=None, metrics: dict | None = None) -> str:
    if isinstance(stats, dict) and "metrics" in stats:
        pdt = stats.get("pdt_blocked", 0)
        skipped = stats.get("premium_skipped", 0)
        bust = "yes" if stats.get("bust") else "no"
        ruin = "n/a"
        metrics = stats["metrics"]
    elif metrics is None and stats is not None and hasattr(stats, "metrics"):
        metrics = stats.metrics
        pdt = stats.pdt_blocked
        skipped = stats.premium_skipped
        bust = "yes" if stats.bust else "no"
        ruin = "n/a" if stats.ruin_estimate is None else f"{stats.ruin_estimate:.2f}"
    else:
        metrics = metrics or {}
        pdt = skipped = 0
        bust = "no"
        ruin = "n/a"
    return (
        f"| {label} | {int(metrics.get('trades') or 0)} | {float(metrics.get('win_rate') or 0):.1%} | "
        f"{_money(metrics.get('avg_win'))} | {_money(metrics.get('avg_loss'))} | "
        f"{_money(metrics.get('expectancy'))} | {_pf(metrics)} | {float(metrics.get('max_drawdown') or 0):.1%} | "
        f"{float(metrics.get('sharpe') or 0):.2f} | {_money(metrics.get('ending_equity'))} | "
        f"{bust} | {ruin} | {pdt} | {skipped} |"
    )


def _table(rows: list[tuple[str, object]]) -> list[str]:
    header = (
        "| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|",
    )
    return [*header, *(_row(label, stats) for label, stats in rows)]


def _study_lines(study: dict) -> list[str]:
    books = study["books"]
    lines = [
        f"### {study['name']}",
        "",
        (
            f"{len(study['symbols'])} symbols, {study['signals']} signals "
            f"({study['longs']} long, {study['shorts']} short). "
            f"In sample {SCORE_FROM.isoformat()} through {IS_END.isoformat()}. "
            f"Out of sample {OOS_START.isoformat()} through {SAMPLE_END.isoformat()}."
        ),
        "",
        "Flags, out of sample: "
        + ", ".join(
            f"{name} [{', '.join(study['flags'][name]) or 'none'}]"
            for name in ("stock", "single", "spread")
        )
        + f". In-sample stock grid fragile: {study['fragile']}.",
        "",
    ]
    lines.extend(
        _table(
            [
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
                ("Stock, walk-forward", study["walks"]["stock"]),
                ("30-60 DTE single, walk-forward", study["walks"]["single"]),
                ("Debit spread, walk-forward", study["walks"]["spread"]),
            ]
        )
    )
    lines.append("")
    lines.append("Signal grid, in-sample fractional stock:")
    lines.append("")
    lines.extend(_table(study["grid_rows"]))
    lines.append("")
    return lines


def _verdict(info: dict, dow: dict, named: dict, shorts: dict) -> str:
    pair = info["pair"]
    stock = dow["books"]["oos_stock"]
    single = dow["books"]["oos_single"]
    named_stock = named["books"]["oos_stock"]
    named_spread = named["books"]["oos_spread"]
    passed = bool(dow["selectable"]["stock"] and named["selectable"]["spread"])
    word = "PASSES" if passed else "DOES NOT PASS"
    return (
        f"{word}. The UNH line selected on 2026-10-06 runs from "
        f"{_day(pair['date1']).isoformat()} at {pair['y1']:.2f} through "
        f"{_day(pair['date2']).isoformat()} at {pair['y2']:.2f}. "
        f"Late July and early September tag that line. "
        f"Dow point-in-time stock, out of sample, ended at {_money(stock.metrics.get('ending_equity'))} "
        f"on {int(stock.metrics.get('trades') or 0)} trades "
        f"(profit factor {_pf(stock.metrics)}, Sharpe {float(stock.metrics.get('sharpe') or 0):.2f}). "
        f"The same signals as 45 DTE calls ended at {_money(single.metrics.get('ending_equity'))} "
        f"with {single.premium_skipped} skipped because the contract did not fit the risk cap. "
        f"The named large-cap list is a survivorship diagnostic: stock ended at "
        f"{_money(named_stock.metrics.get('ending_equity'))}, and SPY/QQQ debit spreads ended at "
        f"{_money(named_spread.metrics.get('ending_equity'))}. "
        f"The rejection-short variant on the Dow ended at "
        f"{_money(shorts['books']['oos_stock'].metrics.get('ending_equity'))}. "
        "It is not optional and not the default book."
    )


def write_report(text_body: str, results_path: Path) -> None:
    start = "<!-- CHART_READS_C_START -->"
    end = "<!-- CHART_READS_C_END -->"
    block = f"{start}\n{text_body.rstrip()}\n{end}\n"
    text = results_path.read_text() if results_path.exists() else ""
    if start in text and end in text:
        text = text[: text.index(start)] + block + text[text.index(end) + len(end) :]
        if not text[text.index(end) + len(end) :].startswith("\n"):
            pass
    else:
        marker = "<!-- CHART_READS_END -->"
        if marker in text:
            at = text.index(marker) + len(marker)
            text = text[:at] + "\n\n" + block + text[at:]
        else:
            if text and not text.endswith("\n"):
                text += "\n"
            text += "\n" + block
    results_path.write_text(text if text.endswith("\n") else text + "\n")


def _jsonable(study: dict) -> dict:
    def pack(stats):
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
        "flags": study["flags"],
        "selectable": study["selectable"],
        "fragile": study["fragile"],
        "books": {key: pack(value) for key, value in study["books"].items()},
        "walks": study["walks"],
    }


def main() -> None:
    print("download daily", flush=True)
    frames, missing = load_daily()
    if "UNH" not in frames:
        raise SystemExit("UNH daily history is missing. Not scoring.")
    info = verify_unh(frames["UNH"])
    chart = save_unh_chart(frames["UNH"], info, Path("reports/setups"))
    print(
        f"UNH line { _day(info['pair']['date1']) } -> { _day(info['pair']['date2']) } chart {chart}",
        flush=True,
    )
    dow_symbols = [symbol for symbol in all_dow_tickers() if symbol in frames]
    dow = score_universe("Dow point-in-time, long breakout-retest", frames, dow_symbols, pit=True, survivorship=False)
    named = score_universe(
        "Named large caps plus SPY and QQQ, survivorship diagnostic",
        frames,
        NAMED,
        pit=False,
        survivorship=True,
    )
    short_params = [dict(DAILY_DEFAULTS, include_long=False, include_short=True)]
    shorts = score_universe(
        "Dow point-in-time, rejection shorts (variant)",
        frames,
        dow_symbols,
        pit=True,
        survivorship=False,
        params_list=short_params,
        walk=False,
    )
    print("sensitivities", flush=True)
    dow_setups = _collect(frames, dow_symbols, DAILY_DEFAULTS, pit=True)
    named_setups = _collect(frames, NAMED, DAILY_DEFAULTS, pit=False)
    dow_sens = _sensitivities(frames, dow_symbols, dow_setups, pit=True)
    named_sens = _sensitivities(frames, NAMED, named_setups, pit=False)
    hold = _hold(frames["SPY"]) if "SPY" in frames else {}
    verdict = _verdict(info, dow, named, shorts)
    july = ", ".join(_day(row["date"]).isoformat() for row in info["july"])
    september = ", ".join(_day(row["date"]).isoformat() for row in info["september"])
    lines = [
        "## Daily setup C: descending-trendline breakout",
        "",
        verdict,
        "",
        (
            "Rules, frozen before this score. The line at each close is two confirmed pivot highs "
            "(4 bars each side, 10 to 126 sessions apart). An intervening pivot that trades through "
            "the segment knocks that pair out. The pair with the most touches wins; a line already "
            "under the high loses to one still overhead. A pair older than 80 sessions stays eligible "
            "only when price is still within 3 ATR of it. Three touches is a grid cell, not the default. "
            "The long is a close at least 0.25 ATR through the line, then within 10 sessions a tag of "
            "the line or the breakout close that does not close back under the line, plus a bullish "
            "candle (body at least half the range, close in the top third). The fill is the next open. "
            "The stop is the retest low. The target is the next confirmed pivot high when that level "
            "is at least 0.5R away, otherwise 2R. The 20 EMA trail and a 30-session time stop also exit. "
            "No end-of-day flatten. Rejection shorts are the variant: a bearish tag of a line that is "
            "already known, and the confirmation bar of a new pivot pair, only while the 9 EMA is under "
            "the 20. Stop above that high."
        ),
        "",
        (
            f"UNH on 2026-10-06. Yahoo's July 16 high is 458.79. The chart label Hi 461.62 is that wick, "
            f"and it sits about 22 points above this line, so the line is not drawn through the wick tip. "
            f"The selected anchors are {_day(info['pair']['date1']).isoformat()} at {info['pair']['y1']:.2f} "
            f"and {_day(info['pair']['date2']).isoformat()} at {info['pair']['y2']:.2f} "
            f"({info['pair']['touches']} touches on the segment, confirmed {_day(info['pair']['confirm']).isoformat()}). "
            f"The line is {float(info['line'].loc['2026-10-06']):.2f} on the last bar. "
            f"Late-July tags: {july}. Early-September tags: {september}. "
            "September 7 2026 was Labor Day, so the session cluster is September 3 and September 8-9. "
            "The September short, in the variant, is entered the session after that pivot confirms, "
            "not on the touch itself. The green boxes on the user's chart are a later hypothetical; "
            "they are not a signal this file is required to find."
        ),
        "",
        f"Chart: `reports/setups/{chart.name}`.",
        "",
        (
            "Dow membership follows the point-in-time list. A name is traded only while it is in the index. "
            f"Yahoo returned no usable daily history for: {', '.join(missing) if missing else 'none'}. "
            "Those gaps are the known delisted or renamed names, not a 2026 survivor list. "
            "The named book (SPY, QQQ, IWM, UNH, AAPL, AMD, NVDA, TSLA, MSFT, META) is labeled a survivorship diagnostic. "
            "SPY and QQQ debit spreads inside that book are the $1,000 options expression that can actually fit. "
            "Singles are 45 DTE, delta 0.45, whole contracts, skipped when the debit is above 20% of equity. "
            "A same-day stop counts as a day trade. A swing entry is not blocked just because the stop might hit today; "
            "a fourth entry is blocked once three same-day round trips are already on the books. "
            "Prices are Black-Scholes on trailing realized volatility times 1.15, with the same haircut as the intraday study. "
            "They are not quotes. Nothing was sent to a broker."
        ),
        "",
    ]
    lines.extend(_study_lines(dow))
    lines.extend(_study_lines(named))
    lines.extend(_study_lines(shorts))
    lines.append("Sensitivities on the Dow out-of-sample window. These were not used to pick the default.")
    lines.append("")
    lines.extend(_table(dow_sens))
    lines.append("")
    lines.append("Sensitivities on the named-list out-of-sample window, same rule.")
    lines.append("")
    lines.extend(_table(named_sens))
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
        "The named list carries survivorship_bias, which blocks it. "
        "The Dow stock book and the named-list spread book would both have to clear the gates. "
        "Under 300 trades the sample is anecdotal. This does not join the optional list or the registry."
    )
    lines.append("")
    body = "\n".join(lines)
    write_report(body, Path("RESULTS.md"))
    summary = {
        "verdict": verdict,
        "missing": missing,
        "anchors": {
            "date1": _day(info["pair"]["date1"]).isoformat(),
            "y1": info["pair"]["y1"],
            "date2": _day(info["pair"]["date2"]).isoformat(),
            "y2": info["pair"]["y2"],
        },
        "july": july,
        "september": september,
        "dow": _jsonable(dow),
        "named": _jsonable(named),
        "shorts": _jsonable(shorts),
        "hold": {key: (None if isinstance(value, float) and not np.isfinite(value) else value) for key, value in hold.items()},
    }
    Path("/tmp/chart_reads_c_summary.json").write_text(json.dumps(summary, default=str, indent=2))
    print(verdict, flush=True)


if __name__ == "__main__":
    main()
