"""Swing strategies.

Citations are the published idea. The code is a testable reading of that
idea plus the hard stop this system requires. It is not a claim that the
author's historical results will repeat.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from webull_bot.indicators import atr, ema, rsi, sma
from webull_bot.strategies.base import Strategy
from webull_bot.strategies.signals import blank, limit_symbols, month_end_mask
from webull_bot.universe import DUAL_MOMENTUM_SYMBOLS, ETF_UNIVERSE, STOCK_UNIVERSE

_EQUITY_ETFS = [
    symbol
    for symbol in ETF_UNIVERSE
    if symbol not in {"BIL", "TLT", "GLD"}
]


def _regime_flag(regime: pd.DataFrame, index: pd.Index, column: str) -> pd.Series:
    if regime.empty or column not in regime.columns:
        return pd.Series(False, index=index)
    return regime[column].reindex(index).fillna(False).astype(bool)


class ConnorsRSI2(Strategy):
    """Larry Connors RSI(2), from *Short Term Trading Strategies That Work*.

    Long only when the instrument is above its 200-day average and RSI(2)
    is washed out. Exit when price closes back above a short average or
    RSI(2) recovers. Connors' published tests often had no catastrophic
    stop. This port adds a 2.5 ATR stop because every position in this
    system must have one. The original exit rule is otherwise intact.
    The market-regime filter also requires SPY uptrend, VIX under 30, and
    breadth of at least 40 percent above the 50-day average.
    """

    name = "connors_rsi2"
    citation = (
        "Larry Connors, Short Term Trading Strategies That Work (2008); "
        "Connors and Alvarez, High Probability ETF Trading"
    )
    style = "swing"
    holds_overnight = True
    survivorship_sensitive = False
    trail_pct = None
    default_params = {"rsi_entry": 10, "rsi_exit": 70, "exit_sma": 5, "stop_atr": 2.5, "max_hold": 6}

    def universe(self, mode: str) -> list[str]:
        if mode == "stock":
            return list(STOCK_UNIVERSE)
        return list(_EQUITY_ETFS)

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for rsi_entry in (5, 10, 15):
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
            rsi2 = rsi(close, 2)
            trend = close > sma(close, 200)
            exit_ma = sma(close, int(params["exit_sma"]))
            stop_dist = float(params["stop_atr"]) * atr(frame, 14)
            risk_on = _regime_flag(regime, frame.index, "risk_on")
            entry = (rsi2 < float(params["rsi_entry"])) & trend & risk_on
            exit_sig = (close > exit_ma) | (rsi2 > float(params["rsi_exit"]))
            signals = blank(frame.index)
            signals["entry_next_open"] = entry.fillna(False).to_numpy()
            signals["exit_next_open"] = exit_sig.fillna(False).to_numpy()
            signals["stop_price"] = (close - stop_dist).to_numpy()
            signals["max_hold"] = int(params["max_hold"])
            out[symbol] = signals
        return out


class EMAPullback(Strategy):
    """Pullback to a rising 10/20-day average in a stage-2 uptrend.

    The trend template is the one associated with Mark Minervini's stage
    analysis and with the 10- and 20-day pullback entries used by many
    swing traders in that tradition (Minervini, *Trade Like a Stock Market
    Wizard*; the shorter-average pullback is also common in Gil Morales and
    Chris Kacher's trend work). Fresh touch of the 20-day EMA that closes
    back above the 10-day EMA, only when the 50-day is above a rising
    200-day and the aggressive regime filter is on.
    """

    name = "ema_pullback"
    citation = (
        "Mark Minervini, Trade Like a Stock Market Wizard (stage-2 trend); "
        "10/20 EMA pullback as used in that swing-trading tradition"
    )
    style = "swing"
    holds_overnight = True
    survivorship_sensitive = False
    trail_pct = None
    default_params = {"fast": 10, "mid": 20, "stop_atr": 2.0, "max_hold": 20}

    def universe(self, mode: str) -> list[str]:
        if mode == "stock":
            return list(STOCK_UNIVERSE)
        return list(_EQUITY_ETFS)

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for mid in (10, 20):
            for stop_atr in (1.5, 2.5):
                params = dict(self.default_params)
                params["mid"] = mid
                params["fast"] = min(10, mid)
                params["stop_atr"] = stop_atr
                grid.append(params)
        return grid

    def generate(self, bars, regime, params):
        out: dict[str, pd.DataFrame] = {}
        fast_n = int(params["fast"])
        mid_n = int(params["mid"])
        for symbol, frame in limit_symbols(bars, params).items():
            if len(frame) < 220:
                continue
            close = frame["close"]
            low = frame["low"]
            ema_fast = ema(close, fast_n)
            ema_mid = ema(close, mid_n)
            ema_50 = ema(close, 50)
            ema_200 = ema(close, 200)
            trend = (close > ema_50) & (ema_50 > ema_200) & (ema_200 > ema_200.shift(20))
            touch = low <= ema_mid * 1.002
            reclaim = close >= ema_fast
            fresh = touch & ~touch.shift(1).fillna(False)
            not_extended = close <= ema_mid * 1.04
            aggressive = _regime_flag(regime, frame.index, "aggressive_ok")
            entry = fresh & reclaim & trend & not_extended & aggressive
            exit_sig = close < ema_50
            distance = np.maximum(close - low, float(params["stop_atr"]) * atr(frame, 14))
            signals = blank(frame.index)
            signals["entry_next_open"] = entry.fillna(False).to_numpy()
            signals["exit_next_open"] = exit_sig.fillna(False).to_numpy()
            signals["stop_price"] = (close - distance).to_numpy()
            signals["max_hold"] = int(params["max_hold"])
            out[symbol] = signals
        return out


class VCPBreakout(Strategy):
    """Volatility-contraction breakout, Minervini / O'Neil style.

    O'Neil (*How to Make Money in Stocks*) buys strength near highs, with
    CAN SLIM's technical component being a proper base. Minervini
    (*Trade Like a Stock Market Wizard*, *Think and Trade Like a Champion*)
    tightens that into a volatility contraction pattern: successive tight
    ranges, a pivot, and a volume expansion. This port is the part that
    can be measured on price and volume alone. It does not score earnings,
    float, or sponsorship, so it is not full CAN SLIM. Trend template:
    price above a rising 200-day, 50-day above 150-day above 200-day, close
    within 15 percent of the 252-day high. Contraction: 10-day ATR below
    0.75 of 40-day ATR and a 10-day range under 8 percent of price.
    Breakout: close above the prior 20-day high on 1.5 times 50-day volume.
    """

    name = "vcp_breakout"
    citation = (
        "Mark Minervini, volatility contraction pattern; "
        "William O'Neil, CAN SLIM base breakout (How to Make Money in Stocks)"
    )
    style = "swing"
    holds_overnight = True
    survivorship_sensitive = False
    trail_pct = None
    default_params = {"contraction": 0.75, "volume_mult": 1.5, "max_hold": 40}

    def universe(self, mode: str) -> list[str]:
        if mode == "stock":
            return list(STOCK_UNIVERSE)
        return list(_EQUITY_ETFS)

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for contraction in (0.65, 0.75, 0.90):
            params = dict(self.default_params)
            params["contraction"] = contraction
            grid.append(params)
        return grid

    def generate(self, bars, regime, params):
        out: dict[str, pd.DataFrame] = {}
        for symbol, frame in limit_symbols(bars, params).items():
            if len(frame) < 260:
                continue
            close = frame["close"]
            high = frame["high"]
            low = frame["low"]
            volume = frame["volume"]
            sma_50 = sma(close, 50)
            sma_150 = sma(close, 150)
            sma_200 = sma(close, 200)
            trend = (
                (close > sma_50)
                & (sma_50 > sma_150)
                & (sma_150 > sma_200)
                & (sma_200 > sma_200.shift(20))
            )
            # Within 15% of the 252-day high. Today's high is known at the
            # close, when this signal is formed for the next open.
            near_high = close >= high.rolling(252, min_periods=252).max() * 0.85
            atr_10 = atr(frame, 10)
            atr_40 = atr(frame, 40)
            contraction = atr_10 < float(params["contraction"]) * atr_40
            tight = (high.rolling(10, min_periods=10).max() - low.rolling(10, min_periods=10).min()) < close * 0.08
            prior_high = high.rolling(20, min_periods=20).max().shift(1)
            breakout = close > prior_high
            vol_ok = volume > float(params["volume_mult"]) * sma(volume, 50)
            aggressive = _regime_flag(regime, frame.index, "aggressive_ok")
            entry = trend & near_high & contraction & tight & breakout & vol_ok & aggressive
            exit_sig = close < sma_50
            pivot_low = low.rolling(10, min_periods=10).min()
            signals = blank(frame.index)
            signals["entry_next_open"] = entry.fillna(False).to_numpy()
            signals["exit_next_open"] = exit_sig.fillna(False).to_numpy()
            signals["stop_price"] = pivot_low.to_numpy()
            signals["max_hold"] = int(params["max_hold"])
            out[symbol] = signals
        return out


class RelativeStrengthRotation(Strategy):
    """Cross-sectional momentum rotation.

    Jegadeesh and Titman (Journal of Finance, 1993) documented 3- to
    12-month return continuation. O'Neil ranks the same idea as relative
    strength inside CAN SLIM. This port buys the top sector ETFs (or, in
    the diagnostic stock mode, the top stocks) by trailing return, skips
    the most recent month, and requires a positive absolute return plus
    the aggressive regime filter. Rebalance is the last session of the
    month. A 15 percent trail from the position peak is the hard stop;
    the academic papers did not use one.
    """

    name = "rs_rotation"
    citation = (
        "Jegadeesh and Titman, Returns to Buying Winners and Selling Losers, "
        "Journal of Finance 1993; O'Neil relative strength"
    )
    style = "swing"
    holds_overnight = True
    survivorship_sensitive = False
    trail_pct = 0.15
    default_params = {"lookback_months": 6, "skip_months": 1, "top_n": 3, "max_hold": 0}

    def universe(self, mode: str) -> list[str]:
        if mode == "stock":
            return list(STOCK_UNIVERSE)
        return list(_EQUITY_ETFS)

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for lookback in (3, 6, 12):
            params = dict(self.default_params)
            params["lookback_months"] = lookback
            grid.append(params)
        return grid

    def generate(self, bars, regime, params):
        return _rotation_signals(
            limit_symbols(bars, params),
            regime,
            lookback_months=int(params["lookback_months"]),
            skip_months=int(params["skip_months"]),
            top_n=int(params["top_n"]),
            max_hold=int(params["max_hold"]),
            require_aggressive=True,
            use_absolute_hurdle=False,
            stop_pct=0.15,
        )


class DualMomentum(Strategy):
    """Gary Antonacci's dual momentum.

    *Dual Momentum Investing* (2014) combines relative momentum (hold the
    asset that has outperformed) with absolute momentum (hold cash when the
    winner has not beaten T-bills). The universe here is SPY, QQQ, IWM,
    EFA, EEM, TLT, and GLD. BIL is the T-bill hurdle, not a traded risk
    asset. If nothing clears BIL's trailing return the account stays in
    cash, which earns zero in this backtest and is slightly pessimistic
    versus holding bills. Lookback is 12 months, skipping the most recent
    month (the 12-1 convention). The hard stop is a 20 percent trail from
    the position peak. Antonacci's published process rebalances monthly
    and does not use a stop; the trail is this system's risk rule.
    """

    name = "dual_momentum"
    citation = "Gary Antonacci, Dual Momentum Investing (2014); absolute and relative momentum"
    style = "swing"
    holds_overnight = True
    survivorship_sensitive = False
    trail_pct = 0.20
    default_params = {"lookback_months": 12, "skip_months": 1, "top_n": 1, "max_hold": 0}

    def universe(self, mode: str) -> list[str]:
        return list(DUAL_MOMENTUM_SYMBOLS)

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for lookback in (6, 9, 12):
            for top_n in (1, 2):
                params = dict(self.default_params)
                params["lookback_months"] = lookback
                params["top_n"] = top_n
                grid.append(params)
        return grid

    def generate(self, bars, regime, params):
        scoped = limit_symbols(bars, params)
        return _rotation_signals(
            scoped,
            regime,
            lookback_months=int(params["lookback_months"]),
            skip_months=int(params["skip_months"]),
            top_n=int(params["top_n"]),
            max_hold=int(params["max_hold"]),
            require_aggressive=False,
            use_absolute_hurdle=True,
            stop_pct=0.20,
            symbols=list(params.get("symbols") or DUAL_MOMENTUM_SYMBOLS),
        )


def _rotation_signals(
    bars: dict[str, pd.DataFrame],
    regime: pd.DataFrame,
    *,
    lookback_months: int,
    skip_months: int,
    top_n: int,
    max_hold: int,
    require_aggressive: bool,
    use_absolute_hurdle: bool,
    stop_pct: float,
    symbols: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    symbol_list = [s for s in (symbols or list(bars)) if s in bars and s != "BIL" and not s.startswith("^")]
    if not symbol_list:
        return {}
    clock = bars["SPY"].index if "SPY" in bars else bars[symbol_list[0]].index
    closes = pd.DataFrame({symbol: bars[symbol]["close"].reindex(clock) for symbol in symbol_list})
    lookback = lookback_months * 21
    skip = skip_months * 21
    if skip <= 0:
        skipped = closes
        long_return = closes / closes.shift(lookback) - 1.0
    else:
        skipped = closes.shift(skip)
        long_return = skipped / closes.shift(lookback) - 1.0
    absolute_return = closes / closes.shift(lookback) - 1.0
    hurdle = pd.Series(0.0, index=clock)
    if use_absolute_hurdle and "BIL" in bars:
        bil = bars["BIL"]["close"].reindex(clock)
        hurdle = (bil / bil.shift(lookback) - 1.0).fillna(0.0)
    rebalance = month_end_mask(pd.DatetimeIndex(clock))
    if require_aggressive:
        allowed = _regime_flag(regime, clock, "aggressive_ok")
    else:
        allowed = pd.Series(True, index=clock)

    chosen = {symbol: pd.Series(False, index=clock) for symbol in symbol_list}
    for ts in clock[rebalance.to_numpy()]:
        if not bool(allowed.loc[ts]):
            continue
        row = long_return.loc[ts]
        abs_row = absolute_return.loc[ts]
        ranked = []
        for symbol in symbol_list:
            rel = row.get(symbol)
            absolute = abs_row.get(symbol)
            if pd.isna(rel) or pd.isna(absolute):
                continue
            if use_absolute_hurdle and float(absolute) <= float(hurdle.loc[ts]):
                continue
            if not use_absolute_hurdle and float(absolute) <= 0:
                continue
            ranked.append((float(rel), symbol))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        for _, symbol in ranked[:top_n]:
            chosen[symbol].loc[ts] = True

    out: dict[str, pd.DataFrame] = {}
    for symbol in symbol_list:
        close = bars[symbol]["close"].reindex(clock)
        held = chosen[symbol]
        # Exit on a rebalance where the name is no longer selected.
        # Between rebalances the trail stop is the protection.
        exit_sig = rebalance & ~held
        signals = blank(clock)
        signals["entry_next_open"] = held.fillna(False).to_numpy()
        signals["exit_next_open"] = exit_sig.fillna(False).to_numpy()
        signals["stop_price"] = (close * (1.0 - stop_pct)).to_numpy()
        if max_hold > 0:
            signals["max_hold"] = max_hold
        out[symbol] = signals
    return out
