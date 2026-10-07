"""Score the multi-timeframe VWAP-test rules. Backtests only.

Nothing in this module calls a broker. The 15-minute Yahoo window is about
60 days. The 60-minute window is the free hourly cap, about two years.
Neither is long enough to join the book. A Binance hourly series is a
labeled proxy, not a stock result.

Run: ``python -m webull_bot.mtf_vwap.research``
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.backtest.assessment import fragile_grid, is_selectable, overfit_flags, pick_params
from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.costs import CostModel
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.mtf_vwap.detect import Setup, find_setups, session_vwap, to_ny
from webull_bot.mtf_vwap.params import DEFAULTS, grid
from webull_bot.mtf_vwap.simulate import BookStats, simulate_options, simulate_stock

SYMBOLS = ["SPY", "QQQ", "AAPL", "AMD", "NVDA", "TSLA", "IWM"]
STARTING = 1_000.0
MIN_CONCLUSION = 300
NY = "America/New_York"
END = "2026-10-07"


def _day(ts) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert(NY)
    return stamp.date()


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
    setups.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    return setups


def _book(kind: str, setups, frames, daily, params) -> BookStats:
    if kind == "stock":
        return simulate_stock(setups, frames, daily, params, starting_equity=STARTING, costs=CostModel())
    return simulate_options(setups, frames, daily, params, starting_equity=STARTING)


def _window_book(kind, setups, frames, daily, params, start: date, end: date) -> BookStats:
    return _book(kind, _in_window(setups, start, end), _slice(frames, start, end), daily, params)


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


def _pf(metrics: dict) -> str:
    value = metrics.get("profit_factor")
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _money(value) -> str:
    return f"${float(value or 0):.2f}"


def _row(label: str, stats: BookStats | None, metrics: dict | None = None) -> str:
    metrics = metrics if metrics is not None else (stats.metrics if stats else {})
    pdt = stats.pdt_blocked if stats else 0
    skipped = stats.premium_skipped if stats else 0
    bust = "yes" if stats and stats.bust else "no"
    ruin = "n/a" if stats is None or stats.ruin_estimate is None else f"{stats.ruin_estimate:.2f}"
    return (
        f"| {label} | {int(metrics.get('trades') or 0)} | {float(metrics.get('win_rate') or 0):.1%} | "
        f"{_money(metrics.get('avg_win'))} | {_money(metrics.get('avg_loss'))} | "
        f"{_money(metrics.get('expectancy'))} | {_pf(metrics)} | {float(metrics.get('max_drawdown') or 0):.1%} | "
        f"{float(metrics.get('sharpe') or 0):.2f} | {_money(metrics.get('ending_equity'))} | "
        f"{bust} | {ruin} | {pdt} | {skipped} |"
    )


def _header() -> str:
    return (
        "| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | "
        "Ending | Bust | Ruin est. | PDT blocked | Premium skipped |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|"
    )


def random_setups(setups: list[Setup], frames: dict[str, pd.DataFrame], seed: int = 17) -> list[Setup]:
    """Same symbols, directions, and count. Timestamps are shuffled. Seed 17.

    The stop distance and the target distance are copied from the real setup
    so the exit rules are the same kind of distance, not the same calendar bar.
    """
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
            real_open = float(frame.iloc[frame.index.get_loc(setup.fill_time)]["open"]) if setup.fill_time in frame.index else opened
            if setup.direction == "long":
                distance = real_open - float(setup.stop)
                stop = opened - abs(distance if np.isfinite(distance) and distance != 0 else opened * 0.005)
                target = None
                if setup.target is not None and np.isfinite(setup.target):
                    target = opened + abs(float(setup.target) - real_open)
            else:
                distance = float(setup.stop) - real_open
                stop = opened + abs(distance if np.isfinite(distance) and distance != 0 else opened * 0.005)
                target = None
                if setup.target is not None and np.isfinite(setup.target):
                    target = opened - abs(real_open - float(setup.target))
            stamp = frame.index[fill_i]
            out.append(
                Setup(
                    symbol=symbol,
                    direction=setup.direction,
                    test_time=frame.index[fill_i - 1],
                    confirm_time=frame.index[fill_i - 1],
                    fill_time=stamp,
                    vwap=float("nan"),
                    zone=None,
                    stop=float(stop),
                    target=None if target is None else float(target),
                    atr=float(setup.atr),
                )
            )
    out.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    return out


def _whole_share_hold(daily: pd.DataFrame, start: date, end: date) -> dict:
    """Buy whole SPY shares with $1,000. No fraction if one share does not fit."""
    frame = to_ny(daily) if getattr(daily.index, "tz", None) is not None else daily
    if getattr(frame.index, "tz", None) is not None:
        mask = np.array([start <= _day(ts) <= end for ts in frame.index])
    else:
        mask = np.array([start <= pd.Timestamp(ts).date() <= end for ts in frame.index])
    window = frame.loc[mask]
    if window.empty:
        return compute_metrics(BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()), STARTING)
    entry = float(window.iloc[0]["open"]) * (1.0 + 6.0 / 10_000.0)
    exit_ = float(window.iloc[-1]["close"]) * (1.0 - 6.0 / 10_000.0)
    shares = int(np.floor(STARTING / entry)) if entry > 0 else 0
    if shares < 1:
        metrics = compute_metrics(
            BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
            STARTING,
        )
        metrics["trades"] = 0
        metrics["note"] = "one share cost more than $1,000"
        return metrics
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


def _same_cell(left: dict, right: dict) -> bool:
    keys = ("alignment", "ema_daily", "require_zone", "use_trendline", "confirm", "use_bands", "execution")
    return all(left.get(key) == right.get(key) for key in keys)


def _walk(frames, daily, found: list[tuple[dict, list]], days: list[date], kind: str = "option") -> dict:
    """Three test folds on the second half. Each fold trains on the prior 180 days."""
    if len(days) < 40:
        return compute_metrics(BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()), STARTING)
    half = len(days) // 2
    test_days = days[half:]
    width = max(1, len(test_days) // 3)
    folds = []
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
            stats = _window_book(kind, setups, frames, daily, cell, train[0], train[-1])
            rows.append({"params": cell, **stats.metrics})
        chosen = pick_params(rows, found[0][0], min_trades=15)
        chosen_setups = found[0][1]
        for cell, setups in found:
            if _same_cell(cell, chosen):
                chosen_setups = setups
                chosen = cell
                break
        folds.append(_window_book(kind, chosen_setups, frames, daily, chosen, test[0], test[-1]))
        print(f"  walk-forward fold {fold + 1}: {test[0]} to {test[-1]} trades {folds[-1].metrics.get('trades')}", flush=True)
    return _stitch(folds)


def _score(oos: dict, walk: dict, train_sharpes: list[float], *, hourly: bool) -> tuple[list[str], bool]:
    trades = int(oos.get("trades") or 0)
    short = True if hourly else trades < MIN_CONCLUSION
    flags = overfit_flags(
        default_oos=oos,
        walk_forward=walk,
        train_sharpes=train_sharpes,
        survivorship_sensitive=False,
        short_sample=short,
        min_trades=20,
    )
    if trades < MIN_CONCLUSION:
        flags.append("anecdotal_sample")
    # Both the long-stock book and the option book would have to clear, and
    # the hourly file is still the free Yahoo cap. Selection stays closed
    # unless a later sample is long enough. ``is_selectable`` already blocks
    # on short_sample.
    selectable = is_selectable(flags, oos, min_trades=MIN_CONCLUSION) and trades >= MIN_CONCLUSION and not hourly
    return flags, selectable


def run_clock(name: str, frames, daily, extras, execution: str, is_fraction: float) -> dict:
    print(f"== {name} ==", flush=True)
    cells = _cells(execution)
    default = cells[0]
    by_cell = []
    for cell in cells:
        label = _cell_label(cell)
        print(f"  detect {label}", flush=True)
        by_cell.append((cell, detect_all(frames, daily, extras, cell)))
    setups = by_cell[0][1]
    days = _sessions(frames)
    if not days:
        raise RuntimeError(f"{name} has no bars")
    split = days[int(len(days) * is_fraction)]
    # The split day belongs to the out-of-sample window.
    is_days = [day for day in days if day < split]
    oos_days = [day for day in days if day >= split]
    if not is_days or not oos_days:
        is_days, oos_days = days[: max(1, len(days) // 2)], days[max(1, len(days) // 2) :]
    print(f"  {name} sessions {days[0]} .. {days[-1]} ({len(days)}), IS through {is_days[-1]}, OOS {oos_days[0]}", flush=True)
    books = {}
    books["full_options"] = _book("option", setups, frames, daily, default)
    books["is_options"] = _window_book("option", setups, frames, daily, default, is_days[0], is_days[-1])
    books["oos_options"] = _window_book("option", setups, frames, daily, default, oos_days[0], oos_days[-1])
    books["full_stock"] = _book("stock", setups, frames, daily, default)
    books["oos_stock"] = _window_book("stock", setups, frames, daily, default, oos_days[0], oos_days[-1])
    loose = dict(default)
    loose["premium_cap"] = 1.0
    books["oos_stock_full"] = _window_book("stock", setups, frames, daily, loose, oos_days[0], oos_days[-1])
    books["full_stock_full"] = _book("stock", setups, frames, daily, loose)
    print("  walk-forward", flush=True)
    walk = _walk(frames, daily, by_cell, days, kind="option")
    # Fragility uses the in-sample option Sharpe of each signal cell, once.
    is_sharpes = []
    grid_rows = []
    for cell, found in by_cell:
        stats = _window_book("option", found, frames, daily, cell, is_days[0], is_days[-1])
        is_sharpes.append(float(stats.metrics.get("sharpe") or 0.0))
        grid_rows.append((_cell_label(cell), stats))
    flags, selectable = _score(books["oos_options"].metrics, walk, is_sharpes, hourly=True)
    shuffled = random_setups(setups, frames, seed=17)
    books["oos_random"] = _window_book("option", shuffled, frames, daily, default, oos_days[0], oos_days[-1])
    books["oos_random_stock"] = _window_book("stock", shuffled, frames, daily, loose, oos_days[0], oos_days[-1])
    sensitivities = []
    for label, patch in _sensitivity_patches(execution):
        params = dict(default)
        params.update(patch)
        if patch.keys() & {"require_5m_reclaim", "confirm", "use_bands", "alignment"}:
            found = detect_all(frames, daily, extras, params)
        else:
            found = setups
        stats = _window_book("option", found, frames, daily, params, oos_days[0], oos_days[-1])
        sensitivities.append((label, stats))
        print(f"  sensitivity {label}: trades {stats.metrics.get('trades')} skipped {stats.premium_skipped}", flush=True)
    hold = _whole_share_hold(daily["SPY"], oos_days[0], oos_days[-1]) if "SPY" in daily else {}
    directions = {"long": sum(1 for s in setups if s.direction == "long"), "short": sum(1 for s in setups if s.direction == "short")}
    return {
        "name": name,
        "execution": execution,
        "sessions": [str(days[0]), str(days[-1]), len(days)],
        "is": [str(is_days[0]), str(is_days[-1])],
        "oos": [str(oos_days[0]), str(oos_days[-1])],
        "signals": len(setups),
        "directions": directions,
        "books": books,
        "walk": walk,
        "flags": flags,
        "selectable": selectable,
        "fragile": fragile_grid(is_sharpes),
        "is_sharpes": is_sharpes,
        "grid_rows": grid_rows,
        "sensitivities": sensitivities,
        "hold": hold,
        "setups": setups,
    }


def _cell_label(cell: dict) -> str:
    changes = [f"{key}={cell[key]}" for key in ("alignment", "ema_daily", "require_zone", "use_trendline", "confirm", "use_bands") if cell.get(key) != DEFAULTS.get(key)]
    return "default" if not changes else ", ".join(changes)


def _sensitivity_patches(execution: str) -> list[tuple[str, dict]]:
    patches = [
        ("0-7 DTE (3, flat at the close)", {"dte": 3, "flatten_eod": True, "max_hold_sessions": 1}),
        ("0 DTE, flat at the close", {"dte": 0, "flatten_eod": True, "max_hold_sessions": 1}),
        ("21 DTE", {"dte": 21}),
        ("delta 0.40", {"delta": 0.40}),
        ("delta 0.60", {"delta": 0.60}),
        ("premium stop -30%", {"premium_stop": -0.30}),
        ("premium target +30%", {"premium_target": 0.30}),
        ("premium target +100%", {"premium_target": 1.00}),
        ("IV 1.00x realized", {"iv_premium": 1.0}),
        ("IV 1.30x realized", {"iv_premium": 1.3}),
        ("doubled bid/ask", {"spread_multiplier": 2.0}),
        ("premium cap 20%", {"premium_cap": 0.20}),
        ("premium cap 30%", {"premium_cap": 0.30}),
        ("max 2 positions", {"max_positions": 2}),
        ("cash account, T+1", {"account": "cash_t1"}),
    ]
    if execution == "15m":
        patches.append(("5-minute reclaim", {"require_5m_reclaim": True}))
    return patches


def _proxy(end: date) -> dict | None:
    try:
        from webull_bot.fanatics.data import download_binance
    except Exception as exc:  # pragma: no cover - import guard
        print(f"binance import failed: {exc}", flush=True)
        return None
    start = end - timedelta(days=730)
    try:
        frame = download_binance("BTCUSDT", "1h", start, end)
    except Exception as exc:
        print(f"binance download failed: {exc}", flush=True)
        return None
    if frame is None or frame.empty or len(frame) < 100:
        print("binance proxy had no usable bars", flush=True)
        return None
    daily = frame.resample("1D").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("volume", "sum")
    ).dropna(subset=["close"])
    params = dict(DEFAULTS)
    params["execution"] = "60m"
    print(f"binance proxy rows {len(frame)}", flush=True)
    setups = find_setups({"60m": frame, "daily": daily}, params, symbol="BTCUSDT")
    days = _sessions({"BTCUSDT": frame})
    if len(days) < 10:
        return {"error": "too few sessions", "signals": len(setups)}
    split = days[len(days) // 2]
    oos = _window_book("option", setups, {"BTCUSDT": frame}, {"BTCUSDT": daily}, params, split, days[-1])
    return {
        "signals": len(setups),
        "sessions": [str(days[0]), str(days[-1]), len(days)],
        "oos": oos,
        "note": (
            "Proxy. BTCUSDT hourly bars from data.binance.vision. Session VWAP is reset at "
            "09:30 America/New_York, which is not a crypto session. Not a stock result and not gated."
        ),
    }


def save_charts(frames_15, daily, setups: list[Setup], report_dir: Path, *, prefix: str = "vwap") -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    folders = [report_dir / "setups", Path("/opt/cursor/artifacts/setups")]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        for stale in folder.glob(f"{prefix}_*.png"):
            stale.unlink()
    longs = [setup for setup in setups if setup.direction == "long"][:2]
    shorts = [setup for setup in setups if setup.direction == "short"][:2]
    chosen = longs + shorts
    saved: list[Path] = []
    for i, setup in enumerate(chosen, start=1):
        frame = frames_15.get(setup.symbol)
        if frame is None or frame.empty:
            continue
        ny = to_ny(frame)
        if setup.test_time not in ny.index:
            continue
        loc = ny.index.get_loc(setup.test_time)
        if isinstance(loc, slice):
            loc = loc.start
        # VWAP is the full session, then the window is drawn. A slice that
        # starts mid-session would otherwise rebuild VWAP from the first plotted bar.
        vwap = session_vwap(ny)
        window = ny.iloc[max(0, loc - 20) : min(len(ny), loc + 8)]
        shown = vwap.reindex(window.index).dropna(subset=["vwap"])
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.plot(window.index, window["close"], color="#1f4e79", label="close", linewidth=1.2)
        if len(shown):
            ax.plot(shown.index, shown["vwap"], color="#c47b00", label="session VWAP", linewidth=1.0)
        if setup.zone is not None:
            ax.axhline(setup.zone, color="#2e7d32", linestyle="--", linewidth=0.8, label="zone")
        ax.axhline(setup.stop, color="#b00020", linestyle=":", linewidth=0.8, label="stop")
        if setup.target is not None:
            ax.axhline(setup.target, color="#6a1b9a", linestyle=":", linewidth=0.8, label="target")
        extreme = "low" if setup.direction == "long" else "high"
        ax.scatter(
            [setup.test_time],
            [float(ny.loc[setup.test_time, extreme])],
            color="#c47b00",
            zorder=3,
            label="test wick",
        )
        if setup.confirm_time in ny.index:
            ax.scatter(
                [setup.confirm_time],
                [float(ny.loc[setup.confirm_time, "close"])],
                color="#1b5e20",
                zorder=3,
                label="confirm close",
            )
        ax.set_title(
            f"{setup.symbol} {setup.direction} VWAP test {_day(setup.test_time)}  "
            f"VWAP {setup.vwap:.2f}  zone {setup.zone if setup.zone is not None else 'none'}"
        )
        ax.legend(loc="best", fontsize=8)
        fig.autofmt_xdate()
        fig.tight_layout()
        name = f"{prefix}_{i}_{setup.symbol}_{setup.direction}_{_day(setup.test_time)}.png"
        for folder in folders:
            path = folder / name
            fig.savefig(path, dpi=120)
            saved.append(path)
        plt.close(fig)
    if saved:
        print("Setup charts: " + ", ".join(str(path) for path in saved), flush=True)
    else:
        print("Setup charts were not written: the 15-minute detector had no example", flush=True)
    return saved


def _verdict(studies: list[dict]) -> str:
    """Plain reading of the default option book. The tables below hold the rest."""
    any_pass = any(study["selectable"] for study in studies)
    bits = []
    for study in studies:
        oos = study["books"]["oos_options"]
        full = study["books"]["full_options"]
        bits.append(
            f"{study['name']}: {study['signals']} signals, "
            f"{int(full.metrics.get('trades') or 0)} option trades, "
            f"{full.premium_skipped} skipped because one contract exceeded the cap, "
            f"out-of-sample ending {_money(oos.metrics.get('ending_equity'))}"
        )
    lead = "PASSES" if any_pass else "DOES NOT PASS"
    tail = (
        " It is optional, paper only."
        if any_pass
        else (
            " Both windows are under 300 trades and inside Yahoo's free intraday cap, "
            "so they are anecdotal and are not a durable edge. "
            "Not added to the optional list. The default book is still dual momentum."
        )
    )
    return lead + ". " + " ".join(bits) + "." + tail


def _study_markdown(study: dict) -> list[str]:
    lines = [
        f"### {study['name']}",
        "",
        (
            f"Sessions {study['sessions'][0]} through {study['sessions'][1]} "
            f"({study['sessions'][2]} sessions). In sample {study['is'][0]} to {study['is'][1]}. "
            f"Out of sample {study['oos'][0]} to {study['oos'][1]}. "
            f"Signals {study['signals']} ({study['directions']['long']} long, {study['directions']['short']} short). "
            f"Flags: {', '.join(study['flags']) if study['flags'] else 'none'}."
        ),
        "",
        _header(),
        _row("Options, full sample", study["books"]["full_options"]),
        _row("Options, in sample", study["books"]["is_options"]),
        _row("Options, out of sample", study["books"]["oos_options"]),
        _row("Options, walk-forward", None, study["walk"]),
        _row("Options, random entries, out of sample", study["books"]["oos_random"]),
        _row("Stock, 25% cap, out of sample", study["books"]["oos_stock"]),
        _row("Stock, whole shares up to $1,000, out of sample", study["books"]["oos_stock_full"]),
        _row("Stock, whole shares up to $1,000, full sample", study["books"]["full_stock_full"]),
    ]
    hold = study["hold"]
    if hold:
        lines.append(
            f"| SPY buy and hold, whole shares, out of sample | {int(hold.get('trades') or 0)} | "
            f"{float(hold.get('win_rate') or 0):.1%} | {_money(hold.get('avg_win'))} | {_money(hold.get('avg_loss'))} | "
            f"{_money(hold.get('expectancy'))} | {_pf(hold)} | {float(hold.get('max_drawdown') or 0):.1%} | "
            f"{float(hold.get('sharpe') or 0):.2f} | {_money(hold.get('ending_equity'))} | no | n/a | 0 | 0 |"
        )
    lines.extend(["", "Signal grid, in-sample option book (one change from the default per row):", "", _header()])
    for label, stats in study["grid_rows"]:
        lines.append(_row(label, stats))
    lines.extend(["", "Sensitivities on the out-of-sample window. These are not grid cells and were not used to pick parameters.", "", _header()])
    for label, stats in study["sensitivities"]:
        lines.append(_row(label, stats))
    lines.append("")
    return lines


def _jsonable(study: dict) -> dict:
    def pack(stats: BookStats) -> dict:
        return {
            "metrics": {key: (None if isinstance(value, float) and not np.isfinite(value) else value) for key, value in stats.metrics.items()},
            "pdt_blocked": stats.pdt_blocked,
            "premium_skipped": stats.premium_skipped,
            "bust": stats.bust,
            "min_equity": stats.min_equity,
            "ruin_estimate": stats.ruin_estimate,
            "reasons": stats.trades["reason"].value_counts().to_dict() if stats.trades is not None and len(stats.trades) else {},
        }

    packed = {name: pack(stats) for name, stats in study["books"].items()}
    return {
        "name": study["name"],
        "sessions": study["sessions"],
        "is": study["is"],
        "oos": study["oos"],
        "signals": study["signals"],
        "directions": study["directions"],
        "flags": study["flags"],
        "selectable": study["selectable"],
        "fragile": study["fragile"],
        "walk": study["walk"],
        "hold": study["hold"],
        "books": packed,
        "grid": [(label, pack(stats)) for label, stats in study["grid_rows"]],
        "sensitivities": [(label, pack(stats)) for label, stats in study["sensitivities"]],
    }


def write_report(studies: list[dict], proxy: dict | None, charts: list[Path], results_path: Path) -> str:
    verdict = _verdict(studies)
    lines = [
        "## Multi-timeframe VWAP test",
        "",
        (
            "Rules, scored on the pre-registered default and not on a mined neighbor: "
            "trend alignment on weekly, daily, and the execution bar (15-minute also requires 60-minute and, when the file is present, 5-minute); "
            "a session VWAP test that wicks into VWAP and closes back with the trend, at a pivot or prior-day zone; "
            "the next 15-minute or 60-minute bar confirms; entry at the following open. "
            "Longs buy a call. Shorts buy a put. Delta 0.50, 14 DTE (inside 7-30), premium stop -50%, premium target +50%, "
            "also exit on a close back through VWAP, through the setup extreme, at the next level, or after 2 sessions. "
            "One position. One contract must cost at most 25% of a $1,000 account or the trade is skipped. "
            "Webull option fees and a bid/ask haircut (4% at-the-money, 8% otherwise, 12% when the mid is under $1). "
            "Margin account under $25,000: at most 3 day trades in 5 sessions. "
            "The signal grid changes one rule at a time (majority alignment, daily EMA 10, no zone, trendline, same-bar confirmation, VWAP bands). "
            "DTE, delta, premium targets, IV, and spreads are sensitivities."
        ),
        "",
        verdict,
        "",
    ]
    for study in studies:
        lines.extend(_study_markdown(study))
    lines.extend(
        [
            "Stock shorts in the comparison book are a research baseline. They are not sent as orders. "
            "A share that costs more than the cap is skipped, same as a contract. "
            "The whole-share column lets the $1,000 account buy one share when the share itself fits, so the signal can be read when the 25% cap blocks every name.",
            "",
            "0-7 DTE prices are a Black-Scholes sketch from recent realized volatility. They are not a quote, and they get worse as expiry approaches zero.",
            "",
        ]
    )
    if proxy and proxy.get("oos"):
        lines.extend(
            [
                "### Binance BTC proxy",
                "",
                proxy["note"],
                "",
                f"Sessions {proxy['sessions'][0]} through {proxy['sessions'][1]} ({proxy['sessions'][2]}). Signals {proxy['signals']}.",
                "",
                _header(),
                _row("Options, second half, proxy", proxy["oos"]),
                "",
            ]
        )
    elif proxy and proxy.get("error"):
        lines.append(f"Binance proxy was not scored: {proxy['error']}.")
        lines.append("")
    else:
        lines.append("Binance proxy was not available, so there is no extra hourly sample.")
        lines.append("")
    if charts:
        names = sorted({path.name for path in charts})
        lines.append("Example charts of detected tests are in `reports/setups/` (" + ", ".join(f"`{name}`" for name in names) + ").")
        lines.append("")
    lines.append(
        "The 15-minute book cannot pass: the file is shorter than 300 trades can honestly support. "
        "The 60-minute book is the bigger sample and is still the free Yahoo hourly cap, which this project does not select from. "
        f"Profit factor gate 1.10, Sharpe gate 0.40, drawdown no worse than -30%. "
        f"Out-of-sample profit factor on the 60-minute default is {_pf(studies[-1]['books']['oos_options'].metrics)}."
        if studies
        else "No study was produced."
    )
    lines.append("")
    body = "\n".join(lines)
    text = results_path.read_text() if results_path.exists() else ""
    start = "<!-- MTF_VWAP_START -->"
    end = "<!-- MTF_VWAP_END -->"
    block = f"{start}\n{body}\n{end}\n"
    if start in text and end in text:
        text = text[: text.index(start)] + block + text[text.index(end) + len(end) + 1 :]
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "\n" + block
    results_path.write_text(text)
    summary = {
        "verdict": verdict,
        "studies": [_jsonable(study) for study in studies],
        "proxy": None
        if not proxy or not proxy.get("oos")
        else {
            "signals": proxy["signals"],
            "sessions": proxy["sessions"],
            "note": proxy["note"],
            "oos": {
                "metrics": proxy["oos"].metrics,
                "pdt_blocked": proxy["oos"].pdt_blocked,
                "premium_skipped": proxy["oos"].premium_skipped,
                "bust": proxy["oos"].bust,
                "ruin_estimate": proxy["oos"].ruin_estimate,
            },
        },
    }
    out = Path("/tmp/mtf_vwap_summary.json")
    out.write_text(json.dumps(summary, default=_dump, indent=2))
    print(verdict, flush=True)
    return verdict


def _dump(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return str(value)


def load_yahoo(provider: YFinanceProvider) -> tuple[dict, dict, dict, dict]:
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
    if "SPY" not in present:
        raise SystemExit("SPY history did not download")
    daily = {symbol: daily[symbol] for symbol in present}
    hourly = {symbol: hourly[symbol] for symbol in present if symbol in hourly}
    m15 = {symbol: m15[symbol] for symbol in present if symbol in m15 and len(m15[symbol]) > 50}
    m5 = {symbol: m5[symbol] for symbol in present if symbol in m5 and len(m5[symbol]) > 50}
    study60 = run_clock("60-minute execution, daily and weekly trend", hourly, daily, {}, "60m", 0.50)
    study15 = run_clock(
        "15-minute execution, weekly daily 60m 15m and 5m trend",
        m15,
        daily,
        {"5m": m5, "60m": hourly},
        "15m",
        0.60,
    )
    proxy = _proxy(date.fromisoformat(END))
    charts = save_charts(m15, daily, study15["setups"], Path("reports"), prefix="vwap15")
    charts.extend(save_charts(hourly, daily, study60["setups"], Path("reports"), prefix="vwap60"))
    write_report([study15, study60], proxy, charts, Path("RESULTS.md"))


if __name__ == "__main__":
    main()
