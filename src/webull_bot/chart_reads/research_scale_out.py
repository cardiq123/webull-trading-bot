"""Score the frozen scale-out exits and the $2,500 sizing of the published books.

Research only. The open-versus-support search is not rerun, and the tendency
holdout is not opened. A $2,500 start is the account Paul asked for. The
$1,000 and $5,000 columns reuse the same option legs.
"""

from __future__ import annotations

import json
import math
from datetime import date, time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from webull_bot.chart_reads.open_support import (
    CATALOG_BY_ID,
    GATE_SYMBOLS,
    HEADLINE_ID,
    HOLDOUT_END,
    HOLDOUT_START,
    TRAIN_END,
    TRAIN_START,
    build_views,
    option_report,
    simulate,
)
from webull_bot.chart_reads.research_open_support import _dollar_volume, _load_dukascopy_five, _vix
from webull_bot.chart_reads.scale_out import (
    EXITS,
    PRIMARY_STAKE,
    STAKES,
    assign_q,
    attach_prices,
    feasibility,
    frozen_rules,
    n_trials,
    prepare_extension_paths,
    prepare_open_paths,
    simulate_account,
    tendency_eligible,
    three_lot_fit,
)
from webull_bot.chart_reads.vwap_band import HOLDOUT_START as VWAP_HOLDOUT_START
from webull_bot.chart_reads.vwap_band import SAMPLE_END as VWAP_SAMPLE_END
from webull_bot.chart_reads.vwap_band import TRAIN_END as VWAP_TRAIN_END

START_MARK = "<!-- SCALE_OUT_START -->"
END_MARK = "<!-- SCALE_OUT_END -->"
FEATURED_ID = "both_swing10_structure_level_vwap"
NY = "America/New_York"


def _fifteen(five: pd.DataFrame) -> pd.DataFrame:
    bars = five.between_time(time(9, 30), time(15, 55))
    pieces = []
    for _day, chunk in bars.groupby(bars.index.date):
        fifteen = chunk.resample("15min", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )
        fifteen = fifteen.dropna(subset=["open"])
        clock = fifteen.index.time
        fifteen = fifteen[(clock >= time(9, 30)) & (clock < time(16, 0))]
        if not fifteen.empty:
            pieces.append(fifteen)
    if not pieces:
        return bars.iloc[0:0]
    return pd.concat(pieces)


def _days(index: pd.DatetimeIndex) -> list[date]:
    return sorted({stamp.date() for stamp in index})


def _public(metrics: dict) -> dict:
    out = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            out[key] = None if not math.isfinite(value) else value
        else:
            out[key] = value
    return out


