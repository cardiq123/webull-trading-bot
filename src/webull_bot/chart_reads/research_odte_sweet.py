"""Sweet spot for QQQ Aggressive Compound under a realistic fill. Backtests only.

Writes reports/odte_sweet.md. Does not place an order and does not change the
sandbox forward books. The rule below was written down before the score.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import pandas as pd

from webull_bot.chart_reads.odte_calibration import (
    price_structures,
    session_dates,
    to_fifteen,
    vwap_structures,
)
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.research_odte_calibration import _load_bars, _load_series
from webull_bot.chart_reads.research_odte_compound import (
    CONTRACT_CAP,
    PREMIUM_UNIT,
    _check_baseline,
    _money,
    _num,
    _pct,
    _published_baselines,
    score_mode,
)
from webull_bot.chart_reads.research_odte_stake2500 import STAKE
from webull_bot.chart_reads.vwap_band import GATE_DRAWDOWN, GATE_PF, GATE_SHARPE, GATE_TRADES

ROOT = Path(__file__).resolve().parents[3]
MD_PATH = ROOT / "reports" / "odte_sweet.md"
JSON_PATH = ROOT / "reports" / "odte_sweet.json"

# Written down before the score. The result does not change these.
FRACTIONS = (0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12)
INSIDE_SIZE = 100
LEVELS = 3
PARTICIPATION = 0.10
RESEARCH_CAP = CONTRACT_CAP
REALISTIC_CAP = min(RESEARCH_CAP, math.floor(PARTICIPATION * INSIDE_SIZE * LEVELS))
CAPS = (10, 25, REALISTIC_CAP)
DECISION_IV = "1.20x prior close, 1 cent"
BASE_IV = "prior close, 1 cent"
DD_FALLBACK = -0.40
IVS = (
    (1.0, BASE_IV),
    (1.2, DECISION_IV),
)


def _fraction_list() -> str:
    return ", ".join(f"{100.0 * fraction:.0f}%" for fraction in FRACTIONS)


def _rule_text() -> str:
    return (
        "QQQ Aggressive Compound, realistic fills. The signal is the QQQ 15-minute 2 SD VWAP continuation, "
        "a 1R underlying stop and target, a 10-minute entry window, and a sale the same day at the stop, "
        "the target, or the 15:45 bar. The scored fill is the next open. One position. At most 5 fills a day. "
        "Fresh $2,500. Expiry is 1 DTE. Pricing is the unscaled prior close and a 1 cent market, "
        "and the same structures at 1.20 times that close. "
        "contracts = floor(f * equity / (ask * 100)), using the unslipped ask. "
        "If that rounds to 0, buy 1 contract when 1 contract costs at most 2f of equity, otherwise skip. "
        "The size is decided once, from that ask. Size slippage is then added on the entry and on the exit. "
        "If the slipped ticket does not fit settled cash, skip the whole ticket. "
        "The size is not cut down and is not recomputed after slippage. "
        "Current equity is settled cash plus credits due. Credits whose settlement date is this session "
        "are added to settled cash first, before this fill's debit is subtracted. "
        "The half-spread is the 1 cent market. Size slippage is an extra $0.01 per share for every 10 contracts "
        "beyond the first 10, on the way in and on the way out. "
        "The charge is 0.01 * (contracts - 10) / 10 once the ticket is larger than 10. "
        "Ten contracts pay the half-spread only. "
        f"Fractions: {_fraction_list()}. "
        "Liquidity assumption, not a measured QQQ quote tape: the inside displayed size is "
        f"{INSIDE_SIZE} contracts. A few levels means the inside quote plus the next {LEVELS - 1}, "
        f"and each of those {LEVELS} levels is assumed equal to that inside size. "
        f"The book takes {PARTICIPATION:.0%} of that displayed size. "
        f"Realistic cap = min({RESEARCH_CAP}, floor({PARTICIPATION:.2f} * {INSIDE_SIZE} * {LEVELS})) "
        f"= {REALISTIC_CAP} contracts. "
        "The same fractions are also scored at caps of 10 and of 25. "
        f"The sweet spot uses only the realistic cap of {REALISTIC_CAP}, with size slippage, "
        "at 1.20 times the prior close. "
        "It is the largest fraction that clears the gate on both the train window and the holdout window. "
        f"The gate is at least {GATE_TRADES} trades, profit factor at least {GATE_PF:.2f}, "
        f"Sharpe at least {GATE_SHARPE:.2f}, and max drawdown no worse than {100.0 * GATE_DRAWDOWN:.0f}%. "
        "If no fraction clears that gate on both windows, the sweet spot is the fraction with the highest "
        "holdout 12-month median ending among those whose max drawdown is no worse than "
        f"{100.0 * DD_FALLBACK:.0f}% on both windows. "
        "A tie on that holdout median goes to the higher train 12-month median, then to the larger fraction. "
        "If none stay inside that drawdown on both windows, no fraction is recommended. "
        "The 1-per-$2,500 tier is scored under the same slippage and the same two volatilities. "
        "Its lot is 1 to 5, so these caps and the extra slippage do not change its fill. "
        "This score does not change the sandbox book."
    )


SWEET_RULE = _rule_text()


def _fraction_label(fraction: float) -> str:
    return f"{100.0 * float(fraction):.0f}%"


def choose_sweet_spot(rows: list[dict]) -> dict:
    """The pre-registered pick. Largest both-window gate pass, else best median inside -40%."""
    compound = [
        row
        for row in rows
        if row.get("mode") == "compound" and row.get("iv") == DECISION_IV and int(row.get("cap")) == REALISTIC_CAP
    ]
    fractions: list[float] = []
    for row in compound:
        fraction = float(row["fraction"])
        if not any(abs(fraction - seen) < 1e-12 for seen in fractions):
            fractions.append(fraction)
    fractions.sort()

    def _pair(fraction: float) -> tuple[dict | None, dict | None]:
        train = hold = None
        for row in compound:
            if abs(float(row["fraction"]) - fraction) >= 1e-12:
                continue
            if row["window"] == "train":
                train = row
            elif row["window"] == "holdout":
                hold = row
        return train, hold

    clearing = []
    for fraction in fractions:
        train, hold = _pair(fraction)
        if train is None or hold is None:
            continue
        if train.get("gate_pass") and hold.get("gate_pass"):
            clearing.append(fraction)
    if clearing:
        chosen = max(clearing)
        return {
            "fraction": chosen,
            "selector": "largest_both_gate",
            "reason": (
                f"{_fraction_label(chosen)} is the largest fraction that clears the gate on both windows "
                f"at 1.20x, the {REALISTIC_CAP}-contract cap, and size slippage."
            ),
        }

    fallback = []
    for fraction in fractions:
        train, hold = _pair(fraction)
        if train is None or hold is None:
            continue
        train_dd = train.get("max_drawdown")
        hold_dd = hold.get("max_drawdown")
        train_median = train.get("median_ending")
        hold_median = hold.get("median_ending")
        if None in (train_dd, hold_dd, train_median, hold_median):
            continue
        if float(train_dd) + 1e-9 < DD_FALLBACK or float(hold_dd) + 1e-9 < DD_FALLBACK:
            continue
        fallback.append((float(hold_median), float(train_median), fraction))
    if not fallback:
        return {
            "fraction": None,
            "selector": "none",
            "reason": (
                "No fraction clears the gate on both windows at 1.20x with the realistic cap, "
                "and none keep max drawdown at or above -40% on both windows."
            ),
        }
    _hold_median, _train_median, chosen = max(fallback)
    return {
        "fraction": chosen,
        "selector": "best_median_dd40",
        "reason": (
            f"No fraction clears the gate on both windows at 1.20x with the {REALISTIC_CAP}-contract cap. "
            f"{_fraction_label(chosen)} has the highest holdout 12-month median among fractions whose "
            "max drawdown is no worse than -40% on both windows."
        ),
    }


def _find(rows: list[dict], mode: str, fraction, cap: int, iv_label: str, window: str) -> dict:
    for row in rows:
        if row["mode"] != mode or row["iv"] != iv_label or int(row["cap"]) != int(cap) or row["window"] != window:
            continue
        if mode == "compound" and abs(float(row["fraction"]) - float(fraction)) >= 1e-12:
            continue
        return row
    raise KeyError((mode, fraction, cap, iv_label, window))


def _blurb(row: dict) -> str:
    label = "Holdout" if row["window"] == "holdout" else "Train"
    return (
        f"{label} ends at {_money(row['ending_equity'])} on {row['trades']} trades, "
        f"max drawdown {_pct(row['max_drawdown'])}, Sharpe {_num(row['sharpe'])}, "
        f"profit factor {_num(row['profit_factor'])}, "
        f"12-month median {_money(row['median_ending'])}, 10th percentile {_money(row['p10_ending'])}, "
        f"P($10k in 4/8/12 months) {_pct(row['p_reach_4'])} / {_pct(row['p_reach_8'])} / {_pct(row['p_reach_12'])}, "
        f"P(ruin) {_pct(row['p_ruin'])}, gate {row['gate']}"
    )


def _both_pass(rows: list[dict]) -> list[str]:
    seen = []
    keys = []
    for row in rows:
        key = (row["mode"], row.get("fraction"), int(row["cap"]), row["iv"])
        if key in keys:
            continue
        keys.append(key)
        train = _find(rows, row["mode"], row.get("fraction"), int(row["cap"]), row["iv"], "train")
        hold = _find(rows, row["mode"], row.get("fraction"), int(row["cap"]), row["iv"], "holdout")
        if train.get("gate_pass") and hold.get("gate_pass"):
            if row["mode"] == "tier":
                seen.append(f"1 per $2,500, cap {int(row['cap'])}, {row['iv']}")
            else:
                seen.append(f"{_fraction_label(row['fraction'])}, cap {int(row['cap'])}, {row['iv']}")
    return seen


def summary_paragraphs(rows: list[dict], choice: dict) -> str:
    """Plain-English read. The fraction comes from the pre-registered rule."""
    bits = [
        "QQQ Aggressive Compound still spends a fixed fraction of current equity on the 1 DTE premium. "
        "The signal, the 1R stop and target, and the same-day 15:45 flatten match the earlier score. "
        "The account starts at $2,500. This pass charges a size slippage and caps the ticket on a liquidity assumption.",
        (
            f"The liquidity number is an assumption, not a print from a QQQ 1 DTE quote tape. "
            f"Inside displayed size is {INSIDE_SIZE} contracts. A few levels means {LEVELS} levels "
            f"(the inside quote plus the next {LEVELS - 1}), each assumed equal to that size. "
            f"Participation is {PARTICIPATION:.0%}. "
            f"The realistic cap is min({RESEARCH_CAP}, floor({PARTICIPATION:.2f} * {INSIDE_SIZE} * {LEVELS})) "
            f"= {REALISTIC_CAP} contracts. Caps of 10 and 25 are scored beside it. "
            "The sweet spot uses the realistic cap only."
        ),
        choice["reason"],
    ]
    if choice["fraction"] is not None:
        fraction = float(choice["fraction"])
        hold = _find(rows, "compound", fraction, REALISTIC_CAP, DECISION_IV, "holdout")
        train = _find(rows, "compound", fraction, REALISTIC_CAP, DECISION_IV, "train")
        bits.append(
            f"Recommended fraction: {_fraction_label(fraction)}. "
            f"At 1.20 times the prior close and the {REALISTIC_CAP}-contract cap, {_blurb(hold)}. {_blurb(train)}."
        )
        base_hold = _find(rows, "compound", fraction, REALISTIC_CAP, BASE_IV, "holdout")
        base_train = _find(rows, "compound", fraction, REALISTIC_CAP, BASE_IV, "train")
        bits.append(
            f"The same {_fraction_label(fraction)} at the unscaled prior close, same cap and slippage: "
            f"{_blurb(base_hold)}. {_blurb(base_train)}."
        )
    decision = []
    for fraction in FRACTIONS:
        hold = _find(rows, "compound", fraction, REALISTIC_CAP, DECISION_IV, "holdout")
        train = _find(rows, "compound", fraction, REALISTIC_CAP, DECISION_IV, "train")
        decision.append(
            f"{_fraction_label(fraction)}: holdout {_money(hold['ending_equity'])}, "
            f"drawdown {_pct(hold['max_drawdown'])}, Sharpe {_num(hold['sharpe'])}, "
            f"profit factor {_num(hold['profit_factor'])}, median {_money(hold['median_ending'])}, "
            f"gate {hold['gate']}. "
            f"Train {_money(train['ending_equity'])}, drawdown {_pct(train['max_drawdown'])}, "
            f"Sharpe {_num(train['sharpe'])}, profit factor {_num(train['profit_factor'])}, "
            f"median {_money(train['median_ending'])}, gate {train['gate']}."
        )
    bits.append(
        f"Every fraction at 1.20 times the prior close, the {REALISTIC_CAP}-contract cap, and size slippage. "
        + " ".join(decision)
    )
    tier_bits = []
    for _scale, iv_label in IVS:
        hold = _find(rows, "tier", None, REALISTIC_CAP, iv_label, "holdout")
        train = _find(rows, "tier", None, REALISTIC_CAP, iv_label, "train")
        tier_bits.append(f"{iv_label}: {_blurb(hold)}. {_blurb(train)}.")
    bits.append(
        "The 1-per-$2,500 tier under the same slippage. Its lot stays between 1 and 5, "
        "so the extra slippage is zero and the cap does not bind. " + " ".join(tier_bits)
    )
    both = _both_pass(rows)
    if both:
        bits.append("Cells that clear the gate on both windows: " + "; ".join(both) + ".")
    else:
        bits.append("No scored cell clears the gate on both windows.")
    bits.append(
        "The live QQQ Aggressive 1 DTE book stays one contract. This table does not change an order."
    )
    return "\n\n".join(bits)


def _line(row: dict) -> str:
    reach = f"{_pct(row['p_reach_4'])} / {_pct(row['p_reach_8'])} / {_pct(row['p_reach_12'])}"
    name = "1 per $2,500" if row["mode"] == "tier" else _fraction_label(row["fraction"])
    cells = [
        name,
        str(int(row["cap"])),
        row["iv"],
        row["window"],
        str(row["trades"]),
        _num(row["profit_factor"]),
        _num(row["sharpe"]),
        _pct(row["max_drawdown"]),
        _money(row["ending_equity"]),
        _money(row["median_ending"]),
        _money(row["p10_ending"]),
        reach,
        _pct(row["p_ruin"]),
        row["gate"],
    ]
    return "| " + " | ".join(cells) + " |"


def _markdown(payload: dict) -> str:
    header = (
        "| Sizing | Cap | IV | Window | Trades | PF | Sharpe | Max DD | Ending | "
        "Median 12m | P10 12m | P($10k 4/8/12m) | P(ruin) | Gate |"
    )
    rule = "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |"
    lines = [
        "# QQQ Aggressive Compound, realistic fills",
        "",
        "Backtest only. Nothing was sent to a broker. Live trading stays off. The sandbox forward books were not changed.",
        "",
        payload["summary"],
        "",
        "## The rule, written down first",
        "",
        payload["rule"],
        "",
        "Train is 2017-02-16 through 2023-12-31. Holdout is a fresh account from 2024-01-01 through 2026-10-06. "
        "Ending, profit factor, Sharpe, max drawdown, and the gate are that one account. "
        "The median, the 10th percentile, the three reach rates, and P(ruin) start a fresh $2,500 on every later "
        "session that still has that many months inside the window. "
        "Reach is equity of $10,000. Ruin is equity under $500. "
        f"The usual gate is at least {GATE_TRADES} trades, profit factor at least {GATE_PF:.2f}, "
        f"Sharpe at least {GATE_SHARPE:.2f}, and max drawdown no worse than {100.0 * GATE_DRAWDOWN:.0f}%. "
        "A both-window pass needs that gate on the train row and the holdout row.",
        "",
        f"## Decision grid: 1.20x, cap {REALISTIC_CAP}",
        "",
        header,
        rule,
    ]
    for row in payload["rows"]:
        if row["mode"] == "compound" and row["iv"] == DECISION_IV and int(row["cap"]) == REALISTIC_CAP:
            lines.append(_line(row))
    lines.extend(["", f"## Realistic cap {REALISTIC_CAP}, both volatilities", "", header, rule])
    for row in payload["rows"]:
        if row["mode"] == "compound" and int(row["cap"]) == REALISTIC_CAP:
            lines.append(_line(row))
    for cap in CAPS:
        if cap == REALISTIC_CAP:
            continue
        lines.extend(["", f"## Cap {cap}, both volatilities", "", header, rule])
        for row in payload["rows"]:
            if row["mode"] == "compound" and int(row["cap"]) == cap:
                lines.append(_line(row))
    lines.extend(["", "## 1 per $2,500 under the same slippage", "", header, rule])
    for row in payload["rows"]:
        if row["mode"] == "tier":
            lines.append(_line(row))
    lines.extend(
        [
            "",
            "This score does not change an order. The live QQQ Aggressive 1 DTE book stays one contract.",
            "",
        ]
    )
    return "\n".join(lines)


def _flatten(mode: str, fraction, cap: int, iv_label: str, scale: float, scored: dict) -> list[dict]:
    rows = []
    for window in ("train", "holdout"):
        rows.append(
            {
                "book": "QQQ Aggressive",
                "mode": mode,
                "expiry": "1 DTE",
                "iv": iv_label,
                "scale": float(scale),
                "fraction": fraction,
                "cap": int(cap),
                "slip": True,
                "stake": STAKE,
                "window": window,
                **scored[window],
            }
        )
    return rows


def _min_ask(cands: list[tuple]) -> float:
    return min(float(row[6]) for row in cands)


def run() -> dict:
    if abs(PREMIUM_UNIT - 100.0) > 1e-9:
        raise SystemExit("The premium unit is not 100. The sweet-spot table was not written.")
    if REALISTIC_CAP != 30 or CAPS != (10, 25, 30):
        raise SystemExit("The liquidity cap is not the pre-registered 30. The sweet-spot table was not written.")
    if tuple(round(100.0 * fraction) for fraction in FRACTIONS) != (2, 3, 4, 5, 6, 7, 8, 10, 12):
        raise SystemExit("The fraction grid is not the pre-registered list. The sweet-spot table was not written.")
    print("loading QQQ", flush=True)
    qqq = _load_bars("QQQ")
    iv = prior_iv(_load_series("VIX1D"), _load_series("VIX"))
    qqq15 = to_fifteen(qqq)
    structures = vwap_structures(qqq15, "QQQ")
    sessions = session_dates(qqq15)
    print(f"signals {len(structures)} sessions {len(sessions)}", flush=True)
    priced = {}
    for scale, iv_label in IVS:
        print(f"pricing {iv_label}", flush=True)
        priced[iv_label] = price_structures(structures, iv, scale, "0.01", dte=1)
        lowest = _min_ask(priced[iv_label])
        print(f"  rows {len(priced[iv_label])} min ask {lowest:.4f}", flush=True)
        if lowest <= 0.02:
            raise SystemExit("An ask is at or under $0.02, so the 1 cent bid can floor. The table was not written.")
    published = _published_baselines()
    print("tier checksum, base IV, slippage on", flush=True)
    tier_base = score_mode(priced[BASE_IV], sessions, "tier", 0.0, REALISTIC_CAP, True)
    for window in ("train", "holdout"):
        _check_baseline(f"tier {window}", tier_base[window], published[("tier", window)])
    rows = _flatten("tier", None, REALISTIC_CAP, BASE_IV, 1.0, tier_base)
    print("tier 1.20x", flush=True)
    tier_rich = score_mode(priced[DECISION_IV], sessions, "tier", 0.0, REALISTIC_CAP, True)
    rows.extend(_flatten("tier", None, REALISTIC_CAP, DECISION_IV, 1.2, tier_rich))
    for cap in CAPS:
        for scale, iv_label in IVS:
            for fraction in FRACTIONS:
                label = _fraction_label(fraction)
                print(f"compound {label} cap {cap} {iv_label}", flush=True)
                scored = score_mode(priced[iv_label], sessions, "compound", fraction, cap, True)
                rows.extend(_flatten("compound", fraction, cap, iv_label, scale, scored))
                hold = scored["holdout"]
                print(
                    f"  holdout trades {hold['trades']} ending {hold['ending_equity']:.2f} "
                    f"dd {100.0 * float(hold['max_drawdown']):.1f}% gate {hold['gate']}",
                    flush=True,
                )
    choice = choose_sweet_spot(rows)
    print(f"sweet spot {choice}", flush=True)
    payload = {
        "rule": SWEET_RULE,
        "stake": STAKE,
        "fractions": list(FRACTIONS),
        "caps": list(CAPS),
        "realistic_cap": REALISTIC_CAP,
        "inside_size": INSIDE_SIZE,
        "levels": LEVELS,
        "participation": PARTICIPATION,
        "decision_iv": DECISION_IV,
        "fallback_drawdown": DD_FALLBACK,
        "sweet_spot": choice,
        "rows": rows,
        "summary": "",
    }
    payload["summary"] = summary_paragraphs(rows, choice)
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
