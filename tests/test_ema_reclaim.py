"""The 2026-10-07 reclaim sequence. No network and no broker."""

from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.ema_reclaim import (
    FEATURE_Q,
    FEATURES,
    FLAT,
    LAST_CONFIRM,
    STOP_PAD,
    Prepared,
    Setup,
    analyze_features,
    feature_names,
    find_setups,
    frozen_rules,
    long_roles,
    simulate,
    walk,
)

NY = "America/New_York"


def _prep(n: int, day: str = "2024-06-03", **columns) -> Prepared:
    stamps = pd.date_range(f"{day} 09:30", periods=n, freq="5min", tz=NY)
    zeros = np.zeros(n, dtype=float)
    ones = np.ones(n, dtype=float)

    def col(name: str, default: np.ndarray) -> np.ndarray:
        if name not in columns:
            return default
        return np.asarray(columns[name], dtype=float)

    close = col("close", np.full(n, 100.0))
    return Prepared(
        index=pd.DatetimeIndex(stamps),
        open=col("open", close.copy()),
        high=col("high", close + 0.2),
        low=col("low", close - 0.2),
        close=close,
        volume=col("volume", np.full(n, 1000.0)),
        ema9=col("ema9", np.full(n, 101.0)),
        ema20=col("ema20", np.full(n, 102.0)),
        ema200=col("ema200", np.full(n, 110.0)),
        atr=col("atr", ones.copy()),
        vwap=col("vwap", np.full(n, 103.0)),
        std=col("std", ones.copy()),
        macd_line=col("macd_line", zeros.copy()),
        macd_signal=col("macd_signal", zeros.copy()),
        macd_hist=col("macd_hist", zeros.copy()),
        rsi=col("rsi", np.full(n, 50.0)),
        hammer=np.zeros(n, dtype=bool),
        engulf_bull=np.zeros(n, dtype=bool),
        morning=np.zeros(n, dtype=bool),
        shooting=np.zeros(n, dtype=bool),
        engulf_bear=np.zeros(n, dtype=bool),
        evening=np.zeros(n, dtype=bool),
        dates=[stamp.date() for stamp in stamps],
        times=[stamp.time() for stamp in stamps],
    )


def _sequence() -> Prepared:
    """Rejections, a crack, a pullback, then a trigger. Indexes 4, 5, 7, 8, 9."""
    n = 12
    ema9 = np.linspace(110.0, 104.5, n)
    ema20 = ema9 + 1.5
    close = ema9 - 1.0
    open_ = close + 0.2
    high = close + 0.3
    low = close - 0.3
    # Two tags that close back under the 9.
    for i in (4, 5):
        high[i] = ema9[i]
        close[i] = ema9[i] - 0.4
        open_[i] = close[i] + 0.2
        low[i] = close[i] - 0.2
    # Prior red bar, then a green crack through its high and both EMAs.
    open_[6] = 106.0
    close[6] = 105.0
    high[6] = 106.2
    low[6] = 104.8
    open_[7] = 105.2
    close[7] = max(high[6], ema20[7]) + 0.5
    high[7] = close[7] + 0.2
    low[7] = open_[7] - 0.1
    # Pullback tags the 9 and holds.
    open_[8] = close[7] - 0.2
    low[8] = ema9[8] - 0.05
    close[8] = ema9[8] + 0.2
    high[8] = close[8] + 0.1
    # Trigger above 9, 20, and VWAP. Confirmation and fill follow.
    level = max(ema9[9], ema20[9], 103.0) + 0.4
    open_[9] = level - 0.3
    close[9] = level
    high[9] = level + 0.2
    low[9] = open_[9] - 0.1
    open_[10] = close[9]
    close[10] = close[9] + 0.3
    high[10] = close[10] + 0.1
    low[10] = open_[10] - 0.1
    open_[11] = close[10]
    close[11] = open_[11]
    high[11] = open_[11] + 0.2
    low[11] = open_[11] - 0.2
    vwap = np.full(n, 120.0)
    vwap[9] = 100.0
    return _prep(n, open=open_, high=high, low=low, close=close, ema9=ema9, ema20=ema20, vwap=vwap)


def _by(prep: Prepared, name: str) -> list[Setup]:
    return [item for item in find_setups(prep, "SPY") if item.variant == name]


