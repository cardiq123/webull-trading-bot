"""Score the frozen 9/20 EMA rejection. Backtests only.

Writes the rules file before any metric. Does not place an order, does not
edit the sandbox forward test, and does not add a strategy to the live list.
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

from webull_bot.account_winners import buy_and_hold, window_stats
from webull_bot.chart_reads.ema_reject import (
    HOLDOUT_START,
    RANDOM_SEED,
    SAMPLE_END,
    TRAIN_END,
    explain_bar,
    find_signals,
    frozen_rules,
    indicator_frame,
    metrics_from,
    passes_gate,
    random_signals,
    simulate,
    to_five_minute,
)
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.vwap_band_data import load_minutes
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.mtf_vwap.detect import rth

START_MARK = "<!-- EMA_REJECT_START -->"
END_MARK = "<!-- EMA_REJECT_END -->"
RULES_PATH = Path("reports/ema_reject_rules.json")
JSON_PATH = Path("reports/ema_reject.json")
EQUITY_PATH = Path("reports/ema_reject_equity.png")
EXAMPLE_PATH = Path("reports/ema_reject_20261007.png")
CHART_DAY = date(2026, 10, 7)
CHART_TIME = "2026-10-07 10:20"

GATED = (
    ("vwap", "reject", "swing", "shares", True),
    ("vwap", "reject", "swing", "0dte", False),
)
NEIGHBORS = (
    ("ema", "reject", "swing", "shares", True),
    ("ema", "reject", "swing", "0dte", False),
    ("ema20", "reject", "swing", "shares", True),
    ("ema20", "reject", "swing", "0dte", False),
    ("vwap", "ema20", "swing", "shares", True),
    ("vwap", "ema20", "swing", "0dte", False),
    ("vwap", "reject", "r1", "shares", True),
    ("vwap", "reject", "r1", "0dte", False),
    ("vwap", "reject", "r2", "shares", True),
    ("vwap", "reject", "r2", "0dte", False),
    ("vwap", "reject", "ema", "shares", True),
    ("vwap", "reject", "ema", "0dte", False),
    ("vwap", "reject", "swing", "shares", False),
)


def _name(spec: tuple) -> str:
    variant, stop, target, kind, long_only = spec
    stop_bit = "" if stop == "reject" else f"_{stop}stop"
    base = f"{variant}{stop_bit}_{target}"
    if kind == "shares" and long_only:
        return f"{base}_shares"
    if kind == "shares":
        return f"{base}_shares_both"
    return f"{base}_{kind}"


def _pct(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _pf(value) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _num(value) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _money(value) -> str:
    if value is None:
        return "n/a"
    return f"${float(value):,.0f}"


def _price(value) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _day(stamp) -> date:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert("America/New_York")
    return clock.date()


def _daily_ohlc(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    bars = rth(frame)
    if bars.empty:
        empty = pd.Series(dtype=float)
        return empty, empty
    opened = bars.groupby(bars.index.date)["open"].first()
    closed = bars.groupby(bars.index.date)["close"].last()
    index = pd.DatetimeIndex(pd.to_datetime(list(closed.index)))
    return (
        pd.Series(opened.to_numpy(), index=index, dtype=float),
        pd.Series(closed.to_numpy(), index=index, dtype=float),
    )


def _prepare_iv() -> tuple[dict, dict[str, pd.Series]]:
    provider = YFinanceProvider(cache_dir="data/cache/vwap_band/yahoo")
    daily = provider.history(["^VIX", "^VIX1D", "SPY", "QQQ"], "2016-01-01", "2026-10-08", interval="1d")
    closes = {}
    for symbol, frame in daily.items():
        if frame is None or frame.empty or "close" not in frame.columns:
            continue
        series = frame["close"].astype(float).copy()
        index = pd.to_datetime(series.index)
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert("America/New_York").tz_localize(None)
        series.index = index
        closes[symbol] = series[~series.index.duplicated(keep="last")].sort_index()
    points = prior_iv(closes.get("^VIX1D", pd.Series(dtype=float)), closes.get("^VIX", pd.Series(dtype=float)))
    return points, closes


def _yahoo_5m(symbol: str) -> pd.DataFrame | None:
    provider = YFinanceProvider(cache_dir="data/cache/ema_reject/yahoo")
    frames = provider.history([symbol], "2026-08-01", "2026-10-08", interval="5m")
    frame = frames.get(symbol)
    if frame is None or frame.empty:
        return None
    return rth(frame)


def _pack(book: dict, gate: bool) -> dict:
    metrics = dict(book["metrics"])
    metrics["passes"] = bool(gate and passes_gate(metrics))
    metrics["skips"] = book["skips"]
    metrics["under_one_share"] = book["under_one_share"]
    return metrics


def _signals_by_variant(frame: pd.DataFrame, symbol: str) -> dict[str, list]:
    grouped = {"ema": [], "vwap": [], "ema20": []}
    for signal in find_signals(frame, symbol):
        grouped[signal.variant].append(signal)
    return grouped


def _run(frame, signals, spec, stake, iv, start=None, end=None):
    _variant, stop, target, kind, long_only = spec
    return simulate(
        frame,
        signals,
        stop=stop,
        target=target,
        kind=kind,
        stake=stake,
        long_only=long_only,
        iv_points=iv,
        start=start,
        end=end,
    )


def _score_symbol(symbol: str, frame: pd.DataFrame, iv: dict, anecdotal: bool) -> dict:
    print(f"SIGNALS {symbol} bars {len(frame)}", flush=True)
    cache = _signals_by_variant(frame, symbol)
    for variant, rows in cache.items():
        print(f"SIGNALS {symbol} {variant} {len(rows)}", flush=True)
    books = []
    equities = {}
    for spec in GATED + NEIGHBORS:
        if anecdotal and spec not in GATED:
            continue
        signals = cache[spec[0]]
        name = _name(spec)
        print(f"SCORE {symbol} {name}", flush=True)
        stakes = (1000.0, 5000.0) if spec in GATED else (1000.0,)
        stake_rows = {}
        paths = {}
        notes: dict[str, str] = {}
        for stake in stakes:
            full = _run(frame, signals, spec, stake, iv)
            train = _run(frame, signals, spec, stake, iv, end=TRAIN_END)
            hold = _run(frame, signals, spec, stake, iv, start=HOLDOUT_START)
            stake_rows[str(int(stake))] = {
                "full": _pack(full, False),
                "train": _pack(train, False),
                "holdout": _pack(hold, spec in GATED and not anecdotal),
            }
            if spec in GATED:
                paths[str(int(stake))] = full["equity"]
            if stake == 1000.0 and spec in GATED:
                equities[name] = hold["equity"]
                if spec[3] != "shares":
                    notes["iv_split"] = _iv_split(hold["trades"], iv)
                    notes["top_trade"] = _top_trade(hold["trades"])
                if not anecdotal and spec[2] == "swing":
                    considered = [
                        item for item in signals
                        if _day(item.fill_time) >= HOLDOUT_START
                        and np.isfinite(item.swing)
                        and (item.direction == "long" or not spec[4])
                    ]
                    random_book = simulate(
                        frame,
                        random_signals(
                            frame.loc[frame.index.date >= HOLDOUT_START] if len(frame) else frame,
                            symbol,
                            len(considered),
                            RANDOM_SEED,
                        ),
                        stop="reject",
                        target="r1",
                        kind=spec[3],
                        stake=stake,
                        long_only=spec[4],
                        iv_points=iv,
                        start=HOLDOUT_START,
                    )
                    stake_rows[str(int(stake))]["random"] = _pack(random_book, False)
        books.append(
            {
                "name": name,
                "spec": list(spec),
                "default": spec in GATED,
                "gated": spec in GATED and not anecdotal,
                "anecdotal": anecdotal,
                "stakes": stake_rows,
                "paths": paths,
                "iv_split": notes.get("iv_split", ""),
                "top_trade": notes.get("top_trade", ""),
            }
        )
    return {"symbol": symbol, "anecdotal": anecdotal, "books": books, "equities": equities}


def _windows(equity: pd.Series, other: pd.Series, months: int, stake: float) -> dict:
    if equity is None or equity.empty or other is None or other.empty:
        return {"windows": 0}
    aligned = other.copy()
    aligned.index = pd.DatetimeIndex(pd.to_datetime(aligned.index)).tz_localize(None)
    curve = equity.copy()
    curve.index = pd.DatetimeIndex(pd.to_datetime(curve.index)).tz_localize(None)
    return window_stats(curve, aligned, months, stake)


def _bh(opened: pd.Series, closed: pd.Series, stake: float, start: date, end: date) -> dict:
    equity = buy_and_hold(
        opened,
        closed,
        starting_equity=stake,
        trade_start=pd.Timestamp(start),
        trade_end=pd.Timestamp(end),
    )
    stats = metrics_from(equity, [], stake)
    stats["equity"] = equity
    return stats


def _style_axis(ax) -> None:
    ax.set_facecolor("#161616")
    ax.tick_params(colors="#cccccc")
    for spine in ax.spines.values():
        spine.set_color("#444444")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(color="#2a2a2a")


def _plot_equity(curves: dict, bh_spy: pd.Series, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12.2, 6.2), dpi=120)
    fig.patch.set_facecolor("#161616")
    _style_axis(ax)
    colors = {"vwap_swing_shares": "#5dade2", "vwap_swing_0dte": "#e67e22"}
    for name, equity in curves.items():
        if equity is None or equity.empty:
            continue
        ax.plot(equity.index, equity.to_numpy(), color=colors.get(name, "#dddddd"), lw=1.4, label=name)
    if bh_spy is not None and not bh_spy.empty:
        ax.plot(bh_spy.index, bh_spy.to_numpy(), color="#f4f4f4", lw=1.4, label="SPY buy and hold")
    ax.set_title("Holdout growth of $1,000 after costs. Not a forecast.", color="#f4f4f4")
    legend = ax.legend(facecolor="#1e1e1e", edgecolor="#333333")
    for text in legend.get_texts():
        text.set_color("#f4f4f4")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def _plot_day(frame: pd.DataFrame, path: Path) -> tuple[dict, list[dict]]:
    """Yahoo illustration of 2026-10-07. Missing data stays missing."""
    reading = explain_bar(frame, CHART_TIME)
    day_signals = []
    ind = indicator_frame(frame)
    session = ind[[stamp.date() == CHART_DAY for stamp in ind.index]] if not ind.empty else ind
    if session.empty:
        return reading, day_signals
    for signal in find_signals(frame, "SPY"):
        if _day(signal.signal_time) != CHART_DAY or signal.variant != "vwap":
            continue
        day_signals.append(
            {
                "direction": signal.direction,
                "signal_time": str(signal.signal_time),
                "fill_time": str(signal.fill_time),
                "stop": signal.stop_reject,
                "swing": None if not np.isfinite(signal.swing) else signal.swing,
            }
        )
    fig, ax = plt.subplots(figsize=(12.2, 6.4), dpi=120)
    fig.patch.set_facecolor("#161616")
    _style_axis(ax)
    ax.plot(session.index, session["close"], color="#f4f4f4", lw=1.1, label="close")
    ax.plot(session.index, session["ema9"], color="#f5b041", lw=1.1, label="9 EMA")
    ax.plot(session.index, session["ema20"], color="#5dade2", lw=1.1, label="20 EMA")
    ax.plot(session.index, session["vwap"], color="#e67e22", lw=1.0, label="VWAP")
    marked = False
    for signal in day_signals:
        stamp = pd.Timestamp(signal["signal_time"])
        if stamp not in session.index:
            continue
        price = float(session.loc[stamp, "high"] if signal["direction"] == "short" else session.loc[stamp, "low"])
        ax.scatter([stamp], [price], color="#58d68d", s=36, zorder=3, label="gate signal" if not marked else None)
        marked = True
    target = pd.Timestamp(CHART_TIME, tz="America/New_York")
    if target in session.index:
        ax.axvline(target, color="#f7dc6f", lw=0.8, ls="--", label="10:20 ET")
    gate = "gate marks 10:20" if reading.get("gate") else "gate does not mark 10:20"
    ax.set_title(f"SPY 2026-10-07, Yahoo 5-minute. {gate}. Not the Dukascopy score.", color="#f4f4f4")
    legend = ax.legend(facecolor="#1e1e1e", edgecolor="#333333", fontsize=8)
    for text in legend.get_texts():
        text.set_color("#f4f4f4")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return reading, day_signals


def _chart_sentence(reading: dict, day_signals: list[dict], source: str) -> str:
    if not reading.get("found"):
        return (
            f"{source} The frozen rule was not loosened. "
            "There is no 10:20 ET bar to mark, and none was invented."
        )
    blockers = reading.get("blockers") or []
    detail = (
        f"9 EMA {_price(reading.get('ema9'))}, 20 EMA {_price(reading.get('ema20'))}, "
        f"VWAP {_price(reading.get('vwap'))}, close {_price(reading.get('close'))}, high {_price(reading.get('high'))}."
    )
    if reading.get("gate"):
        marked = (
            f"The frozen rule marks 10:20 as a {reading.get('direction')} gate signal. "
            f"The chart marks {len(day_signals)} VWAP-confluence signal(s) that day."
        )
    else:
        marked = (
            "The frozen rule does not mark 10:20 as a gate signal. "
            + (f"It failed: {'; '.join(blockers)}. " if blockers else "")
            + f"The chart marks {len(day_signals)} other VWAP-confluence signal(s) that day."
        )
    return (
        f"{source} The user read the 9 EMA and VWAP stacked near 775.05 at 10:20 ET. On these bars, {detail} {marked} "
        "The tolerances were not changed after this reading."
    )


def _window_line(stats: dict, other: str) -> str:
    if not stats or not stats.get("windows"):
        return "no windows"
    return (
        f"{int(stats['windows'])} windows. Median ending {_money(stats.get('ending_median'))} "
        f"({other} {_money(stats.get('spy_ending_median'))}), bad {_money(stats.get('ending_p10'))} "
        f"({other} {_money(stats.get('spy_ending_p10'))}), good {_money(stats.get('ending_p90'))} "
        f"({other} {_money(stats.get('spy_ending_p90'))}). "
        f"{_pct(stats.get('pct_negative'))} lost money, against {_pct(stats.get('spy_pct_negative'))} for {other}."
    )


def _iv_split(trades: list[dict], iv: dict) -> str:
    buckets: dict[str, list[float]] = {}
    for trade in trades:
        point = iv.get(_day(trade["fill_time"]))
        if point is None:
            continue
        buckets.setdefault(point[1], []).append(float(trade["pnl"]))
    parts = []
    for name in ("VIX", "VIX1D"):
        pnls = buckets.get(name) or []
        if not pnls:
            continue
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [pnl for pnl in pnls if pnl < 0]
        gross_loss = -sum(losses)
        factor = (sum(wins) / gross_loss) if gross_loss > 0 else None
        parts.append(f"{name} {len(pnls)} trades, profit factor {_pf(factor)}, dollar profit {_money(sum(pnls))}")
    return "; ".join(parts)


def _top_trade(trades: list[dict]) -> str:
    if not trades:
        return ""
    top = max(trades, key=lambda trade: float(trade["pnl"]))
    total = sum(float(trade["pnl"]) for trade in trades)
    share = (float(top["pnl"]) / total) if total else 0.0
    return (
        f"Largest trade {_money(top['pnl'])} on {_day(top['fill_time'])} ({top['reason']}), "
        f"{_pct(share)} of that book's dollar profit."
    )


def _row(book: dict) -> str:
    hold = book["stakes"]["1000"]["holdout"]
    five = book["stakes"].get("5000", {}).get("holdout", {})
    gate = "yes" if hold.get("passes") else "no"
    return (
        f"| {book['name']} | {hold.get('trades', 0)} | {_pct(hold.get('win_rate'))} | "
        f"{_pct(hold.get('breakeven_win_rate'))} | {_pf(hold.get('profit_factor'))} | "
        f"{_num(hold.get('sharpe'))} | {_pct(hold.get('max_drawdown'))} | "
        f"{_money(hold.get('ending_equity'))} | {_money(five.get('ending_equity')) if five else 'n/a'} | {gate} |"
    )


def _markdown(payload: dict) -> str:
    lines = [
        START_MARK,
        "## 9/20 EMA rejection, 5-minute SPY and QQQ",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox forward test was not changed. "
        "The rules were frozen before this score. The gate is the chart that was pointed at: a 9/20 downtrend or its long mirror, "
        "a bar that tags the 9 EMA within 0.10 ATR and closes back on the trend side, with session VWAP within 0.10 ATR of the 9 EMA. "
        "The stop is one cent beyond the rejection bar. The target is the prior 5-bar swing. "
        "The 9 EMA alone, the intact 20 EMA, the 20 EMA stop, and the 1R, 2R, and 9 EMA cross exits are variants. "
        "A bar within 0.10 ATR of the 9 EMA cannot reach a 20 EMA that is at least 0.10 ATR away, so the intact-20 variant matches the 9 EMA variant. "
        "A variant that looks better was not promoted. Train is a fresh account through 2021-12-31. "
        "The holdout is a fresh account from 2022-01-01 through 2026-10-06. "
        "2026-10-07 is the illustration, not part of the Dukascopy score.",
        "",
        payload["data_text"],
        "",
        "The cash share book is long only. A $1,000 cash account cannot short, so it cannot express the short rejection on that chart. "
        "Calls and puts are long premium, so the 0 DTE book takes both directions. "
        "Shares risk 1% of equity to the stop, with fractional shares. Options are exactly one at-the-money contract when the debit fits in settled cash, "
        "so a $5,000 account does not buy more contracts. When the debit already fits in $1,000, the extra cash sits idle and the dollar profit matches. "
        "A sale settles the next session. The option price is Black-Scholes with the prior session's VIX1D close, or the prior VIX close before that print exists, "
        "a half-spread of the greater of one cent and 1.5% of the mid, and the repo's option fees. There is no listed chain. "
        "Time left uses the bar's left timestamp. QQQ uses the same SPX volatility print. "
        "The chop guard is on for every book: relative volume under 0.85 versus the prior 20 bars (chop v2), an EMA spread under 0.10 ATR, "
        "or a 9 EMA slope under 0.05 ATR. Chop v2's 0.75 ATR stack width is not used. Dukascopy volume is a bid-tick count. "
        "Dukascopy prices are bids and omit dividends, so that buy-and-hold is the lower reference. Yahoo adjusted daily SPY and QQQ include dividends. "
        "Taxes are ignored: these books realize short-term gains, and a buy-and-hold defers them.",
        "",
        "| Book | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for book in payload["rows"]:
        if not book.get("default"):
            continue
        lines.append(_row(book))
    lines += [
        "",
        "### Training account, through 2021-12-31",
        "",
        "Fresh $1,000 and $5,000. This is not the gate. An option account that cannot pay for the next contract stops, and the rest of the signals are skips.",
        "",
        "| Book | Trades | PF | Sharpe | Max DD | $1,000 | $5,000 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for book in payload["rows"]:
        if not book.get("default"):
            continue
        train = book["stakes"]["1000"]["train"]
        train_five = book["stakes"].get("5000", {}).get("train", {})
        lines.append(
            f"| {book['name']} | {train.get('trades', 0)} | {_pf(train.get('profit_factor'))} | "
            f"{_num(train.get('sharpe'))} | {_pct(train.get('max_drawdown'))} | "
            f"{_money(train.get('ending_equity'))} | "
            f"{_money(train_five.get('ending_equity')) if train_five else 'n/a'} |"
        )
    lines += ["", payload["verdict"], "", "### Rolling windows, full sample", ""]
    lines.append(
        "One continuous account from the first SPY session, not a fresh holdout. "
        "Each window is that account's percentage change, restated from the starting stake. "
        "After a $1,000 option account dies, later windows are flat and show $1,000. "
        "The $5,000 continuation is the path that stayed open."
    )
    lines.append("")
    lines.append(payload["window_text"])
    lines += ["", "### Variants and the both-directions share baseline", "", payload["neighbor_text"], ""]
    lines += [payload["random_text"], "", payload["model_text"], "", payload["share_text"], "", payload["chart_text"], ""]
    lines += [
        "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.",
        "",
        "```",
        "python3 -m webull_bot.chart_reads.research_ema_reject",
        "```",
        END_MARK,
        "",
    ]
    return "\n".join(lines)


def _write_results(block: str) -> None:
    path = Path("RESULTS.md")
    text = path.read_text() if path.exists() else ""
    if START_MARK in text and END_MARK in text:
        before = text.split(START_MARK)[0]
        after = text.split(END_MARK)[1]
        path.write_text(before + block + after.lstrip("\n"))
        return
    path.write_text(text.rstrip() + "\n\n" + block)


def _public(payload: dict) -> dict:
    books = []
    for book in payload["rows"]:
        stakes = {}
        for stake, block in book["stakes"].items():
            stakes[stake] = {
                key: {k: v for k, v in metrics.items() if k != "equity"}
                for key, metrics in block.items()
            }
        books.append(
            {
                "name": book["name"],
                "spec": book["spec"],
                "gated": book["gated"],
                "default": book.get("default", False),
                "stakes": stakes,
            }
        )
    reading = dict(payload.get("reading") or {})
    return {
        "rules_holdout": "2022-01-01",
        "data": payload["data"],
        "books": books,
        "buy_hold": payload["buy_hold"],
        "chart_day": payload.get("day_signals", []),
        "chart_10_20": reading,
        "verdict": payload["verdict"],
    }


def _qqq() -> tuple[pd.DataFrame | None, bool, str]:
    cache = Path("data/cache/vwap_band/dukascopy/QQQ")
    count = len(list(cache.glob("*.csv"))) if cache.exists() else 0
    if count >= 2000:
        minutes, info = load_minutes("QQQ")
        if minutes is not None and int(info.get("sessions") or 0) >= 2000 and int(info.get("missing") or 9999) <= 80:
            note = (
                f"QQQ is the same Dukascopy bid feed, {info.get('first')} through {info.get('last')}, "
                f"{info.get('sessions')} sessions, {info.get('missing')} days missing."
            )
            return to_five_minute(minutes), False, note
        count = int(info.get("sessions") or count)
        missing = info.get("missing")
        yahoo = _yahoo_5m("QQQ")
        return yahoo, True, _yahoo_note(yahoo, count, missing)
    yahoo = _yahoo_5m("QQQ")
    return yahoo, True, _yahoo_note(yahoo, count, "not counted, the long file is still short")


def _yahoo_note(frame: pd.DataFrame | None, count: int, missing) -> str:
    if frame is None or frame.empty:
        return (
            f"Dukascopy publishes QQQUSUSD, but this cache has {count} day files "
            f"and {missing} days still missing. Yahoo returned no 5-minute bars."
        )
    return (
        f"Dukascopy publishes QQQUSUSD, but this cache has {count} day files "
        f"and {missing} days still missing, short of the 2017+ file. "
        f"The QQQ rows are Yahoo 5-minute bars from {frame.index[0].date()} through {frame.index[-1].date()}, "
        "about 60 days. That sample cannot clear 300 out-of-sample trades. It is not the gate."
    )


def main() -> None:
    rules = frozen_rules()
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(rules, indent=2) + "\n")
    written = json.loads(RULES_PATH.read_text())
    if "2022-01-01" not in written["split"] or written["gate_variant"] != "vwap" or written["touch_atr"] != 0.10:
        raise SystemExit("frozen rules were not the file that will be scored")

    minutes, info = load_minutes("SPY")
    if minutes is None:
        raise SystemExit(f"SPY minutes are not ready {info}")
    spy = to_five_minute(minutes)
    qqq, qqq_anecdotal, qqq_note = _qqq()
    iv, yahoo_daily = _prepare_iv()
    print(f"IV days {len(iv)} SPY bars {len(spy)}", flush=True)
    spy_score = _score_symbol("SPY", spy, iv, anecdotal=False)
    qqq_score = None
    if qqq is not None and not qqq.empty:
        qqq_score = _score_symbol("QQQ", qqq, iv, anecdotal=qqq_anecdotal)

    opened, closed = _daily_ohlc(spy)
    bh_hold = _bh(opened, closed, 1000.0, HOLDOUT_START, SAMPLE_END)
    bh_hold_5 = _bh(opened, closed, 5000.0, HOLDOUT_START, SAMPLE_END)
    yahoo_bh = {}
    for symbol in ("SPY", "QQQ"):
        series = yahoo_daily.get(symbol)
        if series is None or series.empty:
            continue
        yahoo_bh[symbol] = _bh(series, series, 1000.0, HOLDOUT_START, SAMPLE_END)

    chart = _yahoo_5m("SPY")
    reading: dict = {"found": False}
    day_signals: list[dict] = []
    if chart is not None and not chart.empty:
        reading, day_signals = _plot_day(chart, EXAMPLE_PATH)
        source = (
            f"The 2026-10-07 chart is Yahoo 5-minute, {chart.index[0].date()} through {chart.index[-1].date()}, "
            "because the Dukascopy file ends with the last complete session and does not include that day. "
            "EMAs on the chart are computed from those Yahoo bars, not from the 2017 bid series."
        )
    else:
        source = "Yahoo returned no 5-minute SPY bars for the 2026-10-07 chart."
    _plot_equity(spy_score["equities"], bh_hold.get("equity"), EQUITY_PATH)
    artifact = Path("/opt/cursor/artifacts")
    if artifact.exists():
        for source_path in (EQUITY_PATH, EXAMPLE_PATH):
            if source_path.exists():
                (artifact / source_path.name).write_bytes(source_path.read_bytes())

    rows = list(spy_score["books"])
    if qqq_score is not None:
        for book in qqq_score["books"]:
            renamed = dict(book)
            renamed["name"] = f"QQQ {book['name']}"
            rows.append(renamed)

    payload_windows = []
    qqq_close = yahoo_daily.get("QQQ")
    for book in spy_score["books"]:
        if not book.get("gated"):
            continue
        for stake, label in (("1000", "$1,000"), ("5000", "$5,000")):
            equity = book.get("paths", {}).get(stake)
            if equity is None or equity.empty:
                continue
            for months in (6, 12):
                versus_spy = _windows(equity, closed, months, float(stake))
                versus_qqq = _windows(equity, qqq_close, months, float(stake)) if qqq_close is not None else {"windows": 0}
                payload_windows.append(
                    f"**{book['name']}, {label}, {months} months.** Versus SPY bids: {_window_line(versus_spy, 'SPY')}"
                )
                payload_windows.append(f"Versus Yahoo adjusted QQQ: {_window_line(versus_qqq, 'QQQ')}")

    passed = [book["name"] for book in rows if book["stakes"]["1000"]["holdout"].get("passes")]
    if passed:
        verdict = (
            "The holdout gate is profit factor at least 1.10, Sharpe at least 0.40, max drawdown no worse than -30%, "
            f"and at least 300 trades. These default books cleared it: {', '.join(passed)}. "
            "Clearing the gate is not the same thing as beating buy-and-hold."
        )
    else:
        verdict = (
            "No default book cleared the holdout gate (profit factor at least 1.10, Sharpe at least 0.40, "
            "max drawdown no worse than -30%, and at least 300 trades)."
        )
    verdict += (
        f" SPY buy-and-hold on the same bid series finished the holdout at {_money(bh_hold['ending_equity'])} "
        f"from $1,000 (Sharpe {_num(bh_hold['sharpe'])}, max drawdown {_pct(bh_hold['max_drawdown'])}) "
        f"and {_money(bh_hold_5['ending_equity'])} from $5,000. That series pays no dividends."
    )
    if "SPY" in yahoo_bh:
        verdict += (
            f" Yahoo adjusted SPY, which includes dividends, finished at {_money(yahoo_bh['SPY']['ending_equity'])} "
            f"(Sharpe {_num(yahoo_bh['SPY']['sharpe'])}, max drawdown {_pct(yahoo_bh['SPY']['max_drawdown'])})."
        )
    if "QQQ" in yahoo_bh:
        verdict += (
            f" Yahoo adjusted QQQ finished at {_money(yahoo_bh['QQQ']['ending_equity'])} "
            f"(Sharpe {_num(yahoo_bh['QQQ']['sharpe'])}, max drawdown {_pct(yahoo_bh['QQQ']['max_drawdown'])})."
        )

    neighbor_lines = [
        "These rows use the same holdout and the same $1,000 stake. They do not replace the VWAP-confluence default.",
        "",
        "| Book | Trades | Win | PF | Sharpe | Max DD | Ending | Clears the numbers |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    random_lines = [
        "Random entries use seed 17, the same count of holdout signals that have a prior swing, and a 1R target. One draw. It was not used to change the rule.",
        "",
    ]
    model_lines = [
        "Same holdout trades, split by the volatility print. VIX1D starts in 2023. Earlier sessions use the 30-day VIX as same-day vol. This split was not used to change the rule.",
        "",
    ]
    share_lines = [
        "Fractional share counts are a research fill. Webull equity orders in this repo are whole shares, so a $1,000 or $5,000 account would skip most of these ETF orders. No sandbox forward command was added.",
        "",
    ]
    for book in rows:
        hold = book["stakes"]["1000"]["holdout"]
        if book.get("default"):
            if book.get("gated"):
                random_metrics = book["stakes"]["1000"].get("random")
                if random_metrics:
                    random_lines.append(
                        f"**{book['name']}.** Random holdout trades {random_metrics.get('trades', 0)}, "
                        f"ending {_money(random_metrics.get('ending_equity'))}, "
                        f"profit factor {_pf(random_metrics.get('profit_factor'))}, "
                        f"Sharpe {_num(random_metrics.get('sharpe'))}, "
                        f"max drawdown {_pct(random_metrics.get('max_drawdown'))}."
                    )
                if book.get("iv_split"):
                    model_lines.append(f"**{book['name']}.** {book['iv_split']}. {book.get('top_trade', '')}")
                if book["name"].endswith("shares"):
                    share_lines.append(
                        f"**{book['name']}.** {hold.get('under_one_share', 0)} of {hold.get('trades', 0)} "
                        "holdout trades were under one share."
                    )
            continue
        clears = passes_gate(hold)
        neighbor_lines.append(
            f"| {book['name']} | {hold.get('trades', 0)} | {_pct(hold.get('win_rate'))} | "
            f"{_pf(hold.get('profit_factor'))} | {_num(hold.get('sharpe'))} | "
            f"{_pct(hold.get('max_drawdown'))} | {_money(hold.get('ending_equity'))} | "
            f"{'yes, not promoted' if clears else 'no'} |"
        )

    data_text = (
        f"SPY is Dukascopy 1-minute bids resampled to 5 minutes, {info.get('first')} through {info.get('last')}, "
        f"{info.get('sessions')} sessions, {info.get('rows')} minute bars, {len(spy)} five-minute bars, "
        f"{info.get('missing')} days missing, {info.get('empty')} empty files. Volume is a bid-tick count. {qqq_note}"
    )
    chart_text = (
        f"Charts: `{EQUITY_PATH.as_posix()}` and `{EXAMPLE_PATH.as_posix()}`. "
        + _chart_sentence(reading, day_signals, source)
    )
    payload = {
        "data_text": data_text,
        "data": {
            "spy": {key: info[key] for key in ("first", "last", "sessions", "missing", "empty", "rows") if key in info},
            "spy_five_minute": len(spy),
            "qqq": qqq_note,
        },
        "rows": rows,
        "verdict": verdict,
        "window_text": "\n\n".join(payload_windows),
        "neighbor_text": "\n".join(neighbor_lines),
        "random_text": "\n\n".join(random_lines),
        "model_text": "\n\n".join(model_lines),
        "share_text": "\n\n".join(share_lines),
        "chart_text": chart_text,
        "reading": reading,
        "day_signals": day_signals,
        "buy_hold": {
            "spy_bid_1000": bh_hold["ending_equity"],
            "spy_bid_5000": bh_hold_5["ending_equity"],
            "yahoo": {symbol: stats["ending_equity"] for symbol, stats in yahoo_bh.items()},
        },
    }
    block = _markdown(payload)
    _write_results(block)
    JSON_PATH.write_text(json.dumps(_public(payload), indent=2, default=str) + "\n")
    print(verdict, flush=True)
    print(chart_text, flush=True)
    print(f"WROTE {RULES_PATH} {JSON_PATH} {EQUITY_PATH}", flush=True)


if __name__ == "__main__":
    main()
