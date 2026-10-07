"""Holdings the live loop should have, using the backtest's fill rules.

A rotation such as dual momentum sets ``entry_next_open`` only on the
month-end bar. The backtest buys at the next open and keeps the position
until a later rebalance or the trailing stop. The live loop reconciles
those open holdings on every cycle, including days that are not the
signal day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Optional

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.costs import CostModel, buy_price
from webull_bot.models import OrderType, Side

# Same start the published research backtest uses. Signals before this
# date do not open a position; the book starts flat.
RESEARCH_TRADE_START = pd.Timestamp("2017-01-01")
ALLOCATION_STRATEGIES = {"dual_momentum", "rs_rotation"}
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)


@dataclass
class Held:
    symbol: str
    strategy: str
    entry_time: pd.Timestamp
    entry_price: float
    peak: float
    stop: float
    trail_pct: Optional[float]


@dataclass
class CycleLine:
    strategy: str
    symbol: str
    text: str
    kind: str
    quantity: float = 0.0
    stop: Optional[float] = None
    peak: Optional[float] = None
    entry_key: str = ""
    cancel_stops: bool = False


@dataclass
class StopDecision:
    """Trailed stop for one open backtest holding, in cents for the order."""

    peak: float
    stop: float
    stopped: bool
    entry_key: str


@dataclass
class _Queued:
    kind: str
    symbol: str
    stop: float
    strategy: str
    trail_pct: Optional[float]
    max_hold: Optional[int]
    holds_overnight: bool


def is_allocation(strategy) -> bool:
    return getattr(strategy, "name", "") in ALLOCATION_STRATEGIES


def cents(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def qty_text(quantity: float) -> str:
    if float(quantity).is_integer():
        return str(int(quantity))
    return f"{quantity:.4f}".rstrip("0").rstrip(".")


def split_forming_bar(
    bars: dict[str, pd.DataFrame],
    now: datetime,
) -> tuple[dict[str, pd.DataFrame], Optional[pd.Timestamp]]:
    """Drop today's daily bar before the cash close. Its close is not final."""
    spy = bars.get("SPY")
    if spy is None or spy.empty:
        return bars, None
    last = pd.Timestamp(spy.index[-1])
    last_day = _session_date(last)
    if last_day != now.date() or now.time() >= RTH_CLOSE:
        return bars, None
    trimmed: dict[str, pd.DataFrame] = {}
    for symbol, frame in bars.items():
        if frame.empty:
            continue
        if pd.Timestamp(frame.index[-1]) == last:
            trimmed[symbol] = frame.iloc[:-1]
        else:
            trimmed[symbol] = frame
    if trimmed.get("SPY") is None or trimmed["SPY"].empty:
        return bars, None
    return trimmed, last


def next_session_has_opened(last_completed: pd.Timestamp, now: datetime) -> bool:
    """True once the open after ``last_completed`` has happened."""
    nxt = next_trading_day(_session_date(last_completed))
    if now.date() < nxt:
        return False
    if now.date() == nxt:
        return now.time() >= RTH_OPEN
    return True


def open_targets(
    bars: dict[str, pd.DataFrame],
    signals: dict[str, pd.DataFrame],
    *,
    strategy: str,
    trail_pct: Optional[float],
    holds_overnight: bool,
    now: datetime,
    costs: CostModel | None = None,
    trade_start: pd.Timestamp | None = RESEARCH_TRADE_START,
) -> dict[str, Held]:
    """Holdings the backtest would have open at ``now``."""
    costs = costs or CostModel()
    completed, _forming = split_forming_bar(bars, now)
    # Signals were generated on completed bars. The caller passes that
    # book; clip it to the completed clock so today's unfinished close
    # cannot change the month-end decision.
    if "SPY" not in completed or completed["SPY"].empty:
        return {}
    last = pd.Timestamp(completed["SPY"].index[-1])
    clipped = _clip_signals(signals, last)
    if not next_session_has_opened(last, now):
        held, _path = replay_holdings(
            completed,
            clipped,
            strategy=strategy,
            trail_pct=trail_pct,
            holds_overnight=holds_overnight,
            costs=costs,
            trade_start=trade_start,
        )
        return held
    opens = _opens_for_pending(bars, completed, now)
    return _fill_last_queue(
        completed,
        clipped,
        opens,
        strategy=strategy,
        trail_pct=trail_pct,
        holds_overnight=holds_overnight,
        costs=costs,
        trade_start=trade_start,
        when=pd.Timestamp(now),
    )


