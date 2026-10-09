"""Re-score the three 0 DTE books at a higher volatility. Backtests only.

Writes the report after the score. Does not place an order and does not
change the sandbox forward books.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from webull_bot.chart_reads.odte_calibration import (
    HOLDOUT_END,
    HOLDOUT_START,
    LOGGED_MODEL,
    QUOTE_SPOT,
    QUOTE_STRIKE,
    QUOTE_TIME,
    TRAIN_END,
    TRAIN_START,
    VIX1D_OCT8,
    books,
    calibrate,
    model_mid,
    prepare,
    price_structures,
    scenarios,
    score_window,
    session_dates,
    to_fifteen,
    trapdoor_structures,
    vwap_structures,
)
from webull_bot.chart_reads.orb_mwf import prior_iv

MD_PATH = Path("reports/odte_calibration.md")
JSON_PATH = Path("reports/odte_calibration.json")
PUBLISHED = {
    "qqq_aggr": {
        "holdout": {"trades": 1128, "ending_equity": 96136.46474715552, "profit_factor": 1.9798922014641513},
        "train": {"trades": 2873, "ending_equity": 104070.40923132712},
        "holdout_rolling": {"p_reach_12": 1.0, "p_ruin": 0.0, "median_ending": 35316.365612310125},
    },
    "trapdoor": {
        "holdout": {"trades": 525, "ending_equity": 12264.920661955377, "profit_factor": 1.7667514198940582},
        "train": {"trades": 1167, "ending_equity": 14425.05094981601},
    },
}


def _load_bars(symbol: str) -> pd.DataFrame:
    candidates = [
        Path(f"data/cache/open_support/{symbol}_duka_5m.pkl"),
        Path(f"/workspace/data/cache/open_support/{symbol}_duka_5m.pkl"),
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        raise FileNotFoundError(f"no 5-minute cache for {symbol}")
    frame = pd.read_pickle(path)
    frame = frame.sort_index()
    return frame[~frame.index.duplicated(keep="last")]


def _load_series(name: str) -> pd.Series:
    candidates = [
        Path(f"data/cache/_{name}_1d.csv"),
        Path("/workspace/data/cache") / f"_{name}_1d.csv",
        Path("/tmp/trapdoor-forward/data/cache") / f"_{name}_1d.csv",
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        return pd.Series(dtype=float)
    frame = pd.read_csv(path, parse_dates=["Date"])
    series = frame.set_index("Date")["close"].astype(float)
    series.index = pd.to_datetime(series.index)
    return series[~series.index.duplicated(keep="last")].sort_index()


def _term_structure(vix_points: float) -> list[dict]:
    iv = vix_points / 100.0
    rows = []
    real = (None, 2.155, 2.80, 3.675)
    labels = ("0DTE", "1DTE", "2DTE", "3DTE")
    # Friday 2026-10-09 to Monday, Tuesday, Wednesday is 3, 4, and 5 calendar days.
    dtes = (0, 3, 4, 5)
    mids = ((1.13 + 1.14) / 2.0, 2.155, 2.80, 3.675)
    for label, dte, market, logged in zip(labels, dtes, mids, LOGGED_MODEL):
        priced = model_mid("call", QUOTE_SPOT, QUOTE_STRIKE, QUOTE_TIME, iv, dte)
        rows.append(
            {
                "expiry": label,
                "calendar_days": dte,
                "market": market,
                "logged_model": logged,
                "model_at_vix1d": priced,
                "unused": real,
            }
        )
    return rows


def _money(value) -> str:
    if value is None:
        return "n/a"
    return f"${float(value):,.0f}" if abs(float(value)) >= 100 else f"${float(value):,.2f}"


def _pct(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _num(value) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _row_metrics(metrics: dict) -> dict:
    return {
        "trades": int(metrics.get("trades") or 0),
        "win_rate": metrics.get("win_rate"),
        "profit_factor": metrics.get("profit_factor"),
        "sharpe": metrics.get("sharpe"),
        "max_drawdown": metrics.get("max_drawdown"),
        "ending_equity": metrics.get("ending_equity"),
    }


def _markdown(payload: dict) -> str:
    cal = payload["calibration"]
    lines = [
        "# 0DTE volatility check, 2026-10-09",
        "",
        "Backtest only. Nothing was sent to a broker. Live trading stays off. The sandbox forward books were not changed.",
        "",
        payload["summary"],
        "",
        "## What the quote implies",
        "",
        (
            f"At 11:36 ET, SPY {QUOTE_SPOT:.3f}, the 777 call was {payload['quote']['bid']:.2f} / "
            f"{payload['quote']['ask']:.2f}, mid ${cal['quote_mid']:.3f}. "
            f"The Oct 8 VIX1D close is {cal['vix1d_points']:.2f}. "
            f"The same Black-Scholes the books use prices that call at ${cal['model_at_prior']:.3f}. "
            f"The vol that matches the mid is {100 * cal['implied_0dte']:.1f}%, "
            f"which is {cal['multiplier_0dte']:.2f} times that VIX1D close, "
            f"or {cal['additive_points']:+.1f} volatility points."
        ),
        "",
        (
            f"The morning 776 call fill of ${payload['morning_fill']:.2f}, with SPY at {payload['morning_spot']:.2f} "
            f"at 10:05:30, implies {100 * cal['morning_implied']:.1f}% and "
            f"{cal['morning_multiplier']:.2f} times the same VIX1D close if that fill is taken as the price."
        ),
        "",
        (
            f"The book clock at 11:36 has {cal['book_minutes']:.0f} minutes left until 16:00. "
            f"Making the Oct 8 VIX1D close match the $1.135 mid would take "
            f"{cal['minutes_if_vol_unchanged']:.0f} minutes, about "
            f"{cal['minutes_if_vol_unchanged'] / 60:.1f} hours. That is not a session clock. "
            "The cheap 0 DTE price is the volatility, not an early expiry."
        ),
        "",
        (
            "The four model prices in the live log, $0.548, $2.51, $2.90, and $3.25, "
            f"match about 8.7% vol. The Oct 6 VIX1D close is 8.69 and prices this call at "
            f"${payload['model_oct6']:.3f}. The Oct 8 close of 10.24 prices it at "
            f"${cal['model_at_prior']:.3f}. A cache that stopped on Oct 6 would print the logged model. "
            "The re-score below still scales each day's own prior close, which is what the backtest already does."
        ),
        "",
        "Longer expiries at the same 11:36 spot, using the Oct 8 close of 10.24:",
        "",
        "| Expiry | Market | Model at 10.24 | Logged model |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in payload["term"]:
        lines.append(
            f"| {row['expiry']} | ${row['market']:.3f} | ${row['model_at_vix1d']:.3f} | ${row['logged_model']:.3f} |"
        )
    lines.extend(
        [
            "",
            "1 DTE and 2 DTE are richer in the model than in the market. 3 DTE is close. "
            "The cheap print is the 0 DTE contract. These three books trade only 0 DTE, so the scale is applied only there.",
            "",
            "## How the re-score is run",
            "",
            "Train is 2017-02-16 through 2023-12-31. Holdout is a fresh account from 2024-01-01 through 2026-10-06. "
            "The signals are the frozen ones: SPY and QQQ 15-minute 2 SD continuation, and the QQQ Trapdoor short. "
            "The fill is still the next open, the stop and the 1R target are unchanged, and the option is still flat at 15:45. "
            "x1.0 with the book spread is the published model: half-spread the greater of $0.01 and 1.5% of the mid. "
            "The other rows keep that volatility scale and charge a 1 cent or 2 cent bid-ask, which is the width on the live 777 call. "
            "A ticket that does not fit settled cash is skipped whole. QQQ Aggressive is not cut from 3 contracts to 1. "
            "The one-position lock ends with the session, the same way the original score does, because the option is flat by the close.",
            "",
            "QQQ Aggressive also replays every session that still has 12 months inside the window, from a fresh $2,500. "
            "Reach is equity of $10,000. Ruin is equity under $500.",
            "",
        ]
    )
    for book in payload["books"]:
        lines.append(f"## {book['name']}")
        lines.append("")
        lines.append(book["blurb"])
        lines.append("")
        lines.append("| Case | Window | Trades | Win | PF | Sharpe | Max DD | Ending |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for case in book["cases"]:
            for window in ("train", "holdout"):
                metrics = case[window]
                lines.append(
                    "| {case} | {window} | {trades} | {win} | {pf} | {sharpe} | {dd} | {ending} |".format(
                        case=case["label"],
                        window=window,
                        trades=metrics["trades"],
                        win=_pct(metrics["win_rate"]),
                        pf=_num(metrics["profit_factor"]),
                        sharpe=_num(metrics["sharpe"]),
                        dd=_pct(metrics["max_drawdown"]),
                        ending=_money(metrics["ending_equity"]),
                    )
                )
        if book["id"] == "qqq_aggr":
            lines.extend(
                [
                    "",
                    "| Case | Window | Starts | Median ending | P(reach $10k) | P(ruin) |",
                    "| --- | --- | ---: | ---: | ---: | ---: |",
                ]
            )
            for case in book["cases"]:
                for window in ("train", "holdout"):
                    rolling = case["rolling"][window]
                    lines.append(
                        "| {case} | {window} | {starts} | {median} | {reach} | {ruin} |".format(
                            case=case["label"],
                            window=window,
                            starts=rolling["starts"],
                            median=_money(rolling["median_ending"]),
                            reach=_pct(rolling["p_reach_12"]),
                            ruin=_pct(rolling["p_ruin"]),
                        )
                    )
        lines.append("")
    lines.append(payload["close"])
    lines.append("")
    return "\n".join(lines)


def _summary(payload: dict) -> str:
    """Filled after the numbers exist. The runner replaces this once the tables are scored."""
    return payload.get("summary") or ""


def run() -> dict:
    spy = _load_bars("SPY")
    qqq = _load_bars("QQQ")
    iv = prior_iv(_load_series("VIX1D"), _load_series("VIX"))
    cal = calibrate(VIX1D_OCT8)
    multiplier = round(float(cal["multiplier_0dte"]), 2)
    # Keep the unrounded ratio for the label, and score that exact ratio.
    multiplier = float(cal["multiplier_0dte"])
    spy15 = to_fifteen(spy)
    qqq15 = to_fifteen(qqq)
    print("building structures", flush=True)
    structures = {
        "spy_vwap": vwap_structures(spy15, "SPY"),
        "qqq_aggr": vwap_structures(qqq15, "QQQ"),
        "trapdoor": trapdoor_structures(prepare(qqq, "QQQ")),
    }
    for key, rows in structures.items():
        print(f"  {key} {len(rows)}", flush=True)
    sessions = {
        "spy_vwap": session_dates(spy15),
        "qqq_aggr": session_dates(qqq15),
        "trapdoor": rth_dates(qqq),
    }
    priced = {}
    for spec in books():
        for label, scale, width in scenarios(multiplier):
            print(f"pricing {spec['id']} {label}", flush=True)
            priced[(spec["id"], label)] = price_structures(structures[spec["id"]], iv, scale, width)
    book_rows = []
    checks = {}
    for spec in books():
        cases = []
        for label, scale, width in scenarios(multiplier):
            cands = priced[(spec["id"], label)]
            case = {"label": label, "scale": scale, "width": width, "rolling": {}}
            for window, start, end in (
                ("train", TRAIN_START, TRAIN_END),
                ("holdout", HOLDOUT_START, HOLDOUT_END),
            ):
                scored = score_window(
                    cands,
                    sessions[spec["id"]],
                    start,
                    end,
                    spec["qty"],
                    spec["cap"],
                    spec["stake"],
                    spec["rolling"],
                )
                case[window] = _row_metrics(scored["metrics"])
                if spec["rolling"]:
                    case["rolling"][window] = scored["rolling"]
            cases.append(case)
            metrics = case["holdout"]
            print(
                f"  {spec['id']} {label} holdout trades {metrics['trades']} "
                f"ending {metrics['ending_equity']:.0f} pf {metrics['profit_factor']}",
                flush=True,
            )
        baseline = cases[0]
        published = PUBLISHED.get(spec["id"])
        if published:
            checks[spec["id"]] = {
                "holdout_trades": baseline["holdout"]["trades"],
                "published_trades": published["holdout"]["trades"],
                "holdout_ending": baseline["holdout"]["ending_equity"],
                "published_ending": published["holdout"]["ending_equity"],
                "train_trades": baseline["train"]["trades"],
                "published_train_trades": published["train"]["trades"],
                "train_ending": baseline["train"]["ending_equity"],
                "published_train_ending": published["train"]["ending_equity"],
            }
        book_rows.append({**spec, "cases": cases})
    oct6 = model_mid("call", QUOTE_SPOT, QUOTE_STRIKE, QUOTE_TIME, 8.69 / 100.0, 0)
    payload = {
        "calibration": cal,
        "multiplier": multiplier,
        "quote": {"bid": 1.13, "ask": 1.14, "spot": QUOTE_SPOT, "strike": QUOTE_STRIKE},
        "morning_fill": 1.05,
        "morning_spot": 775.63,
        "model_oct6": oct6,
        "term": _term_structure(VIX1D_OCT8),
        "books": book_rows,
        "checks": checks,
        "summary": "",
        "close": (
            "The cash mirror in the sandbox still uses the unscaled model. "
            "This score does not change an order."
        ),
    }
    payload["summary"] = _lead(payload)
    return payload


def rth_dates(frame: pd.DataFrame) -> list[date]:
    from webull_bot.mtf_vwap.detect import rth

    return session_dates(rth(frame))


def _lead(payload: dict) -> str:
    cal = payload["calibration"]
    aggr = next(item for item in payload["books"] if item["id"] == "qqq_aggr")
    trap = next(item for item in payload["books"] if item["id"] == "trapdoor")
    spy = next(item for item in payload["books"] if item["id"] == "spy_vwap")

    def _case(book, needle: str):
        return next(item for item in book["cases"] if item["label"].startswith(needle))

    base = _case(aggr, "x1.0, book")

    def _by(book, scale, width_name: str):
        return next(item for item in book["cases"] if abs(item["scale"] - scale) < 1e-9 and width_name in item["label"])

    cal_scale = payload["multiplier"]
    a_base = base["holdout"]
    a_cal = _by(aggr, cal_scale, "1 cent")["holdout"]
    a_two = _by(aggr, 2.0, "1 cent")["holdout"]
    a_roll = _by(aggr, cal_scale, "1 cent")["rolling"]["holdout"]
    a_roll_base = base["rolling"]["holdout"]
    t_base = _case(trap, "x1.0, book")["holdout"]
    t_cal = _by(trap, cal_scale, "1 cent")["holdout"]
    s_base = _case(spy, "x1.0, book")["holdout"]
    s_cal = _by(spy, cal_scale, "1 cent")["holdout"]
    return (
        f"The 11:36 SPY 777 call mid is ${cal['quote_mid']:.3f}. "
        f"Black-Scholes at the Oct 8 VIX1D close of {cal['vix1d_points']:.2f} prices it at ${cal['model_at_prior']:.3f}. "
        f"Matching the mid takes {cal['multiplier_0dte']:.2f} times that close, "
        f"{100 * cal['implied_0dte']:.1f}% instead of {cal['vix1d_points']:.2f}, "
        f"or {cal['additive_points']:+.1f} volatility points. "
        f"The morning $1.05 fill implies {cal['morning_multiplier']:.2f} times the same close. "
        f"The logged model near $0.55 lines up with the Oct 6 VIX1D close of 8.69, not with 10.24, "
        f"so the live log looked closer to half the market than the prior-close formula does. "
        f"On the holdout, QQQ Aggressive at the published model ends at {_money(a_base['ending_equity'])} "
        f"({a_base['trades']} trades, profit factor {_num(a_base['profit_factor'])}). "
        f"At {cal_scale:.2f} times volatility and a 1 cent market, it ends at {_money(a_cal['ending_equity'])} "
        f"({a_cal['trades']} trades, profit factor {_num(a_cal['profit_factor'])}). "
        f"At twice volatility it ends at {_money(a_two['ending_equity'])} "
        f"({a_two['trades']} trades, profit factor {_num(a_two['profit_factor'])}). "
        f"The 12-month chance of reaching $10,000 goes from {_pct(a_roll_base['p_reach_12'])} "
        f"on the published model to {_pct(a_roll['p_reach_12'])} at the calibrated vol, "
        f"and the chance of falling under $500 goes from {_pct(a_roll_base['p_ruin'])} to {_pct(a_roll['p_ruin'])}. "
        f"QQQ Trapdoor goes from {_money(t_base['ending_equity'])} to {_money(t_cal['ending_equity'])}. "
        f"SPY VWAP, one contract from $1,000, goes from {_money(s_base['ending_equity'])} to {_money(s_cal['ending_equity'])}. "
        "A 1 cent or 2 cent spread is a small change next to the volatility. "
        "1 DTE and 2 DTE were already richer in the model than in the market, so this bump is only for the 0 DTE price."
    )


def main() -> None:
    payload = run()
    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    public = json.loads(json.dumps(payload, default=_json))
    JSON_PATH.write_text(json.dumps(public, indent=2) + "\n")
    MD_PATH.write_text(_markdown(public))
    print(f"wrote {MD_PATH}", flush=True)
    for key, check in payload["checks"].items():
        trade_gap = abs(check["holdout_trades"] - check["published_trades"])
        money_gap = abs(check["holdout_ending"] - check["published_ending"])
        train_gap = abs(check["train_trades"] - check["published_train_trades"])
        train_money = abs(check["train_ending"] - check["published_train_ending"])
        print(
            f"check {key} holdout trade gap {trade_gap} ending gap {money_gap:.2f} "
            f"train trade gap {train_gap} ending gap {train_money:.2f}",
            flush=True,
        )


def _json(value):
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            return None
        return value
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    if hasattr(value, "item"):
        return _json(value.item())
    raise TypeError(type(value))


if __name__ == "__main__":
    main()
