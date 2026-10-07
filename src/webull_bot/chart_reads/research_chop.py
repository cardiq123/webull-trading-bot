"""Chop as a no-trade filter and as a breakout precursor. Backtests only.

The combination in ``chop.py`` was frozen before this score. A row that
passes ``filter_helps`` is labeled. It does not replace setups A-D and it
does not join the gate.

Run: ``python -m webull_bot.chart_reads.research_chop``
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
from webull_bot.chart_reads.chop import features, filter_helps, find_chop_breakouts
from webull_bot.chart_reads.detect import Setup, rth
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DAILY_DEFAULTS
from webull_bot.chart_reads.research import (
    _cells,
    _sessions,
    _split,
    _window_book as intraday_window,
    detect_all,
    load_yahoo,
)
from webull_bot.chart_reads.research_breakouts import _split_days
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

START = "<!-- CHART_READS_CHOP_START -->"
END = "<!-- CHART_READS_CHOP_END -->"
DAILY_WATCH = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "UNH"]
EXPECTED = {
    "A, 60-minute": (886.97, 131),
    "B, 60-minute": (921.86, 85),
    "A and B, 60-minute": (967.77, 164),
    "A and B, 15-minute": (1001.48, 10),
    "A and B, 5-minute": (978.07, 11),
    "C, daily Dow": (746.56, 207),
    "D, daily Dow": (919.45, 73),
}
EXPECTED_BREAKOUT = {
    "60m": (888.99, 16),
    "15m": (1005.63, 6),
}


@dataclass
class Side:
    key: str
    label: str
    is_metrics: dict
    oos_metrics: dict
    oos_losers: int
    oos_avg_loss: float
    is_losers: int
    helps: bool | None


@dataclass
class FilterBook:
    name: str
    blurb: str
    signals: int
    oos_signals: int
    oos_inside: int
    sides: list[Side] = field(default_factory=list)

    def side(self, key: str) -> Side:
        for row in self.sides:
            if row.key == key:
                return row
        raise KeyError(key)


@dataclass
class Precursor:
    name: str
    blurb: str
    signals: int
    longs: int
    shorts: int
    is_metrics: dict
    oos_metrics: dict
    oos_losers: int
    oos_avg_loss: float
    baseline_label: str
    baseline_oos: dict | None
    baseline_losers: int | None
    baseline_avg_loss: float | None
    baseline_note: str


@dataclass
class TimeRow:
    symbol: str
    bars: int
    chop_bars: int
    share: float
    strict_share: float
    oos_bars: int
    oos_share: float


def _day(ts) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York")
    return stamp.date()


def _stock(params: dict) -> dict:
    chosen = dict(params)
    chosen["expression"] = "stock"
    return chosen


def _loss(stats) -> tuple[int, float]:
    trades = getattr(stats, "trades", None)
    if trades is None or len(trades) == 0 or "pnl" not in trades.columns:
        return 0, float("nan")
    pnl = trades["pnl"].astype(float)
    losers = pnl[pnl < 0]
    if losers.empty:
        return 0, float("nan")
    return int(len(losers)), float(losers.mean())


def _flag(feat: pd.DataFrame | None, ts, column: str) -> bool | None:
    """Chop state on the signal bar. Missing bars stay in the outside book."""
    if feat is None or len(feat) == 0:
        return None
    pos = feat.index.get_indexer([ts])
    if len(pos) == 0 or int(pos[0]) < 0:
        return None
    value = feat.iloc[int(pos[0])][column]
    if pd.isna(value):
        return None
    return bool(value)


def _partition(setups: list[Setup], feats: dict[str, pd.DataFrame]) -> tuple[list[Setup], list[Setup], list[Setup]]:
    outside: list[Setup] = []
    inside: list[Setup] = []
    outside_strict: list[Setup] = []
    for setup in setups:
        chop = _flag(feats.get(setup.symbol), setup.signal_time, "chop")
        strict = _flag(feats.get(setup.symbol), setup.signal_time, "strict")
        if chop is True:
            inside.append(setup)
        else:
            outside.append(setup)
        if strict is not True:
            outside_strict.append(setup)
    return outside, inside, outside_strict


def _windows_ab(frames, fraction: float) -> tuple[tuple[date, date], tuple[date, date]]:
    days = _sessions(frames)
    is_days, oos_days = _split(days, fraction)
    return (is_days[0], is_days[-1]), (oos_days[0], oos_days[-1])


def _between(setups: list[Setup], start: date, end: date) -> list[Setup]:
    return [setup for setup in setups if start <= _day(setup.fill_time) <= end]


def _score_sides(setups, frames, daily, params, windows, *, daily_book: bool) -> list[tuple[str, object, object]]:
    window = daily_window if daily_book else intraday_window
    is_window, oos_window = windows
    chosen = _stock(params)
    rows = []
    for key, group in setups:
        is_stats = window(group, frames, daily, chosen, "stock", is_window[0], is_window[1])
        oos_stats = window(group, frames, daily, chosen, "stock", oos_window[0], oos_window[1])
        rows.append((key, is_stats, oos_stats))
    return rows


def _filter_book(name, blurb, setups, feats, frames, daily, params, windows, *, daily_book: bool) -> FilterBook:
    is_window, oos_window = windows
    oos_setups = _between(setups, oos_window[0], oos_window[1])
    _, oos_inside, _ = _partition(oos_setups, feats)
    outside, inside, outside_strict = _partition(setups, feats)
    book = FilterBook(
        name=name,
        blurb=blurb,
        signals=len(setups),
        oos_signals=len(oos_setups),
        oos_inside=len(oos_inside),
    )
    groups = (
        ("published", "published entries", setups),
        ("skip", "skip chop", outside),
        ("inside", "inside chop only", inside),
        ("skip_strict", "skip stricter chop", outside_strict),
    )
    print(f"  {name}: {len(setups)} signals, OOS inside {len(oos_inside)}/{len(oos_setups)}", flush=True)
    scored = {
        key: (is_stats, oos_stats)
        for key, is_stats, oos_stats in _score_sides(
            [(key, group) for key, _label, group in groups],
            frames,
            daily,
            params,
            windows,
            daily_book=daily_book,
        )
    }
    published_oos = scored["published"][1]
    base_losers, _ = _loss(published_oos)
    for key, label, _group in groups:
        is_stats, oos_stats = scored[key]
        losers, avg = _loss(oos_stats)
        is_losers, _ = _loss(is_stats)
        helps = None
        if key in ("skip", "skip_strict"):
            helps = filter_helps(published_oos.metrics, oos_stats.metrics, base_losers, losers)
        book.sides.append(
            Side(key, label, is_stats.metrics, oos_stats.metrics, losers, avg, is_losers, helps)
        )
        print(
            f"    {key}: OOS trades {oos_stats.metrics.get('trades')} "
            f"ending {oos_stats.metrics.get('ending_equity')} losers {losers} helps {helps}",
            flush=True,
        )
    return book


def _collect_daily(frames, builder, params) -> list[Setup]:
    found: list[Setup] = []
    for symbol in all_dow_tickers():
        frame = frames.get(symbol)
        if frame is None or len(frame) < 80:
            continue
        setups = builder(frame, params, symbol=symbol)
        setups = [setup for setup in setups if is_member(symbol, _day(setup.signal_time))]
        setups = [setup for setup in setups if _day(setup.fill_time) >= SCORE_FROM]
        found.extend(setups)
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.kind))
    return found


def _collect_chop(frames, symbols, *, pit: bool, earliest: date | None) -> list[Setup]:
    found: list[Setup] = []
    for symbol in symbols:
        frame = frames.get(symbol)
        if frame is None or len(frame) < 80:
            continue
        setups = find_chop_breakouts(frame, symbol=symbol)
        if pit:
            setups = [setup for setup in setups if is_member(symbol, _day(setup.signal_time))]
        if earliest is not None:
            setups = [setup for setup in setups if _day(setup.fill_time) >= earliest]
        found.extend(setups)
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    return found


def _precursor_params(execution: str) -> dict:
    chosen = _stock(BREAKOUT_DEFAULTS)
    if execution == "60m":
        chosen.update(flatten_eod=False, max_hold_sessions=5, pdt_prospective=True)
    elif execution in ("15m", "5m"):
        chosen.update(flatten_eod=True, max_hold_sessions=1, pdt_prospective=True)
    return chosen


def _one_window(setups, frames, daily, params, windows, *, daily_book: bool):
    window = daily_window if daily_book else intraday_window
    is_window, oos_window = windows
    is_stats = window(setups, frames, daily, params, "stock", is_window[0], is_window[1])
    oos_stats = window(setups, frames, daily, params, "stock", oos_window[0], oos_window[1])
    return is_stats, oos_stats


def _baseline_note(name: str, metrics: dict) -> str:
    expected = EXPECTED.get(name)
    ending = float(metrics.get("ending_equity") or 0.0)
    trades = int(metrics.get("trades") or 0)
    if expected is None:
        return ""
    want_end, want_trades = expected
    if abs(ending - want_end) <= 0.02 and trades == want_trades:
        return (
            f"The published-entry row matches the gated out-of-sample stock book "
            f"({_fmt_money(want_end)} on {want_trades} trades)."
        )
    return (
        f"The published-entry row in this run is {_fmt_money(ending)} on {trades} trades. "
        f"The gated writeup has {_fmt_money(want_end)} on {want_trades} trades. "
        "The comparison below uses this run's paired baseline."
    )


def _breakout_note(execution: str, metrics: dict) -> str:
    expected = EXPECTED_BREAKOUT.get(execution)
    ending = float(metrics.get("ending_equity") or 0.0)
    trades = int(metrics.get("trades") or 0)
    if expected is None:
        return "There is no published setup D book on this clock. The chop breakout row stands alone."
    want_end, want_trades = expected
    if abs(ending - want_end) <= 0.02 and trades == want_trades:
        return (
            f"The paired setup D row matches the published out-of-sample stock book "
            f"({_fmt_money(want_end)} on {want_trades} trades)."
        )
    return (
        f"The paired setup D row in this run is {_fmt_money(ending)} on {trades} trades. "
        f"The published writeup has {_fmt_money(want_end)} on {want_trades} trades."
    )


def _feats(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    built = {}
    for symbol, frame in frames.items():
        if frame is None or len(frame) < 40:
            continue
        built[symbol] = features(frame)
    return built


def _rth(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    kept = {}
    for symbol, frame in frames.items():
        if frame is None or len(frame) < 80:
            continue
        bars = rth(frame)
        if bars is not None and len(bars) > 80:
            kept[symbol] = bars
    return kept


def _time_rows(frames: dict[str, pd.DataFrame], oos_start: date, oos_end: date) -> list[TimeRow]:
    rows = []
    for symbol in sorted(frames):
        frame = frames[symbol]
        if frame is None or len(frame) < 40:
            continue
        feat = features(frame)
        ready = feat["rel_volume"].notna() & feat["ema20"].notna() & feat["vwap"].notna() & feat["atr"].notna()
        usable = feat.loc[ready]
        if usable.empty:
            continue
        days = pd.Series([_day(ts) for ts in usable.index], index=usable.index)
        oos = usable.loc[(days >= oos_start) & (days <= oos_end)]
        rows.append(
            TimeRow(
                symbol=symbol,
                bars=int(len(usable)),
                chop_bars=int(usable["chop"].sum()),
                share=float(usable["chop"].mean()),
                strict_share=float(usable["strict"].mean()),
                oos_bars=int(len(oos)),
                oos_share=float(oos["chop"].mean()) if len(oos) else 0.0,
            )
        )
    return rows


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


def _fmt_pct(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.1%}"


def _fmt_exp(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"${float(value):,.2f}"


def _filter_table(book: FilterBook) -> str:
    lines = [
        "| Reading | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Helps |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in book.sides:
        if row.helps is None:
            flag = "—"
        else:
            flag = "yes" if row.helps else "no"
        lines.append(
            "| {label} | {is_trades} | {is_end} | {oos_trades} | {losers} | {avg} | {exp} | {pf} | {sharpe} | {dd} | {oos_end} | {flag} |".format(
                label=row.label,
                is_trades=int(row.is_metrics.get("trades") or 0),
                is_end=_fmt_money(row.is_metrics.get("ending_equity")),
                oos_trades=int(row.oos_metrics.get("trades") or 0),
                losers=row.oos_losers,
                avg=_fmt_exp(row.oos_avg_loss),
                exp=_fmt_exp(row.oos_metrics.get("expectancy")),
                pf=_fmt_pf(row.oos_metrics.get("profit_factor")),
                sharpe=_fmt_num(row.oos_metrics.get("sharpe")),
                dd=_fmt_dd(row.oos_metrics.get("max_drawdown")),
                oos_end=_fmt_money(row.oos_metrics.get("ending_equity")),
                flag=flag,
            )
        )
    return "\n".join(lines)


def _time_table(rows: list[TimeRow]) -> str:
    lines = [
        "| Symbol | Bars | Chop bars | Share | Strict share | OOS bars | OOS share |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.symbol} | {row.bars} | {row.chop_bars} | {_fmt_pct(row.share)} | {_fmt_pct(row.strict_share)} | {row.oos_bars} | {_fmt_pct(row.oos_share)} |"
        )
    return "\n".join(lines)


def _median_share(rows: list[TimeRow]) -> str:
    if not rows:
        return "No symbols had a defined chop reading."
    shares = sorted(row.share for row in rows)
    oos = sorted(row.oos_share for row in rows)
    mid = shares[len(shares) // 2]
    oos_mid = oos[len(oos) // 2]
    return (
        f"{len(rows)} symbols. Median time in chop {_fmt_pct(mid)} "
        f"(out-of-sample median {_fmt_pct(oos_mid)})."
    )


def _clears(metrics: dict) -> bool:
    pf = metrics.get("profit_factor")
    sharpe = metrics.get("sharpe")
    trades = int(metrics.get("trades") or 0)
    dd = metrics.get("max_drawdown")
    return bool(
        pf is not None
        and np.isfinite(pf)
        and float(pf) >= 1.10
        and sharpe is not None
        and np.isfinite(sharpe)
        and float(sharpe) >= 0.40
        and trades >= 300
        and dd is not None
        and np.isfinite(dd)
        and float(dd) >= -0.30
    )


def _filter_reading(books: list[FilterBook]) -> str:
    helped = []
    for book in books:
        base = book.side("published")
        for key in ("skip", "skip_strict"):
            row = book.side(key)
            if not row.helps:
                continue
            helped.append(
                f"{row.label} on {book.name} raised out-of-sample expectancy from "
                f"{_fmt_exp(base.oos_metrics.get('expectancy'))} to {_fmt_exp(row.oos_metrics.get('expectancy'))} "
                f"and cut losing trades from {base.oos_losers} to {row.oos_losers}. "
                f"Ending equity {_fmt_money(row.oos_metrics.get('ending_equity'))} against "
                f"{_fmt_money(base.oos_metrics.get('ending_equity'))}, "
                f"profit factor {_fmt_pf(row.oos_metrics.get('profit_factor'))}, "
                f"Sharpe {_fmt_num(row.oos_metrics.get('sharpe'))}. "
                f"In sample it ended at {_fmt_money(row.is_metrics.get('ending_equity'))} "
                f"against {_fmt_money(base.is_metrics.get('ending_equity'))}, "
                f"with {row.is_losers} losing trades against {base.is_losers}."
            )
    if not helped:
        return (
            "Skipping chop did not meet that test on any A-D book, and the stricter ADX or choppiness cut did not either. "
            "Inside-chop rows are the other half of the same signals. They are a diagnostic, not a second entry rule."
        )
    gate = (
        "One labeled row also clears a 1.10 profit factor, a 0.40 Sharpe, a drawdown no worse than -30%, and 300 trades. "
        "The label still does not make it the gate."
        if any(_clears(book.side(key).oos_metrics) for book in books for key in ("skip", "skip_strict") if book.side(key).helps)
        else "None of the labeled rows clears a 1.10 profit factor, a 0.40 Sharpe, a drawdown no worse than -30%, and 300 trades."
    )
    same = []
    for book in books:
        skip = book.side("skip")
        strict = book.side("skip_strict")
        if not skip.helps or not strict.helps:
            continue
        if skip.oos_losers == strict.oos_losers and skip.oos_metrics.get("ending_equity") == strict.oos_metrics.get("ending_equity"):
            same.append(book.name)
    same_note = ""
    if same:
        same_note = " The labeled skip and stricter rows are the same book on " + " and ".join(same) + "."
    return " ".join(helped) + " " + gate + same_note + " The stricter cut is a sensitivity. It is not selectable."


def _precursor_table(row: Precursor) -> str:
    lines = [
        "| Book | Signals | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines.append(
        "| {label} | {signals} | {is_trades} | {is_end} | {oos_trades} | {losers} | {avg} | {exp} | {pf} | {sharpe} | {dd} | {oos_end} |".format(
            label="chop breakout",
            signals=row.signals,
            is_trades=int(row.is_metrics.get("trades") or 0),
            is_end=_fmt_money(row.is_metrics.get("ending_equity")),
            oos_trades=int(row.oos_metrics.get("trades") or 0),
            losers=row.oos_losers,
            avg=_fmt_exp(row.oos_avg_loss),
            exp=_fmt_exp(row.oos_metrics.get("expectancy")),
            pf=_fmt_pf(row.oos_metrics.get("profit_factor")),
            sharpe=_fmt_num(row.oos_metrics.get("sharpe")),
            dd=_fmt_dd(row.oos_metrics.get("max_drawdown")),
            oos_end=_fmt_money(row.oos_metrics.get("ending_equity")),
        )
    )
    if row.baseline_oos is not None:
        lines.append(
            "| {label} | — | — | — | {oos_trades} | {losers} | {avg} | {exp} | {pf} | {sharpe} | {dd} | {oos_end} |".format(
                label=row.baseline_label,
                oos_trades=int(row.baseline_oos.get("trades") or 0),
                losers="—" if row.baseline_losers is None else row.baseline_losers,
                avg=_fmt_exp(row.baseline_avg_loss),
                exp=_fmt_exp(row.baseline_oos.get("expectancy")),
                pf=_fmt_pf(row.baseline_oos.get("profit_factor")),
                sharpe=_fmt_num(row.baseline_oos.get("sharpe")),
                dd=_fmt_dd(row.baseline_oos.get("max_drawdown")),
                oos_end=_fmt_money(row.baseline_oos.get("ending_equity")),
            )
        )
    return "\n".join(lines)


def render(books: list[FilterBook], times: dict[str, list[TimeRow]], precursors: list[Precursor], charts: list[Path]) -> str:
    parts = [
        "## Chop filter",
        "",
        "DOES NOT CHANGE THE GATE. Setups A, B, C, and D keep the entries already scored. "
        "This section asks two questions that were frozen before the score. "
        "First, do those books get better if a signal is skipped while the bar is chop? "
        "Second, is a breakout from that chop, on expanding volume, a useful entry next to setup D? "
        "Nothing was sent to a broker.",
        "",
        "A bar is chop only when four readings are true together at that close. "
        "Volume is quiet: the bar is under 0.80 times the prior 20-bar average, or that 20-bar average is itself "
        "under 0.80 times the prior 60-bar average and the bar is still at most 1.20 times its own 20-bar average. "
        "The range is narrow: Bollinger bandwidth (20, 2 standard deviations) is in the bottom 20% of the last 120 bars, "
        "or the bar's range is under 0.75 times the prior 20-bar average range. "
        "The 9 and 20 EMAs are tangled: they sit within 0.35 ATR, the 20 EMA moved less than 0.50 ATR over 10 bars, "
        "and they crossed at least three times in 20 bars. "
        "Price crossed VWAP at least three times in 20 bars. Intraday VWAP resets each session. Daily VWAP is the 20-bar rolling VWAP. "
        "ADX under 20 or a 14-bar choppiness index above 61.8 is a stricter sensitivity. It is not required for the default flag.",
        "",
        "The no-trade filter helps only when out-of-sample expectancy is higher, the book took fewer losing trades, "
        "and at least 20 trades remain. That label is not a new gate. "
        "\"Inside chop only\" is the complement, so the two rows show the same signals split by the flag. "
        "A signal whose bar is missing from the chop series stays in the published book and in the skip book.",
        "",
        _filter_reading(books),
        "",
    ]
    for book in books:
        note = _baseline_note(book.name, book.side("published").oos_metrics)
        parts.append(f"### {book.name}")
        parts.append("")
        parts.append(book.blurb)
        if note:
            parts.append("")
            parts.append(note)
        parts.append("")
        parts.append(_filter_table(book))
        parts.append("")
    parts.append("## Time in chop")
    parts.append("")
    parts.append(
        "Share is the fraction of bars where relative volume, the 20 EMA, VWAP, and ATR are already defined. "
        "Daily bars are the full Yahoo history used for setups C and D. "
        "The daily out-of-sample window is 2019-01-01 through 2026-10-06. "
        "Intraday shares use regular trading hours. Their out-of-sample window is the same split as the A and B filter above."
    )
    parts.append("")
    labels = (
        ("daily", "Daily"),
        ("60m", "60-minute"),
        ("15m", "15-minute"),
        ("5m", "5-minute"),
    )
    for key, label in labels:
        rows = times.get(key) or []
        parts.append(f"### {label}")
        parts.append("")
        parts.append(_median_share(rows))
        parts.append("")
        if rows:
            parts.append(_time_table(rows))
            parts.append("")
    parts.append("## Chop breakout")
    parts.append("")
    parts.append(
        "The precursor is a close out of a low-volume chop box. The box is the prior 10 bars, at least 6 of them chop, "
        "and the box height is between 0.40 and 6 ATR. The close is at least 0.10 ATR beyond the box, "
        "volume is above 1.5 times the prior 20-bar average, and the candle is confirming "
        "(body at least half the range, close in the outer third). "
        "The fill is the next open. The stop is the signal bar's low on a long and its high on a short. "
        "The target is the box height measured from the broken side when that distance is at least 0.5R, otherwise 2R, "
        "the same measured-move rule as setup D. A new signal waits 10 bars. "
        "Daily holds match setup D (up to 30 sessions, no same-day flatten). "
        "Sixty-minute holds last up to 5 sessions. Fifteen-minute and five-minute trades flatten the same session."
    )
    parts.append("")
    for row in precursors:
        parts.append(f"### {row.name}")
        parts.append("")
        parts.append(row.blurb)
        if row.baseline_note:
            parts.append("")
            parts.append(row.baseline_note)
        parts.append("")
        parts.append(_precursor_table(row))
        parts.append("")
    if charts:
        names = ", ".join(f"`reports/setups/{path.name}`" for path in charts)
        parts.append(f"Example chop windows: {names}.")
        parts.append("")
    parts.append(
        "Profit factor gate 1.10, Sharpe gate 0.40, drawdown no worse than -30%, and at least 300 trades "
        "still apply to the published defaults. Chop was not in that gate. "
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


def _runs(flags: np.ndarray) -> list[tuple[int, int]]:
    found = []
    start = None
    for index, flag in enumerate(flags):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            found.append((start, index))
            start = None
    if start is not None:
        found.append((start, len(flags)))
    return found


def _pick_run(frames: dict[str, pd.DataFrame], symbols: list[str]):
    best = None
    for symbol in symbols:
        frame = frames.get(symbol)
        if frame is None or len(frame) < 80:
            continue
        feat = features(frame)
        runs = _runs(feat["chop"].to_numpy(dtype=bool))
        if not runs:
            continue
        start, stop = max(runs, key=lambda pair: (pair[1] - pair[0], -pair[0]))
        length = stop - start
        if best is None or length > best[0] or (length == best[0] and symbol < best[1]):
            best = (length, symbol, frame, feat, start, stop)
    return best


def _save_chop_chart(picked, path: Path, title: str) -> None:
    _length, _symbol, frame, feat, start, stop = picked
    pad_left = max(0, start - 20)
    pad_right = min(len(frame), stop + 12)
    if pad_right - pad_left > 160:
        pad_left = max(0, start - 30)
        pad_right = min(len(frame), stop + 20)
    window = frame.iloc[pad_left:pad_right]
    feat_w = feat.iloc[pad_left:pad_right]
    fig, (ax, vol) = plt.subplots(
        2,
        1,
        figsize=(12.5, 7.2),
        sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1.0]},
    )
    ax.set_facecolor("#161616")
    vol.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    flags = feat_w["chop"].to_numpy(dtype=bool)
    for pos, flag in enumerate(flags):
        if flag:
            ax.axvspan(pos - 0.5, pos + 0.5, color="#f2d16b", alpha=0.28, linewidth=0)
            vol.axvspan(pos - 0.5, pos + 0.5, color="#f2d16b", alpha=0.28, linewidth=0)
    for pos, (_, row) in enumerate(window.iterrows()):
        color = "#3d9e57" if row["close"] >= row["open"] else "#d64545"
        ax.plot([pos, pos], [row["low"], row["high"]], color=color, linewidth=0.8)
        ax.plot([pos, pos], [row["open"], row["close"]], color=color, linewidth=2.6)
    xs = np.arange(len(window))
    ax.plot(xs, feat_w["ema9"].to_numpy(dtype=float), color="#4ea3ff", linewidth=1.0, label="EMA 9")
    ax.plot(xs, feat_w["ema20"].to_numpy(dtype=float), color="#e0a100", linewidth=1.0, label="EMA 20")
    ax.plot(xs, feat_w["vwap"].to_numpy(dtype=float), color="#7fd1c8", linewidth=1.0, label="VWAP")
    colors = ["#3d9e57" if row["close"] >= row["open"] else "#d64545" for _, row in window.iterrows()]
    vol.bar(xs, window["volume"].to_numpy(dtype=float), color=colors, width=0.7)
    first = pd.Timestamp(window.index[start - pad_left])
    last = pd.Timestamp(window.index[stop - pad_left - 1])
    ax.set_title(f"{title}, {first.date().isoformat()} through {last.date().isoformat()}", color="white")
    ax.tick_params(colors="#cccccc")
    vol.tick_params(colors="#cccccc")
    for spine in (*ax.spines.values(), *vol.spines.values()):
        spine.set_color("#333333")
    ax.legend(facecolor="#161616", edgecolor="#333333", labelcolor="white", loc="upper left")
    step = max(1, len(window) // 6)
    ticks = list(range(0, len(window), step))
    if ticks[-1] != len(window) - 1:
        ticks.append(len(window) - 1)
    stamps = [pd.Timestamp(window.index[pos]) for pos in ticks]
    intraday = len({stamp.date() for stamp in stamps}) < len(stamps)
    fmt = "%m-%d %H:%M" if intraday else "%Y-%m-%d"
    vol.set_xticks(ticks)
    vol.set_xticklabels([stamp.strftime(fmt) for stamp in stamps], rotation=30, ha="right")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def save_charts(daily, hourly, m15, report_dir: Path) -> list[Path]:
    saved = []
    jobs = (
        (_pick_run(daily, [symbol for symbol in DAILY_WATCH if symbol in daily]), "1d", "daily"),
        (_pick_run(hourly, sorted(hourly)), "60m", "60-minute"),
        (_pick_run(m15, sorted(m15)), "15m", "15-minute"),
    )
    artifact = Path("/opt/cursor/artifacts/setups")
    artifact.mkdir(parents=True, exist_ok=True)
    for picked, clock, label in jobs:
        if picked is None:
            continue
        symbol = picked[1]
        path = report_dir / f"readCHOP_{symbol}_{clock}.png"
        _save_chop_chart(picked, path, f"{symbol} {label} chop")
        (artifact / path.name).write_bytes(path.read_bytes())
        saved.append(path)
        print(f"chart {path.name} run {picked[0]} bars", flush=True)
    return saved


def _dump(books, times, precursors, path: Path) -> None:
    payload = {
        "filters": [
            {
                "name": book.name,
                "signals": book.signals,
                "oos_signals": book.oos_signals,
                "oos_inside": book.oos_inside,
                "sides": [
                    {
                        "key": side.key,
                        "helps": side.helps,
                        "oos_losers": side.oos_losers,
                        "oos_avg_loss": side.oos_avg_loss,
                        "is_losers": side.is_losers,
                        "is": side.is_metrics,
                        "oos": side.oos_metrics,
                    }
                    for side in book.sides
                ],
            }
            for book in books
        ],
        "time": {
            clock: [row.__dict__ for row in rows]
            for clock, rows in times.items()
        },
        "precursors": [
            {
                "name": row.name,
                "signals": row.signals,
                "longs": row.longs,
                "shorts": row.shorts,
                "oos_losers": row.oos_losers,
                "oos_avg_loss": row.oos_avg_loss,
                "is": row.is_metrics,
                "oos": row.oos_metrics,
                "baseline_label": row.baseline_label,
                "baseline_oos": row.baseline_oos,
                "baseline_losers": row.baseline_losers,
                "baseline_avg_loss": row.baseline_avg_loss,
                "baseline_note": row.baseline_note,
            }
            for row in precursors
        ],
    }
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


def _run_ab(name, frames, rth_frames, daily, extras, execution, fraction, kind):
    params = _cells(execution)[0]
    print(f"detect {name}", flush=True)
    setups = detect_all(frames, daily, extras, params)
    if kind is not None:
        setups = [setup for setup in setups if setup.kind == kind]
    windows = _windows_ab(frames, fraction)
    feats = _feats(rth_frames)
    if execution == "60m":
        clock_note = "Hourly history is inside the free Yahoo cap, so the sample is short."
    else:
        clock_note = "This clock is inside the free Yahoo intraday cap."
    blurb = (
        f"{len(setups)} signals. In sample {_span(windows[0])}. Out of sample {_span(windows[1])}. "
        f"Named large-cap list. Stock only. {clock_note}"
    )
    return _filter_book(name, blurb, setups, feats, frames, daily, params, windows, daily_book=False), windows


def _span(window: tuple[date, date]) -> str:
    return f"{window[0].isoformat()} through {window[1].isoformat()}"


def _precursor(name, blurb, setups, frames, daily, params, windows, *, daily_book: bool, baseline, baseline_label: str, note: str) -> Precursor:
    print(f"precursor {name}: {len(setups)} signals", flush=True)
    is_stats, oos_stats = _one_window(setups, frames, daily, params, windows, daily_book=daily_book)
    losers, avg = _loss(oos_stats)
    base_metrics = None
    base_losers = None
    base_avg = None
    if baseline is not None:
        _base_is, base_oos = _one_window(baseline, frames, daily, params, windows, daily_book=daily_book)
        base_metrics = base_oos.metrics
        base_losers, base_avg = _loss(base_oos)
        print(
            f"  baseline OOS trades {base_metrics.get('trades')} ending {base_metrics.get('ending_equity')}",
            flush=True,
        )
    print(
        f"  chop OOS trades {oos_stats.metrics.get('trades')} ending {oos_stats.metrics.get('ending_equity')}",
        flush=True,
    )
    return Precursor(
        name=name,
        blurb=blurb,
        signals=len(setups),
        longs=sum(1 for setup in setups if setup.direction == "long"),
        shorts=sum(1 for setup in setups if setup.direction == "short"),
        is_metrics=is_stats.metrics,
        oos_metrics=oos_stats.metrics,
        oos_losers=losers,
        oos_avg_loss=avg,
        baseline_label=baseline_label,
        baseline_oos=base_metrics,
        baseline_losers=base_losers,
        baseline_avg_loss=base_avg,
        baseline_note=note if baseline is None else "",
    )


def main() -> None:
    provider = YFinanceProvider("data/cache")
    print("loading intraday cache", flush=True)
    daily_short, hourly, m15, m5 = load_yahoo(provider)
    present = [symbol for symbol in daily_short if symbol in hourly and len(hourly[symbol]) > 50]
    daily_short = {symbol: daily_short[symbol] for symbol in present}
    hourly = {symbol: hourly[symbol] for symbol in present if symbol in hourly}
    m15 = {symbol: m15[symbol] for symbol in present if symbol in m15 and len(m15[symbol]) > 30}
    m5 = {symbol: m5[symbol] for symbol in present if symbol in m5 and len(m5[symbol]) > 30}
    hourly_rth = _rth(hourly)
    m15_rth = _rth(m15)
    m5_rth = _rth(m5)

    print("loading daily history", flush=True)
    daily_frames, missing = load_daily()
    print(f"  daily symbols {len(daily_frames)} missing {missing}", flush=True)
    print("daily chop features", flush=True)
    daily_feats = _feats(daily_frames)

    books = []
    ab60, win60 = _run_ab("A, 60-minute", hourly, hourly_rth, daily_short, {}, "60m", 0.50, "A")
    books.append(ab60)
    books.append(_run_ab("B, 60-minute", hourly, hourly_rth, daily_short, {}, "60m", 0.50, "B")[0])
    books.append(_run_ab("A and B, 60-minute", hourly, hourly_rth, daily_short, {}, "60m", 0.50, None)[0])
    ab15, win15 = _run_ab("A and B, 15-minute", m15, m15_rth, daily_short, {"60m": hourly}, "15m", 0.60, None)
    books.append(ab15)
    ab5, win5 = _run_ab("A and B, 5-minute", m5, m5_rth, daily_short, {"15m": m15, "60m": hourly}, "5m", 0.60, None)
    books.append(ab5)

    print("detect C", flush=True)
    trend = _collect_daily(daily_frames, find_trend_setups, DAILY_DEFAULTS)
    print(f"  C signals {len(trend)}", flush=True)
    daily_windows = ((SCORE_FROM, IS_END), (OOS_START, SAMPLE_END))
    books.append(
        _filter_book(
            "C, daily Dow",
            f"{len(trend)} Dow point-in-time long breakout-retest signals from {SCORE_FROM.isoformat()}. "
            f"In sample through {IS_END.isoformat()}. Out of sample {OOS_START.isoformat()} through {SAMPLE_END.isoformat()}.",
            trend,
            daily_feats,
            daily_frames,
            daily_frames,
            DAILY_DEFAULTS,
            daily_windows,
            daily_book=True,
        )
    )
    print("detect D", flush=True)
    breaks = _collect_daily(daily_frames, find_breakout_setups, BREAKOUT_DEFAULTS)
    print(f"  D signals {len(breaks)}", flush=True)
    books.append(
        _filter_book(
            "D, daily Dow",
            f"{len(breaks)} Dow point-in-time breakout signals from {SCORE_FROM.isoformat()}. "
            f"In sample through {IS_END.isoformat()}. Out of sample {OOS_START.isoformat()} through {SAMPLE_END.isoformat()}.",
            breaks,
            daily_feats,
            daily_frames,
            daily_frames,
            BREAKOUT_DEFAULTS,
            daily_windows,
            daily_book=True,
        )
    )

    print("time in chop", flush=True)
    times = {
        "daily": _time_rows(daily_frames, OOS_START, SAMPLE_END),
        "60m": _time_rows(hourly_rth, win60[1][0], win60[1][1]),
        "15m": _time_rows(m15_rth, win15[1][0], win15[1][1]),
        "5m": _time_rows(m5_rth, win5[1][0], win5[1][1]),
    }

    print("chop breakouts", flush=True)
    precursors = []
    daily_chop = _collect_chop(daily_frames, [symbol for symbol in all_dow_tickers() if symbol in daily_frames], pit=True, earliest=SCORE_FROM)
    daily_params = _precursor_params("1d")
    d_book = books[-1]
    precursors.append(
        Precursor(
            name="Daily Dow, chop breakout",
            blurb=(
                f"{len(daily_chop)} Dow point-in-time chop breakouts from {SCORE_FROM.isoformat()} "
                f"({sum(1 for setup in daily_chop if setup.direction == 'long')} long, "
                f"{sum(1 for setup in daily_chop if setup.direction == 'short')} short). "
                f"In sample through {IS_END.isoformat()}. Out of sample {OOS_START.isoformat()} through {SAMPLE_END.isoformat()}. "
                "The setup D row is the published-entry book from the filter above, same exits."
            ),
            signals=len(daily_chop),
            longs=sum(1 for setup in daily_chop if setup.direction == "long"),
            shorts=sum(1 for setup in daily_chop if setup.direction == "short"),
            is_metrics={},
            oos_metrics={},
            oos_losers=0,
            oos_avg_loss=float("nan"),
            baseline_label="setup D, published entries",
            baseline_oos=d_book.side("published").oos_metrics,
            baseline_losers=d_book.side("published").oos_losers,
            baseline_avg_loss=d_book.side("published").oos_avg_loss,
            baseline_note="",
        )
    )
    is_stats, oos_stats = _one_window(daily_chop, daily_frames, daily_frames, daily_params, daily_windows, daily_book=True)
    losers, avg = _loss(oos_stats)
    precursors[-1].is_metrics = is_stats.metrics
    precursors[-1].oos_metrics = oos_stats.metrics
    precursors[-1].oos_losers = losers
    precursors[-1].oos_avg_loss = avg
    precursors[-1].baseline_note = _baseline_note("D, daily Dow", d_book.side("published").oos_metrics)
    print(
        f"  daily chop OOS trades {oos_stats.metrics.get('trades')} ending {oos_stats.metrics.get('ending_equity')}",
        flush=True,
    )

    for execution, frames, label in (
        ("60m", hourly_rth, "60-minute"),
        ("15m", m15_rth, "15-minute"),
        ("5m", m5_rth, "5-minute"),
    ):
        params = _precursor_params(execution)
        symbols = list(frames)
        chop_setups = _collect_chop(frames, symbols, pit=False, earliest=None)
        start, is_end, oos_start, end, sessions = _split_days(frames)
        windows = ((start, is_end), (oos_start, end))
        baseline = None
        note = ""
        if execution == "5m":
            note = "There is no published setup D book on the 5-minute clock. This row is anecdotal."
        else:
            baseline = []
            for symbol in symbols:
                baseline.extend(find_breakout_setups(frames[symbol], BREAKOUT_DEFAULTS, symbol=symbol))
            baseline.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.kind))
        blurb = (
            f"{len(chop_setups)} chop breakout{'s' if len(chop_setups) != 1 else ''} on the named list "
            f"({sum(1 for setup in chop_setups if setup.direction == 'long')} long, "
            f"{sum(1 for setup in chop_setups if setup.direction == 'short')} short). "
            f"{sessions} sessions, {_span((start, end))}. In sample through {is_end.isoformat()}. "
            f"Out of sample {oos_start.isoformat()} through {end.isoformat()}."
        )
        row = _precursor(
            f"{label}, chop breakout",
            blurb,
            chop_setups,
            frames,
            daily_short,
            params,
            windows,
            daily_book=False,
            baseline=baseline,
            baseline_label="setup D, same window",
            note=note,
        )
        if baseline is not None:
            row.baseline_note = _breakout_note(execution, row.baseline_oos or {})
        precursors.append(row)

    charts = save_charts(daily_frames, hourly_rth, m15_rth, Path("reports/setups"))
    text = render(books, times, precursors, charts)
    write_report(text, Path("RESULTS.md"))
    _dump(books, times, precursors, Path("reports/chart_reads_chop.json"))
    print("HELPS", [f"{book.name}:{side.key}" for book in books for side in book.sides if side.helps], flush=True)


if __name__ == "__main__":
    main()
