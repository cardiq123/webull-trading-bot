"""HTML and Markdown reports with an inline equity chart."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import pandas as pd


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _money(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:,.2f}"


def equity_svg(equity: pd.Series, width: int = 880, height: int = 320) -> str:
    if equity is None or len(equity) < 2:
        return "<p>No equity curve.</p>"
    values = [float(v) for v in equity.tolist()]
    peak = values[0]
    drawdowns = []
    for value in values:
        peak = max(peak, value)
        drawdowns.append(value / peak - 1.0 if peak else 0.0)
    lo = min(values)
    hi = max(values)
    span = hi - lo or 1.0
    pad_l, pad_r, pad_t, pad_b = 56, 16, 16, 28
    inner_w = width - pad_l - pad_r
    chart_h = 200
    dd_top = pad_t + chart_h + 16
    dd_h = height - dd_top - pad_b

    def xy(i: int, value: float) -> tuple[float, float]:
        x = pad_l + inner_w * (i / (len(values) - 1))
        y = pad_t + chart_h * (1.0 - (value - lo) / span)
        return x, y

    points = " ".join(f"{xy(i, v)[0]:.1f},{xy(i, v)[1]:.1f}" for i, v in enumerate(values))
    dd_lo = min(drawdowns)
    dd_span = abs(dd_lo) or 1.0
    dd_points = []
    for i, dd in enumerate(drawdowns):
        x = pad_l + inner_w * (i / (len(values) - 1))
        y = dd_top + dd_h * (abs(dd) / dd_span)
        dd_points.append(f"{x:.1f},{y:.1f}")
    start = equity.index[0]
    end = equity.index[-1]
    start_label = pd.Timestamp(start).date().isoformat()
    end_label = pd.Timestamp(end).date().isoformat()
    return f"""<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Equity curve">
  <rect width="100%" height="100%" fill="#f7f5f2"/>
  <text x="{pad_l}" y="14" font-size="11" fill="#555">Equity</text>
  <polyline fill="none" stroke="#1f4b3a" stroke-width="1.6" points="{points}"/>
  <text x="{pad_l}" y="{height - 8}" font-size="11" fill="#555">{start_label}</text>
  <text x="{width - pad_r - 70}" y="{height - 8}" font-size="11" fill="#555">{end_label}</text>
  <text x="{pad_l}" y="{dd_top - 2}" font-size="11" fill="#555">Drawdown</text>
  <polyline fill="none" stroke="#8c3a3a" stroke-width="1.4" points="{' '.join(dd_points)}"/>
  <text x="8" y="{pad_t + 8}" font-size="11" fill="#333">{hi:,.0f}</text>
  <text x="8" y="{pad_t + chart_h}" font-size="11" fill="#333">{lo:,.0f}</text>
</svg>"""


def metrics_table(metrics: dict[str, Any]) -> str:
    rows = [
        ("CAGR", _pct(metrics.get("cagr"))),
        ("Total return", _pct(metrics.get("total_return"))),
        ("Ending equity", _money(metrics.get("ending_equity"))),
        ("Win rate", _pct(metrics.get("win_rate"))),
        ("Average win", _money(metrics.get("avg_win"))),
        ("Average loss", _money(metrics.get("avg_loss"))),
        ("Profit factor", _num(metrics.get("profit_factor"))),
        ("Expectancy", _money(metrics.get("expectancy"))),
        ("Max drawdown", _pct(metrics.get("max_drawdown"))),
        ("Sharpe", _num(metrics.get("sharpe"))),
        ("Sortino", _num(metrics.get("sortino"))),
        ("Exposure", _pct(metrics.get("exposure"))),
        ("Trades", str(metrics.get("trades", 0))),
    ]
    body = "\n".join(
        f"<tr><th>{escape(name)}</th><td>{escape(value)}</td></tr>" for name, value in rows
    )
    return f"<table>{body}</table>"


def write_html_report(
    path: Path,
    *,
    title: str,
    disclaimer: str,
    metrics: dict[str, Any],
    equity: pd.Series,
    notes: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    note_html = ""
    if notes:
        items = "\n".join(f"<li>{escape(note)}</li>" for note in notes)
        note_html = f"<ul>{items}</ul>"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 2rem auto; max-width: 920px; color: #1c1c1c; background: #fff; }}
    .banner {{ background: #f3e6e6; border: 1px solid #8c3a3a; padding: 0.8rem 1rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0; }}
    th, td {{ border-bottom: 1px solid #ddd; text-align: left; padding: 0.35rem 0.8rem; }}
    th {{ font-weight: 600; width: 14rem; }}
    h1 {{ font-size: 1.6rem; }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <div class="banner">{escape(disclaimer)}</div>
  {equity_svg(equity)}
  {metrics_table(metrics)}
  {note_html}
</body>
</html>
"""
    path.write_text(html)


def metrics_markdown_row(name: str, metrics: dict[str, Any], flags: list[str] | None = None) -> str:
    flag_text = ", ".join(flags or []) or "—"
    return (
        f"| {name} | {_pct(metrics.get('cagr'))} | {_pct(metrics.get('total_return'))} | "
        f"{_pct(metrics.get('win_rate'))} | {_money(metrics.get('avg_win'))} | {_money(metrics.get('avg_loss'))} | "
        f"{_num(metrics.get('profit_factor'))} | {_money(metrics.get('expectancy'))} | "
        f"{_pct(metrics.get('max_drawdown'))} | {_num(metrics.get('sharpe'))} | {_num(metrics.get('sortino'))} | "
        f"{_pct(metrics.get('exposure'))} | {metrics.get('trades', 0)} | {flag_text} |"
    )


TABLE_HEADER = (
    "| Strategy | CAGR | Total return | Win rate | Avg win | Avg loss | Profit factor | "
    "Expectancy | Max DD | Sharpe | Sortino | Exposure | Trades | Flags |\n"
    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
)
