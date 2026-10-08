"""Run the frozen open-versus-support study and write the report.

Research only. The holdout is scored once, after the training search.
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

from webull_bot.chart_reads.dukascopy_spy import prices_are_bid_scale, to_five_minute
from webull_bot.chart_reads.open_support import (
    CATALOG_BY_ID,
    CONTEXT_SYMBOLS,
    GATE_SYMBOLS,
    HEADLINE_ID,
    HOLDOUT_END,
    HOLDOUT_START,
    TRAIN_END,
    TRAIN_START,
    build_views,
    buy_and_hold,
    daily_from_intraday,
    frozen_rules,
    make_signal,
    option_report,
    run_search,
    score_holdout,
    simulate,
    strip_private,
)
from webull_bot.chart_reads.vwap_band_data import ROOT as DUKA_ROOT
from webull_bot.data.yfinance_provider import YFinanceProvider

START_MARK = "<!-- OPEN_SUPPORT_START -->"
END_MARK = "<!-- OPEN_SUPPORT_END -->"
CACHE = Path("data/cache/open_support")
NY = "America/New_York"


def _load_dukascopy_five(symbol: str) -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{symbol}_duka_5m.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    frames = []
    folder = DUKA_ROOT / symbol
    paths = sorted(folder.glob("*.csv"))
    print(f"reading {symbol} {len(paths)} sessions", flush=True)
    for index, path in enumerate(paths, start=1):
        if path.stat().st_size < 40:
            continue
        frame = pd.read_csv(path)
        if frame.empty or "timestamp" not in frame.columns:
            continue
        if not prices_are_bid_scale(frame):
            continue
        frames.append(frame)
        if index % 400 == 0:
            print(f"reading {symbol} {index}/{len(paths)}", flush=True)
    if not frames:
        raise RuntimeError(f"no Dukascopy sessions for {symbol}")
    combined = pd.concat(frames, ignore_index=True)
    index = pd.to_datetime(combined["timestamp"], utc=True).dt.tz_convert(NY)
    out = combined.drop(columns=["timestamp"])
    out.index = pd.DatetimeIndex(index)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    five = to_five_minute(out)
    five.to_pickle(cache)
    print(f"{symbol} 5m {five.index[0]} {five.index[-1]} {len(five)}", flush=True)
    return five


def _daily_csv(symbol: str) -> pd.DataFrame | None:
    for path in (Path(f"data/cache/survey/{symbol}_1d.csv"), Path(f"data/cache/{symbol}_1d.csv")):
        if not path.exists():
            continue
        frame = pd.read_csv(path, parse_dates=["Date"])
        frame = frame.rename(columns={"Date": "date"}).set_index("date").sort_index()
        frame.index = [stamp.date() for stamp in frame.index]
        return frame
    return None


def _dollar_volume(symbols: tuple[str, ...]) -> dict[str, pd.Series]:
    found = {}
    for symbol in symbols:
        frame = _daily_csv(symbol)
        if frame is None or "close" not in frame.columns or "volume" not in frame.columns:
            continue
        series = (frame["close"].astype(float) * frame["volume"].astype(float)).shift(1)
        series.index = frame.index
        found[symbol] = series
    return found


def _vix() -> dict[date, float]:
    path = Path("data/cache/survey/_VIX_1d.csv")
    if not path.exists():
        path = Path("data/cache/_VIX_1d.csv")
    frame = pd.read_csv(path, parse_dates=["Date"])
    out = {}
    for stamp, close in zip(frame["Date"], frame["close"]):
        out[pd.Timestamp(stamp).date()] = float(close)
    return out


def _yahoo_five(symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    provider = YFinanceProvider(CACHE)
    # Yahoo's 5-minute cap is about 60 days. The end date lets a partial session through for the chart.
    history = provider.history(symbols, "2026-08-01", "2026-10-09", interval="5m")
    return history


def _gate_books() -> dict[str, list]:
    volume = _dollar_volume(GATE_SYMBOLS)
    books = {}
    for symbol in GATE_SYMBOLS:
        five = _load_dukascopy_five(symbol)
        books[symbol] = build_views(symbol, five, dollar_volume=volume.get(symbol))
        print(f"{symbol} sessions {len(books[symbol])}", flush=True)
    return books


def _context_books(featured_id: str) -> dict:
    symbols = tuple(symbol for symbol in CONTEXT_SYMBOLS if symbol not in GATE_SYMBOLS)
    print("yahoo 5m " + " ".join(symbols), flush=True)
    try:
        fives = _yahoo_five(symbols)
    except Exception as exc:
        return {"error": str(exc), "symbols": list(symbols)}
    volume = _dollar_volume(symbols)
    books = {}
    coverage = {}
    for symbol in symbols:
        five = fives.get(symbol)
        if five is None or five.empty:
            coverage[symbol] = "missing"
            continue
        daily = _daily_csv(symbol)
        if daily is not None:
            intra = daily_from_intraday(five)
            if not intra.empty and "close" in daily.columns:
                overlap = sorted(set(intra.index).intersection(daily.index))
                if overlap:
                    ratio = float(daily.loc[overlap[-1], "close"]) / float(intra.loc[overlap[-1], "close"])
                    coverage[symbol] = f"{intra.index[0]} {intra.index[-1]} n={len(intra)} daily_ratio={ratio:.4f}"
                    if abs(ratio - 1.0) > 0.02:
                        daily = None
                else:
                    coverage[symbol] = f"{intra.index[0]} {intra.index[-1]} n={len(intra)}"
            else:
                coverage[symbol] = "empty"
        vwap_daily = daily_from_intraday(five) if daily is not None else None
        if daily is not None and vwap_daily is not None and not vwap_daily.empty:
            merged = daily.copy()
            merged["vwap"] = vwap_daily["vwap"]
            daily_for_views = merged
        else:
            daily_for_views = None
        books[symbol] = build_views(symbol, five, daily=daily_for_views, dollar_volume=volume.get(symbol))
    cell = CATALOG_BY_ID[featured_id]
    if not books:
        return {"error": "no yahoo bars", "coverage": coverage, "symbols": list(symbols)}
    book = simulate(books, cell, HOLDOUT_START, HOLDOUT_END, 1000.0, allow_holdout=True)
    book_5k = simulate(books, cell, HOLDOUT_START, HOLDOUT_END, 5000.0, allow_holdout=True)
    return {
        "id": featured_id,
        "coverage": coverage,
        "metrics_1k": book["metrics"],
        "metrics_5k": book_5k["metrics"],
        "long_trades": book["long_trades"],
        "short_trades": book["short_trades"],
        "by_symbol": book["by_symbol"],
        "_book": book,
    }


def _money(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "n/a"
    return f"${value:,.0f}"


def _num(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "n/a"
    return f"{value:.2f}"


def _pct(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "n/a"
    return f"{value:.1%}"


def _pf(metrics: dict) -> str:
    value = metrics.get("profit_factor")
    if value is None:
        return "n/a"
    return _num(value)


def _chart(path: Path, train_equity: pd.Series, hold_equity: pd.Series, spy_train: pd.Series, spy_hold: pd.Series, title: str) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharey=False)
    for ax, equity, spy, label in (
        (axes[0], train_equity, spy_train, "Train"),
        (axes[1], hold_equity, spy_hold, "Holdout, scored once"),
    ):
        if equity is not None and len(equity):
            ax.plot(equity.index, equity.values, color="#0b6e4f", label=title)
        if spy is not None and len(spy):
            ax.plot(spy.index, spy.values, color="#888888", label="SPY buy and hold")
        ax.set_title(label)
        ax.legend(loc="best")
        ax.set_ylabel("Equity")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _intc_chart(path: Path) -> str:
    """INTC on 2026-10-08 if Yahoo has the session. A partial morning is labeled as partial."""
    try:
        five_map = _yahoo_five(("INTC",))
    except Exception as exc:
        return f"INTC 5-minute bars were not downloaded ({exc})."
    five = five_map.get("INTC")
    daily = _daily_csv("INTC")
    if five is None or five.empty or daily is None:
        return "INTC 5-minute or daily bars were missing, so there is no example chart."
    target = date(2026, 10, 8)
    days = sorted({stamp.date() for stamp in five.index})
    chart_day = target if target in days else days[-1]
    intra = daily_from_intraday(five)
    merged = daily.copy()
    merged["vwap"] = intra["vwap"]
    # The daily file stops at the last completed session. The chart day can still
    # use that prior bar. Its own high and low are left empty so they cannot confirm a swing.
    if chart_day not in set(merged.index):
        merged.loc[chart_day] = {column: float("nan") for column in merged.columns}
        merged = merged.sort_index()
    views = build_views("INTC", five, daily=merged)
    view = next((item for item in views if item.day == chart_day), None)
    cell = CATALOG_BY_ID[HEADLINE_ID]
    signal = make_signal(view, cell) if view is not None else None
    session = five[five.index.date == chart_day]
    fig, axes = plt.subplots(2, 1, figsize=(10, 8))
    recent = daily.tail(60)
    axes[0].plot(range(len(recent)), recent["close"].to_numpy(dtype=float), color="#1f4b99")
    axes[0].set_title("INTC daily close, last 60 sessions")
    axes[0].set_ylabel("Close")
    if not session.empty:
        axes[1].plot(range(len(session)), session["close"].to_numpy(dtype=float), color="#1f4b99")
        if view is not None and np.isfinite(view.support["prior_day"]):
            axes[1].axhline(view.support["prior_day"], color="#a33b20", linestyle="--", label="prior-day low")
            axes[1].legend(loc="best")
        axes[1].set_title(f"INTC 5-minute close, {chart_day.isoformat()}")
        axes[1].set_ylabel("Close")
    note = "the headline rule did not fire"
    if signal is not None:
        note = f"headline rule fired {signal['side']} at {signal['fill']:.2f}, stop {signal['stop']:.2f}"
    elif view is not None:
        note = (
            f"the headline rule did not fire. Open {view.first_open:.2f}, first close {view.first_close:.2f}, "
            f"prior low {view.support['prior_day']:.2f}, 20 EMA trend {view.trend['ema20']}"
        )
    partial = ""
    if chart_day == target and not session.empty:
        last = session.index[-1]
        if last.hour < 15:
            partial = " The session is partial."
    if chart_day != target:
        partial = " 2026-10-08 was not in the file, so this is the latest session instead."
    fig.suptitle(f"INTC {chart_day.isoformat()}. {note}.{partial}")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return f"Example chart `{path.as_posix()}`: {note}.{partial}"


def _render(search: dict, holdout: dict, benchmarks: dict, options: dict, context: dict, chart_note: str) -> str:
    cells = {row["id"]: row for row in search["cells"]}
    survivors = [cells[name] for name in search["survivor_ids"]]
    if survivors:
        lead = f"{len(survivors)} cells passed the training gate, FDR, deflated Sharpe, and the random-entry bar."
    else:
        lead = (
            f"No cell passed every training check. {search['n_combos']} combinations were counted. "
            "The gate was not loosened after the scores."
        )
    lines = [
        START_MARK,
        "### Open versus support",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. No sandbox book was added.",
        "",
        lead,
        "",
        "The rule is Paul's: when the stock opens above support in an uptrend, go long; when it opens below support in a downtrend, go short. "
        "The first 5-minute candle has to close in that direction and beyond the level. The fill is the 09:35 open. "
        "Support is the prior-day low or the last confirmed 3, 5, or 10 day swing. Trend is the daily 20 EMA, the 50 EMA, or higher-high/higher-low structure. "
        "Stops are the crossed level or the first candle. Targets are 1R, 2R, the prior close, the prior session VWAP, or the session close. "
        "A long-only open above resistance is a separate family. One extra cell allows five entries a day.",
        "",
        "Training is 2018-01-01 through 2026-07-06. The holdout is 2026-07-07 through 2026-10-06 and was scored once. "
        "A pass needs 80 training trades, profit factor 1.10, Sharpe 0.40, max drawdown no worse than -30%, ending equity above the start, "
        "q ≤ 0.10, deflated Sharpe ≥ 0.95, and a training Sharpe above the seed-17 random book. "
        "The share book is whole shares, 1% of equity to the stop, at most three new entries a day. "
        "Costs are 5 bps slippage, 1 bp half-spread, SEC $20.60 per million dollars sold, and FINRA TAF. "
        "A cash account cannot short. The short share book is the research expression. Puts are the account expression. "
        "Every one of these is a day trade. The count is reported and the trade is not refused.",
        "",
        "SPY and QQQ use Dukascopy 1-minute bids from 2017-02-16 through 2026-10-06, resampled to 5 minutes. "
        "Those bids are the gate. The other names have about 60 Yahoo 5-minute days, which sit inside the holdout, so they are not in the trial count. "
        "That short book is one look at the cell the training search already picked.",
        "",
    ]
    if survivors:
        lines.append("Training survivors:")
    else:
        lines.append(
            "There is no training survivor. Every cell that traded finished the $1,000 book below the start. "
            "Two long-only cells never traded: after a gap above the prior high, the prior close and the prior VWAP sit on the wrong side of the fill, so those targets are skipped."
        )
    lines.append("")
    headline = cells.get(HEADLINE_ID)
    if headline is not None:
        metrics = headline["train"]
        lines.append(
            f"Paul's wording, frozen as `{HEADLINE_ID}`: prior-day low, daily 20 EMA, stop at that low, 1R target. "
            f"Training took {metrics['trades']} trades ({headline['long_trades']} long, {headline['short_trades']} short), "
            f"win rate {_pct(metrics['win_rate'])} against a break-even {_pct(metrics.get('breakeven_win_rate'))}, "
            f"profit factor {_pf(metrics)}, Sharpe {_num(metrics['sharpe'])}, max drawdown {_pct(metrics['max_drawdown'])}, "
            f"$1,000 ends {_money(metrics['ending_equity'])}, $5,000 ends {_money(headline['train_5k']['ending_equity'])}. "
            f"q is {float(headline['q']):.3f}, deflated Sharpe is {_num(headline.get('dsr'))}, and the matched random Sharpe is {_num(headline['random_sharpe'])}."
        )
        lines.append("")
    header = "| Strategy | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 | q | DSR | Random |"
    rule = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    traded = [row for row in search["cells"] if int(row["train"]["trades"]) > 0]
    show = survivors or sorted(traded, key=lambda row: -float(row["train"]["sharpe"]))[:8]
    lines.extend([header, rule])
    for row in show:
        metrics = row["train"]
        dsr = "n/a" if row.get("dsr") is None else f"{float(row['dsr']):.3f}"
        lines.append(
            f"| {row['id']} | {metrics['trades']} | {_pct(metrics['win_rate'])} | {_pct(metrics.get('breakeven_win_rate'))} | "
            f"{_pf(metrics)} | {_num(metrics['sharpe'])} | {_pct(metrics['max_drawdown'])} | {_money(metrics['ending_equity'])} | "
            f"{_money(row['train_5k']['ending_equity'])} | {float(row['q']):.3f} | {dsr} | {_num(row['random_sharpe'])} |"
        )
    lines.append("")
    for row in show[:4]:
        lines.append(row["plain"])
        lines.append(
            f"{row['id']} took {row['long_trades']} longs and {row['short_trades']} shorts, "
            f"{row['day_trades_1k']} day trades, and {row['pdt_windows_1k']} five-session windows with more than three."
        )
        lines.append("")
    if holdout["rows"]:
        label = "not a pass" if holdout["labeled_non_survivor"] else "the cells that had already passed"
        lines.append(f"Holdout, scored once, {label}:")
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
    if context.get("error"):
        lines.append(f"The short Yahoo book did not run: {context['error']}.")
    elif context.get("metrics_1k"):
        metrics = context["metrics_1k"]
        five = context["metrics_5k"]
        lines.append(
            f"Yahoo 5-minute book for the other names, `{context['id']}` only, through 2026-10-06: "
            f"the $1,000 account took {metrics['trades']} trades and ended {_money(metrics['ending_equity'])}. "
            f"The $5,000 account took {five['trades']} trades, profit factor {_pf(five)}, Sharpe {_num(five['sharpe'])}, "
            f"and ended {_money(five['ending_equity'])}. A wide stop often does not fit one share in $1,000. "
            "This sample cannot pass."
        )
        lines.append("")
    lines.extend(
        [
            "Buy and hold on the Dukascopy bid, same costs, whole shares:",
            "",
            f"- Train SPY $1,000 ends {_money(benchmarks['train_spy_1k']['ending_equity'])}, Sharpe {_num(benchmarks['train_spy_1k']['sharpe'])}.",
            f"- Train QQQ $1,000 ends {_money(benchmarks['train_qqq_1k']['ending_equity'])}, Sharpe {_num(benchmarks['train_qqq_1k']['sharpe'])}.",
            f"- Holdout SPY $1,000 ends {_money(benchmarks['holdout_spy_1k']['ending_equity'])}, Sharpe {_num(benchmarks['holdout_spy_1k']['sharpe'])}.",
            "",
        ]
    )
    if options:
        lines.append(
            "Option prices are Black-Scholes, one contract, volatility the prior close of VIX. "
            "The half-spread is the larger of $0.01 and 1.5% of the mid, plus the option regulatory schedule. "
            "These dollars did not add trials and cannot promote a book that failed the share checks."
        )
        lines.append("")
        for name, books in options.items():
            lines.append(f"{name}:")
            for label, book in books.items():
                lines.append(
                    f"- {label}: {book['trades']} filled, skipped {book['skipped']}, "
                    f"P&L {_money(book['pnl'])}, ending {_money(book['ending'])}."
                )
            lines.append("")
    lines.extend(
        [
            chart_note,
            "",
            "The equity chart is `reports/open_support_equity.png`. The machine-readable summary is `reports/open_support.json`.",
            "",
            "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.",
            "",
            "```",
            "python3 -m webull_bot.chart_reads.research_open_support",
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


def _metrics_only(book: dict) -> dict:
    return {key: value for key, value in book["metrics"].items()}


def main() -> None:
    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "open_support_rules.json").write_text(json.dumps(frozen_rules(), indent=2) + "\n")
    books = _gate_books()
    search = run_search(books)
    print(f"combos {search['n_combos']} survivors {search['survivor_ids']}", flush=True)
    holdout = score_holdout(books, search)
    featured = holdout["rows"][0]["id"] if holdout["rows"] else HEADLINE_ID
    context = _context_books(featured)
    vix = _vix()
    options = {}
    featured_row = next(row for row in search["cells"] if row["id"] == featured)
    train_book = featured_row["_train_book"]
    hold_book = holdout["rows"][0]["_book"] if holdout["rows"] else None
    options[featured] = {
        "train_callput_0": option_report(train_book["trades"], vix, 1000.0, 0),
        "train_callput_7": option_report(train_book["trades"], vix, 1000.0, 7),
    }
    if hold_book is not None:
        options[featured]["holdout_0"] = option_report(hold_book["trades"], vix, 1000.0, 0)
        options[featured]["holdout_7"] = option_report(hold_book["trades"], vix, 1000.0, 7)
    if context.get("_book"):
        options[featured]["yahoo_0"] = option_report(context["_book"]["trades"], vix, 1000.0, 0)
    benchmarks = {
        "train_spy_1k": _metrics_only(buy_and_hold(books["SPY"], TRAIN_START, TRAIN_END, 1000.0)),
        "train_qqq_1k": _metrics_only(buy_and_hold(books["QQQ"], TRAIN_START, TRAIN_END, 1000.0)),
        "holdout_spy_1k": _metrics_only(buy_and_hold(books["SPY"], HOLDOUT_START, HOLDOUT_END, 1000.0, allow_holdout=True)),
    }
    title = featured if search["survivor_ids"] else f"{featured}, no survivor"
    _chart(
        reports / "open_support_equity.png",
        train_book["equity"],
        hold_book["equity"] if hold_book is not None else pd.Series(dtype=float),
        _hold_path(books["SPY"], TRAIN_START, TRAIN_END, 1000.0),
        _hold_path(books["SPY"], HOLDOUT_START, HOLDOUT_END, 1000.0),
        title,
    )
    chart_note = _intc_chart(reports / "open_support_intc.png")
    public_search, public_holdout = strip_private(search, holdout)
    context_public = {key: value for key, value in context.items() if not key.startswith("_")}
    if "metrics_1k" in context_public:
        context_public["metrics_1k"] = _public_numbers(context_public["metrics_1k"])
        context_public["metrics_5k"] = _public_numbers(context_public["metrics_5k"])
    payload = {
        "search": public_search,
        "holdout": public_holdout,
        "benchmarks": benchmarks,
        "options": options,
        "context": context_public,
        "chart_note": chart_note,
    }
    (reports / "open_support.json").write_text(json.dumps(payload, indent=2, default=_json) + "\n")
    section = _render(search, holdout, benchmarks, options, context_public, chart_note)
    (reports / "open_support.md").write_text(section)
    _write_results(section)
    print(chart_note, flush=True)


def _hold_path(views: list, start: date, end: date, starting: float) -> pd.Series:
    window = [view for view in views if start <= view.day <= end]
    if not window:
        return pd.Series(dtype=float)
    from webull_bot.costs import buy_fees, buy_price, sell_price, sell_regulatory_fees
    from webull_bot.chart_reads.open_support import COSTS

    fill = float(window[0].first_open)
    entry_px = buy_price(fill, COSTS)
    qty = int(math.floor(starting / entry_px)) if entry_px > 0 else 0
    if qty < 1:
        return pd.Series([starting] * len(window), index=pd.to_datetime([view.day for view in window]))
    debit = entry_px * qty + buy_fees(COSTS)
    cash_left = starting - debit
    closes = []
    for index, view in enumerate(window):
        spot = float(view.bars_close[-1])
        if index == len(window) - 1:
            credit = sell_price(spot, COSTS) * qty - sell_regulatory_fees(sell_price(spot, COSTS), qty, COSTS)
            closes.append(cash_left + credit)
        else:
            closes.append(cash_left + spot * qty)
    return pd.Series(closes, index=pd.to_datetime([view.day for view in window]))


def _public_numbers(metrics: dict) -> dict:
    out = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            out[key] = None if not math.isfinite(value) else value
        else:
            out[key] = value
    return out


def _json(value):
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)[:10]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    raise TypeError(type(value))


if __name__ == "__main__":
    main()
