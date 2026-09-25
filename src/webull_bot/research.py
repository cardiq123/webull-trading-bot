"""Walk-forward research driver.

The default mix is whatever this module selects. It does not assume a
strategy works because a book said so. Outputs:

* ``RESULTS.md``
* ``reports/research_summary.json``
* ``reports/<strategy>.html``
* ``config/selected_strategies.json``
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from webull_bot.backtest.assessment import (
    fragile_grid,
    is_selectable,
    overfit_flags,
    pick_params,
    profit_factor_value,
)
from webull_bot.backtest.engine import BacktestResult, run_backtest
from webull_bot.backtest.metrics import buy_and_hold_metrics, compute_metrics
from webull_bot.backtest.report import TABLE_HEADER, metrics_markdown_row, write_html_report
from webull_bot.costs import CostModel
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.risk.manager import RiskLimits
from webull_bot.strategies.base import Strategy
from webull_bot.strategies.registry import all_strategies
from webull_bot.strategies.regime import build_regime
from webull_bot.universe import STOCK_UNIVERSE, VIX_SYMBOL, all_sectors, research_symbols

STARTING_EQUITY = 100_000.0
OOS_START = "2017-01-01"
DISCLAIMER = (
    "Past simulated performance is not a prediction of future returns. "
    "No strategy in this system is guaranteed. Costs, slippage, and "
    "missing delistings can erase a paper edge."
)

# Train window, then the contiguous out-of-sample window that follows it.
# The four test windows abut, so they chain into 2017 through the sample end.
FOLDS = [
    ("2013-01-01", "2016-12-31", "2017-01-01", "2018-12-31"),
    ("2015-01-01", "2018-12-31", "2019-01-01", "2020-12-31"),
    ("2017-01-01", "2020-12-31", "2021-01-01", "2022-12-31"),
    ("2019-01-01", "2022-12-31", "2023-01-01", "2026-12-31"),
]


@dataclass
class Study:
    name: str
    mode: str
    citation: str
    default_oos: dict[str, Any]
    walk_forward: dict[str, Any]
    flags: list[str]
    selectable: bool
    train_sharpes: list[float] = field(default_factory=list)
    equity: pd.Series | None = None
    notes: list[str] = field(default_factory=list)
    oos_trades: pd.DataFrame | None = None
    wf_trades: pd.DataFrame | None = None


def run_research(
    *,
    report_dir: str | Path = "reports",
    cache_dir: str = "data/cache",
    config_dir: str | Path = "config",
    end: str | None = None,
) -> list[Study]:
    report_path = Path(report_dir)
    report_path.mkdir(parents=True, exist_ok=True)
    end = end or date.today().isoformat()
    print("Downloading daily bars...")
    provider = YFinanceProvider(cache_dir)
    bars = provider.history(research_symbols(), "2011-01-01", end, "1d")
    missing = [symbol for symbol in research_symbols() if symbol not in bars]
    if "SPY" not in bars or "^VIX" not in bars and VIX_SYMBOL not in bars:
        raise RuntimeError(f"Required series missing. Downloaded {sorted(bars)}. Missing {missing}.")
    if missing:
        print(f"Missing symbols (dropped): {', '.join(missing)}")
    sample_end = min(pd.Timestamp(end), bars["SPY"].index.max())
    limits = RiskLimits()
    costs = CostModel()
    studies: list[Study] = []

    daily_strategies = [
        s for s in all_strategies() if not s.short_sample and not s.custom_universe
    ]
    for strategy in daily_strategies:
        modes = ["etf"] if strategy.name == "dual_momentum" else ["etf", "stock"]
        for mode in modes:
            print(f"Testing {strategy.name} [{mode}]", flush=True)
            try:
                study = _study_daily(
                    strategy,
                    mode,
                    bars,
                    limits,
                    costs,
                    sample_end=sample_end,
                )
            except Exception as exc:
                traceback.print_exc()
                empty = compute_metrics(
                    BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
                    STARTING_EQUITY,
                )
                study = Study(
                    name=strategy.name,
                    mode=mode,
                    citation=strategy.citation,
                    default_oos=empty,
                    walk_forward=empty,
                    flags=["error"],
                    selectable=False,
                    notes=[f"Research run failed: {exc}"],
                )
            studies.append(study)
            if study.equity is not None and len(study.equity):
                write_html_report(
                    report_path / f"{strategy.name}_{mode}.html",
                    title=f"{strategy.name} ({mode}) out-of-sample",
                    disclaimer=DISCLAIMER,
                    metrics=study.default_oos,
                    equity=study.equity,
                    notes=[*study.notes, "Flags: " + ", ".join(study.flags or ["none"])],
                )

    print("Downloading hourly bars for the intraday sample...")
    intraday_notes: list[str] = []
    try:
        hourly_symbols = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMD", "TSLA", "AMZN"]
        hourly = provider.history(hourly_symbols, "2020-01-01", end, "1h")
        daily_for_regime = {key: value for key, value in bars.items() if key in set(research_symbols())}
        for strategy in all_strategies():
            if not strategy.short_sample:
                continue
            for mode in ("etf", "stock"):
                print(f"Testing {strategy.name} [{mode}] on hourly bars", flush=True)
                try:
                    study = _study_intraday(strategy, mode, hourly, daily_for_regime, limits, costs)
                except Exception as exc:
                    traceback.print_exc()
                    empty = compute_metrics(
                        BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
                        STARTING_EQUITY,
                    )
                    study = Study(
                        name=strategy.name,
                        mode=mode,
                        citation=strategy.citation,
                        default_oos=empty,
                        walk_forward=empty,
                        flags=["short_sample", "error"],
                        selectable=False,
                        notes=[f"Hourly test failed: {exc}"],
                    )
                studies.append(study)
                if study.equity is not None and len(study.equity):
                    write_html_report(
                        report_path / f"{strategy.name}_{mode}.html",
                        title=f"{strategy.name} ({mode}) hourly sample",
                        disclaimer=DISCLAIMER,
                        metrics=study.default_oos,
                        equity=study.daily_equity_or_raw(),
                        notes=[*study.notes],
                    )
    except Exception as exc:
        intraday_notes.append(f"Intraday download or test failed: {exc}")
        print(intraday_notes[-1])

    print("Downloading Dow point-in-time history...")
    dow_missing: list[str] = []
    try:
        from webull_bot.research_bluechip import ensure_dow_history, run_bluechip_stock

        dow_missing = ensure_dow_history(provider, bars, end)
        if dow_missing:
            print(f"Dow names with no Yahoo history: {', '.join(dow_missing)}")
        print("Testing bluechip_reversal [dow]", flush=True)
        studies.append(run_bluechip_stock(bars, limits, costs, sample_end))
    except Exception as exc:
        traceback.print_exc()
        empty = compute_metrics(
            BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
            STARTING_EQUITY,
        )
        studies.append(
            Study(
                name="bluechip_reversal",
                mode="dow",
                citation="Point-in-time Dow reversal.",
                default_oos=empty,
                walk_forward=empty,
                flags=["error"],
                selectable=False,
                notes=[f"Research run failed: {exc}"],
            )
        )

    # Cost stress for anything still selectable. The Dow study records its
    # own 15 bps result inside run_bluechip_stock, including the flag.
    stressed: list[str] = []
    harsh = CostModel(slippage_bps=15.0, half_spread_bps=2.0)
    for study in studies:
        if not study.selectable or getattr(study, "stress_metrics", None) is not None:
            continue
        strategy = _by_name(study.name)
        print(f"Cost stress {study.name}")
        result = _execute(
            strategy,
            study.mode,
            bars,
            limits,
            harsh,
            trade_start=pd.Timestamp(OOS_START),
            trade_end=sample_end,
            params=dict(strategy.default_params),
        )
        metrics = compute_metrics(result, STARTING_EQUITY)
        if profit_factor_value(metrics) < 1.0 or float(metrics.get("sharpe") or 0) < 0:
            study.flags.append("cost_fragile")
            study.selectable = False
            study.notes.append(
                f"At 15 bps slippage and 2 bps half-spread, OOS profit factor was "
                f"{profit_factor_value(metrics):.2f} and Sharpe was {metrics.get('sharpe'):.2f}."
            )
            stressed.append(study.name)
        else:
            study.notes.append(
                f"Still profitable at 15 bps slippage (Sharpe {metrics.get('sharpe'):.2f}, "
                f"profit factor {profit_factor_value(metrics):.2f})."
            )

    for study in studies:
        if "slippage" not in " ".join(study.notes):
            continue
        if study.equity is None or len(study.equity) == 0:
            continue
        write_html_report(
            report_path / f"{study.name}_{study.mode}.html",
            title=f"{study.name} ({study.mode}) out-of-sample",
            disclaimer=DISCLAIMER,
            metrics=study.default_oos,
            equity=study.equity,
            notes=[*study.notes, "Flags: " + ", ".join(study.flags or ["none"])],
        )

    from webull_bot.research_bluechip import (
        bluechip_markdown,
        price_options,
        promote_bluechip,
        write_optional_config,
        write_option_html,
    )

    promote_bluechip(studies)
    blue = next((study for study in studies if study.name == "bluechip_reversal"), None)
    if blue is not None and blue.oos_trades is not None and getattr(blue, "insample_trades", None) is not None:
        print("Pricing the Black-Scholes options overlay (estimate, not a chain)...")
        try:
            price_options(blue, bars, sample_end)
            write_option_html(blue, report_path, DISCLAIMER)
        except Exception as exc:
            traceback.print_exc()
            blue.notes.append(f"Options overlay failed: {exc}")
    write_optional_config(studies, Path(config_dir))

    selected = [study for study in studies if study.selectable]
    # Prefer a diversified mix: at most one of each family.
    selected = _diversify(selected)
    portfolio_metrics: dict[str, Any] | None = None
    portfolio_equity: pd.Series | None = None
    if selected:
        print("Portfolio backtest: " + ", ".join(study.name for study in selected))
        strategies = [_by_name(study.name) for study in selected]
        result = _execute_many(
            strategies,
            "etf",
            bars,
            limits,
            costs,
            trade_start=pd.Timestamp(OOS_START),
            trade_end=sample_end,
            modes={study.name: study.mode for study in selected},
        )
        portfolio_metrics = compute_metrics(result, STARTING_EQUITY)
        portfolio_equity = result.daily_equity()
        write_html_report(
            report_path / "portfolio.html",
            title="Selected portfolio, out of sample",
            disclaimer=DISCLAIMER,
            metrics=portfolio_metrics,
            equity=portfolio_equity,
            notes=["Strategies: " + ", ".join(study.name for study in selected)],
        )
    else:
        write_html_report(
            report_path / "portfolio.html",
            title="Selected portfolio",
            disclaimer=DISCLAIMER,
            metrics=compute_metrics(
                BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
                STARTING_EQUITY,
            ),
            equity=pd.Series(dtype=float),
            notes=["No strategy cleared the out-of-sample gates. The default is cash."],
        )

    benchmark = _benchmark(bars, sample_end, costs)
    extra = ""
    if blue is not None and getattr(blue, "insample_metrics", None) is not None:
        extra = bluechip_markdown(blue, benchmark, dow_missing)
    _write_results(
        report_path,
        studies,
        selected,
        portfolio_metrics,
        benchmark,
        missing,
        intraday_notes,
        sample_end,
        extra=extra,
    )
    _write_selection(Path(config_dir), selected, portfolio_metrics, sample_end)
    summary = {
        "as_of": date.today().isoformat(),
        "sample_end": str(pd.Timestamp(sample_end).date()),
        "selected": [study.name for study in selected],
        "studies": [
            {
                "name": study.name,
                "mode": study.mode,
                "selectable": study.selectable,
                "flags": study.flags,
                "default_oos": study.default_oos,
                "walk_forward": study.walk_forward,
            }
            for study in studies
        ],
        "portfolio": portfolio_metrics,
        "benchmark_spy": benchmark,
    }
    (report_path / "research_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("Wrote RESULTS.md and reports/research_summary.json")
    return studies


def _study_daily(strategy: Strategy, mode: str, bars, limits, costs, sample_end) -> Study:
    grid = strategy.param_grid()
    train_sharpes: list[float] = []
    fold_returns: list[pd.Series] = []
    fold_trades: list[pd.DataFrame] = []
    fold_exposure: list[pd.Series] = []
    for train_start, train_end, test_start, test_end in FOLDS:
        test_end_ts = min(pd.Timestamp(test_end), pd.Timestamp(sample_end))
        if pd.Timestamp(test_start) >= test_end_ts:
            continue
        rows = []
        for params in grid:
            result = _execute(
                strategy, mode, bars, limits, costs,
                trade_start=pd.Timestamp(train_start),
                trade_end=pd.Timestamp(train_end),
                params=params,
            )
            metrics = compute_metrics(result, STARTING_EQUITY)
            rows.append({"params": params, **metrics})
        train_sharpes.extend(float(row["sharpe"] or 0.0) for row in rows)
        chosen = pick_params(rows, strategy.default_params)
        test = _execute(
            strategy, mode, bars, limits, costs,
            trade_start=pd.Timestamp(test_start),
            trade_end=test_end_ts,
            params=chosen,
        )
        daily = test.daily_equity()
        if len(daily):
            base = pd.Series([STARTING_EQUITY], index=[daily.index[0] - pd.Timedelta(days=1)])
            fold_returns.append(pd.concat([base, daily]).pct_change().dropna())
        if test.trades is not None and len(test.trades):
            fold_trades.append(test.trades)
        if len(test.exposure):
            fold_exposure.append(test.exposure)
    walk = _metrics_from_returns(fold_returns, fold_trades, fold_exposure)
    default = _execute(
        strategy, mode, bars, limits, costs,
        trade_start=pd.Timestamp(OOS_START),
        trade_end=pd.Timestamp(sample_end),
        params=dict(strategy.default_params),
    )
    default_metrics = compute_metrics(default, STARTING_EQUITY)
    flags = overfit_flags(
        default_oos=default_metrics,
        walk_forward=walk,
        train_sharpes=train_sharpes,
        survivorship_sensitive=(mode == "stock"),
        short_sample=False,
    )
    if mode == "stock":
        flags.append("diagnostic_only")
    # Point-in-time Dow membership is dated, so it can clear the same numeric
    # gates as an ETF book. The 2026 survivor stock list cannot.
    selectable = mode in {"etf", "dow"} and is_selectable(flags, default_metrics)
    notes = [
        strategy.citation,
        "Out-of-sample window starts 2017-01-01 and uses default published parameters.",
        "Walk-forward parameters were chosen on each training window only.",
    ]
    if fragile_grid(train_sharpes):
        notes.append("The in-sample parameter grid did not agree with itself.")
    study = Study(
        name=strategy.name,
        mode=mode,
        citation=strategy.citation,
        default_oos=default_metrics,
        walk_forward=walk,
        flags=flags,
        selectable=selectable,
        train_sharpes=train_sharpes,
        equity=default.daily_equity(),
        notes=notes,
        oos_trades=default.trades,
        wf_trades=pd.concat(fold_trades) if fold_trades else pd.DataFrame(),
    )
    return study


def _study_intraday(strategy, mode, hourly, daily_bars, limits, costs) -> Study:
    symbols = strategy.universe(mode)
    present = {symbol: frame for symbol, frame in hourly.items() if symbol in symbols and len(frame) > 50}
    if "SPY" in hourly and len(hourly["SPY"]) > 50:
        present.setdefault("SPY", hourly["SPY"])
    if len([symbol for symbol in present if symbol in symbols]) < 1:
        empty = compute_metrics(
            BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
            STARTING_EQUITY,
        )
        return Study(
            name=strategy.name,
            mode=mode,
            citation=strategy.citation,
            default_oos=empty,
            walk_forward=empty,
            flags=["short_sample", "no_data"],
            selectable=False,
            notes=["Hourly history was not available for this universe."],
        )
    # Regime comes from the daily sample, shifted inside the strategy.
    breadth = [symbol for symbol in STOCK_UNIVERSE if symbol in daily_bars]
    regime = build_regime(daily_bars, breadth)
    # Split the hourly clock in half. The second half is the only out-of-sample
    # view this short file can support, and it is still too short to select.
    clock = present[next(iter(present))].index
    split = clock[len(clock) // 2]
    params = dict(strategy.default_params)
    params["symbols"] = [symbol for symbol in symbols if symbol in present]
    # Intraday bars only. SPY is included so every symbol shares one clock,
    # and ``symbols`` above keeps it out of a stock-mode book.
    result = run_backtest(
        present,
        [strategy],
        regime,
        starting_equity=STARTING_EQUITY,
        costs=costs,
        limits=limits,
        sectors=all_sectors(),
        params={strategy.name: params},
        trade_start=pd.Timestamp(split),
        flatten_at_end=True,
    )
    metrics = compute_metrics(result, STARTING_EQUITY)
    flags = ["short_sample"]
    if mode == "stock":
        flags.append("survivorship_bias")
    if metrics["trades"] < 20:
        flags.append("insufficient_trades")
    return Study(
        name=strategy.name,
        mode=mode,
        citation=strategy.citation,
        default_oos=metrics,
        walk_forward=metrics,
        flags=flags,
        selectable=False,
        equity=result.equity,
        notes=[
            "Hourly Yahoo history is only about two years. This is reported, not selected.",
            f"Out-of-sample half starts {pd.Timestamp(split)}.",
        ],
    )


def _execute(strategy, mode, bars, limits, costs, trade_start, trade_end, params) -> BacktestResult:
    return _execute_many(
        [strategy], mode, bars, limits, costs, trade_start, trade_end, {strategy.name: params}
    )


def _execute_many(
    strategies, mode, bars, limits, costs, trade_start, trade_end, params_map=None, modes=None
) -> BacktestResult:
    modes = modes or {}

    def _mode(strategy) -> str:
        if strategy.name in modes:
            return modes[strategy.name]
        if strategy.name == "dual_momentum":
            return "etf"
        return mode

    symbols: list[str] = []
    for strategy in strategies:
        symbols.extend(strategy.universe(_mode(strategy)))
    params_map = dict(params_map or {})
    for strategy in strategies:
        params_map.setdefault(strategy.name, dict(strategy.default_params))
        params_map[strategy.name] = dict(params_map[strategy.name])
        params_map[strategy.name]["symbols"] = strategy.universe(_mode(strategy))
    scoped = _scope(bars, symbols, trade_end)
    breadth = [symbol for symbol in STOCK_UNIVERSE if symbol in scoped]
    regime = build_regime(scoped, breadth)
    return run_backtest(
        scoped,
        strategies,
        regime,
        starting_equity=STARTING_EQUITY,
        costs=costs,
        limits=limits,
        sectors=all_sectors(),
        params=params_map,
        trade_start=trade_start,
        trade_end=trade_end,
        flatten_at_end=True,
    )


def _scope(bars, symbols, trade_end) -> dict[str, pd.DataFrame]:
    needed = set(symbols) | {"SPY", "QQQ", VIX_SYMBOL, "BIL"}
    needed.update(STOCK_UNIVERSE)
    end = pd.Timestamp(trade_end)
    scoped = {}
    # Set iteration order changes with PYTHONHASHSEED and would change which
    # signal is filled first when several names fire on the same bar.
    for symbol in sorted(needed):
        frame = bars.get(symbol)
        if frame is None or frame.empty:
            continue
        scoped[symbol] = frame.loc[:end]
    return scoped


def _metrics_from_returns(
    fold_returns: list[pd.Series],
    fold_trades: list[pd.DataFrame],
    fold_exposure: list[pd.Series] | None = None,
) -> dict[str, Any]:
    if not fold_returns:
        return compute_metrics(
            BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
            STARTING_EQUITY,
        )
    stitched = pd.concat(fold_returns)
    equity = (1.0 + stitched).cumprod() * STARTING_EQUITY
    trades = pd.concat(fold_trades) if fold_trades else pd.DataFrame()
    if fold_exposure:
        exposure = pd.concat(fold_exposure)
    else:
        exposure = pd.Series(0.0, index=equity.index)
    result = BacktestResult(equity=equity, exposure=exposure, trades=trades, ending_equity=float(equity.iloc[-1]))
    return compute_metrics(result, STARTING_EQUITY)


def _benchmark(bars, sample_end, costs: CostModel) -> dict[str, Any]:
    spy = bars["SPY"]
    return buy_and_hold_metrics(
        spy["close"],
        spy["open"],
        starting_equity=STARTING_EQUITY,
        trade_start=pd.Timestamp(OOS_START),
        trade_end=pd.Timestamp(sample_end),
        slippage_bps=costs.slippage_bps,
    )


def _diversify(studies: list[Study]) -> list[Study]:
    """Keep the best Sharpe name in each family so the book is not five copies of one idea."""
    families = {
        "mean_reversion": {"connors_rsi2", "eod_mean_reversion"},
        "trend": {"ema_pullback", "vcp_breakout"},
        "rotation": {"dual_momentum", "rs_rotation"},
        "day": {"gap_and_go", "opening_range_breakout", "vwap_pullback"},
    }
    chosen: list[Study] = []
    used: set[str] = set()
    ranked = sorted(studies, key=lambda study: float(study.default_oos.get("sharpe") or 0), reverse=True)
    for study in ranked:
        family = next((name for name, members in families.items() if study.name in members), study.name)
        if family in used:
            study.selectable = False
            study.notes.append(f"Passed on its own, but {family} is already represented by a higher-Sharpe strategy.")
            continue
        used.add(family)
        chosen.append(study)
    return chosen


def _by_name(name: str) -> Strategy:
    for strategy in all_strategies():
        if strategy.name == name:
            return strategy
    raise KeyError(name)


def _write_selection(config_dir: Path, selected: list[Study], portfolio: dict[str, Any] | None, sample_end) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    if selected:
        rationale = (
            "Selected because default parameters were profitable on the 2017-onward "
            "out-of-sample window, walk-forward parameter choices did not flip the sign, "
        "the parameter grid was not fragile, the test was on ETFs or point-in-time "
        "Dow membership rather than a survivorship-biased stock list, and a higher "
        "slippage assumption did not "
            "erase the profit factor. "
            + ", ".join(
                f"{study.name} OOS Sharpe {study.default_oos.get('sharpe'):.2f}, "
                f"CAGR {study.default_oos.get('cagr'):.2%}, "
                f"max DD {study.default_oos.get('max_drawdown'):.2%}, "
                f"trades {study.default_oos.get('trades')}"
                for study in selected
            )
        )
    else:
        rationale = (
            "No strategy cleared the out-of-sample gates (default-parameter profit factor "
            "at least 1.10, Sharpe at least 0.40, at least 20 trades, drawdown better than "
            "-30%, stable parameter grid, ETF universe, and survival at wider slippage). "
            "The default book is cash. Paper mode will not open strategy trades until a "
            "later research run selects one. Live mode refuses unless allow_unproven_strategies is set."
        )
    payload = {
        "as_of": date.today().isoformat(),
        "sample_end": str(pd.Timestamp(sample_end).date()),
        "selected": [study.name for study in selected],
        "modes": {study.name: study.mode for study in selected},
        "rationale": rationale,
        "portfolio": portfolio,
    }
    (config_dir / "selected_strategies.json").write_text(json.dumps(payload, indent=2, default=str))


def _write_results(
    report_dir, studies, selected, portfolio, benchmark, missing, intraday_notes, sample_end, extra: str = ""
) -> None:
    lines = [
        "# Research results",
        "",
        DISCLAIMER,
        "",
        f"Sample: daily bars from 2011 (indicators) with the scored out-of-sample window "
        f"**{OOS_START}** through **{pd.Timestamp(sample_end).date()}**. "
        "Starting equity $100,000. Webull commission $0. SEC Section 31 fee "
        "$20.60 per million dollars sold (the rate effective April 4, 2026, applied "
        "to the whole sample so earlier zero-fee years do not flatter results). "
        "FINRA TAF $0.000195 per share sold, capped at $9.79 (the 2026 statutory rate; "
        "the late-2026 TAF holiday is ignored). Slippage 5 bps and half-spread 1 bp "
        "per side. Position size risks 0.75% of equity per trade, capped at 20% of equity, "
        "with a 2% daily-loss flatten and a sticky 15% drawdown halt.",
        "",
        "Walk-forward folds, each trained only on the window before it:",
        "",
        "| Train | Test |",
        "|---|---|",
    ]
    for train_start, train_end, test_start, test_end in FOLDS:
        lines.append(f"| {train_start} to {train_end} | {test_start} to {test_end} |")
    lines += [
        "",
        "A strategy is marked as showing an out-of-sample edge only if the **default** "
        "parameters (not a mined neighbor) clear profit factor 1.10, Sharpe 0.40, "
        "20 trades, and a drawdown no worse than -30% on 2017-onward data; the "
        "in-sample grid is not fragile; walk-forward choices do not flip the sign; "
        "the test universe is ETFs or point-in-time Dow membership; and the result "
        "survives 15 bps of slippage. A passing Dow book joins the default account "
        "only when its out-of-sample Sharpe beats dual momentum by at least 0.15. "
        "Otherwise it stays optional. Stock-only runs on the fixed 2026 survivor "
        "list are diagnostics and cannot be the default book. Hourly tests use the "
        "free Yahoo limit of roughly two years and are never treated as a durable edge.",
        "",
        "## Default-parameter out-of-sample results",
        "",
        TABLE_HEADER,
    ]
    for study in studies:
        label = f"{study.name} ({study.mode})"
        lines.append(metrics_markdown_row(label, study.default_oos, study.flags))
    lines += [
        "",
        "## Walk-forward (parameters chosen on each training window)",
        "",
        TABLE_HEADER,
    ]
    for study in studies:
        if study.short_sample_flag():
            continue
        lines.append(metrics_markdown_row(f"{study.name} ({study.mode})", study.walk_forward, []))
    lines += [
        "",
        "## Buy and hold SPY, same out-of-sample window",
        "",
        TABLE_HEADER,
        metrics_markdown_row("SPY buy and hold", benchmark, ["benchmark"]),
        "",
        "## What showed an edge",
        "",
    ]
    if selected:
        lines.append(
            "The default book is **" + ", ".join(study.name for study in selected) + "**."
        )
        for study in selected:
            m = study.default_oos
            lines.append(
                f"- **{study.name}**: OOS CAGR {m['cagr']:.2%}, total return {m['total_return']:.2%}, "
                f"win rate {m['win_rate']:.2%}, average win ${m['avg_win']:.2f}, average loss ${m['avg_loss']:.2f}, "
                f"profit factor {float(m['profit_factor']):.2f}, expectancy ${m['expectancy']:.2f}, "
                f"max drawdown {m['max_drawdown']:.2%}, Sharpe {m['sharpe']:.2f}, Sortino {m['sortino']:.2f}, "
                f"exposure {m['exposure']:.2%}, trades {m['trades']}."
            )
            lines.append(f"  Source idea: {study.citation}")
            for note in study.notes:
                if "slippage" in note:
                    lines.append(f"  {note}")
        if portfolio and benchmark:
            lines.append("")
            lines.append(
                f"The selected account's out-of-sample CAGR was {portfolio['cagr']:.2%} "
                f"with Sharpe {portfolio['sharpe']:.2f}, max drawdown {portfolio['max_drawdown']:.2%}, "
                f"and average exposure {portfolio['exposure']:.2%}. Buy-and-hold SPY over the same "
                f"window was CAGR {benchmark['cagr']:.2%}, Sharpe {benchmark['sharpe']:.2f}, "
                f"max drawdown {benchmark['max_drawdown']:.2%}. "
                "Fixed-fractional sizing risks 0.75% of equity divided by the stop distance, "
                "then caps the position at 20% of equity. A wide trail therefore keeps most "
                "of the account in cash earning zero in this test. Sharpe is the risk-adjusted "
                "result of that mostly-cash book. Clearing the gates is not the same thing as "
                "beating buy-and-hold."
            )
    else:
        lines.append(
            "None. Every tested rule failed at least one gate. The honest default is to "
            "hold cash and keep paper-trading the research loop. See the flags column. "
            "Sharpe decay, a profit factor under 1, a fragile parameter grid, too few "
            "trades, survivorship, or a two-year hourly sample are all failures."
        )
    lines += ["", "## What did not", ""]
    for study in studies:
        if study.selectable and study in selected:
            continue
        if any(study.name == kept.name and study.mode == kept.mode for kept in selected):
            continue
        profit_factor = study.default_oos.get("profit_factor")
        profit_factor_text = "n/a" if profit_factor is None else f"{float(profit_factor):.2f}"
        if (
            study.name == "bluechip_reversal"
            and getattr(study, "passed_gates", False)
            and not getattr(study, "promoted", False)
        ):
            reason = (
                "passed the stock gates but did not beat dual momentum by 0.15 Sharpe, "
                "so it is optional rather than the default"
            )
        else:
            reason = ", ".join(study.flags) or "passed the numeric gates but lost the family slot to a higher-Sharpe strategy"
        lines.append(
            f"- **{study.name} ({study.mode})**: {reason}. "
            f"OOS Sharpe {study.default_oos.get('sharpe'):.2f}, "
            f"profit factor {profit_factor_text}, "
            f"trades {study.default_oos.get('trades')}, "
            f"max drawdown {study.default_oos.get('max_drawdown'):.2%}."
        )
    if portfolio:
        lines += [
            "",
            "## Combined portfolio",
            "",
            TABLE_HEADER,
            metrics_markdown_row("portfolio", portfolio, []),
            "",
            "The portfolio shares one account, so correlation and sector caps can reject "
            "a second signal the standalone test would have taken. That is intentional.",
        ]
    lines += [
        "",
        "## Data limits",
        "",
        "- Yahoo Finance daily bars, split- and dividend-adjusted. Not the consolidated tape.",
        "- The stock universe is a 2026 survivor list. Edges that appear only there are biased upward.",
        "- ETF results are the evidence used for selection. They still omit dead funds.",
        "- Free intraday history is short: about 7 days of 1-minute bars, about 60 days of 5- and 15-minute bars, about 730 days of hourly bars.",
        "- VIX and breadth are computed from this same file. Breadth is the fraction of the survivor stock list above its 50-day average, which overstates historical breadth.",
    ]
    if missing:
        lines.append(f"- Symbols that failed to download: {', '.join(missing)}.")
    lines.extend(f"- {note}" for note in intraday_notes)
    if extra:
        lines.append(extra.rstrip("\n"))
    lines.append("")
    # RESULTS.md lives at the repo root; the function is also given the report dir.
    Path("RESULTS.md").write_text("\n".join(lines))


def _patch_study_helpers() -> None:
    return None


# Small helpers used by the markdown writer. Defined on the class via monkeypatch
# below so the dataclass stays declarative.


def _short_sample_flag(self: Study) -> bool:
    return "short_sample" in self.flags


def _daily_equity_or_raw(self: Study) -> pd.Series:
    if self.equity is None:
        return pd.Series(dtype=float)
    sessions = []
    for ts in self.equity.index:
        stamp = pd.Timestamp(ts)
        if stamp.tzinfo is not None:
            stamp = stamp.tz_convert("America/New_York")
        sessions.append(stamp.date())
    grouped = self.equity.groupby(sessions).last()
    grouped.index = pd.to_datetime(list(grouped.index))
    return grouped


Study.short_sample_flag = _short_sample_flag  # type: ignore[attr-defined]
Study.daily_equity_or_raw = _daily_equity_or_raw  # type: ignore[attr-defined]
