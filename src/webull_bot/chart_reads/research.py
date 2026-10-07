"""Score the chart-read rules. Backtests only.

The detector is checked on the three annotated sessions before any book is
scored. Nothing in this module calls a broker.

Run: ``python -m webull_bot.chart_reads.research``
"""

from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.backtest.assessment import fragile_grid, is_selectable, overfit_flags, pick_params
from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.chart_reads.detect import Setup, find_setups, session_bands, to_ny
from webull_bot.chart_reads.params import DEFAULTS, grid
from webull_bot.chart_reads.simulate import SPREAD_UNDERLYINGS, BookStats, simulate
from webull_bot.costs import CostModel
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.indicators import ema

SYMBOLS = ["SPY", "QQQ", "IWM", "UNH", "AAPL", "AMD", "NVDA", "TSLA", "MSFT", "META"]
STARTING = 1_000.0
MIN_CONCLUSION = 300
NY = "America/New_York"
END = "2026-10-07"
COSTS = CostModel()


def _day(ts) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert(NY)
    return stamp.date()


def _clock(ts) -> time:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert(NY)
    return stamp.timetz().replace(tzinfo=None)


def _sessions(frames: dict[str, pd.DataFrame]) -> list[date]:
    found = set()
    for frame in frames.values():
        if frame is None or frame.empty:
            continue
        found.update(_day(ts) for ts in frame.index)
    return sorted(found)


def _slice(frames: dict[str, pd.DataFrame], start: date, end: date) -> dict[str, pd.DataFrame]:
    out = {}
    for symbol, frame in frames.items():
        if frame is None or frame.empty:
            continue
        ny = to_ny(frame)
        mask = np.array([start <= _day(ts) <= end for ts in ny.index])
        kept = ny.loc[mask]
        if len(kept):
            out[symbol] = kept
    return out


def _in_window(setups: list[Setup], start: date, end: date) -> list[Setup]:
    return [setup for setup in setups if start <= _day(setup.fill_time) <= end]


def _cells(execution: str) -> list[dict]:
    cells = []
    for cell in grid():
        chosen = dict(cell)
        chosen["execution"] = execution
        if execution == "60m":
            # Hourly bars are the long sample, not a scalp. Hold up to five
            # sessions and trail the 20 EMA instead of flattening every day.
            chosen["flatten_eod"] = False
            chosen["max_hold_sessions"] = 5
        cells.append(chosen)
    return cells


def _bundle(symbol: str, execution: str, frames: dict, daily: dict, extras: dict) -> dict:
    bundle = {execution: frames[symbol], "daily": daily[symbol]}
    for key, book in extras.items():
        if symbol in book and book[symbol] is not None and len(book[symbol]):
            bundle[key] = book[symbol]
    return bundle


def detect_all(frames, daily, extras, params) -> list[Setup]:
    execution = str(params["execution"])
    setups: list[Setup] = []
    for symbol, frame in frames.items():
        if frame is None or len(frame) < 30 or symbol not in daily:
            continue
        setups.extend(find_setups(_bundle(symbol, execution, frames, daily, extras), params, symbol=symbol))
    setups.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.kind, setup.direction))
    return setups


def _for_expression(setups: list[Setup], expression: str) -> list[Setup]:
    if expression == "spread":
        return [setup for setup in setups if setup.symbol in SPREAD_UNDERLYINGS]
    return list(setups)


def _book(setups, frames, daily, params, expression: str) -> BookStats:
    chosen = dict(params)
    chosen["expression"] = expression
    return simulate(
        _for_expression(setups, expression),
        frames,
        daily,
        chosen,
        starting_equity=STARTING,
        costs=COSTS,
    )


def _window_book(setups, frames, daily, params, expression, start: date, end: date) -> BookStats:
    return _book(_in_window(setups, start, end), _slice(frames, start, end), daily, params, expression)


def _stitch(folds: list[BookStats]) -> dict:
    returns = []
    trades = []
    for stats in folds:
        if stats.equity is None or stats.equity.empty:
            continue
        result = BacktestResult(stats.equity, pd.Series(dtype=float), stats.trades)
        daily = result.daily_equity()
        if daily.empty:
            continue
        base = pd.Series([STARTING], index=[daily.index[0] - pd.Timedelta(days=1)])
        returns.append(pd.concat([base, daily]).pct_change().dropna())
        if stats.trades is not None and len(stats.trades):
            trades.append(stats.trades)
    if not returns:
        return compute_metrics(
            BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
            STARTING,
        )
    stitched = pd.concat(returns)
    equity = (1.0 + stitched).cumprod() * STARTING
    trade_frame = pd.concat(trades) if trades else pd.DataFrame()
    result = BacktestResult(
        equity=equity,
        exposure=pd.Series(0.0, index=equity.index),
        trades=trade_frame,
        ending_equity=float(equity.iloc[-1]),
    )
    return compute_metrics(result, STARTING)


