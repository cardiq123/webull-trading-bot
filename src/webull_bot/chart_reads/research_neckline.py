"""Score the frozen neckline books once. Backtests only.

Writes the rules file before any metric. Does not place an order and does
not add a strategy to the live list.
"""

from __future__ import annotations

import json
import math
from datetime import date, time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from webull_bot.chart_reads.atm_exit import deflated_sharpe
from webull_bot.chart_reads.neckline import (
    HOLDOUT_END,
    HOLDOUT_START,
    MIN_SEP_BARS,
    RANDOM_SEED,
    STAKE,
    TRAIN_END,
    TRAIN_START,
    benjamini_hochberg,
    catalog,
    daily_returns,
    frozen_rules,
    inspect_long,
    n_trials,
    p_value,
    passes_gate,
    prepare,
    public_metrics,
    random_events,
    random_exit,
    select_events,
    simulate,
)
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.data.yfinance_provider import YFinanceProvider

RULES_PATH = Path("reports/neckline_rules.json")
JSON_PATH = Path("reports/neckline.json")
MD_PATH = Path("reports/neckline.md")
EQUITY_PATH = Path("reports/neckline_equity.png")
README_PATH = Path("README.md")
RESULTS_PATH = Path("RESULTS.md")
START_MARK = "<!-- NECKLINE_START -->"
END_MARK = "<!-- NECKLINE_END -->"
NY = "America/New_York"
COMPARE_EXITS = ("r1", "measured", "vwap2", "neckline", "r2")


def _load_bars(symbol: str) -> tuple[pd.DataFrame, str]:
    candidates = [
        Path(f"data/cache/open_support/{symbol}_duka_5m.pkl"),
        Path(f"/workspace/data/cache/open_support/{symbol}_duka_5m.pkl"),
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        raise FileNotFoundError(f"no 5-minute cache for {symbol}")
    frame = pd.read_pickle(path)
    frame = frame.sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    return frame, str(path)


def _load_series(name: str) -> pd.Series:
    candidates = [
        Path(f"data/cache/_{name}_1d.csv"),
        Path(f"/workspace/data/cache/_{name}_1d.csv"),
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        return pd.Series(dtype=float)
    frame = pd.read_csv(path, parse_dates=["Date"])
    series = frame.set_index("Date")["close"].astype(float)
    series.index = pd.to_datetime(series.index)
    return series[~series.index.duplicated(keep="last")].sort_index()


def _window(book, events, start: date, end: date) -> list:
    return [event for event in events if start <= book.dates[event.fill_i] <= end]


def _direction(cell) -> str:
    return "short" if cell.filter == "short" else "long"


def _keep_equity(cell) -> bool:
    if cell.family == "scalp":
        return True
    return cell.family == "confirmed" and cell.filter == "base" and cell.exit in COMPARE_EXITS


def _pack(book: dict) -> dict:
    metrics = public_metrics(book["metrics"])
    metrics["skips"] = book["skips"]
    return metrics


def _score_cell(book, cell, iv: dict) -> dict:
    events = select_events(book.events, cell)
    train_events = _window(book, events, TRAIN_START, TRAIN_END)
    hold_events = _window(book, events, HOLDOUT_START, HOLDOUT_END)
    train = simulate(
        book,
        train_events,
        exit_name=cell.exit,
        kind=cell.kind,
        stake=STAKE,
        iv_points=iv,
        start=TRAIN_START,
        end=TRAIN_END,
        allow_holdout=False,
    )
    hold = simulate(
        book,
        hold_events,
        exit_name=cell.exit,
        kind=cell.kind,
        stake=STAKE,
        iv_points=iv,
        start=HOLDOUT_START,
        end=HOLDOUT_END,
        allow_holdout=True,
    )
    exit_name = random_exit(cell.exit)
    random_train_events = random_events(
        book, len(train_events), _direction(cell), TRAIN_START, TRAIN_END, RANDOM_SEED
    )
    random_hold_events = random_events(
        book, len(hold_events), _direction(cell), HOLDOUT_START, HOLDOUT_END, RANDOM_SEED
    )
    random_train = simulate(
        book,
        random_train_events,
        exit_name=exit_name,
        kind=cell.kind,
        stake=STAKE,
        iv_points=iv,
        start=TRAIN_START,
        end=TRAIN_END,
        allow_holdout=False,
    )
    random_hold = simulate(
        book,
        random_hold_events,
        exit_name=exit_name,
        kind=cell.kind,
        stake=STAKE,
        iv_points=iv,
        start=HOLDOUT_START,
        end=HOLDOUT_END,
        allow_holdout=True,
    )
    row = {
        "id": cell.id,
        "symbol": cell.symbol,
        "family": cell.family,
        "filter": cell.filter,
        "exit": cell.exit,
        "kind": cell.kind,
        "direction": _direction(cell),
        "random_exit": exit_name,
        "signals_train": len(train_events),
        "signals_holdout": len(hold_events),
        "train": _pack(train),
        "holdout": _pack(hold),
        "random_train": _pack(random_train),
        "random_holdout": _pack(random_hold),
        "p": p_value(train["pnls"]),
        "equity_train": train["equity"] if _keep_equity(cell) else None,
        "equity_holdout": hold["equity"] if _keep_equity(cell) else None,
        "random_equity_train": random_train["equity"] if cell.filter == "base" and cell.exit == "r1" else None,
        "random_equity_holdout": random_hold["equity"] if cell.filter == "base" and cell.exit == "r1" else None,
        "dsr_input": daily_returns(train["equity"], STAKE),
    }
    return row


_SKIP_KEYS = {
    "equity_train",
    "equity_holdout",
    "random_equity_train",
    "random_equity_holdout",
    "dsr_input",
}


def _jsonable(value):
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items() if key not in _SKIP_KEYS}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (pd.Timestamp, date)):
        return str(value)
    return value


