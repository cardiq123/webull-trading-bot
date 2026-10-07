"""Which support and resistance source helps setups A-D. Backtests only.

The signals, stops, trails, and holds stay the published ones. The only
change is the profit target. Every source is scored. None of them replaces
the gated default, including a source that beats it out of sample.

Run: ``python -m webull_bot.chart_reads.research_levels``
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from webull_bot.chart_reads.breakouts import find_breakout_setups
from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.levels import (
    VARIANTS,
    build_levels,
    improves_oos,
)
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DAILY_DEFAULTS
from webull_bot.chart_reads.research import (
    _cells,
    _sessions,
    _split,
    _window_book as intraday_window,
    detect_all,
    load_yahoo,
)
from webull_bot.chart_reads.research_daily import (
    IS_END,
    OOS_START,
    SAMPLE_END,
    SCORE_FROM,
    _window_book as daily_window,
    load_daily,
)
from webull_bot.chart_reads.trendline import find_trend_setups
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.universe_dow import all_dow_tickers, is_member

START = "<!-- CHART_READS_SR_START -->"
END = "<!-- CHART_READS_SR_END -->"
LABELS = {
    "published": "published target",
    "horizontal": "horizontal pivots",
    "floor": "floor pivots PP R1 S1 R2 S2",
    "prior_day": "prior-day high and low",
    "zone": "demand and supply zones",
    "fib": "Fibonacci 38.2/50/61.8",
    "trendline": "trendline",
    "flipped": "flipped S/R",
    "confluence": "confluence, two or more sources",
    "any": "nearest of any source",
}
# Published stock out-of-sample endings, used only to check this run's baseline.
EXPECTED = {
    "A and B, 60-minute": (967.77, 164),
    "A and B, 15-minute": (1001.48, 10),
    "A and B, 5-minute": (978.07, 11),
    "C, daily Dow": (746.56, 207),
    "D, daily Dow": (919.45, 73),
}


@dataclass
class Row:
    source: str
    is_metrics: dict
    oos_metrics: dict
    level_share: float
    improves: bool


@dataclass
class Book:
    name: str
    blurb: str
    signals: int
    rows: list[Row] = field(default_factory=list)

    @property
    def published(self) -> Row:
        return self.rows[0]


def _day(ts) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York")
    return stamp.date()


def _loc(frame: pd.DataFrame, ts) -> int | None:
    try:
        loc = frame.index.get_loc(pd.Timestamp(ts))
    except KeyError:
        return None
    if isinstance(loc, slice):
        return None if loc.start is None else int(loc.start)
    if isinstance(loc, np.ndarray):
        hits = np.flatnonzero(loc)
        return int(hits[0]) if len(hits) else None
    return int(loc)


def _tables(frames: dict[str, pd.DataFrame], symbols: set[str]) -> dict:
    built = {}
    for symbol in sorted(symbols):
        frame = frames.get(symbol)
        if frame is None or len(frame) < 30:
            continue
        built[symbol] = build_levels(frame)
    return built


def _retarget(setups: list[Setup], frames, tables, source: str) -> list[Setup]:
    out = []
    for setup in setups:
        frame = frames.get(setup.symbol)
        table = tables.get(setup.symbol)
        price = float("nan")
        if frame is not None and table is not None:
            loc = _loc(frame, setup.signal_time)
            if loc is not None and loc + 1 < len(frame):
                fill = float(frame.iloc[loc + 1]["open"])
                risk = abs(fill - float(setup.stop))
                price = table.target(loc, setup.direction, fill, risk, source)
        out.append(
            Setup(
                symbol=setup.symbol,
                direction=setup.direction,
                kind=setup.kind,
                signal_time=setup.signal_time,
                fill_time=setup.fill_time,
                anchor_time=setup.anchor_time,
                stop=float(setup.stop),
                atr=float(setup.atr),
                reference=float(price) if np.isfinite(price) else float("nan"),
            )
        )
    return out


def _share(setups: list[Setup]) -> float:
    if not setups:
        return 0.0
    hit = sum(1 for setup in setups if np.isfinite(setup.reference))
    return hit / len(setups)


def _between(setups: list[Setup], start: date, end: date) -> list[Setup]:
    return [setup for setup in setups if start <= _day(setup.fill_time) <= end]


def _variant_params(base: dict) -> dict:
    chosen = dict(base)
    chosen["expression"] = "stock"
    chosen["target_mode"] = "level"
    chosen["level_source"] = "reference"
    return chosen


def _published_params(base: dict) -> dict:
    chosen = dict(base)
    chosen["expression"] = "stock"
    return chosen


def _score_book(
    name: str,
    blurb: str,
    setups: list[Setup],
    frames,
    daily,
    base: dict,
    windows: tuple[tuple[date, date], tuple[date, date]],
    tables,
    *,
    daily_book: bool,
) -> Book:
    book = Book(name=name, blurb=blurb, signals=len(setups))
    is_window, oos_window = windows
    window_book = daily_window if daily_book else intraday_window
    published = _published_params(base)
    print(f"  {name}: published target, {len(setups)} signals", flush=True)
    is_stats = window_book(setups, frames, daily, published, "stock", is_window[0], is_window[1])
    oos_stats = window_book(setups, frames, daily, published, "stock", oos_window[0], oos_window[1])
    book.rows.append(
        Row("published", is_stats.metrics, oos_stats.metrics, float("nan"), False)
    )
    variant = _variant_params(base)
    for source in VARIANTS:
        targeted = _retarget(setups, frames, tables, source)
        oos_setups = _between(targeted, oos_window[0], oos_window[1])
        share = _share(oos_setups)
        is_stats = window_book(targeted, frames, daily, variant, "stock", is_window[0], is_window[1])
        oos_stats = window_book(targeted, frames, daily, variant, "stock", oos_window[0], oos_window[1])
        flag = improves_oos(book.published.oos_metrics, oos_stats.metrics, share)
        book.rows.append(Row(source, is_stats.metrics, oos_stats.metrics, share, flag))
        print(
            f"    {source}: OOS trades {oos_stats.metrics.get('trades')} "
            f"ending {oos_stats.metrics.get('ending_equity')} share {share:.0%} improves {flag}",
            flush=True,
        )
    return book


def _collect_daily(frames, builder, params) -> list[Setup]:
    symbols = [symbol for symbol in all_dow_tickers() if symbol in frames]
    found: list[Setup] = []
    for symbol in symbols:
        frame = frames[symbol]
        if len(frame) < 80:
            continue
        setups = builder(frame, params, symbol=symbol)
        setups = [setup for setup in setups if is_member(symbol, _day(setup.signal_time))]
        setups = [setup for setup in setups if _day(setup.fill_time) >= SCORE_FROM]
        found.extend(setups)
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.kind))
    return found


def _fmt_money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"${float(value):,.2f}"


def _fmt_pf(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _fmt_num(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _fmt_dd(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.1%}"


def _fmt_share(value) -> str:
    if value is None or not np.isfinite(value):
        return "—"
    return f"{float(value):.0%}"


def _table(book: Book) -> str:
    lines = [
        "| Level | IS trades | IS ending | OOS trades | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Signals with a level | Improves |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in book.rows:
        flag = "—" if row.source == "published" else ("yes" if row.improves else "no")
        lines.append(
            "| {label} | {is_trades} | {is_end} | {oos_trades} | {pf} | {sharpe} | {dd} | {oos_end} | {share} | {flag} |".format(
                label=LABELS[row.source],
                is_trades=int(row.is_metrics.get("trades") or 0),
                is_end=_fmt_money(row.is_metrics.get("ending_equity")),
                oos_trades=int(row.oos_metrics.get("trades") or 0),
                pf=_fmt_pf(row.oos_metrics.get("profit_factor")),
                sharpe=_fmt_num(row.oos_metrics.get("sharpe")),
                dd=_fmt_dd(row.oos_metrics.get("max_drawdown")),
                oos_end=_fmt_money(row.oos_metrics.get("ending_equity")),
                share=_fmt_share(row.level_share),
                flag=flag,
            )
        )
    return "\n".join(lines)


def _baseline_note(book: Book) -> str:
    expected = EXPECTED.get(book.name)
    row = book.published
    ending = float(row.oos_metrics.get("ending_equity") or 0.0)
    trades = int(row.oos_metrics.get("trades") or 0)
    if expected is None:
        return ""
    want_end, want_trades = expected
    if abs(ending - want_end) <= 0.02 and trades == want_trades:
        return (
            f"The published-target row matches the gated out-of-sample stock book "
            f"({_fmt_money(want_end)} on {want_trades} trades)."
        )
    return (
        f"The published-target row in this run is {_fmt_money(ending)} on {trades} trades. "
        f"The gated writeup has {_fmt_money(want_end)} on {want_trades} trades. "
        f"The comparison below uses this run's paired baseline."
    )


def _reading(books: list[Book]) -> str:
    """Say what a marked row did. The mark itself stays the pre-registered test."""
    bits = []
    clears = False
    for book in books:
        base_oos = book.published.oos_metrics
        base_is = book.published.is_metrics
        for row in book.rows:
            if not row.improves:
                continue
            oos = row.oos_metrics
            ins = row.is_metrics
            pf = oos.get("profit_factor")
            sharpe = oos.get("sharpe")
            trades = int(oos.get("trades") or 0)
            if (
                pf is not None
                and np.isfinite(pf)
                and float(pf) >= 1.10
                and sharpe is not None
                and np.isfinite(sharpe)
                and float(sharpe) >= 0.40
                and trades >= 300
                and float(oos.get("max_drawdown") or -1.0) >= -0.30
            ):
                clears = True
            bits.append(
                f"{LABELS[row.source]} on {book.name} ended at {_fmt_money(oos.get('ending_equity'))} "
                f"against the published {_fmt_money(base_oos.get('ending_equity'))}, "
                f"profit factor {_fmt_pf(pf)}, Sharpe {_fmt_num(sharpe)}, "
                f"drawdown {_fmt_dd(oos.get('max_drawdown'))}. "
                f"In sample it ended at {_fmt_money(ins.get('ending_equity'))} "
                f"against {_fmt_money(base_is.get('ending_equity'))}."
            )
    if not bits:
        return ""
    gate = (
        "One of those rows also clears the profit-factor, Sharpe, drawdown, and trade-count gate. "
        "It is still not selectable from this comparison."
        if clears
        else "None of those rows clears a 1.10 profit factor, a 0.40 Sharpe, a drawdown no worse than -30%, and 300 trades."
    )
    return " ".join(bits) + " " + gate


def _winners(books: list[Book]) -> list[str]:
    found = []
    for book in books:
        for row in book.rows:
            if row.improves:
                found.append(f"{LABELS[row.source]} on {book.name}")
    return found


def render(books: list[Book]) -> str:
    winners = _winners(books)
    if winners:
        verdict = (
            "These rows met the pre-registered improvement test: "
            + "; ".join(winners)
            + ". "
            + _reading(books)
            + " Meeting the test does not make the row the gate. "
            "The comparison was scored after the A-D defaults were already frozen, "
            "so choosing one of these rows now would be after the fact. "
            "None is added to the optional list or the registry."
        )
    else:
        verdict = (
            "No level type, alone or in confluence, met the pre-registered improvement test "
            "on any of these books. The published targets stay the gate."
        )
    parts = [
        "## Support and resistance level set",
        "",
        "DOES NOT CHANGE THE GATE. Setups A, B, C, and D keep the targets already scored. "
        "This section only asks which objective level, used as the profit target on those same signals, "
        "improves the out-of-sample fractional-stock book. The definitions below were frozen before this score. "
        "Nothing was sent to a broker.",
        "",
        verdict,
        "",
        "A level is known only at the close that completes it. Horizontal pivots are the last six confirmed "
        "pivot highs and the last six confirmed pivot lows, four bars on each side, inside 120 bars. "
        "Floor pivots use the prior session's high, low, and close: PP = (H+L+C)/3, R1 = 2×PP−L, S1 = 2×PP−H, "
        "R2 = PP+(H−L), S2 = PP−(H−L). Prior-day high and low are that same session. "
        "A demand or supply zone is a four-bar base no wider than 1.25 ATR followed by a bar whose body is "
        "at least 1 ATR and at least 55% of its range. The level is the near edge of the base. It expires after "
        "60 bars or when a later close trades through the far edge. Fibonacci is 38.2%, 50%, and 61.8% of the "
        "latest confirmed swing, five to 80 bars long, with the end pivot no more than 80 bars old. "
        "The trendline is the rising line through the latest confirmed pivot low and the nearest earlier lower one, "
        "and the falling mirror on pivot highs. A flipped level is a pivot high that a later close has traded above, "
        "or a pivot low that a later close has traded below. Confluence is two or more of those sources within "
        "0.50 ATR; the target is their average. \"Nearest of any source\" takes the closest single-source price.",
        "",
        "The target is the nearest level between 0.5R and 4R from the next open, on the trade side. "
        "If that source has no such level, the target is 2R. Stops, the 20 EMA trail, the hold limit, "
        "the one-position rule, and the 20% risk cap are unchanged. \"Signals with a level\" is the share of "
        "out-of-sample signals that had a level in that range, before the one-position book skipped any. "
        "A row improves the book only when the out-of-sample ending equity is higher, profit factor is not lower, "
        "max drawdown is not worse by more than five points, there are at least 20 trades, and at least 30% of "
        "the out-of-sample signals had a level. In-sample ending equity is shown so a late improvement is visible "
        "next to the training window. It is not used to pick a row.",
        "",
    ]
    for book in books:
        note = _baseline_note(book)
        parts.append(f"### {book.name}")
        parts.append("")
        parts.append(book.blurb)
        if note:
            parts.append("")
            parts.append(note)
        parts.append("")
        parts.append(_table(book))
        parts.append("")
    parts.append(
        "Profit factor gate 1.10, Sharpe gate 0.40, drawdown no worse than -30%, and at least 300 trades "
        "still apply to the published defaults. This level set was not in that gate. "
        "It does not join the optional list or the registry. The default book is still dual momentum."
    )
    return "\n".join(parts).rstrip() + "\n"


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


def save_chart(frame: pd.DataFrame, report_dir: Path) -> Path | None:
    if frame is None or len(frame) < 80:
        return None
    table = build_levels(frame)
    window = frame.iloc[-80:]
    last = len(frame) - 1
    atr_now = float(table.atr[last])
    close = float(frame.iloc[last]["close"])
    if not np.isfinite(atr_now) or atr_now <= 0:
        return None
    fig, ax = plt.subplots(figsize=(12.5, 6.4))
    ax.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    for pos, (_, row) in enumerate(window.iterrows()):
        color = "#3d9e57" if row["close"] >= row["open"] else "#d64545"
        ax.plot([pos, pos], [row["low"], row["high"]], color=color, linewidth=0.8)
        ax.plot([pos, pos], [row["open"], row["close"]], color=color, linewidth=2.6)
    # The line at the last close, drawn across the window. Earlier values jump
    # when a new pivot confirms, so the chart shows the level that is live now.
    live = (
        ("rising trendline", "#4ea3ff", table.trend_support[last]),
        ("falling trendline", "#e0a100", table.trend_resistance[last]),
    )
    colors = {
        "horizontal": "#d0d0d0",
        "floor": "#f2d16b",
        "prior_day": "#7fd1c8",
        "zone": "#c47bff",
        "fib": "#ff8c6b",
        "flipped": "#8fd18a",
    }
    seen: list[float] = []
    for label, color, price in live:
        if not np.isfinite(price) or abs(price - close) > 2.0 * atr_now:
            continue
        ax.axhline(price, color=color, linewidth=1.2, label=label)
        seen.append(float(price))
    for source, color in colors.items():
        kept = 0
        for price in sorted(table.prices(last, source), key=lambda value: abs(value - close)):
            if kept >= 2 or abs(price - close) > 1.5 * atr_now:
                continue
            if any(abs(price - other) <= 0.25 * atr_now for other in seen):
                continue
            ax.axhline(price, color=color, linewidth=0.9, alpha=0.95, label=LABELS[source] if kept == 0 else None)
            seen.append(float(price))
            kept += 1
    ax.set_title("SPY daily levels known at the last close", color="white")
    ax.tick_params(colors="#cccccc")
    for spine in ax.spines.values():
        spine.set_color("#333333")
    ax.legend(facecolor="#161616", edgecolor="#333333", labelcolor="white", loc="upper left")
    fig.tight_layout()
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "readSR_SPY_1d.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    artifact = Path("/opt/cursor/artifacts/setups")
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / path.name).write_bytes(path.read_bytes())
    return path


def _dump(books: list[Book], path: Path) -> None:
    payload = []
    for book in books:
        payload.append(
            {
                "name": book.name,
                "signals": book.signals,
                "rows": [
                    {
                        "source": row.source,
                        "level_share": None if not np.isfinite(row.level_share) else row.level_share,
                        "improves": row.improves,
                        "is": row.is_metrics,
                        "oos": row.oos_metrics,
                    }
                    for row in book.rows
                ],
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json))


def _json(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    return str(value)


def _ab_windows(frames, fraction: float) -> tuple[tuple[date, date], tuple[date, date]]:
    days = _sessions(frames)
    is_days, oos_days = _split(days, fraction)
    return (is_days[0], is_days[-1]), (oos_days[0], oos_days[-1])


def _run_ab(name, frames, daily, extras, execution, fraction, kind: str | None) -> Book:
    params = _cells(execution)[0]
    print(f"detect {name}", flush=True)
    setups = detect_all(frames, daily, extras, params)
    if kind is not None:
        setups = [setup for setup in setups if setup.kind == kind]
    windows = _ab_windows(frames, fraction)
    tables = _tables(frames, {setup.symbol for setup in setups})
    if execution == "60m":
        clock_note = "Hourly history is inside the free Yahoo cap, so the sample is short."
    else:
        clock_note = "This clock is inside the free Yahoo intraday cap."
    blurb = (
        f"{len(setups)} signals. In sample {_day_span(windows[0])}. Out of sample {_day_span(windows[1])}. "
        f"Named large-cap list. Stock only. {clock_note}"
    )
    return _score_book(name, blurb, setups, frames, daily, params, windows, tables, daily_book=False)


def _day_span(window: tuple[date, date]) -> str:
    return f"{window[0].isoformat()} through {window[1].isoformat()}"


def main() -> None:
    provider = YFinanceProvider("data/cache")
    print("loading intraday cache", flush=True)
    daily_short, hourly, m15, m5 = load_yahoo(provider)
    present = [symbol for symbol in daily_short if symbol in hourly and len(hourly[symbol]) > 50]
    daily_short = {symbol: daily_short[symbol] for symbol in present}
    hourly = {symbol: hourly[symbol] for symbol in present if symbol in hourly}
    m15 = {symbol: m15[symbol] for symbol in present if symbol in m15 and len(m15[symbol]) > 30}
    m5 = {symbol: m5[symbol] for symbol in present if symbol in m5 and len(m5[symbol]) > 30}

    print("loading daily history", flush=True)
    daily_frames, missing = load_daily()
    print(f"  daily symbols {len(daily_frames)} missing {missing}", flush=True)

    books = [
        _run_ab("A, 60-minute", hourly, daily_short, {}, "60m", 0.50, "A"),
        _run_ab("B, 60-minute", hourly, daily_short, {}, "60m", 0.50, "B"),
        _run_ab("A and B, 60-minute", hourly, daily_short, {}, "60m", 0.50, None),
        _run_ab("A and B, 15-minute", m15, daily_short, {"60m": hourly}, "15m", 0.60, None),
        _run_ab("A and B, 5-minute", m5, daily_short, {"15m": m15, "60m": hourly}, "5m", 0.60, None),
    ]

    print("detect C", flush=True)
    trend = _collect_daily(daily_frames, find_trend_setups, DAILY_DEFAULTS)
    print(f"  C signals {len(trend)}", flush=True)
    trend_tables = _tables(daily_frames, {setup.symbol for setup in trend})
    daily_windows = ((SCORE_FROM, IS_END), (OOS_START, SAMPLE_END))
    books.append(
        _score_book(
            "C, daily Dow",
            f"{len(trend)} Dow point-in-time long breakout-retest signals from {SCORE_FROM.isoformat()}. "
            f"In sample through {IS_END.isoformat()}. Out of sample {OOS_START.isoformat()} through {SAMPLE_END.isoformat()}.",
            trend,
            daily_frames,
            daily_frames,
            DAILY_DEFAULTS,
            daily_windows,
            trend_tables,
            daily_book=True,
        )
    )
    print("detect D", flush=True)
    breaks = _collect_daily(daily_frames, find_breakout_setups, BREAKOUT_DEFAULTS)
    print(f"  D signals {len(breaks)}", flush=True)
    break_tables = _tables(daily_frames, {setup.symbol for setup in breaks})
    books.append(
        _score_book(
            "D, daily Dow",
            f"{len(breaks)} Dow point-in-time breakout signals from {SCORE_FROM.isoformat()}. "
            f"In sample through {IS_END.isoformat()}. Out of sample {OOS_START.isoformat()} through {SAMPLE_END.isoformat()}.",
            breaks,
            daily_frames,
            daily_frames,
            BREAKOUT_DEFAULTS,
            daily_windows,
            break_tables,
            daily_book=True,
        )
    )

    text = render(books)
    write_report(text, Path("RESULTS.md"))
    _dump(books, Path("reports/chart_reads_sr.json"))
    chart = save_chart(daily_frames.get("SPY"), Path("reports/setups"))
    print(f"chart {chart}", flush=True)
    print("WINNERS", _winners(books), flush=True)


if __name__ == "__main__":
    main()
