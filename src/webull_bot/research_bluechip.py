"""Dow reversal study: stock book, then a Black-Scholes options estimate.

The stock book uses the same gates as the rest of the project. Modeled
option profits do not get their own gate. A pass joins the default book
only when the out-of-sample Sharpe beats dual momentum by at least 0.15.
Otherwise a pass is optional, and a failure is neither.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from webull_bot.backtest.report import write_html_report
from webull_bot.costs import CostModel
from webull_bot.options.overlay import simulate_overlay
from webull_bot.strategies.registry import strategy_by_name
from webull_bot.universe_dow import all_dow_tickers

# Pre-registered before the run. "Clearly beats" means this much more
# out-of-sample Sharpe than the incumbent dual-momentum book.
CLEAR_BEAT_SHARPE = 0.15
OOS_START = "2017-01-01"
IN_SAMPLE_START = "2013-01-01"
IN_SAMPLE_END = "2016-12-31"


def ensure_dow_history(provider, bars: dict, end: str) -> list[str]:
    needed = all_dow_tickers()
    missing = [symbol for symbol in needed if symbol not in bars or bars[symbol].empty]
    if missing:
        bars.update(provider.history(missing, "2009-06-01", end, "1d"))
    if ("UTX" not in bars or bars["UTX"].empty) and "RTX" in bars and not bars["RTX"].empty:
        # Yahoo often continues United Technologies under RTX. Membership
        # windows do not overlap, so the two symbols do not both trade a day.
        bars["UTX"] = bars["RTX"]
    return [symbol for symbol in needed if symbol not in bars or bars[symbol].empty]


def run_bluechip_stock(bars, limits, costs, sample_end) -> Any:
    from webull_bot.research import STARTING_EQUITY, _execute, _study_daily

    strategy = strategy_by_name("bluechip_reversal")
    study = _study_daily(strategy, "dow", bars, limits, costs, sample_end=sample_end)
    earlier = _execute(
        strategy, "dow", bars, limits, costs,
        trade_start=pd.Timestamp(IN_SAMPLE_START),
        trade_end=pd.Timestamp(IN_SAMPLE_END),
        params=dict(strategy.default_params),
    )
    from webull_bot.backtest.assessment import profit_factor_value
    from webull_bot.backtest.metrics import compute_metrics

    study.insample_metrics = compute_metrics(earlier, STARTING_EQUITY)
    study.insample_trades = earlier.trades
    harsh = CostModel(slippage_bps=15.0, half_spread_bps=2.0)
    stressed = _execute(
        strategy, "dow", bars, limits, costs=harsh,
        trade_start=pd.Timestamp(OOS_START),
        trade_end=pd.Timestamp(sample_end),
        params=dict(strategy.default_params),
    )
    study.stress_metrics = compute_metrics(stressed, STARTING_EQUITY)
    stress_pf = profit_factor_value(study.stress_metrics)
    stress_sharpe = float(study.stress_metrics.get("sharpe") or 0)
    if stress_pf < 1.0 or stress_sharpe < 0:
        study.flags.append("cost_fragile")
        study.selectable = False
        study.notes.append(
            f"At 15 bps slippage and 2 bps half-spread, OOS profit factor was "
            f"{stress_pf:.2f} and Sharpe was {stress_sharpe:.2f}."
        )
    else:
        study.notes.append(
            f"Still profitable at 15 bps slippage (Sharpe {stress_sharpe:.2f}, "
            f"profit factor {stress_pf:.2f})."
        )
    return study


def price_options(study, bars, sample_end) -> dict[str, Any]:
    clock = bars["SPY"].index
    clock = clock[(clock >= pd.Timestamp(OOS_START)) & (clock <= pd.Timestamp(sample_end))]
    packs = {
        "call_oos": simulate_overlay(study.oos_trades, bars, structure="call", clock=clock),
        "spread_oos": simulate_overlay(study.oos_trades, bars, structure="spread", clock=clock),
        "call_wf": simulate_overlay(study.wf_trades, bars, structure="call"),
        "spread_wf": simulate_overlay(study.wf_trades, bars, structure="spread"),
        "call_is": simulate_overlay(study.insample_trades, bars, structure="call"),
        "spread_is": simulate_overlay(study.insample_trades, bars, structure="spread"),
        "call_iv_1": simulate_overlay(study.oos_trades, bars, structure="call", iv_premium=1.0, clock=clock),
        "call_iv_130": simulate_overlay(study.oos_trades, bars, structure="call", iv_premium=1.30, clock=clock),
        "spread_iv_1": simulate_overlay(study.oos_trades, bars, structure="spread", iv_premium=1.0, clock=clock),
        "spread_iv_130": simulate_overlay(study.oos_trades, bars, structure="spread", iv_premium=1.30, clock=clock),
        "call_wide": simulate_overlay(study.oos_trades, bars, structure="call", spread_multiplier=2.0, clock=clock),
        "spread_wide": simulate_overlay(study.oos_trades, bars, structure="spread", spread_multiplier=2.0, clock=clock),
    }
    study.options = packs
    return packs


DOW_BOOKS = ("bluechip_reversal", "support_reversal", "wedge_breakout")


def promote_bluechip(studies) -> None:
    """Demote a passing Dow book unless it clearly beats dual momentum."""
    for name in DOW_BOOKS:
        _promote_one(studies, name)


def _promote_one(studies, name: str) -> None:
    blue = next((study for study in studies if study.name == name and study.mode == "dow"), None)
    if blue is None:
        return
    blue.passed_gates = bool(blue.selectable)
    dual = next((study for study in studies if study.name == "dual_momentum" and study.mode == "etf"), None)
    dual_sharpe = float(dual.default_oos.get("sharpe") or 0.0) if dual else 0.0
    blue.dual_sharpe = dual_sharpe
    own = float(blue.default_oos.get("sharpe") or 0.0)
    blue.promoted = bool(blue.passed_gates and own >= dual_sharpe + CLEAR_BEAT_SHARPE)
    if blue.passed_gates and not blue.promoted:
        blue.selectable = False
        blue.notes.append(
            f"Passed the stock gates (Sharpe {own:.2f}) but did not beat dual momentum "
            f"(Sharpe {dual_sharpe:.2f}) by {CLEAR_BEAT_SHARPE:.2f}. Optional, not the default book."
        )
    elif blue.promoted:
        blue.notes.append(
            f"Passed the gates and beat dual momentum's Sharpe {dual_sharpe:.2f} "
            f"by at least {CLEAR_BEAT_SHARPE:.2f}."
        )


def write_optional_config(studies, config_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    optional = []
    notes = []
    for name in DOW_BOOKS:
        study = next((item for item in studies if item.name == name and item.mode == "dow"), None)
        if study is None:
            notes.append(f"{name} did not run.")
            continue
        if getattr(study, "promoted", False):
            notes.append(f"{name} was promoted into the default book.")
        elif getattr(study, "passed_gates", False):
            optional.append(name)
            notes.append(
                f"{name} passed and did not beat dual momentum by 0.15 Sharpe. "
                "Add it to strategies.enabled to paper-trade the long stock. "
                "Option orders and short stock are not sent."
            )
        else:
            notes.append(f"{name} did not pass the out-of-sample gates.")
    payload = {
        "optional": optional,
        "expression": "stock",
        "rationale": " ".join(notes) if notes else "No Dow study ran.",
    }
    (config_dir / "optional_strategies.json").write_text(json.dumps(payload, indent=2))


def bluechip_markdown(study, benchmark: dict, missing: list[str]) -> str:
    if study is None:
        return ""
    hold = _hold(study.oos_trades)
    wf_hold = _hold(study.wf_trades)
    is_hold = _hold(study.insample_trades)
    lines = [
        "",
        "## Blue-chip reversal (Dow 30, point in time)",
        "",
        "Universe: historical Dow Jones Industrial Average membership, effective-dated "
        "from the public component changes (Wikipedia, Historical components of the "
        "Dow Jones Industrial Average, summary since 1991). A name is eligible only "
        "while it is in the index, including names that were later removed. "
        "This is not the 2026 survivor list.",
        "",
        "Signal, pre-registered: confirmed 5/5 swing low or a 1.5% tag of the 200-day EMA, "
        "RSI(2) < 10 within three sessions, RSI(14) bullish divergence, then a 10-day EMA "
        "reclaim. Stop is the swing low minus 0.25 ATR. Target is the last confirmed swing "
        "high. Time stop is 15 sessions. Fill is the next open. The grid is six variants "
        "(RSI(14)<30, RSI(5)<15, anchored-VWAP reclaim, trend filter on, divergence off) "
        "and was not a cartesian search. The gate uses the default parameters, not the "
        "best cell.",
        "",
        "Options are a model. Premiums are Black-Scholes with 20-day realized volatility "
        "times 1.15, rate 2%, dividend yield 1.8%, 45 calendar days, long strike near "
        "0.65 delta, short strike near 0.40 delta, half-spread 4% of the mid (8% below "
        "0.50 delta), and the Webull equity-option fee schedule in `options/fees.py`. "
        "There is no historical option chain. Early assignment is not modeled. "
        "A profitable options column does not pass the gate.",
        "",
        "| Book | Window | CAGR | Total return | Win rate | Profit factor | Max DD | Sharpe | Exposure | Trades | Avg hold |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        _row("Stock, default params", "2013-2016 earlier sample", study.insample_metrics, is_hold),
        _row("Stock, default params", "2017-2026 out of sample", study.default_oos, hold),
        _row("Stock, walk-forward", "stitched OOS folds", study.walk_forward, wf_hold),
        _row("Stock, 15 bps slippage", "2017-2026 out of sample", study.stress_metrics, None),
    ]
    labels = [
        ("Long call, IV 1.15x", "2017-2026 out of sample", "call_oos"),
        ("Long call, IV 1.15x", "walk-forward trades", "call_wf"),
        ("Long call, IV 1.15x", "2013-2016 earlier sample", "call_is"),
        ("Bull call spread, IV 1.15x", "2017-2026 out of sample", "spread_oos"),
        ("Bull call spread, IV 1.15x", "walk-forward trades", "spread_wf"),
        ("Bull call spread, IV 1.15x", "2013-2016 earlier sample", "spread_is"),
        ("Long call, IV 1.00x", "2017-2026 sensitivity", "call_iv_1"),
        ("Long call, IV 1.30x", "2017-2026 sensitivity", "call_iv_130"),
        ("Long call, 2x spread", "2017-2026 sensitivity", "call_wide"),
        ("Bull call spread, IV 1.00x", "2017-2026 sensitivity", "spread_iv_1"),
        ("Bull call spread, IV 1.30x", "2017-2026 sensitivity", "spread_iv_130"),
        ("Bull call spread, 2x spread", "2017-2026 sensitivity", "spread_wide"),
    ]
    packs = getattr(study, "options", {}) or {}
    for label, window, key in labels:
        pack = packs.get(key)
        if not pack:
            continue
        lines.append(_row(label, window, pack["metrics"], pack["metrics"].get("avg_hold_sessions")))
    lines.append(_row("SPY buy and hold", "2017-2026", benchmark, None))
    lines += [
        "",
        f"Stock out-of-sample flags: {', '.join(study.flags) or 'none'}.",
        f"Gate result: **{_verdict(study)}**",
        "",
        "Option sizing risks 1.5% of equity as the debit (the middle of the 1–2% request). "
        "The stock book still uses the system's 0.75% stop-distance sizing, five-position "
        "cap, sector cap, and correlation cap. Average hold is sessions in the trade.",
    ]
    if missing:
        lines.append("")
        lines.append(
            "Dow names with no Yahoo history in this run, so those membership days "
            f"are absent: {', '.join(missing)}. "
            "UTX is not in that list because Yahoo has no UTX file and the study "
            "reuses the RTX series for the pre-2020 United Technologies window. "
            "That splice is a data caveat, not a second listing."
        )
    lines.append("")
    return "\n".join(lines)


def _verdict(study) -> str:
    if getattr(study, "promoted", False):
        return "PASSES and beats dual momentum. Added to the default book."
    if getattr(study, "passed_gates", False):
        return (
            "PASSES the stock gates, does not beat dual momentum by 0.15 Sharpe, "
            "and is optional rather than the default."
        )
    return (
        "DOES NOT PASS the out-of-sample gates. Not in the default book and not optional. "
        "Modeled option profits are not a separate pass."
    )


def _hold(trades) -> float | None:
    if trades is None or len(trades) == 0 or "bars_held" not in trades.columns:
        return None
    return float(pd.to_numeric(trades["bars_held"], errors="coerce").mean())


def _row(book: str, window: str, metrics: dict, hold: float | None) -> str:
    pf = metrics.get("profit_factor")
    pf_text = "n/a" if pf is None else f"{float(pf):.2f}"
    hold_text = "n/a" if hold is None else f"{hold:.1f}"
    return (
        f"| {book} | {window} | {float(metrics.get('cagr') or 0):.2%} | "
        f"{float(metrics.get('total_return') or 0):.2%} | {float(metrics.get('win_rate') or 0):.2%} | "
        f"{pf_text} | {float(metrics.get('max_drawdown') or 0):.2%} | "
        f"{float(metrics.get('sharpe') or 0):.2f} | {float(metrics.get('exposure') or 0):.2%} | "
        f"{int(metrics.get('trades') or 0)} | {hold_text} |"
    )


def write_option_html(study, report_dir: Path, disclaimer: str) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    if study.equity is not None and len(study.equity):
        write_html_report(
            report_dir / "bluechip_reversal_dow.html",
            title="Blue-chip reversal, Dow point-in-time, out of sample",
            disclaimer=disclaimer,
            metrics=study.default_oos,
            equity=study.equity,
            notes=[study.citation, *study.notes, "Flags: " + ", ".join(study.flags or ["none"])],
        )
    packs = getattr(study, "options", {}) or {}
    call = packs.get("call_oos")
    if call and call["equity"] is not None and len(call["equity"]):
        write_html_report(
            report_dir / "bluechip_calls.html",
            title="Blue-chip long calls, Black-Scholes estimate, out of sample",
            disclaimer=disclaimer + " Option prices are a model, not prints.",
            metrics=call["metrics"],
            equity=call["equity"],
            notes=["IV = 1.15 x 20-day realized vol. 0.65 delta, 45 DTE. Not a chain."],
        )