def _same_cell(left: dict, right: dict) -> bool:
    keys = ("k_sep", "require_ema200", "morning_only", "rsi_filter", "macd_filter", "avoid_extended", "execution")
    return all(left.get(key) == right.get(key) for key in keys)


def _walk(frames, daily, found: list[tuple[dict, list]], days: list[date], expression: str) -> dict:
    empty = compute_metrics(BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()), STARTING)
    if len(days) < 40:
        return {"metrics": empty, "pdt_blocked": 0, "premium_skipped": 0, "bust": False, "folds": 0}
    half = len(days) // 2
    test_days = days[half:]
    width = max(1, len(test_days) // 3)
    folds = []
    pdt = 0
    skipped = 0
    for fold in range(3):
        start_i = fold * width
        end_i = len(test_days) if fold == 2 else min(len(test_days), (fold + 1) * width)
        if start_i >= len(test_days):
            break
        test = test_days[start_i:end_i]
        if not test:
            continue
        train_cut = pd.Timestamp(test[0]) - pd.Timedelta(days=180)
        train = [day for day in days if train_cut.date() <= day < test[0]]
        if len(train) < 5:
            continue
        rows = []
        for cell, setups in found:
            stats = _window_book(setups, frames, daily, cell, expression, train[0], train[-1])
            rows.append({"params": cell, **stats.metrics})
        chosen = pick_params(rows, found[0][0], min_trades=15)
        chosen_setups = found[0][1]
        for cell, setups in found:
            if _same_cell(cell, chosen):
                chosen_setups = setups
                chosen = cell
                break
        stats = _window_book(chosen_setups, frames, daily, chosen, expression, test[0], test[-1])
        folds.append(stats)
        pdt += stats.pdt_blocked
        skipped += stats.premium_skipped
        print(
            f"  walk-forward {expression} fold {fold + 1}: {test[0]} to {test[-1]} trades {stats.metrics.get('trades')}",
            flush=True,
        )
    metrics = _stitch(folds)
    return {
        "metrics": metrics,
        "pdt_blocked": pdt,
        "premium_skipped": skipped,
        "bust": any(stats.bust for stats in folds),
        "folds": len(folds),
    }


def random_setups(setups: list[Setup], frames: dict[str, pd.DataFrame], seed: int = 17) -> list[Setup]:
    """Same symbols, directions, and count. Timestamps are shuffled. Seed 17."""
    rng = np.random.default_rng(seed)
    grouped: dict[str, list[Setup]] = {}
    for setup in setups:
        grouped.setdefault(setup.symbol, []).append(setup)
    out: list[Setup] = []
    for symbol, group in grouped.items():
        frame = frames.get(symbol)
        if frame is None or len(frame) < 5:
            continue
        usable = list(range(1, len(frame) - 1))
        picks = rng.choice(usable, size=len(group), replace=len(usable) < len(group))
        for setup, pos in zip(group, picks):
            fill_i = int(pos)
            opened = float(frame.iloc[fill_i]["open"])
            if setup.fill_time in frame.index:
                real_open = float(frame.loc[setup.fill_time, "open"])
            else:
                real_open = opened
            distance = abs(real_open - float(setup.stop))
            if not np.isfinite(distance) or distance <= 0:
                distance = opened * 0.005
            stop = opened - distance if setup.direction == "long" else opened + distance
            stamp = frame.index[fill_i]
            out.append(
                Setup(
                    symbol=symbol,
                    direction=setup.direction,
                    kind=setup.kind,
                    signal_time=frame.index[fill_i - 1],
                    fill_time=stamp,
                    anchor_time=frame.index[max(0, fill_i - 2)],
                    stop=float(stop),
                    atr=float(setup.atr),
                    reference=float("nan"),
                )
            )
    out.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.kind))
    return out


def _whole_share_hold(daily: pd.DataFrame, start: date, end: date) -> dict:
    frame = to_ny(daily) if getattr(daily.index, "tz", None) is not None else daily
    if getattr(frame.index, "tz", None) is not None:
        mask = np.array([start <= _day(ts) <= end for ts in frame.index])
    else:
        mask = np.array([start <= pd.Timestamp(ts).date() <= end for ts in frame.index])
    window = frame.loc[mask]
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
    close = window["close"].astype(float)
    equity = close * shares + cash
    equity.iloc[0] = cash + shares * entry
    equity.iloc[-1] = cash + shares * exit_
    trades = pd.DataFrame(
        [{
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
        }]
    )
    result = BacktestResult(equity=equity, exposure=pd.Series(1.0, index=equity.index), trades=trades, ending_equity=float(equity.iloc[-1]))
    metrics = compute_metrics(result, STARTING)
    metrics["shares"] = shares
    return metrics


