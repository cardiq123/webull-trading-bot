"""Command line: backtest, paper, live, kill, research."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from webull_bot.config import cost_model_from_config, load_config
from webull_bot.execution.kill import PHRASE, kill
from webull_bot.logging_setup import setup_logging

DISCLAIMER = (
    "This software can lose money. A backtest is not a promise. "
    "Live trading is off unless you set live_trading_enabled and type the confirmation phrase."
)


def build_parser() -> argparse.ArgumentParser:
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
    paper.add_argument(
        "--broker",
        choices=["local", "webull-sandbox"],
        default="local",
        help="local fills in this process. webull-sandbox sends orders only to *.sandbox.webull.com.",
    )
    paper.add_argument(
        "--dry-run",
        action="store_true",
        help="With --broker webull-sandbox, build orders and do not send them.",
    )

    live = sub.add_parser("live", help="Trade a real Webull account. Refuses to start without two confirmations.")
    _add_config(live)
    live.add_argument("--max-cycles", type=int, default=0)
    live.add_argument("--poll-seconds", type=int, default=60)

    killer = sub.add_parser("kill", help="Cancel open orders and optionally flatten")
    _add_config(killer)
    killer.add_argument("--flatten", action="store_true")
    killer.add_argument("--mode", choices=["paper", "live", "sandbox"], default="paper")

    check = sub.add_parser("check", help="Read-only account, balance, position, order, and SPY check. Sends no orders.")
    _add_config(check)
    check.add_argument("--env", required=True, choices=["sandbox", "production"], help="sandbox or production. There is no default.")

    research = sub.add_parser("research", help="Walk-forward every strategy and rewrite RESULTS.md")
    _add_config(research)
    research.add_argument("--report-dir", default="reports")
    research.add_argument("--end", default=None)

    paper_sim = sub.add_parser(
        "paper-sim",
        help="Replay every implemented strategy through the local paper broker. Does not call Webull.",
    )
    _add_config(paper_sim)
    paper_sim.add_argument("--sessions", type=int, default=45, help="Trading sessions at the end of the sample. Default 45.")
    paper_sim.add_argument("--report-dir", default="reports")

    forward = sub.add_parser(
        "forward-test",
        help="One sandbox cycle. Pass chop_breakout_60m, or one or both VWAP books. Live trading stays off. --dry-run does not connect.",
    )
    _add_config(forward)
    forward.add_argument(
        "strategy",
        nargs="+",
        choices=["chop_breakout_60m", "vwap_band_15m", "vwap_band_15m_qqq"],
    )
    forward.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the orders and do not connect to Webull or write the journal.",
    )
    forward.add_argument(
        "--now",
        default=None,
        help="ISO time in America/New_York, for a scheduled slot. Default: the clock now.",
    )

    forward_report = sub.add_parser(
        "forward-report",
        help="Print a sandbox forward-test journal. chop_breakout_60m also prints SPY and the random shadow.",
    )
    _add_config(forward_report)
    forward_report.add_argument(
        "strategy", choices=["chop_breakout_60m", "vwap_band_15m", "vwap_band_15m_qqq"]
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
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
    if args.command == "paper-sim":
        from webull_bot.paper_study import run as run_paper_sim

        run_paper_sim(report_dir=args.report_dir, sessions=args.sessions, config_path=args.config)
        return 0
    if args.command == "check":
        return _check(config, args)
    if args.command == "forward-test":
        return _forward_test(config, args)
    if args.command == "forward-report":
        return _forward_report(config, args)
    parser.error(args.command)
    return 2


FORWARD_ONLY = {"chop_breakout_60m", "vwap_band_15m", "vwap_band_15m_qqq"}


def refuse_if_forward_only(names: list[str]) -> None:
    """The live and ordinary paper paths never trade the sandbox forward test.

    ``allow_unproven_strategies`` does not override this.
    """
    hit = [name for name in names if name in FORWARD_ONLY]
    if not hit:
        return
    if hit == ["chop_breakout_60m"]:
        raise SystemExit(
            "Refusing to run chop_breakout_60m on the paper or live book. "
            "It is a sandbox forward test only. allow_unproven_strategies does not enable it. "
            "Live trading stays off. "
            "Use: python -m webull_bot forward-test chop_breakout_60m"
        )
    shown = ", ".join(hit)
    raise SystemExit(
        f"Refusing to run {shown} on the paper or live book. "
        "It is a sandbox forward test only. allow_unproven_strategies does not enable it. "
        "Live trading stays off. "
        f"Use: python -m webull_bot forward-test {' '.join(hit)}"
    )


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="config/default.yaml")


def resolve_live_environment() -> str:
    """Production is never implied. ``live`` starts only with an explicit value."""
    raw = os.environ.get("WEBULL_ENV")
    if raw is None or not str(raw).strip():
        raise SystemExit(
            "Refusing to start live trading without WEBULL_ENV. "
            "Production is not the default. Set WEBULL_ENV=production explicitly, "
            "or use `paper --broker webull-sandbox` for the paper sandbox."
        )
    env = str(raw).strip().lower()
    if env not in {"production", "prod", "live"}:
        raise SystemExit(
            f"WEBULL_ENV={raw} is not production. "
            "Live orders are sent only when WEBULL_ENV=production. "
            "Use `paper --broker webull-sandbox` for the paper sandbox."
        )
    return "production"


def format_check_report(
    *,
    environment: str,
    accounts: list,
    snapshot,
    quote: dict,
    bars: list,
    secrets: list[str],
) -> str:
    """JSON for the read-only check, with app key, secret, and token redacted."""
    from webull_bot.logging_setup import redact_text

    body = {
        "environment": environment,
        "accounts": accounts,
        "equity": snapshot.equity,
        "cash": snapshot.cash,
        "buying_power": snapshot.buying_power,
        "account_type": snapshot.account_type,
        "positions": [
            {"symbol": pos.symbol, "quantity": pos.quantity, "avg_price": pos.avg_price}
            for pos in snapshot.positions
        ],
        "open_orders": [
            {
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "side": order.side.value,
                "quantity": order.quantity,
                "order_type": order.order_type.value,
            }
            for order in snapshot.open_orders
        ],
        "spy_quote": quote,
        "spy_bars": bars,
    }
    return redact_text(json.dumps(body, default=str, indent=2), secrets)


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
    if getattr(args, "broker", "local") == "webull-sandbox":
        return _sandbox_paper(config, args)
    if getattr(args, "dry_run", False):
        raise SystemExit(
            "--dry-run is only for --broker webull-sandbox. "
            "Local paper fills inside this process. Omit --dry-run, or pass --broker webull-sandbox."
        )
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
    refuse_if_forward_only(names)
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


def _sandbox_paper(config, args) -> int:
    """Orders go to the Webull paper sandbox only. No live flag and no phrase."""
    from webull_bot.broker.webull import WebullBroker, assert_sandbox_hosts
    from webull_bot.data.yfinance_provider import YFinanceProvider
    from webull_bot.execution.live import run_sandbox
    from webull_bot.journal.store import Journal
    from webull_bot.notify.webhook import webhook_url
    from webull_bot.strategies.registry import strategy_by_name
    from webull_bot.universe import research_symbols

    if args.replay:
        raise SystemExit(
            "Replay stays on the local paper broker. "
            "Omit --replay, or omit --broker webull-sandbox."
        )
    names, rationale = load_selection(config)
    if args.strategy:
        names = list(args.strategy)
    refuse_if_forward_only(names)
    print(DISCLAIMER)
    print(rationale or "No strategy is selected. The session will not open new risk.")
    print("Sandbox paper sends orders only to *.sandbox.webull.com.")
    print("live_trading_enabled and the live confirmation phrase are not used.")
    if args.dry_run:
        print("Dry run: orders are built and not sent.")
    broker = WebullBroker(environment="sandbox")
    broker.sandbox_only = True
    broker.connect()
    assert_sandbox_hosts(broker.hosts)
    strategies = [strategy_by_name(name) for name in names]
    symbols = set(research_symbols())
    for strategy in strategies:
        symbols.update(name for name in _trade_symbols(strategy) if name != "__none__")
    journal = Journal(config.get("journal", "path", default="data/journal.sqlite"))
    journal.event(
        "sandbox_start",
        "sandbox paper session",
        {"dry_run": bool(args.dry_run), "strategies": names, "hosts": list(broker.hosts)},
    )
    run_sandbox(
        broker=broker,
        data_provider=YFinanceProvider(config.get("data", "cache_dir", default="data/cache")),
        strategies=strategies,
        journal=journal,
        limits=_limits(config),
        symbols=sorted(symbols),
        webhook=webhook_url(config.get("notifications", "webhook_url", default="") or ""),
        poll_seconds=args.poll_seconds,
        max_cycles=args.max_cycles or 1,
        dry_run=bool(args.dry_run),
    )
    return 0


def _check(config, args) -> int:
    """Read accounts, balances, positions, open orders, and a SPY quote and bars."""
    from webull_bot.broker.webull import WebullBroker
    from webull_bot.data.webull_provider import WebullDataProvider

    environment = args.env
    broker = WebullBroker(environment=environment)
    if environment == "sandbox":
        broker.sandbox_only = True
    broker.connect()
    accounts = broker.list_accounts()
    snapshot = broker.snapshot()
    provider = WebullDataProvider(broker)
    quote = provider.quote("SPY")
    end = pd.Timestamp.utcnow().date()
    start = end - pd.Timedelta(days=30)
    history = provider.history(["SPY"], start.isoformat(), end.isoformat(), "1d")
    bars = []
    frame = history.get("SPY")
    if frame is not None and not frame.empty:
        tail = frame.tail(5)
        for ts, row in tail.iterrows():
            bars.append(
                {
                    "time": pd.Timestamp(ts).isoformat(),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
            )
    secrets = [
        os.environ.get("WEBULL_APP_KEY", ""),
        os.environ.get("WEBULL_APP_SECRET", ""),
        broker.app_key,
        broker.app_secret,
    ]
    print(
        format_check_report(
            environment=environment,
            accounts=accounts,
            snapshot=snapshot,
            quote=quote,
            bars=bars,
            secrets=secrets,
        )
    )
    return 0


def _live(config, args) -> int:
    from webull_bot.broker.webull import WebullBroker
    from webull_bot.data.webull_provider import WebullDataProvider
    from webull_bot.journal.store import Journal

    confirm_live(config.live_trading_enabled)
    names, rationale = load_selection(config)
    refuse_if_forward_only(names)
    if not names and not config.allow_unproven_strategies:
        raise SystemExit(
            "Refusing to go live with an empty or unproven book. "
            f"{rationale} Set allow_unproven_strategies only if you accept that."
        )
    broker = WebullBroker(environment=resolve_live_environment())
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


def _forward_now(args) -> datetime:
    from zoneinfo import ZoneInfo

    if args.now:
        stamp = datetime.fromisoformat(args.now)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=ZoneInfo("America/New_York"))
        return stamp
    return datetime.now(ZoneInfo("America/New_York"))


def _forward_names(args) -> list[str]:
    raw = args.strategy
    if isinstance(raw, str):
        return [raw]
    return list(raw)


def _forward_test(config, args) -> int:
    """One sandbox cycle. Dry-run does not connect. A real cycle is sandbox-only."""
    names = _forward_names(args)
    from webull_bot.execution.forward_vwap import BOOKS

    vwap = [name for name in names if name in BOOKS]
    chop = [name for name in names if name == "chop_breakout_60m"]
    if vwap and chop:
        raise SystemExit(
            "Run chop_breakout_60m on its own command. "
            "The two VWAP books share one command: "
            "python -m webull_bot forward-test vwap_band_15m vwap_band_15m_qqq"
        )
    if vwap:
        return _forward_vwap(config, args, vwap)
    if len(chop) != 1:
        raise SystemExit(
            "Unknown forward-test strategy. Known: chop_breakout_60m, vwap_band_15m, vwap_band_15m_qqq"
        )
    args.strategy = chop[0]
    from zoneinfo import ZoneInfo

    from webull_bot.data.yfinance_provider import YFinanceProvider
    from webull_bot.chart_reads.liquid import LIQUID_BLUE_CHIPS
    from webull_bot.execution.forward_chop import NAME, SYMBOLS, in_forward_window, run_cycle
    from webull_bot.journal.store import Journal
    from webull_bot.strategies.registry import forward_strategy

    if args.strategy != NAME:
        raise SystemExit(f"Unknown forward-test strategy {args.strategy!r}. Known: {NAME}")
    now = _forward_now(args)
    if not in_forward_window(now):
        local = now.astimezone(ZoneInfo("America/New_York"))
        print(
            f"forward-test idle at {local.isoformat()}. "
            "Outside the 10:35-15:45 ET window. No orders."
        )
        return 0
    broker = None
    if not args.dry_run:
        raw = os.environ.get("WEBULL_ENV", "").strip().lower()
        if raw not in {"sandbox", "uat", "test"}:
            raise SystemExit(
                "Refusing to forward-test without WEBULL_ENV=sandbox. "
                "Orders go only to *.sandbox.webull.com. "
                "Live trading stays off. Pass --dry-run to print the orders without connecting."
            )
        from webull_bot.broker.webull import WebullBroker, assert_sandbox_hosts

        broker = WebullBroker(environment="sandbox")
        broker.sandbox_only = True
        broker.connect()
        assert_sandbox_hosts(broker.hosts)
    journal = Journal(config.get("journal", "path", default="data/journal.sqlite"))
    provider = YFinanceProvider(config.get("data", "cache_dir", default="data/cache"))
    end = now.date()
    start = end - timedelta(days=720)
    names = list(dict.fromkeys([*SYMBOLS, *LIQUID_BLUE_CHIPS]))
    frames = provider.history(names, start.isoformat(), (end + timedelta(days=1)).isoformat(), "60m")
    lines = run_cycle(
        journal=journal,
        frames=frames,
        now=now,
        strategy=forward_strategy(args.strategy),
        broker=broker,
        dry_run=bool(args.dry_run),
    )
    print("\n".join(lines))
    return 0


def _forward_vwap(config, args, books: list[str] | None = None) -> int:
    """One 5-minute cycle of each frozen 2 SD continuation. Sandbox only."""
    from webull_bot.chart_reads.orb_mwf import prior_iv
    from webull_bot.data.yfinance_provider import YFinanceProvider
    from webull_bot.execution.forward_vwap import BOOKS, in_forward_window, run_cycle
    from webull_bot.journal.store import Journal

    names = list(books) if books else [name for name in _forward_names(args) if name in BOOKS]
    if not names:
        raise SystemExit("No VWAP forward book was named.")
    now = _forward_now(args)
    if not in_forward_window(now):
        from zoneinfo import ZoneInfo

        local = now.astimezone(ZoneInfo("America/New_York"))
        print(
            f"forward-test idle at {local.isoformat()}. "
            "Outside the 09:50-15:50 ET window. No orders."
        )
        return 0
    broker = None
    if not args.dry_run:
        raw = os.environ.get("WEBULL_ENV", "").strip().lower()
        if raw not in {"sandbox", "uat", "test"}:
            raise SystemExit(
                "Refusing to forward-test without WEBULL_ENV=sandbox. "
                "Orders go only to *.sandbox.webull.com. "
                "Live trading stays off. Pass --dry-run to print the orders without connecting."
            )
        from webull_bot.broker.webull import WebullBroker, assert_sandbox_hosts

        broker = WebullBroker(environment="sandbox")
        broker.sandbox_only = True
        broker.connect()
        assert_sandbox_hosts(broker.hosts)
    end = now.date()
    start = end - timedelta(days=50)
    provider = YFinanceProvider(config.get("data", "cache_dir", default="data/cache"))
    end_s = (end + timedelta(days=1)).isoformat()
    symbols = [BOOKS[name] for name in names]
    bars15 = provider.history(symbols, start.isoformat(), end_s, "15m")
    bars5 = provider.history(symbols, start.isoformat(), end_s, "5m")
    daily = provider.history(["^VIX", "^VIX1D"], "2016-01-01", end_s, "1d")
    closes = {}
    for symbol, frame in daily.items():
        if frame is None or frame.empty or "close" not in frame:
            continue
        closes[symbol] = frame["close"]
    points = prior_iv(closes.get("^VIX1D", pd.Series(dtype=float)), closes.get("^VIX", pd.Series(dtype=float)))
    journal = Journal(config.get("journal", "path", default="data/journal.sqlite"))
    blocks = []
    for name in names:
        symbol = BOOKS[name]
        fifteen = bars15.get(symbol) if isinstance(bars15, dict) else None
        five = bars5.get(symbol) if isinstance(bars5, dict) else None
        lines = run_cycle(
            journal=journal,
            bars15=fifteen if fifteen is not None else pd.DataFrame(),
            bars5=five if five is not None else pd.DataFrame(),
            now=now,
            iv_points=points,
            iv_closes=closes,
            broker=broker,
            dry_run=bool(args.dry_run),
            book=name,
        )
        blocks.append("\n".join(lines))
    print("\n\n".join(blocks))
    return 0


def _forward_report(config, args) -> int:
    from webull_bot.execution.forward_vwap import BOOKS

    if args.strategy in BOOKS:
        from webull_bot.execution.forward_vwap import report_text as vwap_report
        from webull_bot.journal.store import Journal

        journal = Journal(config.get("journal", "path", default="data/journal.sqlite"))
        print(vwap_report(journal, book=args.strategy), end="")
        return 0
    from webull_bot.execution.forward_chop import NAME, report_text
    from webull_bot.journal.store import Journal

    if args.strategy != NAME:
        raise SystemExit(f"Unknown forward-test strategy {args.strategy!r}. Known: {NAME}")
    journal = Journal(config.get("journal", "path", default="data/journal.sqlite"))
    print(report_text(journal), end="")
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
