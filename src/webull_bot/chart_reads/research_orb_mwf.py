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
        f"+100% on {_pct(book['pct_target'])}, -50% on {_pct(book['pct_stop'])}, "
        f"15:30 on {_pct(book['pct_time'])}, expectancy {_money(book['expectancy'])}, "
        f"profit factor {pf_text}, Sharpe {book['sharpe']:.2f}, "
        f"max drawdown {_pct(book['max_drawdown'])}, "
        f"longest losing streak {book['losing_streak']}, "
        f"ending {_money(book['ending'])}. "
        f"Premium skips {book['premium_skipped']}. "
        f"Settlement skips {book['settlement_skipped']}. "
        f"PDT blocked {book['pdt_blocked']}."
    )


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


def _holdout_reads(reads: list[SessionRead]) -> list[SessionRead]:
    breaks = [read.day for read in reads if read.status == "break"]
    if len(breaks) < 2:
        return []
    mid = breaks[len(breaks) // 2]
    return [read for read in reads if read.day >= mid]


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
        "A short break of that low buys the at-the-money 0 DTE put. The break is the first later 5-minute bar that "
        "trades through the level. A print equal to the level is not a break. One trade a day. "
        "The default fill prices the underlying at the level plus stock slippage, then buys the option at the ask. "
        "A bar that opens through the level fills at that open. The next bar's open is a sensitivity.",
        "",
        "The book trades Monday, Wednesday, and Friday only, and it skips CPI, the Employment Situation, and FOMC "
        "decision days from the 2026 BLS schedule and the Federal Reserve's 2026 calendar. "
        "Friday SPY expirations were already listed before 2016. Wednesday expirations start August 31, 2016. "
        "Monday expirations start February 26, 2018. Tuesday and Thursday expirations start in November 2022 and "
        "are not traded. The option exits at the first of +100% of the entry ask, -50% of the entry ask, or 15:30 ET. "
        "Risk is the full premium, sized at $100 on a $1,000 cash account. One contract that costs more than $100 is skipped. "
        "$200 and $500 are sensitivities.",
        "",
        "There is no historical option chain. Prices are Black-Scholes with minutes left until 16:00 ET. "
        "Implied volatility is the prior session's VIX1D close when that print exists, otherwise the prior VIX close. "
        "The half-spread is the greater of one cent and 1.5% of the mid. A stop that the bid trades through fills at that bid. "
        "The model is the main source of uncertainty. A 1.3x volatility multiple is a sensitivity, not a new rule.",
        "",
        payload["sample_text"],
        "",
        f"Cash account, $100 risk, fill at the level: {_plain(default)}",
        "",
    ]
    if default["trades"] == 0 or default["expectancy"] <= 0 or default["ending"] <= default["starting"]:
        lines.append("The default book is not profitable on this sample.")
    else:
        lines.append(
            "The default book finished above the start. The sample is still the short Yahoo window, "
            "so that result is not a durable edge and the rule was not promoted."
        )
    lines.extend(
        [
            "",
            f"The same signals at $200 risk: {_plain(payload['risk_200'])}",
            "",
            f"The same signals at $500 risk: {_plain(payload['risk_500'])}",
            "",
            f"Next-bar open, $100, cash: {_plain(payload['next_open'])}",
            "",
            f"Volatility at 1.3 times the prior close, $100, cash: {_plain(payload['iv_130'])}",
            "",
            "A $1,000 account is under the $2,000 minimum to use margin, so the default is cash and the "
            "pattern-day-trader rule does not apply. Sale proceeds settle the next session. "
            f"The same signals on a hypothetical margin account under $25,000: {_plain(payload['margin'])} "
            "Three Monday/Wednesday/Friday trades fit in five business days. A fourth appears only when a "
            "Tuesday or Thursday holiday pulls another one of those weekdays into the window. This file has no such holiday.",
            "",
            f"Random call-or-put at the same break, seed 17, same exits: {_plain(payload['random'])}",
            "",
            f"Second half of the break days, same frozen rule: {_plain(payload['holdout'])}",
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


def main() -> None:
    rules = frozen_rules()
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(rules, indent=2) + "\n")
    if rules["risk"] != RISK_PRIMARY or rules["fill"].startswith("Default") is False or rules["dte"] != 0:
        raise SystemExit("rules file does not match the module")
    print("RULES FROZEN", RULES_PATH, flush=True)
    probe = _probe_yahoo_limit()
    print("PROBE", probe, flush=True)
    provider = YFinanceProvider(CACHE)
    spy = provider.history(["SPY"], "2026-08-13", DOWNLOAD_END, interval="5m").get("SPY")
    one = provider.history(["SPY"], "2026-10-01", DOWNLOAD_END, interval="1m").get("SPY")
    daily = provider.history(["^VIX", "^VIX1D"], "2026-07-01", DOWNLOAD_END, interval="1d")
    if spy is None or spy.empty:
        raise SystemExit("no SPY 5-minute bars")
    vix = daily.get("^VIX")
    vix1d = daily.get("^VIX1D")
    if vix is None or vix.empty:
        raise SystemExit("no VIX")
    iv = prior_iv(
        pd.Series(dtype=float) if vix1d is None else vix1d["close"],
        vix["close"],
    )
    reads = scan(spy, "5m")
    uncovered = [read.day.isoformat() for read in reads if read.status == "calendar_uncovered"]
    if uncovered:
        raise SystemExit("event calendar does not cover " + ", ".join(uncovered))
    common = dict(clock="5m")
    default = _book(spy, reads, iv, risk=RISK_PRIMARY, account="cash", fill=FILL_PRIMARY, iv_scale=IV_PRIMARY, **common)
    books = {
        "default": default,
        "risk_200": _book(spy, reads, iv, risk=RISK_SENSITIVITIES[0], account="cash", **common),
        "risk_500": _book(spy, reads, iv, risk=RISK_SENSITIVITIES[1], account="cash", **common),
        "next_open": _book(spy, reads, iv, risk=RISK_PRIMARY, account="cash", fill="next_open", **common),
        "iv_130": _book(spy, reads, iv, risk=RISK_PRIMARY, account="cash", iv_scale=IV_SENSITIVITY, **common),
        "margin": _book(spy, reads, iv, risk=RISK_PRIMARY, account="margin", **common),
        "random": _book(spy, reads, iv, risk=RISK_PRIMARY, account="cash", seed=SEED, **common),
    }
    hold_reads = _holdout_reads(reads)
    books["holdout"] = _book(spy, hold_reads, iv, risk=RISK_PRIMARY, account="cash", **common) if hold_reads else default
    one_book = None
    if one is not None and not one.empty:
        one_reads = scan(one, "1m")
        one_book = _book(one, one_reads, iv, risk=RISK_PRIMARY, account="cash", clock="1m")
    counted = _counts(reads)
    held = _buy_hold(spy)
    compared = _compare_1m(spy, one if one is not None else pd.DataFrame())
    matched = sum(1 for row in compared if row["match"])
    charts = []
    by_day = {read.day: read for read in reads}
    for day in _chart_days(reads):
        charts.append(_chart(spy, day, by_day.get(day), "5m", CHART_DIR / f"orb_mwf_spy_{day.isoformat()}.png"))
    if one is not None and not one.empty and CHART_DAY in set(rth(one).index.date):
        one_read = next((read for read in scan(one, "1m") if read.day == CHART_DAY), None)
        charts.append(_chart(one, CHART_DAY, one_read, "1m", CHART_DIR / f"orb_mwf_spy_{CHART_DAY.isoformat()}_1m.png"))
    sample_text = (
        f"Yahoo's 5-minute file runs from {counted['first']} through {counted['last']}, "
        f"{counted['sessions']} sessions. {probe} "
        "No Alpaca, Polygon, or other intraday key is in this environment, and a paid archive was not bought. "
        "A 60-minute bar does not contain the 09:30-09:35 high and low, so it was not used as a stand-in. "
        f"Session marks: {json.dumps(counted['statuses'])}. "
        f"Skipped releases inside the file: {json.dumps(counted['events'])}."
    )
    share_word = "share" if held["shares"] == 1 else "shares"
    buy_hold_text = (
        f"SPY buy and hold, {held['shares']} {share_word} from the first open to the last close, "
        f"ended at {_money(held['ending'])}."
    )
    if one_book is None:
        minute_text = "Yahoo returned no 1-minute bars."
    else:
        minute_text = (
            f"1-minute bars cover {compared[0]['date'] if compared else 'n/a'} through "
            f"{compared[-1]['date'] if compared else 'n/a'}. "
            f"The 09:30-09:34 high and low matched the 5-minute candle on {matched} of {len(compared)} overlapping sessions. "
            f"The 1-minute break, cash, $100, over that short window only: {_plain(one_book)} "
            "That window is anecdotal and is not the verdict."
        )
    chart_bits = []
    for fact in charts:
        if "or_high" not in fact:
            continue
        trade = "no trade" if fact["status"] != "break" else "break traded"
        kind = f", {fact['event']}" if fact.get("event") else ""
        chart_bits.append(
            f"{fact['date']} {fact['clock']} high {fact['or_high']:.2f} low {fact['or_low']:.2f}, "
            f"{trade}{kind}, after that candle {fact['low_after']:.2f}-{fact['high_after']:.2f}, close {fact['close']:.2f}"
        )
    chart_text = "Charts, examples only: " + "; ".join(chart_bits) + "."
    payload = {
        "rules": rules,
        "counts": counted,
        "sample_text": sample_text,
        "buy_hold_text": buy_hold_text,
        "minute_text": minute_text,
        "chart_text": chart_text,
        "buy_hold": held,
        "compare_1m": compared,
        "charts": charts,
        "probe": probe,
        **books,
    }
    if one_book is not None:
        payload["one_minute"] = one_book
    block = render(payload)
    _write_results(block)
    stored = dict(payload)
    PAYLOAD_PATH.write_text(json.dumps(stored, indent=2, default=str) + "\n")
    print(block)
    print("WROTE", PAYLOAD_PATH, flush=True)


if __name__ == "__main__":
    main()
