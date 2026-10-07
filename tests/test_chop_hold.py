"""Frozen checks for the chop-hold retest. These do not score a book."""

from __future__ import annotations

import numpy as np
import pandas as pd

from webull_bot.chart_reads.chop import MIN_CHOP_BARS, features
from webull_bot.chart_reads.hold import (
    MAX_HEIGHT_ATR,
    MIN_HEIGHT_ATR,
    MIN_TOUCHES,
    PULLBACK_SESSIONS,
    RANGE_SESSIONS,
    TOUCH_ATR,
    attempt_counts,
    find_chop_holds,
    scan_chop_holds,
)
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DEFAULTS


def test_constants_stay_the_ones_frozen_before_the_score():
    assert RANGE_SESSIONS == 10
    assert PULLBACK_SESSIONS == 5
    assert MIN_TOUCHES == 2
    assert MIN_CHOP_BARS == 6
    assert TOUCH_ATR == float(DEFAULTS["touch_atr"]) == 0.50
    assert MIN_HEIGHT_ATR == float(BREAKOUT_DEFAULTS["min_height_atr"])
    assert MAX_HEIGHT_ATR == float(BREAKOUT_DEFAULTS["max_height_atr"])


def _index(sessions: int, start: str = "2024-01-02") -> pd.DatetimeIndex:
    days = pd.bdate_range(start, periods=sessions)
    stamps = []
    for day in days:
        for hour in range(7):
            stamps.append(pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=30 + 60 * hour))
    return pd.DatetimeIndex(stamps).tz_localize("America/New_York")


def _frame(sessions: int = 48) -> pd.DataFrame:
    """Wide warmup, a two-sided shelf, a breakout, a band rejection, then a dry hold.

    The dry stretch uses the same sine the chop study already flags. It sits
    above the shelf, so a hold is possible, and the last bar of the pullback
    window is a strong close out of that zone.
    """
    index = _index(sessions)
    n = len(index)
    open_ = np.zeros(n)
    high = np.zeros(n)
    low = np.zeros(n)
    close = np.zeros(n)
    volume = np.full(n, 1_000_000.0)
    per = 7
    for session in range(sessions):
        for bar in range(per):
            i = session * per + bar
            if session < 32:
                price = 70.0 + session * 0.15
                open_[i] = price - 1.0
                close[i] = price + 1.0
                high[i] = price + 4.0
                low[i] = price - 4.0
            elif session < 42:
                # Closes oscillate just under a 112 high. Wide lows keep ATR large
                # enough that the breakout does not un-tangle the 9 and 20 EMAs.
                turn = i * np.pi / 4.0
                close[i] = 110.0 + np.sin(turn) * 1.5
                open_[i] = 110.0 + np.sin(turn - 0.8) * 1.5
                high[i] = 112.0
                low[i] = 104.0 if session in (35, 39) and bar == 4 else 107.0
            elif session == 42 and bar == 0:
                open_[i], high[i], low[i], close[i] = 111.6, 113.4, 111.3, 113.1
                volume[i] = 350_000
            elif session == 42 and bar == 1:
                open_[i], high[i], low[i], close[i] = 113.0, 115.2, 112.4, 113.2
                volume[i] = 350_000
            else:
                turn = i * np.pi / 4.0
                close[i] = 113.4 + np.sin(turn) * 0.55
                open_[i] = 113.4 + np.sin(turn - 0.8) * 0.55
                high[i] = max(open_[i], close[i]) + 0.18
                low[i] = min(open_[i], close[i]) - 0.18
                volume[i] = 350_000
    entry = 46 * per + 6
    open_[entry], high[entry], low[entry], close[entry] = 114.4, 116.0, 113.8, 115.7
    volume[entry] = 350_000
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


def test_breakout_chop_hold_fires_one_long_and_stops_under_the_shelf():
    frame = _frame()
    marks = scan_chop_holds(frame, symbol="TEST")
    assert marks, _debug(frame)
    mark = marks[0]
    assert mark.setup.direction == "long"
    assert mark.setup.kind == "hold"
    assert mark.level == 112.0
    assert mark.setup.stop < mark.level
    assert mark.setup.stop < float(frame.loc[mark.setup.signal_time, "close"])
    assert pd.Timestamp(mark.chop_end) >= pd.Timestamp(mark.chop_start)
    assert pd.Timestamp(mark.setup.signal_time) > pd.Timestamp(mark.chop_end)
    assert pd.Timestamp(mark.setup.fill_time) > pd.Timestamp(mark.setup.signal_time)
    assert mark.setup.reference > mark.level
    counts = attempt_counts(frame)
    assert counts["signals"] >= 1
    assert counts["breakouts"] >= 1
    assert counts["chop_runs"] >= 1


def test_a_close_back_through_the_shelf_cancels_the_entry():
    frame = _frame()
    # The first dry bar after the rejection closes back through 110.
    breakout_at = 42 * 7
    frame.iloc[breakout_at + 2, frame.columns.get_loc("close")] = 109.4
    frame.iloc[breakout_at + 2, frame.columns.get_loc("low")] = 109.2
    assert find_chop_holds(frame, symbol="TEST") == []


def test_the_short_is_the_mirror():
    frame = _frame()
    mirrored = pd.DataFrame(
        {
            "open": 220.0 - frame["open"],
            "high": 220.0 - frame["low"],
            "low": 220.0 - frame["high"],
            "close": 220.0 - frame["close"],
            "volume": frame["volume"],
        },
        index=frame.index,
    )
    marks = scan_chop_holds(mirrored, symbol="TEST")
    assert marks, _debug(mirrored)
    assert marks[0].setup.direction == "short"
    assert marks[0].setup.stop > marks[0].level


def test_the_rules_are_not_in_the_registry_and_live_stays_off():
    text = open("config/default.yaml", encoding="utf-8").read()
    assert "live_trading_enabled: false" in text
    optional = open("config/optional_strategies.json", encoding="utf-8").read()
    assert "hold" not in optional
    live = open("src/webull_bot/execution/live.py", encoding="utf-8").read()
    assert "scan_chop_holds" not in live
    assert "find_chop_holds" not in live


def _debug(frame: pd.DataFrame) -> str:
    feat = features(frame)
    flagged = feat.index[feat["chop"].to_numpy()]
    tail = feat.iloc[-40:][["chop", "narrow", "tangled", "vwap_crosses", "rel_volume"]]
    return f"chop bars {len(flagged)} last {list(flagged[-8:])}\n{tail.to_string()}"
