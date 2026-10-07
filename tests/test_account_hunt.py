"""The second small-account search is frozen before it is scored."""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.account_hunt import (
    BAND,
    CONSERVATIVE_DRAWDOWN,
    IBS_ENTRY,
    MOM_TOP,
    RSI_ENTRY,
    SECTOR_TOP,
    assign_tiers,
    calendar_weights,
    change_rows,
    frozen_rules,
    hysteresis,
    mean_reversion_weights,
    qqq_overlay_weights,
    scaled_weight,
    sector_weights,
    session_flags,
    simulate_covered_call,
    simulate_wheel,
    stock_momentum_weights,
)
from webull_bot.account_winners import HOLDOUT_START

ROOT = Path(__file__).resolve().parents[1]


def _ohlc(close: pd.Series, spread: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": close,
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": 1_000_000.0,
        },
        index=close.index,
    )


def _book(name: str, *, winner: bool, raw: bool, dd: float, calmar: float, train_ok: bool = True) -> dict:
    return {
        "name": name,
        "eligible": True,
        "holdout": {"cagr": 0.10, "max_drawdown": dd, "sharpe": 1.0, "calmar": calmar, "years": 9.0},
        "verdict": {"winner_vs_spy": winner, "beats_spy_raw": raw, "train_ok": train_ok},
    }


def test_rules_name_the_frozen_variants_and_no_score():
    rules = frozen_rules()
    assert rules["holdout_start"] == str(HOLDOUT_START.date())
    text = "\n".join(str(value) for value in rules.values())
    assert "RSI(2) below 10" in rules["mean_reversion"]
    assert "5-day" in rules["mean_reversion"]
    assert "IBS below 0.2" in rules["mean_reversion"]
    assert "Three lower closes" in rules["mean_reversion"]
    assert "otherwise holds QQQ" in rules["mean_reversion"]
    assert "1.03" in rules["levered_trend"]
    assert "0.97" in rules["levered_trend"]
    assert "0.20" in rules["levered_trend"]
    assert "Weekly book" in rules["vol_target"]
    assert "point-in-time Dow" in rules["stock_momentum"]
    assert "not the S&P 100" in rules["stock_momentum"]
    assert "one third" in rules["sector_rotation"]
    assert "first three" in rules["calendar"]
    assert "Wheel on F" in rules["income"]
    assert "milder than 15 percent" in rules["tiers"]
    assert RSI_ENTRY == 10
    assert IBS_ENTRY == 0.2
    assert BAND == 0.03
    assert MOM_TOP == 5
    assert SECTOR_TOP == 3
    assert CONSERVATIVE_DRAWDOWN == -0.15
    assert "ending equity" not in text.lower()
    assert "104,429" not in text


def test_band_keeps_the_position_through_a_small_dip():
    index = pd.bdate_range("2020-01-01", periods=5)
    close = pd.Series([104.0, 101.0, 100.5, 96.0, 110.0], index=index)
    level = pd.Series(100.0, index=index)
    state = hysteresis(close, level, 0.03)
    assert state.tolist() == [True, True, True, False, True]
    plain = hysteresis(close, level, 0.0)
    assert plain.tolist() == [True, True, True, False, True]


def test_vol_weight_caps_at_one_and_is_off_when_the_trend_is_off():
    index = pd.bdate_range("2020-01-01", periods=3)
    on = pd.Series([True, True, False], index=index)
    vol = pd.Series([0.30, 0.10, 0.30], index=index)
    weights = scaled_weight(on, vol, 0.15, "SPY")
    assert weights["SPY"].tolist() == [0.5, 1.0, 0.0]


def test_rsi_signal_does_not_use_the_next_close():
    index = pd.bdate_range("2018-01-01", periods=220)
    close = pd.Series(np.linspace(100.0, 140.0, len(index)), index=index)
    close.iloc[-3:] = [120.0, 100.0, 80.0]
    future_index = index.append(pd.DatetimeIndex([index[-1] + pd.offsets.BDay(1)]))
    future = close.reindex(future_index)
    future.iloc[-1] = 200.0
    prefix = mean_reversion_weights({"SPY": _ohlc(close)}, "rsi2", symbols=("SPY",))
    longer = mean_reversion_weights({"SPY": _ohlc(future.dropna())}, "rsi2", symbols=("SPY",))
    assert float(prefix.loc[index[-1], "SPY"]) == float(longer.loc[index[-1], "SPY"])


def test_overlay_holds_qqq_when_nothing_is_washed_out():
    index = pd.bdate_range("2018-01-01", periods=220)
    close = pd.Series(np.linspace(50.0, 80.0, len(index)), index=index)
    frames = {"SPY": _ohlc(close), "QQQ": _ohlc(close)}
    weights = qqq_overlay_weights(frames)
    assert float(weights.iloc[-1]["QQQ"]) == 1.0
    assert float(weights.iloc[-1].drop(labels=["QQQ"]).sum()) == 0.0


