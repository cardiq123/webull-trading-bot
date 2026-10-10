"""Score the pre-registered 4hr refinements. Backtests only.

Writes the rules file before any metric. Walk-forward selection on 2020-2023
finishes before any holdout statistic is computed. Does not place an order
and does not add a strategy to the live list.
"""

from __future__ import annotations

import json
import math
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from webull_bot.chart_reads.atm_exit import deflated_sharpe
from webull_bot.chart_reads.four_hour import (
    HOLDOUT_END,
    HOLDOUT_START,
    STAKE,
    TRAIN_END,
    TRAIN_START,
    Book,
    find_signals,
    gate_label,
    passes_gate,
    random_events,
    resolve,
    session_days,
)
from webull_bot.chart_reads.four_hour_refine import (
    BASE_CELL,
    PRIOR_TRIALS,
    REFINEMENT_IDS,
    WF_YEARS,
    apply_filters,
    dead_trade_days,
    frozen_refine_rules,
    selected_rule,
    train_winners,
    variant_spec,
)
from webull_bot.chart_reads.neckline import benjamini_hochberg, daily_returns, p_value
from webull_bot.chart_reads.odte_calibration import (
    contracts_for,
    daily_equity,
    price_structures,
    session_dates,
    to_fifteen,
    vwap_structures,
)
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.research_four_hour import (
    PUBLISHED,
    _load_bars,
    _load_series,
)
from webull_bot.chart_reads.vwap_band import metrics_from

ROOT = Path(__file__).resolve().parents[3]
RULES_PATH = ROOT / "reports" / "four_hour_refine_rules.json"
JSON_PATH = ROOT / "reports" / "four_hour_refine.json"
MD_PATH = ROOT / "reports" / "four_hour_refine.md"
EQUITY_PATH = ROOT / "reports" / "four_hour_refine_equity.png"
FAMILY_PATH = ROOT / "reports" / "four_hour.json"
README_PATH = ROOT / "README.md"
RESULTS_PATH = ROOT / "RESULTS.md"
START_MARK = "<!-- FOUR_HOUR_REFINE_START -->"
END_MARK = "<!-- FOUR_HOUR_REFINE_END -->"
PUBLISHED_BASE = {
    "train_trades": 3148,
    "train_ending": 15188.834701549413,
    "holdout_trades": 1241,
    "holdout_ending": 19204.08890378868,
}
LABELS = {
    "base": "Base",
    "chop": "Chop filter",
    "time": "Time filter",
    "volume": "Volume filter",
    "vwap_hold": "Hold VWAP",
    "slope": "4h slope 0.15%",
    "dead_tape": "Dead tape",
    "be15": "Breakeven at 0.5R, target 1.5R",
    "cap2": "Max 2 a day",
    "combo": "Train-winner combination",
}


def _price_rows(rows: list[dict], iv: dict) -> list[dict]:
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[(row["day"], row["fill_i"], row["exit_i"])].append(row)
    priced = price_structures(rows, iv, 1.0, "0.01", dte=1)
    out = []
    for day, due, fill_i, exit_i, debit, credit, ask in priced:
        src = buckets[(day, fill_i, exit_i)].pop(0)
        packed = dict(src)
        packed["due"] = due
        packed["debit"] = float(debit)
        packed["credit"] = float(credit)
        packed["ask"] = float(ask)
        out.append(packed)
    return out


def _walk(rows: list[dict], sessions: list[date], cap: int, stake: float = STAKE):
    by_day: dict[date, list[dict]] = {}
    for row in rows:
        by_day.setdefault(row["day"], []).append(row)
    for day_rows in by_day.values():
        day_rows.sort(key=lambda item: int(item["fill_i"]))
    settled = float(stake)
    pending: list[tuple[date, float]] = []
    pnls: list[float] = []
    taken: list[dict] = []
    values = []
    for day in sessions:
        if pending:
            still = []
            for when, amount in pending:
                if when <= day:
                    settled += amount
                else:
                    still.append((when, amount))
            pending = still
        taken_n = 0
        busy = -1
        for row in by_day.get(day, []):
            if taken_n >= cap:
                continue
            if int(row["fill_i"]) <= busy:
                continue
            debit = float(row["debit"])
            credit = float(row["credit"])
            if contracts_for(1, settled, debit) < 1:
                continue
            settled -= debit
            pending.append((row["due"], credit))
            pnls.append(credit - debit)
            taken.append(row)
            taken_n += 1
            busy = int(row["exit_i"])
        values.append(settled + sum(amount for _when, amount in pending))
    if not sessions:
        index = pd.DatetimeIndex([pd.Timestamp(TRAIN_START)])
        equity = pd.Series([stake], index=index, dtype=float)
        return equity, [], []
    index = pd.DatetimeIndex([pd.Timestamp(day) for day in sessions])
    return pd.Series(values, index=index, dtype=float), pnls, taken


