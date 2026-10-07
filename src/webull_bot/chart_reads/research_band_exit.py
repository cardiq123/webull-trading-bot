"""Score the opposite VWAP-band exit on the three frozen studies. Backtests only.

Does not place an order, does not edit the sandbox forward test, and does not
add a strategy to the live list. The percent targets are the comparison.
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
    HOLDOUT_START as RECLAIM_HOLDOUT,
    TRAIN_END as RECLAIM_TRAIN,
    find_setups,
    frozen_rules as reclaim_rules,
    prepare,
    simulate as reclaim_simulate,
)
from webull_bot.chart_reads.ema_reject import (
    HOLDOUT_START as REJECT_HOLDOUT,
    SAMPLE_END as REJECT_END,
    TRAIN_END as REJECT_TRAIN,
    find_signals as reject_signals,
    frozen_rules as reject_rules,
    simulate as reject_simulate,
    to_five_minute,
)
from webull_bot.chart_reads.research_ema_reclaim import _chart_frame
from webull_bot.chart_reads.vwap_band import (
    HOLDOUT_START as VWAP_HOLDOUT,
    SAMPLE_END as VWAP_END,
    TRAIN_END as VWAP_TRAIN,
    find_signals as vwap_signals,
    frozen_rules as vwap_rules,
    passes_gate,
    simulate as vwap_simulate,
)
from webull_bot.chart_reads.vwap_band_data import load_minutes, to_fifteen_minute
from webull_bot.data.base import normalize_frame
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.chart_reads.orb_mwf import prior_iv

MARK_START = "<!-- BAND_EXIT_START -->"
MARK_END = "<!-- BAND_EXIT_END -->"
RESULT_PATH = Path("reports/band_exit.json")
CHART_PATH = Path("reports/band_exit_2026-10-07.png")
CHART_DAY = date(2026, 10, 7)
RECLAIM_VARIANTS = ("strict", "no_crack", "no_pullback")
RECLAIM_MODES = ("band", "band200")


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


def _row(name: str, hold: dict, train: dict | None, five: dict | None) -> str:
    five_bit = _money(five.get("ending_equity")) if five else "n/a"
    train_bit = _money(train.get("ending_equity")) if train else "n/a"
    return (
        f"| {name} | {hold.get('trades', 0)} | {_pct(hold.get('win_rate'))} | "
        f"{_pct(hold.get('breakeven_win_rate'))} | {_pf(hold.get('profit_factor'))} | {_num(hold.get('sharpe'))} | "
        f"{_pct(hold.get('max_drawdown'))} | {_money(hold.get('ending_equity'))} | {five_bit} | {train_bit} | "
        f"{'yes, not promoted' if passes_gate(hold) else 'no'} |"
    )


def _score_reclaim(prep, setups, iv) -> list[dict]:
    grouped = {name: [item for item in setups if item.variant == name] for name in RECLAIM_VARIANTS}
    books = []
    for variant in RECLAIM_VARIANTS:
        for mode in RECLAIM_MODES:
            for kind, long_only in (("shares", True), ("0dte", False)):
                name = f"reclaim_{variant}_{mode}_{kind}"
                print(f"BAND {name}", flush=True)
                hold = reclaim_simulate(
                    prep, grouped[variant], mode=mode, kind=kind, stake=1000.0, long_only=long_only,
                    iv_points=iv, start=RECLAIM_HOLDOUT, end=VWAP_END,
                )
                train = reclaim_simulate(
                    prep, grouped[variant], mode=mode, kind=kind, stake=1000.0, long_only=long_only,
                    iv_points=iv, end=RECLAIM_TRAIN,
                )
                five = None
                if variant in ("strict", "no_crack") and kind == "0dte":
                    five = reclaim_simulate(
                        prep, grouped[variant], mode=mode, kind=kind, stake=5000.0, long_only=long_only,
                        iv_points=iv, start=RECLAIM_HOLDOUT, end=VWAP_END,
                    )
                books.append({"name": name, "hold": hold["metrics"], "train": train["metrics"], "five": None if five is None else five["metrics"]})
    return books


def _score_reject(frame, signals, iv) -> list[dict]:
    books = []
    for variant in ("reversal", "vwap"):
        chosen = [item for item in signals if item.variant == variant]
        for target in ("band", "band200", "prem50", "prem100"):
            for kind, long_only in (("shares", True), ("0dte", False)):
                if target.startswith("prem") and kind == "shares":
                    continue
                name = f"reject_{variant}_{target}_{kind}"
                print(f"BAND {name}", flush=True)
                hold = reject_simulate(
                    frame, chosen, stop="reject", target=target, kind=kind, stake=1000.0, long_only=long_only,
                    iv_points=iv, start=REJECT_HOLDOUT, end=REJECT_END,
                )
                train = reject_simulate(
                    frame, chosen, stop="reject", target=target, kind=kind, stake=1000.0, long_only=long_only,
                    iv_points=iv, end=REJECT_TRAIN,
                )
                five = None
                if variant == "reversal" and target in ("band", "band200") and kind == "0dte":
                    five = reject_simulate(
                        frame, chosen, stop="reject", target=target, kind=kind, stake=5000.0, long_only=long_only,
                        iv_points=iv, start=REJECT_HOLDOUT, end=REJECT_END,
                    )
                books.append({"name": name, "hold": hold["metrics"], "train": train["metrics"], "five": None if five is None else five["metrics"]})
    return books


def _score_vwap(frame, signals, iv) -> list[dict]:
    books = []
    for mode in ("extension", "reversal"):
        chosen = [item for item in signals if item.mode == mode]
        for target in ("band", "band200", "prem50", "prem100"):
            for kind, long_only in (("shares", True), ("0dte", False)):
                if target.startswith("prem") and kind == "shares":
                    continue
                name = f"vwap_{mode}_{target}_{kind}"
                print(f"BAND {name}", flush=True)
                hold = vwap_simulate(
                    frame, chosen, target=target, kind=kind, stake=1000.0, long_only=long_only,
                    iv_points=iv, start=VWAP_HOLDOUT, end=VWAP_END,
                )
                train = vwap_simulate(
                    frame, chosen, target=target, kind=kind, stake=1000.0, long_only=long_only,
                    iv_points=iv, start=None, end=VWAP_TRAIN,
                )
                books.append({"name": name, "hold": hold["metrics"], "train": train["metrics"], "five": None})
    return books


def _prior_prem() -> dict[str, dict]:
    path = Path("reports/ema_reclaim.json")
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    found = {}
    for book in payload.get("books", []):
        name = book["name"]
        if name.startswith(tuple(f"{variant}_prem" for variant in RECLAIM_VARIANTS)) and name.endswith("_0dte"):
            found[name] = book
    return found


def _chart(prep) -> str:
    indexes = [i for i, day in enumerate(prep.dates) if day == CHART_DAY]
    if not indexes:
        return "The Yahoo 5-minute file has no 2026-10-07 session, so the band touch was not invented."
    start, stop = indexes[0], indexes[-1] + 1
    bits = []
    first_tag = None
    for i in range(start, stop):
        clock = prep.index[i].strftime("%H:%M")
        if clock < "11:25" or clock > "12:05":
            continue
        upper = float(prep.vwap[i] + 2.0 * prep.std[i])
        bits.append(
            f"{clock} close {prep.close[i]:.2f} high {prep.high[i]:.2f} upper band {upper:.2f}"
        )
        if first_tag is None and prep.high[i] >= upper and clock >= "11:35":
            first_tag = (clock, upper, float(prep.high[i]))
    last = prep.index[stop - 1].strftime("%H:%M")
    tag = "The high did not reach the upper band in this file."
    if first_tag is not None:
        tag = f"The first high at or through the upper band after 11:35 is {first_tag[0]}, high {first_tag[2]:.2f}, band {first_tag[1]:.2f}."
    _plot(prep, start, stop)
    return (
        f"Yahoo 5-minute SPY on 2026-10-07 runs 09:30 through {last} ET in this file. "
        + " ".join(bits)
        + " "
        + tag
        + " The rule was not moved onto that print."
    )


def _plot(prep, start: int, stop: int) -> None:
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
    ax.plot(x, prep.ema200[start:stop], color="#bb8fce", lw=1.0, label="200 EMA")
    ticks = list(range(0, stop - start, 6))
    ax.set_xticks(ticks)
    ax.set_xticklabels([prep.index[start + tick].strftime("%H:%M") for tick in ticks], color="#cccccc")
    ax.tick_params(colors="#cccccc")
    for spine in ax.spines.values():
        spine.set_color("#444444")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(color="#2a2a2a")
    ax.set_title("SPY 5-minute 2026-10-07. Upper 2 SD band is the long target. Not a forecast.", color="#f4f4f4")
    legend = ax.legend(facecolor="#1e1e1e", edgecolor="#333333", fontsize=8, loc="upper left")
    for text in legend.get_texts():
        text.set_color("#f4f4f4")
    fig.tight_layout()
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, facecolor=fig.get_facecolor())
    plt.close(fig)


def _fresh_chart():
    try:
        import yfinance as yf

        raw = yf.download("SPY", start="2026-10-07", end="2026-10-08", interval="5m", auto_adjust=True, progress=False, threads=False)
        if raw is not None and not raw.empty:
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = [str(column[0]).lower() for column in raw.columns]
            normal = normalize_frame(raw, "5m")
            if not normal.empty and any(stamp.date() == CHART_DAY for stamp in normal.index):
                # The session band needs the day. EMAs need earlier bars, so fall through if this file is one day.
                longer, source = _chart_frame()
                if longer is not None:
                    return longer, source
                return normal, "Yahoo 5-minute download"
    except Exception:
        pass
    return _chart_frame()


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


def _english(books: list[dict], prior: dict[str, dict]) -> str:
    def ending(name: str) -> str:
        row = next((item for item in books if item["name"] == name), None)
        if row is None:
            return "n/a"
        hold = row["hold"]
        return (
            f"{_money(hold.get('ending_equity'))} ({hold.get('trades', 0)} trades, "
            f"profit factor {_pf(hold.get('profit_factor'))}, drawdown {_pct(hold.get('max_drawdown'))}, "
            f"train {_money(row['train'].get('ending_equity'))})"
        )

    def old(name: str) -> str:
        row = prior.get(name)
        if row is None:
            return "n/a"
        hold = row["hold"]
        train = row.get("train") or {}
        return f"{_money(hold.get('ending_equity'))} (train {_money(train.get('ending_equity'))})"

    return (
        "On the five-step reclaim, dropping the crack is the 2026-10-07 tape. "
        f"Its opposite-band 0 DTE book finished at {ending('reclaim_no_crack_band_0dte')}. "
        f"Half at the first of the band and the 200 EMA finished at {ending('reclaim_no_crack_band200_0dte')}. "
        f"The same entries at +50% of premium finished at {old('no_crack_prem50_0dte')} and at +100% finished at {old('no_crack_prem100_0dte')}. "
        f"The strict band 0 DTE book finished at {ending('reclaim_strict_band_0dte')}. "
        f"The strict +50% book finished at {old('strict_prem50_0dte')} and the +100% book at {old('strict_prem100_0dte')}. "
        "Share books are in the table. A row that clears the holdout arithmetic is not promoted."
    )


def main() -> None:
    written = {
        "reclaim": reclaim_rules(),
        "reject": reject_rules(),
        "vwap": vwap_rules(),
    }
    if "beyond the fill" not in written["reclaim"]["band"]:
        raise SystemExit("reclaim band rule was not frozen")
    if "opposite 2 SD" not in written["reject"]["targets"]["band"]:
        raise SystemExit("reject band rule was not frozen")
    if "15-minute 200 EMA" not in written["vwap"]["band200"]:
        raise SystemExit("vwap band rule was not frozen")
    Path("reports").mkdir(parents=True, exist_ok=True)
    minutes, info = load_minutes("SPY")
    if minutes is None:
        raise SystemExit(f"SPY minutes are not ready {info}")
    five = to_five_minute(minutes)
    fifteen = to_fifteen_minute(minutes)
    iv = _iv()
    print("BAND prepare reclaim", flush=True)
    prep = prepare(five)
    setups = find_setups(prep, "SPY")
    books = _score_reclaim(prep, setups, iv)
    print("BAND reject signals", flush=True)
    books.extend(_score_reject(five, reject_signals(five, "SPY"), iv))
    print("BAND vwap signals", flush=True)
    books.extend(_score_vwap(fifteen, vwap_signals(fifteen, "SPY", 2.0), iv))
    chart_frame, chart_source = _fresh_chart()
    if chart_frame is None:
        chart_note = "Yahoo returned no 5-minute SPY bars for 2026-10-07, so the band touch was not invented."
    else:
        chart_note = f"{chart_source}. {_chart(prepare(chart_frame))}"
    prior = _prior_prem()
    lines = [
        MARK_START,
        "### Opposite VWAP band exit",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. The chop-breakout order rules were not changed. "
        "The exit was frozen before this score. A long takes the upper 2 standard deviation session VWAP band. A short takes the lower band. "
        "The band has to be beyond the fill. Alone, the whole position exits there. Combined with the 200 EMA, shares sell half at the first of the two "
        "and the rest at the other or on a close back across the 9 EMA. The original stop is not moved. One 0 DTE contract sells at the first tag. "
        "The +50% and +100% premium targets are the comparison, not a new gate. This exit does not replace the VWAP-confluence rejection gate. "
        "On the 15-minute VWAP study the 9 and the 200 are 15-minute EMAs. On the 5-minute studies they are 5-minute EMAs.",
        "",
        "| Book | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 | Train $1,000 | Clears |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for book in books:
        lines.append(_row(book["name"], book["hold"], book["train"], book["five"]))
    lines += [
        "",
        _english(books, prior),
        "",
        chart_note,
        "",
        "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.",
        "",
        "```",
        "python3 -m webull_bot.chart_reads.research_band_exit",
        "```",
        MARK_END,
        "",
    ]
    _write(lines)
    RESULT_PATH.write_text(json.dumps({"books": books, "chart": chart_note}, indent=2, default=str) + "\n")
    print(chart_note, flush=True)
    print("WROTE reports/band_exit.json", flush=True)


if __name__ == "__main__":
    main()
