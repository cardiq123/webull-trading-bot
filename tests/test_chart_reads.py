"""Offline tests for the chart-read detector and the $1,000 book.

No network. These do not run the research download.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from webull_bot.chart_reads.detect import Setup, find_setups, session_bands, strong_candle
from webull_bot.chart_reads.params import DEFAULTS, htf_allows
from webull_bot.chart_reads.simulate import simulate

NY = "America/New_York"


def _daily(up: bool = True) -> pd.DataFrame:
    index = pd.bdate_range("2026-05-01", periods=40)
    close = np.linspace(80, 120, 40) if up else np.linspace(120, 80, 40)
    wobble = np.sin(np.linspace(0, 6, 40))
    close = close + wobble
    return pd.DataFrame(
        {"open": close, "high": close + 1.0, "low": close - 1.0, "close": close, "volume": 1_000_000.0},
        index=index,
    )


def _frame(rows: list[tuple[float, float, float, float]], day: str = "2026-07-13") -> pd.DataFrame:
    start = pd.Timestamp(day).tz_localize(NY) + pd.Timedelta(hours=9, minutes=30)
    index = pd.date_range(start, periods=len(rows), freq="5min")
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index)
    frame["volume"] = 100_000.0
    return frame


def _pad(rows: list[tuple[float, float, float, float]], n: int = 3):
    last = rows[-1][3]
    for _ in range(n):
        rows.append((last, last + 0.05, last - 0.05, last))
    return rows


def _climb(bars: int = 36, start: float = 100.0, step: float = 0.25):
    rows = []
    price = start
    for _ in range(bars):
        opened = price
        close = price + step
        rows.append((opened, close + 0.05, opened - 0.05, close))
        price = close
    return rows, price


def _long_rows():
    rows, price = _climb()
    opened = price
    close = price + 1.2
    rows.append((opened, close + 0.1, opened, close))
    price = close
    for _ in range(3):
        opened = price
        close = price - 0.45
        rows.append((opened, opened + 0.05, close - 0.15, close))
        price = close
    opened = price
    close = price + 0.9
    rows.append((opened, close + 0.02, opened - 0.02, close))
    return _pad(rows)


def _failed_rows():
    rows, price = _climb(30, step=0.15)
    zone = price
    opened = price
    close = price + 1.5
    rows.append((opened, close + 0.4, opened, close))
    price = close
    opened = price
    close = zone - 0.2
    rows.append((opened, opened + 0.1, close - 0.2, close))
    price = close
    for _ in range(14):
        opened = price
        close = price - 0.7
        rows.append((opened, opened + 0.05, close - 0.1, close))
        price = close
    return _pad(rows)


def _params() -> dict:
    params = dict(DEFAULTS)
    params["execution"] = "5m"
    return params


def test_strong_candle_thresholds():
    assert strong_candle(9.2, 11, 9, 10.8, "long", 0.50, 2 / 3)
    assert not strong_candle(10, 11, 9, 10.2, "long", 0.50, 2 / 3)
    assert strong_candle(10.8, 11, 9, 9.2, "short", 0.50, 2 / 3)
    assert not strong_candle(10.8, 11, 9, 9.2, "long", 0.50, 2 / 3)


def test_majority_is_not_unanimous():
    assert htf_allows(["up", "up", "mixed"], "long", "A")
    assert not htf_allows(["up", "mixed", "mixed"], "long", "A")
    assert htf_allows(["up", "none"], "long", "A")
    assert not htf_allows(["none"], "long", "A")
    assert not htf_allows(["up", "up", "up"], "short", "B")
    assert htf_allows(["up", "mixed", "mixed"], "short", "B")
    assert htf_allows([], "short", "B")


def test_continuation_and_a_close_through_the_20_rejects_it():
    setups = find_setups({"5m": _frame(_long_rows()), "daily": _daily(True)}, _params(), symbol="TEST")
    longs = [setup for setup in setups if setup.kind == "A" and setup.direction == "long"]
    assert longs
    assert longs[0].fill_time > longs[0].signal_time

    rows, price = _climb()
    opened = price
    close = price + 1.2
    rows.append((opened, close + 0.1, opened, close))
    price = close
    rows.append((price, price + 0.05, price - 8.0, price - 7.0))
    knifed = find_setups({"5m": _frame(_pad(rows)), "daily": _daily(True)}, _params(), symbol="TEST")
    assert not any(setup.kind == "A" and setup.direction == "long" for setup in knifed)


def test_failed_breakout_cross_and_a_confirming_close():
    failed = find_setups({"5m": _frame(_failed_rows())}, _params(), symbol="TEST")
    shorts = [setup for setup in failed if setup.kind == "B" and setup.direction == "short"]
    assert shorts
    blocked = find_setups({"5m": _frame(_failed_rows()), "daily": _daily(True)}, _params(), symbol="TEST")
    assert not any(setup.kind == "B" and setup.direction == "short" for setup in blocked)

    rows, price = _climb(30, step=0.15)
    opened = price
    close = price + 1.5
    rows.append((opened, close + 0.4, opened, close))
    price = close
    for _ in range(8):
        opened = price
        close = price + 0.1
        rows.append((opened, close + 0.05, opened - 0.02, close))
        price = close
    confirmed = find_setups({"5m": _frame(_pad(rows))}, _params(), symbol="TEST")
    assert not any(setup.kind == "B" for setup in confirmed)


def test_fill_is_the_next_bar_and_the_future_does_not_move_it():
    frame = _frame(_long_rows())
    bundle = {"5m": frame, "daily": _daily(True)}
    first = find_setups(bundle, _params(), symbol="TEST")
    assert first
    signal = first[0].signal_time
    assert first[0].fill_time == frame.index[frame.index.get_loc(signal) + 1]

    loc = frame.index.get_loc(first[0].fill_time)
    trimmed = find_setups({"5m": frame.iloc[: loc + 1], "daily": _daily(True)}, _params(), symbol="TEST")
    assert any(setup.signal_time == signal for setup in trimmed)

    extra = frame.copy()
    last = extra.index[-1]
    more = pd.date_range(last + pd.Timedelta(minutes=5), periods=6, freq="5min")
    tail = pd.DataFrame(
        {"open": 110.0, "high": 110.2, "low": 109.8, "close": 110.0, "volume": 100_000.0},
        index=more,
    )
    longer = pd.concat([extra, tail])
    again = find_setups({"5m": longer, "daily": _daily(True)}, _params(), symbol="TEST")
    assert any(setup.signal_time == signal for setup in again)


def test_session_bands_are_two_deviations():
    frame = _frame(_long_rows())
    bands = session_bands(frame, 2.0)
    assert len(bands) == len(frame)
    assert (bands["upper"] >= bands["vwap"]).all()
    assert (bands["vwap"] >= bands["lower"]).all()
    assert float(bands["std"].iloc[-1]) > 0


def _flat(day: str, n: int, price: float, low: float) -> pd.DataFrame:
    start = pd.Timestamp(day).tz_localize(NY) + pd.Timedelta(hours=9, minutes=30)
    index = pd.date_range(start, periods=n, freq="5min")
    close = np.full(n, price)
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.2,
            "low": np.full(n, low),
            "close": close,
            "volume": np.full(n, 100_000.0),
        },
        index=index,
    )
    return frame


def _hand(symbol: str, index: pd.DatetimeIndex, i: int, stop: float) -> Setup:
    return Setup(
        symbol=symbol,
        direction="long",
        kind="A",
        signal_time=index[i - 1],
        fill_time=index[i],
        anchor_time=index[i - 2],
        stop=stop,
        atr=1.0,
        reference=stop + 3.0,
    )


def test_contract_and_spread_are_skipped_when_the_debit_does_not_fit():
    frame = _flat("2026-07-13", 8, 800.0, 780.0)
    daily = _daily(True)
    daily["close"] = np.linspace(480, 520, len(daily))
    setup = _hand("SPY", frame.index, 2, 790.0)
    params = _params()
    params["expression"] = "single"
    params["risk_fraction"] = 0.20
    params["dte"] = 3
    skipped = simulate([setup], {"SPY": frame}, {"SPY": daily}, params)
    assert skipped.metrics["trades"] == 0
    assert skipped.premium_skipped >= 1

    params["expression"] = "spread"
    params["risk_fraction"] = 0.05
    params["spread_width"] = 5.0
    spread = simulate([setup], {"SPY": frame}, {"SPY": daily}, params)
    assert spread.metrics["trades"] == 0
    assert spread.premium_skipped >= 1

    other = _hand("AMD", frame.index, 2, 790.0)
    params["risk_fraction"] = 0.20
    refused = simulate([other], {"AMD": frame}, {"AMD": daily}, params)
    assert refused.metrics["trades"] == 0


def test_pdt_blocks_the_fourth_day_trade():
    frame = _flat("2026-07-13", 10, 50.0, 40.0)
    setups = [_hand("TEST", frame.index, i, 48.0) for i in (1, 3, 5, 7)]
    params = _params()
    params["expression"] = "stock"
    params["risk_fraction"] = 0.20
    stats = simulate(setups, {"TEST": frame}, {}, params)
    assert stats.metrics["trades"] == 3
    assert stats.pdt_blocked >= 1


def test_cash_account_does_not_reuse_a_sale_the_same_day():
    frame = _flat("2026-07-13", 8, 50.0, 40.0)
    setups = [_hand("TEST", frame.index, i, 45.0) for i in (1, 4)]
    params = _params()
    params["expression"] = "stock"
    params["risk_fraction"] = 0.90
    params["account"] = "cash_t1"
    cash = simulate(setups, {"TEST": frame}, {}, params)
    assert cash.metrics["trades"] == 1
    assert cash.premium_skipped >= 1

    params["account"] = "margin_pdt"
    margin = simulate(setups, {"TEST": frame}, {}, params)
    assert margin.metrics["trades"] == 2
