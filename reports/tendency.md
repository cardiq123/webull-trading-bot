<!-- TENDENCY_START -->
### Stock tendencies

Backtests only. Nothing was sent to a broker. Live trading stays off. No sandbox book was added.

No stock showed a consistent dip or rip personality. 768 combinations were counted. The bar was not loosened after the scores.

A dip or a rip is an edge: the first bar that closes outside the band, through RSI 30 or 70, a session move of 1 or 1.5 prior-day ATRs, a gap of 1 ATR, or a three-session move of 1.5 ATR. Intraday VWAP is the session VWAP. The daily band is the 20-day volume-weighted average, because a daily bar has no session VWAP. Forward closes are 30 minutes, 60 minutes, the session close, the next session, and three and five sessions, where the bar size allows it. Each cell is compared with a seed-17 random bar at the same clock. Mean-reverting means at least 30 training events, q ≤ 0.10, a positive reversal edge, and a higher reversal rate than the random bars. Trending is the mirror. The holdout is 2026-07-07 through 2026-10-06. It is computed only for a cell that already cleared the training bar, and it has to keep the same sign.

Daily bars cover the whole list. Intraday bars that can reach 2018 are Dukascopy SPY and QQQ bids. The other names have about 60 Yahoo 5-minute days inside the holdout. Those rows are a short sample and are not in the trial count.

Trials counted: 768. The frozen count is 768.

One row per stock. The row is the lowest training q, then the largest edge over the random bars. It is not a pass.

| Stock | Frame | Event | Horizon | Train n | Reversal | Random | Edge | q | Holdout n | Holdout edge | Class |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| UNH | 1d | rsi_rip | d5 | 42 | 50.0% | 42.9% | 0.09% | 1.00 |  | n/a | inconsistent |
| SPY | 5m | atr1_dip | m30 | 696 | 53.7% | 48.9% | 0.04% | 0.30 |  | n/a | inconsistent |
| QQQ | 15m | rsi_dip | d5 | 869 | 62.7% | 58.7% | 0.8% | 0.78 |  | n/a | inconsistent |
| AAPL | 1d | vwap_dip | d5 | 46 | 50.0% | 56.5% | 1.1% | 1.00 |  | n/a | inconsistent |
| MSFT | 1d | vwap_dip | d5 | 49 | 63.3% | 53.1% | 2.0% | 0.78 |  | n/a | inconsistent |
| NVDA | 1d | vwap_dip | d5 | 47 | 70.2% | 48.9% | 2.2% | 1.00 |  | n/a | inconsistent |
| AMZN | 1d | gap_dip | d5 | 40 | 67.5% | 57.5% | 1.7% | 1.00 |  | n/a | inconsistent |
| GOOGL | 1d | gap_dip | d5 | 44 | 59.1% | 50.0% | 1.0% | 1.00 |  | n/a | inconsistent |
| META | 1d | gap_rip | d3 | 32 | 53.1% | 37.5% | 1.1% | 1.00 |  | n/a | inconsistent |
| TSLA | 1d | gap_dip | d5 | 44 | 54.5% | 54.5% | 1.9% | 1.00 |  | n/a | inconsistent |
| PLTR | 1d | vwap_rip | d5 | 55 | 49.1% | 41.8% | 0.17% | 1.00 |  | n/a | inconsistent |
| MSTR | 1d | gap_rip | d5 | 38 | 42.1% | 63.2% | -4.0% | 0.78 |  | n/a | inconsistent |
| HOOD | 1d | multi_dip | d5 | 51 | 41.2% | 43.1% | 0.44% | 1.00 |  | n/a | inconsistent |
| MU | 1d | vwap_dip | d5 | 51 | 51.0% | 47.1% | 0.8% | 1.00 |  | n/a | inconsistent |
| AMD | 1d | gap_dip | d5 | 31 | 54.8% | 48.4% | 2.1% | 1.00 |  | n/a | inconsistent |
| AVGO | 1d | vwap_dip | d5 | 46 | 63.0% | 52.2% | 1.3% | 1.00 |  | n/a | inconsistent |
| INTC | 1d | vwap_dip | d5 | 47 | 57.4% | 48.9% | 0.9% | 1.00 |  | n/a | inconsistent |
| JPM | 1d | vwap_dip | d5 | 46 | 65.2% | 56.5% | 1.3% | 1.00 |  | n/a | inconsistent |
| LLY | 1d | multi_rip | d5 | 130 | 44.6% | 33.8% | -0.37% | 1.00 |  | n/a | inconsistent |
| COST | 1d | multi_rip | d5 | 130 | 43.8% | 35.4% | -0.21% | 1.00 |  | n/a | inconsistent |
| XOM | 1d | rsi_rip | d3 | 33 | 48.5% | 45.5% | 0.33% | 1.00 |  | n/a | inconsistent |
| NFLX | 1d | vwap_rip | d3 | 74 | 45.9% | 43.2% | -0.36% | 1.00 |  | n/a | inconsistent |

No cell cleared q ≤ 0.10. The holdout returns were not computed, because nothing had cleared training, and they were not used to rank the table.

Closest training cells:

- `SPY_5m_atr1_dip_m30`: n=696, reversal 53.7% versus random 48.9%, edge 0.04%, q=0.297.
- `QQQ_15m_rsi_dip_d5`: n=869, reversal 62.7% versus random 58.7%, edge 0.8%, q=0.779.
- `MSFT_1d_vwap_dip_d5`: n=49, reversal 63.3% versus random 53.1%, edge 2.0%, q=0.779.
- `MSTR_1d_gap_rip_d5`: n=38, reversal 42.1% versus random 63.2%, edge -4.0%, q=0.779.

No mean-reverting cell cleared the training bar, so no trade was built from these events.

Short Yahoo 5-minute sample, not a trial. Largest event counts:

| Stock | Event | Horizon | n | Reversal | Edge |
|---|---|---|---:|---:|---:|
| MSFT | vwap_rip | eod | 74 | 45.9% | 0.05% |
| AVGO | vwap_dip | d3 | 73 | 61.6% | 1.1% |
| AVGO | vwap_dip | eod | 73 | 53.4% | 0.09% |
| AVGO | vwap_dip | d1 | 73 | 38.4% | -0.18% |
| MSFT | vwap_rip | d1 | 73 | 39.7% | -0.37% |
| MSFT | vwap_rip | d3 | 73 | 24.7% | -1.3% |
| MSFT | vwap_rip | d5 | 72 | 18.1% | -1.6% |
| AMD | vwap_rip | eod | 71 | 50.7% | 0.15% |

Example chart `reports/tendency_unh.png`: last close 369.11, RSI 28.8, VWAP 372.12, lower band 368.87. A 2 SD dip printed on 3 bars and RSI below 30 on 2 bars. The session is partial.

The machine-readable summary is `reports/tendency.json`.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.

```
python3 -m webull_bot.chart_reads.research_tendency
```
<!-- TENDENCY_END -->
