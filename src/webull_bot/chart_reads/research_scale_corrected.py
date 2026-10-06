"""Re-score the corrected five-contract ladder.

Frozen before this run, in ``premium_scale.corrected_cells``:

* Sell 2 at +15%, 1 at +20%, 1 at +30%. The runner limits at +100%.
* Contracts 1-4 keep the initial premium stop for the whole trade.
* The runner keeps that stop until the +15% tier fills, then stops at the
  entry ask. Break-even does not move contracts 1-4.
* The gate reads premium stop -20% and 21 DTE. 21 is the midpoint of the
  stated 5-35 DTE band. -30%, 5 DTE, and 35 DTE are sensitivities.
* Longs are calls. Shorts are puts. Delta 0.45.
* The sized account is the in-sample median equity that puts the -20% stop
  at about 2% of the account. The $1,000 book takes five contracts only
  when the debit fits. Random entries use seed 17 on the holdout.

Nothing is sent to a broker. This does not rewrite the earlier scale-out
section, which scored the old rule that moved every remaining contract to
break-even.

Run: ``python -m webull_bot.chart_reads.research_scale_corrected``
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.bounce import find_bounces, partial_params
from webull_bot.chart_reads.breakouts import find_breakout_setups
from webull_bot.chart_reads.chop_v2 import find_chop_breakouts
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DAILY_DEFAULTS
from webull_bot.chart_reads.premium_scale import (
    CASH_ACCOUNT,
    CORRECTED_DELTA,
    CORRECTED_DTE,
    CORRECTED_STOP,
    quote_entries,
    corrected_cells,
    simulate_scale,
)
from webull_bot.chart_reads.research import SYMBOLS, _in_window, _sessions, _slice as intraday_slice, _split, random_setups
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
from webull_bot.chart_reads.research_scale import _capture_stats, _dist, _gate_line, _move, _money, _num, _pct, _pf, _dd
from webull_bot.chart_reads.trendline import find_trend_setups
from webull_bot.mtf_vwap.detect import rth
from webull_bot.universe_dow import is_member

START = "<!-- CHART_READS_SCALE_CORRECTED_START -->"
END_MARK = "<!-- CHART_READS_SCALE_CORRECTED_END -->"
GATE_TRADES = 300


def _with_dte(params: dict, spec: dict) -> dict:
    chosen = dict(params)
    chosen["dte"] = int(spec["dte"])
    chosen["delta"] = CORRECTED_DELTA
    chosen["expression"] = "single"
    return chosen


def _run(setups, frames, daily, params, spec, equity, session_filter):
    cell = {key: spec[key] for key in ("mode", "stop_kind", "premium_stop")}
    return simulate_scale(
        setups,
        frames,
        daily,
        _with_dte(params, spec),
        cell,
        starting_equity=equity,
        session_filter=session_filter,
    )


def _metrics_line(stats) -> dict:
    return {
        "metrics": stats.metrics,
        "move": _move(stats),
        "skipped": int(stats.premium_skipped),
        "extra": dict(getattr(stats, "extra", {}) or {}),
    }


def _one(label, role, stats) -> dict:
    packed = _metrics_line(stats)
    packed["label"] = label
    packed["role"] = role
    return packed


def _table(rows: list[dict]) -> str:
    lines = [
        "| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        metrics = row["metrics"]
        lines.append(
            "| {label} | {role} | {trades} | {win} | {move} | {exp} | {pf} | {sharpe} | {dd} | {ending} | {skipped} |".format(
                label=row["label"],
                role=row["role"],
                trades=int(metrics.get("trades") or 0),
                win=_pct(metrics.get("win_rate")),
                move=_signed(row["move"]),
                exp=_money(metrics.get("expectancy")),
                pf=_pf(metrics.get("profit_factor")),
                sharpe=_num(metrics.get("sharpe")),
                dd=_dd(metrics.get("max_drawdown")),
                ending=_money(metrics.get("ending_equity")),
                skipped=int(row["skipped"]),
            )
        )
    return "\n".join(lines)


def _signed(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):+.1f}%"


def _score_book(spec: dict) -> dict:
    print(f"== {spec['name']} ==", flush=True)
    is_setups = _in_window(spec["setups"], spec["is_window"][0], spec["is_window"][1])
    oos_setups = _in_window(spec["setups"], spec["oos_window"][0], spec["oos_window"][1])
    is_frames = spec["slice"](spec["frames"], spec["is_window"][0], spec["is_window"][1])
    oos_frames = spec["slice"](spec["frames"], spec["oos_window"][0], spec["oos_window"][1])
    base = dict(spec["base"])
    base["dte"] = CORRECTED_DTE
    base["delta"] = CORRECTED_DELTA
    is_quotes = quote_entries(is_setups, is_frames, spec["daily"], base, session_filter=spec["session_filter"])
    capital = _capture_stats(is_quotes)
    equity = capital["required_20"]
    if not np.isfinite(equity) or equity <= 0:
        equity = CASH_ACCOUNT
    print(f"  sized equity {equity:,.2f} from {capital['n']} in-sample quotes", flush=True)
    sized = []
    cash = []
    gate_oos = None
    for label, cell, role in corrected_cells():
        print(f"  {label}", flush=True)
        if role == "gate":
            is_stats = _run(is_setups, is_frames, spec["daily"], base, cell, equity, spec["session_filter"])
            sized.append(_one(label + ", in sample", "in sample", is_stats))
        oos_stats = _run(oos_setups, oos_frames, spec["daily"], base, cell, equity, spec["session_filter"])
        packed = _one(label, role, oos_stats)
        sized.append(packed)
        if role == "gate":
            gate_oos = packed
            cash_stats = _run(oos_setups, oos_frames, spec["daily"], base, cell, CASH_ACCOUNT, spec["session_filter"])
            cash.append(_one(label, "gate, $1,000", cash_stats))
        elif cell["premium_stop"] == -0.30 and cell["dte"] == CORRECTED_DTE and cell["mode"] == "scale":
            cash_stats = _run(oos_setups, oos_frames, spec["daily"], base, cell, CASH_ACCOUNT, spec["session_filter"])
            cash.append(_one(label, "sensitivity, $1,000", cash_stats))
    print("  random", flush=True)
    shuffled = random_setups(oos_setups, oos_frames, seed=17)
    gate_cell = corrected_cells()[0][1]
    random_stats = _run(shuffled, oos_frames, spec["daily"], base, gate_cell, equity, spec["session_filter"])
    random_row = _one("random entries, same -20% ladder, 21 DTE", "random", random_stats)
    return {
        "name": spec["name"],
        "blurb": spec["blurb"],
        "window": f"{spec['oos_window'][0].isoformat()} through {spec['oos_window'][1].isoformat()}",
        "signals": len(spec["setups"]),
        "oos_signals": len(oos_setups),
        "capital": capital,
        "equity": equity,
        "sized": sized,
        "cash": cash,
        "random": random_row,
        "gate": gate_oos,
    }


def _beats(candidate: dict, baseline: dict) -> bool:
    left = candidate["metrics"]
    right = baseline["metrics"]
    if int(left.get("trades") or 0) < 20 or int(right.get("trades") or 0) < 1:
        return False
    if float(left.get("sharpe") or 0.0) <= float(right.get("sharpe") or 0.0):
        return False
    return float(left.get("max_drawdown") or 0.0) >= float(right.get("max_drawdown") or 0.0)


def render(books: list[dict]) -> str:
    lines = [
        "## Corrected options scale-out",
        "",
        "DOES NOT CHANGE THE GATE. The earlier scale-out section scored a different rule: after the +15% tier, "
        "every remaining contract moved to break-even. This section is the correction, frozen before the re-score. "
        "Contracts 1-4 (2 at +15%, 1 at +20%, 1 at +30%) keep the initial premium stop for the whole trade. "
        "The runner keeps that stop until the +15% tier fills, then its stop moves to the entry ask, and its limit "
        "stays at +100%. A stop sells only the contracts that stop applies to. Nothing was sent to a broker. "
        "Live trading stays off.",
        "",
        f"The cell the gate reads is a -20% premium stop and {CORRECTED_DTE} DTE, the midpoint of the stated "
        f"5-35 DTE band. -30%, 5 DTE, and 35 DTE are sensitivities and do not replace it. Longs are calls and shorts "
        f"are puts, delta {CORRECTED_DELTA:.2f}. The sized account is the in-sample median equity that puts the -20% "
        "stop at about 2% of the account, and at least the five-lot debit. The $1,000 book takes five contracts only "
        "when that debit fits. Random entries keep the symbols, directions, and count, shuffle the timestamps with "
        "seed 17, and use the same ladder. The holdout is the same window each book used before.",
        "",
    ]
    for book in books:
        lines.append(f"### {book['name']}")
        lines.append("")
        lines.append(book["blurb"])
        capital = book["capital"]
        lines.append(
            f"Holdout {book['window']}. Signals {book['signals']}, of which {book['oos_signals']} are in the holdout. "
            f"In-sample five-lot quotes: {capital['n']}. Median debit {_money(capital['median_debit'])}. "
            f"Quotes that fit five contracts in $1,000: {int(capital.get('fit_1000') or 0)} of {capital['n']}. "
            f"Sized account {_money(book['equity'])}, the in-sample median that puts the -20% stop near 2% of equity. "
            f"The -30% row uses that same account."
        )
        lines.append("")
        lines.append(_table(book["sized"]))
        lines.append("")
        lines.append(_table(book["cash"]))
        lines.append("")
        lines.append(_table([book["random"]]))
        gate = book["gate"]
        if gate is None:
            lines.append("No gated row.")
        else:
            metrics = gate["metrics"]
            lines.append(
                f"Gated holdout row: {int(metrics.get('trades') or 0)} trades, "
                f"expectancy {_money(metrics.get('expectancy'))}, profit factor {_pf(metrics.get('profit_factor'))}, "
                f"Sharpe {_num(metrics.get('sharpe'))}, max drawdown {_dd(metrics.get('max_drawdown'))}, "
                f"ending {_money(metrics.get('ending_equity'))}. It {_gate_line(metrics)}. "
                f"It {'beats' if _beats(gate, book['random']) else 'does not beat'} the random entries on Sharpe "
                "with a drawdown that is not worse."
            )
            lines.append(_dist(gate["extra"]))
        lines.append("")
    gated = [book["gate"] for book in books if book.get("gate")]
    if gated:
        all_lose = all(float(row["metrics"].get("expectancy") or 0.0) < 0 for row in gated)
        none_clear = all(_gate_line(row["metrics"]) != "clears the old gate" for row in gated)
        if all_lose and none_clear:
            lines.append(
                "Every gated holdout row loses money, and none clears the old gate. "
                "Where a row beats the random entries, both Sharpes are negative. "
                "That comparison only requires a higher Sharpe, a drawdown that is not worse, and at least 20 trades."
            )
            lines.append("")
    lines.append(
        "Not added to `config/optional_strategies.json`. The published A-D books, the earlier scale-out numbers, "
        "and the share forward test are unchanged. The default book is still dual momentum."
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
    marker = "<!-- CHART_READS_SCALE_END -->"
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
                "Calls and puts follow the setup. 21 DTE. This is the forward-test candidate."
            ),
        },
        {
            "name": "Partial bounce, daily Dow",
            "setups": bounces,
            "frames": daily_frames,
            "daily": daily_frames,
            "base": partial_params(),
            "session_filter": False,
            "slice": daily_slice,
            "is_window": (SCORE_FROM, IS_END),
            "oos_window": (OOS_START, SAMPLE_END),
            "blurb": f"{len(bounces)} signals. Same bounce entry. Calls, 21 DTE. Holdout {OOS_START.isoformat()} through {SAMPLE_END.isoformat()}.",
        },
        {
            "name": "A, 60-minute",
            "setups": setup_a,
            "frames": hourly,
            "daily": daily_short,
            "base": ab_params,
            "session_filter": True,
            "slice": intraday_slice,
            "is_window": is_ab,
            "oos_window": oos_ab,
            "blurb": f"{len(setup_a)} continuation signals. Calls, 21 DTE.",
        },
        {
            "name": "B, 60-minute",
            "setups": setup_b,
            "frames": hourly,
            "daily": daily_short,
            "base": ab_params,
            "session_filter": True,
            "slice": intraday_slice,
            "is_window": is_ab,
            "oos_window": oos_ab,
            "blurb": f"{len(setup_b)} failed-breakout signals. Calls and puts follow the setup. 21 DTE.",
        },
        {
            "name": "C, daily Dow",
            "setups": trend,
            "frames": daily_frames,
            "daily": daily_frames,
            "base": dict(DAILY_DEFAULTS),
            "session_filter": False,
            "slice": daily_slice,
            "is_window": (SCORE_FROM, IS_END),
            "oos_window": (OOS_START, SAMPLE_END),
            "blurb": f"{len(trend)} signals. Same daily entries. Calls, 21 DTE.",
        },
        {
            "name": "D, daily Dow",
            "setups": ranges,
            "frames": daily_frames,
            "daily": daily_frames,
            "base": dict(BREAKOUT_DEFAULTS),
            "session_filter": False,
            "slice": daily_slice,
            "is_window": (SCORE_FROM, IS_END),
            "oos_window": (OOS_START, SAMPLE_END),
            "blurb": f"{len(ranges)} signals. Same daily entries. Calls and puts follow the setup. 21 DTE.",
        },
    ]
    books = [_score_book(spec) for spec in specs]
    text = render(books)
    write_report(text, Path("RESULTS.md"))
    path = Path("reports/chart_reads_scale_corrected.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(books, indent=2, default=_json) + "\n")
    print(text)


def _json(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    return str(value)


if __name__ == "__main__":
    main()
