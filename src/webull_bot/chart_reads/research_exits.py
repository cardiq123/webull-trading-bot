"""Compare frozen exit styles on the bounce and on setups A-D.

Backtests only. The grid is ``exit_grid``. A winner is a label on that
book's out-of-sample stock row. It does not change the gate. 5-minute and
15-minute books are inside the short Yahoo cap and are not scored here.

Run: ``python -m webull_bot.chart_reads.research_exits``
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.bounce import find_bounces, partial_params
from webull_bot.chart_reads.breakouts import find_breakout_setups
from webull_bot.chart_reads.exits import beats_baseline, exit_grid, select_winner
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DAILY_DEFAULTS
from webull_bot.chart_reads.research import (
    END,
    SYMBOLS,
    _cells,
    _sessions,
    _split,
    _window_book as intraday_window,
    detect_all,
)
from webull_bot.chart_reads.research_daily import (
    IS_END,
    OOS_START,
    SAMPLE_END,
    SCORE_FROM,
    _window_book as daily_window,
    load_daily,
)
from webull_bot.chart_reads.research_levels import _collect_daily
from webull_bot.chart_reads.trendline import find_trend_setups
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.options.fees import CONTRACT_MULTIPLIER
from webull_bot.universe_dow import is_member

START = "<!-- CHART_READS_EXITS_START -->"
END_MARK = "<!-- CHART_READS_EXITS_END -->"
PUBLISHED = {
    "A, 60-minute": (886.97, 131),
    "B, 60-minute": (921.86, 85),
    "C, daily Dow": (746.56, 207),
    "D, daily Dow": (919.45, 73),
}
BOUNCE_LEVEL = (1502.90, 286)


def _bar_day(ts) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York")
    return stamp.date()


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


def _move(stats, expression: str) -> float:
    trades = stats.trades
    if trades is None or len(trades) == 0:
        return float("nan")
    entry = trades["entry_price"].astype(float)
    if expression == "stock":
        return float(((trades["exit_price"].astype(float) - entry) / entry).mean())
    debit = entry * trades["quantity"].astype(float) * CONTRACT_MULTIPLIER
    debit = debit.where(debit > 0)
    return float((trades["pnl"].astype(float) / debit).mean())


def _reasons(stats) -> dict[str, int]:
    trades = stats.trades
    if trades is None or len(trades) == 0 or "reason" not in trades.columns:
        return {}
    return {str(key): int(value) for key, value in trades["reason"].value_counts().items()}


def _check(name: str, metrics: dict, expected: tuple[float, int] | None) -> str:
    if expected is None:
        return ""
    ending = float(metrics.get("ending_equity") or 0.0)
    trades = int(metrics.get("trades") or 0)
    want_end, want_trades = expected
    if abs(ending - want_end) <= 0.02 and trades == want_trades:
        return (
            f"The published stock out-of-sample book still matches {_money(want_end)} on {want_trades} trades."
        )
    raise SystemExit(
        f"{name} published stock OOS is {_money(ending)} on {trades} trades. "
        f"The gated writeup is {_money(want_end)} on {want_trades}. Stopping so that row is not rewritten."
    )


def _score_cell(setups, frames, daily, params, expression, window_fn, is_window, oos_window) -> dict:
    is_stats = window_fn(setups, frames, daily, params, expression, is_window[0], is_window[1])
    oos_stats = window_fn(setups, frames, daily, params, expression, oos_window[0], oos_window[1])
    return {
        "is": is_stats.metrics,
        "oos": oos_stats.metrics,
        "oos_move": _move(oos_stats, expression),
        "oos_reasons": _reasons(oos_stats),
        "premium_skipped": int(oos_stats.premium_skipped),
    }


def _table(rows: list[dict], *, stock: bool) -> str:
    lines = [
        "| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Beats level |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        oos = row["oos"]
        flag = "—"
        if stock:
            if row["role"] == "baseline":
                flag = "baseline"
            elif row["role"] == "published":
                flag = "—"
            else:
                flag = "yes" if row["beats"] else "no"
        lines.append(
            "| {label} | {trades} | {win} | {move} | {exp} | {pf} | {sharpe} | {dd} | {ending} | {is_end} | {flag} |".format(
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
                flag=flag,
            )
        )
    return "\n".join(lines)


def _score_book(spec: dict) -> dict:
    print(f"== {spec['name']} ==", flush=True)
    stock_rows = []
    option_rows = []
    grid = exit_grid(spec["base"])
    published = None
    if spec.get("published") is not None:
        print("  published exit", flush=True)
        published = _score_cell(
            spec["setups"], spec["frames"], spec["daily"], spec["published"], "stock",
            spec["window"], spec["is_window"], spec["oos_window"],
        )
        published["label"] = "published exit"
        published["role"] = "published"
        published["beats"] = False
        note = _check(spec["name"], published["oos"], PUBLISHED.get(spec["name"]))
    else:
        note = ""
    for label, params in grid:
        print(f"  {label} stock", flush=True)
        stock = _score_cell(
            spec["setups"], spec["frames"], spec["daily"], params, "stock",
            spec["window"], spec["is_window"], spec["oos_window"],
        )
        stock["label"] = label
        stock["role"] = "baseline" if label == "level target" else "candidate"
        if label == "level target" and spec.get("level_check") is not None:
            note = _check(spec["name"], stock["oos"], spec.get("level_check"))
        print(f"  {label} calls", flush=True)
        option = _score_cell(
            spec["setups"], spec["frames"], spec["daily"], params, "single",
            spec["window"], spec["is_window"], spec["oos_window"],
        )
        option["label"] = label
        option["role"] = "option"
        stock_rows.append(stock)
        option_rows.append(option)
    baseline = stock_rows[0]["oos"]
    for row in stock_rows[1:]:
        row["beats"] = beats_baseline(baseline, row["oos"])
    stock_rows[0]["beats"] = False
    winner = select_winner([(row["label"], row["oos"]) for row in stock_rows])
    return {
        "name": spec["name"],
        "blurb": spec["blurb"],
        "note": note,
        "winner": winner,
        "stock": stock_rows,
        "options": option_rows,
        "published": published,
        "signals": len(spec["setups"]),
    }


def render(books: list[dict]) -> str:
    lines = [
        "## Exit styles",
        "",
        "DOES NOT CHANGE THE GATE. The same entries and the same stops are scored with a frozen exit grid. "
        "Nothing was sent to a broker. `live_trading_enabled` stays false. The dual-momentum order path is unchanged.",
        "",
        "The grid, fixed before this score: a percent trail at 5%, 10%, and 15%; an ATR trail at 1.5, 2, and 3 times "
        "the signal-bar ATR, as a fixed dollar step; a bracket at the next level and at 1.5R, 2R, and 3R, with the "
        "setup stop and no EMA trail; and one hybrid that sells half at the first level (1R if that level is missing) "
        "and trails the rest at 2 times the signal-bar ATR. The level bracket is the baseline. A pure trail has no "
        "separate hard stop and no take-profit. The book's time stop still exits, because a native order has none. "
        "A row beats the baseline on the out-of-sample stock book only when expectancy is strictly higher, profit "
        "factor is not lower, max drawdown is no more than five points worse, and at least 20 trades closed. "
        "The winner is the passing row with the highest expectancy. An equal expectancy keeps the earlier cell. "
        "Options are reported and do not pick the winner. Meeting the label does not clear the gate.",
        "",
        "Webull's stock trade page accepts `TRAILING_STOP_LOSS` with `trailing_type` `AMOUNT` or `PERCENTAGE` and "
        "`trailing_stop_step` (`0.01` is 1%). That order is DAY only, so a multi-day trail in this backtest is the "
        "economic path of renewing it, not a good-till-cancelled order. The equity bracket on that page is "
        "`MASTER` plus `STOP_PROFIT` plus `STOP_LOSS` with one `client_combo_order_id`. `OTOCO` is a different "
        "pattern, a master that triggers two linked limits, and it is not the bracket used here. The options trade "
        "page lists `MARKET`, `LIMIT`, `STOP_LOSS`, and `STOP_LOSS_LIMIT`. It says `TRAILING_STOP_LOSS` is not "
        "supported, and `OTO`, `OCO`, and `OTOCO` are equity-only. A single-leg option stop is a premium. These "
        "exits are prices on the underlying, so every option row is a bot-managed watch of the stock. No option "
        "order is built or sent. The paper path can rest the equity trail, the equity bracket, or the hybrid's "
        "half-size limit and half-size DAY trail. It refuses any broker other than the paper broker.",
        "",
        "Hourly setup A and hourly setup B are the intraday books. The 5-minute and 15-minute books stay out of "
        "this grid because that Yahoo sample is too short to separate an exit. Daily setup C, daily setup D, and "
        "the partial-bounce book use the Dow point-in-time window, 2010-01-01 through 2018-12-31 in sample and "
        "2019-01-01 through 2026-10-06 out of sample. Calls are 3 DTE on the hourly books and 45 DTE on the daily "
        "books, delta 0.45, inside the $1,000 and 20% risk rules. A contract that does not fit is skipped. "
        "Average capture on a stock row is the mean underlying percent from the fill to the exit. On a call row "
        "it is the mean premium return, including the haircut and the option fees. Expectancy is dollars per "
        "closed trade after costs. A hybrid entry can close as two trades, the partial and the remainder. "
        "One option contract cannot be split, so that position exits in full at the target.",
        "",
    ]
    for book in books:
        lines.append(f"### {book['name']}")
        lines.append("")
        lines.append(book["blurb"])
        if book["note"]:
            lines.append("")
            lines.append(book["note"])
        lines.append("")
        lines.append(
            f"Out-of-sample stock winner: **{book['winner']}**. "
            "That label is not the default book."
        )
        lines.append("")
        lines.append("Stock")
        lines.append("")
        stock = list(book["stock"])
        if book["published"] is not None:
            stock = [book["published"], *stock]
        lines.append(_table(stock, stock=True))
        lines.append("")
        lines.append("Options, bot-managed on the underlying")
        lines.append("")
        lines.append(_table(book["options"], stock=False))
        skipped = book["options"][0]["premium_skipped"]
        lines.append("")
        lines.append(
            f"The level-target call row skipped {skipped} out-of-sample entries that did not fit the risk budget "
            "or had no volatility estimate."
        )
        reasons = next(row["oos_reasons"] for row in book["stock"] if row["label"] == book["winner"])
        if not reasons:
            reasons = book["stock"][0]["oos_reasons"]
        if reasons:
            rendered = ", ".join(f"{count} {name}" for name, count in sorted(reasons.items()))
            lines.append(f"Out-of-sample stock exits for {book['winner']}: {rendered}.")
        lines.append("")
    lines.append(
        "The bounce label is the 15% trail: out-of-sample expectancy $13.63, profit factor 1.43, "
        "Sharpe 0.60, max drawdown -32.3%, 118 trades, ending $2,608.44. Of those exits, 109 were the "
        "15-session time stop and 8 were the trail. The stop is wide enough that it rarely ratchets "
        "inside the hold, so that result is mostly a wide stop plus the time stop. It does not clear "
        "300 trades or a drawdown no worse than -30%. Hourly B's 15% trail is the same pattern, 34 of "
        "36 exits at the time stop, expectancy $2.64. Hourly A and daily C keep the level target because "
        "nothing beat it. Daily C's level target, with the 20 EMA trail off, ended at $2,522.01 on 163 "
        "trades (profit factor 1.30, Sharpe 0.71, drawdown -34.2%). That is not the published C book, "
        "which still matches $746.56 on 207 trades, and it does not clear the gate. Daily D's label is "
        "the 1.5R bracket, expectancy -$1.46 on 73 trades. The option rows do not pick the label. The "
        "only call book that finished ahead of its start was the bounce's 10% trail, $1,584.44 on 96 "
        "trades, with a -70.5% drawdown. Where the 1.5R, 2R, and 3R call rows match, those contracts "
        "were closed by the stop or the time stop before the underlying reached 1.5R."
    )
    lines.append("")
    lines.append(
        "Not added to `config/optional_strategies.json`. The published A-D books are unchanged. "
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
    marker = "<!-- CHART_READS_BOUNCE_END -->"
    if marker in body:
        pre, post = body.split(marker, 1)
        path.write_text(pre + marker + "\n\n" + block + post.lstrip("\n"))
        return
    path.write_text(body.rstrip() + "\n\n" + block)


def _dump(books: list[dict], path: Path) -> None:
    payload = []
    for book in books:
        payload.append(
            {
                "name": book["name"],
                "winner": book["winner"],
                "signals": book["signals"],
                "note": book["note"],
                "stock": [
                    {
                        "label": row["label"],
                        "beats": row["beats"],
                        "oos": row["oos"],
                        "is": row["is"],
                        "oos_move": row["oos_move"],
                        "oos_reasons": row["oos_reasons"],
                    }
                    for row in book["stock"]
                ],
                "options": [
                    {
                        "label": row["label"],
                        "oos": row["oos"],
                        "is": row["is"],
                        "oos_move": row["oos_move"],
                        "premium_skipped": row["premium_skipped"],
                    }
                    for row in book["options"]
                ],
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json) + "\n")


def _json(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    return str(value)


def _ab_window(frames):
    days = _sessions(frames)
    is_days, oos_days = _split(days, 0.50)
    return (is_days[0], is_days[-1]), (oos_days[0], oos_days[-1])


def _load_hourly():
    provider = YFinanceProvider("data/cache")
    end = pd.Timestamp(END)
    print("loading hourly cache", flush=True)
    daily = provider.history(SYMBOLS, "2023-01-01", END, interval="1d")
    hourly = provider.history(SYMBOLS, (end - pd.Timedelta(days=720)).date().isoformat(), END, interval="60m")
    present = [symbol for symbol in SYMBOLS if symbol in daily and symbol in hourly and len(hourly[symbol]) > 50]
    daily = {symbol: daily[symbol] for symbol in present}
    hourly = {symbol: hourly[symbol] for symbol in present}
    return daily, hourly


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
            "published": None,
            "level_check": BOUNCE_LEVEL,
            "window": daily_window,
            "is_window": daily_is,
            "oos_window": daily_oos,
            "blurb": (
                f"{len(bounces)} signals. Same entry and stop as the partial-bounce study. "
                "The level-target row is that study's next-level stock exit."
            ),
        },
        {
            "name": "A, 60-minute",
            "setups": setup_a,
            "frames": hourly,
            "daily": daily_short,
            "base": ab_params,
            "published": dict(ab_params),
            "level_check": None,
            "window": intraday_window,
            "is_window": is_ab,
            "oos_window": oos_ab,
            "blurb": (
                f"{len(setup_a)} continuation signals. The published exit is a 2R target and the 20 EMA trail. "
                "The level-target row is the baseline for this grid, with that trail turned off."
            ),
        },
        {
            "name": "B, 60-minute",
            "setups": setup_b,
            "frames": hourly,
            "daily": daily_short,
            "base": ab_params,
            "published": dict(ab_params),
            "level_check": None,
            "window": intraday_window,
            "is_window": is_ab,
            "oos_window": oos_ab,
            "blurb": (
                f"{len(setup_b)} failed-breakout signals. The published exit is a 2R target and the 20 EMA trail. "
                "The level-target row is the baseline for this grid, with that trail turned off."
            ),
        },
        {
            "name": "C, daily Dow",
            "setups": trend,
            "frames": daily_frames,
            "daily": daily_frames,
            "base": dict(DAILY_DEFAULTS),
            "published": dict(DAILY_DEFAULTS),
            "level_check": None,
            "window": daily_window,
            "is_window": daily_is,
            "oos_window": daily_oos,
            "blurb": (
                f"{len(trend)} signals. The published exit is the measured level, the 20 EMA trail, and a 30-session hold. "
                "The level-target baseline keeps that level and turns the EMA trail off."
            ),
        },
        {
            "name": "D, daily Dow",
            "setups": ranges,
            "frames": daily_frames,
            "daily": daily_frames,
            "base": dict(BREAKOUT_DEFAULTS),
            "published": dict(BREAKOUT_DEFAULTS),
            "level_check": None,
            "window": daily_window,
            "is_window": daily_is,
            "oos_window": daily_oos,
            "blurb": (
                f"{len(ranges)} signals. The published exit is the measured level, the 20 EMA trail, and a 30-session hold. "
                "The level-target baseline keeps that level and turns the EMA trail off."
            ),
        },
    ]
    books = [_score_book(spec) for spec in specs]
    text = render(books)
    write_report(text, Path("RESULTS.md"))
    _dump(books, Path("reports/chart_reads_exits.json"))
    print(text)


if __name__ == "__main__":
    main()
