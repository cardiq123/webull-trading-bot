"""Command line: backtest, paper, live, kill, research."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

from webull_bot.config import cost_model_from_config, load_config
from webull_bot.execution.kill import PHRASE, kill
from webull_bot.logging_setup import setup_logging

DISCLAIMER = (
    "This software can lose money. A backtest is not a promise. "
    "Live trading is off unless you set live_trading_enabled and type the confirmation phrase."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="webull-bot", description="Research-driven Webull trading bot")
    sub = parser.add_subparsers(dest="command", required=True)

    backtest = sub.add_parser("backtest", help="Run the event-driven backtest and write a report")
    _add_config(backtest)
    backtest.add_argument("--strategy", action="append", default=[], help="Strategy name. Repeatable. Default: the selected mix.")
    backtest.add_argument("--start", default="2017-01-01")
    backtest.add_argument("--end", default=None)
    backtest.add_argument("--report-dir", default="reports")

    paper = sub.add_parser("paper", help="Paper trade. This is the default execution mode.")
    _add_config(paper)
    paper.add_argument("--strategy", action="append", default=[], help="Strategy name. Repeatable. Default: the selected mix. Fills stock, not option orders.")
    paper.add_argument("--replay", action="store_true", help="Simulate a session on recent historical bars")
    paper.add_argument("--max-cycles", type=int, default=0, help="Stop after this many cycles. Replay defaults to 5 when omitted.")
    paper.add_argument("--poll-seconds", type=int, default=60)

    live = sub.add_parser("live", help="Trade a real Webull account. Refuses to start without two confirmations.")
    _add_config(live)
    live.add_argument("--max-cycles", type=int, default=0)
    live.add_argument("--poll-seconds", type=int, default=60)

    killer = sub.add_parser("kill", help="Cancel open orders and optionally flatten")
    _add_config(killer)
    killer.add_argument("--flatten", action="store_true")
    killer.add_argument("--mode", choices=["paper", "live"], default="paper")

    research = sub.add_parser("research", help="Walk-forward every strategy and rewrite RESULTS.md")
    _add_config(research)
    research.add_argument("--report-dir", default="reports")
    research.add_argument("--end", default=None)

    args = parser.parse_args(argv)
    config = load_config(args.config)
    setup_logging(config.get("logging", "level", default="INFO"), config.get("logging", "dir", default="logs"))
    if args.command == "backtest":
        return _backtest(config, args)
    if args.command == "paper":
        return _paper(config, args)
    if args.command == "live":
        return _live(config, args)
    if args.command == "kill":
        print(kill(config, mode=args.mode, flatten=args.flatten))
        return 0
    if args.command == "research":
        from webull_bot.research import run_research

        run_research(report_dir=args.report_dir, end=args.end)
        return 0
    parser.error(args.command)
    return 2


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="config/default.yaml")


def confirm_live(enabled: bool) -> None:
    if not enabled:
        raise SystemExit(
            "Refusing to start live trading. Set live_trading_enabled: true in the config. "
            "The default is false, and paper is the mode this bot starts in."
        )
    if os.environ.get("WEBULL_LIVE_CONFIRM") == PHRASE:
        return
    if not sys.stdin.isatty():
        raise SystemExit(
            "Live trading from a non-interactive shell requires WEBULL_LIVE_CONFIRM to equal "
            f"exactly: {PHRASE}"
        )
    print(DISCLAIMER)
    typed = input(f"Type exactly: {PHRASE}\n")
    if typed.strip() != PHRASE:
        raise SystemExit("Live trading aborted. The confirmation phrase did not match.")


def load_selection(config) -> tuple[list[str], str]:
    explicit = config.get("strategies", "enabled", default=[]) or []
    if explicit:
        return list(explicit), "Strategies were named in the config."
    path = Path(config.get("strategies", "selection_file", default="config/selected_strategies.json"))
    if not path.exists():
        return [], "No selection file yet. Run: python -m webull_bot research"
    payload = json.loads(path.read_text())
    return list(payload.get("selected") or []), str(payload.get("rationale") or "")


def _backtest(config, args) -> int:
    from webull_bot.backtest.engine import run_backtest
    from webull_bot.backtest.metrics import compute_metrics
    from webull_bot.backtest.report import write_html_report
    from webull_bot.costs import CostModel
    from webull_bot.data.yfinance_provider import YFinanceProvider
    from webull_bot.research import DISCLAIMER as RESEARCH_DISCLAIMER
    from webull_bot.risk.manager import RiskLimits
    from webull_bot.strategies.regime import build_regime
    from webull_bot.universe import STOCK_UNIVERSE, VIX_SYMBOL, all_sectors, research_symbols

    names, rationale = load_selection(config)
    if args.strategy:
        names = list(args.strategy)
    from webull_bot.strategies.registry import strategy_by_name

    if not names:
        print(rationale)
        print("Nothing to backtest. The selected book is cash.")
        return 0
    strategies = [strategy_by_name(name) for name in names]
    end = args.end or pd.Timestamp.utcnow().date().isoformat()
    provider = YFinanceProvider(config.get("data", "cache_dir", default="data/cache"))
    symbols = set(research_symbols())
    for strategy in strategies:
        symbols.update(name for name in _trade_symbols(strategy) if name != "__none__")
    bars = provider.history(sorted(symbols), "2011-01-01", end, "1d")
    if "SPY" not in bars:
        raise SystemExit("SPY history did not download. Check the network and retry.")
    trade_end = min(pd.Timestamp(end), bars["SPY"].index.max())
    scoped = {}
    for symbol, frame in bars.items():
        scoped[symbol] = frame.loc[:trade_end]
    regime = build_regime(scoped, [s for s in STOCK_UNIVERSE if s in scoped])
    params = {}
    for strategy in strategies:
        chosen = dict(strategy.default_params)
        chosen["symbols"] = _trade_symbols(strategy)
        params[strategy.name] = chosen
    limits = _limits(config)
    result = run_backtest(
        scoped,
        strategies,
        regime,
        starting_equity=float(config.get("account", "starting_equity", default=100_000)),
        costs=cost_model_from_config(config),
        limits=limits,
        sectors=all_sectors(),
        account_type=str(config.get("account", "account_type", default="margin")),
        params=params,
        trade_start=pd.Timestamp(args.start),
        trade_end=trade_end,
        flatten_at_end=True,
    )
    metrics = compute_metrics(result, float(config.get("account", "starting_equity", default=100_000)))
    report = Path(args.report_dir) / "backtest.html"
    write_html_report(
        report,
        title="Backtest " + ", ".join(names),
        disclaimer=RESEARCH_DISCLAIMER,
        metrics=metrics,
        equity=result.daily_equity(),
        notes=[rationale, f"Costs: commission {CostModel().commission_per_trade}, see config for fees."],
    )
    # Silence an unused import if VIX is only pulled via research_symbols.
    _ = VIX_SYMBOL
    print(json.dumps({key: metrics[key] for key in ("cagr", "total_return", "sharpe", "max_drawdown", "win_rate", "profit_factor", "trades", "ending_equity")}, default=str, indent=2))
    print(f"Wrote {report}")
    return 0


def _paper(config, args) -> int:
    from webull_bot.broker.paper import PaperBroker
    from webull_bot.data.yfinance_provider import YFinanceProvider
    from webull_bot.execution.session import run_poll_loop, run_replay
    from webull_bot.journal.store import Journal
    from webull_bot.notify.webhook import webhook_url
    from webull_bot.strategies.regime import build_regime
    from webull_bot.strategies.registry import strategy_by_name
    from webull_bot.universe import STOCK_UNIVERSE, research_symbols

    names, rationale = load_selection(config)
    if args.strategy:
        names = list(args.strategy)
    print(DISCLAIMER)
    print(rationale or "No strategy is selected. The session will not open new risk.")
    broker = PaperBroker(
        config.get("broker", "paper_state_db", default="data/paper_state.sqlite"),
        cost_model_from_config(config),
        starting_equity=float(config.get("account", "starting_equity", default=100_000)),
        account_type=str(config.get("account", "account_type", default="margin")),
    )
    broker.connect()
    journal = Journal(config.get("journal", "path", default="data/journal.sqlite"))
    if not names:
        journal.event("paper", "no selected strategies; monitoring only", {})
    strategies = [strategy_by_name(name) for name in names]
    provider = YFinanceProvider(config.get("data", "cache_dir", default="data/cache"))
    symbols = set(research_symbols())
    params = {}
    for strategy in strategies:
        chosen_symbols = _trade_symbols(strategy)
        params[strategy.name] = {"symbols": chosen_symbols}
        symbols.update(name for name in chosen_symbols if name != "__none__")
    symbols = sorted(symbols)
    webhook = webhook_url(config.get("notifications", "webhook_url", default="") or "")
    limits = _limits(config)
    if args.replay:
        bars = provider.history(symbols, "2018-01-01", pd.Timestamp.utcnow().date().isoformat(), "1d")
        regime = build_regime(bars, [s for s in STOCK_UNIVERSE if s in bars])
        cycles = args.max_cycles or 5
        summary = run_replay(
            bars, strategies, regime, broker, journal,
            cycles=cycles, limits=limits, webhook=webhook, params=params,
        )
        print(json.dumps(summary, default=str, indent=2))
        return 0
    run_poll_loop(
        broker=broker,
        journal=journal,
        strategies=strategies,
        data_provider=provider,
        symbols=symbols,
        limits=limits,
        webhook=webhook,
        poll_seconds=args.poll_seconds,
        max_cycles=args.max_cycles or 1,
    )
    return 0


def _live(config, args) -> int:
    from webull_bot.broker.webull import WebullBroker
    from webull_bot.data.webull_provider import WebullDataProvider
    from webull_bot.journal.store import Journal

    confirm_live(config.live_trading_enabled)
    names, rationale = load_selection(config)
    if not names and not config.allow_unproven_strategies:
        raise SystemExit(
            "Refusing to go live with an empty or unproven book. "
            f"{rationale} Set allow_unproven_strategies only if you accept that."
        )
    broker = WebullBroker(environment=os.environ.get("WEBULL_ENV", "production"))
    broker.connect()
    snapshot = broker.snapshot()
    journal = Journal(config.get("journal", "path", default="data/journal.sqlite"))
    journal.event("live_start", "live session starting", {"equity": snapshot.equity, "strategies": names})
    print(f"Connected. Equity {snapshot.equity:,.2f}. Strategies: {', '.join(names) or '(none)'}.")
    print("Orders go to the official Webull API. Use `kill --mode live --flatten` to exit.")
    from webull_bot.data.yfinance_provider import YFinanceProvider
    from webull_bot.execution.live import run_live
    from webull_bot.notify.webhook import webhook_url
    from webull_bot.strategies.registry import strategy_by_name
    from webull_bot.universe import research_symbols

    # Quote source is Yahoo by default because OpenAPI market data needs a
    # separate subscription. That feed is delayed. Order routing is still Webull.
    _ = WebullDataProvider
    strategies = [strategy_by_name(name) for name in names]
    run_live(
        broker=broker,
        data_provider=YFinanceProvider(config.get("data", "cache_dir", default="data/cache")),
        strategies=strategies,
        journal=journal,
        limits=_limits(config),
        symbols=sorted(set(research_symbols())),
        webhook=webhook_url(config.get("notifications", "webhook_url", default="") or ""),
        poll_seconds=args.poll_seconds,
        max_cycles=args.max_cycles or 1,
    )
    return 0


def _trade_symbols(strategy) -> list[str]:
    """Symbols this strategy may trade. An empty list must not mean "every bar"."""
    if strategy.custom_universe:
        names = strategy.universe("dow")
    else:
        names = strategy.universe("etf")
    return list(names) if names else ["__none__"]


def _limits(config):
    from webull_bot.risk.manager import RiskLimits
    from webull_bot.config import PdtSettings, RiskSettings

    risk = RiskSettings.from_config(config)
    pdt = PdtSettings.from_config(config)
    return RiskLimits(
        risk_per_trade=risk.risk_per_trade,
        max_position_pct=risk.max_position_pct,
        max_concurrent_positions=risk.max_concurrent_positions,
        max_sector_pct=risk.max_sector_pct,
        max_correlation=risk.max_correlation,
        correlation_lookback=risk.correlation_lookback,
        daily_max_loss_pct=risk.daily_max_loss_pct,
        max_drawdown_pct=risk.max_drawdown_pct,
        flatten_on_daily_loss=risk.flatten_on_daily_loss,
        flatten_on_max_drawdown=risk.flatten_on_max_drawdown,
        intraday_margin_ratio=risk.intraday_margin_ratio,
        min_margin_equity=risk.min_margin_equity,
        allow_fractional=risk.allow_fractional,
        pdt_mode=pdt.mode,
        enforce_legacy_during_transition=pdt.enforce_legacy_during_transition,
        legacy_equity_threshold=pdt.legacy_equity_threshold,
        legacy_max_day_trades=pdt.legacy_max_day_trades,
        legacy_window_business_days=pdt.legacy_window_business_days,
    )