def test_rules_name_the_order_and_the_survive_line():
    rules = frozen_rules()
    assert rules["variants"]["strict"].startswith("Steps 1 through 5")
    assert "Drop step 2" in rules["variants"]["no_crack"]
    assert "Drop step 3" in rules["variants"]["no_pullback"]
    assert "at or under 0.10" in rules["feature_outcome"]
    assert rules["not_live"].startswith("Not a live strategy")
    assert FLAT == time(15, 30)
    assert LAST_CONFIRM == time(15, 20)
    assert len(FEATURES) == 22


def test_strict_needs_the_pullback_after_the_crack_and_a_green_confirmation():
    prep = _sequence()
    strict = _by(prep, "strict")
    assert len(strict) == 1
    signal = strict[0]
    assert signal.direction == "long"
    assert signal.trigger_i == 9
    assert signal.confirm_i == 10
    assert signal.fill_i == 11
    assert signal.crack_i == 7
    assert signal.pull_i == 8
    assert signal.stop == float(prep.low[9] - STOP_PAD)
    assert "strict" not in {item.variant for item in find_setups(prep, "SPY") if False}
    red = _sequence()
    red.close = red.close.copy()
    red.open = red.open.copy()
    red.close[10] = red.open[10] - 0.2
    assert _by(red, "strict") == []
    # The pullback has to sit between the crack and the trigger.
    skipped = _sequence()
    skipped.low = skipped.low.copy()
    skipped.close = skipped.close.copy()
    skipped.low[8] = skipped.ema9[8] + 2.0
    skipped.close[8] = skipped.ema9[8] + 2.0
    assert _by(skipped, "strict") == []
    assert len(_by(skipped, "no_pullback")) == 1
    assert _by(skipped, "no_pullback")[0].trigger_i == 9


def test_dropping_the_crack_still_fires_and_the_mirror_stops_above_the_trigger():
    prep = _sequence()
    # Remove the crack's close through the averages. The pullback and the rejections remain.
    muted = _sequence()
    muted.close = muted.close.copy()
    muted.high = muted.high.copy()
    muted.open = muted.open.copy()
    muted.close[7] = muted.ema9[7] - 0.5
    muted.open[7] = muted.close[7] - 0.2
    muted.high[7] = muted.ema9[7] - 0.2
    assert _by(muted, "strict") == []
    # The trigger bar itself still clears the prior high, so dropping the pullback keeps it.
    dropped = _by(muted, "no_pullback")
    assert len(dropped) == 1 and dropped[0].crack_i == 9
    no_crack = _by(muted, "no_crack")
    assert len(no_crack) == 1
    assert no_crack[0].trigger_i == 9
    assert len(_by(prep, "no_crack_no_pullback")) == 1
    short = _mirror(prep)
    shorts = _by(short, "strict")
    assert len(shorts) == 1
    assert shorts[0].direction == "short"
    assert shorts[0].stop == float(short.high[9] + STOP_PAD)


def _mirror(prep: Prepared) -> Prepared:
    """Flip the long sequence through 100 so the short rules see the same shape."""
    def flip(values: np.ndarray) -> np.ndarray:
        return 200.0 - values

    return _prep(
        len(prep.close),
        open=flip(prep.open),
        high=flip(prep.low),
        low=flip(prep.high),
        close=flip(prep.close),
        ema9=flip(prep.ema9),
        ema20=flip(prep.ema20),
        ema200=flip(prep.ema200),
        vwap=flip(prep.vwap),
        atr=prep.atr,
        volume=prep.volume,
    )


def test_roles_mark_each_step_and_a_new_session_does_not_inherit_the_crack():
    prep = _sequence()
    assert "rejection" in long_roles(prep, 4, 0)
    assert "crack" in long_roles(prep, 7, 0)
    assert "pullback" in long_roles(prep, 8, 0)
    assert "trigger" in long_roles(prep, 9, 0)
    assert "confirmation" in long_roles(prep, 10, 0)
    second = _sequence()
    # Move the trigger, confirmation, and fill onto the next day. The crack stays behind.
    shift = pd.Timedelta(days=1)
    index = second.index.to_list()
    for i in (9, 10, 11):
        index[i] = index[i] + shift
    second.index = pd.DatetimeIndex(index)
    second.dates = [stamp.date() for stamp in second.index]
    second.times = [stamp.time() for stamp in second.index]
    assert _by(second, "strict") == []


