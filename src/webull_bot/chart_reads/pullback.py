"""Strong-trend pullback continuation. Rules are frozen before any score.

Nothing in this module places an order or imports the sandbox forward test.

Trend, all required on the signal bar and the bar before it. Short is the
mirror.

* EMA 9 is above EMA 20, and EMA 20 is above EMA 50.
* Each of those three averages is higher than it was 3 bars ago.
* The close is above the 200 EMA and above VWAP. Intraday VWAP is the
  session VWAP. Daily bars have no session, so VWAP there is the
  20-session volume-weighted typical price.
* ADX(14) is above 25, or the last two confirmed swing highs and swing
  lows are both rising. A swing is a unique 5-bar fractal, stored on the
  bar that confirms it, so bar t does not use a pivot that is still open.

Entry, long. The bar pulls into the 9 EMA, the 20 EMA, session or rolling
VWAP, or the previous swing low, within 0.25 ATR, and the close holds that
level. The low does not break the previous swing low (a touch of it is
allowed). The bar closes up from its open and up from the prior close.
The previous bar was not already an entry. The fill is the next bar's
open. An intraday signal whose next bar is a new session is dropped.

The option is the listed strike nearest the spot, so delta is about 0.50.
Calls in an uptrend, puts in a downtrend. The default is 14 calendar days.
7 and 30 are sensitivities, not a search. The exit that this study reports
as the result is a limit at +15% of the entry ask and a stop at -30% of
that ask. A limit fills at the limit. A stop that gaps through fills at
the open bid. If the same bar trades through both, the stop fills. Expiry
flattens at the close of the expiry session. The other exits, +20%/-20%,
+15%/-15%, and a time stop after 16 bars on 15-minute, 8 bars on 60-minute,
or 5 bars on daily, are reported and are not used to pick a winner.

Before costs the +15%/-30% break-even win rate is 30 / 45. The report
compares the realized win rate with the break-even rate implied by the
average win and average loss after spreads and fees.

The $1,000 book buys two contracts when that debit fits in $1,000 and in
current equity, otherwise one, and it skips a debit above $1,000. It uses
the same legacy pattern-day-trader count as the other option studies. The
sized book is one contract. Its equity is the training median that puts
the -30% loss near 2% of the account, and the holdout uses that equity.
The share control uses the same entries, a stop at the swing, a 1.5R
target, and the same bar count as a time stop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.simulate import (
    DIVIDEND,
    RATE,
    _buy,
    _option_bid,
    _session,
    _vol,
    _years,
)
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.indicators import atr, ema
from webull_bot.mtf_vwap.detect import rth, session_vwap
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_delta, option_price
from webull_bot.risk.pdt import check_day_trade

EMA_FAST = 9
EMA_MID = 20
EMA_SLOW = 50
EMA_TREND = 200
RISE_BARS = 3
ADX_WINDOW = 14
ADX_MIN = 25.0
SWING_BARS = 5
TOUCH_ATR = 0.25
VWAP_WINDOW = 20
IV_PREMIUM = 1.15
SPREAD_MULTIPLIER = 1.0
PRIMARY_TARGET = 0.15
PRIMARY_STOP = -0.30
DTE_DEFAULT = 14
DTE_SENSITIVITIES = (7, 30)
EXIT_SENSITIVITIES = (
    ("+20%/-20%", 0.20, -0.20, None),
    ("+15%/-15%", 0.15, -0.15, None),
)
TIME_BARS = {"15m": 16, "60m": 8, "1d": 5}
SHARE_R = 1.5
CASH_ACCOUNT = 1_000.0
RISK_FRACTION = 0.02
MAX_CONTRACTS = 2
SEED = 17
NY = "America/New_York"
_OPEN = time(9, 30)
_CLOSE = time(16, 0)


def frozen_rules() -> dict:
    """The definition that is written down before the holdout is scored."""
    return {
        "trend": "EMA 9 > 20 > 50, each rising over 3 bars, close above the 200 EMA and VWAP, and ADX(14) > 25 or higher highs and higher lows",
        "touch_atr": TOUCH_ATR,
        "swing_bars": SWING_BARS,
        "adx_min": ADX_MIN,
        "primary_target": PRIMARY_TARGET,
        "primary_stop": PRIMARY_STOP,
        "breakeven_before_costs": theoretical_breakeven(PRIMARY_TARGET, PRIMARY_STOP),
        "dte": DTE_DEFAULT,
        "dte_sensitivities": list(DTE_SENSITIVITIES),
        "exit_sensitivities": [name for name, *_rest in EXIT_SENSITIVITIES],
        "time_bars": dict(TIME_BARS),
        "share_r": SHARE_R,
        "cash_account": CASH_ACCOUNT,
        "max_contracts": MAX_CONTRACTS,
        "risk_fraction": RISK_FRACTION,
        "iv_premium": IV_PREMIUM,
        "seed": SEED,
    }


def theoretical_breakeven(target: float, stop: float) -> float:
    """Win rate that breaks even when a win pays ``target`` and a loss pays ``stop``."""
    win = float(target)
    loss = abs(float(stop))
    if win <= 0.0 or loss <= 0.0:
        raise ValueError("target and stop must be non-zero")
    return loss / (win + loss)


def after_cost_breakeven(average_win: float, average_loss: float) -> Optional[float]:
    """Break-even win rate from the realized average win and average loss.

    ``average_loss`` is negative, the way the metrics helper stores it.
    Scratch trades are not part of either average.
    """
    win = float(average_win)
    loss = abs(float(average_loss))
    if win <= 0.0 and loss <= 0.0:
        return None
    if win + loss <= 0.0:
        return None
    return loss / (win + loss)


def atm_strike(spot: float) -> float:
    """Listed strike nearest the spot. The same rounding the rest of the bot uses."""
    return float(listed_strike(spot, spot))


def lot_debit(ask: float, contracts: int) -> float:
    premium = float(ask) * CONTRACT_MULTIPLIER * int(contracts)
    return premium + option_leg_fees(int(contracts), float(ask), sell=False)


def choose_contracts(ask: float, equity: float, mode: str) -> int:
    """Cash buys 1 or 2. Sized buys 1. A debit above the cap is zero."""
    if not np.isfinite(ask) or ask <= 0.0 or equity <= 0.0:
        return 0
    if mode == "sized":
        return 1 if lot_debit(ask, 1) <= float(equity) + 1e-9 else 0
    if mode != "cash":
        raise ValueError("mode must be cash or sized")
    cap = min(float(equity), CASH_ACCOUNT)
    if lot_debit(ask, 2) <= cap + 1e-9:
        return 2
    if lot_debit(ask, 1) <= cap + 1e-9:
        return 1
    return 0


def capital_for_stop(ask: float, stop: float = PRIMARY_STOP) -> float:
    """Equity that puts one contract's premium-stop loss near 2% of the account."""
    debit = lot_debit(ask, 1)
    exit_px = max(0.0, float(ask) * (1.0 + float(stop)))
    fees = option_leg_fees(1, exit_px, sell=True)
    credit = max(0.0, exit_px * CONTRACT_MULTIPLIER - fees)
    risk = max(0.0, debit - credit)
    return max(debit, risk / RISK_FRACTION)


