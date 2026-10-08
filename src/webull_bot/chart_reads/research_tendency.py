"""Run the frozen per-stock tendency study and write the report.

Research only. Yahoo intraday names are a short sample and are not trials.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from webull_bot.chart_reads.open_support import daily_from_intraday
from webull_bot.chart_reads.tendency import (
    HOLDOUT_END,
    HOLDOUT_START,
    INTRADAY_GATE,
    SYMBOLS,
    TRAIN_END,
    TRAIN_START,
    frozen_rules,
    n_trials,
    plain_personality,
    prepare,
    run_search,
    score_holdout,
    short_sample,
    trade_books,
)
from webull_bot.data.yfinance_provider import YFinanceProvider

START_MARK = "<!-- TENDENCY_START -->"
END_MARK = "<!-- TENDENCY_END -->"
CACHE = Path("data/cache/tendency")
NY = "America/New_York"


def _to_fifteen(five: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    for _day, chunk in five.groupby(five.index.date):
        bars = chunk.resample("15min", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )
        bars = bars.dropna(subset=["open"])
        if not bars.empty:
            pieces.append(bars)
    if not pieces:
        return five.iloc[0:0]
    return pd.concat(pieces)


def _load_daily() -> dict[str, pd.DataFrame]:
    provider = YFinanceProvider(CACHE)
    history = provider.history(list(SYMBOLS), "2016-01-01", "2026-10-09", interval="1d")
    frames = {}
    for symbol, frame in history.items():
        if frame is None or frame.empty:
            continue
        frames[symbol] = frame.sort_index()
    return frames


def _load_gate_intraday() -> dict[str, dict[str, pd.DataFrame]]:
    found = {}
    for symbol in INTRADAY_GATE:
        path = Path(f"data/cache/open_support/{symbol}_duka_5m.pkl")
        if not path.exists():
            raise RuntimeError(f"missing Dukascopy 5-minute cache for {symbol}")
        five = pd.read_pickle(path).sort_index()
        found[symbol] = {"5m": five, "15m": _to_fifteen(five)}
    return found


def _load_yahoo_intraday(symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    provider = YFinanceProvider(CACHE)
    try:
        return provider.history(list(symbols), "2026-08-01", "2026-10-09", interval="5m")
    except Exception as exc:
        print(f"yahoo 5m failed {exc}", flush=True)
        return {}


def _vix() -> dict[date, float]:
    path = Path("data/cache/survey/_VIX_1d.csv")
    if not path.exists():
        path = Path("data/cache/_VIX_1d.csv")
    frame = pd.read_csv(path, parse_dates=["Date"])
    return {pd.Timestamp(stamp).date(): float(close) for stamp, close in zip(frame["Date"], frame["close"])}


def _prepare_all(daily: dict[str, pd.DataFrame], intraday: dict[str, dict[str, pd.DataFrame]]) -> dict[str, dict[str, pd.DataFrame]]:
    prepared: dict[str, dict[str, pd.DataFrame]] = {}
    for symbol, frame in daily.items():
        built = prepare(frame, frame, "1d")
        if built is not None:
            prepared.setdefault(symbol, {})["1d"] = built
    for symbol, tapes in intraday.items():
        tape_daily = daily_from_intraday(tapes["5m"])
        for timeframe, frame in tapes.items():
            built = prepare(frame, tape_daily, timeframe)
            if built is not None:
                prepared.setdefault(symbol, {})[timeframe] = built
    return prepared


def _money(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"${float(value):,.0f}"


def _pct(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.1%}"


def _num(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.2f}"


def _best_row(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    reverting = [row for row in rows if row["label"] == "mean-reverting"]
    if reverting:
        return sorted(reverting, key=lambda row: (row["q"], -row["mean_signed"]))[0]
    usable = [row for row in rows if row["n"] >= 30]
    pool = usable or rows
    return sorted(pool, key=lambda row: (-row["mean_signed"], -row["n"]))[0]


def _chart_unh(path: Path, five: pd.DataFrame | None, daily: pd.DataFrame | None) -> str:
    target = date(2026, 10, 8)
    if five is None or five.empty or daily is None:
        return "UNH 5-minute bars were missing, so there is no example chart."
    days = sorted({stamp.date() for stamp in five.index})
    chart_day = target if target in days else days[-1]
    session = five[five.index.date == chart_day]
    tape_daily = daily_from_intraday(five)
    if chart_day not in set(tape_daily.index):
        tape_daily.loc[chart_day] = {"open": np.nan, "high": np.nan, "low": np.nan, "close": np.nan, "volume": np.nan, "vwap": np.nan}
        tape_daily = tape_daily.sort_index()
    # Prefer the long Yahoo daily file for RSI warmup, and the session VWAP from the 5-minute bars.
    merged = daily.copy()
    merged.index = [stamp.date() if hasattr(stamp, "date") else stamp for stamp in merged.index]
    if chart_day not in set(merged.index):
        merged.loc[chart_day] = {column: np.nan for column in merged.columns}
        merged = merged.sort_index()
    prepared = prepare(five, merged, "5m")
    note = "the session was not prepared"
    if prepared is not None:
        day_mask = prepared["session"] == chart_day
        chunk = prepared.loc[day_mask]
        if not chunk.empty:
            dip = chunk["close"] < chunk["vwap"] - 2.0 * chunk["band"]
            rsi_dip = chunk["rsi"] < 30
            last = chunk.iloc[-1]
            note = (
                f"last close {float(last['close']):.2f}, RSI {float(last['rsi']):.1f}, "
                f"VWAP {float(last['vwap']):.2f}, lower band {float(last['vwap'] - 2 * last['band']):.2f}. "
                f"A 2 SD dip printed on {int(dip.fillna(False).sum())} bars and RSI below 30 on {int(rsi_dip.fillna(False).sum())} bars"
            )
            fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
            axes[0].plot(range(len(chunk)), chunk["close"].to_numpy(dtype=float), color="#1f4b99", label="close")
            axes[0].plot(range(len(chunk)), chunk["vwap"].to_numpy(dtype=float), color="#888888", label="VWAP")
            lower = chunk["vwap"].to_numpy(dtype=float) - 2.0 * chunk["band"].to_numpy(dtype=float)
            upper = chunk["vwap"].to_numpy(dtype=float) + 2.0 * chunk["band"].to_numpy(dtype=float)
            axes[0].plot(range(len(chunk)), lower, color="#a33b20", linestyle="--", label="VWAP - 2 SD")
            axes[0].plot(range(len(chunk)), upper, color="#a33b20", linestyle=":", label="VWAP + 2 SD")
            axes[0].legend(loc="best")
            axes[0].set_ylabel("Price")
            axes[1].plot(range(len(chunk)), chunk["rsi"].to_numpy(dtype=float), color="#1f4b99")
            axes[1].axhline(30, color="#a33b20", linestyle="--")
            axes[1].axhline(70, color="#888888", linestyle="--")
            axes[1].set_ylabel("RSI(14)")
            partial = ""
            if chart_day == target and session.index[-1].hour < 15:
                partial = " The session is partial."
            if chart_day != target:
                partial = " 2026-10-08 was not in the file."
            fig.suptitle(f"UNH 5-minute, {chart_day.isoformat()}.{partial}")
            fig.tight_layout()
            fig.savefig(path, dpi=120)
            plt.close(fig)
            return f"Example chart `{path.as_posix()}`: {note}.{partial}"
    if not session.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(range(len(session)), session["close"].to_numpy(dtype=float))
        ax.set_title(f"UNH 5-minute close, {chart_day.isoformat()}")
        fig.tight_layout()
        fig.savefig(path, dpi=120)
        plt.close(fig)
    return f"UNH chart saved without bands. {note}"


def _render(search: dict, books: list[dict], samples: list[dict], chart_note: str) -> str:
    cells = search["cells"]
    reverting = [row for row in cells if row["label"] == "mean-reverting"]
    trending = [row for row in cells if row["label"] == "trending"]
    confirmed = [row for row in cells if row.get("confirmed")]
    if confirmed:
        lead = f"{len(confirmed)} personalities were confirmed on the holdout."
    elif reverting or trending:
        lead = (
            f"{len(reverting)} mean-reverting and {len(trending)} trending cells cleared the training FDR. "
            "None kept the same sign on the holdout with enough events."
        )
    else:
        lead = (
            f"No stock showed a consistent dip or rip personality. {search['n_combos']} combinations were counted. "
            "The bar was not loosened after the scores."
        )
    lines = [
        START_MARK,
        "### Stock tendencies",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. No sandbox book was added.",
        "",
        lead,
        "",
        "A dip or a rip is an edge: the first bar that closes outside the band, through RSI 30 or 70, "
        "a session move of 1 or 1.5 prior-day ATRs, a gap of 1 ATR, or a three-session move of 1.5 ATR. "
        "Intraday VWAP is the session VWAP. The daily band is the 20-day volume-weighted average, because a daily bar has no session VWAP. "
        "Forward closes are 30 minutes, 60 minutes, the session close, the next session, and three and five sessions, where the bar size allows it. "
        "Each cell is compared with a seed-17 random bar at the same clock. "
        "Mean-reverting means at least 30 training events, q ≤ 0.10, a positive reversal edge, and a higher reversal rate than the random bars. "
        "Trending is the mirror. The holdout, 2026-07-07 through 2026-10-06, was scored once and had to keep the sign.",
        "",
        "Daily bars cover the whole list. Intraday bars that can reach 2018 are Dukascopy SPY and QQQ bids. "
        "The other names have about 60 Yahoo 5-minute days inside the holdout. Those rows are a short sample and are not in the trial count.",
        "",
        f"Trials counted: {search['n_combos']}. The frozen count is {n_trials()}.",
        "",
    ]
    header = "| Stock | Frame | Event | Horizon | Train n | Reversal | Random | Edge | q | Holdout n | Holdout edge | Class |"
    rule = "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|"
    lines.extend(["One row per stock, the strongest training cell:", "", header, rule])
    by_symbol: dict[str, list[dict]] = {}
    for row in cells:
        by_symbol.setdefault(row["symbol"], []).append(row)
    for symbol in SYMBOLS:
        row = _best_row(by_symbol.get(symbol, []))
        if row is None:
            lines.append(f"| {symbol} | | | | 0 | | | | | | | missing |")
            continue
        lines.append(
            f"| {symbol} | {row['timeframe']} | {row['event']} | {row['horizon']} | {row['n']} | {_pct(row['reversal'])} | "
            f"{_pct(row['random_reversal'])} | {_pct(row['mean_signed'])} | {_num(row['q'])} | "
            f"{row.get('holdout_n') if row.get('holdout_n') is not None else ''} | {_pct(row.get('holdout_mean_signed'))} | {row['label']} |"
        )
    lines.append("")
    if reverting or trending:
        lines.extend(["Cells that cleared the training FDR:", "", header, rule])
        for row in sorted(reverting + trending, key=lambda item: item["q"]):
            lines.append(
                f"| {row['symbol']} | {row['timeframe']} | {row['event']} | {row['horizon']} | {row['n']} | {_pct(row['reversal'])} | "
                f"{_pct(row['random_reversal'])} | {_pct(row['mean_signed'])} | {row['q']:.3f} | "
                f"{row.get('holdout_n')} | {_pct(row.get('holdout_mean_signed'))} | {row['label']}{' confirmed' if row.get('confirmed') else ''} |"
            )
            lines.append("")
            lines.append(plain_personality(row))
            lines.append("")
    else:
        lines.append("No cell cleared q ≤ 0.10.")
        lines.append("")
    if books:
        lines.append("Trade template, only on mean-reverting cells: confirmation candle, stop beyond the extreme, target the mean, one position, at most three entries a day.")
        lines.append("")
        lines.append("| Rule | Train trades | Train PF | Train Sharpe | Train $1,000 | Holdout trades | Holdout PF | Holdout $1,000 | q | DSR |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for book in books:
            lines.append(
                f"| {book['id']} | {book['train']['trades']} | {_num(book['train'].get('profit_factor'))} | {_num(book['train']['sharpe'])} | "
                f"{_money(book['train']['ending_equity'])} | {book['holdout']['trades']} | {_num(book['holdout'].get('profit_factor'))} | "
                f"{_money(book['holdout']['ending_equity'])} | {_num(book.get('q'))} | {_num(book.get('dsr'))} |"
            )
        lines.append("")
        if not any(book.get("confirmed") for book in books):
            lines.append("No trade book passed the holdout share check.")
            lines.append("")
    else:
        lines.append("No mean-reverting cell cleared the training bar, so no trade was built from these events.")
        lines.append("")
    if samples:
        closest = sorted(samples, key=lambda row: (-row["n"], -row["mean_signed"]))[:8]
        lines.append("Short Yahoo 5-minute sample, not a trial. Largest event counts:")
        lines.append("")
        lines.append("| Stock | Event | Horizon | n | Reversal | Edge |")
        lines.append("|---|---|---|---:|---:|---:|")
        for row in closest:
            lines.append(
                f"| {row['symbol']} | {row['event']} | {row['horizon']} | {row['n']} | {_pct(row['reversal'])} | {_pct(row['mean_signed'])} |"
            )
        lines.append("")
    lines.extend(
        [
            chart_note,
            "",
            "The machine-readable summary is `reports/tendency.json`.",
            "",
            "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.",
            "",
            "```",
            "python3 -m webull_bot.chart_reads.research_tendency",
            "```",
            END_MARK,
            "",
        ]
    )
    return "\n".join(lines)


def _write_results(section: str) -> None:
    path = Path("RESULTS.md")
    existing = path.read_text() if path.exists() else "# Research results\n\n"
    block = section if section.endswith("\n") else section + "\n"
    if START_MARK in existing and END_MARK in existing:
        start = existing.index(START_MARK)
        end = existing.index(END_MARK) + len(END_MARK)
        updated = existing[:start].rstrip() + "\n\n" + block
        if end < len(existing):
            updated += existing[end:].lstrip("\n")
    else:
        updated = existing.rstrip() + "\n\n" + block
    path.write_text(updated)


def _public_metrics(metrics: dict) -> dict:
    out = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            out[key] = None if not math.isfinite(value) else value
        else:
            out[key] = value
    return out


def main() -> None:
    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "tendency_rules.json").write_text(json.dumps(frozen_rules(), indent=2) + "\n")
    print("daily", flush=True)
    daily = _load_daily()
    print(f"daily symbols {len(daily)}", flush=True)
    intraday = _load_gate_intraday()
    prepared = _prepare_all(daily, intraday)
    search = run_search(prepared)
    print(f"combos {search['n_combos']}", flush=True)
    holdout = score_holdout(prepared, search)
    print(f"confirmed {holdout['confirmed_ids']}", flush=True)
    books = trade_books(prepared, search)
    print(f"trade books {len(books)}", flush=True)
    yahoo_symbols = tuple(symbol for symbol in SYMBOLS if symbol not in INTRADAY_GATE)
    yahoo = _load_yahoo_intraday(yahoo_symbols + ("UNH",))
    samples = []
    for symbol, five in yahoo.items():
        if five is None or five.empty or symbol not in daily:
            continue
        built = prepare(five, daily[symbol], "5m")
        samples.extend(short_sample(built, symbol, "5m"))
    chart_note = _chart_unh(reports / "tendency_unh.png", yahoo.get("UNH"), daily.get("UNH"))
    public_books = []
    for book in books:
        public_books.append(
            {
                "id": book["id"],
                "symbol": book["symbol"],
                "timeframe": book["timeframe"],
                "event": book["event"],
                "train": _public_metrics(book["train"]),
                "train_5k": _public_metrics(book["train_5k"]),
                "holdout": _public_metrics(book["holdout"]),
                "holdout_5k": _public_metrics(book["holdout_5k"]),
                "q": book.get("q"),
                "dsr": book.get("dsr"),
                "confirmed": book.get("confirmed"),
            }
        )
    payload = {
        "n_combos": search["n_combos"],
        "confirmed_ids": holdout["confirmed_ids"],
        "cells": search["cells"],
        "books": public_books,
        "short_sample_top": sorted(samples, key=lambda row: -row["n"])[:40],
        "chart_note": chart_note,
    }
    (reports / "tendency.json").write_text(json.dumps(payload, indent=2, default=_json) + "\n")
    section = _render(search, public_books, samples, chart_note)
    (reports / "tendency.md").write_text(section)
    _write_results(section)
    print(chart_note, flush=True)


def _json(value):
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)[:10]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    raise TypeError(type(value))


if __name__ == "__main__":
    main()
