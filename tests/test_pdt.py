from datetime import date

from webull_bot.risk.pdt import (
    TRANSITION_ENDS,
    check_day_trade,
    intraday_margin_ok,
    legacy_rule_applies,
)


def test_legacy_rule_follows_the_2026_transition():
    assert legacy_rule_applies(date(2026, 6, 3), mode="auto") is True
    # During the phase-in the default is still to enforce the old test.
    assert legacy_rule_applies(date(2026, 9, 25), mode="auto", enforce_legacy_during_transition=True) is True
    assert legacy_rule_applies(date(2026, 9, 25), mode="auto", enforce_legacy_during_transition=False) is False
    assert legacy_rule_applies(date(2027, 10, 21), mode="auto", enforce_legacy_during_transition=True) is False
    assert TRANSITION_ENDS == date(2027, 10, 20)
    assert legacy_rule_applies(date(2026, 9, 25), mode="off") is False
    assert legacy_rule_applies(date(2026, 9, 25), mode="auto", account_type="cash") is False


def test_blocks_the_fourth_day_trade_under_the_threshold():
    days = [date(2026, 9, 14), date(2026, 9, 15), date(2026, 9, 16)]
    blocked = check_day_trade(
        as_of=date(2026, 9, 17),
        equity=10_000,
        trade_days=days,
        opening_same_day=True,
        account_type="margin",
    )
    assert blocked.allowed is False
    allowed = check_day_trade(
        as_of=date(2026, 9, 17),
        equity=25_000,
        trade_days=days,
        opening_same_day=True,
        account_type="margin",
    )
    assert allowed.allowed is True


def test_day_trade_rolls_out_of_the_five_session_window():
    # Three day trades Mon-Wed. By the next Monday the Monday trade has left
    # a five-session window, so a new day trade is allowed.
    days = [date(2026, 9, 14), date(2026, 9, 15), date(2026, 9, 16)]
    later = check_day_trade(
        as_of=date(2026, 9, 21),
        equity=10_000,
        trade_days=days,
        opening_same_day=True,
        account_type="margin",
    )
    assert later.allowed is True
    assert later.day_trades_in_window == 2


def test_intraday_margin_blocks_a_deficit_and_the_two_thousand_floor():
    ok, _ = intraday_margin_ok(
        equity=10_000, gross_exposure=20_000, new_exposure=10_000,
        margin_ratio=0.25, min_margin_equity=2_000, account_type="margin",
    )
    assert ok is True
    blocked, reason = intraday_margin_ok(
        equity=5_000, gross_exposure=20_000, new_exposure=10_000,
        margin_ratio=0.25, min_margin_equity=2_000, account_type="margin",
    )
    assert blocked is False
    assert "deficit" in reason
    small, _ = intraday_margin_ok(
        equity=1_500, gross_exposure=0, new_exposure=100,
        margin_ratio=0.25, min_margin_equity=2_000, account_type="margin",
    )
    assert small is False
    cash, _ = intraday_margin_ok(
        equity=500, gross_exposure=0, new_exposure=100,
        margin_ratio=0.25, min_margin_equity=2_000, account_type="cash",
    )
    assert cash is True