def _fill_last_queue(
    bars,
    signals,
    opens: dict[str, float],
    *,
    strategy: str,
    trail_pct: Optional[float],
    holds_overnight: bool,
    costs: CostModel,
    trade_start,
    when: pd.Timestamp,
) -> dict[str, Held]:
    """Replay, then fill only the queue that the last bar left behind."""
    state = _walk(
        bars,
        signals,
        strategy=strategy,
        trail_pct=trail_pct,
        holds_overnight=holds_overnight,
        costs=costs,
        trade_start=trade_start,
    )
    positions = state["positions"]
    for order in state["queue"]:
        if order.kind == "exit":
            positions.pop(order.symbol, None)
            continue
        if order.symbol in positions:
            continue
        raw = opens.get(order.symbol)
        if raw is None:
            continue
        _try_enter(positions, raw, order.stop, when, order.symbol, strategy, trail_pct, costs)
    return positions


def _walk(bars, signals, *, strategy, trail_pct, holds_overnight, costs, trade_start) -> dict[str, Any]:
    """Same walk as ``replay_holdings``, also returning the unfilled queue."""
    # Reuse replay_holdings' loop by inlining the queue return. The public
    # path helper above needs the queue, so the walk lives here and
    # replay_holdings calls it.
    if "SPY" in signals and "SPY" in bars:
        index = pd.DatetimeIndex(signals["SPY"].index)
    elif signals:
        index = pd.DatetimeIndex(next(iter(signals.values())).index)
    else:
        return {"positions": {}, "queue": [], "path": []}
    if trade_start is not None:
        start = pd.Timestamp(trade_start)
        if index.tz is not None and start.tzinfo is None:
            start = start.tz_localize(index.tz)
        index = index[index >= start]
    books = _books(bars, signals, index)
    symbols = sorted(books)
    positions: dict[str, Held] = {}
    queue: list[_Queued] = []
    path: list[tuple[pd.Timestamp, frozenset[str]]] = []
    sessions = [_session_date(ts) for ts in index]
    for i, ts in enumerate(index):
        exited: set[str] = set()
        entries: list[_Queued] = []
        for order in queue:
            if order.kind == "exit":
                if order.symbol in positions and _finite(books[order.symbol]["open"][i]):
                    del positions[order.symbol]
                    exited.add(order.symbol)
                continue
            entries.append(order)
        queue = []
        for order in entries:
            if order.symbol in exited or order.symbol in positions:
                continue
            _try_enter(
                positions,
                books[order.symbol]["open"][i],
                order.stop,
                pd.Timestamp(ts),
                order.symbol,
                strategy,
                trail_pct,
                costs,
            )
        for symbol in symbols:
            if not books[symbol]["entry_this"][i] or symbol in exited:
                continue
            _try_enter(
                positions,
                books[symbol]["open"][i],
                float(books[symbol]["stop"][i]),
                pd.Timestamp(ts),
                symbol,
                strategy,
                trail_pct,
                costs,
            )
        for symbol in list(positions):
            bar_open = books[symbol]["open"][i]
            bar_low = books[symbol]["low"][i]
            bar_high = books[symbol]["high"][i]
            if not (_finite(bar_open) and _finite(bar_low) and _finite(bar_high)):
                continue
            if bar_open <= positions[symbol].stop or bar_low <= positions[symbol].stop:
                del positions[symbol]
        for symbol in list(positions):
            pos = positions[symbol]
            if pos.trail_pct is None:
                continue
            bar_high = books[symbol]["high"][i]
            bar_low = books[symbol]["low"][i]
            if not _finite(bar_high):
                continue
            pos.peak = max(pos.peak, float(bar_high))
            trailed = pos.peak * (1.0 - pos.trail_pct)
            if trailed > pos.stop:
                pos.stop = trailed
                if _finite(bar_low) and bar_low <= pos.stop:
                    del positions[symbol]
        last_in_session = i == len(index) - 1 or sessions[i + 1] != sessions[i]
        for symbol in list(positions):
            if not _finite(books[symbol]["close"][i]):
                continue
            reason = bool(books[symbol]["exit_close"][i])
            max_hold = books[symbol]["max_hold"][i]
            if _finite(max_hold) and max_hold > 0:
                entered = int(index.get_indexer([positions[symbol].entry_time])[0])
                if entered >= 0 and (i - entered) >= int(max_hold):
                    reason = True
            if last_in_session and not holds_overnight:
                reason = True
            if reason:
                del positions[symbol]
        queued: set[str] = set()
        for symbol in symbols:
            in_pos = symbol in positions
            if books[symbol]["exit_next"][i] and in_pos:
                queue.append(_Queued("exit", symbol, 0.0, strategy, trail_pct, None, holds_overnight))
            if not books[symbol]["entry_next"][i]:
                continue
            if last_in_session and not holds_overnight:
                continue
            if in_pos and books[symbol]["exit_next"][i]:
                continue
            if symbol in queued:
                continue
            stop = float(books[symbol]["stop"][i])
            if not _finite(stop):
                continue
            queued.add(symbol)
            queue.append(_Queued("enter", symbol, stop, strategy, trail_pct, None, holds_overnight))
        path.append((pd.Timestamp(ts), frozenset(positions)))
    return {"positions": positions, "queue": queue, "path": path}


