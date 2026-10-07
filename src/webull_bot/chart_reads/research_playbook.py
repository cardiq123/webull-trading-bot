"""Walk-forward score for the combined SPY 0 DTE playbook. Backtests only.

Does not place an order, does not edit an existing sandbox book, and does not
add a strategy to the live list. The grid in playbook.frozen_rules is the one scored.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.ema_reclaim import prepare
from webull_bot.chart_reads.ema_reject import SAMPLE_END, to_five_minute
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.playbook import (
    GRID_SIZE,
    BOOK_SETUPS,
    cell_setups,
    cells,
    deflated_sharpe,
    folds,
    fold_results,
    frozen_rules,
    index_tickets,
    modal_cell,
    price_play,
    promote_decision,
    random_plays,
    rule_sheet,
    run_cell,
    run_plan,
    select_cell,
    session_days,
    stability_score,
    strict_majority,
    worst_month,
    best_sharpe_cell,
    build_tickets,
    spy_hold,
)
from webull_bot.chart_reads.vwap_band import find_signals, simulate
from webull_bot.chart_reads.vwap_band_data import load_minutes, to_fifteen_minute
from webull_bot.data.yfinance_provider import YFinanceProvider

MARK_START = "<!-- PLAYBOOK_START -->"
MARK_END = "<!-- PLAYBOOK_END -->"
RESULT_PATH = Path("reports/playbook.json")
TEST_START = date(2020, 1, 1)


def _money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    number = float(value)
    if abs(number) < 0.5:
        return "$0"
    if number < 0:
        return f"-${abs(number):,.0f}"
    return f"${number:,.0f}"


def _pct(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _num(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _pf(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _iv() -> dict:
    provider = YFinanceProvider(cache_dir="data/cache/vwap_band/yahoo")
    daily = provider.history(["^VIX", "^VIX1D"], "2016-01-01", "2026-10-08", interval="1d")
    closes = {}
    for symbol, frame in daily.items():
        if frame is None or frame.empty or "close" not in frame.columns:
            continue
        series = frame["close"].astype(float).copy()
        index = pd.to_datetime(series.index)
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert("America/New_York").tz_localize(None)
        series.index = index
        closes[symbol.replace("^", "")] = series[~series.index.duplicated(keep="last")].sort_index()
    return prior_iv(closes.get("VIX1D", pd.Series(dtype=float)), closes.get("VIX", pd.Series(dtype=float)))


def _clock(cutoff) -> str:
    if cutoff is None:
        return "none"
    return cutoff.strftime("%H:%M")


def _label(cell: tuple) -> str:
    book, cap, exit_name, stack, cutoff = cell
    return f"{book}, cap {cap}, {exit_name}, two-close {stack}, cutoff {_clock(cutoff)}"


def _check() -> None:
    rules = frozen_rules()
    if rules["grid_size"] != GRID_SIZE or len(cells()) != GRID_SIZE:
        raise SystemExit("playbook grid was not frozen")
    if "15:10 close and the 15:15 close" not in rules["setups"]["stack2"]:
        raise SystemExit("two-close trigger was not frozen")
    if rules["cutoffs"] != ["none", "15:00", "15:15"]:
        raise SystemExit("late-day cutoff was not frozen")


def _train_table(indexed, days) -> dict:
    table = {}
    total = len(cells())
    for offset, cell in enumerate(cells(), start=1):
        if offset == 1 or offset % 100 == 0 or offset == total:
            print(f"CELL {offset}/{total}", flush=True)
        table[cell] = run_cell(indexed, days, cell, 1000.0)["metrics"]
    return table


def _metrics_brief(metrics: dict) -> dict:
    keys = (
        "ending_equity",
        "trades",
        "win_rate",
        "breakeven_win_rate",
        "profit_factor",
        "sharpe",
        "max_drawdown",
        "cagr",
    )
    return {key: metrics.get(key) for key in keys}


def _pack(result: dict, stake: float, fold_list) -> dict:
    metrics = result["metrics"]
    trades = int(metrics.get("trades") or 0)
    sessions = max(len(result["equity"]), 1)
    return {
        "stake": stake,
        "metrics": _metrics_brief(metrics),
        "trades_per_day": trades / sessions,
        "worst_month": worst_month(result["equity"]),
        "folds": fold_results(result["equity"], stake, fold_list),
        "folds_profitable": sum(1 for row in fold_results(result["equity"], stake, fold_list) if row["profit"]),
        "skips": result["skips"],
    }


def _write(lines: list[str]) -> None:
    block = "\n".join(lines)
    path = Path("RESULTS.md")
    text = path.read_text() if path.exists() else ""
    if MARK_START in text and MARK_END in text:
        before = text.split(MARK_START)[0]
        after = text.split(MARK_END)[1]
        path.write_text(before + block + after.lstrip("\n"))
    else:
        path.write_text(text.rstrip() + "\n\n" + block)
    readme = Path("README.md")
    body = readme.read_text() if readme.exists() else ""
    paragraph = next((line for line in lines if line.startswith("Backtests only.")), "")
    readme_block = "\n".join([MARK_START, paragraph, "", "Full table in [RESULTS.md](RESULTS.md).", MARK_END, ""])
    if MARK_START in body and MARK_END in body:
        before = body.split(MARK_START)[0]
        after = body.split(MARK_END)[1]
        readme.write_text(before + readme_block + after.lstrip("\n"))
    else:
        readme.write_text(body.rstrip() + "\n\n" + readme_block)


def main() -> None:
    _check()
    print("LOAD", flush=True)
    minutes, info = load_minutes("SPY")
    if minutes is None:
        raise SystemExit(f"SPY minutes unavailable: {info}")
    five = to_five_minute(minutes)
    fifteen = to_fifteen_minute(minutes)
    print(f"PREPARE sessions {info.get('sessions')} rows {len(five)}", flush=True)
    prep = prepare(five)
    iv = _iv()
    print("TICKETS", flush=True)
    tickets, notes = build_tickets(prep, fifteen, iv)
    print(f"NOTES {notes}", flush=True)
    indexed = index_tickets(tickets)
    days = session_days(prep)
    fold_list = folds()
    picks = []
    fold_rows = []
    for fold in fold_list:
        train_days = [day for day in days if fold.train_start <= day <= fold.train_end]
        print(f"FOLD {fold.name} train {len(train_days)}", flush=True)
        table = _train_table(indexed, train_days)
        cell, eligible = select_cell(table)
        contrast = best_sharpe_cell(table)
        picks.append(cell)
        fold_rows.append(
            {
                "fold": fold.name,
                "train_start": fold.train_start.isoformat(),
                "train_end": fold.train_end.isoformat(),
                "test_start": fold.test_start.isoformat(),
                "test_end": fold.test_end.isoformat(),
                "cell": _label(cell),
                "eligible": eligible,
                "stability": stability_score(cell, table) if eligible else None,
                "train": _metrics_brief(table[cell]),
                "best_sharpe_cell_not_used": None if contrast is None else _label(contrast),
            }
        )
        print(f"PICK {fold.name} {_label(cell)} eligible {eligible}", flush=True)

    modal, count = modal_cell(picks)
    test_days = [day for day in days if TEST_START <= day <= SAMPLE_END]
    plan = {}
    for day in test_days:
        for fold, cell in zip(fold_list, picks):
            if fold.test_start <= day <= fold.test_end:
                _book, cap, exit_name, stack, cutoff = cell
                plan[day] = (cell_setups(cell), cap, exit_name, stack, cutoff)
                break
    print("STITCH", flush=True)
    adaptive_1 = run_plan(indexed, test_days, plan, 1000.0)
    adaptive_5 = run_plan(indexed, test_days, plan, 5000.0)
    fixed_1 = run_cell(indexed, test_days, modal, 1000.0)
    fixed_5 = run_cell(indexed, test_days, modal, 5000.0)
    dsr_adaptive = deflated_sharpe(adaptive_1["equity"], 1000.0, GRID_SIZE)
    dsr_fixed = deflated_sharpe(fixed_1["equity"], 1000.0, GRID_SIZE)
    decision = promote_decision(
        adaptive=adaptive_1["metrics"],
        fixed=fixed_1["metrics"],
        adaptive_dsr=dsr_adaptive,
        fixed_dsr=dsr_fixed,
        majority_count=count,
        fold_count=len(fold_list),
        last_cell=picks[-1],
        modal=modal,
        last_eligible=bool(fold_rows[-1]["eligible"]),
    )
    print("BASELINES", flush=True)
    signals = [item for item in find_signals(fifteen, "SPY") if item.mode == "extension"]
    vwap_1 = simulate(fifteen, signals, target="r", kind="0dte", stake=1000.0, long_only=False, iv_points=iv, start=TEST_START, end=SAMPLE_END)
    vwap_5 = simulate(fifteen, signals, target="r", kind="0dte", stake=5000.0, long_only=False, iv_points=iv, start=TEST_START, end=SAMPLE_END)
    spy_1 = spy_hold(prep, 1000.0, TEST_START, SAMPLE_END)
    spy_5 = spy_hold(prep, 5000.0, TEST_START, SAMPLE_END)
    taken = int(adaptive_1["metrics"].get("trades") or 0)
    drawn = random_plays(prep, taken, TEST_START, SAMPLE_END)
    random_tickets = []
    for play in drawn:
        point = iv.get(play.day)
        vol = None
        if point is not None and np.isfinite(point[0]) and point[0] > 0:
            from webull_bot.chart_reads.vwap_band import _iv_on

            vol = _iv_on(play.day, iv)
        ticket = price_play(prep, play, vol, ("1r",))
        if ticket is not None:
            random_tickets.append(ticket)
    random_book = run_plan(
        index_tickets(random_tickets),
        test_days,
        {day: (frozenset({"random"}), None, "1r", "off", None) for day in test_days},
        1000.0,
    )
    sheet = rule_sheet(modal, promoted=decision["promote"], fallback=not any(row["eligible"] for row in fold_rows))
    adaptive_pack = _pack(adaptive_1, 1000.0, fold_list)
    hold = adaptive_pack["metrics"]
    five = _pack(adaptive_5, 5000.0, fold_list)["metrics"]
    fixed = _pack(fixed_1, 1000.0, fold_list)["metrics"]
    vwap = vwap_1["metrics"]
    promoted = "The stitched books cleared the gate, so a separate sandbox forward book was added." if decision["promote"] else (
        "The stitched books did not clear the gate. No sandbox book was added. The existing books were not changed."
    )
    english = (
        f"Walk-forward from 2020 through {SAMPLE_END.isoformat()}, each year tuned on the prior three calendar years. "
        f"The grid is {GRID_SIZE} cells: four books, caps of 3 and 5, eight exits, the two-close 9/20 rule off or as an exit or as the put/call trigger or both, "
        f"and a late cutoff of none, 15:00, or 15:15. "
        f"The cell chosen most often is {_label(modal)} ({count} of {len(fold_list)} folds"
        f"{', a strict majority' if strict_majority(count, len(fold_list)) else ''}). "
        f"The stitched $1,000 account, using only each year's own pick, finished at {_money(hold.get('ending_equity'))} "
        f"({hold.get('trades', 0)} trades, {adaptive_pack['trades_per_day']:.2f} a day, "
        f"win {_pct(hold.get('win_rate'))} against break-even {_pct(hold.get('breakeven_win_rate'))}, "
        f"profit factor {_pf(hold.get('profit_factor'))}, Sharpe {_num(hold.get('sharpe'))}, "
        f"drawdown {_pct(hold.get('max_drawdown'))}). "
        f"From $5,000 it finished at {_money(five.get('ending_equity'))}. "
        f"Worst month {adaptive_pack['worst_month']['month']} {_pct(adaptive_pack['worst_month']['return'])}. "
        f"Profitable folds {adaptive_pack['folds_profitable']} of {len(fold_list)}. "
        f"Deflated Sharpe probability {_num(dsr_adaptive.get('dsr'))} on the stitch and {_num(dsr_fixed.get('dsr'))} on the single rule. "
        f"Replaying that one rule on every test day finished at {_money(fixed.get('ending_equity'))}. "
        f"The original 2 SD continuation, 1R, no daily cap, on the same dates finished at {_money(vwap.get('ending_equity'))} from $1,000 "
        f"and {_money(vwap_5['metrics'].get('ending_equity'))} from $5,000. "
        f"SPY bought at the first test open finished at {_money(spy_1.get('ending_equity'))} and {_money(spy_5.get('ending_equity'))}. "
        f"Seed 17 random 1R entries finished at {_money(random_book['metrics'].get('ending_equity'))}. "
        f"{promoted} {sheet}"
    )
    lines = [
        MARK_START,
        "### Combined SPY 0 DTE playbook",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. "
        + english,
        "",
        "| Fold | Pick | Eligible | Train end |",
        "|---|---|---|---:|",
    ]
    for row in fold_rows:
        lines.append(
            f"| {row['fold']} | {row['cell']} | {'yes' if row['eligible'] else 'fallback'} | {_money(row['train'].get('ending_equity'))} |"
        )
    lines += [
        "",
        sheet,
        "",
        "Not added to `config/optional_strategies.json` or `config/selected_strategies.json` unless the promote line above says a separate sandbox book was added.",
        "",
        "```",
        "python3 -m webull_bot.chart_reads.research_playbook",
        "```",
        MARK_END,
        "",
    ]
    _write(lines)
    payload = {
        "notes": notes,
        "folds": fold_rows,
        "modal": _label(modal),
        "modal_count": count,
        "decision": decision,
        "sheet": sheet,
        "adaptive_1000": adaptive_pack,
        "adaptive_5000": _pack(adaptive_5, 5000.0, fold_list),
        "fixed_1000": _pack(fixed_1, 1000.0, fold_list),
        "fixed_5000": _pack(fixed_5, 5000.0, fold_list),
        "dsr_adaptive": dsr_adaptive,
        "dsr_fixed": dsr_fixed,
        "vwap_1000": _metrics_brief(vwap),
        "vwap_5000": _metrics_brief(vwap_5["metrics"]),
        "spy_1000": _metrics_brief(spy_1),
        "spy_5000": _metrics_brief(spy_5),
        "random_1000": _metrics_brief(random_book["metrics"]),
        "books": {name: sorted(value) for name, value in BOOK_SETUPS.items()},
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(sheet, flush=True)
    print("WROTE reports/playbook.json", flush=True)


if __name__ == "__main__":
    main()
