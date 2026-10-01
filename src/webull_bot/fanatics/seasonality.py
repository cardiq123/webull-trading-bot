"""Spec 8 and the daily-bar proxies of specs 1 and 4.

SPY and QQQ daily opens are the 09:30 cash open and the closes are the
16:00 cash close. That is the overnight-versus-regular-session split.
Yahoo futures daily bars are the full electronic session, so they are not
used as that split.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.fanatics.detectors import hammer, shooting_star
from webull_bot.fanatics.simulate import STARTING_EQUITY, Signal, simulate

COSTS = CostModel()


def _window(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    index = frame.index
    if getattr(index, "tz", None) is not None:
        index = index.tz_localize(None)
        frame = frame.copy()
        frame.index = index
    return frame[(frame.index >= start_ts) & (frame.index <= end_ts)]


def session_stats(frame: pd.DataFrame) -> dict[str, float]:
    """Mean overnight (prior close → open) and intraday (open → close) returns."""
    close = frame["close"].astype(float)
    open_ = frame["open"].astype(float)
    overnight = open_ / close.shift(1) - 1.0
    intraday = close / open_ - 1.0
    overnight = overnight.replace([np.inf, -np.inf], np.nan).dropna()
    intraday = intraday.replace([np.inf, -np.inf], np.nan).dropna()

    def pack(series: pd.Series) -> dict[str, float]:
        n = int(len(series))
        mean = float(series.mean()) if n else 0.0
        std = float(series.std(ddof=1)) if n > 1 else 0.0
        tstat = mean / (std / math.sqrt(n)) if std > 0 and n > 1 else 0.0
        return {"n": n, "mean": mean, "tstat": tstat}

    return {"overnight": pack(overnight), "intraday": pack(intraday)}


def _trade_overnight(cash: float, close_px: float, next_open: float, costs: CostModel) -> float:
    entry = buy_price(float(close_px), costs)
    if entry <= 0 or cash <= entry:
        return cash
    shares = int(cash // entry)
    if shares < 1:
        return cash
    exit_px = sell_price(float(next_open), costs)
    proceeds = shares * exit_px - sell_regulatory_fees(exit_px, shares, costs) - buy_fees(costs)
    leftover = cash - shares * entry
    return leftover + proceeds


def _trade_intraday(cash: float, open_px: float, close_px: float, costs: CostModel) -> float:
    entry = buy_price(float(open_px), costs)
    if entry <= 0 or cash <= entry:
        return cash
    shares = int(cash // entry)
    if shares < 1:
        return cash
    exit_px = sell_price(float(close_px), costs)
    proceeds = shares * exit_px - sell_regulatory_fees(exit_px, shares, costs) - buy_fees(costs)
    return cash - shares * entry + proceeds


def run_drift(
    frames: dict[str, pd.DataFrame],
    *,
    start: str,
    end: str,
    mode: str = "both",
    vix_max: float | None = None,
    vix_min: float | None = None,
    leg: str = "overnight",
    seed: int | None = None,
    costs: CostModel | None = None,
) -> tuple[dict, pd.DataFrame]:
    """Compound a fully invested overnight or intraday book. ``seed`` keeps a random half of days."""
    costs = costs or COSTS
    names = ["SPY", "QQQ"] if mode == "both" else [mode]
    pieces = []
    for name in names:
        frame = _window(frames[name], start, end)
        pieces.append(frame[["open", "close"]].rename(columns={"open": f"{name}_open", "close": f"{name}_close"}))
    book = pieces[0].join(pieces[1:], how="inner") if len(pieces) > 1 else pieces[0]
    if "VIX" in frames or "^VIX" in frames:
        vix = frames.get("^VIX", frames.get("VIX"))
        vix = _window(vix, start, end)["close"].rename("vix")
        book = book.join(vix, how="left")
    book = book.dropna(subset=[column for column in book.columns if column.endswith("_close") or column.endswith("_open")])
    rng = np.random.default_rng(seed) if seed is not None else None
    equity = STARTING_EQUITY
    rows = []
    closes = {name: book[f"{name}_close"].to_numpy(dtype=float) for name in names}
    opens = {name: book[f"{name}_open"].to_numpy(dtype=float) for name in names}
    vix_values = book["vix"].to_numpy(dtype=float) if "vix" in book.columns else None
    for i in range(len(book) - 1):
        vix_i = i if leg == "overnight" else i - 1
        if vix_values is not None and vix_i >= 0 and np.isfinite(vix_values[vix_i]):
            if vix_max is not None and vix_values[vix_i] >= vix_max:
                rows.append({"exit_time": book.index[i + 1], "pnl": 0.0, "r": 0.0, "taken": False})
                continue
            if vix_min is not None and vix_values[vix_i] < vix_min:
                rows.append({"exit_time": book.index[i + 1], "pnl": 0.0, "r": 0.0, "taken": False})
                continue
        if rng is not None and rng.random() >= 0.5:
            rows.append({"exit_time": book.index[i + 1], "pnl": 0.0, "r": 0.0, "taken": False})
            continue
        before = equity
        sleeve = equity / len(names)
        after = 0.0
        for name in names:
            if leg == "overnight":
                after += _trade_overnight(sleeve, closes[name][i], opens[name][i + 1], costs)
            else:
                after += _trade_intraday(sleeve, opens[name][i], closes[name][i], costs)
        equity = after
        pnl = equity - before
        rows.append(
            {
                "exit_time": book.index[i + 1] if leg == "overnight" else book.index[i],
                "pnl": pnl,
                "r": pnl / before if before else 0.0,
                "taken": True,
            }
        )
    trades = pd.DataFrame(rows)
    taken = trades[trades["taken"]] if len(trades) else trades
    if taken.empty:
        metrics = compute_metrics(
            BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
            STARTING_EQUITY,
        )
        metrics["avg_r"] = 0.0
        return metrics, trades
    equity_curve = STARTING_EQUITY + taken["pnl"].cumsum()
    equity_curve.index = pd.to_datetime(taken["exit_time"])
    # Flat days stay in the curve because skipped days are absent; reindex to
    # every session so Sharpe counts the zeros.
    calendar = pd.DatetimeIndex(book.index).tz_localize(None) if getattr(book.index, "tz", None) else pd.DatetimeIndex(book.index)
    equity_curve = equity_curve.groupby(equity_curve.index.normalize()).last()
    equity_curve = equity_curve.reindex(calendar.normalize().unique()).ffill().fillna(STARTING_EQUITY)
    exposure = pd.Series(1.0 if leg == "overnight" else 6.5 / 24, index=equity_curve.index)
    result = BacktestResult(
        equity=equity_curve,
        exposure=exposure,
        trades=taken.rename(columns={"r": "r"})[["pnl"]].assign(pnl=taken["pnl"].to_numpy()),
        ending_equity=float(equity_curve.iloc[-1]),
    )
    # compute_metrics needs a pnl column, which we have. avg_r is the mean taken-day return.
    metrics = compute_metrics(result, STARTING_EQUITY)
    metrics["avg_r"] = float(taken["r"].mean())
    metrics["trades"] = int(taken["taken"].sum()) if "taken" in taken else int(len(taken))
    return metrics, trades


def crash_and_vix_splits(frames: dict[str, pd.DataFrame]) -> dict[str, dict]:
    """Descriptive splits. These are not a parameter search."""
    out = {}
    spy = frames["SPY"]
    stats = session_stats(spy)
    out["spy_full"] = stats
    if "QQQ" in frames:
        out["qqq_full"] = session_stats(frames["QQQ"])
    for year in (2008, 2020, 2022):
        chunk = spy[spy.index.year == year]
        if len(chunk):
            out[f"spy_{year}"] = session_stats(chunk)
    vix = frames.get("^VIX")
    if vix is not None:
        joined = spy.join(vix["close"].rename("vix"), how="inner")
        low = joined[joined["vix"] < 20]
        high = joined[joined["vix"] >= 20]
        out["spy_vix_below_20"] = session_stats(low)
        out["spy_vix_at_least_20"] = session_stats(high)
    return out


def proxy_signals(frame: pd.DataFrame, symbol: str, kind: str) -> list[Signal]:
    """Daily proxy. ``reclaim`` is spec 1. ``reject`` is spec 4. Not the intraday rule."""
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    open_ = frame["open"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float) if "volume" in frame else np.ones(len(frame))
    star = shooting_star(open_, high, low, close)
    pin = hammer(open_, high, low, close)
    signals = []
    for i in range(1, len(frame) - 6):
        if kind == "reclaim" and low[i] < low[i - 1] and close[i] > low[i - 1]:
            stop = low[i]
            target = high[i - 1]
            risk = close[i] - stop
            if risk <= 0 or (target - close[i]) / risk < 2:
                continue
            signals.append(Signal(symbol, 1, i, float(stop), float(target), i + 5, window=(0, 1)))
        if kind == "reject" and high[i] > high[i - 1] and close[i] < high[i - 1] and star[i] and volume[i] > volume[i - 1]:
            stop = high[i]
            target = low[i - 1]
            risk = stop - close[i]
            if risk <= 0 or (close[i] - target) / risk < 1.5:
                continue
            signals.append(Signal(symbol, -1, i, float(stop), float(target), i + 5, window=(0, 1)))
        if kind == "reject" and low[i] < low[i - 1] and close[i] > low[i - 1] and pin[i] and volume[i] > volume[i - 1]:
            stop = low[i]
            target = high[i - 1]
            risk = close[i] - stop
            if risk <= 0 or (target - close[i]) / risk < 1.5:
                continue
            signals.append(Signal(symbol, 1, i, float(stop), float(target), i + 5, window=(0, 1)))
    return signals


def _in_window(view: pd.DataFrame, signal: Signal, start: str, end: str) -> bool:
    stamp = str(view.index[signal.signal_loc].date())
    return start <= stamp <= end


def random_proxy_signals(view: pd.DataFrame, symbol: str, kind: str, start: str, end: str, seed: int = 7) -> list[Signal]:
    """Same count, risk distance, reward distance, and hold, on random days and sides."""
    real = [signal for signal in proxy_signals(view, symbol, kind) if _in_window(view, signal, start, end)]
    if not real:
        return []
    rng = np.random.default_rng(seed)
    close = view["close"].to_numpy(dtype=float)
    eligible = [i for i in range(1, len(view) - 6) if start <= str(view.index[i].date()) <= end]
    if not eligible:
        return []
    out = []
    for signal in real:
        loc = int(rng.choice(eligible))
        side = int(rng.choice(np.array([-1, 1])))
        anchor = float(close[signal.signal_loc])
        risk = abs(anchor - signal.stop)
        reward = abs(signal.target - anchor)
        if risk <= 0 or not np.isfinite(close[loc]):
            continue
        out.append(
            Signal(
                symbol,
                side,
                loc,
                float(close[loc] - side * risk),
                float(close[loc] + side * reward),
                loc + 5,
                window=(0, 1),
            )
        )
    return out


def run_proxy(frame: pd.DataFrame, symbol: str, kind: str, start: str, end: str, *, costs: CostModel | None = None, signals: list[Signal] | None = None):
    view = frame.copy()
    if getattr(view.index, "tz", None) is not None:
        view.index = view.index.tz_localize(None)
    if signals is None:
        signals = [signal for signal in proxy_signals(view, symbol, kind) if _in_window(view, signal, start, end)]
    else:
        signals = [signal for signal in signals if signal.signal_loc < len(view) and _in_window(view, signal, start, end)]
    bars = {symbol: view}
    calendar = view[(view.index >= pd.Timestamp(start)) & (view.index <= pd.Timestamp(end))].index
    _result, trades = simulate(
        bars,
        signals,
        risk=0.005,
        etf=True,
        max_trades_per_day=1,
        max_consecutive_losses=99,
        day_loss_r=99,
        day_win_r=99,
        calendar=calendar,
        costs=costs,
    )
    from webull_bot.backtest.metrics import compute_metrics as metrics_of

    metrics = metrics_of(_result, STARTING_EQUITY)
    metrics["avg_r"] = float(trades["r"].mean()) if len(trades) else 0.0
    return metrics, trades, _result
