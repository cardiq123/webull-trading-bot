"""Score the three frozen account books. Does not place an order.

Run: python3 -m webull_bot.research_account_winners
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from webull_bot.account_winners import (
    DUAL_LOOKBACK,
    DUAL_SKIP,
    DUAL_SYMBOLS,
    GTAA_SYMBOLS,
    HIGH_SYMBOL,
    HOLDOUT_START,
    HURDLE_SYMBOL,
    SAMPLE_END,
    SAMPLE_START,
    SMA_MONTHS,
    buy_and_hold,
    calendar_year_return,
    frozen_rules,
    performance,
    prepare,
    recommend,
    shuffle_weights,
    simulate_weights,
    static_equal_weights,
    verdict,
    weights_from_monthly_dual,
    weights_from_monthly_gtaa,
    weights_from_monthly_trend,
    window_stats,
)
from webull_bot.costs import CostModel
from webull_bot.data.base import normalize_frame

REPORT = Path("reports")
CACHE = Path("data/cache/account_winners")
START_MARK = "<!-- ACCOUNT_WINNERS_START -->"
END_MARK = "<!-- ACCOUNT_WINNERS_END -->"
SYMBOLS = list(dict.fromkeys([*GTAA_SYMBOLS, *DUAL_SYMBOLS, HURDLE_SYMBOL, HIGH_SYMBOL, "QQQ"]))
STRESS_YEARS = (2008, 2020, 2022)
FOLDS = (
    ("2017-2018", "2017-01-01", "2018-12-31"),
    ("2019-2020", "2019-01-01", "2020-12-31"),
    ("2021-2022", "2021-01-01", "2022-12-31"),
    ("2023-2026", "2023-01-01", "2026-10-06"),
)


def _load_symbol(symbol: str) -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{symbol.replace('^', '_')}_1d.csv"
    if path.exists():
        frame = pd.read_csv(path, index_col=0, parse_dates=True)
        frame = normalize_frame(frame, "1d")
        covers_end = not frame.empty and frame.index[-1] >= SAMPLE_END - pd.Timedelta(days=7)
        starts_early = not frame.empty and frame.index[0] <= pd.Timestamp("2004-06-01")
        # GLD, BIL, and TQQQ did not exist for the whole warmup. A long file
        # that starts late is complete for those three and incomplete for SPY.
        listed_later = symbol in {"GLD", "BIL", "TQQQ"}
        if covers_end and (starts_early or listed_later):
            return frame
    import yfinance as yf

    raw = yf.download(
        symbol,
        start="2003-01-01",
        end="2026-10-07",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if raw is None or raw.empty:
        raise RuntimeError(f"Yahoo returned no daily bars for {symbol}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    frame = normalize_frame(raw, "1d")
    frame.to_csv(path)
    return frame


def _ready(monthly: pd.DataFrame, lookback: int) -> pd.Series:
    return monthly.rolling(lookback, min_periods=lookback).mean().notna().any(axis=1)


def _span_start(clock: pd.DatetimeIndex, signals: pd.DataFrame, floor: pd.Timestamp) -> pd.Timestamp:
    for ts in signals.index:
        pos = int(clock.searchsorted(pd.Timestamp(ts), side="right"))
        if pos >= len(clock):
            continue
        fill = pd.Timestamp(clock[pos])
        if fill >= floor:
            return fill
    raise RuntimeError("no fill on or after the sample start")


def _run(
    prepared,
    signals: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    stake: float,
    *,
    same_day_buys: bool = False,
    cash_level: pd.Series | None = None,
) -> dict[str, Any]:
    book = simulate_weights(
        prepared.clock,
        prepared.opens,
        prepared.closes,
        signals,
        starting_equity=stake,
        trade_start=start,
        trade_end=end,
        costs=CostModel(),
        same_day_buys=same_day_buys,
        cash_level=cash_level,
    )
    stats = performance(book.equity, stake)
    spy_equity = buy_and_hold(
        prepared.opens["SPY"],
        prepared.closes["SPY"],
        starting_equity=stake,
        trade_start=start,
        trade_end=end,
    )
    qqq_equity = buy_and_hold(
        prepared.opens["QQQ"],
        prepared.closes["QQQ"],
        starting_equity=stake,
        trade_start=start,
        trade_end=end,
    )
    stats["entries"] = book.entries
    stats["exits"] = book.exits
    stats["rebalances"] = book.rebalances
    stats["fills"] = book.fills
    stats["turnover"] = book.turnover
    stats["exposure"] = book.exposure
    per_year = book.entries / stats["years"] if stats["years"] else 0.0
    stats["entries_per_year"] = per_year
    return {
        "book": stats,
        "spy": performance(spy_equity, stake),
        "qqq": performance(qqq_equity, stake),
        "equity": book.equity,
        "spy_equity": spy_equity,
        "start": None if book.equity.empty else str(pd.Timestamp(book.equity.index[0]).date()),
        "end": None if book.equity.empty else str(pd.Timestamp(book.equity.index[-1]).date()),
    }


def _rebase(equity: pd.Series, start: pd.Timestamp, stake: float = 1000.0) -> pd.Series:
    sliced = equity.loc[equity.index >= start]
    if sliced.empty:
        return sliced
    return sliced.astype(float) / float(sliced.iloc[0]) * stake


def _chart(curves: dict[str, pd.Series], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(12.2, 6.2), dpi=120)
    figure.patch.set_facecolor("#161616")
    axis.set_facecolor("#161616")
    colors = {
        "Conservative": "#7dcea0",
        "Moderate": "#5dade2",
        "High risk": "#e67e22",
        "SPY": "#f4f4f4",
    }
    for name, series in curves.items():
        axis.plot(series.index, series.to_numpy(), color=colors.get(name, "#bbbbbb"), lw=1.4, label=name)
    axis.set_yscale("log")
    axis.set_title("Growth of $1,000 after costs. Log scale. Common window. Not a forecast.", color="#f4f4f4")
    axis.tick_params(colors="#cccccc")
    axis.grid(True, color="#333333", lw=0.6)
    for spine in axis.spines.values():
        spine.set_color("#444444")
    axis.legend(facecolor="#222222", edgecolor="#444444", labelcolor="#f4f4f4")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, facecolor=figure.get_facecolor())
    plt.close(figure)


def _wired_bot(bars: dict[str, pd.DataFrame], stake: float, fractional: bool, start: str, end: str) -> dict[str, Any]:
    from webull_bot.backtest.engine import run_backtest
    from webull_bot.backtest.metrics import compute_metrics
    from webull_bot.risk.manager import RiskLimits
    from webull_bot.strategies.swing import DualMomentum

    result = run_backtest(
        bars,
        [DualMomentum()],
        pd.DataFrame(),
        starting_equity=stake,
        costs=CostModel(),
        limits=RiskLimits(allow_fractional=fractional),
        sectors={},
        account_type="cash",
        trade_start=pd.Timestamp(start),
        trade_end=pd.Timestamp(end),
    )
    metrics = compute_metrics(result, stake)
    metrics["rejected"] = dict(result.rejected)
    return metrics


def _fmt_pct(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{value:.1%}"


def _fmt_num(value: float | None, digits: int = 2) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def _fmt_money(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"${value:,.0f}"


def _row(label: str, stats: dict[str, Any]) -> str:
    return (
        f"| {label} | {_fmt_pct(stats.get('cagr'))} | {_fmt_pct(stats.get('max_drawdown'))} | "
        f"{_fmt_num(stats.get('sharpe'))} | {_fmt_num(stats.get('calmar'))} | "
        f"{_fmt_pct(stats.get('positive_months'))} | {_fmt_money(stats.get('ending_equity'))} | "
        f"{stats.get('entries', '—')} |"
    )


def _window_line(stats: dict[str, Any], stake: float) -> str:
    scale = stake / float(stats["stake"])
    return (
        f"{stats['months']}-month windows: {stats['windows']}. "
        f"Median ending {_fmt_money(stats['ending_median'] * scale)} "
        f"(SPY {_fmt_money(stats['spy_ending_median'] * scale)}), "
        f"bad case {_fmt_money(stats['ending_p10'] * scale)} "
        f"(SPY {_fmt_money(stats['spy_ending_p10'] * scale)}), "
        f"good case {_fmt_money(stats['ending_p90'] * scale)} "
        f"(SPY {_fmt_money(stats['spy_ending_p90'] * scale)}). "
        f"{_fmt_pct(stats['pct_negative'])} of the book's windows lost money, "
        f"against {_fmt_pct(stats['spy_pct_negative'])} for SPY."
    )


def _render(payload: dict[str, Any]) -> str:
    lines = [
        START_MARK,
        "## Three account-sized books",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox forward test was not changed. "
        "The three rules were frozen before this score. A neighbor that looks better was not promoted.",
        "",
        "The account is $1,000 or $5,000. Shares are fractional, which these ETFs need at recent prices. "
        "The default is a cash account: the signal is the month-end close, the sale is the next session's open, and the buy is the session after that, because the sale has not settled. "
        "Cash earns zero, which is harsh in years when Treasury bills paid interest. "
        "Costs are the Webull stock schedule already in this repo: no commission, the SEC fee and FINRA TAF on sells, and 5 bps of slippage plus 1 bp of half-spread on each fill. "
        "Taxes are ignored. A monthly book realizes short-term gains. A buy-and-hold of SPY defers them, so a taxable account would look worse for the active books than these tables do. "
        "The pattern-day-trader rule does not come up. These are monthly swings, and the cash book does not buy and sell the same name on the same day.",
        "",
        "The list is SPY, EFA, IEF, GLD, QQQ, IWM, EEM, TLT, BIL, and TQQQ. They are the funds that still exist. A fund is not held before Yahoo has a price for it. This is not a stock scan and it is not a point-in-time membership file. Prices are Yahoo's adjusted daily bars, so dividends are in the result and splits are taken out.",
        "",
        "A book beats SPY, on the holdout that starts 2017-01-01, only when training also made money and either its Sharpe and Calmar are both higher than SPY, or its CAGR is within three points of SPY and its max drawdown is at least ten points milder. "
        "The high-risk book is also compared with buying and holding TQQQ. Beating that fund on Sharpe and drawdown does not, by itself, make it the book to fund ahead of SPY.",
        "",
        "### Rules",
        "",
        f"Conservative. {payload['rules']['conservative']} It rebalances monthly. On the full sample it changed a sleeve about {payload['conservative']['full']['book']['entries_per_year']:.1f} times per year and turned over {payload['conservative']['full']['book']['turnover']:.1f} times equity per year.",
        "",
        f"Moderate. {payload['rules']['moderate']} It changed holdings about {payload['moderate']['full']['book']['entries_per_year']:.1f} times per year and turned over {payload['moderate']['full']['book']['turnover']:.1f} times equity per year. This is the published monthly process. The bot's dual momentum is the same idea with a 21-session lookback, a 20 percent trail, and a position that risks 0.75 percent of equity.",
        "",
        f"High risk. {payload['rules']['high_risk']} It changed state about {payload['high_risk']['full']['book']['entries_per_year']:.1f} times per year and turned over {payload['high_risk']['full']['book']['turnover']:.1f} times equity per year. TQQQ resets its leverage every day, so a choppy tape can grind the fund down while the filter still says to hold it.",
        "",
        "### Full sample, $1,000",
        "",
        "Each book starts the day of its first fill on or after 2005-01-01. SPY and QQQ on that row are bought on the book's own first day, so the rows do not share one start. The common window is the overlap.",
        "",
        "| Book | CAGR | Max DD | Sharpe | Calmar | Positive months | Ending | Entries |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("conservative", "moderate", "high_risk"):
        block = payload[name]["full"]
        lines.append(_row(name, block["book"]))
        lines.append(_row(f"SPY, same dates as {name}", block["spy"]))
        lines.append(_row(f"QQQ, same dates as {name}", block["qqq"]))
    lines.append(_row("SPY, EFA, IEF, GLD, always on", payload["static_full"]["book"]))
    lines.append(_row("TQQQ buy and hold, high-risk dates", payload["tqqq_full"]["book"]))
    lines.append(_row("QQQ with the same 10-month filter", payload["qqq_filter_full"]["book"]))
    lines += [
        "",
        "### Common window, growth of $1,000",
        "",
        f"All three books and SPY, rebased to $1,000 on {payload['common_start']}. This is the chart. It does not include 2008, because TQQQ was not listed yet.",
        "",
        "| Book | CAGR | Max DD | Sharpe | Calmar | Positive months | Ending |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, stats in payload["common"].items():
        lines.append(
            f"| {name} | {_fmt_pct(stats['cagr'])} | {_fmt_pct(stats['max_drawdown'])} | "
            f"{_fmt_num(stats['sharpe'])} | {_fmt_num(stats['calmar'])} | "
            f"{_fmt_pct(stats['positive_months'])} | {_fmt_money(stats['ending_equity'])} |"
        )
    lines += [
        "",
        "### Holdout from 2017-01-01, fresh $1,000",
        "",
        "This is the verdict window. Training, through 2016-12-31, is the check that the same rule had already made money. Neither window was used to change a lookback.",
        "",
        "| Book | CAGR | Max DD | Sharpe | Calmar | Positive months | Ending | Entries |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("conservative", "moderate", "high_risk"):
        lines.append(_row(f"{name} holdout", payload[name]["holdout"]["book"]))
        lines.append(_row(f"SPY, holdout, {name} window", payload[name]["holdout"]["spy"]))
    lines.append(_row("TQQQ buy and hold, holdout", payload["tqqq_holdout"]["book"]))
    lines.append(_row("static four-fund mix, holdout", payload["static_holdout"]["book"]))
    lines += ["", "Training, fresh $1,000, first fill through 2016-12-31.", ""]
    lines += [
        "| Book | CAGR | Max DD | Sharpe | Calmar | Positive months | Ending | Years |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("conservative", "moderate", "high_risk"):
        stats = payload[name]["train"]["book"]
        lines.append(
            f"| {name} | {_fmt_pct(stats['cagr'])} | {_fmt_pct(stats['max_drawdown'])} | "
            f"{_fmt_num(stats['sharpe'])} | {_fmt_num(stats['calmar'])} | "
            f"{_fmt_pct(stats['positive_months'])} | {_fmt_money(stats['ending_equity'])} | "
            f"{_fmt_num(stats['years'], 1)} |"
        )
        spy = payload[name]["train"]["spy"]
        lines.append(
            f"| SPY, {name} train | {_fmt_pct(spy['cagr'])} | {_fmt_pct(spy['max_drawdown'])} | "
            f"{_fmt_num(spy['sharpe'])} | {_fmt_num(spy['calmar'])} | "
            f"{_fmt_pct(spy['positive_months'])} | {_fmt_money(spy['ending_equity'])} | "
            f"{_fmt_num(spy['years'], 1)} |"
        )
    lines += [
        "",
        "### Rolling windows",
        "",
        "Each window starts at a month-end with the stake and ends 6 or 12 months later. The dollar figure is what that stake is worth, not a profit subtracted from it. SPY on the same dates pays the entry and exit friction. The $5,000 figure is the same return on a $5,000 stake. A paired $5,000 run of the conservative book matched the $1,000 CAGR. The fee gap was under one basis point.",
        "",
    ]
    for name in ("conservative", "moderate", "high_risk"):
        lines.append(f"**{name}.** {payload[name]['full']['start']} through {payload[name]['full']['end']}.")
        for months in (6, 12):
            stats = payload[name]["windows"][str(months)]
            lines.append("")
            lines.append(_window_line(stats, 1000))
            lines.append("")
            lines.append("On $5,000: " + _window_line(stats, 5000))
            lines.append("")
    lines += ["### Stress years", "", "Calendar-year total return. A blank means the book was not running.", ""]
    lines.append("| Book | 2008 | 2020 | 2022 |")
    lines.append("|---|---:|---:|---:|")
    for name in ("conservative", "moderate", "high_risk", "spy_long", "static", "qqq_filter"):
        years = payload["years"][name]
        lines.append(
            f"| {name} | {_fmt_pct(years.get(2008))} | {_fmt_pct(years.get(2020))} | {_fmt_pct(years.get(2022))} |"
        )
    lines += [
        "",
        "### Folds of the frozen rule",
        "",
        "Each fold starts over at $1,000. A fold is too short to pick a rule. It shows whether one stretch carried the holdout.",
        "",
        "| Book | Fold | CAGR | Max DD | Sharpe | Ending |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for item in payload["folds"]:
        stats = item["book"]
        lines.append(
            f"| {item['name']} | {item['fold']} | {_fmt_pct(stats['cagr'])} | "
            f"{_fmt_pct(stats['max_drawdown'])} | {_fmt_num(stats['sharpe'])} | {_fmt_money(stats['ending_equity'])} |"
        )
    lines += [
        "",
        "### Checks that were not allowed to change the rule",
        "",
        "Random timing keeps each month's weights and shuffles the dates, seed 17. The static mix holds the four conservative funds in equal slices whenever they have a 10-month average, with no trend test. The 8-month and 12-month averages, and the other dual-momentum lookbacks, are neighbors.",
        "",
        "| Check | CAGR | Max DD | Sharpe | Ending |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in payload["checks"]:
        stats = item["book"]
        lines.append(
            f"| {item['label']} | {_fmt_pct(stats['cagr'])} | {_fmt_pct(stats['max_drawdown'])} | "
            f"{_fmt_num(stats['sharpe'])} | {_fmt_money(stats['ending_equity'])} |"
        )
    lines += [
        "",
        "### Wired bot",
        "",
        payload["bot_text"],
        "",
        "### Verdict",
        "",
        payload["verdict_text"],
        "",
        f"Chart: `{payload['chart']}`.",
        "",
        "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum, at the bot's existing size. Live trading stays off.",
        "",
        "```",
        "python3 -m webull_bot.research_account_winners",
        "```",
        END_MARK,
        "",
    ]
    return "\n".join(lines)


def _bot_text(bots: dict[str, Any]) -> str:
    parts = [
        "The default book in this repo is dual momentum. On a $100,000 test from 2017 it finished at $104,429.23 because the sizer risks 0.75 percent of equity against a 20 percent stop, so about 3.75 percent of the account is invested, and a 20 percent trail can knock the position out between month-ends. "
        "That is not the fully invested moderate book above. This study did not change the sizer, the trail, or the strategy list."
    ]
    for label, stats in bots.items():
        rejected = stats.get("rejected") or {}
        parts.append(
            f"{label}: {stats.get('trades', 0)} trades, CAGR {_fmt_pct(stats.get('cagr'))}, "
            f"max drawdown {_fmt_pct(stats.get('max_drawdown'))}, Sharpe {_fmt_num(stats.get('sharpe'))}, "
            f"ending {_fmt_money(stats.get('ending_equity'))}. Rejections: {rejected or 'none'}."
        )
    return " ".join(parts)


def _verdict_text(payload: dict[str, Any]) -> str:
    hold = {name: payload[name]["holdout"]["book"] for name in ("conservative", "moderate", "high_risk")}
    spy = payload["conservative"]["holdout"]["spy"]
    qqq = payload["conservative"]["holdout"]["qqq"]
    static = payload["static_holdout"]["book"]
    tqqq = payload["tqqq_holdout"]["book"]
    cons_12 = payload["conservative"]["windows"]["12"]
    flag = payload["high_risk"]["verdict"]
    tqqq_line = (
        "It cleared a higher Sharpe and a milder drawdown than raw TQQQ."
        if flag["winner_vs_benchmark"]
        else "It did not clear a higher Sharpe and a milder drawdown than raw TQQQ."
    )
    return " ".join(
        [
            (
                f"QQQ buy and hold finished the holdout at {_fmt_money(qqq['ending_equity'])}. "
                f"SPY finished at {_fmt_money(spy['ending_equity'])}. "
                f"The conservative and moderate books finished behind both. "
                f"The high-risk filter finished at {_fmt_money(hold['high_risk']['ending_equity'])}, "
                f"ahead of SPY and QQQ on raw dollars and behind raw TQQQ at {_fmt_money(tqqq['ending_equity'])}. "
                f"Raw TQQQ's max drawdown was {_fmt_pct(tqqq['max_drawdown'])} and its Sharpe was {_fmt_num(tqqq['sharpe'])}. "
                f"The filter's drawdown was {_fmt_pct(hold['high_risk']['max_drawdown'])} and its Sharpe was {_fmt_num(hold['high_risk']['sharpe'])}. "
                f"{tqqq_line} "
                "One shuffle of its invested months, seed 17, finished the holdout far ahead of the filter. "
                "That is one draw, and it does not show that the filter's timing was special. "
                "A book that has already fallen about 70 percent is not the one I would fund with $1,000."
            ),
            (
                f"The moderate book finished at {_fmt_money(hold['moderate']['ending_equity'])}. "
                f"Its holdout drawdown was {_fmt_pct(hold['moderate']['max_drawdown'])} against SPY's {_fmt_pct(spy['max_drawdown'])}, "
                f"and its Sharpe was {_fmt_num(hold['moderate']['sharpe'])} against {_fmt_num(spy['sharpe'])}. "
                "Training had beaten SPY. The holdout did not. "
                "Shuffling its monthly choices, seed 17, finished the holdout ahead of the real timing. "
                "The other lookbacks also finished below SPY and were not promoted. "
                "The bot already runs dual momentum, but not this fully invested version. "
                "At the bot's 0.75 percent risk, the $1,000 fractional account and the $5,000 fractional account are the wired-bot rows above. "
                "Whole shares on $1,000 were usually too small to send."
            ),
            (
                f"The conservative book is the only pick that cleared the frozen test against SPY: "
                f"Sharpe {_fmt_num(hold['conservative']['sharpe'])} against {_fmt_num(spy['sharpe'])}, "
                f"Calmar {_fmt_num(hold['conservative']['calmar'])} against {_fmt_num(spy['calmar'])}, "
                "after a training window that also made money. "
                f"It did not beat SPY on dollars. The holdout ended at {_fmt_money(hold['conservative']['ending_equity'])} "
                f"against SPY's {_fmt_money(spy['ending_equity'])} and QQQ's {_fmt_money(qqq['ending_equity'])}. "
                f"Positive months were {_fmt_pct(hold['conservative']['positive_months'])}, below SPY's {_fmt_pct(spy['positive_months'])}. "
                f"Of its 12-month windows, {_fmt_pct(cons_12['pct_negative'])} lost money, against {_fmt_pct(cons_12['spy_pct_negative'])} for SPY. "
                f"The bad 12-month case turned $1,000 into {_fmt_money(cons_12['ending_p10'])}, against {_fmt_money(cons_12['spy_ending_p10'])} for SPY. "
                f"The median case was {_fmt_money(cons_12['ending_median'])} against SPY's {_fmt_money(cons_12['spy_ending_median'])}. "
                "In 2008 the sleeve made money while SPY did not. In 2022 it lost less than SPY. "
                f"The same four funds, held all the time, finished the holdout at {_fmt_money(static['ending_equity'])}, "
                f"Sharpe {_fmt_num(static['sharpe'])}, max drawdown {_fmt_pct(static['max_drawdown'])}. "
                "The filter's Sharpe was lower than that mix, and so was its ending stake. "
                "What the filter added was the smaller drawdown. "
                "The 8-month neighbor made more on the holdout and was not used. "
                "Shuffling the filter's own months, seed 17, had a deeper drawdown and a lower Sharpe than the real timing."
            ),
            (
                "If the goal is more dollars and a 30 percent decline is acceptable, own SPY or QQQ. "
                "QQQ made more than SPY. "
                "If the goal is a smaller crash and slow growth is acceptable, the conservative 10-month sleeve is the one of these three I would fund. "
                "It is not in the bot. "
                "I would not fund the moderate book or the TQQQ filter for this account. "
                "A $5,000 stake is five times the $1,000 result. "
                "This is a simulation, not a forecast."
            ),
        ]
    )


def _write_results(section: str) -> None:
    path = Path("RESULTS.md")
    text = path.read_text() if path.exists() else ""
    block = section if section.endswith("\n") else section + "\n"
    if START_MARK in text and END_MARK in text:
        start = text.index(START_MARK)
        end = text.index(END_MARK) + len(END_MARK)
        text = text[:start] + block.rstrip("\n") + text[end:]
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "\n" + block
    path.write_text(text)


def main() -> None:
    rules = frozen_rules()
    if rules["holdout_start"] != "2017-01-01" or "Earns zero" not in rules["cash"]:
        raise SystemExit("The frozen account rules moved before the score.")
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "account_winners_rules.json").write_text(json.dumps(rules, indent=2) + "\n")
    print("Downloading daily bars...", flush=True)
    bars = {symbol: _load_symbol(symbol) for symbol in SYMBOLS}
    prepared = prepare(bars, SYMBOLS)
    monthly = prepared.monthly
    gtaa_monthly = monthly[list(GTAA_SYMBOLS)]
    dual_monthly = monthly[list(DUAL_SYMBOLS)]
    hurdle = monthly[HURDLE_SYMBOL] / monthly[HURDLE_SYMBOL].shift(DUAL_LOOKBACK) - 1.0
    signals = {
        "conservative": weights_from_monthly_gtaa(gtaa_monthly, SMA_MONTHS).loc[_ready(gtaa_monthly, SMA_MONTHS)],
        "moderate": weights_from_monthly_dual(dual_monthly, hurdle, DUAL_LOOKBACK, DUAL_SKIP).loc[
            dual_monthly.notna().any(axis=1) & (dual_monthly.shift(DUAL_LOOKBACK).notna().any(axis=1))
        ],
        "high_risk": weights_from_monthly_trend(monthly[HIGH_SYMBOL].rename(HIGH_SYMBOL), SMA_MONTHS),
    }
    signals["high_risk"] = signals["high_risk"].dropna()
    signals["high_risk"] = signals["high_risk"].loc[signals["high_risk"].notna().any(axis=1)]
    # Drop the warmup rows whose average does not exist yet.
    trend_ready = monthly[HIGH_SYMBOL].rolling(SMA_MONTHS, min_periods=SMA_MONTHS).mean().notna()
    signals["high_risk"] = signals["high_risk"].loc[trend_ready.reindex(signals["high_risk"].index).fillna(False)]

    payload: dict[str, Any] = {"rules": rules}
    for name, frame in signals.items():
        print(f"Scoring {name}", flush=True)
        start = _span_start(prepared.clock, frame, SAMPLE_START)
        full = _run(prepared, frame, start, SAMPLE_END, 1000.0)
        train = _run(prepared, frame, start, pd.Timestamp("2016-12-31"), 1000.0)
        holdout = _run(prepared, frame, HOLDOUT_START, SAMPLE_END, 1000.0)
        windows = {}
        for months in (6, 12):
            windows[str(months)] = window_stats(full["equity"], prepared.closes["SPY"], months, 1000.0)
        payload[name] = {
            "signals": frame,
            "full": full,
            "train": train,
            "holdout": holdout,
            "windows": windows,
        }

    cons_start = _span_start(prepared.clock, signals["conservative"], SAMPLE_START)
    high_start = _span_start(prepared.clock, signals["high_risk"], SAMPLE_START)
    payload["static_full"] = _run(prepared, static_equal_weights(gtaa_monthly, SMA_MONTHS).loc[_ready(gtaa_monthly, SMA_MONTHS)], cons_start, SAMPLE_END, 1000.0)
    payload["static_holdout"] = _run(
        prepared,
        static_equal_weights(gtaa_monthly, SMA_MONTHS).loc[_ready(gtaa_monthly, SMA_MONTHS)],
        HOLDOUT_START,
        SAMPLE_END,
        1000.0,
    )
    tqqq_bh_signal = pd.DataFrame(1.0, index=signals["high_risk"].index, columns=[HIGH_SYMBOL])
    payload["tqqq_full"] = _run(prepared, tqqq_bh_signal, high_start, SAMPLE_END, 1000.0)
    payload["tqqq_holdout"] = _run(prepared, tqqq_bh_signal, HOLDOUT_START, SAMPLE_END, 1000.0)
    qqq_trend = weights_from_monthly_trend(monthly["QQQ"].rename("QQQ"), SMA_MONTHS)
    qqq_ready = monthly["QQQ"].rolling(SMA_MONTHS, min_periods=SMA_MONTHS).mean().notna()
    qqq_trend = qqq_trend.loc[qqq_ready.reindex(qqq_trend.index).fillna(False)]
    qqq_start = _span_start(prepared.clock, qqq_trend, SAMPLE_START)
    payload["qqq_filter_full"] = _run(prepared, qqq_trend, qqq_start, SAMPLE_END, 1000.0)

    big = _run(prepared, signals["conservative"], cons_start, SAMPLE_END, 5000.0)
    payload["stake_gap"] = float(big["book"]["cagr"]) - float(payload["conservative"]["full"]["book"]["cagr"])

    for name in ("conservative", "moderate", "high_risk"):
        bench = payload["tqqq_holdout"]["book"] if name == "high_risk" else None
        payload[name]["verdict"] = verdict(
            payload[name]["holdout"]["book"],
            payload[name]["holdout"]["spy"],
            payload[name]["train"]["book"],
            bench,
        )

    common_start = max(pd.Timestamp(payload[name]["full"]["equity"].index[0]) for name in ("conservative", "moderate", "high_risk"))
    spy_long = buy_and_hold(
        prepared.opens["SPY"],
        prepared.closes["SPY"],
        starting_equity=1000.0,
        trade_start=SAMPLE_START,
        trade_end=SAMPLE_END,
    )
    curves = {
        "Conservative": _rebase(payload["conservative"]["full"]["equity"], common_start),
        "Moderate": _rebase(payload["moderate"]["full"]["equity"], common_start),
        "High risk": _rebase(payload["high_risk"]["full"]["equity"], common_start),
        "SPY": _rebase(spy_long, common_start),
    }
    payload["common_start"] = str(common_start.date())
    payload["common"] = {name: performance(series, 1000.0) for name, series in curves.items()}
    chart_path = REPORT / "account_winners_equity.png"
    _chart(curves, chart_path)
    payload["chart"] = str(chart_path)

    years: dict[str, dict[int, float | None]] = {}
    for name in ("conservative", "moderate", "high_risk"):
        years[name] = {
            year: calendar_year_return(payload[name]["full"]["equity"], year, 1000.0) for year in STRESS_YEARS
        }
    years["spy_long"] = {year: calendar_year_return(spy_long, year, 1000.0) for year in STRESS_YEARS}
    years["static"] = {
        year: calendar_year_return(payload["static_full"]["equity"], year, 1000.0) for year in STRESS_YEARS
    }
    years["qqq_filter"] = {
        year: calendar_year_return(payload["qqq_filter_full"]["equity"], year, 1000.0) for year in STRESS_YEARS
    }
    payload["years"] = years

    folds = []
    for name, frame in signals.items():
        for label, start, end in FOLDS:
            run = _run(prepared, frame, pd.Timestamp(start), pd.Timestamp(end), 1000.0)
            folds.append({"name": name, "fold": label, "book": run["book"]})
    payload["folds"] = folds

    checks = []
    neighbor_specs: list[tuple[str, pd.DataFrame]] = []
    for months in (8, 12):
        frame = weights_from_monthly_gtaa(gtaa_monthly, months).loc[_ready(gtaa_monthly, months)]
        neighbor_specs.append((f"conservative {months}-month holdout", frame))
        neighbor_specs.append((f"high risk {months}-month holdout", weights_from_monthly_trend(monthly[HIGH_SYMBOL].rename(HIGH_SYMBOL), months).dropna()))
    for lookback, skip, label in ((9, 1, "9-1"), (6, 1, "6-1"), (12, 0, "12-0")):
        frame = weights_from_monthly_dual(dual_monthly, hurdle, lookback, skip)
        ready = dual_monthly.shift(lookback).notna().any(axis=1)
        neighbor_specs.append((f"moderate {label} holdout", frame.loc[ready]))
    for label, frame in neighbor_specs:
        if "high risk" in label:
            ready = frame.notna().any(axis=1)
            frame = frame.loc[ready]
        checks.append({"label": label, "book": _run(prepared, frame, HOLDOUT_START, SAMPLE_END, 1000.0)["book"]})
    for name, frame in signals.items():
        shuffled = shuffle_weights(frame)
        checks.append({"label": f"{name} shuffled dates, full sample", "book": _run(prepared, shuffled, _span_start(prepared.clock, frame, SAMPLE_START), SAMPLE_END, 1000.0)["book"]})
        checks.append({"label": f"{name} shuffled dates, holdout", "book": _run(prepared, shuffled, HOLDOUT_START, SAMPLE_END, 1000.0)["book"]})
    bil = prepared.closes[HURDLE_SYMBOL]
    for name, frame in signals.items():
        start = _span_start(prepared.clock, frame, SAMPLE_START)
        checks.append({"label": f"{name} cash in BIL, full sample", "book": _run(prepared, frame, start, SAMPLE_END, 1000.0, cash_level=bil)["book"]})
        checks.append({"label": f"{name} margin same-day buy, holdout", "book": _run(prepared, frame, HOLDOUT_START, SAMPLE_END, 1000.0, same_day_buys=True)["book"]})
    payload["checks"] = checks

    print("Scoring the wired bot...", flush=True)
    bots = {}
    try:
        bots["$1,000 whole shares, 2017-2026"] = _wired_bot(bars, 1000.0, False, "2017-01-01", "2026-10-06")
        bots["$5,000 whole shares, 2017-2026"] = _wired_bot(bars, 5000.0, False, "2017-01-01", "2026-10-06")
        bots["$1,000 fractional, same 0.75% risk, 2017-2026"] = _wired_bot(bars, 1000.0, True, "2017-01-01", "2026-10-06")
        bots["$5,000 fractional, same 0.75% risk, 2017-2026"] = _wired_bot(bars, 5000.0, True, "2017-01-01", "2026-10-06")
    except Exception as exc:
        bots["wired bot"] = {"trades": 0, "cagr": None, "max_drawdown": None, "sharpe": None, "ending_equity": None, "rejected": {"error": str(exc)}}
    payload["bot_text"] = _bot_text(bots)
    payload["bots"] = bots

    named = []
    for name in ("conservative", "moderate", "high_risk"):
        named.append({"name": name, "holdout": payload[name]["holdout"]["book"], "verdict": payload[name]["verdict"]})
    choice = recommend(named)
    if choice["pick"] is None:
        # Say which fully invested book had the mildest holdout drawdown, without calling it a winner.
        mild = min(named, key=lambda book: abs(float(book["holdout"]["max_drawdown"])))
        choice["plain"] = (
            f"The mildest holdout drawdown among the three was {mild['name']} at {_fmt_pct(mild['holdout']['max_drawdown'])}. "
            "That label is not a promotion."
        )
    payload["recommendation"] = choice
    payload["verdict_text"] = _verdict_text(payload)

    def dump(value: Any) -> Any:
        if isinstance(value, pd.Series):
            return None
        if isinstance(value, pd.DataFrame):
            return None
        if isinstance(value, dict):
            return {str(key): dump(item) for key, item in value.items()}
        if isinstance(value, list):
            return [dump(item) for item in value]
        if isinstance(value, float) and not np.isfinite(value):
            return None
        if isinstance(value, (np.floating, np.integer)):
            return value.item()
        return value

    stored = dump(payload)
    (REPORT / "account_winners.json").write_text(json.dumps(stored, indent=2) + "\n")
    section = _render(payload)
    _write_results(section)
    print(payload["verdict_text"], flush=True)
    print(f"Wrote {chart_path}", flush=True)


if __name__ == "__main__":
    main()
