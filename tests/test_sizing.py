from webull_bot.risk.sizing import position_risk_dollars, shares_for_risk


def test_fixed_fractional_size():
    # $100,000 equity, 1% risk, $2 of stop distance -> 500 shares.
    qty = shares_for_risk(100_000, 50, 48, 0.01, max_position_pct=1.0)
    assert qty == 500
    assert position_risk_dollars(50, 48, qty) == 1000


def test_max_position_cap_reduces_risk_not_increases_it():
    qty = shares_for_risk(100_000, 50, 48, 0.01, max_position_pct=0.10)
    # Uncapped would be 500 shares ($25,000). Cap is $10,000 / $50 = 200.
    assert qty == 200
    assert position_risk_dollars(50, 48, qty) < 100_000 * 0.01


def test_rejects_bad_stops_and_sub_share_results():
    assert shares_for_risk(100_000, 50, 50, 0.01, 0.2) == 0
    assert shares_for_risk(100_000, 50, 55, 0.01, 0.2) == 0
    assert shares_for_risk(100, 500, 450, 0.01, 1.0) == 0  # $1 of risk cannot buy one share


def test_cash_cap():
    qty = shares_for_risk(100_000, 50, 48, 0.01, 1.0, cash_available=5_000)
    assert qty == 100
