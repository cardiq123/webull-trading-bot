"""Support-reversal and wedge-breakout studies.

The stock gate is the existing one, scored on the pre-registered default
by ``_study_daily`` (long stock only, which is what paper can trade).
The option book is a separate Black-Scholes estimate with a fixed +30%
premium target. It does not choose parameters. A pass that would enable
the strategy requires both the long-stock book and that default option
book to clear the numeric gates. Short stock is reported and is not
paper-traded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from webull_bot.backtest.assessment import is_selectable
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.backtest.short_book import simulate_shorts
from webull_bot.costs import CostModel
from webull_bot.options.premium_exit import (
    DEFAULT_DELTA,
    DEFAULT_DTE,
    PREMIUM_STOP,
    entries_from_signals,
    simulate_premium_book,
)
from webull_bot.strategies.registry import strategy_by_name

IN_SAMPLE_START = "2013-01-01"
IN_SAMPLE_END = "2016-12-31"
OOS_START = "2017-01-01"


def run_pattern_studies(bars, limits, costs, sample_end) -> list[Any]:
    studies = []
    for name in ("support_reversal", "wedge_breakout"):
        print(f"Testing {name} [dow]", flush=True)
        try:
            studies.append(_run_one(name, bars, limits, costs, sample_end))
        except Exception as exc:
            import traceback

            traceback.print_exc()
            from webull_bot.backtest.engine import BacktestResult
            from webull_bot.backtest.metrics import compute_metrics
            from webull_bot.research import STARTING_EQUITY, Study

            empty = compute_metrics(
                BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
                STARTING_EQUITY,
            )
            studies.append(
                Study(
                    name=name,
                    mode="dow",
                    citation=name,
                    default_oos=empty,
                    walk_forward=empty,
                    flags=["error"],
                    selectable=False,
                    notes=[f"Research run failed: {exc}"],
                )
            )
    return studies


def _run_one(name: str, bars, limits, costs, sample_end):
    from webull_bot.research import STARTING_EQUITY, _execute, _metrics_from_returns, _study_daily

    strategy = strategy_by_name(name)
    study = _study_daily(strategy, "dow", bars, limits, costs, sample_end=sample_end)
    earlier = _execute(
        strategy, "dow", bars, limits, costs,
        trade_start=pd.Timestamp(IN_SAMPLE_START),
        trade_end=pd.Timestamp(IN_SAMPLE_END),
        params=dict(strategy.default_params),
    )
    study.insample_metrics = compute_metrics(earlier, STARTING_EQUITY)
    study.insample_trades = earlier.trades
    harsh = CostModel(slippage_bps=15.0, half_spread_bps=2.0)
    stressed = _execute(
        strategy, "dow", bars, limits, harsh,
        trade_start=pd.Timestamp(OOS_START),
        trade_end=pd.Timestamp(sample_end),
        params=dict(strategy.default_params),
    )
    study.stress_metrics = compute_metrics(stressed, STARTING_EQUITY)
    from webull_bot.backtest.assessment import profit_factor_value

    stress_pf = profit_factor_value(study.stress_metrics)
    stress_sharpe = float(study.stress_metrics.get("sharpe") or 0.0)
    if study.selectable and (stress_pf < 1.0 or stress_sharpe < 0):
        study.flags.append("cost_fragile")
        study.selectable = False
        study.notes.append(
            f"At 15 bps slippage and 2 bps half-spread, OOS profit factor was "
            f"{stress_pf:.2f} and Sharpe was {stress_sharpe:.2f}."
        )
    elif study.selectable:
        study.notes.append(
            f"Still profitable at 15 bps slippage (Sharpe {stress_sharpe:.2f}, "
            f"profit factor {stress_pf:.2f})."
        )

    study.shorts = {
        "oos": _short_metrics(strategy, bars, costs, sample_end, dict(strategy.default_params), OOS_START, sample_end),
        "is": _short_metrics(strategy, bars, costs, sample_end, dict(strategy.default_params), IN_SAMPLE_START, IN_SAMPLE_END),
        "wf": _short_walk(strategy, bars, costs, sample_end, study),
    }
    print(f"Pricing {name} option estimate (+30% premium target)", flush=True)
    study.premium = _premium_pack(strategy, bars, sample_end, study)
    option_metrics = study.premium["combined_oos"]["metrics"]
    study.option_passed = is_selectable([], option_metrics)
    if study.selectable and not study.option_passed:
        study.selectable = False
        study.flags.append("option_book_failed")
        study.notes.append(
            "The long-stock book cleared the gates, but the pre-registered "
            "option book (30 DTE, 0.65 delta, +30% premium target, -50% premium "
            "stop, favorable-extreme path, IV 1.15x) did not. Not enabled."
        )
    elif not study.option_passed:
        study.notes.append(
            "The pre-registered option estimate did not clear the numeric gates. "
            "A profitable option column would still not be enabled on its own."
        )
    return study


def _signals(strategy, bars, params, trade_end):
    from webull_bot.research import _scope

    scoped = _scope(bars, strategy.universe("dow"), trade_end)
    chosen = dict(params)
    chosen["symbols"] = strategy.universe("dow")
    return strategy.generate(scoped, None, chosen)


def _short_metrics(strategy, bars, costs, sample_end, params, start, end) -> dict[str, Any]:
    from webull_bot.research import STARTING_EQUITY

    signals = _signals(strategy, bars, params, sample_end)
    result = simulate_shorts(
        signals, bars, costs=costs,
        trade_start=pd.Timestamp(start), trade_end=pd.Timestamp(end),
        starting_equity=STARTING_EQUITY,
    )
    metrics = compute_metrics(result, STARTING_EQUITY)
    metrics["avg_hold_sessions"] = _hold(result.trades)
    return {"metrics": metrics, "equity": result.daily_equity(), "trades": result.trades}


def _short_walk(strategy, bars, costs, sample_end, study) -> dict[str, Any]:
    from webull_bot.research import STARTING_EQUITY, _metrics_from_returns

    fold_returns = []
    fold_trades = []
    fold_exposure = []
    for test_start, test_end, params in getattr(study, "fold_params", []):
        pack = _short_metrics(strategy, bars, costs, sample_end, params, test_start, test_end)
        equity = pack["equity"]
        if equity is not None and len(equity):
            base = pd.Series([STARTING_EQUITY], index=[equity.index[0] - pd.Timedelta(days=1)])
            fold_returns.append(pd.concat([base, equity]).pct_change().dropna())
        if pack["trades"] is not None and len(pack["trades"]):
            fold_trades.append(pack["trades"])
        if equity is not None and len(equity):
            fold_exposure.append(pd.Series(0.0, index=equity.index))
    metrics = _metrics_from_returns(fold_returns, fold_trades, fold_exposure)
    trades = pd.concat(fold_trades) if fold_trades else pd.DataFrame()
    metrics["avg_hold_sessions"] = _hold(trades)
    return {"metrics": metrics, "trades": trades}


def _premium_pack(strategy, bars, sample_end, study) -> dict[str, Any]:
    default = dict(strategy.default_params)
    oos_signals = _signals(strategy, bars, default, sample_end)
    oos_entries = entries_from_signals(oos_signals, pd.Timestamp(OOS_START), pd.Timestamp(sample_end))
    is_signals = _signals(strategy, bars, default, pd.Timestamp(IN_SAMPLE_END))
    is_entries = entries_from_signals(is_signals, pd.Timestamp(IN_SAMPLE_START), pd.Timestamp(IN_SAMPLE_END))
    specs = [
        ("combined_oos", oos_entries, {}),
        ("call_oos", [row for row in oos_entries if row["right"] == "call"], {}),
        ("put_oos", [row for row in oos_entries if row["right"] == "put"], {}),
        ("combined_is", is_entries, {}),
        ("combined_close", oos_entries, {"path": "close"}),
        ("combined_dte_21", oos_entries, {"dte": 21}),
        ("combined_dte_45", oos_entries, {"dte": 45}),
        ("combined_delta_50", oos_entries, {"delta": 0.50}),
        ("combined_stop_30", oos_entries, {"premium_stop": -0.30}),
        ("combined_iv_100", oos_entries, {"iv_premium": 1.00}),
        ("combined_iv_130", oos_entries, {"iv_premium": 1.30}),
        ("combined_wide", oos_entries, {"spread_multiplier": 2.0}),
    ]
    packs = {key: _run_premium(entries, bars, sample_end, **overrides) for key, entries, overrides in specs}
    walks = _premium_walk(strategy, bars, sample_end, study)
    packs.update(walks)
    return packs


def _run_premium(entries, bars, sample_end, **overrides) -> dict[str, Any]:
    kwargs = dict(
        dte=DEFAULT_DTE,
        delta=DEFAULT_DELTA,
        iv_premium=1.15,
        spread_multiplier=1.0,
        premium_stop=PREMIUM_STOP,
        path="extreme",
        trade_end=pd.Timestamp(sample_end),
    )
    kwargs.update(overrides)
    return simulate_premium_book(entries, bars, **kwargs)


def _premium_walk(strategy, bars, sample_end, study) -> dict[str, dict[str, Any]]:
    from webull_bot.research import STARTING_EQUITY, _metrics_from_returns

    buckets = {
        "combined_wf": {"returns": [], "trades": [], "exposure": []},
        "call_wf": {"returns": [], "trades": [], "exposure": []},
        "put_wf": {"returns": [], "trades": [], "exposure": []},
    }
    for test_start, test_end, params in getattr(study, "fold_params", []):
        signals = _signals(strategy, bars, params, sample_end)
        entries = entries_from_signals(signals, pd.Timestamp(test_start), pd.Timestamp(test_end))
        groups = {
            "combined_wf": entries,
            "call_wf": [row for row in entries if row["right"] == "call"],
            "put_wf": [row for row in entries if row["right"] == "put"],
        }
        for key, group in groups.items():
            pack = _run_premium(group, bars, sample_end)
            equity = pack["equity"]
            if equity is not None and len(equity):
                base = pd.Series([STARTING_EQUITY], index=[equity.index[0] - pd.Timedelta(days=1)])
                buckets[key]["returns"].append(pd.concat([base, equity]).pct_change().dropna())
                buckets[key]["exposure"].append(pd.Series(0.0, index=equity.index))
            if pack["trades"] is not None and len(pack["trades"]):
                buckets[key]["trades"].append(pack["trades"])
    out = {}
    for key, bucket in buckets.items():
        metrics = _metrics_from_returns(bucket["returns"], bucket["trades"], bucket["exposure"])
        trades = pd.concat(bucket["trades"]) if bucket["trades"] else pd.DataFrame()
        metrics["avg_hold_sessions"] = _hold(trades)
        metrics["target_hit_rate"] = (
            float((trades["reason"] == "premium_target").mean()) if len(trades) and "reason" in trades.columns else 0.0
        )
        out[key] = {"metrics": metrics, "trades": trades, "equity": pd.Series(dtype=float)}
    return out


def _hold(trades) -> float | None:
    if trades is None or len(trades) == 0 or "bars_held" not in trades.columns:
        return None
    return float(pd.to_numeric(trades["bars_held"], errors="coerce").mean())


def pattern_markdown(studies, benchmark: dict, dual: dict | None) -> str:
    lines = ["", "## Support reversal and wedge breakout (Dow 30, point in time)", ""]
    lines.append(
        "Both books use effective-dated Dow membership. The gate scores the "
        "pre-registered default, not the best of the six variants. Walk-forward "
        "picks the stock-signal variant on the training window only. DTE, delta, "
        "the +30% premium target, and the -50% premium stop are fixed. "
        "Option prices are a Black-Scholes estimate: 20-day realized volatility "
        "times the stated premium, rate 2%, dividend yield 1.8%, half-spread 4% "
        "of the mid at these deltas, and the Webull option fee schedule. "
        "The favorable extreme is the underlying high for calls and the low for "
        "puts. If that bar could also have hit the premium stop, the stop fills. "
        "A target fills at +30% of the ask that was paid, not at the overshoot. "
        "There is no historical option chain."
    )
    lines.append("")
    lines.append(_header())
    if dual:
        lines.append(_row("Dual momentum", "2017-2026 out of sample", dual, None))
    lines.append(_row("SPY buy and hold", "2017-2026", benchmark, None))
    lines.append("")
    for study in studies:
        lines.extend(_one_section(study))
    lines.append("")
    return "\n".join(lines)


def _one_section(study) -> list[str]:
    lines = [f"### {study.name}", ""]
    lines.append(_header())
    lines.append(_row("Long stock, default", "2013-2016 earlier sample", study.insample_metrics, _hold(study.insample_trades)))
    lines.append(_row("Long stock, default", "2017-2026 out of sample", study.default_oos, _hold(study.oos_trades)))
    lines.append(_row("Long stock, walk-forward", "stitched OOS folds", study.walk_forward, _hold(study.wf_trades)))
    lines.append(_row("Long stock, 15 bps slippage", "2017-2026 out of sample", study.stress_metrics, None))
    shorts = getattr(study, "shorts", {}) or {}
    for label, key in (
        ("Short stock, default", "oos"),
        ("Short stock, walk-forward", "wf"),
        ("Short stock, default", "is"),
    ):
        pack = shorts.get(key)
        if not pack:
            continue
        window = {"oos": "2017-2026 out of sample", "wf": "stitched OOS folds", "is": "2013-2016 earlier sample"}[key]
        lines.append(_row(label, window, pack["metrics"], pack["metrics"].get("avg_hold_sessions")))
    premium = getattr(study, "premium", {}) or {}
    labels = [
        ("Options, default +30% target", "2017-2026 out of sample", "combined_oos"),
        ("Options, walk-forward signals", "stitched OOS folds", "combined_wf"),
        ("Options, default +30% target", "2013-2016 earlier sample", "combined_is"),
        ("Calls only", "2017-2026 out of sample", "call_oos"),
        ("Calls, walk-forward signals", "stitched OOS folds", "call_wf"),
        ("Puts only", "2017-2026 out of sample", "put_oos"),
        ("Puts, walk-forward signals", "stitched OOS folds", "put_wf"),
        ("Options, close-based marks", "2017-2026 sensitivity", "combined_close"),
        ("Options, 21 DTE", "2017-2026 sensitivity", "combined_dte_21"),
        ("Options, 45 DTE", "2017-2026 sensitivity", "combined_dte_45"),
        ("Options, 0.50 delta", "2017-2026 sensitivity", "combined_delta_50"),
        ("Options, premium stop -30%", "2017-2026 sensitivity", "combined_stop_30"),
        ("Options, IV 1.00x", "2017-2026 sensitivity", "combined_iv_100"),
        ("Options, IV 1.30x", "2017-2026 sensitivity", "combined_iv_130"),
        ("Options, 2x bid/ask", "2017-2026 sensitivity", "combined_wide"),
    ]
    for label, window, key in labels:
        pack = premium.get(key)
        if not pack:
            continue
        lines.append(_row(label, window, pack["metrics"], pack["metrics"].get("avg_hold_sessions"), pack["metrics"].get("target_hit_rate")))
    lines.append("")
    lines.append(f"Long-stock flags: {', '.join(study.flags) or 'none'}.")
    lines.append(f"Gate result: **{_verdict(study)}**")
    hit = premium.get("combined_oos", {}).get("metrics", {}).get("target_hit_rate")
    if hit is not None:
        lines.append(f"Default option book +30% target hit rate: {float(hit):.2%}.")
    lines.append("")
    return lines


def _verdict(study) -> str:
    if getattr(study, "promoted", False):
        return "PASSES and beats dual momentum. Added to the default book. Paper trades the long stock."
    if getattr(study, "passed_gates", False):
        return (
            "PASSES the long-stock gates and the pre-registered option estimate, "
            "does not beat dual momentum by 0.15 Sharpe, and is optional. Paper trades the long stock."
        )
    if "option_book_failed" in study.flags:
        return (
            "DOES NOT PASS. The long stock cleared the gates and the pre-registered "
            "option estimate did not. Not optional."
        )
    return (
        "DOES NOT PASS the out-of-sample gates. Not in the default book and not optional. "
        "The option column is an estimate and is not a separate pass."
    )


def _header() -> str:
    return (
        "| Book | Window | CAGR | Total | Win rate | Avg win | Avg loss | Expectancy | "
        "PF | Max DD | Sharpe | Exposure | Trades | Avg hold | +30% hit |\n"
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )


def _row(book, window, metrics, hold, hit=None) -> str:
    pf = metrics.get("profit_factor")
    pf_text = "n/a" if pf is None else f"{float(pf):.2f}"
    hold_text = "n/a" if hold is None else f"{float(hold):.1f}"
    hit_text = "n/a" if hit is None else f"{float(hit):.2%}"
    return (
        f"| {book} | {window} | {float(metrics.get('cagr') or 0):.2%} | "
        f"{float(metrics.get('total_return') or 0):.2%} | {float(metrics.get('win_rate') or 0):.2%} | "
        f"${float(metrics.get('avg_win') or 0):.0f} | ${float(metrics.get('avg_loss') or 0):.0f} | "
        f"${float(metrics.get('expectancy') or 0):.0f} | {pf_text} | "
        f"{float(metrics.get('max_drawdown') or 0):.2%} | {float(metrics.get('sharpe') or 0):.2f} | "
        f"{float(metrics.get('exposure') or 0):.2%} | {int(metrics.get('trades') or 0)} | {hold_text} | {hit_text} |"
    )


def save_setup_charts(bars, report_dir: Path) -> list[Path]:
    """Write a few detected trendline and wedge examples. Returns saved paths."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from webull_bot.strategies.support_reversal import SupportReversal
    from webull_bot.strategies.wedge_breakout import WedgeBreakout

    out_dirs = [report_dir / "setups", Path("/opt/cursor/artifacts/setups")]
    for folder in out_dirs:
        folder.mkdir(parents=True, exist_ok=True)
        for stale in folder.glob("trendline_*.png"):
            stale.unlink()
        for stale in folder.glob("wedge_*.png"):
            stale.unlink()
    support = SupportReversal()
    wedge = WedgeBreakout()
    symbols = [symbol for symbol in ("AAPL", "MSFT", "JPM", "CAT", "HD", "UNH", "BA", "IBM") if symbol in bars]
    support_params = dict(support.default_params)
    support_params["support"] = "trendline"
    support_params["symbols"] = symbols
    wedge_params = dict(wedge.default_params)
    wedge_params["symbols"] = symbols
    subset = {symbol: bars[symbol] for symbol in symbols}
    support_book = support.generate(subset, None, support_params)
    wedge_book = wedge.generate(subset, None, wedge_params)
    saved: list[Path] = []
    saved.extend(_plot_trendlines(plt, bars, support_book, out_dirs, limit=2))
    saved.extend(_plot_wedges(plt, bars, wedge_book, out_dirs, limit=2))
    if saved:
        print("Setup charts: " + ", ".join(str(path) for path in saved))
    else:
        print("Setup charts were not written: no trendline or wedge example in the chart symbols")
    return saved


