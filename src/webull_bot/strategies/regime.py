"""Market regime from SPY, QQQ, VIX, and breadth.

All series are causal. ``risk_on`` and ``aggressive_ok`` on date t use only
closes through t, so a next-open order placed after the close may use them.
Strategies that decide at the open (gap-and-go, opening-range breakout)
must shift the regime by one session.
"""

from __future__ import annotations

import pandas as pd

from webull_bot.indicators import sma
from webull_bot.universe import VIX_SYMBOL


def build_regime(
    bars: dict[str, pd.DataFrame],
    breadth_symbols: list[str],
) -> pd.DataFrame:
    if "SPY" not in bars:
        raise KeyError("SPY history is required for the regime filter")
    index = bars["SPY"].index
    spy = bars["SPY"]["close"].reindex(index)
    spy_up = spy > sma(spy, 200)

    qqq_up = pd.Series(False, index=index)
    if "QQQ" in bars:
        qqq = bars["QQQ"]["close"].reindex(index)
        qqq_up = qqq > sma(qqq, 200)

    vix = pd.Series(float("nan"), index=index)
    if VIX_SYMBOL in bars:
        vix = bars[VIX_SYMBOL]["close"].reindex(index).ffill(limit=3)

    flags = []
    for symbol in breadth_symbols:
        if symbol not in bars:
            continue
        close = bars[symbol]["close"].reindex(index)
        flags.append(close > sma(close, 50))
    if flags:
        breadth = pd.concat(flags, axis=1).mean(axis=1)
    else:
        breadth = pd.Series(float("nan"), index=index)

    vix_known = vix.notna()
    # Missing VIX does not silently enable risk-on.
    risk_on = spy_up.fillna(False) & vix_known & (vix < 30) & (breadth >= 0.40)
    aggressive = (
        spy_up.fillna(False)
        & qqq_up.fillna(False)
        & vix_known
        & (vix < 25)
        & (breadth >= 0.45)
    )
    frame = pd.DataFrame(
        {
            "spy_uptrend": spy_up.fillna(False),
            "qqq_uptrend": qqq_up.fillna(False),
            "vix": vix,
            "breadth": breadth,
            "risk_on": risk_on.fillna(False),
            "aggressive_ok": aggressive.fillna(False),
        },
        index=index,
    )
    return frame
