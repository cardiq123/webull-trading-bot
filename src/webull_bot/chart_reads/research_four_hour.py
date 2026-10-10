"""Score the frozen 4-hour family once. Backtests only.

Writes the rules file before any metric. Does not place an order and does
not add a strategy to the live list.
"""

from __future__ import annotations

import json
import math
import shutil
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from webull_bot.chart_reads.atm_exit import deflated_sharpe
from webull_bot.chart_reads.four_hour import (
    COMPOUND_CAP,
    COMPOUND_FRACTION,
    DIRECTIONS,
    EXITS,
    GATE_TRADES,
    HOLDOUT_END,
    HOLDOUT_START,
    KINDS,
    MAG7,
    MAX_TRADES_PER_DAY,
    PULLBACKS,
    REFERENCE_DIRECTION,
    REFERENCE_EXIT,
    REFERENCE_PULLBACK,
    STAKE,
    SYMBOLS,
    TRAIN_END,
    TRAIN_START,
    Book,
    catalog,
    find_signals,
    frozen_rules,
    gate_label,
    n_trials,
    passes_gate,
    random_events,
    resolve,
    session_days,
    simulate_shares,
    window_rows,
)
from webull_bot.chart_reads.neckline import benjamini_hochberg, daily_returns, p_value
from webull_bot.chart_reads.odte_calibration import (
    calibrate,
    daily_equity,
    price_structures,
    rolling_stats,
    session_dates,
    to_fifteen,
    vwap_structures,
)
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.research_odte_compound import rolling_bundle, walk_daily
from webull_bot.chart_reads.vwap_band import metrics_from

ROOT = Path(__file__).resolve().parents[3]
RULES_PATH = ROOT / "reports" / "four_hour_rules.json"
JSON_PATH = ROOT / "reports" / "four_hour.json"
MD_PATH = ROOT / "reports" / "four_hour.md"
EQUITY_PATH = ROOT / "reports" / "four_hour_equity.png"
README_PATH = ROOT / "README.md"
RESULTS_PATH = ROOT / "RESULTS.md"
START_MARK = "<!-- FOUR_HOUR_START -->"
END_MARK = "<!-- FOUR_HOUR_END -->"
PUBLISHED = {
    "train": {"trades": 2873, "ending_equity": 19796.777540727562},
    "holdout": {"trades": 1128, "ending_equity": 18068.577257299898},
}
KIND_LABEL = {"shares": "shares", "1dte": "1 DTE", "0dte": "0 DTE"}
DIR_LABEL = {"ema": "4h EMA", "structure": "4h higher-high structure"}
PULL_LABEL = {"ema20": "15m 20 EMA", "vwap": "session VWAP"}
EXIT_LABEL = {"r1": "1R", "r2": "2R", "vwap2": "VWAP 2 SD"}