def _plot_trendlines(plt, bars, book, out_dirs, limit: int) -> list[Path]:
    """Draw the two confirmed pivot lows the detector actually fitted."""
    from webull_bot.patterns import _pivot_points, confirmed_pivot_low

    candidates = []
    for symbol, signals in book.items():
        frame = bars[symbol]
        points = _pivot_points(confirmed_pivot_low(frame["low"], 3, 3), 3)
        flags = signals["entry_next_open"].fillna(False)
        for ts in flags[flags].index:
            loc = _loc(frame, ts)
            if loc is None:
                continue
            anchors = _trendline_anchors(points, loc)
            if anchors is None:
                continue
            earlier, later, slope = anchors
            span = later[0] - earlier[0]
            price = float(frame["close"].iloc[loc])
            # A chart of a multi-year line is unreadable. The detector itself
            # has no span cap; this filter only chooses the example image.
            if span < 15 or span > 80 or price <= 0:
                continue
            rise = slope * span / price
            candidates.append((rise, symbol, loc, anchors))
    candidates.sort(key=lambda item: item[0], reverse=True)
    saved = []
    used = set()
    for _rise, symbol, loc, anchors in candidates:
        if symbol in used or len(saved) >= limit:
            continue
        used.add(symbol)
        saved.append(_draw_trendline(plt, bars[symbol], symbol, loc, anchors, out_dirs))
    return saved