def qualifies_long(
    *,
    stack: bool,
    rising: bool,
    above: bool,
    adx: float,
    higher_structure: bool,
    low: float,
    close: float,
    open_: float,
    prev_close: float,
    width: float,
    swing: float,
    vwap: float,
    ema_fast: float,
    ema_mid: float,
) -> bool:
    """One long bar. The caller also requires the previous bar to be a trend and not an entry."""
    if not (stack and rising and above):
        return False
    if not (np.isfinite(adx) and adx > ADX_MIN) and not higher_structure:
        return False
    if not all(np.isfinite(value) for value in (low, close, open_, prev_close, width, swing)):
        return False
    if width <= 0.0 or low < swing:
        return False
    if not (close > open_ and close > prev_close):
        return False
    return _touched(low, close, width, (vwap, ema_fast, ema_mid, swing), hold="above")


def qualifies_short(
    *,
    stack: bool,
    falling: bool,
    below: bool,
    adx: float,
    lower_structure: bool,
    high: float,
    close: float,
    open_: float,
    prev_close: float,
    width: float,
    swing: float,
    vwap: float,
    ema_fast: float,
    ema_mid: float,
) -> bool:
    if not (stack and falling and below):
        return False
    if not (np.isfinite(adx) and adx > ADX_MIN) and not lower_structure:
        return False
    if not all(np.isfinite(value) for value in (high, close, open_, prev_close, width, swing)):
        return False
    if width <= 0.0 or high > swing:
        return False
    if not (close < open_ and close < prev_close):
        return False
    return _touched(high, close, width, (vwap, ema_fast, ema_mid, swing), hold="below")