def test_flat_stop_and_half_scale_use_the_trigger_stop_and_the_200():
    prep = _prep(
        8,
        close=np.full(8, 100.0),
        open=np.full(8, 100.0),
        high=np.full(8, 100.4),
        low=np.full(8, 99.6),
        ema9=np.full(8, 90.0),
    )
    prep.times[6] = time(15, 30)
    prep.index = pd.DatetimeIndex(
        list(prep.index[:6]) + [prep.index[6].replace(hour=15, minute=30)] + list(prep.index[7:])
    )
    setup = Setup("SPY", "strict", "long", 2, 3, 4, 1, 2, 99.0)
    # Fill at index 4, open 100. Nothing hits the stop. 15:30 is index 6.
    path = walk(prep, setup, "structure")
    assert path is not None
    assert path["reason"] == "flat"
    assert path["exit_spot"] == float(prep.open[6])
    stopped = _prep(6, open=[100, 100, 100, 100, 100, 98], high=[101] * 6, low=[99, 99, 99, 99, 99, 97], close=[100, 100, 100, 100, 100, 97])
    stopped.ema9 = np.full(6, 90.0)
    hit = walk(stopped, Setup("SPY", "strict", "long", 2, 3, 4, -1, -1, 99.0), "structure")
    assert hit is not None and hit["reason"] == "stop" and hit["exit_spot"] == 99.0
    scaled = _prep(
        7,
        open=[100, 100, 100, 100, 100, 100.2, 100.0],
        high=[100, 100, 100, 100, 100.2, 105.0, 100.2],
        low=[99, 99, 99, 99, 99.5, 100.0, 99.0],
        close=[100, 100, 100, 100, 100.1, 104.0, 99.5],
        ema9=np.full(7, 90.0),
        ema200=np.full(7, 103.0),
    )
    half = walk(scaled, Setup("SPY", "strict", "long", 2, 3, 4, -1, -1, 99.0), "ema200", split_half=True)
    assert half is not None
    assert half["scaled"] is True
    assert half["scale_spot"] == 103.0
    assert half["reason"] == "stop"
    assert half["exit_spot"] == 100.0


def test_a_feature_does_not_read_the_fill_bar_and_the_combo_gate_is_two_sided():
    prep = _prep(26)
    prep.volume = prep.volume.copy()
    prep.volume[:] = 100.0
    prep.volume[23] = 1000.0
    before = feature_names(prep, 23, "long")
    prep.volume[25] = 1.0
    assert feature_names(prep, 23, "long") == before
    assert "volume_expand" in before
    helpful = [{"r": 0.40 + (i % 5) * 0.01, "features": {"volume_expand"}} for i in range(40)]
    helpful += [{"r": -0.20 + (i % 5) * 0.01, "features": set()} for i in range(40)]
    noise = [{"r": 0.05 + (i % 5) * 0.001, "features": {"morning"}} for i in range(40)]
    noise += [{"r": 0.04 + (i % 5) * 0.001, "features": set()} for i in range(40)]
    result = analyze_features(helpful, helpful)
    assert result["survivors"] == ["volume_expand"]
    assert result["rows"][FEATURES.index("volume_expand")]["q"] <= FEATURE_Q
    held = analyze_features(helpful, noise)
    assert held["survivors"] == []


def test_sources_do_not_touch_the_forward_test():
    root = Path("src/webull_bot/chart_reads")
    for name in ("ema_reclaim.py", "research_ema_reclaim.py", "band_exit.py", "research_band_exit.py"):
        text = (root / name).read_text()
        for banned in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
            assert banned not in text
        assert "live_trading_enabled" not in text


def test_share_book_is_long_only_and_flat_books_the_open():
    prep = _sequence()
    setups = _by(prep, "strict")
    book = simulate(prep, setups, mode="structure", kind="shares", stake=1000.0, long_only=True, start=date(2024, 6, 3), end=date(2024, 6, 3))
    assert book["metrics"]["trades"] == 1
    short_only = simulate(prep, _by(_mirror(prep), "strict"), mode="structure", kind="shares", stake=1000.0, long_only=True)
    assert short_only["metrics"]["trades"] == 0
    assert short_only["skips"]["short"] == 1


def _band_setup() -> Setup:
    return Setup("SPY", "strict", "long", 2, 3, 4, -1, -1, 99.0)


