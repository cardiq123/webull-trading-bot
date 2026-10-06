"""Score the partial reversal bounce. Backtests only. Does not rewrite A-D.

The entry, the stop, and both targets were frozen to the Oct 6, 2026 UNH
description before this module scored a book. The UNH chart is a check
after the fact. A miss does not change the rule.

Run: ``python -m webull_bot.chart_reads.research_bounce``
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from webull_bot.chart_reads.bounce import (
    FULL_FALLBACK_R,
    FULL_HOLD,
    PARTIAL_FALLBACK_R,
    PARTIAL_HOLD,
    as_reversal,
    find_bounces,
    fixed_params,
    partial_params,
    reversal_params,
)
from webull_bot.chart_reads.levels import _falling_trendline
from webull_bot.chart_reads.research import random_setups
from webull_bot.chart_reads.research_daily import (
    IS_END,
    OOS_START,
    SAMPLE_END,
    SCORE_FROM,
    _hold,
    _window_book,
    load_daily,
)
from webull_bot.indicators import ema, rsi
from webull_bot.options.fees import CONTRACT_MULTIPLIER
from webull_bot.universe_dow import all_dow_tickers, is_member

START = "<!-- CHART_READS_BOUNCE_START -->"
END = "<!-- CHART_READS_BOUNCE_END -->"
CHART = Path("reports/setups/readBOUNCE_UNH_1d.png")
AS_OF = date(2026, 10, 6)
WINDOW_START = date(2021, 10, 6)
# Bands drawn on the 5-year UNH chart. 375-390, 330-350, and 290-300 are zones.
DRAWN = (500.0, 480.0, 400.0, 390.0, 375.0, 350.0, 330.0, 300.0, 290.0)
ZONES = ((290.0, 300.0, "290-300"), (330.0, 350.0, "330-350"), (375.0, 390.0, "375-390"))
GATE_TRADES = 300
GATE_PF = 1.10
GATE_SHARPE = 0.40
GATE_DD = -0.30


def _day(ts) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York")
    return stamp.date()


def _money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"${value:,.2f}"


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


def _collect(frames: dict[str, pd.DataFrame], *, quiet: bool) -> list:
    symbols = [symbol for symbol in sorted(all_dow_tickers()) if symbol in frames]
    found = []
    for symbol in symbols:
        frame = frames[symbol]
        if len(frame) < 80:
            continue
        setups = find_bounces(frame, symbol, quiet=quiet)
        setups = [
            setup
            for setup in setups
            if _day(setup.fill_time) >= SCORE_FROM and is_member(symbol, _day(setup.signal_time))
        ]
        found.extend(setups)
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol))
    return found


def _in_window(setups, start: date, end: date):
    return [setup for setup in setups if start <= _day(setup.fill_time) <= end]


def _slice(frames, start: date, end: date):
    out = {}
    for symbol, frame in frames.items():
        if frame is None or frame.empty:
            continue
        kept = frame.loc[(frame.index.date >= start) & (frame.index.date <= end)]
        if len(kept):
            out[symbol] = kept
    return out


def _apply_dte(params: dict, dte: int | None) -> dict:
    chosen = dict(params)
    if dte is not None:
        chosen["dte"] = int(dte)
    return chosen


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


def _level_share(setups) -> float:
    if not setups:
        return 0.0
    return sum(1 for setup in setups if np.isfinite(setup.reference)) / len(setups)


def _score_one(setups, frames, params, expression: str, dte: int | None) -> dict:
    chosen = _apply_dte(params, dte)
    is_stats = _window_book(setups, frames, frames, chosen, expression, SCORE_FROM, IS_END)
    oos_stats = _window_book(setups, frames, frames, chosen, expression, OOS_START, SAMPLE_END)
    oos_setups = _in_window(setups, OOS_START, SAMPLE_END)
    return {
        "is": is_stats,
        "oos": oos_stats,
        "signals": len(setups),
        "oos_signals": len(oos_setups),
        "level_share": _level_share(oos_setups),
        "oos_move": _move(oos_stats, expression),
        "expression": expression,
    }


def _clears(metrics: dict) -> bool:
    trades = int(metrics.get("trades") or 0)
    pf = metrics.get("profit_factor")
    sharpe = float(metrics.get("sharpe") or 0.0)
    drawdown = float(metrics.get("max_drawdown") or 0.0)
    return (
        trades >= GATE_TRADES
        and pf is not None
        and np.isfinite(pf)
        and float(pf) >= GATE_PF
        and sharpe >= GATE_SHARPE
        and drawdown >= GATE_DD
    )


def _row(label: str, scored: dict) -> str:
    oos = scored["oos"].metrics
    ins = scored["is"].metrics
    pf = oos.get("profit_factor")
    return (
        f"| {label} | {int(oos.get('trades') or 0)} | {_pct(oos.get('win_rate'))} | "
        f"{_signed_pct(scored['oos_move'])} | {_money(oos.get('expectancy'))} | "
        f"{_num(pf) if pf is not None else 'n/a'} | {_num(oos.get('sharpe'))} | {_pct(oos.get('max_drawdown'))} | "
        f"{_money(oos.get('ending_equity'))} | {int(ins.get('trades') or 0)} | {_money(ins.get('ending_equity'))} |"
    )


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    line = ema(close, 12) - ema(close, 26)
    signal = ema(line, 9)
    return line, line - signal


def _zone(price: float) -> str:
    for low, high, name in ZONES:
        if low - 8.0 <= price <= high + 8.0:
            return name
    nearest = min(DRAWN, key=lambda level: abs(level - price))
    if abs(nearest - price) <= 8.0:
        return f"{nearest:.0f}"
    return ""


def unh_facts(frame: pd.DataFrame, setups: list) -> dict:
    window = frame.loc[(frame.index.date >= WINDOW_START) & (frame.index.date <= AS_OF)]
    close = frame["close"].astype(float)
    line, hist = _macd(close)
    momentum = rsi(close, 14)
    trend = pd.Series(_falling_trendline(frame["high"]), index=frame.index)
    last = window.iloc[-1]
    last_day = _day(window.index[-1])
    high_pos = int(np.argmax(window["high"].to_numpy(dtype=float)))
    low_pos = int(np.argmin(window["low"].to_numpy(dtype=float)))
    vol_pos = int(np.argmax(window["volume"].to_numpy(dtype=float)))
    in_window = [setup for setup in setups if WINDOW_START <= _day(setup.signal_time) <= AS_OF]
    rows = []
    for setup in in_window:
        loc = frame.index.get_loc(pd.Timestamp(setup.signal_time))
        if isinstance(loc, slice):
            loc = loc.start
        bar_low = float(frame["low"].iloc[loc])
        bar_close = float(frame["close"].iloc[loc])
        zone = _zone(bar_low)
        rows.append(
            {
                "date": _day(setup.signal_time).isoformat(),
                "low": bar_low,
                "close": bar_close,
                "rsi": float(momentum.iloc[loc]),
                "reference": float(setup.reference),
                "reversal": float(setup.reversal),
                "zone": zone,
            }
        )
    return {
        "last_day": last_day,
        "open": float(last["open"]),
        "high": float(last["high"]),
        "low": float(last["low"]),
        "close": float(last["close"]),
        "ema9": float(ema(close, 9).iloc[-1]),
        "ema20": float(ema(close, 20).iloc[-1]),
        "ema50": float(ema(close, 50).iloc[-1]),
        "rsi": float(momentum.iloc[-1]),
        "rsi_prev": float(momentum.iloc[-2]),
        "macd": float(line.iloc[-1]),
        "hist": float(hist.iloc[-1]),
        "hist_prev": float(hist.iloc[-2]),
        "trend": float(trend.iloc[-1]),
        "year_high": float(window["high"].iloc[high_pos]),
        "year_high_day": _day(window.index[high_pos]),
        "year_low": float(window["low"].iloc[low_pos]),
        "year_low_day": _day(window.index[low_pos]),
        "climax_day": _day(window.index[vol_pos]),
        "climax_volume": float(window["volume"].iloc[vol_pos]),
        "climax_low": float(window["low"].iloc[vol_pos]),
        "signals": rows,
        "window_bars": len(window),
    }


def save_chart(frame: pd.DataFrame, setups: list, path: Path) -> None:
    window = frame.loc[(frame.index.date >= WINDOW_START) & (frame.index.date <= AS_OF)]
    close = frame["close"].astype(float)
    trend = pd.Series(_falling_trendline(frame["high"]), index=frame.index).reindex(window.index)
    fig, (ax, vol) = plt.subplots(
        2,
        1,
        figsize=(12.8, 7.6),
        sharex=True,
        gridspec_kw={"height_ratios": [3.3, 1.0]},
    )
    ax.set_facecolor("#161616")
    vol.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    xs = np.arange(len(window))
    for low, high, _name in ZONES:
        ax.axhspan(low, high, color="#c47bff", alpha=0.12, linewidth=0)
    labeled = False
    for price in DRAWN:
        ax.axhline(
            price,
            color="#c47bff",
            linewidth=0.7,
            linestyle="--",
            alpha=0.8,
            label="drawn S/R" if not labeled else None,
        )
        labeled = True
    for pos, (_ts, row) in enumerate(window.iterrows()):
        color = "#3d9e57" if row["close"] >= row["open"] else "#d64545"
        ax.plot([pos, pos], [row["low"], row["high"]], color=color, linewidth=0.6)
        ax.plot([pos, pos], [row["open"], row["close"]], color=color, linewidth=2.0)
    ax.plot(xs, ema(close, 9).reindex(window.index), color="#4ea3ff", linewidth=1.0, label="EMA 9")
    ax.plot(xs, ema(close, 20).reindex(window.index), color="#e0a100", linewidth=1.0, label="EMA 20")
    ax.plot(xs, ema(close, 50).reindex(window.index), color="#e07a3d", linewidth=1.0, label="EMA 50")
    ax.plot(xs, trend, color="#ffe14a", linewidth=1.2, label="descending trendline")
    marked = False
    index_pos = {pd.Timestamp(ts): pos for pos, ts in enumerate(window.index)}
    for setup in setups:
        stamp = pd.Timestamp(setup.signal_time)
        if stamp not in index_pos:
            continue
        pos = index_pos[stamp]
        ax.scatter(
            [pos],
            [float(window["low"].iloc[pos])],
            marker="^",
            s=28,
            color="#f2d16b",
            zorder=4,
            label="bounce signal" if not marked else None,
        )
        marked = True
    colors = ["#3d9e57" if row["close"] >= row["open"] else "#d64545" for _, row in window.iterrows()]
    vol.bar(xs, window["volume"].to_numpy(dtype=float), color=colors, width=0.7)
    step = max(1, len(window) // 6)
    ticks = list(range(0, len(window), step))
    if ticks[-1] != len(window) - 1:
        ticks.append(len(window) - 1)
    vol.set_xticks(ticks)
    vol.set_xticklabels([pd.Timestamp(window.index[pos]).strftime("%Y-%m-%d") for pos in ticks], rotation=30, ha="right")
    ax.set_title("UNH daily, 2021-10-06 through 2026-10-06, partial-bounce signals", color="white")
    ax.tick_params(colors="#cccccc")
    vol.tick_params(colors="#cccccc")
    for spine in (*ax.spines.values(), *vol.spines.values()):
        spine.set_color("#333333")
    ax.legend(facecolor="#161616", edgecolor="#333333", labelcolor="white", loc="upper right", fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    artifact = Path("/opt/cursor/artifacts/setups")
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / path.name).write_bytes(path.read_bytes())


def _signal_lines(rows: list[dict]) -> list[str]:
    near = [row for row in rows if row["zone"]]
    lines = [
        f"The detector marked {len(rows)} UNH bounces in that five-year window. "
        f"{len(near)} of them tagged a drawn band, counting a low within $8 of the band.",
    ]
    if not near:
        lines.append(
            "None of those signals tagged 290-300, 330-350, or 375-390. "
            "The rule was left as frozen."
        )
        return lines
    lines.append("")
    lines.append("| Signal | Low | Close | RSI | Next target | Full-reversal target | Band |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    shown = near if len(near) <= 12 else near[-12:]
    for row in shown:
        ref = _money(row["reference"]).replace("$", "") if np.isfinite(row["reference"]) else "1R fallback"
        rev = _money(row["reversal"]).replace("$", "")
        lines.append(
            f"| {row['date']} | {row['low']:.2f} | {row['close']:.2f} | {row['rsi']:.1f} | {ref} | {rev} | {row['zone']} |"
        )
    if len(near) > 12:
        lines.append("")
        lines.append(f"The table is the latest 12 of {len(near)} band tags.")
    return lines


def render(facts: dict, books: list[tuple[str, dict]], random_oos, hold: dict, reasons: dict) -> str:
    last = facts["last_day"].isoformat()
    trend = "n/a" if not np.isfinite(facts["trend"]) else f"{facts['trend']:.2f}"
    turning = "up" if facts["rsi"] > facts["rsi_prev"] else "down"
    flattening = "higher than" if facts["hist"] > facts["hist_prev"] else "lower than"
    target_hits = int(reasons.get("target", 0))
    stops = int(reasons.get("invalidation", 0))
    timed = int(reasons.get("time_stop", 0))
    default = books[0][1]
    oos = default["oos"]
    clears = _clears(oos.metrics)
    lines = [
        "## Partial reversal bounce",
        "",
        "DOES NOT CHANGE THE GATE. This is a separate long-only book. Setups A through D are unchanged. "
        "Nothing was sent to a broker. The rule was frozen before this score.",
        "",
        "A signal is a daily bar that tags a confirmed pivot low from the prior 120 sessions. The pivot is "
        "at least five bars old, the low is within 0.50 ATR of it, and the close does not finish more than "
        "0.10 ATR through it. The same bar is a confirming candle: the body is at least half the range and "
        "the close is in the upper third. RSI(14) is at or under 30, or it is turning up from a prior reading "
        "at or under 45. The fill is the next open. The stop is 0.25 ATR under the signal low. The next signal "
        "in a name waits 10 bars. Quiet volume, the last three bars at or under their prior 20-bar average, "
        "is a sensitivity. It is not required.",
        "",
        f"The partial target is the nearest of the next confirmed pivot high, the 20 EMA, the 50 EMA, and the "
        f"descending pivot trendline, when that price is between 0.5R and 4R above the signal close. Otherwise "
        f"the target is {PARTIAL_FALLBACK_R:.0f}R. The hold is {PARTIAL_HOLD} sessions, with no EMA trail, because "
        f"a long entered under the 20 EMA would be flattened at once. The full-reversal comparison uses the same "
        f"entry and the same stop. Its target is the next of those levels beyond the partial target, out to 8R, "
        f"otherwise {FULL_FALLBACK_R:.0f}R, and the hold is {FULL_HOLD} sessions. A fixed 1R target is the other "
        f"comparison. Calls use delta 0.45. Seven DTE is the short-dated call. Thirty, 45, and 60 DTE are the "
        f"requested range. The account is $1,000, one position, 20% risk. A contract that costs more than that "
        f"risk budget is skipped. The gate does not pick the best row.",
        "",
        f"Dow point-in-time, in sample {SCORE_FROM.isoformat()} through {IS_END.isoformat()}, "
        f"out of sample {OOS_START.isoformat()} through {SAMPLE_END.isoformat()}. "
        f"The default row had a level on {default['level_share'] * 100:.0f}% of its out-of-sample signals. "
        f"The other signals used the 1R fallback. Out of sample, the default stock book exited "
        f"{target_hits} trades at the target, {stops} at the stop, and {timed} at the time stop. "
        f"The out-of-sample call books skipped {int(books[4][1]['oos'].premium_skipped)} seven-DTE entries, "
        f"{int(books[5][1]['oos'].premium_skipped)} thirty-DTE entries, "
        f"{int(books[6][1]['oos'].premium_skipped)} forty-five-DTE entries, and "
        f"{int(books[7][1]['oos'].premium_skipped)} sixty-DTE entries. A skip is a contract that did not fit "
        f"the risk budget, or a bar with no volatility estimate.",
        "",
        "Average move on a stock row is the mean underlying percent from the fill to the exit, after the "
        "stock slippage. On a call row it is the mean premium return, ask notional against the booked P&L, "
        "which includes the haircut and the option fees. Expectancy is dollars per closed trade after those costs.",
        "",
        "| Book | OOS trades | Win rate | Avg move | Expectancy | PF | Sharpe | Max DD | OOS ending | IS trades | IS ending |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, scored in books:
        lines.append(_row(label, scored))
    lines.append("")
    lines.append(
        f"Random dates, same count and the same stop distance, with a 1R target because the shuffled bar "
        f"has no original level: {int(random_oos.metrics.get('trades') or 0)} out-of-sample trades, "
        f"ending {_money(random_oos.metrics.get('ending_equity'))}, expectancy {_money(random_oos.metrics.get('expectancy'))}. "
        f"SPY buy and hold over that window, whole shares that fit in $1,000: "
        f"{int(hold.get('shares') or 0)} shares, ending {_money(hold.get('ending_equity'))}."
    )
    lines.append("")
    lines.append(
        f"UNH on {last}, the five-year daily used as the check. Yahoo's adjusted bar closed at "
        f"{facts['close']:.2f} (open {facts['open']:.2f}, high {facts['high']:.2f}, low {facts['low']:.2f}). "
        f"The 9 EMA is {facts['ema9']:.2f}, the 20 EMA is {facts['ema20']:.2f}, and the 50 EMA is {facts['ema50']:.2f}. "
        f"RSI(14) is {facts['rsi']:.1f} and turning {turning}. The MACD line is {facts['macd']:.2f}. "
        f"The histogram is {facts['hist']:.2f}, {flattening} the prior bar's {facts['hist_prev']:.2f}. "
        f"The descending trendline is {trend}. The five-year high is {facts['year_high']:.2f} on "
        f"{facts['year_high_day'].isoformat()} and the low is {facts['year_low']:.2f} on "
        f"{facts['year_low_day'].isoformat()}. The heaviest volume day in the window is "
        f"{facts['climax_day'].isoformat()}, low {facts['climax_low']:.2f}, volume {facts['climax_volume']:,.0f}."
    )
    lines.append("")
    lines.extend(_signal_lines(facts["signals"]))
    lines.append("")
    verdict = "meets" if clears else "does not meet"
    lines.append(
        f"The default stock row {verdict} a 1.10 profit factor, a 0.40 Sharpe, a drawdown no worse than -30%, "
        f"and 300 trades. The other rows are the pre-registered comparisons. None of them is selected after the fact. "
        f"The chart is `reports/setups/readBOUNCE_UNH_1d.png`. Gold triangles are the bounce signals. "
        f"Dashed lines are the drawn levels. Shaded bands are 290-300, 330-350, and 375-390."
    )
    lines.append("")
    lines.append(
        "Not added to `config/optional_strategies.json`. The published A-D books are unchanged. "
        "The default book is still dual momentum."
    )
    return "\n".join(lines).rstrip() + "\n"


def write_report(text: str, path: Path) -> None:
    body = path.read_text() if path.exists() else ""
    block = f"{START}\n{text.rstrip()}\n{END}\n"
    if START in body and END in body:
        pre = body.split(START)[0].rstrip() + "\n\n"
        post = body.split(END, 1)[1].lstrip("\n")
        path.write_text(pre + block + ("\n" + post if post else ""))
        return
    if body and not body.endswith("\n"):
        body += "\n"
    path.write_text(body + "\n" + block)


def _dump(books, random_oos, facts) -> None:
    payload = {
        "unh": {
            "close": facts["close"],
            "rsi": facts["rsi"],
            "macd": facts["macd"],
            "ema9": facts["ema9"],
            "ema20": facts["ema20"],
            "trend": facts["trend"],
            "signals": len(facts["signals"]),
            "band_tags": sum(1 for row in facts["signals"] if row["zone"]),
        },
        "books": [],
    }
    for label, scored in books:
        oos = scored["oos"].metrics
        payload["books"].append(
            {
                "label": label,
                "oos_trades": int(oos.get("trades") or 0),
                "oos_ending": oos.get("ending_equity"),
                "oos_expectancy": oos.get("expectancy"),
                "oos_win_rate": oos.get("win_rate"),
                "oos_move": scored["oos_move"],
                "oos_pf": oos.get("profit_factor"),
                "oos_sharpe": oos.get("sharpe"),
                "oos_dd": oos.get("max_drawdown"),
                "is_ending": scored["is"].metrics.get("ending_equity"),
                "premium_skipped": int(scored["oos"].premium_skipped),
            }
        )
    payload["random_ending"] = random_oos.metrics.get("ending_equity")
    path = Path("reports/chart_reads_bounce.json")
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")


def main() -> None:
    print("loading daily bars", flush=True)
    frames, missing = load_daily()
    print(f"  {len(frames)} symbols, missing {missing}", flush=True)
    print("detecting bounces", flush=True)
    partial = _collect(frames, quiet=False)
    quiet = _collect(frames, quiet=True)
    reversal = as_reversal(partial)
    print(f"  signals {len(partial)} quiet {len(quiet)}", flush=True)
    specs = [
        ("stock, next level", partial, partial_params(), "stock", None),
        ("stock, fixed 1R", partial, fixed_params(), "stock", None),
        ("stock, full reversal", reversal, reversal_params(), "stock", None),
        ("stock, quiet volume, next level", quiet, partial_params(), "stock", None),
        ("7 DTE calls, next level", partial, partial_params(), "single", 7),
        ("30 DTE calls, next level", partial, partial_params(), "single", 30),
        ("45 DTE calls, next level", partial, partial_params(), "single", 45),
        ("60 DTE calls, next level", partial, partial_params(), "single", 60),
        ("45 DTE calls, full reversal", reversal, reversal_params(), "single", 45),
    ]
    books = []
    for label, setups, params, expression, dte in specs:
        print(f"  score {label}", flush=True)
        books.append((label, _score_one(setups, frames, params, expression, dte)))
    oos_frames = _slice(frames, OOS_START, SAMPLE_END)
    oos_setups = _in_window(partial, OOS_START, SAMPLE_END)
    print("  score random", flush=True)
    shuffled = random_setups(oos_setups, oos_frames)
    random_params = fixed_params()
    random_oos = _window_book(shuffled, oos_frames, frames, random_params, "stock", OOS_START, SAMPLE_END)
    hold = _hold(frames["SPY"]) if "SPY" in frames else {}
    facts = unh_facts(frames["UNH"], find_bounces(frames["UNH"], "UNH"))
    reasons = _reasons(books[0][1]["oos"])
    text = render(facts, books, random_oos, hold, reasons)
    write_report(text, Path("RESULTS.md"))
    save_chart(frames["UNH"], find_bounces(frames["UNH"], "UNH"), CHART)
    _dump(books, random_oos, facts)
    print(text)
    print(f"chart {CHART}", flush=True)


if __name__ == "__main__":
    main()
