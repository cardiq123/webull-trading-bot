"""Score the trendline and support bounce. Backtests only.

Does not place an order, does not edit the sandbox forward test, and does not
add a strategy to the live list. The rule in trendline_bounce.frozen_rules is the one scored.
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
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.reentry import signals_per_month, simulate_paths
from webull_bot.chart_reads.trendline_bounce import find_bounces, frozen_rules, random_bounces, walk_bounce
from webull_bot.chart_reads.vwap_band import passes_gate
from webull_bot.chart_reads.vwap_band_data import load_minutes
from webull_bot.data.yfinance_provider import YFinanceProvider

MARK_START = "<!-- TRENDLINE_BOUNCE_START -->"
MARK_END = "<!-- TRENDLINE_BOUNCE_END -->"
RESULT_PATH = Path("reports/trendline_bounce.json")
CHART_PATH = Path("reports/trendline_bounce_2026-10-07.png")
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
        path = walk_bounce(prep, item, target)
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


def _line_at(item, t: int) -> float:
    return item.y1 + (item.y2 - item.y1) / (item.anchor2 - item.anchor1) * (t - item.anchor1)


def _chart_frame() -> tuple[pd.DataFrame | None, str]:
    """The local 5-minute file with the later 2026-10-07 bar. No fresh download."""
    best = None
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
        return None, "Yahoo returned no 5-minute SPY bars"
    return best


def _day_note(prep) -> str:
    indexes = [i for i, day in enumerate(prep.dates) if day == CHART_DAY]
    if not indexes:
        return "The Yahoo 5-minute file has no 2026-10-07 session, so the bounce was not invented."
    start, stop = indexes[0], indexes[-1] + 1
    longs = [
        item
        for item in find_bounces(prep, "SPY")
        if item.direction == "long" and prep.dates[item.signal_i] == CHART_DAY
    ]
    confluence = [item for item in longs if item.variant == "confluence"]
    bits = [f"Yahoo 5-minute SPY on 2026-10-07 runs 09:30 through {_clock(prep, stop - 1)} ET in this file."]
    for clock in ("10:50", "12:00", "12:05", "12:40", "13:00", "13:05"):
        i = _bar_at(prep, indexes, clock)
        if i is None:
            continue
        bits.append(
            f"{clock} O {float(prep.open[i]):.2f} H {float(prep.high[i]):.2f} L {float(prep.low[i]):.2f} "
            f"C {float(prep.close[i]):.2f} ema9 {float(prep.ema9[i]):.2f} ema20 {float(prep.ema20[i]):.2f} "
            f"band {float(prep.vwap[i]) + 2.0 * float(prep.std[i]):.2f}."
        )
    bits.append(
        "The 12:00 close and the 12:05 low sit near 776.2. The 12:00 low is the wick under that print. "
        "The rule does not move the shelf onto 776.2."
    )
    signal = confluence[0] if confluence else None
    if signal is None:
        bits.append(
            f"No long confluence bounce prints through {_clock(prep, stop - 1)} ET. The hold is left unmarked."
        )
    else:
        line = _line_at(signal, signal.signal_i)
        bits.append(
            f"The first long confluence is {_clock(prep, signal.signal_i)}. "
            f"The line runs from the {_clock(prep, signal.anchor1)} low at {signal.y1:.2f} "
            f"to the {_clock(prep, signal.anchor2)} low at {signal.y2:.2f}, and it is {line:.2f} on the signal bar. "
            f"Horizontal support is that last swing, {signal.shelf:.2f}. "
            f"The low is {float(prep.low[signal.signal_i]):.2f} and the close is {float(prep.close[signal.signal_i]):.2f}. "
            f"The fill is the {_clock(prep, signal.fill_i)} open at {float(prep.open[signal.fill_i]):.2f}."
        )
        if _clock(prep, signal.anchor1) != "10:50":
            bits.append(
                "The 10:50 low is earlier in the higher-low sequence. The active segment is the latest rising pair, not a line forced through 10:50."
            )
        for target, label in (("band", "upper band"), ("ema200", "200 EMA")):
            path = walk_bounce(prep, signal, target)
            if path is None:
                bits.append(f"The {label} book skips it because that level is not beyond the fill.")
                continue
            when = pd.Timestamp(path["exit_time"]).tz_convert("America/New_York").strftime("%H:%M")
            bits.append(f"The {label} book exits {path['reason']} at {path['exit_spot']:.2f} at {when}.")
        if len(confluence) > 1:
            later = ", ".join(_clock(prep, item.signal_i) for item in confluence[1:])
            bits.append(f"Later confluence signals this session: {later}.")
    for variant, label in (("support", "Support alone"), ("trendline", "The trendline alone")):
        first = next((item for item in longs if item.variant == variant), None)
        if first is None:
            bits.append(f"{label} does not fire in this file.")
        else:
            bits.append(f"{label} first fires at {_clock(prep, first.signal_i)}.")
    _plot(prep, start, stop, signal)
    return " ".join(bits)


def _plot(prep, start: int, stop: int, signal) -> None:
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
    ax.plot(x, prep.ema9[start:stop], color="#f7dc6f", lw=1.1, label="9 EMA")
    ax.plot(x, prep.ema20[start:stop], color="#f5b041", lw=1.0, label="20 EMA")
    ax.plot(x, prep.ema200[start:stop], color="#bb8fce", lw=1.0, label="200 EMA")
    if signal is not None:
        xs = np.arange(signal.anchor1 - start, stop - start)
        ys = [_line_at(signal, start + int(offset)) for offset in xs]
        ax.plot(xs, ys, color="#f4f4f4", lw=1.2, label="Trendline")
        ax.axhline(float(signal.shelf), color="#f4f4f4", lw=0.8, ls=":", label=f"Support {float(signal.shelf):.2f}")
        for index, label, price, color in (
            (signal.anchor1, "low", float(prep.low[signal.anchor1]), "#f4f4f4"),
            (signal.anchor2, "low", float(prep.low[signal.anchor2]), "#f4f4f4"),
            (signal.signal_i, "hold", float(prep.low[signal.signal_i]), "#3dd68c"),
            (signal.fill_i, "fill", float(prep.open[signal.fill_i]), "#f5b041"),
        ):
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
    title = "SPY 5-minute 2026-10-07. Rising line and the last swing low."
    if signal is None:
        title += " No confluence."
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
    print(f"BOUNCE {name}", flush=True)
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
    if "0.10 ATR" not in rules["tag"] or "Two higher-low touches" not in rules["trendline"]:
        raise SystemExit("bounce rule was not frozen")
    if "776.2" not in rules["chart_day"] or "10:50" not in rules["chart_day"]:
        raise SystemExit("chart rule was not frozen")
    if "confluence band 0 DTE" not in rules["compare"]:
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
    print("BOUNCE prepare", flush=True)
    prep = prepare(five)
    items = find_bounces(prep, "SPY")
    print(f"BOUNCE signals {len(items)}", flush=True)
    grouped = {}
    for variant in ("confluence", "trendline", "support"):
        chosen = [item for item in items if item.variant == variant]
        grouped[variant] = {
            "band": _paths(prep, chosen, "band"),
            "ema200": _paths(prep, chosen, "ema200"),
        }
        print(
            f"BOUNCE {variant} signals {len(chosen)} band {len(grouped[variant]['band'])} ema200 {len(grouped[variant]['ema200'])}",
            flush=True,
        )
    per_month = signals_per_month(
        prep,
        [item for item in items if item.variant == "confluence" and prep.dates[item.fill_i] >= HOLDOUT_START],
        HOLDOUT_START,
        SAMPLE_END,
    )
    books = []
    for variant in ("confluence", "trendline", "support"):
        for target in ("band", "ema200"):
            for kind in ("shares", "0dte"):
                five_book = variant == "confluence" and target == "band" and kind == "0dte"
                books.append(
                    _score_cell(
                        prep,
                        grouped[variant][target],
                        f"{variant}_{target}_{kind}",
                        iv,
                        five=five_book,
                    )
                )
    by_name = {book["name"]: book for book in books}
    primary = by_name["confluence_band_0dte"]
    share_primary = by_name["confluence_band_shares"]
    random_bits = []
    for label, taken, kind, long_only in (
        ("confluence_band_shares", share_primary["hold"].get("trades", 0), "shares", True),
        ("confluence_band_0dte", primary["hold"].get("trades", 0), "0dte", False),
    ):
        print(f"BOUNCE random {label}", flush=True)
        drawn = random_bounces(prep, int(taken or 0), start=HOLDOUT_START, end=SAMPLE_END)
        paths = _paths(prep, drawn, "band")
        metrics = _book(prep, paths, kind, 1000.0, long_only, iv, HOLDOUT_START, SAMPLE_END)["metrics"]
        random_bits.append(
            f"{label} random holdout, seed 17, {len(drawn)} entries, {metrics.get('trades', 0)} trades, "
            f"ending {_money(metrics.get('ending_equity'))}, profit factor {_pf(metrics.get('profit_factor'))}, "
            f"Sharpe {_num(metrics.get('sharpe'))}, drawdown {_pct(metrics.get('max_drawdown'))}."
        )
    chart_frame, chart_source = _chart_frame()
    if chart_frame is None:
        chart_note = "Yahoo returned no 5-minute SPY bars for 2026-10-07, so the bounce was not invented."
    else:
        chart_note = f"{chart_source}. {_day_note(prepare(chart_frame))}"
    rate = "n/a" if per_month is None else f"{per_month:.1f}"
    five = primary["five"] or {}
    english = (
        f"Confluence signals about {rate} times a month on the holdout, both directions. "
        f"Target the upper band, shares finished at {_ending(share_primary['hold'], share_primary['train'])}. "
        f"The same entries as one 0 DTE contract finished at {_ending(primary['hold'], primary['train'])}. "
        f"From $5,000 that 0 DTE book finished at {_money(five.get('ending_equity'))} "
        f"({five.get('trades', 0)} trades, profit factor {_pf(five.get('profit_factor'))}, "
        f"drawdown {_pct(five.get('max_drawdown'))}). "
        "One contract, so the extra cash is idle and that smaller drawdown is the same dollar path. "
        f"The confluence 200 EMA target finished at {_ending(by_name['confluence_ema200_0dte']['hold'], by_name['confluence_ema200_0dte']['train'])}. "
        f"The trendline alone, upper band, 0 DTE finished at {_ending(by_name['trendline_band_0dte']['hold'], by_name['trendline_band_0dte']['train'])}. "
        f"Support alone, upper band, 0 DTE finished at {_ending(by_name['support_band_0dte']['hold'], by_name['support_band_0dte']['train'])}. "
        + (
            "That row clears the holdout gate. "
            if passes_gate(by_name["support_band_0dte"]["hold"])
            else "That row misses the holdout gate. "
        )
        + "It stays off the live list. "
        f"The trendline alone with the 200 EMA finished at {_ending(by_name['trendline_ema200_0dte']['hold'], by_name['trendline_ema200_0dte']['train'])}. "
        f"Support alone with the 200 EMA finished at {_ending(by_name['support_ema200_0dte']['hold'], by_name['support_ema200_0dte']['train'])}. "
        + " ".join(random_bits)
        + " Share books are long only. A target that is not beyond the fill is skipped. "
        "A row that clears the holdout arithmetic is not promoted."
    )
    lines = [
        MARK_START,
        "### Trendline and support bounce",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. The chop-breakout order rules were not changed. "
        "The sandbox forward test was not changed. The bounce was frozen before this score. "
        "In an uptrend, the 9 EMA above the 20, a rising line joins the latest confirmed 2-bar pivot low to the latest earlier pivot low that is strictly lower. "
        "Two higher-low touches draw the line. A close below the segment invalidates that pair. "
        "Horizontal support is the latest confirmed swing low, not the deepest wick and not a round number. "
        "Confluence is a green bar whose low tags both levels within 0.10 ATR and whose close finishes back above both. "
        "Support alone and the trendline alone drop the other level. The fill is the next open. "
        "The stop is a close back through the level. Confluence uses the lower of the extended line and the swing for a long. "
        "The upper 2 SD band and the 200 EMA are separate targets. "
        "The short is the mirror: a falling line through lower highs, a red close back under the line and the last swing high.",
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
        "python3 -m webull_bot.chart_reads.research_trendline_bounce",
        "```",
        MARK_END,
        "",
    ]
    _write(lines)
    RESULT_PATH.write_text(
        json.dumps(
            {"books": books, "random": random_bits, "chart": chart_note, "per_month": per_month},
            indent=2,
            default=str,
        )
        + "\n"
    )
    print(chart_note, flush=True)
    print("WROTE reports/trendline_bounce.json", flush=True)


if __name__ == "__main__":
    main()
