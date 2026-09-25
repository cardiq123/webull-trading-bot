# Research results

Past simulated performance is not a prediction of future returns. No strategy in this system is guaranteed. Costs, slippage, and missing delistings can erase a paper edge.

Sample: daily bars from 2011 (indicators) with the scored out-of-sample window **2017-01-01** through **2026-09-25**. Starting equity $100,000. Webull commission $0. SEC Section 31 fee $20.60 per million dollars sold (the rate effective April 4, 2026, applied to the whole sample so earlier zero-fee years do not flatter results). FINRA TAF $0.000195 per share sold, capped at $9.79 (the 2026 statutory rate; the late-2026 TAF holiday is ignored). Slippage 5 bps and half-spread 1 bp per side. Position size risks 0.75% of equity per trade, capped at 20% of equity, with a 2% daily-loss flatten and a sticky 15% drawdown halt.

Walk-forward folds, each trained only on the window before it:

| Train | Test |
|---|---|
| 2013-01-01 to 2016-12-31 | 2017-01-01 to 2018-12-31 |
| 2015-01-01 to 2018-12-31 | 2019-01-01 to 2020-12-31 |
| 2017-01-01 to 2020-12-31 | 2021-01-01 to 2022-12-31 |
| 2019-01-01 to 2022-12-31 | 2023-01-01 to 2026-12-31 |

A strategy is marked as showing an out-of-sample edge only if the **default** parameters (not a mined neighbor) clear profit factor 1.10, Sharpe 0.40, 20 trades, and a drawdown no worse than -30% on 2017-onward data; the in-sample grid is not fragile; walk-forward choices do not flip the sign; the test universe is ETFs; and the result survives 15 bps of slippage. Stock-only runs are diagnostics. They use a 2026 list of survivors and cannot be the default book. Hourly tests use the free Yahoo limit of roughly two years and are never treated as a durable edge.

## Default-parameter out-of-sample results

| Strategy | CAGR | Total return | Win rate | Avg win | Avg loss | Profit factor | Expectancy | Max DD | Sharpe | Sortino | Exposure | Trades | Flags |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| gap_and_go (etf) | -0.00% | -0.04% | 0.00% | $0.00 | $-42.79 | 0.00 | $-42.79 | -0.04% | -0.32 | -0.32 | 0.00% | 1 | parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative |
| gap_and_go (stock) | -0.45% | -4.26% | 41.79% | $286.75 | $-315.19 | 0.65 | $-63.63 | -6.69% | -0.41 | -0.55 | 0.00% | 67 | survivorship_bias, parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, diagnostic_only |
| eod_mean_reversion (etf) | 0.47% | 4.63% | 54.58% | $259.71 | $-291.79 | 1.07 | $9.23 | -7.01% | 0.15 | 0.21 | 9.41% | 502 | oos_profit_factor_below_1_10, oos_sharpe_below_0_40 |
| eod_mean_reversion (stock) | 3.15% | 35.16% | 59.07% | $369.22 | $-437.85 | 1.22 | $38.90 | -9.64% | 0.61 | 0.90 | 13.50% | 904 | survivorship_bias, diagnostic_only |
| ema_pullback (etf) | 1.48% | 15.34% | 36.36% | $733.28 | $-378.43 | 1.11 | $25.83 | -14.35% | 0.26 | 0.35 | 48.13% | 594 | oos_sharpe_below_0_40 |
| ema_pullback (stock) | 6.16% | 78.80% | 35.53% | $1,407.32 | $-596.78 | 1.30 | $115.20 | -12.60% | 0.71 | 1.02 | 46.13% | 684 | survivorship_bias, diagnostic_only |
| vcp_breakout (etf) | 0.00% | 0.00% | 0.00% | $0.00 | $0.00 | n/a | $0.00 | 0.00% | 0.00 | 0.00 | 0.00% | 0 | parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40 |
| vcp_breakout (stock) | 0.00% | 0.00% | 0.00% | $0.00 | $0.00 | n/a | $0.00 | 0.00% | 0.00 | 0.00 | 0.00% | 0 | survivorship_bias, parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, sharpe_decay, diagnostic_only |
| connors_rsi2 (etf) | 0.22% | 2.16% | 60.21% | $192.47 | $-283.13 | 1.03 | $3.22 | -13.36% | 0.07 | 0.10 | 14.85% | 671 | parameter_fragile, oos_profit_factor_below_1_10, oos_sharpe_below_0_40, walk_forward_sign_flip |
| connors_rsi2 (stock) | 3.43% | 38.77% | 64.35% | $309.40 | $-455.19 | 1.23 | $36.85 | -12.70% | 0.60 | 0.85 | 17.48% | 1052 | survivorship_bias, diagnostic_only |
| rs_rotation (etf) | 0.07% | 0.71% | 48.98% | $257.66 | $-233.13 | 1.06 | $7.26 | -3.94% | 0.06 | 0.07 | 7.81% | 98 | oos_profit_factor_below_1_10, oos_sharpe_below_0_40 |
| rs_rotation (stock) | 3.70% | 42.46% | 52.08% | $973.09 | $-442.37 | 2.39 | $294.85 | -5.86% | 1.02 | 1.60 | 9.03% | 144 | survivorship_bias, diagnostic_only |
| dual_momentum (etf) | 0.45% | 4.43% | 54.84% | $405.42 | $-175.92 | 2.80 | $142.88 | -1.89% | 0.55 | 0.74 | 3.47% | 31 | — |
| opening_range_breakout (etf) | -0.79% | -0.78% | 31.25% | $62.01 | $-98.88 | 0.29 | $-48.60 | -0.82% | -1.88 | -2.05 | 0.57% | 16 | short_sample, insufficient_trades |
| opening_range_breakout (stock) | -2.79% | -2.75% | 34.78% | $180.30 | $-141.94 | 0.68 | $-29.86 | -3.63% | -1.43 | -1.94 | 3.54% | 92 | short_sample, survivorship_bias |
| vwap_pullback (etf) | -3.86% | -3.80% | 26.85% | $47.94 | $-52.50 | 0.34 | $-25.53 | -3.89% | -4.84 | -5.27 | 3.19% | 149 | short_sample |
| vwap_pullback (stock) | -10.85% | -10.70% | 29.83% | $133.51 | $-94.04 | 0.60 | $-26.16 | -10.99% | -3.48 | -4.26 | 8.51% | 409 | short_sample, survivorship_bias |

