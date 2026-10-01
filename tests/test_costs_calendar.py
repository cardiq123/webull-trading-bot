from datetime import date

from webull_bot.calendar import easter_sunday, is_regular_hours, is_trading_day, to_ny
from webull_bot.costs import CostModel, sell_regulatory_fees
from datetime import datetime


def test_sec_and_finra_fees_on_a_sale():
    costs = CostModel()
    # 100 shares at $10: SEC 1000 * 20.60/1e6 = 0.0206; TAF 100 * 0.000195 = 0.0195.
    fees = sell_regulatory_fees(10, 100, costs)
    assert abs(fees - (0.0206 + 0.0195)) < 1e-9


def test_taf_cap():
    costs = CostModel()
    fees = sell_regulatory_fees(10, 100_000, costs)
    sec = 10 * 100_000 * costs.sec_fee_per_dollar_sold
    assert abs(fees - (sec + 9.79)) < 1e-6


def test_known_2026_holidays():
    assert easter_sunday(2026) == date(2026, 4, 5)
    assert is_trading_day(date(2026, 4, 3)) is False  # Good Friday
    assert is_trading_day(date(2026, 1, 1)) is False
    assert is_trading_day(date(2026, 1, 19)) is False  # MLK
    assert is_trading_day(date(2026, 11, 26)) is False  # Thanksgiving
    assert is_trading_day(date(2026, 12, 25)) is False
    assert is_trading_day(date(2026, 7, 3)) is False  # July 4 observed Friday
    assert is_trading_day(date(2026, 7, 2)) is True


def test_regular_hours_are_new_york():
    moment = datetime(2026, 9, 25, 14, 0)  # 14:00 UTC = 10:00 ET, a Friday
    assert is_regular_hours(moment.replace(tzinfo=to_ny(moment).tzinfo) if False else __import__("datetime").datetime(2026, 9, 25, 14, 0, tzinfo=__import__("zoneinfo").ZoneInfo("UTC")))
    closed = datetime(2026, 9, 25, 21, 0, tzinfo=__import__("zoneinfo").ZoneInfo("UTC"))
    assert is_regular_hours(closed) is False
