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
    ANCHOR_CELL,
    CONTRACTS,
    GRID_SIZE,
    BOOK_SETUPS,
    cell_setups,
    cells,
    day_trade_stats,
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
    unpack_cell,
    worst_month,
    best_sharpe_cell,
    build_tickets,
    spy_hold,
)
from webull_bot.chart_reads.vwap_band import HOLDOUT_START, TRAIN_END, find_signals, passes_gate, simulate
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


def _contract_name(dte: int, hold: str) -> str:
    return f"{dte}dte-{hold}"


def _iv_frame() -> tuple[dict, dict]:
    """(VIX1D-else-VIX, VIX only). 0-1 DTE uses the first. 3-7 DTE uses the second."""
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
    vix = closes.get("VIX", pd.Series(dtype=float))
    vix1d = closes.get("VIX1D", pd.Series(dtype=float))
    return prior_iv(vix1d, vix), prior_iv(pd.Series(dtype=float), vix)


def _clock(cutoff) -> str:
    if cutoff is None:
        return "none"
    return cutoff.strftime("%H:%M")


def _label(cell: tuple) -> str:
    book, cap, exit_name, stack, cutoff, dte, hold = unpack_cell(cell)
    return (
        f"{book}, cap {cap}, {exit_name}, two-close {stack}, cutoff {_clock(cutoff)}, "
        f"{_contract_name(dte, hold)}"
    )


def _check() -> None:
    rules = frozen_rules()
    if rules["grid_size"] != GRID_SIZE or len(cells()) != GRID_SIZE:
        raise SystemExit("playbook grid was not frozen")
    if "15:10 close and the 15:15 close" not in rules["setups"]["stack2"]:
        raise SystemExit("two-close trigger was not frozen")
    if rules["cutoffs"] != ["none", "15:00", "15:15"]:
        raise SystemExit("late-day cutoff was not frozen")
    if rules["contracts"] != [f"{dte}dte-{hold}" for dte, hold in CONTRACTS]:
        raise SystemExit("expiry grid was not frozen")
    if rules["grid_size"] != 5376:
        raise SystemExit("expiry grid size was not frozen")


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


def _expiry_table(indexed, days) -> list[dict]:
    """Train and holdout for the pre-declared anchor, one row per contract. Not a second search."""
    train_days = [day for day in days if day <= TRAIN_END]
    hold_days = [day for day in days if HOLDOUT_START <= day <= SAMPLE_END]
    rows = []
    for dte, hold in CONTRACTS:
        name = _contract_name(dte, hold)
        print(f"EXPIRY {name}", flush=True)
        cell = (*ANCHOR_CELL, dte, hold)
        packed = {"contract": name, "dte": dte, "hold": hold}
        for label, stake, window in (
            ("train_1000", 1000.0, train_days),
            ("train_5000", 5000.0, train_days),
            ("hold_1000", 1000.0, hold_days),
            ("hold_5000", 5000.0, hold_days),
        ):
            result = run_cell(indexed, window, cell, stake)
            brief = _metrics_brief(result["metrics"])
            sessions = max(len(result["equity"]), 1)
            trades = int(brief.get("trades") or 0)
            brief["trades_per_day"] = trades / sessions
            brief["pdt"] = day_trade_stats(result["spans"], window)
            packed[label] = brief
            packed[label + "_gate"] = bool(passes_gate(result["metrics"]))
        packed["robust"] = bool(packed["train_1000_gate"] and packed["hold_1000_gate"])
        rows.append(packed)
    return rows


def _best_expiry(rows: list[dict]) -> dict | None:
    """Highest holdout Sharpe among contracts that clear both windows. None of them is still reported."""
    if not rows:
        return None

    def sharpe(row: dict) -> float:
        value = row["hold_1000"].get("sharpe")
        if value is None or not np.isfinite(value):
            return -1e9
        return float(value)

    robust = [row for row in rows if row["robust"]]
    pool = robust or rows
    return max(pool, key=sharpe)


