"""Score the second small-account search. Does not place an order.

Run: python3 -m webull_bot.research_account_hunt
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from webull_bot.account_hunt import (
    BAND,
    LEV_VOL_TARGET,
    MEAN_REVERSION_SYMBOLS,
    MOM_LOOKBACK,
    MOM_TOP,
    PRIOR_HOLDOUT,
    RANDOM_SEED,
    SECTOR_SYMBOLS,
    SECTOR_TOP,
    SMA_TREND,
    VOL_TARGET,
    assign_tiers,
    calendar_blend_weights,
    calendar_weights,
    change_rows,
    frozen_rules,
    hysteresis,
    mean_reversion_weights,
    qqq_overlay_weights,
    scaled_weight,
    sector_weights,
    simulate_covered_call,
    simulate_wheel,
    stock_momentum_weights,
    trend_weight,
    weekly_rows,
)
from webull_bot.account_winners import (
    DUAL_LOOKBACK,
    DUAL_SKIP,
    DUAL_SYMBOLS,
    GTAA_SYMBOLS,
    HIGH_SYMBOL,
    HOLDOUT_START,
    HURDLE_SYMBOL,
    SAMPLE_END,
    SAMPLE_START,
    SMA_MONTHS,
    buy_and_hold,
    calendar_year_return,
    performance,
    prepare,
    shuffle_weights,
    simulate_weights,
    verdict,
    weights_from_monthly_dual,
    weights_from_monthly_gtaa,
    weights_from_monthly_trend,
    window_stats,
)
from webull_bot.costs import CostModel
from webull_bot.data.base import normalize_frame
from webull_bot.indicators import sma
from webull_bot.options.pricing import realized_vol
from webull_bot.universe_dow import all_dow_tickers, members_on

REPORT = Path("reports")
CACHE = Path("data/cache/account_hunt")
START_MARK = "<!-- ACCOUNT_HUNT_START -->"
END_MARK = "<!-- ACCOUNT_HUNT_END -->"
STAKE = 1000.0
TRAIN_END = pd.Timestamp("2016-12-31")
LATE = {"TQQQ", "UPRO", "QQQM", "SPLG", "GLD", "BIL", "V", "CRM", "DOW", "AMGN", "HON", "NVDA", "SHW", "GOOGL"}


def _load_symbol(symbol: str) -> pd.DataFrame | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{symbol.replace('^', '_')}_1d.csv"
    if path.exists():
        frame = normalize_frame(pd.read_csv(path, index_col=0, parse_dates=True), "1d")
        if not frame.empty and frame.index.max() >= SAMPLE_END - pd.Timedelta(days=10):
            return frame
    import yfinance as yf

    raw = yf.download(
        symbol,
        start="2003-01-01",
        end="2026-10-07",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if raw is None or len(raw) == 0:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    frame = normalize_frame(raw, "1d")
    if frame.empty:
        return None
    frame.to_csv(path)
    return frame


def _clock_frames(bars: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    clock = bars["SPY"].index
    clock = clock[(clock >= pd.Timestamp("2003-01-01")) & (clock <= SAMPLE_END)]
    out = {}
    for symbol, frame in bars.items():
        aligned = frame.reindex(clock)
        out[symbol] = aligned
    return out


def _later(left: pd.Timestamp | None, right: pd.Timestamp | None) -> pd.Timestamp | None:
    if left is None or right is None:
        return None
    return max(left, right)


def _ready_row(mask: pd.Series) -> pd.Timestamp | None:
    if mask.empty or not bool(mask.any()):
        return None
    return pd.Timestamp(mask[mask].index[0])


def _trim(weights: pd.DataFrame, ready: pd.Timestamp | None) -> pd.DataFrame:
    if weights.empty or ready is None:
        return weights.iloc[0:0]
    trimmed = weights.loc[weights.index >= ready]
    return change_rows(trimmed)


def _build(frames: dict[str, pd.DataFrame], monthly: pd.DataFrame) -> dict[str, dict[str, Any]]:
    books: dict[str, dict[str, Any]] = {}
    have = [symbol for symbol in MEAN_REVERSION_SYMBOLS if symbol in frames]
    close = pd.DataFrame({symbol: frames[symbol]["close"] for symbol in have})
    ready_mr = _ready_row(sma(close, SMA_TREND).notna().any(axis=1))

    def add(name: str, family: str, weights: pd.DataFrame, *, eligible: bool = True) -> None:
        books[name] = {"name": name, "family": family, "signals": _trim(weights, ready_mr) if family == "mean_reversion" else weights, "eligible": eligible}

    if have:
        add("rsi2_equal", "mean_reversion", mean_reversion_weights(frames, "rsi2", symbols=tuple(have)))
        add("ibs_equal", "mean_reversion", mean_reversion_weights(frames, "ibs", symbols=tuple(have)))
        add("three_down", "mean_reversion", mean_reversion_weights(frames, "three_down", symbols=tuple(have)))
        add("rsi2_qqq_overlay", "mean_reversion", qqq_overlay_weights(frames, symbols=tuple(have)))
        add(
            "rsi2_entry5",
            "neighbor",
            mean_reversion_weights(frames, "rsi2", symbols=tuple(have), rsi_entry=5),
            eligible=False,
        )
    qqq = frames["QQQ"]["close"]
    spy = frames["SPY"]["close"]
    qqq_avg = sma(qqq, SMA_TREND)
    spy_avg = sma(spy, SMA_TREND)
    qqq_on = hysteresis(qqq, qqq_avg, 0.0)
    qqq_ready = _ready_row(qqq_avg.notna())
    spy_ready = _ready_row(spy_avg.notna())

    def add_trend(name: str, weights: pd.DataFrame, ready: pd.Timestamp | None, family: str, eligible: bool) -> None:
        books[name] = {
            "name": name,
            "family": family,
            "signals": _trim(weights, ready),
            "eligible": eligible,
        }

    if "TQQQ" in frames:
        traded = frames["TQQQ"]["close"]
        tqqq_ready = _later(qqq_ready, _ready_row(traded.notna()))
        add_trend("tqqq_sma200", trend_weight(traded, qqq, band=0.0, name="TQQQ"), tqqq_ready, "levered", True)
        add_trend("tqqq_band3", trend_weight(traded, qqq, band=BAND, name="TQQQ"), tqqq_ready, "levered", True)
        add_trend("tqqq_band2", trend_weight(traded, qqq, band=0.02, name="TQQQ"), tqqq_ready, "neighbor", False)
        vol = realized_vol(qqq, 20)
        add_trend("tqqq_vol20", scaled_weight(qqq_on, vol, LEV_VOL_TARGET, "TQQQ"), tqqq_ready, "levered", True)
        half = qqq_on.astype(float).mul(0.5).rename("TQQQ").to_frame()
        tradable = traded.notna()
        half["TQQQ"] = half["TQQQ"].where(tradable, 0.0)
        add_trend("tqqq_half", half, tqqq_ready, "levered", True)
        blend = pd.DataFrame(0.0, index=qqq.index, columns=["QQQ", "TQQQ"])
        blend.loc[qqq_on & tradable, "QQQ"] = 0.5
        blend.loc[qqq_on & tradable, "TQQQ"] = 0.5
        add_trend("qqq_tqqq_blend", blend, tqqq_ready, "levered", True)
    if "UPRO" in frames:
        upro_ready = _later(spy_ready, _ready_row(frames["UPRO"]["close"].notna()))
        add_trend(
            "upro_sma200",
            trend_weight(frames["UPRO"]["close"], spy, band=0.0, name="UPRO"),
            upro_ready,
            "levered",
            True,
        )
    spy_vol = scaled_weight(pd.Series(True, index=spy.index), realized_vol(spy, 20), VOL_TARGET, "SPY")
    qqq_vol = scaled_weight(pd.Series(True, index=qqq.index), realized_vol(qqq, 20), VOL_TARGET, "QQQ")
    spy_vol_trend = scaled_weight(hysteresis(spy, spy_avg, 0.0), realized_vol(spy, 20), VOL_TARGET, "SPY")
    qqq_vol_trend = scaled_weight(qqq_on, realized_vol(qqq, 20), VOL_TARGET, "QQQ")
    vol_ready_spy = _ready_row(realized_vol(spy, 20).notna())
    vol_ready_qqq = _ready_row(realized_vol(qqq, 20).notna())
    add_trend("spy_vol15_weekly", weekly_rows(spy_vol), vol_ready_spy, "vol", True)
    add_trend("qqq_vol15_weekly", weekly_rows(qqq_vol), vol_ready_qqq, "vol", True)
    add_trend("spy_vol15_weekly_sma", weekly_rows(spy_vol_trend), vol_ready_spy, "vol", True)
    add_trend("qqq_vol15_weekly_sma", weekly_rows(qqq_vol_trend), vol_ready_qqq, "vol", True)
    add_trend("spy_vol15_daily", spy_vol, vol_ready_spy, "neighbor", False)
    add_trend("qqq_vol15_daily", qqq_vol, vol_ready_qqq, "neighbor", False)

    sectors = [symbol for symbol in SECTOR_SYMBOLS if symbol in monthly.columns]
    if len(sectors) >= 3:
        sector_monthly = monthly[sectors]
        ready_sector = _ready_row((sector_monthly / sector_monthly.shift(12) - 1.0).notna().any(axis=1))
        add_trend("sector_top3_12m", sector_weights(sector_monthly, lookback=12, top_n=3), ready_sector, "sector", True)
        add_trend(
            "sector_top2_12m",
            sector_weights(sector_monthly, lookback=12, top_n=2),
            ready_sector,
            "neighbor",
            False,
        )
        add_trend("sector_top3_6m", sector_weights(sector_monthly, lookback=6, top_n=3), _ready_row((sector_monthly / sector_monthly.shift(6) - 1.0).notna().any(axis=1)), "neighbor", False)
        add_trend("sector_top3_3m", sector_weights(sector_monthly, lookback=3, top_n=3), _ready_row((sector_monthly / sector_monthly.shift(3) - 1.0).notna().any(axis=1)), "neighbor", False)

    dow = [symbol for symbol in all_dow_tickers() if symbol in monthly.columns]
    if dow and "SPY" in frames:
        gate = (spy > spy_avg).reindex(monthly.index).fillna(False)
        panel = monthly[dow]
        ready_mom = _ready_row((panel.shift(1) / panel.shift(12) - 1.0).notna().any(axis=1))
        add_trend(
            "dow_mom_top5",
            stock_momentum_weights(panel, gate, point_in_time=True, top_n=MOM_TOP),
            ready_mom,
            "momentum",
            True,
        )
        add_trend(
            "dow_mom_top10",
            stock_momentum_weights(panel, gate, point_in_time=True, top_n=10),
            ready_mom,
            "neighbor",
            False,
        )
        add_trend(
            "dow_mom_survivors",
            stock_momentum_weights(
                panel,
                gate,
                point_in_time=False,
                top_n=MOM_TOP,
                survivor_asof=date(2026, 10, 6),
            ),
            ready_mom,
            "diagnostic",
            False,
        )

    clock = frames["SPY"].index
    for symbol, prefix in (("SPY", "spy"), ("QQQ", "qqq")):
        add_trend(f"{prefix}_tom", calendar_weights(clock, symbol, "tom"), clock.min(), "calendar", True)
        add_trend(f"{prefix}_pre_holiday", calendar_weights(clock, symbol, "pre_holiday"), clock.min(), "calendar", True)
        add_trend(f"{prefix}_calendar_both", calendar_weights(clock, symbol, "both"), clock.min(), "calendar", True)
        add_trend(f"{prefix}_calendar_blend", calendar_blend_weights(clock, symbol), clock.min(), "calendar", True)
    return books


def _run(prepared, signals: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, stake: float) -> dict[str, Any]:
    book = simulate_weights(
        prepared.clock,
        prepared.opens,
        prepared.closes,
        signals,
        starting_equity=stake,
        trade_start=start,
        trade_end=end,
        costs=CostModel(),
    )
    stats = performance(book.equity, stake)
    spy_equity = buy_and_hold(
        prepared.opens["SPY"],
        prepared.closes["SPY"],
        starting_equity=stake,
        trade_start=book.equity.index[0] if len(book.equity) else start,
        trade_end=end,
    )
    qqq_equity = buy_and_hold(
        prepared.opens["QQQ"],
        prepared.closes["QQQ"],
        starting_equity=stake,
        trade_start=book.equity.index[0] if len(book.equity) else start,
        trade_end=end,
    )
    stats["entries"] = book.entries
    stats["exits"] = book.exits
    stats["rebalances"] = book.rebalances
    stats["turnover"] = book.turnover
    stats["exposure"] = book.exposure
    stats["entries_per_year"] = book.entries / stats["years"] if stats["years"] else 0.0
    return {
        "book": stats,
        "spy": performance(spy_equity, stake),
        "qqq": performance(qqq_equity, stake),
        "equity": book.equity,
    }


def _span_start(clock: pd.DatetimeIndex, signals: pd.DataFrame, floor: pd.Timestamp) -> pd.Timestamp:
    for ts in signals.index:
        pos = int(clock.searchsorted(pd.Timestamp(ts), side="right"))
        if pos >= len(clock):
            continue
        fill = pd.Timestamp(clock[pos])
        if fill >= floor:
            return fill
    return pd.Timestamp(floor)


def _pack(prepared, spec: dict[str, Any], stake: float = STAKE) -> dict[str, Any]:
    signals = spec["signals"]
    if signals.empty:
        return {"name": spec["name"], "eligible": False, "empty": True}
    full_start = _span_start(prepared.clock, signals, SAMPLE_START)
    full = _run(prepared, signals, full_start, SAMPLE_END, stake)
    train = _run(prepared, signals, full_start, TRAIN_END, stake)
    hold = _run(prepared, signals, HOLDOUT_START, SAMPLE_END, stake)
    decision = verdict(hold["book"], hold["spy"], train["book"])
    windows = {}
    for months in (6, 12):
        windows[str(months)] = {
            "1000": window_stats(full["equity"], prepared.closes["SPY"], months, 1000.0),
            "5000": window_stats(full["equity"], prepared.closes["SPY"], months, 5000.0),
            "qqq_1000": window_stats(full["equity"], prepared.closes["QQQ"], months, 1000.0),
            "qqq_5000": window_stats(full["equity"], prepared.closes["QQQ"], months, 5000.0),
        }
    return {
        "name": spec["name"],
        "family": spec["family"],
        "eligible": spec["eligible"] and not signals.empty,
        "empty": False,
        "full": full["book"],
        "train": train["book"],
        "holdout": hold["book"],
        "spy_holdout": hold["spy"],
        "qqq_holdout": hold["qqq"],
        "spy_full": full["spy"],
        "qqq_full": full["qqq"],
        "verdict": decision,
        "beats_qqq_raw": float(hold["book"]["cagr"]) > float(hold["qqq"]["cagr"]),
        "windows": windows,
        "equity": full["equity"],
        "hold_equity": hold["equity"],
        "signals": signals,
    }


def _pack_option(name: str, result: dict[str, Any], spy_open, spy_close, qqq_open, qqq_close, stake: float) -> dict[str, Any]:
    equity = result["equity"]
    if result.get("unfit") or equity is None or len(equity) < 30:
        return {"name": name, "eligible": False, "empty": True, "unfit": bool(result.get("unfit")), "reason": result.get("reason")}
    full = performance(equity, stake)
    train_eq = equity.loc[equity.index <= TRAIN_END]
    hold_eq = equity.loc[equity.index >= HOLDOUT_START]
    # Fresh-start holdout is a second run. The caller passes that equity in result["hold"].
    train = performance(train_eq, float(train_eq.iloc[0]) if len(train_eq) else stake)
    hold_equity = result.get("hold_equity", hold_eq)
    hold = performance(hold_equity, stake)
    spy_hold = performance(
        buy_and_hold(spy_open, spy_close, starting_equity=stake, trade_start=HOLDOUT_START, trade_end=SAMPLE_END),
        stake,
    )
    qqq_hold = performance(
        buy_and_hold(qqq_open, qqq_close, starting_equity=stake, trade_start=HOLDOUT_START, trade_end=SAMPLE_END),
        stake,
    )
    decision = verdict(hold, spy_hold, train if len(train_eq) else {"years": 0, "cagr": 0})
    windows = {}
    for months in (6, 12):
        windows[str(months)] = {
            "1000": window_stats(equity, spy_close, months, 1000.0),
            "5000": window_stats(equity, spy_close, months, 5000.0),
            "qqq_1000": window_stats(equity, qqq_close, months, 1000.0),
            "qqq_5000": window_stats(equity, qqq_close, months, 5000.0),
        }
    return {
        "name": name,
        "family": "income",
        "eligible": True,
        "empty": False,
        "full": full,
        "train": train,
        "holdout": hold,
        "spy_holdout": spy_hold,
        "qqq_holdout": qqq_hold,
        "verdict": decision,
        "beats_qqq_raw": float(hold["cagr"]) > float(qqq_hold["cagr"]),
        "windows": windows,
        "equity": equity,
        "hold_equity": hold_equity,
        "opens": result["opens"],
        "assignments": result.get("assignments", 0),
        "called": result.get("called", 0),
        "skips": result.get("skips", 0),
        "stake": stake,
    }


def _earnings_note() -> str:
    try:
        import yfinance as yf

        dates = yf.Ticker("AAPL").get_earnings_dates(limit=48)
    except Exception as exc:
        return f"Post-earnings drift was skipped. Yahoo earnings dates were not usable ({type(exc).__name__})."
    if dates is None or len(dates) == 0:
        return "Post-earnings drift was skipped. Yahoo returned no earnings dates."
    index = pd.to_datetime(dates.index)
    if getattr(index, "tz", None) is not None:
        index = index.tz_convert("America/New_York").tz_localize(None)
    earliest = pd.Timestamp(index.min())
    if earliest > pd.Timestamp("2012-01-01"):
        return (
            f"Post-earnings drift was skipped. The free Yahoo earnings calendar for AAPL starts {earliest.date()}, "
            "which does not cover a training window back through 2008. A short recent list would be a different study."
        )
    return (
        f"Yahoo returned AAPL earnings dates back to {earliest.date()}, but the feed is not a point-in-time "
        "announcement file (revisions and missing names are not documented). Post-earnings drift was not scored."
    )


def _window_line(stats: dict[str, Any], other: str, stake: int) -> str:
    if not stats or not stats.get("windows"):
        return "n/a"
    return (
        f"{stats['windows']} windows. Median ending {_money(stats.get('ending_median'))} ({other} {_money(stats.get('spy_ending_median'))}), "
        f"bad case {_money(stats.get('ending_p10'))} ({other} {_money(stats.get('spy_ending_p10'))}), "
        f"good case {_money(stats.get('ending_p90'))} ({other} {_money(stats.get('spy_ending_p90'))}). "
        f"{_pct(stats.get('pct_negative'))} lost money, against {_pct(stats.get('spy_pct_negative'))} for {other}."
    )


def _num(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.2f}"


def _pct(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{value:.1%}"


def _money(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"${value:,.0f}"


def _row(book: dict[str, Any]) -> str:
    hold = book["holdout"]
    spy = book.get("spy_holdout") or {}
    qqq = book.get("qqq_holdout") or {}
    label = book["name"]
    if float(book.get("stake") or STAKE) >= 5000:
        label = f"{label} ($5,000)"
    return (
        f"| {label} | {_pct(hold.get('cagr'))} | {_pct(hold.get('max_drawdown'))} | "
        f"{_num(hold.get('sharpe'))} | {_pct(hold.get('positive_months'))} | {_money(hold.get('ending_equity'))} | "
        f"{_money(spy.get('ending_equity'))} | {_money(qqq.get('ending_equity'))} | "
        f"{'yes' if book['verdict'].get('winner_vs_spy') else 'no'} | "
        f"{'yes' if book['verdict'].get('beats_spy_raw') else 'no'} |"
    )


def _plain(name: str) -> str:
    text = {
        "rsi2_equal": "Equal-weight the liquid ETFs whose RSI(2) is below 10 and whose close is above the 200-day average. Exit a name when its close is above the 5-day average. Otherwise cash.",
        "ibs_equal": "Equal-weight the liquid ETFs whose internal bar strength is below 0.2 and whose close is above the 200-day average. Exit when IBS is above 0.8. Otherwise cash.",
        "three_down": "Equal-weight the liquid ETFs with three lower closes in a row and a close above the 200-day average. Exit when the close is above the 5-day average. Otherwise cash.",
        "rsi2_qqq_overlay": "Hold the RSI(2) sleeve when any of those ETFs is on. Otherwise hold QQQ.",
        "tqqq_sma200": "Hold TQQQ when QQQ's close is above its 200-day average. Otherwise cash. Checked every day.",
        "tqqq_band3": "Hold TQQQ only after QQQ closes 3 percent above its 200-day average. Exit only after a close 3 percent below it.",
        "upro_sma200": "Hold UPRO when SPY's close is above its 200-day average. Otherwise cash.",
        "tqqq_vol20": "Hold TQQQ only while QQQ is above its 200-day average, and scale the weight to min(1, 0.20 / 20-day realized vol).",
        "tqqq_half": "Hold 50 percent TQQQ when QQQ is above its 200-day average. The rest is cash.",
        "qqq_tqqq_blend": "Hold 50 percent QQQ and 50 percent TQQQ when QQQ is above its 200-day average. Otherwise cash.",
        "spy_vol15_weekly": "Hold SPY at min(1, 0.15 / 20-day realized vol). Rebalance weekly. No leverage.",
        "qqq_vol15_weekly": "Hold QQQ at min(1, 0.15 / 20-day realized vol). Rebalance weekly. No leverage.",
        "spy_vol15_weekly_sma": "The weekly 15 percent SPY vol target, and only while SPY is above its 200-day average.",
        "qqq_vol15_weekly_sma": "The weekly 15 percent QQQ vol target, and only while QQQ is above its 200-day average.",
        "dow_mom_top5": "Each month hold the top 5 point-in-time Dow names by 12-1 month return, and only while SPY is above its 200-day average.",
        "sector_top3_12m": "Each month give one third to each of the three sector SPDRs with the best 12-month return, and only if that return is positive.",
        "spy_tom": "Hold SPY on the last session of the month and the first three sessions. Otherwise cash.",
        "qqq_tom": "Hold QQQ on the last session of the month and the first three sessions. Otherwise cash.",
        "spy_pre_holiday": "Hold SPY on the session before an NYSE weekday holiday. Otherwise cash.",
        "qqq_pre_holiday": "Hold QQQ on the session before an NYSE weekday holiday. Otherwise cash.",
        "spy_calendar_both": "Hold SPY when either the turn-of-month window or the pre-holiday session is on. Otherwise cash.",
        "qqq_calendar_both": "Hold QQQ when either the turn-of-month window or the pre-holiday session is on. Otherwise cash.",
        "spy_calendar_blend": "Keep half in SPY all the time. Add the other half only in the combined calendar window.",
        "qqq_calendar_blend": "Keep half in QQQ all the time. Add the other half only in the combined calendar window.",
        "wheel_f": "On F, sell one 30-day 0.30-delta cash-secured put. If assigned, sell a 0.30-delta covered call until the shares are called away. Black-Scholes, not a chain.",
        "covered_f": "Buy 100 shares of F when they fit, and sell a 30-day 0.30-delta call against them.",
        "gtaa_10m": "The published 10-month sleeve: equal slices of SPY, EFA, IEF, and GLD, each held only above its 10-month average.",
        "dual_invested": "The published fully invested dual-momentum book. It is not the bot's 0.75 percent risk book.",
        "tqqq_monthly": "The published monthly TQQQ filter: all in when TQQQ is above its 10-month average, else cash.",
    }
    return text.get(name, name)


def _chart(curves: dict[str, pd.Series], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(12.2, 6.2), dpi=120)
    figure.patch.set_facecolor("#161616")
    axis.set_facecolor("#161616")
    colors = {
        "Conservative": "#7dcea0",
        "Moderate": "#5dade2",
        "High risk": "#e67e22",
        "SPY": "#f4f4f4",
        "QQQ": "#c39bd3",
    }
    for name, series in curves.items():
        if series is None or len(series) == 0:
            continue
        axis.plot(series.index, series.to_numpy(), color=colors.get(name, "#bbbbbb"), lw=1.4, label=name)
    axis.set_yscale("log")
    axis.set_title("Holdout growth of $1,000 after costs. Log scale. Not a forecast.", color="#f4f4f4")
    axis.tick_params(colors="#cccccc")
    axis.grid(True, color="#333333", lw=0.6)
    for spine in axis.spines.values():
        spine.set_color("#444444")
    axis.legend(facecolor="#222222", edgecolor="#444444", labelcolor="#f4f4f4")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, facecolor=figure.get_facecolor())
    plt.close(figure)


def _rebase(equity: pd.Series, stake: float = 1000.0) -> pd.Series:
    if equity is None or len(equity) == 0:
        return pd.Series(dtype=float)
    sliced = equity.loc[equity.index >= HOLDOUT_START]
    if sliced.empty:
        return sliced
    return sliced.astype(float) / float(sliced.iloc[0]) * stake


def _replay_prior(prepared) -> dict[str, pd.Series]:
    """Chart paths only. The rank still uses the published holdout numbers."""
    curves = {}
    gtaa = weights_from_monthly_gtaa(prepared.monthly[list(GTAA_SYMBOLS)], SMA_MONTHS)
    dual_hurdle = prepared.monthly[HURDLE_SYMBOL] / prepared.monthly[HURDLE_SYMBOL].shift(DUAL_LOOKBACK) - 1.0
    dual = weights_from_monthly_dual(
        prepared.monthly[list(DUAL_SYMBOLS)],
        dual_hurdle,
        DUAL_LOOKBACK,
        DUAL_SKIP,
    )
    tqqq = weights_from_monthly_trend(prepared.monthly[HIGH_SYMBOL].rename(HIGH_SYMBOL), SMA_MONTHS)
    curves["gtaa_10m"] = _run(prepared, change_rows(gtaa), HOLDOUT_START, SAMPLE_END, STAKE)["equity"]
    curves["dual_invested"] = _run(prepared, change_rows(dual), HOLDOUT_START, SAMPLE_END, STAKE)["equity"]
    curves["tqqq_monthly"] = _run(prepared, change_rows(tqqq), HOLDOUT_START, SAMPLE_END, STAKE)["equity"]
    return curves


def _markdown(payload: dict[str, Any]) -> str:
    tiers = payload["tiers"]
    by_name = {book["name"]: book for book in payload["books"] if not book.get("empty")}
    lines = [
        START_MARK,
        "## Second search for a small-account book",
        "",
        "Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox forward test was not changed. The rules were frozen before this score. A neighbor that looks better was not promoted. The earlier 10-month sleeve, the fully invested dual-momentum book, and the monthly TQQQ filter keep the numbers already published.",
        "",
        "Cash earns zero. A cash account sells at the next open and buys the session after that. Costs are the Webull stock schedule. Taxes are ignored, so a monthly or daily book that realizes short-term gains looks better here than it would in a taxable account. Fractional shares. The pattern-day-trader rule does not come up, because these are overnight holds and the cash book does not round-trip the same name the same day.",
        "",
        payload["earnings_note"],
        "",
        payload["universe_note"],
        "",
        "The risk-sized Connors RSI(2) book already published on ETFs had a Sharpe of 0.07 and a walk-forward Sharpe of -0.09. The risk-sized sector rotation had a Sharpe of 0.06. Those books use the 0.75 percent sizer and a hard stop. The books below are fully invested versions of different rules. They do not replace those rows.",
        "",
        "### Holdout from 2017-01-01, fresh $1,000",
        "",
        "SPY and QQQ on each row are bought on that book's own holdout dates. A yes under SPY risk means the frozen test: profitable training, and either a higher holdout Sharpe and Calmar than SPY, or a CAGR within three points of SPY with a drawdown at least ten points milder. Rows marked $5,000 are the option books. One contract does not fit the story of a $1,000 account, so those rows, and the SPY and QQQ numbers beside them, start at $5,000.",
        "",
        "| Book | CAGR | Max DD | Sharpe | Positive months | Ending | SPY ending | QQQ ending | Beats SPY risk | Beats SPY raw |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    order = [book["name"] for book in payload["books"] if not book.get("empty")]
    for name in order:
        lines.append(_row(by_name[name]))
    lines.extend(["", "### What each frozen book does", ""])
    for name in order:
        book = by_name[name]
        if book["family"] in {"neighbor", "diagnostic"}:
            continue
        if book["family"] == "prior":
            continue
        full = book.get("full") or {}
        per_year = full.get("entries_per_year")
        if book["family"] == "income":
            trade = f"Opened {book.get('opens', 0)} option cycles. Assigned {book.get('assignments', 0)}. Called away {book.get('called', 0)}. Skipped {book.get('skips', 0)} cycles when the cash was short of the strike or the credit did not cover the fee."
        else:
            years = float(full.get("years") or 0.0)
            rebalances = full.get("rebalances")
            reb_year = (float(rebalances) / years) if isinstance(rebalances, (int, float)) and years else None
            if isinstance(per_year, float) and reb_year is not None:
                trade = f"About {per_year:.1f} new positions a year and {reb_year:.1f} rebalances a year."
            elif isinstance(per_year, float):
                trade = f"About {per_year:.1f} new positions a year."
            else:
                trade = "Entries were not counted."
        lines.append(f"**{name}.** {_plain(name)} {trade} Full-sample CAGR {_pct(full.get('cagr'))}, max drawdown {_pct(full.get('max_drawdown'))}, Sharpe {full.get('sharpe', float('nan')):.2f}, positive months {_pct(full.get('positive_months'))}, ending {_money(full.get('ending_equity'))}.")
        lines.append("")
    lines.extend(["### Rolling windows versus SPY and QQQ", ""])
    lines.append("Each window starts at a month-end. The dollar figure is what the stake is worth at the end. SPY and QQQ pay entry and exit friction. The $5,000 figure is the same return on a $5,000 stake. For the wheel and the covered call, the $1,000 lines scale that $5,000 path. One contract does not scale that way. The separate $1,000 wheel is in the checks table.")
    lines.append("")
    for name in order:
        book = by_name[name]
        if book["family"] in {"neighbor", "diagnostic"} or "windows" not in book:
            continue
        lines.append(f"**{name}.**")
        for months, label in (("6", "6-month"), ("12", "12-month")):
            block = book["windows"][months]
            lines.append(f"{label}, $1,000 versus SPY: {_window_line(block['1000'], 'SPY', 1000)}")
            qqq = dict(block["qqq_1000"])
            qqq["spy_ending_median"] = qqq.get("spy_ending_median")
            lines.append(f"{label}, $1,000 versus QQQ: {_window_line(block['qqq_1000'], 'QQQ', 1000)}")
            lines.append(f"{label}, $5,000 versus SPY: {_window_line(block['5000'], 'SPY', 5000)}")
            lines.append(f"{label}, $5,000 versus QQQ: {_window_line(block['qqq_5000'], 'QQQ', 5000)}")
        lines.append("")
    lines.extend(["### Neighbors and checks that were not allowed to take a tier", ""])
    lines.append("| Check | Holdout CAGR | Max DD | Sharpe | Ending |")
    lines.append("|---|---:|---:|---:|---:|")
    for name, row in payload["checks"].items():
        label = name if not row.get("note") else f"{name}. {row['note']}"
        lines.append(
            f"| {label} | {_pct(row.get('cagr'))} | {_pct(row.get('max_drawdown'))} | {_num(row.get('sharpe'))} | {_money(row.get('ending_equity'))} |"
        )
    lines.extend(["", "### What the score does and does not say", ""])
    lines.append(_plain_verdict(payload))
    lines.append("")
    lines.extend(["### Tiers across this search and the earlier three books", ""])
    lines.append(payload["tier_text"])
    lines.append("")
    lines.append("The bounce and chop share books were not re-run. On their published Dow windows they finished behind SPY buy-and-hold (the 15 percent trail bounce ended at $2,608.44 against four SPY shares at $3,242.23; the next-level bounce ended at $1,502.90). They are not finalists.")
    lines.append("")
    lines.append("Chart: `reports/account_hunt_equity.png`.")
    lines.append("")
    lines.append(payload["bot_note"])
    lines.append("")
    lines.append("Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. Live trading stays off.")
    lines.append("")
    lines.append("```")
    lines.append("python3 -m webull_bot.research_account_hunt")
    lines.append("```")
    lines.append(END_MARK)
    return "\n".join(lines) + "\n"


def _tier_text(tiers: dict[str, Any], books: dict[str, dict[str, Any]]) -> str:
    parts = []
    for label, key in (("Conservative", "conservative"), ("Moderate", "moderate"), ("High risk", "high_risk")):
        name = tiers.get(key)
        if not name or name not in books:
            parts.append(f"{label}: no book cleared that gate.")
            continue
        book = books[name]
        hold = book["holdout"]
        spy = book.get("spy_holdout") or {}
        qqq = book.get("qqq_holdout") or {}
        raw_spy = "It beat SPY on raw holdout return." if book["verdict"].get("beats_spy_raw") else "It did not beat SPY on raw holdout return."
        raw_qqq = "It beat QQQ on raw holdout return." if book.get("beats_qqq_raw") else "It did not beat QQQ on raw holdout return."
        risk = "It cleared the frozen risk-adjusted test against SPY." if book["verdict"].get("winner_vs_spy") else "It did not clear the frozen risk-adjusted test against SPY."
        parts.append(
            f"{label}: {name}. {_plain(name)} Holdout CAGR {_pct(hold.get('cagr'))}, max drawdown {_pct(hold.get('max_drawdown'))}, "
            f"Sharpe {_num(hold.get('sharpe'))}, positive months {_pct(hold.get('positive_months'))}, ending {_money(hold.get('ending_equity'))}. "
            f"SPY on the same dates ended {_money(spy.get('ending_equity'))} (CAGR {_pct(spy.get('cagr'))}, drawdown {_pct(spy.get('max_drawdown'))}, Sharpe {_num(spy.get('sharpe'))}). "
            f"QQQ ended {_money(qqq.get('ending_equity'))} (CAGR {_pct(qqq.get('cagr'))}, drawdown {_pct(qqq.get('max_drawdown'))}, Sharpe {_num(qqq.get('sharpe'))}). "
            f"{raw_spy} {raw_qqq} {risk}"
        )
    return " ".join(parts)


def _bot_note(tiers: dict[str, Any], books: dict[str, dict[str, Any]]) -> str:
    name = tiers.get("conservative") or tiers.get("moderate") or tiers.get("high_risk")
    if not name:
        return (
            "No tier cleared its gate, so there is nothing to add. The bot still runs dual momentum at 0.75 percent risk. "
            "A $1,000 whole-share account mostly cannot buy these ETFs. The sandbox forward test was not changed."
        )
    return (
        f"If the goal is the milder crash, the book to look at first is still {name}. It is not in the bot. "
        "The default book is still dual momentum at 0.75 percent of equity, which on $1,000 fractional shares ended the earlier test at $1,046 and on whole shares at $1,002. "
        "The moderate book is a weekly QQQ weight between zero and one. The high-risk book is a daily TQQQ weight scaled by 20-day realized vol. "
        "OpenAPI equity orders are whole shares, so a $1,000 or $5,000 account would skip most of these ETF orders. Fractional shares, or a paper notional large enough to buy whole shares, would be required. "
        "A cash account can hold any of them overnight. Adding one to the sandbox would be a new forward command: read the daily close, write the target weight, and send the order on a later session. "
        "That command was not added, and the chop-breakout forward test was not edited. Live trading stays off."
    )


def _plain_verdict(payload: dict[str, Any]) -> str:
    """Say what beat buy-and-hold, using numbers already scored. Does not pick a new rule."""
    stress = payload.get("stress") or {}
    checks = payload.get("checks") or {}

    def year(name: str, key: str) -> str:
        row = stress.get(name) or {}
        return _pct(row.get(key))

    bits = [
        (
            "The daily TQQQ filter did not remove the crash the monthly filter took. "
            f"On the full path, 2020 finished {year('tqqq_sma200', '2020')} for the plain 200-day rule, "
            f"{year('tqqq_band3', '2020')} for the 3 percent band, and {year('tqqq_vol20', '2020')} for the 20 percent vol target, "
            "because the rebound landed in the same year. "
            f"2022 finished {year('tqqq_sma200', '2022')}, {year('tqqq_band3', '2022')}, and {year('tqqq_vol20', '2022')} on those three. "
            "The holdout max drawdown is still -57.8% for the plain daily rule, -62.1% for the 3 percent band, and -50.5% for the vol target, "
            "against -69.9% for the published monthly filter. Smaller than -70%, and still a crash. "
            "The 3 percent band made more holdout money ($15,806) than the vol target ($13,192). The frozen high-risk rule keeps the higher Calmar, so the band stays a candidate that was not the pick."
        ),
        (
            "Two neighbors looked better and were not promoted. The daily 15 percent QQQ vol target, which was not the weekly candidate, "
            f"finished the holdout at {_money((checks.get('qqq_vol15_daily') or {}).get('ending_equity'))} with a Sharpe of {_num((checks.get('qqq_vol15_daily') or {}).get('sharpe'))}. "
            f"The top-2 sector book finished at {_money((checks.get('sector_top2_12m') or {}).get('ending_equity'))}. "
            "The pre-registered books are the weekly vol target and the top 3."
        ),
        (
            "The point-in-time Dow momentum book lost to a shuffle of its own weights "
            f"(seed 17 ended {_money((checks.get('dow_mom_top5 shuffle seed 17') or {}).get('ending_equity'))} against the real book's $1,621). "
            f"The current-member Dow diagnostic ended {_money((checks.get('dow_mom_survivors') or {}).get('ending_equity'))}. "
            "That gap is the survivorship haircut on this universe. It was not subtracted from another return, and this is not an S&P 100 test. "
            "The TQQQ 3 percent band beat its own shuffle, which ended "
            f"{_money((checks.get('tqqq_band3 shuffle seed 17') or {}).get('ending_equity'))}."
        ),
        (
            "The wheel and the covered call are a Black-Scholes model on adjusted prices: no listed chain, no early assignment, and dividends are already inside the adjusted close so the formula uses a zero yield. "
            f"On $5,000 the wheel finished the holdout at $5,260. The separate $1,000 wheel finished at {_money((checks.get('wheel_f $1,000 holdout') or {}).get('ending_equity'))}. "
            "QQQM at about $312.76 needs about $31,276 for 100 shares, so it does not fit. Yahoo returned no SPLG prices here, so that fit check was not scored."
        ),
        (
            "On raw holdout dollars, the plain daily TQQQ rule ($10,774), the 3 percent band ($15,806), the vol target ($13,192), the QQQ/TQQQ blend ($7,062), and the published monthly filter ($9,255) beat both SPY ($4,028) and QQQ ($6,791). "
            "Half TQQQ ($5,304) and UPRO ($4,467) beat SPY and not QQQ. "
            "None of the levered books cleared the frozen risk-adjusted test against SPY. The vol target's Sharpe is 0.83 against SPY's 0.88 and QQQ's 0.98. "
            "The 10-month sleeve ($1,925), the weekly QQQ vol target with the 200-day filter ($3,358), and the weekly QQQ vol target without that filter ($3,627) cleared the SPY risk test. "
            "The filter version had the higher Calmar, so it took the moderate slot. All three finished behind SPY and QQQ on dollars. "
            "The moderate book's Sharpe is 0.99 against QQQ's 0.98. I would not call a one-hundredth of a Sharpe a win over QQQ. "
            "Its Calmar is higher because the drawdown is -17.0% against QQQ's -35.1%, and it made about half as much money. "
            "No book in this search beat QQQ buy-and-hold on both raw return and risk-adjusted return."
        ),
    ]
    return " ".join(bits)


def _write_results(text: str) -> None:
    path = Path("RESULTS.md")
    existing = path.read_text() if path.exists() else ""
    block = text if text.endswith("\n") else text + "\n"
    if START_MARK in existing and END_MARK in existing:
        before = existing.split(START_MARK)[0]
        after = existing.split(END_MARK)[1]
        path.write_text(before + block + after.lstrip("\n"))
        return
    marker = "<!-- ACCOUNT_WINNERS_END -->"
    if marker in existing:
        path.write_text(existing.replace(marker, marker + "\n\n" + block))
        return
    path.write_text(existing + "\n" + block)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items() if key not in {"equity", "hold_equity", "signals"}}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.floating, float)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if value is None or isinstance(value, str):
        return value
    return str(value)


def main() -> None:
    rules = frozen_rules()
    if rules["holdout_start"] != "2017-01-01":
        raise SystemExit("holdout moved")
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "account_hunt_rules.json").write_text(json.dumps(rules, indent=2) + "\n")
    symbols = list(
        dict.fromkeys(
            [
                *MEAN_REVERSION_SYMBOLS,
                *SECTOR_SYMBOLS,
                *GTAA_SYMBOLS,
                *DUAL_SYMBOLS,
                HURDLE_SYMBOL,
                HIGH_SYMBOL,
                "UPRO",
                "F",
                "SPLG",
                "QQQM",
                *all_dow_tickers(),
            ]
        )
    )
    bars: dict[str, pd.DataFrame] = {}
    missing = []
    for symbol in symbols:
        frame = _load_symbol(symbol)
        if frame is None or frame.empty:
            missing.append(symbol)
            continue
        bars[symbol] = frame
        print(f"loaded {symbol} {frame.index.min().date()} {frame.index.max().date()} {len(frame)}", flush=True)
    if "SPY" not in bars or "QQQ" not in bars:
        raise SystemExit("SPY and QQQ are required")
    frames = _clock_frames(bars)
    prepared = prepare(bars, [symbol for symbol in bars if symbol in frames])
    # prepare() reindexes to SPY's own index. Use its clock for signals that must match.
    built = _build(frames, prepared.monthly)
    scored = []
    checks = {}
    for spec in built.values():
        print(f"score {spec['name']}", flush=True)
        if spec["family"] in {"neighbor", "diagnostic"}:
            if spec["signals"].empty:
                continue
            hold = _run(prepared, spec["signals"], HOLDOUT_START, SAMPLE_END, STAKE)
            checks[spec["name"]] = hold["book"]
            continue
        packed = _pack(prepared, spec)
        if packed.get("empty"):
            continue
        scored.append(packed)
        if spec["name"] in {"rsi2_equal", "tqqq_band3", "sector_top3_12m", "dow_mom_top5", "spy_calendar_both"}:
            shuffled = shuffle_weights(spec["signals"], RANDOM_SEED)
            shuffled_hold = _run(prepared, shuffled, HOLDOUT_START, SAMPLE_END, STAKE)
            checks[f"{spec['name']} shuffle seed {RANDOM_SEED}"] = shuffled_hold["book"]
    if "F" in bars:
        wheel_full = simulate_wheel(bars["F"], starting_equity=5000.0, trade_start=SAMPLE_START, trade_end=SAMPLE_END)
        wheel_hold = simulate_wheel(bars["F"], starting_equity=5000.0, trade_start=HOLDOUT_START, trade_end=SAMPLE_END)
        wheel_full["hold_equity"] = wheel_hold["equity"]
        packed = _pack_option(
            "wheel_f",
            wheel_full,
            prepared.opens["SPY"],
            prepared.closes["SPY"],
            prepared.opens["QQQ"],
            prepared.closes["QQQ"],
            5000.0,
        )
        if not packed.get("empty"):
            scored.append(packed)
        wheel_small = simulate_wheel(bars["F"], starting_equity=1000.0, trade_start=HOLDOUT_START, trade_end=SAMPLE_END)
        checks["wheel_f $1,000 holdout"] = performance(wheel_small["equity"], 1000.0) if len(wheel_small["equity"]) else {"cagr": 0}
        covered = simulate_covered_call(bars["F"], starting_equity=5000.0, trade_start=SAMPLE_START, trade_end=SAMPLE_END)
        covered_hold = simulate_covered_call(bars["F"], starting_equity=5000.0, trade_start=HOLDOUT_START, trade_end=SAMPLE_END)
        if covered.get("unfit"):
            checks["covered_f"] = {"cagr": None, "max_drawdown": None, "sharpe": None, "ending_equity": None, "note": covered.get("reason")}
        else:
            covered["hold_equity"] = covered_hold["equity"]
            packed = _pack_option(
                "covered_f",
                covered,
                prepared.opens["SPY"],
                prepared.closes["SPY"],
                prepared.opens["QQQ"],
                prepared.closes["QQQ"],
                5000.0,
            )
            if not packed.get("empty"):
                scored.append(packed)
    for symbol in ("SPLG", "QQQM"):
        if symbol not in bars:
            checks[f"{symbol} covered call"] = {"note": "no prices"}
            continue
        probe = simulate_covered_call(bars[symbol], starting_equity=5000.0, trade_start=HOLDOUT_START, trade_end=SAMPLE_END)
        if probe.get("unfit"):
            price = float(bars[symbol]["close"].dropna().iloc[-1])
            checks[f"{symbol} covered call"] = {
                "cagr": None,
                "max_drawdown": None,
                "sharpe": None,
                "ending_equity": None,
                "note": f"100 shares at about ${price:.2f} do not fit in $5,000",
            }
        else:
            checks[f"{symbol} covered call holdout"] = performance(probe["equity"], 5000.0)
    for name, prior in PRIOR_HOLDOUT.items():
        scored.append(dict(prior))
    tiers = assign_tiers(scored)
    by_name = {book["name"]: book for book in scored if not book.get("empty")}
    earnings_note = _earnings_note()
    present_dow = [symbol for symbol in all_dow_tickers() if symbol in bars]
    absent_dow = [symbol for symbol in all_dow_tickers() if symbol not in bars]
    universe_note = (
        f"Stock momentum uses the point-in-time Dow ({len(present_dow)} names had Yahoo prices). "
        f"Missing Yahoo history, so those membership dates cannot be held: {', '.join(absent_dow) if absent_dow else 'none'}. "
        "That hole can hide a name that was removed and then stopped trading. It is not a survivor list, and it is not the S&P 100. "
        "A free point-in-time S&P 100 file was not in this repo. The current-member Dow book is the survivor diagnostic in the checks table. "
        "The gap between that diagnostic and the point-in-time book is the haircut estimate. It was not applied as a new return."
    )
    tier_text = _tier_text(tiers, by_name)
    bot_note = _bot_note(tiers, by_name)
    # Stress years for levered candidates, from the full path.
    stress = {}
    for name in ("tqqq_sma200", "tqqq_band3", "tqqq_vol20", "tqqq_half", "qqq_tqqq_blend", "upro_sma200"):
        book = by_name.get(name)
        if not book or book.get("equity") is None:
            continue
        stress[name] = {
            "2008": calendar_year_return(book["equity"], 2008, STAKE),
            "2020": calendar_year_return(book["equity"], 2020, STAKE),
            "2022": calendar_year_return(book["equity"], 2022, STAKE),
            "holdout_dd": book["holdout"]["max_drawdown"],
        }
    payload = {
        "rules": rules,
        "missing": missing,
        "books": scored,
        "checks": checks,
        "tiers": tiers,
        "earnings_note": earnings_note,
        "universe_note": universe_note,
        "tier_text": tier_text,
        "bot_note": bot_note,
        "stress": stress,
        "members_2026": members_on(date(2026, 10, 6)),
    }
    text = _markdown(payload)
    _write_results(text)
    (REPORT / "account_hunt.json").write_text(json.dumps(_jsonable(payload), indent=2) + "\n")
    replay = _replay_prior(prepared)
    curves = {}
    labels = {"conservative": "Conservative", "moderate": "Moderate", "high_risk": "High risk"}
    for key, label in labels.items():
        name = tiers.get(key)
        if not name:
            continue
        if name in replay:
            curves[label] = _rebase(replay[name])
        elif name in by_name and by_name[name].get("hold_equity") is not None:
            equity = by_name[name]["hold_equity"]
            stake = float(by_name[name].get("stake") or STAKE)
            curves[label] = _rebase(equity, STAKE) if stake == STAKE else _rebase(equity, STAKE)
        elif name in by_name and by_name[name].get("equity") is not None:
            curves[label] = _rebase(by_name[name]["equity"])
    spy_hold = buy_and_hold(
        prepared.opens["SPY"],
        prepared.closes["SPY"],
        starting_equity=STAKE,
        trade_start=HOLDOUT_START,
        trade_end=SAMPLE_END,
    )
    qqq_hold = buy_and_hold(
        prepared.opens["QQQ"],
        prepared.closes["QQQ"],
        starting_equity=STAKE,
        trade_start=HOLDOUT_START,
        trade_end=SAMPLE_END,
    )
    curves["SPY"] = _rebase(spy_hold)
    curves["QQQ"] = _rebase(qqq_hold)
    _chart(curves, REPORT / "account_hunt_equity.png")
    print(tier_text)
    print("wrote reports/account_hunt_equity.png")


if __name__ == "__main__":
    main()
