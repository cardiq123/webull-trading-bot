"""Concrete strategy catalog.

``chop_breakout_60m`` is a sandbox forward test. It is not in
``all_strategies()``, so research does not score it and the selected book
stays dual momentum.
"""

from __future__ import annotations

from webull_bot.strategies.base import Strategy
from webull_bot.strategies.bluechip_reversal import BluechipReversal
from webull_bot.strategies.chop_breakout import ChopBreakout60m
from webull_bot.strategies.support_reversal import SupportReversal
from webull_bot.strategies.wedge_breakout import WedgeBreakout
from webull_bot.strategies.day import (
    EndOfDayMeanReversion,
    GapAndGo,
    OpeningRangeBreakout,
    VWAPPullback,
)
from webull_bot.strategies.swing import (
    ConnorsRSI2,
    DualMomentum,
    EMAPullback,
    RelativeStrengthRotation,
    VCPBreakout,
)


def all_strategies() -> list[Strategy]:
    return [
        GapAndGo(),
        OpeningRangeBreakout(),
        VWAPPullback(),
        EndOfDayMeanReversion(),
        EMAPullback(),
        VCPBreakout(),
        ConnorsRSI2(),
        RelativeStrengthRotation(),
        DualMomentum(),
        BluechipReversal(),
        SupportReversal(),
        WedgeBreakout(),
    ]


def forward_strategy(name: str) -> Strategy:
    """Sandbox forward-test strategies. These are not in the live book."""
    if name == ChopBreakout60m.name:
        return ChopBreakout60m()
    known = ChopBreakout60m.name
    raise KeyError(f"Unknown forward-test strategy {name!r}. Known: {known}")


def strategy_by_name(name: str) -> Strategy:
    if name == ChopBreakout60m.name:
        raise KeyError(
            "chop_breakout_60m is not in the paper or live book. "
            "Run: python -m webull_bot forward-test chop_breakout_60m"
        )
    if name in {
        "vwap_band_15m",
        "vwap_band_15m_qqq",
        "vwap_band_15m_qqq_aggr",
        "vwap_band_15m_qqq_aggr_1dte",
        "vwap_band_15m_qqq_compound",
        "neckline_trapdoor_qqq",
        "four_hour_qqq_1dte",
    }:
        raise KeyError(
            f"{name} is not in the paper or live book. "
            f"Run: python -m webull_bot forward-test {name}"
        )
    for strategy in all_strategies():
        if strategy.name == name:
            return strategy
    known = ", ".join(strategy.name for strategy in all_strategies())
    raise KeyError(f"Unknown strategy {name!r}. Known: {known}")