def _plot_wedges(plt, bars, book, out_dirs, limit: int) -> list[Path]:
    from webull_bot.patterns import wedge_lines

    candidates = []
    cache = {}
    for symbol, signals in book.items():
        frame = bars[symbol]
        lines = wedge_lines(frame["high"], frame["low"], 3, 3, lookback=40)
        cache[symbol] = lines
        flags = signals["entry_next_open"].fillna(False) | signals["short_next_open"].fillna(False)
        for ts in flags[flags].index:
            loc = _loc(frame, ts)
            if loc is None:
                continue
            row = lines.iloc[loc]
            if not row["kind"] or not np.isfinite(row["start"]):
                continue
            span = loc - int(row["start"])
            price = float(frame["close"].iloc[loc])
            height = float(row["upper"] - row["lower"])
            if span < 20 or price <= 0 or height <= 0:
                continue
            candidates.append((height / price, symbol, loc, str(row["kind"])))
    candidates.sort(key=lambda item: item[0], reverse=True)
    saved = []
    used = set()
    for _height, symbol, loc, kind in candidates:
        if symbol in used or len(saved) >= limit:
            continue
        used.add(symbol)
        saved.append(_draw_wedge(plt, bars[symbol], symbol, loc, cache[symbol].iloc[loc], kind, out_dirs))
    return saved


