"""Indicator and pattern survey. Research only.

The catalog, the windows, and the round plan are frozen in this file.
Round 1 is the catalog. Later rounds only refine near-misses from that
catalog, and every refined cell is another trial. The most recent three
months are not an input to those rounds.

Nothing here places an order or edits a sandbox book.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from webull_bot.calendar import is_trading_day, next_trading_day, nyse_holidays
from webull_bot.chart_reads.atm_exit import deflated_sharpe
from webull_bot.chart_reads.candles import detect
from webull_bot.chart_reads.vwap_band import metrics_from
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.indicators import atr as wilder_atr
from webull_bot.indicators import ema, rsi, sma
from webull_bot.options.pricing import listed_strike, option_price

SELECT_START = date(2025, 10, 8)
SELECT_END = date(2026, 7, 6)
PRIOR_START = date(2018, 1, 1)
PRIOR_END = date(2025, 10, 7)
HOLDOUT_START = date(2026, 7, 7)
HOLDOUT_END = date(2026, 10, 6)

GATE_PF = 1.10
GATE_SHARPE = 0.40
GATE_DRAWDOWN = -0.30
SELECT_MIN_TRADES = 20
PRIOR_MIN_TRADES = 80
FDR_Q = 0.10
DSR_MIN = 0.95
NEAR_MIN_TRADES = 15
NEAR_PF = 1.0
NEAR_SHARPE = 0.0
NEAR_DRAWDOWN = -0.45
MAX_NEAR = 8
DAILY_CAP = 3
RISK_FRACTION = 0.01
RANDOM_SEED = 17
OPTION_RATE = 0.02
OPTION_DIVIDEND = 0.0

# Candidate pools were ranked on average daily dollar volume from
# 2025-10-08 through 2026-10-06 (close times volume) before any signal
# was scored. Liquidity uses that whole year, including the holdout
# dates, and is not a strategy result. The six winners are hardcoded so
# a later vendor revision cannot move the universe.
GROWTH_CANDIDATES = (
    "PLTR", "COIN", "SHOP", "SNOW", "CRWD", "NET", "DDOG", "ARM", "APP", "HOOD",
    "MSTR", "UBER", "ABNB", "MELI", "SE", "DKNG", "ROKU", "AFRM", "RBLX", "SNAP",
)
TECH_CANDIDATES = (
    "AMD", "AVGO", "NFLX", "MU", "AMAT", "QCOM", "CRM", "ORCL", "ADBE", "INTU",
    "PANW", "NOW", "TXN", "LRCX", "KLAC", "SNPS", "CDNS", "IBM", "CSCO", "INTC",
)
GROWTH_DOLLAR_VOLUME = {
    "PLTR": 6838305479.272785,
    "MSTR": 3038281660.8648806,
    "HOOD": 2701432850.5771513,
    "APP": 2481546345.6107545,
    "COIN": 2061596334.0910888,
    "CRWD": 1726198559.3419251,
    "ARM": 1555100988.044403,
    "UBER": 1463309364.3881807,
    "SNOW": 1372330963.017285,
    "SHOP": 1298191850.1029296,
    "MELI": 1013491085.9547851,
    "DDOG": 894880033.2129791,
    "NET": 857233291.491278,
    "RBLX": 662177140.2113967,
    "ABNB": 623999312.7449707,
    "SE": 539771162.2442719,
    "ROKU": 389649995.33487546,
    "DKNG": 376884382.13008046,
    "AFRM": 349254180.5719894,
    "SNAP": 279932932.968304,
}
TECH_DOLLAR_VOLUME = {
    "MU": 23985588720.628525,
    "AMD": 11775828338.164404,
    "AVGO": 9456436633.085426,
    "INTC": 8486265910.046647,
    "ORCL": 4925963231.975146,
    "NFLX": 3816674377.248767,
    "AMAT": 3137506357.639539,
    "LRCX": 2703935188.093066,
    "CRM": 2526852468.0890503,
    "QCOM": 2491978636.3392944,
    "NOW": 2170811009.2967377,
    "CSCO": 2065113045.842102,
    "KLAC": 1839082759.1850219,
    "TXN": 1784207709.3191466,
    "PANW": 1774449457.8498597,
    "IBM": 1773314541.3695495,
    "INTU": 1438400334.1586304,
    "ADBE": 1408591897.1345825,
    "SNPS": 918340837.8201416,
    "CDNS": 744011606.4239868,
}
LIQUID_GROWTH = ("PLTR", "MSTR", "HOOD")
LIQUID_TECH = ("MU", "AMD", "AVGO")
MAG7 = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA")
UNIVERSE = ("SPY",) + MAG7 + LIQUID_GROWTH + LIQUID_TECH
UNIVERSES = {
    "all": UNIVERSE,
    "spy": ("SPY",),
    "mag7": MAG7,
    "liquid6": LIQUID_GROWTH + LIQUID_TECH,
}


@dataclass(frozen=True)
class Rule:
    id: str
    family: str
    timeframe: str
    exit_style: str
    plain: str
    requires_sma200: bool = False
    short: bool = False
    prior_years_complete: bool = True


def _rules() -> tuple[Rule, ...]:
    daily = "1d"
    trend = "trend"
    rows = [
        Rule("ema9_20", "trend", daily, trend, "Buy the next open after the 9 EMA crosses above the 20 EMA."),
        Rule("sma50_200", "trend", daily, trend, "Buy the next open after the 50-day average crosses above the 200-day average."),
        Rule("adx_200", "trend", daily, trend, "Buy the next open when ADX first clears 25 with +DI above -DI and the close above the 200-day average.", True),
        Rule("hhhl_break", "trend", daily, trend, "Buy the next open after a higher-high and higher-low structure breaks the last confirmed swing high."),
        Rule("donchian20", "trend", daily, trend, "Buy the next open after the close breaks the prior 20-day high."),
        Rule("sma200_pullback", "trend", daily, trend, "Buy the next open after price tags the 200-day average within half an ATR and closes back above it while the 9 EMA is above the 20 EMA.", True),
        Rule("rsi30_reclaim", "momentum", daily, trend, "Buy the next open after 14-day RSI crosses back above 30."),
        Rule("rsi_div", "momentum", daily, trend, "Buy the next open on a bullish RSI divergence: a lower price low, a higher RSI low, and a close through the high between those lows."),
        Rule("macd_cross", "momentum", daily, trend, "Buy the next open after the MACD line crosses above its signal line."),
        Rule("stoch_cross", "momentum", daily, trend, "Buy the next open after stochastic %K crosses above %D from below 20."),
        Rule("cci_cross", "momentum", daily, trend, "Buy the next open after CCI crosses above -100."),
        Rule("willr_cross", "momentum", daily, trend, "Buy the next open after Williams %R crosses above -80."),
        Rule("bb_reentry", "mean_reversion", daily, "mean_reversion", "Buy the next open after a close back inside the lower Bollinger band."),
        Rule("rsi2_200", "mean_reversion", daily, "mean_reversion", "Buy the next open when 2-day RSI first drops under 10 while the close is above the 200-day average.", True),
        Rule("vwap20_reclaim", "mean_reversion", daily, "mean_reversion", "Buy the next open after the close reclaims the 20-day VWAP of typical price."),
        Rule("prior_day_high", "support", daily, trend, "Buy the next open after the close breaks the prior day's high."),
        Rule("prior_week_high", "support", daily, trend, "Buy the next open after the close breaks the prior week's high."),
        Rule("swing_break", "support", daily, trend, "Buy the next open after the close breaks the last confirmed swing high."),
        Rule("swing_retest", "support", daily, trend, "Buy the next open after a swing-high break retests that level within half an ATR and closes back above it."),
        Rule("cup_handle", "chart", daily, trend, "Buy the next open on a 40-bar cup and handle: an 8 percent cup, a right rim within 3 percent of the left rim, a handle above the midpoint, and a close through the right rim."),
        Rule("bull_flag", "chart", daily, trend, "Buy the next open after a 5 percent impulse, a flag that gives back less than half of it, and a close through the flag high."),
        Rule("asc_triangle", "chart", daily, trend, "Buy the next open after 15 bars of lower highs and higher lows close through the range high."),
        Rule("double_bottom", "chart", daily, trend, "Buy the next open after two swing lows within 1.5 percent, at least 8 bars apart, and a close through the neckline."),
        Rule("base_breakout", "chart", daily, trend, "Buy the next open after a 15-bar base no wider than 2 ATR breaks out on at least 1.5 times average volume."),
        Rule("double_top", "chart", daily, trend, "Double top. The share book is long-only, so this cell is counted and takes no share trade.", short=True),
        Rule("head_shoulders", "chart", daily, trend, "Head and shoulders. The share book is long-only, so this cell is counted and takes no share trade.", short=True),
        Rule("candle_rev", "candle", daily, trend, "Buy the next open on a long reversal candlestick in its trend-and-location context."),
        Rule("candle_cont", "candle", daily, trend, "Buy the next open on a long continuation candlestick in its trend-and-location context."),
        Rule("relvol_breakout", "volume", daily, trend, "Buy the next open after a 20-day-high close with volume at least 1.5 times the 20-day average."),
        Rule("obv_break", "volume", daily, trend, "Buy the next open when on-balance volume makes a 20-day high and the close breaks the prior high."),
        Rule("vwap_vol", "volume", daily, trend, "Buy the next open after a cross above the 20-day VWAP with volume at least 1.2 times average."),
    ]
    for name, weekday in (("dow_mon", "Monday"), ("dow_tue", "Tuesday"), ("dow_wed", "Wednesday"), ("dow_thu", "Thursday"), ("dow_fri", "Friday")):
        rows.append(Rule(name, "seasonality", daily, "seasonality", f"Buy {weekday}'s open and sell {weekday}'s close. The weekday is known at the prior close."))
    for month in range(1, 13):
        rows.append(Rule(f"month_{month}", "seasonality", daily, "seasonality", f"Buy the first session of month {month} and sell the last session of that month."))
    rows.extend(
        [
            Rule("tom", "seasonality", daily, "seasonality", "Buy the open of the last session of the month and sell the close of the third session of the new month. One trade per turn."),
            Rule("pre_holiday", "seasonality", daily, "seasonality", "Buy the open of a session that is followed by a weekday NYSE holiday and sell that session's close. A normal weekend is not a holiday."),
            Rule("opex", "seasonality", daily, "seasonality", "Buy Monday's open in options-expiration week, or the next session if Monday is shut, and sell the Friday close."),
            Rule("ema_rsi", "combo", daily, trend, "Buy the next open when the 9 EMA is above the 20 EMA and RSI crosses up through 40."),
            Rule("sma200_break", "combo", daily, trend, "Buy the next open after a 20-day-high break while the close is above the 200-day average.", True),
            Rule("sma200_rel_candle", "combo", daily, trend, "Buy the next open when the close is above the 200-day average, volume is at least 1.5 times average, and a continuation candle prints.", True),
            Rule("bb_rsi2", "combo", daily, "mean_reversion", "Buy the next open when the close is under the lower Bollinger band and 2-day RSI is under 10."),
            Rule("db_relvol", "combo", daily, trend, "Buy the next open on a double-bottom neckline break with volume at least 1.5 times average."),
            Rule("cup_sma200", "combo", daily, trend, "Buy the next open on a cup and handle while the close is above the 200-day average.", True),
            Rule("macd_sma200", "combo", daily, trend, "Buy the next open on a MACD cross while the close is above the 200-day average.", True),
            Rule("tom_sma200", "combo", daily, "seasonality", "Turn-of-month trade, and only when the signal close is above the 200-day average.", True),
            Rule("h_ema9_20", "hourly", "60m", trend, "Hourly 9/20 EMA cross. Yahoo hourly history does not reach 2018, so this cell cannot pass the prior-year check.", prior_years_complete=False),
            Rule("h_session_vwap", "hourly", "60m", trend, "Hourly reclaim of the session VWAP. Yahoo hourly history does not reach 2018, so this cell cannot pass the prior-year check.", prior_years_complete=False),
            Rule("h_orb", "hourly", "60m", "session", "Buy the next hour after a close through the first hour's high, and flatten at the 15:30 open. This cell cannot pass the prior-year check.", prior_years_complete=False),
            Rule("h_1030", "hourly", "60m", "session", "Buy the next hour after a green 10:30 bar that closes above the session VWAP, and flatten at the 15:30 open. This cell cannot pass the prior-year check.", prior_years_complete=False),
        ]
    )
    return tuple(rows)


CATALOG: tuple[Rule, ...] = _rules()
CATALOG_BY_ID: dict[str, Rule] = {rule.id: rule for rule in CATALOG}


@dataclass(frozen=True)
class ExitParams:
    stop_atr: float
    stop_from: str
    target: str
    time_bars: int | None
    sma_filter: bool
    universe: str
    cap: int
    style: str


@dataclass(frozen=True)
class Trade:
    symbol: str
    signal_i: int
    fill_i: int
    exit_i: int
    fill_date: date
    exit_date: date
    fill_raw: float
    exit_raw: float
    stop_raw: float
    priority: float
    reason: str
    above_sma: bool


@dataclass
class Prepared:
    symbol: str
    timeframe: str
    dates: list[date]
    session_dates: list[date]
    date_last: dict[date, int]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    atr: np.ndarray
    sma20: np.ndarray
    sma200: np.ndarray
    dollar_vol: np.ndarray
    minutes: np.ndarray
    masks: dict[str, np.ndarray]
    season_exit: dict[str, np.ndarray]


def frozen_rules() -> dict:
    """The grid, written down without reading a price."""
    return {
        "selection": [SELECT_START.isoformat(), SELECT_END.isoformat()],
        "prior": [PRIOR_START.isoformat(), PRIOR_END.isoformat()],
        "holdout": [HOLDOUT_START.isoformat(), HOLDOUT_END.isoformat()],
        "holdout_rule": "Scored once, after the rounds, and never used to choose a refinement.",
        "gate": {
            "profit_factor": GATE_PF,
            "sharpe": GATE_SHARPE,
            "max_drawdown": GATE_DRAWDOWN,
            "selection_min_trades": SELECT_MIN_TRADES,
            "prior_min_trades": PRIOR_MIN_TRADES,
            "fdr_q": FDR_Q,
            "deflated_sharpe": DSR_MIN,
            "must_beat_random_sharpe": True,
            "ending_above_start": True,
        },
        "near_miss": {
            "selection_min_trades": NEAR_MIN_TRADES,
            "profit_factor": NEAR_PF,
            "sharpe": NEAR_SHARPE,
            "max_drawdown": NEAR_DRAWDOWN,
            "must_fail_a_full_window": True,
            "rank": "prior sharpe",
            "max_parents": MAX_NEAR,
            "hourly_not_refined": True,
        },
        "rounds": {
            "1": "The frozen catalog, daily cap 3, family exits.",
            "2": "For each near-miss: 1R or a 3-bar mean-reversion hold, SMA200 or a half-ATR stop, SPY only, Mag7 only, liquid-6 only, cap 5.",
            "3": "If a round-2 cell improves prior Sharpe and keeps selection profit factor at least 1, stack the modal variant with the 1R or shorter-hold variant. At most 8.",
        },
        "costs": {
            "slippage_bps": 5.0,
            "half_spread_bps": 1.0,
            "sec_per_million": 20.60,
            "finra_taf_per_share": 0.000195,
            "finra_taf_cap": 9.79,
        },
        "account": {
            "long_only_shares": True,
            "whole_shares": True,
            "risk_fraction": RISK_FRACTION,
            "daily_cap": DAILY_CAP,
            "settlement": "T+1",
            "starting": [1000, 5000],
        },
        "random": {"seed": RANDOM_SEED, "exit": "time only, median hold of the taken trades"},
        "excluded_timeframes": {
            "15m": "Yahoo 15-minute history is about 60 days and, from this sample, sits inside the holdout. It is not scored.",
        },
        "hourly": "Yahoo 60-minute history starts in 2024. Those cells are in the trial count and cannot pass.",
        "universe": list(UNIVERSE),
        "liquid_growth": list(LIQUID_GROWTH),
        "liquid_tech": list(LIQUID_TECH),
        "growth_dollar_volume": GROWTH_DOLLAR_VOLUME,
        "tech_dollar_volume": TECH_DOLLAR_VOLUME,
        "catalog": [rule.id for rule in CATALOG],
    }


def is_pre_holiday(day: date) -> bool:
    """True when a weekday holiday sits strictly between this session and the next."""
    nxt = next_trading_day(day)
    holidays = nyse_holidays(day.year)
    if nxt.year != day.year:
        holidays = holidays | nyse_holidays(nxt.year)
    cursor = day + timedelta(days=1)
    while cursor < nxt:
        if cursor.weekday() < 5 and cursor in holidays:
            return True
        cursor += timedelta(days=1)
    return False


def assert_window_visible(end: date, *, allow_holdout: bool) -> None:
    if not allow_holdout and end >= HOLDOUT_START:
        raise RuntimeError("this scorer cannot read the final holdout")


def exit_params(rule: Rule, tokens: tuple[str, ...]) -> ExitParams:
    """Family exit, then the frozen variant tokens."""
    style = rule.exit_style
    if style == "mean_reversion":
        stop_atr, stop_from, target, time_bars = 2.0, "fill", "sma20", 5
    elif style == "seasonality":
        stop_atr, stop_from, target, time_bars = 3.0, "fill", "none", None
    elif style == "session":
        stop_atr, stop_from, target, time_bars = 1.0, "low", "r2", None
    else:
        stop_atr, stop_from, target, time_bars = 1.0, "low", "r2", 15
    if "exit" in tokens:
        if style == "mean_reversion":
            time_bars = 3
        else:
            target = "r1"
    if "half_stop" in tokens:
        stop_atr = 0.5
    if "spy" in tokens:
        universe = "spy"
    elif "mag7" in tokens:
        universe = "mag7"
    elif "liquid6" in tokens:
        universe = "liquid6"
    else:
        universe = "all"
    cap = 5 if "cap5" in tokens else DAILY_CAP
    return ExitParams(stop_atr, stop_from, target, time_bars, "sma200" in tokens, universe, cap, style)


def variant_name(tokens: tuple[str, ...]) -> str:
    if not tokens:
        return "base"
    return "+".join(tokens)


def cell_id(rule_id: str, tokens: tuple[str, ...]) -> str:
    name = variant_name(tokens)
    if name == "base":
        return rule_id
    return f"{rule_id}__{name}"


def behavior_key(rule: Rule, tokens: tuple[str, ...]) -> tuple:
    params = exit_params(rule, tokens)
    sma_on = params.sma_filter or rule.requires_sma200
    return (params.stop_atr, params.stop_from, params.target, params.time_bars, params.style, sma_on, params.universe, params.cap)


def plain_text(rule: Rule, tokens: tuple[str, ...]) -> str:
    params = exit_params(rule, tokens)
    if params.style == "mean_reversion":
        exit_line = (
            f"Stop is the fill minus {params.stop_atr:g} ATR. "
            "Target is the 20-day average when that sits above the fill, otherwise 1R. "
            f"Time stop is {params.time_bars} bars."
        )
    elif params.style == "seasonality":
        if params.target == "none":
            exit_line = f"Stop is the fill minus {params.stop_atr:g} ATR. Exit at the end of the seasonal window, with no profit target."
        else:
            exit_line = (
                f"Stop is the fill minus {params.stop_atr:g} ATR. "
                "A 1R target is added, and the seasonal window still closes the trade."
            )
    elif params.style == "session":
        multiple = "1R" if params.target == "r1" else "2R"
        exit_line = f"Stop is the signal low minus {params.stop_atr:g} ATR. Target is {multiple}. Flatten at the 15:30 open."
    else:
        multiple = "1R" if params.target == "r1" else "2R"
        exit_line = (
            f"Stop is the signal low minus {params.stop_atr:g} ATR. Target is {multiple}. "
            f"Time stop is {params.time_bars} bars."
        )
    notes = []
    if params.sma_filter and not rule.requires_sma200:
        notes.append("A close above the 200-day average is required.")
    if params.universe == "spy":
        notes.append("SPY only.")
    elif params.universe == "mag7":
        notes.append("Magnificent Seven only.")
    elif params.universe == "liquid6":
        notes.append("The six liquid growth and tech names only.")
    if params.cap == 5:
        notes.append("Up to five new entries a day.")
    else:
        notes.append("Up to three new entries a day.")
    return " ".join([rule.plain, exit_line, *notes])


def _shift(values: np.ndarray, fill: float = np.nan) -> np.ndarray:
    out = np.empty(len(values), dtype=float)
    if len(values) == 0:
        return out
    out[0] = fill
    out[1:] = values[:-1]
    return out


def _edge(mask: np.ndarray) -> np.ndarray:
    out = np.asarray(mask, dtype=bool).copy()
    if len(out) == 0:
        return out
    out[0] = False
    out[1:] &= ~np.asarray(mask[:-1], dtype=bool)
    return out


def _third_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    offset = (4 - first.weekday()) % 7
    return date(year, month, 1 + offset + 14)


def _seasonal(dates: list[date]) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    n = len(dates)
    masks: dict[str, np.ndarray] = {}
    exits: dict[str, np.ndarray] = {}
    for weekday, name in enumerate(("dow_mon", "dow_tue", "dow_wed", "dow_thu", "dow_fri")):
        sig = np.zeros(n, dtype=bool)
        ex = np.full(n, -1, dtype=int)
        for i in range(1, n):
            if dates[i].weekday() == weekday:
                sig[i - 1] = True
                ex[i - 1] = i
        masks[name] = sig
        exits[name] = ex
    groups: list[tuple[int, int]] = []
    start = 0
    for i in range(1, n + 1):
        if i == n or (dates[i].year, dates[i].month) != (dates[start].year, dates[start].month):
            groups.append((start, i - 1))
            start = i
    for month in range(1, 13):
        sig = np.zeros(n, dtype=bool)
        ex = np.full(n, -1, dtype=int)
        for first, last in groups:
            if dates[first].month != month or first == 0:
                continue
            sig[first - 1] = True
            ex[first - 1] = last
        masks[f"month_{month}"] = sig
        exits[f"month_{month}"] = ex
    sig = np.zeros(n, dtype=bool)
    ex = np.full(n, -1, dtype=int)
    for index in range(len(groups) - 1):
        _first, last = groups[index]
        nxt, nxt_last = groups[index + 1]
        third = nxt + 2
        if third > nxt_last or last < 1:
            continue
        sig[last - 1] = True
        ex[last - 1] = third
    masks["tom"] = sig
    exits["tom"] = ex
    sig = np.zeros(n, dtype=bool)
    ex = np.full(n, -1, dtype=int)
    for i in range(1, n):
        if is_pre_holiday(dates[i]):
            sig[i - 1] = True
            ex[i - 1] = i
    masks["pre_holiday"] = sig
    exits["pre_holiday"] = ex
    sig = np.zeros(n, dtype=bool)
    ex = np.full(n, -1, dtype=int)
    for first, last in groups:
        friday = _third_friday(dates[first].year, dates[first].month)
        monday = friday - timedelta(days=4)
        entry = None
        exit_i = None
        for i in range(first, last + 1):
            if monday <= dates[i] <= friday:
                if entry is None:
                    entry = i
                exit_i = i
        if entry is None or exit_i is None or entry == 0:
            continue
        sig[entry - 1] = True
        ex[entry - 1] = exit_i
    masks["opex"] = sig
    exits["opex"] = ex
    return masks, exits


def _cup_handle(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    n = len(close)
    out = np.zeros(n, dtype=bool)
    for i in range(40, n):
        left = float(np.max(high[i - 39 : i - 24]))
        bottom = float(np.min(low[i - 24 : i - 9]))
        right = float(np.max(high[i - 9 : i - 3]))
        handle = float(np.min(low[i - 3 : i + 1]))
        if not np.isfinite([left, bottom, right, handle]).all() or left <= 0:
            continue
        if bottom > left * 0.92:
            continue
        if abs(right - left) / left > 0.03:
            continue
        if handle <= 0.5 * (right + bottom):
            continue
        if close[i] <= right or close[i - 1] > right:
            continue
        out[i] = True
    return out


def _bull_flag(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    n = len(close)
    out = np.zeros(n, dtype=bool)
    for i in range(8, n):
        base = float(close[i - 8])
        end = float(close[i - 4])
        if base <= 0 or not np.isfinite(base) or not np.isfinite(end):
            continue
        if end / base - 1.0 < 0.05:
            continue
        flag_high = float(np.max(high[i - 3 : i]))
        flag_low = float(np.min(low[i - 3 : i]))
        impulse = end - base
        if impulse <= 0 or end - flag_low >= 0.5 * impulse:
            continue
        if close[i] <= flag_high or close[i - 1] > flag_high:
            continue
        out[i] = True
    return out


def _ascending_triangle(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    n = len(close)
    out = np.zeros(n, dtype=bool)
    for i in range(15, n):
        highs = high[i - 15 : i]
        lows = low[i - 15 : i]
        if float(np.max(highs[7:])) >= float(np.max(highs[:7])):
            continue
        if float(np.min(lows[7:])) <= float(np.min(lows[:7])):
            continue
        if close[i] <= float(np.max(highs)):
            continue
        out[i] = True
    return out


def _base_breakout(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, atr: np.ndarray) -> np.ndarray:
    n = len(close)
    out = np.zeros(n, dtype=bool)
    vol_avg = pd.Series(volume).shift(1).rolling(20, min_periods=20).mean().to_numpy()
    for i in range(20, n):
        if not np.isfinite(atr[i]) or atr[i] <= 0 or not np.isfinite(vol_avg[i]):
            continue
        rng_high = float(np.max(high[i - 15 : i]))
        rng_low = float(np.min(low[i - 15 : i]))
        if rng_high - rng_low > 2.0 * atr[i]:
            continue
        if close[i] <= rng_high or volume[i] < 1.5 * vol_avg[i]:
            continue
        prior = float(np.max(high[i - 16 : i - 1])) if i >= 16 else rng_high
        if close[i - 1] > prior:
            continue
        out[i] = True
    return out


def _swings(high: np.ndarray, low: np.ndarray) -> dict[str, np.ndarray]:
    n = len(high)
    last_h = prev_h = last_l = prev_l = np.nan
    last_hi = prev_hi = last_li = prev_li = -1
    sh = np.full(n, np.nan)
    sh_prev = np.full(n, np.nan)
    sl = np.full(n, np.nan)
    sl_prev = np.full(n, np.nan)
    sh_i = np.full(n, -1, dtype=int)
    sh_prev_i = np.full(n, -1, dtype=int)
    sl_i = np.full(n, -1, dtype=int)
    sl_prev_i = np.full(n, -1, dtype=int)
    conf_l = np.zeros(n, dtype=bool)
    conf_h = np.zeros(n, dtype=bool)
    for i in range(2, n):
        if low[i - 1] < low[i - 2] and low[i - 1] < low[i]:
            prev_l, last_l = last_l, low[i - 1]
            prev_li, last_li = last_li, i - 1
            conf_l[i] = True
        if high[i - 1] > high[i - 2] and high[i - 1] > high[i]:
            prev_h, last_h = last_h, high[i - 1]
            prev_hi, last_hi = last_hi, i - 1
            conf_h[i] = True
        sh[i] = last_h
        sh_prev[i] = prev_h
        sl[i] = last_l
        sl_prev[i] = prev_l
        sh_i[i] = last_hi
        sh_prev_i[i] = prev_hi
        sl_i[i] = last_li
        sl_prev_i[i] = prev_li
    return {
        "sh": sh,
        "sh_prev": sh_prev,
        "sl": sl,
        "sl_prev": sl_prev,
        "sh_i": sh_i,
        "sh_prev_i": sh_prev_i,
        "sl_i": sl_i,
        "sl_prev_i": sl_prev_i,
        "conf_l": conf_l,
        "conf_h": conf_h,
    }


def _pattern_breaks(high: np.ndarray, low: np.ndarray, close: np.ndarray, rsi14: np.ndarray, swings: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    n = len(close)
    div = np.zeros(n, dtype=bool)
    double_bottom = np.zeros(n, dtype=bool)
    double_top = np.zeros(n, dtype=bool)
    head = np.zeros(n, dtype=bool)
    pending_bot: list[tuple[int, float]] = []
    pending_top: list[tuple[int, float]] = []
    pending_head: list[tuple[int, float]] = []
    swing_highs: list[tuple[int, float]] = []
    for i in range(2, n):
        if swings["conf_l"][i] and swings["sl_prev_i"][i] >= 0:
            i1 = int(swings["sl_i"][i])
            i0 = int(swings["sl_prev_i"][i])
            p1 = float(swings["sl"][i])
            p0 = float(swings["sl_prev"][i])
            if i1 - i0 >= 8 and p0 > 0 and abs(p1 - p0) / p0 <= 0.015:
                pending_bot.append((i, float(np.max(high[i0 : i1 + 1]))))
            if p1 < p0 and np.isfinite(rsi14[i1]) and np.isfinite(rsi14[i0]) and rsi14[i1] > rsi14[i0] and i1 > i0 + 1:
                span = high[i0 + 1 : i1]
                if len(span) and close[i] > float(np.max(span)):
                    div[i] = True
        if swings["conf_h"][i] and swings["sh_prev_i"][i] >= 0:
            i1 = int(swings["sh_i"][i])
            i0 = int(swings["sh_prev_i"][i])
            p1 = float(swings["sh"][i])
            p0 = float(swings["sh_prev"][i])
            if i1 - i0 >= 8 and p0 > 0 and abs(p1 - p0) / p0 <= 0.015:
                pending_top.append((i, float(np.min(low[i0 : i1 + 1]))))
            swing_highs.append((i1, p1))
            if len(swing_highs) >= 3:
                (_a, left), (_b, mid), (right_i, right) = swing_highs[-3:]
                if mid > left and mid > right and mid > 0 and (mid - left) / mid >= 0.01 and (mid - right) / mid >= 0.01:
                    pending_head.append((i, float(np.min(low[swing_highs[-3][0] : right_i + 1]))))
        pending_bot = [(born, neck) for born, neck in pending_bot if i - born <= 80]
        still_bot = []
        for born, neck in pending_bot:
            if close[i] > neck and close[i - 1] <= neck:
                double_bottom[i] = True
            else:
                still_bot.append((born, neck))
        pending_bot = still_bot
        pending_top = [(born, neck) for born, neck in pending_top if i - born <= 80]
        still_top = []
        for born, neck in pending_top:
            if close[i] < neck and close[i - 1] >= neck:
                double_top[i] = True
            else:
                still_top.append((born, neck))
        pending_top = still_top
        pending_head = [(born, neck) for born, neck in pending_head if i - born <= 80]
        still_head = []
        for born, neck in pending_head:
            if close[i] < neck and close[i - 1] >= neck:
                head[i] = True
            else:
                still_head.append((born, neck))
        pending_head = still_head
    return {"rsi_div": div, "double_bottom": double_bottom, "double_top": double_top, "head_shoulders": head}


def _hourly_masks(dates: list[date], minutes: np.ndarray, open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, ema9: np.ndarray, ema20: np.ndarray) -> dict[str, np.ndarray]:
    n = len(close)
    typical = (high + low + close) / 3.0
    vwap = np.full(n, np.nan)
    orb = np.full(n, np.nan)
    acc_pv = 0.0
    acc_v = 0.0
    current_orb = np.nan
    prev = None
    for i, day in enumerate(dates):
        if day != prev:
            acc_pv = 0.0
            acc_v = 0.0
            current_orb = np.nan
            prev = day
        acc_pv += float(typical[i] * volume[i])
        acc_v += float(volume[i])
        if acc_v > 0:
            vwap[i] = acc_pv / acc_v
        if int(minutes[i]) == 9 * 60 + 30:
            current_orb = float(high[i])
        orb[i] = current_orb
    ema_sig = np.zeros(n, dtype=bool)
    if n > 1:
        crossed = (ema9[1:] > ema20[1:]) & (ema9[:-1] <= ema20[:-1])
        finite = np.isfinite(ema9[1:]) & np.isfinite(ema20[1:]) & np.isfinite(ema9[:-1]) & np.isfinite(ema20[:-1])
        ema_sig[1:] = crossed & finite
    vwap_sig = np.zeros(n, dtype=bool)
    orb_sig = np.zeros(n, dtype=bool)
    ten_thirty = np.zeros(n, dtype=bool)
    for i in range(1, n):
        same = dates[i] == dates[i - 1]
        if same and int(minutes[i]) < 15 * 60 + 30 and np.isfinite(vwap[i]) and np.isfinite(vwap[i - 1]):
            if close[i] > vwap[i] and close[i - 1] <= vwap[i - 1]:
                vwap_sig[i] = True
        clock = int(minutes[i])
        if 9 * 60 + 30 < clock < 15 * 60 + 30 and np.isfinite(orb[i]) and close[i] > orb[i]:
            prev_above = same and np.isfinite(orb[i - 1]) and close[i - 1] > orb[i - 1]
            if not prev_above:
                orb_sig[i] = True
        if clock == 10 * 60 + 30 and close[i] > open_[i] and np.isfinite(vwap[i]) and close[i] > vwap[i]:
            ten_thirty[i] = True
    return {"h_ema9_20": ema_sig, "h_session_vwap": vwap_sig, "h_orb": orb_sig, "h_1030": ten_thirty}


def compute_masks(frame: pd.DataFrame, dates: list[date], minutes: np.ndarray, timeframe: str) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Causal signal masks. Index i uses bars through i."""
    open_ = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float)
    index = frame.index
    close_s = pd.Series(close, index=index)
    ema9 = ema(close_s, 9).to_numpy(dtype=float)
    ema20 = ema(close_s, 20).to_numpy(dtype=float)
    if timeframe == "60m":
        return _hourly_masks(dates, minutes, open_, high, low, close, volume, ema9, ema20), {}
    sma20_v = sma(close_s, 20).to_numpy(dtype=float)
    sma50 = sma(close_s, 50).to_numpy(dtype=float)
    sma200 = sma(close_s, 200).to_numpy(dtype=float)
    atr = wilder_atr(frame, 14).to_numpy(dtype=float)
    rsi14 = rsi(close_s, 14).to_numpy(dtype=float)
    rsi2 = rsi(close_s, 2).to_numpy(dtype=float)
    macd_line = (ema(close_s, 12) - ema(close_s, 26)).to_numpy(dtype=float)
    macd_signal = ema(pd.Series(macd_line, index=index), 9).to_numpy(dtype=float)
    typical = (high + low + close) / 3.0
    tp = pd.Series(typical, index=index)
    tp_sma = tp.rolling(20, min_periods=20).mean()
    mean_dev = (tp - tp_sma).abs().rolling(20, min_periods=20).mean()
    cci = ((tp - tp_sma) / (0.015 * mean_dev)).to_numpy(dtype=float)
    lowest = pd.Series(low, index=index).rolling(14, min_periods=14).min()
    highest = pd.Series(high, index=index).rolling(14, min_periods=14).max()
    span = (highest - lowest).replace(0.0, np.nan)
    k = (100.0 * (close_s - lowest) / span).to_numpy(dtype=float)
    d = sma(pd.Series(k, index=index), 3).to_numpy(dtype=float)
    willr = (-100.0 * (highest - close_s) / span).to_numpy(dtype=float)
    std = close_s.rolling(20, min_periods=20).std(ddof=0)
    lower = (sma(close_s, 20) - 2.0 * std).to_numpy(dtype=float)
    pv = pd.Series(typical * volume, index=index)
    vol_s = pd.Series(volume, index=index)
    vwap20 = (pv.rolling(20, min_periods=20).sum() / vol_s.rolling(20, min_periods=20).sum()).to_numpy(dtype=float)
    vol_avg = vol_s.shift(1).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
    direction = np.sign(np.diff(close, prepend=close[0] if len(close) else 0.0))
    if len(direction):
        direction[0] = 0.0
    obv = np.cumsum(direction * volume)
    prior_high_20 = pd.Series(high).shift(1).rolling(20, min_periods=20).max().to_numpy(dtype=float)
    prior_high_5 = pd.Series(high).shift(1).rolling(5, min_periods=5).max().to_numpy(dtype=float)
    prior_high_1 = _shift(high)
    obv_prior = pd.Series(obv, index=index).shift(1).rolling(20, min_periods=20).max().to_numpy(dtype=float)
    up_move = np.diff(high, prepend=np.nan)
    down_move = -np.diff(low, prepend=np.nan)
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    prev_close = _shift(close)
    tr = np.nanmax(np.vstack([high - low, np.abs(high - prev_close), np.abs(low - prev_close)]), axis=0)
    atr_w = pd.Series(tr, index=index).ewm(alpha=1.0 / 14.0, adjust=False, min_periods=14).mean().to_numpy()
    plus_di = 100.0 * pd.Series(plus_dm, index=index).ewm(alpha=1.0 / 14.0, adjust=False, min_periods=14).mean().to_numpy() / atr_w
    minus_di = 100.0 * pd.Series(minus_dm, index=index).ewm(alpha=1.0 / 14.0, adjust=False, min_periods=14).mean().to_numpy() / atr_w
    dx = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = pd.Series(dx, index=index).ewm(alpha=1.0 / 14.0, adjust=False, min_periods=14).mean().to_numpy()
    candles = detect(frame)
    rev = candles["reversal_long_context"].to_numpy(dtype=bool) if len(candles) else np.zeros(len(close), dtype=bool)
    cont = candles["continuation_long_context"].to_numpy(dtype=bool) if len(candles) else np.zeros(len(close), dtype=bool)
    swings = _swings(high, low)
    breaks = _pattern_breaks(high, low, close, rsi14, swings)
    n = len(close)

    def cross(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        out = np.zeros(n, dtype=bool)
        if n < 2:
            return out
        out[1:] = (left[1:] > right[1:]) & (left[:-1] <= right[:-1])
        out[1:] &= np.isfinite(left[1:]) & np.isfinite(right[1:]) & np.isfinite(left[:-1]) & np.isfinite(right[:-1])
        return out

    def cross_level(values: np.ndarray, level: float) -> np.ndarray:
        out = np.zeros(n, dtype=bool)
        if n < 2:
            return out
        out[1:] = (values[1:] > level) & (values[:-1] <= level) & np.isfinite(values[1:]) & np.isfinite(values[:-1])
        return out

    masks: dict[str, np.ndarray] = {}
    masks["ema9_20"] = cross(ema9, ema20)
    masks["sma50_200"] = cross(sma50, sma200)
    adx_state = (adx > 25.0) & (plus_di > minus_di) & (close > sma200) & np.isfinite(adx) & np.isfinite(sma200)
    masks["adx_200"] = _edge(adx_state)
    known_h = _shift(swings["sh"])
    known_hp = _shift(swings["sh_prev"])
    known_l = _shift(swings["sl"])
    known_lp = _shift(swings["sl_prev"])
    prev_c = _shift(close)
    masks["hhhl_break"] = (known_h > known_hp) & (known_l > known_lp) & (close > known_h) & (prev_c <= known_h) & np.isfinite(known_h)
    masks["donchian20"] = _edge((close > prior_high_20) & np.isfinite(prior_high_20))
    tag = (low <= sma200 + 0.5 * atr) & (close > sma200) & (ema9 > ema20) & (prev_c <= _shift(sma200))
    masks["sma200_pullback"] = tag & np.isfinite(sma200) & np.isfinite(atr) & np.isfinite(ema9)
    masks["rsi30_reclaim"] = cross_level(rsi14, 30.0)
    masks["rsi_div"] = breaks["rsi_div"]
    masks["macd_cross"] = cross(macd_line, macd_signal)
    stoch = cross(k, d)
    if n > 1:
        stoch[1:] &= k[:-1] < 20.0
    masks["stoch_cross"] = stoch
    masks["cci_cross"] = cross_level(cci, -100.0)
    masks["willr_cross"] = cross_level(willr, -80.0)
    masks["bb_reentry"] = np.zeros(n, dtype=bool)
    if n > 1:
        masks["bb_reentry"][1:] = (close[:-1] < lower[:-1]) & (close[1:] >= lower[1:]) & np.isfinite(lower[1:]) & np.isfinite(lower[:-1])
    rsi2_state = (rsi2 < 10.0) & (close > sma200) & np.isfinite(rsi2) & np.isfinite(sma200)
    masks["rsi2_200"] = _edge(rsi2_state)
    masks["vwap20_reclaim"] = cross(close, vwap20)
    masks["prior_day_high"] = _edge((close > prior_high_1) & np.isfinite(prior_high_1))
    masks["prior_week_high"] = _edge((close > prior_high_5) & np.isfinite(prior_high_5))
    masks["swing_break"] = (close > known_h) & (prev_c <= known_h) & np.isfinite(known_h)
    retest = np.zeros(n, dtype=bool)
    for i in range(2, n):
        level = swings["sh"][i - 1]
        if not np.isfinite(level) or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        window = close[max(0, i - 10) : i]
        if not np.any(window > level):
            continue
        if level - 0.5 * atr[i] <= low[i] <= level + 0.5 * atr[i] and close[i] > level:
            retest[i] = True
    masks["swing_retest"] = _edge(retest)
    masks["cup_handle"] = _cup_handle(high, low, close)
    masks["bull_flag"] = _bull_flag(high, low, close)
    masks["asc_triangle"] = _ascending_triangle(high, low, close)
    masks["double_bottom"] = breaks["double_bottom"]
    masks["base_breakout"] = _base_breakout(high, low, close, volume, atr)
    masks["double_top"] = breaks["double_top"]
    masks["head_shoulders"] = breaks["head_shoulders"]
    masks["candle_rev"] = rev
    masks["candle_cont"] = cont
    rel = (close > prior_high_20) & np.isfinite(prior_high_20) & np.isfinite(vol_avg) & (volume >= 1.5 * vol_avg)
    masks["relvol_breakout"] = _edge(rel)
    obv_high = (obv >= obv_prior) & np.isfinite(obv_prior) & (close > prior_high_1) & np.isfinite(prior_high_1)
    masks["obv_break"] = _edge(obv_high)
    vwap_cross = cross(close, vwap20)
    masks["vwap_vol"] = vwap_cross & np.isfinite(vol_avg) & (volume >= 1.2 * vol_avg)
    season_masks, season_exit = _seasonal(dates)
    masks.update(season_masks)
    masks["ema_rsi"] = (ema9 > ema20) & cross_level(rsi14, 40.0) & np.isfinite(ema9) & np.isfinite(ema20)
    masks["sma200_break"] = masks["donchian20"] & (close > sma200) & np.isfinite(sma200)
    masks["sma200_rel_candle"] = (close > sma200) & np.isfinite(sma200) & np.isfinite(vol_avg) & (volume >= 1.5 * vol_avg) & cont
    bb_rsi = (close < lower) & (rsi2 < 10.0) & np.isfinite(lower) & np.isfinite(rsi2)
    masks["bb_rsi2"] = _edge(bb_rsi)
    masks["db_relvol"] = masks["double_bottom"] & np.isfinite(vol_avg) & (volume >= 1.5 * vol_avg)
    masks["cup_sma200"] = masks["cup_handle"] & (close > sma200) & np.isfinite(sma200)
    masks["macd_sma200"] = masks["macd_cross"] & (close > sma200) & np.isfinite(sma200)
    masks["tom_sma200"] = masks["tom"] & (close > sma200) & np.isfinite(sma200)
    season_exit["tom_sma200"] = season_exit["tom"]
    return masks, season_exit


def _bar_clock(index: pd.Index) -> tuple[list[date], np.ndarray]:
    if getattr(index, "tz", None) is not None:
        local = index.tz_convert("America/New_York")
    else:
        local = index
    dates = [pd.Timestamp(ts).date() for ts in local]
    minutes = np.array([int(pd.Timestamp(ts).hour * 60 + pd.Timestamp(ts).minute) for ts in local], dtype=int)
    return dates, minutes


def _session_dollar(dates: list[date], close: np.ndarray, volume: np.ndarray, include_today: bool) -> np.ndarray:
    totals: dict[date, float] = {}
    order: list[date] = []
    for i, day in enumerate(dates):
        if day not in totals:
            totals[day] = 0.0
            order.append(day)
        totals[day] += float(close[i] * volume[i])
    trail: dict[date, float] = {}
    history: list[float] = []
    for day in order:
        if include_today:
            history.append(totals[day])
            trail[day] = float(np.mean(history[-20:])) if len(history) >= 20 else np.nan
        else:
            trail[day] = float(np.mean(history[-20:])) if len(history) >= 20 else np.nan
            history.append(totals[day])
    return np.array([trail[day] for day in dates], dtype=float)


def prepare(frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> Prepared:
    columns = ["open", "high", "low", "close", "volume"]
    use = frame.loc[:, columns].apply(pd.to_numeric, errors="coerce").dropna(subset=["open", "high", "low", "close"])
    use = use[~use.index.duplicated(keep="last")].sort_index()
    use["volume"] = use["volume"].fillna(0.0)
    dates, minutes = _bar_clock(use.index)
    date_last: dict[date, int] = {}
    for i, day in enumerate(dates):
        date_last[day] = i
    close = use["close"].to_numpy(dtype=float)
    volume = use["volume"].to_numpy(dtype=float)
    masks, season_exit = compute_masks(use, dates, minutes, timeframe)
    dollar = _session_dollar(dates, close, volume, include_today=timeframe == "1d")
    return Prepared(
        symbol=symbol,
        timeframe=timeframe,
        dates=dates,
        session_dates=sorted(date_last),
        date_last=date_last,
        open=use["open"].to_numpy(dtype=float),
        high=use["high"].to_numpy(dtype=float),
        low=use["low"].to_numpy(dtype=float),
        close=close,
        volume=volume,
        atr=wilder_atr(use, 14).to_numpy(dtype=float),
        sma20=sma(use["close"].astype(float), 20).to_numpy(dtype=float),
        sma200=sma(use["close"].astype(float), 200).to_numpy(dtype=float),
        dollar_vol=dollar,
        minutes=minutes,
        masks=masks,
        season_exit=season_exit,
    )


def _last_index(prep: Prepared, end: date) -> int:
    lo = 0
    hi = len(prep.dates) - 1
    found = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if prep.dates[mid] <= end:
            found = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return found


def _session_flat(prep: Prepared, fill_i: int, last: int) -> tuple[int, str]:
    day = prep.dates[fill_i]
    last_same = fill_i
    for j in range(fill_i, last + 1):
        if prep.dates[j] != day:
            break
        last_same = j
        if int(prep.minutes[j]) == 15 * 60 + 30:
            return j, "open"
    return last_same, "close"


def walk(prep: Prepared, rule_id: str, params: ExitParams, start: date, end: date, *, allow_holdout: bool = False) -> list[Trade]:
    """Turn a causal mask into raw round trips. Bars after `end` are not read."""
    assert_window_visible(end, allow_holdout=allow_holdout)
    rule = CATALOG_BY_ID[rule_id]
    if rule.short or rule.timeframe != prep.timeframe:
        return []
    mask = prep.masks.get(rule_id)
    if mask is None:
        return []
    last = _last_index(prep, end)
    if last < 1:
        return []
    exits = prep.season_exit.get(rule_id)
    trades: list[Trade] = []
    for signal_i in np.flatnonzero(mask):
        signal_i = int(signal_i)
        if signal_i > last:
            continue
        fill_i = signal_i + 1
        if fill_i > last:
            continue
        fill_date = prep.dates[fill_i]
        if fill_date < start or fill_date > end:
            continue
        atr = float(prep.atr[signal_i])
        fill = float(prep.open[fill_i])
        if not np.isfinite(atr) or atr <= 0 or not np.isfinite(fill) or fill <= 0:
            continue
        if params.stop_from == "low":
            stop = float(prep.low[signal_i]) - params.stop_atr * atr
        else:
            stop = fill - params.stop_atr * atr
        if not np.isfinite(stop) or fill <= stop:
            continue
        risk = fill - stop
        if params.target == "none":
            target = None
        elif params.target == "sma20":
            mid = float(prep.sma20[signal_i])
            target = mid if np.isfinite(mid) and mid > fill else fill + risk
        elif params.target == "r1":
            target = fill + risk
        else:
            target = fill + 2.0 * risk
        flat_i = None
        flat_kind = None
        scheduled = None
        if params.style == "seasonality":
            if exits is None:
                continue
            scheduled = int(exits[signal_i])
            if scheduled < fill_i:
                continue
            scheduled = min(scheduled, last)
        elif params.style == "session":
            flat_i, flat_kind = _session_flat(prep, fill_i, last)
            if flat_kind == "open" and flat_i == fill_i:
                continue
        elif params.time_bars is not None:
            scheduled = min(fill_i + params.time_bars - 1, last)
        exit_i = None
        exit_raw = None
        reason = None
        limit = last
        if params.style == "session" and flat_i is not None:
            limit = min(last, flat_i)
        if scheduled is not None:
            limit = min(limit, scheduled)
        j = fill_i
        while j <= limit:
            bar_open = float(prep.open[j])
            bar_high = float(prep.high[j])
            bar_low = float(prep.low[j])
            bar_close = float(prep.close[j])
            if bar_open <= stop:
                exit_i, exit_raw, reason = j, bar_open, "stop"
                break
            if target is not None and bar_open >= target:
                exit_i, exit_raw, reason = j, bar_open, "target"
                break
            if params.style == "session" and flat_i is not None and j == flat_i and flat_kind == "open":
                exit_i, exit_raw, reason = j, bar_open, "session"
                break
            if bar_low <= stop:
                exit_i, exit_raw, reason = j, stop, "stop"
                break
            if target is not None and bar_high >= target:
                exit_i, exit_raw, reason = j, float(target), "target"
                break
            if params.style == "seasonality" and scheduled is not None and j == scheduled:
                exit_i, exit_raw, reason = j, bar_close, "season" if scheduled == int(exits[signal_i]) else "window"
                break
            if params.style == "session" and flat_i is not None and j == flat_i:
                exit_i, exit_raw, reason = j, bar_close, "session"
                break
            if params.time_bars is not None and j >= fill_i + params.time_bars - 1:
                exit_i, exit_raw, reason = j, bar_close, "time"
                break
            if j == last:
                exit_i, exit_raw, reason = j, bar_close, "window"
                break
            j += 1
        if exit_i is None:
            continue
        sma200 = float(prep.sma200[signal_i])
        priority = float(prep.dollar_vol[signal_i]) if np.isfinite(prep.dollar_vol[signal_i]) else 0.0
        trades.append(
            Trade(
                symbol=prep.symbol,
                signal_i=signal_i,
                fill_i=fill_i,
                exit_i=int(exit_i),
                fill_date=fill_date,
                exit_date=prep.dates[int(exit_i)],
                fill_raw=fill,
                exit_raw=float(exit_raw),
                stop_raw=float(stop),
                priority=priority,
                reason=str(reason),
                above_sma=bool(np.isfinite(sma200) and prep.close[signal_i] > sma200),
            )
        )
    return trades


def _calendar(preps: dict[str, Prepared], start: date, end: date) -> list[date]:
    spy = preps.get("SPY")
    if spy is not None:
        return [day for day in spy.session_dates if start <= day <= end]
    days = {day for prep in preps.values() for day in prep.session_dates if start <= day <= end}
    return sorted(days)


def _pdt(day_trades: list[date], calendar: list[date]) -> dict:
    counts = Counter(day_trades)
    windows = 0
    for index in range(4, len(calendar)):
        if sum(counts[day] for day in calendar[index - 4 : index + 1]) > 3:
            windows += 1
    return {"day_trades": int(sum(counts.values())), "windows_over_3": int(windows)}


def simulate(trades: list[Trade], preps: dict, calendar: list[date], starting: float, daily_cap: int, costs: CostModel | None = None) -> dict:
    """Cash account, whole shares, one open position per symbol, T+1 sale credit."""
    costs = costs or CostModel()
    by_fill: dict[date, list[Trade]] = {}
    for trade in trades:
        by_fill.setdefault(trade.fill_date, []).append(trade)
    settled = float(starting)
    unsettled: list[tuple[date, float]] = []
    positions: dict[str, dict] = {}
    equity_prev = float(starting)
    taken: list[dict] = []
    equities: list[float] = []
    settled_path: list[float] = []
    day_trade_dates: list[date] = []
    last_close: dict[str, float | None] = {}
    for day in calendar:
        carried: list[tuple[date, float]] = []
        for settle_day, amount in unsettled:
            if settle_day <= day:
                settled += amount
            else:
                carried.append((settle_day, amount))
        unsettled = carried
        pool = sorted(by_fill.get(day, []), key=lambda trade: (-trade.priority, trade.symbol))
        chosen: list[Trade] = []
        seen: set[str] = set()
        for trade in pool:
            if trade.symbol in seen:
                continue
            seen.add(trade.symbol)
            chosen.append(trade)
        filled = 0
        for trade in chosen:
            if filled >= daily_cap or trade.symbol in positions or trade.symbol not in preps:
                continue
            raw = float(trade.fill_raw)
            stop = float(trade.stop_raw)
            if raw <= 0 or not math.isfinite(raw) or not math.isfinite(stop) or stop <= 0:
                continue
            paid = buy_price(raw, costs)
            distance = paid - sell_price(stop, costs)
            if distance <= 0 or paid <= 0:
                continue
            qty = int(math.floor((RISK_FRACTION * equity_prev) / distance))
            afford = int(math.floor((settled - buy_fees(costs)) / paid))
            qty = min(qty, afford)
            if qty < 1:
                continue
            debit = paid * qty + buy_fees(costs)
            if debit > settled + 1e-6:
                continue
            settled -= debit
            positions[trade.symbol] = {"trade": trade, "qty": qty, "debit": debit, "paid": paid}
            filled += 1
        for symbol in list(positions):
            pos = positions[symbol]
            trade = pos["trade"]
            if trade.exit_date != day:
                continue
            raw_exit = float(trade.exit_raw)
            if not math.isfinite(raw_exit) or raw_exit <= 0:
                raw_exit = pos["paid"]
            received = sell_price(raw_exit, costs)
            credit = received * pos["qty"] - sell_regulatory_fees(received, pos["qty"], costs)
            pnl = credit - pos["debit"]
            unsettled.append((next_trading_day(day), credit))
            if trade.fill_date == day:
                day_trade_dates.append(day)
            taken.append(
                {
                    "symbol": symbol,
                    "fill_date": trade.fill_date.isoformat(),
                    "exit_date": trade.exit_date.isoformat(),
                    "fill_i": trade.fill_i,
                    "exit_i": trade.exit_i,
                    "fill_raw": trade.fill_raw,
                    "exit_raw": trade.exit_raw,
                    "stop_raw": trade.stop_raw,
                    "qty": pos["qty"],
                    "debit": float(pos["debit"]),
                    "pnl": float(pnl),
                    "reason": trade.reason,
                }
            )
            del positions[symbol]
        market = 0.0
        for symbol, pos in positions.items():
            prep = preps[symbol]
            index = prep.date_last.get(day) if hasattr(prep, "date_last") else None
            if index is None:
                px = last_close.get(symbol)
            else:
                px = float(prep.close[index])
                last_close[symbol] = px
            if px is None:
                px = pos["paid"]
            market += pos["qty"] * px
        equity = settled + sum(amount for _, amount in unsettled) + market
        equities.append(equity)
        settled_path.append(settled)
        equity_prev = equity
    index = pd.to_datetime(calendar) if calendar else pd.DatetimeIndex([])
    equity_series = pd.Series(equities, index=index, dtype=float)
    pnls = [row["pnl"] for row in taken]
    pdt = _pdt(day_trade_dates, calendar)
    by_symbol: dict[str, dict] = {}
    for row in taken:
        bucket = by_symbol.setdefault(row["symbol"], {"trades": 0, "pnl": 0.0})
        bucket["trades"] += 1
        bucket["pnl"] += row["pnl"]
    return {
        "metrics": metrics_from(equity_series, pnls, starting),
        "trades": taken,
        "equity": equity_series,
        "settled": settled_path,
        "day_trades": pdt["day_trades"],
        "pdt_windows": pdt["windows_over_3"],
        "by_symbol": by_symbol,
    }


def _collect(preps: dict[str, Prepared], rule_id: str, params: ExitParams, start: date, end: date, *, allow_holdout: bool, cache: dict | None = None) -> list[Trade]:
    key = (
        rule_id,
        params.stop_atr,
        params.stop_from,
        params.target,
        params.time_bars,
        params.style,
        params.sma_filter,
        params.universe,
        start.toordinal(),
        end.toordinal(),
        allow_holdout,
    )
    if cache is not None and key in cache:
        return cache[key]
    trades: list[Trade] = []
    allowed = set(UNIVERSES[params.universe])
    for symbol, prep in preps.items():
        if symbol not in allowed:
            continue
        trades.extend(walk(prep, rule_id, params, start, end, allow_holdout=allow_holdout))
    if params.sma_filter:
        trades = [trade for trade in trades if trade.above_sma]
    if cache is not None:
        cache[key] = trades
    return trades


def replay(preps: dict[str, Prepared], rule_id: str, tokens: tuple[str, ...], start: date, end: date, starting: float = 1000.0, *, allow_holdout: bool = False) -> dict:
    params = exit_params(CATALOG_BY_ID[rule_id], tokens)
    trades = _collect(preps, rule_id, params, start, end, allow_holdout=allow_holdout)
    return simulate(trades, preps, _calendar(preps, start, end), starting, params.cap)


def buy_and_hold(preps: dict[str, Prepared], symbols: tuple[str, ...], start: date, end: date, starting: float, *, allow_holdout: bool = False) -> dict:
    """Equal cash slices, whole shares, first open to last close. Not a trial."""
    assert_window_visible(end, allow_holdout=allow_holdout)
    costs = CostModel()
    calendar = _calendar(preps, start, end)
    if not calendar or starting <= 0 or not symbols:
        empty = simulate([], preps, calendar, starting, DAILY_CAP, costs)
        return {"metrics": empty["metrics"], "trades": 0, "equity": empty["equity"]}
    plans = []
    for symbol in symbols:
        prep = preps.get(symbol)
        if prep is None:
            continue
        first = next((i for i, day in enumerate(prep.dates) if start <= day <= end), None)
        last = _last_index(prep, end)
        if first is None or last < 0 or last < first:
            continue
        raw = float(prep.open[first])
        raw_exit = float(prep.close[last])
        if raw <= 0 or raw_exit <= 0 or not math.isfinite(raw) or not math.isfinite(raw_exit):
            continue
        plans.append({"symbol": symbol, "entry": prep.dates[first], "exit": prep.dates[last], "open": raw, "close": raw_exit})
    slice_cash = starting / len(symbols)
    settled = float(starting)
    positions: dict[str, dict] = {}
    taken = []
    equities = []
    for day in calendar:
        for plan in plans:
            if plan["entry"] != day or plan["symbol"] in positions:
                continue
            paid = buy_price(plan["open"], costs)
            qty = int(math.floor(min(slice_cash, settled) / paid)) if paid > 0 else 0
            if qty < 1:
                continue
            debit = paid * qty + buy_fees(costs)
            if debit > settled + 1e-6:
                continue
            settled -= debit
            positions[plan["symbol"]] = {"qty": qty, "debit": debit, "exit": plan["exit"], "close": plan["close"]}
        for symbol in list(positions):
            pos = positions[symbol]
            if pos["exit"] != day:
                continue
            received = sell_price(pos["close"], costs)
            credit = received * pos["qty"] - sell_regulatory_fees(received, pos["qty"], costs)
            taken.append({"symbol": symbol, "pnl": credit - pos["debit"], "qty": pos["qty"]})
            settled += credit
            del positions[symbol]
        market = 0.0
        for symbol, pos in positions.items():
            prep = preps[symbol]
            index = prep.date_last.get(day)
            if index is not None:
                market += pos["qty"] * float(prep.close[index])
        equities.append(settled + market)
    series = pd.Series(equities, index=pd.to_datetime(calendar), dtype=float)
    metrics = metrics_from(series, [row["pnl"] for row in taken], starting)
    return {"metrics": metrics, "trades": len(taken), "equity": series}


def _window_passes(metrics: dict, min_trades: int) -> bool:
    trades = int(metrics.get("trades") or 0)
    if trades < min_trades:
        return False
    if float(metrics["ending_equity"]) <= float(metrics["starting_equity"]):
        return False
    if float(metrics["sharpe"]) < GATE_SHARPE:
        return False
    if float(metrics["max_drawdown"]) < GATE_DRAWDOWN:
        return False
    profit_factor = metrics.get("profit_factor")
    if profit_factor is None:
        return float(metrics.get("win_rate") or 0.0) == 1.0
    return float(profit_factor) >= GATE_PF


def trade_p_value(pnls: list[float]) -> float:
    """One-sample normal approximation. Weak samples get p=1 so they cannot be discoveries."""
    values = np.asarray(pnls, dtype=float)
    values = values[np.isfinite(values)]
    count = int(len(values))
    if count < 5:
        return 1.0
    std = float(values.std(ddof=1))
    if std <= 0.0 or not math.isfinite(std):
        return 1.0
    stat = float(values.mean() / (std / math.sqrt(count)))
    if not math.isfinite(stat):
        return 1.0
    return float(0.5 * math.erfc(stat / math.sqrt(2.0)))


def benjamini_hochberg(p_values: list[float]) -> np.ndarray:
    count = len(p_values)
    if count == 0:
        return np.array([])
    order = np.argsort(np.asarray(p_values, dtype=float))
    ranked = np.asarray(p_values, dtype=float)[order]
    adjusted = np.empty(count)
    running = 1.0
    for index in range(count - 1, -1, -1):
        running = min(running, ranked[index] * count / (index + 1))
        adjusted[index] = running
    out = np.empty(count)
    out[order] = np.clip(adjusted, 0.0, 1.0)
    return out


def _daily_returns(equity: pd.Series, starting: float) -> np.ndarray:
    if equity is None or len(equity) == 0:
        return np.array([])
    curve = pd.concat([pd.Series([starting], index=[equity.index[0] - pd.Timedelta(days=1)]), equity.astype(float)])
    returns = curve.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    return returns.to_numpy(dtype=float)


def _eligible(preps: dict[str, Prepared], symbols: tuple[str, ...], start: date, end: date) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for symbol in symbols:
        prep = preps.get(symbol)
        if prep is None:
            continue
        last = _last_index(prep, end)
        for signal_i in range(0, max(last, 0)):
            fill_i = signal_i + 1
            if fill_i > last:
                break
            fill_date = prep.dates[fill_i]
            if fill_date < start:
                continue
            if fill_date > end:
                break
            if not np.isfinite(prep.atr[signal_i]) or prep.atr[signal_i] <= 0:
                continue
            if not np.isfinite(prep.open[fill_i]) or prep.open[fill_i] <= 0:
                continue
            found.append((symbol, signal_i))
    return found


def _random_sharpe(preps: dict[str, Prepared], symbols: tuple[str, ...], taken: list[dict], start: date, end: date, calendar: list[date], cache: dict, daily_cap: int) -> tuple[float, int]:
    count = len(taken)
    if count == 0:
        return 0.0, 0
    holds = [int(row["exit_i"]) - int(row["fill_i"]) + 1 for row in taken]
    hold = max(1, int(np.median(holds)))
    key = (symbols, start, end)
    pool = cache.get(key)
    if pool is None:
        pool = _eligible(preps, symbols, start, end)
        cache[key] = pool
    if not pool:
        return 0.0, 0
    rng = np.random.default_rng(RANDOM_SEED)
    pick = rng.choice(len(pool), size=min(count, len(pool)), replace=False)
    trades: list[Trade] = []
    for choice in np.atleast_1d(pick):
        symbol, signal_i = pool[int(choice)]
        prep = preps[symbol]
        last = _last_index(prep, end)
        fill_i = signal_i + 1
        scheduled = fill_i + hold - 1
        exit_i = min(scheduled, last)
        fill = float(prep.open[fill_i])
        atr = float(prep.atr[signal_i])
        stop = fill - atr
        if fill <= stop or stop <= 0:
            continue
        trades.append(
            Trade(
                symbol=symbol,
                signal_i=signal_i,
                fill_i=fill_i,
                exit_i=exit_i,
                fill_date=prep.dates[fill_i],
                exit_date=prep.dates[exit_i],
                fill_raw=fill,
                exit_raw=float(prep.close[exit_i]),
                stop_raw=float(stop),
                priority=float(prep.dollar_vol[signal_i]) if np.isfinite(prep.dollar_vol[signal_i]) else 0.0,
                reason="time" if exit_i == scheduled else "window",
                above_sma=False,
            )
        )
    book = simulate(trades, preps, calendar, 1000.0, daily_cap)
    return float(book["metrics"]["sharpe"]), int(book["metrics"]["trades"])


def _public_metrics(metrics: dict) -> dict:
    out = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            out[key] = None if not math.isfinite(value) else value
        else:
            out[key] = value
    return out


def _score_spec(preps: dict[str, Prepared], rule: Rule, tokens: tuple[str, ...], round_no: int, parent_id: str, cache: dict, eligible_cache: dict) -> dict:
    params = exit_params(rule, tokens)
    selection_trades = _collect(preps, rule.id, params, SELECT_START, SELECT_END, allow_holdout=False, cache=cache)
    prior_trades = _collect(preps, rule.id, params, PRIOR_START, PRIOR_END, allow_holdout=False, cache=cache)
    selection_calendar = _calendar(preps, SELECT_START, SELECT_END)
    prior_calendar = _calendar(preps, PRIOR_START, PRIOR_END)
    selection = simulate(selection_trades, preps, selection_calendar, 1000.0, params.cap)
    selection_5k = simulate(selection_trades, preps, selection_calendar, 5000.0, params.cap)
    prior = simulate(prior_trades, preps, prior_calendar, 1000.0, params.cap)
    prior_5k = simulate(prior_trades, preps, prior_calendar, 5000.0, params.cap)
    random_sharpe, random_trades = _random_sharpe(
        preps, UNIVERSES[params.universe], selection["trades"], SELECT_START, SELECT_END, selection_calendar, eligible_cache, params.cap
    )
    returns = [row["pnl"] / row["debit"] for row in selection["trades"] if row["debit"] > 0]
    symbols = {
        symbol: {"trades": bucket["trades"], "pnl": bucket["pnl"]}
        for symbol, bucket in sorted(selection["by_symbol"].items())
    }
    return {
        "id": cell_id(rule.id, tokens),
        "rule_id": rule.id,
        "tokens": list(tokens),
        "variant": variant_name(tokens),
        "round": round_no,
        "parent_id": parent_id,
        "family": rule.family,
        "timeframe": rule.timeframe,
        "plain": plain_text(rule, tokens),
        "prior_years_complete": rule.prior_years_complete,
        "behavior": list(behavior_key(rule, tokens)),
        "selection": _public_metrics(selection["metrics"]),
        "selection_5k": _public_metrics(selection_5k["metrics"]),
        "prior": _public_metrics(prior["metrics"]),
        "prior_5k": _public_metrics(prior_5k["metrics"]),
        "selection_pass": _window_passes(selection["metrics"], SELECT_MIN_TRADES),
        "prior_pass": _window_passes(prior["metrics"], PRIOR_MIN_TRADES) and rule.prior_years_complete,
        "random_sharpe": random_sharpe,
        "random_trades": random_trades,
        "p": trade_p_value(returns),
        "q": None,
        "dsr": None,
        "survivor": False,
        "day_trades_1k": selection["day_trades"],
        "pdt_windows_1k": selection["pdt_windows"],
        "day_trades_5k": selection_5k["day_trades"],
        "pdt_windows_5k": selection_5k["pdt_windows"],
        "by_symbol": symbols,
        "selection_equity": selection["equity"],
        "prior_equity": prior["equity"],
        "selection_trades": selection["trades"],
        "prior_trades": prior["trades"],
    }


def pick_near_misses(cells: list[dict]) -> list[dict]:
    """Round-1 daily cells that almost cleared, ranked by prior-year Sharpe."""
    found = []
    for cell in cells:
        if cell["round"] != 1 or cell["timeframe"] != "1d":
            continue
        metrics = cell["selection"]
        if int(metrics["trades"]) < NEAR_MIN_TRADES:
            continue
        if float(metrics["sharpe"]) < NEAR_SHARPE:
            continue
        if float(metrics["max_drawdown"]) < NEAR_DRAWDOWN:
            continue
        profit_factor = metrics.get("profit_factor")
        if profit_factor is not None and float(profit_factor) < NEAR_PF:
            continue
        if cell["selection_pass"] and cell["prior_pass"]:
            continue
        found.append(cell)
    found.sort(key=lambda cell: (-float(cell["prior"]["sharpe"]), cell["id"]))
    return found[:MAX_NEAR]


def round2_tokens(rule: Rule) -> list[tuple[str, ...]]:
    second = ("half_stop",) if rule.requires_sma200 else ("sma200",)
    return [("exit",), second, ("spy",), ("mag7",), ("liquid6",), ("cap5",)]


def plan_round3(cells: list[dict]) -> list[tuple[str, tuple[str, ...]]]:
    """Stack the modal improving variant with the exit variant. Duplicates are not new trials."""
    parents = {cell["id"]: cell for cell in cells if cell["round"] == 1}
    improving = []
    for cell in cells:
        if cell["round"] != 2:
            continue
        parent = parents.get(cell["parent_id"])
        if parent is None:
            continue
        profit_factor = cell["selection"].get("profit_factor")
        profit_ok = profit_factor is None or float(profit_factor) >= 1.0
        if profit_ok and float(cell["prior"]["sharpe"]) > float(parent["prior"]["sharpe"]):
            improving.append(cell)
    if not improving:
        return []
    counts = Counter(cell["variant"] for cell in improving)
    modal = sorted(counts, key=lambda name: (-counts[name], name))[0]
    if modal == "exit":
        return []
    best: dict[str, float] = {}
    for cell in improving:
        best[cell["parent_id"]] = max(best.get(cell["parent_id"], -1e9), float(cell["prior"]["sharpe"]))
    existing = {tuple(cell["behavior"]) for cell in cells}
    planned: list[tuple[str, tuple[str, ...]]] = []
    for parent_id in sorted(best, key=lambda key: (-best[key], key)):
        rule = CATALOG_BY_ID[parent_id]
        tokens = tuple(sorted({"exit", modal}))
        key = behavior_key(rule, tokens)
        if key in existing:
            continue
        planned.append((parent_id, tokens))
        existing.add(key)
        if len(planned) >= MAX_NEAR:
            break
    return planned


def _mark_inference(cells: list[dict]) -> None:
    p_values = [float(cell["p"]) for cell in cells]
    adjusted = benjamini_hochberg(p_values)
    trials = len(cells)
    for cell, q_value in zip(cells, adjusted):
        cell["q"] = float(q_value)
        dsr = deflated_sharpe(_daily_returns(cell["selection_equity"], 1000.0), trials)
        cell["dsr"] = dsr.get("dsr")
        cell["dsr_detail"] = {key: value for key, value in dsr.items() if key != "dsr"}
        beats = float(cell["selection"]["sharpe"]) > float(cell["random_sharpe"])
        cell["survivor"] = bool(
            cell["selection_pass"]
            and cell["prior_pass"]
            and cell["prior_years_complete"]
            and cell["q"] <= FDR_Q
            and cell["dsr"] is not None
            and float(cell["dsr"]) >= DSR_MIN
            and beats
        )


def run_search(daily: dict[str, Prepared], hourly: dict[str, Prepared] | None = None) -> dict:
    """Score the frozen rounds on the selection slice and on prior years.

    The final three-month slice is not read here.
    """
    hourly = hourly or {}
    cache: dict = {}
    eligible_cache: dict = {}
    cells: list[dict] = []
    for rule in CATALOG:
        preps = hourly if rule.timeframe == "60m" else daily
        print(f"round 1 {rule.id}", flush=True)
        cells.append(_score_spec(preps, rule, (), 1, rule.id, cache, eligible_cache))
    near = pick_near_misses(cells)
    print(f"near misses {len(near)}", flush=True)
    for parent in near:
        rule = CATALOG_BY_ID[parent["rule_id"]]
        for tokens in round2_tokens(rule):
            print(f"round 2 {cell_id(rule.id, tokens)}", flush=True)
            cells.append(_score_spec(daily, rule, tokens, 2, parent["id"], cache, eligible_cache))
    planned = plan_round3(cells)
    print(f"round 3 {len(planned)}", flush=True)
    for parent_id, tokens in planned:
        rule = CATALOG_BY_ID[parent_id]
        print(f"round 3 {cell_id(rule.id, tokens)}", flush=True)
        cells.append(_score_spec(daily, rule, tokens, 3, parent_id, cache, eligible_cache))
    _mark_inference(cells)
    benches = {
        "selection_spy_1k": _public_metrics(buy_and_hold(daily, ("SPY",), SELECT_START, SELECT_END, 1000.0)["metrics"]),
        "selection_spy_5k": _public_metrics(buy_and_hold(daily, ("SPY",), SELECT_START, SELECT_END, 5000.0)["metrics"]),
        "selection_basket_1k": _public_metrics(buy_and_hold(daily, UNIVERSE, SELECT_START, SELECT_END, 1000.0)["metrics"]),
        "selection_basket_5k": _public_metrics(buy_and_hold(daily, UNIVERSE, SELECT_START, SELECT_END, 5000.0)["metrics"]),
        "prior_spy_1k": _public_metrics(buy_and_hold(daily, ("SPY",), PRIOR_START, PRIOR_END, 1000.0)["metrics"]),
        "prior_spy_5k": _public_metrics(buy_and_hold(daily, ("SPY",), PRIOR_START, PRIOR_END, 5000.0)["metrics"]),
        "prior_basket_1k": _public_metrics(buy_and_hold(daily, UNIVERSE, PRIOR_START, PRIOR_END, 1000.0)["metrics"]),
        "prior_basket_5k": _public_metrics(buy_and_hold(daily, UNIVERSE, PRIOR_START, PRIOR_END, 5000.0)["metrics"]),
    }
    return {
        "n_combos": len(cells),
        "rounds": {str(number): sum(1 for cell in cells if cell["round"] == number) for number in (1, 2, 3)},
        "near_miss_ids": [cell["id"] for cell in near],
        "survivor_ids": [cell["id"] for cell in cells if cell["survivor"]],
        "cells": cells,
        "benchmarks": benches,
        "holdout_scored": False,
    }


def score_holdout(daily: dict[str, Prepared], hourly: dict[str, Prepared], search: dict) -> dict:
    """One look at the final slice. Does not choose which rule was refined."""
    survivors = [cell for cell in search["cells"] if cell["survivor"]]
    labeled = False
    if survivors:
        chosen = survivors
    else:
        labeled = True
        pool = [cell for cell in search["cells"] if cell["timeframe"] == "1d"]
        pool.sort(key=lambda cell: (-float(cell["prior"]["sharpe"]), cell["id"]))
        chosen = pool[:1]
    rows = []
    for cell in chosen:
        preps = hourly if cell["timeframe"] == "60m" else daily
        tokens = tuple(cell["tokens"])
        book = replay(preps, cell["rule_id"], tokens, HOLDOUT_START, HOLDOUT_END, 1000.0, allow_holdout=True)
        book_5k = replay(preps, cell["rule_id"], tokens, HOLDOUT_START, HOLDOUT_END, 5000.0, allow_holdout=True)
        rows.append(
            {
                "id": cell["id"],
                "labeled_non_survivor": labeled,
                "metrics_1k": _public_metrics(book["metrics"]),
                "metrics_5k": _public_metrics(book_5k["metrics"]),
                "by_symbol": book["by_symbol"],
                "day_trades": book["day_trades"],
                "pdt_windows": book["pdt_windows"],
                "equity": book["equity"],
                "trades": book["trades"],
            }
        )
    benches = {
        "spy_1k": _public_metrics(buy_and_hold(daily, ("SPY",), HOLDOUT_START, HOLDOUT_END, 1000.0, allow_holdout=True)["metrics"]),
        "spy_5k": _public_metrics(buy_and_hold(daily, ("SPY",), HOLDOUT_START, HOLDOUT_END, 5000.0, allow_holdout=True)["metrics"]),
        "basket_1k": _public_metrics(buy_and_hold(daily, UNIVERSE, HOLDOUT_START, HOLDOUT_END, 1000.0, allow_holdout=True)["metrics"]),
        "basket_5k": _public_metrics(buy_and_hold(daily, UNIVERSE, HOLDOUT_START, HOLDOUT_END, 5000.0, allow_holdout=True)["metrics"]),
    }
    return {"scored_once": True, "labeled_non_survivor": labeled, "rows": rows, "benchmarks": benches}


def score_years(preps: dict[str, Prepared], rule_id: str, tokens: tuple[str, ...]) -> list[dict]:
    """Stability of one frozen rule. Not a new trial and not a refit."""
    rows = []
    for year in range(2018, 2025):
        book = replay(preps, rule_id, tokens, date(year, 1, 1), date(year, 12, 31), 1000.0, allow_holdout=False)
        rows.append({"year": year, "metrics": _public_metrics(book["metrics"])})
    return rows


def _vix_on(vix: dict[date, float], day: date) -> float | None:
    if day in vix and vix[day] > 0:
        return vix[day]
    earlier = [key for key in vix if key <= day and vix[key] > 0]
    if not earlier:
        return None
    return vix[max(earlier)]


def _close_on(prep: Prepared, day: date) -> float | None:
    if day in prep.date_last:
        return float(prep.close[prep.date_last[day]])
    earlier = [key for key in prep.session_dates if key <= day]
    if not earlier:
        return None
    return float(prep.close[prep.date_last[max(earlier)]])


def _option_exit_spot(prep: Prepared, trade: dict, expiry: date) -> tuple[date, float] | None:
    share_exit = date.fromisoformat(trade["exit_date"])
    exit_day = share_exit if share_exit <= expiry else expiry
    while not is_trading_day(exit_day):
        exit_day -= timedelta(days=1)
    if exit_day <= share_exit and exit_day == share_exit:
        return exit_day, float(trade["exit_raw"])
    spot = _close_on(prep, exit_day)
    if spot is None or spot <= 0:
        return None
    return exit_day, spot


def _spread(mid: float) -> float:
    return max(0.01, 0.015 * mid)


def option_report(trades: list[dict], preps: dict[str, Prepared], vix: dict[date, float], starting: float) -> dict:
    """Price ATM calls and debit call verticals. Not an extra trial and not a promotion."""
    books = {
        "call_0": _option_book(trades, preps, vix, starting, 0, vertical=False),
        "call_7": _option_book(trades, preps, vix, starting, 7, vertical=False),
        "call_14": _option_book(trades, preps, vix, starting, 14, vertical=False),
        "vertical_7": _option_book(trades, preps, vix, starting, 7, vertical=True),
        "vertical_14": _option_book(trades, preps, vix, starting, 14, vertical=True),
    }
    return books


def _option_book(trades: list[dict], preps: dict[str, Prepared], vix: dict[date, float], starting: float, dte: int, vertical: bool) -> dict:
    relevant = []
    for trade in trades:
        same_day = trade["fill_date"] == trade["exit_date"]
        if dte == 0 and same_day:
            relevant.append(trade)
        elif dte > 0 and not same_day:
            relevant.append(trade)
    if dte == 0 and not relevant:
        return {"applicable": False, "trades": 0, "pnl": 0.0, "skipped": 0, "note": "No same-session share exit, so 0 DTE is not priced."}
    settled = float(starting)
    pnl = 0.0
    taken = 0
    skipped = 0
    busy: dict[str, date] = {}
    for trade in sorted(relevant, key=lambda row: (row["fill_date"], row["symbol"])):
        fill_day = date.fromisoformat(trade["fill_date"])
        symbol = trade["symbol"]
        if symbol in busy and busy[symbol] >= fill_day:
            skipped += 1
            continue
        prep = preps.get(symbol)
        sigma_points = _vix_on(vix, date.fromisoformat(trade["fill_date"]) - timedelta(days=1))
        # VIX known at the prior close. The signal day's close is not required.
        if prep is None or sigma_points is None:
            skipped += 1
            continue
        sigma = sigma_points / 100.0
        spot = float(trade["fill_raw"])
        if spot <= 0 or sigma <= 0:
            skipped += 1
            continue
        expiry = fill_day if dte == 0 else fill_day + timedelta(days=dte)
        located = _option_exit_spot(prep, trade, expiry)
        if located is None:
            skipped += 1
            continue
        exit_day, spot_out = located
        t_in = max(dte, 1) / 365.0 if dte > 0 else 1.0 / 365.0
        t_out = max((expiry - exit_day).days, 0) / 365.0
        atm = listed_strike(spot, spot)
        if vertical:
            step = 1.0 if spot >= 25.0 else 0.5
            short_strike = listed_strike(spot, max(atm + step, spot * 1.02))
            if short_strike <= atm:
                short_strike = listed_strike(spot, atm + step)
            long_in = option_price("call", spot, atm, t_in, sigma, OPTION_RATE, OPTION_DIVIDEND)
            short_in = option_price("call", spot, short_strike, t_in, sigma, OPTION_RATE, OPTION_DIVIDEND)
            debit = (long_in + _spread(long_in) - max(0.0, short_in - _spread(short_in))) * 100.0
            long_out = option_price("call", spot_out, atm, t_out, sigma, OPTION_RATE, OPTION_DIVIDEND)
            short_out = option_price("call", spot_out, short_strike, t_out, sigma, OPTION_RATE, OPTION_DIVIDEND)
            credit = max(0.0, (max(0.0, long_out - _spread(long_out)) - (short_out + _spread(short_out))) * 100.0)
        else:
            mid_in = option_price("call", spot, atm, t_in, sigma, OPTION_RATE, OPTION_DIVIDEND)
            debit = (mid_in + _spread(mid_in)) * 100.0
            mid_out = option_price("call", spot_out, atm, t_out, sigma, OPTION_RATE, OPTION_DIVIDEND)
            credit = max(0.0, mid_out - _spread(mid_out)) * 100.0
        if debit <= 0 or not math.isfinite(debit) or not math.isfinite(credit):
            skipped += 1
            continue
        # One contract. Buying every contract the cash can hold spends the account on the first signal.
        if debit > settled:
            skipped += 1
            continue
        qty = 1
        settled -= debit * qty
        settled += credit * qty
        pnl += (credit - debit) * qty
        taken += 1
        busy[symbol] = exit_day
    return {"applicable": True, "trades": taken, "pnl": pnl, "ending": settled, "skipped": skipped, "dte": dte, "vertical": vertical}