def _touched(extreme: float, close: float, width: float, levels, *, hold: str) -> bool:
    band = TOUCH_ATR * width
    for level in levels:
        if not np.isfinite(level):
            continue
        if extreme > level + band or extreme < level - band:
            continue
        if hold == "above" and close + 1e-12 >= level:
            return True
        if hold == "below" and close - 1e-12 <= level:
            return True
    return False


def _adx(frame: pd.DataFrame) -> pd.Series:
    """Wilder ADX. The smoothing matches ``atr`` in this repo."""
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=frame.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=frame.index)
    span = atr(frame, ADX_WINDOW).replace(0.0, np.nan)
    alpha = 1.0 / ADX_WINDOW
    plus_di = 100.0 * plus_dm.ewm(alpha=alpha, adjust=False, min_periods=ADX_WINDOW).mean() / span
    minus_di = 100.0 * minus_dm.ewm(alpha=alpha, adjust=False, min_periods=ADX_WINDOW).mean() / span
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=alpha, adjust=False, min_periods=ADX_WINDOW).mean()


def _swings(high: np.ndarray, low: np.ndarray, width: int):
    count = len(high)
    last_low = np.full(count, np.nan)
    prev_low = np.full(count, np.nan)
    last_high = np.full(count, np.nan)
    prev_high = np.full(count, np.nan)
    lows: list[float] = []
    highs: list[float] = []
    for index in range(count):
        confirm = index - width
        if confirm >= width:
            start = confirm - width
            stop = confirm + width + 1
            window_low = low[start:stop]
            window_high = high[start:stop]
            if low[confirm] == window_low.min() and np.sum(window_low == low[confirm]) == 1:
                lows.append(float(low[confirm]))
            if high[confirm] == window_high.max() and np.sum(window_high == high[confirm]) == 1:
                highs.append(float(high[confirm]))
        if lows:
            last_low[index] = lows[-1]
            if len(lows) >= 2:
                prev_low[index] = lows[-2]
        if highs:
            last_high[index] = highs[-1]
            if len(highs) >= 2:
                prev_high[index] = highs[-2]
    higher = (last_high > prev_high) & (last_low > prev_low)
    lower = (last_high < prev_high) & (last_low < prev_low)
    return last_low, last_high, higher, lower


def _rolling_vwap(frame: pd.DataFrame) -> pd.Series:
    typical = (frame["high"].astype(float) + frame["low"].astype(float) + frame["close"].astype(float)) / 3.0
    volume = frame["volume"].astype(float).clip(lower=0.0)
    volume = volume.where(volume > 0.0, 1.0)
    traded = (typical * volume).rolling(VWAP_WINDOW, min_periods=VWAP_WINDOW).sum()
    weight = volume.rolling(VWAP_WINDOW, min_periods=VWAP_WINDOW).sum()
    return traded / weight


def _day(stamp) -> date:
    return _session(pd.Timestamp(stamp))