def _load_bars(symbol: str) -> tuple[pd.DataFrame, str]:
    candidates = [
        ROOT / f"data/cache/open_support/{symbol}_duka_5m.pkl",
        Path(f"/workspace/data/cache/open_support/{symbol}_duka_5m.pkl"),
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        raise FileNotFoundError(f"no 5-minute cache for {symbol}")
    frame = pd.read_pickle(path)
    frame = frame.sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    return frame, str(path)


def _load_series(name: str) -> pd.Series:
    candidates = [
        ROOT / f"data/cache/_{name}_1d.csv",
        Path(f"/workspace/data/cache/_{name}_1d.csv"),
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        return pd.Series(dtype=float)
    frame = pd.read_csv(path, parse_dates=["Date"])
    series = frame.set_index("Date")["close"].astype(float)
    series.index = pd.to_datetime(series.index)
    return series[~series.index.duplicated(keep="last")].sort_index()


def _load_mag(symbol: str) -> tuple[pd.DataFrame, str]:
    candidates = [
        Path(f"/workspace/data/cache/orb5/{symbol}_5m.csv"),
        ROOT / f"data/cache/orb5/{symbol}_5m.csv",
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        raise FileNotFoundError(symbol)
    frame = pd.read_csv(path)
    stamp = pd.to_datetime(frame["Datetime"], utc=True).dt.tz_convert("America/New_York")
    frame = frame.drop(columns=["Datetime"])
    frame.index = pd.DatetimeIndex(stamp)
    frame = frame.sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    keep = [column for column in ("open", "high", "low", "close", "volume") if column in frame.columns]
    return frame[keep].astype(float), str(path)


def _tape(symbol: str, frame: pd.DataFrame, path: str) -> str:
    start = pd.Timestamp(frame.index[0]).tz_convert("America/New_York")
    end = pd.Timestamp(frame.index[-1]).tz_convert("America/New_York")
    sessions = len(set(frame.index.date))
    return (
        f"{symbol} is 5-minute data from {start.date().isoformat()} through {end.date().isoformat()}, "
        f"{sessions} sessions, {len(frame)} bars, file `{path}`."
    )


def _window_sessions(sessions: list[date], start: date, end: date) -> list[date]:
    return [day for day in sessions if start <= day <= end]


def _option_score(cands: list[tuple], sessions: list[date], start: date, end: date, with_rolling: bool = True) -> dict:
    window_sessions = _window_sessions(sessions, start, end)
    window_cands = [row for row in cands if start <= row[0] <= end]
    equity, pnls = daily_equity(window_cands, window_sessions, 1, MAX_TRADES_PER_DAY, STAKE)
    scored = {
        "metrics": metrics_from(equity, pnls, STAKE),
        "pnls": pnls,
        "equity": equity,
        "rolling": {},
    }
    if with_rolling:
        scored["rolling"] = rolling_stats(window_cands, window_sessions, end, 1, MAX_TRADES_PER_DAY, STAKE)
    return scored


def _share_score(rows: list[dict], sessions: list[date], start: date, end: date, with_rolling: bool = True) -> dict:
    from webull_bot.chart_reads.odte_calibration import _add_months

    window_sessions = _window_sessions(sessions, start, end)
    window_rows_ = window_rows(rows, start, end)
    scored = simulate_shares(window_rows_, window_sessions, STAKE)
    if not with_rolling:
        scored["rolling"] = {}
        return scored
    eligible = [day for day in window_sessions if _add_months(day, 12) <= end]
    endings = []
    reach = 0
    ruins = 0
    for origin in eligible:
        horizon = _add_months(origin, 12)
        path_sessions = _window_sessions(window_sessions, origin, horizon)
        path = simulate_shares(window_rows(window_rows_, origin, horizon), path_sessions, STAKE)
        ending = float(path["metrics"]["ending_equity"])
        endings.append(ending)
        curve = path["equity"]
        if len(curve) and float(curve.min()) < 500.0:
            ruins += 1
        if len(curve) and float(curve.max()) >= 10_000.0:
            reach += 1
    count = len(eligible)
    scored["rolling"] = {
        "starts": count,
        "median_ending": None if not endings else float(np.median(endings)),
        "p_reach_12": None if not count else reach / count,
        "p_ruin": None if not count else ruins / count,
    }
    return scored


def _pack(scored: dict) -> dict:
    metrics = dict(scored["metrics"])
    rolling = scored.get("rolling") or {}
    metrics["median_ending"] = rolling.get("median_ending")
    metrics["p_reach_12"] = rolling.get("p_reach_12")
    metrics["p_ruin"] = rolling.get("p_ruin")
    metrics["starts"] = rolling.get("starts")
    return metrics


def _rank(row: dict) -> tuple:
    hold = row["holdout"]
    profit_factor = hold.get("profit_factor")
    factor = -1.0 if profit_factor is None else float(profit_factor)
    return (
        float(hold.get("sharpe") or 0.0),
        factor,
        int(hold.get("trades") or 0),
        row["id"],
    )


def _choose_compound(rows: list[dict]) -> tuple[dict, str]:
    options = [row for row in rows if row["kind"] in ("1dte", "0dte")]
    passed = [row for row in options if row["passes"]]
    if passed:
        return max(passed, key=_rank), "cleared the gate"
    enough = [row for row in options if int(row["holdout"].get("trades") or 0) >= GATE_TRADES]
    if enough:
        return max(enough, key=_rank), "highest holdout Sharpe among option cells with at least 300 trades"
    return max(options, key=lambda row: (int(row["holdout"].get("trades") or 0), _rank(row))), "most holdout trades"


def _money(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    number = float(value)
    if abs(number) >= 100:
        return f"${number:,.0f}"
    return f"${number:,.2f}"


def _pct(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.1%}"


def _num(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.2f}"


def _plain(row: dict) -> str:
    return (
        f"{row['symbol']} {DIR_LABEL[row['direction_mode']]}, "
        f"{PULL_LABEL[row['pullback']]} pullback, {EXIT_LABEL[row['exit']]}, {KIND_LABEL[row['kind']]}"
    )


def _line(row: dict, window: str) -> str:
    metrics = row[window]
    return (
        f"{int(metrics.get('trades') or 0)} trades, win {_pct(metrics.get('win_rate'))}, "
        f"profit factor {_num(metrics.get('profit_factor'))}, Sharpe {_num(metrics.get('sharpe'))}, "
        f"max drawdown {_pct(metrics.get('max_drawdown'))}, ending {_money(metrics.get('ending_equity'))} "
        f"from {_money(STAKE)}, 12-month median {_money(metrics.get('median_ending'))}, "
        f"P(reach $10k) {_pct(metrics.get('p_reach_12'))}, P(ruin) {_pct(metrics.get('p_ruin'))}"
    )


def _aggressive(frame: pd.DataFrame, iv: dict) -> dict:
    fifteen = to_fifteen(frame)
    structures = vwap_structures(fifteen, "QQQ")
    cands = price_structures(structures, iv, 1.0, "0.01", dte=1)
    sessions = session_dates(fifteen)
    out = {}
    for name, start, end in (
        ("train", TRAIN_START, TRAIN_END),
        ("holdout", HOLDOUT_START, HOLDOUT_END),
    ):
        scored = _option_score(cands, sessions, start, end)
        packed = _pack(scored)
        packed["equity"] = scored["equity"]
        out[name] = packed
        print(
            f"AGGRESSIVE {name} trades {packed.get('trades')} ending {packed.get('ending_equity')}",
            flush=True,
        )
    return out


def _compound_score(row: dict, sessions: list[date]) -> dict:
    out = {"why": row.get("compound_why")}
    for name, start, end, key in (
        ("train", TRAIN_START, TRAIN_END, "cands_train"),
        ("holdout", HOLDOUT_START, HOLDOUT_END, "cands_holdout"),
    ):
        cands = row[key]
        window_sessions = _window_sessions(sessions, start, end)
        equity, pnls, info = walk_daily(
            cands, window_sessions, "compound", COMPOUND_FRACTION, cap=COMPOUND_CAP, slip=True
        )
        metrics = metrics_from(equity, pnls, STAKE)
        bundle = rolling_bundle(
            cands, window_sessions, end, "compound", COMPOUND_FRACTION, cap=COMPOUND_CAP, slip=True
        )
        metrics["median_ending"] = bundle.get("median_ending")
        metrics["p_reach_12"] = bundle.get("p_reach_12")
        metrics["p_ruin"] = bundle.get("p_ruin")
        metrics["starts"] = bundle.get("starts_12")
        metrics["equity"] = equity
        metrics["rescues"] = int(info.get("rescues") or 0)
        metrics["dear_skips"] = int(info.get("dear_skips") or 0)
        simple = (
            int(metrics.get("trades") or 0) >= GATE_TRADES
            and (metrics.get("profit_factor") is None or float(metrics["profit_factor"]) >= 1.10)
            and float(metrics.get("sharpe") or 0.0) >= 0.40
            and float(metrics.get("max_drawdown") or 0.0) >= -0.30
        )
        metrics["gate"] = "yes" if simple else "no"
        out[name] = metrics
    return out


def _chart(path: Path, series: list[tuple[str, pd.Series]]) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    colors = ("#1f4e79", "#c47b2b", "#2f6b4f")
    for (label, equity), color in zip(series, colors):
        if equity is None or len(equity) == 0:
            continue
        ax.plot(equity.index, equity.to_numpy(dtype=float), label=label, color=color, linewidth=1.6)
    ax.axhline(STAKE, color="#888888", linewidth=0.8)
    ax.set_title("Holdout equity from a fresh $2,500")
    ax.set_ylabel("Account ($)")
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    artifact = Path("/opt/cursor/artifacts")
    if artifact.is_dir():
        shutil.copyfile(path, artifact / path.name)


def _table(rows: list[dict]) -> list[str]:
    header = (
        "| Cell | Train trades | Train PF | Train ending | Holdout trades | Holdout win | "
        "Holdout PF | Holdout Sharpe | Holdout DD | Holdout ending | Holdout 12m median | "
        "P($10k) | P(ruin) | Random holdout ending | q | DSR | Gate |"
    )
    sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
    lines = [header, sep]
    for row in rows:
        train = row["train"]
        hold = row["holdout"]
        lines.append(
            "| "
            + " | ".join(
                [
                    row["id"],
                    str(int(train.get("trades") or 0)),
                    _num(train.get("profit_factor")),
                    _money(train.get("ending_equity")),
                    str(int(hold.get("trades") or 0)),
                    _pct(hold.get("win_rate")),
                    _num(hold.get("profit_factor")),
                    _num(hold.get("sharpe")),
                    _pct(hold.get("max_drawdown")),
                    _money(hold.get("ending_equity")),
                    _money(hold.get("median_ending")),
                    _pct(hold.get("p_reach_12")),
                    _pct(hold.get("p_ruin")),
                    _money(row["random_holdout"].get("ending_equity")),
                    f"{float(row['q']):.3f}",
                    f"{float(row['dsr']):.3f}",
                    row["gate"],
                ]
            )
            + " |"
        )
    return lines


def _one_line_misses(rows: list[dict]) -> list[dict]:
    found = []
    for row in rows:
        label = str(row.get("gate") or "")
        if not label.startswith("no (") or not label.endswith(")"):
            continue
        reasons = [part.strip() for part in label[4:-1].split(",") if part.strip()]
        if len(reasons) == 1 and int(row["holdout"].get("trades") or 0) >= GATE_TRADES:
            found.append(row)
    return sorted(found, key=_rank, reverse=True)


def _prose(rows: list[dict], tapes: list[str], aggressive: dict, compound: dict, mag: list[dict], scale: float) -> str:
    passed = [row["id"] for row in rows if row["passes"]]
    busiest = max(int(row["holdout"].get("trades") or 0) for row in rows)
    compound_row = next(row for row in rows if row["id"] == compound["id"])
    misses = _one_line_misses(rows)
    if passed:
        lead = (
            f"Cleared the full gate: {', '.join(passed)}. "
            "None of those cells was added to the live book."
        )
    else:
        lead = "No cell cleared the full gate. Nothing was added to the live book."
    rare = ""
    if busiest < GATE_TRADES:
        rare = (
            f" The busiest holdout cell has {busiest} trades, so this setup is too rare "
            f"to reach the {GATE_TRADES}-trade line on 2024-01-01 through 2026-10-06."
        )
    miss_bits = []
    for row in misses:
        reason = str(row["gate"])[4:-1]
        miss_bits.append(f"{_plain(row)} fails only on {reason}. Holdout: {_line(row, 'holdout')}. Train: {_line(row, 'train')}.")
    miss_text = " ".join(miss_bits) if miss_bits else "No holdout book with at least 300 trades failed on only one line."
    agg_hold = aggressive["holdout"]
    agg_train = aggressive["train"]
    lines = [
        "# 4hr",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. "
        "The sandbox forward books were not changed. The rules in `reports/four_hour_rules.json` "
        "were written before any metric.",
        "",
        lead + rare,
        "",
        miss_text,
        "",
        "The 4-hour bars are the cash-session blocks, 9:30-13:30 and 13:30-16:00, built from "
        "completed 5-minute bars. The afternoon block is two and a half hours and counts as one bar. "
        "A block is used only after its first and last 5-minute bars have both printed. "
        "The 1-hour bars are the six 60-minute blocks from 9:30. The 15:30-16:00 stub is left out of that average. "
        "A long needs the last completed 4-hour close above its 20 EMA with that EMA rising, "
        "or, in the other cell, a higher high, a higher low, and a close above the prior 4-hour high. "
        "The 1-hour bar has to agree: close above its 20 EMA and the 9 EMA above the 20 EMA. "
        "Shorts mirror both tests. The pullback is the next completed 15-minute bar that touches "
        "the 15-minute 20 EMA or session VWAP, within 0.1 of that bar's ATR(14). "
        "A 15-minute close through the 1-hour 20 EMA cancels it. "
        "The entry is the first later 5-minute bar that closes back with the trend through the 5-minute 9 EMA, "
        "a bullish close for longs and a bearish close for shorts. The fill is the next 5-minute open. "
        "The stop is one cent under the pullback low or one cent over the pullback high. "
        "Exits, scored as separate cells, are 1R, 2R, and the outer session-VWAP 2 SD band. "
        "Every position is flat at the 15:45 open. One position. At most 5 new trades a day.",
        "",
        f"The chart compares three holdout accounts. The 4hr line is {_plain(compound_row)} "
        f"({compound_row['id']}). Selection: {compound['why']}. "
        f"Holdout: {_line(compound_row, 'holdout')}. Train: {_line(compound_row, 'train')}. "
        f"Gate: {compound_row['gate']}.",
        "",
        f"QQQ Aggressive, 1 contract, 1 DTE, the same unscaled prior close and 1 cent market, "
        f"same-day 15:45 flatten, fresh $2,500, at most 5 fills a day. "
        f"Holdout: {_line({'holdout': agg_hold}, 'holdout')}. "
        f"Train: {_line({'train': agg_train}, 'train')}.",
        "",
        f"The 5% compound book uses the same signals as {compound_row['id']}. "
        f"Selection rule: {compound['why']}. It is outside the family of {n_trials()} cells. "
        f"The lot is floor(0.05 times equity divided by ask times 100), capped at 30. "
        f"A zero lot still buys one contract when that contract costs at most 10% of equity. "
        f"Size slippage adds one cent per share for every ten contracts past the first ten. "
        f"Holdout: {_line({'holdout': compound['holdout']}, 'holdout')}. "
        f"The holdout profit-factor, Sharpe, drawdown, and trade-count gate is {compound['holdout']['gate']}. "
        f"Train: {_line({'train': compound['train']}, 'train')}. "
        f"That train gate is {compound['train']['gate']}.",
        "",
        f"Each primary cell starts a fresh $2,500. Train is {TRAIN_START.isoformat()} through {TRAIN_END.isoformat()}. "
        f"Holdout is {HOLDOUT_START.isoformat()} through {HOLDOUT_END.isoformat()}. "
        "Shares risk 1% of start-of-day equity to the stop, in whole shares. "
        "1 DTE is one at-the-money contract at the prior VIX1D close, or the prior VIX close when that print is missing, "
        "with a 1 cent bid-ask and the next session's expiry. The position is still sold the same day at 15:45. "
        f"0 DTE uses that same prior close times {scale:.4f}, the 1.67 volatility scale, and a 1 cent market. "
        f"The false-discovery family is the {n_trials()} primary cells. The Mag 7 share books and the compound book stay out of it. "
        "The random baseline draws the same number of bars with seed 17 and keeps each signal's direction. "
        "Its stop is one cent beyond that bar. "
        "The gate is holdout trades at least 300, profit factor at least 1.10, Sharpe at least 0.40, "
        "max drawdown no worse than -30%, ending above $2,500, training Sharpe above that cell's random training Sharpe, "
        "a Benjamini-Hochberg q at or under 0.10 on the training trade P&L, and a deflated Sharpe at least 0.95. "
        "Reach is a fresh $2,500 growing to $10,000 inside the next 12 months. Ruin is equity under $500.",
        "",
        "## Tapes",
        "",
        *tapes,
        "",
        "## QQQ Aggressive 1 DTE, one contract",
        "",
        "This is the published comparison book, recomputed on the same caches for the chart.",
        "",
        "| Window | Trades | Win | PF | Sharpe | Max DD | Ending | 12m median | P($10k) | P(ruin) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("train", "holdout"):
        metrics = aggressive[name]
        lines.append(
            f"| {name} | {int(metrics.get('trades') or 0)} | {_pct(metrics.get('win_rate'))} | "
            f"{_num(metrics.get('profit_factor'))} | {_num(metrics.get('sharpe'))} | "
            f"{_pct(metrics.get('max_drawdown'))} | {_money(metrics.get('ending_equity'))} | "
            f"{_money(metrics.get('median_ending'))} | {_pct(metrics.get('p_reach_12'))} | {_pct(metrics.get('p_ruin'))} |"
        )
    lines.extend(["", "## Full family", "", *_table(rows), "", "## Mag 7 shares, reference", ""])
    lines.append(
        "Same EMA direction, 15-minute 20 EMA pullback, 1R exit, and 1% share risk. "
        "The Yahoo 5-minute cache is only the recent window below, so these books cannot reach 300 trades. "
        "They are not in the q-value family."
    )
    lines.append("")
    lines.append("| Symbol | First | Last | Trades | Win | PF | Sharpe | Max DD | Ending |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|")
    for item in mag:
        metrics = item["metrics"]
        lines.append(
            f"| {item['symbol']} | {item['first']} | {item['last']} | {int(metrics.get('trades') or 0)} | "
            f"{_pct(metrics.get('win_rate'))} | {_num(metrics.get('profit_factor'))} | "
            f"{_num(metrics.get('sharpe'))} | {_pct(metrics.get('max_drawdown'))} | "
            f"{_money(metrics.get('ending_equity'))} |"
        )
    lines.extend(
        [
            "",
            f"Chart: `{EQUITY_PATH.relative_to(ROOT).as_posix()}`. Machine-readable summary: `{JSON_PATH.relative_to(ROOT).as_posix()}`.",
            "",
            "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. "
            "The default book is still dual momentum.",
            "",
            "```",
            "PYTHONPATH=src python3 -m webull_bot.chart_reads.research_four_hour",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _upsert(path: Path, body: str) -> None:
    text = path.read_text() if path.exists() else ""
    block = f"{START_MARK}\n{body.rstrip()}\n{END_MARK}\n"
    if START_MARK in text and END_MARK in text:
        pre, rest = text.split(START_MARK, 1)
        _old, post = rest.split(END_MARK, 1)
        path.write_text(pre + block + post.lstrip("\n"))
        return
    anchor = "Full tables, including the stock diagnostics, are in [RESULTS.md](RESULTS.md)."
    if path.name == "README.md" and anchor in text:
        path.write_text(text.replace(anchor, block + "\n" + anchor, 1))
        return
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n" + block)


def _blurb(rows: list[dict], compound: dict) -> str:
    passed = [row["id"] for row in rows if row["passes"]]
    chart_row = next(row for row in rows if row["id"] == compound["id"])
    verdict = "No cell cleared the gate." if not passed else "Cleared the gate and was not promoted: " + ", ".join(passed) + "."
    return (
        "**4hr: does not join the book.** Session-aligned 4-hour trend, 1-hour agreement, "
        "15-minute pullback, and 5-minute entry on SPY and QQQ. Train 2017-2023, holdout 2024-01-01 "
        f"through 2026-10-06, fresh $2,500, family of {n_trials()} cells. "
        f"{_plain(chart_row)} holdout ended {_money(chart_row['holdout'].get('ending_equity'))} "
        f"on {int(chart_row['holdout'].get('trades') or 0)} trades, profit factor {_num(chart_row['holdout'].get('profit_factor'))}, "
        f"and the gate is {chart_row['gate']}. "
        f"The 5% compound path on that cell ended {_money(compound['holdout'].get('ending_equity'))}. "
        f"QQQ Aggressive 1 DTE, one contract, is the comparison book. "
        f"{verdict} The chart is `reports/four_hour_equity.png`. Nothing was sent to a broker."
    )


def _jsonable(value):
    if isinstance(value, dict):
        skip = {"equity", "equity_holdout", "pnls", "pnls_train", "cands_train", "cands_holdout"}
        return {key: _jsonable(item) for key, item in value.items() if key not in skip}
    if isinstance(value, pd.Series):
        return None
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _score_kind(kind: str, pack: dict, start: date, end: date, with_rolling: bool = True) -> dict:
    if kind == "shares":
        return _share_score(pack["structs"], pack["sessions"], start, end, with_rolling)
    key = "1dte" if kind == "1dte" else "0dte"
    return _option_score(pack[key], pack["sessions"], start, end, with_rolling)


def _prepare_cache(books: dict[str, Book], iv: dict, scale: float) -> dict:
    cache = {}
    for symbol in SYMBOLS:
        book = books[symbol]
        sessions = session_days(book)
        for direction_mode in DIRECTIONS:
            for pullback in PULLBACKS:
                events = find_signals(book, direction_mode, pullback)
                print(f"EVENTS {symbol} {direction_mode} {pullback} {len(events)}", flush=True)
                for exit_name in EXITS:
                    structs = resolve(book, events, exit_name)
                    cache[(symbol, direction_mode, pullback, exit_name)] = {
                        "events": events,
                        "structs": structs,
                        "sessions": sessions,
                        "1dte": price_structures(structs, iv, 1.0, "0.01", dte=1),
                        "0dte": price_structures(structs, iv, scale, "0.01", dte=0),
                    }
                    print(f"  {exit_name} structures {len(structs)}", flush=True)
    return cache


def _random_pack(book: Book, events: list, exit_name: str, iv: dict, scale: float, start: date, end: date, kind: str) -> dict:
    sampled = random_events(book, events, start, end)
    structs = resolve(book, sampled, exit_name)
    sessions = _window_sessions(session_days(book), start, end)
    if kind == "shares":
        return _share_score(structs, sessions, start, end, with_rolling=False)
    priced = price_structures(structs, iv, 1.0 if kind == "1dte" else scale, "0.01", dte=1 if kind == "1dte" else 0)
    return _option_score(priced, sessions, start, end, with_rolling=False)


def _mag_rows() -> list[dict]:
    found = []
    for symbol in MAG7:
        try:
            frame, path = _load_mag(symbol)
        except FileNotFoundError:
            found.append(
                {
                    "symbol": symbol,
                    "first": "missing",
                    "last": "missing",
                    "path": "",
                    "metrics": {"trades": 0, "win_rate": 0.0, "profit_factor": None, "sharpe": 0.0, "max_drawdown": 0.0, "ending_equity": STAKE},
                }
            )
            continue
        book = Book(frame, symbol)
        events = find_signals(book, REFERENCE_DIRECTION, REFERENCE_PULLBACK)
        structs = resolve(book, events, REFERENCE_EXIT)
        sessions = session_days(book)
        scored = simulate_shares(structs, sessions, STAKE)
        first = pd.Timestamp(frame.index[0]).tz_convert("America/New_York").date().isoformat()
        last = pd.Timestamp(frame.index[-1]).tz_convert("America/New_York").date().isoformat()
        print(f"MAG {symbol} {first} {last} trades {scored['metrics'].get('trades')} file {path}", flush=True)
        found.append(
            {
                "symbol": symbol,
                "first": first,
                "last": last,
                "path": path,
                "metrics": scored["metrics"],
            }
        )
    return found


def main() -> None:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    rules = frozen_rules()
    RULES_PATH.write_text(json.dumps(rules, indent=2) + "\n")
    print(f"RULES {RULES_PATH} cells {rules['n_trials']}", flush=True)
    scale = float(calibrate()["multiplier_0dte"])
    iv = prior_iv(_load_series("VIX1D"), _load_series("VIX"))
    books = {}
    tapes = []
    frames = {}
    for symbol in SYMBOLS:
        frame, path = _load_bars(symbol)
        frames[symbol] = frame
        tapes.append(_tape(symbol, frame, path))
        print(f"PREPARE {symbol} bars {len(frame)}", flush=True)
        books[symbol] = Book(frame, symbol)
        print(
            f"  sessions {books[symbol].sessions} 4h {books[symbol].h4_bars} 1h {books[symbol].h1_bars}",
            flush=True,
        )
    cache = _prepare_cache(books, iv, scale)
    rows = []
    for cell in catalog():
        pack = cache[(cell.symbol, cell.direction_mode, cell.pullback, cell.exit)]
        print(f"SCORE {cell.id}", flush=True)
        train = _score_kind(cell.kind, pack, TRAIN_START, TRAIN_END)
        hold = _score_kind(cell.kind, pack, HOLDOUT_START, HOLDOUT_END)
        random_train = _random_pack(books[cell.symbol], pack["events"], cell.exit, iv, scale, TRAIN_START, TRAIN_END, cell.kind)
        random_hold = _random_pack(books[cell.symbol], pack["events"], cell.exit, iv, scale, HOLDOUT_START, HOLDOUT_END, cell.kind)
        dsr_pack = deflated_sharpe(daily_returns(train["equity"], STAKE), n_trials())
        dsr = dsr_pack.get("dsr")
        row = {
            "id": cell.id,
            "symbol": cell.symbol,
            "direction_mode": cell.direction_mode,
            "pullback": cell.pullback,
            "exit": cell.exit,
            "kind": cell.kind,
            "train": _pack(train),
            "holdout": _pack(hold),
            "random_train": _pack(random_train),
            "random_holdout": _pack(random_hold),
            "p": p_value(train["pnls"]),
            "dsr": 0.0 if dsr is None else float(dsr),
            "equity_holdout": hold["equity"],
            "pnls_train": train["pnls"],
        }
        if cell.kind == "1dte":
            row["cands_train"] = [item for item in pack["1dte"] if TRAIN_START <= item[0] <= TRAIN_END]
            row["cands_holdout"] = [item for item in pack["1dte"] if HOLDOUT_START <= item[0] <= HOLDOUT_END]
        elif cell.kind == "0dte":
            row["cands_train"] = [item for item in pack["0dte"] if TRAIN_START <= item[0] <= TRAIN_END]
            row["cands_holdout"] = [item for item in pack["0dte"] if HOLDOUT_START <= item[0] <= HOLDOUT_END]
        rows.append(row)
        print(
            f"  hold {row['holdout'].get('trades')} end {row['holdout'].get('ending_equity')}",
            flush=True,
        )
    q_values = [float(item) for item in benjamini_hochberg([row["p"] for row in rows])]
    for row, q_value in zip(rows, q_values):
        row["q"] = q_value
        row["passes"] = passes_gate(row["holdout"], row["train"], row["random_train"], q_value, row["dsr"])
        row["gate"] = gate_label(row["holdout"], row["train"], row["random_train"], q_value, row["dsr"])
    compound_row, why = _choose_compound(rows)
    compound_row["compound_why"] = why
    compound = _compound_score(compound_row, cache[(compound_row["symbol"], compound_row["direction_mode"], compound_row["pullback"], compound_row["exit"])]["sessions"])
    compound["id"] = compound_row["id"]
    compound["why"] = why
    print(f"COMPOUND {compound['id']} {why} hold {compound['holdout'].get('ending_equity')}", flush=True)
    print("AGGRESSIVE", flush=True)
    aggressive = _aggressive(frames["QQQ"], iv)
    for name in ("train", "holdout"):
        gap_trades = abs(int(aggressive[name]["trades"]) - PUBLISHED[name]["trades"])
        gap_money = abs(float(aggressive[name]["ending_equity"]) - PUBLISHED[name]["ending_equity"])
        print(f"  published gap {name} trades {gap_trades} money {gap_money:.2f}", flush=True)
        aggressive[name]["published_trade_gap"] = gap_trades
        aggressive[name]["published_money_gap"] = gap_money
    mag = _mag_rows()
    series = [
        (f"4hr {_plain(compound_row)}", compound_row["equity_holdout"]),
        ("QQQ Aggressive 1 DTE, 1 contract", aggressive["holdout"]["equity"]),
        (f"5% compound {compound_row['id']}", compound["holdout"]["equity"]),
    ]
    _chart(EQUITY_PATH, series)
    prose = _prose(rows, tapes, aggressive, compound, mag, scale)
    MD_PATH.write_text(prose)
    payload = {
        "rules": rules,
        "scale_0dte": scale,
        "passed": [row["id"] for row in rows if row["passes"]],
        "chart_cell": compound_row["id"],
        "compound": _jsonable(compound),
        "aggressive": _jsonable(aggressive),
        "mag7": _jsonable(mag),
        "tapes": tapes,
        "cells": [_jsonable(row) for row in rows],
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    blurb = _blurb(rows, compound)
    _upsert(README_PATH, blurb)
    _upsert(RESULTS_PATH, blurb)
    print(f"WROTE {MD_PATH} passed {payload['passed']}", flush=True)


if __name__ == "__main__":
    main()
