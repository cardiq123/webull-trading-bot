"""Train and holdout for 0, 1, 3, and 7 DTE on the original 2 SD extension.

Backtests only. Does not edit vwap_band_15m or the quality-filter family.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.vwap_band import (
    HOLDOUT_START,
    SAMPLE_END,
    TRAIN_END,
    find_signals,
    passes_gate,
)
from webull_bot.chart_reads.vwap_band_data import load_minutes, to_fifteen_minute
from webull_bot.chart_reads.vwap_expiry import (
    CONTRACTS,
    contract_name,
    day_trade_stats,
    price_contracts,
    run_expiry_account,
)
from webull_bot.chart_reads.vwap_quality import (
    FDR_MIN_TRADES,
    FDR_Q,
    benjamini_hochberg,
    one_sided_p,
    sessions_between,
    trade_t,
)
from webull_bot.data.yfinance_provider import YFinanceProvider

MARK_START = "<!-- VWAP_EXPIRY_START -->"
MARK_END = "<!-- VWAP_EXPIRY_END -->"
RESULT_PATH = Path("reports/vwap_expiry.json")
NY = "America/New_York"


def _money(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    number = float(value)
    if abs(number) < 0.5:
        return "$0"
    if number < 0:
        return f"-${abs(number):,.0f}"
    return f"${number:,.0f}"


def _pct(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _num(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _pf(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _iv_frame() -> tuple[dict, dict]:
    provider = YFinanceProvider(cache_dir="data/cache/vwap_band/yahoo")
    daily = provider.history(["^VIX", "^VIX1D"], "2016-01-01", "2026-10-08", interval="1d")
    closes = {}
    for symbol, frame in daily.items():
        if frame is None or frame.empty or "close" not in frame.columns:
            continue
        series = frame["close"].astype(float).copy()
        index = pd.to_datetime(series.index)
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert(NY).tz_localize(None)
        series.index = index
        closes[symbol.replace("^", "")] = series[~series.index.duplicated(keep="last")].sort_index()
    vix = closes.get("VIX", pd.Series(dtype=float))
    vix1d = closes.get("VIX1D", pd.Series(dtype=float))
    return prior_iv(vix1d, vix), prior_iv(pd.Series(dtype=float), vix)


def _brief(result: dict, sessions: list[date]) -> dict:
    metrics = result["metrics"]
    trades = int(metrics.get("trades") or 0)
    return {
        "ending_equity": metrics.get("ending_equity"),
        "trades": trades,
        "trades_per_day": trades / max(len(sessions), 1),
        "win_rate": metrics.get("win_rate"),
        "breakeven_win_rate": metrics.get("breakeven_win_rate"),
        "profit_factor": metrics.get("profit_factor"),
        "sharpe": metrics.get("sharpe"),
        "max_drawdown": metrics.get("max_drawdown"),
        "pdt": day_trade_stats(result["spans"], sessions),
        "t": trade_t([float(trade["pnl"]) for trade in result["trades"]]),
        "passes": bool(passes_gate(metrics)),
    }


def _best(rows: list[dict]) -> dict | None:
    robust = [row for row in rows if row["robust"]]

    def sharpe(row: dict) -> float:
        value = row["hold_1000"].get("sharpe")
        if value is None or not np.isfinite(value):
            return -1e9
        return float(value)

    pool = robust or rows
    return max(pool, key=sharpe) if pool else None


def _sentence(rows: list[dict], best: dict | None) -> str:
    if best is None:
        return "No expiry row was scored."
    robust = [row["contract"] for row in rows if row["robust"]]
    hold = best["hold_1000"]
    train = best["train_1000"]
    if robust:
        which = (
            f"{best['contract']} is the robust contract with the highest holdout Sharpe. "
            f"Robust on both windows: {', '.join(robust)}."
        )
    else:
        which = (
            "No contract clears the published gate on both the train window and the holdout, "
            "after the seven-contract false-discovery check. "
            f"{best['contract']} has the highest holdout Sharpe and is not a promotion."
        )
    pdt = hold.get("pdt") or {}
    return (
        "The table is the original uncapped 2 SD continuation, 1R, one position. The quality filters are not crossed with it. "
        f"{which} "
        f"On that contract the $1,000 holdout finished at {_money(hold.get('ending_equity'))} "
        f"({hold.get('trades', 0)} trades, {hold.get('trades_per_day', 0):.2f} a day, "
        f"win {_pct(hold.get('win_rate'))} against break-even {_pct(hold.get('breakeven_win_rate'))}, "
        f"profit factor {_pf(hold.get('profit_factor'))}, Sharpe {_num(hold.get('sharpe'))}, "
        f"drawdown {_pct(hold.get('max_drawdown'))}). "
        f"Training finished at {_money(train.get('ending_equity'))}. "
        f"From $5,000 the holdout finished at {_money(best['hold_5000'].get('ending_equity'))} "
        f"and training at {_money(best['train_5000'].get('ending_equity'))}. "
        f"Holdout same-day round trips {pdt.get('day_trades', 0)}, overnight holds {pdt.get('overnight_holds', 0)}, "
        f"worst same-day count in any five sessions {pdt.get('worst_day_trades_in_5_sessions', 0)}, "
        f"five-session windows over 3 day trades {pdt.get('windows_over_3', 0)} of {pdt.get('windows', 0)}. "
        "A $1,000 or $5,000 margin account is under the $25,000 pattern-day-trader line. "
        "This test is a cash account: it does not refuse the fourth day trade, and a sale settles the next session. "
        "An overnight hold that closes on a later session is not a day trade. The debit stays invested until that exit. "
        "vwap_band_15m was not changed."
    )


def _lines(rows: list[dict], sentence: str) -> list[str]:
    lines = [
        MARK_START,
        "### VWAP extension by option expiry",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. " + sentence,
        "",
        "| Contract | Window | Trades/day | Win | Break-even | PF | Sharpe | Max DD | $1k end | $5k end | Gate |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        for window, key, five_key in (("train", "train_1000", "train_5000"), ("holdout", "hold_1000", "hold_5000")):
            metrics = row[key]
            five = row[five_key]
            lines.append(
                f"| {row['contract']} | {window} | {metrics.get('trades_per_day', 0):.2f} | "
                f"{_pct(metrics.get('win_rate'))} | {_pct(metrics.get('breakeven_win_rate'))} | "
                f"{_pf(metrics.get('profit_factor'))} | {_num(metrics.get('sharpe'))} | "
                f"{_pct(metrics.get('max_drawdown'))} | {_money(metrics.get('ending_equity'))} | "
                f"{_money(five.get('ending_equity'))} | {'yes' if metrics.get('passes') else 'no'} |"
            )
    lines += [
        "",
        "Not added to `config/optional_strategies.json` or `config/selected_strategies.json`.",
        "",
        "```",
        "python3 -m webull_bot.chart_reads.research_vwap_expiry",
        "```",
        MARK_END,
        "",
    ]
    return lines


def _write(lines: list[str]) -> None:
    block = "\n".join(lines)
    path = Path("RESULTS.md")
    text = path.read_text() if path.exists() else ""
    if MARK_START in text and MARK_END in text:
        before = text.split(MARK_START)[0]
        after = text.split(MARK_END)[1]
        path.write_text(before + block + after.lstrip("\n"))
    else:
        path.write_text(text.rstrip() + "\n\n" + block)
    readme = Path("README.md")
    body = readme.read_text() if readme.exists() else ""
    paragraph = next((line for line in lines if line.startswith("Backtests only.")), "")
    readme_block = "\n".join([MARK_START, paragraph, "", "Full table in [RESULTS.md](RESULTS.md).", MARK_END, ""])
    if MARK_START in body and MARK_END in body:
        before = body.split(MARK_START)[0]
        after = body.split(MARK_END)[1]
        readme.write_text(before + readme_block + after.lstrip("\n"))
    else:
        readme.write_text(body.rstrip() + "\n\n" + readme_block)


def _fdr(rows: list[dict]) -> dict[str, float | None]:
    tested = []
    for row in rows:
        metrics = row["hold_1000"]
        p_value = one_sided_p(metrics.get("t"))
        if int(metrics.get("trades") or 0) >= FDR_MIN_TRADES and p_value is not None:
            tested.append((row["contract"], float(p_value)))
    adjusted = benjamini_hochberg([p_value for _name, p_value in tested])
    found = {row["contract"]: None for row in rows}
    for (name, _p_value), q_value in zip(tested, adjusted):
        found[name] = float(q_value)
    return found


def main() -> None:
    print("LOAD", flush=True)
    minutes, info = load_minutes("SPY")
    if minutes is None:
        raise SystemExit(f"SPY minutes unavailable: {info}")
    fifteen = to_fifteen_minute(minutes)
    short_points, long_points = _iv_frame()
    signals = [item for item in find_signals(fifteen, "SPY", 2.0) if item.mode == "extension"]
    print(f"SIGNALS {len(signals)}", flush=True)
    books = price_contracts(fifteen, signals, short_points, long_points)
    train_sessions = sessions_between(fifteen, None, TRAIN_END)
    hold_sessions = sessions_between(fifteen, HOLDOUT_START, SAMPLE_END)
    rows = []
    for dte, hold in CONTRACTS:
        name = contract_name(dte, hold)
        print(f"SCORE {name}", flush=True)
        priced = books[name]
        packed = {"contract": name, "dte": dte, "hold": hold}
        for label, stake, sessions, start, end in (
            ("train_1000", 1000.0, train_sessions, None, TRAIN_END),
            ("train_5000", 5000.0, train_sessions, None, TRAIN_END),
            ("hold_1000", 1000.0, hold_sessions, HOLDOUT_START, SAMPLE_END),
            ("hold_5000", 5000.0, hold_sessions, HOLDOUT_START, SAMPLE_END),
        ):
            result = run_expiry_account(fifteen, priced, stake=stake, start=start, end=end)
            packed[label] = _brief(result, sessions)
        rows.append(packed)
    q_values = _fdr(rows)
    for row in rows:
        q_value = q_values[row["contract"]]
        row["q"] = q_value
        row["robust"] = bool(
            row["train_1000"]["passes"]
            and row["hold_1000"]["passes"]
            and q_value is not None
            and q_value <= FDR_Q
        )
    best = _best(rows)
    sentence = _sentence(rows, best)
    _write(_lines(rows, sentence))
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps({"rows": rows, "best": None if best is None else best["contract"], "sentence": sentence}, indent=2, default=str) + "\n")
    print(sentence, flush=True)
    print("WROTE reports/vwap_expiry.json", flush=True)


if __name__ == "__main__":
    main()
