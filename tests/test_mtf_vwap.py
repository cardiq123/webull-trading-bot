"""Offline tests for the multi-timeframe VWAP detector and the $1,000 book.

No network. These do not run the research download.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from webull_bot.mtf_vwap.detect import (
    Setup,
    find_setups,
    session_vwap,
    trend_flags,
    weekly_from_daily,
)
from webull_bot.mtf_vwap.params import DEFAULTS, grid, majority_needed
from webull_bot.mtf_vwap.simulate import simulate_options, simulate_stock

NY = "America/New_York"


def _zigzag_ohlc(n: int, start: float, step: float = 1.2) -> pd.DataFrame:
    """Rising swings so confirmed pivots make higher highs and higher lows."""
    close = np.zeros(n)
    high = np.zeros(n)
    low = np.zeros(n)
    price = start
    for i in range(n):
        phase = i % 6
        if phase == 0:
            c = price
            low_ex = price - step
            high_ex = price + step * 0.1
        elif phase == 1:
            price += step * 0.8
            c = price
            low_ex = price - step * 0.1
            high_ex = price + step * 0.1
        elif phase == 2:
            price += step * 0.8
            c = price
            high_ex = price + step * 1.2
            low_ex = price - step * 0.1
        elif phase == 3:
            price -= step * 0.3
            c = price
            high_ex = price + step * 0.1
            low_ex = price - step * 0.1
        elif phase == 4:
            price -= step * 0.25
            c = price
            low_ex = price - step
            high_ex = price + step * 0.1
        else:
            price += step * 0.7
            c = price
            high_ex = price + step * 0.1
            low_ex = price - step * 0.1
        close[i] = c
        high[i] = high_ex
        low[i] = low_ex
    opened = np.r_[close[0], close[:-1]]
    high = np.maximum(high, np.maximum(opened, close))
    low = np.minimum(low, np.minimum(opened, close))
    return pd.DataFrame(
        {"open": opened, "high": high, "low": low, "close": close, "volume": 2_000.0}
    )


def _weekly_friendly_daily(weeks: int = 40) -> pd.DataFrame:
    """Daily bars whose weekly aggregate also swings up."""
    rows = []
    price = 80.0
    for week in range(weeks):
        phase = week % 6
        if phase == 0:
            close, low, high = price, price - 2.0, price + 0.3
        elif phase == 1:
            price += 3.0
            close, low, high = price, price - 0.3, price + 0.3
        elif phase == 2:
            price += 3.0
            close, low, high = price, price - 0.3, price + 3.0
        elif phase == 3:
            price -= 1.0
            close, low, high = price, price - 0.3, price + 0.3
        elif phase == 4:
            price -= 0.8
            close, low, high = price, price - 2.5, price + 0.3
        else:
            price += 2.2
            close, low, high = price, price - 0.3, price + 0.3
        for day in range(5):
            if day == 4:
                rows.append((high, low, close))
            else:
                rows.append((close + 0.1, close - 0.4, close - 0.1))
    close = np.array([row[2] for row in rows], dtype=float)
    high = np.array([row[0] for row in rows], dtype=float)
    low = np.array([row[1] for row in rows], dtype=float)
    opened = np.r_[close[0], close[:-1]]
    high = np.maximum(high, np.maximum(opened, close))
    low = np.minimum(low, np.minimum(opened, close))
    index = pd.bdate_range("2023-06-01", periods=len(rows), tz=NY)
    return pd.DataFrame(
        {"open": opened, "high": high, "low": low, "close": close, "volume": 1_000_000.0},
        index=index,
    )


def _intraday_bundle():
    """15-minute bars plus a daily history that is up on the higher timeframes.

    The intraday path is a small rising zigzag. On this path the session VWAP
    is tagged from above around noon, which is the touch the detector should see.
    """
    daily = _weekly_friendly_daily()
    stamped_index = daily.index
    from webull_bot.mtf_vwap.detect import _stamp_daily, direction_asof, weekly_from_daily

    stamped = _stamp_daily(daily)
    weekly_flags = trend_flags(weekly_from_daily(stamped), 8, 2, 2)
    daily_flags = trend_flags(stamped, 8, 2, 2)
    both = (direction_asof(daily_flags, stamped.index) == "up") & (
        direction_asof(weekly_flags, stamped.index) == "up"
    )
    day = pd.Timestamp(stamped.index[both.to_numpy()][-1]).tz_convert(NY)
    sessions = pd.bdate_range((day - pd.Timedelta(days=30)).date(), day.date())
    stamps = []
    for session in sessions:
        for minute in range(9 * 60 + 30, 16 * 60, 15):
            stamps.append(pd.Timestamp(session).tz_localize(NY) + pd.Timedelta(minutes=minute))
    index = pd.DatetimeIndex(stamps)
    base = float(daily.loc[daily.index.normalize() == day.normalize(), "close"].iloc[-1])
    close = np.zeros(len(index))
    high = np.zeros(len(index))
    low = np.zeros(len(index))
    price = base - 5.0
    for i in range(len(index)):
        phase = i % 6
        if phase == 0:
            c, low_ex, high_ex = price, price - 0.8, price + 0.1
        elif phase == 1:
            price += 0.5
            c, low_ex, high_ex = price, price - 0.1, price + 0.1
        elif phase == 2:
            price += 0.5
            c, low_ex, high_ex = price, price - 0.1, price + 0.9
        elif phase == 3:
            price -= 0.2
            c, low_ex, high_ex = price, price - 0.1, price + 0.1
        elif phase == 4:
            price -= 0.15
            c, low_ex, high_ex = price, price - 0.85, price + 0.1
        else:
            price += 0.4
            c, low_ex, high_ex = price, price - 0.1, price + 0.1
        close[i], high[i], low[i] = c, high_ex, low_ex
    opened = np.r_[close[0], close[:-1]]
    high = np.maximum(high, np.maximum(opened, close))
    low = np.minimum(low, np.minimum(opened, close))
    intra = pd.DataFrame(
        {"open": opened, "high": high, "low": low, "close": close, "volume": 2_000.0},
        index=index,
    )
    return {"15m": intra, "daily": daily}, intra


def _detector_params(**overrides) -> dict:
    params = dict(DEFAULTS)
    params.update({"ema_intraday": 8, "ema_daily": 8, "require_zone": False, "execution": "15m"})
    params.update(overrides)
    return params


def test_grid_is_one_change_from_the_default():
    cells = grid()
    assert cells[0] == DEFAULTS
    assert len(cells) == 7
    for cell in cells[1:]:
        changed = [key for key in DEFAULTS if cell[key] != DEFAULTS[key]]
        assert len(changed) == 1
    assert majority_needed(5) == 4
    assert majority_needed(3) == 2


def test_trend_flags_require_higher_highs_and_higher_lows():
    frame = _zigzag_ohlc(80, start=100.0)
    frame.index = pd.bdate_range("2023-01-02", periods=80)
    flags = trend_flags(frame, ema_window=10, left=2, right=2)
    assert bool(flags["up"].iloc[-1])
    assert not bool(flags["down"].iloc[-1])

    from webull_bot.indicators import ema

    broken = frame.copy()
    # A lower swing low, unique in its neighborhood, breaks the up structure.
    broken.iloc[-8, broken.columns.get_loc("low")] = float(broken["low"].iloc[-20]) - 4.0
    broken.iloc[-8, broken.columns.get_loc("close")] = float(broken["low"].iloc[-8]) + 0.2
    broken_flags = trend_flags(broken, ema_window=10, left=2, right=2)
    average = ema(broken["close"], 10)
    failed = broken_flags.index[~broken_flags["up"].to_numpy()]
    assert len(failed)
    # The close can still sit above a rising EMA. Structure is what fails.
    spot = failed[-1]
    assert float(broken.loc[spot, "close"]) > float(average.loc[spot])
    assert not bool(broken_flags.loc[spot, "up"])


def test_session_vwap_resets_each_day():
    index = []
    for day in pd.bdate_range("2024-06-03", periods=2):
        for minute in range(9 * 60 + 30, 16 * 60, 15):
            index.append(pd.Timestamp(day).tz_localize(NY) + pd.Timedelta(minutes=minute))
    index = pd.DatetimeIndex(index)
    close = np.linspace(100, 110, len(index))
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": 1_000.0,
        },
        index=index,
    )
    vwap = session_vwap(bars)
    second = vwap.index.date == index[-1].date()
    first_bar = vwap.loc[second].iloc[0]
    typical = (bars.iloc[-26]["high"] + bars.iloc[-26]["low"] + bars.iloc[-26]["close"]) / 3.0
    assert abs(float(first_bar["vwap"]) - typical) < 1e-9
    assert float(first_bar["vwap"]) != float(vwap.iloc[25]["vwap"])


def test_weekly_from_daily_accepts_a_timezone():
    daily = _weekly_friendly_daily(weeks=8)
    weekly = weekly_from_daily(daily)
    assert len(weekly) >= 2
    assert weekly.index.tz is not None
    assert all(stamp.hour == 16 for stamp in weekly.index)


def test_long_vwap_test_confirms_on_the_next_bar_and_fills_after_it():
    bundle, bars = _intraday_bundle()
    setups = find_setups(bundle, _detector_params(), symbol="SPY")
    longs = [setup for setup in setups if setup.direction == "long"]
    assert longs, "expected a long VWAP test"
    setup = longs[0]
    assert setup.fill_time > setup.confirm_time > setup.test_time
    loc = bars.index.get_loc(setup.test_time)
    assert bars.index[loc + 1] == setup.confirm_time
    assert bars.index[loc + 2] == setup.fill_time
    assert not any(item.direction == "short" and item.test_time == setup.test_time for item in setups)


def test_a_bearish_next_bar_does_not_confirm():
    bundle, bars = _intraday_bundle()
    params = _detector_params()
    original = find_setups(bundle, params, symbol="SPY")
    assert original
    target = original[0].test_time
    confirm_loc = bars.index.get_loc(original[0].confirm_time)
    bars = bars.copy()
    high = float(bars.iloc[confirm_loc]["high"])
    low = float(bars.iloc[confirm_loc]["low"])
    bars.iloc[confirm_loc, bars.columns.get_loc("open")] = high
    bars.iloc[confirm_loc, bars.columns.get_loc("close")] = low
    bars.iloc[confirm_loc, bars.columns.get_loc("high")] = high
    bars.iloc[confirm_loc, bars.columns.get_loc("low")] = low
    bundle = dict(bundle)
    bundle["15m"] = bars
    again = find_setups(bundle, params, symbol="SPY")
    assert all(setup.test_time != target for setup in again)


def _invert(frame: pd.DataFrame, anchor: float = 400.0) -> pd.DataFrame:
    out = frame.copy()
    out["open"] = anchor - frame["open"]
    out["close"] = anchor - frame["close"]
    out["high"] = anchor - frame["low"]
    out["low"] = anchor - frame["high"]
    return out


def test_downtrend_is_the_mirror():
    bundle, bars = _intraday_bundle()
    setups = find_setups(
        {"15m": _invert(bars), "daily": _invert(bundle["daily"])},
        _detector_params(),
        symbol="SPY",
    )
    assert setups
    assert all(setup.direction == "short" for setup in setups)
    assert setups[0].fill_time > setups[0].confirm_time


def test_require_zone_rejects_a_test_far_from_support():
    bundle, _bars = _intraday_bundle()
    near = find_setups(bundle, _detector_params(require_zone=False), symbol="SPY")
    far = find_setups(bundle, _detector_params(require_zone=True, zone_atr=0.05), symbol="SPY")
    assert near
    assert len(near) > len(far)


def test_truncating_the_future_does_not_change_an_earlier_setup():
    bundle, bars = _intraday_bundle()
    params = _detector_params()
    full = find_setups(bundle, params, symbol="SPY")
    assert full
    cut_at = bars.index.get_loc(full[0].fill_time) + 1
    trimmed = dict(bundle)
    trimmed["15m"] = bars.iloc[:cut_at]
    early = find_setups(trimmed, params, symbol="SPY")
    assert early
    assert early[0].test_time == full[0].test_time
    assert early[0].direction == full[0].direction
    assert early[0].fill_time == full[0].fill_time
    assert early[0].stop == full[0].stop


def _execution(fill: pd.Timestamp, rows: list[tuple]) -> pd.DataFrame:
    index = pd.DatetimeIndex([fill + pd.Timedelta(minutes=15 * i) for i in range(len(rows))])
    if index.tz is None:
        index = index.tz_localize(NY)
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index)
    frame["volume"] = 1_000.0
    return frame


def _daily_vol() -> pd.DataFrame:
    index = pd.bdate_range("2024-03-01", periods=40)
    close = 40 + np.linspace(0, 2, len(index)) + np.sin(np.arange(len(index))) * 0.4
    opened = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "open": opened,
            "high": np.maximum(opened, close) + 0.3,
            "low": np.minimum(opened, close) - 0.3,
            "close": close,
            "volume": 1_000_000.0,
        },
        index=index,
    )


def test_one_contract_is_skipped_when_the_debit_exceeds_the_cap():
    fill = pd.Timestamp("2024-06-04 10:00", tz=NY)
    setup = Setup("SPY", "long", fill, fill, fill, 500.0, 500.0, 490.0, 520.0, 2.0)
    bars = _execution(fill, [(500, 501, 499, 500.5), (500.5, 502, 500, 501)])
    daily = {"SPY": _daily_vol()}
    params = dict(DEFAULTS)
    params.update({"premium_cap": 0.25, "dte": 14, "delta": 0.50, "max_positions": 1})
    stats = simulate_options([setup], {"SPY": bars}, daily, params, starting_equity=1_000.0)
    assert stats.trades.empty
    assert stats.premium_skipped >= 1
    assert stats.ending_equity == 1_000.0


def test_pdt_blocks_the_fourth_same_day_round_trip():
    start = pd.Timestamp("2024-06-04 10:00", tz=NY)
    setups = []
    rows = []
    for i in range(4):
        fill = start + pd.Timedelta(minutes=15 * i)
        setups.append(Setup("AMD", "long", fill, fill, fill, 20.0, 20.0, 21.0, None, 0.4))
        rows.append((20.0, 20.4, 19.0, 19.5))
    bars = _execution(start, rows)
    params = dict(DEFAULTS)
    params.update({"premium_cap": 0.25, "max_positions": 1, "account": "margin_pdt", "dte": 14})
    stats = simulate_stock(setups, {"AMD": bars}, {}, params, starting_equity=1_000.0)
    assert len(stats.trades) == 3
    assert stats.pdt_blocked >= 1


def test_cash_account_does_not_reuse_sale_proceeds_the_same_day():
    first = pd.Timestamp("2024-06-04 10:00", tz=NY)
    second = first + pd.Timedelta(minutes=15)
    setups = [
        Setup("AMD", "long", first, first, first, 100.0, 100.0, 399.5, None, 1.0),
        Setup("AMD", "long", second, second, second, 100.0, 100.0, 90.0, None, 1.0),
    ]
    bars = _execution(first, [(400.0, 401.0, 399.0, 400.0), (700.0, 701.0, 699.0, 700.0)])
    params = dict(DEFAULTS)
    params.update({"premium_cap": 0.50, "max_positions": 1, "account": "cash_t1"})
    stats = simulate_stock(setups, {"AMD": bars}, {}, params, starting_equity=1_000.0)
    assert len(stats.trades) == 1
    assert stats.premium_skipped >= 1


def test_premium_stop_wins_when_the_same_bar_could_hit_both():
    fill = pd.Timestamp("2024-06-04 10:00", tz=NY)
    later = fill + pd.Timedelta(minutes=15)
    setup = Setup("AMD", "long", fill, fill, fill, 40.0, 40.0, 10.0, None, 0.5)
    bars = _execution(fill, [(40.0, 40.4, 39.8, 40.1), (40.1, 80.0, 20.0, 40.0)])
    params = dict(DEFAULTS)
    params.update(
        {
            "premium_cap": 0.80,
            "premium_stop": -0.50,
            "premium_target": 0.50,
            "dte": 14,
            "delta": 0.50,
            "max_hold_sessions": 5,
            "use_level_target": False,
        }
    )
    stats = simulate_options([setup], {"AMD": bars}, {"AMD": _daily_vol()}, params, starting_equity=1_000.0)
    assert len(stats.trades) == 1
    assert stats.trades.iloc[0]["reason"] == "premium_stop"
    assert stats.trades.iloc[0]["exit_time"] == later