def test_sector_slice_is_cash_when_the_twelve_month_return_is_not_positive():
    index = pd.date_range("2020-01-31", periods=13, freq="ME")
    up = np.linspace(10.0, 20.0, len(index))
    down = np.linspace(20.0, 10.0, len(index))
    flat = np.full(len(index), 10.0)
    monthly = pd.DataFrame({"XLK": up, "XLF": down, "XLE": flat}, index=index)
    weights = sector_weights(monthly, lookback=12, top_n=3)
    last = weights.iloc[-1]
    assert last["XLK"] == pytest_third()
    assert last["XLF"] == 0.0
    assert last["XLE"] == 0.0


def pytest_third() -> float:
    return 1.0 / 3.0


def test_point_in_time_dow_excludes_a_name_that_has_not_joined():
    index = pd.date_range("2016-01-31", periods=14, freq="ME")
    base = np.linspace(10.0, 12.0, len(index))
    rocket = np.linspace(10.0, 40.0, len(index))
    columns = {"NVDA": rocket, "MSFT": base, "JPM": base, "JNJ": base, "KO": base, "XOM": base}
    monthly = pd.DataFrame(columns, index=index)
    gate = pd.Series(True, index=index)
    pit = stock_momentum_weights(monthly, gate, point_in_time=True, top_n=5)
    assert float(pit.loc[index[-1], "NVDA"]) == 0.0
    assert float(pit.loc[index[-1], "MSFT"]) == 0.2
    survivors = stock_momentum_weights(
        monthly,
        gate,
        point_in_time=False,
        top_n=5,
        survivor_asof=date(2026, 10, 6),
    )
    assert float(survivors.loc[index[-1], "NVDA"]) == 0.2


def test_turn_of_month_is_the_last_session_and_the_first_three():
    index = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-31", "2024-02-01", "2024-02-02"]
    )
    flags = session_flags(pd.DatetimeIndex(index))
    assert flags["tom"].tolist() == [True, True, True, False, True, True, True]
    weights = calendar_weights(pd.DatetimeIndex(index), "SPY", "tom")
    # The Jan 31 close knows that Feb 1 is inside the next month's window.
    assert float(weights.loc[pd.Timestamp("2024-01-31"), "SPY"]) == 1.0
    assert float(weights.loc[pd.Timestamp("2024-01-04"), "SPY"]) == 0.0


def test_pre_holiday_is_the_session_before_the_weekday_closure():
    index = pd.to_datetime(["2024-07-02", "2024-07-03", "2024-07-05"])
    flags = session_flags(pd.DatetimeIndex(index))
    assert bool(flags.loc[pd.Timestamp("2024-07-03"), "pre_holiday"]) is True
    assert bool(flags.loc[pd.Timestamp("2024-07-02"), "pre_holiday"]) is False


def test_wheel_assigns_after_a_crash_and_a_small_account_skips():
    index = pd.bdate_range("2020-01-01", periods=90)
    close = pd.Series(10.0, index=index)
    close.iloc[40:] = 4.0
    frame = _ohlc(close, spread=0.05)
    rich = simulate_wheel(frame, starting_equity=5_000.0, trade_start=index[0], trade_end=index[-1])
    assert rich["opens"] >= 1
    assert rich["assignments"] >= 1
    poor = simulate_wheel(
        _ohlc(pd.Series(80.0, index=index), spread=0.05),
        starting_equity=1_000.0,
        trade_start=index[0],
        trade_end=index[-1],
    )
    assert poor["opens"] == 0
    assert poor["skips"] >= 1
    unfit = simulate_covered_call(
        _ohlc(pd.Series(80.0, index=index), spread=0.05),
        starting_equity=5_000.0,
        trade_start=index[0],
        trade_end=index[-1],
    )
    assert unfit["unfit"] is True


def test_tiers_follow_the_drawdown_gates_and_ignore_ineligible_books():
    books = [
        _book("mild", winner=True, raw=False, dd=-0.10, calmar=0.50),
        _book("milder_better", winner=True, raw=False, dd=-0.12, calmar=0.80),
        _book("mid", winner=True, raw=False, dd=-0.25, calmar=0.40),
        _book("fast", winner=False, raw=True, dd=-0.55, calmar=0.30),
        _book("faster", winner=False, raw=True, dd=-0.60, calmar=0.90),
        _book("loser", winner=False, raw=False, dd=-0.05, calmar=2.0),
    ]
    books.append({**_book("hidden", winner=True, raw=True, dd=-0.01, calmar=5.0), "eligible": False})
    tiers = assign_tiers(books)
    assert tiers["conservative"] == "milder_better"
    assert tiers["moderate"] == "mild"
    assert tiers["high_risk"] == "faster"


def test_change_rows_keeps_a_flat_weight_from_trading_every_day():
    index = pd.bdate_range("2020-01-01", periods=4)
    weights = pd.DataFrame({"SPY": [0.0, 1.0, 1.0, 0.0]}, index=index)
    kept = change_rows(weights)
    assert list(kept.index) == [index[0], index[1], index[3]]


def test_source_does_not_touch_the_forward_test():
    for name in ("account_hunt.py", "research_account_hunt.py"):
        text = (ROOT / "src" / "webull_bot" / name).read_text()
        for banned in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
            assert banned not in text
