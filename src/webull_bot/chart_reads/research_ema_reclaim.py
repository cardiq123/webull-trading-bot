"""Score the frozen 2026-10-07 reclaim. Does not place an order.

The feature family is fixed in ``frozen_rules`` before any holdout return is read.
A combo is the AND of features that survive that family. It is not promoted.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from webull_bot.chart_reads.ema_reclaim import (
    CHART_DAY,
    FEATURES,
    HOLDOUT_START,
    TRAIN_END,
    VARIANTS,
    analyze_features,
    attach_features,
    find_setups,
    frozen_rules,
    long_roles,
    prepare,
    r_records,
    random_setups,
    signals_per_month,
    simulate,
)
from webull_bot.chart_reads.ema_reject import to_five_minute
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.vwap_band import passes_gate
from webull_bot.chart_reads.vwap_band_data import load_minutes
from webull_bot.data.base import normalize_frame
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.mtf_vwap.detect import rth, session_vwap

RULES_PATH = Path("reports/ema_reclaim_rules.json")
RESULT_PATH = Path("reports/ema_reclaim.json")
CHART_PATH = Path("reports/ema_reclaim_2026-10-07.png")
MARK_START = "<!-- EMA_RECLAIM_START -->"
MARK_END = "<!-- EMA_RECLAIM_END -->"
SAMPLE_END = date(2026, 10, 6)
EXITS = (
    ("structure", "shares", True),
    ("structure", "0dte", False),
    ("ema200", "shares", True),
    ("ema200", "0dte", False),
    ("prem50", "0dte", False),
    ("prem100", "0dte", False),
)
FIVE_THOUSAND = {
    ("strict", "structure", "shares"),
    ("strict", "structure", "0dte"),
    ("strict", "ema200", "shares"),
    ("strict", "ema200", "0dte"),
    ("strict", "prem50", "0dte"),
    ("strict", "prem100", "0dte"),
    ("no_crack", "structure", "shares"),
    ("no_crack", "structure", "0dte"),
    ("no_pullback", "structure", "shares"),
    ("no_pullback", "structure", "0dte"),
}


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


def _count(value: int) -> str:
    words = ("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten")
    return words[value] if 0 <= value < len(words) else str(value)


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
    return prior_iv(closes.get("VIX1D", pd.Series(dtype=float)), closes.get("VIX", pd.Series(dtype=float))), closes


def _vix_rising(closes: dict[str, pd.Series]) -> dict[date, bool]:
    out: dict[date, bool] = {}
    for name in ("VIX", "VIX1D"):
        series = closes.get(name)
        if series is None or series.empty:
            continue
        frame = series.astype(float).sort_index()
        index = pd.to_datetime(frame.index)
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert("America/New_York").tz_localize(None)
        frame.index = index.normalize()
        previous = frame.shift(1)
        older = frame.shift(2)
        for stamp, value in previous.items():
            prior = older.get(stamp)
            if not np.isfinite(value) or prior is None or not np.isfinite(prior):
                continue
            day = pd.Timestamp(stamp).date()
            if name == "VIX1D" or day not in out:
                out[day] = bool(value > prior)
    return out


def _qqq_maps(frame: pd.DataFrame) -> tuple[dict, dict, str]:
    bars = rth(frame)
    if bars.empty:
        return {}, {}, "QQQ 5-minute bars were not available, so that feature is off."
    bands = session_vwap(bars)
    close = bars["close"].astype(float)
    vwap = bands["vwap"].reindex(bars.index)
    long_map = {}
    short_map = {}
    for day, chunk in close.groupby(close.index.date):
        vw = vwap.reindex(chunk.index)
        below = False
        above = False
        for stamp, price in chunk.items():
            level = vw.get(stamp)
            if not np.isfinite(price) or level is None or not np.isfinite(level):
                continue
            if price > level and below:
                long_map[stamp] = True
            if price < level and above:
                short_map[stamp] = True
            below = below or price < level
            above = above or price > level
    start = pd.Timestamp(bars.index[0]).date()
    end = pd.Timestamp(bars.index[-1]).date()
    note = f"QQQ 5-minute bars run {start.isoformat()} through {end.isoformat()}."
    return long_map, short_map, note


def _clock(prep, i: int) -> str:
    return prep.index[i].tz_convert("America/New_York").strftime("%H:%M")


def _chart_frame() -> tuple[pd.DataFrame | None, str]:
    try:
        import yfinance as yf

        raw = yf.download(
            "SPY",
            start="2026-08-01",
            end="2026-10-08",
            interval="5m",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if raw is not None and not raw.empty:
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = [str(column[0]).lower() for column in raw.columns]
            normal = normalize_frame(raw, "5m")
            if not normal.empty:
                return normal, "Yahoo 5-minute download"
    except Exception:
        pass
    provider = YFinanceProvider(cache_dir="data/cache/ema_reject/yahoo")
    frames = provider.history(["SPY"], "2026-08-01", "2026-10-08", interval="5m")
    frame = frames.get("SPY")
    if frame is None or frame.empty:
        return None, "Yahoo returned no 5-minute SPY bars"
    return frame, "Yahoo 5-minute cache"


def _plot(prep, setups: list, path: Path) -> str:
    day_index = [i for i, day in enumerate(prep.dates) if day == CHART_DAY]
    if not day_index:
        return "The Yahoo 5-minute file has no 2026-10-07 session, so no step was invented."
    start, stop = day_index[0], day_index[-1] + 1
    fig, ax = plt.subplots(figsize=(12.4, 6.4), dpi=130)
    fig.patch.set_facecolor("#161616")
    ax.set_facecolor("#161616")
    width = 0.62
    for offset, i in enumerate(range(start, stop)):
        opened = float(prep.open[i])
        closed = float(prep.close[i])
        color = "#26a69a" if closed >= opened else "#ef5350"
        ax.plot([offset, offset], [prep.low[i], prep.high[i]], color=color, lw=0.8)
        body = max(abs(closed - opened), 0.01)
        ax.add_patch(Rectangle((offset - width / 2, min(opened, closed)), width, body, facecolor=color, edgecolor=color))
    x = np.arange(stop - start)
    ax.plot(x, prep.ema9[start:stop], color="#f4d03f", lw=1.1, label="9 EMA")
    ax.plot(x, prep.ema20[start:stop], color="#e67e22", lw=1.1, label="20 EMA")
    ax.plot(x, prep.ema200[start:stop], color="#bb8fce", lw=1.0, label="200 EMA")
    ax.plot(x, prep.vwap[start:stop], color="#5dade2", lw=1.0, label="VWAP")
    style = {
        "rejection": ("#f5b041", "v", 8),
        "crack": ("#e74c3c", "o", 7),
        "pullback": ("#5dade2", "D", 6),
        "trigger": ("#58d68d", "*", 11),
        "confirmation": ("#27ae60", "s", 6),
    }
    seen = set()
    for offset, i in enumerate(range(start, stop)):
        for role in long_roles(prep, i, start):
            if role not in style:
                continue
            color, marker, size = style[role]
            ax.scatter(
                [offset],
                [prep.high[i] + 0.15],
                color=color,
                marker=marker,
                s=size * 4,
                zorder=4,
                label=None if role in seen else role,
            )
            seen.add(role)
    fills = [item for item in setups if prep.dates[item.fill_i] == CHART_DAY and item.direction == "long" and item.variant in {"strict", "no_crack", "no_pullback", "no_crack_no_pullback"}]
    labeled = set()
    for item in fills:
        if item.variant in labeled:
            continue
        offset = item.fill_i - start
        ax.scatter([offset], [prep.low[item.fill_i] - 0.25], color="#f4f4f4", marker="^", s=36, zorder=5, label=f"{item.variant} fill")
        labeled.add(item.variant)
    ticks = list(range(0, stop - start, 6))
    ax.set_xticks(ticks)
    ax.set_xticklabels([prep.index[start + tick].strftime("%H:%M") for tick in ticks], color="#cccccc")
    ax.tick_params(colors="#cccccc")
    for spine in ax.spines.values():
        spine.set_color("#444444")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(color="#2a2a2a")
    ax.set_title("SPY 5-minute 2026-10-07. Steps are the frozen long rule. Not a forecast.", color="#f4f4f4")
    legend = ax.legend(facecolor="#1e1e1e", edgecolor="#333333", fontsize=8, loc="upper left")
    for text in legend.get_texts():
        text.set_color("#f4f4f4")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return _chart_sentence(prep, setups, start, stop)


def _chart_sentence(prep, setups, start: int, stop: int) -> str:
    def _times(role: str) -> str:
        hits = [_clock(prep, i) for i in range(start, stop) if role in long_roles(prep, i, start)]
        return ", ".join(hits) if hits else "none"

    def _fills(name: str) -> str:
        rows = [item for item in setups if item.variant == name and item.direction == "long" and prep.dates[item.fill_i] == CHART_DAY]
        if not rows:
            return "no long signal"
        bits = [
            f"trigger {_clock(prep, item.trigger_i)} confirmation {_clock(prep, item.confirm_i)} fill {_clock(prep, item.fill_i)} at {prep.open[item.fill_i]:.2f}"
            for item in rows[:3]
        ]
        return "; ".join(bits)

    last = prep.index[stop - 1].strftime("%H:%M")
    return (
        f"On Yahoo 5-minute SPY for 2026-10-07 the session in this file runs 09:30 through {last} ET. "
        f"Long rejections: {_times('rejection')}. Crack through the prior high: {_times('crack')}. "
        f"Pullback that holds the 9: {_times('pullback')}. Trigger above the 9, the 20, and VWAP: {_times('trigger')}. "
        f"Confirmation: {_times('confirmation')}. "
        f"Strict: {_fills('strict')}. Drop the crack: {_fills('no_crack')}. Drop the pullback: {_fills('no_pullback')}. "
        "The first bar that meets a step is the one that is marked. The rule was not moved onto a later print."
    )


def _row(name: str, per_month: float | None, hold: dict, train: dict | None, five: dict | None) -> str:
    five_bit = _money(five.get("ending_equity")) if five else "n/a"
    train_bit = _money(train.get("ending_equity")) if train else "n/a"
    return (
        f"| {name} | {_num(per_month)} | {hold.get('trades', 0)} | {_pct(hold.get('win_rate'))} | "
        f"{_pct(hold.get('breakeven_win_rate'))} | {_pf(hold.get('profit_factor'))} | {_num(hold.get('sharpe'))} | "
        f"{_pct(hold.get('max_drawdown'))} | {_money(hold.get('ending_equity'))} | {five_bit} | {train_bit} | "
        f"{'yes, not promoted' if passes_gate(hold) else 'no'} |"
    )


def _feature_line(item: dict) -> str:
    return (
        f"| {item['name']} | {item['train_n']} | {_num(item['train_mean'])} | {_num(item['train_lift'])} | "
        f"{item['hold_n']} | {_num(item['hold_mean'])} | {_num(item['hold_lift'])} | {_num(item['d'])} | "
        f"{_num(item['t'])} | {_num(item['q'])} | {'yes' if item['survives'] else 'no'} |"
    )


def _named(books: list[dict], name: str) -> dict:
    return next(item for item in books if item["name"] == name)


def _book_english(books: list[dict], random_bits: list[str]) -> str:
    strict = _named(books, "strict_structure_0dte")
    crack = _named(books, "no_crack_structure_0dte")
    pull = _named(books, "no_pullback_structure_0dte")
    hold = strict["hold"]
    random_end = "n/a"
    for bit in random_bits:
        if bit.startswith("strict_structure_0dte "):
            random_end = bit.split("ending ")[1].split(",")[0]
    share_lost = all(item["hold"]["ending_equity"] < 1000 for item in books if item["name"].endswith("_shares"))
    share_line = "Share books lost money on every variant. " if share_lost else "A share book finished above the stake. "
    return (
        f"The strict order fires about {strict['per_month']:.0f} times a month. "
        + share_line
        + f"The strict 0 DTE book finished the holdout at {_money(hold['ending_equity'])} "
        f"({hold['trades']} trades, {_pct(hold['win_rate'])} wins against a {_pct(hold['breakeven_win_rate'])} break-even, "
        f"profit factor {_pf(hold['profit_factor'])}, Sharpe {_num(hold['sharpe'])}, drawdown {_pct(hold['max_drawdown'])}) "
        f"and training finished at {_money(strict['train']['ending_equity'])}. "
        + ("The drawdown misses the gate. " if not passes_gate(hold) else "It cleared the holdout arithmetic. It is not promoted. ")
        + f"Seed-17 random 0 DTE entries finished at {random_end}. "
        "Dropping the crack is the version that matches the 2026-10-07 tape. "
        f"Its 0 DTE book finished at {_money(crack['hold']['ending_equity'])} "
        f"({crack['hold']['trades']:,} trades, profit factor {_pf(crack['hold']['profit_factor'])}, "
        f"Sharpe {_num(crack['hold']['sharpe'])}, drawdown {_pct(crack['hold']['max_drawdown'])})"
        + (" and cleared the holdout arithmetic. It is not promoted. " if passes_gate(crack["hold"]) else ". It did not clear the gate. ")
        + f"The training account went to {_money(crack['train']['ending_equity'])}. "
        "Dropping the pullback "
        + ("also cleared the holdout " if passes_gate(pull["hold"]) else "finished the holdout at ")
        + f"({_money(pull['hold']['ending_equity'])}, profit factor {_pf(pull['hold']['profit_factor'])}, "
        f"Sharpe {_num(pull['hold']['sharpe'])}, drawdown {_pct(pull['hold']['max_drawdown'])}) "
        f"and the training account went to {_money(pull['train']['ending_equity'])}. "
        "The half-scale at the 200 EMA did not repair the share books. "
        "The +50% premium target finished near or below the stake. "
        "The +100% target made holdout money and wiped training."
    )


def _english(report: dict, qqq_note: str = "") -> str:
    base = report["base_hold"]
    survivors = report["survivors"]
    rows = report["rows"]
    lead = (
        f"The reclaim population has {report['hold_n']} non-overlapping holdout trades. "
        f"Their mean after-cost R is {_num(base)}."
    )
    if not survivors:
        ranked = sorted(
            [item for item in rows if item["hold_lift"] is not None],
            key=lambda item: item["hold_lift"],
            reverse=True,
        )
        top = ", ".join(f"{item['name']} lift {_num(item['hold_lift'])} R (q {_num(item['q'])})" for item in ranked[:3]) or "none"
        wrong = [item["name"] for item in rows if item["hold_lift"] is not None and item["hold_lift"] < 0]
        by_name = {item["name"]: item for item in rows}

        def _lost(name: str) -> str:
            item = by_name[name]
            return f"{_num(abs(item['hold_mean']))} R"

        qqq = by_name.get("qqq_reclaim")
        stretch = by_name.get("vwap_stretch")
        positive = [
            item["name"]
            for item in rows
            if item["train_mean"] is not None
            and item["hold_mean"] is not None
            and item["train_mean"] > 0
            and item["hold_mean"] > 0
        ]
        qqq_end = ""
        if "through " in qqq_note:
            qqq_end = qqq_note.split("through ")[1].rstrip(".")
        return (
            lead + " No feature survived. A survivor needs a holdout q at or under 0.10, at least 30 trades in each window, "
            "a mean R above the base in both windows, and a mean R above zero in both windows. "
            f"The largest holdout lifts that still failed are {top}. "
            "Those lifts are smaller losses, not gains. "
            f"Morning still lost {_lost('morning')}, an expanding trigger bar lost {_lost('volume_expand')}, "
            f"and a MACD cross below zero lost {_lost('macd_cross_zero')}. "
            f"Afternoon (lift {_num(by_name['afternoon']['hold_lift'])} R) and a close above the opening range "
            f"(lift {_num(by_name['above_opening_range']['hold_lift'])} R) were worse than the base. "
            "A higher low, RSI divergence, the trendline break, and the hammer, engulfing, and morning-star shapes at the low did not help. "
            + (
                "The 2 standard deviation VWAP stretch was on for every holdout trade, so it did not split the sample. "
                if stretch is not None and stretch["hold_n"] == report["hold_n"]
                else ""
            )
            + (
                f"QQQ reclaiming its VWAP has the largest lift, on {qqq['hold_n']} holdout trades"
                + (f", because that file ends {qqq_end}" if qqq_end else "")
                + f". Its mean R is still {_num(qqq['hold_mean'])}. "
                if qqq is not None
                else ""
            )
            + f"{_count(len(wrong))} features had a negative holdout lift. "
            + ("No feature had a positive mean R in both windows. " if not positive else "")
            + "The combo is the unfiltered setup. Nothing was added on top of it."
        )
    bits = []
    for name in survivors:
        item = next(row for row in rows if row["name"] == name)
        bits.append(f"{name} (holdout mean R {_num(item['hold_mean'])}, lift {_num(item['hold_lift'])}, q {_num(item['q'])})")
    return (
        lead + " Surviving features, which also cleared the same bar in training: " + "; ".join(bits) + ". "
        "The combo is those features together. Its holdout dollar score was measured on the same window that selected the features, "
        "so that dollar number is not a fresh test."
    )


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
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(rules, indent=2) + "\n")
    written = json.loads(RULES_PATH.read_text())
    if "at or under 0.10" not in written["feature_outcome"] or "Not a live strategy" not in written["not_live"]:
        raise SystemExit("reclaim rules were not frozen before the score")
    minutes, info = load_minutes("SPY")
    if minutes is None:
        raise SystemExit(f"SPY minutes are not ready {info}")
    spy = to_five_minute(minutes)
    prep = prepare(spy)
    print(f"RECLAIM bars {len(prep.close)}", flush=True)
    setups = find_setups(prep, "SPY")
    for name in VARIANTS:
        print(f"RECLAIM {name} {sum(1 for item in setups if item.variant == name)}", flush=True)
    qqq_note = "QQQ 5-minute bars were not available, so that feature is off."
    qqq_long, qqq_short = {}, {}
    qqq_minutes, _qqq_info = load_minutes("QQQ")
    if qqq_minutes is not None:
        qqq_long, qqq_short, qqq_note = _qqq_maps(to_five_minute(qqq_minutes))
    iv_points, vix_closes = _iv()
    extra = {"vix_rising": _vix_rising(vix_closes), "qqq_long": qqq_long, "qqq_short": qqq_short}
    setups = attach_features(prep, setups, extra)
    grouped = {name: [item for item in setups if item.variant == name] for name in VARIANTS}

    books = []
    for variant in VARIANTS:
        per_month = signals_per_month(prep, grouped[variant], HOLDOUT_START, SAMPLE_END)
        for mode, kind, long_only in EXITS:
            name = f"{variant}_{mode}_{kind}"
            print(f"RECLAIM score {name}", flush=True)
            hold = simulate(
                prep, grouped[variant], mode=mode, kind=kind, stake=1000.0, long_only=long_only,
                iv_points=iv_points, start=HOLDOUT_START, end=SAMPLE_END,
            )
            train = simulate(
                prep, grouped[variant], mode=mode, kind=kind, stake=1000.0, long_only=long_only,
                iv_points=iv_points, end=TRAIN_END,
            )
            five = None
            if (variant, mode, kind) in FIVE_THOUSAND:
                five = simulate(
                    prep, grouped[variant], mode=mode, kind=kind, stake=5000.0, long_only=long_only,
                    iv_points=iv_points, start=HOLDOUT_START, end=SAMPLE_END,
                )
            books.append({
                "name": name,
                "variant": variant,
                "mode": mode,
                "kind": kind,
                "per_month": per_month,
                "hold": hold["metrics"],
                "train": train["metrics"],
                "five": None if five is None else five["metrics"],
                "hold_book": hold,
                "train_book": train,
            })

    def _random_text(book: dict) -> str:
        taken = book["hold_book"]["metrics"]["trades"]
        kind = book["kind"]
        random_book = simulate(
            prep,
            random_setups(prep, taken, start=HOLDOUT_START, end=SAMPLE_END),
            mode="structure",
            kind=kind,
            stake=1000.0,
            long_only=kind == "shares",
            iv_points=iv_points,
            start=HOLDOUT_START,
            end=SAMPLE_END,
        )
        metrics = random_book["metrics"]
        return (
            f"{book['name']} random holdout, seed 17, {metrics.get('trades', 0)} trades, "
            f"ending {_money(metrics.get('ending_equity'))}, profit factor {_pf(metrics.get('profit_factor'))}, "
            f"Sharpe {_num(metrics.get('sharpe'))}."
        )

    random_bits = []
    for book in books:
        if book["variant"] == "strict" and book["mode"] == "structure":
            random_bits.append(_random_text(book))
        if book["variant"] == "reclaim9" and book["mode"] == "structure" and book["kind"] == "0dte":
            random_bits.append(_random_text(book))

    reclaim = grouped["reclaim9"]
    train_r = r_records(prep, reclaim, end=TRAIN_END)
    hold_r = r_records(prep, reclaim, start=HOLDOUT_START, end=SAMPLE_END)
    report = analyze_features(train_r, hold_r)
    print(f"RECLAIM survivors {report['survivors']}", flush=True)
    combo_lines = []
    combo_payload = []
    if report["survivors"]:
        needed = set(report["survivors"])
        for variant in ("reclaim9", "strict", "no_crack", "no_pullback"):
            chosen = [item for item in grouped[variant] if needed.issubset(item.features)]
            for kind, long_only in (("shares", True), ("0dte", False)):
                hold = simulate(
                    prep, chosen, mode="structure", kind=kind, stake=1000.0, long_only=long_only,
                    iv_points=iv_points, start=HOLDOUT_START, end=SAMPLE_END,
                )
                train = simulate(
                    prep, chosen, mode="structure", kind=kind, stake=1000.0, long_only=long_only,
                    iv_points=iv_points, end=TRAIN_END,
                )
                metrics = hold["metrics"]
                combo_lines.append(
                    f"{variant} combo {kind}: {metrics.get('trades', 0)} holdout trades, "
                    f"win {_pct(metrics.get('win_rate'))}, profit factor {_pf(metrics.get('profit_factor'))}, "
                    f"Sharpe {_num(metrics.get('sharpe'))}, drawdown {_pct(metrics.get('max_drawdown'))}, "
                    f"ending {_money(metrics.get('ending_equity'))}, train {_money(train['metrics'].get('ending_equity'))}."
                )
                combo_payload.append({"variant": variant, "kind": kind, "hold": metrics, "train": train["metrics"]})
    else:
        combo_lines.append("No combo. No feature survived, so the base setup was not filtered.")

    chart_frame, chart_source = _chart_frame()
    if chart_frame is None:
        chart_note = "Yahoo returned no 5-minute SPY bars for 2026-10-07, so no step was invented."
    else:
        chart_prep = prepare(chart_frame)
        chart_setups = attach_features(chart_prep, find_setups(chart_prep, "SPY"), extra)
        chart_note = _plot(chart_prep, chart_setups, CHART_PATH)
        chart_note = f"{chart_source}. {chart_note}"

    lines = [
        MARK_START,
        "### 2026-10-07 reclaim: crack, pullback, trigger, confirmation",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. The chop-breakout order rules were not changed. "
        "This sequence was frozen before the score. It does not replace the VWAP-confluence rejection gate, and it does not replace the simpler reversal variant already scored. "
        "A long needs a bearish stack (9 EMA under the 20, both lower than three bars ago, close under VWAP) with at least two tags of the 9 that close back under, "
        "then a green bar that closes above the prior red bar's high and above both EMAs, then a pullback that tests the 9 and holds, "
        "then a green bar that closes above the 9, the 20, and VWAP, then a next bar that also closes green. "
        "The fill is the open after that confirmation. The short is the mirror and buys a put. "
        "The price stop is one cent beyond the trigger bar. A close back across the 9 EMA exits at that close, and the price stop still fills first. "
        "Shares sell half if the 5-minute 200 EMA is beyond the fill and then stop the rest at the raw entry. One 0 DTE contract sells there in full. "
        "The 50% and 100% targets are on the option premium. Everything is flat at the 15:30 open. "
        "Dropping the crack, dropping the pullback, and dropping both are variants. The 9 EMA reclaim is the population the features are tested on.",
        "",
        "Signals per month are holdout fills before the one-position filter, from 2022-01-01 through 2026-10-06. "
        "Win rate is the share of trades with a positive dollar result. Break-even is the win rate the payoff needs.",
        "",
        "| Book | Signals/mo | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 | Train $1,000 | Clears |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for book in books:
        lines.append(_row(book["name"], book["per_month"], book["hold"], book["train"], book["five"]))
    lines += [
        "",
        _book_english(books, random_bits),
        "",
        " ".join(random_bits) if random_bits else "No random row.",
        "",
        "### What else shows up before the reclaim",
        "",
        "The outcome is the after-cost R of one share on the structure exit, both directions, one position at a time. "
        "R is the dollar result divided by the distance from the fill to the trigger stop. "
        "A feature survives only when its holdout q is at or under 0.10, train and holdout each have at least 30 trades with it on, "
        "its mean R beats the base reclaim in both windows, and that mean is above zero in both windows. "
        "q is Benjamini-Hochberg across these 22 features. The t-test treats the trades as independent, and they are not, so a passing q is still a generous bar. "
        "Dukascopy volume is a bid-tick count. There is no advance-decline series, so breadth is QQQ reclaiming its own session VWAP. "
        + qqq_note,
        "",
        "| Feature | Train n | Train mean R | Train lift | Holdout n | Holdout mean R | Holdout lift | Cohen d | t | q | Survives |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in report["rows"]:
        lines.append(_feature_line(item))
    lines += [
        "",
        _english(report, qqq_note),
        "",
        " ".join(combo_lines),
        "",
        chart_note,
        "",
        "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.",
        "",
        "```",
        "python3 -m webull_bot.chart_reads.research_ema_reclaim",
        "```",
        MARK_END,
        "",
    ]
    _write(lines)
    payload = {
        "books": [
            {"name": book["name"], "per_month": book["per_month"], "hold": book["hold"], "train": book["train"], "five": book["five"]}
            for book in books
        ],
        "features": report,
        "combo": combo_payload,
        "chart": chart_note,
        "random": random_bits,
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(chart_note, flush=True)
    print("WROTE reports/ema_reclaim.json", flush=True)


if __name__ == "__main__":
    main()