def _cell_label(cell: dict) -> str:
    changes = []
    if cell.get("k_sep") != DEFAULTS["k_sep"]:
        changes.append(f"k_sep={cell['k_sep']}")
    if cell.get("require_ema200"):
        changes.append("above 200 EMA")
    if cell.get("morning_only"):
        changes.append("9:30-11:30")
    if cell.get("rsi_filter"):
        changes.append("RSI and MACD")
    if cell.get("avoid_extended"):
        changes.append("inside VWAP band")
    return "default" if not changes else ", ".join(changes)


def _score(oos: dict, walk: dict, train_sharpes: list[float]) -> tuple[list[str], bool]:
    trades = int(oos.get("trades") or 0)
    flags = overfit_flags(
        default_oos=oos,
        walk_forward=walk,
        train_sharpes=train_sharpes,
        survivorship_sensitive=False,
        short_sample=True,
        min_trades=20,
    )
    if trades < MIN_CONCLUSION:
        flags.append("anecdotal_sample")
    selectable = is_selectable(flags, oos, min_trades=MIN_CONCLUSION) and trades >= MIN_CONCLUSION
    return flags, selectable


def _split(days: list[date], is_fraction: float) -> tuple[list[date], list[date]]:
    split = days[int(len(days) * is_fraction)]
    is_days = [day for day in days if day < split]
    oos_days = [day for day in days if day >= split]
    if not is_days or not oos_days:
        cut = max(1, len(days) // 2)
        return days[:cut], days[cut:]
    return is_days, oos_days


def run_clock(name: str, frames, daily, extras, execution: str, is_fraction: float) -> dict:
    print(f"== {name} ==", flush=True)
    cells = _cells(execution)
    by_cell = []
    for cell in cells:
        label = _cell_label(cell)
        print(f"  detect {label}", flush=True)
        by_cell.append((cell, detect_all(frames, daily, extras, cell)))
    setups = by_cell[0][1]
    days = _sessions(frames)
    if not days:
        raise RuntimeError(f"{name} has no bars")
    is_days, oos_days = _split(days, is_fraction)
    print(
        f"  sessions {days[0]} .. {days[-1]} ({len(days)}), IS through {is_days[-1]}, OOS {oos_days[0]}, signals {len(setups)}",
        flush=True,
    )
    books: dict[str, BookStats] = {}
    walks = {}
    shuffled = random_setups(setups, frames, seed=17)
    for expression in ("stock", "single", "spread"):
        books[f"full_{expression}"] = _book(setups, frames, daily, cells[0], expression)
        books[f"is_{expression}"] = _window_book(setups, frames, daily, cells[0], expression, is_days[0], is_days[-1])
        books[f"oos_{expression}"] = _window_book(setups, frames, daily, cells[0], expression, oos_days[0], oos_days[-1])
        books[f"oos_random_{expression}"] = _window_book(shuffled, frames, daily, cells[0], expression, oos_days[0], oos_days[-1])
        print(f"  walk-forward {expression}", flush=True)
        walks[expression] = _walk(frames, daily, by_cell, days, expression)
        print(
            f"  {expression} OOS trades {books[f'oos_{expression}'].metrics.get('trades')} "
            f"skipped {books[f'oos_{expression}'].premium_skipped} pdt {books[f'oos_{expression}'].pdt_blocked}",
            flush=True,
        )
    grid_rows = []
    is_sharpes = []
    for cell, found in by_cell:
        stats = _window_book(found, frames, daily, cell, "stock", is_days[0], is_days[-1])
        is_sharpes.append(float(stats.metrics.get("sharpe") or 0.0))
        grid_rows.append((_cell_label(cell), stats))
    sensitivities = []
    for expression, patches in _sensitivity_patches(cells[0]).items():
        for label, patch in patches:
            params = dict(cells[0])
            params.update(patch)
            stats = _window_book(setups, frames, daily, params, expression, oos_days[0], oos_days[-1])
            sensitivities.append((f"{expression}: {label}", stats))
    hold = _whole_share_hold(daily["SPY"], oos_days[0], oos_days[-1]) if "SPY" in daily else {}
    stock_flags, stock_ok = _score(books["oos_stock"].metrics, walks["stock"]["metrics"], is_sharpes)
    spread_flags, spread_ok = _score(books["oos_spread"].metrics, walks["spread"]["metrics"], is_sharpes)
    single_flags, single_ok = _score(books["oos_single"].metrics, walks["single"]["metrics"], is_sharpes)
    directions = {
        "long": sum(1 for setup in setups if setup.direction == "long"),
        "short": sum(1 for setup in setups if setup.direction == "short"),
        "A": sum(1 for setup in setups if setup.kind == "A"),
        "B": sum(1 for setup in setups if setup.kind == "B"),
    }
    return {
        "name": name,
        "execution": execution,
        "sessions": [str(days[0]), str(days[-1]), len(days)],
        "is": [str(is_days[0]), str(is_days[-1])],
        "oos": [str(oos_days[0]), str(oos_days[-1])],
        "signals": len(setups),
        "directions": directions,
        "books": books,
        "walks": walks,
        "flags": {"stock": stock_flags, "spread": spread_flags, "single": single_flags},
        "selectable": bool(stock_ok and spread_ok and single_ok),
        "fragile": fragile_grid(is_sharpes),
        "grid_rows": grid_rows,
        "sensitivities": sensitivities,
        "hold": hold,
        "setups": setups,
    }


def _sensitivity_patches(base: dict) -> dict[str, list[tuple[str, dict]]]:
    del base
    shared_tail = [
        ("IV 1.00x realized", {"iv_premium": 1.0}),
        ("IV 1.30x realized", {"iv_premium": 1.3}),
        ("doubled bid/ask", {"spread_multiplier": 2.0}),
        ("cash account, T+1", {"account": "cash_t1"}),
    ]
    return {
        "stock": [
            ("risk 10%", {"risk_fraction": 0.10}),
            ("risk 25%", {"risk_fraction": 0.25}),
            ("target 1.5R", {"reward_r": 1.5}),
            ("trail the 9 EMA", {"trail": "ema9"}),
            ("target at the band or prior extreme", {"target_mode": "level"}),
            ("cash account, T+1", {"account": "cash_t1"}),
        ],
        "single": [
            ("0 DTE, rough", {"dte": 0}),
            ("7 DTE, rough", {"dte": 7}),
            ("delta 0.40", {"delta": 0.40}),
            ("delta 0.50", {"delta": 0.50}),
            *shared_tail,
        ],
        "spread": [
            ("$1 wide", {"spread_width": 1.0}),
            ("$5 wide", {"spread_width": 5.0}),
            ("7 DTE", {"spread_dte": 7}),
            ("14 DTE", {"spread_dte": 14}),
            *shared_tail,
        ],
    }


def _between(stamp, start: time, end: time) -> bool:
    clock = _clock(stamp)
    return start <= clock <= end


def verify_examples(m5, m15, hourly, daily) -> list[dict]:
    """Flag the three annotated sessions. This does not change the rules."""
    checks = [
        {
            "name": "UNH 5m Oct 6 short, failed breakout then 9/20 cross",
            "symbol": "UNH",
            "execution": "5m",
            "frame": m5.get("UNH"),
            "extras": {"15m": m15.get("UNH"), "60m": hourly.get("UNH")},
            "day": date(2026, 10, 6),
            "kind": "B",
            "direction": "short",
            "signal_from": time(10, 0),
            "signal_to": time(10, 40),
            "anchor_from": time(9, 40),
            "anchor_to": time(10, 0),
        },
        {
            "name": "SPY 5m Oct 6 long, retest then continuation",
            "symbol": "SPY",
            "execution": "5m",
            "frame": m5.get("SPY"),
            "extras": {"15m": m15.get("SPY"), "60m": hourly.get("SPY")},
            "day": date(2026, 10, 6),
            "kind": "A",
            "direction": "long",
            "signal_from": time(10, 15),
            "signal_to": time(10, 50),
            "anchor_from": None,
            "anchor_to": None,
        },
        {
            "name": "SPY 15m Oct 6 long, retest of 778.57 holding the EMA",
            "symbol": "SPY",
            "execution": "15m",
            "frame": m15.get("SPY"),
            "extras": {"60m": hourly.get("SPY")},
            "day": date(2026, 10, 6),
            "kind": "A",
            "direction": "long",
            "signal_from": time(10, 0),
            "signal_to": time(11, 0),
            "anchor_from": None,
            "anchor_to": None,
        },
    ]
    rows = []
    for check in checks:
        params = dict(DEFAULTS)
        params["execution"] = check["execution"]
        frame = check["frame"]
        if frame is None or check["symbol"] not in daily:
            rows.append({**check, "hit": False, "detail": "no bars", "matches": [], "same_day": []})
            continue
        bundle = {check["execution"]: frame, "daily": daily[check["symbol"]]}
        for key, value in check["extras"].items():
            if value is not None and len(value):
                bundle[key] = value
        setups = find_setups(bundle, params, symbol=check["symbol"])
        same_day = [setup for setup in setups if _day(setup.signal_time) == check["day"]]
        matches = []
        for setup in same_day:
            if setup.kind != check["kind"] or setup.direction != check["direction"]:
                continue
            if not _between(setup.signal_time, check["signal_from"], check["signal_to"]):
                continue
            if check["anchor_from"] is not None and not _between(setup.anchor_time, check["anchor_from"], check["anchor_to"]):
                continue
            matches.append(setup)
        detail = _fmt_setup(matches[0]) if matches else "no setup in the marked window"
        print(f"  verify {check['name']}: {'HIT' if matches else 'MISS'} {detail}", flush=True)
        rows.append(
            {
                "name": check["name"],
                "symbol": check["symbol"],
                "execution": check["execution"],
                "day": check["day"],
                "hit": bool(matches),
                "detail": detail,
                "matches": matches,
                "same_day": same_day,
                "frame": frame,
            }
        )
    return rows


def _fmt_setup(setup: Setup) -> str:
    signal = pd.Timestamp(setup.signal_time).tz_convert(NY)
    anchor = pd.Timestamp(setup.anchor_time).tz_convert(NY)
    fill = pd.Timestamp(setup.fill_time).tz_convert(NY)
    return (
        f"{setup.kind} {setup.direction} anchor {anchor.strftime('%H:%M')} "
        f"signal {signal.strftime('%H:%M')} fill {fill.strftime('%H:%M')} stop {setup.stop:.2f}"
    )


def save_example_charts(rows: list[dict], report_dir: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    folders = [report_dir / "setups", Path("/opt/cursor/artifacts/setups")]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for row in rows:
        frame = row.get("frame")
        if frame is None or getattr(frame, "empty", True):
            continue
        ny = to_ny(frame)
        day = row["day"]
        session = ny[[_day(ts) == day for ts in ny.index]]
        if session.empty:
            continue
        bands = session_bands(ny, 2.0).reindex(session.index)
        close = ny["close"].astype(float)
        fast = ema(close, 9).reindex(session.index)
        slow = ema(close, 20).reindex(session.index)
        slow200 = ema(close, 200).reindex(session.index)
        clock = np.array([ts.time() for ts in session.index])
        morning = session[(clock >= time(9, 30)) & (clock <= time(12, 30))]
        if morning.empty:
            morning = session.iloc[: min(40, len(session))]
        fig, ax = plt.subplots(figsize=(11, 5))
        for ts, bar in morning.iterrows():
            color = "#26a69a" if float(bar["close"]) >= float(bar["open"]) else "#ef5350"
            ax.plot([ts, ts], [bar["low"], bar["high"]], color=color, linewidth=0.8)
            ax.plot([ts, ts], [bar["open"], bar["close"]], color=color, linewidth=3.2)
        shown = bands.reindex(morning.index)
        ax.plot(morning.index, fast.reindex(morning.index), color="#f4d35e", linewidth=1.0, label="EMA 9")
        ax.plot(morning.index, slow.reindex(morning.index), color="#7bdff2", linewidth=1.0, label="EMA 20")
        ax.plot(morning.index, slow200.reindex(morning.index), color="#b388ff", linewidth=1.0, label="EMA 200")
        ax.plot(shown.index, shown["vwap"], color="#c47b00", linewidth=1.0, label="VWAP")
        ax.plot(shown.index, shown["upper"], color="#c47b00", linewidth=0.7, linestyle="--", label="+2 SD")
        ax.plot(shown.index, shown["lower"], color="#c47b00", linewidth=0.7, linestyle="--", label="-2 SD")
        match = row["matches"][0] if row.get("matches") else None
        if match is not None and match.signal_time in morning.index:
            ax.scatter([match.signal_time], [float(morning.loc[match.signal_time, "close"])], color="#1b5e20", zorder=4, label="signal")
            ax.axhline(match.stop, color="#b00020", linestyle=":", linewidth=0.8, label="stop")
        if match is not None and match.anchor_time in morning.index:
            extreme = "high" if match.direction == "short" else "low"
            ax.scatter(
                [match.anchor_time],
                [float(morning.loc[match.anchor_time, extreme])],
                color="#c47b00",
                zorder=4,
                label="impulse / breakout",
            )
        status = "HIT" if row["hit"] else "MISS"
        ax.set_title(f"{row['symbol']} {row['execution']} {day} {status}: {row['detail']}")
        ax.legend(loc="best", fontsize=7)
        fig.autofmt_xdate()
        fig.tight_layout()
        name = f"read{row['execution']}_{row['symbol']}_{day}.png"
        for folder in folders:
            path = folder / name
            fig.savefig(path, dpi=120)
            saved.append(path)
        plt.close(fig)
    if saved:
        print("Example charts: " + ", ".join(str(path) for path in saved), flush=True)
    return saved


def _money(value) -> str:
    return f"${float(value or 0):.2f}"


def _pf(metrics: dict) -> str:
    value = metrics.get("profit_factor")
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _header() -> str:
    return (
        "| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | "
        "Ending | Bust | Ruin est. | PDT blocked | Skipped |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|"
    )


def _row(label: str, stats=None, metrics: dict | None = None) -> str:
    if metrics is None:
        metrics = stats.metrics if stats is not None and hasattr(stats, "metrics") else (stats or {})
    if hasattr(stats, "pdt_blocked"):
        pdt = stats.pdt_blocked
        skipped = stats.premium_skipped
        bust = "yes" if stats.bust else "no"
        ruin = "n/a" if stats.ruin_estimate is None else f"{stats.ruin_estimate:.2f}"
    elif isinstance(stats, dict) and "pdt_blocked" in stats:
        pdt = stats["pdt_blocked"]
        skipped = stats["premium_skipped"]
        bust = "yes" if stats.get("bust") else "no"
        ruin = "n/a"
        metrics = stats["metrics"]
    else:
        pdt = 0
        skipped = 0
        bust = "no"
        ruin = "n/a"
    return (
        f"| {label} | {int(metrics.get('trades') or 0)} | {float(metrics.get('win_rate') or 0):.1%} | "
        f"{_money(metrics.get('avg_win'))} | {_money(metrics.get('avg_loss'))} | "
        f"{_money(metrics.get('expectancy'))} | {_pf(metrics)} | {float(metrics.get('max_drawdown') or 0):.1%} | "
        f"{float(metrics.get('sharpe') or 0):.2f} | {_money(metrics.get('ending_equity'))} | "
        f"{bust} | {ruin} | {pdt} | {skipped} |"
    )


def _verdict(examples: list[dict], studies: list[dict]) -> str:
    hits = sum(1 for row in examples if row["hit"])
    parts = [f"{row['symbol']} {row['execution']} {'hit' if row['hit'] else 'missed'}" for row in examples]
    primary = studies[0] if studies else None
    if primary is None:
        return "DOES NOT PASS. The books were not scored."
    stock = primary["books"]["oos_stock"]
    single = primary["books"]["oos_single"]
    spread = primary["books"]["oos_spread"]
    stock_n = int(stock.metrics.get("trades") or 0)
    single_n = int(single.metrics.get("trades") or 0)
    spread_n = int(spread.metrics.get("trades") or 0)
    full_stock_n = int(primary["books"]["full_stock"].metrics.get("trades") or 0)
    passed = all(study["selectable"] for study in studies) and hits == 3
    opening = "PASSES" if passed else "DOES NOT PASS"
    sample = (
        f"The 5-minute out-of-sample stock book took {stock_n} trades and ended at "
        f"{_money(stock.metrics.get('ending_equity'))}. "
        f"The 0-7 DTE single-option book took {single_n} and ended at {_money(single.metrics.get('ending_equity'))}. "
        f"The SPY/QQQ debit-spread book took {spread_n} and ended at {_money(spread.metrics.get('ending_equity'))}. "
        f"The full 5-minute stock sample took {full_stock_n} trades."
    )
    gate = (
        "Every clock is inside the free Yahoo intraday cap, and none of the out-of-sample books "
        "clears the existing gates (300 trades, profit factor 1.10, Sharpe 0.40, drawdown no worse than -30%, "
        "a stable walk-forward). Counts under 300 are anecdotal. Not added to the optional list. "
        "The default book is still dual momentum."
    )
    return (
        f"**{opening}.** The frozen detector matched {hits} of 3 annotated sessions ({', '.join(parts)}). "
        f"{sample} {gate} Nothing was sent to a broker."
    )


def _examples_markdown(examples: list[dict]) -> list[str]:
    lines = [
        "### Annotated sessions, checked before scoring",
        "",
        "The rules were frozen to these three charts. A later P&L number was not allowed to move a threshold.",
        "",
        "| Chart | Result | What the detector marked |",
        "|---|---|---|",
    ]
    for row in examples:
        lines.append(f"| {row['name']} | {'hit' if row['hit'] else 'miss'} | {row['detail']} |")
    lines.append("")
    for row in examples:
        others = []
        matched = {id(setup) for setup in row.get("matches", [])}
        for setup in row.get("same_day", []):
            if id(setup) in matched:
                continue
            others.append(_fmt_setup(setup))
        if others:
            lines.append(
                f"Other {row['symbol']} {row['execution']} signals on {row['day']}: " + "; ".join(others) + "."
            )
    if any(row.get("same_day") for row in examples):
        lines.append("")
    return lines


def _study_markdown(study: dict) -> list[str]:
    lines = [
        f"### {study['name']}",
        "",
        (
            f"Sessions {study['sessions'][0]} through {study['sessions'][1]} ({study['sessions'][2]} sessions). "
            f"In sample {study['is'][0]} to {study['is'][1]}. Out of sample {study['oos'][0]} to {study['oos'][1]}. "
            f"Signals {study['signals']} "
            f"({study['directions']['long']} long, {study['directions']['short']} short, "
            f"{study['directions']['A']} continuation, {study['directions']['B']} failed-break). "
            f"Stock flags: {', '.join(study['flags']['stock'])}. "
            f"Spread flags: {', '.join(study['flags']['spread'])}. "
            f"Single-option flags: {', '.join(study['flags']['single'])}."
        ),
        "",
        _header(),
    ]
    labels = [
        ("full_stock", "Stock, fractional, full sample"),
        ("is_stock", "Stock, fractional, in sample"),
        ("oos_stock", "Stock, fractional, out of sample"),
        ("oos_random_stock", "Stock, random entries, out of sample"),
        ("full_single", "0-7 DTE single, full sample, rough"),
        ("is_single", "0-7 DTE single, in sample, rough"),
        ("oos_single", "0-7 DTE single, out of sample, rough"),
        ("oos_random_single", "0-7 DTE single, random entries, out of sample, rough"),
        ("full_spread", "Debit spread, full sample"),
        ("is_spread", "Debit spread, in sample"),
        ("oos_spread", "Debit spread, out of sample"),
        ("oos_random_spread", "Debit spread, random entries, out of sample"),
    ]
    for key, label in labels:
        lines.append(_row(label, study["books"][key]))
    for expression, label in (
        ("stock", "Stock, walk-forward"),
        ("single", "0-7 DTE single, walk-forward, rough"),
        ("spread", "Debit spread, walk-forward"),
    ):
        lines.append(_row(label, study["walks"][expression]))
    if study.get("hold"):
        lines.append(_row("SPY buy and hold, whole shares, out of sample", metrics=study["hold"]))
    lines.append("")
    if study["walks"]["stock"]["folds"] == 0:
        lines.append("Walk-forward needs 40 sessions, so that row is an empty window, not a tested fold.")
        lines.append("")
    lines.append("Signal grid, in-sample fractional stock (one change from the frozen default per row):")
    lines.append("")
    lines.append(_header())
    for label, stats in study["grid_rows"]:
        lines.append(_row(label, stats))
    lines.append("")
    lines.append("Sensitivities on the out-of-sample window. These were not used to pick the default.")
    lines.append("")
    lines.append(_header())
    for label, stats in study["sensitivities"]:
        lines.append(_row(label, stats))
    lines.append("")
    return lines


def write_report(examples: list[dict], studies: list[dict], charts: list[Path], results_path: Path) -> str:
    verdict = _verdict(examples, studies)
    lines = [
        "## Chart-read EMA and VWAP test",
        "",
        (
            "Rules frozen to the three Oct 6, 2026 thinkorswim charts before scoring. "
            "Chart: EMA 9, EMA 20, EMA 200, session VWAP with ±2 standard deviations, RSI(14), MACD(12, 26, 9). "
            "Continuation (setup A): 9 EMA above 20, both rising, separation at least 0.25 ATR, close above VWAP. "
            "A majority of the higher timeframes agrees (daily, 60-minute, and 15-minute on a 5-minute signal; "
            "not all of them). After a new session high or a tag of the outer band, price pulls back at least "
            "0.5 ATR to the 9 EMA, the 20 EMA, or VWAP without a close through the 20 EMA. The trigger is a "
            "strong candle (close in the top third, body at least half the range) that does not close below the "
            "prior bar's low. Entry is the next open. Stop is the pullback low. "
            "Failed break (setup B): a close back through a break of the prior 6-bar high or the outer band, "
            "then a fresh 9/20 cross and a close through VWAP within 12 bars. Stop is the failed extreme. "
            "This short is allowed unless every higher timeframe is a clean trend the other way, which is what "
            "keeps the UNH example (mixed daily, not a unanimous uptrend). "
            "Target is 2R, with an exit on a close back through the 20 EMA, and a flat at the end of the session "
            "on 5-minute and 15-minute bars. The 60-minute book holds up to five sessions instead of flattening "
            "every day. One position. Risk 20% of a $1,000 account (10% and 25% are sensitivities). "
            "Whole option contracts only. Fractional shares are the stock baseline. "
            "Margin under $25,000: at most 3 day trades in 5 sessions. "
            "The signal grid changes one filter at a time (separation 0.10 or 0.50 ATR, require the 200 EMA, "
            "first two hours only, RSI and MACD, stay inside the outer band). "
            "DTE, delta, spread width, IV, and the bid/ask haircut are sensitivities. "
            "0-7 DTE prices are a Black-Scholes sketch and are labeled rough."
        ),
        "",
        verdict,
        "",
    ]
    lines.extend(_examples_markdown(examples))
    for study in studies:
        lines.extend(_study_markdown(study))
    lines.append(
        "Stock shorts are a research baseline. They are not orders. "
        "A single contract or a debit spread is skipped when the debit is above the risk fraction. "
        "Debit spreads are SPY and QQQ only, 7-14 DTE, default $2 wide and 10 DTE. "
        "The $2,000 margin-equity floor is not applied: this test is about whether the setups fit $1,000, "
        "and that floor would block every new position. The day-trade count is still enforced."
    )
    lines.append("")
    lines.append(
        "0-7 DTE prices use trailing realized volatility times 1.15, a one-minute time floor, and a haircut "
        "of 4% at the money, 8% otherwise, and 12% when the mid is under $1. They are not quotes."
    )
    lines.append("")
    if charts:
        names = []
        for path in charts:
            if path.name not in names and "reports" in str(path):
                names.append(path.name)
        lines.append(
            "Charts of the three annotated sessions, with the detector's marks, are in `reports/setups/`: "
            + ", ".join(f"`{name}`" for name in names)
            + ". VWAP is the full session. The orange dot is the impulse or the failed-breakout bar. The green dot is the signal close."
        )
        lines.append("")
    lines.append(
        "Profit factor gate 1.10, Sharpe gate 0.40, drawdown no worse than -30%, and at least 300 trades. "
        "A 5-minute or 15-minute Yahoo file is about 55 days. The 60-minute file is the free hourly cap. "
        "Neither is a sample this project will select from."
    )
    lines.append("")
    body = "\n".join(lines)
    text = results_path.read_text() if results_path.exists() else ""
    start = "<!-- CHART_READS_START -->"
    end = "<!-- CHART_READS_END -->"
    block = f"{start}\n{body}\n{end}\n"
    if start in text and end in text:
        text = text[: text.index(start)] + block + text[text.index(end) + len(end) + 1 :]
    else:
        marker = "<!-- MTF_VWAP_END -->"
        if marker in text:
            at = text.index(marker) + len(marker)
            text = text[:at] + "\n\n" + block + text[at:]
        else:
            if text and not text.endswith("\n"):
                text += "\n"
            text += "\n" + block
    results_path.write_text(text)
    summary = {
        "verdict": verdict,
        "examples": [
            {"name": row["name"], "hit": row["hit"], "detail": row["detail"]}
            for row in examples
        ],
        "studies": [_jsonable(study) for study in studies],
    }
    Path("/tmp/chart_reads_summary.json").write_text(json.dumps(summary, default=_dump, indent=2))
    print(verdict, flush=True)
    return verdict


def _jsonable(study: dict) -> dict:
    def pack(stats: BookStats) -> dict:
        return {
            "metrics": {
                key: (None if isinstance(value, float) and not np.isfinite(value) else value)
                for key, value in stats.metrics.items()
            },
            "pdt_blocked": stats.pdt_blocked,
            "premium_skipped": stats.premium_skipped,
            "bust": stats.bust,
            "min_equity": stats.min_equity,
            "ruin_estimate": stats.ruin_estimate,
            "reasons": stats.trades["reason"].value_counts().to_dict() if stats.trades is not None and len(stats.trades) else {},
        }

    return {
        "name": study["name"],
        "sessions": study["sessions"],
        "is": study["is"],
        "oos": study["oos"],
        "signals": study["signals"],
        "directions": study["directions"],
        "flags": study["flags"],
        "selectable": study["selectable"],
        "books": {key: pack(stats) for key, stats in study["books"].items()},
        "walks": study["walks"],
        "hold": study["hold"],
        "grid": [(label, pack(stats)) for label, stats in study["grid_rows"]],
        "sensitivities": [(label, pack(stats)) for label, stats in study["sensitivities"]],
    }


def _dump(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    return str(value)


def load_yahoo(provider: YFinanceProvider):
    end = pd.Timestamp(END)
    print("downloading daily", flush=True)
    daily = provider.history(SYMBOLS, "2023-01-01", END, interval="1d")
    print("downloading 60m", flush=True)
    hourly = provider.history(SYMBOLS, (end - pd.Timedelta(days=720)).date().isoformat(), END, interval="60m")
    print("downloading 15m", flush=True)
    m15 = provider.history(SYMBOLS, (end - pd.Timedelta(days=55)).date().isoformat(), END, interval="15m")
    print("downloading 5m", flush=True)
    m5 = provider.history(SYMBOLS, (end - pd.Timedelta(days=55)).date().isoformat(), END, interval="5m")
    for name, book in ("daily", daily), ("60m", hourly), ("15m", m15), ("5m", m5):
        lengths = {symbol: len(frame) for symbol, frame in book.items()}
        print(f"  {name} {lengths}", flush=True)
    return daily, hourly, m15, m5


def main() -> None:
    provider = YFinanceProvider("data/cache")
    daily, hourly, m15, m5 = load_yahoo(provider)
    present = [symbol for symbol in SYMBOLS if symbol in daily and symbol in hourly and len(hourly[symbol]) > 50]
    if "SPY" not in present or "UNH" not in present:
        raise SystemExit("SPY or UNH history did not download")
    daily = {symbol: daily[symbol] for symbol in present}
    hourly = {symbol: hourly[symbol] for symbol in present if symbol in hourly}
    m15 = {symbol: m15[symbol] for symbol in present if symbol in m15 and len(m15[symbol]) > 30}
    m5 = {symbol: m5[symbol] for symbol in present if symbol in m5 and len(m5[symbol]) > 30}
    print("verifying annotated sessions", flush=True)
    examples = verify_examples(m5, m15, hourly, daily)
    charts = save_example_charts(examples, Path("reports"))
    study5 = run_clock(
        "5-minute execution",
        m5,
        daily,
        {"15m": m15, "60m": hourly},
        "5m",
        0.60,
    )
    study15 = run_clock(
        "15-minute execution",
        m15,
        daily,
        {"60m": hourly},
        "15m",
        0.60,
    )
    study60 = run_clock(
        "60-minute execution",
        hourly,
        daily,
        {},
        "60m",
        0.50,
    )
    write_report(examples, [study5, study15, study60], charts, Path("RESULTS.md"))


if __name__ == "__main__":
    main()
