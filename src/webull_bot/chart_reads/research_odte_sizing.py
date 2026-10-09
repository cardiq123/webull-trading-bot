"""Score fixed lots and a 1-minute exit check. Backtests only.

Writes reports/odte_sizing.md. Does not place an order and does not change
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
from webull_bot.chart_reads.odte_sizing import load_minutes, retime
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.research_odte_calibration import _load_bars, _load_series, rth_dates

MD_PATH = Path("reports/odte_sizing.md")
JSON_PATH = Path("reports/odte_sizing.json")
# The published 3-lot QQQ Aggressive row at x1.67 and a 1 cent market.
CHECK_TRADES = 1128
CHECK_ENDING = 40755.37


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
        "max_drawdown": metrics.get("max_drawdown"),
        "ending_equity": metrics.get("ending_equity"),
        "starts": rolling["starts"],
        "median_ending": rolling["median_ending"],
        "p_reach_12": rolling["p_reach_12"],
        "p_ruin": rolling["p_ruin"],
    }


def _score(cands, sessions, qty, cap, stake) -> dict:
    out = {}
    for window, start, end in (
        ("train", TRAIN_START, TRAIN_END),
        ("holdout", HOLDOUT_START, HOLDOUT_END),
    ):
        scored = score_window(cands, sessions, start, end, qty, cap, stake, True)
        out[window] = _pack(scored)
    return out


def _line(row: dict) -> str:
    cells = [
        row["book"],
        row["expiry"],
        row["iv"],
        str(row["qty"]),
        row["window"],
        _money(row["ending_equity"]),
        _pct(row["max_drawdown"]),
        _money(row["median_ending"]),
        _pct(row["p_reach_12"]),
        _pct(row["p_ruin"]),
        str(row["trades"]),
        _pct(row["win_rate"]),
        _num(row["profit_factor"]),
    ]
    return "| " + " | ".join(cells) + " |"


def _markdown(payload: dict) -> str:
    lines = [
        "# Contract size and one-minute checks",
        "",
        "Backtest only. Nothing was sent to a broker. Live trading stays off. The sandbox forward books were not changed.",
        "",
        payload["summary"],
        "",
        "## How this is scored",
        "",
        "Train is 2017-02-16 through 2023-12-31. Holdout is a fresh account from 2024-01-01 through 2026-10-06. "
        "QQQ Aggressive and QQQ Trapdoor start at $2,500. SPY VWAP starts at $1,000. "
        "Aggressive still takes at most 5 fills a day. Trapdoor still takes at most 3. SPY has no daily count cap. "
        "One position. The whole ticket is bought or the signal is skipped. A 15-lot is not cut down to whatever cash can afford.",
        "",
        "The 0 DTE rows use each day's prior VIX1D close, or the prior VIX close when that print is missing, "
        f"times {payload['multiplier_label']} (the unrounded ratio is {payload['multiplier']:.4f}), and a 1 cent bid-ask. "
        "That is half a cent on the bid and half a cent on the ask. "
        "The 1 DTE and 2 DTE rows use the same prior close with no multiplier. "
        "At the 11:36 SPY quote the model was already richer than the market on those two expiries, so the 0 DTE bump is not applied again. "
        "1 DTE expires at 16:00 on the next trading session. 2 DTE expires two trading sessions out. "
        "A Friday signal's 1 DTE contract expires Monday. The underlying stop, the 1R target, and the 15:45 flat are unchanged, "
        "so the longer contract still has time value when it is sold.",
        "",
        "Reach is equity of $10,000. Ruin is equity under $500. "
        "Ending is one account started at the first session of that window. "
        "The median and the two probabilities start a fresh account on every later session that still has a full 12 months inside the window. "
        "An account that goes broke stops taking the later signals. A fresh account started the next year still takes them. "
        "That is why one holdout path can end near zero while the typical 12-month start does not, and the reverse.",
        "",
        "There are no 5-second bars. The finest Dukascopy file here is 1 minute, for SPY and QQQ, "
        f"from {payload['minute_start']} through {payload['minute_end']}. "
        "A 1-minute bar approximates a 5-second check. "
        "The entry is the first 1-minute open at the signal's fill time. On this file that open is the same price as the next 5-minute or 15-minute open, "
        "so the entry matches the current backtest except where a minute is missing. "
        "The exit is the first 1-minute bar that touches the stop or the target, instead of waiting for the 5-minute or 15-minute bar. "
        "When both levels trade inside one of those coarser bars, the earlier minute decides. "
        "When both trade inside the same minute, the stop still wins.",
        "",
        payload["timing_note"],
        "",
        "## Fixed size at the current bar timing",
        "",
        "QQQ Aggressive and QQQ Trapdoor. The signal and the exit bar are unchanged. Only the contract count, and on the later rows the expiry, change.",
        "",
        "| Book | Expiry | IV | Contracts | Window | Ending | Max DD | Median 12m | P(reach $10k) | P(ruin) | Trades | Win | PF |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["size_rows"]:
        lines.append(_line(row))
    lines.extend(
        [
            "",
            "## Fifteen contracts, current timing next to one-minute checks",
            "",
            "Same 15-contract ticket. Current timing is the bar the book already uses: 15 minutes for the VWAP books, 5 minutes for Trapdoor. "
            "One-minute timing enters on the first minute after the signal bar and exits on the first minute that touches the stop or the target.",
            "",
            "| Book | Expiry | IV | Check | Window | Ending | Max DD | Median 12m | P(reach $10k) | P(ruin) | Trades | Win | PF |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["fast_rows"]:
        cells = [
            row["book"],
            row["expiry"],
            row["iv"],
            row["timing"],
            row["window"],
            _money(row["ending_equity"]),
            _pct(row["max_drawdown"]),
            _money(row["median_ending"]),
            _pct(row["p_reach_12"]),
            _pct(row["p_ruin"]),
            str(row["trades"]),
            _pct(row["win_rate"]),
            _num(row["profit_factor"]),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.extend(["", payload["close"], ""])
    return "\n".join(lines)


def _flatten(spec: dict, expiry: str, iv: str, qty: int, scored: dict, timing: str | None = None) -> list[dict]:
    rows = []
    for window in ("train", "holdout"):
        row = {
            "book": spec["name"],
            "book_id": spec["id"],
            "expiry": expiry,
            "iv": iv,
            "qty": qty,
            "window": window,
            **scored[window],
        }
        if timing is not None:
            row["timing"] = timing
        rows.append(row)
    return rows


def _lead(payload: dict) -> str:
    def pick(rows, book, expiry, window, qty=None, timing=None):
        for row in rows:
            if row["book"] != book or row["expiry"] != expiry or row["window"] != window:
                continue
            if qty is not None and row["qty"] != qty:
                continue
            if timing is not None and row["timing"] != timing:
                continue
            return row
        raise KeyError((book, expiry, window, qty, timing))

    a3h = pick(payload["size_rows"], "QQQ Aggressive", "0 DTE", "holdout", 3)
    a3t = pick(payload["size_rows"], "QQQ Aggressive", "0 DTE", "train", 3)
    a15h = pick(payload["size_rows"], "QQQ Aggressive", "0 DTE", "holdout", 15)
    a1 = pick(payload["size_rows"], "QQQ Aggressive", "1 DTE", "holdout", 3)
    a1t = pick(payload["size_rows"], "QQQ Aggressive", "1 DTE", "train", 3)
    t15 = pick(payload["size_rows"], "QQQ Trapdoor", "0 DTE", "holdout", 15)
    t1 = pick(payload["size_rows"], "QQQ Trapdoor", "1 DTE", "holdout", 15)
    cur = pick(payload["fast_rows"], "QQQ Trapdoor", "1 DTE", "holdout", timing="current")
    fast = pick(payload["fast_rows"], "QQQ Trapdoor", "1 DTE", "holdout", timing="1-minute")
    stats = payload["timing_stats"]
    return (
        f"At {payload['multiplier_label']} 0 DTE volatility and a 1 cent market, "
        f"QQQ Aggressive at 3 contracts still matches the earlier score: "
        f"holdout {_money(a3h['ending_equity'])} on {a3h['trades']} trades, "
        f"profit factor {_num(a3h['profit_factor'])}, max drawdown {_pct(a3h['max_drawdown'])}, "
        f"12-month median {_money(a3h['median_ending'])}, "
        f"P(reach $10k) {_pct(a3h['p_reach_12'])}, P(ruin) {_pct(a3h['p_ruin'])}. "
        f"The train account is spent, ending {_money(a3t['ending_equity'])} after {a3t['trades']} trades, "
        f"with P(ruin) {_pct(a3t['p_ruin'])}. "
        f"Five, ten, and fifteen contracts make the 0 DTE ticket too expensive for a $2,500 start. "
        f"The 15-contract holdout takes {a15h['trades']} trades and ends at {_money(a15h['ending_equity'])}, "
        f"and P(ruin) is {_pct(a15h['p_ruin'])}. "
        f"QQQ Trapdoor at 15 of those 0 DTE contracts ends the holdout at {_money(t15['ending_equity'])} "
        f"on {t15['trades']} trades. "
        f"The same Trapdoor signals on an unscaled 1 DTE contract do fit 15 lots on the holdout: "
        f"{t1['trades']} trades, ending {_money(t1['ending_equity'])}, profit factor {_num(t1['profit_factor'])}, "
        f"but the typical 12-month start ends at {_money(t1['median_ending'])} and "
        f"P(reach $10k) is {_pct(t1['p_reach_12'])}. "
        f"Aggressive at 3 unscaled 1 DTE contracts keeps every signal and ends the holdout at {_money(a1['ending_equity'])} "
        f"and the train at {_money(a1t['ending_equity'])}. "
        "Checking every minute instead of every 5 or 15 minutes changes the underlying exit price on "
        f"{stats['qqq_aggr']['exit_price_changed']} of {stats['qqq_aggr']['signals']} Aggressive signals, "
        f"{stats['trapdoor']['exit_price_changed']} of {stats['trapdoor']['signals']} Trapdoor signals, and "
        f"{stats['spy_vwap']['exit_price_changed']} of {stats['spy_vwap']['signals']} SPY signals. "
        f"The clearest same-trade comparison is Trapdoor 1 DTE at 15 contracts: "
        f"the holdout goes from {_money(cur['ending_equity'])} on the current bar to {_money(fast['ending_equity'])} on the minute. "
        "A 1-minute bar approximates a 5-second check. This cache has no 5-second bars. "
        "1 DTE and 2 DTE use the unscaled prior close."
    )


def _timing_note(stats: dict) -> str:
    parts = []
    for key, row in stats.items():
        parts.append(
            f"{key}: {row['kept']} of {row['signals']} signals kept, "
            f"{row['entry_changed']} entries changed, "
            f"{row['exit_price_changed']} exit prices changed, "
            f"{row['exit_reason_changed']} exit reasons changed, "
            f"{row['through_stop']} skipped because the first minute opened through the stop, "
            f"{row['missing']} missing a minute."
        )
    return "What the 1-minute file changed, before pricing: " + " ".join(parts)


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
    current = {
        "spy_vwap": vwap_structures(spy15, "SPY"),
        "qqq_aggr": vwap_structures(qqq15, "QQQ"),
        "trapdoor": trapdoor_structures(prepare(qqq, "QQQ")),
    }
    sessions = {
        "spy_vwap": session_dates(spy15),
        "qqq_aggr": session_dates(qqq15),
        "trapdoor": rth_dates(qqq),
    }
    print("loading 1-minute bars", flush=True)
    minutes = {"SPY": load_minutes("SPY"), "QQQ": load_minutes("QQQ")}
    symbol = {"spy_vwap": "SPY", "qqq_aggr": "QQQ", "trapdoor": "QQQ"}
    fast = {}
    timing_stats = {}
    for key, rows in current.items():
        fast[key], timing_stats[key] = retime(rows, minutes[symbol[key]])
        print(f"  {key} current {len(rows)} minute {len(fast[key])} {timing_stats[key]}", flush=True)
    named = {spec["id"]: spec for spec in books()}
    size_books = (named["qqq_aggr"], named["trapdoor"])
    grids = (
        (0, "0 DTE", f"{label} prior close, 1 cent", multiplier, (3, 5, 10, 15)),
        (1, "1 DTE", "prior close, 1 cent", 1.0, (1, 3, 5, 10, 15)),
        (2, "2 DTE", "prior close, 1 cent", 1.0, (1, 3, 5, 10, 15)),
    )
    size_rows = []
    priced_current = {}
    for spec in size_books:
        for dte, expiry, iv_label, scale, qtys in grids:
            print(f"pricing {spec['id']} {expiry}", flush=True)
            cands = price_structures(current[spec["id"]], iv, scale, "0.01", dte=dte)
            priced_current[(spec["id"], dte)] = cands
            for qty in qtys:
                print(f"  qty {qty}", flush=True)
                scored = _score(cands, sessions[spec["id"]], qty, spec["cap"], spec["stake"])
                size_rows.extend(_flatten(spec, expiry, iv_label, qty, scored))
                hold = scored["holdout"]
                print(
                    f"    holdout trades {hold['trades']} ending {hold['ending_equity']:.2f} "
                    f"pf {hold['profit_factor']}",
                    flush=True,
                )
    check = next(
        row
        for row in size_rows
        if row["book_id"] == "qqq_aggr" and row["expiry"] == "0 DTE" and row["qty"] == 3 and row["window"] == "holdout"
    )
    trade_gap = abs(check["trades"] - CHECK_TRADES)
    money_gap = abs(float(check["ending_equity"]) - CHECK_ENDING)
    print(f"check aggressive 3-lot holdout trade gap {trade_gap} ending gap {money_gap:.2f}", flush=True)
    fast_rows = []
    compare_books = (named["qqq_aggr"], named["trapdoor"], named["spy_vwap"])
    for spec in compare_books:
        for dte, expiry, iv_label, scale, _qtys in grids:
            if (spec["id"], dte) not in priced_current:
                print(f"pricing {spec['id']} {expiry}", flush=True)
                priced_current[(spec["id"], dte)] = price_structures(current[spec["id"]], iv, scale, "0.01", dte=dte)
            print(f"pricing minute {spec['id']} {expiry}", flush=True)
            priced_fast = price_structures(fast[spec["id"]], iv, scale, "0.01", dte=dte)
            for timing, cands in (("current", priced_current[(spec["id"], dte)]), ("1-minute", priced_fast)):
                print(f"  {timing} 15", flush=True)
                scored = _score(cands, sessions[spec["id"]], 15, spec["cap"], spec["stake"])
                fast_rows.extend(_flatten(spec, expiry, iv_label, 15, scored, timing))
                hold = scored["holdout"]
                print(
                    f"    holdout trades {hold['trades']} ending {hold['ending_equity']:.2f} "
                    f"win {hold['win_rate']} pf {hold['profit_factor']}",
                    flush=True,
                )
    minute_start = str(minutes["QQQ"].index[0])
    minute_end = str(minutes["QQQ"].index[-1])
    payload = {
        "multiplier": multiplier,
        "multiplier_label": label,
        "minute_start": minute_start,
        "minute_end": minute_end,
        "timing_stats": timing_stats,
        "timing_note": _timing_note(timing_stats),
        "size_rows": size_rows,
        "fast_rows": fast_rows,
        "check": {"trades": check["trades"], "ending": check["ending_equity"], "trade_gap": trade_gap, "money_gap": money_gap},
        "summary": "",
        "close": (
            "The cash mirror in the sandbox still uses the unscaled 0 DTE model and the book's fixed lot. "
            "This score does not change an order. "
            f"QQQ Trapdoor's daily cap stays {MAX_TRADES_PER_DAY}."
        ),
    }
    payload["summary"] = _lead(payload)
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
