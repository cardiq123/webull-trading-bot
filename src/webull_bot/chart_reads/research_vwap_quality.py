"""Score the frozen VWAP quality, cap, and confirmation family. Backtests only.

Writes the rules file before any account result. Does not place an order,
does not edit the sandbox forward test, and does not add a strategy to the
live list.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.vwap_band import (
    HOLDOUT_START,
    RANDOM_SEED,
    SAMPLE_END,
    TRAIN_END,
    find_signals,
    random_signals,
    simulate,
)
from webull_bot.chart_reads.vwap_band_data import load_minutes, to_fifteen_minute
from webull_bot.chart_reads.vwap_quality import (
    FAMILY,
    FDR_MIN_TRADES,
    FDR_Q,
    benjamini_hochberg,
    build_features,
    cleared,
    confirmation_marks,
    count_by_day,
    freeze_cuts,
    one_sided_p,
    path_of,
    price_signals,
    qqq_covers,
    run_account,
    scored_family,
    select_signals,
    sessions_between,
    summarize_days,
    to_rth_bars,
    trade_t,
    frozen_rules,
)
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.mtf_vwap.detect import rth

START_MARK = "<!-- VWAP_QUALITY_START -->"
END_MARK = "<!-- VWAP_QUALITY_END -->"
RULES_PATH = Path("reports/vwap_quality_rules.json")
JSON_PATH = Path("reports/vwap_quality.json")
CHART_PATH = Path("reports/vwap_quality_2026-10-07.png")
YAHOO_15 = Path("data/cache/SPY_15m.csv")
YAHOO_5 = Path("data/cache/SPY_5m.csv")
NY = "America/New_York"
TODAY = date(2026, 10, 7)


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


def _prepare_iv() -> dict:
    provider = YFinanceProvider(cache_dir="data/cache/vwap_band/yahoo")
    daily = provider.history(["^VIX", "^VIX1D"], "2016-01-01", "2026-10-07", interval="1d")
    closes = {}
    for symbol, frame in daily.items():
        if frame is None or frame.empty or "close" not in frame.columns:
            continue
        series = frame["close"].astype(float).copy()
        index = pd.to_datetime(series.index)
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert(NY).tz_localize(None)
        series.index = index
        closes[symbol] = series[~series.index.duplicated(keep="last")].sort_index()
    return prior_iv(closes.get("^VIX1D", pd.Series(dtype=float)), closes.get("^VIX", pd.Series(dtype=float)))


def _yahoo(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if "Datetime" not in frame.columns:
        return None
    index = pd.to_datetime(frame["Datetime"], utc=True).dt.tz_convert(NY)
    out = frame.drop(columns=["Datetime"])
    out.index = pd.DatetimeIndex(index)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    for column in ("open", "high", "low", "close", "volume"):
        if column in out.columns:
            out[column] = out[column].astype(float)
    return out


def _window_signals(signals: list, start: date | None, end: date | None) -> list:
    from webull_bot.chart_reads.vwap_band import _day_key

    kept = []
    for signal in signals:
        day = _day_key(signal.fill_time)
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        kept.append(signal)
    return kept


def _pack(book: dict, distribution: dict) -> dict:
    metrics = dict(book["metrics"])
    metrics["passes"] = cleared(metrics)
    metrics["bust"] = int(book["skips"].get("bust", 0))
    metrics["survives"] = bool(metrics["ending_equity"] > 1.0 and metrics["bust"] == 0)
    metrics["distribution"] = distribution
    metrics["skips"] = book["skips"]
    return metrics


def _distribution(trades: list[dict], sessions: list[date]) -> dict:
    from webull_bot.chart_reads.vwap_band import _day_key

    counts: dict[date, int] = {}
    for trade in trades:
        day = _day_key(trade["signal_time"])
        counts[day] = counts.get(day, 0) + 1
    return summarize_days(counts, sessions)


def _score_book(frame, priced, sessions, stake: float, start, end, path) -> dict:
    book = run_account(frame, priced, stake=stake, start=start, end=end, path=path)
    packed = _pack(book, _distribution(book["trades"], sessions))
    packed["t"] = trade_t([float(trade["pnl"]) for trade in book["trades"]])
    return packed


def _public_metrics(metrics: dict) -> dict:
    return {key: value for key, value in metrics.items() if key != "equity"}


def _row(name: str, metrics: dict, q_value) -> str:
    dist = metrics.get("distribution") or {}
    q_text = "n/a" if q_value is None else f"{float(q_value):.3f}"
    return (
        f"| {name} | {metrics.get('trades', 0)} | {dist.get('mean', 0):.2f} | "
        f"{_pct(dist.get('pct_gt_3'))} | {_pct(dist.get('pct_gt_5'))} | "
        f"{_pct(metrics.get('win_rate'))} | {_pct(metrics.get('breakeven_win_rate'))} | "
        f"{_pf(metrics.get('profit_factor'))} | {_num(metrics.get('sharpe'))} | "
        f"{_pct(metrics.get('max_drawdown'))} | {_money(metrics.get('ending_equity'))} | "
        f"{'yes' if metrics.get('passes') else 'no'} | {q_text} |"
    )


def _train_row(name: str, metrics: dict, five: dict) -> str:
    survived = "yes" if metrics.get("survives") else "no"
    return (
        f"| {name} | {metrics.get('trades', 0)} | {_pf(metrics.get('profit_factor'))} | "
        f"{_num(metrics.get('sharpe'))} | {_pct(metrics.get('max_drawdown'))} | "
        f"{_money(metrics.get('ending_equity'))} | {_money(five.get('ending_equity'))} | "
        f"{'yes' if metrics.get('passes') else 'no'} | {survived} |"
    )


def _clock(stamp) -> str:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    return clock.strftime("%H:%M")


def _today_lines(rows: list[dict]) -> list[str]:
    if not rows:
        return [
            "The Yahoo 15-minute cache has no 2 SD extension on 2026-10-07 through the last bar in the file. "
            "The 09:30 bar is zero width and is not an extension."
        ]
    lines = [
        "Yahoo 15-minute and 5-minute cache, the same tape as the sandbox dry run. "
        "This day is after the holdout and is not in the score. "
        "A filter keeps a signal when it still accepts it. A delayed fill is a different trade. "
        "The 13:30 long can pass the 15-minute follow-through only when the next 15-minute bar has closed.",
        "",
        "| Signal | Side | 15m follow-through | 5m follow-through | 9/20 and VWAP | Before 10:30 needs 15m |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        waiting = " awaiting fill" if row.get("awaiting_fill") else ""
        lines.append(
            f"| {_clock(row['signal_time'])}{waiting} | {row['direction']} | "
            f"{'yes' if row['confirm_15m'] else 'no'} | "
            f"{'yes' if row['confirm_5m'] else 'no'} | "
            f"{'yes' if row['ema_vwap'] else 'no'} | "
            f"{'yes' if row['early_15m'] else 'no'} |"
        )
    wanted = {("10:00", "short"), ("10:30", "short"), ("11:30", "long"), ("13:30", "long")}
    found = {( _clock(row["signal_time"]), row["direction"]) for row in rows}
    missing = sorted(wanted - found)
    if missing:
        lines += ["", "Missing from the extension list: " + ", ".join(f"{clock} {side}" for clock, side in missing) + "."]

    def _flag(clock: str, key: str) -> str:
        for row in rows:
            if _clock(row["signal_time"]) == clock:
                return "drops" if not row[key] else "keeps"
        return "absent"

    lines += [
        "",
        "15-minute follow-through "
        f"{_flag('10:00', 'confirm_15m')} the 10:00 short, {_flag('10:30', 'confirm_15m')} the 10:30 short, "
        f"{_flag('11:30', 'confirm_15m')} the 11:30 long, and {_flag('13:30', 'confirm_15m')} the 13:30 long.",
        "5-minute follow-through "
        f"{_flag('10:00', 'confirm_5m')} the 10:00 short, {_flag('10:30', 'confirm_5m')} the 10:30 short, "
        f"{_flag('11:30', 'confirm_5m')} the 11:30 long, and {_flag('13:30', 'confirm_5m')} the 13:30 long.",
        "9/20 plus VWAP "
        f"{_flag('10:00', 'ema_vwap')} the 10:00 short, {_flag('10:30', 'ema_vwap')} the 10:30 short, "
        f"{_flag('11:30', 'ema_vwap')} the 11:30 long, and {_flag('13:30', 'ema_vwap')} the 13:30 long.",
        "Before-10:30 confirmation "
        f"{_flag('10:00', 'early_15m')} the 10:00 short, {_flag('10:30', 'early_15m')} the 10:30 short, "
        f"{_flag('11:30', 'early_15m')} the 11:30 long, and {_flag('13:30', 'early_15m')} the 13:30 long.",
    ]
    both_shorts = ("10:00", "10:30")
    both_longs = ("11:30", "13:30")
    removers = []
    for key, label in (
        ("confirm_15m", "15-minute follow-through"),
        ("confirm_5m", "5-minute follow-through"),
        ("ema_vwap", "9/20 plus VWAP"),
        ("early_15m", "before 10:30"),
    ):
        drops_shorts = all(_flag(clock, key) == "drops" for clock in both_shorts)
        keeps_longs = all(_flag(clock, key) == "keeps" for clock in both_longs)
        if drops_shorts and keeps_longs:
            removers.append(label)
    if removers:
        lines.append(
            "These frozen rules remove both losing shorts and still accept both longs: " + ", ".join(removers) + "."
        )
    else:
        lines.append(
            "No frozen confirmation rule removes both the 10:00 and 10:30 shorts and still accepts both the 11:30 and 13:30 longs. "
            "The definitions were not loosened after that count."
        )
    return lines


def _plot_today(frame: pd.DataFrame, rows: list[dict], path: Path) -> None:
    from webull_bot.chart_reads.detect import session_bands

    day = frame[frame.index.date == TODAY]
    if day.empty:
        return
    bands = session_bands(frame, deviations=1.0).reindex(day.index)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(11, 5.5))
    axis.plot(day.index, day["close"], color="#1a5276", label="close")
    upper = bands["vwap"] + 2.0 * bands["std"]
    lower = bands["vwap"] - 2.0 * bands["std"]
    axis.plot(day.index, upper, color="#196f3d", linewidth=0.8, label="upper 2 SD")
    axis.plot(day.index, lower, color="#922b21", linewidth=0.8, label="lower 2 SD")
    for row in rows:
        stamp = pd.Timestamp(row["signal_time"])
        if stamp not in day.index:
            continue
        color = "#196f3d" if row["direction"] == "long" else "#922b21"
        axis.scatter([stamp], [float(day.loc[stamp, "close"])], color=color, zorder=3)
        axis.annotate(_clock(stamp), (stamp, float(day.loc[stamp, "close"])), textcoords="offset points", xytext=(4, 6), fontsize=8)
    axis.set_title("SPY 15-minute, 2026-10-07, Yahoo cache")
    axis.legend(loc="upper left", fontsize=8)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(path, dpi=120)
    plt.close(figure)


def _markdown(payload: dict) -> str:
    lines = [
        START_MARK,
        "## VWAP continuation quality, caps, and confirmation",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox book `vwap_band_15m` was not changed. "
        "The caps, quality filters, and confirmation rules were frozen before this score. "
        "Train is a fresh account through 2021-12-31. The holdout is a fresh account from 2022-01-01 through 2026-10-06. "
        "2026-10-07 is the illustration, not part of the Dukascopy score.",
        "",
        payload["data_text"],
        "",
        "An end-of-day top-N would look ahead. It is not in the family. "
        "Thresholds are the training median, and both the tight and the wide stop were scored. "
        "The 5-minute follow-through walks 5-minute bars. Every other row walks 15-minute bars, the same path as the published extension book. "
        "False discovery is Benjamini-Hochberg on the holdout mean trade pnl, q at most 0.10. "
        "The original uncapped extension is the baseline and is not in that family.",
        "",
        payload["distribution_text"],
        "",
        "### Holdout, fresh $1,000",
        "",
        "Trades per day use every session in the window, including sessions with no trade. "
        "Win rate is next to the break-even win rate. Gate is the published 300-trade, 1.10, 0.40, -30% test on this account.",
        "",
        "| Book | Trades | Trades/day | >3 | >5 | Win | Break-even | PF | Sharpe | Max DD | $1,000 | Gate | q |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    qmap = payload["q"]
    for name in payload["order"]:
        hold = payload["books"][name]["1000"]["holdout"]
        lines.append(_row(name, hold, qmap.get(name)))
    lines += [
        "",
        "### Holdout, fresh $5,000",
        "",
        "One contract either way. When the debit already fits in $1,000, the extra cash sits idle and the dollar profit matches.",
        "",
        "| Book | Trades | Trades/day | >3 | >5 | Win | Break-even | PF | Sharpe | Max DD | $5,000 | Gate | q |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for name in payload["order"]:
        hold = payload["books"][name]["5000"]["holdout"]
        lines.append(_row(name, hold, qmap.get(name)))
    lines += [
        "",
        "### Training account, through 2021-12-31",
        "",
        "The published extension book died here: the $1,000 training account stopped at $1. "
        "Survives means the $1,000 account never hit that stop and finished above $1.",
        "",
        "| Book | Trades | PF | Sharpe | Max DD | $1,000 | $5,000 | Gate | Survives |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for name in payload["order"]:
        train = payload["books"][name]["1000"]["train"]
        train_five = payload["books"][name]["5000"]["train"]
        lines.append(_train_row(name, train, train_five))
    lines += ["", payload["verdict"], "", "### 2026-10-07 confirmation", ""]
    lines.extend(payload["today_lines"])
    lines += ["", payload["random_text"], ""]
    lines += [
        "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. "
        "The default book is still dual momentum. `vwap_band_15m` is unchanged.",
        "",
        "```",
        "python3 -m webull_bot.chart_reads.research_vwap_quality",
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


def _subset(priced: list, signals: list) -> list:
    by_id = {id(item.signal): item for item in priced}
    return [by_id[id(signal)] for signal in signals]


def main() -> None:
    rules = frozen_rules()
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(rules, indent=2) + "\n")
    written = json.loads(RULES_PATH.read_text())
    if written["family"] != list(FAMILY) or "2022-01-01" not in written["split"]:
        raise SystemExit("frozen rules were not the file that will be scored")

    minutes, info = load_minutes("SPY")
    if minutes is None:
        raise SystemExit(f"SPY minutes are not ready {info}")
    spy = to_fifteen_minute(minutes)
    five = to_rth_bars(minutes, "5min")
    hourly = to_rth_bars(minutes, "60min")
    del minutes
    qqq_minutes, qqq_info = load_minutes("QQQ")
    qqq = None
    if qqq_minutes is not None:
        qqq = to_fifteen_minute(qqq_minutes)
        del qqq_minutes
    iv = _prepare_iv()
    print(f"IV {len(iv)} SPY15 {len(spy)} SPY5 {len(five)} hour {len(hourly)}", flush=True)

    signals = [item for item in find_signals(spy, "SPY", 2.0) if item.mode == "extension"]
    features = build_features(spy, signals, hourly, qqq)
    cuts = freeze_cuts(features)
    train_features = [item for item in features if item.signal.signal_time.tz_convert(NY).date() <= TRAIN_END]
    known = 0.0
    if train_features:
        known = sum(1 for item in train_features if item.qqq_known) / len(train_features)
    qqq_first = None if qqq is None or qqq.empty else qqq.index[0].date()
    use_qqq = qqq_covers(qqq_first, known)
    family = list(scored_family(use_qqq))
    print(
        f"FROZEN cuts stretch {cuts['stretch']:.6f} relvol {cuts['relvol']:.6f} "
        f"stop_atr {cuts['stop_atr']:.6f} train_signals {cuts['train_signals']}",
        flush=True,
    )
    print(f"FROZEN qqq first {qqq_first} known {known:.4f} in_family {use_qqq}", flush=True)
    print("FROZEN family " + ",".join(family), flush=True)

    priced = price_signals(spy, [item.signal for item in features], iv)
    check = run_account(spy, priced, stake=1000.0, start=HOLDOUT_START, end=SAMPLE_END)
    slow = simulate(
        spy,
        _window_signals(signals, HOLDOUT_START, SAMPLE_END),
        target="r",
        kind="0dte",
        stake=1000.0,
        long_only=False,
        iv_points=iv,
        start=HOLDOUT_START,
        end=SAMPLE_END,
    )
    if len(check["trades"]) != len(slow["trades"]) or not _close(check["metrics"]["ending_equity"], slow["metrics"]["ending_equity"]):
        raise SystemExit(
            f"account path does not match simulate trades {len(check['trades'])} vs {len(slow['trades'])} "
            f"equity {check['metrics']['ending_equity']} vs {slow['metrics']['ending_equity']}"
        )
    print(f"PARITY holdout trades {len(check['trades'])} equity {check['metrics']['ending_equity']:.2f}", flush=True)

    train_sessions = sessions_between(spy, None, TRAIN_END)
    hold_sessions = sessions_between(spy, HOLDOUT_START, SAMPLE_END)
    signal_train = summarize_days(count_by_day(_window_signals(signals, None, TRAIN_END)), train_sessions)
    signal_hold = summarize_days(count_by_day(_window_signals(signals, HOLDOUT_START, SAMPLE_END)), hold_sessions)

    books: dict[str, dict] = {}
    order = ["baseline"] + family
    frames = {"15m": spy, "5m": five}
    priced_5 = None
    for name in order:
        path = path_of(name)
        if name == "baseline":
            chosen = [item.signal for item in features]
            clock = "15m"
            book_priced = priced
        else:
            chosen, clock = select_signals(name, features, cuts, spy, five, use_qqq=use_qqq)
            retimed = name in ("confirm_15m", "early_15m", "confirm15_cap3", "confirm_5m")
            if clock == "5m":
                priced_5 = price_signals(five, chosen, iv)
                book_priced = priced_5
            elif retimed:
                book_priced = price_signals(spy, chosen, iv)
            else:
                book_priced = _subset(priced, chosen)
        print(f"SCORE {name} signals {len(chosen)} walk {clock}", flush=True)
        stakes = {}
        for stake, sessions_train, sessions_hold in (
            (1000.0, train_sessions, hold_sessions),
            (5000.0, train_sessions, hold_sessions),
        ):
            stakes[str(int(stake))] = {
                "train": _score_book(frames[clock], book_priced, sessions_train, stake, None, TRAIN_END, path),
                "holdout": _score_book(frames[clock], book_priced, sessions_hold, stake, HOLDOUT_START, SAMPLE_END, path),
            }
        books[name] = stakes

    q_values = _fdr(books, family)
    candidates = []
    for name in family:
        train = books[name]["1000"]["train"]
        hold = books[name]["1000"]["holdout"]
        q_value = q_values.get(name)
        if train["passes"] and hold["passes"] and q_value is not None and q_value <= FDR_Q:
            candidates.append(name)
    print(f"CANDIDATES {candidates or 'none'}", flush=True)

    considered = _window_signals(signals, HOLDOUT_START, SAMPLE_END)
    hold_days = pd.Series([stamp.date() for stamp in spy.index], index=spy.index)
    hold_frame = spy.loc[(hold_days >= HOLDOUT_START) & (hold_days <= SAMPLE_END)]
    random_list = random_signals(hold_frame, "SPY", len(considered), RANDOM_SEED)
    random_book = simulate(
        spy,
        random_list,
        target="r",
        kind="0dte",
        stake=1000.0,
        long_only=False,
        iv_points=iv,
        start=HOLDOUT_START,
        end=SAMPLE_END,
    )
    random_five = simulate(
        spy,
        random_list,
        target="r",
        kind="0dte",
        stake=5000.0,
        long_only=False,
        iv_points=iv,
        start=HOLDOUT_START,
        end=SAMPLE_END,
    )

    today_rows = []
    yahoo15 = _yahoo(YAHOO_15)
    yahoo5 = _yahoo(YAHOO_5)
    if yahoo15 is not None and yahoo5 is not None:
        today_rows = confirmation_marks(yahoo15, yahoo5, TODAY)
        _plot_today(yahoo15, today_rows, CHART_PATH)
        artifact = Path("/opt/cursor/artifacts")
        if artifact.exists() and CHART_PATH.exists():
            (artifact / CHART_PATH.name).write_bytes(CHART_PATH.read_bytes())

    base_hold = books["baseline"]["1000"]["holdout"]
    base_train = books["baseline"]["1000"]["train"]
    distribution_text = (
        f"Raw extension signals, train: mean {signal_train['mean']:.2f} per session, "
        f"{_pct(signal_train['pct_gt_3'])} of sessions above 3, {_pct(signal_train['pct_gt_5'])} above 5, "
        f"max {signal_train['max']} ({signal_train['sessions']} sessions). "
        f"Holdout signals: mean {signal_hold['mean']:.2f}, "
        f"{_pct(signal_hold['pct_gt_3'])} above 3, {_pct(signal_hold['pct_gt_5'])} above 5, "
        f"max {signal_hold['max']} ({signal_hold['sessions']} sessions). "
        f"The $1,000 0 DTE account, after overlap, IV, and premium skips, train: mean "
        f"{base_train['distribution']['mean']:.2f} trades per session, "
        f"{_pct(base_train['distribution']['pct_gt_3'])} of sessions above 3, "
        f"{_pct(base_train['distribution']['pct_gt_5'])} above 5. "
        f"Holdout account: mean {base_hold['distribution']['mean']:.2f}, "
        f"{_pct(base_hold['distribution']['pct_gt_3'])} above 3, "
        f"{_pct(base_hold['distribution']['pct_gt_5'])} above 5."
    )
    qqq_text = (
        f"QQQ Dukascopy starts {qqq_first}, and {known:.1%} of training signals have a QQQ bar. "
        + ("QQQ confirmation is in the family." if use_qqq else "QQQ confirmation is reported and left out of the family.")
    )
    data_text = (
        f"SPY is Dukascopy 1-minute bids, {info.get('first')} through {info.get('last')}, "
        f"{info.get('sessions')} sessions, {info.get('missing')} days missing. {qqq_text} "
        f"Training medians, frozen before the account runs: stretch {cuts['stretch']:.4f} ATR, "
        f"relative volume {cuts['relvol']:.4f}, stop distance {cuts['stop_atr']:.4f} ATR "
        f"({cuts['train_signals']} training signals)."
    )
    if candidates:
        verdict = (
            "Candidates that clear the published gate on the fresh $1,000 account in both windows and survive q <= 0.10: "
            + ", ".join(candidates)
            + ". A passing book would be added beside `vwap_band_15m` under a new name. It would not replace that book."
        )
    else:
        verdict = (
            "No capped, filtered, or confirmation book clears the published gate on the fresh $1,000 account in both windows "
            "and survives the false-discovery correction. The sandbox forward test is unchanged. "
            f"The baseline $1,000 training account finished at {_money(base_train['ending_equity'])}"
            + (" and hit the bust stop." if not base_train.get("survives") else " and did not hit the bust stop.")
        )
    random_text = (
        f"Seed {RANDOM_SEED} random baseline, matched to {len(considered)} holdout extension signals: "
        f"{random_book['metrics']['trades']} trades, profit factor {_pf(random_book['metrics']['profit_factor'])}, "
        f"Sharpe {_num(random_book['metrics']['sharpe'])}, max drawdown {_pct(random_book['metrics']['max_drawdown'])}, "
        f"$1,000 ended {_money(random_book['metrics']['ending_equity'])}, "
        f"$5,000 ended {_money(random_five['metrics']['ending_equity'])}."
    )
    payload = {
        "data_text": data_text,
        "distribution_text": distribution_text,
        "verdict": verdict,
        "today_lines": _today_lines(_json_stamps(today_rows)),
        "random_text": random_text,
        "order": order,
        "books": books,
        "q": q_values,
    }
    _write_results(_markdown(payload))
    public_books = {}
    for name, stakes in books.items():
        public_books[name] = {
            stake: {window: _public_metrics(metrics) for window, metrics in windows.items()}
            for stake, windows in stakes.items()
        }
    public = {
        "family": family,
        "qqq_in_family": use_qqq,
        "qqq_known_fraction": known,
        "cuts": cuts,
        "candidates": candidates,
        "signal_distribution": {"train": signal_train, "holdout": signal_hold},
        "books": public_books,
        "q": q_values,
        "random": {
            "1000": {key: value for key, value in random_book["metrics"].items()},
            "5000": {key: value for key, value in random_five["metrics"].items()},
        },
        "today": _json_rows(today_rows),
        "verdict": verdict,
    }
    JSON_PATH.write_text(json.dumps(public, indent=2, default=_json_default) + "\n")
    print(verdict, flush=True)


def _fdr(books: dict, family: list[str]) -> dict[str, float | None]:
    """Benjamini-Hochberg on the stored holdout $1,000 t-stats."""
    tested: list[tuple[str, float]] = []
    for name in family:
        metrics = books[name]["1000"]["holdout"]
        p_value = one_sided_p(metrics.get("t"))
        if int(metrics.get("trades") or 0) >= FDR_MIN_TRADES and p_value is not None:
            tested.append((name, float(p_value)))
    adjusted = benjamini_hochberg([p_value for _name, p_value in tested])
    found: dict[str, float | None] = {name: None for name in family}
    for (name, _p_value), q_value in zip(tested, adjusted):
        found[name] = float(q_value)
    return found


def _close(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= 0.05


def _json_default(value):
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    raise TypeError(type(value))


def _json_stamps(rows: list[dict]) -> list[dict]:
    return rows


def _json_rows(rows: list[dict]) -> list[dict]:
    copied = []
    for row in rows:
        item = {}
        for key, value in row.items():
            item[key] = str(value) if isinstance(value, pd.Timestamp) else value
        copied.append(item)
    return copied
