"""QQQ Aggressive Compound: constant-percentage premium sizing. Backtests only.

Writes reports/odte_compound.md. Does not place an order and does not change
the sandbox forward books. The rule below was written down before the score.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.odte_calibration import (
    GOAL,
    HOLDOUT_END,
    HOLDOUT_START,
    RUIN,
    TRAIN_END,
    TRAIN_START,
    _add_months,
    calibrate,
    contracts_for,
    price_structures,
    session_dates,
    to_fifteen,
    vwap_structures,
)
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.research_odte_calibration import _load_bars, _load_series
from webull_bot.chart_reads.research_odte_stake2500 import (
    JSON_PATH as STAKE_JSON,
    STAKE,
    TIER_DAILY_CAP,
    gate_label,
    tier_contracts,
)
from webull_bot.chart_reads.vwap_band import metrics_from, passes_gate
from webull_bot.options.fees import (
    CAT_PER_CONTRACT,
    CONTRACT_MULTIPLIER,
    OCC_PER_CONTRACT,
    ORF_PER_CONTRACT,
    SEC_PER_DOLLAR,
    TAF_MIN,
    option_leg_fees,
)

ROOT = Path(__file__).resolve().parents[3]
MD_PATH = ROOT / "reports" / "odte_compound.md"
JSON_PATH = ROOT / "reports" / "odte_compound.json"

# Written down before the score. The result does not change these.
FRACTIONS = (0.05, 0.10, 0.15, 0.20)
PRIMARY_FRACTION = 0.10
CONTRACT_CAP = 50
DAILY_CAP = TIER_DAILY_CAP
PREMIUM_UNIT = float(CONTRACT_MULTIPLIER)
HORIZONS = (4, 8, 12)
COMPOUND_RULE = (
    "QQQ Aggressive Compound. The signal is the QQQ 15-minute 2 SD VWAP continuation, "
    "a 1R underlying stop and target, a 10-minute entry window, and a sale the same day at the stop, "
    "the target, or the 15:45 bar. The scored fill is the next open. One position. At most 5 fills a day. Fresh $2,500. "
    "The primary expiry is 1 DTE at the unscaled prior close and a 1 cent market, the same "
    "pricing as the live 1 DTE book. 0 DTE at 1.67 times the prior close and a 1 cent market "
    "is the reference. Each fill spends a fixed fraction f of current equity on premium. "
    "Current equity is settled cash plus credits due. Credits due are sale proceeds that have "
    "not settled. Credits whose settlement date is this session are added to settled cash first, "
    "before this fill's debit is subtracted. "
    "contracts = floor(f * equity / (ask * 100)). "
    "If that rounds to 0, buy 1 contract when 1 contract costs at most 2f of equity, otherwise skip. "
    "Cost is ask * 100. Cap at 50 contracts. "
    "If the whole ticket does not fit settled cash, skip it. The size is not cut down. "
    "The fractions are 5%, 10%, 15%, and 20%. 10% is the primary. "
    "The 1 DTE 10% cell is also scored at 0.80 times and at 1.20 times the prior close."
)


def size_slippage(qty: int) -> float:
    """Extra dollars per share. $0.01 for every 10 contracts past the first 10.

    Ten contracts pay the half-spread only. Twenty pay one extra cent per share
    on the way in and on the way out. The charge scales with the contracts past 10.
    """
    if qty <= 10:
        return 0.0
    return 0.01 * (qty - 10) / 10.0


def _bid_from_credit(credit: float) -> float:
    """The one-contract bid inside a sell credit. Fees are the published one-lot schedule."""
    fixed = ORF_PER_CONTRACT + OCC_PER_CONTRACT + CAT_PER_CONTRACT + TAF_MIN
    scale = PREMIUM_UNIT * (1.0 - SEC_PER_DOLLAR)
    bid = (float(credit) + fixed) / scale
    if bid < 1e-9:
        return 0.0
    return bid


def slipped_fill(ask: float, qty: int, debit: float, credit: float) -> tuple[float, float]:
    """Per-contract debit and credit after size slippage.

    ``debit`` and ``credit`` already include the 1 cent half-spread and the modeled
    exit. Ten contracts and fewer are returned unchanged. A larger ticket pays the
    extra on the ask and gives the same extra back on the bid.
    """
    extra = size_slippage(qty)
    if extra <= 0.0 or qty < 1:
        return float(debit), float(credit)
    entry = float(ask) + extra
    new_debit = entry * PREMIUM_UNIT + option_leg_fees(1, entry, sell=False)
    exit_px = max(0.0, _bid_from_credit(credit) - extra)
    new_credit = exit_px * PREMIUM_UNIT - option_leg_fees(1, exit_px, sell=True)
    return new_debit, new_credit


def compound_contracts(equity: float, ask: float, fraction: float, cap: int = CONTRACT_CAP) -> tuple[int, str]:
    """The pre-registered lot. The tag is size, rescue, cap, dear, or skip."""
    unit = float(ask) * PREMIUM_UNIT
    if equity <= 0 or unit <= 0 or fraction <= 0:
        return 0, "skip"
    raw = math.floor((float(fraction) * float(equity)) / unit + 1e-9)
    if raw <= 0:
        if unit <= 2.0 * float(fraction) * float(equity) + 1e-6:
            return 1, "rescue"
        return 0, "dear"
    if raw > cap:
        return int(cap), "cap"
    return int(raw), "size"


def _mark_equity(settled: float, pending: list[tuple[date, float]]) -> float:
    return settled + sum(amount for _when, amount in pending)


def _settle(settled: float, pending: list[tuple[date, float]], day: date) -> tuple[float, list[tuple[date, float]]]:
    if not pending:
        return settled, pending
    still = []
    for when, amount in pending:
        if when <= day:
            settled += amount
        else:
            still.append((when, amount))
    return settled, still


def _resolve(
    mode: str,
    fraction: float,
    equity: float,
    ask: float,
    debit: float,
    credit: float,
    settled: float,
    cap: int = CONTRACT_CAP,
    slip: bool = False,
) -> tuple[int, str, bool, float, float]:
    """Lot, tag, cap flag, and the per-contract debit and credit actually charged."""
    if mode == "fixed":
        qty, tag = 1, "fixed"
    elif mode == "tier":
        qty, tag = tier_contracts(equity), "tier"
        if qty > cap:
            qty, tag = int(cap), "cap"
    else:
        qty, tag = compound_contracts(equity, ask, fraction, cap)
    capped = tag == "cap"
    if slip and qty >= 1:
        debit, credit = slipped_fill(ask, qty, debit, credit)
    if qty < 1:
        return 0, tag, capped, debit, credit
    if contracts_for(qty, settled, debit) < 1:
        return 0, "cash", capped, debit, credit
    return qty, tag, capped, debit, credit


def _empty_info() -> dict:
    return {
        "lots": [],
        "cap_fills": 0,
        "cap_signals": 0,
        "rescues": 0,
        "dear_skips": 0,
        "cash_skips": 0,
        "reached": None,
        "ruined": False,
    }


def _note(info: dict, qty: int, tag: str, capped: bool, day: date, equity: float) -> None:
    if capped:
        info["cap_signals"] += 1
    if qty < 1:
        if tag == "dear":
            info["dear_skips"] += 1
        elif tag == "cash":
            info["cash_skips"] += 1
        return
    info["lots"].append(qty)
    if capped:
        info["cap_fills"] += 1
    elif tag == "rescue":
        info["rescues"] += 1
    if info["reached"] is None and equity >= GOAL:
        info["reached"] = day
    if equity < RUIN:
        info["ruined"] = True


def walk_daily(
    cands: list[tuple],
    sessions: list[date],
    mode: str,
    fraction: float,
    cap: int = CONTRACT_CAP,
    slip: bool = False,
) -> tuple[pd.Series, list[float], dict]:
    """One account from the first session. Same settlement as the fixed-lot walk."""
    info = _empty_info()
    if not sessions:
        index = pd.DatetimeIndex([pd.Timestamp(TRAIN_START)])
        return pd.Series([STAKE], index=index), [], info
    by_day: dict[date, list[tuple]] = {}
    for row in cands:
        by_day.setdefault(row[0], []).append(row)
    settled = float(STAKE)
    pending: list[tuple[date, float]] = []
    pnls: list[float] = []
    values = []
    for day in sessions:
        settled, pending = _settle(settled, pending, day)
        taken_n = 0
        busy = -1
        for _day, due, fill_i, exit_i, debit, credit, ask in by_day.get(day, []):
            if taken_n >= DAILY_CAP:
                continue
            if fill_i <= busy:
                continue
            equity = _mark_equity(settled, pending)
            qty, tag, capped, used_debit, used_credit = _resolve(
                mode, fraction, equity, float(ask), float(debit), float(credit), settled, cap, slip
            )
            if qty < 1:
                _note(info, qty, tag, capped, day, equity)
                continue
            settled -= qty * used_debit
            pending.append((due, qty * used_credit))
            pnls.append(qty * (used_credit - used_debit))
            _note(info, qty, tag, capped, day, _mark_equity(settled, pending))
            taken_n += 1
            busy = exit_i
        marked = _mark_equity(settled, pending)
        if info["reached"] is None and marked >= GOAL:
            info["reached"] = day
        if marked < RUIN:
            info["ruined"] = True
        values.append(marked)
    index = pd.DatetimeIndex([pd.Timestamp(day) for day in sessions])
    return pd.Series(values, index=index, dtype=float), pnls, info


def walk_path(
    cands: list[tuple], start: date, end: date, mode: str, fraction: float, cap: int = CONTRACT_CAP, slip: bool = False
) -> dict:
    """Fill-by-fill path used for the rolling starts. Same clock as the earlier studies."""
    settled = float(STAKE)
    pending: list[tuple[date, float]] = []
    busy = -1
    taken_day = None
    taken_n = 0
    equity = float(STAKE)
    reached = None
    ruined = False
    for day, due, fill_i, exit_i, debit, credit, ask in cands:
        if day < start or day > end:
            continue
        settled, pending = _settle(settled, pending, day)
        if taken_day != day:
            taken_day = day
            taken_n = 0
            busy = -1
        if taken_n >= DAILY_CAP:
            continue
        if fill_i <= busy:
            continue
        marked = _mark_equity(settled, pending)
        qty, _tag, _capped, used_debit, used_credit = _resolve(
            mode, fraction, marked, float(ask), float(debit), float(credit), settled, cap, slip
        )
        if qty < 1:
            continue
        settled -= qty * used_debit
        pending.append((due, qty * used_credit))
        taken_n += 1
        busy = exit_i
        equity = _mark_equity(settled, pending)
        if reached is None and equity >= GOAL:
            reached = day
        if equity < RUIN:
            ruined = True
    return {"ending": equity, "reached": reached, "ruined": ruined}


def _bisect_left(ords: list[int], target: int) -> int:
    lo, hi = 0, len(ords)
    while lo < hi:
        mid = (lo + hi) // 2
        if ords[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _bisect_right(ords: list[int], target: int) -> int:
    lo, hi = 0, len(ords)
    while lo < hi:
        mid = (lo + hi) // 2
        if ords[mid] <= target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def rolling_bundle(
    cands: list[tuple],
    sessions: list[date],
    window_end: date,
    mode: str,
    fraction: float,
    cap: int = CONTRACT_CAP,
    slip: bool = False,
) -> dict:
    """12-month endings, plus the chance of $10k inside 4, 8, and 12 months."""
    ords = [row[0].toordinal() for row in cands]
    cached: dict[tuple[date, int], dict] = {}

    def _path(start: date, months: int) -> dict:
        key = (start, months)
        saved = cached.get(key)
        if saved is not None:
            return saved
        horizon = _add_months(start, months)
        left = _bisect_left(ords, start.toordinal())
        right = _bisect_right(ords, horizon.toordinal())
        saved = walk_path(cands[left:right], start, horizon, mode, fraction, cap, slip)
        cached[key] = saved
        return saved

    twelve = [day for day in sessions if _add_months(day, 12) <= window_end]
    twelve_set = set(twelve)
    endings = []
    ruins = 0
    reach_12 = 0
    day_counts = []
    for start in twelve:
        path = _path(start, 12)
        endings.append(path["ending"])
        if path["ruined"]:
            ruins += 1
        reached = path["reached"]
        horizon = _add_months(start, 12)
        if reached is not None and reached <= horizon:
            reach_12 += 1
            day_counts.append((reached - start).days)
    count_12 = len(twelve)
    out = {
        "starts_12": count_12,
        "median_ending": None if not endings else float(np.median(endings)),
        "p10_ending": None if not endings else float(np.percentile(endings, 10)),
        "p_reach_12": None if not count_12 else reach_12 / count_12,
        "p_ruin": None if not count_12 else ruins / count_12,
        "median_days": None if not day_counts else float(np.median(day_counts)),
        "reached_12": reach_12,
    }
    for months, key in ((4, "p_reach_4"), (8, "p_reach_8")):
        eligible = [day for day in sessions if _add_months(day, months) <= window_end]
        if not eligible:
            out[key] = None
            out[f"starts_{months}"] = 0
            continue
        hits = 0
        for start in eligible:
            if start in twelve_set:
                path = _path(start, 12)
                horizon = _add_months(start, months)
                reached = path["reached"]
                if reached is not None and reached <= horizon:
                    hits += 1
            else:
                path = _path(start, months)
                if path["reached"] is not None:
                    hits += 1
        out[key] = hits / len(eligible)
        out[f"starts_{months}"] = len(eligible)
    return out


def _lot_summary(lots: list[int], trades: int, cap_fills: int) -> dict:
    if not lots:
        return {"median_qty": None, "max_qty": None, "cap_fills": 0, "cap_rate": None}
    return {
        "median_qty": float(np.median(lots)),
        "max_qty": int(max(lots)),
        "cap_fills": int(cap_fills),
        "cap_rate": (cap_fills / trades) if trades else None,
    }


def score_mode(
    cands, sessions, mode: str, fraction: float, cap: int = CONTRACT_CAP, slip: bool = False
) -> dict:
    out = {}
    for window, start, end in (
        ("train", TRAIN_START, TRAIN_END),
        ("holdout", HOLDOUT_START, HOLDOUT_END),
    ):
        window_sessions = [day for day in sessions if start <= day <= end]
        equity, pnls, info = walk_daily(cands, window_sessions, mode, fraction, cap, slip)
        metrics = metrics_from(equity, pnls, STAKE)
        rolling = rolling_bundle(cands, window_sessions, end, mode, fraction, cap, slip)
        reached = info["reached"]
        origin = window_sessions[0] if window_sessions else None
        days = None if reached is None or origin is None else (reached - origin).days
        packed = {
            "trades": int(metrics.get("trades") or 0),
            "win_rate": metrics.get("win_rate"),
            "profit_factor": metrics.get("profit_factor"),
            "sharpe": metrics.get("sharpe"),
            "max_drawdown": metrics.get("max_drawdown"),
            "ending_equity": metrics.get("ending_equity"),
            "median_ending": rolling["median_ending"],
            "p10_ending": rolling["p10_ending"],
            "p_reach_4": rolling["p_reach_4"],
            "p_reach_8": rolling["p_reach_8"],
            "p_reach_12": rolling["p_reach_12"],
            "median_days": rolling["median_days"],
            "p_ruin": rolling["p_ruin"],
            "gate": gate_label(metrics),
            "gate_pass": bool(passes_gate(metrics)),
            "days_to_goal": days,
            "account_ruined": bool(info["ruined"]),
            "cap_fills": info["cap_fills"],
            "cap_signals": info["cap_signals"],
            "rescues": info["rescues"],
            "dear_skips": info["dear_skips"],
            "cash_skips": info["cash_skips"],
            **_lot_summary(info["lots"], int(metrics.get("trades") or 0), info["cap_fills"]),
        }
        out[window] = packed
    return out


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


def _days(value) -> str:
    if value is None:
        return "n/a"
    return str(int(round(float(value))))


def _fraction_label(fraction) -> str:
    if fraction in (None, "", "1 contract", "tier"):
        return str(fraction)
    return f"{100.0 * float(fraction):.0f}%"


def _flatten(name: str, mode: str, expiry: str, iv_label: str, scale: float, fraction, scored: dict) -> list[dict]:
    rows = []
    for window in ("train", "holdout"):
        rows.append(
            {
                "book": "QQQ Aggressive",
                "name": name,
                "mode": mode,
                "expiry": expiry,
                "iv": iv_label,
                "scale": float(scale),
                "fraction": fraction,
                "stake": STAKE,
                "window": window,
                **scored[window],
            }
        )
    return rows


def _pair(rows: list[dict]) -> list[dict]:
    keys = []
    for row in rows:
        key = (row["name"], row["expiry"], row["iv"])
        if key not in keys:
            keys.append(key)
    by = {(row["name"], row["expiry"], row["iv"], row["window"]): row for row in rows}
    cells = []
    for name, expiry, iv_label in keys:
        train = by[(name, expiry, iv_label, "train")]
        hold = by[(name, expiry, iv_label, "holdout")]
        cells.append({"name": name, "expiry": expiry, "iv": iv_label, "train": train, "holdout": hold})
    return cells


def _side(row: dict) -> str:
    label = "Holdout" if row["window"] == "holdout" else "Train"
    return (
        f"{label} {_money(row['ending_equity'])} on {row['trades']} trades, "
        f"win {_pct(row['win_rate'])}, profit factor {_num(row['profit_factor'])}, "
        f"Sharpe {_num(row['sharpe'])}, max drawdown {_pct(row['max_drawdown'])}, "
        f"12-month median {_money(row['median_ending'])}, 10th percentile {_money(row['p10_ending'])}, "
        f"P($10k in 4/8/12 months) {_pct(row['p_reach_4'])} / {_pct(row['p_reach_8'])} / {_pct(row['p_reach_12'])}, "
        f"median days to $10k {_days(row['median_days'])}, P(ruin) {_pct(row['p_ruin'])}, "
        f"gate {row['gate']}"
    )


def _cap_phrase(row: dict) -> str:
    trades = int(row["trades"] or 0)
    fills = int(row["cap_fills"] or 0)
    if trades == 0:
        return "no fills"
    rate = fills / trades
    return f"{fills} of {trades} fills ({_pct(rate)}) stopped at {CONTRACT_CAP} contracts"


def summary_paragraphs(cells: list[dict]) -> str:
    """Plain-English read of the pre-registered cells. The rule is not revised here."""
    by = {(cell["name"], cell["expiry"], cell["iv"]): cell for cell in cells}
    primary = by[("10% of equity", "1 DTE", "prior close, 1 cent")]
    fixed = by[("1 contract", "1 DTE", "prior close, 1 cent")]
    tier = by[("1 per $2,500", "1 DTE", "prior close, 1 cent")]
    base_iv = {"prior close, 1 cent", "x1.67 prior close, 1 cent"}
    compound_both = [
        f"{cell['name']} {cell['expiry']}"
        for cell in cells
        if str(cell["name"]).endswith("of equity")
        and cell["iv"] in base_iv
        and cell["train"]["gate_pass"]
        and cell["holdout"]["gate_pass"]
    ]
    holdout_only = [
        f"{cell['name']} {cell['expiry']}"
        for cell in cells
        if str(cell["name"]).endswith("of equity")
        and cell["iv"] in base_iv
        and cell["holdout"]["gate_pass"]
        and not cell["train"]["gate_pass"]
    ]
    cleared = (
        "The fixed 1-contract book and the 1-per-$2,500 tier clear the usual gate on both windows. "
    )
    if compound_both:
        cleared += "Compound cells that also clear both windows: " + ", ".join(compound_both) + ". "
    else:
        cleared += "No compound fraction clears both windows. "
    if holdout_only:
        cleared += "Holdout gate only: " + ", ".join(holdout_only) + "."
    bits = [
        "QQQ Aggressive Compound spends a fixed fraction of current equity on premium. "
        "10% is the primary fraction. The signal, the 1R stop and target, and the same-day 15:45 flatten "
        "match the other QQQ Aggressive scores. The account starts at $2,500.",
        cleared,
        (
            f"At 10% and 1 DTE, {_side(primary['holdout'])}. {_side(primary['train'])}."
        ),
        (
            f"The fixed 1-contract 1 DTE book, on this same reach clock, {_side(fixed['holdout'])}. "
            f"{_side(fixed['train'])}."
        ),
        (
            f"The 1-contract-per-$2,500 tier, on this same reach clock, {_side(tier['holdout'])}. "
            f"{_side(tier['train'])}."
        ),
    ]
    other = []
    for fraction in FRACTIONS:
        if abs(fraction - PRIMARY_FRACTION) < 1e-9:
            continue
        label = _fraction_label(fraction)
        cell = by[(f"{label} of equity", "1 DTE", "prior close, 1 cent")]
        other.append(
            f"{label} of equity, 1 DTE: holdout {_money(cell['holdout']['ending_equity'])} "
            f"on {cell['holdout']['trades']} trades, drawdown {_pct(cell['holdout']['max_drawdown'])}, "
            f"gate {cell['holdout']['gate']}. Train {_money(cell['train']['ending_equity'])} "
            f"on {cell['train']['trades']} trades, drawdown {_pct(cell['train']['max_drawdown'])}, "
            f"gate {cell['train']['gate']}."
        )
    bits.append("The other 1 DTE fractions. " + " ".join(other))
    zero_bits = []
    for fraction in FRACTIONS:
        label = _fraction_label(fraction)
        cell = by[(f"{label} of equity", "0 DTE", "x1.67 prior close, 1 cent")]
        zero_bits.append(
            f"{label}: holdout {_money(cell['holdout']['ending_equity'])} on {cell['holdout']['trades']} trades, "
            f"gate {cell['holdout']['gate']}; train {_money(cell['train']['ending_equity'])} "
            f"on {cell['train']['trades']} trades, gate {cell['train']['gate']}"
        )
    bits.append(
        "0 DTE at 1.67 times the prior close and a 1 cent market, same fractions. " + ". ".join(zero_bits) + "."
    )
    shock = []
    for iv_label, title in (
        ("0.80x prior close, 1 cent", "0.80x"),
        ("prior close, 1 cent", "base"),
        ("1.20x prior close, 1 cent", "1.20x"),
    ):
        cell = by[("10% of equity", "1 DTE", iv_label)]
        shock.append(
            f"{title} holdout {_money(cell['holdout']['ending_equity'])} on {cell['holdout']['trades']} trades "
            f"(gate {cell['holdout']['gate']}), train {_money(cell['train']['ending_equity'])} "
            f"on {cell['train']['trades']} trades (gate {cell['train']['gate']})"
        )
    bits.append("1 DTE at 10%, with the prior close moved 20% either way. " + ". ".join(shock) + ".")
    cap_bits = []
    for cell in cells:
        if cell["name"].endswith("of equity") and cell["iv"] in {"prior close, 1 cent", "x1.67 prior close, 1 cent"}:
            hold = cell["holdout"]
            train = cell["train"]
            if int(hold["cap_fills"] or 0) or int(train["cap_fills"] or 0):
                cap_bits.append(
                    f"{cell['name']} {cell['expiry']}: holdout {_cap_phrase(hold)}, train {_cap_phrase(train)}"
                )
    if cap_bits:
        bits.append("The 50-contract cap binds on these cells. " + ". ".join(cap_bits) + ".")
    else:
        bits.append("The 50-contract cap does not bind on any base fill. The formula never asked for more than 50.")
    return "\n\n".join(bits)


def _line(row: dict) -> str:
    cells = [
        row["name"],
        row["expiry"],
        row["iv"],
        _fraction_label(row["fraction"]) if row["mode"] == "compound" else row["name"],
        row["window"],
        str(row["trades"]),
        _pct(row["win_rate"]),
        _num(row["profit_factor"]),
        _num(row["sharpe"]),
        _pct(row["max_drawdown"]),
        _money(row["ending_equity"]),
        _money(row["median_ending"]),
        _money(row["p10_ending"]),
        _pct(row["p_reach_4"]),
        _pct(row["p_reach_8"]),
        _pct(row["p_reach_12"]),
        _days(row["median_days"]),
        _pct(row["p_ruin"]),
        row["gate"],
    ]
    return "| " + " | ".join(cells) + " |"


def _markdown(payload: dict) -> str:
    header = (
        "| Sizing | Expiry | IV | Fraction | Window | Trades | Win | PF | Sharpe | Max DD | Ending | "
        "Median 12m | P10 12m | P($10k 4m) | P($10k 8m) | P($10k 12m) | Median days | P(ruin) | Gate |"
    )
    rule = "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"
    lines = [
        "# QQQ Aggressive Compound",
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
        "Ending, win rate, profit factor, Sharpe, max drawdown, and the gate are that one account. "
        "The median, the 10th percentile, the three reach rates, the median days, and P(ruin) start a fresh "
        "$2,500 on every later session that still has that many months inside the window. "
        "Median days counts the starts that do reach $10,000 inside 12 months. "
        "Reach is equity of $10,000. Ruin is equity under $500. "
        f"The usual gate is at least 300 trades, profit factor at least 1.10, Sharpe at least 0.40, "
        "and max drawdown no worse than -30%. The formal pass is the holdout row.",
        "",
        "## 1 DTE compared with one contract and the $2,500 tier",
        "",
        header,
        rule,
    ]
    for row in payload["rows"]:
        if row["expiry"] != "1 DTE" or row["iv"] != "prior close, 1 cent":
            continue
        lines.append(_line(row))
    lines.extend(
        [
            "",
            "## All pre-registered fractions",
            "",
            "1 DTE uses the unscaled prior close. 0 DTE uses 1.67 times that close. Both use a 1 cent market.",
            "",
            header,
            rule,
        ]
    )
    for row in payload["rows"]:
        if row["mode"] != "compound":
            continue
        if row["expiry"] == "1 DTE" and abs(float(row["scale"]) - 1.0) > 1e-9:
            continue
        lines.append(_line(row))
    lines.extend(
        [
            "",
            "## 1 DTE at 10%, prior close moved 20%",
            "",
            header,
            rule,
        ]
    )
    for row in payload["rows"]:
        if row["name"] == "10% of equity" and row["expiry"] == "1 DTE":
            lines.append(_line(row))
    lines.extend(["", "## Where the 50-contract cap binds", ""])
    any_cap = False
    for row in payload["rows"]:
        if row["mode"] != "compound":
            continue
        if int(row["cap_fills"] or 0) == 0 and int(row["cap_signals"] or 0) == 0:
            continue
        any_cap = True
        lines.append(
            f"- {row['name']}, {row['expiry']}, {row['iv']}, {row['window']}: "
            f"{_cap_phrase(row)}. Signals whose formula was above {CONTRACT_CAP}: {row['cap_signals']}. "
            f"One-contract rescues: {row['rescues']}. Skips because one contract cost more than 2f: {row['dear_skips']}. "
            f"Skips because the ticket did not fit settled cash: {row['cash_skips']}."
        )
    if not any_cap:
        lines.append("No scored fill was cut back to 50 contracts.")
    lines.extend(
        [
            "",
            "This score does not change an order. The live QQQ Aggressive 1 DTE book stays a fixed lot.",
            "",
        ]
    )
    return "\n".join(lines)


def _published_baselines() -> dict:
    payload = json.loads(STAKE_JSON.read_text())
    found = {}
    for row in payload["rows"]:
        if row["book_id"] != "qqq_aggr" or row["expiry"] != "1 DTE" or int(row["qty"]) != 1:
            continue
        if row["iv"] != "prior close, 1 cent":
            continue
        found[("fixed", row["window"])] = row
    for row in payload["tier"]["rows"]:
        found[("tier", row["window"])] = row
    return found


def _check_baseline(label: str, fresh: dict, old: dict) -> None:
    trade_gap = int(fresh["trades"]) - int(old["trades"])
    money_gap = abs(float(fresh["ending_equity"]) - float(old["ending_equity"]))
    print(f"{label} trade gap {trade_gap} ending gap {money_gap:.4f}", flush=True)
    if trade_gap or money_gap > 0.05:
        raise SystemExit(f"{label} does not match the published score. The compound table was not written.")


def run() -> dict:
    if abs(PREMIUM_UNIT - 100.0) > 1e-9:
        raise SystemExit("The premium unit is not 100. The compound rule was not scored.")
    multiplier = float(calibrate()["multiplier_0dte"])
    print("loading QQQ", flush=True)
    qqq = _load_bars("QQQ")
    iv = prior_iv(_load_series("VIX1D"), _load_series("VIX"))
    qqq15 = to_fifteen(qqq)
    structures = vwap_structures(qqq15, "QQQ")
    sessions = session_dates(qqq15)
    print(f"signals {len(structures)} sessions {len(sessions)}", flush=True)
    priced = {}
    for dte, expiry, iv_label, scale in (
        (1, "1 DTE", "prior close, 1 cent", 1.0),
        (1, "1 DTE", "0.80x prior close, 1 cent", 0.8),
        (1, "1 DTE", "1.20x prior close, 1 cent", 1.2),
        (0, "0 DTE", "x1.67 prior close, 1 cent", multiplier),
    ):
        print(f"pricing {iv_label} dte {dte}", flush=True)
        priced[(expiry, iv_label)] = price_structures(structures, iv, scale, "0.01", dte=dte)
    published = _published_baselines()
    rows = []
    base_key = ("1 DTE", "prior close, 1 cent")
    print("baseline fixed 1 contract", flush=True)
    fixed = score_mode(priced[base_key], sessions, "fixed", 0.0)
    for window in ("train", "holdout"):
        _check_baseline(f"fixed 1-lot {window}", fixed[window], published[("fixed", window)])
    rows.extend(_flatten("1 contract", "fixed", "1 DTE", "prior close, 1 cent", 1.0, "1 contract", fixed))
    print("baseline tier", flush=True)
    tier = score_mode(priced[base_key], sessions, "tier", 0.0)
    for window in ("train", "holdout"):
        _check_baseline(f"tier {window}", tier[window], published[("tier", window)])
    rows.extend(_flatten("1 per $2,500", "tier", "1 DTE", "prior close, 1 cent", 1.0, "tier", tier))
    for expiry, iv_label, scale in (
        ("1 DTE", "prior close, 1 cent", 1.0),
        ("0 DTE", "x1.67 prior close, 1 cent", multiplier),
    ):
        for fraction in FRACTIONS:
            label = _fraction_label(fraction)
            print(f"compound {expiry} {label}", flush=True)
            scored = score_mode(priced[(expiry, iv_label)], sessions, "compound", fraction)
            rows.extend(_flatten(f"{label} of equity", "compound", expiry, iv_label, scale, fraction, scored))
            hold = scored["holdout"]
            print(
                f"  holdout trades {hold['trades']} ending {hold['ending_equity']:.2f} "
                f"sharpe {float(hold['sharpe']):.2f} gate {hold['gate']} cap {hold['cap_fills']}",
                flush=True,
            )
    for iv_label, scale in (("0.80x prior close, 1 cent", 0.8), ("1.20x prior close, 1 cent", 1.2)):
        print(f"compound 1 DTE 10% {iv_label}", flush=True)
        scored = score_mode(priced[("1 DTE", iv_label)], sessions, "compound", PRIMARY_FRACTION)
        rows.extend(
            _flatten("10% of equity", "compound", "1 DTE", iv_label, scale, PRIMARY_FRACTION, scored)
        )
        hold = scored["holdout"]
        print(
            f"  holdout trades {hold['trades']} ending {hold['ending_equity']:.2f} gate {hold['gate']}",
            flush=True,
        )
    payload = {
        "rule": COMPOUND_RULE,
        "stake": STAKE,
        "fractions": list(FRACTIONS),
        "primary_fraction": PRIMARY_FRACTION,
        "contract_cap": CONTRACT_CAP,
        "multiplier": multiplier,
        "rows": rows,
        "summary": "",
    }
    payload["summary"] = summary_paragraphs(_pair(rows))
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