def _draw_trendline(plt, frame, symbol, loc, anchors, out_dirs) -> Path:
    earlier, later, slope = anchors
    pad_left = max(0, earlier[0] - 8)
    pad_right = min(len(frame), loc + 12)
    window = frame.iloc[pad_left:pad_right]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    _candles(ax, window)
    xs = frame.index[earlier[0] : loc + 1]
    ys = [earlier[1] + slope * (i - earlier[0]) for i in range(earlier[0], loc + 1)]
    ax.plot(xs, ys, color="#c47b00", linewidth=1.6, label="rising trendline")
    ax.scatter(
        [frame.index[earlier[0]], frame.index[later[0]]],
        [earlier[1], later[1]],
        color="#c47b00",
        zorder=3,
        label="confirmed pivot lows",
    )
    ax.scatter([frame.index[loc]], [frame["close"].iloc[loc]], color="#b00020", zorder=4, label="confirmation")
    when = pd.Timestamp(frame.index[loc]).date()
    ax.set_title(f"{symbol} rising trendline support, confirmed {when}")
    ax.legend(frameon=False, loc="upper left")
    fig.autofmt_xdate()
    return _save_fig(plt, fig, out_dirs, f"trendline_{symbol}.png")


def _draw_wedge(plt, frame, symbol, loc, row, kind, out_dirs) -> Path:
    start = int(row["start"])
    pad_left = max(0, start - 5)
    pad_right = min(len(frame), loc + 8)
    window = frame.iloc[pad_left:pad_right]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    _candles(ax, window)
    indexes = range(start, loc + 1)
    xs = frame.index[start : loc + 1]
    upper = [float(row["upper"]) + float(row["upper_slope"]) * (i - loc) for i in indexes]
    lower = [float(row["lower"]) + float(row["lower_slope"]) * (i - loc) for i in indexes]
    ax.plot(xs, upper, color="#9a3b2f", linewidth=1.6, label="upper line")
    ax.plot(xs, lower, color="#2f6b4f", linewidth=1.6, label="lower line")
    ax.scatter([frame.index[loc]], [frame["close"].iloc[loc]], color="#b00020", zorder=4, label="breakout close")
    when = pd.Timestamp(frame.index[loc]).date()
    ax.set_title(f"{symbol} {kind} wedge breakout, {when}")
    ax.legend(frameon=False, loc="upper left")
    fig.autofmt_xdate()
    return _save_fig(plt, fig, out_dirs, f"wedge_{symbol}.png")


