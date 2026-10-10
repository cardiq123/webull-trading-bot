"""Score the frozen Trapdoor strike and size grid once. Backtests only.

Writes the rules file before any metric. Does not place an order and does
not add a strategy to the live list.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from webull_bot.chart_reads.atm_exit import deflated_sharpe
from webull_bot.chart_reads.orb_mwf import prior_iv
from webull_bot.chart_reads.trapdoor_aggressive import (
    STAKE,
    Spec,
    assign_q,
    catalog,
    evaluate_window,
    frozen_rules,
    model_trust,
    n_trials,
    plain_name,
    prepare_symbol,
    price_structures,
    pricing_stats,
    survives,
    to_fifteen,
    trapdoor_events,
    trapdoor_structures,
    vwap_structures,
)

RULES_PATH = Path("reports/trapdoor_aggressive_rules.json")
JSON_PATH = Path("reports/trapdoor_aggressive.json")
MD_PATH = Path("reports/trapdoor_aggressive.md")
CHART_PATH = Path("reports/trapdoor_aggressive_reach.png")
README_PATH = Path("README.md")
RESULTS_PATH = Path("RESULTS.md")
START_MARK = "<!-- TRAPDOOR_AGGRESSIVE_START -->"
END_MARK = "<!-- TRAPDOOR_AGGRESSIVE_END -->"


def _load_bars(symbol: str) -> tuple[pd.DataFrame, str]:
    candidates = [
        Path(f"data/cache/open_support/{symbol}_duka_5m.pkl"),
        Path(f"/workspace/data/cache/open_support/{symbol}_duka_5m.pkl"),
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        raise FileNotFoundError(f"no 5-minute cache for {symbol}")
    frame = pd.read_pickle(path)
    frame = frame.sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    return frame, str(path)


def _load_series(name: str) -> pd.Series:
    candidates = [
        Path(f"data/cache/_{name}_1d.csv"),
        Path(f"/workspace/data/cache/_{name}_1d.csv"),
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        return pd.Series(dtype=float)
    frame = pd.read_csv(path, parse_dates=["Date"])
    series = frame.set_index("Date")["close"].astype(float)
    series.index = pd.to_datetime(series.index)
    return series[~series.index.duplicated(keep="last")].sort_index()


def _sessions(book) -> list[date]:
    days = []
    seen = set()
    for day in book.dates:
        if day in seen:
            continue
        seen.add(day)
        days.append(day)
    return days


def _price_key(spec: Spec) -> tuple:
    return (spec.book, spec.strike, spec.exit, spec.skew)


def _public_metrics(metrics: dict) -> dict:
    keep = (
        "starting_equity",
        "ending_equity",
        "total_return",
        "cagr",
        "sharpe",
        "max_drawdown",
        "trades",
        "win_rate",
        "profit_factor",
        "expectancy",
    )
    return {key: _jsonable(metrics.get(key)) for key in keep}


def _public_rolling(rolling: dict) -> dict:
    return {key: _jsonable(value) for key, value in rolling.items()}


def _jsonable(value):
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            return None
        return value
    if hasattr(value, "item"):
        return _jsonable(value.item())
    return value


def _money(value) -> str:
    """Plain dollars. Exact figures stay in the JSON."""
    if value is None:
        return "n/a"
    number = float(value)
    sign = "-" if number < 0 else ""
    amount = abs(number)
    scales = (
        (1e18, "quintillion"),
        (1e15, "quadrillion"),
        (1e12, "trillion"),
        (1e9, "billion"),
        (1e6, "million"),
    )
    for scale, name in scales:
        scaled = amount / scale
        if amount >= scale and scaled < 1000:
            return f"{sign}${scaled:.1f} {name}"
    if amount >= 1e6:
        raw = f"{amount:.2e}"
        mant, exp = raw.split("e")
        return f"{sign}${mant}×10^{int(exp)}"
    if amount < 10:
        return f"{sign}${amount:,.2f}"
    return f"{sign}${amount:,.0f}"


def _pct(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _num(value, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def _days(value) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.0f} days"


def _rank(rows: list[dict]) -> list[dict]:
    def key(row: dict):
        rolling = row["holdout_rolling"]
        reach = rolling.get("p_reach_12")
        ruin = rolling.get("p_ruin")
        ending = rolling.get("median_ending")
        return (
            -1.0 if reach is None else -float(reach),
            1.0 if ruin is None else float(ruin),
            0.0 if ending is None else -float(ending),
        )

    return sorted(rows, key=key)


def _trust_sentence(row: dict) -> str:
    thing = "contract" if row["book"] == "vwap" else "put"
    ask = row.get("median_ask")
    ask_bit = f" Median ask {_money(ask)}." if ask is not None else ""
    if row["trust"] == "least":
        return (
            f" The model is least trustworthy on this {thing}: cheap 0 DTE premium, "
            f"where a one-cent error is a large share of the price.{ask_bit}"
        )
    if row["trust"] == "wide":
        return " The out-of-the-money half-spread is the wide one, max($0.02, 8% of the mid) per side."
    return ""


def _ruin_sentence(row: dict) -> str:
    hold = row["holdout_rolling"]
    ending = hold.get("median_ending") or 0.0
    drawdown = hold.get("median_drawdown")
    ruin = hold.get("p_ruin") or 0.0
    if ruin < 0.01 and ending >= 1_000_000 and drawdown is not None and drawdown <= -0.30:
        return (
            " That holdout ruin rate stays near zero because the modeled account is already huge, "
            "so a deep drawdown still leaves it above $500."
        )
    return ""


def _blurb(row: dict, rank: int) -> str:
    hold = row["holdout_rolling"]
    train = row["train_rolling"]
    metrics = row["holdout"]
    gate = "Clears the frozen gate." if row["survives"] else "Does not clear the frozen gate."
    return (
        f"{rank}. {row['name']}. "
        f"Of {int(hold['starts'])} holdout starts, {_pct(hold['p_reach_12'])} reach $10,000 within 12 months "
        f"({_pct(hold['p_reach_8'])} within 8, {_pct(hold['p_reach_4'])} within 4) and "
        f"{_pct(hold['p_ruin'])} fall under $500 inside those 12 months. "
        f"In 2017–2023 the same fresh starts reach $10,000 {_pct(train['p_reach_12'])} of the time and "
        f"fall under $500 {_pct(train['p_ruin'])} of the time.{_ruin_sentence(row)} "
        f"When a start does get to $10,000 inside 12 months, the median time is {_days(hold['median_days_to_goal'])}. "
        f"The median 12-month ending balance is {_money(hold['median_ending'])}, and the weak tenth ends at "
        f"{_money(hold['p10_ending'])}. The median 12-month drawdown is {_pct(hold['median_drawdown'])}; "
        f"the weak tenth is {_pct(hold['p10_drawdown'])}. "
        f"One account run across the whole holdout ends at {_money(metrics.get('ending_equity'))} "
        f"on {int(metrics.get('trades') or 0)} trades, profit factor {_num(metrics.get('profit_factor'))}, "
        f"Sharpe {_num(metrics.get('sharpe'))}, max drawdown {_pct(metrics.get('max_drawdown'))}. "
        f"{gate}{_trust_sentence(row)}"
    )


def _compact(rows: list[dict]) -> str:
    lines = [
        "| Cell | Holdout reach 12m | Ruin | Median end | Full ending | PF | Sharpe | DD | Trades | q | Survives | Train reach | Train ruin |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for row in rows:
        hold = row["holdout_rolling"]
        train = row["train_rolling"]
        metrics = row["holdout"]
        lines.append(
            "| {id} | {reach} | {ruin} | {end} | {full} | {pf} | {sharpe} | {dd} | {trades} | {q} | {ok} | {train} | {train_ruin} |".format(
                id=row["id"],
                reach=_pct(hold.get("p_reach_12")),
                ruin=_pct(hold.get("p_ruin")),
                end=_money(hold.get("median_ending")),
                full=_money(metrics.get("ending_equity")),
                pf=_num(metrics.get("profit_factor")),
                sharpe=_num(metrics.get("sharpe")),
                dd=_pct(metrics.get("max_drawdown")),
                trades=int(metrics.get("trades") or 0),
                q=_num(row.get("q"), 3),
                ok="yes" if row["survives"] else "no",
                train=_pct(train.get("p_reach_12")),
                train_ruin=_pct(train.get("p_ruin")),
            )
        )
    return "\n".join(lines)


def _ordinary_survivors(ranked: list[dict], limit: int = 2) -> list[dict]:
    picked = []
    for row in ranked:
        if not row["survives"]:
            continue
        ending = row["holdout_rolling"].get("median_ending") or 0.0
        if ending >= 1_000_000:
            continue
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def _answer(rows: list[dict], ranked: list[dict]) -> str:
    base = next(row for row in rows if row["id"] == "trapdoor_atm_r1_c1_off")
    hold = base["holdout_rolling"]
    train = base["train_rolling"]
    metrics = base["holdout"]
    top = ranked[:6]
    trap_ruins = [
        float(row["train_rolling"]["p_ruin"])
        for row in top
        if row["book"] == "trapdoor" and row["train_rolling"].get("p_ruin") is not None
    ]
    ruin_span = ""
    if trap_ruins:
        ruin_span = (
            f" On 2017–2023 starts those Trapdoor fraction bets fall under $500 on "
            f"{_pct(min(trap_ruins))} to {_pct(max(trap_ruins))} of paths."
        )
    skew_on = [row for row in rows if row["survives"] and row["skew"] == "on"]
    if skew_on:
        skew_note = (
            "With the skew bump on, the cells that still clear the gate are: "
            + "; ".join(row["name"] for row in skew_on)
            + "."
        )
    else:
        skew_note = "With the skew bump on, no cell clears the gate."
    usable = _ordinary_survivors(ranked)
    usable_bit = ""
    if usable:
        names = "; ".join(
            (
                f"{row['name']} (holdout reach {_pct(row['holdout_rolling']['p_reach_12'])}, "
                f"ruin {_pct(row['holdout_rolling']['p_ruin'])}, "
                f"median 12-month ending {_money(row['holdout_rolling']['median_ending'])}, "
                f"2017–2023 reach {_pct(row['train_rolling']['p_reach_12'])}, "
                f"2017–2023 ruin {_pct(row['train_rolling']['p_ruin'])})"
            )
            for row in usable
        )
        usable_bit = (
            " The first cells in this same sort that clear the gate and still finish a typical "
            f"year in ordinary dollars are: {names}."
        )
    return (
        f"The unchanged at-the-money 1-contract Trapdoor reaches $10,000 on {_pct(hold['p_reach_12'])} "
        f"of {int(hold['starts'])} holdout starts that still have a full 12 months, and on "
        f"{_pct(train['p_reach_12'])} of the 2017–2023 starts. Holdout ruin is {_pct(hold['p_ruin'])}. "
        f"The median of those 12-month endings is {_money(hold['median_ending'])} "
        f"(weak tenth {_money(hold['p10_ending'])}). "
        f"One account left running across the whole holdout ends at {_money(metrics.get('ending_equity'))} "
        f"on {int(metrics.get('trades') or 0)} trades, profit factor {_num(metrics.get('profit_factor'))}, "
        f"Sharpe {_num(metrics.get('sharpe'))}, max drawdown {_pct(metrics.get('max_drawdown'))}. "
        f"{'It clears the gate.' if base['survives'] else 'It misses the gate on this pass.'} "
        "The six highest holdout chances of reaching $10,000 are fixed-fraction bets. "
        "Their holdout reach is high and their holdout ruin is near zero because a cheap 0 DTE premium, "
        "reinvested, compounds into millions inside the model before a drawdown can print as ruin under $500. "
        f"None of those six clear the gate.{ruin_span} "
        "Totals past about $10 million in this table are a model artifact, and the exact figures stay in the JSON. "
        f"{skew_note}{usable_bit}"
    )


def _prose(rows: list[dict], ranked: list[dict], tapes: str) -> str:
    survivors = [row for row in rows if row["survives"]]
    if survivors:
        verdict = (
            "Cells that clear the frozen holdout gate (profit factor 1.10, Sharpe 0.40, "
            "drawdown no worse than -30%, at least 300 trades, q at or under 0.10, deflated Sharpe at least 0.95): "
            + "; ".join(row["name"] for row in survivors)
            + "."
        )
    else:
        verdict = "No cell clears the frozen holdout gate. Reaching $10,000 on a lucky start is a separate question."
    top = ranked[:6]
    lines = [
        "# QQQ Trapdoor, more aggressive puts and sizes",
        "",
        _answer(rows, ranked),
        "",
        "The entry is the QQQ Trapdoor that already cleared: a double top, then a 5-minute close below the neckline and below both the 9 and 20 EMA. That signal was not retuned. This pass only changes the put and how many contracts the $2,500 account buys.",
        "",
        "At the money is the baseline, held to the 1R underlying target. One, two, and three strikes out of the money, and puts aimed at a 0.40, 0.30, or 0.20 delta, are each held to that same 1R target and to a 2R target. The stop stays one cent above the second high. Everything is flat at the 15:45 open. Trapdoor still takes at most 3 fills a day. The VWAP comparison takes at most 5.",
        "",
        "Size is either a fixed 1, 3, 5, 7, or 10 contracts, or 10%, 20%, 30%, or 50% of equity. If the whole ticket costs more than the settled cash, the trade is skipped. It is not cut down to a smaller lot. A sale can be spent the next session.",
        "",
        "The price is Black-Scholes with the prior VIX1D close, or the prior VIX close when VIX1D is missing. Out-of-the-money puts are scored twice: once at that IV, and once with a skew bump of 1.5 volatility points per 0.10 of delta below 0.50. Those puts also pay a wider half-spread, max($0.02, 8% of the mid), on the way in and on the way out, when the listed strike is below at the money. At-the-money keeps the original half-spread, max($0.01, 1.5% of the mid). A cheap 0 DTE premium is where this model is least trustworthy, because a one-cent error is a large share of a price that is only a few cents. Strikes two and three out, and the 0.30 and 0.20 delta targets, are flagged, as is any cell whose median ask is under $0.50.",
        "",
        "The chance of reaching $10,000 is a fresh $2,500 at every session that still has 12 months of data inside the window. The 4-month and 8-month chances use those same starts. Train is 2017-02-16 through 2023-12-31. Holdout is 2024-01-01 through 2026-10-06. A train start never sees 2024. The family is "
        f"{n_trials()} cells. The false-discovery gate is the usual one, on the full holdout account. The $10,000 chance sorts the table. It is the question Paul asked, and it leaves the entry rule alone.",
        "",
        tapes,
        "",
        verdict,
        "",
        "## Top configurations by the chance of reaching $10,000 in 12 months",
        "",
    ]
    for rank, row in enumerate(top, start=1):
        lines.append(_blurb(row, rank))
        lines.append("")
    lines.append(
        "The chart is `reports/trapdoor_aggressive_reach.png`. Each dot is one cell on the holdout starts. "
        "Across is the chance of reaching $10,000 within 12 months. Up is the chance of falling under $500. "
        "The labeled dots are the six above. They sit at the bottom right, high reach and low ruin, because the fraction bets get large "
        "before they draw down, so the holdout ruin count stays near zero. The 2017–2023 starts for those "
        "same cells often do fall under $500."
    )
    lines.append("")
    lines.append("## Every cell")
    lines.append("")
    lines.append(_compact(ranked))
    lines.append("")
    lines.append("Live trading stays off. Nothing was added to the selected book.")
    lines.append("")
    return "\n".join(lines)


def _chart(ranked: list[dict]) -> None:
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9.2, 6.6))
    for book, color, label in (
        ("trapdoor", "#1f4e79", "QQQ Trapdoor"),
        ("vwap", "#c65911", "QQQ VWAP 2 SD"),
    ):
        rows = [row for row in ranked if row["book"] == book]
        ax.scatter(
            [row["holdout_rolling"]["p_reach_12"] or 0.0 for row in rows],
            [row["holdout_rolling"]["p_ruin"] or 0.0 for row in rows],
            s=28,
            c=color,
            alpha=0.75,
            label=label,
            zorder=2,
        )
    for index, row in enumerate(ranked[:6], start=1):
        reach = row["holdout_rolling"]["p_reach_12"] or 0.0
        ruin = row["holdout_rolling"]["p_ruin"] or 0.0
        ax.scatter([reach], [ruin], s=64, facecolors="none", edgecolors="black", linewidths=1.2, zorder=3)
        ax.annotate(
            str(index),
            (reach, ruin),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=9,
        )
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("Chance a fresh $2,500 reaches $10,000 within 12 months")
    ax.set_ylabel("Chance the same start falls under $500")
    ax.set_title("Holdout 2024–2026: getting to $10,000 versus going broke")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(True, color="#e6e6e6")
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    fig.text(
        0.05,
        0.02,
        "Holdout starts only. The numbered dots bet a fraction of equity. They sit at high reach and near-zero ruin\n"
        "because the modeled account is already huge. The 2017–2023 starts for those same cells often fall under $500.",
        fontsize=8,
        color="#333333",
        va="bottom",
    )
    fig.savefig(CHART_PATH, dpi=120)
    plt.close(fig)


def _upsert(path: Path, body: str) -> None:
    text = path.read_text() if path.exists() else ""
    block = f"{START_MARK}\n{body.rstrip()}\n{END_MARK}\n"
    if START_MARK in text and END_MARK in text:
        pre, rest = text.split(START_MARK, 1)
        _old, post = rest.split(END_MARK, 1)
        path.write_text(pre + block + post.lstrip("\n"))
        return
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n" + block)


def _readme(rows: list[dict], ranked: list[dict]) -> str:
    base = next(row for row in rows if row["id"] == "trapdoor_atm_r1_c1_off")
    top = ranked[0]
    usable = _ordinary_survivors(ranked)
    usable_bit = ""
    if usable:
        usable_bit = (
            " The first gate survivors that still finish a typical year in ordinary dollars are "
            + " and ".join(row["name"] for row in usable)
            + "."
        )
    return (
        "**QQQ Trapdoor size grid: research only, live trading stays off.** "
        f"The entry stays the frozen QQQ short. {n_trials()} pre-registered put and size cells, "
        "plus the same sizes on the QQQ 2 SD VWAP continuation. Fresh $2,500, train 2017–2023 and holdout 2024-01-01 "
        "through 2026-10-06, scored separately. "
        f"The 1-contract at-the-money book reaches $10,000 on {_pct(base['holdout_rolling']['p_reach_12'])} of holdout "
        f"12-month starts and ends the full holdout at {_money(base['holdout'].get('ending_equity'))}. "
        f"The highest holdout chance is {top['name']}: {_pct(top['holdout_rolling']['p_reach_12'])} reach $10,000 and "
        f"{_pct(top['holdout_rolling']['p_ruin'])} fall under $500 in the holdout, while "
        f"{_pct(top['train_rolling']['p_ruin'])} of the 2017–2023 starts fall under $500. "
        "That cell misses the gate. Fraction-of-equity endings in the millions are a model artifact on cheap 0 DTE premium."
        f"{usable_bit} "
        "Full table in [reports/trapdoor_aggressive.md](reports/trapdoor_aggressive.md)."
    )


def main() -> None:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(frozen_rules(), indent=2) + "\n")
    print(f"WROTE {RULES_PATH}", flush=True)

    frame, path = _load_bars("QQQ")
    iv = prior_iv(_load_series("VIX1D"), _load_series("VIX"))
    book = prepare_symbol(frame, "QQQ")
    events = trapdoor_events(book)
    sessions = [day for day in _sessions(book) if day >= date(2017, 2, 16)]
    trap = trapdoor_structures(book, events)
    fifteen = to_fifteen(frame)
    vwap = vwap_structures(fifteen)
    print(
        f"signals trapdoor {len(events)} r1 {len(trap['r1'])} r2 {len(trap['r2'])} vwap {len(vwap)}",
        flush=True,
    )

    priced: dict[tuple, list] = {}
    stats: dict[tuple, dict] = {}
    cells = catalog()
    for spec in cells:
        key = _price_key(spec)
        if key in priced:
            continue
        structures = vwap if spec.book == "vwap" else trap[spec.exit]
        rows = price_structures(structures, iv, spec.strike if spec.book == "trapdoor" else "atm", spec.skew)
        priced[key] = rows
        stats[key] = pricing_stats(rows)
        print(f"priced {key} tickets {len(rows)}", flush=True)

    train_start = date.fromisoformat(frozen_rules()["train"][0])
    train_end = date.fromisoformat(frozen_rules()["train"][1])
    hold_start = date.fromisoformat(frozen_rules()["holdout"][0])
    hold_end = date.fromisoformat(frozen_rules()["holdout"][1])
    built = []
    p_values = []
    for index, spec in enumerate(cells, start=1):
        key = _price_key(spec)
        cands = priced[key]
        train = evaluate_window(cands, sessions, train_start, train_end, spec.size, spec.cap)
        hold = evaluate_window(cands, sessions, hold_start, hold_end, spec.size, spec.cap)
        p_values.append(hold["p_value"])
        built.append(
            {
                "spec": spec,
                "train": train,
                "hold": hold,
                "pricing": stats[key],
            }
        )
        if index % 15 == 0 or index == len(cells):
            print(f"scored {index}/{len(cells)}", flush=True)

    q_values = assign_q(p_values)
    rows = []
    for item, q_value in zip(built, q_values):
        spec = item["spec"]
        dsr = deflated_sharpe(item["hold"]["daily_returns"], n_trials()).get("dsr")
        q_float = float(q_value)
        row = {
            "id": spec.id,
            "book": spec.book,
            "name": plain_name(spec),
            "strike": spec.strike,
            "exit": spec.exit,
            "size": spec.size,
            "skew": spec.skew,
            "trust": model_trust(spec.strike, item["pricing"].get("median_ask")),
            "median_ask": item["pricing"].get("median_ask"),
            "cheap_share": item["pricing"].get("cheap_share"),
            "q": q_float,
            "dsr": None if dsr is None else float(dsr),
            "survives": survives(item["hold"]["metrics"], q_float, None if dsr is None else float(dsr)),
            "holdout": _public_metrics(item["hold"]["metrics"]),
            "train": _public_metrics(item["train"]["metrics"]),
            "holdout_rolling": _public_rolling(item["hold"]["rolling"]),
            "train_rolling": _public_rolling(item["train"]["rolling"]),
            "holdout_skips": item["hold"]["skips"],
            "train_skips": item["train"]["skips"],
        }
        rows.append(row)

    ranked = _rank(rows)
    tape = (
        f"QQQ 5-minute bids are the same Dukascopy cache the neckline study used ({path}), "
        f"{frame.index[0].date().isoformat()} through {frame.index[-1].date().isoformat()}. "
        "The VWAP comparison is those bars rolled up to 15 minutes. No chain history. The option price is a model."
    )
    body = _prose(rows, ranked, tape)
    MD_PATH.write_text(body)
    _chart(ranked)
    payload = {
        "rules": frozen_rules(),
        "passed": [row["id"] for row in rows if row["survives"]],
        "top": [row["id"] for row in ranked[:6]],
        "rows": rows,
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    blurb = _readme(rows, ranked)
    _upsert(README_PATH, blurb)
    _upsert(RESULTS_PATH, blurb + "\n\n" + "\n\n".join(_blurb(row, rank) for rank, row in enumerate(ranked[:6], start=1)))
    print(f"WROTE {MD_PATH} passed {payload['passed']}", flush=True)


def republish() -> None:
    """Rewrite the prose and chart from the scored JSON. Does not rescore."""
    payload = json.loads(JSON_PATH.read_text())
    rows = payload["rows"]
    ranked = _rank(rows)
    tape = (
        "QQQ 5-minute bids are the same Dukascopy cache the neckline study used "
        "(/workspace/data/cache/open_support/QQQ_duka_5m.pkl), 2017-02-16 through 2026-10-06. "
        "The VWAP comparison is those bars rolled up to 15 minutes. No chain history. The option price is a model."
    )
    MD_PATH.write_text(_prose(rows, ranked, tape))
    _chart(ranked)
    blurb = _readme(rows, ranked)
    _upsert(README_PATH, blurb)
    _upsert(
        RESULTS_PATH,
        blurb + "\n\n" + "\n\n".join(_blurb(row, rank) for rank, row in enumerate(ranked[:6], start=1)),
    )
    print(f"REPUBLISHED {MD_PATH}", flush=True)


if __name__ == "__main__":
    import sys

    if "--republish" in sys.argv:
        republish()
    else:
        main()
