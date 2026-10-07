"""Score the 9 EMA wick continuation against the 20 EMA test. Backtests only.

Does not place an order, does not edit the sandbox forward test, and does not
add a strategy to the live list. The rule in wick.frozen_rules is the one scored.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

from webull_bot.chart_reads.ema_reclaim import HOLDOUT_START, TRAIN_END, prepare
from webull_bot.chart_reads.ema_reject import SAMPLE_END, to_five_minute
from webull_bot.chart_reads.reentry import random_reentries, signals_per_month, simulate, simulate_paths, walk_reentry
from webull_bot.chart_reads.research_ema_reclaim import _chart_frame
from webull_bot.chart_reads.vwap_band import passes_gate
from webull_bot.chart_reads.vwap_band_data import load_minutes
from webull_bot.chart_reads.wick import WICK_BODY, WICK_RANGE, find_wicks, frozen_rules, illustrate
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.chart_reads.orb_mwf import prior_iv

MARK_START = "<!-- WICK_START -->"
MARK_END = "<!-- WICK_END -->"
RESULT_PATH = Path("reports/wick.json")
PRIOR_PATH = Path("reports/reentry.json")
CHART_PATH = Path("reports/wick_2026-10-07.png")
CHART_DAY = date(2026, 10, 7)


def _money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    number = float(value)
    if abs(number) < 0.5:
        return "$0"
    if number < 0:
        return f"-${abs(number):,.0f}"
    return f"${number:,.0f}"


def _pct(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _num(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _pf(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _iv() -> dict:
    provider = YFinanceProvider(cache_dir="data/cache/vwap_band/yahoo")
    daily = provider.history(["^VIX", "^VIX1D"], "2016-01-01", "2026-10-08", interval="1d")
    closes = {}
    for symbol, frame in daily.items():
        if frame is None or frame.empty or "close" not in frame.columns:
            continue
        series = frame["close"].astype(float).copy()
        index = pd.to_datetime(series.index)
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert("America/New_York").tz_localize(None)
        series.index = index
        closes[symbol.replace("^", "")] = series[~series.index.duplicated(keep="last")].sort_index()
    return prior_iv(closes.get("VIX1D", pd.Series(dtype=float)), closes.get("VIX", pd.Series(dtype=float)))


def _paths(prep, items, target: str, stop_name: str) -> list[dict]:
    found = []
    for item in items:
        path = walk_reentry(prep, item, target, stop_name)
        if path is not None:
            found.append(path)
    return found


def _book(prep, paths, kind: str, stake: float, long_only: bool, iv, start, end) -> dict:
    return simulate_paths(
        prep, paths, kind=kind, stake=stake, long_only=long_only, iv_points=iv, start=start, end=end,
    )


def _row(name: str, hold: dict, train: dict, five: dict | None) -> str:
    five_bit = _money(five.get("ending_equity")) if five else "n/a"
    return (
        f"| {name} | {hold.get('trades', 0)} | {_pct(hold.get('win_rate'))} | "
        f"{_pct(hold.get('breakeven_win_rate'))} | {_pf(hold.get('profit_factor'))} | {_num(hold.get('sharpe'))} | "
        f"{_pct(hold.get('max_drawdown'))} | {_money(hold.get('ending_equity'))} | {five_bit} | "
        f"{_money(train.get('ending_equity'))} | {'yes, not promoted' if passes_gate(hold) else 'no'} |"
    )


def _ending(hold: dict, train: dict) -> str:
    return (
        f"{_money(hold.get('ending_equity'))} ({hold.get('trades', 0)} trades, "
        f"win {_pct(hold.get('win_rate'))} against break-even {_pct(hold.get('breakeven_win_rate'))}, "
        f"profit factor {_pf(hold.get('profit_factor'))}, Sharpe {_num(hold.get('sharpe'))}, "
        f"drawdown {_pct(hold.get('max_drawdown'))}, train {_money(train.get('ending_equity'))})"
    )


def _clock(prep, i: int) -> str:
    return prep.index[i].strftime("%H:%M")


def _prior() -> dict:
    if not PRIOR_PATH.exists():
        return {}
    payload = json.loads(PRIOR_PATH.read_text())
    return {book["name"]: book for book in payload.get("books", [])}


def _day_note(prep, items: list) -> str:
    indexes = [i for i, day in enumerate(prep.dates) if day == CHART_DAY]
    if not indexes:
        return "The Yahoo 5-minute file has no 2026-10-07 session, so the wick was not invented."
    start, stop = indexes[0], indexes[-1] + 1
    picture = illustrate(prep, CHART_DAY)
    steps = picture.get("steps") or []
    chosen = next((step for step in steps if _clock(prep, step["wick"]) == "12:00"), None)
    if chosen is None and steps:
        chosen = min(steps, key=lambda step: abs(int(_clock(prep, step["wick"]).replace(":", "")) - 1200))
    bits = []
    for i in range(start, stop):
        clock = _clock(prep, i)
        if clock < "11:50" or clock > "12:15":
            continue
        opened = float(prep.open[i])
        high = float(prep.high[i])
        low = float(prep.low[i])
        closed = float(prep.close[i])
        body = abs(closed - opened)
        rng = high - low
        lower = min(opened, closed) - low
        color = "G" if closed > opened else "R" if closed < opened else "D"
        ratio = lower / body if body > 0 else float("inf")
        bits.append(
            f"{clock} {color} high {high:.2f} low {low:.2f} close {closed:.2f} ema9 {prep.ema9[i]:.2f} "
            f"lower/body {ratio:.2f} lower/range {(lower / rng) if rng else 0:.2f}"
        )
    if chosen is None:
        marked = "No filtered long wick fills on this session. The rule was not loosened."
        wick_i = confirm_i = fill_i = None
    else:
        wick_i, confirm_i, fill_i = chosen["wick"], chosen["confirm"], chosen["fill"]
        marked = (
            f"The filtered long wick is {_clock(prep, wick_i)}. The green close is {_clock(prep, confirm_i)}. "
            f"The fill is the {_clock(prep, fill_i)} open at {prep.open[fill_i]:.2f}."
        )
        sample = next(
            item for item in items
            if item.fill_i == fill_i and item.variant == "filtered" and item.direction == "long" and item.tag_i == wick_i
        )
        for stop_name, label in (("ema9", "9 EMA stop"), ("ema20", "20 EMA stop")):
            path = walk_reentry(prep, sample, "band", stop_name)
            if path is None:
                continue
            when = pd.Timestamp(path["exit_time"]).tz_convert("America/New_York").strftime("%H:%M")
            marked += f" The {label} exits {path['reason']} at {path['exit_spot']:.2f} at {when}."
    others = [
        _clock(prep, step["fill"]) for step in steps if chosen is None or step["wick"] != chosen["wick"]
    ]
    extra = ""
    if others:
        extra = " Other filtered long fills this session: " + ", ".join(others) + "."
    _plot(prep, start, stop, wick_i if chosen else None, confirm_i if chosen else None, fill_i if chosen else None)
    return (
        f"Yahoo 5-minute SPY on 2026-10-07 runs 09:30 through {_clock(prep, stop - 1)} ET in this file. "
        "The stamp is the bar open, so the bar that closes at 12:05 is the 12:00 bar. "
        + " ".join(bits)
        + " "
        + marked
        + extra
        + f" The wick filter is {WICK_BODY:.1f} times the body, or {WICK_RANGE:.0%} of the range."
    )


def _plot(prep, start: int, stop: int, wick_i, confirm_i, fill_i) -> None:
    x = np.arange(stop - start)
    fig, ax = plt.subplots(figsize=(12.4, 6.4), dpi=130)
    fig.patch.set_facecolor("#161616")
    ax.set_facecolor("#161616")
    width = 0.6
    for offset, i in enumerate(range(start, stop)):
        opened = float(prep.open[i])
        closed = float(prep.close[i])
        color = "#3dd68c" if closed >= opened else "#ff5d5d"
        ax.plot([offset, offset], [prep.low[i], prep.high[i]], color=color, lw=1.0)
        body = abs(closed - opened)
        ax.add_patch(
            Rectangle((offset - width / 2, min(opened, closed)), width, max(body, 0.01), facecolor=color, edgecolor=color)
        )
    upper = prep.vwap[start:stop] + 2.0 * prep.std[start:stop]
    ax.plot(x, prep.vwap[start:stop], color="#5dade2", lw=1.0, label="VWAP")
    ax.plot(x, upper, color="#5dade2", lw=1.0, ls="--", label="Upper 2 SD")
    ax.plot(x, prep.ema9[start:stop], color="#f7dc6f", lw=1.2, label="9 EMA")
    ax.plot(x, prep.ema20[start:stop], color="#f5b041", lw=1.0, label="20 EMA")
    marks = ((wick_i, "wick", "#f4f4f4"), (confirm_i, "green", "#3dd68c"), (fill_i, "fill", "#f5b041"))
    for index, label, color in marks:
        if index is None:
            continue
        offset = index - start
        ax.scatter([offset], [prep.low[index] if label == "wick" else prep.high[index]], color=color, s=28, zorder=4)
        ax.annotate(label, (offset, prep.high[index]), textcoords="offset points", xytext=(0, 8), color=color, fontsize=8, ha="center")
    ticks = list(range(0, stop - start, 6))
    ax.set_xticks(ticks)
    ax.set_xticklabels([prep.index[start + tick].strftime("%H:%M") for tick in ticks], color="#cccccc")
    ax.tick_params(colors="#cccccc")
    for spine in ax.spines.values():
        spine.set_color("#444444")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(color="#2a2a2a")
    ax.set_title("SPY 5-minute 2026-10-07. 9 EMA wick, then the green close. Not a forecast.", color="#f4f4f4")
    legend = ax.legend(facecolor="#1e1e1e", edgecolor="#333333", fontsize=8, loc="upper left")
    for text in legend.get_texts():
        text.set_color("#f4f4f4")
    fig.tight_layout()
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, facecolor=fig.get_facecolor())
    plt.close(fig)


def _write(lines: list[str]) -> None:
    block = "\n".join(lines)
    path = Path("RESULTS.md")
    text = path.read_text() if path.exists() else ""
    if MARK_START in text and MARK_END in text:
        before = text.split(MARK_START)[0]
        after = text.split(MARK_END)[1]
        path.write_text(before + block + after.lstrip("\n"))
    else:
        path.write_text(text.rstrip() + "\n\n" + block)


def _score_cell(prep, paths, name: str, iv, *, five: bool) -> dict:
    print(f"WICK {name}", flush=True)
    kind = "0dte" if name.endswith("0dte") else "shares"
    long_only = kind == "shares"
    hold = _book(prep, paths, kind, 1000.0, long_only, iv, HOLDOUT_START, SAMPLE_END)
    train = _book(prep, paths, kind, 1000.0, long_only, iv, None, TRAIN_END)
    five_book = _book(prep, paths, "0dte", 5000.0, False, iv, HOLDOUT_START, SAMPLE_END) if five else None
    return {
        "name": name,
        "hold": hold["metrics"],
        "train": train["metrics"],
        "five": None if five_book is None else five_book["metrics"],
    }


def main() -> None:
    rules = frozen_rules()
    if "1.5 times the body" not in rules["filter"] or "0.10 ATR" not in rules["wick"]:
        raise SystemExit("wick rule was not frozen")
    if "not a substitute wick" not in rules["chart_day"]:
        raise SystemExit("chart rule was not frozen")
    Path("reports").mkdir(parents=True, exist_ok=True)
    minutes, info = load_minutes("SPY")
    if minutes is None:
        raise SystemExit(f"SPY minutes are not ready {info}")
    five = to_five_minute(minutes)
    iv = _iv()
    print("WICK prepare", flush=True)
    prep = prepare(five)
    items = find_wicks(prep, "SPY")
    filtered = [item for item in items if item.variant == "filtered"]
    plain = [item for item in items if item.variant == "plain"]
    print(f"WICK signals filtered {len(filtered)} plain {len(plain)}", flush=True)
    per_month = signals_per_month(
        prep, [item for item in filtered if prep.dates[item.fill_i] >= HOLDOUT_START], HOLDOUT_START, SAMPLE_END,
    )
    filtered_9 = _paths(prep, filtered, "band", "ema9")
    filtered_20 = _paths(prep, filtered, "band", "ema20")
    plain_9 = _paths(prep, plain, "band", "ema9")
    books = []
    for label, paths, want_five in (
        ("filtered_ema9_band", filtered_9, True),
        ("plain_ema9_band", plain_9, False),
        ("filtered_ema20_band", filtered_20, False),
    ):
        for kind in ("shares", "0dte"):
            books.append(_score_cell(prep, paths, f"{label}_{kind}", iv, five=want_five and kind == "0dte"))
    primary = next(item for item in books if item["name"] == "filtered_ema9_band_0dte")
    share_primary = next(item for item in books if item["name"] == "filtered_ema9_band_shares")
    random_bits = []
    for label, taken, kind, long_only in (
        ("filtered_ema9_band_shares", share_primary["hold"].get("trades", 0), "shares", True),
        ("filtered_ema9_band_0dte", primary["hold"].get("trades", 0), "0dte", False),
    ):
        print(f"WICK random {label}", flush=True)
        drawn = random_reentries(prep, int(taken or 0), start=HOLDOUT_START, end=SAMPLE_END)
        random_book = simulate(
            prep, drawn, target="band", stop_name="ema9", kind=kind, stake=1000.0, long_only=long_only,
            iv_points=iv, start=HOLDOUT_START, end=SAMPLE_END,
        )
        metrics = random_book["metrics"]
        random_bits.append(
            f"{label} random holdout, seed 17, {metrics.get('trades', 0)} trades, "
            f"ending {_money(metrics.get('ending_equity'))}, profit factor {_pf(metrics.get('profit_factor'))}, "
            f"Sharpe {_num(metrics.get('sharpe'))}, drawdown {_pct(metrics.get('max_drawdown'))}."
        )
    prior = _prior()
    prior_bits = []
    for name in ("green_ema20_band_shares", "green_ema20_band_0dte"):
        row = prior.get(name)
        if row is None:
            prior_bits.append(f"The prior {name} row is not on disk.")
            continue
        five = row.get("five") or {}
        five_bit = ""
        if name.endswith("0dte") and five:
            five_bit = f" From $5,000 it finished at {_money(five.get('ending_equity'))}."
        prior_bits.append(f"The 20 EMA continuation, {name}, finished at {_ending(row['hold'], row['train'])}.{five_bit}")
    chart_frame, chart_source = _chart_frame()
    if chart_frame is None:
        chart_note = "Yahoo returned no 5-minute SPY bars for 2026-10-07, so the wick was not invented."
    else:
        chart_prep = prepare(chart_frame)
        chart_note = f"{chart_source}. {_day_note(chart_prep, find_wicks(chart_prep, 'SPY'))}"
    rate = "n/a" if per_month is None else f"{per_month:.1f}"
    by_name = {book["name"]: book for book in books}
    english = (
        f"The filtered wick fires about {rate} times a month on the holdout. "
        f"Filter on, stop at a close through the 9 EMA, target the upper band, shares finished at {_ending(by_name['filtered_ema9_band_shares']['hold'], by_name['filtered_ema9_band_shares']['train'])}. "
        f"The same cell as one 0 DTE contract finished at {_ending(by_name['filtered_ema9_band_0dte']['hold'], by_name['filtered_ema9_band_0dte']['train'])}. "
        f"From $5,000 that 0 DTE book finished at {_money(by_name['filtered_ema9_band_0dte']['five'].get('ending_equity'))} "
        f"({by_name['filtered_ema9_band_0dte']['five'].get('trades', 0)} trades, "
        f"profit factor {_pf(by_name['filtered_ema9_band_0dte']['five'].get('profit_factor'))}, "
        f"drawdown {_pct(by_name['filtered_ema9_band_0dte']['five'].get('max_drawdown'))}). "
        f"Filter off, same 9 EMA stop, finished at {_ending(by_name['plain_ema9_band_0dte']['hold'], by_name['plain_ema9_band_0dte']['train'])}. "
        f"Filter on with the 20 EMA stop, the same stop as the 20 EMA continuation, finished at {_ending(by_name['filtered_ema20_band_0dte']['hold'], by_name['filtered_ema20_band_0dte']['train'])}. "
        + " ".join(prior_bits)
        + " "
        + " ".join(random_bits)
        + " Share books are long only. A row that clears the holdout arithmetic is not promoted."
    )
    lines = [
        MARK_START,
        "### 9 EMA wick continuation",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. The chop-breakout order rules were not changed. "
        "The wick was frozen before this score. In an established bullish stack (9 EMA above the 20, both higher than 3 bars ago, "
        "close above the 9, the 20, and session VWAP), a bar wicks into the 9 EMA within 0.10 ATR and closes back above it. "
        "The candle may be red. With the filter on, the lower wick is at least 1.5 times the body, or at least 50% of the range. "
        "A zero body uses the range test only. The filter off drops that size test. "
        "A green wick bar fills on the next open. A red wick bar waits for a later green close that is still above the 9 EMA, "
        "then fills on the open after that close. A close back through the 9 EMA before the green close cancels the wick. "
        "The bearish stack buys the put on an upper wick. The primary stop is a close back through the 9 EMA. "
        "The 20 EMA stop is the same stop as the 20 EMA continuation. The target is the opposite 2 SD band. Flat at the 15:30 open.",
        "",
        "| Book | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 | Train $1,000 | Clears |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for book in books:
        lines.append(_row(book["name"], book["hold"], book["train"], book["five"]))
    lines += [
        "",
        english,
        "",
        chart_note,
        "",
        "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.",
        "",
        "```",
        "python3 -m webull_bot.chart_reads.research_wick",
        "```",
        MARK_END,
        "",
    ]
    _write(lines)
    RESULT_PATH.write_text(json.dumps({"books": books, "random": random_bits, "chart": chart_note, "per_month": per_month}, indent=2, default=str) + "\n")
    print(chart_note, flush=True)
    print("WROTE reports/wick.json", flush=True)


if __name__ == "__main__":
    main()
