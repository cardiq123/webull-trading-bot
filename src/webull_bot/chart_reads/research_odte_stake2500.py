"""Score 3- and 5-lot tickets from a fresh $2,500. Backtests only.

Writes reports/odte_stake2500.md. Does not place an order and does not change
the sandbox forward books.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from webull_bot.chart_reads.neckline import MAX_TRADES_PER_DAY
from webull_bot.chart_reads.odte_calibration import (
    HOLDOUT_END,
    HOLDOUT_START,
    TRAIN_END,
    TRAIN_START,
    books,
    calibrate,
    prepare,
    price_structures,
    score_window,
    session_dates,
    to_fifteen,
    trapdoor_structures,
    vwap_structures,
)
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.research_odte_calibration import _load_bars, _load_series, rth_dates
from webull_bot.chart_reads.vwap_band import (
    GATE_DRAWDOWN,
    GATE_PF,
    GATE_SHARPE,
    GATE_TRADES,
    passes_gate,
)

ROOT = Path(__file__).resolve().parents[3]
MD_PATH = ROOT / "reports" / "odte_stake2500.md"
JSON_PATH = ROOT / "reports" / "odte_stake2500.json"
PRIOR_JSON = ROOT / "reports" / "odte_sizing.json"
STAKE = 2_500.0
QTYS = (1, 3, 5)
# The published QQQ Aggressive 3-lot holdout at x1.67 and a 1 cent market.
CHECK_TRADES = 1128
CHECK_ENDING = 40755.372888142854
CHECK_SHARPE = 1.6481434934033377


def gate_label(metrics: dict) -> str:
    """The usual holdout gate, also applied to a train row so a spent train is visible."""
    if passes_gate(metrics):
        return "yes"
    misses = []
    trades = int(metrics.get("trades") or 0)
    if trades < GATE_TRADES:
        misses.append(f"trades {trades}<{GATE_TRADES}")
    profit_factor = metrics.get("profit_factor")
    if profit_factor is None:
        pf_ok = trades > 0 and float(metrics.get("win_rate") or 0.0) == 1.0
    else:
        pf_ok = float(profit_factor) >= GATE_PF
    if not pf_ok:
        shown = "n/a" if profit_factor is None else f"{float(profit_factor):.3f}"
        misses.append(f"PF {shown}<{GATE_PF:.2f}")
    sharpe = float(metrics.get("sharpe") or 0.0)
    if sharpe < GATE_SHARPE:
        misses.append(f"Sharpe {sharpe:.2f}<{GATE_SHARPE:.2f}")
    drawdown = float(metrics.get("max_drawdown") or 0.0)
    if drawdown < GATE_DRAWDOWN:
        misses.append(f"drawdown {100.0 * drawdown:.1f}%")
    return "no (" + ", ".join(misses) + ")"


def _money(value) -> str:
    if value is None:
        return "n/a"
    number = float(value)
    if abs(number) >= 100:
        return f"${number:,.0f}"
    return f"${number:,.2f}"


def _pct(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _num(value) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _pack(scored: dict) -> dict:
    metrics = scored["metrics"]
    rolling = scored["rolling"]
    return {
        "trades": int(metrics.get("trades") or 0),
        "win_rate": metrics.get("win_rate"),
        "profit_factor": metrics.get("profit_factor"),
        "sharpe": metrics.get("sharpe"),
        "max_drawdown": metrics.get("max_drawdown"),
        "ending_equity": metrics.get("ending_equity"),
        "starts": rolling["starts"],
        "median_ending": rolling["median_ending"],
        "p_reach_12": rolling["p_reach_12"],
        "p_ruin": rolling["p_ruin"],
        "gate": gate_label(metrics),
        "gate_pass": bool(passes_gate(metrics)),
    }


def _score(cands, sessions, qty, cap) -> dict:
    out = {}
    for window, start, end in (
        ("train", TRAIN_START, TRAIN_END),
        ("holdout", HOLDOUT_START, HOLDOUT_END),
    ):
        scored = score_window(cands, sessions, start, end, qty, cap, STAKE, True)
        out[window] = _pack(scored)
    return out


def published_reference() -> list[dict]:
    """1- and 3-contract rows already stored in the earlier sizing report.

    That report has no 0 DTE 1-contract row, and no SPY row at 1 or 3 contracts.
    SPY there is 15 contracts from $1,000.
    """
    payload = json.loads(PRIOR_JSON.read_text())
    found = []
    for row in payload["size_rows"]:
        if row["book_id"] not in {"qqq_aggr", "trapdoor"}:
            continue
        if row["expiry"] not in {"0 DTE", "1 DTE"}:
            continue
        if int(row["qty"]) not in {1, 3}:
            continue
        found.append(row)
    return found


def _flatten(spec: dict, expiry: str, iv_label: str, scale: float, qty: int, scored: dict) -> list[dict]:
    rows = []
    for window in ("train", "holdout"):
        rows.append(
            {
                "book": spec["name"],
                "book_id": spec["id"],
                "expiry": expiry,
                "iv": iv_label,
                "scale": float(scale),
                "qty": qty,
                "stake": STAKE,
                "window": window,
                **scored[window],
            }
        )
    return rows


def _pair(rows: list[dict], iv_label: str) -> list[dict]:
    cells = []
    keys = []
    for row in rows:
        if row["iv"] != iv_label:
            continue
        key = (row["book_id"], row["expiry"], row["qty"])
        if key not in keys:
            keys.append(key)
    by = {
        (row["book_id"], row["expiry"], row["qty"], row["window"]): row
        for row in rows
        if row["iv"] == iv_label
    }
    for book_id, expiry, qty in keys:
        train = by[(book_id, expiry, qty, "train")]
        hold = by[(book_id, expiry, qty, "holdout")]
        cells.append(
            {
                "book": train["book"],
                "book_id": book_id,
                "expiry": expiry,
                "qty": qty,
                "iv": train["iv"],
                "train": train,
                "holdout": hold,
            }
        )
    return cells


def rank_cells(cells: list[dict]) -> list[dict]:
    """Holdout and train both above the start, then a cleared holdout gate, then the smaller ending."""

    def key(cell: dict) -> tuple:
        train = cell["train"]
        hold = cell["holdout"]
        both = float(train["ending_equity"]) > STAKE and float(hold["ending_equity"]) > STAKE
        train_alive = float(train["ending_equity"]) >= 500.0
        return (
            both,
            bool(hold["gate_pass"]),
            train_alive,
            min(float(train["ending_equity"]), float(hold["ending_equity"])),
            -max(float(train["p_ruin"] or 1.0), float(hold["p_ruin"] or 1.0)),
        )

    return sorted(cells, key=key, reverse=True)


def _qty_phrase(qty: int) -> str:
    return "1 contract" if int(qty) == 1 else f"{int(qty)} contracts"


def _short(row: dict, name: str) -> str:
    return (
        f"{name} {_money(row['ending_equity'])} on {row['trades']} trades, "
        f"profit factor {_num(row['profit_factor'])}, max drawdown {_pct(row['max_drawdown'])}, "
        f"12-month median {_money(row['median_ending'])}, "
        f"P(reach $10k) {_pct(row['p_reach_12'])}, P(ruin) {_pct(row['p_ruin'])}, "
        f"gate {row['gate']}."
    )


def summary_paragraphs(cells: list[dict], shock_rows: list[dict], matched: bool) -> str:
    ranked = rank_cells(cells)
    both = []
    hold_only = []
    rest = []
    for cell in ranked:
        train_end = float(cell["train"]["ending_equity"])
        hold_end = float(cell["holdout"]["ending_equity"])
        if train_end > STAKE and hold_end > STAKE:
            both.append(cell)
        elif hold_end > STAKE and train_end < 500.0:
            hold_only.append(cell)
        else:
            rest.append(cell)
    both_gates = [
        cell
        for cell in both
        if cell["train"]["gate_pass"] and cell["holdout"]["gate_pass"]
    ]
    lines = [
        "Ranked by a holdout that finishes above the $2,500 start together with a train account that also finishes above that start. "
        "A cell whose train account ends under $500 fails that check, even when the holdout is large."
    ]
    if both_gates:
        names = ", ".join(
            f"{cell['book']} {_qty_phrase(cell['qty'])} {cell['expiry']}" for cell in both_gates
        )
        lines.append(f"The cells that clear the usual gate on both windows: {names}.")
    else:
        lines.append("No cell clears the usual gate on both the train and the holdout.")
    if matched:
        lines.append(
            "The overlapping 1-, 3-, and 5-contract QQQ Aggressive and QQQ Trapdoor rows match the earlier report, "
            f"including Aggressive at 3 contracts, 0 DTE, holdout: {CHECK_TRADES} trades and {_money(CHECK_ENDING)}."
        )
    if both:
        lines.append("These finish above $2,500 on the train and on the holdout. Holdout gate-passers come first.")
        for index, cell in enumerate(both, start=1):
            lines.append(
                f"{index}. {cell['book']}, {_qty_phrase(cell['qty'])}, {cell['expiry']}. "
                f"{_short(cell['holdout'], 'Holdout')} {_short(cell['train'], 'Train')}"
            )
    else:
        lines.append("No 1-, 3-, or 5-contract cell finishes above $2,500 on both windows.")
    three = next(
        (
            cell
            for cell in both
            if cell["book"] == "QQQ Aggressive" and cell["expiry"] == "1 DTE" and cell["qty"] == 3
        ),
        None,
    )
    if three is not None:
        lines.append(
            "QQQ Aggressive at 3 contracts, 1 DTE, is the largest account that still takes every signal "
            f"({three['train']['trades']} train, {three['holdout']['trades']} holdout). "
            "It misses the usual gate on drawdown: "
            f"{_pct(three['train']['max_drawdown'])} on the train and {_pct(three['holdout']['max_drawdown'])} on the holdout."
        )
    if hold_only:
        lines.append(
            "These holdout accounts finish above $2,500 while the train account ends under $500."
        )
        for cell in hold_only:
            lines.append(
                f"{cell['book']}, {_qty_phrase(cell['qty'])}, {cell['expiry']}: "
                f"holdout {_money(cell['holdout']['ending_equity'])} on {cell['holdout']['trades']} trades, "
                f"train {_money(cell['train']['ending_equity'])} on {cell['train']['trades']} trades, "
                f"train P(ruin) {_pct(cell['train']['p_ruin'])}."
            )
    if rest:
        lines.append("The remaining cells finish the holdout at or under $2,500, or the train ends between $500 and the start.")
        for cell in rest:
            lines.append(
                f"{cell['book']}, {_qty_phrase(cell['qty'])}, {cell['expiry']}: "
                f"holdout {_money(cell['holdout']['ending_equity'])} on {cell['holdout']['trades']} trades "
                f"(gate {cell['holdout']['gate']}), "
                f"train {_money(cell['train']['ending_equity'])} on {cell['train']['trades']} trades."
            )
    lines.append(_shock_prose(shock_rows))
    return "\n\n".join(line for line in lines if line)


def _shock_prose(rows: list[dict]) -> str:
    if not rows:
        return ""
    by = {(row["book_id"], row["qty"], row["scale"], row["window"]): row for row in rows}
    bits = [
        "The unscaled 1 DTE price rests on one session of live quotes, 2026-10-09 at 11:36 ET: "
        "the SPY 1 DTE call market mid was $2.155 and the model at the Oct 8 VIX1D close of 10.24 was $2.974. "
        "The same signals scored at 0.80 times and at 1.20 times that prior close, still with a 1 cent market and a same-day 15:45 flat, move as follows."
    ]
    order = []
    for row in rows:
        key = (row["book"], row["qty"])
        if key not in order and abs(float(row["scale"]) - 1.0) < 1e-9 and row["window"] == "holdout":
            order.append(key)
    for book, qty in order:
        book_id = next(row["book_id"] for row in rows if row["book"] == book)
        base_h = by[(book_id, qty, 1.0, "holdout")]
        low_h = by[(book_id, qty, 0.8, "holdout")]
        high_h = by[(book_id, qty, 1.2, "holdout")]
        base_t = by[(book_id, qty, 1.0, "train")]
        low_t = by[(book_id, qty, 0.8, "train")]
        high_t = by[(book_id, qty, 1.2, "train")]
        notes = []
        if base_h["trades"] and high_h["trades"] < 0.5 * base_h["trades"]:
            notes.append("The 1.20x holdout takes fewer than half the base trades, so the dearer ticket stops fitting.")
        elif float(base_t["ending_equity"]) > STAKE and float(high_t["ending_equity"]) < 500.0:
            notes.append("The 1.20x train ends under $500.")
        if base_h["trades"] and low_h["trades"] > 2 * base_h["trades"] and float(base_h["ending_equity"]) < STAKE:
            notes.append("The 0.80x holdout is the vol at which that ticket fits.")
        if float(base_t["ending_equity"]) < 500.0 and float(low_t["ending_equity"]) > STAKE:
            notes.append("The 0.80x train finishes above the $2,500 start.")
        if low_h["gate_pass"] and not base_h["gate_pass"]:
            notes.append("The 0.80x holdout clears the usual gate.")
        if base_h["gate_pass"] and not high_h["gate_pass"]:
            notes.append("The 1.20x holdout misses the usual gate.")
        sentence = (
            f"{book}, {_qty_phrase(qty)}. Holdout 0.80x {_money(low_h['ending_equity'])} on {low_h['trades']} trades, "
            f"base {_money(base_h['ending_equity'])} on {base_h['trades']} trades, "
            f"1.20x {_money(high_h['ending_equity'])} on {high_h['trades']} trades. "
            f"Train 0.80x {_money(low_t['ending_equity'])} on {low_t['trades']} trades, "
            f"base {_money(base_t['ending_equity'])} on {base_t['trades']} trades, "
            f"1.20x {_money(high_t['ending_equity'])} on {high_t['trades']} trades."
        )
        if notes:
            sentence = sentence + " " + " ".join(notes)
        bits.append(sentence)
    return "\n\n".join(bits)


def _line(row: dict, extra: str | None = None) -> str:
    cells = [
        row["book"],
        row["expiry"],
        row["iv"],
        str(row["qty"]),
        row["window"],
        str(row["trades"]),
        _pct(row["win_rate"]),
        _num(row["profit_factor"]),
        _pct(row["max_drawdown"]),
        _money(row["ending_equity"]),
        _money(row["median_ending"]),
        _pct(row["p_reach_12"]),
        _pct(row["p_ruin"]),
        row["gate"],
    ]
    if extra is not None:
        cells.append(extra)
    return "| " + " | ".join(cells) + " |"


def _ref_line(row: dict) -> str:
    cells = [
        row["book"],
        row["expiry"],
        str(row["qty"]),
        row["window"],
        str(row["trades"]),
        _pct(row["win_rate"]),
        _num(row["profit_factor"]),
        _pct(row["max_drawdown"]),
        _money(row["ending_equity"]),
        _money(row["median_ending"]),
        _pct(row["p_reach_12"]),
        _pct(row["p_ruin"]),
    ]
    return "| " + " | ".join(cells) + " |"


def _markdown(payload: dict) -> str:
    lines = [
        "# $2,500 lots at 3 and 5 contracts",
        "",
        "Backtest only. Nothing was sent to a broker. Live trading stays off. The sandbox forward books were not changed.",
        "",
        payload["summary"],
        "",
        "## How this is scored",
        "",
        "Train is 2017-02-16 through 2023-12-31. Holdout is a fresh account from 2024-01-01 through 2026-10-06. "
        "SPY VWAP, QQQ Aggressive, and QQQ Trapdoor each start at $2,500. "
        "Aggressive still takes at most 5 fills a day. Trapdoor still takes at most 3. SPY has no daily count cap. "
        "One position. The whole ticket is bought or the signal is skipped.",
        "",
        "The signal is unchanged: SPY VWAP is the 15-minute 2 SD continuation, QQQ Aggressive is the same rule on QQQ, "
        "and QQQ Trapdoor is the neckline put. The fill is the next open. The stop and the 1R target are unchanged. "
        "Every position is sold on the underlying stop, the 1R target, or the 15:45 bar of the entry day. "
        "A 1 DTE contract expires at 16:00 on the next trading session, so it still has time value at that same-day sale. "
        "A Friday signal's 1 DTE contract expires Monday. The live QQQ Aggressive 1 DTE book uses this same flatten.",
        "",
        f"The 0 DTE rows use each day's prior VIX1D close, or the prior VIX close when that print is missing, "
        f"times {payload['multiplier_label']} (the unrounded ratio is {payload['multiplier']:.4f}), and a 1 cent bid-ask. "
        "That is half a cent on the bid and half a cent on the ask. "
        "The 1 DTE rows use that prior close with no multiplier. "
        "The sensitivity rows reprice the same 1 DTE signals at 0.80 times and at 1.20 times the prior close.",
        "",
        "Reach is equity of $10,000. Ruin is equity under $500. "
        "Ending is one account started at the first session of that window. "
        "The median and the two probabilities start a fresh account on every later session that still has a full 12 months inside the window. "
        "An account that goes broke stops taking the later signals. A fresh account started the next year still takes them.",
        "",
        f"The usual gate is the VWAP holdout gate: at least {GATE_TRADES} trades, profit factor at least {GATE_PF:.2f}, "
        f"Sharpe at least {GATE_SHARPE:.2f}, and max drawdown no worse than {100.0 * GATE_DRAWDOWN:.0f}%. "
        "The same numbers are shown on the train row. The formal pass is the holdout row. "
        "The earlier sizing report did not store Sharpe, so its rows have no gate column.",
        "",
        "## Reference: 1- and 3-contract rows already published",
        "",
        "Copied from reports/odte_sizing.md. QQQ Aggressive and QQQ Trapdoor already started at $2,500. "
        "That file has no 0 DTE 1-contract row. It has no SPY row at 1 or 3 contracts. "
        "The SPY rows there are 15 contracts from $1,000, so they are left in that report.",
        "",
        "| Book | Expiry | Contracts | Window | Trades | Win | PF | Max DD | Ending | Median 12m | P(reach $10k) | P(ruin) |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["reference"]:
        lines.append(_ref_line(row))
    lines.extend(
        [
            "",
            "## Fresh $2,500, contracts 1, 3, and 5",
            "",
            "Contract 1 is scored again so the gate can be read, and so 0 DTE has a 1-contract row. "
            "Contracts 3 and 5 are the sizing question. SPY uses $2,500 here.",
            "",
            "| Book | Expiry | IV | Contracts | Window | Trades | Win | PF | Max DD | Ending | Median 12m | P(reach $10k) | P(ruin) | Gate |",
            "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["rows"]:
        if row["expiry"] == "1 DTE" and abs(float(row["scale"]) - 1.0) > 1e-9:
            continue
        lines.append(_line(row))
    lines.extend(
        [
            "",
            "## 1 DTE sensitivity to a 20% IV change",
            "",
            "Same 1 DTE signals and the same 1 cent market. 0.80x and 1.20x replace the unscaled prior close. "
            "The base row is repeated so the three vols sit together.",
            "",
            "| Book | Expiry | IV | Contracts | Window | Trades | Win | PF | Max DD | Ending | Median 12m | P(reach $10k) | P(ruin) | Gate |",
            "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["rows"]:
        if row["expiry"] != "1 DTE":
            continue
        lines.append(_line(row))
    lines.extend(
        [
            "",
            "The cash mirror in the sandbox still uses the unscaled 0 DTE model and the book's fixed lot. "
            "This score does not change an order. "
            f"QQQ Trapdoor's daily cap stays {MAX_TRADES_PER_DAY}.",
            "",
        ]
    )
    return "\n".join(lines)


def _match_published(rows: list[dict]) -> tuple[bool, list[str]]:
    gaps = []
    prior = {
        (row["book_id"], row["expiry"], int(row["qty"]), row["window"]): row
        for row in json.loads(PRIOR_JSON.read_text())["size_rows"]
    }
    for row in rows:
        if abs(float(row["scale"]) - 1.0) > 1e-9 and row["expiry"] == "1 DTE":
            continue
        if row["expiry"] == "0 DTE" and abs(float(row["scale"]) - float(calibrate()["multiplier_0dte"])) > 1e-6:
            continue
        key = (row["book_id"], row["expiry"], int(row["qty"]), row["window"])
        old = prior.get(key)
        if old is None:
            continue
        trade_gap = int(row["trades"]) - int(old["trades"])
        money_gap = float(row["ending_equity"]) - float(old["ending_equity"])
        if trade_gap != 0 or abs(money_gap) > 0.05:
            gaps.append(
                f"{key[0]} {key[1]} qty {key[2]} {key[3]}: trade gap {trade_gap}, ending gap {money_gap:.2f}"
            )
    return not gaps, gaps


def run() -> dict:
    multiplier = float(calibrate()["multiplier_0dte"])
    label = "x1.67"
    print("loading bars", flush=True)
    spy = _load_bars("SPY")
    qqq = _load_bars("QQQ")
    iv = prior_iv(_load_series("VIX1D"), _load_series("VIX"))
    spy15 = to_fifteen(spy)
    qqq15 = to_fifteen(qqq)
    print("structures", flush=True)
    structures = {
        "spy_vwap": vwap_structures(spy15, "SPY"),
        "qqq_aggr": vwap_structures(qqq15, "QQQ"),
        "trapdoor": trapdoor_structures(prepare(qqq, "QQQ")),
    }
    sessions = {
        "spy_vwap": session_dates(spy15),
        "qqq_aggr": session_dates(qqq15),
        "trapdoor": rth_dates(qqq),
    }
    for key, rows in structures.items():
        print(f"  {key} signals {len(rows)} sessions {len(sessions[key])}", flush=True)
    named = {spec["id"]: spec for spec in books()}
    order = (named["spy_vwap"], named["qqq_aggr"], named["trapdoor"])
    grids = (
        (0, "0 DTE", f"{label} prior close, 1 cent", multiplier),
        (1, "1 DTE", "prior close, 1 cent", 1.0),
        (1, "1 DTE", "0.80x prior close, 1 cent", 0.8),
        (1, "1 DTE", "1.20x prior close, 1 cent", 1.2),
    )
    rows = []
    for spec in order:
        for dte, expiry, iv_label, scale in grids:
            print(f"pricing {spec['id']} {iv_label}", flush=True)
            cands = price_structures(structures[spec["id"]], iv, scale, "0.01", dte=dte)
            for qty in QTYS:
                print(f"  qty {qty}", flush=True)
                scored = _score(cands, sessions[spec["id"]], qty, spec["cap"])
                rows.extend(_flatten(spec, expiry, iv_label, scale, qty, scored))
                hold = scored["holdout"]
                print(
                    f"    holdout trades {hold['trades']} ending {hold['ending_equity']:.2f} "
                    f"sharpe {hold['sharpe']:.2f} gate {hold['gate']}",
                    flush=True,
                )
    check = next(
        row
        for row in rows
        if row["book_id"] == "qqq_aggr"
        and row["expiry"] == "0 DTE"
        and row["qty"] == 3
        and row["window"] == "holdout"
    )
    trade_gap = abs(int(check["trades"]) - CHECK_TRADES)
    money_gap = abs(float(check["ending_equity"]) - CHECK_ENDING)
    sharpe_gap = abs(float(check["sharpe"]) - CHECK_SHARPE)
    print(
        f"check aggressive 3-lot holdout trade gap {trade_gap} ending gap {money_gap:.4f} sharpe gap {sharpe_gap:.4f}",
        flush=True,
    )
    if trade_gap or money_gap > 0.05 or sharpe_gap > 0.01:
        raise SystemExit("Aggressive 0 DTE 3-lot holdout does not match the published score")
    matched, gaps = _match_published(rows)
    if gaps:
        print("published gaps:", flush=True)
        for gap in gaps:
            print(f"  {gap}", flush=True)
        raise SystemExit("A published 1-, 3-, or 5-lot row does not match")
    base_cells = []
    for expiry, iv_label in (("0 DTE", f"{label} prior close, 1 cent"), ("1 DTE", "prior close, 1 cent")):
        base_cells.extend(_pair(rows, iv_label))
    shock_rows = [row for row in rows if row["expiry"] == "1 DTE"]
    payload = {
        "multiplier": multiplier,
        "multiplier_label": label,
        "stake": STAKE,
        "reference": published_reference(),
        "rows": rows,
        "matched_published": matched,
        "check": {
            "trades": check["trades"],
            "ending": check["ending_equity"],
            "sharpe": check["sharpe"],
        },
        "summary": "",
        "close": (
            "The cash mirror in the sandbox still uses the unscaled 0 DTE model and the book's fixed lot. "
            "This score does not change an order."
        ),
    }
    payload["summary"] = summary_paragraphs(base_cells, shock_rows, matched)
    return payload


def _json(value):
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            return None
        return value
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    if hasattr(value, "item"):
        return _json(value.item())
    raise TypeError(type(value))


def main() -> None:
    payload = run()
    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    public = json.loads(json.dumps(payload, default=_json))
    JSON_PATH.write_text(json.dumps(public, indent=2) + "\n")
    MD_PATH.write_text(_markdown(public))
    print(f"wrote {MD_PATH}", flush=True)


if __name__ == "__main__":
    main()
