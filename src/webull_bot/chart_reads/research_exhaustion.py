"""Score the trend-exhaustion shelf. Backtests only.

Does not place an order, does not edit the sandbox forward test, and does not
add a strategy to the live list. The rule in exhaustion.frozen_rules is the one scored.
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
from webull_bot.chart_reads.exhaustion import (
    find_exhaustions,
    frozen_rules,
    illustrate,
    random_exhaustions,
    walk_exhaustion,
)
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.reentry import signals_per_month, simulate_paths
from webull_bot.chart_reads.vwap_band import passes_gate
from webull_bot.chart_reads.vwap_band_data import load_minutes
from webull_bot.data.yfinance_provider import YFinanceProvider

MARK_START = "<!-- EXHAUST_START -->"
MARK_END = "<!-- EXHAUST_END -->"
RESULT_PATH = Path("reports/exhaustion.json")
CHART_PATH = Path("reports/exhaustion_2026-10-07.png")
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


def _paths(prep, items, target: str) -> list[dict]:
    found = []
    for item in items:
        path = walk_exhaustion(prep, item, target)
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


def _bar_at(prep, indexes: list[int], clock: str) -> int | None:
    for i in indexes:
        if _clock(prep, i) == clock:
            return i
    return None


def _chart_frame() -> tuple[pd.DataFrame | None, str]:
    """The local 5-minute file with the later 2026-10-07 bar. No fresh download."""
    best = None
    label = "Yahoo returned no 5-minute SPY bars"
    for folder, name in (
        ("data/cache", "Yahoo 5-minute cache"),
        ("data/cache/ema_reject/yahoo", "Yahoo 5-minute ema_reject cache"),
    ):
        provider = YFinanceProvider(cache_dir=folder)
        frame = provider.history(["SPY"], "2026-08-18", "2026-10-08", interval="5m").get("SPY")
        if frame is None or frame.empty:
            continue
        if best is None or frame.index[-1] > best[0].index[-1]:
            best = (frame, name)
    if best is None:
        return None, label
    return best


def _day_note(prep) -> str:
    indexes = [i for i, day in enumerate(prep.dates) if day == CHART_DAY]
    if not indexes:
        return "The Yahoo 5-minute file has no 2026-10-07 session, so the short was not invented."
    start, stop = indexes[0], indexes[-1] + 1
    picture = illustrate(prep, CHART_DAY)
    tag_i = picture["tag_i"]
    support = picture["support"]
    support_i = picture["support_i"]
    signals = picture["signals"]
    bits = [f"Yahoo 5-minute SPY on 2026-10-07 runs 09:30 through {_clock(prep, stop - 1)} ET in this file."]
    if tag_i is None:
        bits.append("No uptrend bar tags the upper 2 SD band, so no shelf is marked.")
    else:
        band = float(prep.vwap[tag_i]) + 2.0 * float(prep.std[tag_i])
        bits.append(
            f"The first uptrend upper-band tag is {_clock(prep, tag_i)}, high {float(prep.high[tag_i]):.2f} "
            f"against the band {band:.2f}, with the 9 EMA at {float(prep.ema9[tag_i]):.2f} and the 20 EMA at {float(prep.ema20[tag_i]):.2f}."
        )
    if support is not None and support_i is not None:
        bits.append(
            f"Support is the lowest low after that tag, the {_clock(prep, support_i)} low at {float(support):.2f}."
        )
    i1200 = _bar_at(prep, indexes, "12:00")
    i1205 = _bar_at(prep, indexes, "12:05")
    if i1200 is not None:
        bits.append(
            f"The 12:00 bar closes at {float(prep.close[i1200]):.2f} and its low is {float(prep.low[i1200]):.2f}."
        )
    if i1205 is not None:
        bits.append(f"The 12:05 low is {float(prep.low[i1205]):.2f}.")
    bits.append("Those prints sit near 776.2. The line stays on the pullback low. It is not moved onto 776.2.")
    if not signals:
        bits.append(
            f"No 5-minute close in this file, through {_clock(prep, stop - 1)} ET, is below that support and the 9 EMA "
            "with a three-bar MACD fade off a positive histogram and RSI rolling down from 70. The short is not marked."
        )
    else:
        for item in signals:
            bits.append(
                f"The short signals at {_clock(prep, item.signal_i)}, close {float(prep.close[item.signal_i]):.2f}, "
                f"support {item.support:.2f}, stop {item.stop:.2f}. The fill is the {_clock(prep, item.fill_i)} open "
                f"at {float(prep.open[item.fill_i]):.2f}."
            )
            for target, label in (("ema20", "20 EMA"), ("vwap", "VWAP")):
                path = walk_exhaustion(prep, item, target)
                if path is None:
                    bits.append(f"The {label} book skips it because that level is not beyond the fill.")
                    continue
                when = pd.Timestamp(path["exit_time"]).tz_convert("America/New_York").strftime("%H:%M")
                bits.append(f"The {label} book exits {path['reason']} at {path['exit_spot']:.2f} at {when}.")
    _plot(prep, start, stop, tag_i, support, support_i, signals[0] if signals else None)
    return " ".join(bits)


def _plot(prep, start: int, stop: int, tag_i, support, support_i, signal) -> None:
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
    if support is not None and np.isfinite(support):
        ax.axhline(float(support), color="#f4f4f4", lw=1.0, ls=":", label=f"Support {float(support):.2f}")
    marks = []
    if tag_i is not None:
        marks.append((tag_i, "tag", float(prep.high[tag_i]), "#5dade2"))
    if support_i is not None:
        marks.append((support_i, "shelf", float(prep.low[support_i]), "#f4f4f4"))
    if signal is not None:
        marks.append((signal.signal_i, "short", float(prep.close[signal.signal_i]), "#ff5d5d"))
        marks.append((signal.fill_i, "fill", float(prep.open[signal.fill_i]), "#f5b041"))
    for index, label, price, color in marks:
        offset = index - start
        ax.scatter([offset], [price], color=color, s=28, zorder=4)
        ax.annotate(label, (offset, price), textcoords="offset points", xytext=(0, 8), color=color, fontsize=8, ha="center")
    ticks = list(range(0, stop - start, 6))
    ax.set_xticks(ticks)
    ax.set_xticklabels([prep.index[start + tick].strftime("%H:%M") for tick in ticks], color="#cccccc")
    ax.tick_params(colors="#cccccc")
    for spine in ax.spines.values():
        spine.set_color("#444444")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(color="#2a2a2a")
    title = "SPY 5-minute 2026-10-07. Upper-band tag and the pullback shelf."
    if signal is None:
        title += " No short."
    ax.set_title(title + " Not a forecast.", color="#f4f4f4")
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
    print(f"EXHAUST {name}", flush=True)
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


def _check(rules: dict) -> None:
    if "lowest low" not in rules["support"] or "does not move the anchor" not in rules["tag"]:
        raise SystemExit("exhaustion shelf was not frozen")
    if "more negative" not in rules["macd"] or "at least 70" not in rules["rsi"]:
        raise SystemExit("exhaustion momentum rule was not frozen")
    if "776.2" not in rules["chart_day"] or "left unmarked" not in rules["chart_day"]:
        raise SystemExit("chart rule was not frozen")
    if "20 EMA 0 DTE" not in rules["books"]:
        raise SystemExit("primary book was not named")


def main() -> None:
    rules = frozen_rules()
    _check(rules)
    Path("reports").mkdir(parents=True, exist_ok=True)
    minutes, info = load_minutes("SPY")
    if minutes is None:
        raise SystemExit(f"SPY minutes are not ready {info}")
    five = to_five_minute(minutes)
    iv = _iv()
    print("EXHAUST prepare", flush=True)
    prep = prepare(five)
    items = find_exhaustions(prep, "SPY")
    print(f"EXHAUST signals {len(items)}", flush=True)
    per_month = signals_per_month(
        prep, [item for item in items if prep.dates[item.fill_i] >= HOLDOUT_START], HOLDOUT_START, SAMPLE_END,
    )
    ema_paths = _paths(prep, items, "ema20")
    vwap_paths = _paths(prep, items, "vwap")
    print(f"EXHAUST paths ema20 {len(ema_paths)} vwap {len(vwap_paths)}", flush=True)
    books = []
    for label, paths, want_five in (
        ("ema20", ema_paths, True),
        ("vwap", vwap_paths, False),
    ):
        for kind in ("shares", "0dte"):
            books.append(_score_cell(prep, paths, f"{label}_{kind}", iv, five=want_five and kind == "0dte"))
    by_name = {book["name"]: book for book in books}
    primary = by_name["ema20_0dte"]
    share_primary = by_name["ema20_shares"]
    random_bits = []
    for label, taken, kind, long_only, target in (
        ("ema20_shares", share_primary["hold"].get("trades", 0), "shares", True, "ema20"),
        ("ema20_0dte", primary["hold"].get("trades", 0), "0dte", False, "ema20"),
    ):
        print(f"EXHAUST random {label}", flush=True)
        drawn = random_exhaustions(prep, int(taken or 0), start=HOLDOUT_START, end=SAMPLE_END)
        paths = _paths(prep, drawn, target)
        metrics = _book(prep, paths, kind, 1000.0, long_only, iv, HOLDOUT_START, SAMPLE_END)["metrics"]
        random_bits.append(
            f"{label} random holdout, seed 17, {len(drawn)} entries, {metrics.get('trades', 0)} trades, "
            f"ending {_money(metrics.get('ending_equity'))}, profit factor {_pf(metrics.get('profit_factor'))}, "
            f"Sharpe {_num(metrics.get('sharpe'))}, drawdown {_pct(metrics.get('max_drawdown'))}."
        )
    chart_frame, chart_source = _chart_frame()
    if chart_frame is None:
        chart_note = "Yahoo returned no 5-minute SPY bars for 2026-10-07, so the short was not invented."
    else:
        chart_note = f"{chart_source}. {_day_note(prepare(chart_frame))}"
    rate = "n/a" if per_month is None else f"{per_month:.1f}"
    five = primary["five"] or {}
    english = (
        f"The shelf fires about {rate} times a month on the holdout, both directions. "
        f"Target the 20 EMA, shares finished at {_ending(share_primary['hold'], share_primary['train'])}. "
        f"The same entries as one 0 DTE contract finished at {_ending(primary['hold'], primary['train'])}. "
        f"From $5,000 that 0 DTE book finished at {_money(five.get('ending_equity'))} "
        f"({five.get('trades', 0)} trades, profit factor {_pf(five.get('profit_factor'))}, "
        f"drawdown {_pct(five.get('max_drawdown'))}). "
        "One contract, so the extra cash is idle and that smaller drawdown is the same dollar path. "
        f"The VWAP target, shares, finished at {_ending(by_name['vwap_shares']['hold'], by_name['vwap_shares']['train'])}. "
        f"The VWAP target as one 0 DTE contract finished at {_ending(by_name['vwap_0dte']['hold'], by_name['vwap_0dte']['train'])}. "
        + " ".join(random_bits)
        + " Share books are long only. A target that is not beyond the fill is skipped. "
        "A row that clears the holdout arithmetic is not promoted."
    )
    lines = [
        MARK_START,
        "### Trend-exhaustion shelf",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. The chop-breakout order rules were not changed. "
        "The sandbox forward test was not changed. The shelf was frozen before this score. "
        "After the first bar of the session that tags the upper 2 SD VWAP band while the 9 EMA is above the 20 EMA, "
        "support is the lowest low of the later bars. A later tag does not move that anchor. "
        "The signal is a 5-minute close strictly below that support and strictly below the 9 EMA, with the 9 still above the 20. "
        "The MACD histogram has to shrink for three bars off a positive print. A histogram that is only getting more negative does not count. "
        "RSI has to have printed at least 70 after the tag, and the signal bar has to be rolling down from that print. "
        "The fill is the next open. The stop is one cent above the last confirmed 2-bar swing high. "
        "The 20 EMA and VWAP are separate targets, because one contract cannot scale out of both. "
        "A book skips the trade when that level is not beyond the fill. Flat at the 15:30 open. "
        "The long is the mirror: a lower-band tag in a downtrend, resistance at the highest high after it, "
        "a close above that high and the 9 EMA, MACD rising off a negative print, and RSI rolling up from 30.",
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
        "python3 -m webull_bot.chart_reads.research_exhaustion",
        "```",
        MARK_END,
        "",
    ]
    _write(lines)
    RESULT_PATH.write_text(
        json.dumps({"books": books, "random": random_bits, "chart": chart_note, "per_month": per_month}, indent=2, default=str) + "\n"
    )
    print(chart_note, flush=True)
    print("WROTE reports/exhaustion.json", flush=True)


if __name__ == "__main__":
    main()