def find_pullbacks(frame: pd.DataFrame, symbol: str, clock: str) -> list[Setup]:
    """Causal signals. ``clock`` is ``15m``, ``60m``, or ``1d``."""
    if clock not in TIME_BARS:
        raise ValueError("clock must be 15m, 60m, or 1d")
    if frame is None or frame.empty:
        return []
    bars = rth(frame) if clock != "1d" else frame.sort_index()
    if len(bars) < EMA_TREND + RISE_BARS + 2:
        return []
    if clock == "1d":
        vwap = _rolling_vwap(bars)
    else:
        try:
            vwap = session_vwap(bars)["vwap"].reindex(bars.index)
        except (KeyError, TypeError, ValueError):
            return []
    close = bars["close"].astype(float)
    open_ = bars["open"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    fast = ema(close, EMA_FAST)
    mid = ema(close, EMA_MID)
    slow = ema(close, EMA_SLOW)
    trend = ema(close, EMA_TREND)
    width = atr(bars, ADX_WINDOW)
    directional = _adx(bars)
    swing_low, swing_high, higher, lower = _swings(high.to_numpy(), low.to_numpy(), SWING_BARS)
    stack_long = (fast > mid) & (mid > slow)
    rising = (fast > fast.shift(RISE_BARS)) & (mid > mid.shift(RISE_BARS)) & (slow > slow.shift(RISE_BARS))
    above = (close > trend) & (close > vwap)
    stack_short = (fast < mid) & (mid < slow)
    falling = (fast < fast.shift(RISE_BARS)) & (mid < mid.shift(RISE_BARS)) & (slow < slow.shift(RISE_BARS))
    below = (close < trend) & (close < vwap)
    adx_ok = directional > ADX_MIN
    strong_long = (stack_long & rising & above & (adx_ok | pd.Series(higher, index=bars.index))).fillna(False)
    strong_short = (stack_short & falling & below & (adx_ok | pd.Series(lower, index=bars.index))).fillna(False)
    band = TOUCH_ATR * width
    hold_low = low.to_numpy() >= swing_low
    hold_high = high.to_numpy() <= swing_high

    def _touch_row(extreme: pd.Series, level: pd.Series, hold: str) -> pd.Series:
        near = (extreme <= level + band) & (extreme >= level - band)
        if hold == "above":
            return near & (close >= level)
        return near & (close <= level)

    swing_low_s = pd.Series(swing_low, index=bars.index)
    swing_high_s = pd.Series(swing_high, index=bars.index)
    touched_long = (
        _touch_row(low, vwap, "above")
        | _touch_row(low, fast, "above")
        | _touch_row(low, mid, "above")
        | _touch_row(low, swing_low_s, "above")
    )
    touched_short = (
        _touch_row(high, vwap, "below")
        | _touch_row(high, fast, "below")
        | _touch_row(high, mid, "below")
        | _touch_row(high, swing_high_s, "below")
    )
    bull = (close > open_) & (close > close.shift(1))
    bear = (close < open_) & (close < close.shift(1))
    long_entry = (strong_long & strong_long.shift(1).fillna(False) & touched_long & bull & pd.Series(hold_low, index=bars.index)).fillna(False)
    short_entry = (strong_short & strong_short.shift(1).fillna(False) & touched_short & bear & pd.Series(hold_high, index=bars.index)).fillna(False)
    long_signal = long_entry & ~long_entry.shift(1).fillna(False)
    short_signal = short_entry & ~short_entry.shift(1).fillna(False)
    index = bars.index
    found: list[Setup] = []
    for direction, mask, swing, levels in (
        ("long", long_signal, swing_low, (vwap, fast, mid, swing_low_s)),
        ("short", short_signal, swing_high, (vwap, fast, mid, swing_high_s)),
    ):
        for pos in np.flatnonzero(mask.to_numpy()):
            nxt = int(pos) + 1
            if nxt >= len(bars):
                continue
            if clock != "1d" and _day(index[pos]) != _day(index[nxt]):
                continue
            level_values = []
            extreme = float(low.iloc[pos] if direction == "long" else high.iloc[pos])
            closed = float(close.iloc[pos])
            span = float(width.iloc[pos])
            for series in levels:
                level = float(series.iloc[pos])
                if _touched(extreme, closed, span, (level,), hold="above" if direction == "long" else "below"):
                    level_values.append(level)
            if not level_values or not np.isfinite(span):
                continue
            reference = min(level_values, key=lambda level: abs(closed - level))
            found.append(
                Setup(
                    symbol=symbol,
                    direction=direction,
                    kind="trend_pullback",
                    signal_time=pd.Timestamp(index[pos]),
                    fill_time=pd.Timestamp(index[nxt]),
                    anchor_time=pd.Timestamp(index[pos]),
                    stop=float(swing[pos]),
                    atr=float(span),
                    reference=float(reference),
                )
            )
    found.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    return found


@dataclass
class PremiumPath:
    symbol: str
    direction: str
    fill: pd.Timestamp
    fill_date: date
    signal_date: date
    ok: bool
    ask: float = 0.0
    delta: float = 0.0
    strike: float = 0.0
    right: str = ""
    expiry: Optional[date] = None
    open_bid: Optional[np.ndarray] = None
    adverse_bid: Optional[np.ndarray] = None
    favorable_bid: Optional[np.ndarray] = None
    close_bid: Optional[np.ndarray] = None
    expired: Optional[np.ndarray] = None
    stamps: Optional[list] = None


def _stamp_on(day: date, clock: time) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(day, clock), tz=NY)