def replay_path(
    bars,
    signals,
    *,
    strategy: str,
    trail_pct: Optional[float],
    holds_overnight: bool,
    costs: CostModel | None = None,
    trade_start: pd.Timestamp | None = RESEARCH_TRADE_START,
) -> list[tuple[pd.Timestamp, frozenset[str]]]:
    state = _walk(
        bars,
        signals,
        strategy=strategy,
        trail_pct=trail_pct,
        holds_overnight=holds_overnight,
        costs=costs or CostModel(),
        trade_start=trade_start,
    )
    return state["path"]


def _books(bars, signals, index: pd.DatetimeIndex) -> dict[str, dict[str, np.ndarray]]:
    books: dict[str, dict[str, np.ndarray]] = {}
    for symbol, frame in signals.items():
        if symbol not in bars or str(symbol).startswith("^"):
            continue
        price = bars[symbol].reindex(index)
        sig = frame.reindex(index)
        books[symbol] = {
            "open": price["open"].to_numpy(dtype=float),
            "high": price["high"].to_numpy(dtype=float),
            "low": price["low"].to_numpy(dtype=float),
            "close": price["close"].to_numpy(dtype=float),
            "entry_next": _flag(sig, "entry_next_open", len(index)),
            "entry_this": _flag(sig, "entry_this_open", len(index)),
            "exit_next": _flag(sig, "exit_next_open", len(index)),
            "exit_close": _flag(sig, "exit_this_close", len(index)),
            "stop": sig["stop_price"].to_numpy(dtype=float) if "stop_price" in sig else np.full(len(index), np.nan),
            "max_hold": sig["max_hold"].to_numpy(dtype=float) if "max_hold" in sig else np.full(len(index), np.nan),
        }
    return books


def _flag(frame: pd.DataFrame, column: str, n: int) -> np.ndarray:
    if column not in frame:
        return np.zeros(n, dtype=bool)
    return frame[column].fillna(False).to_numpy(dtype=bool)


def replay_holdings(
    bars: dict[str, pd.DataFrame],
    signals: dict[str, pd.DataFrame],
    *,
    strategy: str,
    trail_pct: Optional[float],
    holds_overnight: bool,
    costs: CostModel | None = None,
    trade_start: pd.Timestamp | None = RESEARCH_TRADE_START,
) -> tuple[dict[str, Held], list[tuple[pd.Timestamp, frozenset[str]]]]:
    state = _walk(
        bars,
        signals,
        strategy=strategy,
        trail_pct=trail_pct,
        holds_overnight=holds_overnight,
        costs=costs or CostModel(),
        trade_start=trade_start,
    )
    return state["positions"], state["path"]


def _try_enter(positions, raw, stop, when, symbol, strategy, trail_pct, costs) -> None:
    if symbol in positions:
        return
    if not _finite(raw) or raw <= 0:
        return
    if not _finite(stop) or stop <= 0 or stop >= raw:
        return
    fill = buy_price(float(raw), costs)
    if fill <= stop:
        return
    positions[symbol] = Held(
        symbol=symbol,
        strategy=strategy,
        entry_time=pd.Timestamp(when),
        entry_price=fill,
        peak=fill,
        stop=float(stop),
        trail_pct=trail_pct,
    )


def _clip_signals(signals: dict[str, pd.DataFrame], last: pd.Timestamp) -> dict[str, pd.DataFrame]:
    clipped = {}
    for symbol, frame in signals.items():
        clipped[symbol] = frame.loc[:last]
    return clipped


def _opens_for_pending(bars, completed, now: datetime) -> dict[str, float]:
    """Open of the session after the completed bars, else the last close."""
    opens: dict[str, float] = {}
    spy = completed.get("SPY")
    last = pd.Timestamp(spy.index[-1]) if spy is not None and not spy.empty else None
    for symbol, frame in bars.items():
        if frame.empty:
            continue
        if last is not None and pd.Timestamp(frame.index[-1]) > last:
            opens[symbol] = float(frame["open"].iloc[-1])
        else:
            done = completed.get(symbol)
            if done is not None and not done.empty:
                opens[symbol] = float(done["close"].iloc[-1])
    return opens


