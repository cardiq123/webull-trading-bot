"""SPY daily chart check against the Oct 6, 2026 thinkorswim drawing.

Reference only. The chop rule and the horizontal-level rule stay the ones
already scored. This module does not rescore a book and does not place orders.

Run: ``python -m webull_bot.chart_reads.research_spy_ref``
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from webull_bot.chart_reads.chop import features
from webull_bot.chart_reads.levels import HORIZONTAL_KEEP, HORIZONTAL_LOOKBACK, build_levels
from webull_bot.chart_reads.research_daily import load_daily
from webull_bot.indicators import atr, ema
from webull_bot.patterns import confirmed_pivot_high, confirmed_pivot_low

START = "<!-- CHART_READS_SPY_REF_START -->"
END = "<!-- CHART_READS_SPY_REF_END -->"
# Prices drawn on the thinkorswim chart. 740 and 735 are one thick zone.
DRAWN = (781, 768, 760, 752, 737.5, 700, 690, 683, 675, 655, 632)
DRAWN_LABEL = {
    781: "781",
    768: "768",
    760: "760",
    752: "752",
    737.5: "740/735",
    700: "700",
    690: "690",
    683: "683",
    675: "675",
    655: "655",
    632: "632",
}
BAND_FROM = date(2026, 8, 1)
BAND_TO = date(2026, 10, 5)
AS_OF = date(2026, 10, 6)


def _day(ts) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York")
    return stamp.date()


def _rsi(close: pd.Series) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0).ewm(alpha=1.0 / 14.0, adjust=False).mean()
    loss = (-delta.clip(upper=0.0)).ewm(alpha=1.0 / 14.0, adjust=False).mean()
    return 100.0 - 100.0 / (1.0 + gain / loss.replace(0.0, np.nan))


def _pivots(frame: pd.DataFrame) -> list[tuple[date, float, str]]:
    found = []
    for kind, series in (
        ("high", confirmed_pivot_high(frame["high"], 4, 4)),
        ("low", confirmed_pivot_low(frame["low"], 4, 4)),
    ):
        for stamp, price in series.dropna().items():
            loc = int(frame.index.get_loc(stamp))
            if loc < 4:
                continue
            found.append((_day(frame.index[loc - 4]), float(price), kind))
    found.sort(key=lambda row: (row[0], row[2], row[1]))
    return found


def _in_live(price: float, live: list[float]) -> bool:
    return any(abs(price - other) <= 0.05 for other in live)


def _nearest(level: float, pivots: list[tuple[date, float, str]]) -> tuple[date, float, str]:
    return min(pivots, key=lambda row: abs(row[1] - level))


def _band_stats(frame: pd.DataFrame, feat: pd.DataFrame) -> dict:
    mask = np.array([BAND_FROM <= _day(ts) <= BAND_TO for ts in frame.index])
    window = frame.loc[mask]
    part = feat.loc[mask]
    width = atr(frame)
    fast = ema(frame["close"].astype(float), 9)
    slow = ema(frame["close"].astype(float), 20)
    sep = ((fast - slow).abs() <= 0.35 * width).loc[mask]
    slope = ((slow - slow.shift(10)).abs() <= 0.50 * width).loc[mask]
    width = width.loc[mask]
    fast = fast.loc[mask]
    slow = slow.loc[mask]
    sign = np.sign(fast - slow)
    crosses = int((sign.ne(sign.shift(1)) & sign.ne(0) & sign.shift(1).ne(0)).sum())
    slope_known = slope.notna() & width.notna()
    return {
        "bars": int(len(window)),
        "low": float(window["low"].min()),
        "low_day": _day(window["low"].idxmin()),
        "high": float(window["high"].max()),
        "high_day": _day(window["high"].idxmax()),
        "close_low": float(window["close"].min()),
        "close_high": float(window["close"].max()),
        "chop": int(part["chop"].sum()),
        "narrow": float(part["narrow"].mean()),
        "vwap": float((part["vwap_crosses"] >= 3).mean()),
        "sep": float(sep.mean()),
        "slope": float(slope[slope_known].mean()) if slope_known.any() else 0.0,
        "crosses": crosses,
        "rel80": float((part["rel_volume"] < 0.80).mean()),
        "volume": float(window["volume"].median()),
    }


def _fmt(price: float) -> str:
    return f"{price:.2f}"


def render(frame: pd.DataFrame) -> str:
    close = frame["close"].astype(float)
    feat = features(frame)
    table = build_levels(frame)
    last = len(frame) - 1
    year_start = frame.index[-252]
    year = frame.loc[year_start:]
    year_feat = feat.loc[year.index]
    slow = ema(close, 200)
    macd = ema(close, 12) - ema(close, 26)
    signal = ema(macd, 9)
    hist = macd - signal
    rsi = _rsi(close)
    pivots = [row for row in _pivots(frame) if row[0] >= _day(year_start)]
    live = sorted(float(price) for price in table.prices(last, "horizontal"))
    band = _band_stats(frame, feat)
    rally = frame.loc["2026-03-30":"2026-07-31"]
    chop_days = [_day(ts).isoformat() for ts in year_feat.index[year_feat["chop"].to_numpy()]]
    low_day = _day(year["low"].idxmin())
    lines = [
        "## SPY daily, Oct 6 2026 chart",
        "",
        "REFERENCE ONLY. This does not change the gate, the chop rule, or the level rule. "
        "Nothing was sent to a broker.",
        "",
        "The thinkorswim chart is a 1-year daily SPY as of 2026-10-06. Price is 781.03 at a high of 781.62. "
        "The 9 and 20 EMAs are tight under price. The 200 EMA is near 725.4 and rising. VWAP is on the chart. "
        "RSI(14) is 64. MACD(12, 26, 9) is about +2.45 and just crossing up. The year's low, 629.28, was a V-bottom "
        "with RSI oversold. After the rally, price chopped for weeks in about a 755-775 band on declining volume, "
        "then broke out. The drawn horizontals are about 781, 768, 760, 752, a thick zone at 740/735, then 700, 690, "
        "683, 675, 655, and 632.",
        "",
        (
            f"Yahoo's adjusted daily bar on {AS_OF.isoformat()} has a high of {_fmt(float(frame.iloc[-1]['high']))} "
            f"and a close of {_fmt(float(frame.iloc[-1]['close']))}. "
            f"The 9 EMA is {_fmt(float(ema(close, 9).iloc[-1]))} and the 20 EMA is {_fmt(float(ema(close, 20).iloc[-1]))}, "
            f"both under the close. The 200 EMA is {_fmt(float(slow.iloc[-1]))} and rose "
            f"{_fmt(float(slow.iloc[-1] - slow.iloc[-21]))} points over the prior 20 sessions. "
            f"RSI(14) is {float(rsi.iloc[-1]):.1f}. The MACD line is {float(macd.iloc[-1]):.2f} and the histogram is "
            f"{float(hist.iloc[-1]):.2f}, up from {float(hist.iloc[-2]):.2f} the day before. "
            f"The adjusted low of the last 252 sessions is {_fmt(float(year['low'].min()))} on {low_day.isoformat()}. "
            f"March 27's low was {_fmt(float(frame.loc['2026-03-27', 'low']))}. "
            f"RSI on {low_day.isoformat()} was {float(rsi.loc[year['low'].idxmin()]):.1f}. "
            "Older Yahoo prices sit a few points under the thinkorswim labels because the series is split- and dividend-adjusted. "
            "The October 6 high matches."
        ),
        "",
        (
            f"The chop flag does not mark that sideways stretch. In the last 252 sessions it is on for "
            f"{len(chop_days)} bar{'s' if len(chop_days) != 1 else ''}"
            + (": " + ", ".join(chop_days) if chop_days else "")
            + ". "
            f"From {BAND_FROM.isoformat()} through {BAND_TO.isoformat()} ({band['bars']} sessions) the high was "
            f"{_fmt(band['high'])} on {band['high_day'].isoformat()} and the low was {_fmt(band['low'])} on {band['low_day'].isoformat()}, "
            f"with closes from {_fmt(band['close_low'])} to {_fmt(band['close_high'])}. "
            f"The range was narrow on {band['narrow']:.0%} of those bars, and close had crossed the 20-bar VWAP at least three times "
            f"on {band['vwap']:.0%} of them. The 9 and 20 EMAs were within 0.35 ATR on {band['sep']:.0%} of the bars and the 20 EMA's "
            f"10-bar slope was inside 0.50 ATR on {band['slope']:.0%}, but they changed order only {band['crosses']} times in the whole stretch, "
            f"so the tangled-EMA leg stays off and the four-way flag never turns on ({band['chop']} chop bars). "
            f"Relative volume was under 0.80 on {band['rel80']:.0%} of the bars. "
            f"Median volume in the stretch was {band['volume'] / 1e6:.1f} million shares, against "
            f"{float(rally['volume'].median()) / 1e6:.1f} million from the March low through July. "
            "The October 6 breakout bar is not chop. The rule was left as scored."
        ),
        "",
        (
            f"The live horizontal set on {AS_OF.isoformat()} is the last {HORIZONTAL_KEEP} confirmed pivot highs and the last "
            f"{HORIZONTAL_KEEP} confirmed pivot lows inside {HORIZONTAL_LOOKBACK} bars, which reaches back to "
            f"{_day(frame.index[-HORIZONTAL_LOOKBACK]).isoformat()}: "
            + ", ".join(_fmt(price) for price in reversed(live))
            + ". A pivot is confirmed four bars after it prints, so the October 6 high is not in the set yet. "
            "The 781 row is that unfinished high. The other rows are the nearest confirmed swing in the last 252 sessions."
        ),
        "",
        "| Drawn | Nearest swing | Date | Kind | In the live set |",
        "|---|---:|---|---|---|",
    ]
    session_high = (AS_OF, float(frame.iloc[-1]["high"]), "high, not confirmed")
    for level in DRAWN:
        when, price, kind = _nearest(level, pivots)
        if abs(session_high[1] - level) < abs(price - level):
            when, price, kind = session_high
        live_flag = "yes" if kind != "high, not confirmed" and _in_live(price, live) else "no"
        lines.append(
            f"| {DRAWN_LABEL[level]} | {_fmt(price)} | {when.isoformat()} | {kind} | {live_flag} |"
        )
    lines.extend(
        [
            "",
            "760.15 is the drawn 760 line, 752.87 is the drawn 752 line, and 737.68 sits in the 740/735 zone. "
            "768 has no confirmed pivot at that price. The nearest swing is the August 28 high at 773.38, about five points higher, and that high is in the live set. "
            "698.74 is still inside the 120-bar window and is the April 23 low, near 700, but six later pivot lows are newer, so the keeper drops it. "
            "The January and November swings, and the March low, are older than 120 bars, so they are not targets on this close. "
            "They are the same kind of swing the drawing uses.",
            "",
            "The chart is `reports/setups/readSPY_chop_levels_1d.png`. Gold bands are detected chop. "
            "Solid gold lines are the live horizontal set. Dotted lines are the other confirmed swings in the year. "
            "Dashed lines are the thinkorswim prices.",
            "",
            "The published A-D books are unchanged. Chop and this level set stay off the optional list and off the registry. "
            "The default book is still dual momentum.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_report(text: str, path: Path) -> None:
    body = path.read_text() if path.exists() else ""
    block = f"{START}\n{text.rstrip()}\n{END}\n"
    if START in body and END in body:
        pre = body.split(START)[0].rstrip() + "\n\n"
        post = body.split(END, 1)[1].lstrip("\n")
        path.write_text(pre + block + ("\n" + post if post else ""))
        return
    if body and not body.endswith("\n"):
        body += "\n"
    path.write_text(body + "\n" + block)


def save_chart(frame: pd.DataFrame, path: Path) -> None:
    feat = features(frame)
    table = build_levels(frame)
    window = frame.iloc[-252:]
    feat_w = feat.loc[window.index]
    live = sorted(float(price) for price in table.prices(len(frame) - 1, "horizontal"))
    pivots = [row for row in _pivots(frame) if row[0] >= _day(window.index[0]) and not _in_live(row[1], live)]
    fig, (ax, vol) = plt.subplots(
        2,
        1,
        figsize=(12.8, 7.6),
        sharex=True,
        gridspec_kw={"height_ratios": [3.3, 1.0]},
    )
    ax.set_facecolor("#161616")
    vol.set_facecolor("#161616")
    fig.patch.set_facecolor("#161616")
    flags = feat_w["chop"].to_numpy(dtype=bool)
    for pos, flag in enumerate(flags):
        if flag:
            ax.axvspan(pos - 0.5, pos + 0.5, color="#f2d16b", alpha=0.35, linewidth=0)
            vol.axvspan(pos - 0.5, pos + 0.5, color="#f2d16b", alpha=0.35, linewidth=0)
    labeled = {"live": False, "older": False, "drawn": False}
    for price in sorted({row[1] for row in pivots}):
        ax.axhline(price, color="#6d6d6d", linewidth=0.6, linestyle=":", label="older confirmed swing" if not labeled["older"] else None)
        labeled["older"] = True
    for price in DRAWN:
        ax.axhline(
            price,
            color="#c47bff",
            linewidth=0.8,
            linestyle="--",
            alpha=0.85,
            label="thinkorswim level" if not labeled["drawn"] else None,
        )
        labeled["drawn"] = True
    for price in live:
        ax.axhline(price, color="#f2d16b", linewidth=1.05, label="live horizontal pivot" if not labeled["live"] else None)
        labeled["live"] = True
    xs = np.arange(len(window))
    for pos, (_, row) in enumerate(window.iterrows()):
        color = "#3d9e57" if row["close"] >= row["open"] else "#d64545"
        ax.plot([pos, pos], [row["low"], row["high"]], color=color, linewidth=0.7)
        ax.plot([pos, pos], [row["open"], row["close"]], color=color, linewidth=2.2)
    ax.plot(xs, ema(frame["close"].astype(float), 9).loc[window.index], color="#4ea3ff", linewidth=1.0, label="EMA 9")
    ax.plot(xs, ema(frame["close"].astype(float), 20).loc[window.index], color="#e0a100", linewidth=1.0, label="EMA 20")
    ax.plot(xs, ema(frame["close"].astype(float), 200).loc[window.index], color="#d0d0d0", linewidth=1.0, label="EMA 200")
    ax.plot(xs, feat_w["vwap"], color="#7fd1c8", linewidth=0.9, label="20-bar VWAP")
    colors = ["#3d9e57" if row["close"] >= row["open"] else "#d64545" for _, row in window.iterrows()]
    vol.bar(xs, window["volume"].to_numpy(dtype=float), color=colors, width=0.7)
    step = max(1, len(window) // 6)
    ticks = list(range(0, len(window), step))
    if ticks[-1] != len(window) - 1:
        ticks.append(len(window) - 1)
    vol.set_xticks(ticks)
    vol.set_xticklabels([pd.Timestamp(window.index[pos]).strftime("%Y-%m-%d") for pos in ticks], rotation=30, ha="right")
    ax.set_title("SPY daily through 2026-10-06, detected chop and horizontal levels", color="white")
    ax.tick_params(colors="#cccccc")
    vol.tick_params(colors="#cccccc")
    for spine in (*ax.spines.values(), *vol.spines.values()):
        spine.set_color("#333333")
    ax.legend(facecolor="#161616", edgecolor="#333333", labelcolor="white", loc="upper left", fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    artifact = Path("/opt/cursor/artifacts/setups")
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / path.name).write_bytes(path.read_bytes())


def main() -> None:
    frames, _missing = load_daily()
    frame = frames["SPY"]
    text = render(frame)
    write_report(text, Path("RESULTS.md"))
    path = Path("reports/setups/readSPY_chop_levels_1d.png")
    save_chart(frame, path)
    print(text)
    print(f"chart {path}", flush=True)


if __name__ == "__main__":
    main()