def _blank(setup: Setup) -> PremiumPath:
    fill = pd.Timestamp(setup.fill_time)
    return PremiumPath(
        symbol=str(setup.symbol),
        direction=str(setup.direction),
        fill=fill,
        fill_date=_day(fill),
        signal_date=_day(setup.signal_time),
        ok=False,
    )


def price_paths(
    setups: list[Setup],
    frames: dict[str, pd.DataFrame],
    realized: dict[str, pd.Series],
    dte: int,
    clock: str,
) -> list[PremiumPath]:
    """Black-Scholes bids for the nearest strike. A missing vol or bar is not a trade."""
    params = {"spread_multiplier": SPREAD_MULTIPLIER}
    paths: list[PremiumPath] = []
    total = len(setups)
    for count, setup in enumerate(setups, start=1):
        if count % 400 == 0 or count == total:
            print(f"    priced {count}/{total}", flush=True)
        frame = frames.get(setup.symbol)
        fill = pd.Timestamp(setup.fill_time)
        if frame is None or fill not in frame.index:
            paths.append(_blank(setup))
            continue
        row = frame.loc[fill]
        try:
            spot = float(row["open"])
        except (TypeError, ValueError, KeyError):
            paths.append(_blank(setup))
            continue
        if not np.isfinite(spot) or spot <= 0.0:
            paths.append(_blank(setup))
            continue
        fill_date = _day(fill)
        sigma = _vol(realized.get(setup.symbol, pd.Series(dtype=float)), fill_date, IV_PREMIUM)
        if sigma is None:
            paths.append(_blank(setup))
            continue
        entry_stamp = _stamp_on(fill_date, _OPEN) if clock == "1d" else fill
        years = _years(int(dte), entry_stamp)
        right = "call" if setup.direction == "long" else "put"
        strike = atm_strike(spot)
        mid = option_price(right, spot, strike, years, sigma, RATE, DIVIDEND)
        delta = option_delta(right, spot, strike, years, sigma, RATE, DIVIDEND)
        ask = _buy(mid, delta, SPREAD_MULTIPLIER)
        if not np.isfinite(ask) or ask <= 0.0:
            paths.append(_blank(setup))
            continue
        opened = {
            "right": right,
            "strike": strike,
            "sigma": sigma,
            "expiry_years": years,
            "entry_time": entry_stamp,
            "direction": setup.direction,
        }
        start = frame.index.get_loc(fill)
        if isinstance(start, slice):
            start = start.start
        if isinstance(start, np.ndarray):
            start = int(start[0])
        expiry = fill_date + timedelta(days=int(dte))
        stamps: list[pd.Timestamp] = []
        opens: list[float] = []
        adverses: list[float] = []
        favorables: list[float] = []
        closes: list[float] = []
        expired_flags: list[bool] = []
        mark_stamps: list[pd.Timestamp] = []
        open_stamps: list[pd.Timestamp] = []
        index = frame.index
        for offset, (ts, bar) in enumerate(frame.iloc[int(start) :].iterrows()):
            ts = pd.Timestamp(ts)
            try:
                open_px = float(bar["open"])
                high_px = float(bar["high"])
                low_px = float(bar["low"])
                close_px = float(bar["close"])
            except (TypeError, ValueError, KeyError):
                continue
            if not all(np.isfinite(value) and value > 0.0 for value in (open_px, high_px, low_px, close_px)):
                continue
            session = _day(ts)
            if setup.direction == "long":
                adverse, favorable = low_px, high_px
            else:
                adverse, favorable = high_px, low_px
            loc = int(start) + offset
            last = loc >= len(index) - 1 or _day(index[loc + 1]) != session
            if clock == "1d":
                open_at = _stamp_on(session, _OPEN)
                close_at = _stamp_on(session, _CLOSE)
            else:
                open_at = ts
                close_at = ts
            stamps.append(ts)
            opens.append(open_px)
            adverses.append(adverse)
            favorables.append(favorable)
            closes.append(close_px)
            open_stamps.append(open_at)
            mark_stamps.append(close_at)
            expired_flags.append(bool(session >= expiry and last))
            if expired_flags[-1]:
                break
        if not stamps:
            paths.append(_blank(setup))
            continue
        open_bid = np.empty(len(stamps))
        adverse_bid = np.empty(len(stamps))
        favorable_bid = np.empty(len(stamps))
        close_bid = np.empty(len(stamps))
        for index_bar, stamp in enumerate(stamps):
            open_bid[index_bar] = _option_bid(opened, open_stamps[index_bar], opens[index_bar], params)
            adverse_bid[index_bar] = _option_bid(opened, mark_stamps[index_bar], adverses[index_bar], params)
            favorable_bid[index_bar] = _option_bid(opened, mark_stamps[index_bar], favorables[index_bar], params)
            close_bid[index_bar] = _option_bid(opened, mark_stamps[index_bar], closes[index_bar], params)
        paths.append(
            PremiumPath(
                symbol=str(setup.symbol),
                direction=str(setup.direction),
                fill=fill,
                fill_date=fill_date,
                signal_date=_day(setup.signal_time),
                ok=True,
                ask=float(ask),
                delta=float(delta),
                strike=float(strike),
                right=right,
                expiry=expiry,
                open_bid=open_bid,
                adverse_bid=adverse_bid,
                favorable_bid=favorable_bid,
                close_bid=close_bid,
                expired=np.asarray(expired_flags, dtype=bool),
                stamps=stamps,
            )
        )
    return paths


