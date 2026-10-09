"""Sweet-spot rule for QQQ Aggressive Compound. No market data and no orders."""

from webull_bot.chart_reads.research_odte_compound import (
    compound_contracts,
    size_slippage,
    slipped_fill,
    _resolve,
)
from webull_bot.chart_reads.research_odte_sweet import (
    BASE_IV,
    CAPS,
    DD_FALLBACK,
    DECISION_IV,
    FRACTIONS,
    INSIDE_SIZE,
    LEVELS,
    PARTICIPATION,
    REALISTIC_CAP,
    RESEARCH_CAP,
    SWEET_RULE,
    choose_sweet_spot,
)
from webull_bot.options.fees import option_leg_fees


def _row(fraction, window, *, gate=False, dd=-0.20, median=1000.0, cap=REALISTIC_CAP, iv=DECISION_IV, mode="compound"):
    return {
        "mode": mode,
        "iv": iv,
        "cap": cap,
        "fraction": fraction,
        "window": window,
        "gate_pass": gate,
        "max_drawdown": dd,
        "median_ending": median,
    }


def _both(fraction, **kwargs):
    return [_row(fraction, "train", **kwargs), _row(fraction, "holdout", **kwargs)]


def test_the_liquidity_cap_is_thirty_contracts_from_the_stated_assumption():
    assert INSIDE_SIZE == 100
    assert LEVELS == 3
    assert PARTICIPATION == 0.10
    assert RESEARCH_CAP == 50
    assert REALISTIC_CAP == min(50, int(0.10 * 100 * 3))
    assert REALISTIC_CAP == 30
    assert CAPS == (10, 25, 30)
    assert FRACTIONS == (0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12)
    assert DD_FALLBACK == -0.40
    assert "floor(f * equity / (ask * 100))" in SWEET_RULE
    assert "not a measured QQQ quote tape" in SWEET_RULE
    assert "Realistic cap = min(50, floor(0.10 * 100 * 3)) = 30" in SWEET_RULE
    assert "largest fraction" in SWEET_RULE
    assert "-40%" in SWEET_RULE
    assert "1.20 times" in SWEET_RULE
    assert compound_contracts(200_000, 0.40, 0.10, REALISTIC_CAP) == (30, "cap")
    assert compound_contracts(200_000, 0.40, 0.10) == (50, "cap")


def test_size_slippage_starts_after_ten_contracts_and_a_twenty_lot_is_worse():
    assert size_slippage(1) == 0.0
    assert size_slippage(10) == 0.0
    assert size_slippage(15) == 0.005
    assert size_slippage(20) == 0.01
    assert size_slippage(30) == 0.02
    ask = 2.0
    bid = 3.0
    plain_debit = ask * 100 + option_leg_fees(1, ask, sell=False)
    plain_credit = bid * 100 - option_leg_fees(1, bid, sell=True)
    debit_one, credit_one = slipped_fill(ask, 1, plain_debit, plain_credit)
    assert debit_one == plain_debit
    assert credit_one == plain_credit
    debit_twenty, credit_twenty = slipped_fill(ask, 20, plain_debit, plain_credit)
    assert debit_twenty > plain_debit
    assert credit_twenty < plain_credit
    assert abs((debit_twenty - plain_debit) - 1.0) < 1e-9
    assert 0.99 < (plain_credit - credit_twenty) < 1.01
    assert credit_twenty > 250.0


def test_a_slipped_ticket_is_skipped_whole_instead_of_cut_down():
    ask = 2.0
    assert compound_contracts(40_000, ask, 0.10, REALISTIC_CAP) == (20, "size")
    plain = ask * 100 + option_leg_fees(1, ask, sell=False)
    slipped, _credit = slipped_fill(ask, 20, plain, 0.0)
    assert slipped > plain
    short = 20 * plain + 0.01
    qty, tag, _capped, _debit, _credit = _resolve("compound", 0.10, 40_000, ask, plain, 0.0, short, 30, True)
    assert (qty, tag) == (0, "cash")
    qty, tag, _capped, debit, _credit = _resolve(
        "compound", 0.10, 40_000, ask, plain, 0.0, 20 * slipped + 1.0, 30, True
    )
    assert qty == 20 and tag == "size"
    assert debit == slipped


def test_the_sweet_spot_is_the_largest_fraction_that_clears_both_windows():
    rows = []
    rows.extend(_both(0.04, gate=True, median=5_000))
    rows.extend(_both(0.08, gate=True, median=4_000))
    rows.extend(
        [
            _row(0.12, "train", gate=False, dd=-0.45),
            _row(0.12, "holdout", gate=True, dd=-0.20, median=20_000),
        ]
    )
    rows.extend(_both(0.12, gate=True, cap=10, median=30_000))
    rows.extend(_both(0.12, gate=True, iv=BASE_IV, median=30_000))
    choice = choose_sweet_spot(rows)
    assert choice["selector"] == "largest_both_gate"
    assert choice["fraction"] == 0.08


def test_the_fallback_is_the_best_holdout_median_inside_a_forty_percent_drawdown():
    rows = []
    rows.extend(_both(0.04, gate=False, dd=-0.35, median=8_000))
    rows[0]["median_ending"] = 4_000
    rows.extend(_both(0.06, gate=False, dd=-0.39, median=9_000))
    rows.extend(_both(0.08, gate=False, dd=-0.20, median=20_000))
    rows[-2]["max_drawdown"] = -0.50
    choice = choose_sweet_spot(rows)
    assert choice["selector"] == "best_median_dd40"
    assert choice["fraction"] == 0.06

    tied = []
    tied.extend(_both(0.04, gate=False, dd=-0.30, median=9_000))
    tied[0]["median_ending"] = 5_000
    tied.extend(_both(0.06, gate=False, dd=-0.30, median=9_000))
    tied[-2]["median_ending"] = 7_000
    tied_choice = choose_sweet_spot(tied)
    assert tied_choice["fraction"] == 0.06

    exact = _both(0.05, gate=False, dd=-0.40, median=1_000)
    assert choose_sweet_spot(exact)["fraction"] == 0.05

    spent = _both(0.05, gate=False, dd=-0.41, median=50_000)
    none = choose_sweet_spot(spent)
    assert none["selector"] == "none"
    assert none["fraction"] is None