## Walk-forward (parameters chosen on each training window)

| Strategy | CAGR | Total return | Win rate | Avg win | Avg loss | Profit factor | Expectancy | Max DD | Sharpe | Sortino | Exposure | Trades | Flags |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| gap_and_go (etf) | -0.00% | -0.04% | 0.00% | $0.00 | $-42.79 | 0.00 | $-42.79 | -0.04% | -0.32 | -0.32 | 0.00% | 1 | — |
| gap_and_go (stock) | -0.11% | -1.05% | 46.00% | $304.48 | $-298.24 | 0.87 | $-20.98 | -3.60% | -0.11 | -0.17 | 0.00% | 50 | — |
| eod_mean_reversion (etf) | 0.05% | 0.49% | 54.24% | $249.47 | $-293.21 | 1.01 | $1.14 | -12.79% | 0.03 | 0.04 | 10.59% | 566 | — |
| eod_mean_reversion (stock) | 2.85% | 31.47% | 57.88% | $329.80 | $-387.22 | 1.17 | $27.79 | -11.61% | 0.52 | 0.76 | 14.96% | 1028 | — |
| ema_pullback (etf) | 0.80% | 8.05% | 34.05% | $637.22 | $-307.20 | 1.07 | $14.34 | -14.66% | 0.16 | 0.22 | 46.96% | 608 | — |
| ema_pullback (stock) | 10.70% | 168.80% | 43.52% | $1,109.65 | $-560.01 | 1.53 | $166.67 | -10.89% | 1.13 | 1.66 | 49.65% | 687 | — |
| vcp_breakout (etf) | 0.00% | 0.00% | 0.00% | $0.00 | $0.00 | n/a | $0.00 | 0.00% | 0.00 | 0.00 | 0.00% | 0 | — |
| vcp_breakout (stock) | 0.00% | 0.00% | 0.00% | $0.00 | $0.00 | n/a | $0.00 | 0.00% | 0.00 | 0.00 | 0.00% | 0 | — |
| connors_rsi2 (etf) | -0.51% | -4.84% | 57.46% | $206.78 | $-295.37 | 0.95 | $-6.82 | -16.83% | -0.09 | -0.12 | 15.38% | 717 | — |
| connors_rsi2 (stock) | 2.09% | 22.30% | 62.95% | $255.84 | $-379.40 | 1.15 | $20.48 | -12.68% | 0.39 | 0.54 | 17.18% | 1058 | — |
| rs_rotation (etf) | 0.19% | 1.91% | 55.21% | $236.69 | $-246.77 | 1.18 | $20.14 | -4.66% | 0.14 | 0.19 | 7.67% | 96 | — |
| rs_rotation (stock) | 4.17% | 48.80% | 54.49% | $779.80 | $-372.00 | 2.51 | $255.63 | -5.61% | 1.18 | 1.93 | 9.08% | 167 | — |
| dual_momentum (etf) | 0.71% | 7.14% | 59.09% | $295.26 | $-166.72 | 2.56 | $106.27 | -1.97% | 0.69 | 0.95 | 6.02% | 66 | — |

## Buy and hold SPY, same out-of-sample window

| Strategy | CAGR | Total return | Win rate | Avg win | Avg loss | Profit factor | Expectancy | Max DD | Sharpe | Sortino | Exposure | Trades | Flags |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SPY buy and hold | 15.26% | 298.25% | 100.00% | $298,248.07 | $0.00 | n/a | $298,248.07 | -33.72% | 0.88 | 1.24 | 100.00% | 1 | benchmark |

## What showed an edge

