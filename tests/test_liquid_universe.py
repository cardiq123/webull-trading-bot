"""The option universe is registered, and the share book does not inherit it."""

from datetime import date

from webull_bot.chart_reads.liquid import LIQUID_BLUE_CHIPS, dow_members_between
from webull_bot.chart_reads.research import SYMBOLS
from webull_bot.chart_reads.research_atm_universe import GATE
from webull_bot.universe_dow import is_member

REGISTERED = (
    "NVDA",
    "AAPL",
    "UNH",
    "MSFT",
    "AMZN",
    "META",
    "GOOGL",
    "JPM",
    "AMD",
    "TSLA",
    "AVGO",
    "COST",
    "V",
    "MA",
    "LLY",
    "XOM",
    "SPY",
    "QQQ",
)


def test_liquid_list_is_the_registered_snapshot():
    assert LIQUID_BLUE_CHIPS == REGISTERED
    assert "IWM" not in LIQUID_BLUE_CHIPS
    assert LIQUID_BLUE_CHIPS[-2:] == ("SPY", "QQQ")
    assert SYMBOLS == ["SPY", "QQQ", "IWM", "UNH", "AAPL", "AMD", "NVDA", "TSLA", "MSFT", "META"]
    assert GATE == "dow_point_in_time"


def test_gate_membership_is_point_in_time():
    assert is_member("XOM", date(2019, 1, 2))
    assert not is_member("XOM", date(2025, 1, 2))
    assert not is_member("AMZN", date(2020, 1, 2))
    assert is_member("AMZN", date(2025, 1, 2))
    assert not is_member("AMD", date(2025, 6, 2))
    assert not is_member("META", date(2025, 6, 2))
    assert not is_member("SPY", date(2025, 6, 2))
    assert "AMZN" in dow_members_between(date(2024, 1, 1), date(2026, 10, 6))
    assert "AMD" not in dow_members_between(date(2024, 1, 1), date(2026, 10, 6))
