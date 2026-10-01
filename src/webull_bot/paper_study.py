"""Paper-broker replay of every implemented strategy.

Stock and ETF rules go through ``run_replay`` and are scored against the
backtest engine on the same sessions. Chart Fanatics specs go through the
same broker's fills, stops, and daily-loss flatten. Shorts are not sent.
No Webull request is made.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from webull_bot.backtest.engine import run_backtest
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.broker.paper import PaperBroker
from webull_bot.config import cost_model_from_config, load_config
from webull_bot.costs import CostModel
from webull_bot.execution.session import _session_day, run_replay
from webull_bot.execution.signal_replay import FUTURES_LEVERAGE, replay_signals
from webull_bot.fanatics.data import BARS, value_areas_from_bars
from webull_bot.fanatics.seasonality import run_drift
from webull_bot.fanatics.simulate import Signal, simulate
from webull_bot.fanatics.specs import SIM, generate
from webull_bot.journal.store import Journal
from webull_bot.strategies.registry import all_strategies
from webull_bot.universe import STOCK_UNIVERSE, all_sectors, research_symbols
from webull_bot.universe_dow import all_dow_tickers

SESSIONS = 45
WARMUP_SESSIONS = 20
HOURLY = {"opening_range_breakout", "vwap_pullback"}
MARKER_START = "<!-- PAPER_SIM_START -->"
MARKER_END = "<!-- PAPER_SIM_END -->"


def run(report_dir: str = "reports", sessions: int = SESSIONS, config_path: str = "config/default.yaml") -> str:
    """Replay each strategy and splice the comparison into RESULTS.md."""
    config = load_config(config_path)
    from webull_bot.cli import _limits

    limits = _limits(config)
    costs = cost_model_from_config(config)
    equity = float(config.get("account", "starting_equity", default=100_000))
    account = str(config.get("account", "account_type", default="margin"))
    rows: list[dict] = []
    bugs: list[str] = []
    print("Loading daily bars for the stock and ETF books", flush=True)
    daily, regime = _load_daily(config)
    if daily:
        start_ts, end_ts, label = _window_bounds(daily["SPY"].index, sessions)
        for strategy in all_strategies():
            if strategy.name in HOURLY:
                continue
            print(f"Paper replay {strategy.name}", flush=True)
            try:
                rows.append(
                    _stock_row(strategy, daily, regime, start_ts, limits, costs, equity, account, label)
                )
            except Exception as exc:
                rows.append(_error_row(strategy.name, label, exc))
                bugs.append(f"{strategy.name}: {exc}")
        _flag_mismatches(rows, bugs)
    else:
        bugs.append("Daily Yahoo history did not load, so the stock books were not replayed.")
    print("Loading hourly bars for the opening-range and VWAP rules", flush=True)
    hourly = _load_hourly(config)
    if hourly and "SPY" in hourly and daily:
        start_ts, end_ts, label = _window_bounds(hourly["SPY"].index, sessions)
        daily_regime = regime if regime is not None else pd.DataFrame()
        for strategy in all_strategies():
            if strategy.name not in HOURLY:
                continue
            print(f"Paper replay {strategy.name}", flush=True)
            try:
                rows.append(
                    _stock_row(strategy, hourly, daily_regime, start_ts, limits, costs, equity, account, label)
                )
            except Exception as exc:
                rows.append(_error_row(strategy.name, label, exc))
                bugs.append(f"{strategy.name}: {exc}")
        _flag_mismatches(rows, bugs)
    elif hourly is None:
        bugs.append("Hourly Yahoo history did not load, so opening-range and VWAP were not replayed.")
    print("Paper replay Chart Fanatics specs", flush=True)
    rows.extend(_fanatics_rows(limits, costs, equity, account, sessions, bugs))
    text = _markdown(rows, bugs, sessions)
    out = Path(report_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "paper_sim_section.md").write_text(text)
    _splice_results(text)
    print(text, flush=True)
    return text


def _load_daily(config):
    from webull_bot.data.yfinance_provider import YFinanceProvider
    from webull_bot.strategies.regime import build_regime

    symbols = sorted(set(research_symbols()) | set(all_dow_tickers()))
    provider = YFinanceProvider(config.get("data", "cache_dir", default="data/cache"))
    end = (pd.Timestamp.utcnow() + pd.Timedelta(days=1)).date().isoformat()
    try:
        bars = provider.history(symbols, "2022-01-01", end, "1d")
    except Exception as exc:
        print(f"daily download failed: {exc}", flush=True)
        return None, None
    if "SPY" not in bars or bars["SPY"].empty:
        return None, None
    regime = build_regime(bars, [name for name in STOCK_UNIVERSE if name in bars])
    return bars, regime


def _load_hourly(config):
    from webull_bot.data.yfinance_provider import YFinanceProvider

    provider = YFinanceProvider(config.get("data", "cache_dir", default="data/cache"))
    end = (pd.Timestamp.utcnow() + pd.Timedelta(days=1)).date().isoformat()
    try:
        bars = provider.history(["SPY", "QQQ"], "2026-04-01", end, "60m")
    except Exception as exc:
        print(f"hourly download failed: {exc}", flush=True)
        return None
    return bars


def _window_bounds(index: pd.DatetimeIndex, sessions: int):
    days = _days(index)
    chosen = days[-sessions:] if len(days) >= sessions else days
    start = chosen[0]
    end = chosen[-1]
    label = f"{start.isoformat()} to {end.isoformat()} ({len(chosen)} sessions)"
    return _first_ts(index, start), _first_ts(index, end), label


def _first_ts(index: pd.DatetimeIndex, day):
    for ts in index:
        if _session_day(ts) >= day:
            return ts
    return index[-1]


def _days(index) -> list:
    found = []
    for ts in index:
        day = _session_day(ts)
        if not found or found[-1] != day:
            found.append(day)
    return found


def _stock_row(strategy, bars, regime, start_ts, limits, costs, equity, account, label) -> dict:
    from webull_bot.cli import _trade_symbols

    symbols = _trade_symbols(strategy)
    params = {strategy.name: {"symbols": symbols}}
    scoped = {symbol: frame for symbol, frame in bars.items() if symbol in set(symbols) | {"SPY", "^VIX", "BIL"}}
    if "SPY" not in scoped:
        scoped["SPY"] = bars["SPY"]
    result = run_backtest(
        scoped,
        [strategy],
        regime,
        starting_equity=equity,
        costs=costs,
        limits=limits,
        sectors=all_sectors(),
        account_type=account,
        params=params,
        trade_start=pd.Timestamp(start_ts),
        flatten_at_end=True,
    )
    metrics = compute_metrics(result, equity)
    with tempfile.TemporaryDirectory() as tmp:
        broker = PaperBroker(Path(tmp) / "paper.sqlite", costs, starting_equity=equity, account_type=account)
        broker.connect()
        journal = Journal(Path(tmp) / "journal.sqlite")
        summary = run_replay(
            scoped,
            [strategy],
            regime,
            broker,
            journal,
            cycles=1,
            limits=limits,
            params=params,
            start=start_ts,
            quiet=True,
            flatten_at_end=True,
            include_prior_open=False,
        )
    note = _stock_note(metrics, summary)
    return _row(
        strategy.name,
        label,
        metrics,
        summary,
        note,
        equity,
    )


def _stock_note(metrics: dict, summary: dict) -> str:
    trades_ok = int(metrics["trades"]) == int(summary["closed_trades"])
    pnl_gap = abs(float(metrics["ending_equity"]) - float(summary["ending_equity"]))
    if trades_ok and pnl_gap <= 1.0:
        return "Paper matches the backtest on this window."
    return (
        f"Paper and backtest differ (trade count {summary['closed_trades']} vs {metrics['trades']}, "
        f"ending equity gap ${pnl_gap:,.2f})."
    )


def _fanatics_rows(limits, costs, equity, account, sessions, bugs: list[str]) -> list[dict]:
    rows = []
    try:
        rows.append(_spec8_row(limits, costs, equity, account, sessions))
    except Exception as exc:
        rows.append(_error_row("fanatics_8_overnight", "SPY+QQQ daily", exc))
        bugs.append(f"fanatics_8_overnight: {exc}")
    specs = [
        (1, "fanatics_1_pdh_pdl", ("NQ=F", "ES=F"), "yahoo_NQF_5m.pkl", "yahoo_ESF_5m.pkl"),
        (3, "fanatics_3_value_area", ("NQ=F", "ES=F"), "yahoo_NQF_5m.pkl", "yahoo_ESF_5m.pkl"),
        (5, "fanatics_5_liquidity", ("NQ=F", "ES=F"), "yahoo_NQF_5m.pkl", "yahoo_ESF_5m.pkl"),
        (6, "fanatics_6_1000_sweep", ("NQ=F", "ES=F"), "yahoo_NQF_5m.pkl", "yahoo_ESF_5m.pkl"),
        (7, "fanatics_7_orb", ("NQ=F", "ES=F"), "yahoo_NQF_5m.pkl", "yahoo_ESF_5m.pkl"),
        (4, "fanatics_4_edge", ("NQ=F", "ES=F"), "yahoo_NQF_60m.pkl", "yahoo_ESF_60m.pkl"),
        (2, "fanatics_2_london_fvg", ("GC=F",), "yahoo_GCF_30m.pkl", None),
    ]
    zero_cost = CostModel(
        slippage_bps=0.0,
        half_spread_bps=0.0,
        sec_fee_per_dollar_sold=0.0,
        finra_taf_per_share=0.0,
    )
    for spec_id, name, symbols, primary, secondary in specs:
        print(f"Paper replay {name}", flush=True)
        try:
            rows.append(
                _spec_row(
                    spec_id, name, symbols, primary, secondary, limits, zero_cost, equity, account, sessions
                )
            )
        except Exception as exc:
            rows.append(_error_row(name, "intraday cache", exc))
            bugs.append(f"{name}: {exc}")
    return rows


def _spec_row(spec_id, name, symbols, primary, secondary, limits, costs, equity, account, sessions) -> dict:
    raw = {}
    first = _load_pkl(primary)
    if first is not None:
        raw[symbols[0]] = first
    if secondary and len(symbols) > 1:
        second = _load_pkl(secondary)
        if second is not None:
            raw[symbols[1]] = second
    if not raw:
        return _error_row(name, "missing cache", RuntimeError(f"no bars in {primary}"))
    sample = next(iter(raw.values()))
    warmup_day, trade_day, end_day = _bounds_for(sample.index, sessions)
    sliced = {symbol: _since(frame, warmup_day) for symbol, frame in raw.items()}
    areas = {}
    if spec_id == 3:
        for symbol, frame in sliced.items():
            areas[symbol] = value_areas_from_bars(frame, 0.25)
    if spec_id == 2 and not _has_london(sample):
        paxg = _load_pkl("PAXGUSDT_30m.pkl")
        if paxg is not None:
            sliced = {"PAXGUSDT": _since(paxg, _bounds_for(paxg.index, sessions)[0])}
            symbols = ("PAXGUSDT",)
            warmup_day, trade_day, end_day = _bounds_for(sliced["PAXGUSDT"].index, sessions)
            sample_note = "PAXG 30-minute proxy; Yahoo GC=F had no London hours"
        else:
            sample_note = "GC=F 30-minute"
    else:
        sample_note = ", ".join(sliced)
    params = {"symbols": list(sliced)}
    signals, frames = generate(spec_id, sliced, params, areas or None)
    if not frames:
        frames = sliced
    kept = [signal for signal in signals if _fill_day(frames, signal) is not None and _fill_day(frames, signal) >= trade_day]
    sim = dict(SIM.get(spec_id, {}))
    result, trades = simulate(frames, kept, **sim)
    metrics = _fanatics_metrics(result, trades, equity)
    with tempfile.TemporaryDirectory() as tmp:
        broker = PaperBroker(
            Path(tmp) / "paper.sqlite",
            costs,
            starting_equity=equity,
            account_type=account,
            leverage=FUTURES_LEVERAGE,
        )
        broker.connect()
        journal = Journal(Path(tmp) / "journal.sqlite")
        summary = replay_signals(
            frames,
            kept,
            broker,
            journal,
            limits,
            strategy=name,
            risk=float(sim.get("risk", 0.005)),
            trade_start=trade_day,
        )
    label = f"{trade_day.isoformat()} to {end_day.isoformat()} ({sample_note})"
    longs = [signal for signal in kept if signal.side > 0]
    long_result, long_trades = simulate(frames, longs, **sim)
    long_metrics = _fanatics_metrics(long_result, long_trades, equity)
    note = (
        f"Shorts not sent: {summary['shorts_not_sent']}. "
        f"Long-only backtest P&L ${long_metrics['pnl']:,.2f} on {int(long_metrics['trades'])} "
        f"{'trade' if int(long_metrics['trades']) == 1 else 'trades'}. "
        "Paper reserves futures margin at 20x and does not apply stock bps; "
        "the backtest charges 1 tick of entry slippage, extra stop ticks, and futures or crypto fees. "
        f"Rejections: {_reject_text(summary['rejected'])}."
    )
    return _row(name, label, metrics, summary, note, equity)


def _spec8_row(limits, costs, equity, account, sessions) -> dict:
    from webull_bot.broker.webull import new_client_order_id
    from webull_bot.costs import buy_price
    from webull_bot.execution.session import _sized_order
    from webull_bot.models import Side
    from webull_bot.risk.manager import RiskState, circuit_update

    spy = _load_pkl("yahoo_SPY_1d.pkl")
    qqq = _load_pkl("yahoo_QQQ_1d.pkl")
    if spy is None or qqq is None:
        raise RuntimeError("SPY/QQQ daily cache is missing")
    days = _days(spy.index)
    chosen = days[-sessions:] if len(days) >= sessions else days
    start, end = chosen[0], chosen[-1]
    spy_w = spy[(spy.index.map(_session_day) >= start) & (spy.index.map(_session_day) <= end)]
    qqq_w = qqq[(qqq.index.map(_session_day) >= start) & (qqq.index.map(_session_day) <= end)]
    metrics, _trades = run_drift(
        {"SPY": spy_w, "QQQ": qqq_w},
        start=start.isoformat(),
        end=end.isoformat(),
        costs=costs,
    )
    backtest = {
        "trades": int(metrics.get("trades") or 0),
        "ending_equity": float(metrics.get("ending_equity") or equity),
        "pnl": float(metrics.get("ending_equity") or equity) - equity,
        "win_rate": float(metrics.get("win_rate") or 0.0),
        "max_drawdown": float(metrics.get("max_drawdown") or 0.0),
    }
    with tempfile.TemporaryDirectory() as tmp:
        broker = PaperBroker(Path(tmp) / "paper.sqlite", costs, starting_equity=equity, account_type=account)
        broker.connect()
        journal = Journal(Path(tmp) / "journal.sqlite")
        summary = _replay_drift(spy_w, qqq_w, broker, journal, limits, _sized_order, circuit_update, RiskState, buy_price, new_client_order_id, Side)
    label = f"{start.isoformat()} to {end.isoformat()} ({len(chosen)} sessions, SPY+QQQ daily)"
    note = (
        "Research book is fully invested, split across SPY and QQQ. "
        "Paper sizes with the account risk cap (0.75% at a 2% disaster stop, 20% position cap, 35% sector cap) "
        "and exits at the next open. Both names are the broad sector, so the second order can be rejected. "
        f"Rejections: {_reject_text(summary['rejected'])}."
    )
    return _row("fanatics_8_overnight", label, backtest, summary, note, equity)


def _replay_drift(spy, qqq, broker, journal, limits, sized, circuit_update, risk_state, buy_price, new_id, side) -> dict:
    from webull_bot.models import Order, OrderType, TimeInForce

    left = spy[["open", "close"]].rename(columns={"open": "SPY_open", "close": "SPY_close"})
    right = qqq[["open", "close"]].rename(columns={"open": "QQQ_open", "close": "QQQ_close"})
    book = left.join(right, how="inner")
    opening = broker.snapshot()
    peak = opening.equity
    drawdown_halt = False
    flattened_today = False
    orders_n = 0
    fills_n = 0
    rejected: dict[str, int] = {}
    triggers = []
    closed = []
    open_lots: dict[str, dict] = {}
    equity_curve = []
    names = ("SPY", "QQQ")

    def realize(fills) -> None:
        nonlocal fills_n
        fills_n += len(fills)
        for fill in fills:
            if fill.side == side.BUY:
                open_lots[fill.symbol] = {"price": fill.price, "qty": fill.quantity, "fees": fill.fees}
            else:
                lot = open_lots.pop(fill.symbol, None)
                if lot is not None:
                    qty = min(float(fill.quantity), float(lot["qty"]))
                    pnl = (float(fill.price) - float(lot["price"])) * qty - float(fill.fees) - float(lot["fees"])
                    closed.append(pnl)

    for i, ts in enumerate(book.index):
        session = _session_day(ts)
        # Measure the overnight gap against the prior close. Marking to the
        # open first would hide that gap from the daily-loss breaker.
        day_start = broker.snapshot().equity
        for name in names:
            if any(pos.symbol == name for pos in broker.positions()):
                realize(broker.fill_exit(name, float(book.iloc[i][f"{name}_open"]), "signal"))
        snap = broker.snapshot()
        state = circuit_update(
            risk_state(
                equity=snap.equity,
                cash=snap.cash,
                peak_equity=peak,
                day_start_equity=day_start,
                positions=snap.positions,
                drawdown_halt=drawdown_halt,
            ),
            limits,
        )
        peak = state.peak_equity
        drawdown_halt = state.drawdown_halt
        daily_hit = day_start > 0 and (1.0 - snap.equity / day_start) >= limits.daily_max_loss_pct - 1e-12
        flattened_today = False
        if daily_hit and limits.flatten_on_daily_loss:
            flattened_today = True
            triggers.append({"session": session.isoformat(), "kind": "daily_loss"})
            if snap.positions or broker.open_orders():
                realize(broker.flatten())
            journal.event("kill", "paper daily-loss flatten", {"session": session.isoformat(), "strategy": "fanatics_8_overnight"})
        if i == len(book) - 1 or flattened_today or drawdown_halt:
            equity_curve.append(broker.snapshot().equity)
            continue
        cash_left = broker.snapshot().cash
        snapshot = broker.snapshot()
        for name in names:
            close_px = float(book.iloc[i][f"{name}_close"])
            stop = close_px * 0.98
            order, plan = sized(
                limits,
                snapshot,
                {pos.symbol: pos.peak_price or pos.avg_price for pos in snapshot.positions},
                [],
                peak_equity=peak,
                day_start_equity=day_start,
                drawdown_halt=drawdown_halt,
                symbol=name,
                raw_price=buy_price(close_px, broker.costs),
                stop_price=stop,
                strategy="fanatics_8_overnight",
                session=session,
                sector=all_sectors().get(name, "broad"),
                holds_overnight=True,
                day_trade_dates=[],
                returns=None,
                cash=cash_left,
            )
            if order is None:
                rejected[plan.reason] = rejected.get(plan.reason, 0) + 1
                if plan.flatten_now and (broker.positions() or broker.open_orders()):
                    triggers.append({"session": session.isoformat(), "kind": plan.halt_kind or "daily"})
                    realize(broker.flatten())
                    flattened_today = True
                    break
                continue
            placed = Order(
                client_order_id=new_id(),
                symbol=name,
                side=side.BUY,
                quantity=order.quantity,
                order_type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
                stop_price=stop,
                strategy="fanatics_8_overnight",
            )
            realize(broker.fill_order_at(placed, close_px))
            broker.set_sector(name, all_sectors().get(name, "broad"))
            orders_n += 1
            cash_left -= order.quantity * buy_price(close_px, broker.costs)
            snapshot = broker.snapshot()
        equity_curve.append(broker.snapshot().equity)
    snap = broker.snapshot()
    wins = [pnl for pnl in closed if pnl > 0]
    peak_eq = opening.equity
    worst = 0.0
    for value in equity_curve:
        peak_eq = max(peak_eq, value)
        if peak_eq:
            worst = min(worst, value / peak_eq - 1.0)
    return {
        "orders": orders_n,
        "fills": fills_n,
        "closed_trades": len(closed),
        "pnl": snap.equity - opening.equity,
        "ending_equity": snap.equity,
        "win_rate": (len(wins) / len(closed)) if closed else 0.0,
        "max_drawdown": worst,
        "risk_triggers": triggers,
        "rejected": rejected,
        "shorts_not_sent": 0,
    }


def _fanatics_metrics(result, trades: pd.DataFrame, equity: float) -> dict:
    metrics = compute_metrics(result, equity)
    pnl = float(metrics["ending_equity"]) - equity
    return {
        "trades": int(len(trades)) if trades is not None else int(metrics["trades"]),
        "ending_equity": float(metrics["ending_equity"]),
        "pnl": pnl,
        "win_rate": float(metrics["win_rate"] or 0.0),
        "max_drawdown": float(metrics["max_drawdown"] or 0.0),
    }


def _fill_day(frames: dict[str, pd.DataFrame], signal: Signal):
    frame = frames.get(signal.symbol)
    if frame is None:
        return None
    loc = signal.signal_loc if signal.limit_entry is not None else signal.signal_loc + 1
    if loc < 0 or loc >= len(frame):
        return None
    return _session_day(frame.index[loc])


def _bounds_for(index, sessions: int):
    days = _days(index)
    trade = days[-sessions:] if len(days) >= sessions else days
    warmup = days[-(sessions + WARMUP_SESSIONS) :] if len(days) >= sessions else days
    return warmup[0], trade[0], trade[-1]


def _since(frame: pd.DataFrame, day) -> pd.DataFrame:
    mask = [_session_day(ts) >= day for ts in frame.index]
    return frame.loc[mask]


def _has_london(frame: pd.DataFrame) -> bool:
    if frame.empty or getattr(frame.index, "tz", None) is None:
        return False
    minutes = frame.index.tz_convert("America/New_York")
    clock = minutes.hour * 60 + minutes.minute
    return bool(((clock >= 150) & (clock < 390)).any())


def _load_pkl(name: str):
    path = BARS / name
    if not path.exists():
        return None
    frame = pd.read_pickle(path)
    if frame is None or len(frame) == 0:
        return None
    return frame


def _row(name, label, backtest, paper, note, equity) -> dict:
    if "pnl" not in backtest:
        backtest = {
            "trades": int(backtest.get("trades") or 0),
            "pnl": float(backtest.get("ending_equity") or equity) - equity,
            "win_rate": float(backtest.get("win_rate") or 0.0),
            "max_drawdown": float(backtest.get("max_drawdown") or 0.0),
            "ending_equity": float(backtest.get("ending_equity") or equity),
        }
    triggers = paper.get("risk_triggers") or []
    kinds = sorted({item.get("kind", "") for item in triggers if item.get("kind")})
    return {
        "name": name,
        "window": label,
        "bt_trades": int(backtest["trades"]),
        "bt_pnl": float(backtest["pnl"]),
        "bt_win": float(backtest["win_rate"]),
        "bt_dd": float(backtest["max_drawdown"]),
        "orders": int(paper.get("orders") or 0),
        "fills": int(paper.get("fills") or 0),
        "closed": int(paper.get("closed_trades") or 0),
        "pnl": float(paper.get("pnl") or 0.0),
        "win": float(paper.get("win_rate") or 0.0),
        "dd": float(paper.get("max_drawdown") or 0.0),
        "triggers": f"{len(triggers)}" + (f" ({', '.join(kinds)})" if kinds else ""),
        "note": note,
        "error": False,
    }


def _error_row(name: str, label: str, exc: Exception) -> dict:
    return {
        "name": name,
        "window": label,
        "bt_trades": 0,
        "bt_pnl": 0.0,
        "bt_win": 0.0,
        "bt_dd": 0.0,
        "orders": 0,
        "fills": 0,
        "closed": 0,
        "pnl": 0.0,
        "win": 0.0,
        "dd": 0.0,
        "triggers": "0",
        "note": f"Replay failed: {exc}",
        "error": True,
    }


def _flag_mismatches(rows: list[dict], bugs: list[str]) -> None:
    for row in rows:
        if row.get("error"):
            continue
        if row["name"].startswith("fanatics_"):
            continue
        text = f"{row['name']}: {row['note']}"
        if "differ" in row["note"] and text not in bugs:
            bugs.append(text)


def _reject_text(rejected: dict) -> str:
    if not rejected:
        return "none"
    return ", ".join(f"{key} {value}" for key, value in sorted(rejected.items()))


def _markdown(rows: list[dict], bugs: list[str], sessions: int) -> str:
    lines = [
        "## Paper replay versus backtest",
        "",
        f"Each implemented strategy was replayed on the last {sessions} sessions available in the local cache, "
        "or on that many recent Yahoo sessions for the daily and hourly stock rules. "
        "The paper column uses the paper broker: simulated fills, protective stops, the configured "
        "daily-loss flatten (default 2%), and the same flatten the kill switch calls. "
        "The backtest column is the research fill model on that same window. "
        "Both start flat, so a signal that closed before the window is not filled. "
        "Shorts and option orders were not sent. The Webull API was not called. "
        "When the note says paper matches, closed-trade count and P&L agree to the dollar. "
        "Max drawdown can still differ by a few basis points because the two equity curves are not sampled on the same marks.",
        "",
        "Dual momentum is the reference book. A paper result that does not match its backtest "
        "on this window is a simulator bug. Fanatics specs 1–7 are futures or crypto prints. "
        "The stock paper account cannot buy an index future for cash, so those replays reserve "
        "margin at 20x inside the paper ledger and still refuse shorts. They are not Webull stock orders "
        "and they are not in the config. Each spec's session stop (its consecutive-loss limit and its "
        "±R day limit) is in the backtest column only. Paper also skips the one-tick entry slip "
        "and the extra stop ticks, so the same trades can print a different dollar P&L.",
        "",
        "| Strategy | Window | Backtest trades | Backtest P&L | Backtest win | Backtest max DD | Paper orders | Paper fills | Paper closed | Paper P&L | Paper win | Paper max DD | Risk triggers | Notes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {name} | {window} | {bt_trades} | {bt_pnl} | {bt_win} | {bt_dd} | {orders} | {fills} | {closed} | {pnl} | {win} | {dd} | {triggers} | {note} |".format(
                name=row["name"],
                window=row["window"],
                bt_trades=row["bt_trades"],
                bt_pnl=_money(row["bt_pnl"]),
                bt_win=_pct(row["bt_win"]),
                bt_dd=_pct(row["bt_dd"]),
                orders=row["orders"],
                fills=row["fills"],
                closed=row["closed"],
                pnl=_money(row["pnl"]),
                win=_pct(row["win"]),
                dd=_pct(row["dd"]),
                triggers=row["triggers"],
                note=row["note"],
            )
        )
    lines.append("")
    if bugs:
        lines.append("Issues the replay exposed:")
        lines.append("")
        for bug in bugs:
            lines.append(f"- {bug}")
    else:
        lines.append("No paper-versus-backtest mismatch remained on the stock and ETF rules, and no replay crashed.")
    lines.append("")
    lines.append(
        "Run it again with `python -m webull_bot paper-sim`. "
        "That command stays on the local paper broker. See the README for the sandbox account settings, which this run did not use."
    )
    lines.append("")
    return "\n".join(lines)


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _splice_results(section: str) -> None:
    path = Path("RESULTS.md")
    text = path.read_text() if path.exists() else ""
    block = f"{MARKER_START}\n{section.strip()}\n{MARKER_END}\n"
    if MARKER_START in text and MARKER_END in text:
        start = text.index(MARKER_START)
        end = text.index(MARKER_END) + len(MARKER_END)
        text = text[:start] + block.rstrip("\n") + text[end:]
    else:
        text = text.rstrip() + "\n\n" + block
    path.write_text(text if text.endswith("\n") else text + "\n")
