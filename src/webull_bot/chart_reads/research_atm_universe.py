"""Re-score the frozen ATM exit grid on a pre-registered universe.

The exit grid is the one in ``atm_exit`` (1,293 cells). It is not enlarged.
The cell for the gate is the highest training Sharpe on the point-in-time
Dow, among cells with at least 30 training trades. The liquid blue-chip
list is a survivorship-biased diagnostic: pooled and per symbol, using that
same cell. A cell chosen on the liquid list's own training is reported and
is not the gate. Neither holdout is visible when the cell is chosen.

A chop cell is wired only when the Dow holdout meets the same hold-up bar
as the earlier search. The options sub-book already scans the liquid list.
This run does not replace the published ATM section.

Run: ``python3 -m webull_bot.chart_reads.research_atm_universe``
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.atm_exit import frozen_grid, public_row, score_cell
from webull_bot.chart_reads.bounce import find_bounces, partial_params
from webull_bot.chart_reads.breakouts import find_breakout_setups
from webull_bot.chart_reads.chop_v2 import find_chop_breakouts
from webull_bot.chart_reads.liquid import LIQUID_BLUE_CHIPS, dow_members_between
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DAILY_DEFAULTS
from webull_bot.chart_reads.research import END, _cells, detect_all
from webull_bot.chart_reads.research_atm_exit import (
    _choose_pooled,
    _finish_book,
    _json,
    _money,
    _prepare_book,
)
from webull_bot.chart_reads.research_daily import (
    DOWNLOAD_END,
    HISTORY_START,
    IS_END,
    OOS_START,
    SAMPLE_END,
    SCORE_FROM,
    _naive,
    load_daily,
)
from webull_bot.chart_reads.research_exits import _ab_window, _bar_day
from webull_bot.chart_reads.research_levels import _collect_daily
from webull_bot.chart_reads.research_scale import _gate_line, _num, _pct, _pf
from webull_bot.chart_reads.trendline import find_trend_setups
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.mtf_vwap.detect import rth
from webull_bot.universe_dow import is_member

START = "<!-- CHART_READS_ATM_UNIVERSE_START -->"
END_MARK = "<!-- CHART_READS_ATM_UNIVERSE_END -->"
SELECTION_PATH = Path("reports/atm_universe_selection.json")
REPORT_PATH = Path("reports/chart_reads_atm_universe.json")
GATE = "dow_point_in_time"


def _pit(setups: list) -> list:
    return [setup for setup in setups if is_member(setup.symbol, _bar_day(setup.signal_time))]


def _load_hourly(symbols: list[str]) -> tuple[dict, dict, list[str]]:
    provider = YFinanceProvider("data/cache")
    end = pd.Timestamp(END)
    start = (end - pd.Timedelta(days=720)).date().isoformat()
    print(f"loading hourly bars for {len(symbols)} symbols", flush=True)
    daily = provider.history(symbols, "2023-01-01", END, interval="1d")
    hourly = provider.history(symbols, start, END, interval="60m")
    missing = []
    daily_out = {}
    hourly_out = {}
    for symbol in symbols:
        day = daily.get(symbol)
        hour = hourly.get(symbol)
        if day is None or hour is None or len(hour) <= 50:
            missing.append(symbol)
            continue
        daily_out[symbol] = day
        hourly_out[symbol] = hour
    return daily_out, hourly_out, missing


def _add_daily(frames: dict) -> list[str]:
    missing = [symbol for symbol in LIQUID_BLUE_CHIPS if symbol not in frames]
    if not missing:
        return []
    provider = YFinanceProvider("data/cache/daily_long")
    raw = provider.history(missing, HISTORY_START, DOWNLOAD_END, interval="1d")
    still = []
    for symbol in missing:
        frame = raw.get(symbol)
        if frame is None or frame.empty:
            still.append(symbol)
            continue
        normal = _naive(frame)
        if len(normal) < 60:
            still.append(symbol)
            continue
        frames[symbol] = normal
    return still


def _chop(frames: dict) -> list:
    found = []
    for symbol, frame in frames.items():
        if frame is None or len(frame) < 30:
            continue
        bars = rth(frame)
        if bars is None or len(bars) < 30:
            continue
        found.extend(find_chop_breakouts(bars, symbol=symbol))
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    return found


def _liquid_daily(frames: dict, builder, params) -> list:
    found = []
    for symbol in LIQUID_BLUE_CHIPS:
        frame = frames.get(symbol)
        if frame is None or len(frame) < 80:
            continue
        if params is None:
            setups = builder(frame, symbol)
        else:
            setups = builder(frame, params, symbol=symbol)
        setups = [setup for setup in setups if _bar_day(setup.fill_time) >= SCORE_FROM]
        found.extend(setups)
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    return found


def _spec(name, clock, setups, frames, daily, base, session_filter, slice_fn, is_window, oos_window, blurb) -> dict:
    return {
        "name": name,
        "clock": clock,
        "setups": setups,
        "frames": frames,
        "daily": daily,
        "base": base,
        "session_filter": session_filter,
        "slice": slice_fn,
        "is_window": is_window,
        "oos_window": oos_window,
        "blurb": blurb,
    }


def _per_symbol(paths, cell, equity, max_hold, pdt, symbols) -> list[dict]:
    rows = []
    for symbol in symbols:
        subset = [path for path in paths if path.symbol == symbol]
        if not subset or not np.isfinite(equity) or equity <= 0.0:
            rows.append(
                {
                    "symbol": symbol,
                    "trades": 0,
                    "expectancy": None,
                    "profit_factor": None,
                    "sharpe": None,
                    "max_drawdown": None,
                    "ending_equity": None,
                    "win_rate": None,
                    "starting_equity": None if not np.isfinite(equity) else float(equity),
                }
            )
            continue
        row = score_cell(
            subset,
            cell,
            starting_equity=float(equity),
            max_hold=int(max_hold),
            pdt_prospective=bool(pdt),
        )
        item = public_row(row)
        item["symbol"] = symbol
        rows.append(item)
    return rows


def _symbol_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        trades = int(row.get("trades") or 0)
        if trades == 0:
            lines.append(f"| {row['symbol']} | 0 | n/a | n/a | n/a | n/a | n/a | n/a |")
            continue
        lines.append(
            "| {symbol} | {trades} | {win} | {exp} | {pf} | {sharpe} | {dd} | {ending} |".format(
                symbol=row["symbol"],
                trades=trades,
                win=_pct(row.get("win_rate")),
                exp=_money(row.get("expectancy")),
                pf=_pf(row.get("profit_factor")),
                sharpe=_num(row.get("sharpe")),
                dd=_pct(row.get("max_drawdown")),
                ending=_money(row.get("ending_equity")),
            )
        )
    return lines


def _book_line(book: dict) -> str:
    hold = book.get("holdout") or {}
    decision = book.get("decision") or {}
    return (
        f"{book['name']}: `{decision.get('label')}` on {int(hold.get('trades') or 0)} holdout trades, "
        f"expectancy {_money(hold.get('expectancy'))}, profit factor {_pf(hold.get('profit_factor'))}, "
        f"Sharpe {_num(hold.get('sharpe'))}, max drawdown {_pct(hold.get('max_drawdown'))}, "
        f"ending {_money(hold.get('ending_equity'))}. {_gate_line(hold)}"
    )


def render(payload: dict) -> str:
    lines = [
        "## ATM exits on the liquid list and the Dow gate",
        "",
        "DOES NOT CHANGE THE EXIT GRID. The 1,293 cells were already frozen. "
        "This run only changes the symbol universe. The liquid list was written down before the holdout was scored: "
        + ", ".join(LIQUID_BLUE_CHIPS)
        + ". SPY and QQQ are index references. That list is a 2026 snapshot and is survivorship-biased. "
        "The gate is point-in-time Dow membership on the signal day, from `universe_dow`. "
        "There is no point-in-time S&P 500 file here, so a name that was never in the Dow is reported on the liquid list and cannot pass the gate by itself. "
        "The cell is the highest training Sharpe on the Dow book among cells with at least 30 training trades. "
        "The liquid list is then scored with that same cell, pooled and per symbol. "
        "A cell chosen on the liquid list's own training is a sensitivity. It is not the gate. "
        "Per-symbol rows were not used to pick the cell. Costs are the spread haircut, the option fees, and a gap fill at the worse bid.",
        "",
        "### Dow point-in-time gate",
        "",
    ]
    for book in payload["gate_books"]:
        lines.append(_book_line(book))
        lines.append("")
        lines.append("Holdout by symbol, same Dow cell and the Dow sized equity. A zero means that name had no holdout trade.")
        lines.append("")
        lines.extend(_symbol_table(book.get("symbols") or []))
        lines.append("")
    lines.append(
        f"Pooled cell across the six Dow books, chosen before the holdout: `{payload['pooled'].get('label')}`. "
        "It does not replace a book's cell."
    )
    lines.append("")
    lines.append("### Liquid list, same Dow cell")
    lines.append("")
    lines.append(
        "Each row uses the Dow book's chosen cell and the liquid list's own training equity at that cell's stop. "
        "This is the survivor snapshot. It is not the gate."
    )
    lines.append("")
    for book in payload["liquid_books"]:
        transfer = book.get("transfer") or {}
        lines.append(
            f"{book['name']}: {int(transfer.get('trades') or 0)} holdout trades, "
            f"expectancy {_money(transfer.get('expectancy'))}, profit factor {_pf(transfer.get('profit_factor'))}, "
            f"Sharpe {_num(transfer.get('sharpe'))}, max drawdown {_pct(transfer.get('max_drawdown'))}, "
            f"ending {_money(transfer.get('ending_equity'))}."
        )
        lines.append("")
        lines.extend(_symbol_table(book.get("symbols") or []))
        lines.append("")
        sens = book.get("holdout") or {}
        lines.append(
            f"Sensitivity, cell chosen on this list's training only: `{book['decision'].get('label')}`. "
            f"Holdout {int(sens.get('trades') or 0)} trades, expectancy {_money(sens.get('expectancy'))}, "
            f"Sharpe {_num(sens.get('sharpe'))}, max drawdown {_pct(sens.get('max_drawdown'))}, "
            f"ending {_money(sens.get('ending_equity'))}. Not used for the gate."
        )
        lines.append("")
    chop = payload["chop"]
    lines.append("### Wiring")
    lines.append("")
    if payload["wired"]:
        lines.append(
            f"The Dow chop book's cell holds up (`{payload['wired_label']}`), so that exit is the options sub-book. "
            "Live trading stays off."
        )
    else:
        reasons = ". ".join(chop.get("hold_reasons") or [])
        lines.append(
            "The Dow chop book's cell does not hold up"
            + (f" ({reasons})." if reasons else ".")
            + " The sandbox options sub-book stays the corrected ladder: 21 DTE, delta 0.45, "
            "contracts 1-4 at the -20% stop, runner break-even only after +15%, target +100%. "
            "It now scans the liquid list above. The share book stays on the named list. Live trading stays off."
        )
    lines.append("")
    lines.append(
        "No Dow-gate cell is described as an edge unless its holdout expectancy is positive and ending equity is above the start. "
        "The earlier ATM section, on the named hourly list and the Dow daily books, is unchanged."
    )
    lines.append("")
    lines.append("Not added to `config/optional_strategies.json`. The default book is still dual momentum.")
    return "\n".join(lines).rstrip() + "\n"


def write_report(text: str, path: Path) -> None:
    body = path.read_text() if path.exists() else ""
    block = f"{START}\n{text.rstrip()}\n{END_MARK}\n"
    if START in body and END_MARK in body:
        pre, rest = body.split(START, 1)
        _, post = rest.split(END_MARK, 1)
        path.write_text(pre.rstrip() + "\n\n" + block + post.lstrip("\n"))
        return
    marker = "<!-- CHART_READS_ATM_EXIT_END -->"
    if marker in body:
        pre, post = body.split(marker, 1)
        path.write_text(pre + marker + "\n\n" + block + post.lstrip("\n"))
        return
    path.write_text(body.rstrip() + "\n\n" + block)


def _selection(gate, liquid, pooled) -> dict:
    def _books(items):
        return [
            {
                "name": item["spec"]["name"],
                "label": item["decision"]["label"],
                "rule": item["decision"]["rule"],
                "fallback": item["decision"]["fallback"],
                "eligible": item["decision"]["eligible"],
                "train": public_row(item["decision"]["row"]) if item["decision"]["row"] else None,
            }
            for item in items
        ]

    return {
        "frozen_before_holdout": True,
        "universe_registered_before_scoring": True,
        "liquid_blue_chips": list(LIQUID_BLUE_CHIPS),
        "gate": GATE,
        "cells": len(frozen_grid("hourly")),
        "rule": "highest training Sharpe among cells with at least 30 training trades",
        "books": _books(gate),
        "liquid_diagnostic": _books(liquid),
        "pooled": {
            "label": pooled.get("label"),
            "rule": pooled.get("rule"),
            "fallback": pooled.get("fallback"),
            "row": pooled.get("row"),
        },
    }


def _attach_symbols(book: dict, prepared: dict, symbols: list[str]) -> None:
    decision = prepared["decision"]["label"]
    if not decision:
        book["symbols"] = _per_symbol([], None, float("nan"), prepared["max_hold"], prepared["pdt"], symbols)
        return
    cell = next(item for item in prepared["grid"] if item.label == decision)
    equity = prepared["equities"].get(float(cell.stop), float("nan"))
    book["symbols"] = _per_symbol(
        prepared.get("oos_paths") or [],
        cell,
        equity,
        prepared["max_hold"],
        prepared["pdt"],
        symbols,
    )


def _transfer(prepared: dict, label: str | None) -> dict:
    if not label:
        return {}
    cell = next((item for item in prepared["grid"] if item.label == label), None)
    paths = prepared.get("oos_paths") or []
    if cell is None:
        return {}
    equity = prepared["equities"].get(float(cell.stop), float("nan"))
    if not np.isfinite(equity) or equity <= 0.0:
        return public_row({"label": label, "trades": 0, "expectancy": None, "ending_equity": None})
    return public_row(
        score_cell(
            paths,
            cell,
            starting_equity=float(equity),
            max_hold=prepared["max_hold"],
            pdt_prospective=prepared["pdt"],
        )
    )


def main() -> None:
    from webull_bot.chart_reads.research import _slice as intraday_slice
    from webull_bot.chart_reads.research_daily import _slice as daily_slice

    print("LIQUID LIST REGISTERED", ", ".join(LIQUID_BLUE_CHIPS), flush=True)
    print("GATE", GATE, flush=True)
    print("loading daily bars", flush=True)
    daily_frames, missing = load_daily()
    extra_missing = _add_daily(daily_frames)
    print(f"  {len(daily_frames)} symbols, missing {missing}, liquid missing {extra_missing}", flush=True)

    print("detecting Dow bounces", flush=True)
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
    liquid_bounces = _liquid_daily(daily_frames, find_bounces, None)
    print(f"  Dow bounce {len(bounces)} liquid bounce {len(liquid_bounces)}", flush=True)

    print("detecting C and D", flush=True)
    trend = _collect_daily(daily_frames, find_trend_setups, DAILY_DEFAULTS)
    ranges = _collect_daily(daily_frames, find_breakout_setups, BREAKOUT_DEFAULTS)
    liquid_trend = _liquid_daily(daily_frames, find_trend_setups, DAILY_DEFAULTS)
    liquid_ranges = _liquid_daily(daily_frames, find_breakout_setups, BREAKOUT_DEFAULTS)
    print(
        f"  Dow C {len(trend)} D {len(ranges)} liquid C {len(liquid_trend)} D {len(liquid_ranges)}",
        flush=True,
    )

    hourly_names = list(dict.fromkeys([*dow_members_between(date(2024, 1, 1), SAMPLE_END), *LIQUID_BLUE_CHIPS]))
    daily_short, hourly, hourly_missing = _load_hourly(hourly_names)
    print(f"  hourly present {len(hourly)} missing {hourly_missing}", flush=True)
    spy = hourly.get("SPY")
    if spy is not None and len(spy):
        is_ab, oos_ab = _ab_window({"SPY": spy})
    else:
        is_ab, oos_ab = _ab_window(hourly)
    print(f"  hourly train {is_ab[0]} through {is_ab[1]}; holdout {oos_ab[0]} through {oos_ab[1]}", flush=True)

    gate_names = set(dow_members_between(is_ab[0], oos_ab[1]))
    gate_hourly = {symbol: frame for symbol, frame in hourly.items() if symbol in gate_names}
    gate_daily_short = {symbol: frame for symbol, frame in daily_short.items() if symbol in gate_names}
    if "SPY" in daily_short:
        gate_daily_short["SPY"] = daily_short["SPY"]
    liquid_hourly = {symbol: hourly[symbol] for symbol in LIQUID_BLUE_CHIPS if symbol in hourly}
    liquid_daily_short = {symbol: daily_short[symbol] for symbol in LIQUID_BLUE_CHIPS if symbol in daily_short}

    print("detecting chop and A/B", flush=True)
    gate_chop = _pit(_chop(gate_hourly))
    liquid_chop = _chop(liquid_hourly)
    ab_params = _cells("60m")[0]
    gate_ab = detect_all(gate_hourly, gate_daily_short, {}, ab_params)
    liquid_ab = detect_all(liquid_hourly, liquid_daily_short, {}, ab_params)
    gate_a = _pit([setup for setup in gate_ab if setup.kind == "A"])
    gate_b = _pit([setup for setup in gate_ab if setup.kind == "B"])
    liquid_a = [setup for setup in liquid_ab if setup.kind == "A"]
    liquid_b = [setup for setup in liquid_ab if setup.kind == "B"]
    print(
        f"  Dow chop {len(gate_chop)} A {len(gate_a)} B {len(gate_b)}; "
        f"liquid chop {len(liquid_chop)} A {len(liquid_a)} B {len(liquid_b)}",
        flush=True,
    )

    chop_params = dict(ab_params)
    chop_params["expression"] = "single"
    daily_window = ((SCORE_FROM, IS_END), (OOS_START, SAMPLE_END))

    def _pair(title, clock, gate_setups, liquid_setups, frames_g, frames_l, daily_g, daily_l, base, session_filter, slice_fn, windows):
        is_window, oos_window = windows
        gate = _spec(
            f"{title}, Dow point-in-time",
            clock,
            gate_setups,
            frames_g,
            daily_g,
            dict(base),
            session_filter,
            slice_fn,
            is_window,
            oos_window,
            f"{len(gate_setups)} Dow point-in-time signals. The gate.",
        )
        liquid = _spec(
            f"{title}, liquid list",
            clock,
            liquid_setups,
            frames_l,
            daily_l,
            dict(base),
            session_filter,
            slice_fn,
            is_window,
            oos_window,
            f"{len(liquid_setups)} signals on the pre-registered liquid list. Not the gate.",
        )
        return gate, liquid

    pairs = [
        _pair("Chop-v2 60-minute", "hourly", gate_chop, liquid_chop, gate_hourly, liquid_hourly, gate_daily_short, liquid_daily_short, chop_params, True, intraday_slice, (is_ab, oos_ab)),
        _pair("Partial bounce", "daily", bounces, liquid_bounces, daily_frames, daily_frames, daily_frames, daily_frames, partial_params(), False, daily_slice, daily_window),
        _pair("A, 60-minute", "hourly", gate_a, liquid_a, gate_hourly, liquid_hourly, gate_daily_short, liquid_daily_short, ab_params, True, intraday_slice, (is_ab, oos_ab)),
        _pair("B, 60-minute", "hourly", gate_b, liquid_b, gate_hourly, liquid_hourly, gate_daily_short, liquid_daily_short, ab_params, True, intraday_slice, (is_ab, oos_ab)),
        _pair("C, daily", "daily", trend, liquid_trend, daily_frames, daily_frames, daily_frames, daily_frames, DAILY_DEFAULTS, False, daily_slice, daily_window),
        _pair("D, daily", "daily", ranges, liquid_ranges, daily_frames, daily_frames, daily_frames, daily_frames, BREAKOUT_DEFAULTS, False, daily_slice, daily_window),
    ]
    print("training grids, before any holdout", flush=True)
    gate_prepared = [_prepare_book(pair[0]) for pair in pairs]
    pooled = _choose_pooled([item["rows"] for item in gate_prepared])
    liquid_prepared = [_prepare_book(pair[1]) for pair in pairs]
    selection = _selection(gate_prepared, liquid_prepared, pooled)
    SELECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SELECTION_PATH.write_text(json.dumps(selection, indent=2, default=_json) + "\n")
    print("SELECTION FROZEN before holdout", flush=True)
    saved = json.loads(SELECTION_PATH.read_text())
    if saved["liquid_blue_chips"] != list(LIQUID_BLUE_CHIPS):
        raise RuntimeError("selection file lost the registered list")
    if [item["label"] for item in saved["books"]] != [item["decision"]["label"] for item in gate_prepared]:
        raise RuntimeError("selection file does not match the Dow training choice")
    if [item["label"] for item in saved["liquid_diagnostic"]] != [item["decision"]["label"] for item in liquid_prepared]:
        raise RuntimeError("selection file does not match the liquid training choice")

    print("holdout, after the freeze", flush=True)
    gate_books = [_finish_book(item, pooled.get("label")) for item in gate_prepared]
    for book, prepared in zip(gate_books, gate_prepared):
        symbols = sorted({path.symbol for path in prepared["is_paths"]} | {path.symbol for path in prepared.get("oos_paths") or []})
        _attach_symbols(book, prepared, symbols)
    liquid_books = []
    for prepared, gate in zip(liquid_prepared, gate_prepared):
        book = _finish_book(prepared, gate["decision"]["label"])
        book["transfer"] = book.get("pooled_holdout") or _transfer(prepared, gate["decision"]["label"])
        cell_label = gate["decision"]["label"]
        cell = next((item for item in prepared["grid"] if item.label == cell_label), None)
        equity = prepared["equities"].get(float(cell.stop), float("nan")) if cell is not None else float("nan")
        if cell is None:
            book["symbols"] = _per_symbol([], None, float("nan"), prepared["max_hold"], prepared["pdt"], list(LIQUID_BLUE_CHIPS))
        else:
            book["symbols"] = _per_symbol(
                prepared.get("oos_paths") or [],
                cell,
                equity,
                prepared["max_hold"],
                prepared["pdt"],
                list(LIQUID_BLUE_CHIPS),
            )
        liquid_books.append(book)

    chop = next(book for book in gate_books if book["name"].startswith("Chop-v2"))
    wired = bool(chop["holds_up"] and chop["decision"]["label"])
    payload = {
        "gate": GATE,
        "liquid_blue_chips": list(LIQUID_BLUE_CHIPS),
        "cells": len(frozen_grid("hourly")),
        "gate_books": gate_books,
        "liquid_books": liquid_books,
        "pooled": {
            "label": pooled.get("label"),
            "rule": pooled.get("rule"),
            "fallback": pooled.get("fallback"),
        },
        "wired": wired,
        "wired_label": chop["decision"]["label"] if wired else None,
        "chop": {"holds_up": chop["holds_up"], "hold_reasons": chop.get("hold_reasons")},
    }
    text = render(payload)
    write_report(text, Path("RESULTS.md"))
    stored = json.loads(json.dumps(payload, default=_json))
    for book in stored["gate_books"] + stored["liquid_books"]:
        for key in ("train_view", "holdout_view", "random_view", "spy_view", "cash_view", "training_rows"):
            book.pop(key, None)
    REPORT_PATH.write_text(json.dumps(stored, indent=2, default=_json) + "\n")
    print(text)
    if wired:
        print("WIRE chop options sub-book:", chop["decision"]["label"], flush=True)
    else:
        print("DO NOT WIRE the exit. Corrected ladder stays. Liquid symbol list stays.", flush=True)


if __name__ == "__main__":
    main()