def _window(rows: list[dict], sessions: list[date], start: date, end: date, cap: int) -> dict:
    window_sessions = [day for day in sessions if start <= day <= end]
    window_rows = [row for row in rows if start <= row["day"] <= end]
    equity, pnls, taken = _walk(window_rows, window_sessions, cap)
    return {
        "metrics": metrics_from(equity, pnls, STAKE),
        "pnls": pnls,
        "equity": equity,
        "taken": taken,
    }


def _walk_forward(rows: list[dict], sessions: list[date], cap: int) -> dict:
    yearly = []
    for year in WF_YEARS:
        scored = _window(rows, sessions, date(year, 1, 1), date(year, 12, 31), cap)
        yearly.append(
            {
                "year": year,
                "sharpe": float(scored["metrics"].get("sharpe") or 0.0),
                "trades": int(scored["metrics"].get("trades") or 0),
                "ending_equity": float(scored["metrics"].get("ending_equity") or STAKE),
            }
        )
    stitched = _window(rows, sessions, date(WF_YEARS[0], 1, 1), date(WF_YEARS[-1], 12, 31), cap)
    return {
        "yearly": yearly,
        "mean_yearly_sharpe": float(np.mean([item["sharpe"] for item in yearly])),
        "wf_trades": int(sum(item["trades"] for item in yearly)),
        "stitched": stitched,
    }


def _build(book: Book, iv: dict, base_events, hold_events, names: list[str], dead_days: set[date]):
    spec = variant_spec(names)
    events = hold_events if spec["hold_vwap"] else base_events
    events = apply_filters(book, events, spec["event_filters"], dead_days)
    resolved = resolve(book, events, spec["exit"])
    priced = _price_rows(resolved, iv)
    return {
        "events": events,
        "rows": priced,
        "cap": spec["cap"],
        "exit": spec["exit"],
        "signals": len(events),
        "quoted": len(priced),
    }


def _tuples(rows: list[dict]) -> list[tuple]:
    return [
        (row["day"], row["due"], row["fill_i"], row["exit_i"], row["debit"], row["credit"], row["ask"])
        for row in rows
    ]


def _check_base(rows: list[dict], sessions: list[date]) -> None:
    """The unfiltered 1R path has to match the published cell and daily_equity."""
    window_sessions = [day for day in sessions if TRAIN_START <= day <= TRAIN_END]
    window_rows = [row for row in rows if TRAIN_START <= row["day"] <= TRAIN_END]
    equity, pnls, _taken = _walk(window_rows, window_sessions, 5)
    ref_equity, ref_pnls = daily_equity(_tuples(window_rows), window_sessions, 1, 5, STAKE)
    if len(pnls) != len(ref_pnls) or abs(float(equity.iloc[-1]) - float(ref_equity.iloc[-1])) > 0.01:
        raise RuntimeError("cash walk drifted from daily_equity on the base train book")
    trades = len(pnls)
    ending = float(equity.iloc[-1])
    if trades != PUBLISHED_BASE["train_trades"] or abs(ending - PUBLISHED_BASE["train_ending"]) > 0.02:
        raise RuntimeError(f"base train drifted from the published cell: trades {trades} ending {ending}")


def _dsr(equity: pd.Series, trials: int) -> float:
    packed = deflated_sharpe(daily_returns(equity, STAKE), trials)
    value = packed.get("dsr")
    return 0.0 if value is None else float(value)