def _expiry_sentence(rows: list[dict], best: dict | None) -> str:
    if best is None:
        return "No expiry row was scored."
    robust = [row["contract"] for row in rows if row["robust"]]
    hold = best["hold_1000"]
    train = best["train_1000"]
    if robust:
        which = (
            f"{best['contract']} is the robust contract with the highest holdout Sharpe. "
            f"Robust on both windows: {', '.join(robust)}."
        )
    else:
        which = (
            f"No contract clears the published gate on both the train window and the holdout. "
            f"{best['contract']} has the highest holdout Sharpe on the anchor and is not a promotion."
        )
    pdt = hold.get("pdt") or {}
    return (
        "The expiry table holds every other choice at trend, cap 3, 1R, the two-close rule off, and no late cutoff. "
        f"{which} "
        f"On that anchor the $1,000 holdout finished at {_money(hold.get('ending_equity'))} "
        f"({hold.get('trades', 0)} trades, {hold.get('trades_per_day', 0):.2f} a day, "
        f"win {_pct(hold.get('win_rate'))} against break-even {_pct(hold.get('breakeven_win_rate'))}, "
        f"profit factor {_pf(hold.get('profit_factor'))}, Sharpe {_num(hold.get('sharpe'))}, "
        f"drawdown {_pct(hold.get('max_drawdown'))}). "
        f"The same anchor in training finished at {_money(train.get('ending_equity'))}. "
        f"From $5,000 the holdout finished at {_money(best['hold_5000'].get('ending_equity'))} "
        f"and training at {_money(best['train_5000'].get('ending_equity'))}. "
        f"Holdout same-day round trips {pdt.get('day_trades', 0)}, overnight holds {pdt.get('overnight_holds', 0)}, "
        f"worst same-day count in any five sessions {pdt.get('worst_day_trades_in_5_sessions', 0)}, "
        f"five-session windows over 3 day trades {pdt.get('windows_over_3', 0)} of {pdt.get('windows', 0)}. "
        "A $1,000 or $5,000 margin account would be under the $25,000 pattern-day-trader line. "
        "This test is a cash account: it does not refuse the fourth day trade, and a sale settles the next session. "
        "An overnight hold that closes on a later session is not a day trade. The debit stays invested until that exit."
    )


def _expiry_lines(rows: list[dict]) -> list[str]:
    lines = [
        "Expiry comparison on the pre-declared anchor (trend, cap 3, 1R, two-close off, no late cutoff). "
        "0 DTE and 1 DTE use prior VIX1D, or prior VIX when that print is missing. 3 DTE and 7 DTE use prior VIX. "
        "Half-spread is the greater of $0.01 and 1.5% of the mid.",
        "",
        "| Contract | Window | Trades/day | Win | Break-even | PF | Sharpe | Max DD | $1k end | $5k end |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        for window, key, five_key in (("train", "train_1000", "train_5000"), ("holdout", "hold_1000", "hold_5000")):
            metrics = row[key]
            five = row[five_key]
            lines.append(
                f"| {row['contract']} | {window} | {metrics.get('trades_per_day', 0):.2f} | "
                f"{_pct(metrics.get('win_rate'))} | {_pct(metrics.get('breakeven_win_rate'))} | "
                f"{_pf(metrics.get('profit_factor'))} | {_num(metrics.get('sharpe'))} | "
                f"{_pct(metrics.get('max_drawdown'))} | {_money(metrics.get('ending_equity'))} | "
                f"{_money(five.get('ending_equity'))} |"
            )
    return lines


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
    iv, iv_long = _iv_frame()
    print("TICKETS", flush=True)
    tickets, notes = build_tickets(prep, fifteen, iv, iv_long=iv_long)
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
                _book, cap, exit_name, stack, cutoff, dte, hold = unpack_cell(cell)
                plan[day] = (cell_setups(cell), cap, exit_name, stack, cutoff, dte, hold)
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
    print("EXPIRY", flush=True)
    expiry_rows = _expiry_table(indexed, days)
    best = _best_expiry(expiry_rows)
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
        f"a late cutoff of none, 15:00, or 15:15, and seven contracts: 0 DTE flat, plus 1, 3, and 7 DTE each flat and overnight. "
        f"0 DTE and 1 DTE use prior VIX1D, otherwise prior VIX. 3 DTE and 7 DTE use prior VIX. "
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
        f"{promoted} {_expiry_sentence(expiry_rows, best)} {sheet}"
    )
    lines = [
        MARK_START,
        "### Combined SPY playbook",
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
        *_expiry_lines(expiry_rows),
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
        "expiry": expiry_rows,
        "expiry_best": None if best is None else best["contract"],
        "books": {name: sorted(value) for name, value in BOOK_SETUPS.items()},
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(sheet, flush=True)
    print("WROTE reports/playbook.json", flush=True)


if __name__ == "__main__":
    main()
