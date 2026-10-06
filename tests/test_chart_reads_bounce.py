"""Frozen checks for the partial-bounce rule. These do not score a book."""

import numpy as np
import pandas as pd

from webull_bot.chart_reads.bounce import find_bounces


def _frame() -> pd.DataFrame:
    """A prior swing low, a rally, a decline, then one confirming retest."""
    count = 180
    index = pd.bdate_range("2018-01-01", periods=count)
    close = np.full(count, 110.0)
    open_ = np.full(count, 110.0)
    high = np.full(count, 112.0)
    low = np.full(count, 108.0)
    volume = np.full(count, 1_000_000.0)
    for i in range(count):
        base = 110.0 + np.sin(i / 5.0) * 1.5
        close[i] = base
        open_[i] = base - 0.4
        high[i] = base + 1.4 + (i % 5) * 0.03
        low[i] = base - 1.4 - (i % 4) * 0.03
    # Confirmed pivot low at bar 40, price 90.
    low[40] = 90.0
    high[40] = 94.0
    open_[40] = 93.0
    close[40] = 91.0
    # Rally into a pivot high, then a long decline that leaves RSI weak.
    for i in range(70, 100):
        close[i] = 112.0 + (i - 70) * 0.6
        open_[i] = close[i] - 0.5
        high[i] = close[i] + 1.2
        low[i] = close[i] - 1.0
    high[90] = 148.0
    for i in range(100, 130):
        close[i] = 130.0 - (i - 100) * 1.05
        open_[i] = close[i] + 0.8
        high[i] = close[i] + 1.1
        low[i] = close[i] - 0.6
    # Confirming retest of the 90 low. Neighbors stay above it.
    open_[130] = 91.0
    low[130] = 90.2
    high[130] = 100.0
    close[130] = 98.0
    volume[128:131] = 400_000.0
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


def test_retest_is_one_bounce_with_a_stop_under_the_low():
    frame = _frame()
    setups = find_bounces(frame, "TEST")
    assert len(setups) == 1
    setup = setups[0]
    assert setup.direction == "long"
    assert setup.kind == "bounce"
    assert setup.signal_time == frame.index[130]
    assert setup.fill_time == frame.index[131]
    assert setup.anchor_time == frame.index[40]
    assert setup.stop < 90.2
    assert setup.stop > 90.2 - 5.0
    assert np.isfinite(setup.reference)
    assert setup.reference > float(frame["close"].iloc[130])
    assert setup.reference < 148.0
    assert setup.reversal > setup.reference


def test_quiet_volume_is_optional():
    frame = _frame()
    frame.loc[frame.index[128:131], "volume"] = 5_000_000.0
    assert len(find_bounces(frame, "TEST")) == 1
    assert find_bounces(frame, "TEST", quiet=True) == []


def test_closing_through_the_low_is_not_a_bounce():
    frame = _frame()
    frame.loc[frame.index[130], "close"] = 88.0
    frame.loc[frame.index[130], "open"] = 91.0
    assert find_bounces(frame, "TEST") == []


def test_a_later_bar_does_not_change_the_signal():
    frame = _frame()
    original = find_bounces(frame, "TEST")[0]
    changed = frame.copy()
    changed.loc[changed.index[-1], "close"] = 200.0
    changed.loc[changed.index[-1], "high"] = 205.0
    again = find_bounces(changed, "TEST")[0]
    assert again.signal_time == original.signal_time
    assert again.stop == original.stop
    assert again.reference == original.reference
    assert again.reversal == original.reversal