def _bucket(stamp) -> tuple:
    ts = pd.Timestamp(stamp)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("America/New_York")
    return (ts.date(), int(ts.hour), int(ts.minute) // 15 * 15)


def _pearson(left: np.ndarray, right: np.ndarray) -> float | None:
    if len(left) < 3 or len(right) != len(left):
        return None
    if float(np.std(left)) == 0.0 or float(np.std(right)) == 0.0:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def _pnl_vector(taken: list[dict], sessions: list[date]) -> tuple[np.ndarray, np.ndarray]:
    totals = {day: 0.0 for day in sessions}
    counts = {day: 0 for day in sessions}
    for row in taken:
        totals[row["day"]] = totals.get(row["day"], 0.0) + float(row["credit"]) - float(row["debit"])
        counts[row["day"]] = counts.get(row["day"], 0) + 1
    return (
        np.array([totals[day] for day in sessions], dtype=float),
        np.array([counts[day] for day in sessions], dtype=int),
    )


def _share(part: int, whole: int) -> float | None:
    if whole <= 0:
        return None
    return part / whole


def _overlap(four_signals: list[dict], four_taken: list[dict], agg_signals: list[dict], agg_taken: list[dict], sessions: list[date]) -> dict:
    four_days = {row["day"] for row in four_signals}
    agg_days = {row["day"] for row in agg_signals}
    common_days = four_days & agg_days
    four_trade_days = {row["day"] for row in four_taken}
    agg_trade_days = {row["day"] for row in agg_taken}
    common_trade_days = four_trade_days & agg_trade_days
    agg_buckets = {_bucket(row["fill_time"]) for row in agg_taken}
    agg_signal_buckets = {_bucket(row["fill_time"]) for row in agg_signals}
    four_bucket_hits = sum(1 for row in four_taken if _bucket(row["fill_time"]) in agg_buckets)
    four_signal_bucket_hits = sum(1 for row in four_signals if _bucket(row["fill_time"]) in agg_signal_buckets)
    same_day_trades = sum(1 for row in four_taken if row["day"] in agg_trade_days)
    four_pnl, four_n = _pnl_vector(four_taken, sessions)
    agg_pnl, agg_n = _pnl_vector(agg_taken, sessions)
    either = (four_n > 0) | (agg_n > 0)
    union_days = four_days | agg_days
    union_trade_days = four_trade_days | agg_trade_days
    return {
        "four_signal_days": len(four_days),
        "aggressive_signal_days": len(agg_days),
        "common_signal_days": len(common_days),
        "share_of_four_signal_days": _share(len(common_days), len(four_days)),
        "share_of_aggressive_signal_days": _share(len(common_days), len(agg_days)),
        "signal_day_jaccard": _share(len(common_days), len(union_days)),
        "four_signals": len(four_signals),
        "aggressive_signals": len(agg_signals),
        "four_signals_in_aggressive_bucket": four_signal_bucket_hits,
        "share_of_four_signals_in_aggressive_bucket": _share(four_signal_bucket_hits, len(four_signals)),
        "four_filled_trades": len(four_taken),
        "aggressive_filled_trades": len(agg_taken),
        "common_filled_days": len(common_trade_days),
        "share_of_four_filled_days": _share(len(common_trade_days), len(four_trade_days)),
        "share_of_aggressive_filled_days": _share(len(common_trade_days), len(agg_trade_days)),
        "filled_day_jaccard": _share(len(common_trade_days), len(union_trade_days)),
        "four_trades_on_aggressive_day": same_day_trades,
        "share_of_four_trades_on_aggressive_day": _share(same_day_trades, len(four_taken)),
        "four_trades_in_aggressive_bucket": four_bucket_hits,
        "share_of_four_trades_in_aggressive_bucket": _share(four_bucket_hits, len(four_taken)),
        "pnl_correlation_all_days": _pearson(four_pnl, agg_pnl),
        "pnl_correlation_either_traded": _pearson(four_pnl[either], agg_pnl[either]),
        "days_either_traded": int(either.sum()),
    }


def _aggressive(frame: pd.DataFrame, iv: dict) -> dict:
    fifteen = to_fifteen(frame)
    structures = vwap_structures(fifteen, "QQQ")
    priced = _price_rows(structures, iv)
    sessions = session_dates(fifteen)
    out = {"rows": priced, "sessions": sessions}
    for name, start, end in (("train", TRAIN_START, TRAIN_END), ("holdout", HOLDOUT_START, HOLDOUT_END)):
        out[name] = _window(priced, sessions, start, end, 5)
        metrics = out[name]["metrics"]
        print(
            f"AGGRESSIVE {name} trades {metrics.get('trades')} ending {metrics.get('ending_equity')}",
            flush=True,
        )
    return out


def _money(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"${float(value):,.0f}"


def _pct(value) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.1%}"


def _num(value, digits: int = 2) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def _metric_cells(metrics: dict, dsr: float) -> str:
    return (
        f"{int(metrics.get('trades') or 0)} | {_pct(metrics.get('win_rate'))} | "
        f"{_num(metrics.get('profit_factor'))} | {_num(metrics.get('sharpe'))} | "
        f"{_pct(metrics.get('max_drawdown'))} | {_money(metrics.get('ending_equity'))} | {_num(dsr, 3)}"
    )


def _jsonable(value):
    if isinstance(value, dict):
        skip = {
            "equity",
            "pnls",
            "taken",
            "rows",
            "events",
            "stitched",
            "wf_equity",
            "train_pnls",
            "train_equity",
            "holdout_equity",
            "holdout_taken",
            "train_taken",
        }
        return {key: _jsonable(item) for key, item in value.items() if key not in skip}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, pd.Series):
        return None
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (date, pd.Timestamp)):
        return value.isoformat()
    return value


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