def replay_exit(
    path: PremiumPath,
    target: Optional[float],
    stop: float,
    time_bars: Optional[int],
) -> tuple[float, str, int]:
    """Premium exit. The stop is checked before the target on the same bar."""
    if not path.ok or path.adverse_bid is None or path.ask <= 0.0:
        raise ValueError("path is not priced")
    stop_px = float(path.ask) * (1.0 + float(stop))
    target_px = None if target is None else float(path.ask) * (1.0 + float(target))
    count = len(path.adverse_bid)
    for index in range(count):
        open_bid = float(path.open_bid[index])
        adverse = float(path.adverse_bid[index])
        favorable = float(path.favorable_bid[index])
        if open_bid <= stop_px:
            return open_bid, "stop", index
        if adverse <= stop_px:
            return stop_px, "stop", index
        if target_px is not None and favorable >= target_px:
            return target_px, "target", index
        if time_bars is not None and (index + 1) >= int(time_bars):
            return float(path.close_bid[index]), "time", index
        if path.expired is not None and bool(path.expired[index]):
            return float(path.close_bid[index]), "expiry", index
    return float(path.close_bid[-1]), "window", count - 1


def _credit(contracts: int, price: float) -> float:
    fees = option_leg_fees(contracts, max(price, 0.0), sell=True)
    return max(0.0, contracts * max(price, 0.0) * CONTRACT_MULTIPLIER - fees)


def _empty_book(starting: float, before: Optional[float]) -> dict:
    metrics = compute_metrics(
        BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
        starting,
    )
    return _pack(metrics, before, [], 0, 0, 0, {}, starting)


def _pack(metrics, before, trades, skipped, blocked, overlapped, reasons, starting) -> dict:
    after = after_cost_breakeven(float(metrics.get("avg_win") or 0.0), float(metrics.get("avg_loss") or 0.0))
    trades_n = int(metrics.get("trades") or 0)
    win_rate = float(metrics.get("win_rate") or 0.0)
    clears = bool(trades_n > 0 and after is not None and win_rate > after)
    ending = float(metrics.get("ending_equity") or starting)
    expectancy = float(metrics.get("expectancy") or 0.0)
    profitable = bool(trades_n > 0 and expectancy > 0.0 and ending > float(starting))
    deltas = [float(row["delta"]) for row in trades if np.isfinite(row.get("delta", np.nan))]
    return {
        "metrics": metrics,
        "breakeven_before": before,
        "breakeven_after": after,
        "clears_breakeven": clears,
        "profitable": profitable,
        "skipped": int(skipped),
        "pdt_blocked": int(blocked),
        "overlapped": int(overlapped),
        "reasons": reasons,
        "trades": trades,
        "median_delta": float(np.median(deltas)) if deltas else float("nan"),
        "starting_equity": float(starting),
    }