def _candles(ax, window: pd.DataFrame) -> None:
    for ts, row in window.iterrows():
        color = "#1f7a4d" if row["close"] >= row["open"] else "#9a3b2f"
        ax.plot([ts, ts], [row["low"], row["high"]], color=color, linewidth=0.8)
        body_low = min(row["open"], row["close"])
        body_high = max(row["open"], row["close"])
        ax.plot([ts, ts], [body_low, body_high], color=color, linewidth=3.2)


def _trendline_anchors(points: list[tuple[int, float, int]], t: int):
    """The same two pivots ``rising_trendline`` uses on bar ``t``."""
    known = [point for point in points if point[2] < t]
    if len(known) < 2:
        return None
    x2, y2, _confirm = known[-1]
    chosen = None
    for point in reversed(known[:-1]):
        if point[0] < x2 and point[1] < y2:
            chosen = point
            break
    if chosen is None or x2 == chosen[0]:
        return None
    slope = (y2 - chosen[1]) / (x2 - chosen[0])
    if slope <= 0:
        return None
    return (chosen[0], chosen[1]), (x2, y2), slope


def _loc(frame: pd.DataFrame, ts) -> int | None:
    loc = frame.index.get_loc(ts)
    if isinstance(loc, slice):
        return None
    try:
        return int(loc)
    except (TypeError, ValueError):
        return None


def _save_fig(plt, fig, out_dirs, name: str) -> Path:
    path = out_dirs[0] / name
    fig.savefig(path, dpi=120, bbox_inches="tight")
    fig.savefig(out_dirs[1] / name, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path