def _upsert(path: Path, body: str) -> None:
    text = path.read_text() if path.exists() else ""
    block = f"{START_MARK}\n{body.rstrip()}\n{END_MARK}\n"
    if START_MARK in text and END_MARK in text:
        pre, rest = text.split(START_MARK, 1)
        _old, post = rest.split(END_MARK, 1)
        path.write_text(pre + block + post.lstrip("\n"))
        return
    anchor = "<!-- FOUR_HOUR_END -->"
    if anchor in text:
        path.write_text(text.replace(anchor, anchor + "\n" + block, 1))
        return
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n" + block)


def _public_metrics(metrics: dict) -> dict:
    keys = (
        "trades",
        "win_rate",
        "profit_factor",
        "sharpe",
        "max_drawdown",
        "ending_equity",
    )
    return {key: metrics.get(key) for key in keys}


def _prose(result: dict) -> str:
    choice = result["selection"]
    rows = result["rows"]
    by_id = {row["id"]: row for row in rows}
    base = by_id["base"]
    selected = by_id[choice["id"]]
    lines = [
        "# 4hr refinement",
        "",
        result["lead"],
        "",
        "The choice used the mean of four fresh yearly Sharpes, 2020 through 2023. "
        "A refinement had to beat the base mean and collect at least 80 trades across those years. "
        "The holdout column was computed after that choice and did not vote.",
        "",
        (
            f"Family size for this round is {result['n_trials']}: the original {PRIOR_TRIALS} cells, "
            f"these {len(REFINEMENT_IDS)} single changes, and "
            + (
                "the one combination. "
                if result["combo_scored"]
                else "no combination, because fewer than two refinements won. "
            )
            + "The base cell is already inside the original 72, so it is not counted again. "
            "Deflated Sharpe uses that expanded count. The original published deflated Sharpe of "
            f"{result['published_base_dsr']:.3f} used 72 trials and is a little easier than the number in this table. "
            "The gate is the original one, including full-train Sharpe against seed 17, the expanded q, "
            "and full-train deflated Sharpe. The drawdown line and the 0.95 line were not moved."
        ),
        "",
        "Dukascopy volume is a bid-tick count. The dead-tape filter uses VIX1D only. "
        "That cache starts 2023-04-24, and 252 prior closes do not exist anywhere in 2017-2023, "
        "so on the train and on the walk-forward the dead-tape book is the base book.",
        "",
        "## Walk-forward selection",
        "",
        "Mean is the average of the four yearly Sharpes. Trades are the four years added together. "
        "A winner is marked yes.",
        "",
        "| Rule | Mean Sharpe | 2020 | 2021 | 2022 | 2023 | Trades | Winner |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        if row["id"] == "combo":
            continue
        yearly = {item["year"]: item["sharpe"] for item in row["yearly"]}
        winner = "yes" if row["id"] in choice["winners"] else ""
        lines.append(
            f"| {LABELS[row['id']]} | {_num(row['mean_yearly_sharpe'])} | "
            f"{_num(yearly[2020])} | {_num(yearly[2021])} | {_num(yearly[2022])} | {_num(yearly[2023])} | "
            f"{row['wf_trades']} | {winner} |"
        )
    if result["combo_scored"]:
        combo = by_id["combo"]
        yearly = {item["year"]: item["sharpe"] for item in combo["yearly"]}
        lines.append(
            f"| {LABELS['combo']} | {_num(combo['mean_yearly_sharpe'])} | "
            f"{_num(yearly[2020])} | {_num(yearly[2021])} | {_num(yearly[2022])} | {_num(yearly[2023])} | "
            f"{combo['wf_trades']} | selected |"
        )
    lines.extend(
        [
            "",
            "## Walk-forward account, 2020-2023, one fresh $2,500",
            "",
            "This is one account across the four years, which is not the same object as the mean of four fresh years. "
            "Deflated Sharpe here uses this account's daily returns and the expanded trial count.",
            "",
            "| Rule | Trades | Win | PF | Sharpe | Max DD | Ending | Deflated Sharpe |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(f"| {LABELS[row['id']]} | {_metric_cells(row['walk_forward'], row['wf_dsr'])} |")
    lines.extend(
        [
            "",
            "## Holdout, 2024-01-01 through 2026-10-06, one fresh $2,500",
            "",
            "Scored once after selection. Deflated Sharpe here uses the holdout daily returns and the same trial count. "
            "The gate's deflated-Sharpe leg is the full 2017-2023 train, shown in the last table.",
            "",
            "| Rule | Trades | Win | PF | Sharpe | Max DD | Ending | Deflated Sharpe |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(f"| {LABELS[row['id']]} | {_metric_cells(row['holdout'], row['holdout_dsr'])} |")
    lines.extend(
        [
            "",
            "## Gate, full train 2017-2023",
            "",
            "| Rule | Train trades | Train Sharpe | Train ending | Full-train DSR | q | Seed-17 train Sharpe | Gate |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {LABELS[row['id']]} | {int(row['train'].get('trades') or 0)} | "
            f"{_num(row['train'].get('sharpe'))} | {_money(row['train'].get('ending_equity'))} | "
            f"{_num(row['train_dsr'], 3)} | {_num(row['q'], 3)} | {_num(row['random_train'].get('sharpe'))} | {row['gate']} |"
        )
    overlap = result["overlap"]
    lines.extend(["", "## Overlap with QQQ Aggressive", ""])
    lines.append(result["overlap_prose"])
    lines.extend(["", "| Window | 4hr signal days | Aggressive signal days | Days in common | Share of 4hr days | Share of Aggressive days | 4hr trades | Aggressive trades | 4hr trades on an Aggressive day | 4hr trades in the same 15-minute bucket | Corr, all days | Corr, days either traded |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for name in ("train", "holdout"):
        item = overlap[name]
        lines.append(
            f"| {name} | {item['four_signal_days']} | {item['aggressive_signal_days']} | {item['common_signal_days']} | "
            f"{_pct(item['share_of_four_signal_days'])} | {_pct(item['share_of_aggressive_signal_days'])} | "
            f"{item['four_filled_trades']} | {item['aggressive_filled_trades']} | "
            f"{_pct(item['share_of_four_trades_on_aggressive_day'])} | "
            f"{_pct(item['share_of_four_trades_in_aggressive_bucket'])} | "
            f"{_num(item['pnl_correlation_all_days'])} | {_num(item['pnl_correlation_either_traded'])} |"
        )
    lines.extend(
        [
            "",
            "Daily P&L for the correlation is the sum of that day's filled-trade P&L, and zero when the book did not trade. "
            "QQQ Aggressive was rebuilt on the same caches: 15-minute 2 SD continuation, 1R, unscaled 1 DTE, 1 cent, one contract, cap 5.",
            "",
            f"Selected rule: {LABELS[selected['id']]}. "
            f"Holdout ending {_money(selected['holdout'].get('ending_equity'))} on {int(selected['holdout'].get('trades') or 0)} trades, "
            f"profit factor {_num(selected['holdout'].get('profit_factor'))}, Sharpe {_num(selected['holdout'].get('sharpe'))}, "
            f"max drawdown {_pct(selected['holdout'].get('max_drawdown'))}. "
            f"Base holdout ending {_money(base['holdout'].get('ending_equity'))} on {int(base['holdout'].get('trades') or 0)} trades, "
            f"profit factor {_num(base['holdout'].get('profit_factor'))}, Sharpe {_num(base['holdout'].get('sharpe'))}, "
            f"max drawdown {_pct(base['holdout'].get('max_drawdown'))}. "
            f"Gate for the selected rule: {selected['gate']}.",
            "",
            "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. "
            "Nothing was sent to a broker.",
            "",
            "```",
            "PYTHONPATH=src python3 -m webull_bot.chart_reads.research_four_hour_refine",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _lead(choice: dict, rows: list[dict]) -> str:
    by_id = {row["id"]: row for row in rows}
    base = by_id["base"]
    selected = by_id[choice["id"]]
    if choice["id"] == "base":
        return (
            "Refining this cell did not clear a better rule on the train walk-forward. "
            f"None of the eight single changes beat the base mean yearly Sharpe of {_num(base['mean_yearly_sharpe'])} "
            f"with at least 80 trades. The selected rule stays the base. "
            f"Its one holdout look still ends at {_money(base['holdout'].get('ending_equity'))} "
            f"on {int(base['holdout'].get('trades') or 0)} trades, and the expanded family keeps it short of the gate "
            f"({base['gate']})."
        )
    parts = ", ".join(LABELS[name] for name in choice["parts"])
    kind = "The combination of the train winners" if choice["kind"] == "combination" else "The one train winner"
    return (
        f"{kind} ({parts}) is the selected rule. "
        f"Its walk-forward mean Sharpe is {_num(selected['mean_yearly_sharpe'])} against the base "
        f"{_num(base['mean_yearly_sharpe'])}. Scored once on the holdout, it ends at "
        f"{_money(selected['holdout'].get('ending_equity'))} on {int(selected['holdout'].get('trades') or 0)} trades, "
        f"profit factor {_num(selected['holdout'].get('profit_factor'))}, Sharpe {_num(selected['holdout'].get('sharpe'))}, "
        f"max drawdown {_pct(selected['holdout'].get('max_drawdown'))}, "
        f"against the base holdout {_money(base['holdout'].get('ending_equity'))} on "
        f"{int(base['holdout'].get('trades') or 0)} trades. Gate: {selected['gate']}."
    )


def _overlap_prose(overlap: dict) -> str:
    hold = overlap["holdout"]
    train = overlap["train"]
    return (
        "Running both books is only a partial diversifier. "
        f"On the holdout, {_pct(hold['share_of_four_signal_days'])} of 4hr signal days are also QQQ Aggressive signal days, "
        f"and {_pct(hold['share_of_four_trades_in_aggressive_bucket'])} of filled 4hr trades share a 15-minute bucket "
        f"with a filled Aggressive trade. "
        f"Daily filled-trade P&L correlation is {_num(hold['pnl_correlation_all_days'])} across every holdout session "
        f"and {_num(hold['pnl_correlation_either_traded'])} on sessions where at least one book traded. "
        f"The train figures are {_pct(train['share_of_four_signal_days'])} of signal days in common and "
        f"a daily P&L correlation of {_num(train['pnl_correlation_all_days'])}."
    )


def _blurb(result: dict) -> str:
    choice = result["selection"]
    by_id = {row["id"]: row for row in result["rows"]}
    selected = by_id[choice["id"]]
    base = by_id["base"]
    return (
        "**4hr refinement: does not join the book.** Eight single changes to the QQQ 4-hour EMA, "
        "session-VWAP, 1R, 1 DTE cell, chosen on a 2020-2023 walk-forward and scored once on the holdout. "
        f"Selected rule: {LABELS[choice['id']]}. "
        f"Holdout ending {_money(selected['holdout'].get('ending_equity'))} "
        f"on {int(selected['holdout'].get('trades') or 0)} trades, gate {selected['gate']}. "
        f"Base holdout stays {_money(base['holdout'].get('ending_equity'))} "
        f"on {int(base['holdout'].get('trades') or 0)} trades. "
        "The chart is `reports/four_hour_refine_equity.png`. Nothing was sent to a broker."
    )


def _finish_row(variant: dict, wf: dict, sessions: list[date], book: Book, iv: dict, trials: int) -> dict:
    train = _window(variant["rows"], sessions, TRAIN_START, TRAIN_END, variant["cap"])
    hold = _window(variant["rows"], sessions, HOLDOUT_START, HOLDOUT_END, variant["cap"])
    print(f"RANDOM {variant['id']}", flush=True)
    drawn = random_events(book, variant["events"], TRAIN_START, TRAIN_END)
    random_rows = _price_rows(resolve(book, drawn, variant["exit"]), iv)
    random_train = _window(random_rows, sessions, TRAIN_START, TRAIN_END, variant["cap"])
    return {
        "id": variant["id"],
        "cap": variant["cap"],
        "exit": variant["exit"],
        "signals": variant["signals"],
        "quoted": variant["quoted"],
        "mean_yearly_sharpe": wf["mean_yearly_sharpe"],
        "wf_trades": wf["wf_trades"],
        "yearly": wf["yearly"],
        "walk_forward": _public_metrics(wf["stitched"]["metrics"]),
        "wf_equity": wf["stitched"]["equity"],
        "wf_dsr": _dsr(wf["stitched"]["equity"], trials),
        "train": _public_metrics(train["metrics"]),
        "train_pnls": train["pnls"],
        "train_equity": train["equity"],
        "train_dsr": _dsr(train["equity"], trials),
        "holdout": _public_metrics(hold["metrics"]),
        "holdout_equity": hold["equity"],
        "holdout_taken": hold["taken"],
        "holdout_dsr": _dsr(hold["equity"], trials),
        "train_taken": train["taken"],
        "random_train": _public_metrics(random_train["metrics"]),
        "p": p_value(train["pnls"]),
    }


def main() -> None:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    rules = frozen_refine_rules()
    RULES_PATH.write_text(json.dumps(rules, indent=2) + "\n")
    print(f"RULES {RULES_PATH}", flush=True)

    frame, path = _load_bars("QQQ")
    iv = prior_iv(_load_series("VIX1D"), _load_series("VIX"))
    vix1d = _load_series("VIX1D")
    print(f"PREPARE QQQ bars {len(frame)} file {path}", flush=True)
    book = Book(frame, "QQQ")
    sessions = session_days(book)
    dead_days = dead_trade_days(vix1d, sessions)
    print(f"DEAD TAPE days {len(dead_days)}", flush=True)
    base_events = find_signals(book, "ema", "vwap", hold_vwap=False)
    hold_events = find_signals(book, "ema", "vwap", hold_vwap=True)
    print(f"SIGNALS base {len(base_events)} vwap-hold {len(hold_events)}", flush=True)

    variants = []
    for name in ("base",) + REFINEMENT_IDS:
        print(f"BUILD {name}", flush=True)
        built = _build(book, iv, base_events, hold_events, [] if name == "base" else [name], dead_days)
        built["id"] = name
        variants.append(built)
        print(f"  signals {built['signals']} quoted {built['quoted']}", flush=True)

    _check_base(variants[0]["rows"], sessions)
    print("BASE TRAIN matches the published cell", flush=True)

    wf_by_id = {}
    selection_rows = []
    for variant in variants:
        print(f"WALK {variant['id']}", flush=True)
        wf = _walk_forward(variant["rows"], sessions, variant["cap"])
        wf_by_id[variant["id"]] = wf
        selection_rows.append(
            {
                "id": variant["id"],
                "mean_yearly_sharpe": wf["mean_yearly_sharpe"],
                "wf_trades": wf["wf_trades"],
            }
        )
        print(
            f"  mean {wf['mean_yearly_sharpe']:.4f} trades {wf['wf_trades']}",
            flush=True,
        )

    base_mean = next(item["mean_yearly_sharpe"] for item in selection_rows if item["id"] == "base")
    winners = train_winners(base_mean, selection_rows)
    choice = selected_rule(winners)
    print(f"WINNERS {winners} CHOICE {choice}", flush=True)

    combo_scored = False
    if choice["extra_trial"]:
        print("BUILD combo", flush=True)
        combo = _build(book, iv, base_events, hold_events, choice["parts"], dead_days)
        combo["id"] = "combo"
        combo_wf = _walk_forward(combo["rows"], sessions, combo["cap"])
        wf_by_id["combo"] = combo_wf
        variants.append(combo)
        combo_scored = True
        print(f"  combo mean {combo_wf['mean_yearly_sharpe']:.4f} trades {combo_wf['wf_trades']}", flush=True)

    # Holdout starts here. Selection above did not read it.
    trials = PRIOR_TRIALS + len(REFINEMENT_IDS) + (1 if combo_scored else 0)
    finished = []
    for variant in variants:
        print(f"SCORE {variant['id']}", flush=True)
        finished.append(_finish_row(variant, wf_by_id[variant["id"]], sessions, book, iv, trials))
        row = finished[-1]
        print(
            f"  hold {row['holdout'].get('trades')} end {row['holdout'].get('ending_equity')}",
            flush=True,
        )

    family = json.loads(FAMILY_PATH.read_text())
    saved_p = [float(cell["p"]) for cell in family["cells"]]
    base_index = next(i for i, cell in enumerate(family["cells"]) if cell["id"] == BASE_CELL)
    refine_ids = [row["id"] for row in finished if row["id"] != "base"]
    refine_p = [next(row["p"] for row in finished if row["id"] == name) for name in refine_ids]
    q_values = [float(item) for item in benjamini_hochberg(saved_p + refine_p)]
    q_by_refine = {name: q_values[len(saved_p) + i] for i, name in enumerate(refine_ids)}
    q_by_refine["base"] = q_values[base_index]

    for row in finished:
        row["q"] = q_by_refine[row["id"]]
        row["passes"] = passes_gate(row["holdout"], row["train"], row["random_train"], row["q"], row["train_dsr"])
        row["gate"] = gate_label(row["holdout"], row["train"], row["random_train"], row["q"], row["train_dsr"])

    print("AGGRESSIVE", flush=True)
    aggressive = _aggressive(frame, iv)
    for name, published_key in (("train", "train"), ("holdout", "holdout")):
        gap_trades = abs(int(aggressive[name]["metrics"]["trades"]) - PUBLISHED[published_key]["trades"])
        gap_money = abs(float(aggressive[name]["metrics"]["ending_equity"]) - PUBLISHED[published_key]["ending_equity"])
        print(f"  published gap {name} trades {gap_trades} money {gap_money:.2f}", flush=True)
        if gap_trades != 0 or gap_money > 0.05:
            raise RuntimeError(f"QQQ Aggressive drifted on {name}")

    overlap = {}
    base_row = next(row for row in finished if row["id"] == "base")
    for name, start, end in (("train", TRAIN_START, TRAIN_END), ("holdout", HOLDOUT_START, HOLDOUT_END)):
        four_signals = [row for row in variants[0]["rows"] if start <= row["day"] <= end]
        overlap[name] = _overlap(
            four_signals,
            base_row["train_taken"] if name == "train" else base_row["holdout_taken"],
            [row for row in aggressive["rows"] if start <= row["day"] <= end],
            aggressive[name]["taken"],
            [day for day in sessions if start <= day <= end],
        )

    hold_check = _window(variants[0]["rows"], sessions, HOLDOUT_START, HOLDOUT_END, 5)
    if int(hold_check["metrics"]["trades"]) != PUBLISHED_BASE["holdout_trades"]:
        raise RuntimeError("base holdout trade count drifted")
    if abs(float(hold_check["metrics"]["ending_equity"]) - PUBLISHED_BASE["holdout_ending"]) > 0.02:
        raise RuntimeError("base holdout ending drifted")

    # Confirm the rules file was not rewritten after the score.
    written = json.loads(RULES_PATH.read_text())
    if written != rules:
        raise RuntimeError("rules file changed during the score")

    choice_public = {
        "winners": winners,
        "id": choice["id"],
        "kind": choice["kind"],
        "parts": choice["parts"],
        "extra_trial": choice["extra_trial"],
        "base_mean_yearly_sharpe": base_mean,
    }
    result = {
        "selection": choice_public,
        "rows": finished,
        "n_trials": trials,
        "combo_scored": combo_scored,
        "published_base_dsr": 0.9045376762526429,
        "overlap": overlap,
        "dead_tape_days": len(dead_days),
    }
    result["lead"] = _lead(choice_public, finished)
    result["overlap_prose"] = _overlap_prose(overlap)
    prose = _prose(result)
    MD_PATH.write_text(prose)
    series = [("4hr base, 1 DTE", base_row["holdout_equity"])]
    if choice["id"] != "base":
        selected = next(row for row in finished if row["id"] == choice["id"])
        series.append((f"Selected: {LABELS[choice['id']]}", selected["holdout_equity"]))
    _chart(EQUITY_PATH, series)
    payload = {
        "rules_path": str(RULES_PATH),
        "n_trials": trials,
        "prior_trials": PRIOR_TRIALS,
        "published_base_dsr_at_72": result["published_base_dsr"],
        "dead_tape_days": len(dead_days),
        "selection": choice_public,
        "lead": result["lead"],
        "overlap_prose": result["overlap_prose"],
        "rows": [_jsonable(row) for row in finished],
        "overlap": _jsonable(overlap),
        "aggressive_gap": {
            name: {
                "trade_gap": abs(int(aggressive[name]["metrics"]["trades"]) - PUBLISHED[name]["trades"]),
                "money_gap": abs(float(aggressive[name]["metrics"]["ending_equity"]) - PUBLISHED[name]["ending_equity"]),
            }
            for name in ("train", "holdout")
        },
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    blurb = _blurb(result)
    _upsert(README_PATH, blurb)
    _upsert(RESULTS_PATH, blurb)
    print(f"WROTE {MD_PATH} selected {choice['id']}", flush=True)


if __name__ == "__main__":
    main()
