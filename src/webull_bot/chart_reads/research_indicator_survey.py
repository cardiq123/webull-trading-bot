"""Run the frozen indicator survey and write the report. No orders.

The holdout is scored once, after the rounds, and is not used to choose
a refinement. A book that fails the share checks is not promoted by an
option price.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.indicator_survey import (
    GROWTH_DOLLAR_VOLUME,
    HOLDOUT_END,
    HOLDOUT_START,
    LIQUID_GROWTH,
    LIQUID_TECH,
    PRIOR_END,
    PRIOR_START,
    SELECT_END,
    SELECT_START,
    TECH_DOLLAR_VOLUME,
    UNIVERSE,
    buy_and_hold,
    frozen_rules,
    option_report,
    prepare,
    run_search,
    score_holdout,
    score_years,
)
from webull_bot.data.yfinance_provider import YFinanceProvider

START_MARK = "<!-- INDICATOR_SURVEY_START -->"
END_MARK = "<!-- INDICATOR_SURVEY_END -->"
PRIVATE = {"selection_equity", "prior_equity", "selection_trades", "prior_trades"}


def _load() -> tuple[dict, dict, dict[date, float]]:
    provider = YFinanceProvider("data/cache/survey")
    daily_frames = provider.history(list(UNIVERSE), "2016-01-01", "2026-10-07", "1d")
    hourly_frames = provider.history(list(UNIVERSE), "2020-01-01", "2026-10-07", "60m")
    vix_frame = provider.history(["^VIX"], "2016-01-01", "2026-10-07", "1d")["^VIX"]
    daily = {symbol: prepare(frame, symbol, "1d") for symbol, frame in daily_frames.items()}
    hourly = {symbol: prepare(frame, symbol, "60m") for symbol, frame in hourly_frames.items()}
    vix = {pd.Timestamp(ts).date(): float(value) for ts, value in vix_frame["close"].items() if pd.notna(value)}
    missing = [symbol for symbol in UNIVERSE if symbol not in daily]
    if missing:
        raise RuntimeError(f"missing daily history for {missing}")
    return daily, hourly, vix


def _money(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"${value:,.0f}"


def _num(value: float | None, digits: int = 2) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def _pct(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _pf(metrics: dict) -> str:
    value = metrics.get("profit_factor")
    if value is None and metrics.get("trades"):
        return "inf"
    return _num(value)


def _row(cell: dict, window: str) -> str:
    metrics = cell[window]
    other = cell["selection_5k" if window == "selection" else "prior_5k"]
    breakeven = metrics.get("breakeven_win_rate")
    per_year = None
    if metrics.get("years"):
        per_year = metrics["trades"] / metrics["years"]
    tickers = ", ".join(
        f"{symbol} {bucket['trades']} ({_money(bucket['pnl'])})"
        for symbol, bucket in sorted(cell.get("by_symbol", {}).items(), key=lambda item: -item[1]["pnl"])
    )
    if window != "selection":
        tickers = ""
    return (
        f"| {cell['id']} | {window} | {metrics['trades']} | {_num(per_year, 1)} | {_pct(metrics['win_rate'])} | "
        f"{_pct(breakeven)} | {_pf(metrics)} | {_num(metrics['sharpe'])} | {_pct(metrics['max_drawdown'])} | "
        f"{_money(metrics['ending_equity'])} | {_money(other['ending_equity'])} |"
    )


def _option_cells(search: dict) -> list[dict]:
    cells = search["cells"]
    passed = [cell for cell in cells if cell["selection_pass"] and cell["prior_pass"]]
    if passed:
        passed.sort(key=lambda cell: (-float(cell["prior"]["sharpe"]), cell["id"]))
        return passed[:3]
    pool = []
    for cell in cells:
        if cell["timeframe"] != "1d":
            continue
        profit_factor = cell["selection"].get("profit_factor")
        if profit_factor is None or float(profit_factor) >= 1.0:
            pool.append(cell)
    pool.sort(key=lambda cell: (-float(cell["prior"]["sharpe"]), cell["id"]))
    return pool[:3]


def _sanitize(value):
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items() if key not in PRIVATE}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (date, pd.Timestamp)):
        return pd.Timestamp(value).date().isoformat()
    return value


def _curve(series: pd.Series | None) -> list[list]:
    if series is None or len(series) == 0:
        return []
    return [[pd.Timestamp(stamp).date().isoformat(), round(float(value), 2)] for stamp, value in series.items()]


def _chart(path: Path, featured: dict, holdout_row: dict, spy: dict, passed: bool) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=False)
    panels = (
        ("Prior years, fresh $1,000", featured.get("prior_equity"), spy.get("prior")),
        ("Selection year, fresh $1,000", featured.get("selection_equity"), spy.get("selection")),
        ("Holdout, scored once, fresh $1,000", holdout_row.get("equity"), spy.get("holdout")),
    )
    for axis, (title, strategy, benchmark) in zip(axes, panels):
        if strategy is not None and len(strategy):
            axis.plot(strategy.index, strategy.to_numpy(), label=featured["id"], color="#1f4e79")
        if benchmark is not None and len(benchmark):
            axis.plot(benchmark.index, benchmark.to_numpy(), label="SPY buy and hold", color="#b35c00")
        axis.axhline(1000, color="0.6", linewidth=0.6)
        axis.set_title(title)
        axis.set_ylabel("Equity")
        axis.legend(loc="best", fontsize=8)
    status = "passed the search checks" if passed else "not a survivor"
    fig.suptitle(f"{featured['id']} ({status})")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _volume_lines() -> list[str]:
    lines = ["Growth, average daily dollar volume, 2025-10-08 through 2026-10-06:"]
    for name, value in list(GROWTH_DOLLAR_VOLUME.items())[:5]:
        mark = " frozen" if name in LIQUID_GROWTH else ""
        lines.append(f"- {name}: ${value / 1e9:.2f} billion{mark}")
    lines.append("Tech:")
    for name, value in list(TECH_DOLLAR_VOLUME.items())[:5]:
        mark = " frozen" if name in LIQUID_TECH else ""
        lines.append(f"- {name}: ${value / 1e9:.2f} billion{mark}")
    return lines


def render(search: dict, holdout: dict, years: list[dict], options: dict) -> str:
    cells = {cell["id"]: cell for cell in search["cells"]}
    survivors = [cells[name] for name in search["survivor_ids"]]
    n = search["n_combos"]
    rounds = search["rounds"]
    if survivors:
        lead = (
            f"{len(survivors)} strategy passed the selection window, the prior-year window, "
            f"Benjamini-Hochberg q ≤ 0.10, deflated Sharpe ≥ 0.95, and a Sharpe above the seed-17 random book. "
            f"{n} combinations were counted, across round 1 ({rounds.get('1', 0)}), "
            f"round 2 ({rounds.get('2', 0)}), and round 3 ({rounds.get('3', 0)})."
        )
    else:
        lead = (
            f"No strategy passed every check. {n} combinations were counted, across round 1 "
            f"({rounds.get('1', 0)}), round 2 ({rounds.get('2', 0)}), and round 3 ({rounds.get('3', 0)}). "
            "The gate was not loosened after the scores."
        )
    lines = [
        START_MARK,
        "### Indicator and pattern survey",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. No sandbox book was added. "
        "The chop-breakout order rules were not changed.",
        "",
        lead,
        "",
        "Selection is 2025-10-08 through 2026-07-06. Prior years are 2018-01-01 through 2025-10-07, with the rules frozen. "
        "The holdout is 2026-07-07 through 2026-10-06 and was scored once, after the rounds. "
        "A cell needs 20 selection trades and 80 prior-year trades, profit factor 1.10, Sharpe 0.40, "
        "max drawdown no worse than -30%, and ending equity above the start. "
        "The share book is long-only, whole shares, 1% of equity to the stop, at most three new entries a day, "
        "cash settlement the next session. Costs are 5 bps slippage, 1 bp half-spread, SEC $20.60 per million dollars sold, "
        "and FINRA TAF $0.000195 per share capped at $9.79.",
        "",
        "Yahoo 15-minute history is about 60 days and falls inside the holdout, so 15-minute bars were not scored. "
        "Yahoo hourly history starts in October 2024. Those four cells are in the trial count and cannot pass the 2018 prior-year check.",
        "",
        "Universe, ranked by trailing dollar volume before any signal was scored: SPY, the Magnificent Seven "
        "(AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA), growth PLTR, MSTR, HOOD, and tech MU, AMD, AVGO.",
        "",
        *_volume_lines(),
        "",
        "A cash account does not use the margin pattern-day-trade block. Same-day round trips are still counted. "
        "Under $25,000, a margin account would be limited; this test does not refuse the fourth day trade.",
        "",
    ]
    header = (
        "| Strategy | Window | Trades | Trades/yr | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 |"
    )
    rule = "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    if survivors:
        lines.extend(["Search survivors:", "", header, rule])
        for cell in survivors:
            lines.append(_row(cell, "selection"))
            lines.append(_row(cell, "prior"))
            lines.append("")
            lines.append(cell["plain"])
            lines.append("")
    else:
        lines.append("There is no search survivor.")
        lines.append("")
    if holdout["rows"]:
        if holdout["labeled_non_survivor"]:
            lines.append(
                "The holdout was scored once on the best prior-year Sharpe among daily cells, because nothing had passed. "
                "That score is not a pass and was not used to pick a refinement."
            )
        else:
            lines.append("The holdout was scored once on the strategies that had already passed. It was not used to choose them.")
        lines.append("")
        lines.append("| Strategy | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in holdout["rows"]:
            metrics = row["metrics_1k"]
            lines.append(
                f"| {row['id']} | {metrics['trades']} | {_pct(metrics['win_rate'])} | {_pct(metrics.get('breakeven_win_rate'))} | "
                f"{_pf(metrics)} | {_num(metrics['sharpe'])} | {_pct(metrics['max_drawdown'])} | "
                f"{_money(metrics['ending_equity'])} | {_money(row['metrics_5k']['ending_equity'])} |"
            )
        lines.append("")
    benches = search["benchmarks"]
    lines.extend(
        [
            "Buy and hold, same costs, whole shares:",
            "",
            f"- Selection SPY $1,000 ends {_money(benches['selection_spy_1k']['ending_equity'])}, Sharpe {_num(benches['selection_spy_1k']['sharpe'])}.",
            f"- Selection equal-weight basket $1,000 ends {_money(benches['selection_basket_1k']['ending_equity'])}, Sharpe {_num(benches['selection_basket_1k']['sharpe'])}.",
            f"- Prior SPY $1,000 ends {_money(benches['prior_spy_1k']['ending_equity'])}, Sharpe {_num(benches['prior_spy_1k']['sharpe'])}.",
            f"- Prior equal-weight basket $1,000 ends {_money(benches['prior_basket_1k']['ending_equity'])}, Sharpe {_num(benches['prior_basket_1k']['sharpe'])}.",
            f"- Holdout SPY $1,000 ends {_money(holdout['benchmarks']['spy_1k']['ending_equity'])}, Sharpe {_num(holdout['benchmarks']['spy_1k']['sharpe'])}.",
            f"- Holdout equal-weight basket $1,000 ends {_money(holdout['benchmarks']['basket_1k']['ending_equity'])}, Sharpe {_num(holdout['benchmarks']['basket_1k']['sharpe'])}.",
            "",
        ]
    )
    near = [cells[name] for name in search["near_miss_ids"]]
    lines.extend(["Near-misses refined in round 2, ranked by prior-year Sharpe:", "", header, rule])
    if not near:
        lines.append("| none | | | | | | | | | | |")
    for cell in near:
        lines.append(_row(cell, "selection"))
        lines.append(_row(cell, "prior"))
    lines.append("")
    ranked = sorted((cell for cell in search["cells"] if cell["timeframe"] == "1d"), key=lambda cell: -float(cell["prior"]["sharpe"]))[:8]
    lines.extend(["Highest prior-year Sharpe, daily cells, whether or not they were near-misses:", "", header, rule])
    for cell in ranked:
        lines.append(_row(cell, "prior"))
        q_value = "n/a" if cell.get("q") is None else f"{cell['q']:.3f}"
        dsr = "n/a" if cell.get("dsr") is None else f"{cell['dsr']:.3f}"
        lines.append(
            f"| {cell['id']} selection | q {q_value} | DSR {dsr} | random Sharpe {_num(cell['random_sharpe'])} | "
            f"selection Sharpe {_num(cell['selection']['sharpe'])} | PF {_pf(cell['selection'])} | "
            f"trades {cell['selection']['trades']} | prior pass {cell['prior_pass']} | selection pass {cell['selection_pass']} | | |"
        )
    lines.append("")
    if years:
        lines.extend(["Year by year for the featured frozen rule, each year a fresh $1,000. This is not an extra trial.", ""])
        lines.append("| Year | Trades | PF | Sharpe | Max DD | Ending |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for row in years:
            metrics = row["metrics"]
            lines.append(
                f"| {row['year']} | {metrics['trades']} | {_pf(metrics)} | {_num(metrics['sharpe'])} | "
                f"{_pct(metrics['max_drawdown'])} | {_money(metrics['ending_equity'])} |"
            )
        lines.append("")
    if options:
        lines.extend(
            [
                "Option prices are Black-Scholes, volatility is the prior close of VIX, strikes are listed, "
                "and the half-spread is the larger of $0.01 and 1.5% of the mid. "
                "0 DTE is priced only when the share trade exits the same session. Multi-day holds use 7 and 14 calendar days. "
                "These dollars did not add trials and cannot promote a book that failed the share checks.",
                "",
            ]
        )
        for name, books in options.items():
            lines.append(f"{name}:")
            for label, book in books.items():
                if not book.get("applicable", True):
                    lines.append(f"- {label}: {book.get('note', 'not priced')}")
                else:
                    lines.append(
                        f"- {label}: {book['trades']} filled, skipped {book['skipped']}, "
                        f"P&L {_money(book['pnl'])}, ending {_money(book.get('ending'))}."
                    )
            lines.append("")
    featured = holdout["rows"][0]["id"] if holdout["rows"] else None
    if featured and featured in cells:
        cell = cells[featured]
        lines.append(cell["plain"])
        lines.append(
            f"On the $1,000 selection book, {cell['id']} logged {cell['day_trades_1k']} same-day round trips "
            f"and {cell['pdt_windows_1k']} rolling five-session windows with more than three of them."
        )
        if cell.get("by_symbol"):
            lines.append("Selection P&L by ticker: " + ", ".join(
                f"{symbol} {_money(bucket['pnl'])} on {bucket['trades']}"
                for symbol, bucket in sorted(cell["by_symbol"].items(), key=lambda item: -item[1]["pnl"])
            ) + ".")
        lines.append("")
    lines.extend(
        [
            "The chart is `reports/indicator_survey_equity.png`. The machine-readable summary is `reports/indicator_survey.json`.",
            "",
            "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.",
            "",
            "```",
            "python3 -m webull_bot.chart_reads.research_indicator_survey",
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
        # Keep a single trailing newline boundary.
        updated = existing[:start].rstrip() + "\n\n" + block
        if end < len(existing):
            updated += existing[end:].lstrip("\n")
    else:
        updated = existing.rstrip() + "\n\n" + block
    path.write_text(updated)


def main() -> None:
    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "indicator_survey_rules.json").write_text(json.dumps(frozen_rules(), indent=2) + "\n")
    print("loading", flush=True)
    daily, hourly, vix = _load()
    print(f"daily {len(daily)} hourly {len(hourly)}", flush=True)
    search = run_search(daily, hourly)
    print(f"combos {search['n_combos']} survivors {search['survivor_ids']}", flush=True)
    holdout = score_holdout(daily, hourly, search)
    featured_id = holdout["rows"][0]["id"] if holdout["rows"] else None
    featured = next(cell for cell in search["cells"] if cell["id"] == featured_id) if featured_id else None
    years = score_years(daily, featured["rule_id"], tuple(featured["tokens"])) if featured and featured["timeframe"] == "1d" else []
    options = {}
    for cell in _option_cells(search):
        options[f"{cell['id']} selection $1,000"] = option_report(cell["selection_trades"], daily, vix, 1000.0)
        options[f"{cell['id']} selection $5,000"] = option_report(cell["selection_trades"], daily, vix, 5000.0)
        options[f"{cell['id']} prior $1,000"] = option_report(cell["prior_trades"], daily, vix, 1000.0)
    for row in holdout["rows"]:
        options[f"{row['id']} holdout $1,000 (not a selection input)"] = option_report(row["trades"], daily, vix, 1000.0)
    spy = {
        "selection": buy_and_hold(daily, ("SPY",), SELECT_START, SELECT_END, 1000.0)["equity"],
        "prior": buy_and_hold(daily, ("SPY",), PRIOR_START, PRIOR_END, 1000.0)["equity"],
        "holdout": buy_and_hold(daily, ("SPY",), HOLDOUT_START, HOLDOUT_END, 1000.0, allow_holdout=True)["equity"],
    }
    passed = bool(featured and featured["survivor"])
    if featured:
        _chart(reports / "indicator_survey_equity.png", featured, holdout["rows"][0], spy, passed)
    section = render(search, holdout, years, options)
    payload = {
        "n_combos": search["n_combos"],
        "rounds": search["rounds"],
        "survivor_ids": search["survivor_ids"],
        "near_miss_ids": search["near_miss_ids"],
        "benchmarks": search["benchmarks"],
        "holdout": _sanitize({key: value for key, value in holdout.items() if key != "rows"} | {"rows": [
            {key: value for key, value in row.items() if key not in {"equity", "trades"}} for row in holdout["rows"]
        ]}),
        "years": _sanitize(years),
        "options": _sanitize(options),
        "cells": [_sanitize(cell) for cell in search["cells"]],
        "featured_equity": {
            "id": featured_id,
            "passed": passed,
            "prior": _curve(featured["prior_equity"]) if featured else [],
            "selection": _curve(featured["selection_equity"]) if featured else [],
            "holdout": _curve(holdout["rows"][0]["equity"]) if holdout["rows"] else [],
        },
    }
    (reports / "indicator_survey.json").write_text(json.dumps(payload, indent=2) + "\n")
    (reports / "indicator_survey.md").write_text(section)
    _write_results(section)
    print(section.splitlines()[4] if len(section.splitlines()) > 4 else "wrote report", flush=True)


if __name__ == "__main__":
    main()