def test_opposite_band_exits_the_whole_position_and_ignores_a_later_bar():
    rules = frozen_rules()
    assert "upper band for a long" in rules["band"]
    assert "sell half at the first" in rules["band200"]
    prep = _prep(
        8,
        open=[100, 100, 100, 100, 100, 100.2, 100, 100],
        high=[100, 100, 100, 100, 100.2, 102.5, 100, 100],
        low=[99, 99, 99, 99, 99.5, 99.8, 99, 99],
        close=[100, 100, 100, 100, 100.1, 102.0, 100, 100],
        ema9=np.full(8, 90.0),
        vwap=np.full(8, 100.0),
        std=np.full(8, 1.0),
    )
    path = walk(prep, _band_setup(), "band")
    assert path is not None
    assert path["reason"] == "band"
    assert path["exit_spot"] == 102.0
    assert path["scaled"] is False
    later = _prep(
        8,
        open=[100, 100, 100, 100, 100, 100.2, 100, 100],
        high=[100, 100, 100, 100, 100.2, 102.5, 1000, 100],
        low=[99, 99, 99, 99, 99.5, 99.8, 99, 99],
        close=[100, 100, 100, 100, 100.1, 102.0, 100, 100],
        ema9=np.full(8, 90.0),
        vwap=np.array([100, 100, 100, 100, 100, 100, 1, 100], dtype=float),
        std=np.full(8, 1.0),
    )
    again = walk(later, _band_setup(), "band")
    assert again["exit_spot"] == path["exit_spot"]
    assert again["exit_time"] == path["exit_time"]
    quiet = _prep(
        8,
        high=np.full(8, 100.4),
        low=np.full(8, 99.6),
        close=np.full(8, 100.0),
        open=np.full(8, 100.0),
        ema9=np.full(8, 90.0),
        vwap=np.full(8, 100.0),
        std=np.full(8, 1.0),
    )
    held = walk(quiet, _band_setup(), "band")
    assert held is not None and held["reason"] == "last"


def test_half_at_the_first_target_and_the_rest_at_the_other_or_the_9():
    base = dict(
        open=[100, 100, 100, 100, 100, 100.2, 100.4],
        low=[99, 99, 99, 99, 99.5, 99.8, 99.5],
        ema9=np.full(7, 90.0),
        vwap=np.full(7, 100.0),
        std=np.full(7, 1.0),
        ema200=np.full(7, 104.0),
    )
    both = _prep(7, high=[100, 100, 100, 100, 100.2, 103.0, 105.0], close=[100, 100, 100, 100, 100, 102.4, 104.2], **base)
    half = walk(both, _band_setup(), "band200", split_half=True)
    assert half is not None
    assert half["scaled"] is True
    assert half["scale_spot"] == 102.0
    assert half["reason"] == "ema200"
    assert half["exit_spot"] == 104.0
    faded = _prep(7, high=[100, 100, 100, 100, 100.2, 103.0, 100.4], close=[100, 100, 100, 100, 100, 102.4, 90.0], ema9=np.array([90, 90, 90, 90, 90, 90, 95.0]), **{k: v for k, v in base.items() if k != "ema9"})
    rest = walk(faded, _band_setup(), "band200", split_half=True)
    assert rest is not None and rest["reason"] == "ema" and rest["scaled"] is True and rest["exit_spot"] == 90.0
    stopped = _prep(
        7,
        high=[100, 100, 100, 100, 100, 110, 110],
        low=[99, 99, 99, 99, 99, 98, 99],
        close=[100] * 7,
        **{k: v for k, v in base.items() if k != "low"},
    )
    hit = walk(stopped, _band_setup(), "band200", split_half=True)
    assert hit is not None and hit["reason"] == "stop" and hit["scaled"] is False
    only_band = _prep(
        7,
        high=[100, 100, 100, 100, 100.2, 103.0, 100],
        close=[100, 100, 100, 100, 100, 102.4, 100],
        ema200=np.full(7, 90.0),
        **{k: v for k, v in base.items() if k != "ema200"},
    )
    whole = walk(only_band, _band_setup(), "band200", split_half=True)
    assert whole is not None and whole["reason"] == "band" and whole["scaled"] is False and whole["exit_spot"] == 102.0
    contract = walk(both, _band_setup(), "band200", split_half=False)
    assert contract is not None and contract["reason"] == "band" and contract["scaled"] is False and contract["exit_spot"] == 102.0
    short = _prep(
        7,
        open=np.full(7, 100.0),
        high=np.full(7, 100.4),
        low=[100, 100, 100, 100, 100, 97.5, 100],
        close=np.full(7, 99.5),
        ema9=np.full(7, 110.0),
        vwap=np.full(7, 100.0),
        std=np.full(7, 1.0),
    )
    put = walk(short, Setup("SPY", "strict", "short", 2, 3, 4, -1, -1, 101.0), "band")
    assert put is not None and put["reason"] == "band" and put["exit_spot"] == 98.0
