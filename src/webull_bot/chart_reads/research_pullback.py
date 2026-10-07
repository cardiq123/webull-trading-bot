"""Score the frozen strong-trend pullback. The holdout does not change the rules.

Run: ``python3 -m webull_bot.chart_reads.research_pullback``

Nothing is sent to a broker. This does not import or edit the sandbox
forward test.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.liquid import LIQUID_BLUE_CHIPS
from webull_bot.chart_reads.pullback import (
    CASH_ACCOUNT,
    DTE_DEFAULT,
    DTE_SENSITIVITIES,
    EXIT_SENSITIVITIES,
    PRIMARY_STOP,
    PRIMARY_TARGET,
    SEED,
    TIME_BARS,
    find_pullbacks,
    frozen_rules,
    price_paths,
    simulate_premium,
    simulate_shares,
    sized_equity,
)
from webull_bot.chart_reads.research import random_setups
from webull_bot.chart_reads.research_daily import IS_END, OOS_START, SAMPLE_END, SCORE_FROM, _naive
from webull_bot.chart_reads.simulate import _realized
from webull_bot.costs import CostModel, buy_price, sell_price
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.mtf_vwap.detect import rth
from webull_bot.universe_dow import is_member

START = "<!-- CHART_READS_PULLBACK_START -->"
END_MARK = "<!-- CHART_READS_PULLBACK_END -->"
RULES_PATH = Path("reports/pullback_rules.json")
REPORT_PATH = Path("reports/chart_reads_pullback.json")
CHART_DIR = Path("reports/setups")
DOWNLOAD_END = "2026-10-07"
DAILY_TRAIN = (SCORE_FROM, IS_END)
DAILY_HOLDOUT = (OOS_START, SAMPLE_END)
# Replays of the frozen rule inside the training span. The holdout is not a fold.
DAILY_FOLDS = (
    (date(2013, 1, 1), date(2014, 12, 31)),
    (date(2015, 1, 1), date(2016, 12, 31)),
    (date(2017, 1, 1), date(2018, 12, 31)),
)


def _day(stamp) -> date:
    ts = pd.Timestamp(stamp)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("America/New_York")
    return ts.date()


def _in_window(setups, start: date, end: date):
    return [setup for setup in setups if start <= _day(setup.fill_time) <= end]


def _paths_in(paths, start: date, end: date):
    return [path for path in paths if start <= path.fill_date <= end]


def _dow(setups):
    return [setup for setup in setups if is_member(setup.symbol, _day(setup.signal_time))]


def _dow_paths(paths):
    return [path for path in paths if is_member(path.symbol, path.signal_date)]


def _sessions(frames) -> list[date]:
    found = set()
    for frame in frames.values():
        if frame is None or frame.empty:
            continue
        found.update(_day(stamp) for stamp in frame.index)
    return sorted(found)


def _half(days: list[date]) -> tuple[tuple[date, date], tuple[date, date]] | None:
    if len(days) < 4:
        return None
    mid = len(days) // 2
    return (days[0], days[mid - 1]), (days[mid], days[-1])


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
    if trades == 0:
        return (
            f"0 trades, skipped {int(book.get('skipped') or 0)}, "
            f"PDT blocked {int(book.get('pdt_blocked') or 0)}"
        )
    return (
        f"{trades} trades, win {_pct(metrics.get('win_rate'))}, "
        f"after-cost break-even {_pct(book.get('breakeven_after'))}, "
        f"expectancy {_money(metrics.get('expectancy'))}, "
        f"profit factor {_pf(metrics.get('profit_factor'))}, "
        f"Sharpe {_num(metrics.get('sharpe'))}, "
        f"max drawdown {_pct(metrics.get('max_drawdown'))}, "
        f"ending {_money(metrics.get('ending_equity'))}"
    )


def _plain(name: str, book: dict, *, sample: str) -> str:
    metrics = book.get("metrics") or {}
    trades = int(metrics.get("trades") or 0)
    if trades == 0:
        return f"{name}: no {sample} trades, so it does not clear break-even and it is not profitable."
    clears = "clears" if book.get("clears_breakeven") else "does not clear"
    profit = "profitable" if book.get("profitable") else "not profitable"
    before = book.get("breakeven_before")
    before_text = f" The before-cost break-even is {_pct(before)}." if before is not None else ""
    return (
        f"{name}: realized win rate {_pct(metrics.get('win_rate'))} against an after-cost "
        f"break-even of {_pct(book.get('breakeven_after'))}. The win rate {clears} that rate."
        f"{before_text} On the {sample} it is {profit} "
        f"({_money(metrics.get('expectancy'))} expectancy, ending {_money(metrics.get('ending_equity'))} "
        f"from {_money(book.get('starting_equity'))}, {trades} trades)."
    )


def _symbol_rows(trades: list[dict], symbols: list[str]) -> list[dict]:
    grouped: dict[str, list[float]] = {symbol: [] for symbol in symbols}
    for trade in trades:
        grouped.setdefault(trade["symbol"], []).append(float(trade["pnl"]))
    rows = []
    for symbol in symbols:
        pnls = grouped.get(symbol) or []
        if not pnls:
            rows.append({"symbol": symbol, "trades": 0})
            continue
        wins = [pnl for pnl in pnls if pnl > 0]
        rows.append(
            {
                "symbol": symbol,
                "trades": len(pnls),
                "win_rate": len(wins) / len(pnls),
                "expectancy": float(np.mean(pnls)),
                "ending_pnl": float(np.sum(pnls)),
            }
        )
    return rows


def _option_book(paths, equity: float, mode: str, target, stop, time_bars) -> dict:
    return simulate_premium(
        paths,
        target=target,
        stop=stop,
        time_bars=time_bars,
        starting_equity=float(equity),
        mode=mode,
        pdt=True,
    )


def _primary(paths, equity: float, mode: str) -> dict:
    return _option_book(paths, equity, mode, PRIMARY_TARGET, PRIMARY_STOP, None)


def _walk(paths, folds, equity: float) -> dict:
    pnl = 0.0
    trades = 0
    rows = []
    for start, end in folds:
        book = _primary(_paths_in(paths, start, end), equity, "cash")
        metrics = book["metrics"]
        count = int(metrics.get("trades") or 0)
        pnl += float(metrics.get("expectancy") or 0.0) * count
        trades += count
        rows.append({"test": [start.isoformat(), end.isoformat()], "book": _public(book)})
    expectancy = (pnl / trades) if trades else None
    return {"folds": rows, "expectancy": expectancy, "trades": trades}


def _spy_hold(frame: pd.DataFrame, start: date, end: date) -> dict:
    if frame is None or frame.empty:
        return {"trades": 0, "ending_equity": CASH_ACCOUNT, "starting_equity": CASH_ACCOUNT}
    window = frame.loc[[start <= _day(stamp) <= end for stamp in frame.index]]
    if window.empty:
        return {"trades": 0, "ending_equity": CASH_ACCOUNT, "starting_equity": CASH_ACCOUNT, "shares": 0}
    costs = CostModel()
    entry = buy_price(float(window.iloc[0]["open"]), costs)
    exit_ = sell_price(float(window.iloc[-1]["close"]), costs)
    shares = int(np.floor(CASH_ACCOUNT / entry)) if entry > 0 else 0
    if shares < 1:
        return {
            "trades": 0,
            "shares": 0,
            "ending_equity": CASH_ACCOUNT,
            "starting_equity": CASH_ACCOUNT,
            "note": "one share cost more than $1,000",
        }
    cash = CASH_ACCOUNT - shares * entry
    close = window["close"].astype(float)
    equity = close * shares + cash
    equity.index = pd.DatetimeIndex(window.index)
    sold = shares * exit_
    ending = cash + sold
    equity.iloc[-1] = ending
    exposure = pd.Series(np.ones(len(equity)), index=equity.index)
    trades = pd.DataFrame([{"pnl": ending - CASH_ACCOUNT}])
    metrics = compute_metrics(BacktestResult(equity, exposure, trades), CASH_ACCOUNT)
    metrics["shares"] = shares
    return metrics


def _load_intraday(interval: str, lookback_days: int) -> dict[str, pd.DataFrame]:
    provider = YFinanceProvider("data/cache")
    start = (pd.Timestamp(DOWNLOAD_END) - pd.Timedelta(days=lookback_days)).date().isoformat()
    print(f"loading {interval} from {start}", flush=True)
    raw = provider.history(list(LIQUID_BLUE_CHIPS), start, DOWNLOAD_END, interval=interval)
    frames = {}
    for symbol in LIQUID_BLUE_CHIPS:
        frame = raw.get(symbol)
        if frame is None or frame.empty:
            continue
        bars = rth(frame)
        if len(bars) > 50:
            frames[symbol] = bars
    missing = [symbol for symbol in LIQUID_BLUE_CHIPS if symbol not in frames]
    print(f"  {interval} present {len(frames)} missing {missing}", flush=True)
    return frames


def _detect(frames, clock: str) -> list[Setup]:
    found = []
    for symbol in LIQUID_BLUE_CHIPS:
        frame = frames.get(symbol)
        if frame is None:
            continue
        found.extend(find_pullbacks(frame, symbol, clock))
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    return found


def _price(setups, frames, realized, dte: int, clock: str):
    print(f"  pricing {clock} {dte} DTE, {len(setups)} signals", flush=True)
    return price_paths(setups, frames, realized, dte, clock)


def _slice_frames(frames, start: date, end: date) -> dict:
    sliced = {}
    for symbol, frame in frames.items():
        piece = frame.loc[[start <= _day(stamp) <= end for stamp in frame.index]]
        if len(piece) > 5:
            sliced[symbol] = piece
    return sliced


def _latest(setups, direction: str):
    chosen = [setup for setup in setups if setup.direction == direction]
    if not chosen:
        return None
    return max(chosen, key=lambda setup: pd.Timestamp(setup.signal_time))


def _save_chart(frame: pd.DataFrame, setup: Setup, clock: str, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from webull_bot.chart_reads.pullback import _rolling_vwap
    from webull_bot.indicators import ema
    from webull_bot.mtf_vwap.detect import session_vwap

    path.parent.mkdir(parents=True, exist_ok=True)
    bars = frame.sort_index()
    loc = bars.index.get_loc(pd.Timestamp(setup.signal_time))
    if isinstance(loc, slice):
        loc = loc.start
    if isinstance(loc, np.ndarray):
        loc = int(loc[0])
    start = max(0, int(loc) - 80)
    stop = min(len(bars), int(loc) + 21)
    window = bars.iloc[start:stop]
    close = window["close"].astype(float)
    fast = ema(bars["close"].astype(float), 9).reindex(window.index)
    mid = ema(bars["close"].astype(float), 20).reindex(window.index)
    if clock == "1d":
        vwap = _rolling_vwap(bars).reindex(window.index)
        vwap_name = "20-session VWAP"
    else:
        vwap = session_vwap(bars)["vwap"].reindex(window.index)
        vwap_name = "session VWAP"
    fig, ax = plt.subplots(figsize=(12.2, 6.0))
    ax.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    x = np.arange(len(window))
    ax.plot(x, close.to_numpy(), color="#f2f2f2", lw=1.2, label="close")
    ax.plot(x, fast.to_numpy(), color="#4ea3ff", lw=1.0, label="EMA 9")
    ax.plot(x, mid.to_numpy(), color="#f0c14a", lw=1.0, label="EMA 20")
    ax.plot(x, vwap.to_numpy(), color="#c08bff", lw=1.0, label=vwap_name)
    ax.axhline(float(setup.stop), color="#ff6b6b", lw=0.8, ls="--", label="swing")
    signal_x = int(loc) - start
    ax.scatter([signal_x], [float(window.iloc[signal_x]["close"])], color="#7dffa1", s=36, zorder=3, label="signal")
    fill_x = signal_x + 1
    if 0 <= fill_x < len(window):
        ax.scatter([fill_x], [float(window.iloc[fill_x]["open"])], color="#ffffff", s=28, zorder=3, label="next open")
    ax.set_title(
        f"{setup.symbol} {clock} {setup.direction} pullback, { _day(setup.signal_time).isoformat() }. Example only.",
        color="#f2f2f2",
    )
    ax.tick_params(colors="#cccccc")
    ax.legend(facecolor="#222222", edgecolor="#333333", labelcolor="#f2f2f2", fontsize=8)
    for spine in ax.spines.values():
        spine.set_color("#333333")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _clock_block(name, clock, detected, dow, paths, train, hold, frames, realized) -> dict:
    train_paths = _dow_paths(_paths_in(paths, train[0], train[1]))
    hold_paths = _dow_paths(_paths_in(paths, hold[0], hold[1]))
    liquid_hold = _paths_in(paths, hold[0], hold[1])
    print(f"{name}: train paths {len(train_paths)} holdout paths {len(hold_paths)}", flush=True)
    train_cash = _primary(train_paths, CASH_ACCOUNT, "cash")
    equity = sized_equity(train_paths, PRIMARY_STOP)
    train_sized = _primary(train_paths, equity, "sized") if np.isfinite(equity) else None
    hold_cash = _primary(hold_paths, CASH_ACCOUNT, "cash")
    hold_sized = _primary(hold_paths, equity, "sized") if np.isfinite(equity) else None
    liquid = _primary(liquid_hold, CASH_ACCOUNT, "cash")
    if clock == "1d":
        folds = list(DAILY_FOLDS)
    else:
        days = [day for day in _sessions(frames) if train[0] <= day <= train[1]]
        folds = []
        if len(days) >= 8:
            cuts = [0, len(days) // 4, len(days) // 2, (3 * len(days)) // 4, len(days)]
            folds = [(days[cuts[index]], days[cuts[index + 1] - 1]) for index in range(1, 4)]
    walk = _walk(_dow_paths(paths), folds, CASH_ACCOUNT) if folds else {"folds": [], "expectancy": None, "trades": 0}
    sensitivities = []
    for label, target, stop, _time in EXIT_SENSITIVITIES:
        sensitivities.append({"label": label, "book": _public(_option_book(hold_paths, CASH_ACCOUNT, "cash", target, stop, None))})
    sensitivities.append(
        {
            "label": f"time stop {TIME_BARS[clock]} bars, stop -30%",
            "book": _public(_option_book(hold_paths, CASH_ACCOUNT, "cash", None, PRIMARY_STOP, TIME_BARS[clock])),
        }
    )
    dte_rows = []
    for dte in DTE_SENSITIVITIES:
        priced = _price(dow, frames, realized, dte, clock)
        dte_hold = _paths_in(priced, hold[0], hold[1])
        dte_rows.append({"dte": dte, "book": _public(_primary(dte_hold, CASH_ACCOUNT, "cash"))})
    random_source = _in_window(dow, hold[0], hold[1])
    random_frames = _slice_frames(frames, hold[0], hold[1])
    random_book = None
    shuffled = []
    if random_source and random_frames:
        shuffled = _in_window(random_setups(random_source, random_frames, seed=SEED), hold[0], hold[1])
        random_paths = _price(shuffled, frames, realized, DTE_DEFAULT, clock)
        random_book = _primary(random_paths, CASH_ACCOUNT, "cash")
    share_train = simulate_shares(_in_window(dow, train[0], train[1]), frames, clock=clock, starting_equity=CASH_ACCOUNT, pdt=True)
    share_hold = simulate_shares(_in_window(dow, hold[0], hold[1]), frames, clock=clock, starting_equity=CASH_ACCOUNT, pdt=True)
    share_random = None
    if shuffled:
        share_random = simulate_shares(
            shuffled,
            frames,
            clock=clock,
            starting_equity=CASH_ACCOUNT,
            pdt=True,
        )
    return {
        "name": name,
        "clock": clock,
        "train_window": [train[0].isoformat(), train[1].isoformat()],
        "holdout_window": [hold[0].isoformat(), hold[1].isoformat()],
        "signals": len(detected),
        "dow_signals": len(dow),
        "priced": int(sum(1 for path in paths if path.ok)),
        "train_cash": _public(train_cash),
        "sized_equity": equity,
        "train_sized": _public(train_sized) if train_sized else None,
        "hold_cash": _public(hold_cash),
        "hold_sized": _public(hold_sized) if hold_sized else None,
        "liquid_hold": _public(liquid),
        "symbols": _symbol_rows(hold_cash["trades"], list(LIQUID_BLUE_CHIPS)),
        "walk": walk,
        "sensitivities": sensitivities,
        "dte": dte_rows,
        "random": _public(random_book) if random_book else None,
        "share_train": _public(share_train),
        "share_hold": _public(share_hold),
        "share_random": _public(share_random) if share_random else None,
        "_plain_cash": hold_cash,
        "_plain_sized": hold_sized,
        "_plain_share": share_hold,
    }


def _table(rows: list[dict]) -> list[str]:
    lines = [
        "| Symbol | Trades | Win rate | Expectancy | Sum of P&L |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        if int(row.get("trades") or 0) == 0:
            lines.append(f"| {row['symbol']} | 0 | n/a | n/a | n/a |")
            continue
        lines.append(
            f"| {row['symbol']} | {row['trades']} | {_pct(row.get('win_rate'))} | "
            f"{_money(row.get('expectancy'))} | {_money(row.get('ending_pnl'))} |"
        )
    return lines


def _book_row(label: str, book: dict | None) -> str:
    if not book:
        return f"| {label} | n/a | n/a | n/a | n/a | n/a | n/a | n/a |"
    return (
        f"| {label} | {int(book.get('trades') or 0)} | {_pct(book.get('win_rate'))} | "
        f"{_pct(book.get('breakeven_after'))} | {_money(book.get('expectancy'))} | "
        f"{_pf(book.get('profit_factor'))} | {_num(book.get('sharpe'))} | "
        f"{_pct(book.get('max_drawdown'))} | {_money(book.get('ending_equity'))} |"
    )


def render(payload: dict) -> str:
    lines = [
        "## Strong-trend pullback continuation",
        "",
        "BACKTESTS ONLY. The rules were written down before this score, in `reports/pullback_rules.json`. "
        "Nothing was sent to a broker. The sandbox forward test was not changed, and live trading stays off.",
        "",
        "A long needs EMA 9 above EMA 20 above EMA 50, each higher than it was 3 bars ago, the close above "
        "the 200 EMA and above VWAP, and either ADX(14) above 25 or a higher-high and higher-low swing. "
        "The bar then touches the 9 EMA, the 20 EMA, VWAP, or the previous swing low within 0.25 ATR, "
        "closes back at or above that level, and does not trade below the previous swing low. The close "
        "is up from the open and up from the prior close. The previous bar was already in that trend and "
        "was not itself an entry. Short is the mirror, and it buys a put. The fill is the next bar's open. "
        "Intraday VWAP is the session VWAP. Daily VWAP is the 20-session volume-weighted typical price.",
        "",
        "The contract is the listed strike nearest the spot, so the model delta is about 0.50. "
        "The reported exit is +15% of the entry ask and -30% of that ask, 14 calendar days. "
        "Before costs that payoff breaks even at a 66.7% win rate. A limit fills at the limit. "
        "A stop that gaps through fills at the open bid. The same bar cannot take the target if it also "
        "hits the stop. Spreads are the Black-Scholes haircut and the option fees. "
        "+20%/-20%, +15%/-15%, a time stop, and 7 or 30 DTE are sensitivities. They were not used to pick an exit.",
        "",
        "The universe is the pre-registered liquid list: " + ", ".join(LIQUID_BLUE_CHIPS) + ". "
        "The verdict is the point-in-time Dow gate on the signal day. Names that were never in the Dow "
        "stay in the liquid table and cannot pass the gate. The $1,000 book buys two contracts when the "
        "debit fits in $1,000, otherwise one, and it skips a larger debit. The sized book is one contract "
        "at the training median equity that puts the -30% loss near 2% of the account. "
        "The share control uses the same entries, a stop at the swing, a 1.5R target, and the clock's time stop.",
        "",
    ]
    for book in payload["books"]:
        lines.append(f"### {book['name']}")
        lines.append("")
        lines.append(
            f"Window train {book['train_window'][0]} through {book['train_window'][1]}, "
            f"holdout {book['holdout_window'][0]} through {book['holdout_window'][1]}. "
            f"{book['signals']} liquid signals, {book['dow_signals']} after the Dow gate, "
            f"{book['priced']} priced at 14 DTE."
        )
        lines.append("")
        lines.append(_plain(f"{book['name']}, $1,000, 14 DTE, +15%/-30%", book["_plain_cash"], sample="holdout"))
        if book["_plain_sized"] is not None:
            lines.append("")
            lines.append(
                _plain(
                    f"{book['name']}, sized at {_money(book['sized_equity'])}, one contract",
                    book["_plain_sized"],
                    sample="holdout",
                )
            )
        else:
            lines.append("")
            lines.append(f"{book['name']}: the training sample had no priced contract, so there is no sized book.")
        lines.append("")
        lines.append(_plain(f"{book['name']} shares, $1,000, swing stop and 1.5R", book["_plain_share"], sample="holdout"))
        lines.append("")
        lines.append("| Book | Trades | Win rate | After-cost BE | Expectancy | PF | Sharpe | Max DD | Ending |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        lines.append(_book_row("$1,000 train, +15%/-30%", book["train_cash"]))
        lines.append(_book_row("$1,000 holdout, +15%/-30%", book["hold_cash"]))
        lines.append(_book_row("sized holdout, +15%/-30%", book["hold_sized"]))
        lines.append(_book_row("liquid list holdout, not the gate", book["liquid_hold"]))
        lines.append(_book_row("random entries, same exit", book["random"]))
        for row in book["sensitivities"]:
            lines.append(_book_row(row["label"], row["book"]))
        for row in book["dte"]:
            lines.append(_book_row(f"{row['dte']} DTE, +15%/-30%", row["book"]))
        lines.append(_book_row("shares train", book["share_train"]))
        lines.append(_book_row("shares holdout", book["share_hold"]))
        lines.append(_book_row("shares, random entries", book["share_random"]))
        lines.append("")
        walk = book["walk"]
        lines.append(
            f"Walk-forward inside the training span, frozen +15%/-30% rule, no re-selection: "
            f"{int(walk.get('trades') or 0)} trades, pooled expectancy {_money(walk.get('expectancy'))}."
        )
        lines.append("")
        lines.append("Holdout by symbol on the $1,000 Dow-gated option book. A zero means that name had no holdout trade.")
        lines.append("")
        lines.extend(_table(book["symbols"]))
        lines.append("")
        cash = book["hold_cash"]
        lines.append(
            f"Median model delta on the trades that filled: {_num(cash.get('median_delta'))}. "
            f"Skipped {int(cash.get('skipped') or 0)}, PDT blocked {int(cash.get('pdt_blocked') or 0)}, "
            f"overlapped {int(cash.get('overlapped') or 0)}. Exit reasons: {cash.get('reasons') or {}}."
        )
        lines.append("")
    lines.append("### Verdict")
    lines.append("")
    for book in payload["books"]:
        lines.append(_plain(book["name"], book["_plain_cash"], sample="holdout"))
        lines.append("")
    above = []
    for book in payload["books"]:
        for label, key in (
            ("$1,000 options", "hold_cash"),
            ("sized options", "hold_sized"),
            ("shares", "share_hold"),
            ("random options", "random"),
            ("random shares", "share_random"),
        ):
            row = book.get(key) or {}
            if row.get("profitable"):
                above.append(
                    f"{book['name']} {label}, {_money(row.get('ending_equity'))} on {int(row.get('trades') or 0)} trades"
                )
    if above:
        lines.append(
            "Holdout rows above the starting equity: "
            + "; ".join(above)
            + ". A random-entry row is the baseline. It was not used to change the rule."
        )
    else:
        lines.append("No holdout row finished above its starting equity.")
    lines.append("")
    lines.append(
        "No sensitivity was promoted after the score. No cell was wired into the sandbox, "
        "and the forward-test code was left as it is. Not added to `config/optional_strategies.json`. "
        "The default book is still dual momentum."
    )
    lines.append("")
    if payload["charts"]:
        lines.append("Charts, most recent long and short the detector marked, not chosen for P&L: " + ", ".join(f"`{path}`" for path in payload["charts"]) + ".")
        lines.append("")
    spy = payload.get("spy") or {}
    lines.append(
        f"SPY buy and hold over {payload['spy_window'][0]} through {payload['spy_window'][1]}, "
        f"$1,000 whole shares: {int(spy.get('shares') or 0)} shares, ending {_money(spy.get('ending_equity'))}, "
        f"Sharpe {_num(spy.get('sharpe'))}, max drawdown {_pct(spy.get('max_drawdown'))}."
    )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(text: str, path: Path) -> None:
    body = path.read_text() if path.exists() else ""
    block = f"{START}\n{text.rstrip()}\n{END_MARK}\n"
    if START in body and END_MARK in body:
        pre, rest = body.split(START, 1)
        _, post = rest.split(END_MARK, 1)
        path.write_text(pre.rstrip() + "\n\n" + block + post.lstrip("\n"))
        return
    path.write_text(body.rstrip() + "\n\n" + block)


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


def main() -> None:
    rules = frozen_rules()
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(rules, indent=2) + "\n")
    print("RULES FROZEN", RULES_PATH, flush=True)
    if rules["primary_target"] != PRIMARY_TARGET or rules["dte"] != DTE_DEFAULT:
        raise SystemExit("rules file does not match the module")
    print("loading daily", flush=True)
    provider = YFinanceProvider("data/cache/daily_long")
    raw_daily = provider.history(list(LIQUID_BLUE_CHIPS), "2009-01-01", DOWNLOAD_END, interval="1d")
    daily = {}
    for symbol in LIQUID_BLUE_CHIPS:
        frame = raw_daily.get(symbol)
        if frame is None or frame.empty:
            continue
        normal = _naive(frame)
        if len(normal) >= 220:
            daily[symbol] = normal
    missing = [symbol for symbol in LIQUID_BLUE_CHIPS if symbol not in daily]
    print(f"  daily present {len(daily)} missing {missing}", flush=True)
    realized = _realized(daily)
    hourly = _load_intraday("60m", 720)
    m15 = _load_intraday("15m", 55)
    print("detecting", flush=True)
    daily_signals = _detect(daily, "1d")
    hourly_signals = _detect(hourly, "60m")
    m15_signals = _detect(m15, "15m")
    print(
        f"  signals daily {len(daily_signals)} dow {_dow(daily_signals) and len(_dow(daily_signals))} "
        f"60m {len(hourly_signals)} 15m {len(m15_signals)}",
        flush=True,
    )
    charts = []
    for clock, frames, signals in (("60m", hourly, hourly_signals), ("1d", daily, daily_signals), ("15m", m15, m15_signals)):
        for direction in ("long", "short"):
            setup = _latest(signals, direction)
            if setup is None or setup.symbol not in frames:
                continue
            filename = CHART_DIR / f"pullback_{direction}_{clock}.png"
            if filename.exists() and clock != "60m":
                continue
            if any(path.endswith(f"_{direction}_60m.png") for path in charts) and clock != "60m":
                continue
            _save_chart(frames[setup.symbol], setup, clock, filename)
            charts.append(str(filename))
            print(f"  chart {filename}", flush=True)
        if sum(1 for path in charts if "_long_" in path) and sum(1 for path in charts if "_short_" in path):
            break
    books = []
    specs = (
        ("Daily", "1d", daily_signals, daily, DAILY_TRAIN, DAILY_HOLDOUT),
        ("60-minute", "60m", hourly_signals, hourly, None, None),
        ("15-minute", "15m", m15_signals, m15, None, None),
    )
    for name, clock, signals, frames, train, hold in specs:
        days = _sessions(frames)
        if train is None:
            split = _half(days)
            if split is None:
                print(f"{name}: not enough sessions", flush=True)
                continue
            train, hold = split
        paths = _price(signals, frames, realized, DTE_DEFAULT, clock)
        block = _clock_block(name, clock, signals, _dow(signals), paths, train, hold, frames, realized)
        books.append(block)
    spy_window = DAILY_HOLDOUT
    spy = _spy_hold(daily.get("SPY"), spy_window[0], spy_window[1])
    payload = {
        "rules": rules,
        "books": books,
        "charts": charts,
        "spy": spy,
        "spy_window": [spy_window[0].isoformat(), spy_window[1].isoformat()],
        "missing_daily": missing,
    }
    text = render(payload)
    write_report(text, Path("RESULTS.md"))
    REPORT_PATH.write_text(json.dumps(_jsonable(payload), indent=2) + "\n")
    print(text)
    print("WROTE", REPORT_PATH, flush=True)


if __name__ == "__main__":
    main()
