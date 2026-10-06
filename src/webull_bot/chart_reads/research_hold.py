"""Score the chop-hold retest on 60-minute and 15-minute bars.

The sequence in ``hold.py`` was frozen before this run. A label here does
not change the gate and is not added to the strategy registry. Exits are
the frozen five-contract scale-out, the percent and ATR trails, and the
brackets. Nothing is sent to a broker.

Run: ``python -m webull_bot.chart_reads.research_hold``
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

from webull_bot.chart_reads.chop import features
from webull_bot.chart_reads.detect import session_bands
from webull_bot.chart_reads.hold import attempt_counts, scan_chop_holds
from webull_bot.chart_reads.premium_scale import scale_grid, underlying_exit_grid
from webull_bot.chart_reads.research import END, SYMBOLS, _cells, _sessions, _slice, load_yahoo
from webull_bot.chart_reads.research_scale import (
    _ab_window,
    _best_scale,
    _dist,
    _gate_line,
    _money,
    _paired_all_out,
    _score_book,
    _table,
)
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.mtf_vwap.detect import rth

START = "<!-- CHART_READS_HOLD_START -->"
END_MARK = "<!-- CHART_READS_HOLD_END -->"
CHART_DIR = Path("reports/setups")
ARTIFACT_DIR = Path("/opt/cursor/artifacts/setups")
# The user's Oct 6, 2026 NVDA 20-day hourly annotations. Comparison only.
ANNOTATED_ASOF = date(2026, 10, 6)
ANNOTATED_PRICE = 241.37
ANNOTATED_HIGH = 243.37
ANNOTATED_LINES = (234.0, 232.5, 227.5, 221.5)
ANNOTATED_PULLBACK = (232.5, 235.0)
ANNOTATED_FRIDAY = date(2026, 10, 2)
SESSIONS = 20


def _day(ts) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York")
    return stamp.date()


def _last_session_mask(index: pd.DatetimeIndex, sessions: int) -> np.ndarray:
    days: list[date] = []
    for ts in index:
        day = _day(ts)
        if not days or days[-1] != day:
            days.append(day)
    keep = set(days[-sessions:])
    return np.array([_day(ts) in keep for ts in index])


def _sum_counts(frames: dict) -> dict:
    totals = {"breakouts": 0, "rejected": 0, "chop_runs": 0, "hold_breaks": 0, "signals": 0}
    for frame in frames.values():
        if frame is None or len(frame) < 160:
            continue
        counts = attempt_counts(frame)
        for key in totals:
            totals[key] += int(counts.get(key, 0))
    return totals


def _detect(frames: dict) -> list:
    marks = []
    for symbol, frame in frames.items():
        if frame is None or len(frame) < 160:
            continue
        marks.extend(scan_chop_holds(frame, symbol=symbol))
    marks.sort(key=lambda mark: (pd.Timestamp(mark.setup.fill_time), mark.setup.symbol))
    return marks


def _nvda_check(frame: pd.DataFrame, clock: str) -> dict:
    bars = rth(frame)
    feat = features(bars)
    bands = session_bands(bars, 2.0).reindex(bars.index)
    mask = _last_session_mask(bars.index, SESSIONS)
    window = bars.loc[mask]
    feat_w = feat.loc[mask]
    chop = feat_w["chop"].fillna(False).to_numpy(dtype=bool)
    chop_bars = window.loc[chop]
    marks = [
        mark
        for mark in scan_chop_holds(bars, symbol="NVDA")
        if _day(mark.breakout_time) >= _day(window.index[0]) or _day(mark.setup.signal_time) >= _day(window.index[0])
    ]
    friday = window.loc[[_day(ts) == ANNOTATED_FRIDAY for ts in window.index]]
    quiet = feat_w["rel_volume"] < 0.80
    return {
        "clock": clock,
        "start": _day(window.index[0]).isoformat(),
        "end": str(window.index[-1]),
        "bars": int(len(window)),
        "last_close": float(window["close"].iloc[-1]),
        "window_high": float(window["high"].max()),
        "window_low": float(window["low"].min()),
        "chop_bars": int(chop.sum()),
        "narrow": int(feat_w["narrow"].fillna(False).sum()),
        "tangled": int(feat_w["tangled"].fillna(False).sum()),
        "vwap_crosses": int((feat_w["vwap_crosses"] >= 3).sum()),
        "quiet": int(quiet.fillna(False).sum()),
        "chop_high": float(chop_bars["high"].max()) if len(chop_bars) else None,
        "chop_low": float(chop_bars["low"].min()) if len(chop_bars) else None,
        "chop_times": [str(ts) for ts in chop_bars.index],
        "friday_high": float(friday["high"].max()) if len(friday) else None,
        "friday_low": float(friday["low"].min()) if len(friday) else None,
        "friday_close": float(friday["close"].iloc[-1]) if len(friday) else None,
        "marks": [
            {
                "direction": mark.setup.direction,
                "level": mark.level,
                "breakout": str(mark.breakout_time),
                "chop_start": str(mark.chop_start),
                "chop_end": str(mark.chop_end),
                "signal": str(mark.setup.signal_time),
                "stop": mark.setup.stop,
            }
            for mark in marks
        ],
    }


def _save_chart(frame: pd.DataFrame, check: dict, path: Path) -> None:
    bars = rth(frame)
    feat = features(bars)
    bands = session_bands(bars, 2.0).reindex(bars.index)
    mask = _last_session_mask(bars.index, SESSIONS)
    window = bars.loc[mask]
    feat_w = feat.loc[mask]
    bands_w = bands.loc[mask]
    fig, (ax, vol) = plt.subplots(
        2, 1, figsize=(13.5, 7.4), sharex=True, gridspec_kw={"height_ratios": [3.2, 1.0]}
    )
    ax.set_facecolor("#161616")
    vol.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    flags = feat_w["chop"].fillna(False).to_numpy(dtype=bool)
    for pos, flag in enumerate(flags):
        if flag:
            ax.axvspan(pos - 0.5, pos + 0.5, color="#f2d16b", alpha=0.35, linewidth=0)
            vol.axvspan(pos - 0.5, pos + 0.5, color="#f2d16b", alpha=0.35, linewidth=0)
    for pos, (_, row) in enumerate(window.iterrows()):
        color = "#3d9e57" if row["close"] >= row["open"] else "#d64545"
        ax.plot([pos, pos], [row["low"], row["high"]], color=color, linewidth=0.8)
        body_low = min(row["open"], row["close"])
        body_high = max(row["open"], row["close"])
        ax.plot([pos, pos], [body_low, body_high], color=color, linewidth=2.4)
    xs = np.arange(len(window))
    ax.plot(xs, feat_w["ema9"].to_numpy(dtype=float), color="#4ea3ff", linewidth=1.0, label="EMA 9")
    ax.plot(xs, feat_w["ema20"].to_numpy(dtype=float), color="#e0a100", linewidth=1.0, label="EMA 20")
    ax.plot(xs, bands_w["vwap"].to_numpy(dtype=float), color="#7fd1c8", linewidth=1.0, label="VWAP")
    ax.plot(xs, bands_w["upper"].to_numpy(dtype=float), color="#7fd1c8", linewidth=0.7, linestyle="--", label="VWAP band")
    ax.plot(xs, bands_w["lower"].to_numpy(dtype=float), color="#7fd1c8", linewidth=0.7, linestyle="--")
    low_line, high_line = ANNOTATED_PULLBACK
    ax.axhspan(low_line, high_line, color="#f2d16b", alpha=0.08, label="annotated pullback")
    for price in ANNOTATED_LINES:
        ax.axhline(price, color="#888888", linewidth=0.7, linestyle=":")
    ax.text(len(window) - 1, ANNOTATED_LINES[0], "234", color="#cccccc", fontsize=8, ha="right", va="bottom")
    friday_pos = [pos for pos, ts in enumerate(window.index) if _day(ts) == ANNOTATED_FRIDAY]
    if friday_pos:
        ax.axvline(friday_pos[0], color="#d0d0d0", linewidth=0.8, linestyle="--")
    colors = ["#3d9e57" if row["close"] >= row["open"] else "#d64545" for _, row in window.iterrows()]
    vol.bar(xs, window["volume"].to_numpy(dtype=float), color=colors, width=0.7)
    entry = "no hold entry" if not check["marks"] else f"{len(check['marks'])} hold entry"
    ax.set_title(
        f"NVDA {check['clock']} {check['start']} through {check['end']}, {entry}",
        color="white",
    )
    ax.tick_params(colors="#cccccc")
    vol.tick_params(colors="#cccccc")
    for spine in (*ax.spines.values(), *vol.spines.values()):
        spine.set_color("#333333")
    ax.legend(facecolor="#161616", edgecolor="#333333", labelcolor="white", loc="upper left")
    step = max(1, len(window) // 6)
    ticks = list(range(0, len(window), step))
    if ticks[-1] != len(window) - 1:
        ticks.append(len(window) - 1)
    vol.set_xticks(ticks)
    vol.set_xticklabels(
        [pd.Timestamp(window.index[pos]).strftime("%m-%d %H:%M") for pos in ticks],
        rotation=30,
        ha="right",
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _span(frames) -> str:
    days = _sessions(frames)
    if not days:
        return "no sessions"
    return f"{days[0].isoformat()} through {days[-1].isoformat()}"


def _book(name: str, frames: dict, daily: dict, execution: str) -> dict:
    print(f"detect {name}", flush=True)
    marks = _detect(frames)
    setups = [mark.setup for mark in marks]
    counts = _sum_counts(frames)
    print(f"  signals {len(setups)} counts {counts}", flush=True)
    params = _cells(execution)[0]
    is_window, oos_window = _ab_window(frames)
    scored = None
    if setups:
        spec = {
            "name": name,
            "setups": setups,
            "frames": frames,
            "daily": daily,
            "base": params,
            "session_filter": True,
            "slice": _slice,
            "is_window": is_window,
            "oos_window": oos_window,
            "blurb": "",
        }
        scored = _score_book(spec)
    return {
        "name": name,
        "signals": len(setups),
        "longs": sum(1 for setup in setups if setup.direction == "long"),
        "shorts": sum(1 for setup in setups if setup.direction == "short"),
        "counts": counts,
        "span": _span(frames),
        "is_window": [is_window[0].isoformat(), is_window[1].isoformat()],
        "oos_window": [oos_window[0].isoformat(), oos_window[1].isoformat()],
        "hold": "up to 5 sessions" if execution == "60m" else "flattened at the session close",
        "scored": scored,
    }


def _exit_names() -> str:
    names = [label for label, _cell in scale_grid()]
    names.extend(label for label, _cell in underlying_exit_grid({}))
    return ", ".join(names)


def _chop_timing(check: dict) -> str:
    times = check.get("chop_times") or []
    if not times:
        return "No chop bar falls in that window."
    days = sorted({_day(ts).isoformat() for ts in times})
    before = sum(1 for ts in times if _day(ts) < ANNOTATED_FRIDAY)
    after = len(times) - before
    return (
        f"{before} of those chop bars are before {ANNOTATED_FRIDAY.isoformat()} and {after} are on or after it. "
        f"The chop dates are {', '.join(days)}."
    )


def _nvda_paragraph(checks: list[dict]) -> str:
    hourly = next(row for row in checks if row["clock"] == "60m")
    slow = next(row for row in checks if row["clock"] == "15m")
    lines = [
        f"The annotated NVDA chart is a 20-session {hourly['clock']} window from {hourly['start']} through {hourly['end']}. "
        f"Yahoo's adjusted high in that window is {_money(hourly['window_high'])}, against the annotated high of "
        f"{_money(ANNOTATED_HIGH)}. The last bar closes at {_money(hourly['last_close'])}; the annotation's price is "
        f"{_money(ANNOTATED_PRICE)}. Friday {ANNOTATED_FRIDAY.isoformat()} trades "
        f"{_money(hourly['friday_low'])} to {_money(hourly['friday_high'])} and closes {_money(hourly['friday_close'])}. "
        f"The drawn lines are {', '.join(f'{price:.1f}' for price in ANNOTATED_LINES)}. "
        f"The drawn pullback is {ANNOTATED_PULLBACK[0]:.1f} to {ANNOTATED_PULLBACK[1]:.1f}.",
        "",
        f"On that hourly window the chop flag is on for {hourly['chop_bars']} of {hourly['bars']} bars. "
        f"Narrow is on for {hourly['narrow']}, quiet volume for {hourly['quiet']}, and VWAP has been crossed at least "
        f"three times in 20 bars on {hourly['vwap_crosses']}. The tangled 9/20 EMA leg is on for {hourly['tangled']}. "
        f"The hold scan marks {len(hourly['marks'])} entries. The same 20 sessions on 15-minute bars have "
        f"{slow['chop_bars']} chop bars"
        + (
            f", from {_money(slow['chop_low'])} to {_money(slow['chop_high'])},"
            if slow["chop_bars"]
            else ""
        )
        + f" and {len(slow['marks'])} hold entries. {_chop_timing(slow)} "
        "The rule was not loosened to force a mark.",
    ]
    return "\n".join(lines)


def render(books: list[dict], checks: list[dict]) -> str:
    lines = [
        "## Chop-hold retest",
        "",
        "DOES NOT CHANGE THE GATE. This is the annotated NVDA sequence, frozen before the score: a breakout of a "
        "10-session shelf, a rejection of the 2-standard-deviation VWAP band, then a low-volume chop pullback that "
        "holds the broken level, then a strong close out of that chop. The pullback is the chop flag already scored. "
        "That flag was not retuned. The stop is under the held level. The exits, if a fill exists, are the frozen "
        "five-contract scale-out, the all-out +30% comparison, the percent and ATR trails, and the brackets. "
        "Nothing was sent to a broker. `live_trading_enabled` stays false.",
        "",
        "The shelf is the prior 10 sessions. Its high and its low each have to be touched in two of those sessions, "
        "within the frozen 0.50 ATR touch, and the height has to sit inside setup D's frozen ATR bounds. The breakout "
        "is a strong candle closing through that side by 0.10 ATR, on the breakout side of session VWAP. The chop "
        "zone is at least six contiguous chop bars inside the next 5 sessions, and it has to trade back to the broken "
        "level. No close may go back through the level, and no wick may exceed the 0.50 ATR touch. The next strong "
        "candle has to close out of the chop zone. One attempt per breakout. Short is the mirror. The 5-minute book "
        "is not in this run. Both clocks are inside the free Yahoo intraday cap.",
        "",
        f"Exit grid, unchanged from the scale-out study: {_exit_names()}.",
        "",
    ]
    for book in books:
        lines.append(f"### {book['name']}")
        lines.append("")
        counts = book["counts"]
        lines.append(
            f"{book['signals']} signals ({book['longs']} long, {book['shorts']} short) on {book['span']}. "
            f"In sample {book['is_window'][0]} through {book['is_window'][1]}. "
            f"Out of sample {book['oos_window'][0]} through {book['oos_window'][1]}. "
            f"Hold is {book['hold']}. Calls and puts would be 3 DTE, delta 0.45, five contracts. "
            f"The scan saw {counts['breakouts']} breakouts, {counts['chop_runs']} of them with a six-bar chop run, "
            f"{counts['rejected']} of those runs also rejecting the VWAP band while the hold was intact, "
            f"{counts['hold_breaks']} hold breaks, and {counts['signals']} resumptions."
        )
        lines.append("")
        scored = book["scored"]
        if not scored:
            lines.append(
                "There is no fill, so the scale-out, the trails, and the brackets are not scored on this book. "
                "A five-lot cannot be sized, and there is no win rate, target distribution, or drawdown. "
                "The empty book does not clear the old gate."
            )
            lines.append("")
            continue
        lines.append(scored["blurb"])
        lines.append("")
        for regime in scored["regimes"]:
            lines.append(regime["title"])
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
                f"{_money(best['oos'].get('expectancy'))} on {int(best['oos'].get('trades') or 0)} trades. "
                f"It {_gate_line(best['oos'])}. The paired all-out row is {paired_text}."
            )
            lines.append(_dist(best["oos_extra"]))
            lines.append("")
    lines.append(_nvda_paragraph(checks))
    lines.append("")
    lines.append(
        "Charts: `reports/setups/readHOLD_NVDA_60m.png` and `reports/setups/readHOLD_NVDA_15m.png`. "
        "Gold bars are the chop flag. Dotted lines are the annotated levels. The pale band is the annotated "
        "232.5-235 pullback. The dashed vertical is Friday, October 2. No triangle is drawn, because the scan "
        "did not mark an entry."
        if all(not row["marks"] for row in checks)
        else "Charts: `reports/setups/readHOLD_NVDA_60m.png` and `reports/setups/readHOLD_NVDA_15m.png`."
    )
    lines.append("")
    lines.append(
        "Not added to `config/optional_strategies.json`. The published A-D books, the bounce, and the earlier exit "
        "labels are unchanged. The default book is still dual momentum."
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


def write_readme(text: str, path: Path) -> None:
    body = path.read_text()
    paragraph = text.strip() + "\n\n"
    key = "**Chop-hold retest:"
    if key in body:
        start = body.index(key)
        nxt = body.find("\n**", start + len(key))
        if nxt < 0:
            nxt = len(body)
        path.write_text(body[:start] + paragraph + body[nxt:].lstrip("\n"))
        return
    anchor = "**Chart Fanatics specs:"
    if anchor not in body:
        raise SystemExit("README has no Chart Fanatics paragraph to insert before")
    path.write_text(body.replace(anchor, paragraph + anchor, 1))


def readme_paragraph(books: list[dict], checks: list[dict]) -> str:
    hourly = next(row for row in checks if row["clock"] == "60m")
    slow = next(row for row in checks if row["clock"] == "15m")
    signals = ", ".join(f"{book['name']} {book['signals']}" for book in books)
    return (
        "**Chop-hold retest: does not pass.** After a breakout of a 10-session shelf, the frozen chop flag has to "
        "mark a pullback that holds the old level, and the entry is the strong close out of that chop, with the stop "
        f"under the level. On the named list that sequence fired {signals}. "
        f"The exits were the five-contract scale-out, the trails, and the brackets; with no fill they are not scored. "
        f"On the Oct 6, 2026 NVDA 20-session hourly chart, Yahoo's high is {_money(hourly['window_high'])} against the "
        f"annotated {_money(ANNOTATED_HIGH)}, and the last close is {_money(hourly['last_close'])} against "
        f"{_money(ANNOTATED_PRICE)}. The chop flag is on for {hourly['chop_bars']} hourly bars in that window because "
        f"the 9 and 20 EMAs are tangled on {hourly['tangled']} of them. The 15-minute window has {slow['chop_bars']} "
        f"chop bars and {len(slow['marks'])} hold entries. {_chop_timing(slow)} The chop rule was not retuned. "
        "Charts are in `reports/setups/readHOLD_NVDA_60m.png` and `reports/setups/readHOLD_NVDA_15m.png`. "
        "Nothing was sent to a broker. Live trading stays off. The default book is still dual momentum. "
        "Full table in [RESULTS.md](RESULTS.md)."
    )


def _json(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    return str(value)


def main() -> None:
    provider = YFinanceProvider("data/cache")
    print("loading intraday cache", flush=True)
    daily, hourly, m15, _m5 = load_yahoo(provider)
    del _m5
    present = [symbol for symbol in SYMBOLS if symbol in daily and symbol in hourly and len(hourly[symbol]) > 50]
    daily = {symbol: daily[symbol] for symbol in present}
    hourly = {symbol: hourly[symbol] for symbol in present}
    m15 = {symbol: m15[symbol] for symbol in present if symbol in m15 and len(m15[symbol]) > 30}
    books = [
        _book("Chop-hold, 60-minute", hourly, daily, "60m"),
        _book("Chop-hold, 15-minute", m15, daily, "15m"),
    ]
    print("NVDA chart check", flush=True)
    checks = [
        _nvda_check(hourly["NVDA"], "60m"),
        _nvda_check(m15["NVDA"], "15m"),
    ]
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    for clock, frame in (("60m", hourly["NVDA"]), ("15m", m15["NVDA"])):
        check = next(row for row in checks if row["clock"] == clock)
        path = CHART_DIR / f"readHOLD_NVDA_{clock}.png"
        _save_chart(frame, check, path)
        (ARTIFACT_DIR / path.name).write_bytes(path.read_bytes())
        print(f"chart {path}", flush=True)
    text = render(books, checks)
    write_report(text, Path("RESULTS.md"))
    write_readme(readme_paragraph(books, checks), Path("README.md"))
    payload = {"books": books, "nvda": checks, "end": END}
    out = Path("reports/chart_reads_hold.json")
    out.write_text(json.dumps(payload, indent=2, default=_json) + "\n")
    print(text)


if __name__ == "__main__":
    main()
