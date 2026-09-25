"""Concrete strategy catalog."""

from __future__ import annotations

from webull_bot.strategies.base import Strategy
from webull_bot.strategies.bluechip_reversal import BluechipReversal
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
    ]


def strategy_by_name(name: str) -> Strategy:
    for strategy in all_strategies():
        if strategy.name == name:
            return strategy
    known = ", ".join(strategy.name for strategy in all_strategies())
    raise KeyError(f"Unknown strategy {name!r}. Known: {known}")
