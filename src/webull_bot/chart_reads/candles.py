"""Candlestick shapes, with the location left as a separate flag.

Pure pandas and numpy. There is no TA-Lib dependency. This is not the Dow
swing detector in ``webull_bot.patterns``. Nothing here places an order.

Thresholds are ATR fractions chosen before any return was measured. They are
not loosened after a count or a P&L. Every comparison uses the Wilder ATR of
the bar on which the pattern completes.

The hammer column is the lower-shadow shape only. Hanging man is that shape
after an uptrend. The same split applies to the inverted hammer and the
shooting star. Without the location filter, one uptrend bar can therefore
be both a long and a short. A dragonfly is also a doji. A long-legged doji
is a doji with two long wicks. Those overlaps stay in the flags.

Multi-bar patterns read consecutive rows, including the overnight jump from
the last regular-hours bar to the next open. An opening gap can complete a
star, a kicker, or a tasuki. Daily bars (every timestamp at midnight) are
not passed through the regular-hours filter. On those bars session VWAP and
the bands are left false, and location is the 9 EMA, the 20 EMA, or a swing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.costs import CostModel
from webull_bot.indicators import atr, ema
from webull_bot.mtf_vwap.detect import session_vwap
from webull_bot.patterns import confirmed_pivot_high, confirmed_pivot_low

ATR_WINDOW = 14
DOJI_BODY = 0.10
DOJI_RANGE = 0.20
HAMMER_BODY_MIN = 0.10
HAMMER_BODY_MAX = 0.40
HAMMER_WICK_BODY = 2.0
HAMMER_WICK_ATR = 0.30
HAMMER_OPP_BODY = 0.50
SPIN_BODY_MIN = 0.10
SPIN_BODY_MAX = 0.25
SPIN_RANGE = 0.30
LONG_WICK = 0.30
DRAGON_LOWER = 0.40
DRAGON_UPPER = 0.10
MARU_BODY = 0.60
MARU_WICK = 0.05
ENGULF_BODY = 0.30
ENGULF_PRIOR = 0.25
HARAMI_PRIOR = 0.40
PIERCE_PRIOR = 0.40
PIERCE_BODY = 0.30
TWEEZER_MATCH = 0.10
TWEEZER_PRIOR = 0.20
KICKER_BODY = 0.40
STAR_PRIOR = 0.40
STAR_MID = 0.25
STAR_BODY = 0.30
STAR_DOJI = 0.10
SOLDIER_BODY = 0.30
SOLDIER_WICK = 0.50
METHODS_FIRST = 0.50
METHODS_MID = 0.25
METHODS_LAST = 0.40
TASUKI_FIRST = 0.40
TASUKI_SECOND = 0.30
TASUKI_GAP = 0.02
TREND_BARS = 5
TREND_ATR = 0.50
NEAR_ATR = 0.25
SWING_WIDTH = 2
HOLDOUT_START = date(2022, 1, 1)
TRAIN_END = date(2021, 12, 31)
SAMPLE_END = date(2026, 10, 6)
RANDOM_SEED = 17

CONFIRMATION = (
    "Enter at the next bar's open, in the pattern's direction. "
    "The old rule that the next bar must close in that direction is the one-bar forward result, "
    "not a second filter in front of the fill."
)
WHERE_BULL = (
    "After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, "
    "or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, "
    "the 20 EMA, or a swing."
)
WHERE_BEAR = (
    "After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, "
    "or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, "
    "the 20 EMA, or a swing."
)
WHERE_BULL_CONT = (
    "During an uptrend. The location flag uses the same support set as a bullish reversal "
    "(VWAP, either EMA, the lower band, or a swing low). It does not switch over to the upper band."
)
WHERE_BEAR_CONT = (
    "During a downtrend. The location flag uses the same resistance set as a bearish reversal "
    "(VWAP, either EMA, the upper band, or a swing high). It does not switch over to the lower band."
)
WHERE_NEUTRAL = (
    "Anywhere the bar prints. With the context filter on, it only counts when the bar is at VWAP, "
    "either EMA, a 1 SD band, or a confirmed swing. It has no trade direction, so it is not a "
    "confirmation filter and it cannot be labeled an edge."
)


@dataclass(frozen=True)
class Pattern:
    id: str
    name: str
    group: str
    bias: str
    family: str
    span: int
    context_trend: str
    looks: str
    story: str
    where: str
    sketch: tuple[tuple[float, float, float, float], ...]


def _p(
    pid: str,
    name: str,
    group: str,
    bias: str,
    family: str,
    span: int,
    trend: str,
    looks: str,
    story: str,
    where: str,
    sketch: tuple[tuple[float, float, float, float], ...],
) -> Pattern:
    return Pattern(pid, name, group, bias, family, span, trend, looks, story, where, sketch)


CATALOG: tuple[Pattern, ...] = (
    _p(
        "doji", "Doji", "single", "neutral", "indecision", 1, "none",
        "The open and the close are almost the same price, and the bar still has a real range.",
        "Buyers and sellers traded to a standstill. The bar does not say who won.",
        WHERE_NEUTRAL, ((1.0, 1.7, 0.3, 1.05),),
    ),
    _p(
        "long_legged_doji", "Long-legged doji", "single", "neutral", "indecision", 1, "none",
        "A doji with a long wick above the open and a long wick below it.",
        "Price traveled a long way in both directions and closed back where it started. Neither side kept control.",
        WHERE_NEUTRAL, ((1.0, 2.4, -0.4, 1.04),),
    ),
    _p(
        "dragonfly_doji", "Dragonfly doji", "single", "bullish", "reversal", 1, "down",
        "The open, the high, and the close sit together, and a long lower wick hangs underneath.",
        "Sellers pushed the bar down and buyers brought it all the way back. After a decline that is a rejection of lower prices.",
        WHERE_BULL, ((1.0, 1.12, -0.6, 1.04),),
    ),
    _p(
        "gravestone_doji", "Gravestone doji", "single", "bearish", "reversal", 1, "up",
        "The open, the low, and the close sit together, and a long upper wick stands above them.",
        "Buyers pushed the bar up and sellers brought it all the way back. After a rally that is a rejection of higher prices.",
        WHERE_BEAR, ((1.0, 2.4, 0.92, 1.04),),
    ),
    _p(
        "hammer", "Hammer", "single", "bullish", "reversal", 1, "down",
        "A small real body at the top of the bar and a lower wick at least twice that body. The upper wick is short. The column is this shape only. It does not require a downtrend.",
        "Sellers drove price down during the bar and buyers closed it back near the high. After a decline, the story is that the decline was refused.",
        WHERE_BULL, ((1.0, 1.35, -0.8, 1.28),),
    ),
    _p(
        "hanging_man", "Hanging man", "single", "bearish", "reversal", 1, "up",
        "The same lower-shadow shape as a hammer, and the five closes before the bar are an uptrend.",
        "The bar looks like a hammer, but it prints after a rally. Buyers are no longer getting an easy close at the high of a rising market. The long lower wick is supply showing up overhead.",
        WHERE_BEAR, ((1.0, 1.35, -0.8, 1.28),),
    ),
    _p(
        "inverted_hammer", "Inverted hammer", "single", "bullish", "reversal", 1, "down",
        "A small real body at the bottom of the bar and an upper wick at least twice that body. The lower wick is short. The column is this shape only.",
        "Buyers tried to lift the bar and the close gave a lot of it back. After a decline, the long upper wick is the first sign that buyers can reach higher prices.",
        WHERE_BULL, ((1.0, 2.3, 0.92, 1.22),),
    ),
    _p(
        "shooting_star", "Shooting star", "single", "bearish", "reversal", 1, "up",
        "The same upper-shadow shape as an inverted hammer, and the five closes before the bar are an uptrend.",
        "After a rally, buyers ran the bar up and sellers closed it back near the low. The long upper wick is a rejection of the new high.",
        WHERE_BEAR, ((1.2, 2.5, 1.05, 1.0),),
    ),
    _p(
        "spinning_top", "Spinning top", "single", "neutral", "indecision", 1, "none",
        "A small real body, larger than a doji, with a wick on each side at least as long as the body.",
        "Both sides pushed and neither one finished the bar in control. It is pause, not a direction.",
        WHERE_NEUTRAL, ((1.0, 1.7, 0.3, 1.2),),
    ),
    _p(
        "marubozu_bull", "Bullish marubozu", "continuation", "bullish", "continuation", 1, "up",
        "A long bullish body with almost no wick on either end.",
        "Buyers paid the low and kept paying through the close. In an uptrend it says the push is still one-sided.",
        WHERE_BULL_CONT, ((0.2, 2.05, 0.15, 2.0),),
    ),
    _p(
        "marubozu_bear", "Bearish marubozu", "continuation", "bearish", "continuation", 1, "down",
        "A long bearish body with almost no wick on either end.",
        "Sellers hit the open and kept hitting through the close. In a downtrend it says the push is still one-sided.",
        WHERE_BEAR_CONT, ((2.0, 2.05, 0.15, 0.2),),
    ),
    _p(
        "bullish_engulfing", "Bullish engulfing", "two-bar", "bullish", "reversal", 2, "down",
        "A bearish body, then a larger bullish body that opens below the prior close and closes above the prior open.",
        "The second bar's buyers did not just stop the decline. They traded through the entire prior body.",
        WHERE_BULL, ((2.0, 2.15, 0.85, 1.0), (0.75, 2.35, 0.65, 2.2)),
    ),
    _p(
        "bearish_engulfing", "Bearish engulfing", "two-bar", "bearish", "reversal", 2, "up",
        "A bullish body, then a larger bearish body that opens above the prior close and closes below the prior open.",
        "The second bar's sellers traded through the entire prior body. The rally's last up bar was given back.",
        WHERE_BEAR, ((1.0, 2.15, 0.85, 2.0), (2.25, 2.35, 0.65, 0.8)),
    ),
    _p(
        "bullish_harami", "Bullish harami", "two-bar", "bullish", "reversal", 2, "down",
        "A long bearish body, then a smaller bullish body that sits strictly inside it.",
        "The decline's wide bar is followed by a bar that cannot leave that range. Selling stalled, and the close turned up inside the prior body.",
        WHERE_BULL, ((2.2, 2.3, 0.35, 0.5), (1.15, 1.55, 1.0, 1.45)),
    ),
    _p(
        "bearish_harami", "Bearish harami", "two-bar", "bearish", "reversal", 2, "up",
        "A long bullish body, then a smaller bearish body that sits strictly inside it.",
        "The rally's wide bar is followed by a bar that cannot leave that range. Buying stalled, and the close turned down inside the prior body.",
        WHERE_BEAR, ((0.5, 2.3, 0.4, 2.2), (1.45, 1.6, 1.05, 1.15)),
    ),
    _p(
        "bullish_harami_cross", "Bullish harami cross", "two-bar", "bullish", "reversal", 2, "down",
        "A long bearish body with a doji sitting strictly inside it.",
        "After a strong down bar, the next bar cannot choose a direction at all. The cross is the stall. It is a harami whose second body is a doji.",
        WHERE_BULL, ((2.2, 2.3, 0.35, 0.5), (1.3, 1.7, 0.9, 1.32)),
    ),
    _p(
        "bearish_harami_cross", "Bearish harami cross", "two-bar", "bearish", "reversal", 2, "up",
        "A long bullish body with a doji sitting strictly inside it.",
        "After a strong up bar, the next bar cannot choose a direction. The rally paused inside its own range.",
        WHERE_BEAR, ((0.5, 2.3, 0.4, 2.2), (1.3, 1.7, 0.9, 1.32)),
    ),
    _p(
        "piercing_line", "Piercing line", "two-bar", "bullish", "reversal", 2, "down",
        "A long bearish bar, then a bullish bar that opens below the prior low and closes above the prior midpoint without taking out the prior open.",
        "The second bar gaps down, which looks like more selling, then buyers reclaim more than half of the prior body. They do not erase the whole bar.",
        WHERE_BULL, ((2.0, 2.1, 0.7, 0.9), (0.5, 1.65, 0.4, 1.55)),
    ),
    _p(
        "dark_cloud_cover", "Dark cloud cover", "two-bar", "bearish", "reversal", 2, "up",
        "A long bullish bar, then a bearish bar that opens above the prior high and closes below the prior midpoint without taking out the prior open.",
        "The second bar gaps up, which looks like more buying, then sellers take back more than half of the prior body.",
        WHERE_BEAR, ((0.9, 2.1, 0.8, 2.0), (2.3, 2.4, 1.25, 1.35)),
    ),
    _p(
        "tweezer_bottom", "Tweezer bottom", "two-bar", "bullish", "reversal", 2, "down",
        "Two bars share a low, within a tenth of an ATR. The first is bearish. The second is bullish and its lower wick is at least as long as its body.",
        "Both bars found the same floor. The second one bounced off it. The matching lows are the test.",
        WHERE_BULL, ((1.6, 1.7, 0.4, 1.0), (0.7, 1.35, 0.4, 1.25)),
    ),
    _p(
        "tweezer_top", "Tweezer top", "two-bar", "bearish", "reversal", 2, "up",
        "Two bars share a high, within a tenth of an ATR. The first is bullish. The second is bearish and its upper wick is at least as long as its body.",
        "Both bars found the same ceiling. The second one sold off it. The matching highs are the test.",
        WHERE_BEAR, ((1.0, 2.2, 0.9, 1.6), (1.9, 2.2, 1.25, 1.4)),
    ),
    _p(
        "bullish_kicker", "Bullish kicker", "two-bar", "bullish", "reversal", 2, "down",
        "A long bearish bar, then a long bullish bar whose entire range gaps above the prior high.",
        "The market did not overlap the prior bar at all. Buyers repriced the instrument above the whole of the last down bar.",
        WHERE_BULL, ((1.5, 1.6, 0.4, 0.5), (1.9, 3.1, 1.85, 3.0)),
    ),
    _p(
        "bearish_kicker", "Bearish kicker", "two-bar", "bearish", "reversal", 2, "up",
        "A long bullish bar, then a long bearish bar whose entire range gaps below the prior low.",
        "Sellers repriced the instrument under the whole of the last up bar. The two ranges do not touch.",
        WHERE_BEAR, ((0.5, 1.6, 0.4, 1.5), (0.15, 0.2, -1.0, -0.9)),
    ),
    _p(
        "morning_star", "Morning star", "three-bar", "bullish", "reversal", 3, "down",
        "A long bearish bar, a small bar that gaps below that close, and a long bullish bar that closes above the first bar's midpoint. The second gap is not required.",
        "Selling, then a stall under the decline, then buyers take back more than half of the first bar. The small middle bar is the turn.",
        WHERE_BULL, ((2.2, 2.3, 0.7, 0.9), (0.55, 0.75, 0.2, 0.45), (0.5, 1.9, 0.4, 1.8)),
    ),
    _p(
        "evening_star", "Evening star", "three-bar", "bearish", "reversal", 3, "up",
        "A long bullish bar, a small bar that gaps above that close, and a long bearish bar that closes below the first bar's midpoint. The second gap is not required.",
        "Buying, then a stall above the rally, then sellers take back more than half of the first bar.",
        WHERE_BEAR, ((0.8, 2.3, 0.7, 2.2), (2.35, 2.7, 2.25, 2.5), (2.4, 2.5, 1.0, 1.1)),
    ),
    _p(
        "morning_doji_star", "Morning doji star", "three-bar", "bullish", "reversal", 3, "down",
        "A morning star whose middle bar is a doji: the middle body is at most a tenth of an ATR.",
        "The stall in the middle is complete indecision, not a small trend bar. Buyers still have to close the third bar back through the first midpoint.",
        WHERE_BULL, ((2.2, 2.3, 0.7, 0.9), (0.45, 0.7, 0.2, 0.47), (0.5, 1.9, 0.4, 1.8)),
    ),
    _p(
        "evening_doji_star", "Evening doji star", "three-bar", "bearish", "reversal", 3, "up",
        "An evening star whose middle bar is a doji.",
        "The stall above the rally is a doji. Sellers still have to close the third bar back through the first midpoint.",
        WHERE_BEAR, ((0.8, 2.3, 0.7, 2.2), (2.45, 2.75, 2.3, 2.47), (2.4, 2.5, 1.0, 1.1)),
    ),
    _p(
        "three_white_soldiers", "Three white soldiers", "three-bar", "bullish", "reversal", 3, "down",
        "Three bullish bars, each with a real body, each close higher, each open inside the prior body, and no long upper wick.",
        "Buyers closed higher three times in a row and did not leave a tall wick of rejection. It is scored as a reversal of a prior decline, which is the three-bar group it belongs to.",
        WHERE_BULL, ((0.4, 1.15, 0.3, 1.05), (0.7, 1.6, 0.65, 1.5), (1.05, 2.05, 1.0, 1.95)),
    ),
    _p(
        "three_black_crows", "Three black crows", "three-bar", "bearish", "reversal", 3, "up",
        "Three bearish bars, each with a real body, each close lower, each open inside the prior body, and no long lower wick.",
        "Sellers closed lower three times and did not leave a tall wick of demand. It is scored as a reversal of a prior rally.",
        WHERE_BEAR, ((2.0, 2.1, 1.2, 1.3), (1.7, 1.75, 0.85, 0.95), (1.35, 1.4, 0.45, 0.55)),
    ),
    _p(
        "three_inside_up", "Three inside up", "three-bar", "bullish", "reversal", 3, "down",
        "A bullish harami, then a third bullish bar that closes above the high of the first bar.",
        "The harami said selling stalled. The third bar is the buyers leaving the first bar's range.",
        WHERE_BULL, ((2.2, 2.3, 0.4, 0.55), (1.2, 1.55, 1.05, 1.45), (1.4, 2.55, 1.3, 2.45)),
    ),
    _p(
        "three_inside_down", "Three inside down", "three-bar", "bearish", "reversal", 3, "up",
        "A bearish harami, then a third bearish bar that closes below the low of the first bar.",
        "The harami said buying stalled. The third bar is the sellers leaving the first bar's range.",
        WHERE_BEAR, ((0.55, 2.3, 0.45, 2.2), (1.45, 1.6, 1.1, 1.2), (1.25, 1.35, 0.2, 0.3)),
    ),
    _p(
        "three_outside_up", "Three outside up", "three-bar", "bullish", "reversal", 3, "down",
        "A bullish engulfing pattern, then a third bullish bar that closes above the engulfing bar's close.",
        "The engulfing bar took the prior body. The next bar's buyers pushed the close still higher.",
        WHERE_BULL, ((2.0, 2.1, 0.9, 1.05), (0.85, 2.25, 0.75, 2.15), (1.9, 2.7, 1.85, 2.6)),
    ),
    _p(
        "three_outside_down", "Three outside down", "three-bar", "bearish", "reversal", 3, "up",
        "A bearish engulfing pattern, then a third bearish bar that closes below the engulfing bar's close.",
        "The engulfing bar took the prior body. The next bar's sellers pushed the close still lower.",
        WHERE_BEAR, ((1.0, 2.1, 0.9, 2.0), (2.15, 2.25, 0.75, 0.85), (1.05, 1.1, 0.3, 0.4)),
    ),
    _p(
        "abandoned_baby_bull", "Bullish abandoned baby", "three-bar", "bullish", "reversal", 3, "down",
        "A long bearish bar, a doji that gaps below that bar's low, and a bullish bar that gaps above the doji and closes above the first midpoint.",
        "The middle bar is left alone, with a gap on both sides. Price abandoned the low and the next bar did not come back to it.",
        WHERE_BULL, ((2.2, 2.3, 0.8, 0.95), (0.35, 0.55, 0.1, 0.37), (0.85, 1.9, 0.8, 1.8)),
    ),
    _p(
        "abandoned_baby_bear", "Bearish abandoned baby", "three-bar", "bearish", "reversal", 3, "up",
        "A long bullish bar, a doji that gaps above that bar's high, and a bearish bar that gaps below the doji and closes below the first midpoint.",
        "The middle bar is left alone above the rally. The next bar gaps away from it and does not come back.",
        WHERE_BEAR, ((0.8, 2.2, 0.7, 2.1), (2.5, 2.75, 2.35, 2.52), (2.05, 2.1, 0.9, 1.0)),
    ),
    _p(
        "rising_three_methods", "Rising three methods", "continuation", "bullish", "continuation", 5, "up",
        "A long bullish bar, three small bars that stay inside its high and low (at least two of them bearish), and a bullish bar that closes above the first close.",
        "The trend bar pauses while small bars drift inside it, then the next bullish bar resumes above the first close. The pause did not break the first bar's range.",
        WHERE_BULL_CONT,
        ((0.4, 2.15, 0.3, 2.05), (1.8, 1.9, 1.4, 1.5), (1.55, 1.65, 1.15, 1.25), (1.3, 1.4, 0.95, 1.05), (1.2, 2.45, 1.15, 2.35)),
    ),
    _p(
        "falling_three_methods", "Falling three methods", "continuation", "bearish", "continuation", 5, "down",
        "A long bearish bar, three small bars that stay inside its high and low (at least two of them bullish), and a bearish bar that closes below the first close.",
        "The decline pauses inside its own bar, then selling resumes below the first close.",
        WHERE_BEAR_CONT,
        ((2.05, 2.15, 0.3, 0.4), (0.6, 1.05, 0.5, 0.95), (0.9, 1.35, 0.8, 1.25), (1.15, 1.55, 1.05, 1.45), (1.3, 1.4, 0.05, 0.15)),
    ),
    _p(
        "upside_tasuki_gap", "Upside tasuki gap", "continuation", "bullish", "continuation", 3, "up",
        "Two bullish bars with a gap between them, then a bearish bar that opens inside the second body and closes back into the gap without filling it.",
        "The pullback sells into the gap and stops short of closing it. The unfilled gap is the continuation.",
        WHERE_BULL_CONT, ((0.4, 1.35, 0.3, 1.25), (1.6, 2.55, 1.55, 2.45), (2.2, 2.3, 1.45, 1.55)),
    ),
    _p(
        "downside_tasuki_gap", "Downside tasuki gap", "continuation", "bearish", "continuation", 3, "down",
        "Two bearish bars with a gap between them, then a bullish bar that opens inside the second body and closes back into the gap without filling it.",
        "The bounce buys into the gap and stops short of closing it. The unfilled gap is the continuation.",
        WHERE_BEAR_CONT, ((2.45, 2.55, 1.3, 1.4), (1.15, 1.2, 0.2, 0.3), (0.55, 1.25, 0.45, 1.15)),
    ),
)

_BY_ID = {item.id: item for item in CATALOG}
REVERSAL_LONG = tuple(item.id for item in CATALOG if item.family == "reversal" and item.bias == "bullish")
REVERSAL_SHORT = tuple(item.id for item in CATALOG if item.family == "reversal" and item.bias == "bearish")
CONTINUATION_LONG = tuple(item.id for item in CATALOG if item.family == "continuation" and item.bias == "bullish")
CONTINUATION_SHORT = tuple(item.id for item in CATALOG if item.family == "continuation" and item.bias == "bearish")
INDECISION = tuple(item.id for item in CATALOG if item.family == "indecision")


def pattern_ids() -> tuple[str, ...]:
    return tuple(item.id for item in CATALOG)


def frozen_rules() -> dict:
    """The definitions the score is allowed to use. Written before any return."""
    return {
        "atr_window": ATR_WINDOW,
        "doji_body": DOJI_BODY,
        "doji_range": DOJI_RANGE,
        "hammer_body_min_exclusive": HAMMER_BODY_MIN,
        "hammer_body_max": HAMMER_BODY_MAX,
        "hammer_wick_body": HAMMER_WICK_BODY,
        "hammer_wick_atr": HAMMER_WICK_ATR,
        "hammer_opposite_wick_body": HAMMER_OPP_BODY,
        "spin_body_min_exclusive": SPIN_BODY_MIN,
        "spin_body_max": SPIN_BODY_MAX,
        "spin_range": SPIN_RANGE,
        "long_legged_wick": LONG_WICK,
        "dragon_wick": DRAGON_LOWER,
        "dragon_opposite": DRAGON_UPPER,
        "marubozu_body": MARU_BODY,
        "marubozu_wick": MARU_WICK,
        "engulf_body": ENGULF_BODY,
        "engulf_prior": ENGULF_PRIOR,
        "harami_prior": HARAMI_PRIOR,
        "pierce_prior": PIERCE_PRIOR,
        "pierce_body": PIERCE_BODY,
        "tweezer_match": TWEEZER_MATCH,
        "tweezer_prior": TWEEZER_PRIOR,
        "kicker_body": KICKER_BODY,
        "star_prior": STAR_PRIOR,
        "star_middle": STAR_MID,
        "star_body": STAR_BODY,
        "star_doji": STAR_DOJI,
        "soldier_body": SOLDIER_BODY,
        "soldier_wick_body": SOLDIER_WICK,
        "methods_first": METHODS_FIRST,
        "methods_middle": METHODS_MID,
        "methods_last": METHODS_LAST,
        "tasuki_first": TASUKI_FIRST,
        "tasuki_second": TASUKI_SECOND,
        "tasuki_gap": TASUKI_GAP,
        "trend_bars": TREND_BARS,
        "trend_atr": TREND_ATR,
        "near_atr": NEAR_ATR,
        "swing_width": SWING_WIDTH,
        "holdout_start": HOLDOUT_START.isoformat(),
        "train_end": TRAIN_END.isoformat(),
        "sample_end": SAMPLE_END.isoformat(),
        "seed": RANDOM_SEED,
        "costs": "CostModel defaults: 5 bps slippage, 1 bp half-spread, SEC 20.60 per million of sales, FINRA TAF 0.000195 per share cap 9.79. One share.",
        "entry": "Next bar open. Exit is the close h bars later, h in 1, 3, 6. Intraday entry and exit stay in the signal session.",
        "context_off": "The named column, traded in the catalog direction. Hammer is the shape. Hanging man already includes the uptrend.",
        "context_on": "The named column, the pattern's context trend measured before the pattern, and the matching location flag. Neutral uses location only.",
        "edge": {
            "family_books": ["SPY_5m", "SPY_15m", "SPY_1d", "LIQUID_1d"],
            "horizons": [1, 3, 6],
            "contexts": ["off", "on"],
            "min_cell_n": 30,
            "min_n": 300,
            "fdr_q": 0.10,
            "neutral_can_pass": False,
            "require_train_mean_positive": True,
            "require_holdout_mean_positive": True,
            "require_beat_random_mean": True,
            "require_beat_random_hit": True,
            "require_expected_max_t": True,
            "pooled_also_requires_spy_daily_both_windows_positive": True,
        },
        "reversal_long": list(REVERSAL_LONG),
        "reversal_short": list(REVERSAL_SHORT),
        "continuation_long": list(CONTINUATION_LONG),
        "continuation_short": list(CONTINUATION_SHORT),
        "indecision": list(INDECISION),
        "filters": [
            "EMA variant vwap, stop reject, target swing, reversal filter",
            "VWAP reversal 2 SD target vwap, reversal filter",
            "VWAP extension 2 SD target 1R, continuation filter",
        ],
        "improvement": "Holdout trades at least 20, ending equity higher, profit factor not lower, max drawdown not worse by more than 5 percentage points. passes_gate is still required before a book could replace a published gate, and this study does not replace one.",
    }


def _shift(values: np.ndarray, bars: int) -> np.ndarray:
    out = np.full(len(values), np.nan, dtype=float)
    if 0 < bars < len(values):
        out[bars:] = values[:-bars]
    return out


def _shift_bool(values: np.ndarray, bars: int) -> np.ndarray:
    out = np.zeros(len(values), dtype=bool)
    if 0 < bars < len(values):
        out[bars:] = values[:-bars]
    return out


def _daily_index(index: pd.DatetimeIndex) -> bool:
    if len(index) == 0:
        return False
    return bool(((index.hour == 0) & (index.minute == 0) & (index.second == 0)).all())


def _near_level(low: np.ndarray, high: np.ndarray, close: np.ndarray, level: np.ndarray, scale: np.ndarray) -> np.ndarray:
    finite = np.isfinite(level) & np.isfinite(scale)
    overlap = (low <= level) & (level <= high)
    close_enough = np.abs(close - level) <= NEAR_ATR * scale
    return finite & (overlap | close_enough)


def _patterns(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray, scale: np.ndarray) -> dict[str, np.ndarray]:
    count = len(close)
    body = np.abs(close - open_)
    upper = np.maximum(high - np.maximum(open_, close), 0.0)
    lower = np.maximum(np.minimum(open_, close) - low, 0.0)
    span = high - low
    finite = np.isfinite(scale) & (scale > 0) & np.isfinite(open_) & np.isfinite(high) & np.isfinite(low) & np.isfinite(close)
    bull = finite & (close > open_)
    bear = finite & (close < open_)
    body_high = np.maximum(open_, close)
    body_low = np.minimum(open_, close)
    mid = (open_ + close) / 2.0
    unit = scale

    doji = finite & (body <= DOJI_BODY * unit) & (span >= DOJI_RANGE * unit)
    long_legged = doji & (lower >= LONG_WICK * unit) & (upper >= LONG_WICK * unit)
    dragonfly = finite & (body <= DOJI_BODY * unit) & (lower >= DRAGON_LOWER * unit) & (upper <= DRAGON_UPPER * unit)
    gravestone = finite & (body <= DOJI_BODY * unit) & (upper >= DRAGON_LOWER * unit) & (lower <= DRAGON_UPPER * unit)
    hammer = (
        finite
        & (body > HAMMER_BODY_MIN * unit)
        & (body <= HAMMER_BODY_MAX * unit)
        & (lower >= HAMMER_WICK_BODY * body)
        & (lower >= HAMMER_WICK_ATR * unit)
        & (upper <= HAMMER_OPP_BODY * body)
    )
    inverted = (
        finite
        & (body > HAMMER_BODY_MIN * unit)
        & (body <= HAMMER_BODY_MAX * unit)
        & (upper >= HAMMER_WICK_BODY * body)
        & (upper >= HAMMER_WICK_ATR * unit)
        & (lower <= HAMMER_OPP_BODY * body)
    )
    spinning = (
        finite
        & (body > SPIN_BODY_MIN * unit)
        & (body <= SPIN_BODY_MAX * unit)
        & (lower >= body)
        & (upper >= body)
        & (span >= SPIN_RANGE * unit)
    )
    maru_bull = bull & (body >= MARU_BODY * unit) & (upper <= MARU_WICK * unit) & (lower <= MARU_WICK * unit)
    maru_bear = bear & (body >= MARU_BODY * unit) & (upper <= MARU_WICK * unit) & (lower <= MARU_WICK * unit)

    prior_body = _shift(body, 1)
    prior_open = _shift(open_, 1)
    prior_close = _shift(close, 1)
    prior_high = _shift(high, 1)
    prior_low = _shift(low, 1)
    prior_mid = _shift(mid, 1)
    prior_body_high = _shift(body_high, 1)
    prior_body_low = _shift(body_low, 1)
    prior_bull = _shift_bool(bull, 1)
    prior_bear = _shift_bool(bear, 1)
    inside = finite & (body_high < prior_body_high) & (body_low > prior_body_low)

    engulf_bull = (
        bull
        & prior_bear
        & (open_ < prior_close)
        & (close > prior_open)
        & (body > prior_body)
        & (body >= ENGULF_BODY * unit)
        & (prior_body >= ENGULF_PRIOR * unit)
    )
    engulf_bear = (
        bear
        & prior_bull
        & (open_ > prior_close)
        & (close < prior_open)
        & (body > prior_body)
        & (body >= ENGULF_BODY * unit)
        & (prior_body >= ENGULF_PRIOR * unit)
    )
    harami_bull = bull & prior_bear & (prior_body >= HARAMI_PRIOR * unit) & inside
    harami_bear = bear & prior_bull & (prior_body >= HARAMI_PRIOR * unit) & inside
    harami_cross_bull = doji & prior_bear & (prior_body >= HARAMI_PRIOR * unit) & inside
    harami_cross_bear = doji & prior_bull & (prior_body >= HARAMI_PRIOR * unit) & inside
    piercing = (
        bull
        & prior_bear
        & (prior_body >= PIERCE_PRIOR * unit)
        & (body >= PIERCE_BODY * unit)
        & (open_ < prior_low)
        & (close > prior_mid)
        & (close < prior_open)
    )
    dark_cloud = (
        bear
        & prior_bull
        & (prior_body >= PIERCE_PRIOR * unit)
        & (body >= PIERCE_BODY * unit)
        & (open_ > prior_high)
        & (close < prior_mid)
        & (close > prior_open)
    )
    tweezer_bottom = (
        bull
        & prior_bear
        & (np.abs(low - prior_low) <= TWEEZER_MATCH * unit)
        & (lower >= body)
        & (prior_body >= TWEEZER_PRIOR * unit)
    )
    tweezer_top = (
        bear
        & prior_bull
        & (np.abs(high - prior_high) <= TWEEZER_MATCH * unit)
        & (upper >= body)
        & (prior_body >= TWEEZER_PRIOR * unit)
    )
    kicker_bull = bull & prior_bear & (body >= KICKER_BODY * unit) & (prior_body >= KICKER_BODY * unit) & (low > prior_high)
    kicker_bear = bear & prior_bull & (body >= KICKER_BODY * unit) & (prior_body >= KICKER_BODY * unit) & (high < prior_low)

    first_body = _shift(body, 2)
    first_close = _shift(close, 2)
    first_mid = _shift(mid, 2)
    first_high = _shift(high, 2)
    first_low = _shift(low, 2)
    first_bull = _shift_bool(bull, 2)
    first_bear = _shift_bool(bear, 2)
    mid_body = _shift(body, 1)
    mid_high = _shift(high, 1)
    mid_low = _shift(low, 1)
    mid_span = _shift(span, 1)
    morning = (
        first_bear
        & (first_body >= STAR_PRIOR * unit)
        & (mid_body <= STAR_MID * unit)
        & (mid_high < first_close)
        & bull
        & (body >= STAR_BODY * unit)
        & (close > first_mid)
    )
    evening = (
        first_bull
        & (first_body >= STAR_PRIOR * unit)
        & (mid_body <= STAR_MID * unit)
        & (mid_low > first_close)
        & bear
        & (body >= STAR_BODY * unit)
        & (close < first_mid)
    )
    morning_doji = morning & (mid_body <= STAR_DOJI * unit)
    evening_doji = evening & (mid_body <= STAR_DOJI * unit)
    middle_doji = (mid_body <= DOJI_BODY * unit) & (mid_span >= DOJI_RANGE * unit)
    abandoned_bull = (
        first_bear
        & (first_body >= STAR_PRIOR * unit)
        & middle_doji
        & (mid_high < first_low)
        & bull
        & (low > mid_high)
        & (close > first_mid)
    )
    abandoned_bear = (
        first_bull
        & (first_body >= STAR_PRIOR * unit)
        & middle_doji
        & (mid_low > first_high)
        & bear
        & (high < mid_low)
        & (close < first_mid)
    )

    body_2 = _shift(body, 2)
    close_1 = _shift(close, 1)
    close_2 = _shift(close, 2)
    open_1 = _shift(open_, 1)
    upper_1 = _shift(upper, 1)
    upper_2 = _shift(upper, 2)
    lower_1 = _shift(lower, 1)
    lower_2 = _shift(lower, 2)
    bull_1 = _shift_bool(bull, 1)
    bull_2 = _shift_bool(bull, 2)
    bear_1 = _shift_bool(bear, 1)
    bear_2 = _shift_bool(bear, 2)
    high_body_1 = _shift(body_high, 1)
    low_body_1 = _shift(body_low, 1)
    high_body_2 = _shift(body_high, 2)
    low_body_2 = _shift(body_low, 2)
    soldiers = (
        bull
        & bull_1
        & bull_2
        & (body >= SOLDIER_BODY * unit)
        & (prior_body >= SOLDIER_BODY * unit)
        & (body_2 >= SOLDIER_BODY * unit)
        & (close > close_1)
        & (close_1 > close_2)
        & (open_1 >= low_body_2)
        & (open_1 <= high_body_2)
        & (open_ >= low_body_1)
        & (open_ <= high_body_1)
        & (upper <= SOLDIER_WICK * body)
        & (upper_1 <= SOLDIER_WICK * prior_body)
        & (upper_2 <= SOLDIER_WICK * body_2)
    )
    crows = (
        bear
        & bear_1
        & bear_2
        & (body >= SOLDIER_BODY * unit)
        & (prior_body >= SOLDIER_BODY * unit)
        & (body_2 >= SOLDIER_BODY * unit)
        & (close < close_1)
        & (close_1 < close_2)
        & (open_1 >= low_body_2)
        & (open_1 <= high_body_2)
        & (open_ >= low_body_1)
        & (open_ <= high_body_1)
        & (lower <= SOLDIER_WICK * body)
        & (lower_1 <= SOLDIER_WICK * prior_body)
        & (lower_2 <= SOLDIER_WICK * body_2)
    )
    inside_up = _shift_bool(harami_bull, 1) & bull & (close > first_high)
    inside_down = _shift_bool(harami_bear, 1) & bear & (close < first_low)
    outside_up = _shift_bool(engulf_bull, 1) & bull & (close > close_1)
    outside_down = _shift_bool(engulf_bear, 1) & bear & (close < close_1)

    lead_body = _shift(body, 4)
    lead_high = _shift(high, 4)
    lead_low = _shift(low, 4)
    lead_close = _shift(close, 4)
    lead_bull = _shift_bool(bull, 4)
    lead_bear = _shift_bool(bear, 4)
    middles_ok = np.ones(count, dtype=bool)
    middle_bears = np.zeros(count, dtype=int)
    middle_bulls = np.zeros(count, dtype=int)
    for bars in (3, 2, 1):
        middles_ok &= _shift(body, bars) <= METHODS_MID * unit
        middles_ok &= _shift(high, bars) <= lead_high
        middles_ok &= _shift(low, bars) >= lead_low
        middle_bears += _shift_bool(bear, bars).astype(int)
        middle_bulls += _shift_bool(bull, bars).astype(int)
    rising = (
        lead_bull
        & (lead_body >= METHODS_FIRST * unit)
        & middles_ok
        & (middle_bears >= 2)
        & bull
        & (body >= METHODS_LAST * unit)
        & (close > lead_close)
    )
    falling = (
        lead_bear
        & (lead_body >= METHODS_FIRST * unit)
        & middles_ok
        & (middle_bulls >= 2)
        & bear
        & (body >= METHODS_LAST * unit)
        & (close < lead_close)
    )

    second_low = _shift(low, 1)
    second_high = _shift(high, 1)
    second_close = _shift(close, 1)
    gap_high = _shift(high, 2)
    gap_low = _shift(low, 2)
    upside_tasuki = (
        bull_2
        & (body_2 >= TASUKI_FIRST * unit)
        & bull_1
        & (prior_body >= TASUKI_SECOND * unit)
        & (second_low > gap_high + TASUKI_GAP * unit)
        & bear
        & (open_ >= low_body_1)
        & (open_ <= high_body_1)
        & (close > gap_high)
        & (close < second_close)
    )
    downside_tasuki = (
        bear_2
        & (body_2 >= TASUKI_FIRST * unit)
        & bear_1
        & (prior_body >= TASUKI_SECOND * unit)
        & (second_high < gap_low - TASUKI_GAP * unit)
        & bull
        & (open_ >= low_body_1)
        & (open_ <= high_body_1)
        & (close < gap_low)
        & (close > second_close)
    )

    return {
        "doji": doji,
        "long_legged_doji": long_legged,
        "dragonfly_doji": dragonfly,
        "gravestone_doji": gravestone,
        "hammer": hammer,
        "inverted_hammer": inverted,
        "spinning_top": spinning,
        "marubozu_bull": maru_bull,
        "marubozu_bear": maru_bear,
        "bullish_engulfing": engulf_bull,
        "bearish_engulfing": engulf_bear,
        "bullish_harami": harami_bull,
        "bearish_harami": harami_bear,
        "bullish_harami_cross": harami_cross_bull,
        "bearish_harami_cross": harami_cross_bear,
        "piercing_line": piercing,
        "dark_cloud_cover": dark_cloud,
        "tweezer_bottom": tweezer_bottom,
        "tweezer_top": tweezer_top,
        "bullish_kicker": kicker_bull,
        "bearish_kicker": kicker_bear,
        "morning_star": morning,
        "evening_star": evening,
        "morning_doji_star": morning_doji,
        "evening_doji_star": evening_doji,
        "three_white_soldiers": soldiers,
        "three_black_crows": crows,
        "three_inside_up": inside_up,
        "three_inside_down": inside_down,
        "three_outside_up": outside_up,
        "three_outside_down": outside_down,
        "abandoned_baby_bull": abandoned_bull,
        "abandoned_baby_bear": abandoned_bear,
        "rising_three_methods": rising,
        "falling_three_methods": falling,
        "upside_tasuki_gap": upside_tasuki,
        "downside_tasuki_gap": downside_tasuki,
    }


def _trend(close: np.ndarray, scale: np.ndarray) -> dict[str, np.ndarray]:
    found: dict[str, np.ndarray] = {}
    for span in (1, 2, 3, 5):
        earlier = _shift(close, span + TREND_BARS)
        recent = _shift(close, span)
        found[f"downtrend_{span}"] = np.isfinite(scale) & ((earlier - recent) >= TREND_ATR * scale)
        found[f"uptrend_{span}"] = np.isfinite(scale) & ((recent - earlier) >= TREND_ATR * scale)
    return found


def _location(frame: pd.DataFrame, scale: np.ndarray) -> dict[str, np.ndarray]:
    index = pd.DatetimeIndex(frame.index)
    close = frame["close"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    count = len(frame)
    blank = np.zeros(count, dtype=bool)
    daily = _daily_index(index)
    if daily:
        at_vwap = blank
        at_lower = blank
        at_upper = blank
    else:
        work = frame if "volume" in frame.columns else frame.assign(volume=1.0)
        bands = session_vwap(work).reindex(index)
        vwap = bands["vwap"].to_numpy(dtype=float) if "vwap" in bands.columns else np.full(count, np.nan)
        upper = bands["upper"].to_numpy(dtype=float) if "upper" in bands.columns else np.full(count, np.nan)
        lower = bands["lower"].to_numpy(dtype=float) if "lower" in bands.columns else np.full(count, np.nan)
        at_vwap = _near_level(low, high, close, vwap, scale)
        lower_finite = np.isfinite(lower) & np.isfinite(scale)
        upper_finite = np.isfinite(upper) & np.isfinite(scale)
        at_lower = lower_finite & (low <= lower + NEAR_ATR * scale) & (close >= lower - NEAR_ATR * scale)
        at_upper = upper_finite & (high >= upper - NEAR_ATR * scale) & (close <= upper + NEAR_ATR * scale)
    average9 = ema(frame["close"].astype(float), 9).to_numpy(dtype=float)
    average20 = ema(frame["close"].astype(float), 20).to_numpy(dtype=float)
    at_ema9 = _near_level(low, high, close, average9, scale)
    at_ema20 = _near_level(low, high, close, average20, scale)
    swing_low = confirmed_pivot_low(frame["low"].astype(float), SWING_WIDTH, SWING_WIDTH).ffill().to_numpy(dtype=float)
    swing_high = confirmed_pivot_high(frame["high"].astype(float), SWING_WIDTH, SWING_WIDTH).ffill().to_numpy(dtype=float)
    at_swing_low = _near_level(low, high, close, swing_low, scale)
    at_swing_high = _near_level(low, high, close, swing_high, scale)
    located_bull = at_vwap | at_ema9 | at_ema20 | at_lower | at_swing_low
    located_bear = at_vwap | at_ema9 | at_ema20 | at_upper | at_swing_high
    return {
        "at_vwap": at_vwap,
        "at_ema9": at_ema9,
        "at_ema20": at_ema20,
        "at_lower_band": at_lower,
        "at_upper_band": at_upper,
        "at_swing_low": at_swing_low,
        "at_swing_high": at_swing_high,
        "located_bull": located_bull,
        "located_bear": located_bear,
        "located_any": located_bull | located_bear,
    }


def detect(frame: pd.DataFrame) -> pd.DataFrame:
    """Boolean pattern columns plus trend and location. Row i uses bars through i."""
    columns = list(pattern_ids())
    extra = [
        "downtrend_1", "downtrend_2", "downtrend_3", "downtrend_5",
        "uptrend_1", "uptrend_2", "uptrend_3", "uptrend_5",
        "at_vwap", "at_ema9", "at_ema20", "at_lower_band", "at_upper_band",
        "at_swing_low", "at_swing_high", "located_bull", "located_bear", "located_any",
        "reversal_long", "reversal_long_context", "reversal_short", "reversal_short_context",
        "continuation_long", "continuation_long_context", "continuation_short", "continuation_short_context",
        "atr",
    ]
    context_names = [f"context_{item.id}" for item in CATALOG]
    if frame is None or len(frame) == 0:
        return pd.DataFrame(columns=[*columns, *context_names, *extra])
    scale = atr(frame, ATR_WINDOW).to_numpy(dtype=float)
    open_ = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    shapes = _patterns(open_, high, low, close, scale)
    trend = _trend(close, scale)
    shapes["hanging_man"] = shapes["hammer"] & trend["uptrend_1"]
    shapes["shooting_star"] = shapes["inverted_hammer"] & trend["uptrend_1"]
    place = _location(frame, scale)
    data: dict[str, np.ndarray] = {}
    for item in CATALOG:
        column = shapes[item.id]
        data[item.id] = column
        if item.context_trend == "none":
            data[f"context_{item.id}"] = column & place["located_any"]
        elif item.context_trend == "down":
            data[f"context_{item.id}"] = column & trend[f"downtrend_{item.span}"] & place["located_bull"]
        else:
            data[f"context_{item.id}"] = column & trend[f"uptrend_{item.span}"] & place["located_bear"]
    data.update(trend)
    data.update(place)

    def _combine(names: tuple[str, ...], context: bool) -> np.ndarray:
        acc = np.zeros(len(frame), dtype=bool)
        prefix = "context_" if context else ""
        for name in names:
            acc |= data[f"{prefix}{name}"]
        return acc

    data["reversal_long"] = _combine(REVERSAL_LONG, False)
    data["reversal_long_context"] = _combine(REVERSAL_LONG, True)
    data["reversal_short"] = _combine(REVERSAL_SHORT, False)
    data["reversal_short_context"] = _combine(REVERSAL_SHORT, True)
    data["continuation_long"] = _combine(CONTINUATION_LONG, False)
    data["continuation_long_context"] = _combine(CONTINUATION_LONG, True)
    data["continuation_short"] = _combine(CONTINUATION_SHORT, False)
    data["continuation_short_context"] = _combine(CONTINUATION_SHORT, True)
    data["atr"] = scale
    return pd.DataFrame(data, index=frame.index)


def forward_returns(frame: pd.DataFrame, horizon: int, intraday: bool) -> tuple[np.ndarray, np.ndarray]:
    """After-cost return of one share entered at the next open and sold at the close ``horizon`` bars later.

    On an intraday frame the entry and the exit have to fall in the signal's session.
    A daily frame holds the next rows. The long return buys the open and sells the close.
    The short return sells the open and buys the close. Fees are the repo's default stock schedule.
    """
    count = len(frame)
    long_ret = np.full(count, np.nan)
    short_ret = np.full(count, np.nan)
    if horizon < 1 or count <= horizon:
        return long_ret, short_ret
    opened = frame["open"].to_numpy(dtype=float)
    closed = frame["close"].to_numpy(dtype=float)
    slots = np.arange(0, count - horizon)
    entry = opened[slots + 1]
    exit_ = closed[slots + horizon]
    dates = pd.DatetimeIndex(frame.index)
    if dates.tz is not None:
        dates = dates.tz_convert("America/New_York")
    day = np.asarray(dates.date)
    if intraday:
        same = (day[slots] == day[slots + 1]) & (day[slots] == day[slots + horizon])
    else:
        same = np.ones(len(slots), dtype=bool)
    usable = same & np.isfinite(entry) & np.isfinite(exit_) & (entry > 0) & (exit_ > 0)
    costs = CostModel()
    bump = costs.friction_bps / 10_000.0
    share_fee = min(costs.finra_taf_per_share, costs.finra_taf_cap)
    long_entry = entry * (1.0 + bump)
    long_exit = exit_ * (1.0 - bump)
    long_fee = long_exit * costs.sec_fee_per_dollar_sold + share_fee
    long_values = (long_exit - long_entry - long_fee) / long_entry
    short_entry = entry * (1.0 - bump)
    short_exit = exit_ * (1.0 + bump)
    short_fee = short_entry * costs.sec_fee_per_dollar_sold + share_fee
    short_values = (short_entry - short_exit - short_fee) / short_entry
    long_ret[slots[usable]] = long_values[usable]
    short_ret[slots[usable]] = short_values[usable]
    return long_ret, short_ret


def confirms(flags: pd.DataFrame, direction: str, kind: str, require_location: bool) -> pd.Series:
    """True on bars where a pre-registered family agrees with the setup direction.

    ``kind`` is ``reversal`` or ``continuation``. Location also requires that
    pattern's trend flag. This is a research filter. It is not a live order.
    """
    if direction not in ("long", "short") or kind not in ("reversal", "continuation"):
        raise ValueError("direction must be long or short and kind must be reversal or continuation")
    column = f"{kind}_{direction}" + ("_context" if require_location else "")
    return flags[column].fillna(False).astype(bool)


def catalog_markdown() -> str:
    """The pattern guide. Generated from ``CATALOG`` so the prose cannot drift from the detector."""
    lines = [
        "# Candlestick patterns",
        "",
        "These are the shapes the backtest measures. The thresholds were written down before any forward return. A later result does not change a definition.",
        "",
        "The size of a body or a wick is compared with the Wilder ATR(14) of the bar that completes the pattern. A doji is a body of at most 0.10 ATR on a bar whose high-low range is at least 0.20 ATR, so a print with no range is not a doji. A hammer or inverted hammer has a body above 0.10 ATR and at most 0.40 ATR, so it does not also count as a doji. Its long wick is at least twice the body and at least 0.30 ATR, and the other wick is at most half the body.",
        "",
        "The hammer column is only that lower-shadow shape. Hanging man is the same shape after the five closes before the bar have risen by at least 0.50 ATR. Inverted hammer and shooting star split the same way on the upper wick. Without the location filter, an uptrend bar with a long lower wick is both a hammer (a long) and a hanging man (a short). That overlap is the point of scoring the filter. A dragonfly doji is also a doji. A long-legged doji is a doji whose two wicks are each at least 0.30 ATR.",
        "",
        "Trend is measured on the closes before the pattern, not on the pattern bars. For a pattern of S bars ending at bar i, the recent close is bar i−S and the earlier close is five bars before that. Down means the earlier close is at least 0.50 ATR above the recent close. Up is the mirror.",
        "",
        "Location is 0.25 ATR. The bar is at a level when its range covers the level or the close is within 0.25 ATR of it. The lower band uses the 1 standard-deviation session band: the low is at or through that band plus 0.25 ATR, and the close is not more than 0.25 ATR under it. Swings are a two-bar fractal, confirmed two bars later, then carried forward. A bullish pattern's location is VWAP, the 9 EMA, the 20 EMA, the lower band, or a swing low. A bearish pattern uses VWAP, either EMA, the upper band, or a swing high.",
        "",
        "On a daily bar every timestamp is midnight. Those bars are not run through the regular-hours session, because that filter would drop them. Session VWAP and both bands stay false. Daily location is the two EMAs and the swings.",
        "",
        "Multi-bar patterns use consecutive rows in the frame, including the jump from one session's last bar to the next session's open. An opening gap can complete a star, a kicker, piercing line, dark cloud cover, or a tasuki gap.",
        "",
        "Neutral patterns are measured both directions and cannot receive the edge label. They are not confirmation filters. Reversal patterns, including three white soldiers and three black crows, are the optional filter for the VWAP reversal and the 9/20 EMA rejection. Continuation patterns (the two marubozu, rising and falling three methods, and the two tasuki gaps) are the optional filter for the VWAP extension. The filter is research only. It is not in the live list.",
        "",
        CONFIRMATION,
        "",
        "## Patterns",
        "",
    ]
    for item in CATALOG:
        bias = {"bullish": "Bullish", "bearish": "Bearish", "neutral": "Neutral"}[item.bias]
        lines += [
            f"### {item.name}",
            "",
            f"**Id:** `{item.id}`  ",
            f"**Group:** {item.group}  ",
            f"**Bias:** {bias}  ",
            f"**Family:** {item.family}",
            "",
            f"**How it looks.** {item.looks}",
            "",
            f"**What it means.** {item.story}",
            "",
            f"**Where it matters.** {item.where}",
            "",
            f"**Confirmation.** {CONFIRMATION}",
            "",
        ]
    lines += [
        "The drawing of each shape is `reports/candlestick_patterns.png`. The candles there are a schematic, not a fit to a backtest.",
        "",
    ]
    return "\n".join(lines)


def draw_reference(path: str | Path) -> None:
    """Schematic candles for the catalog. Not fitted to a price series."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(5, 8, figsize=(16.5, 10.5))
    figure.patch.set_facecolor("#161616")
    for axis, item in zip(axes.ravel(), CATALOG):
        axis.set_facecolor("#161616")
        for slot, (opened, high, low, closed) in enumerate(item.sketch):
            color = "#3DDC97" if closed >= opened else "#FF5C5C"
            axis.plot([slot, slot], [low, high], color=color, linewidth=1.2, solid_capstyle="round")
            axis.plot(
                [slot, slot],
                [min(opened, closed), max(opened, closed)],
                color=color,
                linewidth=5.5,
                solid_capstyle="butt",
            )
        axis.set_xlim(-0.65, max(item.span - 0.35, 0.65))
        axis.set_title(item.name, color="#f2f2f2", fontsize=8, pad=2)
        axis.set_xticks([])
        axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_visible(False)
    for axis in axes.ravel()[len(CATALOG) :]:
        axis.set_facecolor("#161616")
        axis.axis("off")
    figure.suptitle("Candlestick patterns", color="#f2f2f2", fontsize=14)
    figure.tight_layout(rect=(0, 0, 1, 0.97))
    figure.savefig(destination, dpi=120, facecolor=figure.get_facecolor())
    plt.close(figure)
    artifacts = Path("/opt/cursor/artifacts")
    if artifacts.is_dir():
        target = artifacts / destination.name
        target.write_bytes(destination.read_bytes())
