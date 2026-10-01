"""Day-trading strategies.

Daily-bar versions never use the signal day's high, low, close, or volume
to decide an entry. Intraday versions confirm on a completed bar and fill
on the next bar, and they are flattened at the session close.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from webull_bot.indicators import atr, rsi, sma
from webull_bot.strategies.base import Strategy
from webull_bot.strategies.signals import blank, limit_symbols
from webull_bot.universe import ETF_UNIVERSE, INTRADAY_SYMBOLS, STOCK_UNIVERSE

_GAP_ETFS = ["SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "XLV", "XLY", "XLI"]


def _intraday_session(index: pd.Index) -> pd.Series:
    dates = []
    for ts in index:
        stamp = pd.Timestamp(ts)
        if stamp.tzinfo is not None:
            stamp = stamp.tz_convert("America/New_York")
        dates.append(stamp.date())
    return pd.Series(dates, index=index)


def _prior_regime(regime: pd.DataFrame, index: pd.Index, column: str) -> pd.Series:
    """Regime known before today's session: yesterday's close reading."""
    if regime.empty or column not in regime.columns:
        return pd.Series(False, index=index)
    shifted = regime[column].shift(1)
    sessions = _intraday_session(index)
    # Daily regime indexes are normalized midnights. Map by calendar date.
    by_date = {}
    for ts, value in shifted.items():
        by_date[pd.Timestamp(ts).date()] = bool(value) if pd.notna(value) else False
    return pd.Series([by_date.get(day, False) for day in sessions], index=index)


class GapAndGo(Strategy):
    """Gap-and-go momentum.

    The scanner shape is the one popularized by active momentum day traders
    (a widely published retail version is Ross Cameron's gap-and-go criteria:
    a meaningful gap and elevated relative volume). Premarket volume and
    float are not in free daily data, so this port uses only what is known
    at the open: today's open versus yesterday's close, yesterday's volume
    versus its prior 20-day average, and yesterday's close above the 20-day
    average. The stop is a gap fill back to yesterday's close. The trade is
    flattened at the cash close. Same-day high, low, close, and volume are
    not inputs to the entry.
    """

    name = "gap_and_go"
    citation = (
        "Momentum gap-and-go day trading; scanner criteria in the public "
        "style of Ross Cameron / Warrior Trading (gap plus relative volume)"
    )
    style = "day"
    holds_overnight = False
    survivorship_sensitive = False
    short_sample = False
    trail_pct = None
    default_params = {"gap_min": 0.04, "rvol_min": 1.5}

    def universe(self, mode: str) -> list[str]:
        if mode == "stock":
            return list(STOCK_UNIVERSE)
        return list(_GAP_ETFS)

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for gap_min in (0.02, 0.04, 0.06):
            params = dict(self.default_params)
            params["gap_min"] = gap_min
            grid.append(params)
        return grid

    def generate(self, bars, regime, params):
        out: dict[str, pd.DataFrame] = {}
        for symbol, frame in limit_symbols(bars, params).items():
            if "open" not in frame or len(frame) < 30:
                continue
            close = frame["close"]
            opened = frame["open"]
            volume = frame["volume"]
            prior_close = close.shift(1)
            gap = opened / prior_close - 1.0
            vol_base = volume.rolling(20, min_periods=20).mean().shift(1)
            rvol = volume.shift(1) / vol_base
            trend = prior_close > sma(close, 20).shift(1)
            risk = _prior_regime(regime, frame.index, "risk_on")
            entry = (
                (gap >= float(params["gap_min"]))
                & (gap <= 0.20)
                & (rvol >= float(params["rvol_min"]))
                & trend.fillna(False)
                & risk
            )
            signals = blank(frame.index)
            signals["entry_this_open"] = entry.fillna(False).to_numpy()
            signals["stop_price"] = prior_close.to_numpy()
            signals["max_hold"] = 1
            out[symbol] = signals
        return out


class EndOfDayMeanReversion(Strategy):
    """Buy weakness for a short hold, Connors-style.

    The published version often buys the closing print. Filling at that
    same close would use the price that defined the signal. This port
    signals at the close and fills at the next open, then looks for the
    exit over the following sessions (RSI recovery, a close back above the
    5-day average, or four sessions). Conditions, all known at the signal
    close: above the 200-day average, down at least 1 percent on the day,
    close in the bottom 30 percent of the day's range, RSI(2) below 15,
    and the risk-on regime. The hard stop is 2 ATR. On daily bars this is
    an overnight trade, not an intraday round trip.
    """

    name = "eod_mean_reversion"
    citation = (
        "Larry Connors short-term weakness entries; related to the overnight "
        "return literature (buying the close of a down day in an uptrend)"
    )
    style = "swing"
    holds_overnight = True
    survivorship_sensitive = False
    trail_pct = None
    default_params = {"min_drop": 0.01, "rsi_entry": 15, "range_pct": 0.30, "stop_atr": 2.0, "max_hold": 4}

    def universe(self, mode: str) -> list[str]:
        if mode == "stock":
            return list(STOCK_UNIVERSE)
        symbols = [s for s in ETF_UNIVERSE if s not in {"BIL", "TLT"}]
        return symbols

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for rsi_entry in (10, 15, 25):
            params = dict(self.default_params)
            params["rsi_entry"] = rsi_entry
            grid.append(params)
        return grid

    def generate(self, bars, regime, params):
        out: dict[str, pd.DataFrame] = {}
        for symbol, frame in limit_symbols(bars, params).items():
            if len(frame) < 210:
                continue
            close = frame["close"]
            high = frame["high"]
            low = frame["low"]
            day_range = (high - low).replace(0, pd.NA)
            close_loc = (close - low) / day_range
            down = close / close.shift(1) - 1.0 <= -float(params["min_drop"])
            rsi2 = rsi(close, 2)
            trend = close > sma(close, 200)
            risk = regime["risk_on"].reindex(frame.index).fillna(False) if "risk_on" in regime else False
            entry = (
                down
                & (close_loc < float(params["range_pct"]))
                & (rsi2 < float(params["rsi_entry"]))
                & trend
                & risk
            )
            exit_sig = (rsi2 > 70) | (close > sma(close, 5))
            signals = blank(frame.index)
            signals["entry_next_open"] = entry.fillna(False).to_numpy()
            signals["exit_next_open"] = exit_sig.fillna(False).to_numpy()
            signals["stop_price"] = (close - float(params["stop_atr"]) * atr(frame, 14)).to_numpy()
            signals["max_hold"] = int(params["max_hold"])
            out[symbol] = signals
        return out


class OpeningRangeBreakout(Strategy):
    """Opening-range breakout.

    Toby Crabel, *Day Trading with Short Term Price Patterns and Opening
    Range Breakout* (1990). The first bar of the regular session is the
    opening range. A later bar that closes above that high, with volume
    above 1.2 times its 20-bar average, is the signal. The fill is the next
    bar's open, so the breakout bar's close is not the fill. The stop is
    the opening-range low. Positions are flattened at the session close
    because ``holds_overnight`` is false. On hourly data the opening range
    is the first hour, which is a coarse version of Crabel's window.
    """

    name = "opening_range_breakout"
    citation = "Toby Crabel, Day Trading with Short Term Price Patterns and Opening Range Breakout (1990)"
    style = "day"
    holds_overnight = False
    survivorship_sensitive = False
    short_sample = True
    trail_pct = None
    default_params = {"rvol_min": 1.2, "max_hold": 8}

    def universe(self, mode: str) -> list[str]:
        if mode == "stock":
            return [s for s in INTRADAY_SYMBOLS if s not in {"SPY", "QQQ"}]
        return ["SPY", "QQQ"]

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for rvol_min in (1.0, 1.2, 1.5):
            params = dict(self.default_params)
            params["rvol_min"] = rvol_min
            grid.append(params)
        return grid

    def generate(self, bars, regime, params):
        out: dict[str, pd.DataFrame] = {}
        for symbol, frame in limit_symbols(bars, params).items():
            if len(frame) < 30:
                continue
            session = _intraday_session(frame.index)
            first = frame.groupby(session).cumcount() == 0
            last = frame.groupby(session).cumcount(ascending=False) == 0
            or_high = frame["high"].where(first).groupby(session).ffill()
            or_low = frame["low"].where(first).groupby(session).ffill()
            closed_above = frame["close"] > or_high
            prior_above = closed_above.groupby(session).shift(1).fillna(False).astype(bool)
            fresh = closed_above & ~prior_above
            vol_ma = frame["volume"].rolling(20, min_periods=20).mean()
            rvol_ok = frame["volume"] > float(params["rvol_min"]) * vol_ma
            risk = _prior_regime(regime, frame.index, "aggressive_ok")
            entry = fresh & rvol_ok & ~first & ~last & risk
            signals = blank(frame.index)
            signals["entry_next_open"] = entry.fillna(False).to_numpy()
            signals["stop_price"] = or_low.to_numpy()
            signals["max_hold"] = int(params["max_hold"])
            out[symbol] = signals
        return out


class VWAPPullback(Strategy):
    """VWAP pullback and reclaim.

    Brian Shannon, *Technical Analysis Using Multiple Timeframes*, is the
    standard reference for anchoring decisions to VWAP. Institutional
    execution desks treat VWAP as the session's fair price. This port
    requires a push above the session open, a dip that tags VWAP, and a
    close back above VWAP after the prior bar was also above it. The fill
    is the next bar's open. The stop is the pullback bar's low. Flat by
    the session close. A close back under VWAP schedules an exit at the
    next bar's open.
    """

    name = "vwap_pullback"
    citation = (
        "Brian Shannon, Technical Analysis Using Multiple Timeframes "
        "(anchored VWAP); session VWAP as used by execution desks"
    )
    style = "day"
    holds_overnight = False
    survivorship_sensitive = False
    short_sample = True
    trail_pct = None
    default_params = {"thrust": 0.001, "max_hold": 8}

    def universe(self, mode: str) -> list[str]:
        if mode == "stock":
            return [s for s in INTRADAY_SYMBOLS if s not in {"SPY", "QQQ"}]
        return ["SPY", "QQQ"]

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for thrust in (0.0, 0.001, 0.003):
            params = dict(self.default_params)
            params["thrust"] = thrust
            grid.append(params)
        return grid

    def generate(self, bars, regime, params):
        out: dict[str, pd.DataFrame] = {}
        for symbol, frame in limit_symbols(bars, params).items():
            if len(frame) < 20:
                continue
            session = _intraday_session(frame.index)
            typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
            cumulative_pv = (typical * frame["volume"]).groupby(session).cumsum()
            # Zero-volume hours are missing prints, not a price of zero.
            # pd.NA would make the later comparison raise on float vs None.
            cumulative_v = frame["volume"].groupby(session).cumsum()
            cumulative_v = cumulative_v.mask(cumulative_v == 0)
            vwap = (cumulative_pv / cumulative_v).astype(float)
            first = frame.groupby(session).cumcount() == 0
            last = frame.groupby(session).cumcount(ascending=False) == 0
            session_open = frame["open"].where(first).groupby(session).ffill()
            running_high = frame["high"].groupby(session).cummax()
            thrust = running_high > session_open * (1.0 + float(params["thrust"]))
            was_above = frame["close"].shift(1) > vwap.shift(1)
            reclaim = (frame["low"] <= vwap) & (frame["close"] > vwap) & was_above.fillna(False)
            risk = _prior_regime(regime, frame.index, "risk_on")
            entry = reclaim & thrust & ~first & ~last & risk
            exit_sig = frame["close"] < vwap
            signals = blank(frame.index)
            signals["entry_next_open"] = entry.fillna(False).to_numpy()
            signals["exit_next_open"] = exit_sig.fillna(False).to_numpy()
            signals["stop_price"] = frame["low"].to_numpy()
            signals["max_hold"] = int(params["max_hold"])
            out[symbol] = signals
        return out
