"""Gate label and ranking for the $2,500 lot study. No market data and no orders."""

from webull_bot.chart_reads.research_odte_stake2500 import (
    CHECK_ENDING,
    CHECK_TRADES,
    gate_label,
    published_reference,
    rank_cells,
    summary_paragraphs,
)


def _metrics(**overrides) -> dict:
    row = {
        "trades": 300,
        "sharpe": 0.40,
        "max_drawdown": -0.30,
        "profit_factor": 1.10,
        "win_rate": 0.5,
    }
    row.update(overrides)
    return row


def _cell(book, expiry, qty, train_end, hold_end, hold_gate=False, train_ruin=0.0, hold_ruin=0.0, hold_trades=400):
    def side(ending, gate, ruin, trades):
        return {
            "ending_equity": ending,
            "trades": trades,
            "win_rate": 0.5,
            "profit_factor": 1.2,
            "sharpe": 0.5,
            "max_drawdown": -0.2,
            "median_ending": ending,
            "p_reach_12": 0.5,
            "p_ruin": ruin,
            "gate": "yes" if gate else "no (drawdown -40.0%)",
            "gate_pass": gate,
        }

    return {
        "book": book,
        "book_id": "qqq_aggr",
        "expiry": expiry,
        "qty": qty,
        "iv": "prior close, 1 cent",
        "train": side(train_end, True, train_ruin, 500),
        "holdout": side(hold_end, hold_gate, hold_ruin, hold_trades),
    }


def test_the_usual_gate_needs_three_hundred_trades_and_a_shallow_drawdown():
    assert gate_label(_metrics()) == "yes"
    label = gate_label(_metrics(max_drawdown=-0.31, trades=10, profit_factor=1.0, sharpe=0.1))
    assert label.startswith("no")
    assert "trades" in label
    assert "PF" in label
    assert "Sharpe" in label
    assert "drawdown" in label


def test_published_reference_keeps_the_aggressive_three_lot_holdout():
    row = next(
        item
        for item in published_reference()
        if item["book_id"] == "qqq_aggr" and item["expiry"] == "0 DTE" and item["qty"] == 3 and item["window"] == "holdout"
    )
    assert row["trades"] == CHECK_TRADES
    assert abs(float(row["ending_equity"]) - CHECK_ENDING) < 0.01
    expiries = {(item["book_id"], item["expiry"], item["qty"]) for item in published_reference()}
    assert ("qqq_aggr", "0 DTE", 1) not in expiries
    assert ("spy_vwap", "1 DTE", 3) not in expiries
    assert ("qqq_aggr", "1 DTE", 1) in expiries
    assert ("trapdoor", "1 DTE", 3) in expiries


def test_a_spent_train_ranks_behind_a_book_that_survives_both_windows():
    spent = _cell("QQQ Aggressive", "0 DTE", 3, train_end=0.97, hold_end=40755.0, hold_gate=False, train_ruin=0.36)
    alive = _cell("QQQ Aggressive", "1 DTE", 1, train_end=19797.0, hold_end=18069.0, hold_gate=True)
    ranked = rank_cells([spent, alive])
    assert ranked[0]["qty"] == 1
    assert ranked[0]["expiry"] == "1 DTE"
    text = summary_paragraphs([spent, alive], [], matched=True)
    assert text.index("1. QQQ Aggressive, 1 contract, 1 DTE") < text.index("3 contracts, 0 DTE: holdout")
    assert "1128 trades" in text
    assert "clear the usual gate on both windows" in text
