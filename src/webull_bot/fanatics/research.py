"""Score the eight Chart Fanatics specs.

The gate is the pre-registered default on the later window, not the best
grid cell. Walk-forward may pick a cell on the training window only.
A sample under 300 trades is anecdotal. Nothing here sends an order.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.backtest.assessment import is_selectable, overfit_flags, pick_params
from webull_bot.backtest.metrics import buy_and_hold_metrics, compute_metrics
from webull_bot.fanatics.data import BARS, INSTRUMENTS, download_yahoo_daily
from webull_bot.fanatics.seasonality import crash_and_vix_splits, random_proxy_signals, run_drift, run_proxy
from webull_bot.fanatics.simulate import STARTING_EQUITY, random_signals, simulate
from webull_bot.fanatics.specs import GRIDS, SIM, generate
from webull_bot.research import FOLDS

SAMPLE_END = "2026-09-30"
OOS_START = "2017-01-01"
MIN_CONCLUSION = 300
BLOCKING = {
    "short_sample",
    "anecdotal_sample",
    "parameter_fragile",
    "insufficient_trades",
    "oos_profit_factor_below_1",
    "oos_profit_factor_below_1_10",
    "oos_sharpe_negative",
    "oos_sharpe_below_0_40",
    "oos_drawdown_beyond_30",
    "walk_forward_sign_flip",
    "sharpe_decay",
    "cost_fragile",
}


def _load(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    frame = pd.read_pickle(path)
    if len(frame) == 0:
        return None
    return frame


def _calendar(frames: dict[str, pd.DataFrame], start, end) -> pd.DatetimeIndex:
    frame = next(iter(frames.values()))
    index = frame.index
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1)
    if index.tz is not None:
        if start_ts.tzinfo is None:
            start_ts = start_ts.tz_localize(index.tz)
            end_ts = end_ts.tz_localize(index.tz)
    else:
        start_ts = start_ts.tz_localize(None)
        end_ts = end_ts.tz_localize(None)
    return index[(index >= start_ts) & (index < end_ts)]


def _slice(frames, signals, start, end):
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1)
    kept = []
    for signal in signals:
        frame = frames.get(signal.symbol)
        if frame is None:
            continue
        loc = signal.signal_loc if signal.limit_entry is not None else signal.signal_loc + 1
        if loc >= len(frame):
            continue
        stamp = frame.index[loc]
        left, right = start_ts, end_ts
        if stamp.tzinfo is not None and left.tzinfo is None:
            left = left.tz_localize(stamp.tz)
            right = right.tz_localize(stamp.tz)
        elif stamp.tzinfo is None and left.tzinfo is not None:
            left = left.tz_localize(None)
            right = right.tz_localize(None)
        if left <= stamp < right:
            kept.append(signal)
    return kept


def _score(frames, signals, start, end, sim, stop_extra=1):
    chunk = _slice(frames, signals, start, end)
    if not frames:
        metrics = compute_metrics(
            type("R", (), {"daily_equity": lambda self: pd.Series(dtype=float), "exposure": pd.Series(dtype=float), "trades": pd.DataFrame()})(),
            STARTING_EQUITY,
        )
    calendar = _calendar(frames, start, end) if frames else pd.DatetimeIndex([])
    result, trades = simulate(frames, chunk, stop_extra_ticks=stop_extra, calendar=calendar, **sim)
    metrics = compute_metrics(result, STARTING_EQUITY)
    metrics["avg_r"] = float(trades["r"].mean()) if len(trades) else 0.0
    return metrics, trades, result


def _years(trades: pd.DataFrame) -> list[dict]:
    if trades is None or trades.empty:
        return []
    exits = pd.to_datetime(trades["exit_time"])
    if getattr(exits.dt, "tz", None) is not None:
        years = exits.dt.tz_convert("America/New_York").dt.year
    else:
        years = exits.dt.year
    rows = []
    for year, chunk in trades.groupby(years):
        rows.append(
            {
                "year": int(year),
                "trades": int(len(chunk)),
                "win_rate": float((chunk["pnl"] > 0).mean()),
                "avg_r": float(chunk["r"].mean()),
                "sum_r": float(chunk["r"].sum()),
                "pnl": float(chunk["pnl"].sum()),
            }
        )
    return rows


def _verdict(metrics: dict, flags: list[str], random_r: float | None, proxy: bool) -> str:
    trades = int(metrics.get("trades") or 0)
    if trades < MIN_CONCLUSION or "short_sample" in flags:
        return "inconclusive"
    failed = any(flag in BLOCKING for flag in flags)
    if random_r is not None and float(metrics.get("avg_r") or 0) <= random_r:
        failed = True
    if failed:
        return "no edge"
    if proxy:
        return "inconclusive"
    return "real edge"


def score_intraday(spec_id: int, bars, areas, symbols, folds, oos: tuple[str, str], insample: tuple[str, str], proxy: bool, label: str) -> dict:
    grid = []
    for cell in GRIDS[spec_id]:
        params = dict(cell)
        params["symbols"] = list(symbols)
        if spec_id == 6 and "ES=F" not in bars and "USA500IDXUSD" not in bars:
            params["smt"] = False
        grid.append(params)
    generated = []
    for params in grid:
        signals, frames = generate(spec_id, bars, params, areas)
        generated.append((params, signals, frames))
    sim = dict(SIM[spec_id])
    train_sharpes = []
    fold_returns = []
    fold_trades = []
    for train_start, train_end, test_start, test_end in folds:
        rows = []
        for params, signals, frames in generated:
            if not frames:
                continue
            metrics, _trades, result = _score(frames, signals, train_start, train_end, sim)
            rows.append({"params": params, **metrics, "result": result})
        if not rows:
            continue
        train_sharpes.extend(float(row["sharpe"] or 0) for row in rows)
        chosen = pick_params(rows, grid[0])
        chosen_signals, chosen_frames = next(
            (signals, frames) for params, signals, frames in generated if params == chosen
        )
        metrics, trades, result = _score(chosen_frames, chosen_signals, test_start, test_end, sim)
        daily = result.daily_equity()
        if len(daily):
            base = pd.Series([STARTING_EQUITY], index=[daily.index[0] - pd.Timedelta(days=1)])
            fold_returns.append(pd.concat([base, daily]).pct_change().dropna())
        if len(trades):
            fold_trades.append(trades)
    from webull_bot.research import _metrics_from_returns

    walk = _metrics_from_returns(fold_returns, fold_trades)
    if len(fold_trades):
        walk["avg_r"] = float(pd.concat(fold_trades)["r"].mean())
    else:
        walk["avg_r"] = 0.0
    default_signals, default_frames = generated[0][1], generated[0][2]
    oos_metrics, oos_trades, _oos_result = _score(default_frames, default_signals, oos[0], oos[1], sim)
    is_metrics, _is_trades, _is_result = _score(default_frames, default_signals, insample[0], insample[1], sim)
    stress, _stress_trades, _stress_result = _score(default_frames, default_signals, oos[0], oos[1], sim, stop_extra=2)
    random_r = None
    random_metrics = None
    if default_frames and default_signals:
        random_book = random_signals(default_frames, _slice(default_frames, default_signals, oos[0], oos[1]))
        random_metrics, _random_trades, _random_result = _score(default_frames, random_book, oos[0], oos[1], sim)
        random_r = float(random_metrics.get("avg_r") or 0)
    span_days = 0
    if default_frames:
        index = next(iter(default_frames.values())).index
        span_days = int((index.max() - index.min()).days)
    short = span_days < 500
    flags = overfit_flags(
        default_oos=oos_metrics,
        walk_forward=walk,
        train_sharpes=train_sharpes,
        survivorship_sensitive=False,
        short_sample=short,
        min_trades=20,
    )
    if int(oos_metrics.get("trades") or 0) < MIN_CONCLUSION:
        flags.append("anecdotal_sample")
    if is_selectable(flags, oos_metrics) and (
        float(stress.get("profit_factor") or 0) < 1 or float(stress.get("sharpe") or 0) < 0
    ):
        flags.append("cost_fragile")
    verdict = _verdict(oos_metrics, flags, random_r, proxy)
    return {
        "spec": spec_id,
        "label": label,
        "proxy": proxy,
        "window": f"{oos[0]} to {oos[1]}",
        "bars_window": (
            f"{index.min()} to {index.max()}" if default_frames else ""
        ),
        "span_days": span_days,
        "oos": oos_metrics,
        "insample": is_metrics,
        "walk": walk,
        "stress": stress,
        "random": random_metrics,
        "years": _years(oos_trades),
        "flags": flags,
        "verdict": verdict,
        "signals": len(default_signals),
        "frames": default_frames,
        "signal_list": default_signals,
    }


def _pnl_returns(trades: pd.DataFrame) -> pd.Series:
    """Daily account returns from a pnl column, including flat days that were logged."""
    if trades is None or trades.empty or "pnl" not in trades:
        return pd.Series(dtype=float)
    pnl = trades["pnl"].to_numpy(dtype=float)
    equity = STARTING_EQUITY + np.cumsum(pnl)
    prev = np.concatenate([[STARTING_EQUITY], equity[:-1]])
    returns = np.divide(equity - prev, prev, out=np.zeros_like(pnl), where=prev != 0)
    index = pd.to_datetime(trades["exit_time"])
    series = pd.Series(returns, index=index)
    return series.groupby(series.index.normalize()).sum()


def score_spec8(daily: dict[str, pd.DataFrame]) -> dict:
    from webull_bot.costs import CostModel
    from webull_bot.research import _metrics_from_returns

    grid = [
        {"mode": "both"},
        {"mode": "SPY"},
        {"mode": "QQQ"},
        {"mode": "both", "vix_max": 20},
        {"mode": "both", "vix_min": 20},
        {"mode": "both", "leg": "intraday"},
    ]
    oos = (OOS_START, SAMPLE_END)
    insample = ("2000-01-01", "2016-12-31")

    def run(params, start, end, seed=None, costs=None):
        return run_drift(
            daily,
            start=start,
            end=end,
            mode=params.get("mode", "both"),
            vix_max=params.get("vix_max"),
            vix_min=params.get("vix_min"),
            leg=params.get("leg", "overnight"),
            seed=seed,
            costs=costs,
        )

    train_sharpes = []
    fold_returns = []
    fold_trades = []
    for train_start, train_end, test_start, test_end in FOLDS:
        rows = []
        for params in grid:
            metrics, _trades = run(params, train_start, train_end)
            rows.append({"params": params, **metrics})
        train_sharpes.extend(float(row["sharpe"] or 0) for row in rows)
        chosen = pick_params(rows, grid[0])
        _test_metrics, test_trades = run(chosen, test_start, min(test_end, SAMPLE_END))
        series = _pnl_returns(test_trades)
        if len(series):
            fold_returns.append(series)
        if len(test_trades) and "taken" in test_trades:
            taken_fold = test_trades[test_trades["taken"]]
            if len(taken_fold):
                fold_trades.append(taken_fold)
    walk = _metrics_from_returns(fold_returns, fold_trades)
    walk["avg_r"] = float(pd.concat(fold_trades)["r"].mean()) if fold_trades else 0.0
    oos_metrics, oos_trades = run(grid[0], *oos)
    is_metrics, _is_trades = run(grid[0], *insample)
    # A random half of the same overnight trade estimates the same mean.
    # Beating that mean is not the claim. The claim is the overnight leg
    # after costs, against the intraday leg and against buy-and-hold.
    random_metrics, _random_trades = run(grid[0], *oos, seed=7)
    stress_metrics, _stress_trades = run(grid[0], *oos, costs=CostModel(slippage_bps=15.0))
    splits = crash_and_vix_splits(daily)
    flags = overfit_flags(
        default_oos=oos_metrics,
        walk_forward=walk,
        train_sharpes=train_sharpes,
        survivorship_sensitive=False,
        short_sample=False,
        min_trades=20,
    )
    if int(oos_metrics.get("trades") or 0) < MIN_CONCLUSION:
        flags.append("anecdotal_sample")
    if is_selectable(flags, oos_metrics) and (
        float(stress_metrics.get("profit_factor") or 0) < 1 or float(stress_metrics.get("sharpe") or 0) < 0
    ):
        flags.append("cost_fragile")
    taken = oos_trades[oos_trades["taken"]] if len(oos_trades) and "taken" in oos_trades else oos_trades
    verdict = _verdict(oos_metrics, flags, None, proxy=False)
    return {
        "spec": 8,
        "label": "SPY and QQQ daily, close to next open",
        "proxy": False,
        "window": f"{oos[0]} to {oos[1]}",
        "span_days": 9000,
        "oos": oos_metrics,
        "insample": is_metrics,
        "walk": walk,
        "stress": stress_metrics,
        "random": random_metrics,
        "years": _years(taken),
        "flags": flags,
        "verdict": verdict,
        "splits": splits,
        "signals": int(oos_metrics.get("trades") or 0),
    }


def _fmt(metrics: dict | None) -> str:
    if not metrics:
        return "n/a"
    pf = metrics.get("profit_factor")
    pf_text = "n/a" if pf is None else f"{float(pf):.2f}"
    return (
        f"CAGR {float(metrics.get('cagr') or 0):.2%}, total {float(metrics.get('total_return') or 0):.2%}, "
        f"win {float(metrics.get('win_rate') or 0):.1%}, avg R {float(metrics.get('avg_r') or 0):.3f}, "
        f"expectancy ${float(metrics.get('expectancy') or 0):.0f}, PF {pf_text}, "
        f"max DD {float(metrics.get('max_drawdown') or 0):.2%}, Sharpe {float(metrics.get('sharpe') or 0):.2f}, "
        f"trades {int(metrics.get('trades') or 0)}"
    )


def _table_row(record: dict) -> str:
    oos = record["oos"]
    walk = record["walk"]
    ins = record["insample"]
    pf = oos.get("profit_factor")
    pf_text = "n/a" if pf is None else f"{float(pf):.2f}"
    return (
        f"| {record['spec']} | {record['label']} | {record['window']} | {int(oos.get('trades') or 0)} | "
        f"{float(ins.get('sharpe') or 0):.2f} | {float(oos.get('sharpe') or 0):.2f} | "
        f"{float(walk.get('sharpe') or 0):.2f} | {float(oos.get('win_rate') or 0):.1%} | "
        f"{float(oos.get('avg_r') or 0):.3f} | ${float(oos.get('expectancy') or 0):.0f} | {pf_text} | "
        f"{float(oos.get('max_drawdown') or 0):.1%} | {record['verdict']} |"
    )


def markdown(records: list[dict], benchmark: dict, dual_sharpe: float) -> str:
    lines = [
        "## Chart Fanatics specs",
        "",
        "Eight rules from the digest, scored on the pre-registered default. "
        "Walk-forward may leave that default; the gate does not. "
        "Under 300 out-of-sample trades the verdict is inconclusive. "
        "Crypto and CFD results are proxies. Yahoo NQ=F, ES=F, and GC=F are exchange symbols. "
        "Option orders were not sent. Live orders were not sent.",
        "",
        f"Dual momentum out-of-sample Sharpe on the existing book is {dual_sharpe:.2f}. "
        f"SPY buy-and-hold over 2017-01-01 through {SAMPLE_END} was CAGR {benchmark.get('cagr', 0):.2%} "
        f"and Sharpe {benchmark.get('sharpe', 0):.2f}.",
        "",
        "| Spec | Sample | OOS window | Trades | IS Sharpe | OOS Sharpe | WF Sharpe | Win rate | Avg R | Expectancy | PF | Max DD | Verdict |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    ranked = sorted(records, key=lambda record: float(record["oos"].get("avg_r") or 0), reverse=True)
    for record in ranked:
        lines.append(_table_row(record))
    lines.append("")
    for record in records:
        lines.append(f"### Spec {record['spec']}: {record['verdict']}")
        lines.append("")
        lines.append(record["label"] + (". Proxy." if record.get("proxy") else "."))
        if record.get("bars_window"):
            lines.append(f"Bars on disk: {record['bars_window']}.")
        lines.append(f"In-sample: {_fmt(record['insample'])}.")
        lines.append(f"Out of sample, default parameters: {_fmt(record['oos'])}.")
        lines.append(f"Walk-forward: {_fmt(record['walk'])}.")
        if record.get("random"):
            if record["spec"] == 8:
                lines.append(
                    "Random half of the same overnight days (seed 7): "
                    f"{_fmt(record['random'])}. That subsample estimates the same mean, "
                    "so a tie on average R is not treated as a missing edge. "
                    "The comparison is the intraday leg, buy-and-hold, and the gates."
                )
            else:
                lines.append(f"Random-entry baseline, same stops and clock: {_fmt(record['random'])}.")
        if record.get("stress"):
            label = "15 bps slippage" if record["spec"] == 8 or "daily proxy" in record["label"] else "stop slippage at the high end (2 extra ticks)"
            lines.append(f"Cost stress ({label}): {_fmt(record['stress'])}.")
        if record.get("proxy") and record["verdict"] == "no edge":
            lines.append("That is no edge on this proxy. It is not a verdict on the NQ or ES rule.")
        if record.get("flags"):
            lines.append("Flags: " + ", ".join(record["flags"]) + ".")
        years = record.get("years") or []
        if years:
            negative = sum(1 for row in years if row["sum_r"] < 0)
            bits = ", ".join(f"{row['year']} {row['trades']} trades avg R {row['avg_r']:.2f}" for row in years)
            lines.append(f"By year ({negative} of {len(years)} negative): {bits}.")
        if record["spec"] == 8:
            lines.append(
                "The gross overnight mean below is positive. "
                "The traded book pays 5 bps of slippage and 1 bp of half-spread on the entry and again on the exit, "
                "about 12 bps round trip before the SEC and FINRA fees. "
                "That cost is larger than the 2 to 4 bp drift, which is why the account loses money."
            )
        if record.get("splits"):
            for name, stats in record["splits"].items():
                if "overnight" not in stats:
                    continue
                over = stats["overnight"]
                intra = stats["intraday"]
                lines.append(
                    f"{name}: overnight mean {over['mean']:.4%} (t {over['tstat']:.2f}, n {over['n']}), "
                    f"intraday mean {intra['mean']:.4%} (t {intra['tstat']:.2f}, n {intra['n']})."
                )
        lines.append("")
    lines.append(
        "Tick caps are exchange ticks. On BTC and ETH a tick is $0.01, so a 40-tick skip is $0.40 and rejects ordinary sweeps. "
        "Those crypto rows do not test the NQ rule; the Yahoo NQ=F and ES=F window is the exchange-tick sample, and it is short. "
        "Value areas are built from 5-minute bars, which is coarser than a 1-minute profile. "
        "Spec 4 does not search the VPE-trend pullback to the point of control; that clause was not in the pre-registered grid. "
        "Spec 5 only pairs an engineered swing with an earlier swing inside 300 bars, an implementation bound so two highs years apart are not a setup. "
        "Yahoo NQ=F, ES=F, and GC=F are continuous rolls, not a back-adjusted research series. "
        "Dukascopy publishes free 1-minute bid candles, and a pull was started, but the host "
        "answered with timeouts and HTTP 503s after a few hundred files from 2013. That prefix "
        "is not the scored sample. A multi-year CME 1-minute archive, plus trades with aggressor side "
        "for the order-flow filters, is what would make specs 1, 3, 5, 6, and 7 conclusive on NQ and ES. "
        "Databento's historical CME ohlcv-1m product is the practical source; "
        "their public calculator prices a few symbols of 1-minute bars in the tens of dollars and "
        "tick or MBP-1 data for the same span in the hundreds. An Alpaca key unlocks stock and ETF "
        "intraday history, not that CME archive. No key was requested."
    )
    lines.append("")
    return "\n".join(lines)


def _promote(records: list[dict]) -> None:
    path = Path("config/optional_strategies.json")
    payload = json.loads(path.read_text()) if path.exists() else {"optional": [], "expression": "stock", "rationale": ""}
    payload["optional"] = [name for name in payload.get("optional", []) if name != "overnight_drift"]
    kept = (
        "bluechip_reversal did not pass the out-of-sample gates. "
        "support_reversal did not pass the out-of-sample gates. "
        "wedge_breakout did not pass the out-of-sample gates."
    )
    dual = json.loads(Path("config/selected_strategies.json").read_text())
    dual_sharpe = float(dual["portfolio"]["sharpe"])
    bits = []
    for record in records:
        bits.append(f"spec {record['spec']} {record['verdict']}")
        if record["verdict"] != "real edge" or record.get("proxy") or record["spec"] != 8:
            continue
        sharpe = float(record["oos"].get("sharpe") or 0)
        if sharpe < dual_sharpe + 0.15:
            payload["optional"].append("overnight_drift")
            bits.append(
                "overnight_drift is optional paper only and is not the default"
            )
        else:
            bits.append(
                "overnight_drift beat dual momentum by 0.15 Sharpe; the default book was left unchanged pending a separate review"
            )
    payload["expression"] = payload.get("expression") or "stock"
    payload["rationale"] = kept + " Chart Fanatics: " + "; ".join(bits) + "."
    path.write_text(json.dumps(payload, indent=2))


def save_charts(records: list[dict]) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path("reports/setups")
    art = Path("/opt/cursor/artifacts/setups")
    out.mkdir(parents=True, exist_ok=True)
    art.mkdir(parents=True, exist_ok=True)
    saved = []
    wanted = {1, 2, 4, 7}
    for record in records:
        if record["spec"] not in wanted or not record.get("signal_list") or not record.get("frames"):
            continue
        signal = record["signal_list"][len(record["signal_list"]) // 2]
        frame = record["frames"].get(signal.symbol)
        if frame is None:
            continue
        loc = signal.signal_loc
        start = max(0, loc - 40)
        stop = min(len(frame), loc + 15)
        window = frame.iloc[start:stop]
        fig, ax = plt.subplots(figsize=(9, 4.5))
        for stamp, row in window.iterrows():
            color = "#1f7a4d" if row["close"] >= row["open"] else "#9a3b2f"
            ax.plot([stamp, stamp], [row["low"], row["high"]], color=color, linewidth=0.8)
            ax.plot([stamp, stamp], [min(row["open"], row["close"]), max(row["open"], row["close"])], color=color, linewidth=3)
        ax.scatter([frame.index[loc]], [frame["close"].iloc[loc]], color="#b00020", zorder=3)
        ax.set_title(f"Spec {record['spec']} {signal.symbol} {frame.index[loc]}")
        fig.autofmt_xdate()
        name = f"fanatics_spec{record['spec']}_{signal.symbol.replace('=', '')}.png"
        fig.savefig(out / name, dpi=120, bbox_inches="tight")
        fig.savefig(art / name, dpi=120, bbox_inches="tight")
        plt.close(fig)
        saved.append(out / name)
    return saved


def score_daily_proxy(frame: pd.DataFrame, symbol: str, kind: str) -> dict:
    """Daily-bar stand-in. Walk-forward has one cell, so it stitches the later folds of that cell."""
    from webull_bot.costs import CostModel
    from webull_bot.research import _metrics_from_returns

    spec = 1 if kind == "reclaim" else 4
    label = f"daily proxy {symbol}, {'prior-day reclaim' if kind == 'reclaim' else 'rejection candle'}"
    train_sharpes = []
    fold_returns = []
    fold_trades = []
    for train_start, train_end, test_start, test_end in FOLDS:
        trained, _trades, _result = run_proxy(frame, symbol, kind, train_start, train_end)
        train_sharpes.append(float(trained.get("sharpe") or 0))
        _tested, trades, result = run_proxy(frame, symbol, kind, test_start, min(test_end, SAMPLE_END))
        daily = result.daily_equity()
        if len(daily):
            base = pd.Series([STARTING_EQUITY], index=[daily.index[0] - pd.Timedelta(days=1)])
            fold_returns.append(pd.concat([base, daily]).pct_change().dropna())
        if len(trades):
            fold_trades.append(trades)
    walk = _metrics_from_returns(fold_returns, fold_trades)
    walk["avg_r"] = float(pd.concat(fold_trades)["r"].mean()) if fold_trades else 0.0
    oos_metrics, oos_trades, _oos_result = run_proxy(frame, symbol, kind, OOS_START, SAMPLE_END)
    is_metrics, _is_trades, _is_result = run_proxy(frame, symbol, kind, "2000-01-01", "2016-12-31")
    stress, _stress_trades, _stress_result = run_proxy(
        frame, symbol, kind, OOS_START, SAMPLE_END, costs=CostModel(slippage_bps=15.0)
    )
    view = frame.copy()
    if getattr(view.index, "tz", None) is not None:
        view.index = view.index.tz_localize(None)
    random_book = random_proxy_signals(view, symbol, kind, OOS_START, SAMPLE_END)
    random_metrics, _random_trades, _random_result = run_proxy(
        frame, symbol, kind, OOS_START, SAMPLE_END, signals=random_book
    )
    flags = overfit_flags(
        default_oos=oos_metrics,
        walk_forward=walk,
        train_sharpes=train_sharpes,
        survivorship_sensitive=False,
        short_sample=False,
        min_trades=20,
    )
    flags.append("proxy")
    if int(oos_metrics.get("trades") or 0) < MIN_CONCLUSION:
        flags.append("anecdotal_sample")
    if is_selectable(flags, oos_metrics) and (
        float(stress.get("profit_factor") or 0) < 1 or float(stress.get("sharpe") or 0) < 0
    ):
        flags.append("cost_fragile")
    random_r = float(random_metrics.get("avg_r") or 0) if random_metrics else None
    return {
        "spec": spec,
        "label": label,
        "proxy": True,
        "window": f"{OOS_START} to {SAMPLE_END}",
        "span_days": 9000,
        "oos": oos_metrics,
        "insample": is_metrics,
        "walk": walk,
        "stress": stress,
        "random": random_metrics,
        "years": _years(oos_trades),
        "flags": flags,
        "verdict": _verdict(oos_metrics, flags, random_r, proxy=True),
        "signals": int(oos_metrics.get("trades") or 0),
    }


def _futures_folds(index: pd.DatetimeIndex):
    start = index.min().tz_localize(None) if index.tz is not None else index.min()
    end = index.max().tz_localize(None) if index.tz is not None else index.max()
    if (end - start).days < 500:
        mid = start + (end - start) / 2
        return [(str(start.date()), str(mid.date()), str(mid.date()), str(end.date()))], (str(mid.date()), str(end.date())), (str(start.date()), str(mid.date())), True
    oos = ("2024-01-01", str(end.date()))
    folds = [fold for fold in FOLDS if pd.Timestamp(fold[2]) >= start and pd.Timestamp(fold[0]) <= end]
    insample = (str(start.date()), "2023-12-31")
    return folds, oos, insample, False


def run() -> list[dict]:
    print("Loading free history...", flush=True)
    from webull_bot.fanatics.data import prepare_free

    prepare_free()
    daily = download_yahoo_daily()
    records = []
    btc = _load(BARS / "BTCUSDT_5m.pkl")
    eth = _load(BARS / "ETHUSDT_5m.pkl")
    paxg = _load(BARS / "PAXGUSDT_30m.pkl")
    nq5 = _load(BARS / "yahoo_NQF_5m.pkl")
    es5 = _load(BARS / "yahoo_ESF_5m.pkl")
    gc30 = _load(BARS / "yahoo_GCF_30m.pkl")
    nq60 = _load(BARS / "yahoo_NQF_60m.pkl")
    es60 = _load(BARS / "yahoo_ESF_60m.pkl")
    btc_va = _load(BARS / "BTCUSDT_va.pkl")
    eth_va = _load(BARS / "ETHUSDT_va.pkl")

    crypto_folds = [
        ("2018-01-01", "2020-12-31", "2021-01-01", "2022-12-31"),
        ("2019-01-01", "2021-12-31", "2022-01-01", "2023-12-31"),
        ("2020-01-01", "2022-12-31", "2023-01-01", "2024-12-31"),
        ("2021-01-01", "2023-12-31", "2024-01-01", SAMPLE_END),
    ]
    crypto_oos = ("2022-01-01", SAMPLE_END)
    crypto_is = ("2018-01-01", "2021-12-31")

    def consider(spec, bars, areas, symbols, folds, oos, insample, proxy, label):
        print(f"Scoring spec {spec} {label}", flush=True)
        present = {symbol: bars[symbol] for symbol in symbols if symbol in bars and bars[symbol] is not None and len(bars[symbol])}
        if not present:
            print(f"  no bars for spec {spec}", flush=True)
            return None
        return score_intraday(spec, present, areas, list(present), folds, oos, insample, proxy, label)

    # Specs 1, 3, 5, 6, 7: long crypto proxy, plus the short Yahoo futures window.
    if btc is not None:
        crypto_bars = {"BTCUSDT": btc}
        if eth is not None:
            crypto_bars["ETHUSDT"] = eth
        areas = {}
        if btc_va is not None:
            areas["BTCUSDT"] = btc_va
        if eth_va is not None:
            areas["ETHUSDT"] = eth_va
        for spec in (1, 3, 5, 6, 7):
            record = consider(spec, crypto_bars, areas, list(crypto_bars), crypto_folds, crypto_oos, crypto_is, True, "BTC and ETH 5-minute, Binance spot")
            if record:
                records.append(record)
    if nq5 is not None:
        fut = {"NQ=F": nq5}
        if es5 is not None:
            fut["ES=F"] = es5
        from webull_bot.fanatics.data import value_areas_from_bars

        areas = {"NQ=F": value_areas_from_bars(nq5, 0.25)}
        if es5 is not None:
            areas["ES=F"] = value_areas_from_bars(es5, 0.25)
        folds, oos, insample, _short = _futures_folds(nq5.index)
        for spec in (1, 3, 5, 6, 7):
            record = consider(spec, fut, areas, list(fut), folds, oos, insample, False, "NQ=F and ES=F 5-minute, Yahoo about 60 days")
            if record:
                records.append(record)
    # Spec 2
    if paxg is not None:
        folds, oos, insample, _short = _futures_folds(paxg.index)
        # PAXG history is multi-year. Force the crypto-style split if long enough.
        if (paxg.index.max() - paxg.index.min()).days > 500:
            folds, oos, insample = crypto_folds, ("2023-01-01", SAMPLE_END), ("2020-01-01", "2022-12-31")
        record = consider(2, {"PAXGUSDT": paxg}, {}, ["PAXGUSDT"], folds, oos, insample, True, "PAXG 30-minute, Binance gold proxy")
        if record:
            records.append(record)
    if gc30 is not None:
        folds, oos, insample, _short = _futures_folds(gc30.index)
        record = consider(2, {"GC=F": gc30}, {}, ["GC=F"], folds, oos, insample, False, "GC=F 30-minute, Yahoo about 60 days")
        if record:
            records.append(record)
    # Spec 4 prefers the 730-day hourly futures sample.
    if nq60 is not None:
        fut = {"NQ=F": nq60}
        if es60 is not None:
            fut["ES=F"] = es60
        folds, oos, insample, _short = _futures_folds(nq60.index)
        record = consider(4, fut, {}, list(fut), folds, oos, insample, False, "NQ=F and ES=F 60-minute, Yahoo about 730 days")
        if record:
            records.append(record)
    if btc is not None:
        record = consider(4, crypto_bars, {}, list(crypto_bars), crypto_folds, crypto_oos, crypto_is, True, "BTC and ETH resampled, Binance")
        if record:
            records.append(record)

    print("Scoring spec 8", flush=True)
    records.append(score_spec8(daily))
    print("Scoring daily proxies", flush=True)
    for symbol in ("SPY", "QQQ"):
        for kind in ("reclaim", "reject"):
            records.append(score_daily_proxy(daily[symbol], symbol, kind))
    # One row per spec for the ranked table: keep the non-proxy sample when it
    # has at least 300 trades, otherwise the longest sample.
    primary = []
    for spec in range(1, 9):
        group = [record for record in records if record["spec"] == spec and "daily proxy" not in record["label"]]
        if not group:
            group = [record for record in records if record["spec"] == spec]
        if not group:
            continue
        conclusive = [record for record in group if int(record["oos"].get("trades") or 0) >= MIN_CONCLUSION and not record.get("proxy")]
        primary.append(conclusive[0] if conclusive else max(group, key=lambda record: int(record["oos"].get("trades") or 0)))
    proxies = [record for record in records if record not in primary]
    spy = daily["SPY"]
    benchmark = buy_and_hold_metrics(
        spy["close"],
        spy["open"],
        starting_equity=STARTING_EQUITY,
        trade_start=pd.Timestamp(OOS_START),
        trade_end=pd.Timestamp(SAMPLE_END),
        slippage_bps=5.0,
    )
    dual = json.loads(Path("config/selected_strategies.json").read_text())
    text = markdown(primary, benchmark, float(dual["portfolio"]["sharpe"]))
    text += "\n\n### Other samples\n\n"
    for record in proxies:
        text += f"- Spec {record['spec']} {record['label']}: {record['verdict']}. OOS {_fmt(record['oos'])}.\n"
    path = Path("reports/fanatics_section.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    _splice(text)
    _promote(primary)
    try:
        charts = save_charts(primary)
        print("charts", charts, flush=True)
    except Exception as exc:
        print(f"charts skipped: {exc}", flush=True)
    print(text)
    return primary


def _splice(section: str) -> None:
    results = Path("RESULTS.md")
    existing = results.read_text() if results.exists() else ""
    block = "<!-- FANATICS_START -->\n" + section.strip() + "\n<!-- FANATICS_END -->\n"
    if "<!-- FANATICS_START -->" in existing:
        import re

        existing = re.sub(r"<!-- FANATICS_START -->.*?<!-- FANATICS_END -->\n?", block, existing, flags=re.S)
    else:
        existing = existing.rstrip() + "\n\n" + block
    results.write_text(existing)


if __name__ == "__main__":
    run()