def _session_date(ts) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York")
    return stamp.date()


def _finite(value) -> bool:
    try:
        return bool(np.isfinite(value))
    except TypeError:
        return False


def line_for(
    *,
    strategy: str,
    symbol: str,
    kind: str,
    quantity: float = 0.0,
    stop: Optional[float] = None,
    dry_run: bool = False,
    detail: str = "",
) -> str:
    """One status line. The action phrases are what a dry run prints."""
    prefix = f"{strategy} {symbol}: "
    if kind == "buy":
        verb = "would BUY" if dry_run else "sent BUY"
        return (
            f"{prefix}{verb} {symbol} qty {qty_text(quantity)} MARKET DAY "
            f"+ STOP_LOSS GTC @ {cents(stop or 0):.2f}"
        )
    if kind == "sell":
        verb = "would SELL" if dry_run else "sent SELL"
        return f"{prefix}{verb} {symbol} qty {qty_text(quantity)} MARKET DAY; cancel STOP_LOSS"
    if kind == "trail":
        verb = "would replace" if dry_run else "sent replace"
        return f"{prefix}{verb} STOP_LOSS {symbol} qty {qty_text(quantity)} GTC @ {cents(stop or 0):.2f}"
    if kind == "hold":
        return f"{prefix}no signal: {strategy} target {symbol} already held"
    if kind == "idle":
        return f"{prefix}outside rebalance"
    if kind == "flat":
        return f"{prefix}no signal: {strategy} {symbol}"
    if kind == "reject":
        return f"{prefix}no signal: {detail}"
    return f"{prefix}{kind}"


def forming_range(
    bars: dict[str, pd.DataFrame],
    symbol: str,
    now: datetime,
) -> tuple[Optional[float], Optional[float]]:
    """High and low of today's daily bar while the cash session is open.

    The close is not a finished signal yet. The high can raise the trail,
    and the low can stop the position out, which is how the backtest
    walks a completed bar.
    """
    frame = bars.get(symbol)
    if frame is None or frame.empty:
        return None, None
    last = pd.Timestamp(frame.index[-1])
    if _session_date(last) != now.date() or now.time() >= RTH_CLOSE:
        return None, None
    high = float(frame["high"].iloc[-1])
    low = float(frame["low"].iloc[-1])
    return (high if _finite(high) else None, low if _finite(low) else None)


def decide_stop(target: Held, bars: dict[str, pd.DataFrame], now: datetime, journal, strategy: str) -> StopDecision:
    """Peak and protective stop, including a high-water mark saved earlier."""
    entry_key = pd.Timestamp(target.entry_time).isoformat()
    peak = remembered_peak(journal, strategy, target.symbol, entry_key, target.peak)
    high, low = forming_range(bars, target.symbol, now)
    if high is not None:
        peak = max(peak, float(high))
    raw = float(target.stop)
    if target.trail_pct:
        trailed = peak * (1.0 - float(target.trail_pct))
        if trailed > raw:
            raw = trailed
    price = mark_price(bars, target.symbol)
    stopped = False
    if low is not None and float(low) <= raw:
        stopped = True
    if price is not None and price <= raw:
        stopped = True
    return StopDecision(peak=peak, stop=cents(raw), stopped=stopped, entry_key=entry_key)


def mark_price(bars: dict[str, pd.DataFrame], symbol: str) -> Optional[float]:
    frame = bars.get(symbol)
    if frame is None or frame.empty:
        return None
    close = float(frame["close"].iloc[-1])
    if not _finite(close) or close <= 0:
        return None
    return close


def protective_stop(orders, symbol: str):
    """Resting sell stop for this symbol, if the broker has one."""
    found = None
    for order in orders:
        if order.symbol != symbol or order.side != Side.SELL:
            continue
        if order.order_type != OrderType.STOP:
            continue
        found = order
    return found


def remembered_peak(journal, strategy: str, symbol: str, entry_key: str, replay_peak: float) -> float:
    stored = None
    getter = getattr(journal, "get_peak", None)
    if getter is not None and entry_key:
        stored = getter(strategy, symbol, entry_key)
    if stored is None:
        return float(replay_peak)
    return max(float(replay_peak), float(stored))


def remember_peak(journal, strategy: str, symbol: str, entry_key: str, peak: float, stop: float) -> None:
    saver = getattr(journal, "save_peak", None)
    if saver is None or not entry_key:
        return
    saver(strategy, symbol, entry_key, peak, stop)
