"""Score the frozen Monday/Wednesday/Friday SPY opening range.

Writes the rules file first. Does not place an order and does not import
the sandbox forward test.
"""

from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.dukascopy_spy import load_study_minutes, to_five_minute
from webull_bot.chart_reads.orb_mwf import (
    FILL_PRIMARY,
    IV_PRIMARY,
    IV_SENSITIVITY,
    RISK_PRIMARY,
    RISK_SENSITIVITIES,
    SEED,
    STARTING_EQUITY,
    SessionRead,
    frozen_rules,
    opening_bounds,
    prior_iv,
    scan,
    simulate,
)
from webull_bot.costs import CostModel, buy_price, sell_price, sell_regulatory_fees
from webull_bot.data.yfinance_provider import YFinanceProvider
from webull_bot.mtf_vwap.detect import rth

START = "<!-- CHART_READS_ORB_MWF_START -->"
END_MARK = "<!-- CHART_READS_ORB_MWF_END -->"
RULES_PATH = Path("reports/orb_mwf_rules.json")
PAYLOAD_PATH = Path("reports/chart_reads_orb_mwf.json")
CHART_DIR = Path("reports/setups")
CACHE = "data/cache/orb_mwf"
DOWNLOAD_END = "2026-10-07"
CHART_DAY = date(2026, 10, 6)


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _pct(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def _hit(rate: float | None, count: int, label: str) -> str:
    if count == 0 or rate is None:
        return f"{label} n/a"
    return f"{label} {_pct(rate)} of {count}"


def _flat_text(book: dict) -> str:
    trades = int(book.get("trades") or 0)
    count = int(book.get("time_at_1530") or 0)
    rate = (count / trades) if trades else 0.0
    if count == 0 or book.get("time_avg_exit") is None:
        return f"15:30 on {_pct(rate)}"
    return (
        f"15:30 on {_pct(rate)}, "
        f"average value {_money(book['time_avg_exit'])} "
        f"({_pct(book['time_avg_ratio'])} of the entry ask)"
    )


def _plain(book: dict) -> str:
    trades = int(book["trades"])
    if trades == 0:
        return (
            f"0 trades, ending {_money(book['ending'])}. "
            f"Premium skips {book['premium_skipped']}. "
            f"Settlement skips {book['settlement_skipped']}. "
            f"PDT blocked {book['pdt_blocked']}."
        )
    pf = book["profit_factor"]
    pf_text = "n/a" if pf is None else f"{pf:.2f}"
    return (
        f"{trades} trades, win rate {_pct(book['win_rate'])}, "
        f"{_hit(book.get('pct_call_target'), int(book.get('call_trades') or 0), 'calls at +100%')}, "
        f"{_hit(book.get('pct_put_target'), int(book.get('put_trades') or 0), 'puts at +50%')}, "
        f"{_flat_text(book)}, expectancy {_money(book['expectancy'])}, "
        f"profit factor {pf_text}, Sharpe {book['sharpe']:.2f}, "
        f"max drawdown {_pct(book['max_drawdown'])}, "
        f"longest losing streak {book['losing_streak']}, "
        f"ending {_money(book['ending'])}. "
        f"Premium skips {book['premium_skipped']}. "
        f"Settlement skips {book['settlement_skipped']}. "
        f"PDT blocked {book['pdt_blocked']}."
    )


def _event_counts(counted: dict) -> dict:
    kinds: dict[str, int] = {}
    for event in counted.get("events") or []:
        name = str(event.get("kind") or "")
        kinds[name] = kinds.get(name, 0) + 1
    return kinds


def _counts(reads: list[SessionRead]) -> dict:
    buckets: dict[str, int] = {}
    events = []
    for read in reads:
        buckets[read.status] = buckets.get(read.status, 0) + 1
        if read.status == "event":
            events.append({"date": read.day.isoformat(), "kind": read.event})
    return {
        "sessions": len(reads),
        "statuses": buckets,
        "events": events,
        "first": None if not reads else reads[0].day.isoformat(),
        "last": None if not reads else reads[-1].day.isoformat(),
    }


def _split_reads(reads: list[SessionRead]) -> tuple[list[SessionRead], list[SessionRead]]:
    """First half and second half of the break days. Each half is replayed from $1,000."""
    breaks = [read.day for read in reads if read.status == "break"]
    if len(breaks) < 2:
        return [], []
    mid = breaks[len(breaks) // 2]
    first = [read for read in reads if read.day < mid]
    second = [read for read in reads if read.day >= mid]
    return first, second


def _after_cost_breakeven(book: dict) -> float | None:
    win = float(book.get("avg_win") or 0.0)
    loss = abs(float(book.get("avg_loss") or 0.0))
    if int(book.get("trades") or 0) == 0 or win + loss <= 0:
        return None
    return loss / (win + loss)


def _buy_hold(frame: pd.DataFrame) -> dict:
    bars = rth(frame)
    if bars.empty:
        return {"shares": 0, "ending": STARTING_EQUITY}
    first = float(bars.iloc[0]["open"])
    last = float(bars.iloc[-1]["close"])
    costs = CostModel()
    paid = buy_price(first, costs)
    shares = int(STARTING_EQUITY // paid)
    if shares < 1:
        return {"shares": 0, "ending": STARTING_EQUITY, "start": str(bars.index[0].date()), "end": str(bars.index[-1].date())}
    leftover = STARTING_EQUITY - paid * shares
    sold = sell_price(last, costs)
    fees = sell_regulatory_fees(sold, shares, costs)
    ending = leftover + sold * shares - fees
    return {
        "shares": shares,
        "ending": ending,
        "start": str(bars.index[0].date()),
        "end": str(bars.index[-1].date()),
        "first_open": first,
        "last_close": last,
    }


def _compare_1m(five: pd.DataFrame, one: pd.DataFrame) -> list[dict]:
    rows = []
    if one is None or one.empty:
        return rows
    left_days = set(rth(five).index.date)
    right_days = set(rth(one).index.date)
    for day in sorted(left_days & right_days):
        left = opening_bounds(rth(five).loc[rth(five).index.date == day], "5m")
        right = opening_bounds(rth(one).loc[rth(one).index.date == day], "1m")
        rows.append(
            {
                "date": day.isoformat(),
                "five_high": None if left is None else left[0],
                "five_low": None if left is None else left[1],
                "one_high": None if right is None else right[0],
                "one_low": None if right is None else right[1],
                "match": left is not None
                and right is not None
                and abs(left[0] - right[0]) < 0.02
                and abs(left[1] - right[1]) < 0.02,
            }
        )
    return rows


def _chart(frame: pd.DataFrame, day: date, read: SessionRead | None, clock: str, path: Path) -> dict:
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    bars = rth(frame)
    day_bars = bars.loc[bars.index.date == day]
    fact: dict = {"date": day.isoformat(), "clock": clock, "path": str(path)}
    if day_bars.empty or read is None or read.or_high is None:
        fact["note"] = "no first candle"
        return fact
    after = day_bars.loc[day_bars.index.time >= time(9, 35)]
    fact.update(
        {
            "or_high": read.or_high,
            "or_low": read.or_low,
            "status": read.status,
            "event": read.event,
            "close": float(day_bars.iloc[-1]["close"]),
            "high_after": float(after["high"].max()) if len(after) else None,
            "low_after": float(after["low"].min()) if len(after) else None,
            "complete": bool(day_bars.index[-1].time() >= time(15, 55)),
        }
    )
    fig, ax = plt.subplots(figsize=(12.2, 6.2))
    ax.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    x = np.arange(len(day_bars))
    for i, row in enumerate(day_bars.itertuples(index=False)):
        opened, high, low, closed = float(row.open), float(row.high), float(row.low), float(row.close)
        first = day_bars.index[i].time() < time(9, 35)
        color = "#d7b56d" if first else ("#7dffa1" if closed >= opened else "#ff8b8b")
        ax.plot([i, i], [low, high], color=color, lw=0.8)
        ax.plot([i, i], [min(opened, closed), max(opened, closed)], color=color, lw=2.4)
    ax.axhline(read.or_high, color="#4ea3ff", lw=1.1, label=f"09:30-09:35 high {read.or_high:.2f}")
    ax.axhline(read.or_low, color="#f0c14a", lw=1.1, label=f"09:30-09:35 low {read.or_low:.2f}")
    if read.orb is not None and read.orb.break_time in day_bars.index:
        loc = int(day_bars.index.get_loc(read.orb.break_time))
        label = "break, traded" if read.status == "break" else f"break not traded ({read.status})"
        ax.scatter([loc], [read.orb.level], color="#ffffff", s=36, zorder=3, label=label)
    step = 6 if clock == "5m" else 15
    ticks = list(range(0, len(day_bars), step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([day_bars.index[i].strftime("%H:%M") for i in ticks])
    ax.set_title(
        f"SPY {clock} {day.isoformat()}. Range is the 09:30-09:35 candle only. Example only.",
        color="#f2f2f2",
    )
    ax.tick_params(colors="#cccccc")
    ax.legend(facecolor="#222222", edgecolor="#333333", labelcolor="#f2f2f2", fontsize=8)
    for spine in ax.spines.values():
        spine.set_color("#333333")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return fact


def _book(frame, reads, iv, **kwargs) -> dict:
    book = simulate(frame, reads, iv, **kwargs)
    book.pop("rows", None)
    return book


def _probe_yahoo_limit() -> str:
    import yfinance as yf

    raw = yf.download(
        "SPY",
        start="2026-01-02",
        end="2026-01-10",
        interval="5m",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    errors = getattr(getattr(yf, "shared", None), "_ERRORS", None)
    if raw is None or raw.empty:
        detail = ""
        if errors:
            detail = " " + " ".join(str(item) for item in errors.values())
        return "Yahoo returned no 5-minute SPY bars for January 2026." + detail
    return f"Yahoo returned {len(raw)} January 2026 5-minute bars, which was not expected."


def render(payload: dict) -> str:
    default = payload["default"]
    lines = [
        START,
        "## Monday, Wednesday, and Friday opening range",
        "",
        "Backtests only. This rule replaces the earlier first-candle test as the pre-registered default. "
        "It was frozen before the score. Nothing was sent to a broker. The sandbox forward test was not changed, "
        "and live trading stays off. The earlier first-candle numbers are a different rule and stay as scored.",
        "",
        "The range is only the 09:30-09:35 ET candle. A long break of that high buys the at-the-money 0 DTE call. "
        "A short break of that low buys the at-the-money 0 DTE put. The break is the first later bar that "
        "trades through the level. A print equal to the level is not a break. One trade a day. "
        "The default fill prices the underlying at the level plus stock slippage, then buys the option at the ask. "
        "A bar that opens through the level fills at that open. The next bar's open is a sensitivity.",
        "",
        "The book trades Monday, Wednesday, and Friday only, and it skips CPI, the Employment Situation, and FOMC "
        "decision days. The dates are the real release day or the statement day. "
        "Friday SPY expirations were already listed before 2016. Wednesday expirations start August 31, 2016. "
        "Monday expirations start February 26, 2018. Tuesday and Thursday expirations start in November 2022 and "
        "are not traded. There is no stop. A call is a win at +100% of the entry ask or whatever the 15:30 bid is worth. "
        "A put is a win at +50% of the entry ask or whatever the 15:30 bid is worth. That bid can be near zero. "
        "Risk is the full premium, sized at $100 on a $1,000 cash account. One contract that costs more than $100 is skipped. "
        "$200 and $500 are sensitivities. No adds and no rolls.",
        "",
        "There is no historical option chain. Prices are Black-Scholes with minutes left until 16:00 ET. "
        "Implied volatility is the prior session's VIX1D close when that print exists, otherwise the prior VIX close. "
        "The half-spread is the greater of one cent and 1.5% of the mid. "
        "The model is the main source of uncertainty. A 1.3x volatility multiple is a sensitivity, not a new rule. "
        "An earlier score of this same study used a -50% stop. That stop is not this rule, and those dollars are not reused.",
        "",
        payload["sample_text"],
        "",
        f"Cash account, $100 risk, fill at the level: {_plain(default)}",
        "",
    ]
    be = _after_cost_breakeven(default)
    if be is not None:
        lines.append(
            "Before costs, a call that doubles against a worthless miss needs a 50% win rate, "
            "and a put that gains 50% against a worthless miss needs a 66.7% win rate. "
            "A 15:30 exit still has whatever bid the model gives it, so it is not automatically a total loss. "
            f"After the spread and the fees, the realized wins and losses in this sample need {_pct(be)}. "
            f"The realized win rate is {_pct(default['win_rate'])}."
        )
        lines.append("")
    if default["trades"] == 0 or default["expectancy"] <= 0 or default["ending"] <= default["starting"]:
        lines.append("The win rate does not clear that rate. The default book is not profitable on this sample.")
    else:
        lines.append(
            "The default book finished above the start. The rule was frozen before this score and was not changed to keep the row. "
            "It was not promoted."
        )
    lines.extend(
        [
            "",
            payload["flat_note"],
            "",
            f"The same signals at $200 risk: {_plain(payload['risk_200'])}",
            "",
            payload["risk_200_note"],
            "",
            f"The same signals at $500 risk: {_plain(payload['risk_500'])}",
            "",
            f"Next-bar open, $100, cash: {_plain(payload['next_open'])}",
            "",
            f"Volatility at 1.3 times the prior close, $100, cash: {_plain(payload['iv_130'])} "
            "That row was not promoted.",
            "",
            payload.get("clock_5m_text", ""),
            "",
            "A $1,000 account is under the $2,000 minimum to use margin, so the default is cash and the "
            "pattern-day-trader rule does not apply. Sale proceeds settle the next session. "
            f"The same signals on a hypothetical margin account under $25,000: {_plain(payload['margin'])} "
            "Three Monday/Wednesday/Friday trades fit in five business days. A fourth appears only when a "
            "Tuesday or Thursday holiday pulls another one of those weekdays into the window. "
            + payload["pdt_note"],
            "",
            f"Random call-or-put at the same break, seed 17, same exits: {_plain(payload['random'])}",
            "",
            f"First half of the break days, replayed from a fresh $1,000: {_plain(payload['first_half'])}",
            "",
            f"Second half of the break days, also from a fresh $1,000 and not from the equity left after the first half: {_plain(payload['holdout'])} "
            "That half was not used to change the rule. A second-half row that finishes above $1,000 was not promoted.",
            "",
            payload["buy_hold_text"],
            "",
            payload["minute_text"],
            "",
            payload["chart_text"],
            "",
            "Not added to `config/optional_strategies.json`. The default book is still dual momentum.",
            "",
            "```",
            "python3 -m webull_bot.chart_reads.research_orb_mwf",
            "```",
            END_MARK,
        ]
    )
    return "\n".join(lines) + "\n"


def _write_results(block: str) -> None:
    path = Path("RESULTS.md")
    text = path.read_text() if path.exists() else ""
    if START in text and END_MARK in text:
        before = text.split(START)[0]
        after = text.split(END_MARK)[1]
        path.write_text(before + block + after.lstrip("\n"))
        return
    path.write_text(text.rstrip() + "\n\n" + block)


def _chart_days(reads: list[SessionRead]) -> list[date]:
    wanted = [CHART_DAY, date(2026, 10, 5), date(2026, 10, 2), date(2026, 9, 30), date(2026, 9, 25)]
    present = {read.day for read in reads}
    return [day for day in wanted if day in present]


OVERLAP_GATE = 0.05


def _overlap_gate(minutes: pd.DataFrame, yahoo: pd.DataFrame) -> dict:
    """Median absolute gap between Dukascopy and Yahoo opening bounds. Under $0.05 passes."""
    rows = []
    if yahoo is None or yahoo.empty or minutes.empty:
        return {"sessions": 0, "median": None, "passed": False, "rows": rows}
    yahoo_days = rth(yahoo)
    minute_days = rth(minutes)
    shared = sorted(set(yahoo_days.index.date) & set(minute_days.index.date))
    diffs = []
    for day in shared:
        left = opening_bounds(yahoo_days.loc[yahoo_days.index.date == day], "5m")
        right = opening_bounds(minute_days.loc[minute_days.index.date == day], "1m")
        if left is None or right is None:
            continue
        high_gap = abs(left[0] - right[0])
        low_gap = abs(left[1] - right[1])
        diffs.extend((high_gap, low_gap))
        rows.append(
            {
                "date": day.isoformat(),
                "yahoo_high": left[0],
                "yahoo_low": left[1],
                "bid_high": right[0],
                "bid_low": right[1],
                "high_gap": high_gap,
                "low_gap": low_gap,
            }
        )
    median = None if not diffs else float(np.median(diffs))
    return {
        "sessions": len(rows),
        "median": median,
        "passed": median is not None and median < OVERLAP_GATE and len(rows) >= 5,
        "rows": rows,
    }


def _flat_note(book: dict) -> str:
    trades = int(book["trades"])
    at_close = int(book.get("time_at_1530") or 0)
    early = int(book.get("time_count") or 0) - at_close
    if trades == 0:
        return "There were no default trades to mark at 15:30."
    if at_close == 0 or book.get("time_avg_exit") is None:
        note = "None of the default trades reached 15:30."
    else:
        note = (
            f"{at_close} of {trades} default trades reached 15:30. "
            f"Their average bid was {_money(book['time_avg_exit'])}, "
            f"{_pct(book['time_avg_ratio'])} of the entry ask."
        )
    if early:
        note += f" {early} other time exits were the last bar of a session that ended before 15:30."
    return note


def _risk_200_note(book: dict) -> str:
    if int(book["trades"]) and float(book["sharpe"]) > 0 and float(book["ending"]) < float(book["starting"]):
        return (
            f"The $200 book prints a Sharpe of {book['sharpe']:.2f} while ending at {_money(book['ending'])}, "
            "below the start. That Sharpe is not a profit."
        )
    return "The $200 book is a sensitivity. It does not replace the $100 cash rule."


def _run_books(frame: pd.DataFrame, reads: list[SessionRead], iv: dict, clock: str) -> dict:
    common = dict(clock=clock)
    default = _book(frame, reads, iv, risk=RISK_PRIMARY, account="cash", fill=FILL_PRIMARY, iv_scale=IV_PRIMARY, **common)
    books = {
        "default": default,
        "risk_200": _book(frame, reads, iv, risk=RISK_SENSITIVITIES[0], account="cash", **common),
        "risk_500": _book(frame, reads, iv, risk=RISK_SENSITIVITIES[1], account="cash", **common),
        "next_open": _book(frame, reads, iv, risk=RISK_PRIMARY, account="cash", fill="next_open", **common),
        "iv_130": _book(frame, reads, iv, risk=RISK_PRIMARY, account="cash", iv_scale=IV_SENSITIVITY, **common),
        "margin": _book(frame, reads, iv, risk=RISK_PRIMARY, account="margin", **common),
        "random": _book(frame, reads, iv, risk=RISK_PRIMARY, account="cash", seed=SEED, **common),
    }
    first_reads, hold_reads = _split_reads(reads)
    books["first_half"] = _book(frame, first_reads, iv, risk=RISK_PRIMARY, account="cash", **common) if first_reads else default
    books["holdout"] = _book(frame, hold_reads, iv, risk=RISK_PRIMARY, account="cash", **common) if hold_reads else default
    return books


def main() -> None:
    rules = frozen_rules()
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(rules, indent=2) + "\n")
    if rules["risk"] != RISK_PRIMARY or rules["fill"].startswith("Default") is False or rules["dte"] != 0:
        raise SystemExit("rules file does not match the module")
    if "no stop" not in rules["exit"].lower():
        raise SystemExit("rules file does not state that there is no stop")
    print("RULES FROZEN", RULES_PATH, flush=True)
    probe = _probe_yahoo_limit()
    print("PROBE", probe, flush=True)
    minutes, coverage = load_study_minutes()
    if minutes is None:
        missing = len(coverage.get("missing") or [])
        poison = coverage.get("poison") or []
        raise SystemExit(f"dukascopy file is not ready missing={missing} poison={poison[:8]}")
    print(
        f"DUKASCOPY sessions {coverage['sessions']} empty {len(coverage['empty'])} rows {coverage['rows']}",
        flush=True,
    )
    provider = YFinanceProvider(CACHE)
    yahoo = provider.history(["SPY"], "2026-08-13", DOWNLOAD_END, interval="5m").get("SPY")
    daily = provider.history(["^VIX", "^VIX1D"], "2017-01-01", DOWNLOAD_END, interval="1d")
    vix = None if daily is None else daily.get("^VIX")
    vix1d = None if daily is None else daily.get("^VIX1D")
    if vix is None or vix.empty:
        raise SystemExit("no VIX")
    iv = prior_iv(
        pd.Series(dtype=float) if vix1d is None else vix1d["close"],
        vix["close"],
    )
    gate = _overlap_gate(minutes, yahoo if yahoo is not None else pd.DataFrame())
    print("GATE", gate["sessions"], gate["median"], gate["passed"], flush=True)
    use_minutes = bool(gate["passed"])
    if use_minutes:
        frame = minutes
        clock = "1m"
        five = to_five_minute(minutes)
    else:
        if yahoo is None or yahoo.empty:
            raise SystemExit("Dukascopy failed the overlap gate and Yahoo returned no 5-minute bars")
        frame = yahoo
        clock = "5m"
        five = None
    reads = scan(frame, clock)
    uncovered = [read.day.isoformat() for read in reads if read.status == "calendar_uncovered"]
    if uncovered:
        raise SystemExit("event calendar does not cover " + ", ".join(uncovered[:12]))
    print(f"SCAN {clock} sessions {len(reads)}", flush=True)
    books = _run_books(frame, reads, iv, clock)
    counted = _counts(reads)
    held = _buy_hold(frame)
    charts = []
    chart_frame = five if five is not None else frame
    chart_clock = "5m" if five is not None else clock
    chart_reads = scan(chart_frame, chart_clock)
    by_day = {read.day: read for read in chart_reads}
    for day in _chart_days(chart_reads):
        charts.append(_chart(chart_frame, day, by_day.get(day), chart_clock, CHART_DIR / f"orb_mwf_spy_{day.isoformat()}.png"))
    if use_minutes and CHART_DAY in set(rth(minutes).index.date):
        one_read = next((read for read in reads if read.day == CHART_DAY), None)
        charts.append(_chart(minutes, CHART_DAY, one_read, "1m", CHART_DIR / f"orb_mwf_spy_{CHART_DAY.isoformat()}_1m.png"))
    median_text = "n/a" if gate["median"] is None else f"${gate['median']:.4f}"
    empty_note = f" {len(coverage['empty'])} study days had no published regular-session bars."
    source_lead = (
        "The sample is Dukascopy's public SPYUSUSD bid 1-minute candles, no account, from "
        f"{counted['first']} through {counted['last']}, {counted['sessions']} sessions with a bar. "
        "Prices are bids, about a penny under the consolidated mid, and they are unadjusted. "
        "SPY did not split in this window. Dukascopy volume is unused. "
        "Tuesday and Thursday were not downloaded, except 2026-10-06 for the chart. "
        f"Yahoo's 5-minute opening high and low on {gate['sessions']} overlapping sessions "
        f"differed by a median of {median_text}. The pre-registered gate is ${OVERLAP_GATE:.2f}, and this file passed, "
        "so the default break is the first 1-minute bar through the 09:30-09:35 range. "
        f"{probe} No Alpaca, Polygon, or other intraday key is in this environment, and a paid archive was not bought. "
        "A 60-minute bar does not contain the 09:30-09:35 high and low, so it was not used. "
        "The shared holiday list treats Juneteenth as closed in every year, so 2019-06-19 and 2020-06-19 "
        "are missing even though the NYSE was open. 2019-06-19 was also an FOMC statement day. "
        f"Session marks: {json.dumps(counted['statuses'])}. "
        f"Skipped releases inside the file: {json.dumps(_event_counts(counted))}. "
        f"The dates are the 2017-2026 calendar.{empty_note}"
    )
    if not use_minutes:
        source_lead = (
            "Dukascopy's bid file did not pass the overlap gate against Yahoo, so it is not the verdict. "
            f"The median absolute opening-range gap was {median_text} across {gate['sessions']} sessions, "
            f"against a gate of ${OVERLAP_GATE:.2f}. "
            f"The scored file is Yahoo 5-minute bars from {counted['first']} through {counted['last']}, "
            f"{counted['sessions']} sessions. {probe} "
            "A 60-minute bar was not used. "
            f"Session marks: {json.dumps(counted['statuses'])}. "
            f"Skipped releases inside the file: {json.dumps(_event_counts(counted))}."
        )
    sample_text = source_lead
    share_word = "share" if held["shares"] == 1 else "shares"
    buy_hold_text = (
        f"SPY buy and hold, {held['shares']} {share_word} from the first open to the last close of the scored file, "
        f"ended at {_money(held['ending'])}."
    )
    minute_text = (
        f"Overlap check: {gate['sessions']} sessions, median absolute difference {median_text} "
        f"on the 09:30-09:35 high and the low. Gate ${OVERLAP_GATE:.2f}. "
        + ("Passed." if gate["passed"] else "Not passed.")
    )
    if use_minutes and five is not None:
        print("SCORE 5m sensitivity", flush=True)
        five_reads = scan(five, "5m")
        five_book = _book(five, five_reads, iv, risk=RISK_PRIMARY, account="cash", clock="5m")
        clock_5m_text = (
            f"The same ticks aggregated to 5-minute bars, cash, $100: {_plain(five_book)} "
            "That aggregation is a sensitivity, not the verdict."
        )
        books["clock_5m"] = five_book
    else:
        clock_5m_text = "There is no separate 5-minute sensitivity. The scored clock is already 5 minutes."
    blocked = int(books["margin"]["pdt_blocked"])
    if blocked:
        pdt_note = (
            f"This file blocked {blocked} margin trades. The cash book took those trades. Cash is the verdict."
        )
    else:
        pdt_note = "This file blocked no margin trades."
    chart_bits = []
    for fact in charts:
        if "or_high" not in fact:
            continue
        trade = "no trade" if fact["status"] != "break" else "break traded"
        kind = f", {fact['event']}" if fact.get("event") else ""
        after = ""
        if fact.get("low_after") is not None and fact.get("high_after") is not None:
            after = f", after that candle {fact['low_after']:.2f}-{fact['high_after']:.2f}, close {fact['close']:.2f}"
        chart_bits.append(
            f"{fact['date']} {fact['clock']} high {fact['or_high']:.2f} low {fact['or_low']:.2f}, "
            f"{trade}{kind}{after}"
        )
    chart_text = "Charts, examples only: " + "; ".join(chart_bits) + "."
    payload = {
        "rules": rules,
        "counts": counted,
        "sample_text": sample_text,
        "buy_hold_text": buy_hold_text,
        "minute_text": minute_text,
        "chart_text": chart_text,
        "flat_note": _flat_note(books["default"]),
        "risk_200_note": _risk_200_note(books["risk_200"]),
        "clock_5m_text": clock_5m_text,
        "pdt_note": pdt_note,
        "clock": clock,
        "coverage": {key: value for key, value in coverage.items() if key != "rows" or True},
        "gate": {key: value for key, value in gate.items() if key != "rows"},
        "gate_rows": gate["rows"],
        "buy_hold": held,
        "charts": charts,
        "probe": probe,
        **books,
    }
    block = render(payload)
    _write_results(block)
    stored = dict(payload)
    stored["coverage"] = {
        "study_days": coverage["study_days"],
        "sessions": coverage["sessions"],
        "empty": coverage["empty"],
        "missing": len(coverage["missing"]),
        "poison": coverage["poison"],
        "first": coverage.get("first"),
        "last": coverage.get("last"),
        "rows": coverage.get("rows"),
    }
    PAYLOAD_PATH.write_text(json.dumps(stored, indent=2, default=str) + "\n")
    print(block)
    print("WROTE", PAYLOAD_PATH, flush=True)


if __name__ == "__main__":
    main()
