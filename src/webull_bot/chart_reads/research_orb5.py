"""Score the frozen first-candle opening range. The holdout does not change the rules.

Run: ``python3 -m webull_bot.chart_reads.research_orb5``

Nothing is sent to a broker. This does not import or edit the sandbox
forward test. Yahoo's 5-minute history is about 55 calendar days, and the
1-minute history is about a week. Both samples are short.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.liquid import LIQUID_BLUE_CHIPS
from webull_bot.chart_reads.orb5 import (
    CASH_ACCOUNT,
    DTE_LIST,
    DTE_PRIMARY,
    ENTRY_PRIMARY,
    ENTRY_VARIANTS,
    LADDER_STOP,
    SEED,
    SHARE_R_PRIMARY,
    STOP_PRIMARY,
    find_orb,
    frozen_rules,
    opening_bounds,
    range_stop,
    simulate_ladder,
    simulate_shares,
)
from webull_bot.chart_reads.premium_scale import required_capital
from webull_bot.chart_reads.pullback import (
    PRIMARY_STOP,
    PRIMARY_TARGET,
    lot_debit,
    price_paths,
    simulate_premium,
    sized_equity,
)
from webull_bot.chart_reads.research import random_setups
from webull_bot.chart_reads.research_daily import _naive
from webull_bot.chart_reads.simulate import _realized
from webull_bot.costs import CostModel, buy_price, sell_price
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.mtf_vwap.detect import rth

START = "<!-- CHART_READS_ORB5_START -->"
END_MARK = "<!-- CHART_READS_ORB5_END -->"
RULES_PATH = Path("reports/orb5_rules.json")
REPORT_PATH = Path("reports/chart_reads_orb5.json")
CHART_DIR = Path("reports/setups")
DOWNLOAD_END = "2026-10-07"
CHART_DAY = date(2026, 10, 6)
CACHE = "data/cache/orb5"


def _day(stamp) -> date:
    ts = pd.Timestamp(stamp)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("America/New_York")
    return ts.date()


def _sessions(frames) -> list[date]:
    found = set()
    for frame in frames.values():
        if frame is None or frame.empty:
            continue
        found.update(_day(stamp) for stamp in frame.index)
    return sorted(found)


def _half(days: list[date]):
    if len(days) < 4:
        return None
    mid = len(days) // 2
    return (days[0], days[mid - 1]), (days[mid], days[-1])


def _in_window(setups, start: date, end: date):
    return [setup for setup in setups if start <= _day(setup.fill_time) <= end]


def _paths_in(paths, start: date, end: date):
    return [path for path in paths if start <= path.fill_date <= end]


def _slice(frames, start: date, end: date) -> dict:
    sliced = {}
    for symbol, frame in frames.items():
        piece = frame.loc[[start <= _day(stamp) <= end for stamp in frame.index]]
        if len(piece) > 5:
            sliced[symbol] = piece
    return sliced


def _stopped(setups, kind: str) -> list[Setup]:
    return [replace(setup, stop=range_stop(setup, kind)) for setup in setups]


def _money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"${float(value):,.2f}"


def _pct(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.1%}"


def _num(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _pf(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _public(book: dict) -> dict:
    metrics = book.get("metrics") or {}
    return {
        "trades": int(metrics.get("trades") or 0),
        "win_rate": metrics.get("win_rate"),
        "expectancy": metrics.get("expectancy"),
        "profit_factor": metrics.get("profit_factor"),
        "sharpe": metrics.get("sharpe"),
        "max_drawdown": metrics.get("max_drawdown"),
        "ending_equity": metrics.get("ending_equity"),
        "starting_equity": book.get("starting_equity"),
        "breakeven_before": book.get("breakeven_before"),
        "breakeven_after": book.get("breakeven_after"),
        "clears_breakeven": book.get("clears_breakeven"),
        "profitable": book.get("profitable"),
        "skipped": book.get("skipped"),
        "pdt_blocked": book.get("pdt_blocked"),
        "overlapped": book.get("overlapped"),
        "reasons": book.get("reasons"),
        "median_delta": book.get("median_delta"),
        "avg_win": metrics.get("avg_win"),
        "avg_loss": metrics.get("avg_loss"),
    }


def _bits(book: dict) -> str:
    metrics = book.get("metrics") or {}
    trades = int(metrics.get("trades") or 0)
    blocked = int(book.get("pdt_blocked") or 0)
    if trades == 0:
        return f"0 trades, skipped {int(book.get('skipped') or 0)}, PDT blocked {blocked}"
    return (
        f"{trades} trades, win {_pct(metrics.get('win_rate'))}, "
        f"after-cost break-even {_pct(book.get('breakeven_after'))}, "
        f"expectancy {_money(metrics.get('expectancy'))}, "
        f"profit factor {_pf(metrics.get('profit_factor'))}, "
        f"Sharpe {_num(metrics.get('sharpe'))}, "
        f"max drawdown {_pct(metrics.get('max_drawdown'))}, "
        f"ending {_money(metrics.get('ending_equity'))}, "
        f"PDT blocked {blocked}"
    )


def _plain(name: str, book: dict) -> str:
    metrics = book.get("metrics") or {}
    trades = int(metrics.get("trades") or 0)
    blocked = int(book.get("pdt_blocked") or 0)
    if trades == 0:
        return (
            f"{name}: no closed trades, so the win rate does not clear a break-even rate "
            f"and the book is not profitable. PDT blocked {blocked}. "
            f"Skipped {int(book.get('skipped') or 0)}."
        )
    clears = "clears" if book.get("clears_breakeven") else "does not clear"
    profit = "profitable" if book.get("profitable") else "not profitable"
    before = book.get("breakeven_before")
    before_text = f" The before-cost break-even is {_pct(before)}." if before is not None else ""
    return (
        f"{name}: realized win rate {_pct(metrics.get('win_rate'))} against an after-cost "
        f"break-even of {_pct(book.get('breakeven_after'))}. The win rate {clears} that rate."
        f"{before_text} It is {profit} out of sample "
        f"({_money(metrics.get('expectancy'))} expectancy, ending {_money(metrics.get('ending_equity'))} "
        f"from {_money(book.get('starting_equity'))}, {trades} trades). PDT blocked {blocked}."
    )


def _load(interval: str, symbols: list[str], lookback_days: int) -> dict[str, pd.DataFrame]:
    provider = YFinanceProvider(CACHE)
    start = (pd.Timestamp(DOWNLOAD_END) - pd.Timedelta(days=lookback_days)).date().isoformat()
    print(f"loading {interval} from {start}", flush=True)
    raw = provider.history(symbols, start, DOWNLOAD_END, interval=interval)
    frames = {}
    for symbol in symbols:
        frame = raw.get(symbol)
        if frame is None or frame.empty:
            continue
        bars = rth(frame)
        if len(bars) > 20:
            frames[symbol] = bars
    missing = [symbol for symbol in symbols if symbol not in frames]
    print(f"  {interval} present {len(frames)} missing {missing}", flush=True)
    return frames


def _detect(frames, clock: str, variant: str, symbols: list[str]) -> list[Setup]:
    found = []
    for symbol in symbols:
        frame = frames.get(symbol)
        if frame is None:
            continue
        found.extend(find_orb(frame, symbol, clock, variant))
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol))
    return found


def _shares(setups, frames, target_r, stop_kind: str) -> dict:
    return simulate_shares(
        _stopped(setups, stop_kind),
        frames,
        target_r=target_r,
        starting_equity=CASH_ACCOUNT,
        pdt=True,
    )


def _option(paths, equity: float, mode: str) -> dict:
    book = simulate_premium(
        paths,
        target=PRIMARY_TARGET,
        stop=PRIMARY_STOP,
        time_bars=None,
        starting_equity=equity,
        mode=mode,
        pdt=True,
    )
    book["starting_equity"] = float(equity)
    return book


def _ladder_equity(paths) -> float:
    required = []
    for path in paths:
        if not path.ok or path.ask <= 0:
            continue
        debit = lot_debit(path.ask, 5)
        required.append(required_capital(path.ask, debit, LADDER_STOP))
    if not required:
        return float("nan")
    return float(np.median(required))


def _walk(setups, frames, folds, paths) -> dict:
    rows = []
    pnl = 0.0
    trades = 0
    for start, end in folds:
        book = _shares(_in_window(setups, start, end), frames, SHARE_R_PRIMARY, STOP_PRIMARY)
        count = int(book["metrics"].get("trades") or 0)
        pnl += float(book["metrics"].get("expectancy") or 0.0) * count
        trades += count
        option = _option(_paths_in(paths, start, end), CASH_ACCOUNT, "cash")
        rows.append({"test": [start.isoformat(), end.isoformat()], "shares": _public(book), "option": _public(option)})
    return {"folds": rows, "share_expectancy": (pnl / trades) if trades else None, "share_trades": trades}


def _spy_hold(frame: pd.DataFrame, start: date, end: date) -> dict:
    if frame is None or frame.empty:
        return {"trades": 0, "ending_equity": CASH_ACCOUNT, "shares": 0}
    window = frame.loc[[start <= _day(stamp) <= end for stamp in frame.index]]
    if window.empty:
        return {"trades": 0, "ending_equity": CASH_ACCOUNT, "shares": 0}
    costs = CostModel()
    entry = buy_price(float(window.iloc[0]["open"]), costs)
    exit_ = sell_price(float(window.iloc[-1]["close"]), costs)
    shares = int(np.floor(CASH_ACCOUNT / entry)) if entry > 0 else 0
    if shares < 1:
        return {"trades": 0, "shares": 0, "ending_equity": CASH_ACCOUNT, "note": "one share cost more than $1,000"}
    cash = CASH_ACCOUNT - shares * entry
    close = window["close"].astype(float)
    equity = close * shares + cash
    equity.index = pd.DatetimeIndex(window.index)
    ending = cash + shares * exit_
    equity.iloc[-1] = ending
    exposure = pd.Series(np.ones(len(equity)), index=equity.index)
    metrics = compute_metrics(BacktestResult(equity, exposure, pd.DataFrame([{"pnl": ending - CASH_ACCOUNT}])), CASH_ACCOUNT)
    metrics["shares"] = shares
    return metrics


def _chart_days(frame: pd.DataFrame) -> list[date]:
    days = sorted({_day(stamp) for stamp in frame.index})
    if CHART_DAY in days:
        loc = days.index(CHART_DAY)
        return days[max(0, loc - 3) : loc + 1]
    return days[-4:]


def _session(frame: pd.DataFrame, day: date) -> pd.DataFrame:
    return frame.loc[[_day(stamp) == day for stamp in frame.index]]


def _save_chart(frame: pd.DataFrame, day: date, setup: Setup | None, clock: str, path: Path) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    day_bars = _session(frame, day)
    bounds = opening_bounds(day_bars, clock)
    fact = {"date": day.isoformat(), "clock": clock, "path": str(path), "complete": False}
    if bounds is None or day_bars.empty:
        fact["note"] = "no first candle"
        return fact
    or_high, or_low, anchor = bounds
    after = day_bars.loc[day_bars.index > anchor]
    last = day_bars.index[-1]
    fact.update(
        {
            "or_high": or_high,
            "or_low": or_low,
            "or_bar": str(anchor),
            "close": float(day_bars.iloc[-1]["close"]),
            "high_after": float(after["high"].max()) if len(after) else None,
            "low_after": float(after["low"].min()) if len(after) else None,
            "complete": bool(last.time() >= time(15, 55) or (clock == "1m" and last.time() >= time(15, 59))),
            "bars": int(len(day_bars)),
        }
    )
    if setup is not None:
        fact["signal"] = setup.direction
        fact["signal_time"] = str(setup.signal_time)
    fig, ax = plt.subplots(figsize=(12.2, 6.2))
    ax.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    x = np.arange(len(day_bars))
    opens = day_bars["open"].to_numpy(dtype=float)
    highs = day_bars["high"].to_numpy(dtype=float)
    lows = day_bars["low"].to_numpy(dtype=float)
    closes = day_bars["close"].to_numpy(dtype=float)
    for i, (opened, high, low, closed) in enumerate(zip(opens, highs, lows, closes)):
        color = "#d7b56d" if day_bars.index[i] <= anchor else ("#7dffa1" if closed >= opened else "#ff8b8b")
        ax.plot([i, i], [low, high], color=color, lw=0.8)
        ax.plot([i, i], [min(opened, closed), max(opened, closed)], color=color, lw=2.4)
    ax.axhline(or_high, color="#4ea3ff", lw=1.1, label=f"first-candle high {or_high:.2f}")
    ax.axhline(or_low, color="#f0c14a", lw=1.1, label=f"first-candle low {or_low:.2f}")
    if setup is not None and setup.signal_time in day_bars.index:
        loc = day_bars.index.get_loc(pd.Timestamp(setup.signal_time))
        if isinstance(loc, slice):
            loc = loc.start
        if isinstance(loc, np.ndarray):
            loc = int(loc[0])
        ax.scatter([int(loc)], [float(day_bars.iloc[int(loc)]["close"])], color="#ffffff", s=36, zorder=3, label="close through")
        fill_i = int(loc) + 1
        if fill_i < len(day_bars):
            ax.scatter([fill_i], [float(day_bars.iloc[fill_i]["open"])], color="#c08bff", s=28, zorder=3, label="next open")
    step = 6 if clock == "5m" else 15
    ticks = list(range(0, len(day_bars), step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([day_bars.index[i].strftime("%H:%M") for i in ticks], rotation=0)
    title = f"SPY {clock} {day.isoformat()}. Opening range is the 09:30-09:35 candle only. Example only."
    ax.set_title(title, color="#f2f2f2")
    ax.tick_params(colors="#cccccc")
    ax.legend(facecolor="#222222", edgecolor="#333333", labelcolor="#f2f2f2", fontsize=8)
    for spine in ax.spines.values():
        spine.set_color("#333333")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return fact


def _compare_1m(five: pd.DataFrame, one: pd.DataFrame) -> list[dict]:
    rows = []
    days = sorted(set(_sessions({"SPY": five})) & set(_sessions({"SPY": one})))
    for day in days:
        left = opening_bounds(_session(five, day), "5m")
        right = opening_bounds(_session(one, day), "1m")
        rows.append(
            {
                "date": day.isoformat(),
                "five_high": None if left is None else left[0],
                "five_low": None if left is None else left[1],
                "one_high": None if right is None else right[0],
                "one_low": None if right is None else right[1],
                "match": bool(
                    left is not None
                    and right is not None
                    and abs(left[0] - right[0]) < 0.02
                    and abs(left[1] - right[1]) < 0.02
                ),
            }
        )
    return rows


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items() if not str(key).startswith("_")}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (np.floating, np.integer)):
        number = float(value)
        return None if not np.isfinite(number) else number
    return value


def _row(name: str, book: dict) -> str:
    metrics = book.get("metrics") or {}
    return (
        f"| {name} | {int(metrics.get('trades') or 0)} | {_pct(metrics.get('win_rate'))} | "
        f"{_pct(book.get('breakeven_after'))} | {_money(metrics.get('expectancy'))} | "
        f"{_pf(metrics.get('profit_factor'))} | {_num(metrics.get('sharpe'))} | "
        f"{_pct(metrics.get('max_drawdown'))} | {_money(metrics.get('ending_equity'))} | "
        f"{int(book.get('pdt_blocked') or 0)} |"
    )


def render(payload: dict) -> str:
    hold = payload["holdout"]
    train = payload["train"]
    lines = [
        START,
        "## First-candle opening range, 09:30-09:35",
        "",
        "Backtests only. The rule was frozen before the score. Nothing was sent to a broker. "
        "The sandbox forward test was not changed, and live trading stays off.",
        "",
        "The opening range is only the first regular-session candle. On the 5-minute chart that is the "
        "09:30 bar, covering 09:30-09:35 ET. The rest of the open does not move the high or the low. "
        "A long is the first later 5-minute close above that high. A short is the first close below that low. "
        "The fill is the next bar's open. One signal per symbol per session. "
        "The confirming-candle variant and the retest-and-hold variant are reported below and were not used to pick an entry.",
        "",
        "The primary share stop is the other side of that candle. The midpoint is a sensitivity. "
        "The primary share target is 1R, then the session close if neither side has traded. "
        "2R and a session-close exit with no R target are sensitivities. "
        "The primary option is the listed strike nearest the spot, 0 DTE, at +15% and -30% of premium. "
        "Before costs that needs a 66.7% win rate. 1 DTE, 7 DTE, and the five-contract ladder "
        "(2 at +15%, 1 at +20%, 1 at +30%, runner at +100%, initial stop -30%) are sensitivities. "
        "The $1,000 book is capped at the legacy pattern-day-trader count, 3 day trades in 5 sessions, "
        "because the account is under $25,000 and these dates sit in the 2026-2027 phase-in. "
        "Blocked entries are counted and not filled.",
        "",
        f"Yahoo's 5-minute file runs {payload['span'][0]} through {payload['span'][1]}, "
        f"{payload['sessions']} sessions. The loader's cap is 55 calendar days, so this is a short sample. "
        "It is not a durable edge and it is under 300 trades. "
        "The holdout is the second half of those sessions. The rule was not refit on it.",
        "",
        "Chart Fanatics spec 7 was a different opening-range breakout. Its default used a 5-minute range on "
        "NQ and ES, a volume filter, an ATR band on the range, a midpoint stop, a 2R target, and a flat by 11:30. "
        "The gated proxy row was 7 trades, win rate 0.0%, average R -10.403, and the verdict was inconclusive. "
        "This study does not use those filters and it does not replace that row. "
        "The hourly opening-range breakout already in the strategy library uses the first hour, not this candle.",
        "",
        "### Oct 6, 2026, and the recent sessions",
        "",
    ]
    for fact in payload["charts"]:
        if fact.get("or_high") is None:
            lines.append(f"{fact['date']}: no first candle in the file.")
            continue
        broke = "the file ends before the close" if not fact.get("complete") else (
            f"after that candle the session traded {_money(fact.get('high_after'))} to {_money(fact.get('low_after'))} "
            f"and closed {_money(fact.get('close'))}"
        )
        signal = fact.get("signal") or "no close through the range"
        lines.append(
            f"{fact['date']} ({fact['clock']}): first-candle high {_money(fact['or_high'])}, "
            f"low {_money(fact['or_low'])}. {broke}. Primary signal: {signal}. Chart: `{fact['path']}`."
        )
    lines.extend(["", "### 1-minute check", ""])
    if not payload["one_minute"]:
        lines.append("Yahoo did not return a 1-minute SPY file for this window. The 5-minute candle is the range that was scored.")
    else:
        matched = sum(1 for row in payload["one_minute"] if row["match"])
        lines.append(
            f"The 1-minute high and low from 09:30 through 09:34 match the 5-minute 09:30 bar on "
            f"{matched} of {len(payload['one_minute'])} overlapping sessions, within two cents. "
            "The 1-minute window is about a week. A score on it is anecdotal and is not the verdict."
        )
        lines.append("")
        lines.append("| Date | 5m high | 5m low | 1m high | 1m low | Match |")
        lines.append("|---|---:|---:|---:|---:|---|")
        for row in payload["one_minute"]:
            lines.append(
                f"| {row['date']} | {_money(row['five_high'])} | {_money(row['five_low'])} | "
                f"{_money(row['one_high'])} | {_money(row['one_low'])} | {'yes' if row['match'] else 'no'} |"
            )
        if payload.get("one_shares"):
            lines.append("")
            lines.append(f"1-minute SPY, same primary share rule, the whole short window: {_bits(payload['one_shares'])}.")
        if payload.get("one_option"):
            lines.append(f"1-minute SPY, 0 DTE +15%/-30%, the whole short window: {_bits(payload['one_option'])}.")
    lines.extend(
        [
            "",
            f"### SPY holdout, {hold[0]} through {hold[1]}",
            "",
            "The verdict is the first row of each table. The other rows were frozen before the score and were not promoted.",
            "",
            "| Book | Trades | Win rate | After-cost BE | Expectancy | PF | Sharpe | Max DD | Ending | PDT blocked |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            _row("shares, opposite stop, 1R", payload["spy_shares"]),
            _row("shares, midpoint stop, 1R", payload["spy_mid"]),
            _row("shares, opposite stop, 2R", payload["spy_2r"]),
            _row("shares, opposite stop, session close", payload["spy_eod"]),
            _row("shares, confirming candle, 1R", payload["spy_confirm"]),
            _row("shares, retest, 1R", payload["spy_retest"]),
            _row("shares, random entries, 1R", payload["spy_random_shares"]),
            "",
            "| Option book | Trades | Win rate | After-cost BE | Expectancy | PF | Sharpe | Max DD | Ending | PDT blocked |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            _row("0 DTE, +15%/-30%, $1,000", payload["spy_0"]),
            _row("1 DTE, +15%/-30%, $1,000", payload["spy_1"]),
            _row("7 DTE, +15%/-30%, $1,000", payload["spy_7"]),
            _row("0 DTE, five-contract ladder, $1,000", payload["spy_ladder"]),
            _row("0 DTE, +15%/-30%, sized", payload["spy_0_sized"]),
            _row("0 DTE, random entries, +15%/-30%", payload["spy_random_option"]),
            "",
            _plain("SPY shares", payload["spy_shares"]),
            "",
            _plain("SPY 0 DTE options", payload["spy_0"]),
            "",
            f"Training, {train[0]} through {train[1]}, same primary rules: shares {_bits(payload['train_shares'])}. "
            f"0 DTE {_bits(payload['train_option'])}.",
            "",
            f"Walk-forward inside training, frozen rule, no re-selection: "
            f"{payload['walk']['share_trades']} share trades, pooled expectancy {_money(payload['walk']['share_expectancy'])}.",
            "",
            f"Sized 0 DTE equity, frozen from the training median that puts the -30% loss near 2% of the account: "
            f"{_money(payload['sized_equity'])}.",
            "",
            f"SPY buy and hold over the holdout, $1,000 whole shares: {payload['spy_hold'].get('shares', 0)} shares, "
            f"ending {_money(payload['spy_hold'].get('ending_equity'))}, "
            f"Sharpe {_num(payload['spy_hold'].get('sharpe'))}, "
            f"max drawdown {_pct(payload['spy_hold'].get('max_drawdown'))}.",
            "",
            "### QQQ and the liquid list",
            "",
            "These rows are secondary. They were not used to change the SPY rule.",
            "",
            f"QQQ shares: {_bits(payload['qqq_shares'])}.",
            "",
            f"QQQ 0 DTE, +15%/-30%: {_bits(payload['qqq_0'])}.",
            "",
            f"Liquid list, one account, primary entry, shares: {_bits(payload['liquid_shares'])}.",
            "",
            f"Liquid list, one account, 0 DTE, +15%/-30%: {_bits(payload['liquid_0'])}.",
            "",
            f"Signals on the full 5-minute file, primary entry: SPY {payload['counts']['spy']}, "
            f"QQQ {payload['counts']['qqq']}, liquid list {payload['counts']['liquid']}. "
            f"Confirming candle {payload['counts']['confirm']}. Retest {payload['counts']['retest']}.",
            "",
            "No sensitivity was promoted after the score. The strategy was not added to "
            "`config/optional_strategies.json`. The default book is still dual momentum.",
            "",
            "```",
            "python3 -m webull_bot.chart_reads.research_orb5",
            "```",
            END_MARK,
            "",
        ]
    )
    return "\n".join(lines)


def _write_results(block: str) -> None:
    path = Path("RESULTS.md")
    text = path.read_text() if path.exists() else ""
    if START in text and END_MARK in text:
        before = text.split(START)[0]
        after = text.split(END_MARK)[1]
        path.write_text(before + block + after.lstrip("\n"))
        return
    path.write_text(text.rstrip() + "\n\n" + block)


def main() -> None:
    rules = frozen_rules()
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(rules, indent=2) + "\n")
    print("RULES FROZEN", RULES_PATH, flush=True)
    if rules["entry"] != ENTRY_PRIMARY or rules["dte"] != DTE_PRIMARY or rules["stop"] != STOP_PRIMARY:
        raise SystemExit("rules file does not match the module")
    print("loading daily", flush=True)
    provider = YFinanceProvider("data/cache/daily_long")
    raw_daily = provider.history(list(LIQUID_BLUE_CHIPS), "2024-01-01", DOWNLOAD_END, interval="1d")
    daily = {}
    for symbol in LIQUID_BLUE_CHIPS:
        frame = raw_daily.get(symbol)
        if frame is None or frame.empty:
            continue
        normal = _naive(frame)
        if len(normal) >= 40:
            daily[symbol] = normal
    realized = _realized(daily)
    frames = _load("5m", list(LIQUID_BLUE_CHIPS), 70)
    if "SPY" not in frames:
        raise SystemExit("SPY 5-minute bars did not load")
    days = _sessions({"SPY": frames["SPY"]})
    split = _half(days)
    if split is None:
        raise SystemExit("not enough SPY sessions")
    train, hold = split
    print(f"sessions {len(days)} {days[0]} {days[-1]} train {train} hold {hold}", flush=True)
    detected = {variant: _detect(frames, "5m", variant, list(LIQUID_BLUE_CHIPS)) for variant in ENTRY_VARIANTS}
    spy = [setup for setup in detected["close"] if setup.symbol == "SPY"]
    qqq = [setup for setup in detected["close"] if setup.symbol == "QQQ"]
    print(f"signals close {len(detected['close'])} spy {len(spy)} qqq {len(qqq)}", flush=True)
    chart_facts = []
    spy_frame = frames["SPY"]
    for day in _chart_days(spy_frame):
        chosen = next((setup for setup in spy if _day(setup.signal_time) == day), None)
        name = f"orb5_spy_{day.isoformat()}.png"
        chart_facts.append(_save_chart(spy_frame, day, chosen, "5m", CHART_DIR / name))
        print(f"  chart {day}", flush=True)
    one = _load("1m", ["SPY", "QQQ"], 8)
    one_rows = _compare_1m(spy_frame, one["SPY"]) if "SPY" in one else []
    one_shares = None
    one_option = None
    if "SPY" in one:
        one_signals = find_orb(one["SPY"], "SPY", "1m", "close")
        one_shares = _shares(one_signals, {"SPY": one["SPY"]}, SHARE_R_PRIMARY, STOP_PRIMARY)
        if one_signals:
            one_paths = price_paths(one_signals, {"SPY": one["SPY"]}, realized, DTE_PRIMARY, "1m")
            one_option = _option(one_paths, CASH_ACCOUNT, "cash")
        if CHART_DAY in set(_sessions({"SPY": one["SPY"]})):
            chosen = next((setup for setup in find_orb(one["SPY"], "SPY", "1m", "close") if _day(setup.signal_time) == CHART_DAY), None)
            chart_facts.append(_save_chart(one["SPY"], CHART_DAY, chosen, "1m", CHART_DIR / "orb5_spy_2026-10-06_1m.png"))
    hold_spy = _in_window(spy, hold[0], hold[1])
    train_spy = _in_window(spy, train[0], train[1])
    print("pricing SPY", flush=True)
    priced = {dte: price_paths(spy, frames, realized, dte, "5m") for dte in DTE_LIST}
    print("pricing QQQ and the liquid list at 0 DTE", flush=True)
    qqq_paths = price_paths(qqq, frames, realized, DTE_PRIMARY, "5m")
    liquid_paths = price_paths(detected["close"], frames, realized, DTE_PRIMARY, "5m")
    hold_frames = _slice(frames, hold[0], hold[1])
    random_share_setups = random_setups(hold_spy, hold_frames, seed=SEED)
    random_paths = price_paths(random_share_setups, hold_frames, realized, DTE_PRIMARY, "5m") if random_share_setups else []
    sized = sized_equity(_paths_in(priced[DTE_PRIMARY], train[0], train[1]), PRIMARY_STOP)
    ladder_sized = _ladder_equity(_paths_in(priced[DTE_PRIMARY], train[0], train[1]))
    print(f"sized equity {sized} ladder {ladder_sized}", flush=True)
    spy_shares = _shares(hold_spy, frames, SHARE_R_PRIMARY, STOP_PRIMARY)
    books = {
        "spy_shares": spy_shares,
        "spy_mid": _shares(hold_spy, frames, SHARE_R_PRIMARY, "mid"),
        "spy_2r": _shares(hold_spy, frames, 2.0, STOP_PRIMARY),
        "spy_eod": _shares(hold_spy, frames, None, STOP_PRIMARY),
        "spy_confirm": _shares(
            _in_window([setup for setup in detected["confirm"] if setup.symbol == "SPY"], hold[0], hold[1]),
            frames,
            SHARE_R_PRIMARY,
            STOP_PRIMARY,
        ),
        "spy_retest": _shares(
            _in_window([setup for setup in detected["retest"] if setup.symbol == "SPY"], hold[0], hold[1]),
            frames,
            SHARE_R_PRIMARY,
            STOP_PRIMARY,
        ),
        "spy_random_shares": simulate_shares(
            random_share_setups,
            hold_frames,
            target_r=SHARE_R_PRIMARY,
            starting_equity=CASH_ACCOUNT,
            pdt=True,
        ),
        "spy_0": _option(_paths_in(priced[0], hold[0], hold[1]), CASH_ACCOUNT, "cash"),
        "spy_1": _option(_paths_in(priced[1], hold[0], hold[1]), CASH_ACCOUNT, "cash"),
        "spy_7": _option(_paths_in(priced[7], hold[0], hold[1]), CASH_ACCOUNT, "cash"),
        "spy_ladder": simulate_ladder(_paths_in(priced[0], hold[0], hold[1]), starting_equity=CASH_ACCOUNT, mode="cash", pdt=True),
        "spy_0_sized": _option(_paths_in(priced[0], hold[0], hold[1]), sized, "sized") if np.isfinite(sized) else _option([], CASH_ACCOUNT, "cash"),
        "spy_random_option": _option(random_paths, CASH_ACCOUNT, "cash"),
        "train_shares": _shares(train_spy, frames, SHARE_R_PRIMARY, STOP_PRIMARY),
        "train_option": _option(_paths_in(priced[0], train[0], train[1]), CASH_ACCOUNT, "cash"),
        "qqq_shares": _shares(_in_window(qqq, hold[0], hold[1]), frames, SHARE_R_PRIMARY, STOP_PRIMARY),
        "qqq_0": _option(_paths_in(qqq_paths, hold[0], hold[1]), CASH_ACCOUNT, "cash"),
        "liquid_shares": _shares(_in_window(detected["close"], hold[0], hold[1]), frames, SHARE_R_PRIMARY, STOP_PRIMARY),
        "liquid_0": _option(_paths_in(liquid_paths, hold[0], hold[1]), CASH_ACCOUNT, "cash"),
    }
    train_days = [day for day in days if train[0] <= day <= train[1]]
    folds = []
    if len(train_days) >= 8:
        cuts = [0, len(train_days) // 4, len(train_days) // 2, (3 * len(train_days)) // 4, len(train_days)]
        folds = [(train_days[cuts[index]], train_days[cuts[index + 1] - 1]) for index in range(1, 4)]
    walk = _walk(spy, frames, folds, priced[0]) if folds else {"folds": [], "share_expectancy": None, "share_trades": 0}
    payload = {
        "span": [days[0].isoformat(), days[-1].isoformat()],
        "sessions": len(days),
        "train": [train[0].isoformat(), train[1].isoformat()],
        "holdout": [hold[0].isoformat(), hold[1].isoformat()],
        "charts": chart_facts,
        "one_minute": one_rows,
        "one_shares": one_shares,
        "one_option": one_option,
        "sized_equity": sized,
        "ladder_sized_equity": ladder_sized,
        "walk": walk,
        "spy_hold": _spy_hold(daily.get("SPY"), hold[0], hold[1]),
        "counts": {
            "spy": len(spy),
            "qqq": len(qqq),
            "liquid": len(detected["close"]),
            "confirm": len([setup for setup in detected["confirm"] if setup.symbol == "SPY"]),
            "retest": len([setup for setup in detected["retest"] if setup.symbol == "SPY"]),
        },
        **books,
    }
    block = render(payload)
    _write_results(block)
    public = _jsonable({key: (_public(value) if isinstance(value, dict) and "metrics" in value else value) for key, value in payload.items()})
    REPORT_PATH.write_text(json.dumps(public, indent=2) + "\n")
    print(block, flush=True)
    print("WROTE", REPORT_PATH, flush=True)


if __name__ == "__main__":
    main()