def simulate_premium(
    paths: list[PremiumPath],
    *,
    target: Optional[float],
    stop: float,
    time_bars: Optional[int],
    starting_equity: float,
    mode: str,
    pdt: bool,
) -> dict:
    """One account, one position. Equity resets with the caller."""
    before = theoretical_breakeven(target, stop) if target is not None and stop < 0 else None
    if starting_equity <= 0.0:
        return _empty_book(starting_equity, before)
    ordered = sorted(paths, key=lambda path: (path.fill, path.symbol, path.direction))
    cash = float(starting_equity)
    busy: Optional[pd.Timestamp] = None
    day_trades: list[date] = []
    trades: list[dict] = []
    skipped = 0
    blocked = 0
    overlapped = 0
    reasons: dict[str, int] = {}
    curve_stamps: list[pd.Timestamp] = []
    curve_eq: list[float] = []
    for path in ordered:
        if busy is not None and path.fill <= busy:
            overlapped += 1
            continue
        if pdt:
            decision = check_day_trade(
                as_of=path.fill_date,
                equity=cash,
                trade_days=day_trades,
                opening_same_day=True,
                account_type="margin",
                mode="on",
            )
            if not decision.allowed:
                blocked += 1
                continue
        if not path.ok:
            skipped += 1
            continue
        contracts = choose_contracts(path.ask, cash, mode)
        if contracts < 1:
            skipped += 1
            continue
        debit = lot_debit(path.ask, contracts)
        if debit > cash + 1e-9:
            skipped += 1
            continue
        exit_px, reason, exit_index = replay_exit(path, target, stop, time_bars)
        cash -= debit
        stamps = path.stamps or [path.fill]
        for mark_at in range(exit_index):
            marked = _credit(contracts, float(path.close_bid[mark_at]))
            curve_stamps.append(pd.Timestamp(stamps[mark_at]))
            curve_eq.append(cash + marked)
        credit = _credit(contracts, exit_px)
        cash += credit
        exit_time = pd.Timestamp(stamps[min(exit_index, len(stamps) - 1)])
        curve_stamps.append(exit_time)
        curve_eq.append(cash)
        busy = exit_time
        pnl = credit - debit
        if _day(exit_time) == path.fill_date:
            day_trades.append(path.fill_date)
        reasons[reason] = reasons.get(reason, 0) + 1
        trades.append(
            {
                "symbol": path.symbol,
                "direction": path.direction,
                "pnl": pnl,
                "debit": debit,
                "delta": abs(float(path.delta)),
                "reason": reason,
                "contracts": contracts,
                "fill": path.fill_date.isoformat(),
            }
        )
    equity = pd.Series(curve_eq, index=pd.DatetimeIndex(curve_stamps)) if curve_eq else pd.Series(dtype=float)
    exposure = pd.Series(np.ones(len(equity)), index=equity.index) if len(equity) else pd.Series(dtype=float)
    frame = pd.DataFrame(trades)
    metrics = compute_metrics(BacktestResult(equity, exposure, frame), float(starting_equity))
    return _pack(metrics, before, trades, skipped, blocked, overlapped, reasons, float(starting_equity))


def sized_equity(paths: list[PremiumPath], stop: float = PRIMARY_STOP) -> float:
    required = [capital_for_stop(path.ask, stop) for path in paths if path.ok and path.ask > 0.0]
    if not required:
        return float("nan")
    return float(np.median(required))