The default book is **dual_momentum**.
- **dual_momentum**: OOS CAGR 0.45%, total return 4.43%, win rate 54.84%, average win $405.42, average loss $-175.92, profit factor 2.80, expectancy $142.88, max drawdown -1.89%, Sharpe 0.55, Sortino 0.74, exposure 3.47%, trades 31.
  Source idea: Gary Antonacci, Dual Momentum Investing (2014); absolute and relative momentum
  Still profitable at 15 bps slippage (Sharpe 0.52, profit factor 2.62).

The selected account's out-of-sample CAGR was 0.45% with Sharpe 0.55, max drawdown -1.89%, and average exposure 3.47%. Buy-and-hold SPY over the same window was CAGR 15.26%, Sharpe 0.88, max drawdown -33.72%. Fixed-fractional sizing risks 0.75% of equity divided by the stop distance, then caps the position at 20% of equity. A wide trail therefore keeps most of the account in cash earning zero in this test. Sharpe is the risk-adjusted result of that mostly-cash book. Clearing the gates is not the same thing as beating buy-and-hold.

## What did not

- **gap_and_go (etf)**: parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative. OOS Sharpe -0.32, profit factor 0.00, trades 1, max drawdown -0.04%.
- **gap_and_go (stock)**: survivorship_bias, parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, diagnostic_only. OOS Sharpe -0.41, profit factor 0.65, trades 67, max drawdown -6.69%.
- **eod_mean_reversion (etf)**: oos_profit_factor_below_1_10, oos_sharpe_below_0_40. OOS Sharpe 0.15, profit factor 1.07, trades 502, max drawdown -7.01%.
- **eod_mean_reversion (stock)**: survivorship_bias, diagnostic_only. OOS Sharpe 0.61, profit factor 1.22, trades 904, max drawdown -9.64%.
- **ema_pullback (etf)**: oos_sharpe_below_0_40. OOS Sharpe 0.26, profit factor 1.11, trades 594, max drawdown -14.35%.
- **ema_pullback (stock)**: survivorship_bias, diagnostic_only. OOS Sharpe 0.71, profit factor 1.30, trades 684, max drawdown -12.60%.
- **vcp_breakout (etf)**: parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40. OOS Sharpe 0.00, profit factor n/a, trades 0, max drawdown 0.00%.
- **vcp_breakout (stock)**: survivorship_bias, parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, sharpe_decay, diagnostic_only. OOS Sharpe 0.00, profit factor n/a, trades 0, max drawdown 0.00%.
- **connors_rsi2 (etf)**: parameter_fragile, oos_profit_factor_below_1_10, oos_sharpe_below_0_40, walk_forward_sign_flip. OOS Sharpe 0.07, profit factor 1.03, trades 671, max drawdown -13.36%.
- **connors_rsi2 (stock)**: survivorship_bias, diagnostic_only. OOS Sharpe 0.60, profit factor 1.23, trades 1052, max drawdown -12.70%.
- **rs_rotation (etf)**: oos_profit_factor_below_1_10, oos_sharpe_below_0_40. OOS Sharpe 0.06, profit factor 1.06, trades 98, max drawdown -3.94%.
- **rs_rotation (stock)**: survivorship_bias, diagnostic_only. OOS Sharpe 1.02, profit factor 2.39, trades 144, max drawdown -5.86%.
- **opening_range_breakout (etf)**: short_sample, insufficient_trades. OOS Sharpe -1.88, profit factor 0.29, trades 16, max drawdown -0.82%.
- **opening_range_breakout (stock)**: short_sample, survivorship_bias. OOS Sharpe -1.43, profit factor 0.68, trades 92, max drawdown -3.63%.
- **vwap_pullback (etf)**: short_sample. OOS Sharpe -4.84, profit factor 0.34, trades 149, max drawdown -3.89%.
- **vwap_pullback (stock)**: short_sample, survivorship_bias. OOS Sharpe -3.48, profit factor 0.60, trades 409, max drawdown -10.99%.

## Combined portfolio

| Strategy | CAGR | Total return | Win rate | Avg win | Avg loss | Profit factor | Expectancy | Max DD | Sharpe | Sortino | Exposure | Trades | Flags |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| portfolio | 0.45% | 4.43% | 54.84% | $405.42 | $-175.92 | 2.80 | $142.88 | -1.89% | 0.55 | 0.74 | 3.47% | 31 | — |

The portfolio shares one account, so correlation and sector caps can reject a second signal the standalone test would have taken. That is intentional.

## Data limits

- Yahoo Finance daily bars, split- and dividend-adjusted. Not the consolidated tape.
- The stock universe is a 2026 survivor list. Edges that appear only there are biased upward.
- ETF results are the evidence used for selection. They still omit dead funds.
- Free intraday history is short: about 7 days of 1-minute bars, about 60 days of 5- and 15-minute bars, about 730 days of hourly bars.
- VIX and breadth are computed from this same file. Breadth is the fraction of the survivor stock list above its 50-day average, which overstates historical breadth.