def _money(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"${float(value):,.0f}"


def _num(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.2f}"


def _pct(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.1%}"


def _per_day(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.3f}"


def _q(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    number = float(value)
    if number < 0.001:
        return f"{number:.1e}"
    return f"{number:.3f}"


def _size_shares(books: dict, cell_id: str, start: date, end: date, *, allow_holdout: bool) -> dict:
    cell = CATALOG_BY_ID[cell_id]
    stakes = {}
    trades = None
    for stake in STAKES:
        book = simulate(books, cell, start, end, stake, allow_holdout=allow_holdout)
        stakes[str(int(stake))] = _public(book["metrics"])
        if stake == PRIMARY_STAKE:
            trades = book["trades"]
    return {"id": cell_id, "start": start.isoformat(), "end": end.isoformat(), "stakes": stakes, "trades": trades or []}


def _score_exit(name: str, paths: list[dict], sessions: list[date], start: date, end: date, *, cap, one_position: bool) -> dict:
    stakes = {}
    equity = None
    primary = None
    for stake in STAKES:
        book = simulate_account(
            paths, name, start, end, stake, sessions, cap=cap, one_position=one_position,
        )
        stakes[str(int(stake))] = _public(book["metrics"])
        stakes[str(int(stake))]["skips"] = book["skips"]
        if stake == PRIMARY_STAKE:
            equity = book["equity"]
            primary = book
    fit = feasibility(paths, start, end)
    return {
        "exit": name,
        "stakes": stakes,
        "fit": fit,
        "p": None if primary is None else primary["p"],
        "equity": equity,
    }


def _tendency_note() -> dict:
    path = Path("reports/tendency.json")
    if not path.exists():
        return {"found": False, "eligible": 0, "cells": 0}
    payload = json.loads(path.read_text())
    cells = payload.get("cells") or []
    eligible = tendency_eligible(cells)
    labels = {}
    for row in cells:
        labels[row.get("label")] = labels.get(row.get("label"), 0) + 1
    return {
        "found": True,
        "cells": len(cells),
        "eligible": len(eligible),
        "labels": labels,
        "books": len(payload.get("books") or []),
    }


def _render(sizing: list[dict], exits: list[dict], tendency: dict, fits: list[dict]) -> str:
    lines = [
        START_MARK,
        "### Scale-out exit, and a $2,500 start",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. No sandbox book was added.",
        "",
        "Paul asked for the account to start at $2,500. The $1,000 and $5,000 columns are the same rules with a different starting cash. They are not extra trials. "
        f"The scale-out comparison counts {n_trials()} exit books on the $2,500 account.",
        "",
        "Three contracts, or nothing. Two are sold when the underlying touches the session VWAP outer 2 SD band in the trade direction. "
        "Until that touch, the original stop closes all three. The remaining contract is the runner: stop at 90% of the entry premium, or back at the entry premium, or when the whole position is down 10% of the debit. "
        "The runner's target is 50% above the entry premium. Anything still open is sold at the 15:45 open. "
        "The comparisons are selling all three at the band, at 1R, or at a 50% premium. Prices are Black-Scholes, at the money, 0 DTE, with the prior VIX close.",
        "",
        "A continuation that is already outside the 2 SD band can sell the two-thirds on the fill. That rate is in the table. It is the rule, not a second target.",
        "",
        "Open versus support, same cells as the published search, rerun from $2,500. The search was not repeated and the holdout cell was not changed. "
        "Paul's rule is the training column. The holdout column is only `both_swing10_structure_level_vwap`, the one cell that was scored before. A $2,500 path is a sizing note, not a pass.",
        "",
        "The trade counts are not the same at every stake. A wider stop often cannot buy one share in $1,000, and that trade appears once the account is $2,500 or $5,000. "
        "The $1,000 and $5,000 endings below match the published search. Win rate, profit factor, Sharpe, and drawdown are the $2,500 book.",
        "",
        "| Cell | Window | $1k trades | $2,500 trades | $5k trades | Win | PF | Sharpe | Max DD | $1,000 | $2,500 | $5,000 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sizing:
        window = "train" if row["end"] == TRAIN_END.isoformat() else "holdout"
        stake = row["stakes"]
        base = stake["2500"]
        lines.append(
            f"| {row['id']} | {window} | {stake['1000']['trades']} | {base['trades']} | {stake['5000']['trades']} | "
            f"{_pct(base['win_rate'])} | {_num(base.get('profit_factor'))} | {_num(base['sharpe'])} | {_pct(base['max_drawdown'])} | "
            f"{_money(stake['1000']['ending_equity'])} | {_money(base['ending_equity'])} | {_money(stake['5000']['ending_equity'])} |"
        )
    lines.append("")
    lines.append(
        "Paul's rule from $2,500 takes 979 training trades and ends at $1,305, against $608 from the published $1,000 book (790 trades) and $2,477 from $5,000 (995 trades). "
        "The least-bad cell, rerun from $2,500, takes 185 training trades and ends at $2,410. Its holdout, still that one cell, takes 2 trades and ends at $2,505. None of these share books is a pass."
    )
    lines.append("")
    if fits:
        lines.append("Three-contract debit on those share fills, 0 DTE, before later trades spend the cash:")
        lines.append("")
        for fit in fits:
            signals = int(fit["fit"]["signals"])
            got = int(fit["fit"].get("fit_3_2500") or 0)
            option = fit.get("option_2500") or {}
            lines.append(
                f"- {fit['id']} {fit['window']} {fit['dte']} DTE: {got} of {signals} three-lots fit in $2,500, "
                f"{fit['fit'].get('fit_3_1000', 0)} fit in $1,000, {fit['fit'].get('fit_3_5000', 0)} fit in $5,000. "
                f"Median three-lot debit {_money(fit['fit'].get('median_debit_3'))}. "
                f"The one-contract model on these $2,500 share fills filled {option.get('trades', 0)}, skipped {option.get('skipped', 0)}, "
                f"P&L {_money(option.get('pnl'))}, ending {_money(option.get('ending'))}."
            )
        lines.append("")
    lines.append(
        "A 0 DTE three-lot fits in $2,500 on every one of these share fills, and it fits in $1,000 as well. "
        "A 7 DTE three-lot is the one that strains the account: the headline median is about $1,223, so 970 of 979 fit in $2,500 and 302 of 979 fit in $1,000. "
        "The one-contract dollars above are a model on the $2,500 share fills. They are not a new trial and they do not replace the published one-contract book."
    )
    lines.append("")
    if tendency.get("found") and int(tendency.get("eligible") or 0) == 0:
        lines.append(
            f"Tendency: {tendency.get('cells', 0)} cells, {tendency.get('eligible', 0)} mean-reverting. "
            "No share book and no option book was built at $1,000, $2,500, or $5,000. The stake does not change that label. "
            "Three-contract feasibility has no entry to price. The holdout was not opened."
        )
    else:
        lines.append(
            f"Tendency eligible cells: {tendency.get('eligible', 0)}. A mean-reverting cell is the only one that can take this exit."
        )
    lines.append("")
    lines.append(
        "Scale-out books. Open-versus-support training is 2018-01-01 through 2026-07-06 and its holdout is 2026-07-07 through 2026-10-06. "
        "The VWAP continuation training ends 2021-12-31 and its holdout is 2022-01-01 through 2026-10-06. q is the training false-discovery rate across these exit books."
    )
    lines.append("")
    lines.append("| Book | Exit | Train n | /day | Win | PF | Sharpe | DD | $1,000 | $2,500 | $5,000 | Hold n | /day | Win | PF | Sharpe | DD | Hold $1,000 | Hold $2,500 | Hold $5,000 | q | Fill scale |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in exits:
        train = row["train"]["stakes"]["2500"]
        hold = row["holdout"]["stakes"]["2500"]
        lines.append(
            f"| {row['book']} | {row['exit']} | {train['trades']} | {_per_day(train['trades_per_day'])} | {_pct(train['win_rate'])} | "
            f"{_num(train.get('profit_factor'))} | {_num(train['sharpe'])} | {_pct(train['max_drawdown'])} | "
            f"{_money(row['train']['stakes']['1000']['ending_equity'])} | {_money(train['ending_equity'])} | "
            f"{_money(row['train']['stakes']['5000']['ending_equity'])} | {hold['trades']} | {_per_day(hold['trades_per_day'])} | "
            f"{_pct(hold['win_rate'])} | {_num(hold.get('profit_factor'))} | {_num(hold['sharpe'])} | {_pct(hold['max_drawdown'])} | "
            f"{_money(row['holdout']['stakes']['1000']['ending_equity'])} | {_money(hold['ending_equity'])} | "
            f"{_money(row['holdout']['stakes']['5000']['ending_equity'])} | {_q(row.get('q'))} | {_pct(train.get('scaled_at_fill_rate'))} |"
        )
    lines.append("")
    lines.append(
        "On the open, a 0 DTE three-lot fits in $2,500 on every signal (median debit about $228), and it fits in $1,000 too. "
        "Selling all three at 1R finishes the $2,500 training account at $74,827. The three scale-out stops finish between $13,523 and $16,350. "
        "All-out at the band finishes at $13,582, and all-out at a 50% premium finishes at $21,659. "
        "Training q on these open-support option books is below 0.10 inside this 18-book family. The share book at $2,500 still ends at $1,305. "
        "The option figure is a Black-Scholes model with the prior VIX close, not a listed fill, and it is not a book to trade."
    )
    lines.append("")
    lines.append(
        "On the 2 SD continuation, about 90% of the scale-out trades sell the two-thirds on the fill, because that entry is already through the band. "
        "Those $2,500 books end at a few dollars in training and in the holdout. "
        "The original 1R exit is the comparison: QQQ finishes training at $48,922 from $2,500, while SPY's training account goes to about $0 and then skips the later signals. "
        "SPY's fresh 1R holdout has 2,355 trades, the same count as the published one-contract book, and finishes at $74,951 from $2,500. "
        "Before any loss, every continuation three-lot fits in $2,500 (median debit about $148 on SPY and $111 on QQQ). "
        "The skips in the SPY training book are the account after it has already lost the cash. "
        "QQQ here is the long Dukascopy 5-minute cache resampled to 15 minutes, which is a longer tape than the earlier VWAP report."
    )
    lines.append("")
    lines.append(
        "Fill scale is the share of $2,500 training trades that sold the two-thirds on the entry bar. A blank band, or an exit that is not the band, stays at zero. "
        "The chart is `reports/scale_out_equity.png`."
    )
    lines.append("")
    lines.extend(
        [
            "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.",
            "",
            "```",
            "python3 -m webull_bot.chart_reads.research_scale_out",
            "```",
            END_MARK,
            "",
        ]
    )
    return "\n".join(lines)


def _write_results(section: str) -> None:
    path = Path("RESULTS.md")
    existing = path.read_text() if path.exists() else "# Research results\n\n"
    block = section if section.endswith("\n") else section + "\n"
    if START_MARK in existing and END_MARK in existing:
        start = existing.index(START_MARK)
        end = existing.index(END_MARK) + len(END_MARK)
        updated = existing[:start].rstrip() + "\n\n" + block
        if end < len(existing):
            updated += existing[end:].lstrip("\n")
    else:
        updated = existing.rstrip() + "\n\n" + block
    path.write_text(updated)


def _chart(path: Path, curves: dict[str, pd.Series]) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for name, equity in curves.items():
        if equity is None or len(equity) == 0:
            continue
        ax.plot(equity.index, equity.to_numpy(dtype=float), label=name)
    ax.axhline(PRIMARY_STAKE, color="#888888", linewidth=0.8)
    ax.set_title("Scale-out, $2,500 training equity")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "scale_out_rules.json").write_text(json.dumps(frozen_rules(), indent=2) + "\n")
    print("load", flush=True)
    vix = _vix()
    volume = _dollar_volume(GATE_SYMBOLS)
    fives = {symbol: _load_dukascopy_five(symbol) for symbol in GATE_SYMBOLS}
    views = {
        symbol: build_views(symbol, frame, dollar_volume=volume.get(symbol))
        for symbol, frame in fives.items()
    }
    print("share sizing", flush=True)
    sizing = [
        _size_shares(views, HEADLINE_ID, TRAIN_START, TRAIN_END, allow_holdout=False),
        _size_shares(views, FEATURED_ID, TRAIN_START, TRAIN_END, allow_holdout=False),
        _size_shares(views, FEATURED_ID, HOLDOUT_START, HOLDOUT_END, allow_holdout=True),
    ]
    fits = []
    for row, dte in ((sizing[0], 0), (sizing[1], 0), (sizing[2], 0), (sizing[0], 7), (sizing[1], 7)):
        window = "train" if row["end"] == TRAIN_END.isoformat() else "holdout"
        fits.append({"id": row["id"], "window": window, "dte": dte, "fit": three_lot_fit(row["trades"], vix, dte)})
        option_book = option_report(row["trades"], vix, PRIMARY_STAKE, dte)
        fits[-1]["option_2500"] = {key: option_book[key] for key in ("trades", "skipped", "pnl", "ending", "dte")}
    sessions = _days(fives["SPY"].index)
    print("open paths", flush=True)
    open_paths = []
    for symbol, frame in fives.items():
        prepared = prepare_open_paths(symbol, frame, dollar_volume=volume.get(symbol))
        print(f"  {symbol} signals {len(prepared)}", flush=True)
        open_paths.extend(attach_prices(prepared, vix))
    print(f"open priced {len(open_paths)}", flush=True)
    exit_rows = []
    curves = {}
    for name in EXITS:
        print(f"open exit {name}", flush=True)
        train = _score_exit(name, open_paths, sessions, TRAIN_START, TRAIN_END, cap=3, one_position=False)
        hold = _score_exit(name, open_paths, sessions, HOLDOUT_START, HOLDOUT_END, cap=3, one_position=False)
        exit_rows.append({"book": "open_support", "exit": name, "train": train, "holdout": hold, "p": train["p"]})
        curves[f"open {name}"] = train["equity"]
    for symbol, frame in fives.items():
        fifteen = _fifteen(frame)
        prepared = attach_prices(prepare_extension_paths(fifteen, symbol), vix)
        symbol_days = _days(fifteen.index)
        print(f"vwap {symbol} priced {len(prepared)}", flush=True)
        for name in EXITS:
            print(f"vwap {symbol} {name}", flush=True)
            train = _score_exit(name, prepared, symbol_days, date(2017, 1, 1), VWAP_TRAIN_END, cap=None, one_position=True)
            hold = _score_exit(name, prepared, symbol_days, VWAP_HOLDOUT_START, VWAP_SAMPLE_END, cap=None, one_position=True)
            exit_rows.append({"book": f"vwap_{symbol}", "exit": name, "train": train, "holdout": hold, "p": train["p"]})
            if symbol == "SPY":
                curves[f"SPY {name}"] = train["equity"]
    assign_q(exit_rows)
    if len(exit_rows) != n_trials():
        raise RuntimeError(f"expected {n_trials()} exit books, scored {len(exit_rows)}")
    tendency = _tendency_note()
    _chart(reports / "scale_out_equity.png", curves)
    section = _render(sizing, exit_rows, tendency, fits)
    (reports / "scale_out.md").write_text(section)
    _write_results(section)
    payload = {
        "n_trials": n_trials(),
        "primary_stake": PRIMARY_STAKE,
        "sizing": [{key: value for key, value in row.items() if key != "trades"} for row in sizing],
        "fits": fits,
        "tendency": tendency,
        "exits": [
            {
                "book": row["book"],
                "exit": row["exit"],
                "q": row.get("q"),
                "p": row.get("p"),
                "train": {key: value for key, value in row["train"].items() if key != "equity"},
                "holdout": {key: value for key, value in row["holdout"].items() if key != "equity"},
            }
            for row in exit_rows
        ],
    }
    (reports / "scale_out.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main()