def _money(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"${float(value):,.0f}"


def _pct(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _num(value, digits=2) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def _metric_line(label: str, metrics: dict) -> str:
    return (
        f"{label}: trades {int(metrics.get('trades') or 0)}, "
        f"win {_pct(metrics.get('win_rate'))}, "
        f"planned R:R {_num(metrics.get('planned_rr'))}, "
        f"profit factor {_num(metrics.get('profit_factor'))}, "
        f"Sharpe {_num(metrics.get('sharpe'))}, "
        f"max drawdown {_pct(metrics.get('max_drawdown'))}, "
        f"ending {_money(metrics.get('ending_equity'))}"
    )


def _compare_rows(rows: list[dict]) -> list[dict]:
    wanted = []
    for row in rows:
        if row["family"] == "scalp" or (row["family"] == "confirmed" and row["filter"] == "base"):
            wanted.append(row)
    return wanted


def _table(rows: list[dict]) -> str:
    header = (
        "| Book | Window | Trades | Win | R:R | PF | Sharpe | Max DD | Ending | Random ending |\n"
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    )
    lines = [header]
    for row in rows:
        for window, random_key in (("train", "random_train"), ("holdout", "random_holdout")):
            metrics = row[window]
            baseline = row[random_key]
            name = f"{row['symbol']} {row['family']} {row['filter']} {row['exit']} {row['kind']}"
            lines.append(
                "| "
                + " | ".join(
                    [
                        name,
                        window,
                        str(int(metrics.get("trades") or 0)),
                        _pct(metrics.get("win_rate")),
                        _num(metrics.get("planned_rr")),
                        _num(metrics.get("profit_factor")),
                        _num(metrics.get("sharpe")),
                        _pct(metrics.get("max_drawdown")),
                        _money(metrics.get("ending_equity")),
                        _money(baseline.get("ending_equity")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines)


def _full_table(rows: list[dict]) -> str:
    header = (
        "| Cell | Train trades | Train PF | Train ending | Holdout trades | Holdout win | "
        "Holdout R:R | Holdout PF | Holdout Sharpe | Holdout DD | Holdout ending | "
        "Random holdout ending | q | DSR | Pass |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
    )
    lines = [header]
    for row in rows:
        train = row["train"]
        hold = row["holdout"]
        lines.append(
            "| "
            + " | ".join(
                [
                    row["id"],
                    str(int(train.get("trades") or 0)),
                    _num(train.get("profit_factor")),
                    _money(train.get("ending_equity")),
                    str(int(hold.get("trades") or 0)),
                    _pct(hold.get("win_rate")),
                    _num(hold.get("planned_rr")),
                    _num(hold.get("profit_factor")),
                    _num(hold.get("sharpe")),
                    _pct(hold.get("max_drawdown")),
                    _money(hold.get("ending_equity")),
                    _money(row["random_holdout"].get("ending_equity")),
                    _num(row.get("q"), 3),
                    _num(row.get("dsr"), 3),
                    "yes" if row.get("passes") else "no",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _chart(rows: list[dict]) -> None:
    panels = (
        ("SPY", "0dte", "Train"),
        ("SPY", "0dte", "Holdout"),
        ("QQQ", "0dte", "Train"),
        ("QQQ", "0dte", "Holdout"),
        ("SPY", "shares", "Train"),
        ("SPY", "shares", "Holdout"),
        ("QQQ", "shares", "Train"),
        ("QQQ", "shares", "Holdout"),
    )
    styles = {
        "r1": ("#222222", "Confirmed 1R"),
        "measured": ("#1f77b4", "Confirmed measured move"),
        "vwap2": ("#2ca02c", "Confirmed VWAP 2SD"),
        "neckline": ("#ff7f0e", "Scalp to neckline"),
        "r2": ("#d62728", "Scalp 2R"),
    }
    figure, axes = plt.subplots(4, 2, figsize=(12.5, 14), sharex=False)
    for axis, (symbol, kind, window) in zip(axes.ravel(), panels):
        key = "equity_train" if window == "Train" else "equity_holdout"
        for row in rows:
            if row["symbol"] != symbol or row["kind"] != kind or row["exit"] not in styles:
                continue
            if row["family"] == "confirmed" and row["filter"] != "base":
                continue
            curve = row.get(key)
            if curve is None or len(curve) == 0:
                continue
            color, label = styles[row["exit"]]
            axis.plot(curve.index, curve.to_numpy(), color=color, linewidth=1.2, label=label)
        for row in rows:
            if row["symbol"] == symbol and row["kind"] == kind and row["filter"] == "base" and row["exit"] == "r1":
                curve = row.get("random_equity_train" if window == "Train" else "random_equity_holdout")
                if curve is not None and len(curve):
                    axis.plot(curve.index, curve.to_numpy(), color="#888888", linestyle="--", linewidth=1.0, label="Random 1R")
        axis.axhline(STAKE, color="#bbbbbb", linewidth=0.8)
        axis.set_title(f"{symbol} {kind} {window.lower()}")
        axis.set_ylabel("Equity")
        axis.tick_params(axis="x", labelrotation=30, labelsize=8)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    if handles:
        figure.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    figure.suptitle("Neckline study, fresh $2,500. Dashed line is the seed-17 random 1R book.", y=0.995)
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    EQUITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(EQUITY_PATH, dpi=120)
    plt.close(figure)


def _tape_note(symbol: str, frame: pd.DataFrame, path: str) -> str:
    index = frame.index
    if getattr(index, "tz", None) is not None:
        index = index.tz_convert(NY)
    days = pd.Index(index.date).unique()
    return (
        f"{symbol} is Dukascopy 5-minute bids from {index[0].date().isoformat()} through "
        f"{index[-1].date().isoformat()}, {len(days)} sessions, {len(frame)} bars, file `{path}`. "
        "Volume is a bid-tick count. Prices are bids and omit dividends."
    )


def _anecdote() -> str:
    """How 2026-10-08 would have been flagged. This day is not in the scored sample."""
    try:
        provider = YFinanceProvider(cache_dir="data/cache/neckline_yahoo")
        frames = provider.history(["SPY"], "2026-08-01", "2026-10-09", interval="5m")
        frame = frames.get("SPY")
    except Exception as exc:
        return f"The 2026-10-08 afternoon tape was not loaded ({type(exc).__name__}). It was not used to change the rule."
    if frame is None or frame.empty:
        return "The 2026-10-08 afternoon tape was not in the file. It was not used to change the rule."
    book = prepare(frame, "SPY")
    day = date(2026, 10, 8)
    day_idx = [i for i, stamp in enumerate(book.dates) if stamp == day]
    if not day_idx:
        last = book.index[-1]
        return (
            f"Yahoo 5-minute SPY in this file ends at {last}. "
            "There is no 2026-10-08 session, so the 14:15-14:25 read was not made. "
            "That day is not in the Dukascopy score, and the rule was not changed."
        )
    cutoff = time(14, 20)
    usable = [i for i in day_idx if book.index[i].time() <= cutoff]
    if not usable:
        return (
            "Yahoo has 2026-10-08 bars, and none of them start at or before 14:20 ET. "
            "The rule was not changed."
        )
    last_i = usable[-1]
    when = book.index[last_i]
    state = inspect_long(book, when)
    events = [
        event
        for event in book.events
        if book.dates[event.signal_i] == day and event.signal_i <= last_i
    ]
    later = [
        event
        for event in book.events
        if book.dates[event.signal_i] == day and event.signal_i == last_i + 1
    ]
    bits = [
        "The illustration is Yahoo 5-minute SPY, not the thinkorswim print. "
        f"The last bar that has closed by 14:25 ET starts at {when.strftime('%H:%M')} "
        f"and closes five minutes later. Close {state['close']:.2f}, "
        f"9 EMA {state['ema9']:.2f}, 20 EMA {state['ema20']:.2f}, "
        f"200 EMA {state['ema200']:.2f}, VWAP {state['vwap']:.2f}, "
        f"MACD histogram {state['hist']:.3f}."
    ]
    if events:
        for event in events:
            bits.append(
                f"On or before that bar the detector marks a {event.family} {event.direction} at "
                f"{book.index[event.signal_i].strftime('%H:%M')}, fill "
                f"{book.index[event.fill_i].strftime('%H:%M')}, neckline {event.neckline:.2f}, "
                f"second swing {event.second:.2f}, stop {event.stop:.2f}."
            )
    else:
        bits.append("No scalp and no confirmed entry is marked on or before that bar.")
    active = state.get("active")
    lows = state.get("swing_lows") or []
    recent = lows[-4:]
    if recent:
        text = ", ".join(f"{item['time'].strftime('%H:%M')} at {item['low']:.2f}" for item in recent)
        bits.append(f"Session swing lows into that bar include {text}.")
        if len(recent) >= 2:
            gap_bars = int((recent[-1]["time"] - recent[-2]["time"]).total_seconds() // 300)
            if gap_bars < MIN_SEP_BARS:
                bits.append(
                    f"The {recent[-2]['time'].strftime('%H:%M')} low is {gap_bars} bars before the "
                    f"{recent[-1]['time'].strftime('%H:%M')} low, short of the {MIN_SEP_BARS}-bar minimum, "
                    "so those two are not the pair."
                )
    if active:
        bits.append(
            f"The active long cluster has a mechanical neckline at {active['neckline']:.2f} "
            f"against the drawn line near 773.1. The second low is {active['second']:.2f} "
            f"and the cluster extreme is {active['extreme']:.2f}. "
            f"The 9 EMA has been reclaimed: {str(active['reclaimed']).lower()}. "
            f"A close has already gone through the neckline: {str(active['neckline_closed']).lower()}. "
            f"The scalp has already been taken: {str(active['scalp_done']).lower()}."
        )
    else:
        bits.append("No long double-bottom cluster is still active at that close.")
    if later:
        event = later[0]
        bits.append(
            f"The next bar, which opens at {book.index[event.signal_i].strftime('%H:%M')} and closes "
            f"five minutes after the requested window, is a {event.family} {event.direction} signal. "
            f"Its fill would be {book.index[event.fill_i].strftime('%H:%M')}, stop {event.stop:.2f}, "
            f"neckline {event.neckline:.2f}. That bar was not required to call the 14:15-14:25 read."
        )
    bits.append("2026-10-08 is not in the scored sample. The tolerances were not changed after this reading.")
    return " ".join(bits)


def _cell(rows: list[dict], cell_id: str) -> dict:
    return next(row for row in rows if row["id"] == cell_id)


def _sentence(row: dict, window: str) -> str:
    metrics = row[window]
    baseline = row["random_train" if window == "train" else "random_holdout"]
    return (
        f"{row['symbol']} {row['kind']} {row['family']} {row['exit']} {window}: "
        f"{int(metrics.get('trades') or 0)} trades, win {_pct(metrics.get('win_rate'))}, "
        f"planned R:R {_num(metrics.get('planned_rr'))}, profit factor {_num(metrics.get('profit_factor'))}, "
        f"Sharpe {_num(metrics.get('sharpe'))}, max drawdown {_pct(metrics.get('max_drawdown'))}, "
        f"ending {_money(metrics.get('ending_equity'))} from $2,500, "
        f"random ending {_money(baseline.get('ending_equity'))}"
    )


def _prose(rows: list[dict], tapes: list[str], anecdote: str) -> str:
    passed = [row for row in rows if row.get("passes")]
    if passed:
        verdict = (
            "One pre-registered cell cleared every line of the gate: "
            + ", ".join(row["id"] for row in passed)
            + ". It is the QQQ short mirror, one at-the-money 0 DTE put, with the 1R exit. "
            "It is not the scalp and it is not the long neckline close. "
            "It was not added to the live list and no sandbox book was created. "
            "The option price is Black-Scholes, not a listed chain."
        )
    else:
        verdict = "No cell cleared the frozen gate. Nothing was added to the live list."
    spotlight = [
        "SPY_scalp_scalp_neckline_0dte",
        "SPY_scalp_scalp_r2_0dte",
        "SPY_confirmed_base_r1_0dte",
        "SPY_confirmed_base_measured_0dte",
        "SPY_confirmed_base_vwap2_0dte",
        "SPY_scalp_scalp_neckline_shares",
        "SPY_scalp_scalp_r2_shares",
        "SPY_confirmed_base_r1_shares",
        "QQQ_scalp_scalp_neckline_0dte",
        "QQQ_scalp_scalp_r2_0dte",
        "QQQ_confirmed_base_r1_0dte",
        "QQQ_confirmed_base_measured_0dte",
        "QQQ_confirmed_base_vwap2_0dte",
        "QQQ_scalp_scalp_neckline_shares",
        "QQQ_scalp_scalp_r2_shares",
        "QQQ_confirmed_base_r1_shares",
    ]
    comparison = []
    for cell_id in spotlight:
        row = _cell(rows, cell_id)
        comparison.append(_sentence(row, "train") + ". " + _sentence(row, "holdout") + ".")
    lines = [
        "# Neckline break",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. "
        "The sandbox forward books were not changed. The rules in `reports/neckline_rules.json` "
        "were written before any metric. Paul's 2026-10-08 chart is an illustration, not a trial.",
        "",
        "The quick scalp does not clear the gate on SPY or QQQ, in shares or in 0 DTE. "
        "Its planned reward-to-risk is wider than the confirmed 1R entry when the target is the neckline, "
        "and it is 2.0 when that is the target, but the win rate is lower and the $2,500 account finishes "
        "below the start on every scalp cell. The confirmed-close books are the comparison, not a stack "
        "with the scalp. A holdout account that finishes above $2,500 still fails when the training account "
        "dies, the drawdown is past -30%, or the q-value and deflated Sharpe miss the line.",
        "",
        verdict,
        "",
        "Training account first, then the fresh holdout, for the scalp and the confirmed base entry:",
        "",
        *comparison,
        "",
        "The confirmed entry buys the next open after a 5-minute close strictly above the neckline, "
        "the 9 EMA, and the 20 EMA. The quick scalp is a separate long-only book inside the same "
        "double bottom, before any close above the neckline: a down-close bar after an earlier bar "
        "has reclaimed the 9 EMA, with that red bar holding above the second low and above the lower "
        "of the 9 and 20 EMA. The scalp stop is one cent under the red bar. Its targets, scored separately, "
        "are the neckline and 2R. The confirmed stop is one cent under the second swing low. "
        "Confirmed targets, scored separately, are 1R, the measured move, and the prior bar's outer "
        "session-VWAP band. Both books are flat at the 15:45 open. They are not stacked into one "
        "'scalp, then add on the close' strategy.",
        "",
        "A swing is a strict 2-bar fractal in the same session, known two bars later. The first swing "
        "has to be at least 0.5 ATR(14) beyond the prior 12 bars. The two swings are 6 to 30 bars apart "
        "and within the larger of 0.15% and 0.5 ATR. The neckline is the highest high strictly between "
        "the swing lows, or the lowest low between swing highs on the short mirror. A close through the "
        "cluster extreme kills it. One cluster is active at a time. EMAs and the MACD histogram use the "
        "continuous regular-hours series. Session VWAP resets at 9:30.",
        "",
        "Each cell starts a fresh $2,500 cash account. Train is 2017-02-16 through 2023-12-31. "
        "Holdout is 2024-01-01 through 2026-10-06. One position, at most three new trades a day. "
        "Shares risk 1% of start-of-day equity to the stop, in whole shares. Options are one "
        "at-the-money 0 DTE contract, Black-Scholes, prior VIX1D close or else the prior VIX close, "
        "rate 2%, dividend 0, half-spread the greater of one cent and 1.5% of the mid. A missing print "
        "skips the option trade. There is no quote fallback in this research. The false-discovery family "
        "is all 68 cells, including the eight scalp cells. The random baseline draws the same number of "
        "bars with seed 17 and the same direction. Its stop is one cent beyond that bar. A 1R, 2R, or "
        "VWAP-band exit is used as-is. A neckline or measured-move exit falls back to 1R, because a "
        "random bar has no neckline. The same cash rules then decide which of those bars fill.",
        "",
        "The gate, all of it, is holdout trades at least 300, profit factor at least 1.10, Sharpe at least "
        "0.40, max drawdown no worse than -30%, ending above $2,500, training Sharpe above that cell's "
        "random training Sharpe, a Benjamini-Hochberg q at or under 0.10 on the training trade P&L, and "
        "a deflated Sharpe at least 0.95. The q values use every training p-value in the family of 68. "
        "The deflated Sharpe uses that cell's training daily returns and the same 68 trials.",
        "",
        *tapes,
        "",
        "## Scalp against the confirmed close",
        "",
        "This is the comparison that was registered with the scalp: planned R:R, win rate, profit factor, "
        "and the $2,500 ending, in train and in holdout, against the seed-17 random book. "
        "Confirmed rows are the base filter. The VWAP, 200 EMA, MACD, and short filters are in the full table.",
        "",
        _table(_compare_rows(rows)),
        "",
        "## Full family",
        "",
        _full_table(rows),
        "",
        "## 2026-10-08, about 14:15 to 14:25 ET",
        "",
        anecdote,
        "",
        f"Chart: `{EQUITY_PATH.as_posix()}`. Machine-readable summary: `{JSON_PATH.as_posix()}`.",
        "",
        "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. "
        "The default book is still dual momentum.",
        "",
        "```",
        "PYTHONPATH=src python3 -m webull_bot.chart_reads.research_neckline",
        "```",
        "",
    ]
    return "\n".join(lines)


def _upsert(path: Path, body: str) -> None:
    text = path.read_text() if path.exists() else ""
    block = f"{START_MARK}\n{body.rstrip()}\n{END_MARK}\n"
    if START_MARK in text and END_MARK in text:
        pre, rest = text.split(START_MARK, 1)
        _old, post = rest.split(END_MARK, 1)
        path.write_text(pre + block + post.lstrip("\n"))
        return
    if path.name == "README.md":
        anchor = "Full tables, including the stock diagnostics, are in [RESULTS.md](RESULTS.md)."
        if anchor in text:
            path.write_text(text.replace(anchor, block + "\n" + anchor, 1))
            return
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n" + block)


def _readme_blurb(rows: list[dict]) -> str:
    passed = [row["id"] for row in rows if row.get("passes")]
    verdict = (
        "No cell cleared the gate."
        if not passed
        else "Cleared the gate and was not promoted: " + ", ".join(passed) + "."
    )
    spy = next(row for row in rows if row["id"] == "SPY_scalp_scalp_neckline_0dte")
    base = next(row for row in rows if row["id"] == "SPY_confirmed_base_r1_0dte")
    return (
        "**Neckline break: does not join the book.** "
        "A 5-minute double bottom on Dukascopy SPY and QQQ, train 2017-2023 and holdout 2024-01-01 "
        "through 2026-10-06, fresh $2,500. The confirmed entry is the next open after a close above the "
        "neckline and both the 9 and 20 EMA. The quick scalp is a separate long, counted in the same "
        f"family of {n_trials()} cells: buy the red pullback after the 9 EMA reclaim, stop under that bar, "
        "target the neckline or 2R, flat at 15:45. "
        f"SPY 0 DTE scalp-to-neckline holdout ended {_money(spy['holdout'].get('ending_equity'))} "
        f"on {int(spy['holdout'].get('trades') or 0)} trades, profit factor {_num(spy['holdout'].get('profit_factor'))}, "
        f"win {_pct(spy['holdout'].get('win_rate'))}. "
        f"The confirmed 1R 0 DTE book ended {_money(base['holdout'].get('ending_equity'))} "
        f"on {int(base['holdout'].get('trades') or 0)} trades, profit factor {_num(base['holdout'].get('profit_factor'))}, "
        f"win {_pct(base['holdout'].get('win_rate'))}. "
        f"{verdict} "
        "The chart is `reports/neckline_equity.png`. Nothing was sent to a broker. "
        "Full table in [RESULTS.md](RESULTS.md)."
    )


def main() -> None:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    rules = frozen_rules()
    RULES_PATH.write_text(json.dumps(rules, indent=2) + "\n")
    print(f"RULES {RULES_PATH} cells {rules['n_trials']}", flush=True)
    iv = prior_iv(_load_series("VIX1D"), _load_series("VIX"))
    rows = []
    tapes = []
    books = {}
    for symbol in ("SPY", "QQQ"):
        frame, path = _load_bars(symbol)
        tapes.append(_tape_note(symbol, frame, path))
        print(f"PREPARE {symbol} bars {len(frame)}", flush=True)
        books[symbol] = prepare(frame, symbol)
        print(f"EVENTS {symbol} {len(books[symbol].events)}", flush=True)
    for cell in catalog():
        print(f"SCORE {cell.id}", flush=True)
        rows.append(_score_cell(books[cell.symbol], cell, iv))
    q_values = [float(item) for item in benjamini_hochberg([row["p"] for row in rows])]
    for row, q_value in zip(rows, q_values):
        dsr_pack = deflated_sharpe(row.pop("dsr_input"), n_trials())
        dsr = dsr_pack.get("dsr")
        dsr_value = 0.0 if dsr is None else float(dsr)
        row["q"] = q_value
        row["dsr"] = dsr_value
        row["passes"] = passes_gate(
            {"metrics": row["holdout"]},
            {"metrics": row["train"]},
            {"metrics": row["random_train"]},
            q_value,
            dsr_value,
        )
        print(
            f"DONE {row['id']} hold {row['holdout'].get('trades')} "
            f"end {row['holdout'].get('ending_equity')} pass {row['passes']}",
            flush=True,
        )
    _chart(rows)
    anecdote = _anecdote()
    prose = _prose(rows, tapes, anecdote)
    MD_PATH.write_text(prose)
    payload = {
        "rules": rules,
        "tapes": tapes,
        "anecdote": anecdote,
        "passed": [row["id"] for row in rows if row["passes"]],
        "cells": [_jsonable(row) for row in rows],
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    blurb = _readme_blurb(rows)
    _upsert(README_PATH, blurb)
    _upsert(RESULTS_PATH, prose)
    print(f"WROTE {MD_PATH} passed {payload['passed']}", flush=True)


if __name__ == "__main__":
    main()
