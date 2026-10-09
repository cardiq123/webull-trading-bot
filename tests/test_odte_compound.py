"""Sizing rule for QQQ Aggressive Compound. No market data and no orders."""

from datetime import date

from webull_bot.chart_reads.research_odte_compound import (
    COMPOUND_RULE,
    CONTRACT_CAP,
    PREMIUM_UNIT,
    compound_contracts,
    walk_daily,
)


def test_the_rule_is_one_fraction_of_equity_with_a_one_lot_rescue_and_a_fifty_cap():
    assert "floor(f * equity / (ask * 100))" in COMPOUND_RULE
    assert "2f of equity" in COMPOUND_RULE
    assert "Cap at 50" in COMPOUND_RULE
    assert "10% is the primary" in COMPOUND_RULE
    assert PREMIUM_UNIT == 100.0
    assert CONTRACT_CAP == 50
    assert compound_contracts(2500, 2.0, 0.10) == (1, "size")
    assert compound_contracts(10_000, 1.0, 0.10) == (10, "size")
    assert compound_contracts(2500, 4.0, 0.10) == (1, "rescue")
    assert compound_contracts(2500, 5.0, 0.10) == (1, "rescue")
    assert compound_contracts(2500, 5.01, 0.10) == (0, "dear")
    assert compound_contracts(2500, 1.0, 0.05) == (1, "size")
    assert compound_contracts(2500, 3.0, 0.05) == (0, "dear")
    assert compound_contracts(200_000, 0.40, 0.10) == (50, "cap")
    assert compound_contracts(0, 1.0, 0.10) == (0, "skip")


def test_a_short_ticket_is_skipped_whole_and_the_cap_is_counted():
    first = date(2024, 1, 3)
    second = date(2024, 1, 4)
    third = date(2024, 1, 5)
    # Day 1 buys 1 at ask $2. The credit is still due on day 3, so day 2's equity
    # includes it and the formula asks for 10, which settled cash cannot pay.
    cash_short = [
        (first, third, 0, 1, 200.0, 8000.0, 2.0),
        (second, third, 0, 1, 1000.0, 1000.0, 1.0),
    ]
    _equity, pnls, info = walk_daily(cash_short, [first, second], "compound", 0.10)
    assert info["lots"] == [1]
    assert pnls == [7800.0]
    assert info["cash_skips"] == 1
    assert info["cap_fills"] == 0

    # Day 1's credit settles on day 2 and the next ask is cheap enough to exceed 50.
    capped = [
        (first, second, 0, 1, 10.0, 25000.0, 1.0),
        (second, third, 0, 1, 40.0, 40.0, 0.40),
    ]
    _equity, _pnls, capped_info = walk_daily(capped, [first, second], "compound", 0.10)
    assert capped_info["lots"] == [2, 50]
    assert capped_info["cap_fills"] == 1
    assert capped_info["cap_signals"] == 1

    rescued = [(first, second, 0, 1, 400.0, 400.0, 4.0)]
    _equity, _pnls, rescued_info = walk_daily(rescued, [first], "compound", 0.10)
    assert rescued_info["lots"] == [1]
    assert rescued_info["rescues"] == 1

    dear = [(first, second, 0, 1, 600.0, 600.0, 6.0)]
    _equity, pnls, dear_info = walk_daily(dear, [first], "compound", 0.10)
    assert dear_info["lots"] == []
    assert pnls == []
    assert dear_info["dear_skips"] == 1