def simulate_shares(
    setups: list[Setup],
    frames: dict[str, pd.DataFrame],
    *,
    clock: str,
    starting_equity: float,
    pdt: bool,
    costs: CostModel | None = None,
) -> dict:
    """Same entries. Stop at the swing, target at 1.5R, then the clock's bar count."""
    model = costs or CostModel()
    time_bars = TIME_BARS[clock]
    ordered = sorted(setups, key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    cash = float(starting_equity)
    busy: Optional[pd.Timestamp] = None
    day_trades: list[date] = []
    trades: list[dict] = []
    skipped = 0
    blocked = 0
    overlapped = 0
    reasons: dict[str, int] = {}
    curve_stamps: list[pd.Timestamp] = []
    curve_eq: list[float] = []
    for setup in ordered:
        fill = pd.Timestamp(setup.fill_time)
        if busy is not None and fill <= busy:
            overlapped += 1
            continue
        fill_date = _day(fill)
        if pdt:
            decision = check_day_trade(
                as_of=fill_date,
                equity=cash,
                trade_days=day_trades,
                opening_same_day=True,
                account_type="margin",
                mode="on",
            )
            if not decision.allowed:
                blocked += 1
                continue
        frame = frames.get(setup.symbol)
        if frame is None or fill not in frame.index:
            skipped += 1
            continue
        start = frame.index.get_loc(fill)
        if isinstance(start, slice):
            start = start.start
        if isinstance(start, np.ndarray):
            start = int(start[0])
        window = frame.iloc[int(start) : int(start) + int(time_bars) + 5]
        if window.empty:
            skipped += 1
            continue
        raw_open = float(window.iloc[0]["open"])
        swing = float(setup.stop)
        if not np.isfinite(raw_open) or raw_open <= 0.0 or not np.isfinite(swing) or swing <= 0.0:
            skipped += 1
            continue
        risk = abs(raw_open - swing)
        if risk <= 0.0:
            skipped += 1
            continue
        if setup.direction == "long":
            entry_px = buy_price(raw_open, model)
            target = raw_open + SHARE_R * risk
            risk_per = max(entry_px - sell_price(min(swing, raw_open), model), raw_open * 0.002)
        else:
            entry_px = sell_price(raw_open, model)
            target = raw_open - SHARE_R * risk
            risk_per = max(buy_price(max(swing, raw_open), model) - entry_px, raw_open * 0.002)
        quantity = (cash * RISK_FRACTION) / risk_per
        if entry_px * quantity > cash:
            quantity = cash / entry_px
        if quantity < 0.01 or entry_px * quantity > cash + 1e-6:
            skipped += 1
            continue
        exit_raw = None
        reason = "time"
        exit_time = pd.Timestamp(window.index[0])
        for offset, (ts, bar) in enumerate(window.iterrows()):
            opened = float(bar["open"])
            high_px = float(bar["high"])
            low_px = float(bar["low"])
            closed = float(bar["close"])
            if setup.direction == "long":
                if opened <= swing:
                    exit_raw, reason, exit_time = opened, "stop", pd.Timestamp(ts)
                    break
                if low_px <= swing:
                    exit_raw, reason, exit_time = swing, "stop", pd.Timestamp(ts)
                    break
                if high_px >= target:
                    exit_raw, reason, exit_time = target, "target", pd.Timestamp(ts)
                    break
            else:
                if opened >= swing:
                    exit_raw, reason, exit_time = opened, "stop", pd.Timestamp(ts)
                    break
                if high_px >= swing:
                    exit_raw, reason, exit_time = swing, "stop", pd.Timestamp(ts)
                    break
                if low_px <= target:
                    exit_raw, reason, exit_time = target, "target", pd.Timestamp(ts)
                    break
            if offset + 1 >= time_bars:
                exit_raw, reason, exit_time = closed, "time", pd.Timestamp(ts)
                break
        if exit_raw is None:
            last = window.iloc[-1]
            exit_raw = float(last["close"])
            reason = "window"
            exit_time = pd.Timestamp(window.index[-1])
        if setup.direction == "long":
            debit = quantity * entry_px + buy_fees(model)
            credit = quantity * sell_price(float(exit_raw), model) - sell_regulatory_fees(sell_price(float(exit_raw), model), quantity, model)
            pnl = credit - debit
        else:
            credit_open = quantity * entry_px - sell_regulatory_fees(entry_px, quantity, model)
            cover = quantity * buy_price(float(exit_raw), model) + buy_fees(model)
            pnl = credit_open - cover
        cash += pnl
        curve_stamps.append(exit_time)
        curve_eq.append(cash)
        busy = exit_time
        if _day(exit_time) == fill_date:
            day_trades.append(fill_date)
        reasons[reason] = reasons.get(reason, 0) + 1
        trades.append(
            {
                "symbol": setup.symbol,
                "direction": setup.direction,
                "pnl": pnl,
                "debit": float(abs(raw_open * quantity)),
                "delta": float("nan"),
                "reason": reason,
                "contracts": 0,
                "fill": fill_date.isoformat(),
            }
        )
    equity = pd.Series(curve_eq, index=pd.DatetimeIndex(curve_stamps)) if curve_eq else pd.Series(dtype=float)
    exposure = pd.Series(np.ones(len(equity)), index=equity.index) if len(equity) else pd.Series(dtype=float)
    metrics = compute_metrics(
        BacktestResult(equity, exposure, pd.DataFrame(trades)),
        float(starting_equity),
    )
    before = theoretical_breakeven(SHARE_R, -1.0)
    return _pack(metrics, before, trades, skipped, blocked, overlapped, reasons, float(starting_equity))
