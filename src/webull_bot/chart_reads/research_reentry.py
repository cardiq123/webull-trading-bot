"""Score the band-tag re-entry. Backtests only.

Does not place an order, does not edit the sandbox forward test, and does not
add a strategy to the live list. The rule in reentry.frozen_rules is the one scored.
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

from webull_bot.chart_reads.ema_reclaim import (
    HOLDOUT_START,
    TRAIN_END,
    find_setups,
    prepare,
)
from webull_bot.chart_reads.ema_reject import SAMPLE_END, find_signals as reject_signals
from webull_bot.chart_reads.reentry import (
    addons,
    base_band_keys,
    campaign_paths,
    find_reentries,
    frozen_rules,
    illustrate,
    random_reentries,
    reversal_paths,
    signals_per_month,
    simulate,
    simulate_paths,
    walk_reentry,
)
from webull_bot.chart_reads.research_ema_reclaim import _chart_frame
from webull_bot.chart_reads.vwap_band import passes_gate
from webull_bot.chart_reads.vwap_band_data import load_minutes, to_five_minute
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.chart_reads.orb_mwf import prior_iv

MARK_START = "<!-- REENTRY_START -->"
MARK_END = "<!-- REENTRY_END -->"
RESULT_PATH = Path("reports/reentry.json")
CHART_PATH = Path("reports/reentry_2026-10-07.png")
CHART_DAY = date(2026, 10, 7)
TOUCH = 0.10


def _money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    number = float(value)
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


def _pack(name: str, hold: dict, train: dict, five: dict | None, per_month) -> dict:
    return {
        "name": name,
        "hold": hold["metrics"],
        "train": train["metrics"],
        "five": None if five is None else five["metrics"],
        "per_month": per_month,
    }


def _row(book: dict) -> str:
    hold = book["hold"]
    train = book["train"]
    five = book.get("five")
    five_bit = _money(five.get("ending_equity")) if five else "n/a"
    return (
        f"| {book['name']} | {hold.get('trades', 0)} | {_pct(hold.get('win_rate'))} | "
        f"{_pct(hold.get('breakeven_win_rate'))} | {_pf(hold.get('profit_factor'))} | {_num(hold.get('sharpe'))} | "
        f"{_pct(hold.get('max_drawdown'))} | {_money(hold.get('ending_equity'))} | {five_bit} | "
        f"{_money(train.get('ending_equity'))} | {'yes, not promoted' if passes_gate(hold) else 'no'} |"
    )


def _ending(books: list[dict], name: str) -> str:
    row = next((item for item in books if item["name"] == name), None)
    if row is None:
        return "n/a"
    hold = row["hold"]
    return (
        f"{_money(hold.get('ending_equity'))} ({hold.get('trades', 0)} trades, "
        f"win {_pct(hold.get('win_rate'))} against break-even {_pct(hold.get('breakeven_win_rate'))}, "
        f"profit factor {_pf(hold.get('profit_factor'))}, Sharpe {_num(hold.get('sharpe'))}, "
        f"drawdown {_pct(hold.get('max_drawdown'))}, train {_money(row['train'].get('ending_equity'))})"
    )


def _five(books: list[dict], name: str) -> str:
    row = next((item for item in books if item["name"] == name), None)
    if row is None or not row.get("five"):
        return "n/a"
    metrics = row["five"]
    return (
        f"{_money(metrics.get('ending_equity'))} ({metrics.get('trades', 0)} trades, "
        f"profit factor {_pf(metrics.get('profit_factor'))}, drawdown {_pct(metrics.get('max_drawdown'))})"
    )


def _english(books: list[dict], random_bits: list[str], per_month) -> str:
    rate = "n/a" if per_month is None else f"{per_month:.1f}"
    return (
        f"The green hold fires about {rate} times a month on the holdout. "
        f"Standalone, green, 20 EMA stop, upper band again, shares finished at {_ending(books, 'green_ema20_band_shares')}. "
        f"The same cell as one 0 DTE contract finished at {_ending(books, 'green_ema20_band_0dte')}. "
        f"From $5,000 that 0 DTE book finished at {_five(books, 'green_ema20_band_0dte')}. "
        f"The VWAP close stop, same band target, finished at {_ending(books, 'green_vwap_band_0dte')}. "
        f"The 200 EMA target, 20 EMA stop, finished at {_ending(books, 'green_ema20_ema200_0dte')}. "
        f"The looser hold, any candle color, finished at {_ending(books, 'hold_ema20_band_0dte')}. "
        f"As an add-on to the strict reclaim's band exit, the green re-entry finished at {_ending(books, 'addon_strict_0dte')}. "
        f"On the drop-the-crack tape it finished at {_ending(books, 'addon_no_crack_0dte')}. "
        f"On the simpler reversal it finished at {_ending(books, 'addon_reversal_0dte')}. "
        f"The drop-the-crack campaign, base band exit alone, finished at {_ending(books, 'campaign_no_crack_base_0dte')}. "
        f"Base plus the linked re-entry finished at {_ending(books, 'campaign_no_crack_both_0dte')}. "
        f"The simpler reversal campaign, base alone, finished at {_ending(books, 'campaign_reversal_base_0dte')}. "
        f"Base plus the re-entry finished at {_ending(books, 'campaign_reversal_both_0dte')}. "
        + (" ".join(random_bits) + " " if random_bits else "")
        + "Share books are long only. A row that clears the holdout arithmetic is not promoted."
    )


def _clock(prep, i: int) -> str:
    return prep.index[i].strftime("%H:%M")


def _day_note(prep, items: list) -> str:
    indexes = [i for i, day in enumerate(prep.dates) if day == CHART_DAY]
    if not indexes:
        return "The Yahoo 5-minute file has no 2026-10-07 session, so the re-entry was not invented."
    start, stop = indexes[0], indexes[-1] + 1
    last = _clock(prep, stop - 1)
    picture = illustrate(prep, CHART_DAY)
    steps = picture.get("steps") or []
    chosen = next((step for step in steps if _clock(prep, step["tag"]) >= "11:35"), None)
    if chosen is None and steps:
        chosen = steps[0]
    bits = []
    for i in range(start, stop):
        clock = _clock(prep, i)
        if clock < "11:35" or clock > "13:05":
            continue
        upper = float(prep.vwap[i] + 2.0 * prep.std[i])
        color = "G" if prep.close[i] > prep.open[i] else "R" if prep.close[i] < prep.open[i] else "D"
        bits.append(
            f"{clock} {color} high {prep.high[i]:.2f} low {prep.low[i]:.2f} close {prep.close[i]:.2f} "
            f"ema20 {prep.ema20[i]:.2f} upper {upper:.2f}"
        )
    tag_i = None if chosen is None else chosen["tag"]
    reject_i = None if chosen is None else chosen["reject"]
    hold_i = None if chosen is None else chosen["hold"]
    if tag_i is None:
        tag_i = picture.get("pending_tag")
        reject_i = picture.get("pending_reject")
    tag = "No long bar trades the upper band after the open has a positive standard deviation."
    if tag_i is not None:
        upper = float(prep.vwap[tag_i] + 2.0 * prep.std[tag_i])
        tag = f"The long tag is {_clock(prep, tag_i)}, high {prep.high[tag_i]:.2f}, band {upper:.2f}."
    reject = "No red rejection closes back under that band."
    if reject_i is not None:
        upper = float(prep.vwap[reject_i] + 2.0 * prep.std[reject_i])
        reject = (
            f"The red rejection is {_clock(prep, reject_i)}, high {prep.high[reject_i]:.2f}, "
            f"close {prep.close[reject_i]:.2f}, band {upper:.2f}."
        )
    approach = "There is no bar after that rejection in this file."
    if reject_i is not None and hold_i is None:
        nearest = None
        for i in range(reject_i + 1, stop):
            width = float(prep.atr[i])
            ema20 = float(prep.ema20[i])
            if not np.isfinite(width) or width <= 0 or not np.isfinite(ema20):
                continue
            gap = float(prep.low[i]) - ema20
            room = TOUCH * width
            if nearest is None or gap < nearest[0]:
                nearest = (gap, i, room)
        if nearest is None:
            approach = "No later bar has a finite 20 EMA."
        else:
            gap, i, room = nearest
            approach = (
                f"The closest later low is {_clock(prep, i)}, low {prep.low[i]:.2f} against the 20 EMA {prep.ema20[i]:.2f}, "
                f"gap {gap:.2f}, against a 0.10 ATR touch of {room:.2f}."
            )
    elif hold_i is not None:
        room = TOUCH * float(prep.atr[hold_i])
        gap = float(prep.low[hold_i]) - float(prep.ema20[hold_i])
        approach = (
            f"The hold is {_clock(prep, hold_i)}, low {prep.low[hold_i]:.2f} against the 20 EMA {prep.ema20[hold_i]:.2f}, "
            f"gap {gap:.2f}, inside a 0.10 ATR touch of {room:.2f}, close {prep.close[hold_i]:.2f}."
        )
    early = "The 11:40 20 EMA is not in this window."
    for i in range(start, stop):
        if _clock(prep, i) == "11:40":
            early = f"The 11:40 20 EMA is {prep.ema20[i]:.2f}. That print is before the rejection."
            break
    fills = [item for item in items if prep.dates[item.fill_i] == CHART_DAY and item.direction == "long" and item.variant == "green"]
    if hold_i is None:
        held = "The 20 EMA test is missing. The rule was not widened, and this sequence does not fill."
    else:
        fill_i = chosen["fill"]
        held = f"The fill is the {_clock(prep, fill_i)} open at {prep.open[fill_i]:.2f}."
    if fills:
        held += " Green long fills this session: " + ", ".join(_clock(prep, item.fill_i) for item in fills) + "."
    others = [
        item for item in items
        if prep.dates[item.fill_i] == CHART_DAY and not (item.direction == "long" and item.variant == "green")
    ]
    if others:
        held += " Other fills, same session: " + ", ".join(
            f"{item.variant} {item.direction} {_clock(prep, item.fill_i)}" for item in others
        ) + "."
    _plot(prep, start, stop, tag_i, reject_i, hold_i)
    return (
        f"Yahoo 5-minute SPY on 2026-10-07 runs 09:30 through {last} ET in this file. "
        + " ".join(bits)
        + " "
        + tag
        + " "
        + reject
        + " "
        + early
        + " "
        + approach
        + " "
        + held
    )


def _plot(prep, start: int, stop: int, tag_i, reject_i, hold_i) -> None:
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
    ax.plot(x, prep.vwap[start:stop], color="#5dade2", lw=1.1, label="VWAP")
    ax.plot(x, upper, color="#5dade2", lw=1.0, ls="--", label="Upper 2 SD")
    ax.plot(x, prep.ema9[start:stop], color="#f7dc6f", lw=1.0, label="9 EMA")
    ax.plot(x, prep.ema20[start:stop], color="#f5b041", lw=1.1, label="20 EMA")
    ax.plot(x, prep.ema200[start:stop], color="#bb8fce", lw=1.0, label="200 EMA")
    marks = ((tag_i, "tag", "#f4f4f4"), (reject_i, "reject", "#ff5d5d"), (hold_i, "hold", "#3dd68c"))
    for index, label, color in marks:
        if index is None:
            continue
        offset = index - start
        ax.scatter([offset], [prep.high[index]], color=color, s=28, zorder=4)
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
    title = "SPY 5-minute 2026-10-07. Band tag, then the red rejection."
    title += " No 20 EMA hold." if hold_i is None else " Hold marked."
    ax.set_title(title + " Not a forecast.", color="#f4f4f4")
    legend = ax.legend(facecolor="#1e1e1e", edgecolor="#333333", fontsize=8, loc="upper left")
    for text in legend.get_texts():
        text.set_color("#f4f4f4")
    fig.tight_layout()
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, facecolor=fig.get_facecolor())
    plt.close(fig)


def _score_cell(prep, paths, name: str, iv, *, five: bool, per_month) -> dict:
    print(f"REENTRY {name}", flush=True)
    hold = _book(prep, paths, "0dte" if name.endswith("0dte") else "shares", 1000.0, name.endswith("shares"), iv, HOLDOUT_START, SAMPLE_END)
    train = _book(prep, paths, "0dte" if name.endswith("0dte") else "shares", 1000.0, name.endswith("shares"), iv, None, TRAIN_END)
    five_book = None
    if five:
        five_book = _book(prep, paths, "0dte", 5000.0, False, iv, HOLDOUT_START, SAMPLE_END)
    return _pack(name, hold, train, five_book, per_month)


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


def main() -> None:
    rules = frozen_rules()
    if "0.10 ATR" not in rules["pullback"] or "does not need a position" not in rules["standalone"]:
        raise SystemExit("re-entry rule was not frozen")
    if "missing 20 EMA test is left missing" not in rules["chart_day"]:
        raise SystemExit("chart rule was not frozen")
    Path("reports").mkdir(parents=True, exist_ok=True)
    minutes, info = load_minutes("SPY")
    if minutes is None:
        raise SystemExit(f"SPY minutes are not ready {info}")
    five = to_five_minute(minutes)
    iv = _iv()
    print("REENTRY prepare", flush=True)
    prep = prepare(five)
    items = find_reentries(prep, "SPY")
    green = [item for item in items if item.variant == "green"]
    hold_items = [item for item in items if item.variant == "hold"]
    print(f"REENTRY signals green {len(green)} hold {len(hold_items)}", flush=True)
    per_month = signals_per_month(prep, [item for item in green if prep.dates[item.fill_i] >= HOLDOUT_START], HOLDOUT_START, SAMPLE_END)
    green_band = _paths(prep, green, "band", "ema20")
    green_vwap = _paths(prep, green, "band", "vwap")
    green_200 = _paths(prep, green, "ema200", "ema20")
    hold_band = _paths(prep, hold_items, "band", "ema20")
    books = []
    for label, paths, want_five in (
        ("green_ema20_band", green_band, True),
        ("green_vwap_band", green_vwap, False),
        ("green_ema20_ema200", green_200, False),
        ("hold_ema20_band", hold_band, False),
    ):
        for kind in ("shares", "0dte"):
            books.append(_score_cell(prep, paths, f"{label}_{kind}", iv, five=want_five and kind == "0dte", per_month=per_month if label == "green_ema20_band" else None))
    print("REENTRY base keys", flush=True)
    setups = find_setups(prep, "SPY")
    reversal = [item for item in reject_signals(five, "SPY") if item.variant == "reversal"]
    grouped = {
        "strict": [item for item in setups if item.variant == "strict"],
        "no_crack": [item for item in setups if item.variant == "no_crack"],
    }
    key_sets = {
        "strict": base_band_keys(prep, grouped["strict"]),
        "no_crack": base_band_keys(prep, grouped["no_crack"]),
        "reversal": base_band_keys(prep, [], reversal),
    }
    green_only = [item for item in green if item.direction in ("long", "short")]
    for name, keys in key_sets.items():
        linked = addons(prep, green_only, keys)
        print(f"REENTRY addon {name} {len(linked)}", flush=True)
        linked_paths = _paths(prep, linked, "band", "ema20")
        for kind in ("shares", "0dte"):
            books.append(_score_cell(prep, linked_paths, f"addon_{name}_{kind}", iv, five=False, per_month=None))
        if name == "strict":
            continue
        if name == "reversal":
            base_paths = reversal_paths(prep, reversal)
        else:
            base_paths, _both = campaign_paths(prep, grouped[name], [], "band", "ema20")
        both = base_paths + linked_paths
        for kind in ("shares", "0dte"):
            books.append(_score_cell(prep, base_paths, f"campaign_{name}_base_{kind}", iv, five=False, per_month=None))
            books.append(_score_cell(prep, both, f"campaign_{name}_both_{kind}", iv, five=False, per_month=None))
    primary = next(item for item in books if item["name"] == "green_ema20_band_0dte")
    share_primary = next(item for item in books if item["name"] == "green_ema20_band_shares")
    random_bits = []
    for label, taken, kind, long_only in (
        ("green_ema20_band_shares", share_primary["hold"].get("trades", 0), "shares", True),
        ("green_ema20_band_0dte", primary["hold"].get("trades", 0), "0dte", False),
    ):
        print(f"REENTRY random {label}", flush=True)
        drawn = random_reentries(prep, int(taken or 0), start=HOLDOUT_START, end=SAMPLE_END)
        random_book = simulate(
            prep, drawn, target="band", stop_name="ema20", kind=kind, stake=1000.0, long_only=long_only,
            iv_points=iv, start=HOLDOUT_START, end=SAMPLE_END,
        )
        metrics = random_book["metrics"]
        random_bits.append(
            f"{label} random holdout, seed 17, {metrics.get('trades', 0)} trades, "
            f"ending {_money(metrics.get('ending_equity'))}, profit factor {_pf(metrics.get('profit_factor'))}, "
            f"Sharpe {_num(metrics.get('sharpe'))}, drawdown {_pct(metrics.get('max_drawdown'))}."
        )
    chart_frame, chart_source = _chart_frame()
    if chart_frame is None:
        chart_note = "Yahoo returned no 5-minute SPY bars for 2026-10-07, so the re-entry was not invented."
    else:
        chart_prep = prepare(chart_frame)
        chart_items = find_reentries(chart_prep, "SPY")
        chart_note = f"{chart_source}. {_day_note(chart_prep, chart_items)}"
    lines = [
        MARK_START,
        "### Band-tag re-entry",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. The chop-breakout order rules were not changed. "
        "The re-entry was frozen before this score. After a bar trades the opposite 2 SD session VWAP band, a rejection candle closes back through that band: "
        "red and back under the upper band for a long, green and back above the lower band for a short. A later bar tests the 20 EMA within 0.10 ATR and closes back "
        "on the near side. The primary also requires the trade color, green for a long and red for a short. A hold of any color is the looser book. "
        "The fill is the next open. One position at a time. The stop is a close back through the 20 EMA, or through VWAP, scored separately. "
        "A gap through that level at the open fills at the open. The target is the opposite band again, or the 200 EMA when it is beyond the fill, scored separately. "
        "A target tag during the bar fills before the close stop. Flat at the 15:30 open. "
        "The standalone book does not need a position already open. The add-on keeps a re-entry only when that band tag is the bar where a base reversal exited at the band. "
        "The campaign account takes the base band exit and then the linked re-entry. Shares are long only, 1% of equity to the stop on the fill bar. "
        "Options are one at-the-money 0 DTE contract, calls and puts.",
        "",
        "| Book | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 | Train $1,000 | Clears |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for book in books:
        lines.append(_row(book))
    lines += [
        "",
        _english(books, random_bits, per_month),
        "",
        chart_note,
        "",
        "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.",
        "",
        "```",
        "python3 -m webull_bot.chart_reads.research_reentry",
        "```",
        MARK_END,
        "",
    ]
    _write(lines)
    RESULT_PATH.write_text(json.dumps({"books": books, "random": random_bits, "chart": chart_note, "per_month": per_month}, indent=2, default=str) + "\n")
    print(chart_note, flush=True)
    print("WROTE reports/reentry.json", flush=True)


if __name__ == "__main__":
    main()
