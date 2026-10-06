"""Search ATM 14 DTE option exits. Training picks the cell. The holdout does not.

Frozen in ``atm_exit`` before this run:

* 14 DTE, delta 0.50. Longs are calls. Shorts are puts.
* 1,293 exit cells. Stops, ascending ladders, runner targets, all-out
  targets, one reference time-stop ladder, and runner trails.
* The cell is the highest training Sharpe among cells with at least 30
  training trades. Expectancy, then a milder drawdown, then the label break
  ties. A 15-trade fallback is used only when nothing has 30. The grid is
  not enlarged after the holdout.
* The sized account is the training median equity that puts that cell's
  premium stop near 2% of the account. The holdout uses that equity.
* Walk-forward re-selects inside each training fold. Those folds sit inside
  the training span, so the holdout is scored once.
* A chop cell is wired onto the sandbox options sub-book only when its
  holdout expectancy is positive, ending equity is above the start, it has
  at least 20 trades, Sharpe is positive, it beats random entries, and the
  walk-forward pooled expectancy is positive. That bar is not the old
  300-trade gate.

Nothing is sent to a broker. This does not rewrite the earlier scale-out
sections.

Run: ``python -m webull_bot.chart_reads.research_atm_exit``
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.chart_reads.atm_exit import (
    ATM_DELTA,
    ATM_DTE,
    POOL_MIN_BOOKS,
    POOLED_FAMILIES,
    STOPS,
    beats,
    build_paths,
    choose,
    deflated_sharpe,
    filter_paths,
    frozen_grid,
    holds_up,
    neighbors,
    public_row,
    score_cell,
    sized_equity,
    truncate_paths,
)
from webull_bot.chart_reads.bounce import find_bounces, partial_params
from webull_bot.chart_reads.breakouts import find_breakout_setups
from webull_bot.chart_reads.chop_v2 import find_chop_breakouts
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DAILY_DEFAULTS
from webull_bot.chart_reads.premium_scale import CASH_ACCOUNT
from webull_bot.chart_reads.research import SYMBOLS, _in_window, _sessions, _slice as intraday_slice, random_setups
from webull_bot.chart_reads.research_daily import (
    IS_END,
    OOS_START,
    SAMPLE_END,
    SCORE_FROM,
    _slice as daily_slice,
    load_daily,
)
from webull_bot.chart_reads.research_exits import _ab_window, _bar_day, _load_hourly
from webull_bot.chart_reads.research_levels import _collect_daily
from webull_bot.chart_reads.research_scale import _dd, _gate_line, _money, _num, _pct, _pf
from webull_bot.chart_reads.trendline import find_trend_setups
from webull_bot.mtf_vwap.detect import rth
from webull_bot.universe_dow import is_member

START = "<!-- CHART_READS_ATM_EXIT_START -->"
END_MARK = "<!-- CHART_READS_ATM_EXIT_END -->"
SELECTION_PATH = Path("reports/atm_exit_selection.json")
REPORT_PATH = Path("reports/chart_reads_atm_exit.json")
# Expanding folds inside 2010-2018. The 2019-2026 holdout is not a fold.
DAILY_FOLDS = (
    (date(2010, 1, 1), date(2012, 12, 31), date(2013, 1, 1), date(2014, 12, 31)),
    (date(2010, 1, 1), date(2014, 12, 31), date(2015, 1, 1), date(2016, 12, 31)),
    (date(2010, 1, 1), date(2016, 12, 31), date(2017, 1, 1), date(2018, 12, 31)),
)


def _blank(cell) -> dict:
    return {
        "label": cell.label,
        "family": cell.family,
        "stop": float(cell.stop),
        "sharpe": 0.0,
        "expectancy": 0.0,
        "max_drawdown": 0.0,
        "trades": 0,
        "ending_equity": None,
        "starting_equity": None,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "skipped": 0,
        "pdt_blocked": 0,
        "overlapped": 0,
        "targets": {},
        "runner": {},
        "armed": 0,
    }


def _equities(paths) -> dict[float, float]:
    return {float(stop): float(sized_equity(paths, stop)) for stop in STOPS}


def _score_grid(paths, grid, equities, max_hold, pdt_prospective, tag: str) -> list[dict]:
    rows = []
    started = time.perf_counter()
    for index, cell in enumerate(grid, start=1):
        equity = equities.get(float(cell.stop), float("nan"))
        if not np.isfinite(equity) or equity <= 0.0:
            rows.append(_blank(cell))
        else:
            rows.append(
                score_cell(
                    paths,
                    cell,
                    starting_equity=float(equity),
                    max_hold=int(max_hold),
                    pdt_prospective=bool(pdt_prospective),
                )
            )
        if index % 250 == 0 or index == len(grid):
            print(f"    {tag} {index}/{len(grid)} in {time.perf_counter() - started:.1f}s", flush=True)
    return rows


def _by_label(grid) -> dict:
    return {cell.label: cell for cell in grid}


def _capture(row: dict) -> float:
    trades = row.get("trade_rows") or []
    ratios = []
    for trade in trades:
        debit = float(trade.get("debit") or 0.0)
        if debit > 0.0:
            ratios.append(float(trade["pnl"]) / debit)
    if not ratios:
        return float("nan")
    return float(np.mean(ratios))


def _official(paths, cell, equity, max_hold, pdt_prospective) -> dict:
    row = score_cell(
        paths,
        cell,
        starting_equity=float(equity),
        max_hold=int(max_hold),
        pdt_prospective=bool(pdt_prospective),
        keep_returns=True,
        keep_trades=True,
    )
    row["capture"] = _capture(row)
    return row


def _quote_stats(paths) -> dict:
    opened = [path for path in paths if path.ok]
    debits = [path.debit for path in opened]
    deltas = [path.delta for path in opened]
    return {
        "opened": len(opened),
        "failed": sum(1 for path in paths if not path.ok),
        "median_debit": float(np.median(debits)) if debits else float("nan"),
        "median_delta": float(np.median(deltas)) if deltas else float("nan"),
        "fit_1000": int(sum(1 for path in opened if path.debit <= CASH_ACCOUNT)),
    }


def _hourly_folds(frames, window) -> list[dict]:
    days = _sessions(intraday_slice(frames, window[0], window[1]))
    if len(days) < 8:
        return []
    cuts = [0, len(days) // 4, len(days) // 2, (3 * len(days)) // 4, len(days)]
    folds = []
    for index in range(1, 4):
        folds.append(
            {
                "train": (days[0], days[cuts[index] - 1]),
                "test": (days[cuts[index]], days[cuts[index + 1] - 1]),
            }
        )
    return folds


def _daily_folds() -> list[dict]:
    return [{"train": (start, train_end), "test": (test_start, test_end)} for start, train_end, test_start, test_end in DAILY_FOLDS]


def _walk(is_paths, grid, max_hold, pdt_prospective, folds) -> dict:
    fold_rows = []
    pnl = 0.0
    trades = 0
    for fold in folds:
        train_start, train_end = fold["train"]
        test_start, test_end = fold["test"]
        print(f"    walk-forward train {train_start} through {train_end}", flush=True)
        train_paths = truncate_paths(filter_paths(is_paths, train_start, train_end), train_end)
        equities = _equities(train_paths)
        rows = _score_grid(train_paths, grid, equities, max_hold, pdt_prospective, "walk-forward")
        decision = choose(rows)
        test_paths = filter_paths(is_paths, test_start, test_end)
        test_row = None
        if decision["label"]:
            cell = _by_label(grid)[decision["label"]]
            equity = equities.get(float(cell.stop), float("nan"))
            if np.isfinite(equity) and equity > 0.0:
                test_row = _official(test_paths, cell, equity, max_hold, pdt_prospective)
                pnl += float(test_row["expectancy"]) * int(test_row["trades"])
                trades += int(test_row["trades"])
        fold_rows.append(
            {
                "train": [train_start.isoformat(), train_end.isoformat()],
                "test": [test_start.isoformat(), test_end.isoformat()],
                "label": decision["label"],
                "rule": decision["rule"],
                "fallback": decision["fallback"],
                "test_metrics": public_row(test_row) if test_row else None,
            }
        )
    expectancy = (pnl / trades) if trades else None
    return {"folds": fold_rows, "expectancy": expectancy, "trades": trades}


def _spy_hold(frame: pd.DataFrame, start: date, end: date, starting: float) -> dict:
    empty = {
        "label": "SPY buy and hold",
        "sharpe": 0.0,
        "expectancy": 0.0,
        "max_drawdown": 0.0,
        "trades": 0,
        "ending_equity": float(starting),
        "starting_equity": float(starting),
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "shares": 0,
        "capture": float("nan"),
    }
    if frame is None or len(frame) == 0:
        return empty
    index = frame.index
    if getattr(index, "tz", None) is not None:
        days = [pd.Timestamp(ts).tz_convert("America/New_York").date() for ts in index]
    else:
        days = [pd.Timestamp(ts).date() for ts in index]
    mask = np.array([start <= day <= end for day in days])
    window = frame.loc[mask]
    if window.empty:
        return empty
    entry = float(window.iloc[0]["open"]) * (1.0 + 6.0 / 10_000.0)
    exit_ = float(window.iloc[-1]["close"]) * (1.0 - 6.0 / 10_000.0)
    shares = int(np.floor(float(starting) / entry)) if entry > 0.0 else 0
    if shares < 1:
        empty["shares"] = 0
        return empty
    cash = float(starting) - shares * entry
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
        exposure=pd.Series(1.0, index=equity.index),
        trades=trades,
        ending_equity=float(equity.iloc[-1]),
    )
    metrics = compute_metrics(result, float(starting))
    metrics["shares"] = shares
    metrics["label"] = "SPY buy and hold"
    metrics["capture"] = float("nan")
    return metrics


def _choose_pooled(book_rows: list[list[dict]]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for rows in book_rows:
        for row in rows:
            if row.get("family") not in POOLED_FAMILIES:
                continue
            grouped.setdefault(row["label"], []).append(row)
    candidates = []
    for label, group in grouped.items():
        eligible = [row for row in group if int(row.get("trades") or 0) >= 30]
        if len(eligible) < POOL_MIN_BOOKS:
            continue
        candidates.append(
            {
                "label": label,
                "family": eligible[0]["family"],
                "sharpe": float(np.mean([row["sharpe"] for row in eligible])),
                "expectancy": float(np.mean([row["expectancy"] for row in eligible])),
                "max_drawdown": float(np.mean([row["max_drawdown"] for row in eligible])),
                "trades": min(int(row["trades"]) for row in eligible),
                "books": len(eligible),
            }
        )
    decision = choose(candidates)
    decision["pool_min_books"] = POOL_MIN_BOOKS
    if decision["row"] is not None:
        decision["row"] = public_row(decision["row"])
    return decision


def _cell_table(rows: list[dict]) -> str:
    lines = [
        "| Sample | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row is None:
            continue
        lines.append(
            "| {label} | {trades} | {win} | {capture} | {exp} | {pf} | {sharpe} | {dd} | {ending} |".format(
                label=row.get("label"),
                trades=int(row.get("trades") or 0),
                win=_pct(row.get("win_rate")),
                capture=_signed(row.get("capture")),
                exp=_money(row.get("expectancy")),
                pf=_pf(row.get("profit_factor")),
                sharpe=_num(row.get("sharpe")),
                dd=_dd(row.get("max_drawdown")),
                ending=_money(row.get("ending_equity")),
            )
        )
    return "\n".join(lines)


def _signed(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):+.1f}%"


def _neighbor_table(rows: list[dict]) -> str:
    lines = [
        "| Neighbor | Train Sharpe | Train exp. | Train DD | Train trades | Holdout Sharpe | Holdout exp. | Holdout DD | Holdout trades | Holdout ending |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        train = row["train"]
        holdout = row["holdout"]
        lines.append(
            "| {label} | {tsharpe} | {texp} | {tdd} | {ttrades} | {hsharpe} | {hexp} | {hdd} | {htrades} | {hending} |".format(
                label=row["label"],
                tsharpe=_num(train.get("sharpe")),
                texp=_money(train.get("expectancy")),
                tdd=_dd(train.get("max_drawdown")),
                ttrades=int(train.get("trades") or 0),
                hsharpe=_num(holdout.get("sharpe")),
                hexp=_money(holdout.get("expectancy")),
                hdd=_dd(holdout.get("max_drawdown")),
                htrades=int(holdout.get("trades") or 0),
                hending=_money(holdout.get("ending_equity")),
            )
        )
    return "\n".join(lines)


def _fold_table(folds: list[dict]) -> str:
    lines = [
        "| Fold train | Fold test | Cell chosen on that train | Test trades | Test exp. | Test Sharpe | Test DD | Test ending |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for fold in folds:
        metrics = fold.get("test_metrics") or {}
        lines.append(
            "| {train} | {test} | {label} | {trades} | {exp} | {sharpe} | {dd} | {ending} |".format(
                train=f"{fold['train'][0]} through {fold['train'][1]}",
                test=f"{fold['test'][0]} through {fold['test'][1]}",
                label=fold.get("label") or "none",
                trades=int(metrics.get("trades") or 0),
                exp=_money(metrics.get("expectancy")),
                sharpe=_num(metrics.get("sharpe")),
                dd=_dd(metrics.get("max_drawdown")),
                ending=_money(metrics.get("ending_equity")),
            )
        )
    return "\n".join(lines)


def _dist(row: dict) -> str:
    targets = row.get("targets") or {}
    runner = row.get("runner") or {}
    counts = ", ".join(f"{int(targets.get(str(index), 0))} hit {index}" for index in range(5))
    runner_text = ", ".join(f"{key} {value}" for key, value in sorted(runner.items())) or "none"
    return f"{counts}. Runner outcomes: {runner_text}. Armed after the first rung: {int(row.get('armed') or 0)}."


def render(payload: dict) -> str:
    lines = [
        "## ATM 14 DTE option exits",
        "",
        "DOES NOT CHANGE THE GATE. This search was frozen before the holdout was scored. "
        f"Longs buy calls and shorts buy puts, delta {ATM_DELTA:.2f}, {ATM_DTE} calendar days. "
        f"Each book tried {payload['cells']} exit cells: ascending 3-rung and 2-rung ladders, "
        "runner targets at +50%, +75%, +100%, and +150%, all-out targets, one reference time-stop ladder, "
        "and runner trails of 10%, 15%, and 25% off the peak premium. Stops are -10%, -15%, -20%, -25%, -30%, and -40% "
        "of the premium. Contracts 1-4 keep that stop. The runner moves to break-even only after the first rung fills, "
        "and only at the end of that bar. A stop that gaps through fills at the worse bid. Costs are the spread haircut "
        "and the option fees. The grid was not enlarged after these numbers.",
        "",
        "The cell is the highest training Sharpe among cells with at least 30 training trades. Higher expectancy, "
        "then a milder drawdown, then the label break a tie. If no cell has 30 trades, the same rule uses cells with "
        "at least 15. The sized account is the training median equity that puts that cell's stop near 2% of the account, "
        "and at least the five-lot debit. Random entries keep the symbols, directions, and count, shuffle the timestamps "
        "with seed 17, and use that same cell and equity. SPY buy and hold is whole shares of that equity, 6 bps of "
        "slippage each side. Walk-forward re-selects inside the training span. It does not replace the cell.",
        "",
        "A time stop is N trading sessions, the same clock as the existing hold. Hourly books try 2, 5, and 10 sessions. "
        "Daily books try 3, 7, and 14. Expiry at 14 DTE still applies, so the earlier of the two exits wins. "
        "The reference ladder for the time stop and the trail is 2 at +15%, 1 at +25%, 1 at +40%, runner +100%, "
        "and it was fixed before the run. Other cells keep the book's existing session hold.",
        "",
    ]
    for book in payload["books"]:
        lines.append(f"### {book['name']}")
        lines.append("")
        lines.append(book["blurb"])
        quotes = book["quotes"]
        lines.append(
            f"Holdout {book['window']}. Opened training quotes {quotes['opened']}, failed opens {quotes['failed']}. "
            f"Median debit {_money(quotes['median_debit'])}. Median delta {_num(quotes['median_delta'])}. "
            f"Quotes that fit five contracts in $1,000: {quotes['fit_1000']} of {quotes['opened']}. "
            f"Cells tried: {book['cells']}. Cells with at least 30 training trades: {book['eligible']}. "
            f"Training cells with positive expectancy: {book['positive_expectancy']}."
        )
        decision = book["decision"]
        if not decision.get("label"):
            lines.append(decision["rule"] + ". No holdout cell was scored for this book.")
            lines.append("")
            continue
        train = book["train"]
        lines.append(
            f"Chosen on training only, before the holdout: `{decision['label']}`. {decision['rule']}. "
            f"Sized account {_money(train.get('starting_equity'))}."
        )
        lines.append("")
        lines.append(_cell_table([book["train_view"], book["holdout_view"], book["random_view"], book["spy_view"], book["cash_view"]]))
        lines.append("")
        holdout = book["holdout"]
        lines.append(
            f"Holdout: {int(holdout.get('trades') or 0)} trades, expectancy {_money(holdout.get('expectancy'))}, "
            f"profit factor {_pf(holdout.get('profit_factor'))}, Sharpe {_num(holdout.get('sharpe'))}, "
            f"max drawdown {_dd(holdout.get('max_drawdown'))}, ending {_money(holdout.get('ending_equity'))}. "
            f"It {_gate_line(holdout)}. "
            f"It {'beats' if book['beats_random'] else 'does not beat'} the random entries. "
            f"It {'beats' if book['beats_spy'] else 'does not beat'} SPY buy and hold on Sharpe with a drawdown that is not worse."
        )
        lines.append(_dist(holdout))
        dsr = book["dsr"]
        if dsr.get("dsr") is None:
            lines.append("Deflated Sharpe was not computed. The training return series was too short.")
        else:
            lines.append(
                f"Multiple testing: {dsr['trials']} cells were tried. The training Sharpe is {_num(dsr['sr_annual'])} "
                f"annualized. The Sharpe expected from the best of {dsr['trials']} zero-edge tries, on a sample of this "
                f"length and shape, is about {_num(dsr['sr_star_annual'])} annualized. The deflated Sharpe probability "
                f"is {_pct(dsr['dsr'])} (skew {_num(dsr['skew'])}, kurtosis {_num(dsr['kurtosis'])}, "
                f"{dsr['observations']} return observations). A high training Sharpe with a deflated Sharpe near zero "
                "is what trying this many cells produces when there is no edge. This probability does not include the "
                "other books. Six books were selected, plus one pooled cell, so the chance that some book looks good "
                "is higher than one book's deflated Sharpe says."
            )
        lines.append("")
        if book["neighbors"]:
            lines.append(
                "Neighbors are the adjacent stop, runner, first rung, trail, or time stop inside the frozen grid. "
                "Their holdout numbers were not used to pick the cell."
            )
            lines.append("")
            lines.append(_neighbor_table(book["neighbors"]))
            lines.append("")
            train_positive = sum(1 for row in book["neighbors"] if float(row["train"].get("sharpe") or 0.0) > 0.0)
            hold_positive = sum(
                1
                for row in book["neighbors"]
                if float(row["holdout"].get("expectancy") or 0.0) > 0.0
                and float(row["holdout"].get("ending_equity") or 0.0) > float(row["holdout"].get("starting_equity") or 0.0)
            )
            lines.append(
                f"{train_positive} of {len(book['neighbors'])} neighbors have a positive training Sharpe. "
                f"{hold_positive} of {len(book['neighbors'])} have a positive holdout expectancy and an ending equity above the start."
            )
            lines.append("")
        walk = book["walk"]
        if not walk["folds"]:
            lines.append("Walk-forward was not run. The training calendar was too short.")
        else:
            lines.append(
                f"Walk-forward pooled expectancy {_money(walk['expectancy'])} on {int(walk['trades'])} test trades. "
                "Each fold's cell was chosen on that fold's training window only."
            )
            lines.append("")
            lines.append(_fold_table(walk["folds"]))
            lines.append("")
        pooled = book.get("pooled_holdout")
        if pooled is not None:
            lines.append(
                f"Pooled training cell on this holdout: `{payload['pooled']['label']}`. "
                f"{int(pooled.get('trades') or 0)} trades, expectancy {_money(pooled.get('expectancy'))}, "
                f"Sharpe {_num(pooled.get('sharpe'))}, max drawdown {_dd(pooled.get('max_drawdown'))}, "
                f"ending {_money(pooled.get('ending_equity'))}. The pooled cell does not replace this book's cell."
            )
            lines.append("")
        if book["holds_up"]:
            lines.append("This cell meets the pre-registered hold-up bar.")
        else:
            lines.append(
                "This cell does not meet the pre-registered hold-up bar. "
                + ". ".join(book["hold_reasons"])
                + "."
            )
        lines.append("")
    pooled = payload["pooled"]
    lines.append("### Pooled cell")
    lines.append("")
    if not pooled.get("label"):
        lines.append(pooled.get("rule", "No pooled cell.") + " Families A, B, C, and E were eligible. The time-stop family was not, because the session counts differ by clock.")
    else:
        lines.append(
            f"The pooled cell is `{pooled['label']}`. It is the highest mean training Sharpe across books where that "
            f"cell has at least 30 training trades, and it has to clear that bar on at least {POOL_MIN_BOOKS} books. "
            f"{pooled['rule']}. It was chosen before any holdout score. It is not wired unless it is also the chop book's own cell and that cell holds up."
        )
    lines.append("")
    profitable = payload["profitable_books"]
    if profitable:
        lines.append(
            "Holdout cells with positive expectancy and ending equity above the start, after costs: "
            + "; ".join(
                f"{item['name']} ({item['trades']} trades, expectancy {_money(item['expectancy'])}, ending {_money(item['ending'])})"
                for item in profitable
            )
            + "."
        )
    else:
        lines.append(
            "No chosen cell is profitable on its untouched holdout after costs. Profit here means expectancy above zero "
            "and ending equity above the start. Costs are the spread haircut, the option fees, and a gap fill at the worse bid."
        )
    lines.append("")
    if payload["wired"]:
        lines.append(
            f"The chop book's cell holds up, so the sandbox options sub-book uses `{payload['wired_label']}`. "
            "Live trading stays off. The premium is still the model, not a Webull quote."
        )
    else:
        lines.append(
            "The chop book's cell does not hold up, so the sandbox options sub-book is unchanged. "
            "It is still the corrected ladder: 21 DTE, delta 0.45, contracts 1-4 at the -20% stop, "
            "runner break-even only after +15%, target +100%. Live trading stays off."
        )
    lines.append("")
    lines.append(
        "Not added to `config/optional_strategies.json`. The published scale-out numbers and the share forward test "
        "are unchanged. The default book is still dual momentum."
    )
    return "\n".join(lines).rstrip() + "\n"


def write_report(text: str, path: Path) -> None:
    body = path.read_text() if path.exists() else ""
    block = f"{START}\n{text.rstrip()}\n{END_MARK}\n"
    if START in body and END_MARK in body:
        pre, rest = body.split(START, 1)
        _, post = rest.split(END_MARK, 1)
        path.write_text(pre.rstrip() + "\n\n" + block + post.lstrip("\n"))
        return
    marker = "<!-- CHART_READS_SCALE_CORRECTED_END -->"
    if marker in body:
        pre, post = body.split(marker, 1)
        path.write_text(pre + marker + "\n\n" + block + post.lstrip("\n"))
        return
    path.write_text(body.rstrip() + "\n\n" + block)


def _chop_setups(hourly: dict[str, pd.DataFrame]) -> list:
    found = []
    for symbol, frame in hourly.items():
        if symbol not in SYMBOLS or frame is None or len(frame) < 30:
            continue
        bars = rth(frame)
        if bars is None or len(bars) < 30:
            continue
        found.extend(find_chop_breakouts(bars, symbol=symbol))
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    return found


def _prepare_book(spec: dict) -> dict:
    print(f"== {spec['name']} ==", flush=True)
    is_setups = _in_window(spec["setups"], spec["is_window"][0], spec["is_window"][1])
    oos_setups = _in_window(spec["setups"], spec["oos_window"][0], spec["oos_window"][1])
    is_frames = spec["slice"](spec["frames"], spec["is_window"][0], spec["is_window"][1])
    oos_frames = spec["slice"](spec["frames"], spec["oos_window"][0], spec["oos_window"][1])
    params = dict(spec["base"])
    params["dte"] = ATM_DTE
    params["delta"] = ATM_DELTA
    params["expression"] = "single"
    print(f"  pricing training paths ({len(is_setups)} signals)", flush=True)
    is_paths = build_paths(is_setups, is_frames, spec["daily"], params, session_filter=spec["session_filter"])
    grid = frozen_grid(spec["clock"])
    equities = _equities(is_paths)
    pdt = bool(params.get("pdt_prospective", True))
    max_hold = int(params.get("max_hold_sessions", 1))
    print("  training grid", flush=True)
    rows = _score_grid(is_paths, grid, equities, max_hold, pdt, "training")
    decision = choose(rows)
    print(f"  chosen: {decision['label']}", flush=True)
    return {
        "spec": spec,
        "params": params,
        "is_paths": is_paths,
        "oos_setups": oos_setups,
        "oos_frames": oos_frames,
        "grid": grid,
        "equities": equities,
        "rows": rows,
        "decision": decision,
        "pdt": pdt,
        "max_hold": max_hold,
    }


def _finish_book(prepared: dict, pooled_label: str | None) -> dict:
    spec = prepared["spec"]
    decision = prepared["decision"]
    grid = prepared["grid"]
    by_label = _by_label(grid)
    rows = prepared["rows"]
    train_row = None
    holdout = None
    random_row = None
    spy = None
    cash = None
    neighbor_rows = []
    walk = {"folds": [], "expectancy": None, "trades": 0}
    dsr = {"dsr": None, "trials": len(grid)}
    beats_random = False
    beats_spy = False
    held = False
    reasons = ["no cell was selected"]
    pooled_holdout = None
    print(f"  pricing holdout paths ({len(prepared['oos_setups'])} signals)", flush=True)
    oos_paths = build_paths(
        prepared["oos_setups"],
        prepared["oos_frames"],
        spec["daily"],
        prepared["params"],
        session_filter=spec["session_filter"],
    )
    prepared["oos_paths"] = oos_paths
    if decision["label"]:
        cell = by_label[decision["label"]]
        equity = prepared["equities"][float(cell.stop)]
        train_row = _official(
            prepared["is_paths"], cell, equity, prepared["max_hold"], prepared["pdt"]
        )
        dsr = deflated_sharpe(train_row.get("returns"), len(grid))
        print("  holdout", flush=True)
        holdout = _official(oos_paths, cell, equity, prepared["max_hold"], prepared["pdt"])
        print("  random", flush=True)
        shuffled = random_setups(prepared["oos_setups"], prepared["oos_frames"], seed=17)
        random_paths = build_paths(
            shuffled,
            prepared["oos_frames"],
            spec["daily"],
            prepared["params"],
            session_filter=spec["session_filter"],
        )
        random_row = _official(random_paths, cell, equity, prepared["max_hold"], prepared["pdt"])
        random_row["label"] = "random entries, same cell"
        spy = _spy_hold(spec["daily"].get("SPY"), spec["oos_window"][0], spec["oos_window"][1], float(equity))
        cash = _official(prepared["oos_paths"], cell, CASH_ACCOUNT, prepared["max_hold"], prepared["pdt"])
        cash["label"] = "$1,000 holdout"
        print("  neighbors", flush=True)
        train_by_label = {row["label"]: row for row in rows}
        for neighbor in neighbors(cell, grid, spec["clock"]):
            neighbor_equity = prepared["equities"].get(float(neighbor.stop), float("nan"))
            if not np.isfinite(neighbor_equity) or neighbor_equity <= 0.0:
                hold_row = _blank(neighbor)
            else:
                hold_row = score_cell(
                    prepared["oos_paths"],
                    neighbor,
                    starting_equity=float(neighbor_equity),
                    max_hold=prepared["max_hold"],
                    pdt_prospective=prepared["pdt"],
                )
            neighbor_rows.append(
                {
                    "label": neighbor.label,
                    "train": public_row(train_by_label.get(neighbor.label, _blank(neighbor))),
                    "holdout": public_row(hold_row),
                }
            )
        folds = _hourly_folds(spec["frames"], spec["is_window"]) if spec["clock"] == "hourly" else _daily_folds()
        walk = _walk(prepared["is_paths"], grid, prepared["max_hold"], prepared["pdt"], folds)
        beats_random = beats(holdout, random_row)
        beats_spy = beats(holdout, spy)
        held, reasons = holds_up(holdout, random_row, walk["expectancy"])
        train_row["label"] = "training, chosen cell"
        holdout["label"] = "holdout, chosen cell"
    if pooled_label and pooled_label in by_label:
        pooled_cell = by_label[pooled_label]
        pooled_equity = prepared["equities"].get(float(pooled_cell.stop), float("nan"))
        if np.isfinite(pooled_equity) and pooled_equity > 0.0:
            print("  pooled cell on holdout", flush=True)
            pooled_holdout = score_cell(
                prepared.get("oos_paths") or [],
                pooled_cell,
                starting_equity=float(pooled_equity),
                max_hold=prepared["max_hold"],
                pdt_prospective=prepared["pdt"],
            )
    positive = sum(1 for row in rows if float(row.get("expectancy") or 0.0) > 0.0 and int(row.get("trades") or 0) > 0)
    return {
        "name": spec["name"],
        "blurb": spec["blurb"],
        "window": f"{spec['oos_window'][0].isoformat()} through {spec['oos_window'][1].isoformat()}",
        "clock": spec["clock"],
        "cells": len(grid),
        "quotes": _quote_stats(prepared["is_paths"]),
        "decision": {
            "label": decision["label"],
            "rule": decision["rule"],
            "fallback": decision["fallback"],
            "eligible": decision["eligible"],
        },
        "eligible": decision["eligible"],
        "positive_expectancy": positive,
        "train": public_row(train_row) if train_row else None,
        "holdout": public_row(holdout) if holdout else None,
        "random": public_row(random_row) if random_row else None,
        "spy": {key: value for key, value in (spy or {}).items() if key != "returns"},
        "cash": public_row(cash) if cash else None,
        "train_view": train_row,
        "holdout_view": holdout,
        "random_view": random_row,
        "spy_view": spy,
        "cash_view": cash,
        "neighbors": neighbor_rows,
        "walk": {
            "folds": walk["folds"],
            "expectancy": walk["expectancy"],
            "trades": walk["trades"],
        },
        "dsr": dsr,
        "beats_random": beats_random,
        "beats_spy": beats_spy,
        "holds_up": held,
        "hold_reasons": reasons,
        "pooled_holdout": public_row(pooled_holdout) if pooled_holdout else None,
        "training_rows": [public_row(row) for row in rows],
    }


def _json(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    return str(value)


def _selection_payload(prepared_books: list[dict], pooled: dict) -> dict:
    return {
        "frozen_before_holdout": True,
        "dte": ATM_DTE,
        "delta": ATM_DELTA,
        "cells": len(prepared_books[0]["grid"]) if prepared_books else 0,
        "rule": "highest training Sharpe among cells with at least 30 training trades",
        "books": [
            {
                "name": item["spec"]["name"],
                "label": item["decision"]["label"],
                "rule": item["decision"]["rule"],
                "fallback": item["decision"]["fallback"],
                "eligible": item["decision"]["eligible"],
                "train": public_row(item["decision"]["row"]) if item["decision"]["row"] else None,
            }
            for item in prepared_books
        ],
        "pooled": {
            "label": pooled.get("label"),
            "rule": pooled.get("rule"),
            "fallback": pooled.get("fallback"),
            "row": pooled.get("row"),
        },
    }


def main() -> None:
    print("loading daily bars", flush=True)
    daily_frames, missing = load_daily()
    print(f"  {len(daily_frames)} symbols, missing {missing}", flush=True)
    print("detecting bounces", flush=True)
    bounces = []
    for symbol, frame in daily_frames.items():
        if len(frame) < 80:
            continue
        found = find_bounces(frame, symbol)
        found = [
            setup
            for setup in found
            if _bar_day(setup.fill_time) >= SCORE_FROM and is_member(symbol, _bar_day(setup.signal_time))
        ]
        bounces.extend(found)
    bounces.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol))
    print(f"  bounce signals {len(bounces)}", flush=True)
    daily_short, hourly = _load_hourly()
    print("detecting chop-v2 60-minute breakouts", flush=True)
    chop = _chop_setups(hourly)
    print(f"  chop signals {len(chop)}", flush=True)
    from webull_bot.chart_reads.research import _cells, detect_all

    ab_params = _cells("60m")[0]
    print("detecting A and B", flush=True)
    detected = detect_all(hourly, daily_short, {}, ab_params)
    setup_a = [setup for setup in detected if setup.kind == "A"]
    setup_b = [setup for setup in detected if setup.kind == "B"]
    print(f"  A {len(setup_a)} B {len(setup_b)}", flush=True)
    is_ab, oos_ab = _ab_window(hourly)
    print("detecting C and D", flush=True)
    trend = _collect_daily(daily_frames, find_trend_setups, DAILY_DEFAULTS)
    ranges = _collect_daily(daily_frames, find_breakout_setups, BREAKOUT_DEFAULTS)
    print(f"  C {len(trend)} D {len(ranges)}", flush=True)
    chop_params = dict(ab_params)
    chop_params["expression"] = "single"
    specs = [
        {
            "name": "Chop-v2 60-minute box breakout",
            "clock": "hourly",
            "setups": chop,
            "frames": hourly,
            "daily": daily_short,
            "base": chop_params,
            "session_filter": True,
            "slice": intraday_slice,
            "is_window": is_ab,
            "oos_window": oos_ab,
            "blurb": (
                f"{len(chop)} signals on the named list, frozen chop-v2 box, no cell override. "
                "Calls and puts follow the setup. 14 DTE, delta 0.50. This is the forward-test candidate."
            ),
        },
        {
            "name": "Partial bounce, daily Dow",
            "clock": "daily",
            "setups": bounces,
            "frames": daily_frames,
            "daily": daily_frames,
            "base": partial_params(),
            "session_filter": False,
            "slice": daily_slice,
            "is_window": (SCORE_FROM, IS_END),
            "oos_window": (OOS_START, SAMPLE_END),
            "blurb": (
                f"{len(bounces)} signals. Same bounce entry. Calls, 14 DTE, delta 0.50. "
                f"Holdout {OOS_START.isoformat()} through {SAMPLE_END.isoformat()}."
            ),
        },
        {
            "name": "A, 60-minute",
            "clock": "hourly",
            "setups": setup_a,
            "frames": hourly,
            "daily": daily_short,
            "base": ab_params,
            "session_filter": True,
            "slice": intraday_slice,
            "is_window": is_ab,
            "oos_window": oos_ab,
            "blurb": f"{len(setup_a)} continuation signals. Calls, 14 DTE, delta 0.50.",
        },
        {
            "name": "B, 60-minute",
            "clock": "hourly",
            "setups": setup_b,
            "frames": hourly,
            "daily": daily_short,
            "base": ab_params,
            "session_filter": True,
            "slice": intraday_slice,
            "is_window": is_ab,
            "oos_window": oos_ab,
            "blurb": f"{len(setup_b)} failed-breakout signals. Calls and puts follow the setup. 14 DTE, delta 0.50.",
        },
        {
            "name": "C, daily Dow",
            "clock": "daily",
            "setups": trend,
            "frames": daily_frames,
            "daily": daily_frames,
            "base": dict(DAILY_DEFAULTS),
            "session_filter": False,
            "slice": daily_slice,
            "is_window": (SCORE_FROM, IS_END),
            "oos_window": (OOS_START, SAMPLE_END),
            "blurb": f"{len(trend)} signals. Same daily entries. Calls, 14 DTE, delta 0.50.",
        },
        {
            "name": "D, daily Dow",
            "clock": "daily",
            "setups": ranges,
            "frames": daily_frames,
            "daily": daily_frames,
            "base": dict(BREAKOUT_DEFAULTS),
            "session_filter": False,
            "slice": daily_slice,
            "is_window": (SCORE_FROM, IS_END),
            "oos_window": (OOS_START, SAMPLE_END),
            "blurb": f"{len(ranges)} signals. Same daily entries. Calls and puts follow the setup. 14 DTE, delta 0.50.",
        },
    ]
    prepared = [_prepare_book(spec) for spec in specs]
    pooled = _choose_pooled([item["rows"] for item in prepared])
    print(f"pooled: {pooled.get('label')}", flush=True)
    SELECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    selection = _selection_payload(prepared, pooled)
    SELECTION_PATH.write_text(json.dumps(selection, indent=2, default=_json) + "\n")
    print("SELECTION FROZEN before holdout", flush=True)
    saved = json.loads(SELECTION_PATH.read_text())
    if [item["label"] for item in saved["books"]] != [item["decision"]["label"] for item in prepared]:
        raise RuntimeError("selection file does not match the training choice")
    books = [_finish_book(item, pooled.get("label")) for item in prepared]
    profitable = []
    for book in books:
        holdout = book.get("holdout") or {}
        if (
            float(holdout.get("expectancy") or 0.0) > 0.0
            and float(holdout.get("ending_equity") or 0.0) > float(holdout.get("starting_equity") or 0.0)
            and int(holdout.get("trades") or 0) > 0
        ):
            profitable.append(
                {
                    "name": book["name"],
                    "trades": int(holdout.get("trades") or 0),
                    "expectancy": holdout.get("expectancy"),
                    "ending": holdout.get("ending_equity"),
                }
            )
    chop = next(book for book in books if book["name"].startswith("Chop-v2"))
    wired = bool(chop["holds_up"] and chop["decision"]["label"])
    payload = {
        "cells": len(frozen_grid("hourly")),
        "books": books,
        "pooled": {
            "label": pooled.get("label"),
            "rule": pooled.get("rule"),
            "fallback": pooled.get("fallback"),
            "row": pooled.get("row"),
        },
        "profitable_books": profitable,
        "wired": wired,
        "wired_label": chop["decision"]["label"] if wired else None,
    }
    text = render(payload)
    write_report(text, Path("RESULTS.md"))
    stored = dict(payload)
    for book in stored["books"]:
        book.pop("train_view", None)
        book.pop("holdout_view", None)
        book.pop("random_view", None)
        book.pop("spy_view", None)
        book.pop("cash_view", None)
    REPORT_PATH.write_text(json.dumps(stored, indent=2, default=_json) + "\n")
    print(text)
    if wired:
        print("WIRE chop options sub-book:", chop["decision"]["label"], flush=True)
    else:
        print("DO NOT WIRE. Corrected ladder stays.", flush=True)


if __name__ == "__main__":
    main()
