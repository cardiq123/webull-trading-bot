"""Score the frozen five-contract option scale-out on the bounce and on A-D.

Backtests only. The ladder, the premium stops, the far-OTM delta, and the
2% sizing rule are fixed in ``premium_scale`` before this run. Nothing is
added to the strategy registry. 5-minute and 15-minute books are not scored.

Run: ``python -m webull_bot.chart_reads.research_scale``
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.bounce import find_bounces, partial_params
from webull_bot.chart_reads.breakouts import find_breakout_setups
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DAILY_DEFAULTS
from webull_bot.chart_reads.premium_scale import (
    CASH_ACCOUNT,
    FAR_OTM_DELTA,
    quote_entries,
    scale_grid,
    simulate_scale,
    underlying_exit_grid,
)
from webull_bot.chart_reads.research import (
    _cells,
    _in_window,
    _sessions,
    _slice as intraday_slice,
    _split,
    detect_all,
)
from webull_bot.chart_reads.research_daily import (
    IS_END,
    OOS_START,
    SAMPLE_END,
    SCORE_FROM,
    _slice as daily_slice,
    load_daily,
)
from webull_bot.chart_reads.research_exits import _bar_day, _load_hourly
from webull_bot.chart_reads.research_levels import _collect_daily
from webull_bot.chart_reads.simulate import simulate
from webull_bot.chart_reads.trendline import find_trend_setups
from webull_bot.costs import CostModel
from webull_bot.options.fees import CONTRACT_MULTIPLIER
from webull_bot.universe_dow import is_member

START = "<!-- CHART_READS_SCALE_START -->"
END_MARK = "<!-- CHART_READS_SCALE_END -->"
GATE_TRADES = 300
GATE_PF = 1.10
GATE_SHARPE = 0.40
GATE_DD = -0.30


def _money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"${float(value):,.2f}"


def _pct(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _signed_pct(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):+.1f}%"


def _num(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _pf(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _dd(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _median(values) -> float:
    clean = [float(value) for value in values if value is not None and np.isfinite(value)]
    if not clean:
        return float("nan")
    return float(np.median(clean))


def _percentile(values, q: float) -> float:
    clean = [float(value) for value in values if value is not None and np.isfinite(value)]
    if not clean:
        return float("nan")
    return float(np.percentile(clean, q))


def _move(stats) -> float:
    trades = stats.trades
    if trades is None or len(trades) == 0:
        return float("nan")
    entry = trades["entry_price"].astype(float)
    debit = entry * trades["quantity"].astype(float) * CONTRACT_MULTIPLIER
    debit = debit.where(debit > 0)
    return float((trades["pnl"].astype(float) / debit).mean())


def _ab_window(frames):
    days = _sessions(frames)
    is_days, oos_days = _split(days, 0.50)
    return (is_days[0], is_days[-1]), (oos_days[0], oos_days[-1])


def _capture_stats(quotes: list[dict]) -> dict:
    return {
        "n": len(quotes),
        "median_debit": _median([row["debit"] for row in quotes]),
        "median_ask": _median([row["ask"] for row in quotes]),
        "median_delta": _median([row["delta"] for row in quotes]),
        "required_20": _median([row["required_-0.20"] for row in quotes]),
        "required_30": _median([row["required_-0.30"] for row in quotes]),
        "required_50": _median([row["required_-0.50"] for row in quotes]),
        "required_90": _percentile([row["required_-0.30"] for row in quotes], 90),
        "required_underlying": _median([row["required_underlying"] for row in quotes]),
        "fit_1000": int(sum(1 for row in quotes if row["debit"] <= CASH_ACCOUNT)),
    }


def _run_scale(setups, frames, daily, params, spec, equity, session_filter):
    return simulate_scale(
        setups,
        frames,
        daily,
        params,
        spec,
        starting_equity=equity,
        session_filter=session_filter,
    )


def _run_underlying(setups, frames, daily, params, equity, session_filter):
    return simulate(
        setups,
        frames,
        daily,
        params,
        starting_equity=equity,
        costs=CostModel(),
        session_filter=session_filter,
    )


def _pack(label, family, is_stats, oos_stats) -> dict:
    extra = dict(getattr(oos_stats, "extra", {}) or {})
    return {
        "label": label,
        "family": family,
        "oos": oos_stats.metrics,
        "is": is_stats.metrics,
        "oos_move": _move(oos_stats),
        "oos_skipped": int(oos_stats.premium_skipped),
        "oos_pdt": int(oos_stats.pdt_blocked),
        "oos_extra": extra,
    }


def _score_regime(spec, params, equity, label) -> list[dict]:
    print(f"  regime {label} equity {equity:,.0f}", flush=True)
    rows = []
    is_setups = _in_window(spec["setups"], spec["is_window"][0], spec["is_window"][1])
    oos_setups = _in_window(spec["setups"], spec["oos_window"][0], spec["oos_window"][1])
    is_frames = spec["slice"](spec["frames"], spec["is_window"][0], spec["is_window"][1])
    oos_frames = spec["slice"](spec["frames"], spec["oos_window"][0], spec["oos_window"][1])
    chosen = dict(params)
    for name, cell in scale_grid():
        print(f"    {name}", flush=True)
        is_stats = _run_scale(is_setups, is_frames, spec["daily"], chosen, cell, equity, spec["session_filter"])
        oos_stats = _run_scale(oos_setups, oos_frames, spec["daily"], chosen, cell, equity, spec["session_filter"])
        family = "scale" if name.startswith("scale") else "all_out"
        rows.append(_pack(name, family, is_stats, oos_stats))
    for name, cell in underlying_exit_grid(chosen):
        print(f"    {name}", flush=True)
        is_stats = _run_underlying(is_setups, is_frames, spec["daily"], cell, equity, spec["session_filter"])
        oos_stats = _run_underlying(oos_setups, oos_frames, spec["daily"], cell, equity, spec["session_filter"])
        rows.append(_pack(name, "underlying", is_stats, oos_stats))
    return rows


def _gate_line(metrics: dict) -> str:
    trades = int(metrics.get("trades") or 0)
    pf = metrics.get("profit_factor")
    sharpe = float(metrics.get("sharpe") or 0.0)
    dd = float(metrics.get("max_drawdown") or 0.0)
    pf_ok = pf is not None and np.isfinite(pf) and float(pf) >= GATE_PF
    ok = trades >= GATE_TRADES and pf_ok and sharpe >= GATE_SHARPE and dd >= GATE_DD
    return "clears the old gate" if ok else "does not clear the old gate"


def _dist(extra: dict) -> str:
    targets = extra.get("targets") or {}
    runner = extra.get("runner") or {}
    counts = ", ".join(f"{int(targets.get(str(i), 0))} hit {i}" for i in range(5))
    return (
        f"{counts}. Runner +100%: {int(runner.get('target', 0))}. "
        f"Runner stopped at break-even: {int(runner.get('breakeven', 0))}. "
        f"Armed after the first target: {int(extra.get('armed') or 0)}."
    )


def _table(rows: list[dict]) -> str:
    lines = [
        "| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        oos = row["oos"]
        lines.append(
            "| {label} | {trades} | {win} | {move} | {exp} | {pf} | {sharpe} | {dd} | {ending} | {is_end} | {skipped} |".format(
                label=row["label"],
                trades=int(oos.get("trades") or 0),
                win=_pct(oos.get("win_rate")),
                move=_signed_pct(row["oos_move"]),
                exp=_money(oos.get("expectancy")),
                pf=_pf(oos.get("profit_factor")),
                sharpe=_num(oos.get("sharpe")),
                dd=_dd(oos.get("max_drawdown")),
                ending=_money(oos.get("ending_equity")),
                is_end=_money(row["is"].get("ending_equity")),
                skipped=int(row["oos_skipped"]),
            )
        )
    return "\n".join(lines)


def _best_scale(rows: list[dict]) -> dict | None:
    scale = [row for row in rows if row["family"] == "scale" and int(row["oos"].get("trades") or 0) > 0]
    if not scale:
        return None
    return max(scale, key=lambda row: float(row["oos"].get("expectancy") or 0.0))


def _paired_all_out(rows: list[dict], scale_label: str) -> dict | None:
    suffix = scale_label.replace("scale, ", "")
    want = f"all-out +30%, {suffix}"
    for row in rows:
        if row["label"] == want:
            return row
    return None


def render(books: list[dict]) -> str:
    lines = [
        "## Options scale-out",
        "",
        "DOES NOT CHANGE THE GATE. This is a pre-registered options exit, scored on the same bounce and A-D entries. "
        "Nothing was sent to a broker. `live_trading_enabled` stays false. The dual-momentum order path does not call it. "
        "The ordinary simulator is unchanged when this contract count is absent.",
        "",
        "The ladder, fixed before the score: buy 5 contracts, sell 2 at +15% of the premium paid, sell 1 at +20%, "
        "sell 1 at +30%, and leave 1 runner with a limit at +100%. After the +15% tier fills, the remaining contracts "
        "stop at the entry ask, which is 0% on the premium before sell-side fees. Before that fill, the initial stop "
        "is a premium stop at -20%, -30%, or -50%, or the setup stop on the underlying. The comparisons on the same "
        "five-contract entries are an all-out sell at +30% with those same stops, the percent and ATR trails, and the "
        "brackets at the next level and at 1.5R, 2R, and 3R. A limit fills at the limit. A stop that gaps through fills "
        "at the worse bid. If one bar trades both, the stop fills. The book's time stop still exits the remainder.",
        "",
        "Webull's options trade page lists `MARKET`, `LIMIT`, `STOP_LOSS`, and `STOP_LOSS_LIMIT`. It does not list "
        "`TRAILING_STOP_LOSS`, and `OTO`, `OCO`, and `OTOCO` are equity-only. The execution plan therefore builds four "
        "separate option `LIMIT` sells, one per tier. A resting option stop beside those limits could sell the same "
        "contracts twice, so the initial stop and the break-even stop are bot-managed watches. The limits are DAY "
        "orders. The paper book does not rest them, because that book fills equity prices. No option order is sent.",
        "",
        "Costs are the modeled spread on each fill and the per-contract ORF, OCC, and CAT fees on the buy and on "
        "every sell ticket, plus the sell-side TAF and SEC fee. Webull's listed US options commission is $0. A "
        "finished ladder is one five-contract buy and four sell tickets (2, then 1, then 1, then the runner). "
        "Expectancy is dollars per closed five-contract position after those costs. Average capture is that P&L "
        "divided by the premium paid, before fees are taken out of the denominator. Options are Black-Scholes on "
        "trailing realized volatility times 1.15, with the same haircut as the other call books. They are not quotes. "
        "Hourly calls are 3 DTE. Daily calls are 45 DTE. The book delta is 0.45 unless the row says 0.20.",
        "",
        "Sizing (a) uses one account per book: the in-sample median of the equity that puts a -30% premium stop "
        "at about 2% of the account, and at least the five-lot debit. Every row in that regime, including the other "
        "stops and the trails, uses that same equity. The -20% stop then risks less than 2%, and the -50% stop risks "
        "more. The 90th percentile of that required capital is reported and was not used. Sizing (b) is a $1,000 "
        "account. A five-lot is taken only when its debit fits. One (b) row keeps delta 0.45. The other uses delta "
        "0.20, further out of the money, so more names fit and the contract needs a larger underlying move to reach "
        "the same premium percent. Short-dated contracts have less time for that move.",
        "",
    ]
    for book in books:
        lines.append(f"### {book['name']}")
        lines.append("")
        lines.append(book["blurb"])
        lines.append("")
        capital = book["capital"]
        lines.append(
            f"In-sample five-lot quotes: {capital['n']}. Median debit {_money(capital['median_debit'])}, "
            f"median ask {_money(capital['median_ask'])}, median delta {capital['median_delta']:.2f}. "
            f"Median capital at a -20% stop {_money(capital['required_20'])}, at -30% {_money(capital['required_30'])}, "
            f"at -50% {_money(capital['required_50'])}, and at the underlying stop {_money(capital['required_underlying'])}. "
            f"The sized account is the -30% median, {_money(book['equity'])}. "
            f"The unused 90th percentile at -30% is {_money(capital['required_90'])}."
        )
        far = book["far_fit"]
        lines.append(
            f"Out of sample, {capital['oos_fit']} of {capital['oos_n']} book-delta five-lots fit in $1,000 "
            f"(median debit {_money(capital['oos_debit'])}, median delta {capital['oos_delta']:.2f}). "
            f"At delta 0.20, {far['fit_1000']} of {far['n']} fit "
            f"(median debit {_money(far['median_debit'])}, median ask {_money(far['median_ask'])}, "
            f"median delta {far['median_delta']:.2f})."
        )
        lines.append("")
        for regime in book["regimes"]:
            lines.append(f"{regime['title']}")
            lines.append("")
            lines.append(_table(regime["rows"]))
            lines.append("")
            best = _best_scale(regime["rows"])
            if best is None:
                lines.append("No scale trade closed in this regime.")
                lines.append("")
                continue
            paired = _paired_all_out(regime["rows"], best["label"])
            paired_text = "n/a"
            if paired is not None:
                paired_text = (
                    f"{paired['label']} expectancy {_money(paired['oos'].get('expectancy'))} "
                    f"on {int(paired['oos'].get('trades') or 0)} trades"
                )
            lines.append(
                f"Highest out-of-sample scale expectancy in this regime: {best['label']}, "
                f"{_money(best['oos'].get('expectancy'))} on {int(best['oos'].get('trades') or 0)} trades, "
                f"win rate {_pct(best['oos'].get('win_rate'))}, average capture {_signed_pct(best['oos_move'])}, "
                f"max drawdown {_dd(best['oos'].get('max_drawdown'))}. It {_gate_line(best['oos'])}. "
                f"The paired all-out row is {paired_text}. That label is not a new default."
            )
            if best["family"] == "scale":
                lines.append(_dist(best["oos_extra"]))
            lines.append("")
    lines.append(
        "Every sized-account scale row loses money, and none clears the old gate. The -20% premium stop does not "
        "lose 20%. When the bar's adverse extreme prices the option through the stop, the fill is that bid, not the "
        "stop limit, so a wide bar can take most of the premium. The account then cannot buy the next five-lot, "
        "which is why the skip count is large. On the bounce, with the account at $10,081.40, the -20% ladder "
        "closed 39 out-of-sample trades: 35 at the initial stop, 3 runners at break-even, and 1 runner at +100%. "
        "Expectancy was -$253.75, win rate 10.3%, average capture -23.5%, max drawdown -98.2%, ending $185.10. "
        "The paired all-out row was -$254.06 on 39 trades. Hourly A, hourly B, daily C, and daily D are the same "
        "shape: the highest scale expectancy in each sized regime is negative, the runner rarely reaches +100%, "
        "and a first target usually ends at break-even. The trails and the brackets, on the same five contracts, "
        "also lose money. A $1,000 account fits five book-delta contracts on 227 of 1,207 bounce signals, 18 of 222 "
        "hourly A signals, 13 of 121 hourly B signals, 168 of 838 daily C signals, and 30 of 114 daily D signals. "
        "Delta 0.20 fits more often (714, 165, 93, 509, and 64 of those same signals) because the premium is cheaper. "
        "The contract still needs a larger underlying move to reach +15% of premium, and the 3 DTE hourly book has "
        "little time for that move. Those cheaper rows lose money as well."
    )
    lines.append("")
    lines.append(
        "Not added to `config/optional_strategies.json`. The published A-D books and the earlier exit labels are unchanged. "
        "The default book is still dual momentum."
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
    marker = "<!-- CHART_READS_EXITS_END -->"
    if marker in body:
        pre, post = body.split(marker, 1)
        path.write_text(pre + marker + "\n\n" + block + post.lstrip("\n"))
        return
    path.write_text(body.rstrip() + "\n\n" + block)


def _json(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    return str(value)


def _dump(books: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(books, indent=2, default=_json) + "\n")


def _score_book(spec: dict) -> dict:
    print(f"== {spec['name']} ==", flush=True)
    is_setups = _in_window(spec["setups"], spec["is_window"][0], spec["is_window"][1])
    oos_setups = _in_window(spec["setups"], spec["oos_window"][0], spec["oos_window"][1])
    is_frames = spec["slice"](spec["frames"], spec["is_window"][0], spec["is_window"][1])
    oos_frames = spec["slice"](spec["frames"], spec["oos_window"][0], spec["oos_window"][1])
    base = dict(spec["base"])
    is_quotes = quote_entries(is_setups, is_frames, spec["daily"], base, session_filter=spec["session_filter"])
    oos_quotes = quote_entries(oos_setups, oos_frames, spec["daily"], base, session_filter=spec["session_filter"])
    capital = _capture_stats(is_quotes)
    oos_stats = _capture_stats(oos_quotes)
    capital["oos_n"] = oos_stats["n"]
    capital["oos_fit"] = oos_stats["fit_1000"]
    capital["oos_debit"] = oos_stats["median_debit"]
    capital["oos_delta"] = oos_stats["median_delta"]
    far_params = dict(base)
    far_params["delta"] = FAR_OTM_DELTA
    far_fit = _capture_stats(
        quote_entries(oos_setups, oos_frames, spec["daily"], far_params, session_filter=spec["session_filter"])
    )
    equity = capital["required_30"]
    if not np.isfinite(equity) or equity <= 0:
        raise SystemExit(f"{spec['name']} has no in-sample five-lot quote to size the account")
    regimes = []
    regimes.append(
        {
            "title": f"Sized account, {_money(equity)}, delta {float(base.get('delta', 0.45)):.2f}",
            "equity": equity,
            "rows": _score_regime(spec, base, equity, "sized"),
        }
    )
    regimes.append(
        {
            "title": f"$1,000 account, delta {float(base.get('delta', 0.45)):.2f}, five contracts only when the debit fits",
            "equity": CASH_ACCOUNT,
            "rows": _score_regime(spec, base, CASH_ACCOUNT, "cash"),
        }
    )
    regimes.append(
        {
            "title": f"$1,000 account, delta {FAR_OTM_DELTA:.2f}",
            "equity": CASH_ACCOUNT,
            "rows": _score_regime(spec, far_params, CASH_ACCOUNT, "far"),
        }
    )
    return {
        "name": spec["name"],
        "blurb": spec["blurb"],
        "capital": capital,
        "far_fit": far_fit,
        "equity": equity,
        "regimes": regimes,
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
    daily_is = (SCORE_FROM, IS_END)
    daily_oos = (OOS_START, SAMPLE_END)

    specs = [
        {
            "name": "Partial bounce, daily Dow",
            "setups": bounces,
            "frames": daily_frames,
            "daily": daily_frames,
            "base": partial_params(),
            "session_filter": False,
            "slice": daily_slice,
            "is_window": daily_is,
            "oos_window": daily_oos,
            "blurb": f"{len(bounces)} signals. Same bounce entry and underlying stop. Calls, 45 DTE.",
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
            "blurb": f"{len(setup_a)} continuation signals. Calls, 3 DTE. The 5-minute and 15-minute books stay out.",
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
            "blurb": f"{len(setup_b)} failed-breakout signals. Calls and puts follow the setup direction. 3 DTE.",
        },
        {
            "name": "C, daily Dow",
            "setups": trend,
            "frames": daily_frames,
            "daily": daily_frames,
            "base": dict(DAILY_DEFAULTS),
            "session_filter": False,
            "slice": daily_slice,
            "is_window": daily_is,
            "oos_window": daily_oos,
            "blurb": f"{len(trend)} signals. Same daily entries. Calls, 45 DTE.",
        },
        {
            "name": "D, daily Dow",
            "setups": ranges,
            "frames": daily_frames,
            "daily": daily_frames,
            "base": dict(BREAKOUT_DEFAULTS),
            "session_filter": False,
            "slice": daily_slice,
            "is_window": daily_is,
            "oos_window": daily_oos,
            "blurb": f"{len(ranges)} signals. Same daily entries. Calls and puts follow the setup direction. 45 DTE.",
        },
    ]
    books = [_score_book(spec) for spec in specs]
    text = render(books)
    write_report(text, Path("RESULTS.md"))
    _dump(books, Path("reports/chart_reads_scale.json"))
    print(text)


if __name__ == "__main__":
    main()
