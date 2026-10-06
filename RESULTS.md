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

A strategy is marked as showing an out-of-sample edge only if the **default** parameters (not a mined neighbor) clear profit factor 1.10, Sharpe 0.40, 20 trades, and a drawdown no worse than -30% on 2017-onward data; the in-sample grid is not fragile; walk-forward choices do not flip the sign; the test universe is ETFs or point-in-time Dow membership; and the result survives 15 bps of slippage. A passing Dow book joins the default account only when its out-of-sample Sharpe beats dual momentum by at least 0.15. Otherwise it stays optional. Stock-only runs on the fixed 2026 survivor list are diagnostics and cannot be the default book. Hourly tests use the free Yahoo limit of roughly two years and are never treated as a durable edge.

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
| bluechip_reversal (dow) | -0.06% | -0.56% | 40.00% | $662.14 | $-627.93 | 0.70 | $-111.91 | -2.07% | -0.13 | -0.17 | 0.26% | 5 | parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, sharpe_decay, cost_fragile |
| support_reversal (dow) | 2.40% | 25.97% | 42.28% | $717.03 | $-471.81 | 1.11 | $30.84 | -15.43% | 0.35 | 0.51 | 25.85% | 842 | parameter_fragile, oos_sharpe_below_0_40 |
| wedge_breakout (dow) | -0.31% | -2.98% | 54.36% | $224.79 | $-274.15 | 0.98 | $-2.95 | -10.10% | -0.06 | -0.07 | 18.83% | 1010 | parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, sharpe_decay |

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
| bluechip_reversal (dow) | 2.90% | 32.07% | 56.98% | $423.95 | $-453.24 | 1.24 | $46.62 | -10.72% | 0.59 | 0.85 | 20.55% | 630 | — |
| support_reversal (dow) | 0.64% | 6.45% | 45.49% | $484.48 | $-384.32 | 1.05 | $10.94 | -12.68% | 0.14 | 0.20 | 20.49% | 677 | — |
| wedge_breakout (dow) | 1.16% | 11.89% | 42.70% | $176.79 | $-107.41 | 1.23 | $13.95 | -3.34% | 0.57 | 0.82 | 10.58% | 829 | — |

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
- **bluechip_reversal (dow)**: parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, sharpe_decay, cost_fragile. OOS Sharpe -0.13, profit factor 0.70, trades 5, max drawdown -2.07%.
- **support_reversal (dow)**: parameter_fragile, oos_sharpe_below_0_40. OOS Sharpe 0.35, profit factor 1.11, trades 842, max drawdown -15.43%.
- **wedge_breakout (dow)**: parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, sharpe_decay. OOS Sharpe -0.06, profit factor 0.98, trades 1010, max drawdown -10.10%.

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

## Blue-chip reversal (Dow 30, point in time)

Universe: historical Dow Jones Industrial Average membership, effective-dated from the public component changes (Wikipedia, Historical components of the Dow Jones Industrial Average, summary since 1991). A name is eligible only while it is in the index, including names that were later removed. This is not the 2026 survivor list.

Signal, pre-registered: confirmed 5/5 swing low or a 1.5% tag of the 200-day EMA, RSI(2) < 10 within three sessions, RSI(14) bullish divergence, then a 10-day EMA reclaim. Stop is the swing low minus 0.25 ATR. Target is the last confirmed swing high. Time stop is 15 sessions. Fill is the next open. The grid is six variants (RSI(14)<30, RSI(5)<15, anchored-VWAP reclaim, trend filter on, divergence off) and was not a cartesian search. The gate uses the default parameters, not the best cell.

Options are a model. Premiums are Black-Scholes with 20-day realized volatility times 1.15, rate 2%, dividend yield 1.8%, 45 calendar days, long strike near 0.65 delta, short strike near 0.40 delta, half-spread 4% of the mid (8% below 0.50 delta), and the Webull equity-option fee schedule in `options/fees.py`. There is no historical option chain. Early assignment is not modeled. A profitable options column does not pass the gate.

| Book | Window | CAGR | Total return | Win rate | Profit factor | Max DD | Sharpe | Exposure | Trades | Avg hold |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Stock, default params | 2013-2016 earlier sample | 0.00% | 0.00% | 0.00% | n/a | 0.00% | 0.00 | 0.00% | 0 | n/a |
| Stock, default params | 2017-2026 out of sample | -0.06% | -0.56% | 40.00% | 0.70 | -2.07% | -0.13 | 0.26% | 5 | 7.0 |
| Stock, walk-forward | stitched OOS folds | 2.90% | 32.07% | 56.98% | 1.24 | -10.72% | 0.59 | 20.55% | 630 | 5.8 |
| Stock, 15 bps slippage | 2017-2026 out of sample | -0.08% | -0.76% | 40.00% | 0.62 | -2.15% | -0.17 | 0.26% | 5 | n/a |
| Long call, IV 1.15x | 2017-2026 out of sample | -0.06% | -0.38% | 50.00% | 0.69 | -1.26% | -0.17 | 0.02% | 4 | 6.5 |
| Long call, IV 1.15x | walk-forward trades | -2.48% | -21.70% | 49.38% | 0.79 | -23.43% | -0.52 | 1.41% | 482 | 5.7 |
| Long call, IV 1.15x | 2013-2016 earlier sample | 0.00% | 0.00% | 0.00% | n/a | 0.00% | 0.00 | 0.00% | 0 | 0.0 |
| Bull call spread, IV 1.15x | 2017-2026 out of sample | -0.24% | -1.60% | 20.00% | 0.09 | -1.92% | -0.67 | 0.02% | 5 | 7.0 |
| Bull call spread, IV 1.15x | walk-forward trades | -11.37% | -69.08% | 23.40% | 0.13 | -69.13% | -3.48 | 1.33% | 453 | 5.7 |
| Bull call spread, IV 1.15x | 2013-2016 earlier sample | 0.00% | 0.00% | 0.00% | n/a | 0.00% | 0.00 | 0.00% | 0 | 0.0 |
| Long call, IV 1.00x | 2017-2026 sensitivity | -0.16% | -1.07% | 50.00% | 0.44 | -1.96% | -0.34 | 0.02% | 4 | 6.5 |
| Long call, IV 1.30x | 2017-2026 sensitivity | -0.07% | -0.46% | 50.00% | 0.64 | -1.31% | -0.21 | 0.02% | 4 | 6.5 |
| Long call, 2x spread | 2017-2026 sensitivity | -0.11% | -0.72% | 50.00% | 0.46 | -1.42% | -0.32 | 0.02% | 4 | 6.5 |
| Bull call spread, IV 1.00x | 2017-2026 sensitivity | -0.28% | -1.87% | 20.00% | 0.10 | -2.31% | -0.65 | 0.03% | 5 | 7.0 |
| Bull call spread, IV 1.30x | 2017-2026 sensitivity | -0.23% | -1.57% | 20.00% | 0.10 | -1.91% | -0.71 | 0.02% | 5 | 7.0 |
| Bull call spread, 2x spread | 2017-2026 sensitivity | -0.38% | -2.59% | 0.00% | 0.00 | -2.70% | -0.93 | 0.02% | 5 | 7.0 |
| SPY buy and hold | 2017-2026 | 15.26% | 298.25% | 100.00% | n/a | -33.72% | 0.88 | 100.00% | 1 | n/a |

Stock out-of-sample flags: parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, sharpe_decay, cost_fragile.
Gate result: **DOES NOT PASS the out-of-sample gates. Not in the default book and not optional. Modeled option profits are not a separate pass.**

Option sizing risks 1.5% of equity as the debit (the middle of the 1–2% request). The stock book still uses the system's 0.75% stop-distance sizing, five-position cap, sector cap, and correlation cap. Average hold is sessions in the trade.

Dow names with no Yahoo history in this run, so those membership days are absent: DWDP, KFT, WBA. UTX is not in that list because Yahoo has no UTX file and the study reuses the RTX series for the pre-2020 United Technologies window. That splice is a data caveat, not a second listing.

## Support reversal and wedge breakout (Dow 30, point in time)

Both books use effective-dated Dow membership. The gate scores the pre-registered default, not the best of the six variants. Walk-forward picks the stock-signal variant on the training window only. DTE, delta, the +30% premium target, and the -50% premium stop are fixed. Option prices are a Black-Scholes estimate: 20-day realized volatility times the stated premium, rate 2%, dividend yield 1.8%, half-spread 4% of the mid at these deltas, and the Webull option fee schedule. The favorable extreme is the underlying high for calls and the low for puts. If that bar could also have hit the premium stop, the stop fills. A target fills at +30% of the ask that was paid, not at the overshoot. There is no historical option chain.

| Book | Window | CAGR | Total | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Exposure | Trades | Avg hold | +30% hit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Dual momentum | 2017-2026 out of sample | 0.45% | 4.43% | 54.84% | $405 | $-176 | $143 | 2.80 | -1.89% | 0.55 | 3.47% | 31 | n/a | n/a |
| SPY buy and hold | 2017-2026 | 15.26% | 298.25% | 100.00% | $298248 | $0 | $298248 | n/a | -33.72% | 0.88 | 100.00% | 1 | n/a | n/a |

### support_reversal

| Book | Window | CAGR | Total | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Exposure | Trades | Avg hold | +30% hit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Long stock, default | 2013-2016 earlier sample | 0.86% | 3.49% | 42.89% | $447 | $-323 | $8 | 1.04 | -10.40% | 0.16 | 34.55% | 464 | 4.4 | n/a |
| Long stock, default | 2017-2026 out of sample | 2.40% | 25.97% | 42.28% | $717 | $-472 | $31 | 1.11 | -15.43% | 0.35 | 25.85% | 842 | 4.5 | n/a |
| Long stock, walk-forward | stitched OOS folds | 0.64% | 6.45% | 45.49% | $484 | $-384 | $11 | 1.05 | -12.68% | 0.14 | 20.49% | 677 | 4.5 | n/a |
| Long stock, 15 bps slippage | 2017-2026 out of sample | 0.25% | 2.49% | 42.38% | $603 | $-437 | $4 | 1.01 | -15.44% | 0.07 | 21.49% | 689 | n/a | n/a |
| Short stock, default | 2017-2026 out of sample | 0.00% | 0.00% | 0.00% | $0 | $0 | $0 | n/a | 0.00% | 0.00 | 0.00% | 0 | n/a | n/a |
| Short stock, walk-forward | stitched OOS folds | 0.00% | 0.00% | 0.00% | $0 | $0 | $0 | n/a | 0.00% | 0.00 | 0.00% | 0 | n/a | n/a |
| Short stock, default | 2013-2016 earlier sample | 0.00% | 0.00% | 0.00% | $0 | $0 | $0 | n/a | 0.00% | 0.00 | 0.00% | 0 | n/a | n/a |
| Options, default +30% target | 2017-2026 out of sample | -1.01% | -14.79% | 44.09% | $375 | $-580 | $-159 | 0.51 | -15.38% | -0.64 | 0.11% | 93 | 3.6 | 40.86% |
| Options, walk-forward signals | stitched OOS folds | -3.93% | -46.81% | 41.62% | $334 | $-509 | $-158 | 0.47 | -46.81% | -0.35 | 0.00% | 370 | 3.5 | 38.38% |
| Options, default +30% target | 2013-2016 earlier sample | -0.92% | -13.52% | 45.28% | $411 | $-574 | $-128 | 0.59 | -15.42% | -0.50 | 0.10% | 106 | 2.9 | 45.28% |
| Calls only | 2017-2026 out of sample | -1.01% | -14.79% | 44.09% | $375 | $-580 | $-159 | 0.51 | -15.38% | -0.64 | 0.11% | 93 | 3.6 | 40.86% |
| Calls, walk-forward signals | stitched OOS folds | -3.93% | -46.81% | 41.62% | $334 | $-509 | $-158 | 0.47 | -46.81% | -0.35 | 0.00% | 370 | 3.5 | 38.38% |
| Puts only | 2017-2026 out of sample | 0.00% | 0.00% | 0.00% | $0 | $0 | $0 | n/a | 0.00% | 0.00 | 0.00% | 0 | 0.0 | 0.00% |
| Puts, walk-forward signals | stitched OOS folds | 0.00% | 0.00% | 0.00% | $0 | $0 | $0 | n/a | 0.00% | 0.00 | 0.00% | 0 | n/a | 0.00% |
| Options, close-based marks | 2017-2026 sensitivity | -1.02% | -14.85% | 45.30% | $347 | $-520 | $-127 | 0.55 | -15.52% | -0.55 | 0.18% | 117 | 4.7 | 38.46% |
| Options, 21 DTE | 2017-2026 sensitivity | -0.94% | -13.85% | 48.28% | $373 | $-655 | $-159 | 0.53 | -14.87% | -0.56 | 0.08% | 87 | 3.0 | 44.83% |
| Options, 45 DTE | 2017-2026 sensitivity | -1.04% | -15.20% | 50.20% | $339 | $-462 | $-60 | 0.74 | -15.61% | -0.45 | 0.31% | 255 | 3.9 | 45.10% |
| Options, 0.50 delta | 2017-2026 sensitivity | -1.10% | -16.02% | 43.28% | $377 | $-709 | $-239 | 0.41 | -16.25% | -0.71 | 0.06% | 67 | 2.9 | 38.81% |
| Options, premium stop -30% | 2017-2026 sensitivity | -1.06% | -15.44% | 36.67% | $357 | $-478 | $-172 | 0.43 | -15.44% | -0.79 | 0.06% | 90 | 2.3 | 33.33% |
| Options, IV 1.00x | 2017-2026 sensitivity | -0.98% | -14.39% | 45.24% | $373 | $-621 | $-171 | 0.50 | -15.03% | -0.62 | 0.09% | 84 | 3.2 | 41.67% |
| Options, IV 1.30x | 2017-2026 sensitivity | -1.01% | -14.78% | 51.23% | $344 | $-485 | $-61 | 0.74 | -15.10% | -0.43 | 0.26% | 244 | 3.6 | 46.72% |
| Options, 2x bid/ask | 2017-2026 sensitivity | -1.03% | -15.09% | 35.94% | $366 | $-573 | $-236 | 0.36 | -15.82% | -0.73 | 0.08% | 64 | 3.8 | 34.38% |

Long-stock flags: parameter_fragile, oos_sharpe_below_0_40.
Gate result: **DOES NOT PASS the out-of-sample gates. Not in the default book and not optional. The option column is an estimate and is not a separate pass.**
Default option book +30% target hit rate: 40.86%.

### wedge_breakout

| Book | Window | CAGR | Total | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Exposure | Trades | Avg hold | +30% hit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Long stock, default | 2013-2016 earlier sample | 1.54% | 6.29% | 58.21% | $243 | $-302 | $15 | 1.12 | -8.98% | 0.40 | 24.56% | 414 | 4.9 | n/a |
| Long stock, default | 2017-2026 out of sample | -0.31% | -2.98% | 54.36% | $225 | $-274 | $-3 | 0.98 | -10.10% | -0.06 | 18.83% | 1010 | 4.6 | n/a |
| Long stock, walk-forward | stitched OOS folds | 1.16% | 11.89% | 42.70% | $177 | $-107 | $14 | 1.23 | -3.34% | 0.57 | 10.58% | 829 | 5.7 | n/a |
| Long stock, 15 bps slippage | 2017-2026 out of sample | -1.57% | -14.29% | 50.75% | $191 | $-260 | $-31 | 0.76 | -15.80% | -0.56 | 9.51% | 465 | n/a | n/a |
| Short stock, default | 2017-2026 out of sample | -15.27% | -80.04% | 40.00% | $99 | $-194 | $-77 | 0.34 | -80.04% | -0.32 | 0.09% | 5 | 3.2 | n/a |
| Short stock, walk-forward | stitched OOS folds | -10.54% | -66.14% | 46.15% | $116 | $-133 | $-18 | 0.74 | -66.22% | -0.70 | 0.00% | 13 | 4.6 | n/a |
| Short stock, default | 2013-2016 earlier sample | -11.81% | -39.47% | 0.00% | $0 | $-299 | $-299 | 0.00 | -39.48% | -0.51 | 0.24% | 3 | 7.0 | n/a |
| Options, default +30% target | 2017-2026 out of sample | -0.92% | -13.58% | 49.52% | $375 | $-625 | $-129 | 0.59 | -15.44% | -0.54 | 0.14% | 105 | 4.0 | 45.71% |
| Options, walk-forward signals | stitched OOS folds | -4.04% | -47.75% | 41.32% | $342 | $-433 | $-113 | 0.56 | -47.75% | -0.36 | 0.00% | 530 | 2.8 | 39.06% |
| Options, default +30% target | 2013-2016 earlier sample | -1.05% | -15.32% | 50.35% | $377 | $-598 | $-107 | 0.64 | -15.42% | -0.48 | 0.17% | 143 | 3.7 | 47.55% |
| Calls only | 2017-2026 out of sample | -0.82% | -12.17% | 55.56% | $392 | $-692 | $-90 | 0.71 | -16.52% | -0.37 | 0.15% | 135 | 3.4 | 52.59% |
| Calls, walk-forward signals | stitched OOS folds | -3.48% | -42.74% | 45.88% | $348 | $-445 | $-81 | 0.66 | -43.01% | -0.36 | 0.00% | 643 | 2.9 | 43.86% |
| Puts only | 2017-2026 out of sample | -1.09% | -15.78% | 34.48% | $384 | $-617 | $-272 | 0.33 | -15.78% | -0.88 | 0.08% | 58 | 4.1 | 32.76% |
| Puts, walk-forward signals | stitched OOS folds | -4.11% | -48.34% | 33.16% | $327 | $-404 | $-161 | 0.40 | -48.34% | -0.36 | 0.00% | 377 | 2.7 | 31.03% |
| Options, close-based marks | 2017-2026 sensitivity | -1.06% | -15.48% | 41.58% | $358 | $-517 | $-153 | 0.49 | -15.68% | -0.65 | 0.17% | 101 | 5.2 | 35.64% |
| Options, 21 DTE | 2017-2026 sensitivity | -1.05% | -15.24% | 50.00% | $391 | $-702 | $-156 | 0.56 | -15.40% | -0.65 | 0.10% | 98 | 3.0 | 48.98% |
| Options, 45 DTE | 2017-2026 sensitivity | -1.09% | -15.81% | 40.40% | $355 | $-509 | $-160 | 0.47 | -15.81% | -0.69 | 0.17% | 99 | 5.3 | 35.35% |
| Options, 0.50 delta | 2017-2026 sensitivity | -1.03% | -15.03% | 44.93% | $405 | $-726 | $-218 | 0.45 | -15.03% | -0.62 | 0.07% | 69 | 3.1 | 43.48% |
| Options, premium stop -30% | 2017-2026 sensitivity | -1.03% | -15.06% | 39.39% | $373 | $-494 | $-152 | 0.49 | -15.33% | -0.65 | 0.07% | 99 | 2.4 | 38.38% |
| Options, IV 1.00x | 2017-2026 sensitivity | -1.11% | -16.13% | 48.28% | $396 | $-639 | $-139 | 0.58 | -16.51% | -0.64 | 0.13% | 116 | 3.5 | 47.41% |
| Options, IV 1.30x | 2017-2026 sensitivity | -1.07% | -15.57% | 44.00% | $353 | $-555 | $-156 | 0.50 | -15.93% | -0.65 | 0.15% | 100 | 4.7 | 39.00% |
| Options, 2x bid/ask | 2017-2026 sensitivity | -1.10% | -15.99% | 38.10% | $362 | $-633 | $-254 | 0.35 | -15.99% | -0.71 | 0.09% | 63 | 4.5 | 34.92% |

Long-stock flags: parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, sharpe_decay.
Gate result: **DOES NOT PASS the out-of-sample gates. Not in the default book and not optional. The option column is an estimate and is not a separate pass.**
Default option book +30% target hit rate: 45.71%.

<!-- FANATICS_START -->
## Chart Fanatics specs

Eight rules from the digest, scored on the pre-registered default. Walk-forward may leave that default; the gate does not. Under 300 out-of-sample trades the verdict is inconclusive. Crypto and CFD results are proxies. Yahoo NQ=F, ES=F, and GC=F are exchange symbols. Option orders were not sent. Live orders were not sent.

Dual momentum out-of-sample Sharpe on the existing book is 0.55. SPY buy-and-hold over 2017-01-01 through 2026-09-30 was CAGR 13.33% and Sharpe 0.78.

| Spec | Sample | OOS window | Trades | IS Sharpe | OOS Sharpe | WF Sharpe | Win rate | Avg R | Expectancy | PF | Max DD | Verdict |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 3 | BTC and ETH 5-minute, Binance spot | 2022-01-01 to 2026-09-30 | 0 | -1.04 | 0.00 | -0.68 | 0.0% | 0.000 | $0 | n/a | 0.0% | inconclusive |
| 8 | SPY and QQQ daily, close to next open | 2017-01-01 to 2026-09-30 | 2448 | -1.96 | -1.54 | -0.51 | 46.4% | -0.001 | $-35 | 0.71 | -85.6% | no edge |
| 2 | PAXG 30-minute, Binance gold proxy | 2023-01-01 to 2026-09-30 | 5 | -0.77 | -0.04 | -0.28 | 20.0% | -0.187 | $-29 | 0.88 | -1.3% | inconclusive |
| 4 | BTC and ETH resampled, Binance | 2022-01-01 to 2026-09-30 | 522 | -2.02 | -2.98 | -0.76 | 30.8% | -0.501 | $-114 | 0.41 | -60.0% | no edge |
| 6 | NQ=F and ES=F 5-minute, Yahoo about 60 days | 2026-08-27 to 2026-10-01 | 5 | -3.07 | -5.08 | -5.08 | 20.0% | -0.786 | $-276 | 0.13 | -1.4% | inconclusive |
| 1 | BTC and ETH 5-minute, Binance spot | 2022-01-01 to 2026-09-30 | 555 | -2.39 | -3.18 | -1.54 | 24.1% | -1.184 | $-120 | 0.40 | -67.8% | no edge |
| 5 | BTC and ETH 5-minute, Binance spot | 2022-01-01 to 2026-09-30 | 142 | -4.35 | -2.68 | -0.95 | 11.3% | -3.163 | $-183 | 0.18 | -27.0% | inconclusive |
| 7 | BTC and ETH 5-minute, Binance spot | 2022-01-01 to 2026-09-30 | 7 | -3.84 | -1.00 | -0.74 | 0.0% | -10.403 | $-187 | 0.00 | -1.3% | inconclusive |

### Spec 1: no edge

BTC and ETH 5-minute, Binance spot. Proxy.
Bars on disk: 2017-12-31 19:00:00-05:00 to 2026-09-30 19:45:00-04:00.
In-sample: CAGR -18.86%, total -56.65%, win 24.7%, avg R -0.918, expectancy $-114, PF 0.48, max DD -59.64%, Sharpe -2.39, trades 497.
Out of sample, default parameters: CAGR -20.65%, total -66.65%, win 24.1%, avg R -1.184, expectancy $-120, PF 0.40, max DD -67.80%, Sharpe -3.18, trades 555.
Walk-forward: CAGR -19.74%, total -71.75%, win 25.5%, avg R -1.054, expectancy $-143, PF 0.50, max DD -72.12%, Sharpe -1.54, trades 748.
Random-entry baseline, same stops and clock: CAGR -15.08%, total -53.96%, win 26.8%, avg R -0.935, expectancy $-97, PF 0.58, max DD -57.96%, Sharpe -1.96, trades 557.
Cost stress (stop slippage at the high end (2 extra ticks)): CAGR -20.66%, total -66.68%, win 24.1%, avg R -1.185, expectancy $-120, PF 0.40, max DD -67.83%, Sharpe -3.18, trades 555.
That is no edge on this proxy. It is not a verdict on the NQ or ES rule.
Flags: parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30.
By year (5 of 5 negative): 2022 123 trades avg R -0.88, 2023 119 trades avg R -1.44, 2024 134 trades avg R -1.21, 2025 101 trades avg R -1.29, 2026 78 trades avg R -1.08.

### Spec 2: inconclusive

PAXG 30-minute, Binance gold proxy. Proxy.
Bars on disk: 2020-08-28 08:00:00-04:00 to 2026-09-30 19:30:00-04:00.
In-sample: CAGR -0.26%, total -0.61%, win 0.0%, avg R -2.926, expectancy $-305, PF 0.00, max DD -0.61%, Sharpe -0.77, trades 2.
Out of sample, default parameters: CAGR -0.04%, total -0.15%, win 20.0%, avg R -0.187, expectancy $-29, PF 0.88, max DD -1.25%, Sharpe -0.04, trades 5.
Walk-forward: CAGR -0.20%, total -1.15%, win 12.5%, avg R -1.086, expectancy $-144, PF 0.49, max DD -2.24%, Sharpe -0.28, trades 8.
Random-entry baseline, same stops and clock: CAGR -0.32%, total -1.21%, win 20.0%, avg R -1.313, expectancy $-242, PF 0.04, max DD -1.21%, Sharpe -0.76, trades 5.
Cost stress (stop slippage at the high end (2 extra ticks)): CAGR -0.04%, total -0.15%, win 20.0%, avg R -0.189, expectancy $-29, PF 0.88, max DD -1.25%, Sharpe -0.05, trades 5.
Flags: parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, anecdotal_sample.
By year (2 of 3 negative): 2024 1 trades avg R -2.05, 2025 2 trades avg R -1.36, 2026 2 trades avg R 1.91.

### Spec 3: inconclusive

BTC and ETH 5-minute, Binance spot. Proxy.
Bars on disk: 2017-12-31 19:00:00-05:00 to 2026-09-30 19:55:00-04:00.
In-sample: CAGR -0.49%, total -1.96%, win 18.2%, avg R -1.860, expectancy $-178, PF 0.11, max DD -1.96%, Sharpe -1.04, trades 11.
Out of sample, default parameters: CAGR 0.00%, total 0.00%, win 0.0%, avg R 0.000, expectancy $0, PF n/a, max DD 0.00%, Sharpe 0.00, trades 0.
Walk-forward: CAGR -0.08%, total -0.25%, win 0.0%, avg R -5.532, expectancy $-127, PF 0.00, max DD -0.25%, Sharpe -0.68, trades 2.
Random-entry baseline, same stops and clock: CAGR 0.00%, total 0.00%, win 0.0%, avg R 0.000, expectancy $0, PF n/a, max DD 0.00%, Sharpe 0.00, trades 0.
Cost stress (stop slippage at the high end (2 extra ticks)): CAGR 0.00%, total 0.00%, win 0.0%, avg R 0.000, expectancy $0, PF n/a, max DD 0.00%, Sharpe 0.00, trades 0.
Flags: parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, anecdotal_sample.

### Spec 4: no edge

BTC and ETH resampled, Binance. Proxy.
Bars on disk: 2017-12-31 19:00:00-05:00 to 2026-09-30 19:00:00-04:00.
In-sample: CAGR -12.19%, total -40.54%, win 35.2%, avg R -0.305, expectancy $-95, PF 0.51, max DD -40.76%, Sharpe -2.02, trades 426.
Out of sample, default parameters: CAGR -17.41%, total -59.67%, win 30.8%, avg R -0.501, expectancy $-114, PF 0.41, max DD -59.96%, Sharpe -2.98, trades 522.
Walk-forward: CAGR -1.97%, total -10.82%, win 46.9%, avg R -0.200, expectancy $-78, PF 0.62, max DD -13.26%, Sharpe -0.76, trades 143.
Random-entry baseline, same stops and clock: CAGR -16.75%, total -58.11%, win 29.9%, avg R -0.517, expectancy $-112, PF 0.40, max DD -58.11%, Sharpe -2.92, trades 519.
Cost stress (stop slippage at the high end (2 extra ticks)): CAGR -17.42%, total -59.69%, win 30.8%, avg R -0.501, expectancy $-114, PF 0.41, max DD -59.97%, Sharpe -2.98, trades 522.
That is no edge on this proxy. It is not a verdict on the NQ or ES rule.
Flags: parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30.
By year (5 of 5 negative): 2022 107 trades avg R -0.21, 2023 137 trades avg R -0.59, 2024 117 trades avg R -0.47, 2025 91 trades avg R -0.51, 2026 70 trades avg R -0.81.

### Spec 5: inconclusive

BTC and ETH 5-minute, Binance spot. Proxy.
Bars on disk: 2017-12-31 19:00:00-05:00 to 2026-09-30 19:55:00-04:00.
In-sample: CAGR -19.56%, total -58.13%, win 18.6%, avg R -2.230, expectancy $-140, PF 0.25, max DD -58.13%, Sharpe -4.35, trades 415.
Out of sample, default parameters: CAGR -6.14%, total -25.97%, win 11.3%, avg R -3.163, expectancy $-183, PF 0.18, max DD -26.98%, Sharpe -2.68, trades 142.
Walk-forward: CAGR -1.27%, total -7.11%, win 18.6%, avg R -1.694, expectancy $-170, PF 0.25, max DD -7.70%, Sharpe -0.95, trades 43.
Random-entry baseline, same stops and clock: CAGR -5.76%, total -24.54%, win 12.0%, avg R -3.340, expectancy $-173, PF 0.17, max DD -24.54%, Sharpe -2.80, trades 142.
Cost stress (stop slippage at the high end (2 extra ticks)): CAGR -6.15%, total -26.00%, win 11.3%, avg R -3.168, expectancy $-183, PF 0.18, max DD -27.02%, Sharpe -2.68, trades 142.
Flags: parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, anecdotal_sample.
By year (5 of 5 negative): 2022 27 trades avg R -2.64, 2023 47 trades avg R -3.18, 2024 19 trades avg R -3.32, 2025 20 trades avg R -4.03, 2026 29 trades avg R -2.93.

### Spec 6: inconclusive

NQ=F and ES=F 5-minute, Yahoo about 60 days.
Bars on disk: 2026-07-23 00:05:00-04:00 to 2026-10-01 15:10:00-04:00.
In-sample: CAGR -7.61%, total -0.78%, win 40.0%, avg R -0.368, expectancy $-156, PF 0.23, max DD -0.92%, Sharpe -3.07, trades 5.
Out of sample, default parameters: CAGR -13.13%, total -1.38%, win 20.0%, avg R -0.786, expectancy $-276, PF 0.13, max DD -1.38%, Sharpe -5.08, trades 5.
Walk-forward: CAGR -13.13%, total -1.38%, win 20.0%, avg R -0.786, expectancy $-276, PF 0.13, max DD -1.38%, Sharpe -5.08, trades 5.
Random-entry baseline, same stops and clock: CAGR 5.96%, total 0.57%, win 80.0%, avg R 0.454, expectancy $114, PF 2.23, max DD -0.46%, Sharpe 2.28, trades 5.
Cost stress (stop slippage at the high end (2 extra ticks)): CAGR -13.80%, total -1.45%, win 20.0%, avg R -0.827, expectancy $-291, PF 0.13, max DD -1.45%, Sharpe -5.12, trades 5.
Flags: short_sample, parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, anecdotal_sample.
By year (1 of 1 negative): 2026 5 trades avg R -0.79.

### Spec 7: inconclusive

BTC and ETH 5-minute, Binance spot. Proxy.
Bars on disk: 2017-12-31 19:00:00-05:00 to 2026-09-30 19:55:00-04:00.
In-sample: CAGR -9.64%, total -33.35%, win 21.1%, avg R -1.568, expectancy $-176, PF 0.17, max DD -33.35%, Sharpe -3.84, trades 190.
Out of sample, default parameters: CAGR -0.28%, total -1.31%, win 0.0%, avg R -10.403, expectancy $-187, PF 0.00, max DD -1.31%, Sharpe -1.00, trades 7.
Walk-forward: CAGR -0.22%, total -1.23%, win 0.0%, avg R -9.931, expectancy $-206, PF 0.00, max DD -1.23%, Sharpe -0.74, trades 6.
Random-entry baseline, same stops and clock: CAGR -0.29%, total -1.39%, win 0.0%, avg R -10.559, expectancy $-198, PF 0.00, max DD -1.39%, Sharpe -1.00, trades 7.
Cost stress (stop slippage at the high end (2 extra ticks)): CAGR -0.28%, total -1.31%, win 0.0%, avg R -10.425, expectancy $-187, PF 0.00, max DD -1.31%, Sharpe -1.00, trades 7.
Flags: parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, anecdotal_sample.
By year (3 of 3 negative): 2022 1 trades avg R -10.69, 2023 5 trades avg R -10.06, 2026 1 trades avg R -11.82.

### Spec 8: no edge

SPY and QQQ daily, close to next open.
In-sample: CAGR -21.57%, total -98.39%, win 43.2%, avg R -0.001, expectancy $-23, PF 0.74, max DD -98.54%, Sharpe -1.96, trades 4276.
Out of sample, default parameters: CAGR -17.99%, total -85.51%, win 46.4%, avg R -0.001, expectancy $-35, PF 0.71, max DD -85.64%, Sharpe -1.54, trades 2448.
Walk-forward: CAGR -5.85%, total -44.41%, win 48.4%, avg R -0.001, expectancy $-65, PF 0.83, max DD -50.87%, Sharpe -0.51, trades 777.
Random half of the same overnight days (seed 7): CAGR -12.95%, total -74.10%, win 44.3%, avg R -0.001, expectancy $-60, PF 0.65, max DD -74.15%, Sharpe -1.50, trades 1227. That subsample estimates the same mean, so a tie on average R is not treated as a missing edge. The comparison is the intraday leg, buy-and-hold, and the gates.
The gross overnight mean below is positive. The traded book pays 5 bps of slippage and 1 bp of half-spread on the entry and again on the exit, about 12 bps round trip before the SEC and FINRA fees. That cost is larger than the 2 to 4 bp drift, which is why the account loses money.
Cost stress (15 bps slippage): CAGR -38.31%, total -99.10%, win 22.6%, avg R -0.002, expectancy $-40, PF 0.23, max DD -99.13%, Sharpe -4.51, trades 2448.
Flags: parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30.
By year (10 of 10 negative): 2017 250 trades avg R -0.00, 2018 251 trades avg R -0.00, 2019 252 trades avg R -0.00, 2020 253 trades avg R -0.00, 2021 252 trades avg R -0.00, 2022 251 trades avg R -0.00, 2023 250 trades avg R -0.00, 2024 252 trades avg R -0.00, 2025 250 trades avg R -0.00, 2026 187 trades avg R -0.00.
spy_full: overnight mean 0.0228% (t 2.66, n 6725), intraday mean 0.0088% (t 0.74, n 6726).
qqq_full: overnight mean 0.0442% (t 4.04, n 6725), intraday mean 0.0005% (t 0.03, n 6726).
spy_2008: overnight mean -0.0593% (t -0.67, n 252), intraday mean -0.1004% (t -0.76, n 253).
spy_2020: overnight mean 0.0566% (t 0.58, n 252), intraday mean 0.0205% (t 0.27, n 253).
spy_2022: overnight mean -0.0611% (t -1.11, n 250), intraday mean -0.0149% (t -0.19, n 251).
spy_vix_below_20: overnight mean -0.0218% (t -1.93, n 4170), intraday mean 0.0658% (t 7.48, n 4171).
spy_vix_at_least_20: overnight mean 0.1697% (t 5.12, n 2554), intraday mean -0.0843% (t -3.05, n 2555).

Tick caps are exchange ticks. On BTC and ETH a tick is $0.01, so a 40-tick skip is $0.40 and rejects ordinary sweeps. Those crypto rows do not test the NQ rule; the Yahoo NQ=F and ES=F window is the exchange-tick sample, and it is short. Value areas are built from 5-minute bars, which is coarser than a 1-minute profile. Spec 4 does not search the VPE-trend pullback to the point of control; that clause was not in the pre-registered grid. Spec 5 only pairs an engineered swing with an earlier swing inside 300 bars, an implementation bound so two highs years apart are not a setup. Yahoo NQ=F, ES=F, and GC=F are continuous rolls, not a back-adjusted research series. Dukascopy publishes free 1-minute bid candles, and a pull was started, but the host answered with timeouts and HTTP 503s after a few hundred files from 2013. That prefix is not the scored sample. A multi-year CME 1-minute archive, plus trades with aggressor side for the order-flow filters, is what would make specs 1, 3, 5, 6, and 7 conclusive on NQ and ES. Databento's historical CME ohlcv-1m product is the practical source; their public calculator prices a few symbols of 1-minute bars in the tens of dollars and tick or MBP-1 data for the same span in the hundreds. An Alpaca key unlocks stock and ETF intraday history, not that CME archive. No key was requested.


### Other samples

- Spec 6 BTC and ETH 5-minute, Binance spot: inconclusive. OOS CAGR -0.03%, total -0.14%, win 0.0%, avg R -8.470, expectancy $-138, PF 0.00, max DD -0.14%, Sharpe -0.38, trades 1.
- Spec 1 NQ=F and ES=F 5-minute, Yahoo about 60 days: inconclusive. OOS CAGR -13.31%, total -1.40%, win 16.7%, avg R -0.511, expectancy $-233, PF 0.36, max DD -1.44%, Sharpe -3.34, trades 6.
- Spec 3 NQ=F and ES=F 5-minute, Yahoo about 60 days: inconclusive. OOS CAGR 0.00%, total 0.00%, win 0.0%, avg R 0.000, expectancy $0, PF n/a, max DD 0.00%, Sharpe 0.00, trades 0.
- Spec 5 NQ=F and ES=F 5-minute, Yahoo about 60 days: inconclusive. OOS CAGR -14.11%, total -1.49%, win 23.1%, avg R -0.338, expectancy $-114, PF 0.71, max DD -3.04%, Sharpe -1.51, trades 13.
- Spec 7 NQ=F and ES=F 5-minute, Yahoo about 60 days: inconclusive. OOS CAGR -8.07%, total -0.83%, win 0.0%, avg R -0.793, expectancy $-275, PF 0.00, max DD -0.83%, Sharpe -4.62, trades 3.
- Spec 2 GC=F 30-minute, Yahoo about 60 days: inconclusive. OOS CAGR 0.00%, total 0.00%, win 0.0%, avg R 0.000, expectancy $0, PF n/a, max DD 0.00%, Sharpe 0.00, trades 0.
- Spec 4 NQ=F and ES=F 60-minute, Yahoo about 730 days: inconclusive. OOS CAGR -0.89%, total -2.12%, win 33.3%, avg R -0.133, expectancy $-50, PF 0.79, max DD -3.17%, Sharpe -0.32, trades 42.
- Spec 1 daily proxy SPY, prior-day reclaim: inconclusive. OOS CAGR 0.02%, total 0.16%, win 40.2%, avg R -0.169, expectancy $2, PF 1.02, max DD -1.94%, Sharpe 0.03, trades 82.
- Spec 4 daily proxy SPY, rejection candle: inconclusive. OOS CAGR 0.00%, total 0.04%, win 52.6%, avg R 0.092, expectancy $2, PF 1.03, max DD -0.88%, Sharpe 0.02, trades 19.
- Spec 1 daily proxy QQQ, prior-day reclaim: inconclusive. OOS CAGR -0.13%, total -1.27%, win 32.5%, avg R -0.464, expectancy $-17, PF 0.82, max DD -2.64%, Sharpe -0.20, trades 77.
- Spec 4 daily proxy QQQ, rejection candle: inconclusive. OOS CAGR 0.04%, total 0.40%, win 28.6%, avg R -0.214, expectancy $28, PF 1.26, max DD -1.32%, Sharpe 0.08, trades 14.
<!-- FANATICS_END -->

<!-- PAPER_SIM_START -->
## Paper replay versus backtest

Each implemented strategy was replayed on the last 45 sessions available in the local cache, or on that many recent Yahoo sessions for the daily and hourly stock rules. The paper column uses the paper broker: simulated fills, protective stops, the configured daily-loss flatten (default 2%), and the same flatten the kill switch calls. The backtest column is the research fill model on that same window. Both start flat, so a signal that closed before the window is not filled. Shorts and option orders were not sent. The Webull API was not called. When the note says paper matches, closed-trade count and P&L agree to the dollar. Max drawdown can still differ by a few basis points because the two equity curves are not sampled on the same marks.

Dual momentum is the reference book. A paper result that does not match its backtest on this window is a simulator bug. Fanatics specs 1–7 are futures or crypto prints. The stock paper account cannot buy an index future for cash, so those replays reserve margin at 20x inside the paper ledger and still refuse shorts. They are not Webull stock orders and they are not in the config. Each spec's session stop (its consecutive-loss limit and its ±R day limit) is in the backtest column only. Paper also skips the one-tick entry slip and the extra stop ticks, so the same trades can print a different dollar P&L.

| Strategy | Window | Backtest trades | Backtest P&L | Backtest win | Backtest max DD | Paper orders | Paper fills | Paper closed | Paper P&L | Paper win | Paper max DD | Risk triggers | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| gap_and_go | 2026-07-30 to 2026-10-01 (45 sessions) | 0 | $0.00 | 0.00% | 0.00% | 0 | 0 | 0 | $0.00 | 0.00% | 0.00% | 0 | Paper matches the backtest on this window. |
| eod_mean_reversion | 2026-07-30 to 2026-10-01 (45 sessions) | 22 | $-185.76 | 36.36% | -1.66% | 22 | 44 | 22 | $-185.76 | 36.36% | -1.66% | 0 | Paper matches the backtest on this window. |
| ema_pullback | 2026-07-30 to 2026-10-01 (45 sessions) | 14 | $-1,111.80 | 28.57% | -2.59% | 14 | 28 | 14 | $-1,111.80 | 28.57% | -2.59% | 0 | Paper matches the backtest on this window. |
| vcp_breakout | 2026-07-30 to 2026-10-01 (45 sessions) | 0 | $0.00 | 0.00% | 0.00% | 0 | 0 | 0 | $0.00 | 0.00% | 0.00% | 0 | Paper matches the backtest on this window. |
| connors_rsi2 | 2026-07-30 to 2026-10-01 (45 sessions) | 24 | $-696.41 | 45.83% | -2.29% | 24 | 48 | 24 | $-696.41 | 45.83% | -2.29% | 0 | Paper matches the backtest on this window. |
| rs_rotation | 2026-07-30 to 2026-10-01 (45 sessions) | 4 | $11.58 | 50.00% | -0.54% | 4 | 8 | 4 | $11.58 | 50.00% | -0.54% | 0 | Paper matches the backtest on this window. |
| dual_momentum | 2026-07-30 to 2026-10-01 (45 sessions) | 1 | $176.42 | 100.00% | -0.18% | 1 | 2 | 1 | $176.42 | 100.00% | -0.18% | 0 | Paper matches the backtest on this window. |
| bluechip_reversal | 2026-07-30 to 2026-10-01 (45 sessions) | 0 | $0.00 | 0.00% | 0.00% | 0 | 0 | 0 | $0.00 | 0.00% | 0.00% | 0 | Paper matches the backtest on this window. |
| support_reversal | 2026-07-30 to 2026-10-01 (45 sessions) | 29 | $-4,691.33 | 24.14% | -6.40% | 29 | 58 | 29 | $-4,691.33 | 24.14% | -6.40% | 0 | Paper matches the backtest on this window. |
| wedge_breakout | 2026-07-30 to 2026-10-01 (45 sessions) | 21 | $-3,622.97 | 28.57% | -3.88% | 21 | 42 | 21 | $-3,622.97 | 28.57% | -3.88% | 0 | Paper matches the backtest on this window. |
| opening_range_breakout | 2026-07-30 to 2026-10-01 (45 sessions) | 4 | $-147.94 | 25.00% | -0.28% | 4 | 8 | 4 | $-147.94 | 25.00% | -0.32% | 0 | Paper matches the backtest on this window. |
| vwap_pullback | 2026-07-30 to 2026-10-01 (45 sessions) | 33 | $-1,228.06 | 15.15% | -1.26% | 33 | 66 | 33 | $-1,228.06 | 15.15% | -1.30% | 0 | Paper matches the backtest on this window. |
| fanatics_8_overnight | 2026-07-29 to 2026-09-30 (45 sessions, SPY+QQQ daily) | 44 | $-113.60 | 50.00% | -4.61% | 44 | 88 | 44 | $-152.39 | 47.73% | -0.73% | 0 | Research book is fully invested, split across SPY and QQQ. Paper sizes with the account risk cap (0.75% at a 2% disaster stop, 20% position cap, 35% sector cap) and exits at the next open. Both names are the broad sector, so the second order can be rejected. Rejections: sector broad would exceed 35% 44. |
| fanatics_1_pdh_pdl | 2026-08-09 to 2026-10-01 (NQ=F, ES=F) | 8 | $-1,538.50 | 25.00% | -1.58% | 3 | 6 | 3 | $-1,175.00 | 0.00% | -1.18% | 0 | Shorts not sent: 8. Long-only backtest P&L $-1,398.00 on 3 trades. Paper reserves futures margin at 20x and does not apply stock bps; the backtest charges 1 tick of entry slippage, extra stop ticks, and futures or crypto fees. Rejections: position size rounded to zero 3. |
| fanatics_3_value_area | 2026-08-09 to 2026-10-01 (NQ=F, ES=F) | 1 | $-29.00 | 0.00% | -0.03% | 0 | 0 | 0 | $0.00 | 0.00% | 0.00% | 0 | Shorts not sent: 1. Long-only backtest P&L $0.00 on 0 trades. Paper reserves futures margin at 20x and does not apply stock bps; the backtest charges 1 tick of entry slippage, extra stop ticks, and futures or crypto fees. Rejections: position size rounded to zero 1. |
| fanatics_5_liquidity | 2026-08-09 to 2026-10-01 (NQ=F, ES=F) | 19 | $-1,760.50 | 26.32% | -3.35% | 10 | 18 | 9 | $1,112.50 | 33.33% | -2.27% | 0 | Shorts not sent: 7. Long-only backtest P&L $1,294.00 on 12 trades. Paper reserves futures margin at 20x and does not apply stock bps; the backtest charges 1 tick of entry slippage, extra stop ticks, and futures or crypto fees. Rejections: unfilled 1. |
| fanatics_6_1000_sweep | 2026-08-09 to 2026-10-01 (NQ=F, ES=F) | 7 | $-1,352.50 | 28.57% | -1.43% | 4 | 8 | 4 | $-975.00 | 25.00% | -1.12% | 0 | Shorts not sent: 3. Long-only backtest P&L $-1,199.00 on 4 trades. Paper reserves futures margin at 20x and does not apply stock bps; the backtest charges 1 tick of entry slippage, extra stop ticks, and futures or crypto fees. Rejections: none. |
| fanatics_7_orb | 2026-08-09 to 2026-10-01 (NQ=F, ES=F) | 4 | $-1,236.50 | 0.00% | -1.24% | 1 | 2 | 1 | $0.00 | 0.00% | -0.30% | 0 | Shorts not sent: 3. Long-only backtest P&L $-58.00 on 1 trade. Paper reserves futures margin at 20x and does not apply stock bps; the backtest charges 1 tick of entry slippage, extra stop ticks, and futures or crypto fees. Rejections: none. |
| fanatics_4_edge | 2026-08-09 to 2026-10-01 (NQ=F, ES=F) | 4 | $-1,817.50 | 0.00% | -1.82% | 2 | 4 | 2 | $-890.00 | 0.00% | -0.89% | 0 | Shorts not sent: 7. Long-only backtest P&L $-992.00 on 2 trades. Paper reserves futures margin at 20x and does not apply stock bps; the backtest charges 1 tick of entry slippage, extra stop ticks, and futures or crypto fees. Rejections: position size rounded to zero 7. |
| fanatics_2_london_fvg | 2026-08-09 to 2026-10-01 (GC=F) | 0 | $0.00 | 0.00% | 0.00% | 0 | 0 | 0 | $0.00 | 0.00% | 0.00% | 0 | Shorts not sent: 0. Long-only backtest P&L $0.00 on 0 trades. Paper reserves futures margin at 20x and does not apply stock bps; the backtest charges 1 tick of entry slippage, extra stop ticks, and futures or crypto fees. Rejections: position size rounded to zero 1. |

No paper-versus-backtest mismatch remained on the stock and ETF rules, and no replay crashed.

Run it again with `python -m webull_bot paper-sim`. That command stays on the local paper broker. See the README for the sandbox account settings, which this run did not use.
<!-- PAPER_SIM_END -->

<!-- MTF_VWAP_START -->
## Multi-timeframe VWAP test

Rules, scored on the pre-registered default and not on a mined neighbor: trend alignment on weekly, daily, and the execution bar (15-minute also requires 60-minute and, when the file is present, 5-minute); a session VWAP test that wicks into VWAP and closes back with the trend, at a pivot or prior-day zone; the next 15-minute or 60-minute bar confirms; entry at the following open. Longs buy a call. Shorts buy a put. Delta 0.50, 14 DTE (inside 7-30), premium stop -50%, premium target +50%, also exit on a close back through VWAP, through the setup extreme, at the next level, or after 2 sessions. One position. One contract must cost at most 25% of a $1,000 account or the trade is skipped. Webull option fees and a bid/ask haircut (4% at-the-money, 8% otherwise, 12% when the mid is under $1). Margin account under $25,000: at most 3 day trades in 5 sessions. The signal grid changes one rule at a time (majority alignment, daily EMA 10, no zone, trendline, same-bar confirmation, VWAP bands). DTE, delta, premium targets, IV, and spreads are sensitivities.

**DOES NOT PASS.** The default option book (delta 0.50, 14 DTE, one contract, at most 25% of $1,000) took no trades. The 15-minute file, 2026-08-13 through 2026-10-06 (38 sessions), found 1 long signal and skipped it because one contract cost more than the cap. The 60-minute file, 2024-10-17 through 2026-10-06 (493 sessions), found 6 signals (2 long, 4 short) and skipped all 6 for the same reason. Ending equity stayed $1,000. Equity never fell under $100. No day trade was blocked, because nothing opened. Both windows are under 300 trades, so they are anecdotal. Both sit inside Yahoo's free intraday cap, which this project does not treat as a durable edge.

The only option fills were the rough 0-7 DTE sensitivities on the hourly out-of-sample half. Three DTE lost its one trade and ended at $973.33. Zero DTE lost both trades to the premium stop and ended at $651.01. Those prices are a Black-Scholes sketch from realized volatility, and they are especially rough inside a week. IV at 1.0x and 1.3x, and a doubled spread, still could not buy a 14 DTE contract under the cap.

The same hourly signals as stock, still capped at 25% of $1,000, made 2 trades on the full sample and the out-of-sample half ended at $999.71 (profit factor 0.00). Allowing one whole share up to the full $1,000 made 5 trades and ended at $992.89 (Sharpe -0.53, profit factor 0.32, ruin estimate 1). The out-of-sample half of that looser stock book ended at $1,002.26 on 3 trades. A random-entry book with the same exits ended at $1,001.38 on 3 trades. One SPY share bought and held over that out-of-sample window ended at $1,126.37. The 15-minute stock comparison is one trade for $1.32. A Binance BTC hourly proxy, with a New York 09:30 VWAP pasted on, found 0 signals.

The in-sample grid did not produce a positive option Sharpe on any cell. Looser cells found more signals (majority alignment skipped 30 in-sample contracts) and still could not buy one. Walk-forward on the hourly file filled nothing. Not added to the optional list. The default book is still dual momentum. Nothing was sent to a broker.

### 15-minute execution, weekly daily 60m 15m and 5m trend

Sessions 2026-08-13 through 2026-10-06 (38 sessions). In sample 2026-08-13 to 2026-09-14. Out of sample 2026-09-15 to 2026-10-06. Signals 1 (1 long, 0 short). Flags: short_sample, parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, anecdotal_sample. Walk-forward needs 40 sessions, so that row is an empty window, not a tested fold. The fragile flag is the in-sample grid: every cell's option Sharpe is zero because the contracts did not fit.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Premium skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Options, full sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| Options, in sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| Options, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| Options, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| Options, random entries, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| Stock, 25% cap, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| Stock, whole shares up to $1,000, out of sample | 1 | 100.0% | $1.32 | $0.00 | $1.32 | n/a | 0.0% | 4.10 | $1001.32 | no | n/a | 0 | 0 |
| Stock, whole shares up to $1,000, full sample | 1 | 100.0% | $1.32 | $0.00 | $1.32 | n/a | 0.0% | 2.61 | $1001.32 | no | n/a | 0 | 0 |
| SPY buy and hold, whole shares, out of sample | 1 | 100.0% | $21.67 | $0.00 | $21.67 | n/a | -1.1% | 4.30 | $1021.67 | no | n/a | 0 | 0 |

Signal grid, in-sample option book (one change from the default per row):

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Premium skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| default | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| alignment=majority | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| ema_daily=10 | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| require_zone=False | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| use_trendline=True | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| confirm=same | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| use_bands=True | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |

Sensitivities on the out-of-sample window. These are not grid cells and were not used to pick parameters.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Premium skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 0-7 DTE (3, flat at the close) | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| 0 DTE, flat at the close | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| 21 DTE | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| delta 0.40 | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| delta 0.60 | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| premium stop -30% | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| premium target +30% | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| premium target +100% | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| IV 1.00x realized | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| IV 1.30x realized | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| doubled bid/ask | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| premium cap 20% | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| premium cap 30% | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| max 2 positions | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| cash account, T+1 | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| 5-minute reclaim | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |

### 60-minute execution, daily and weekly trend

Sessions 2024-10-17 through 2026-10-06 (493 sessions). In sample 2024-10-17 to 2025-10-10. Out of sample 2025-10-13 to 2026-10-06. Signals 6 (2 long, 4 short). Flags: short_sample, parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, anecdotal_sample.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Premium skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Options, full sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 6 |
| Options, in sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| Options, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| Options, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| Options, random entries, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| Stock, 25% cap, out of sample | 1 | 0.0% | $0.00 | $-0.29 | $-0.29 | 0.00 | -0.0% | -1.01 | $999.71 | no | n/a | 0 | 2 |
| Stock, whole shares up to $1,000, out of sample | 3 | 66.7% | $1.70 | $-1.14 | $0.75 | 2.98 | -0.1% | 0.69 | $1002.26 | no | n/a | 0 | 0 |
| Stock, whole shares up to $1,000, full sample | 5 | 40.0% | $1.70 | $-3.50 | $-1.42 | 0.32 | -1.1% | -0.53 | $992.89 | no | 1.00 | 0 | 0 |
| SPY buy and hold, whole shares, out of sample | 1 | 100.0% | $126.37 | $0.00 | $126.37 | n/a | -5.9% | 1.47 | $1126.37 | no | n/a | 0 | 0 |

Signal grid, in-sample option book (one change from the default per row):

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Premium skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| default | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| alignment=majority | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 30 |
| ema_daily=10 | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 1 |
| require_zone=False | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 13 |
| use_trendline=True | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| confirm=same | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 8 |
| use_bands=True | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 7 |

Sensitivities on the out-of-sample window. These are not grid cells and were not used to pick parameters.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Premium skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 0-7 DTE (3, flat at the close) | 1 | 0.0% | $0.00 | $-26.67 | $-26.67 | 0.00 | -2.7% | -1.01 | $973.33 | no | n/a | 0 | 2 |
| 0 DTE, flat at the close | 2 | 0.0% | $0.00 | $-174.49 | $-174.49 | 0.00 | -34.9% | -1.41 | $651.01 | no | n/a | 0 | 1 |
| 21 DTE | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| delta 0.40 | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| delta 0.60 | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| premium stop -30% | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| premium target +30% | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| premium target +100% | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| IV 1.00x realized | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| IV 1.30x realized | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| doubled bid/ask | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| premium cap 20% | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| premium cap 30% | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| max 2 positions | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |
| cash account, T+1 | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 3 |

Stock shorts in the comparison book are a research baseline. They are not sent as orders. A share that costs more than the cap is skipped, same as a contract. The whole-share column lets the $1,000 account buy one share when the share itself fits, so the signal can be read when the 25% cap blocks every name.

0-7 DTE prices are a Black-Scholes sketch from recent realized volatility. They are not a quote, and they get worse as expiry approaches zero.

### Binance BTC proxy

Proxy. BTCUSDT hourly bars from data.binance.vision. Session VWAP is reset at 09:30 America/New_York, which is not a crypto session. Not a stock result and not gated.

Sessions 2024-09-30 through 2026-10-05 (736). Signals 0.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Premium skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Options, second half, proxy | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |

Example charts of detected tests are in `reports/setups/`: `vwap15_1_AMD_long_2026-10-01.png`, `vwap60_1_AAPL_long_2026-09-21.png`, `vwap60_2_AMD_long_2026-09-22.png`, `vwap60_3_QQQ_short_2025-04-16.png`, `vwap60_4_SPY_short_2025-04-16.png`. The VWAP line is the full session, not a line rebuilt from the first plotted bar. The orange dot is the test wick (the low on a long, the high on a short). The green dot is the confirmation close.

The 15-minute book cannot pass: the file is shorter than 300 trades can honestly support. The 60-minute book is the bigger sample and is still the free Yahoo hourly cap, which this project does not select from. Profit factor gate 1.10, Sharpe gate 0.40, drawdown no worse than -30%. Out-of-sample profit factor on the 60-minute default is n/a.

<!-- MTF_VWAP_END -->

<!-- CHART_READS_START -->
## Chart-read EMA and VWAP test

Rules frozen to the three Oct 6, 2026 thinkorswim charts before scoring. Chart: EMA 9, EMA 20, EMA 200, session VWAP with ±2 standard deviations, RSI(14), MACD(12, 26, 9). Continuation (setup A): 9 EMA above 20, both rising, separation at least 0.25 ATR, close above VWAP. A majority of the higher timeframes agrees (daily, 60-minute, and 15-minute on a 5-minute signal; not all of them). After a new session high or a tag of the outer band, price pulls back at least 0.5 ATR to the 9 EMA, the 20 EMA, or VWAP without a close through the 20 EMA. The trigger is a strong candle (close in the top third, body at least half the range) that does not close below the prior bar's low. Entry is the next open. Stop is the pullback low. Failed break (setup B): a close back through a break of the prior 6-bar high or the outer band, then a fresh 9/20 cross and a close through VWAP within 12 bars. Stop is the failed extreme. This short is allowed unless every higher timeframe is a clean trend the other way, which is what keeps the UNH example (mixed daily, not a unanimous uptrend). Target is 2R, with an exit on a close back through the 20 EMA, and a flat at the end of the session on 5-minute and 15-minute bars. The 60-minute book holds up to five sessions instead of flattening every day. One position. Risk 20% of a $1,000 account (10% and 25% are sensitivities). Whole option contracts only. Fractional shares are the stock baseline. Margin under $25,000: at most 3 day trades in 5 sessions. The signal grid changes one filter at a time (separation 0.10 or 0.50 ATR, require the 200 EMA, first two hours only, RSI and MACD, stay inside the outer band). DTE, delta, spread width, IV, and the bid/ask haircut are sensitivities. 0-7 DTE prices are a Black-Scholes sketch and are labeled rough.

**DOES NOT PASS.** The detector was frozen before any P&L was scored, and it marked all three annotated bars. UNH 5-minute short: failed breakout at 09:45, 9/20 cross at 10:25, fill at the 10:30 open, stop 380.41. SPY 5-minute long: impulse at 10:05, strong candle at 10:35, fill at 10:40, stop 778.56. SPY 15-minute long: impulse at 10:00, signal at 10:30, fill at 10:45, stop 778.56, which is the marked 778.57 retest.

On the 5-minute clock these charts use (38 sessions, 908 signals), a $1,000 fractional-stock account took 11 out-of-sample trades, won 27.3%, average win $2.72, average loss $3.76, expectancy -$1.99, profit factor 0.27, max drawdown -2.2%, Sharpe -6.46, and ended at $978.07. Random entries with the same exits ended at $986.79. One SPY share bought and held ended at $1,021.67. The day-trade cap blocked 326 out-of-sample entries, because flattening at the close makes every fill a day trade and three in five sessions is the limit under $25,000. The rough 3 DTE single-option book took 9 trades and ended at $839.47 (63 signals skipped because one contract cost more than 20% of equity). The SPY and QQQ debit-spread book took 3 trades, all losses, and ended at $621.78. Equity did not fall under $100. The ruin estimate on the losing stock and option paths is 1. Walk-forward is an empty window: the file has 38 sessions and a fold needs 40. The full 5-minute stock sample is 24 trades ending at $974.01.

The 15-minute stock out-of-sample book ended at $1,001.48 on 10 trades (profit factor 1.07, Sharpe 0.39). That misses the 1.10 and 0.40 gates. Buy and hold on the same window ended at $1,021.67.

The 60-minute file is the longer sample (493 sessions, 692 signals) and it still loses. Fractional stock took 164 out-of-sample trades: win rate 32.3%, average win $19.65, average loss $9.67, expectancy -$0.20, profit factor 0.97, max drawdown -19.9%, Sharpe -0.03, ending $967.77. Random entries ended at $959.03. One SPY share ended at $1,126.37. Walk-forward stock Sharpe was -0.68 and ended at $847.87. The full hourly stock sample is 298 trades and ended at $833.59 (max drawdown -39.8%). Rough 0-7 DTE singles on the out-of-sample window took 20 trades and ended at $496.28 (max drawdown -74.8%). Debit spreads took 3 trades and ended at $587.59. No book went under $100. 298 trades is still under 300, and the file is the free Yahoo hourly cap, so this is anecdotal and is not selectable.

Not added to the optional list. The default book is still dual momentum. Nothing was sent to a broker.

### Annotated sessions, checked before scoring

The rules were frozen to these three charts. A later P&L number was not allowed to move a threshold.

| Chart | Result | What the detector marked |
|---|---|---|
| UNH 5m Oct 6 short, failed breakout then 9/20 cross | hit | B short anchor 09:45 signal 10:25 fill 10:30 stop 380.41 |
| SPY 5m Oct 6 long, retest then continuation | hit | A long anchor 10:05 signal 10:35 fill 10:40 stop 778.56 |
| SPY 15m Oct 6 long, retest of 778.57 holding the EMA | hit | A long anchor 10:00 signal 10:30 fill 10:45 stop 778.56 |

Other SPY 5m signals on 2026-10-06: A long anchor 09:40 signal 09:45 fill 09:50 stop 778.43; A long anchor 10:00 signal 10:05 fill 10:10 stop 779.72.

### 5-minute execution

Sessions 2026-08-13 through 2026-10-06 (38 sessions). In sample 2026-08-13 to 2026-09-14. Out of sample 2026-09-15 to 2026-10-06. Signals 908 (461 long, 447 short, 654 continuation, 254 failed-break). Stock flags: short_sample, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, sharpe_decay, anecdotal_sample. Spread flags: short_sample, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30, sharpe_decay, anecdotal_sample. Single-option flags: short_sample, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, sharpe_decay, anecdotal_sample.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Stock, fractional, full sample | 24 | 29.2% | $6.23 | $-4.09 | $-1.08 | 0.63 | -4.5% | -2.03 | $974.01 | no | 1.00 | 785 | 0 |
| Stock, fractional, in sample | 15 | 46.7% | $6.23 | $-2.97 | $1.32 | 1.83 | -0.9% | 3.52 | $1019.80 | no | 0.00 | 408 | 0 |
| Stock, fractional, out of sample | 11 | 27.3% | $2.72 | $-3.76 | $-1.99 | 0.27 | -2.2% | -6.46 | $978.07 | no | 1.00 | 326 | 0 |
| Stock, random entries, out of sample | 12 | 16.7% | $3.29 | $-1.98 | $-1.10 | 0.33 | -1.3% | -7.43 | $986.79 | no | 1.00 | 343 | 0 |
| 0-7 DTE single, full sample, rough | 17 | 5.9% | $27.07 | $-30.37 | $-26.99 | 0.06 | -45.9% | -8.40 | $541.11 | no | 1.00 | 324 | 454 |
| 0-7 DTE single, in sample, rough | 10 | 0.0% | $0.00 | $-26.79 | $-26.79 | 0.00 | -26.8% | -8.98 | $732.08 | no | 1.00 | 232 | 205 |
| 0-7 DTE single, out of sample, rough | 9 | 22.2% | $64.74 | $-41.43 | $-17.84 | 0.45 | -16.1% | -4.31 | $839.47 | no | 1.00 | 278 | 63 |
| 0-7 DTE single, random entries, out of sample, rough | 9 | 44.4% | $40.87 | $-19.28 | $7.45 | 1.70 | -4.0% | 2.74 | $1067.08 | no | 0.00 | 209 | 87 |
| Debit spread, full sample | 2 | 0.0% | $0.00 | $-173.09 | $-173.09 | 0.00 | -34.6% | -3.74 | $653.81 | no | n/a | 0 | 190 |
| Debit spread, in sample | 2 | 0.0% | $0.00 | $-173.09 | $-173.09 | 0.00 | -34.6% | -5.02 | $653.81 | no | n/a | 0 | 84 |
| Debit spread, out of sample | 3 | 0.0% | $0.00 | $-126.07 | $-126.07 | 0.00 | -37.8% | -4.10 | $621.78 | no | n/a | 31 | 66 |
| Debit spread, random entries, out of sample | 3 | 0.0% | $0.00 | $-137.38 | $-137.38 | 0.00 | -41.2% | -5.76 | $587.85 | no | n/a | 17 | 56 |
| Stock, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| 0-7 DTE single, walk-forward, rough | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| Debit spread, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| SPY buy and hold, whole shares, out of sample | 1 | 100.0% | $21.67 | $0.00 | $21.67 | n/a | -1.1% | 4.30 | $1021.67 | no | n/a | 0 | 0 |

Walk-forward needs 40 sessions, so that row is an empty window, not a tested fold.

Signal grid, in-sample fractional stock (one change from the frozen default per row):

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| default | 15 | 46.7% | $6.23 | $-2.97 | $1.32 | 1.83 | -0.9% | 3.52 | $1019.80 | no | 0.00 | 408 | 0 |
| k_sep=0.1 | 15 | 46.7% | $6.23 | $-2.97 | $1.32 | 1.83 | -0.9% | 3.52 | $1019.80 | no | 0.00 | 411 | 0 |
| k_sep=0.5 | 15 | 40.0% | $8.73 | $-2.95 | $1.72 | 1.97 | -0.9% | 4.09 | $1025.84 | no | 0.00 | 377 | 0 |
| above 200 EMA | 12 | 16.7% | $0.88 | $-2.67 | $-2.08 | 0.07 | -2.5% | -6.69 | $975.06 | no | 1.00 | 337 | 0 |
| 9:30-11:30 | 14 | 50.0% | $5.94 | $-5.91 | $0.01 | 1.00 | -1.9% | 0.07 | $1000.18 | no | 0.47 | 143 | 0 |
| RSI and MACD | 15 | 40.0% | $6.93 | $-3.90 | $0.43 | 1.19 | -1.7% | 1.07 | $1006.50 | no | 0.00 | 210 | 0 |
| inside VWAP band | 15 | 40.0% | $7.86 | $-3.47 | $1.06 | 1.51 | -0.6% | 3.59 | $1015.96 | no | 0.00 | 304 | 0 |

Sensitivities on the out-of-sample window. These were not used to pick the default.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| stock: risk 10% | 11 | 27.3% | $2.72 | $-3.76 | $-1.99 | 0.27 | -2.2% | -6.46 | $978.07 | no | 1.00 | 326 | 0 |
| stock: risk 25% | 11 | 27.3% | $2.72 | $-3.76 | $-1.99 | 0.27 | -2.2% | -6.46 | $978.07 | no | 1.00 | 326 | 0 |
| stock: target 1.5R | 11 | 27.3% | $2.23 | $-3.71 | $-2.09 | 0.23 | -2.3% | -6.68 | $977.04 | no | 1.00 | 326 | 0 |
| stock: trail the 9 EMA | 12 | 8.3% | $11.27 | $-2.70 | $-1.54 | 0.38 | -2.3% | -5.23 | $981.53 | no | 1.00 | 356 | 0 |
| stock: target at the band or prior extreme | 11 | 27.3% | $2.72 | $-3.76 | $-1.99 | 0.27 | -2.2% | -6.46 | $978.07 | no | 1.00 | 326 | 0 |
| stock: cash account, T+1 | 16 | 18.8% | $1.94 | $-6.47 | $-4.89 | 0.07 | -7.9% | -17.94 | $921.70 | no | 1.00 | 0 | 299 |
| single: 0 DTE, rough | 10 | 30.0% | $43.18 | $-66.48 | $-33.58 | 0.28 | -42.8% | -3.65 | $664.22 | no | 1.00 | 325 | 3 |
| single: 7 DTE, rough | 4 | 0.0% | $0.00 | $-50.85 | $-50.85 | 0.00 | -20.3% | -8.89 | $796.60 | no | n/a | 0 | 404 |
| single: delta 0.40 | 9 | 22.2% | $60.21 | $-36.80 | $-15.24 | 0.47 | -13.7% | -3.90 | $862.84 | no | 1.00 | 278 | 63 |
| single: delta 0.50 | 9 | 22.2% | $57.86 | $-42.40 | $-20.12 | 0.39 | -18.1% | -5.19 | $818.96 | no | 1.00 | 278 | 65 |
| single: IV 1.00x realized | 9 | 22.2% | $66.40 | $-39.89 | $-16.27 | 0.48 | -15.1% | -3.95 | $853.59 | no | 1.00 | 278 | 63 |
| single: IV 1.30x realized | 9 | 22.2% | $61.32 | $-45.22 | $-21.55 | 0.39 | -19.4% | -4.98 | $806.06 | no | 1.00 | 278 | 63 |
| single: doubled bid/ask | 9 | 22.2% | $45.53 | $-60.99 | $-37.32 | 0.21 | -33.6% | -6.55 | $664.12 | no | 1.00 | 264 | 65 |
| single: cash account, T+1 | 20 | 20.0% | $41.31 | $-35.90 | $-20.46 | 0.29 | -42.9% | -7.60 | $590.86 | no | 1.00 | 0 | 259 |
| spread: $1 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 106 |
| spread: $5 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 106 |
| spread: 7 DTE | 3 | 0.0% | $0.00 | $-105.49 | $-105.49 | 0.00 | -31.6% | -4.10 | $683.54 | no | n/a | 31 | 66 |
| spread: 14 DTE | 2 | 0.0% | $0.00 | $-157.27 | $-157.27 | 0.00 | -31.5% | -4.10 | $685.46 | no | n/a | 0 | 98 |
| spread: IV 1.00x realized | 3 | 0.0% | $0.00 | $-123.83 | $-123.83 | 0.00 | -37.1% | -4.10 | $628.51 | no | n/a | 31 | 66 |
| spread: IV 1.30x realized | 2 | 0.0% | $0.00 | $-149.51 | $-149.51 | 0.00 | -29.9% | -4.10 | $700.97 | no | n/a | 0 | 98 |
| spread: doubled bid/ask | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 106 |
| spread: cash account, T+1 | 3 | 0.0% | $0.00 | $-126.07 | $-126.07 | 0.00 | -37.8% | -4.10 | $621.78 | no | n/a | 0 | 97 |

### 15-minute execution

Sessions 2026-08-13 through 2026-10-06 (38 sessions). In sample 2026-08-13 to 2026-09-14. Out of sample 2026-09-15 to 2026-10-06. Signals 397 (220 long, 177 short, 315 continuation, 82 failed-break). Stock flags: short_sample, parameter_fragile, insufficient_trades, oos_profit_factor_below_1_10, oos_sharpe_below_0_40, anecdotal_sample. Spread flags: short_sample, parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30, anecdotal_sample. Single-option flags: short_sample, parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, anecdotal_sample.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Stock, fractional, full sample | 24 | 25.0% | $6.67 | $-6.36 | $-3.10 | 0.35 | -8.4% | -5.84 | $925.54 | no | 1.00 | 265 | 0 |
| Stock, fractional, in sample | 14 | 21.4% | $7.77 | $-6.24 | $-3.24 | 0.34 | -4.5% | -6.57 | $954.63 | no | 1.00 | 161 | 0 |
| Stock, fractional, out of sample | 10 | 40.0% | $5.93 | $-3.70 | $0.15 | 1.07 | -1.4% | 0.39 | $1001.48 | no | 0.00 | 127 | 0 |
| Stock, random entries, out of sample | 11 | 18.2% | $3.09 | $-3.52 | $-2.32 | 0.19 | -2.8% | -6.12 | $974.46 | no | 1.00 | 131 | 0 |
| 0-7 DTE single, full sample, rough | 17 | 35.3% | $37.00 | $-40.76 | $-13.32 | 0.50 | -28.8% | -3.37 | $773.62 | no | 1.00 | 108 | 186 |
| 0-7 DTE single, in sample, rough | 11 | 27.3% | $36.48 | $-37.14 | $-17.06 | 0.37 | -20.3% | -4.47 | $812.35 | no | 1.00 | 89 | 86 |
| 0-7 DTE single, out of sample, rough | 8 | 37.5% | $44.98 | $-45.15 | $-11.35 | 0.60 | -16.7% | -3.09 | $909.18 | no | 1.00 | 46 | 76 |
| 0-7 DTE single, random entries, out of sample, rough | 8 | 12.5% | $37.46 | $-39.30 | $-29.71 | 0.14 | -23.8% | -8.74 | $762.33 | no | 1.00 | 56 | 80 |
| Debit spread, full sample | 2 | 0.0% | $0.00 | $-166.02 | $-166.02 | 0.00 | -33.2% | -3.73 | $667.95 | no | n/a | 0 | 83 |
| Debit spread, in sample | 2 | 0.0% | $0.00 | $-166.02 | $-166.02 | 0.00 | -33.2% | -5.01 | $667.95 | no | n/a | 0 | 40 |
| Debit spread, out of sample | 2 | 0.0% | $0.00 | $-153.04 | $-153.04 | 0.00 | -30.6% | -5.97 | $693.93 | no | n/a | 0 | 39 |
| Debit spread, random entries, out of sample | 2 | 0.0% | $0.00 | $-152.38 | $-152.38 | 0.00 | -30.5% | -5.98 | $695.25 | no | n/a | 0 | 25 |
| Stock, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| 0-7 DTE single, walk-forward, rough | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| Debit spread, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 0 |
| SPY buy and hold, whole shares, out of sample | 1 | 100.0% | $21.67 | $0.00 | $21.67 | n/a | -1.1% | 4.30 | $1021.67 | no | n/a | 0 | 0 |

Walk-forward needs 40 sessions, so that row is an empty window, not a tested fold.

Signal grid, in-sample fractional stock (one change from the frozen default per row):

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| default | 14 | 21.4% | $7.77 | $-6.24 | $-3.24 | 0.34 | -4.5% | -6.57 | $954.63 | no | 1.00 | 161 | 0 |
| k_sep=0.1 | 14 | 21.4% | $7.77 | $-6.24 | $-3.24 | 0.34 | -4.5% | -6.57 | $954.63 | no | 1.00 | 167 | 0 |
| k_sep=0.5 | 14 | 21.4% | $9.22 | $-5.16 | $-2.08 | 0.49 | -4.5% | -3.27 | $970.91 | no | 1.00 | 120 | 0 |
| above 200 EMA | 9 | 33.3% | $7.42 | $-5.19 | $-0.99 | 0.72 | -3.0% | -1.13 | $991.13 | no | 1.00 | 79 | 0 |
| 9:30-11:30 | 13 | 7.7% | $14.78 | $-5.44 | $-3.89 | 0.23 | -5.4% | -6.83 | $949.46 | no | 1.00 | 28 | 0 |
| RSI and MACD | 13 | 0.0% | $0.00 | $-4.89 | $-4.89 | 0.00 | -6.4% | -11.68 | $936.42 | no | 1.00 | 68 | 0 |
| inside VWAP band | 14 | 35.7% | $5.05 | $-4.86 | $-1.32 | 0.58 | -2.3% | -2.53 | $981.53 | no | 1.00 | 87 | 0 |

Sensitivities on the out-of-sample window. These were not used to pick the default.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| stock: risk 10% | 10 | 40.0% | $5.93 | $-3.70 | $0.15 | 1.07 | -1.4% | 0.39 | $1001.48 | no | 0.00 | 127 | 0 |
| stock: risk 25% | 10 | 40.0% | $5.93 | $-3.70 | $0.15 | 1.07 | -1.4% | 0.39 | $1001.48 | no | 0.00 | 127 | 0 |
| stock: target 1.5R | 10 | 50.0% | $5.28 | $-3.89 | $0.69 | 1.36 | -1.4% | 1.49 | $1006.93 | no | 0.00 | 125 | 0 |
| stock: trail the 9 EMA | 10 | 30.0% | $6.12 | $-3.23 | $-0.43 | 0.81 | -2.0% | -0.85 | $995.72 | no | 1.00 | 136 | 0 |
| stock: target at the band or prior extreme | 11 | 45.5% | $4.38 | $-3.70 | $-0.03 | 0.98 | -1.4% | -0.06 | $999.65 | no | 1.00 | 127 | 0 |
| stock: cash account, T+1 | 16 | 31.2% | $3.88 | $-5.54 | $-2.59 | 0.32 | -5.1% | -6.93 | $958.50 | no | 1.00 | 0 | 75 |
| single: 0 DTE, rough | 10 | 30.0% | $84.85 | $-87.82 | $-36.02 | 0.41 | -56.2% | -1.44 | $639.81 | no | 1.00 | 121 | 6 |
| single: 7 DTE, rough | 4 | 50.0% | $26.38 | $-47.12 | $-10.37 | 0.56 | -9.4% | -1.95 | $958.54 | no | n/a | 0 | 146 |
| single: delta 0.40 | 8 | 37.5% | $41.48 | $-40.76 | $-9.92 | 0.61 | -14.5% | -3.10 | $920.62 | no | 1.00 | 46 | 76 |
| single: delta 0.50 | 8 | 37.5% | $50.90 | $-46.91 | $-10.23 | 0.65 | -17.6% | -2.43 | $918.14 | no | 1.00 | 46 | 76 |
| single: IV 1.00x realized | 8 | 37.5% | $46.83 | $-44.22 | $-10.08 | 0.64 | -16.3% | -2.72 | $919.38 | no | 1.00 | 46 | 76 |
| single: IV 1.30x realized | 8 | 50.0% | $36.57 | $-52.61 | $-8.02 | 0.70 | -15.8% | -2.05 | $935.84 | no | 1.00 | 34 | 77 |
| single: doubled bid/ask | 7 | 42.9% | $20.17 | $-70.45 | $-31.61 | 0.21 | -24.0% | -7.61 | $778.71 | no | 1.00 | 34 | 78 |
| single: cash account, T+1 | 10 | 40.0% | $38.42 | $-47.38 | $-13.06 | 0.54 | -23.3% | -3.91 | $869.41 | no | 1.00 | 0 | 104 |
| spread: $1 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 43 |
| spread: $5 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 43 |
| spread: 7 DTE | 3 | 0.0% | $0.00 | $-119.28 | $-119.28 | 0.00 | -35.8% | -5.81 | $642.17 | no | n/a | 11 | 25 |
| spread: 14 DTE | 2 | 0.0% | $0.00 | $-169.70 | $-169.70 | 0.00 | -33.9% | -6.00 | $660.60 | no | n/a | 0 | 37 |
| spread: IV 1.00x realized | 3 | 0.0% | $0.00 | $-132.22 | $-132.22 | 0.00 | -39.7% | -5.73 | $603.35 | no | n/a | 11 | 25 |
| spread: IV 1.30x realized | 2 | 0.0% | $0.00 | $-165.56 | $-165.56 | 0.00 | -33.1% | -6.00 | $668.88 | no | n/a | 0 | 39 |
| spread: doubled bid/ask | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 43 |
| spread: cash account, T+1 | 2 | 0.0% | $0.00 | $-153.04 | $-153.04 | 0.00 | -30.6% | -5.97 | $693.93 | no | n/a | 0 | 39 |

### 60-minute execution

Sessions 2024-10-17 through 2026-10-06 (493 sessions). In sample 2024-10-17 to 2025-10-10. Out of sample 2025-10-13 to 2026-10-06. Signals 692 (385 long, 307 short, 457 continuation, 235 failed-break). Stock flags: short_sample, parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, anecdotal_sample. Spread flags: short_sample, parameter_fragile, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30, anecdotal_sample. Single-option flags: short_sample, parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30, anecdotal_sample.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Stock, fractional, full sample | 298 | 32.6% | $18.70 | $-9.85 | $-0.56 | 0.92 | -39.8% | -0.27 | $833.59 | no | 1.00 | 10 | 0 |
| Stock, fractional, in sample | 134 | 33.6% | $20.66 | $-11.79 | $-0.89 | 0.89 | -29.2% | -0.42 | $880.43 | no | 1.00 | 2 | 0 |
| Stock, fractional, out of sample | 164 | 32.3% | $19.65 | $-9.67 | $-0.20 | 0.97 | -19.9% | -0.03 | $967.77 | no | 1.00 | 8 | 0 |
| Stock, random entries, out of sample | 142 | 30.3% | $11.48 | $-5.40 | $-0.29 | 0.92 | -10.9% | -0.27 | $959.03 | no | 1.00 | 115 | 0 |
| 0-7 DTE single, full sample, rough | 6 | 0.0% | $0.00 | $-89.83 | $-89.83 | 0.00 | -53.9% | -1.52 | $461.01 | no | 1.00 | 0 | 680 |
| 0-7 DTE single, in sample, rough | 5 | 0.0% | $0.00 | $-95.82 | $-95.82 | 0.00 | -47.9% | -1.93 | $520.88 | no | 1.00 | 0 | 338 |
| 0-7 DTE single, out of sample, rough | 20 | 15.0% | $485.09 | $-115.23 | $-25.19 | 0.74 | -74.8% | -0.09 | $496.28 | no | 1.00 | 0 | 284 |
| 0-7 DTE single, random entries, out of sample, rough | 32 | 21.9% | $245.39 | $-83.38 | $-11.46 | 0.82 | -67.4% | 0.02 | $633.31 | no | 1.00 | 5 | 258 |
| Debit spread, full sample | 4 | 0.0% | $0.00 | $-102.36 | $-102.36 | 0.00 | -46.6% | -1.08 | $590.57 | no | n/a | 0 | 149 |
| Debit spread, in sample | 4 | 0.0% | $0.00 | $-102.36 | $-102.36 | 0.00 | -46.6% | -1.53 | $590.57 | no | n/a | 0 | 73 |
| Debit spread, out of sample | 3 | 0.0% | $0.00 | $-137.47 | $-137.47 | 0.00 | -41.4% | -1.81 | $587.59 | no | n/a | 0 | 72 |
| Debit spread, random entries, out of sample | 3 | 0.0% | $0.00 | $-141.88 | $-141.88 | 0.00 | -43.2% | -1.63 | $574.35 | no | n/a | 0 | 81 |
| Stock, walk-forward | 145 | 30.3% | $18.28 | $-9.52 | $-1.09 | 0.84 | -22.0% | -0.68 | $847.87 | no | n/a | 5 | 0 |
| 0-7 DTE single, walk-forward, rough | 24 | 12.5% | $485.09 | $-107.79 | $-33.68 | 0.64 | -82.3% | -0.35 | $347.69 | no | n/a | 0 | 274 |
| Debit spread, walk-forward | 7 | 0.0% | $0.00 | $-139.88 | $-139.88 | 0.00 | -69.9% | -2.42 | $300.73 | no | n/a | 0 | 66 |
| SPY buy and hold, whole shares, out of sample | 1 | 100.0% | $126.37 | $0.00 | $126.37 | n/a | -5.9% | 1.47 | $1126.37 | no | n/a | 0 | 0 |

Signal grid, in-sample fractional stock (one change from the frozen default per row):

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| default | 134 | 33.6% | $20.66 | $-11.79 | $-0.89 | 0.89 | -29.2% | -0.42 | $880.43 | no | 1.00 | 2 | 0 |
| k_sep=0.1 | 140 | 32.9% | $19.37 | $-11.28 | $-1.21 | 0.84 | -32.4% | -0.66 | $831.20 | no | 1.00 | 2 | 0 |
| k_sep=0.5 | 123 | 35.8% | $19.88 | $-12.33 | $-0.81 | 0.90 | -27.2% | -0.33 | $900.54 | no | 1.00 | 1 | 0 |
| above 200 EMA | 111 | 34.2% | $20.12 | $-10.51 | $-0.02 | 1.00 | -12.9% | 0.08 | $997.49 | no | 1.00 | 0 | 0 |
| 9:30-11:30 | 22 | 54.5% | $24.87 | $-19.38 | $4.75 | 1.54 | -7.7% | 0.94 | $1104.58 | no | 0.00 | 0 | 0 |
| RSI and MACD | 100 | 34.0% | $17.03 | $-11.28 | $-1.66 | 0.78 | -26.4% | -0.73 | $834.31 | no | 1.00 | 1 | 0 |
| inside VWAP band | 113 | 26.5% | $15.19 | $-8.08 | $-1.90 | 0.68 | -23.7% | -1.30 | $785.17 | no | 1.00 | 0 | 0 |

Sensitivities on the out-of-sample window. These were not used to pick the default.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| stock: risk 10% | 164 | 32.3% | $19.65 | $-9.67 | $-0.20 | 0.97 | -19.9% | -0.03 | $967.77 | no | 1.00 | 8 | 0 |
| stock: risk 25% | 164 | 32.3% | $19.65 | $-9.67 | $-0.20 | 0.97 | -19.9% | -0.03 | $967.77 | no | 1.00 | 8 | 0 |
| stock: target 1.5R | 174 | 34.5% | $13.19 | $-9.00 | $-1.35 | 0.77 | -28.9% | -1.21 | $764.92 | no | 1.00 | 13 | 0 |
| stock: trail the 9 EMA | 171 | 32.7% | $16.44 | $-9.10 | $-0.74 | 0.88 | -21.5% | -0.52 | $873.87 | no | 1.00 | 14 | 0 |
| stock: target at the band or prior extreme | 167 | 35.9% | $12.00 | $-8.77 | $-1.31 | 0.77 | -29.6% | -1.10 | $781.44 | no | 1.00 | 22 | 0 |
| stock: cash account, T+1 | 111 | 27.0% | $16.62 | $-9.16 | $-2.19 | 0.67 | -27.6% | -1.64 | $756.80 | no | 1.00 | 0 | 134 |
| single: 0 DTE, rough | 118 | 22.9% | $28125478.76 | $-7253009.51 | $842068.32 | 1.15 | -98.9% | 4.12 | $99365061.22 | no | 1.00 | 0 | 0 |
| single: 7 DTE, rough | 8 | 12.5% | $417.84 | $-83.30 | $-20.66 | 0.72 | -40.4% | -0.15 | $834.76 | no | 1.00 | 0 | 322 |
| single: delta 0.40 | 23 | 17.4% | $433.08 | $-117.81 | $-22.01 | 0.77 | -71.8% | 0.01 | $493.85 | no | 1.00 | 1 | 269 |
| single: delta 0.50 | 9 | 11.1% | $473.32 | $-97.15 | $-33.76 | 0.61 | -50.3% | -0.19 | $696.12 | no | 1.00 | 0 | 320 |
| single: IV 1.00x realized | 26 | 15.4% | $496.60 | $-117.08 | $-22.67 | 0.77 | -78.1% | 0.10 | $410.67 | no | 1.00 | 0 | 266 |
| single: IV 1.30x realized | 18 | 16.7% | $464.10 | $-122.35 | $-24.61 | 0.76 | -70.6% | -0.21 | $557.00 | no | 1.00 | 1 | 291 |
| single: doubled bid/ask | 17 | 17.6% | $447.32 | $-130.47 | $-28.51 | 0.73 | -72.1% | -0.26 | $515.34 | no | 1.00 | 1 | 295 |
| single: cash account, T+1 | 20 | 15.0% | $485.09 | $-115.23 | $-25.19 | 0.74 | -74.8% | -0.09 | $496.28 | no | 1.00 | 0 | 284 |
| spread: $1 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 76 |
| spread: $5 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1000.00 | no | n/a | 0 | 76 |
| spread: 7 DTE | 4 | 0.0% | $0.00 | $-110.49 | $-110.49 | 0.00 | -44.2% | -1.66 | $558.04 | no | n/a | 0 | 68 |
| spread: 14 DTE | 2 | 0.0% | $0.00 | $-159.35 | $-159.35 | 0.00 | -32.5% | -1.39 | $681.29 | no | n/a | 0 | 73 |
| spread: IV 1.00x realized | 3 | 0.0% | $0.00 | $-127.55 | $-127.55 | 0.00 | -38.4% | -1.43 | $617.34 | no | n/a | 0 | 69 |
| spread: IV 1.30x realized | 2 | 0.0% | $0.00 | $-165.43 | $-165.43 | 0.00 | -33.5% | -1.48 | $669.14 | no | n/a | 0 | 73 |
| spread: doubled bid/ask | 1 | 0.0% | $0.00 | $-193.55 | $-193.55 | 0.00 | -19.4% | -1.01 | $806.45 | no | n/a | 0 | 75 |
| spread: cash account, T+1 | 3 | 0.0% | $0.00 | $-137.47 | $-137.47 | 0.00 | -41.4% | -1.81 | $587.59 | no | n/a | 0 | 72 |

Stock shorts are a research baseline. They are not orders. A single contract or a debit spread is skipped when the debit is above the risk fraction. Debit spreads are SPY and QQQ only, 7-14 DTE, default $2 wide and 10 DTE. The $2,000 margin-equity floor is not applied: this test is about whether the setups fit $1,000, and that floor would block every new position. The day-trade count is still enforced.

0-7 DTE prices use trailing realized volatility times 1.15, a one-minute time floor, and a haircut of 4% at the money, 8% otherwise, and 12% when the mid is under $1. They are not quotes.

Charts of the three annotated sessions, with the detector's marks, are in `reports/setups/`: `read5m_UNH_2026-10-06.png`, `read5m_SPY_2026-10-06.png`, `read15m_SPY_2026-10-06.png`. VWAP is the full session. The orange dot is the impulse or the failed-breakout bar. The green dot is the signal close.

Profit factor gate 1.10, Sharpe gate 0.40, drawdown no worse than -30%, and at least 300 trades. A 5-minute or 15-minute Yahoo file is about 55 days. The 60-minute file is the free hourly cap. Neither is a sample this project will select from.

<!-- CHART_READS_END -->

<!-- CHART_READS_C_START -->
## Daily setup C: descending-trendline breakout

DOES NOT PASS. The UNH line selected on 2026-10-06 runs from 2026-07-29 at 429.04 through 2026-09-09 at 404.04. Late July and early September tag that line. Dow point-in-time stock, out of sample, ended at $746.56 on 207 trades (profit factor 0.92, Sharpe -0.12). The same signals as 45 DTE calls ended at $281.24 with 759 skipped because the contract did not fit the risk cap. The named large-cap list is a survivorship diagnostic: stock ended at $2,344.05, and SPY/QQQ debit spreads ended at $981.23. The rejection-short variant on the Dow ended at $108.74. It is not optional and not the default book.

Rules, frozen before this score. The line at each close is two confirmed pivot highs (4 bars each side, 10 to 126 sessions apart). An intervening pivot that trades through the segment knocks that pair out. The pair with the most touches wins; a line already under the high loses to one still overhead. A pair older than 80 sessions stays eligible only when price is still within 3 ATR of it. Three touches is a grid cell, not the default. The long is a close at least 0.25 ATR through the line, then within 10 sessions a tag of the line or the breakout close that does not close back under the line, plus a bullish candle (body at least half the range, close in the top third). The fill is the next open. The stop is the retest low. The target is the next confirmed pivot high when that level is at least 0.5R away, otherwise 2R. The 20 EMA trail and a 30-session time stop also exit. No end-of-day flatten. Rejection shorts are the variant: a bearish tag of a line that is already known, and the confirmation bar of a new pivot pair, only while the 9 EMA is under the 20. Stop above that high.

UNH on 2026-10-06. Yahoo's July 16 high is 458.79. The chart label Hi 461.62 is that wick, and it sits about 22 points above this line, so the line is not drawn through the wick tip. The selected anchors are 2026-07-29 at 429.04 and 2026-09-09 at 404.04 (5 touches on the segment, confirmed 2026-09-15). The line is 387.67 on the last bar. Late-July tags: 2026-07-21, 2026-07-22, 2026-07-23, 2026-07-24, 2026-07-28, 2026-07-29, 2026-07-30. Early-September tags: 2026-09-03, 2026-09-08, 2026-09-09. September 7 2026 was Labor Day, so the session cluster is September 3 and September 8-9. The September short, in the variant, is entered the session after that pivot confirms, not on the touch itself. The green boxes on the user's chart are a later hypothetical; they are not a signal this file is required to find.

Chart: `reports/setups/read1d_UNH_2026.png`.

Dow membership follows the point-in-time list. A name is traded only while it is in the index. Yahoo returned no usable daily history for: DWDP, KFT, UTX, WBA. Those gaps are the known delisted or renamed names, not a 2026 survivor list. The named book (SPY, QQQ, IWM, UNH, AAPL, AMD, NVDA, TSLA, MSFT, META) is labeled a survivorship diagnostic. SPY and QQQ debit spreads inside that book are the $1,000 options expression that can actually fit. Singles are 45 DTE, delta 0.45, whole contracts, skipped when the debit is above 20% of equity. A same-day stop counts as a day trade. A swing entry is not blocked just because the stop might hit today; a fourth entry is blocked once three same-day round trips are already on the books. Prices are Black-Scholes on trailing realized volatility times 1.15, with the same haircut as the intraday study. They are not quotes. Nothing was sent to a broker.

### Dow point-in-time, long breakout-retest

42 symbols, 1838 signals (1838 long, 0 short). In sample 2010-01-01 through 2018-12-31. Out of sample 2019-01-01 through 2026-10-06.

Flags, out of sample: stock [oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30, anecdotal_sample], single [oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30, anecdotal_sample], spread [insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, anecdotal_sample]. In-sample stock grid fragile: False.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Stock, full sample | 426 | 39.7% | $33.72 | $-22.90 | $-0.44 | 0.97 | -46.6% | 0.01 | $812.79 | no | 1.00 | 2 | 13 |
| Stock, in sample | 216 | 40.3% | $28.11 | $-17.96 | $0.60 | 1.06 | -28.1% | 0.17 | $1,129.36 | no | 0.05 | 0 | 7 |
| Stock, out of sample | 207 | 39.1% | $36.45 | $-25.45 | $-1.22 | 0.92 | -46.6% | -0.12 | $746.56 | no | 1.00 | 2 | 6 |
| Stock, random entries, out of sample | 368 | 33.7% | $29.17 | $-15.13 | $-0.21 | 0.98 | -36.4% | 0.04 | $923.94 | no | 1.00 | 19 | 0 |
| 30-60 DTE single, full sample | 71 | 22.5% | $12.55 | $-19.83 | $-12.53 | 0.18 | -89.0% | -0.79 | $110.36 | no | 1.00 | 0 | 1594 |
| 30-60 DTE single, in sample | 71 | 22.5% | $12.55 | $-19.83 | $-12.53 | 0.18 | -89.0% | -1.08 | $110.36 | no | 1.00 | 0 | 741 |
| 30-60 DTE single, out of sample | 34 | 14.7% | $19.99 | $-28.23 | $-21.14 | 0.12 | -72.7% | -1.32 | $281.24 | no | 1.00 | 0 | 759 |
| 30-60 DTE single, random entries, out of sample | 22 | 4.5% | $2.26 | $-34.72 | $-33.04 | 0.00 | -73.3% | -0.71 | $273.07 | no | 1.00 | 0 | 774 |
| Debit spread, full sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Debit spread, in sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Debit spread, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Debit spread, random entries, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Stock, walk-forward | 224 | 37.1% | $32.37 | $-23.14 | $-2.57 | 0.82 | -64.8% | -0.43 | $476.79 | no | n/a | 2 | 7 |
| 30-60 DTE single, walk-forward | 77 | 18.2% | $24.29 | $-33.27 | $-22.81 | 0.16 | -91.5% | -1.69 | $88.11 | no | n/a | 0 | 693 |
| Debit spread, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |

Signal grid, in-sample fractional stock:

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| default | 216 | 40.3% | $28.11 | $-17.96 | $0.60 | 1.06 | -28.1% | 0.17 | $1,129.36 | no | 0.05 | 0 | 7 |
| pivot 3/3 | 236 | 40.3% | $20.22 | $-15.02 | $-0.84 | 0.91 | -52.2% | -0.08 | $802.73 | no | 1.00 | 0 | 7 |
| touch 0.25 | 235 | 39.6% | $20.34 | $-14.79 | $-0.89 | 0.90 | -48.5% | -0.10 | $791.96 | no | 1.00 | 0 | 9 |
| touch 1.0 | 225 | 40.9% | $29.81 | $-20.12 | $0.30 | 1.02 | -38.2% | 0.12 | $1,066.63 | no | 0.29 | 0 | 5 |
| buffer 0.1 | 214 | 43.0% | $42.02 | $-25.78 | $3.36 | 1.23 | -28.1% | 0.50 | $1,719.98 | no | 0.00 | 0 | 7 |
| buffer 0.5 | 213 | 41.8% | $34.90 | $-23.39 | $0.97 | 1.07 | -35.7% | 0.21 | $1,206.30 | no | 0.05 | 0 | 6 |
| retest 5d | 212 | 40.1% | $29.82 | $-19.36 | $0.36 | 1.03 | -38.9% | 0.13 | $1,075.46 | no | 0.21 | 0 | 6 |
| retest 20d | 218 | 40.4% | $29.62 | $-18.20 | $1.10 | 1.10 | -28.7% | 0.23 | $1,240.68 | no | 0.00 | 0 | 7 |
| 3 touches | 214 | 41.1% | $28.64 | $-19.42 | $0.34 | 1.03 | -28.1% | 0.13 | $1,073.60 | no | 0.22 | 0 | 5 |

### Named large caps plus SPY and QQQ, survivorship diagnostic

10 symbols, 686 signals (686 long, 0 short). In sample 2010-01-01 through 2018-12-31. Out of sample 2019-01-01 through 2026-10-06.

Flags, out of sample: stock [survivorship_bias, anecdotal_sample], single [survivorship_bias, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30, anecdotal_sample], spread [insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, anecdotal_sample]. In-sample stock grid fragile: False.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Stock, full sample | 269 | 42.4% | $96.62 | $-52.12 | $10.92 | 1.36 | -36.1% | 0.51 | $3,936.45 | no | 0.00 | 0 | 8 |
| Stock, in sample | 144 | 40.3% | $58.81 | $-33.89 | $3.45 | 1.17 | -36.1% | 0.32 | $1,496.69 | no | 0.01 | 0 | 3 |
| Stock, out of sample | 123 | 43.1% | $83.55 | $-44.06 | $10.93 | 1.44 | -27.4% | 0.69 | $2,344.05 | no | 0.00 | 0 | 4 |
| Stock, random entries, out of sample | 204 | 37.7% | $36.45 | $-21.06 | $0.65 | 1.05 | -39.2% | 0.18 | $1,132.11 | no | 0.10 | 1 | 0 |
| 30-60 DTE single, full sample | 42 | 9.5% | $40.63 | $-29.88 | $-23.17 | 0.14 | -97.4% | -1.10 | $27.01 | yes | 1.00 | 0 | 621 |
| 30-60 DTE single, in sample | 42 | 9.5% | $40.63 | $-29.88 | $-23.17 | 0.14 | -97.4% | -1.50 | $27.01 | yes | 1.00 | 0 | 284 |
| 30-60 DTE single, out of sample | 18 | 11.1% | $7.87 | $-38.59 | $-33.43 | 0.03 | -64.0% | -0.95 | $398.35 | no | 1.00 | 0 | 307 |
| 30-60 DTE single, random entries, out of sample | 19 | 10.5% | $197.17 | $-61.78 | $-34.52 | 0.38 | -74.7% | -0.58 | $344.05 | no | 1.00 | 0 | 303 |
| Debit spread, full sample | 20 | 10.0% | $144.22 | $-32.17 | $-14.53 | 0.50 | -33.4% | -0.29 | $709.32 | no | 1.00 | 0 | 99 |
| Debit spread, in sample | 20 | 10.0% | $144.22 | $-32.17 | $-14.53 | 0.50 | -33.4% | -0.40 | $709.32 | no | 1.00 | 0 | 38 |
| Debit spread, out of sample | 1 | 0.0% | $0.00 | $-18.77 | $-18.77 | 0.00 | -5.0% | -0.10 | $981.23 | no | n/a | 0 | 59 |
| Debit spread, random entries, out of sample | 5 | 40.0% | $189.43 | $-80.20 | $27.65 | 1.57 | -16.6% | 0.22 | $1,138.27 | no | 0.00 | 0 | 54 |
| Stock, walk-forward | 123 | 42.3% | $57.17 | $-30.49 | $6.57 | 1.37 | -26.3% | 0.59 | $2,032.65 | no | n/a | 0 | 4 |
| 30-60 DTE single, walk-forward | 25 | 12.0% | $6.61 | $-43.90 | $-37.84 | 0.02 | -74.6% | -1.24 | $281.36 | no | n/a | 0 | 269 |
| Debit spread, walk-forward | 1 | 0.0% | $0.00 | $-18.77 | $-18.77 | 0.00 | -5.0% | -0.10 | $981.23 | no | n/a | 0 | 63 |

Signal grid, in-sample fractional stock:

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| default | 144 | 40.3% | $58.81 | $-33.89 | $3.45 | 1.17 | -36.1% | 0.32 | $1,496.69 | no | 0.01 | 0 | 3 |
| pivot 3/3 | 160 | 38.1% | $58.77 | $-31.95 | $2.64 | 1.13 | -48.2% | 0.29 | $1,422.33 | no | 0.02 | 0 | 2 |
| touch 0.25 | 143 | 37.8% | $49.21 | $-29.97 | $-0.07 | 1.00 | -52.1% | 0.10 | $990.21 | no | 1.00 | 0 | 4 |
| touch 1.0 | 149 | 37.6% | $50.50 | $-29.99 | $0.26 | 1.01 | -49.0% | 0.13 | $1,039.39 | no | 0.63 | 0 | 3 |
| buffer 0.1 | 147 | 41.5% | $52.90 | $-35.07 | $1.43 | 1.07 | -53.0% | 0.21 | $1,210.55 | no | 0.15 | 0 | 4 |
| buffer 0.5 | 151 | 41.1% | $38.71 | $-28.64 | $-0.99 | 0.94 | -40.4% | 0.02 | $850.60 | no | 1.00 | 0 | 3 |
| retest 5d | 132 | 43.2% | $56.94 | $-36.17 | $4.04 | 1.20 | -29.0% | 0.34 | $1,533.02 | no | 0.01 | 0 | 3 |
| retest 20d | 146 | 40.4% | $71.13 | $-38.69 | $5.69 | 1.25 | -27.6% | 0.42 | $1,830.49 | no | 0.00 | 0 | 3 |
| 3 touches | 139 | 39.6% | $58.61 | $-33.66 | $2.85 | 1.14 | -31.6% | 0.28 | $1,395.96 | no | 0.02 | 0 | 3 |

### Dow point-in-time, rejection shorts (variant)

42 symbols, 2466 signals (0 long, 2466 short). In sample 2010-01-01 through 2018-12-31. Out of sample 2019-01-01 through 2026-10-06.

Flags, out of sample: stock [oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30, anecdotal_sample], single [oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30, anecdotal_sample], spread [insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, anecdotal_sample]. In-sample stock grid fragile: False.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Stock, full sample | 597 | 29.8% | $11.65 | $-7.22 | $-1.59 | 0.69 | -95.8% | -0.79 | $48.89 | yes | 1.00 | 19 | 28 |
| Stock, in sample | 314 | 29.6% | $17.41 | $-10.05 | $-1.91 | 0.73 | -71.3% | -0.47 | $398.74 | no | 1.00 | 13 | 13 |
| Stock, out of sample | 283 | 29.7% | $11.75 | $-9.44 | $-3.15 | 0.53 | -89.9% | -1.15 | $108.74 | no | 1.00 | 6 | 15 |
| Stock, random entries, out of sample | 469 | 37.3% | $10.36 | $-8.22 | $-1.29 | 0.75 | -67.2% | -0.47 | $395.23 | no | 1.00 | 44 | 0 |
| 30-60 DTE single, full sample | 48 | 10.4% | $17.79 | $-24.07 | $-19.71 | 0.09 | -95.8% | -0.86 | $54.04 | yes | 1.00 | 2 | 2223 |
| 30-60 DTE single, in sample | 48 | 10.4% | $17.79 | $-24.07 | $-19.71 | 0.09 | -95.8% | -1.17 | $54.04 | yes | 1.00 | 2 | 1050 |
| 30-60 DTE single, out of sample | 24 | 8.3% | $141.39 | $-44.76 | $-29.25 | 0.29 | -73.1% | -0.46 | $298.02 | no | 1.00 | 0 | 1047 |
| 30-60 DTE single, random entries, out of sample | 29 | 13.8% | $8.60 | $-29.65 | $-24.38 | 0.05 | -70.7% | -1.28 | $293.09 | no | 1.00 | 0 | 1121 |
| Debit spread, full sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Debit spread, in sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Debit spread, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Debit spread, random entries, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Stock, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| 30-60 DTE single, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Debit spread, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |

Signal grid, in-sample fractional stock:

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| default | 314 | 29.6% | $17.41 | $-10.05 | $-1.91 | 0.73 | -71.3% | -0.47 | $398.74 | no | 1.00 | 13 | 13 |

Sensitivities on the Dow out-of-sample window. These were not used to pick the default.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| stock: risk 10% | 207 | 39.1% | $36.72 | $-25.45 | $-1.12 | 0.93 | -45.6% | -0.10 | $767.23 | no | 1.00 | 2 | 6 |
| stock: risk 25% | 207 | 39.1% | $36.45 | $-25.45 | $-1.22 | 0.92 | -46.6% | -0.12 | $746.56 | no | 1.00 | 2 | 6 |
| stock: target 1.5R | 227 | 41.9% | $29.20 | $-23.37 | $-1.37 | 0.90 | -50.6% | -0.20 | $688.94 | no | 1.00 | 2 | 6 |
| stock: no EMA trail | 163 | 47.9% | $84.62 | $-59.75 | $9.34 | 1.30 | -34.2% | 0.71 | $2,522.01 | no | 0.01 | 0 | 4 |
| stock: target 2R only | 193 | 33.2% | $49.18 | $-26.46 | $-1.38 | 0.92 | -48.6% | -0.13 | $734.34 | no | 1.00 | 2 | 4 |
| stock: cash account, T+1 | 208 | 38.9% | $36.15 | $-25.16 | $-1.28 | 0.92 | -46.6% | -0.13 | $732.75 | no | 1.00 | 0 | 6 |
| single: 30 DTE | 42 | 31.0% | $22.61 | $-35.21 | $-17.31 | 0.29 | -74.5% | -1.07 | $272.86 | no | 1.00 | 0 | 727 |
| single: 60 DTE | 33 | 21.2% | $13.38 | $-29.74 | $-20.59 | 0.12 | -68.5% | -1.36 | $320.50 | no | 1.00 | 0 | 758 |
| single: delta 0.40 | 38 | 13.2% | $31.03 | $-27.18 | $-19.52 | 0.17 | -74.6% | -1.31 | $258.27 | no | 1.00 | 0 | 750 |
| single: delta 0.50 | 27 | 14.8% | $16.26 | $-30.47 | $-23.55 | 0.09 | -66.0% | -1.25 | $364.28 | no | 1.00 | 0 | 773 |
| single: IV 1.00x realized | 38 | 26.3% | $14.08 | $-30.78 | $-18.97 | 0.16 | -73.2% | -1.16 | $279.11 | no | 1.00 | 0 | 752 |
| single: IV 1.30x realized | 33 | 15.2% | $16.98 | $-27.40 | $-20.68 | 0.11 | -68.5% | -1.40 | $317.57 | no | 1.00 | 0 | 760 |
| single: doubled bid/ask | 21 | 9.5% | $5.39 | $-39.22 | $-34.97 | 0.01 | -73.5% | -1.47 | $265.62 | no | 1.00 | 0 | 789 |
| single: cash account, T+1 | 34 | 14.7% | $19.99 | $-28.23 | $-21.14 | 0.12 | -72.7% | -1.32 | $281.24 | no | 1.00 | 0 | 759 |
| spread: $2 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: $10 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: 30 DTE | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: 60 DTE | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: IV 1.00x realized | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: IV 1.30x realized | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: doubled bid/ask | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: cash account, T+1 | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |

Sensitivities on the named-list out-of-sample window, same rule.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| stock: risk 10% | 123 | 43.1% | $82.13 | $-43.44 | $10.67 | 1.43 | -26.7% | 0.68 | $2,312.46 | no | 0.00 | 0 | 4 |
| stock: risk 25% | 123 | 43.1% | $83.55 | $-44.06 | $10.93 | 1.44 | -27.4% | 0.69 | $2,344.05 | no | 0.00 | 0 | 4 |
| stock: target 1.5R | 132 | 45.5% | $58.83 | $-40.80 | $4.49 | 1.20 | -32.5% | 0.42 | $1,592.06 | no | 0.01 | 0 | 4 |
| stock: no EMA trail | 110 | 50.9% | $125.17 | $-73.52 | $27.63 | 1.77 | -30.6% | 1.00 | $4,039.63 | no | 0.00 | 0 | 5 |
| stock: target 2R only | 113 | 38.1% | $204.79 | $-80.74 | $27.91 | 1.56 | -30.5% | 1.08 | $4,154.23 | no | 0.00 | 0 | 3 |
| stock: cash account, T+1 | 123 | 43.1% | $83.55 | $-44.06 | $10.93 | 1.44 | -27.4% | 0.69 | $2,344.05 | no | 0.00 | 0 | 4 |
| single: 30 DTE | 18 | 11.1% | $8.75 | $-41.07 | $-35.54 | 0.03 | -68.7% | -0.83 | $360.31 | no | 1.00 | 0 | 307 |
| single: 60 DTE | 16 | 12.5% | $10.10 | $-39.18 | $-33.02 | 0.04 | -56.5% | -0.88 | $471.66 | no | 1.00 | 0 | 310 |
| single: delta 0.40 | 18 | 5.6% | $11.74 | $-34.84 | $-32.25 | 0.02 | -62.1% | -0.92 | $419.48 | no | 1.00 | 0 | 307 |
| single: delta 0.50 | 16 | 12.5% | $7.87 | $-41.20 | $-35.06 | 0.03 | -60.3% | -0.87 | $438.97 | no | 1.00 | 0 | 309 |
| single: IV 1.00x realized | 18 | 11.1% | $8.39 | $-39.86 | $-34.50 | 0.03 | -66.7% | -0.88 | $379.03 | no | 1.00 | 0 | 307 |
| single: IV 1.30x realized | 15 | 13.3% | $9.94 | $-41.95 | $-35.03 | 0.04 | -56.0% | -0.87 | $474.49 | no | 1.00 | 0 | 311 |
| single: doubled bid/ask | 15 | 0.0% | $0.00 | $-46.59 | $-46.59 | 0.00 | -71.0% | -1.14 | $301.16 | no | 1.00 | 0 | 311 |
| single: cash account, T+1 | 18 | 11.1% | $7.87 | $-38.59 | $-33.43 | 0.03 | -64.0% | -0.95 | $398.35 | no | 1.00 | 0 | 307 |
| spread: $2 wide | 4 | 0.0% | $0.00 | $-114.07 | $-114.07 | 0.00 | -45.6% | -0.68 | $543.72 | no | n/a | 0 | 57 |
| spread: $10 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 61 |
| spread: 30 DTE | 3 | 0.0% | $0.00 | $-52.13 | $-52.13 | 0.00 | -15.6% | -0.51 | $843.61 | no | n/a | 0 | 57 |
| spread: 60 DTE | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 61 |
| spread: IV 1.00x realized | 3 | 0.0% | $0.00 | $-43.84 | $-43.84 | 0.00 | -13.2% | -0.45 | $868.48 | no | n/a | 0 | 57 |
| spread: IV 1.30x realized | 1 | 0.0% | $0.00 | $-99.48 | $-99.48 | 0.00 | -9.9% | -0.43 | $900.52 | no | n/a | 0 | 60 |
| spread: doubled bid/ask | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 61 |
| spread: cash account, T+1 | 1 | 0.0% | $0.00 | $-18.77 | $-18.77 | 0.00 | -5.0% | -0.10 | $981.23 | no | n/a | 0 | 59 |

SPY buy and hold, whole shares that fit in $1,000, 2019-01-01 through 2026-10-06: 4 shares, ending $3,242.23, Sharpe 0.95, max drawdown -30.7%.

Profit factor gate 1.10, Sharpe gate 0.40, drawdown no worse than -30%, and at least 300 trades. The named list carries survivorship_bias, which blocks it. The Dow stock book and the named-list spread book would both have to clear the gates. Under 300 trades the sample is anecdotal. This does not join the optional list or the registry.
<!-- CHART_READS_C_END -->

<!-- CHART_READS_D_START -->
## Setup D: three breakout types

DOES NOT PASS. Dow point-in-time stock, out of sample, ended at $919.45 on 73 trades (profit factor 0.92, Sharpe -0.03). The same signals as 45 DTE calls ended at $435.61 with 93 skipped because the contract did not fit the risk cap. The named large-cap list is a survivorship diagnostic: stock ended at $1,174.40, and SPY/QQQ debit spreads ended at $1,000.00. The 15-minute and 60-minute books are inside the free Yahoo intraday cap, so they are anecdotal. It is not optional and not the default book.

Rules, frozen before this score. A descending triangle is a flat support with at least two confirmed pivot lows and at least two lower highs. It is a short only, through the support. An ascending triangle is a flat resistance and higher lows. It is a long only, through the resistance. A range has both sides flat, at least two touches each, and may break either way. Pivots are 4 bars on each side. The pattern is 15 to 80 bars long and must still be open (the sloped side has not crossed the flat side). The flat side's prices sit within 0.50 ATR. The sloped side rises or falls at least 0.75 ATR, which is what separates it from a second flat side. Three touches on the flat side is a grid cell. The trigger is a close at least 0.25 ATR beyond the level on a confirming candle (body at least half the range, close in the outer third), or that same candle within the next 3 bars if the first close through is not itself confirming. A retest that holds is the other grid cell, not the default. The fill is the next open. The stop is the signal bar's high on a short and its low on a long. The retest variant uses the retest extreme instead. The target is the pattern height measured from the broken level when that distance is at least 0.5R, otherwise 2R. Daily holds trail the 20 EMA for up to 30 sessions and do not flatten at the close. A close the other way through the sloped side cancels the triangle. Nothing was sent to a broker.

Dow membership follows the point-in-time list. Yahoo returned no usable daily history for: DWDP, KFT, UTX, WBA. The named book (SPY, QQQ, IWM, UNH, AAPL, AMD, NVDA, TSLA, MSFT, META) is a survivorship diagnostic. SPY and QQQ debit spreads are the options expression that can fit a $1,000 account. Singles are 45 DTE, delta 0.45, whole contracts, skipped when the debit is above 20% of equity. Prices are Black-Scholes on trailing realized volatility times 1.15. They are not quotes. The 15-minute and 60-minute runs use the same pivot rules on the named list. Fifteen-minute trades flatten the same session. Sixty-minute trades can be held for 5 sessions. Both clocks are short samples.

### Dow point-in-time, three breakout types

42 symbols, 292 signals (164 long, 128 short; lower highs + flat support, breakdown 79, higher lows + flat resistance, breakout 121, horizontal range 92). In sample 2010-01-01 through 2018-12-31. Out of sample 2019-01-01 through 2026-10-06.

Flags, out of sample: stock [oos_profit_factor_below_1, oos_sharpe_negative, anecdotal_sample], single [insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, oos_drawdown_beyond_30, anecdotal_sample], spread [insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, anecdotal_sample]. In-sample stock grid fragile: False.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Stock, full sample | 172 | 28.5% | $53.27 | $-20.99 | $0.17 | 1.01 | -48.2% | 0.07 | $1,028.76 | no | 0.59 | 0 | 4 |
| Stock, in sample | 99 | 29.3% | $54.88 | $-21.04 | $1.20 | 1.08 | -36.8% | 0.17 | $1,118.89 | no | 0.02 | 0 | 2 |
| Stock, out of sample | 73 | 27.4% | $45.53 | $-18.70 | $-1.10 | 0.92 | -26.3% | -0.03 | $919.45 | no | 1.00 | 0 | 2 |
| Stock, random entries, out of sample | 98 | 37.8% | $17.94 | $-14.25 | $-2.10 | 0.76 | -26.9% | -0.27 | $794.46 | no | 1.00 | 0 | 0 |
| 30-60 DTE single, full sample | 46 | 19.6% | $93.68 | $-43.13 | $-16.37 | 0.53 | -78.9% | -0.27 | $247.19 | no | 1.00 | 0 | 206 |
| 30-60 DTE single, in sample | 46 | 19.6% | $93.68 | $-43.13 | $-16.37 | 0.53 | -78.9% | -0.37 | $247.19 | no | 1.00 | 0 | 90 |
| 30-60 DTE single, out of sample | 19 | 15.8% | $184.06 | $-69.79 | $-29.70 | 0.49 | -70.8% | -0.55 | $435.61 | no | 1.00 | 0 | 93 |
| 30-60 DTE single, random entries, out of sample | 11 | 9.1% | $1.16 | $-41.16 | $-37.31 | 0.00 | -41.0% | -0.63 | $589.59 | no | 1.00 | 0 | 104 |
| Debit spread, full sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Debit spread, in sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Debit spread, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Debit spread, random entries, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Stock, walk-forward | 134 | 29.9% | $45.59 | $-23.16 | $-2.63 | 0.84 | -40.2% | -0.19 | $675.83 | no | n/a | 0 | 5 |
| 30-60 DTE single, walk-forward | 41 | 14.6% | $149.30 | $-60.36 | $-29.67 | 0.42 | -83.5% | -0.62 | $216.95 | no | n/a | 0 | 237 |
| Debit spread, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |

Signal grid, in-sample fractional stock:

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| default | 99 | 29.3% | $54.88 | $-21.04 | $1.20 | 1.08 | -36.8% | 0.17 | $1,118.89 | no | 0.02 | 0 | 2 |
| pivot 3/3 | 85 | 25.9% | $29.95 | $-15.47 | $-3.71 | 0.68 | -37.0% | -0.41 | $684.41 | no | 1.00 | 0 | 2 |
| touch 0.25 | 43 | 25.6% | $36.75 | $-19.20 | $-4.88 | 0.66 | -31.0% | -0.29 | $789.95 | no | 1.00 | 0 | 0 |
| touch 1.0 | 182 | 37.9% | $60.83 | $-26.77 | $6.44 | 1.39 | -25.4% | 0.68 | $2,171.99 | no | 0.00 | 0 | 3 |
| buffer 0.1 | 90 | 25.6% | $53.57 | $-19.73 | $-1.00 | 0.93 | -37.4% | -0.05 | $910.35 | no | 1.00 | 0 | 1 |
| buffer 0.5 | 97 | 30.9% | $50.94 | $-21.86 | $0.65 | 1.04 | -36.8% | 0.12 | $1,063.33 | no | 0.14 | 0 | 2 |
| 3 flat touches | 58 | 25.9% | $39.72 | $-16.42 | $-1.90 | 0.84 | -34.4% | -0.13 | $889.94 | no | 1.00 | 0 | 0 |
| span 10 | 151 | 30.5% | $44.65 | $-19.88 | $-0.22 | 0.98 | -40.6% | 0.04 | $966.47 | no | 1.00 | 0 | 2 |
| span 30 | 10 | 40.0% | $77.56 | $-23.77 | $16.76 | 2.18 | -5.0% | 0.45 | $1,167.62 | no | 0.00 | 0 | 0 |
| retest | 51 | 29.4% | $70.46 | $-23.71 | $3.98 | 1.24 | -19.8% | 0.27 | $1,203.11 | no | 0.00 | 0 | 2 |

### Named large caps plus SPY and QQQ, survivorship diagnostic

10 symbols, 89 signals (43 long, 46 short; lower highs + flat support, breakdown 26, higher lows + flat resistance, breakout 28, horizontal range 35). In sample 2010-01-01 through 2018-12-31. Out of sample 2019-01-01 through 2026-10-06.

Flags, out of sample: stock [survivorship_bias, oos_sharpe_below_0_40, oos_drawdown_beyond_30, anecdotal_sample], single [survivorship_bias, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, anecdotal_sample], spread [insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, anecdotal_sample]. In-sample stock grid fragile: False.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Stock, full sample | 66 | 37.9% | $86.44 | $-35.00 | $11.00 | 1.51 | -34.6% | 0.38 | $1,725.88 | no | 0.00 | 0 | 3 |
| Stock, in sample | 31 | 38.7% | $81.16 | $-25.34 | $15.88 | 2.02 | -12.0% | 0.53 | $1,492.40 | no | 0.00 | 0 | 0 |
| Stock, out of sample | 35 | 37.1% | $62.13 | $-28.79 | $4.98 | 1.28 | -30.9% | 0.25 | $1,174.40 | no | 0.00 | 0 | 3 |
| Stock, random entries, out of sample | 48 | 37.5% | $25.36 | $-18.41 | $-2.00 | 0.83 | -19.6% | -0.09 | $904.23 | no | 1.00 | 0 | 0 |
| 30-60 DTE single, full sample | 15 | 20.0% | $69.23 | $-67.65 | $-40.27 | 0.26 | -63.0% | -0.42 | $395.94 | no | 1.00 | 0 | 71 |
| 30-60 DTE single, in sample | 15 | 20.0% | $69.23 | $-67.65 | $-40.27 | 0.26 | -63.0% | -0.57 | $395.94 | no | 1.00 | 0 | 22 |
| 30-60 DTE single, out of sample | 1 | 0.0% | $0.00 | $-44.68 | $-44.68 | 0.00 | -4.5% | -0.50 | $955.32 | no | n/a | 0 | 48 |
| 30-60 DTE single, random entries, out of sample | 4 | 0.0% | $0.00 | $-79.56 | $-79.56 | 0.00 | -31.8% | -0.62 | $681.75 | no | n/a | 0 | 45 |
| Debit spread, full sample | 1 | 0.0% | $0.00 | $-90.37 | $-90.37 | 0.00 | -11.0% | -0.24 | $909.63 | no | n/a | 0 | 10 |
| Debit spread, in sample | 1 | 0.0% | $0.00 | $-90.37 | $-90.37 | 0.00 | -11.0% | -0.33 | $909.63 | no | n/a | 0 | 0 |
| Debit spread, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 10 |
| Debit spread, random entries, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 10 |
| Stock, walk-forward | 25 | 32.0% | $64.15 | $-26.51 | $2.51 | 1.14 | -30.9% | 0.13 | $1,057.21 | no | n/a | 0 | 1 |
| 30-60 DTE single, walk-forward | 1 | 0.0% | $0.00 | $-44.68 | $-44.68 | 0.00 | -4.5% | -0.50 | $955.32 | no | n/a | 0 | 48 |
| Debit spread, walk-forward | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 10 |

Signal grid, in-sample fractional stock:

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| default | 31 | 38.7% | $81.16 | $-25.34 | $15.88 | 2.02 | -12.0% | 0.53 | $1,492.40 | no | 0.00 | 0 | 0 |
| pivot 3/3 | 24 | 25.0% | $53.31 | $-24.70 | $-5.20 | 0.72 | -23.6% | -0.19 | $875.19 | no | 1.00 | 0 | 1 |
| touch 0.25 | 10 | 30.0% | $50.82 | $-18.33 | $2.41 | 1.19 | -7.5% | 0.08 | $1,024.12 | no | 0.00 | 0 | 0 |
| touch 1.0 | 84 | 35.7% | $85.34 | $-33.72 | $8.80 | 1.41 | -26.6% | 0.48 | $1,739.50 | no | 0.00 | 0 | 1 |
| buffer 0.1 | 28 | 39.3% | $77.44 | $-26.36 | $14.42 | 1.90 | -13.7% | 0.47 | $1,403.81 | no | 0.00 | 0 | 1 |
| buffer 0.5 | 31 | 35.5% | $63.84 | $-24.09 | $7.11 | 1.46 | -14.5% | 0.31 | $1,220.54 | no | 0.00 | 0 | 0 |
| 3 flat touches | 12 | 33.3% | $101.23 | $-25.73 | $16.59 | 1.97 | -10.0% | 0.35 | $1,199.05 | no | 0.00 | 0 | 0 |
| span 10 | 60 | 31.7% | $71.26 | $-26.71 | $4.31 | 1.24 | -21.2% | 0.29 | $1,258.89 | no | 0.00 | 0 | 1 |
| span 30 | 1 | 0.0% | $0.00 | $-13.28 | $-13.28 | 0.00 | -2.5% | -0.19 | $986.72 | no | n/a | 0 | 0 |
| retest | 16 | 25.0% | $93.52 | $-25.27 | $4.43 | 1.23 | -20.5% | 0.14 | $1,070.86 | no | 0.00 | 0 | 0 |

Sensitivities on the Dow out-of-sample window. These were not used to pick the default.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| stock: risk 10% | 73 | 27.4% | $45.53 | $-18.70 | $-1.10 | 0.92 | -26.3% | -0.03 | $919.45 | no | 1.00 | 0 | 2 |
| stock: risk 25% | 73 | 27.4% | $45.53 | $-18.70 | $-1.10 | 0.92 | -26.3% | -0.03 | $919.45 | no | 1.00 | 0 | 2 |
| stock: target 1.5R | 73 | 27.4% | $40.61 | $-18.19 | $-2.08 | 0.84 | -29.2% | -0.12 | $848.14 | no | 1.00 | 0 | 2 |
| stock: no EMA trail | 71 | 31.0% | $38.37 | $-21.46 | $-2.92 | 0.80 | -35.1% | -0.17 | $792.57 | no | 1.00 | 0 | 2 |
| stock: target 2R only | 72 | 27.8% | $53.53 | $-20.31 | $0.20 | 1.01 | -18.7% | 0.07 | $1,014.72 | no | 0.51 | 0 | 2 |
| stock: cash account, T+1 | 73 | 27.4% | $45.53 | $-18.70 | $-1.10 | 0.92 | -26.3% | -0.03 | $919.45 | no | 1.00 | 0 | 2 |
| single: 30 DTE | 20 | 15.0% | $193.16 | $-68.91 | $-29.60 | 0.49 | -70.9% | -0.48 | $407.99 | no | 1.00 | 0 | 93 |
| single: 60 DTE | 19 | 15.8% | $174.12 | $-62.39 | $-25.05 | 0.52 | -63.9% | -0.43 | $524.09 | no | 1.00 | 0 | 93 |
| single: delta 0.40 | 24 | 16.7% | $245.34 | $-77.22 | $-23.46 | 0.64 | -77.6% | -0.28 | $436.93 | no | 1.00 | 0 | 87 |
| single: delta 0.50 | 18 | 16.7% | $184.06 | $-67.62 | $-25.67 | 0.54 | -64.0% | -0.37 | $537.89 | no | 1.00 | 0 | 93 |
| single: IV 1.00x realized | 21 | 14.3% | $191.12 | $-66.47 | $-29.67 | 0.48 | -72.9% | -0.52 | $376.92 | no | 1.00 | 0 | 91 |
| single: IV 1.30x realized | 20 | 15.0% | $174.70 | $-61.77 | $-26.30 | 0.50 | -67.4% | -0.50 | $474.02 | no | 1.00 | 0 | 92 |
| single: doubled bid/ask | 15 | 13.3% | $246.50 | $-78.29 | $-34.98 | 0.48 | -66.2% | -0.49 | $475.26 | no | 1.00 | 0 | 100 |
| single: cash account, T+1 | 19 | 15.8% | $184.06 | $-69.79 | $-29.70 | 0.49 | -70.8% | -0.55 | $435.61 | no | 1.00 | 0 | 93 |
| spread: $2 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: $10 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: 30 DTE | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: 60 DTE | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: IV 1.00x realized | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: IV 1.30x realized | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: doubled bid/ask | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| spread: cash account, T+1 | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |

Sensitivities on the named-list out-of-sample window, same rule.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| stock: risk 10% | 35 | 37.1% | $62.13 | $-28.79 | $4.98 | 1.28 | -30.9% | 0.25 | $1,174.40 | no | 0.00 | 0 | 3 |
| stock: risk 25% | 35 | 37.1% | $62.13 | $-28.79 | $4.98 | 1.28 | -30.9% | 0.25 | $1,174.40 | no | 0.00 | 0 | 3 |
| stock: target 1.5R | 35 | 37.1% | $61.12 | $-28.76 | $4.62 | 1.26 | -30.9% | 0.24 | $1,161.81 | no | 0.00 | 0 | 3 |
| stock: no EMA trail | 35 | 34.3% | $72.98 | $-30.44 | $5.02 | 1.25 | -32.1% | 0.25 | $1,175.78 | no | 0.00 | 0 | 3 |
| stock: target 2R only | 36 | 30.6% | $31.94 | $-25.08 | $-7.66 | 0.56 | -33.9% | -0.32 | $724.35 | no | 1.00 | 0 | 3 |
| stock: cash account, T+1 | 35 | 37.1% | $62.13 | $-28.79 | $4.98 | 1.28 | -30.9% | 0.25 | $1,174.40 | no | 0.00 | 0 | 3 |
| single: 30 DTE | 1 | 0.0% | $0.00 | $-46.39 | $-46.39 | 0.00 | -4.6% | -0.51 | $953.61 | no | n/a | 0 | 48 |
| single: 60 DTE | 1 | 0.0% | $0.00 | $-46.07 | $-46.07 | 0.00 | -4.6% | -0.49 | $953.93 | no | n/a | 0 | 48 |
| single: delta 0.40 | 1 | 0.0% | $0.00 | $-42.57 | $-42.57 | 0.00 | -4.3% | -0.48 | $957.43 | no | n/a | 0 | 48 |
| single: delta 0.50 | 1 | 0.0% | $0.00 | $-47.47 | $-47.47 | 0.00 | -4.7% | -0.50 | $952.53 | no | n/a | 0 | 48 |
| single: IV 1.00x realized | 1 | 0.0% | $0.00 | $-46.69 | $-46.69 | 0.00 | -4.7% | -0.51 | $953.31 | no | n/a | 0 | 48 |
| single: IV 1.30x realized | 1 | 0.0% | $0.00 | $-45.05 | $-45.05 | 0.00 | -4.5% | -0.50 | $954.95 | no | n/a | 0 | 48 |
| single: doubled bid/ask | 1 | 0.0% | $0.00 | $-63.01 | $-63.01 | 0.00 | -6.3% | -0.46 | $936.99 | no | n/a | 0 | 48 |
| single: cash account, T+1 | 1 | 0.0% | $0.00 | $-44.68 | $-44.68 | 0.00 | -4.5% | -0.50 | $955.32 | no | n/a | 0 | 48 |
| spread: $2 wide | 1 | 0.0% | $0.00 | $-179.79 | $-179.79 | 0.00 | -18.0% | -0.36 | $820.21 | no | n/a | 0 | 9 |
| spread: $10 wide | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 10 |
| spread: 30 DTE | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 10 |
| spread: 60 DTE | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 10 |
| spread: IV 1.00x realized | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 10 |
| spread: IV 1.30x realized | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 10 |
| spread: doubled bid/ask | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 10 |
| spread: cash account, T+1 | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 10 |

### 60-minute, anecdotal

10 symbols, 47 signals (20 long, 27 short; lower highs + flat support, breakdown 18, higher lows + flat resistance, breakout 13, horizontal range 16). 493 sessions, 2024-10-17 through 2026-10-06. In sample through 2025-12-19. Out of sample 2025-12-22 through 2026-10-06.

Flags, out of sample: stock [short_sample, survivorship_bias, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_negative, anecdotal_sample], single [short_sample, survivorship_bias, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, anecdotal_sample], spread [short_sample, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, anecdotal_sample]. In-sample stock grid fragile: False.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Stock, full sample | 38 | 21.1% | $12.54 | $-11.80 | $-6.67 | 0.28 | -26.0% | -1.66 | $746.37 | no | 1.00 | 0 | 0 |
| Stock, in sample | 22 | 18.2% | $13.90 | $-12.00 | $-7.29 | 0.26 | -16.8% | -2.36 | $839.57 | no | 1.00 | 0 | 0 |
| Stock, out of sample | 16 | 25.0% | $13.32 | $-13.69 | $-6.94 | 0.32 | -12.5% | -1.23 | $888.99 | no | 1.00 | 0 | 0 |
| Stock, random entries, out of sample | 16 | 37.5% | $2.31 | $-7.08 | $-3.56 | 0.20 | -5.7% | -1.49 | $943.10 | no | 1.00 | 0 | 0 |
| 30-60 DTE single, full sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 47 |
| 30-60 DTE single, in sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 30 |
| 30-60 DTE single, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 17 |
| 30-60 DTE single, random entries, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 17 |
| Debit spread, full sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 6 |
| Debit spread, in sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 4 |
| Debit spread, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 2 |
| Debit spread, random entries, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 2 |

### 15-minute, anecdotal

10 symbols, 16 signals (10 long, 6 short; lower highs + flat support, breakdown 5, higher lows + flat resistance, breakout 8, horizontal range 3). 38 sessions, 2026-08-13 through 2026-10-06. In sample through 2026-09-14. Out of sample 2026-09-15 through 2026-10-06.

Flags, out of sample: stock [short_sample, survivorship_bias, insufficient_trades, anecdotal_sample], single [short_sample, survivorship_bias, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, anecdotal_sample], spread [short_sample, insufficient_trades, oos_profit_factor_below_1, oos_sharpe_below_0_40, anecdotal_sample]. In-sample stock grid fragile: False.

| Book | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Ending | Bust | Ruin est. | PDT blocked | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| Stock, full sample | 12 | 41.7% | $5.90 | $-5.22 | $-0.59 | 0.81 | -2.1% | -0.77 | $992.98 | no | 1.00 | 0 | 0 |
| Stock, in sample | 6 | 33.3% | $4.50 | $-5.39 | $-2.10 | 0.42 | -1.6% | -2.83 | $987.42 | no | 1.00 | 0 | 0 |
| Stock, out of sample | 6 | 50.0% | $6.92 | $-5.04 | $0.94 | 1.37 | -1.0% | 1.35 | $1,005.63 | no | 0.00 | 0 | 0 |
| Stock, random entries, out of sample | 8 | 25.0% | $0.85 | $-4.29 | $-3.00 | 0.07 | -2.4% | -9.69 | $975.98 | no | 1.00 | 0 | 0 |
| 30-60 DTE single, full sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 16 |
| 30-60 DTE single, in sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 8 |
| 30-60 DTE single, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 8 |
| 30-60 DTE single, random entries, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 8 |
| Debit spread, full sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 4 |
| Debit spread, in sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 4 |
| Debit spread, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |
| Debit spread, random entries, out of sample | 0 | 0.0% | $0.00 | $0.00 | $0.00 | n/a | 0.0% | 0.00 | $1,000.00 | no | n/a | 0 | 0 |

Charts: `reports/setups/readD_1d_Dd_BA_2026-09-22.png`, `reports/setups/readD_1d_Da_NVDA_2026-08-07.png`, `reports/setups/readD_1d_Dr_QQQ_2026-04-14.png`, `reports/setups/readD_60m_Dd_AAPL_2026-08-11.png`, `reports/setups/readD_60m_Da_META_2026-10-05.png`, `reports/setups/readD_60m_Dr_TSLA_2026-09-03.png`, `reports/setups/readD_15m_Dd_UNH_2026-09-22.png`, `reports/setups/readD_15m_Da_TSLA_2026-09-30.png`, `reports/setups/readD_15m_Dr_MSFT_2026-09-30.png`.

SPY buy and hold, whole shares that fit in $1,000, 2019-01-01 through 2026-10-06: 4 shares, ending $3,242.23, Sharpe 0.95, max drawdown -30.7%.

Profit factor gate 1.10, Sharpe gate 0.40, drawdown no worse than -30%, and at least 300 trades. The named list carries survivorship_bias, which blocks it. The Dow stock book and the named-list spread book would both have to clear the gates. The intraday clocks carry short_sample. Under 300 trades the sample is anecdotal. This does not join the optional list or the registry.
<!-- CHART_READS_D_END -->




<!-- CHART_READS_SR_START -->
## Support and resistance level set

DOES NOT CHANGE THE GATE. Setups A, B, C, and D keep the targets already scored. This section only asks which objective level, used as the profit target on those same signals, improves the out-of-sample fractional-stock book. The definitions below were frozen before this score. Nothing was sent to a broker.

These rows met the pre-registered improvement test: floor pivots PP R1 S1 R2 S2 on A, 60-minute; flipped S/R on C, daily Dow; confluence, two or more sources on C, daily Dow; horizontal pivots on D, daily Dow; confluence, two or more sources on D, daily Dow; nearest of any source on D, daily Dow. Floor pivots on A, 60-minute ended at $928.24 against the published $886.97, profit factor 0.91, Sharpe -0.40, drawdown -14.8%. In sample it ended at $675.19 against $676.70. Flipped S/R on C, daily Dow ended at $939.99 against the published $746.56, profit factor 0.98, Sharpe 0.05, drawdown -36.9%. In sample it ended at $1,030.41 against $1,129.36. Confluence, two or more sources on C, daily Dow ended at $812.57 against the published $746.56, profit factor 0.95, Sharpe -0.05, drawdown -46.5%. In sample it ended at $1,146.01 against $1,129.36. Horizontal pivots on D, daily Dow ended at $921.85 against the published $919.45, profit factor 0.92, Sharpe -0.05, drawdown -21.5%. In sample it ended at $828.26 against $1,118.89. Confluence, two or more sources on D, daily Dow ended at $970.48 against the published $919.45, profit factor 0.97, Sharpe 0.02, drawdown -18.1%. In sample it ended at $804.52 against $1,118.89. Nearest of any source on D, daily Dow ended at $922.48 against the published $919.45, profit factor 0.92, Sharpe -0.05, drawdown -20.7%. In sample it ended at $740.32 against $1,118.89. None of those rows clears a 1.10 profit factor, a 0.40 Sharpe, a drawdown no worse than -30%, and 300 trades. Meeting the test does not make the row the gate. The comparison was scored after the A-D defaults were already frozen, so choosing one of these rows now would be after the fact. None is added to the optional list or the registry.

A level is known only at the close that completes it. Horizontal pivots are the last six confirmed pivot highs and the last six confirmed pivot lows, four bars on each side, inside 120 bars. Floor pivots use the prior session's high, low, and close: PP = (H+L+C)/3, R1 = 2×PP−L, S1 = 2×PP−H, R2 = PP+(H−L), S2 = PP−(H−L). Prior-day high and low are that same session. A demand or supply zone is a four-bar base no wider than 1.25 ATR followed by a bar whose body is at least 1 ATR and at least 55% of its range. The level is the near edge of the base. It expires after 60 bars or when a later close trades through the far edge. Fibonacci is 38.2%, 50%, and 61.8% of the latest confirmed swing, five to 80 bars long, with the end pivot no more than 80 bars old. The trendline is the rising line through the latest confirmed pivot low and the nearest earlier lower one, and the falling mirror on pivot highs. A flipped level is a pivot high that a later close has traded above, or a pivot low that a later close has traded below. Confluence is two or more of those sources within 0.50 ATR; the target is their average. "Nearest of any source" takes the closest single-source price.

The target is the nearest level between 0.5R and 4R from the next open, on the trade side. If that source has no such level, the target is 2R. Stops, the 20 EMA trail, the hold limit, the one-position rule, and the 20% risk cap are unchanged. "Signals with a level" is the share of out-of-sample signals that had a level in that range, before the one-position book skipped any. A row improves the book only when the out-of-sample ending equity is higher, profit factor is not lower, max drawdown is not worse by more than five points, there are at least 20 trades, and at least 30% of the out-of-sample signals had a level. In-sample ending equity is shown so a late improvement is visible next to the training window. It is not used to pick a row.

### A, 60-minute

457 signals. In sample 2024-10-17 through 2025-10-10. Out of sample 2025-10-13 through 2026-10-06. Named large-cap list. Stock only. Hourly history is inside the free Yahoo cap, so the sample is short.

| Level | IS trades | IS ending | OOS trades | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Signals with a level | Improves |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published target | 117 | $676.70 | 131 | 0.86 | -0.65 | -14.0% | $886.97 | — | — |
| horizontal pivots | 118 | $650.32 | 131 | 0.84 | -0.81 | -17.8% | $872.42 | 42% | no |
| floor pivots PP R1 S1 R2 S2 | 120 | $675.19 | 131 | 0.91 | -0.40 | -14.8% | $928.24 | 49% | yes |
| prior-day high and low | 117 | $669.15 | 131 | 0.83 | -0.88 | -16.4% | $860.05 | 14% | no |
| demand and supply zones | 117 | $674.19 | 131 | 0.83 | -0.81 | -16.4% | $863.52 | 5% | no |
| Fibonacci 38.2/50/61.8 | 117 | $676.70 | 131 | 0.85 | -0.70 | -14.8% | $879.40 | 1% | no |
| trendline | 119 | $696.52 | 131 | 0.97 | -0.06 | -12.6% | $976.07 | 21% | no |
| flipped S/R | 117 | $612.32 | 131 | 0.81 | -0.95 | -16.7% | $848.03 | 11% | no |
| confluence, two or more sources | 118 | $662.13 | 131 | 0.82 | -0.92 | -16.1% | $857.24 | 34% | no |
| nearest of any source | 121 | $643.48 | 132 | 0.84 | -0.81 | -18.7% | $882.10 | 64% | no |

### B, 60-minute

235 signals. In sample 2024-10-17 through 2025-10-10. Out of sample 2025-10-13 through 2026-10-06. Named large-cap list. Stock only. Hourly history is inside the free Yahoo cap, so the sample is short.

| Level | IS trades | IS ending | OOS trades | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Signals with a level | Improves |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published target | 70 | $972.61 | 85 | 0.86 | -0.36 | -23.8% | $921.86 | — | — |
| horizontal pivots | 75 | $1,081.52 | 87 | 0.66 | -1.04 | -27.1% | $828.33 | 96% | no |
| floor pivots PP R1 S1 R2 S2 | 75 | $849.77 | 86 | 0.77 | -0.68 | -26.8% | $876.10 | 61% | no |
| prior-day high and low | 71 | $960.15 | 85 | 0.86 | -0.35 | -24.3% | $924.03 | 19% | no |
| demand and supply zones | 70 | $1,028.75 | 85 | 0.93 | -0.13 | -22.1% | $961.54 | 20% | no |
| Fibonacci 38.2/50/61.8 | 70 | $973.55 | 85 | 0.86 | -0.36 | -23.8% | $921.86 | 5% | no |
| trendline | 71 | $1,054.39 | 85 | 0.82 | -0.49 | -25.2% | $899.22 | 24% | no |
| flipped S/R | 70 | $949.21 | 88 | 0.76 | -0.68 | -25.0% | $877.49 | 74% | no |
| confluence, two or more sources | 71 | $877.66 | 87 | 0.72 | -0.88 | -26.3% | $851.92 | 87% | no |
| nearest of any source | 75 | $925.37 | 87 | 0.68 | -0.96 | -27.1% | $839.06 | 97% | no |

### A and B, 60-minute

692 signals. In sample 2024-10-17 through 2025-10-10. Out of sample 2025-10-13 through 2026-10-06. Named large-cap list. Stock only. Hourly history is inside the free Yahoo cap, so the sample is short.

The published-target row matches the gated out-of-sample stock book ($967.77 on 164 trades).

| Level | IS trades | IS ending | OOS trades | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Signals with a level | Improves |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published target | 134 | $880.43 | 164 | 0.97 | -0.03 | -19.9% | $967.77 | — | — |
| horizontal pivots | 144 | $938.34 | 169 | 0.89 | -0.39 | -18.4% | $896.81 | 61% | no |
| floor pivots PP R1 S1 R2 S2 | 144 | $795.34 | 172 | 0.94 | -0.20 | -19.7% | $935.40 | 53% | no |
| prior-day high and low | 140 | $819.95 | 165 | 0.96 | -0.08 | -19.8% | $956.97 | 15% | no |
| demand and supply zones | 137 | $914.55 | 169 | 1.04 | 0.29 | -14.7% | $1,040.15 | 10% | no |
| Fibonacci 38.2/50/61.8 | 137 | $868.70 | 164 | 0.97 | -0.03 | -19.9% | $967.77 | 2% | no |
| trendline | 136 | $938.94 | 163 | 1.02 | 0.20 | -19.5% | $1,019.61 | 22% | no |
| flipped S/R | 133 | $838.08 | 169 | 0.93 | -0.19 | -19.2% | $934.52 | 33% | no |
| confluence, two or more sources | 141 | $771.98 | 170 | 0.91 | -0.32 | -17.9% | $912.67 | 52% | no |
| nearest of any source | 144 | $896.71 | 172 | 0.83 | -0.73 | -23.3% | $840.22 | 76% | no |

### A and B, 15-minute

397 signals. In sample 2026-08-13 through 2026-09-14. Out of sample 2026-09-15 through 2026-10-06. Named large-cap list. Stock only. This clock is inside the free Yahoo intraday cap.

The published-target row matches the gated out-of-sample stock book ($1,001.48 on 10 trades).

| Level | IS trades | IS ending | OOS trades | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Signals with a level | Improves |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published target | 14 | $954.63 | 10 | 1.07 | 0.39 | -1.4% | $1,001.48 | — | — |
| horizontal pivots | 14 | $954.63 | 10 | 0.86 | -0.72 | -1.4% | $996.94 | 54% | no |
| floor pivots PP R1 S1 R2 S2 | 14 | $954.63 | 10 | 1.32 | 1.39 | -1.4% | $1,006.30 | 63% | no |
| prior-day high and low | 14 | $954.63 | 10 | 1.07 | 0.39 | -1.4% | $1,001.48 | 21% | no |
| demand and supply zones | 14 | $954.63 | 10 | 1.07 | 0.39 | -1.4% | $1,001.48 | 3% | no |
| Fibonacci 38.2/50/61.8 | 14 | $954.63 | 10 | 1.07 | 0.39 | -1.4% | $1,001.48 | 0% | no |
| trendline | 14 | $954.63 | 10 | 1.07 | 0.39 | -1.4% | $1,001.48 | 16% | no |
| flipped S/R | 14 | $954.63 | 10 | 1.07 | 0.39 | -1.4% | $1,001.48 | 24% | no |
| confluence, two or more sources | 14 | $954.63 | 10 | 1.01 | 0.09 | -1.4% | $1,000.24 | 47% | no |
| nearest of any source | 14 | $954.63 | 10 | 0.86 | -0.72 | -1.4% | $996.94 | 77% | no |

### A and B, 5-minute

908 signals. In sample 2026-08-13 through 2026-09-14. Out of sample 2026-09-15 through 2026-10-06. Named large-cap list. Stock only. This clock is inside the free Yahoo intraday cap.

The published-target row matches the gated out-of-sample stock book ($978.07 on 11 trades).

| Level | IS trades | IS ending | OOS trades | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Signals with a level | Improves |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published target | 15 | $1,019.80 | 11 | 0.27 | -6.46 | -2.2% | $978.07 | — | — |
| horizontal pivots | 15 | $1,030.19 | 11 | 0.31 | -5.79 | -2.0% | $980.43 | 44% | no |
| floor pivots PP R1 S1 R2 S2 | 15 | $1,026.03 | 11 | 0.27 | -6.46 | -2.2% | $978.07 | 57% | no |
| prior-day high and low | 15 | $1,025.29 | 11 | 0.27 | -6.46 | -2.2% | $978.07 | 23% | no |
| demand and supply zones | 15 | $1,019.80 | 11 | 0.27 | -6.46 | -2.2% | $978.07 | 1% | no |
| Fibonacci 38.2/50/61.8 | 15 | $1,019.80 | 11 | 0.27 | -6.46 | -2.2% | $978.07 | 0% | no |
| trendline | 15 | $1,019.80 | 11 | 0.31 | -5.79 | -2.0% | $980.43 | 16% | no |
| flipped S/R | 15 | $1,016.94 | 11 | 0.27 | -6.46 | -2.2% | $978.07 | 20% | no |
| confluence, two or more sources | 15 | $1,016.93 | 11 | 0.31 | -5.79 | -2.0% | $980.43 | 35% | no |
| nearest of any source | 15 | $1,017.69 | 11 | 0.31 | -5.79 | -2.0% | $980.43 | 75% | no |

### C, daily Dow

1838 Dow point-in-time long breakout-retest signals from 2010-01-01. In sample through 2018-12-31. Out of sample 2019-01-01 through 2026-10-06.

The published-target row matches the gated out-of-sample stock book ($746.56 on 207 trades).

| Level | IS trades | IS ending | OOS trades | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Signals with a level | Improves |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published target | 216 | $1,129.36 | 207 | 0.92 | -0.12 | -46.6% | $746.56 | — | — |
| horizontal pivots | 233 | $1,275.58 | 228 | 0.91 | -0.14 | -44.7% | $728.89 | 63% | no |
| floor pivots PP R1 S1 R2 S2 | 208 | $1,316.16 | 196 | 0.92 | -0.14 | -47.8% | $734.54 | 26% | no |
| prior-day high and low | 206 | $1,197.04 | 195 | 0.92 | -0.12 | -47.3% | $744.95 | 12% | no |
| demand and supply zones | 201 | $1,228.27 | 193 | 0.92 | -0.15 | -48.6% | $717.87 | 3% | no |
| Fibonacci 38.2/50/61.8 | 201 | $1,217.94 | 193 | 0.93 | -0.11 | -47.6% | $754.35 | 2% | no |
| trendline | 202 | $1,205.19 | 196 | 0.89 | -0.18 | -47.6% | $679.09 | 8% | no |
| flipped S/R | 214 | $1,030.41 | 210 | 0.98 | 0.05 | -36.9% | $939.99 | 40% | yes |
| confluence, two or more sources | 218 | $1,146.01 | 208 | 0.95 | -0.05 | -46.5% | $812.57 | 49% | yes |
| nearest of any source | 242 | $1,307.27 | 225 | 0.89 | -0.18 | -48.6% | $691.44 | 71% | no |

### D, daily Dow

292 Dow point-in-time breakout signals from 2010-01-01. In sample through 2018-12-31. Out of sample 2019-01-01 through 2026-10-06.

The published-target row matches the gated out-of-sample stock book ($919.45 on 73 trades).

| Level | IS trades | IS ending | OOS trades | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Signals with a level | Improves |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published target | 99 | $1,118.89 | 73 | 0.92 | -0.03 | -26.3% | $919.45 | — | — |
| horizontal pivots | 108 | $828.26 | 73 | 0.92 | -0.05 | -21.5% | $921.85 | 40% | yes |
| floor pivots PP R1 S1 R2 S2 | 111 | $809.37 | 73 | 1.04 | 0.11 | -18.6% | $1,043.97 | 25% | no |
| prior-day high and low | 105 | $814.10 | 72 | 0.99 | 0.05 | -19.6% | $993.81 | 9% | no |
| demand and supply zones | 105 | $815.94 | 72 | 1.03 | 0.09 | -18.6% | $1,032.16 | 1% | no |
| Fibonacci 38.2/50/61.8 | 105 | $815.94 | 72 | 1.01 | 0.07 | -18.7% | $1,014.72 | 0% | no |
| trendline | 105 | $791.53 | 72 | 1.01 | 0.07 | -18.7% | $1,014.72 | 5% | no |
| flipped S/R | 105 | $857.41 | 72 | 0.93 | -0.04 | -20.5% | $925.78 | 18% | no |
| confluence, two or more sources | 108 | $804.52 | 73 | 0.97 | 0.02 | -18.1% | $970.48 | 32% | yes |
| nearest of any source | 111 | $740.32 | 74 | 0.92 | -0.05 | -20.7% | $922.48 | 50% | yes |

The level set on the last SPY daily close is in `reports/setups/readSR_SPY_1d.png`. Profit factor gate 1.10, Sharpe gate 0.40, drawdown no worse than -30%, and at least 300 trades still apply to the published defaults. This level set was not in that gate. It does not join the optional list or the registry. The default book is still dual momentum.
<!-- CHART_READS_SR_END -->

<!-- CHART_READS_CHOP_START -->
## Chop filter

DOES NOT CHANGE THE GATE. Setups A, B, C, and D keep the entries already scored. This section asks two questions that were frozen before the score. First, do those books get better if a signal is skipped while the bar is chop? Second, is a breakout from that chop, on expanding volume, a useful entry next to setup D? Nothing was sent to a broker.

A bar is chop only when four readings are true together at that close. Volume is quiet: the bar is under 0.80 times the prior 20-bar average, or that 20-bar average is itself under 0.80 times the prior 60-bar average and the bar is still at most 1.20 times its own 20-bar average. The range is narrow: Bollinger bandwidth (20, 2 standard deviations) is in the bottom 20% of the last 120 bars, or the bar's range is under 0.75 times the prior 20-bar average range. The 9 and 20 EMAs are tangled: they sit within 0.35 ATR, the 20 EMA moved less than 0.50 ATR over 10 bars, and they crossed at least three times in 20 bars. Price crossed VWAP at least three times in 20 bars. Intraday VWAP resets each session. Daily VWAP is the 20-bar rolling VWAP. ADX under 20 or a 14-bar choppiness index above 61.8 is a stricter sensitivity. It is not required for the default flag.

The no-trade filter helps only when out-of-sample expectancy is higher, the book took fewer losing trades, and at least 20 trades remain. That label is not a new gate. "Inside chop only" is the complement, so the two rows show the same signals split by the flag. A signal whose bar is missing from the chop series stays in the published book and in the skip book.

skip chop on C, daily Dow raised out-of-sample expectancy from $-1.22 to $-1.08 and cut losing trades from 126 to 125. Ending equity $778.23 against $746.56, profit factor 0.93, Sharpe -0.09. In sample it ended at $1,105.06 against $1,129.36, with 129 losing trades against 129. skip stricter chop on C, daily Dow raised out-of-sample expectancy from $-1.22 to $-1.08 and cut losing trades from 126 to 125. Ending equity $778.23 against $746.56, profit factor 0.93, Sharpe -0.09. In sample it ended at $1,105.06 against $1,129.36, with 129 losing trades against 129. None of the labeled rows clears a 1.10 profit factor, a 0.40 Sharpe, a drawdown no worse than -30%, and 300 trades. The two labeled rows on setup C are the same book: the trade that was dropped was inside the stricter cut as well. The stricter cut is a sensitivity. It is not selectable.

### A, 60-minute

457 signals. In sample 2024-10-17 through 2025-10-10. Out of sample 2025-10-13 through 2026-10-06. Named large-cap list. Stock only. Hourly history is inside the free Yahoo cap, so the sample is short.

The published-entry row matches the gated out-of-sample stock book ($886.97 on 131 trades).

| Reading | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Helps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published entries | 117 | $676.70 | 131 | 90 | $-9.22 | $-0.86 | 0.86 | -0.65 | -14.0% | $886.97 | — |
| skip chop | 115 | $658.31 | 131 | 90 | $-9.22 | $-0.86 | 0.86 | -0.65 | -14.0% | $886.97 | no |
| inside chop only | 2 | $1,037.42 | 0 | 0 | n/a | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 | — |
| skip stricter chop | 116 | $659.78 | 131 | 90 | $-9.22 | $-0.86 | 0.86 | -0.65 | -14.0% | $886.97 | no |

### B, 60-minute

235 signals. In sample 2024-10-17 through 2025-10-10. Out of sample 2025-10-13 through 2026-10-06. Named large-cap list. Stock only. Hourly history is inside the free Yahoo cap, so the sample is short.

The published-entry row matches the gated out-of-sample stock book ($921.86 on 85 trades).

| Reading | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Helps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published entries | 70 | $972.61 | 85 | 61 | $-9.33 | $-0.92 | 0.86 | -0.36 | -23.8% | $921.86 | — |
| skip chop | 67 | $998.64 | 78 | 56 | $-9.66 | $-1.04 | 0.85 | -0.46 | -21.7% | $919.25 | no |
| inside chop only | 8 | $986.20 | 12 | 9 | $-6.66 | $-1.24 | 0.75 | -0.11 | -6.6% | $985.07 | — |
| skip stricter chop | 68 | $983.97 | 81 | 58 | $-9.54 | $-0.94 | 0.86 | -0.43 | -23.0% | $923.59 | no |

### A and B, 60-minute

692 signals. In sample 2024-10-17 through 2025-10-10. Out of sample 2025-10-13 through 2026-10-06. Named large-cap list. Stock only. Hourly history is inside the free Yahoo cap, so the sample is short.

The published-entry row matches the gated out-of-sample stock book ($967.77 on 164 trades).

| Reading | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Helps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published entries | 134 | $880.43 | 164 | 111 | $-9.67 | $-0.20 | 0.97 | -0.03 | -19.9% | $967.77 | — |
| skip chop | 130 | $891.14 | 163 | 111 | $-9.64 | $-0.37 | 0.94 | -0.20 | -20.6% | $939.08 | no |
| inside chop only | 10 | $1,023.10 | 12 | 9 | $-6.66 | $-1.24 | 0.75 | -0.11 | -6.6% | $985.07 | — |
| skip stricter chop | 131 | $869.53 | 163 | 111 | $-9.63 | $-0.37 | 0.94 | -0.19 | -22.2% | $939.31 | no |

### A and B, 15-minute

397 signals. In sample 2026-08-13 through 2026-09-14. Out of sample 2026-09-15 through 2026-10-06. Named large-cap list. Stock only. This clock is inside the free Yahoo intraday cap.

The published-entry row matches the gated out-of-sample stock book ($1,001.48 on 10 trades).

| Reading | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Helps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published entries | 14 | $954.63 | 10 | 6 | $-3.70 | $0.15 | 1.07 | 0.39 | -1.4% | $1,001.48 | — |
| skip chop | 14 | $954.63 | 10 | 6 | $-3.70 | $0.15 | 1.07 | 0.39 | -1.4% | $1,001.48 | no |
| inside chop only | 0 | $1,000.00 | 3 | 2 | $-4.86 | $-1.55 | 0.52 | -3.27 | -0.6% | $995.35 | — |
| skip stricter chop | 14 | $954.63 | 10 | 6 | $-3.70 | $0.15 | 1.07 | 0.39 | -1.4% | $1,001.48 | no |

### A and B, 5-minute

908 signals. In sample 2026-08-13 through 2026-09-14. Out of sample 2026-09-15 through 2026-10-06. Named large-cap list. Stock only. This clock is inside the free Yahoo intraday cap.

The published-entry row matches the gated out-of-sample stock book ($978.07 on 11 trades).

| Reading | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Helps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published entries | 15 | $1,019.80 | 11 | 8 | $-3.76 | $-1.99 | 0.27 | -6.46 | -2.2% | $978.07 | — |
| skip chop | 15 | $1,019.80 | 11 | 8 | $-3.76 | $-1.99 | 0.27 | -6.46 | -2.2% | $978.07 | no |
| inside chop only | 6 | $979.16 | 5 | 4 | $-2.51 | $-0.55 | 0.73 | -1.13 | -1.0% | $997.26 | — |
| skip stricter chop | 15 | $1,019.80 | 11 | 8 | $-3.76 | $-1.99 | 0.27 | -6.46 | -2.2% | $978.07 | no |

### C, daily Dow

1838 Dow point-in-time long breakout-retest signals from 2010-01-01. In sample through 2018-12-31. Out of sample 2019-01-01 through 2026-10-06.

The published-entry row matches the gated out-of-sample stock book ($746.56 on 207 trades).

| Reading | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Helps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published entries | 216 | $1,129.36 | 207 | 126 | $-25.45 | $-1.22 | 0.92 | -0.12 | -46.6% | $746.56 | — |
| skip chop | 216 | $1,105.06 | 206 | 125 | $-25.40 | $-1.08 | 0.93 | -0.09 | -44.4% | $778.23 | yes |
| inside chop only | 6 | $1,053.13 | 3 | 2 | $-25.99 | $-14.04 | 0.19 | -0.46 | -4.2% | $957.88 | — |
| skip stricter chop | 216 | $1,105.06 | 206 | 125 | $-25.40 | $-1.08 | 0.93 | -0.09 | -44.4% | $778.23 | yes |

### D, daily Dow

292 Dow point-in-time breakout signals from 2010-01-01. In sample through 2018-12-31. Out of sample 2019-01-01 through 2026-10-06.

The published-entry row matches the gated out-of-sample stock book ($919.45 on 73 trades).

| Reading | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending | Helps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published entries | 99 | $1,118.89 | 73 | 53 | $-18.70 | $-1.10 | 0.92 | -0.03 | -26.3% | $919.45 | — |
| skip chop | 98 | $1,138.03 | 73 | 53 | $-18.70 | $-1.10 | 0.92 | -0.03 | -26.3% | $919.45 | no |
| inside chop only | 1 | $983.18 | 0 | 0 | n/a | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 | — |
| skip stricter chop | 98 | $1,138.03 | 73 | 53 | $-18.70 | $-1.10 | 0.92 | -0.03 | -26.3% | $919.45 | no |

## Time in chop

Share is the fraction of bars where relative volume, the 20 EMA, VWAP, and ATR are already defined. Daily bars are the full Yahoo history used for setups C and D. The daily out-of-sample window is 2019-01-01 through 2026-10-06. Intraday shares use regular trading hours. Their out-of-sample window is the same split as the A and B filter above.

### Daily

48 symbols. Median time in chop 0.9% (out-of-sample median 1.0%).

| Symbol | Bars | Chop bars | Share | Strict share | OOS bars | OOS share |
|---|---:|---:|---:|---:|---:|---:|
| AA | 4447 | 61 | 1.4% | 1.3% | 1951 | 1.9% |
| AAPL | 4447 | 35 | 0.8% | 0.7% | 1951 | 0.4% |
| AMD | 4427 | 45 | 1.0% | 1.0% | 1951 | 1.4% |
| AMGN | 4447 | 50 | 1.1% | 1.1% | 1951 | 1.1% |
| AMZN | 4447 | 32 | 0.7% | 0.7% | 1951 | 0.9% |
| AXP | 4447 | 26 | 0.6% | 0.6% | 1951 | 0.3% |
| BA | 4447 | 53 | 1.2% | 1.1% | 1951 | 1.5% |
| BAC | 4447 | 29 | 0.7% | 0.6% | 1951 | 0.6% |
| CAT | 4447 | 26 | 0.6% | 0.6% | 1951 | 0.5% |
| CRM | 4447 | 34 | 0.8% | 0.7% | 1951 | 1.3% |
| CSCO | 4447 | 43 | 1.0% | 0.8% | 1951 | 0.8% |
| CVX | 4447 | 33 | 0.7% | 0.6% | 1951 | 0.7% |
| DD | 4447 | 42 | 0.9% | 0.9% | 1951 | 1.3% |
| DIS | 4447 | 23 | 0.5% | 0.5% | 1951 | 0.8% |
| DOW | 1878 | 33 | 1.8% | 1.8% | 1878 | 1.8% |
| GE | 4447 | 69 | 1.6% | 1.5% | 1951 | 2.4% |
| GOOGL | 4447 | 32 | 0.7% | 0.7% | 1951 | 0.8% |
| GS | 4447 | 25 | 0.6% | 0.5% | 1951 | 1.1% |
| HD | 4447 | 24 | 0.5% | 0.5% | 1951 | 0.3% |
| HON | 4447 | 47 | 1.1% | 0.9% | 1951 | 1.5% |
| HPQ | 4447 | 42 | 0.9% | 0.9% | 1951 | 1.4% |
| IBM | 4447 | 30 | 0.7% | 0.6% | 1951 | 1.1% |
| INTC | 4447 | 22 | 0.5% | 0.4% | 1951 | 0.6% |
| IWM | 4447 | 33 | 0.7% | 0.7% | 1951 | 1.1% |
| JNJ | 4447 | 37 | 0.8% | 0.8% | 1951 | 0.4% |
| JPM | 4447 | 27 | 0.6% | 0.6% | 1951 | 0.2% |
| KO | 4447 | 42 | 0.9% | 0.9% | 1951 | 0.4% |
| MCD | 4447 | 35 | 0.8% | 0.8% | 1951 | 0.6% |
| META | 3596 | 35 | 1.0% | 1.0% | 1951 | 0.8% |
| MMM | 4447 | 52 | 1.2% | 1.2% | 1951 | 1.8% |
| MRK | 4447 | 59 | 1.3% | 1.3% | 1951 | 1.4% |
| MSFT | 4447 | 36 | 0.8% | 0.7% | 1951 | 1.0% |
| NKE | 4447 | 77 | 1.7% | 1.6% | 1951 | 2.1% |
| NVDA | 4447 | 36 | 0.8% | 0.8% | 1951 | 0.9% |
| PFE | 4447 | 39 | 0.9% | 0.8% | 1951 | 0.9% |
| PG | 4447 | 37 | 0.8% | 0.8% | 1951 | 1.6% |
| QQQ | 4447 | 39 | 0.9% | 0.8% | 1951 | 0.9% |
| RTX | 4447 | 40 | 0.9% | 0.9% | 1951 | 1.1% |
| SHW | 4447 | 59 | 1.3% | 1.2% | 1951 | 1.5% |
| SPY | 4447 | 42 | 0.9% | 0.8% | 1951 | 0.2% |
| T | 4447 | 20 | 0.4% | 0.4% | 1951 | 0.5% |
| TRV | 4447 | 67 | 1.5% | 1.4% | 1951 | 1.7% |
| TSLA | 4073 | 59 | 1.4% | 1.3% | 1951 | 1.1% |
| UNH | 4447 | 18 | 0.4% | 0.4% | 1951 | 0.3% |
| V | 4447 | 29 | 0.7% | 0.7% | 1951 | 0.6% |
| VZ | 4447 | 74 | 1.7% | 1.4% | 1951 | 2.9% |
| WMT | 4447 | 44 | 1.0% | 1.0% | 1951 | 1.8% |
| XOM | 4447 | 19 | 0.4% | 0.4% | 1951 | 0.4% |

### 60-minute

10 symbols. Median time in chop 0.9% (out-of-sample median 1.1%).

| Symbol | Bars | Chop bars | Share | Strict share | OOS bars | OOS share |
|---|---:|---:|---:|---:|---:|---:|
| AAPL | 3397 | 30 | 0.9% | 0.7% | 1707 | 0.6% |
| AMD | 3397 | 35 | 1.0% | 0.4% | 1707 | 1.1% |
| IWM | 3396 | 43 | 1.3% | 1.0% | 1706 | 1.0% |
| META | 3398 | 40 | 1.2% | 0.6% | 1708 | 1.1% |
| MSFT | 3398 | 30 | 0.9% | 0.8% | 1708 | 1.3% |
| NVDA | 3397 | 27 | 0.8% | 0.3% | 1707 | 0.6% |
| QQQ | 3397 | 41 | 1.2% | 0.6% | 1707 | 2.1% |
| SPY | 3396 | 23 | 0.7% | 0.6% | 1706 | 0.8% |
| TSLA | 3397 | 18 | 0.5% | 0.5% | 1707 | 0.4% |
| UNH | 3397 | 30 | 0.9% | 0.8% | 1707 | 1.5% |

### 15-minute

10 symbols. Median time in chop 0.7% (out-of-sample median 0.5%).

| Symbol | Bars | Chop bars | Share | Strict share | OOS bars | OOS share |
|---|---:|---:|---:|---:|---:|---:|
| AAPL | 949 | 2 | 0.2% | 0.1% | 397 | 0.5% |
| AMD | 949 | 2 | 0.2% | 0.2% | 397 | 0.5% |
| IWM | 949 | 0 | 0.0% | 0.0% | 397 | 0.0% |
| META | 952 | 8 | 0.8% | 0.7% | 400 | 0.2% |
| MSFT | 952 | 7 | 0.7% | 0.7% | 400 | 0.5% |
| NVDA | 949 | 18 | 1.9% | 1.8% | 397 | 2.0% |
| QQQ | 949 | 3 | 0.3% | 0.1% | 397 | 0.3% |
| SPY | 952 | 3 | 0.3% | 0.2% | 400 | 0.0% |
| TSLA | 949 | 9 | 0.9% | 0.9% | 397 | 0.0% |
| UNH | 952 | 15 | 1.6% | 1.6% | 400 | 3.8% |

### 5-minute

10 symbols. Median time in chop 0.8% (out-of-sample median 0.9%).

| Symbol | Bars | Chop bars | Share | Strict share | OOS bars | OOS share |
|---|---:|---:|---:|---:|---:|---:|
| AAPL | 2887 | 18 | 0.6% | 0.6% | 1191 | 0.9% |
| AMD | 2887 | 26 | 0.9% | 0.9% | 1191 | 0.8% |
| IWM | 2887 | 15 | 0.5% | 0.5% | 1191 | 0.1% |
| META | 2896 | 24 | 0.8% | 0.8% | 1200 | 0.2% |
| MSFT | 2896 | 18 | 0.6% | 0.6% | 1200 | 0.9% |
| NVDA | 2887 | 53 | 1.8% | 1.7% | 1191 | 2.7% |
| QQQ | 2887 | 27 | 0.9% | 0.8% | 1191 | 1.0% |
| SPY | 2887 | 5 | 0.2% | 0.2% | 1191 | 0.0% |
| TSLA | 2887 | 70 | 2.4% | 2.4% | 1191 | 1.5% |
| UNH | 2896 | 9 | 0.3% | 0.2% | 1200 | 0.2% |

## Chop breakout

The precursor is a close out of a low-volume chop box. The box is the prior 10 bars, at least 6 of them chop, and the box height is between 0.40 and 6 ATR. The close is at least 0.10 ATR beyond the box, volume is above 1.5 times the prior 20-bar average, and the candle is confirming (body at least half the range, close in the outer third). The fill is the next open. The stop is the signal bar's low on a long and its high on a short. The target is the box height measured from the broken side when that distance is at least 0.5R, otherwise 2R, the same measured-move rule as setup D. A new signal waits 10 bars. Daily holds match setup D (up to 30 sessions, no same-day flatten). Sixty-minute holds last up to 5 sessions. Fifteen-minute and five-minute trades flatten the same session.

### Daily Dow, chop breakout

5 Dow point-in-time chop breakouts from 2010-01-01 (2 long, 3 short). In sample through 2018-12-31. Out of sample 2019-01-01 through 2026-10-06. The setup D row is the published-entry book from the filter above, same exits.

The published-entry row matches the gated out-of-sample stock book ($919.45 on 73 trades).

| Book | Signals | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chop breakout | 5 | 1 | $1,027.10 | 4 | 2 | $-18.76 | $14.53 | 2.55 | 0.25 | -7.4% | $1,058.11 |
| setup D, published entries | — | — | — | 73 | 53 | $-18.70 | $-1.10 | 0.92 | -0.03 | -26.3% | $919.45 |

### 60-minute, chop breakout

1 chop breakout on the named list (1 long, 0 short). 493 sessions, 2024-10-17 through 2026-10-06. In sample through 2025-12-19. Out of sample 2025-12-22 through 2026-10-06.

The paired setup D row matches the published out-of-sample stock book ($888.99 on 16 trades).

| Book | Signals | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chop breakout | 1 | 1 | $992.63 | 0 | 0 | n/a | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 |
| setup D, same window | — | — | — | 16 | 12 | $-13.69 | $-6.94 | 0.32 | -1.23 | -12.5% | $888.99 |

### 15-minute, chop breakout

0 chop breakouts on the named list (0 long, 0 short). 38 sessions, 2026-08-13 through 2026-10-06. In sample through 2026-09-14. Out of sample 2026-09-15 through 2026-10-06.

The paired setup D row matches the published out-of-sample stock book ($1,005.63 on 6 trades).

| Book | Signals | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chop breakout | 0 | 0 | $1,000.00 | 0 | 0 | n/a | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 |
| setup D, same window | — | — | — | 6 | 3 | $-5.04 | $0.94 | 1.37 | 1.35 | -1.0% | $1,005.63 |

### 5-minute, chop breakout

1 chop breakout on the named list (0 long, 1 short). 38 sessions, 2026-08-13 through 2026-10-06. In sample through 2026-09-14. Out of sample 2026-09-15 through 2026-10-06.

There is no published setup D book on the 5-minute clock. This row is anecdotal.

| Book | Signals | IS trades | IS ending | OOS trades | OOS losers | OOS avg loss | OOS expectancy | OOS PF | OOS Sharpe | OOS max DD | OOS ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chop breakout | 1 | 1 | $998.24 | 0 | 0 | n/a | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 |

Example chop windows: `reports/setups/readCHOP_AAPL_1d.png` (2015-04-01 through 2015-04-14), `reports/setups/readCHOP_META_60m.png` (2025-10-16, 10:30 through 15:30 ET), `reports/setups/readCHOP_UNH_15m.png` (2026-09-17, 12:00 through 13:15 ET).

Profit factor gate 1.10, Sharpe gate 0.40, drawdown no worse than -30%, and at least 300 trades still apply to the published defaults. Chop was not in that gate. It does not join the optional list or the registry. The default book is still dual momentum.
<!-- CHART_READS_CHOP_END -->

<!-- CHART_READS_SPY_REF_START -->
## SPY daily, Oct 6 2026 chart

REFERENCE ONLY. This does not change the gate, the chop rule, or the level rule. Nothing was sent to a broker.

The thinkorswim chart is a 1-year daily SPY as of 2026-10-06. Price is 781.03 at a high of 781.62. The 9 and 20 EMAs are tight under price. The 200 EMA is near 725.4 and rising. VWAP is on the chart. RSI(14) is 64. MACD(12, 26, 9) is about +2.45 and just crossing up. The year's low, 629.28, was a V-bottom with RSI oversold. After the rally, price chopped for weeks in about a 755-775 band on declining volume, then broke out. The drawn horizontals are about 781, 768, 760, 752, a thick zone at 740/735, then 700, 690, 683, 675, 655, and 632.

Yahoo's adjusted daily bar on 2026-10-06 has a high of 781.62 and a close of 780.66. The 9 EMA is 770.37 and the 20 EMA is 767.36, both under the close. The 200 EMA is 722.13 and rose 9.58 points over the prior 20 sessions. RSI(14) is 63.7. The MACD line is 2.91 and the histogram is 1.15, up from 0.50 the day before. The adjusted low of the last 252 sessions is 626.11 on 2026-03-30. March 27's low was 629.92. RSI on 2026-03-30 was 27.7. Older Yahoo prices sit a few points under the thinkorswim labels because the series is split- and dividend-adjusted. The October 6 high matches.

The chop flag does not mark that sideways stretch. In the last 252 sessions it is on for 2 bars: 2026-02-19, 2026-02-25. From 2026-08-01 through 2026-10-05 (45 sessions) the high was 777.44 on 2026-08-13 and the low was 746.95 on 2026-08-03, with closes from 752.18 to 775.95. The range was narrow on 87% of those bars, and close had crossed the 20-bar VWAP at least three times on 69% of them. The 9 and 20 EMAs were within 0.35 ATR on 58% of the bars and the 20 EMA's 10-bar slope was inside 0.50 ATR on 53%, but they changed order only 3 times in the whole stretch, so the tangled-EMA leg stays off and the four-way flag never turns on (0 chop bars). Relative volume was under 0.80 on 24% of the bars. Median volume in the stretch was 42.7 million shares, against 51.0 million from the March low through July. The October 6 breakout bar is not chop. The rule was left as scored.

The live horizontal set on 2026-10-06 is the last 6 confirmed pivot highs and the last 6 confirmed pivot lows inside 120 bars, which reaches back to 2026-04-16: 777.44, 775.14, 774.93, 773.38, 760.15, 757.60, 753.71, 752.87, 747.74, 737.68, 727.29, 714.81. A pivot is confirmed four bars after it prints, so the October 6 high is not in the set yet. The 781 row is that unfinished high. The other rows are the nearest confirmed swing in the last 252 sessions.

| Drawn | Nearest swing | Date | Kind | In the live set |
|---|---:|---|---|---|
| 781 | 781.62 | 2026-10-06 | high, not confirmed | no |
| 768 | 773.38 | 2026-08-28 | high | yes |
| 760 | 760.15 | 2026-08-20 | low | yes |
| 752 | 752.87 | 2026-06-15 | high | yes |
| 740/735 | 737.68 | 2026-07-08 | low | yes |
| 700 | 698.74 | 2026-04-23 | low | no |
| 690 | 690.70 | 2026-01-13 | high | no |
| 683 | 682.34 | 2025-10-29 | high | no |
| 675 | 674.55 | 2026-01-02 | low | no |
| 655 | 654.15 | 2025-11-07 | low | no |
| 632 | 626.11 | 2026-03-30 | low | no |

760.15 is the drawn 760 line, 752.87 is the drawn 752 line, and 737.68 sits in the 740/735 zone. 768 has no confirmed pivot at that price. The nearest swing is the August 28 high at 773.38, about five points higher, and that high is in the live set. 698.74 is still inside the 120-bar window and is the April 23 low, near 700, but six later pivot lows are newer, so the keeper drops it. The January and November swings, and the March low, are older than 120 bars, so they are not targets on this close. They are the same kind of swing the drawing uses.

The chart is `reports/setups/readSPY_chop_levels_1d.png`. Gold bands are detected chop. Solid gold lines are the live horizontal set. Dotted lines are the other confirmed swings in the year. Dashed lines are the thinkorswim prices.

The published A-D books are unchanged. Chop and this level set stay off the optional list and off the registry. The default book is still dual momentum.
<!-- CHART_READS_SPY_REF_END -->

<!-- CHART_READS_BOUNCE_START -->
## Partial reversal bounce

DOES NOT CHANGE THE GATE. This is a separate long-only book. Setups A through D are unchanged. Nothing was sent to a broker. The rule was frozen before this score.

A signal is a daily bar that tags a confirmed pivot low from the prior 120 sessions. The pivot is at least five bars old, the low is within 0.50 ATR of it, and the close does not finish more than 0.10 ATR through it. The same bar is a confirming candle: the body is at least half the range and the close is in the upper third. RSI(14) is at or under 30, or it is turning up from a prior reading at or under 45. The fill is the next open. The stop is 0.25 ATR under the signal low. The next signal in a name waits 10 bars. Quiet volume, the last three bars at or under their prior 20-bar average, is a sensitivity. It is not required.

The partial target is the nearest of the next confirmed pivot high, the 20 EMA, the 50 EMA, and the descending pivot trendline, when that price is between 0.5R and 4R above the signal close. Otherwise the target is 1R. The hold is 15 sessions, with no EMA trail, because a long entered under the 20 EMA would be flattened at once. The full-reversal comparison uses the same entry and the same stop. Its target is the next of those levels beyond the partial target, out to 8R, otherwise 3R, and the hold is 40 sessions. A fixed 1R target is the other comparison. Calls use delta 0.45. Seven DTE is the short-dated call. Thirty, 45, and 60 DTE are the requested range. The account is $1,000, one position, 20% risk. A contract that costs more than that risk budget is skipped. The gate does not pick the best row.

Dow point-in-time, in sample 2010-01-01 through 2018-12-31, out of sample 2019-01-01 through 2026-10-06. The default row had a level on every out-of-sample signal, so none of them used the 1R fallback. Out of sample, the default stock book exited 135 trades at the target, 129 at the stop, and 21 at the time stop. The out-of-sample call books skipped 1055 seven-DTE entries, 1118 thirty-DTE entries, 1126 forty-five-DTE entries, and 1123 sixty-DTE entries. A skip is a contract that did not fit the risk budget, or a bar with no volatility estimate.

Average move on a stock row is the mean underlying percent from the fill to the exit, after the stock slippage. On a call row it is the mean premium return, ask notional against the booked P&L, which includes the haircut and the option fees. Expectancy is dollars per closed trade after those costs.

| Book | OOS trades | Win rate | Avg move | Expectancy | PF | Sharpe | Max DD | OOS ending | IS trades | IS ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stock, next level | 286 | 50.7% | +0.2% | $1.76 | 1.13 | 0.36 | -46.9% | $1,502.90 | 298 | $1,434.05 |
| stock, fixed 1R | 301 | 51.2% | +0.1% | $0.21 | 1.02 | 0.14 | -44.7% | $1,062.31 | 300 | $1,269.03 |
| stock, full reversal | 204 | 42.6% | +0.4% | $3.55 | 1.18 | 0.41 | -41.1% | $1,724.59 | 227 | $868.65 |
| stock, quiet volume, next level | 246 | 50.4% | +0.1% | $0.30 | 1.02 | 0.14 | -37.5% | $1,073.90 | 244 | $1,816.20 |
| 7 DTE calls, next level | 61 | 37.7% | -22.8% | $-14.96 | 0.59 | -0.64 | -93.4% | $87.67 | 92 | $26.15 |
| 30 DTE calls, next level | 39 | 25.6% | -21.0% | $-19.32 | 0.21 | -1.33 | -75.4% | $246.43 | 65 | $73.27 |
| 45 DTE calls, next level | 39 | 28.2% | -17.5% | $-17.16 | 0.27 | -1.03 | -69.7% | $330.78 | 77 | $97.16 |
| 60 DTE calls, next level | 35 | 22.9% | -17.4% | $-17.49 | 0.20 | -1.05 | -64.0% | $387.79 | 57 | $96.62 |
| 45 DTE calls, full reversal | 34 | 35.3% | -19.4% | $-20.69 | 0.39 | -0.88 | -73.3% | $296.56 | 67 | $85.93 |

Random dates, same count and the same stop distance, with a 1R target because the shuffled bar has no original level: 322 out-of-sample trades, ending $3,502.34, expectancy $7.77. SPY buy and hold over that window, whole shares that fit in $1,000: 4 shares, ending $3,242.23.

UNH on 2026-10-06, the five-year daily used as the check. Yahoo's adjusted bar closed at 375.48 (open 379.03, high 380.41, low 374.44). The 9 EMA is 374.14, the 20 EMA is 377.63, and the 50 EMA is 385.95. RSI(14) is 45.5 and turning down. The MACD line is -5.07. The histogram is 0.86, higher than the prior bar's 0.61. The bounce trendline, the latest pivot high joined to the nearest earlier higher pivot, is 356.22 and is under the close. Setup C's longer line, from 2026-07-29 at 429.04 through 2026-09-09 at 404.04, is 387.67 on this close, which is the line near 390-400. This study did not switch to that line. The five-year high is 601.33 on 2024-11-11 and the low is 227.08 on 2025-08-01. The heaviest volume day in the window is 2025-05-15, low 239.21, volume 121,849,200.

The detector marked 34 UNH bounces in that five-year window. 5 of them tagged a drawn band, counting a low within $8 of the band. None of them tagged the 330-350 band.

| Signal | Low | Close | RSI | Next target | Full-reversal target | Band |
|---|---:|---:|---:|---:|---:|---|
| 2022-09-01 | 475.20 | 483.42 | 43.4 | 491.49 | 502.19 | 480 |
| 2025-02-19 | 476.75 | 489.09 | 41.0 | 504.74 | 511.75 | 480 |
| 2025-07-11 | 288.45 | 294.36 | 44.7 | 301.36 | 306.41 | 290-300 |
| 2025-11-21 | 303.36 | 311.67 | 41.2 | 320.44 | 325.34 | 290-300 |
| 2026-08-05 | 395.37 | 410.22 | 46.8 | 429.04 | 431.64 | 375-390 |

The default stock row does not meet a 1.10 profit factor, a 0.40 Sharpe, a drawdown no worse than -30%, and 300 trades. The full-reversal stock row is higher out of sample and its in-sample book ended lower. It still fails the drawdown and the 300-trade test, and it is not selected. Trade counts differ across the stock rows because the account holds one position, so an earlier exit frees the next signal. The chart is `reports/setups/readBOUNCE_UNH_1d.png`. Gold triangles are the bounce signals. Dashed lines are the drawn levels. Shaded bands are 290-300, 330-350, and 375-390.

Not added to `config/optional_strategies.json`. The published A-D books are unchanged. The default book is still dual momentum.
<!-- CHART_READS_BOUNCE_END -->

<!-- CHART_READS_EXITS_START -->
## Exit styles

DOES NOT CHANGE THE GATE. The same entries and the same stops are scored with a frozen exit grid. Nothing was sent to a broker. `live_trading_enabled` stays false. The dual-momentum order path is unchanged.

The grid, fixed before this score: a percent trail at 5%, 10%, and 15%; an ATR trail at 1.5, 2, and 3 times the signal-bar ATR, as a fixed dollar step; a bracket at the next level and at 1.5R, 2R, and 3R, with the setup stop and no EMA trail; and one hybrid that sells half at the first level (1R if that level is missing) and trails the rest at 2 times the signal-bar ATR. The level bracket is the baseline. A pure trail has no separate hard stop and no take-profit. The book's time stop still exits, because a native order has none. A row beats the baseline on the out-of-sample stock book only when expectancy is strictly higher, profit factor is not lower, max drawdown is no more than five points worse, and at least 20 trades closed. The winner is the passing row with the highest expectancy. An equal expectancy keeps the earlier cell. Options are reported and do not pick the winner. Meeting the label does not clear the gate.

Webull's stock trade page accepts `TRAILING_STOP_LOSS` with `trailing_type` `AMOUNT` or `PERCENTAGE` and `trailing_stop_step` (`0.01` is 1%). That order is DAY only, so a multi-day trail in this backtest is the economic path of renewing it, not a good-till-cancelled order. The equity bracket on that page is `MASTER` plus `STOP_PROFIT` plus `STOP_LOSS` with one `client_combo_order_id`. `OTOCO` is a different pattern, a master that triggers two linked limits, and it is not the bracket used here. The options trade page lists `MARKET`, `LIMIT`, `STOP_LOSS`, and `STOP_LOSS_LIMIT`. It says `TRAILING_STOP_LOSS` is not supported, and `OTO`, `OCO`, and `OTOCO` are equity-only. A single-leg option stop is a premium. These exits are prices on the underlying, so every option row is a bot-managed watch of the stock. No option order is built or sent. The paper path can rest the equity trail, the equity bracket, or the hybrid's half-size limit and half-size DAY trail. It refuses any broker other than the paper broker.

Hourly setup A and hourly setup B are the intraday books. The 5-minute and 15-minute books stay out of this grid because that Yahoo sample is too short to separate an exit. Daily setup C, daily setup D, and the partial-bounce book use the Dow point-in-time window, 2010-01-01 through 2018-12-31 in sample and 2019-01-01 through 2026-10-06 out of sample. Calls are 3 DTE on the hourly books and 45 DTE on the daily books, delta 0.45, inside the $1,000 and 20% risk rules. A contract that does not fit is skipped. Average capture on a stock row is the mean underlying percent from the fill to the exit. On a call row it is the mean premium return, including the haircut and the option fees. Expectancy is dollars per closed trade after costs. A hybrid entry can close as two trades, the partial and the remainder. One option contract cannot be split, so that position exits in full at the target.

### Partial bounce, daily Dow

2508 signals. Same entry and stop as the partial-bounce study. The level-target row is that study's next-level stock exit.

The published stock out-of-sample book still matches $1,502.90 on 286 trades.

Out-of-sample stock winner: **trail 15%**. That label is not the default book.

Stock

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Beats level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| level target | 286 | 50.7% | +0.2% | $1.76 | 1.13 | 0.36 | -46.9% | $1,502.90 | $1,434.05 | baseline |
| trail 5% | 178 | 44.4% | +0.2% | $0.70 | 1.03 | 0.18 | -35.5% | $1,124.59 | $1,351.97 | no |
| trail 10% | 124 | 53.2% | +0.7% | $6.18 | 1.19 | 0.41 | -31.1% | $1,766.39 | $1,126.89 | yes |
| trail 15% | 118 | 55.1% | +1.1% | $13.63 | 1.43 | 0.60 | -32.3% | $2,608.44 | $1,863.54 | yes |
| trail 1.5 ATR | 253 | 35.2% | +0.0% | $-0.41 | 0.97 | 0.05 | -37.7% | $895.70 | $629.58 | no |
| trail 2 ATR | 177 | 42.9% | +0.5% | $4.75 | 1.20 | 0.45 | -26.3% | $1,841.04 | $985.79 | yes |
| trail 3 ATR | 134 | 53.0% | +0.8% | $9.49 | 1.25 | 0.54 | -32.5% | $2,271.66 | $1,141.81 | yes |
| bracket 1.5R | 254 | 44.1% | +0.4% | $3.99 | 1.21 | 0.50 | -40.2% | $2,012.92 | $1,048.74 | yes |
| bracket 2R | 219 | 40.6% | +0.5% | $6.52 | 1.27 | 0.61 | -34.3% | $2,427.77 | $905.03 | yes |
| bracket 3R | 188 | 38.3% | +0.5% | $4.53 | 1.19 | 0.45 | -42.5% | $1,851.02 | $762.99 | yes |
| hybrid half at level, trail 2 ATR | 288 | 55.2% | +1.1% | $0.23 | 1.02 | 0.14 | -42.0% | $1,066.09 | $952.89 | no |

Options, bot-managed on the underlying

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Beats level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| level target | 39 | 28.2% | -17.5% | $-17.16 | 0.27 | -1.03 | -69.7% | $330.78 | $97.16 | — |
| trail 5% | 34 | 26.5% | -11.5% | $-16.26 | 0.66 | -0.15 | -77.3% | $447.23 | $103.33 | — |
| trail 10% | 96 | 41.7% | +11.3% | $6.09 | 1.07 | 0.38 | -70.5% | $1,584.44 | $215.57 | — |
| trail 15% | 41 | 31.7% | -12.1% | $-16.37 | 0.71 | -0.22 | -77.0% | $328.63 | $238.43 | — |
| trail 1.5 ATR | 25 | 12.0% | -33.9% | $-29.92 | 0.08 | -1.02 | -75.6% | $252.09 | $82.87 | — |
| trail 2 ATR | 21 | 9.5% | -37.2% | $-35.96 | 0.09 | -0.94 | -75.5% | $244.76 | $83.03 | — |
| trail 3 ATR | 35 | 28.6% | -11.1% | $-15.28 | 0.67 | -0.13 | -79.7% | $465.30 | $129.98 | — |
| bracket 1.5R | 55 | 21.8% | -6.3% | $-8.68 | 0.77 | -0.05 | -71.3% | $522.46 | $73.50 | — |
| bracket 2R | 55 | 21.8% | -6.3% | $-8.68 | 0.77 | -0.05 | -71.3% | $522.46 | $73.50 | — |
| bracket 3R | 55 | 21.8% | -6.3% | $-8.68 | 0.77 | -0.05 | -71.3% | $522.46 | $73.50 | — |
| hybrid half at level, trail 2 ATR | 41 | 26.8% | -16.8% | $-17.06 | 0.30 | -0.92 | -73.1% | $300.68 | $94.59 | — |

The level-target call row skipped 1126 out-of-sample entries that did not fit the risk budget or had no volatility estimate.
Out-of-sample stock exits for trail 15%: 109 time_stop, 8 trail, 1 window_end.

### A, 60-minute

457 continuation signals. The published exit is a 2R target and the 20 EMA trail. The level-target row is the baseline for this grid, with that trail turned off.

The published stock out-of-sample book still matches $886.97 on 131 trades.

Out-of-sample stock winner: **level target**. That label is not the default book.

Stock

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Beats level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published exit | 131 | 31.3% | -0.1% | $-0.86 | 0.86 | -0.65 | -14.0% | $886.97 | $676.70 | — |
| level target | 128 | 35.9% | -0.1% | $-0.72 | 0.90 | -0.48 | -18.2% | $908.43 | $695.84 | baseline |
| trail 5% | 49 | 40.8% | -0.7% | $-6.57 | 0.56 | -1.44 | -34.0% | $677.93 | $749.33 | no |
| trail 10% | 44 | 40.9% | -0.7% | $-7.38 | 0.61 | -0.89 | -37.9% | $675.31 | $612.12 | no |
| trail 15% | 43 | 41.9% | -1.6% | $-12.29 | 0.39 | -2.14 | -56.6% | $471.46 | $670.64 | no |
| trail 1.5 ATR | 125 | 27.2% | -0.3% | $-2.95 | 0.55 | -2.02 | -37.9% | $631.72 | $458.16 | no |
| trail 2 ATR | 107 | 39.3% | -0.2% | $-1.64 | 0.81 | -0.66 | -26.2% | $824.42 | $454.84 | no |
| trail 3 ATR | 71 | 33.8% | -0.1% | $-1.59 | 0.88 | -0.22 | -29.2% | $887.04 | $374.26 | no |
| bracket 1.5R | 131 | 37.4% | -0.2% | $-1.61 | 0.74 | -1.48 | -23.0% | $789.28 | $656.79 | no |
| bracket 2R | 127 | 33.1% | -0.1% | $-1.22 | 0.82 | -0.92 | -18.3% | $844.57 | $725.01 | no |
| bracket 3R | 115 | 27.8% | -0.1% | $-0.94 | 0.88 | -0.46 | -22.0% | $891.67 | $695.55 | no |
| hybrid half at level, trail 2 ATR | 166 | 49.4% | +0.1% | $-1.55 | 0.64 | -1.83 | -28.1% | $742.89 | $532.22 | no |

Options, bot-managed on the underlying

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Beats level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| level target | 16 | 12.5% | -9.4% | $-31.41 | 0.58 | -0.38 | -70.1% | $497.46 | $612.39 | — |
| trail 5% | 10 | 0.0% | -32.6% | $-43.50 | 0.00 | -1.43 | -43.5% | $564.96 | $617.98 | — |
| trail 10% | 10 | 0.0% | -32.6% | $-43.50 | 0.00 | -1.43 | -43.5% | $564.96 | $632.29 | — |
| trail 15% | 10 | 0.0% | -32.6% | $-43.50 | 0.00 | -1.43 | -43.5% | $564.96 | $632.29 | — |
| trail 1.5 ATR | 13 | 0.0% | -22.5% | $-28.25 | 0.00 | -3.18 | -36.7% | $632.71 | $534.61 | — |
| trail 2 ATR | 13 | 0.0% | -22.5% | $-28.25 | 0.00 | -3.18 | -36.7% | $632.71 | $495.76 | — |
| trail 3 ATR | 13 | 0.0% | -22.5% | $-28.25 | 0.00 | -3.18 | -36.7% | $632.71 | $442.45 | — |
| bracket 1.5R | 14 | 14.3% | -9.8% | $-35.69 | 0.58 | -0.34 | -69.1% | $500.41 | $574.23 | — |
| bracket 2R | 14 | 14.3% | -9.8% | $-35.69 | 0.58 | -0.34 | -69.1% | $500.41 | $574.23 | — |
| bracket 3R | 14 | 14.3% | -9.8% | $-35.69 | 0.58 | -0.34 | -69.1% | $500.41 | $574.23 | — |
| hybrid half at level, trail 2 ATR | 16 | 12.5% | -9.4% | $-31.41 | 0.58 | -0.38 | -70.1% | $497.46 | $617.98 | — |

The level-target call row skipped 181 out-of-sample entries that did not fit the risk budget or had no volatility estimate.
Out-of-sample stock exits for level target: 81 invalidation, 45 target, 1 time_stop, 1 window_end.

### B, 60-minute

235 failed-breakout signals. The published exit is a 2R target and the 20 EMA trail. The level-target row is the baseline for this grid, with that trail turned off.

The published stock out-of-sample book still matches $921.86 on 85 trades.

Out-of-sample stock winner: **trail 15%**. That label is not the default book.

Stock

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Beats level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published exit | 85 | 28.2% | -0.1% | $-0.92 | 0.86 | -0.36 | -23.8% | $921.86 | $972.61 | — |
| level target | 73 | 34.2% | -0.2% | $-1.67 | 0.78 | -0.49 | -25.7% | $878.38 | $963.41 | baseline |
| trail 5% | 42 | 42.9% | -0.0% | $-1.11 | 0.92 | -0.11 | -17.7% | $953.26 | $1,150.85 | yes |
| trail 10% | 37 | 51.4% | +0.3% | $2.60 | 1.16 | 0.51 | -20.0% | $1,096.05 | $1,271.64 | yes |
| trail 15% | 36 | 50.0% | +0.3% | $2.64 | 1.16 | 0.50 | -16.2% | $1,094.94 | $1,369.87 | yes |
| trail 1.5 ATR | 84 | 32.1% | -0.3% | $-2.88 | 0.51 | -1.76 | -26.8% | $757.76 | $904.23 | no |
| trail 2 ATR | 79 | 29.1% | -0.4% | $-3.52 | 0.46 | -1.92 | -29.6% | $721.69 | $910.13 | no |
| trail 3 ATR | 60 | 31.7% | -0.5% | $-4.59 | 0.52 | -1.58 | -27.6% | $724.57 | $1,118.40 | no |
| bracket 1.5R | 76 | 35.5% | -0.3% | $-2.50 | 0.67 | -0.90 | -26.0% | $810.37 | $936.32 | no |
| bracket 2R | 73 | 34.2% | -0.2% | $-1.67 | 0.78 | -0.49 | -25.7% | $878.38 | $963.41 | no |
| bracket 3R | 67 | 25.4% | -0.4% | $-3.60 | 0.57 | -1.14 | -30.1% | $758.71 | $1,098.52 | no |
| hybrid half at level, trail 2 ATR | 105 | 52.4% | +0.1% | $-1.88 | 0.60 | -1.07 | -26.2% | $802.69 | $1,022.83 | no |

Options, bot-managed on the underlying

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Beats level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| level target | 4 | 0.0% | -70.2% | $-83.17 | 0.00 | -1.74 | -36.4% | $667.33 | $545.94 | — |
| trail 5% | 18 | 11.1% | -2.4% | $-20.88 | 0.71 | -0.39 | -65.1% | $624.15 | $1,486.51 | — |
| trail 10% | 18 | 11.1% | -2.4% | $-20.88 | 0.71 | -0.39 | -65.1% | $624.15 | $1,523.77 | — |
| trail 15% | 18 | 11.1% | -2.4% | $-20.88 | 0.71 | -0.39 | -65.1% | $624.15 | $1,950.54 | — |
| trail 1.5 ATR | 19 | 10.5% | -1.6% | $-15.34 | 0.74 | -0.30 | -64.1% | $708.47 | $596.31 | — |
| trail 2 ATR | 23 | 8.7% | -0.4% | $-14.11 | 0.77 | -0.29 | -64.1% | $675.58 | $545.05 | — |
| trail 3 ATR | 23 | 13.0% | +7.0% | $-1.76 | 0.97 | 0.35 | -54.6% | $959.47 | $1,157.18 | — |
| bracket 1.5R | 4 | 0.0% | -85.4% | $-100.07 | 0.00 | -1.74 | -42.8% | $599.74 | $633.52 | — |
| bracket 2R | 4 | 0.0% | -85.4% | $-100.07 | 0.00 | -1.74 | -42.8% | $599.74 | $633.52 | — |
| bracket 3R | 4 | 0.0% | -85.4% | $-100.07 | 0.00 | -1.74 | -42.8% | $599.74 | $633.52 | — |
| hybrid half at level, trail 2 ATR | 4 | 0.0% | -70.2% | $-83.17 | 0.00 | -1.74 | -36.4% | $667.33 | $545.94 | — |

The level-target call row skipped 115 out-of-sample entries that did not fit the risk budget or had no volatility estimate.
Out-of-sample stock exits for trail 15%: 34 time_stop, 1 trail, 1 window_end.

### C, daily Dow

1838 signals. The published exit is the measured level, the 20 EMA trail, and a 30-session hold. The level-target baseline keeps that level and turns the EMA trail off.

The published stock out-of-sample book still matches $746.56 on 207 trades.

Out-of-sample stock winner: **level target**. That label is not the default book.

Stock

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Beats level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published exit | 207 | 39.1% | -0.1% | $-1.22 | 0.92 | -0.12 | -46.6% | $746.56 | $1,129.36 | — |
| level target | 163 | 47.9% | +0.7% | $9.34 | 1.30 | 0.71 | -34.2% | $2,522.01 | $1,436.06 | baseline |
| trail 5% | 120 | 39.2% | -0.0% | $-1.29 | 0.93 | -0.02 | -46.4% | $845.16 | $1,555.46 | no |
| trail 10% | 70 | 44.3% | -0.5% | $-5.69 | 0.80 | -0.19 | -57.1% | $601.54 | $1,555.13 | no |
| trail 15% | 62 | 51.6% | -0.1% | $-4.13 | 0.89 | -0.04 | -65.6% | $743.66 | $1,941.07 | no |
| trail 1.5 ATR | 207 | 31.4% | -0.2% | $-1.82 | 0.84 | -0.27 | -61.9% | $623.16 | $565.23 | no |
| trail 2 ATR | 149 | 34.2% | +0.1% | $0.06 | 1.00 | 0.10 | -52.5% | $1,008.39 | $1,160.12 | no |
| trail 3 ATR | 96 | 50.0% | +0.3% | $1.78 | 1.06 | 0.20 | -49.7% | $1,171.28 | $911.77 | no |
| bracket 1.5R | 174 | 43.7% | +0.4% | $3.80 | 1.16 | 0.44 | -32.4% | $1,661.47 | $1,188.86 | no |
| bracket 2R | 153 | 43.8% | +0.6% | $7.73 | 1.25 | 0.61 | -31.2% | $2,182.40 | $1,801.76 | no |
| bracket 3R | 135 | 36.3% | +0.5% | $5.30 | 1.17 | 0.44 | -31.7% | $1,715.04 | $1,383.56 | no |
| hybrid half at level, trail 2 ATR | 214 | 54.2% | +0.8% | $-0.68 | 0.94 | -0.05 | -42.3% | $855.01 | $916.21 | no |

Options, bot-managed on the underlying

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Beats level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| level target | 36 | 16.7% | -21.5% | $-19.49 | 0.13 | -1.24 | -71.1% | $298.52 | $124.47 | — |
| trail 5% | 21 | 14.3% | -35.8% | $-37.23 | 0.32 | -0.38 | -83.6% | $218.17 | $118.50 | — |
| trail 10% | 19 | 26.3% | -39.3% | $-35.93 | 0.28 | -0.28 | -78.1% | $317.32 | $472.92 | — |
| trail 15% | 16 | 25.0% | -46.7% | $-42.59 | 0.22 | -0.29 | -78.0% | $318.58 | $478.58 | — |
| trail 1.5 ATR | 32 | 25.0% | -11.8% | $-16.37 | 0.48 | -0.39 | -73.6% | $476.02 | $98.58 | — |
| trail 2 ATR | 37 | 32.4% | -5.7% | $-13.46 | 0.74 | -0.10 | -78.6% | $501.90 | $99.52 | — |
| trail 3 ATR | 18 | 16.7% | -40.7% | $-40.11 | 0.14 | -0.46 | -74.5% | $278.03 | $478.21 | — |
| bracket 1.5R | 22 | 13.6% | -39.4% | $-34.96 | 0.15 | -0.53 | -78.2% | $230.86 | $585.01 | — |
| bracket 2R | 22 | 13.6% | -39.4% | $-34.96 | 0.15 | -0.53 | -78.2% | $230.86 | $585.01 | — |
| bracket 3R | 22 | 13.6% | -39.4% | $-34.96 | 0.15 | -0.53 | -78.2% | $230.86 | $585.01 | — |
| hybrid half at level, trail 2 ATR | 49 | 16.3% | -13.6% | $-13.98 | 0.32 | -0.86 | -72.4% | $315.18 | $87.33 | — |

The level-target call row skipped 755 out-of-sample entries that did not fit the risk budget or had no volatility estimate.
Out-of-sample stock exits for level target: 83 invalidation, 59 target, 20 time_stop, 1 window_end.

### D, daily Dow

292 signals. The published exit is the measured level, the 20 EMA trail, and a 30-session hold. The level-target baseline keeps that level and turns the EMA trail off.

The published stock out-of-sample book still matches $919.45 on 73 trades.

Out-of-sample stock winner: **bracket 1.5R**. That label is not the default book.

Stock

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Beats level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| published exit | 73 | 27.4% | -0.0% | $-1.10 | 0.92 | -0.03 | -26.3% | $919.45 | $1,118.89 | — |
| level target | 71 | 31.0% | -0.2% | $-2.92 | 0.80 | -0.17 | -35.1% | $792.57 | $1,187.49 | baseline |
| trail 5% | 62 | 37.1% | -0.7% | $-6.09 | 0.60 | -0.39 | -46.5% | $622.40 | $903.94 | no |
| trail 10% | 45 | 37.8% | -1.2% | $-10.78 | 0.56 | -0.39 | -52.8% | $514.83 | $1,061.55 | no |
| trail 15% | 40 | 52.5% | -0.3% | $-5.87 | 0.84 | -0.08 | -50.0% | $765.29 | $958.01 | no |
| trail 1.5 ATR | 89 | 27.0% | -0.5% | $-4.28 | 0.58 | -0.54 | -46.3% | $619.36 | $548.27 | no |
| trail 2 ATR | 68 | 32.4% | -0.4% | $-4.31 | 0.70 | -0.26 | -39.8% | $706.84 | $648.04 | no |
| trail 3 ATR | 53 | 41.5% | -0.4% | $-4.74 | 0.76 | -0.14 | -43.4% | $748.79 | $910.54 | no |
| bracket 1.5R | 73 | 37.0% | -0.1% | $-1.46 | 0.90 | -0.08 | -27.2% | $893.28 | $700.85 | yes |
| bracket 2R | 70 | 30.0% | -0.1% | $-2.07 | 0.87 | -0.11 | -27.6% | $855.16 | $769.62 | yes |
| bracket 3R | 66 | 24.2% | -0.3% | $-3.40 | 0.80 | -0.17 | -35.2% | $775.47 | $690.44 | no |
| hybrid half at level, trail 2 ATR | 88 | 42.0% | +0.6% | $-3.69 | 0.66 | -0.35 | -41.8% | $674.99 | $1,081.62 | no |

Options, bot-managed on the underlying

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Beats level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| level target | 19 | 15.8% | -17.0% | $-29.70 | 0.49 | -0.55 | -70.8% | $435.61 | $247.66 | — |
| trail 5% | 17 | 17.6% | -25.2% | $-33.62 | 0.22 | -1.03 | -59.7% | $428.52 | $498.04 | — |
| trail 10% | 15 | 20.0% | -29.5% | $-40.37 | 0.21 | -0.93 | -61.0% | $394.43 | $561.97 | — |
| trail 15% | 15 | 20.0% | -29.8% | $-40.60 | 0.21 | -0.93 | -61.3% | $390.94 | $545.80 | — |
| trail 1.5 ATR | 17 | 11.8% | -24.3% | $-30.00 | 0.07 | -1.32 | -52.0% | $489.95 | $240.52 | — |
| trail 2 ATR | 16 | 12.5% | -26.8% | $-34.90 | 0.11 | -1.04 | -56.1% | $441.67 | $242.37 | — |
| trail 3 ATR | 15 | 13.3% | -28.2% | $-37.91 | 0.21 | -1.01 | -59.7% | $431.40 | $222.62 | — |
| bracket 1.5R | 19 | 10.5% | -18.9% | $-29.14 | 0.52 | -0.49 | -69.9% | $446.31 | $258.84 | — |
| bracket 2R | 19 | 10.5% | -18.9% | $-29.14 | 0.52 | -0.49 | -69.9% | $446.31 | $258.84 | — |
| bracket 3R | 19 | 10.5% | -18.9% | $-29.14 | 0.52 | -0.49 | -69.9% | $446.31 | $258.84 | — |
| hybrid half at level, trail 2 ATR | 19 | 15.8% | -17.0% | $-29.70 | 0.49 | -0.55 | -70.8% | $435.61 | $253.61 | — |

The level-target call row skipped 93 out-of-sample entries that did not fit the risk budget or had no volatility estimate.
Out-of-sample stock exits for bracket 1.5R: 46 invalidation, 23 target, 4 time_stop.

The bounce label is the 15% trail: out-of-sample expectancy $13.63, profit factor 1.43, Sharpe 0.60, max drawdown -32.3%, 118 trades, ending $2,608.44. Of those exits, 109 were the 15-session time stop and 8 were the trail. The stop is wide enough that it rarely ratchets inside the hold, so that result is mostly a wide stop plus the time stop. It does not clear 300 trades or a drawdown no worse than -30%. Hourly B's 15% trail is the same pattern, 34 of 36 exits at the time stop, expectancy $2.64. Hourly A and daily C keep the level target because nothing beat it. Daily C's level target, with the 20 EMA trail off, ended at $2,522.01 on 163 trades (profit factor 1.30, Sharpe 0.71, drawdown -34.2%). That is not the published C book, which still matches $746.56 on 207 trades, and it does not clear the gate. Daily D's label is the 1.5R bracket, expectancy -$1.46 on 73 trades. The option rows do not pick the label. The only call book that finished ahead of its start was the bounce's 10% trail, $1,584.44 on 96 trades, with a -70.5% drawdown. Where the 1.5R, 2R, and 3R call rows match, those contracts were closed by the stop or the time stop before the underlying reached 1.5R.

Not added to `config/optional_strategies.json`. The published A-D books are unchanged. The default book is still dual momentum.
<!-- CHART_READS_EXITS_END -->

<!-- CHART_READS_SCALE_START -->
## Options scale-out

DOES NOT CHANGE THE GATE. This is a pre-registered options exit, scored on the same bounce and A-D entries. Nothing was sent to a broker. `live_trading_enabled` stays false. The dual-momentum order path does not call it. The ordinary simulator is unchanged when this contract count is absent.

The ladder, fixed before the score: buy 5 contracts, sell 2 at +15% of the premium paid, sell 1 at +20%, sell 1 at +30%, and leave 1 runner with a limit at +100%. After the +15% tier fills, the remaining contracts stop at the entry ask, which is 0% on the premium before sell-side fees. Before that fill, the initial stop is a premium stop at -20%, -30%, or -50%, or the setup stop on the underlying. The comparisons on the same five-contract entries are an all-out sell at +30% with those same stops, the percent and ATR trails, and the brackets at the next level and at 1.5R, 2R, and 3R. A limit fills at the limit. A stop that gaps through fills at the worse bid. If one bar trades both, the stop fills. The book's time stop still exits the remainder.

Webull's options trade page lists `MARKET`, `LIMIT`, `STOP_LOSS`, and `STOP_LOSS_LIMIT`. It does not list `TRAILING_STOP_LOSS`, and `OTO`, `OCO`, and `OTOCO` are equity-only. The execution plan therefore builds four separate option `LIMIT` sells, one per tier. A resting option stop beside those limits could sell the same contracts twice, so the initial stop and the break-even stop are bot-managed watches. The limits are DAY orders. The paper book does not rest them, because that book fills equity prices. No option order is sent.

Costs are the modeled spread on each fill and the per-contract ORF, OCC, and CAT fees on the buy and on every sell ticket, plus the sell-side TAF and SEC fee. Webull's listed US options commission is $0. A finished ladder is one five-contract buy and four sell tickets (2, then 1, then 1, then the runner). Expectancy is dollars per closed five-contract position after those costs. Average capture is that P&L divided by the premium paid, before fees are taken out of the denominator. Options are Black-Scholes on trailing realized volatility times 1.15, with the same haircut as the other call books. They are not quotes. Hourly calls are 3 DTE. Daily calls are 45 DTE. The book delta is 0.45 unless the row says 0.20.

Sizing (a) uses one account per book: the in-sample median of the equity that puts a -30% premium stop at about 2% of the account, and at least the five-lot debit. Every row in that regime, including the other stops and the trails, uses that same equity. The -20% stop then risks less than 2%, and the -50% stop risks more. The 90th percentile of that required capital is reported and was not used. Sizing (b) is a $1,000 account. A five-lot is taken only when its debit fits. One (b) row keeps delta 0.45. The other uses delta 0.20, further out of the money, so more names fit and the contract needs a larger underlying move to reach the same premium percent. Short-dated contracts have less time for that move.

### Partial bounce, daily Dow

2508 signals. Same bounce entry and underlying stop. Calls, 45 DTE.

In-sample five-lot quotes: 1270. Median debit $670.87, median ask $1.34, median delta 0.45. Median capital at a -20% stop $6,728.11, at -30% $10,081.40, at -50% $16,787.98, and at the underlying stop $14,602.10. The sized account is the -30% median, $10,081.40. The unused 90th percentile at -30% is $25,481.64.
Out of sample, 227 of 1207 book-delta five-lots fit in $1,000 (median debit $2,470.21, median delta 0.45). At delta 0.20, 714 of 1207 fit (median debit $811.98, median ask $1.62, median delta 0.20).

Sized account, $10,081.40, delta 0.45

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 39 | 10.3% | -23.5% | $-253.75 | 0.07 | -8.33 | -98.2% | $185.10 | $40.62 | 1145 |
| scale, premium stop -30% | 35 | 28.6% | -19.7% | $-283.02 | 0.18 | -4.66 | -98.3% | $175.85 | $46.94 | 1110 |
| scale, premium stop -50% | 36 | 36.1% | -26.0% | $-275.85 | 0.25 | -3.52 | -98.8% | $150.94 | $41.30 | 1087 |
| scale, underlying stop | 37 | 37.8% | -19.2% | $-270.86 | 0.31 | -2.80 | -99.5% | $59.63 | $42.86 | 1081 |
| all-out +30%, premium stop -20% | 39 | 7.7% | -23.7% | $-254.06 | 0.08 | -8.24 | -98.3% | $173.13 | $41.69 | 1145 |
| all-out +30%, premium stop -30% | 39 | 33.3% | -14.3% | $-253.34 | 0.29 | -4.63 | -98.0% | $201.11 | $45.96 | 1110 |
| all-out +30%, premium stop -50% | 57 | 45.6% | -15.6% | $-174.92 | 0.63 | -1.83 | -99.2% | $111.20 | $63.67 | 997 |
| all-out +30%, underlying stop | 60 | 41.7% | -13.9% | $-166.99 | 0.63 | -1.77 | -99.5% | $61.93 | $123.85 | 987 |
| bracket, next level | 44 | 31.8% | -18.3% | $-224.15 | 0.28 | -1.00 | -98.3% | $218.92 | $9.76 | 1085 |
| trail 5% | 30 | 20.0% | -16.5% | $-331.65 | 0.48 | -0.48 | -99.2% | $131.80 | $207.19 | 1036 |
| trail 10% | 30 | 26.7% | -26.5% | $-332.72 | 0.47 | -0.45 | -99.4% | $99.80 | $233.57 | 982 |
| trail 15% | 26 | 26.9% | -22.6% | $-380.80 | 0.43 | -0.44 | -98.7% | $180.63 | $696.51 | 1021 |
| trail 1.5 ATR | 28 | 25.0% | -21.2% | $-354.68 | 0.15 | -0.71 | -98.9% | $150.49 | $38.22 | 1110 |
| trail 2 ATR | 31 | 29.0% | -16.6% | $-322.05 | 0.32 | -0.40 | -99.3% | $97.86 | $124.62 | 1042 |
| trail 3 ATR | 21 | 14.3% | -25.2% | $-474.00 | 0.25 | -0.39 | -99.1% | $127.32 | $143.40 | 1056 |
| bracket 1.5R | 84 | 27.4% | +2.4% | $-117.84 | 0.83 | -0.13 | -99.3% | $182.76 | $101.99 | 685 |
| bracket 2R | 84 | 27.4% | +2.4% | $-117.84 | 0.83 | -0.13 | -99.3% | $182.76 | $101.99 | 685 |
| bracket 3R | 84 | 27.4% | +2.4% | $-117.84 | 0.83 | -0.13 | -99.3% | $182.76 | $101.99 | 685 |

Highest out-of-sample scale expectancy in this regime: scale, premium stop -20%, $-253.75 on 39 trades, win rate 10.3%, average capture -23.5%, max drawdown -98.2%. It does not clear the old gate. The paired all-out row is all-out +30%, premium stop -20% expectancy $-254.06 on 39 trades. That label is not a new default.
35 hit 0, 1 hit 1, 1 hit 2, 1 hit 3, 1 hit 4. Runner +100%: 1. Runner stopped at break-even: 3. Armed after the first target: 4.

$1,000 account, delta 0.45, five contracts only when the debit fits

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 8 | 0.0% | -31.1% | $-102.13 | 0.00 | -32.06 | -81.7% | $182.92 | $14.54 | 1214 |
| scale, premium stop -30% | 9 | 22.2% | -22.0% | $-94.86 | 0.17 | -5.95 | -85.4% | $146.30 | $38.16 | 1205 |
| scale, premium stop -50% | 8 | 50.0% | -19.9% | $-100.45 | 0.22 | -3.63 | -80.4% | $196.39 | $54.35 | 1199 |
| scale, underlying stop | 11 | 54.5% | -13.9% | $-78.90 | 0.26 | -3.40 | -86.8% | $132.05 | $34.30 | 1180 |
| all-out +30%, premium stop -20% | 8 | 0.0% | -31.1% | $-102.13 | 0.00 | -32.06 | -81.7% | $182.92 | $14.54 | 1214 |
| all-out +30%, premium stop -30% | 14 | 35.7% | -13.1% | $-62.81 | 0.56 | -3.97 | -92.5% | $120.63 | $63.54 | 1194 |
| all-out +30%, premium stop -50% | 11 | 36.4% | -20.9% | $-81.62 | 0.33 | -2.95 | -89.8% | $102.15 | $32.21 | 1185 |
| all-out +30%, underlying stop | 20 | 50.0% | -7.4% | $-39.63 | 0.76 | -0.55 | -89.5% | $207.40 | $7.28 | 1137 |
| bracket, next level | 9 | 22.2% | -16.5% | $-94.24 | 0.17 | -0.69 | -84.8% | $151.86 | $42.65 | 1201 |
| trail 5% | 7 | 28.6% | -21.8% | $-130.65 | 0.23 | -0.34 | -91.5% | $85.43 | $32.74 | 1176 |
| trail 10% | 13 | 38.5% | -12.2% | $-68.66 | 0.67 | -0.10 | -96.0% | $107.38 | $28.33 | 1111 |
| trail 15% | 13 | 38.5% | -12.2% | $-68.66 | 0.67 | -0.10 | -96.0% | $107.38 | $37.34 | 1111 |
| trail 1.5 ATR | 6 | 0.0% | -37.5% | $-146.00 | 0.00 | -0.91 | -87.6% | $123.99 | $35.45 | 1209 |
| trail 2 ATR | 11 | 27.3% | -16.1% | $-77.27 | 0.39 | -0.03 | -85.0% | $149.98 | $56.80 | 1150 |
| trail 3 ATR | 6 | 33.3% | -25.6% | $-156.60 | 0.23 | -0.46 | -94.0% | $60.40 | $13.09 | 1183 |
| bracket 1.5R | 7 | 28.6% | -15.1% | $-119.98 | 0.25 | -0.54 | -84.0% | $160.15 | $43.42 | 1191 |
| bracket 2R | 7 | 28.6% | -15.1% | $-119.98 | 0.25 | -0.54 | -84.0% | $160.15 | $43.42 | 1191 |
| bracket 3R | 7 | 28.6% | -15.1% | $-119.98 | 0.25 | -0.54 | -84.0% | $160.15 | $43.42 | 1191 |

Highest out-of-sample scale expectancy in this regime: scale, underlying stop, $-78.90 on 11 trades, win rate 54.5%, average capture -13.9%, max drawdown -86.8%. It does not clear the old gate. The paired all-out row is all-out +30%, underlying stop expectancy $-39.63 on 20 trades. That label is not a new default.
6 hit 0, 0 hit 1, 2 hit 2, 2 hit 3, 1 hit 4. Runner +100%: 1. Runner stopped at break-even: 4. Armed after the first target: 5.

$1,000 account, delta 0.20

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 12 | 0.0% | -32.4% | $-80.34 | 0.00 | -35.96 | -96.4% | $35.90 | $17.74 | 1206 |
| scale, premium stop -30% | 13 | 7.7% | -33.9% | $-74.16 | 0.03 | -15.48 | -96.4% | $35.94 | $22.87 | 1203 |
| scale, premium stop -50% | 24 | 41.7% | -20.3% | $-39.45 | 0.41 | -2.27 | -95.7% | $53.31 | $11.67 | 1139 |
| scale, underlying stop | 22 | 31.8% | -23.5% | $-44.18 | 0.38 | -3.81 | -97.2% | $28.08 | $27.16 | 1163 |
| all-out +30%, premium stop -20% | 12 | 0.0% | -32.4% | $-80.34 | 0.00 | -35.96 | -96.4% | $35.90 | $17.74 | 1206 |
| all-out +30%, premium stop -30% | 15 | 13.3% | -28.4% | $-64.49 | 0.13 | -11.50 | -96.7% | $32.68 | $16.98 | 1199 |
| all-out +30%, premium stop -50% | 18 | 38.9% | -22.7% | $-53.67 | 0.43 | -3.98 | -97.9% | $34.00 | $25.98 | 1168 |
| all-out +30%, underlying stop | 24 | 50.0% | -11.6% | $-40.05 | 0.56 | -2.08 | -97.2% | $38.86 | $22.86 | 1139 |
| bracket, next level | 19 | 26.3% | -16.2% | $-51.67 | 0.36 | -0.73 | -98.5% | $18.34 | $27.24 | 1180 |
| trail 5% | 14 | 28.6% | -32.2% | $-70.78 | 0.53 | -0.55 | -99.5% | $9.13 | $11.73 | 1114 |
| trail 10% | 13 | 30.8% | -38.7% | $-76.02 | 0.53 | -0.39 | -99.5% | $11.78 | $23.62 | 1098 |
| trail 15% | 13 | 30.8% | -38.7% | $-76.02 | 0.53 | -0.39 | -99.5% | $11.78 | $24.99 | 1098 |
| trail 1.5 ATR | 13 | 30.8% | -25.5% | $-75.14 | 0.28 | -0.58 | -98.7% | $23.12 | $20.06 | 1179 |
| trail 2 ATR | 20 | 35.0% | -18.0% | $-49.16 | 0.62 | -0.40 | -99.1% | $16.76 | $7.35 | 1105 |
| trail 3 ATR | 12 | 25.0% | -35.9% | $-82.51 | 0.44 | -0.58 | -99.5% | $9.92 | $24.46 | 1113 |
| bracket 1.5R | 66 | 22.7% | +13.7% | $-14.48 | 0.96 | 0.17 | -99.5% | $44.40 | $8.09 | 844 |
| bracket 2R | 66 | 22.7% | +13.7% | $-14.48 | 0.96 | 0.17 | -99.5% | $44.40 | $8.09 | 844 |
| bracket 3R | 66 | 22.7% | +13.7% | $-14.48 | 0.96 | 0.17 | -99.5% | $44.40 | $8.09 | 844 |

Highest out-of-sample scale expectancy in this regime: scale, premium stop -50%, $-39.45 on 24 trades, win rate 41.7%, average capture -20.3%, max drawdown -95.7%. It does not clear the old gate. The paired all-out row is all-out +30%, premium stop -50% expectancy $-53.67 on 18 trades. That label is not a new default.
11 hit 0, 6 hit 1, 0 hit 2, 4 hit 3, 3 hit 4. Runner +100%: 3. Runner stopped at break-even: 10. Armed after the first target: 13.

### A, 60-minute

457 continuation signals. Calls, 3 DTE. The 5-minute and 15-minute books stay out.

In-sample five-lot quotes: 225. Median debit $1,547.81, median ask $3.10, median delta 0.43. Median capital at a -20% stop $15,498.17, at -30% $23,236.04, at -50% $38,711.76, and at the underlying stop $27,003.95. The sized account is the -30% median, $23,236.04. The unused 90th percentile at -30% is $56,803.29.
Out of sample, 18 of 222 book-delta five-lots fit in $1,000 (median debit $2,059.29, median delta 0.44). At delta 0.20, 165 of 222 fit (median debit $668.20, median ask $1.34, median delta 0.19).

Sized account, $23,236.04, delta 0.45

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 56 | 12.5% | -24.7% | $-410.29 | 0.13 | -7.11 | -98.9% | $259.58 | $510.57 | 123 |
| scale, premium stop -30% | 40 | 25.0% | -30.5% | $-571.44 | 0.12 | -6.81 | -98.4% | $378.39 | $172.68 | 154 |
| scale, premium stop -50% | 35 | 28.6% | -36.0% | $-654.69 | 0.11 | -7.45 | -98.6% | $322.04 | $531.82 | 160 |
| scale, underlying stop | 41 | 34.1% | -27.0% | $-554.63 | 0.17 | -5.47 | -97.9% | $496.34 | $294.73 | 148 |
| all-out +30%, premium stop -20% | 56 | 12.5% | -23.8% | $-411.32 | 0.16 | -7.12 | -99.1% | $202.29 | $500.75 | 123 |
| all-out +30%, premium stop -30% | 41 | 24.4% | -31.9% | $-556.09 | 0.23 | -6.61 | -98.1% | $436.48 | $166.89 | 158 |
| all-out +30%, premium stop -50% | 35 | 31.4% | -35.9% | $-651.54 | 0.19 | -5.62 | -98.2% | $431.97 | $507.13 | 161 |
| all-out +30%, underlying stop | 34 | 32.4% | -33.1% | $-671.96 | 0.19 | -6.17 | -98.3% | $389.28 | $272.70 | 162 |
| bracket, next level | 35 | 8.6% | -16.7% | $-650.00 | 0.31 | -1.36 | -97.9% | $486.19 | $179.87 | 150 |
| trail 5% | 52 | 13.5% | -9.7% | $-443.20 | 0.55 | -1.00 | -99.2% | $189.39 | $37,234.56 | 48 |
| trail 10% | 66 | 10.6% | -9.6% | $-62.82 | 0.95 | 0.62 | -75.7% | $19,090.14 | $74,342.46 | 0 |
| trail 15% | 66 | 10.6% | -7.6% | $-10.95 | 0.99 | 0.64 | -71.7% | $22,513.15 | $74,366.17 | 0 |
| trail 1.5 ATR | 34 | 2.9% | -38.4% | $-669.08 | 0.01 | -4.20 | -97.9% | $487.18 | $347.95 | 164 |
| trail 2 ATR | 105 | 8.6% | -9.8% | $-216.33 | 0.74 | -0.31 | -98.4% | $520.93 | $164.88 | 15 |
| trail 3 ATR | 89 | 11.2% | -12.0% | $-253.27 | 0.75 | 0.41 | -98.1% | $694.80 | $247.17 | 9 |
| bracket 1.5R | 28 | 14.3% | -29.9% | $-822.65 | 0.33 | -1.89 | -99.2% | $201.89 | $71,159.30 | 148 |
| bracket 2R | 28 | 14.3% | -29.9% | $-822.65 | 0.33 | -1.89 | -99.2% | $201.89 | $71,159.30 | 148 |
| bracket 3R | 28 | 14.3% | -29.9% | $-822.65 | 0.33 | -1.89 | -99.2% | $201.89 | $71,159.30 | 148 |

Highest out-of-sample scale expectancy in this regime: scale, premium stop -20%, $-410.29 on 56 trades, win rate 12.5%, average capture -24.7%, max drawdown -98.9%. It does not clear the old gate. The paired all-out row is all-out +30%, premium stop -20% expectancy $-411.32 on 56 trades. That label is not a new default.
48 hit 0, 0 hit 1, 1 hit 2, 3 hit 3, 4 hit 4. Runner +100%: 4. Runner stopped at break-even: 4. Armed after the first target: 8.

$1,000 account, delta 0.45, five contracts only when the debit fits

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 6 | 33.3% | -15.0% | $-105.10 | 0.42 | -6.99 | -75.0% | $369.38 | $392.16 | 210 |
| scale, premium stop -30% | 8 | 50.0% | -7.9% | $-76.12 | 0.53 | -3.82 | -73.5% | $391.01 | $284.60 | 207 |
| scale, premium stop -50% | 6 | 66.7% | -10.0% | $-102.39 | 0.52 | -3.76 | -77.4% | $385.67 | $331.08 | 209 |
| scale, underlying stop | 7 | 57.1% | -9.2% | $-102.39 | 0.47 | -1.89 | -83.4% | $283.25 | $305.22 | 208 |
| all-out +30%, premium stop -20% | 6 | 33.3% | -10.5% | $-97.54 | 0.47 | -6.04 | -73.2% | $414.75 | $392.16 | 211 |
| all-out +30%, premium stop -30% | 8 | 37.5% | -12.5% | $-87.93 | 0.55 | -7.13 | -80.9% | $296.58 | $284.60 | 208 |
| all-out +30%, premium stop -50% | 7 | 57.1% | -12.4% | $-114.61 | 0.59 | -3.56 | -89.3% | $197.74 | $331.08 | 210 |
| all-out +30%, underlying stop | 5 | 60.0% | -7.5% | $-100.87 | 0.63 | -0.73 | -73.1% | $495.64 | $291.46 | 211 |
| bracket, next level | 4 | 25.0% | -7.0% | $-130.46 | 0.62 | 0.33 | -78.1% | $478.16 | $502.78 | 208 |
| trail 5% | 5 | 0.0% | -33.2% | $-199.07 | 0.00 | 1.00 | -99.5% | $4.67 | $156.17 | 210 |
| trail 10% | 5 | 0.0% | -33.2% | $-199.07 | 0.00 | 1.00 | -99.5% | $4.67 | $235.59 | 210 |
| trail 15% | 5 | 0.0% | -33.2% | $-199.07 | 0.00 | 1.00 | -99.5% | $4.67 | $235.59 | 210 |
| trail 1.5 ATR | 5 | 0.0% | -33.2% | $-199.07 | 0.00 | -1.80 | -99.5% | $4.67 | $207.01 | 214 |
| trail 2 ATR | 5 | 0.0% | -33.2% | $-199.07 | 0.00 | -1.80 | -99.5% | $4.67 | $78.46 | 214 |
| trail 3 ATR | 5 | 0.0% | -33.2% | $-199.07 | 0.00 | -1.80 | -99.5% | $4.67 | $21.75 | 214 |
| bracket 1.5R | 4 | 25.0% | -15.7% | $-221.46 | 0.49 | 0.11 | -95.0% | $114.16 | $291.46 | 205 |
| bracket 2R | 4 | 25.0% | -15.7% | $-221.46 | 0.49 | 0.11 | -95.0% | $114.16 | $291.46 | 205 |
| bracket 3R | 4 | 25.0% | -15.7% | $-221.46 | 0.49 | 0.11 | -95.0% | $114.16 | $291.46 | 205 |

Highest out-of-sample scale expectancy in this regime: scale, premium stop -30%, $-76.12 on 8 trades, win rate 50.0%, average capture -7.9%, max drawdown -73.5%. It does not clear the old gate. The paired all-out row is all-out +30%, premium stop -30% expectancy $-87.93 on 8 trades. That label is not a new default.
4 hit 0, 0 hit 1, 1 hit 2, 1 hit 3, 2 hit 4. Runner +100%: 2. Runner stopped at break-even: 2. Armed after the first target: 4.

$1,000 account, delta 0.20

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 8 | 0.0% | -34.7% | $-111.87 | 0.00 | -38.70 | -89.5% | $105.04 | $177.96 | 206 |
| scale, premium stop -30% | 7 | 14.3% | -32.1% | $-119.99 | 0.10 | -13.70 | -84.0% | $160.06 | $102.19 | 208 |
| scale, premium stop -50% | 5 | 20.0% | -42.1% | $-178.95 | 0.06 | -12.43 | -89.5% | $105.23 | $105.35 | 215 |
| scale, underlying stop | 10 | 40.0% | -18.1% | $-93.33 | 0.28 | -2.10 | -93.3% | $66.67 | $66.23 | 208 |
| all-out +30%, premium stop -20% | 8 | 0.0% | -34.7% | $-111.87 | 0.00 | -38.70 | -89.5% | $105.04 | $107.87 | 206 |
| all-out +30%, premium stop -30% | 7 | 14.3% | -32.9% | $-122.20 | 0.08 | -15.72 | -85.5% | $144.57 | $102.19 | 209 |
| all-out +30%, premium stop -50% | 4 | 25.0% | -40.5% | $-196.89 | 0.06 | -10.48 | -83.5% | $212.43 | $105.35 | 216 |
| all-out +30%, underlying stop | 9 | 44.4% | -18.1% | $-100.69 | 0.32 | -4.33 | -90.6% | $93.81 | $66.23 | 204 |
| bracket, next level | 6 | 0.0% | -44.6% | $-158.13 | 0.00 | -0.25 | -94.9% | $51.22 | $165.61 | 202 |
| trail 5% | 4 | 50.0% | +6.2% | $-211.66 | 0.40 | 0.42 | -94.7% | $153.37 | $89.89 | 208 |
| trail 10% | 3 | 66.7% | +14.3% | $-287.61 | 0.40 | 0.44 | -95.2% | $137.16 | $89.89 | 206 |
| trail 15% | 3 | 66.7% | +14.3% | $-287.61 | 0.40 | 0.44 | -95.2% | $137.16 | $89.89 | 206 |
| trail 1.5 ATR | 4 | 0.0% | -52.0% | $-215.35 | 0.00 | -1.96 | -86.1% | $138.60 | $62.71 | 217 |
| trail 2 ATR | 5 | 0.0% | -42.4% | $-165.36 | 0.00 | -2.31 | -82.7% | $173.19 | $16.00 | 212 |
| trail 3 ATR | 40 | 7.5% | +7.0% | $-24.60 | 0.90 | 0.40 | -99.8% | $16.08 | $68.11 | 137 |
| bracket 1.5R | 7 | 28.6% | -27.6% | $-136.86 | 0.45 | 0.41 | -98.5% | $42.01 | $66.13 | 196 |
| bracket 2R | 7 | 28.6% | -27.6% | $-136.86 | 0.45 | 0.41 | -98.5% | $42.01 | $66.13 | 196 |
| bracket 3R | 7 | 28.6% | -27.6% | $-136.86 | 0.45 | 0.41 | -98.5% | $42.01 | $66.13 | 196 |

Highest out-of-sample scale expectancy in this regime: scale, underlying stop, $-93.33 on 10 trades, win rate 40.0%, average capture -18.1%, max drawdown -93.3%. It does not clear the old gate. The paired all-out row is all-out +30%, underlying stop expectancy $-100.69 on 9 trades. That label is not a new default.
6 hit 0, 0 hit 1, 0 hit 2, 0 hit 3, 4 hit 4. Runner +100%: 4. Runner stopped at break-even: 0. Armed after the first target: 4.

### B, 60-minute

235 failed-breakout signals. Calls and puts follow the setup direction. 3 DTE.

In-sample five-lot quotes: 112. Median debit $1,518.86, median ask $3.04, median delta -0.43. Median capital at a -20% stop $15,208.72, at -30% $22,801.87, at -50% $37,988.18, and at the underlying stop $43,409.77. The sized account is the -30% median, $22,801.87. The unused 90th percentile at -30% is $74,109.44.
Out of sample, 13 of 121 book-delta five-lots fit in $1,000 (median debit $1,828.65, median delta 0.42). At delta 0.20, 93 of 121 fit (median debit $613.95, median ask $1.23, median delta 0.18).

Sized account, $22,801.87, delta 0.45

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 42 | 19.0% | -23.1% | $-531.16 | 0.05 | -8.40 | -97.8% | $492.97 | $596.11 | 66 |
| scale, premium stop -30% | 34 | 26.5% | -27.5% | $-657.50 | 0.07 | -9.32 | -98.0% | $447.00 | $587.17 | 76 |
| scale, premium stop -50% | 33 | 33.3% | -30.9% | $-682.57 | 0.10 | -9.62 | -98.8% | $277.18 | $62.94 | 73 |
| scale, underlying stop | 36 | 38.9% | -27.5% | $-622.11 | 0.10 | -6.22 | -98.2% | $405.87 | $521.34 | 67 |
| all-out +30%, premium stop -20% | 42 | 16.7% | -22.4% | $-532.42 | 0.11 | -7.67 | -98.1% | $440.22 | $456.62 | 64 |
| all-out +30%, premium stop -30% | 30 | 20.0% | -31.8% | $-745.34 | 0.09 | -13.18 | -98.1% | $441.61 | $567.16 | 80 |
| all-out +30%, premium stop -50% | 33 | 36.4% | -30.0% | $-677.37 | 0.19 | -5.02 | -98.1% | $448.81 | $558.60 | 77 |
| all-out +30%, underlying stop | 36 | 41.7% | -24.0% | $-619.09 | 0.20 | -4.79 | -97.7% | $514.54 | $441.47 | 66 |
| bracket, next level | 28 | 7.1% | -30.4% | $-807.17 | 0.35 | -0.60 | -99.3% | $201.23 | $36,032.83 | 72 |
| trail 5% | 29 | 10.3% | -16.1% | $-780.35 | 0.17 | 1.01 | -100.0% | $171.60 | $19,995.68 | 64 |
| trail 10% | 50 | 16.0% | +1.3% | $-448.04 | 0.62 | -0.10 | -98.9% | $399.81 | $18,635.64 | 8 |
| trail 15% | 51 | 15.7% | -0.3% | $-424.53 | 0.63 | 0.06 | -96.8% | $1,150.70 | $19,979.04 | 5 |
| trail 1.5 ATR | 38 | 5.3% | -13.1% | $-590.05 | 0.17 | -3.15 | -98.3% | $379.88 | $552.03 | 69 |
| trail 2 ATR | 38 | 7.9% | -8.4% | $-590.34 | 0.21 | -3.04 | -98.4% | $368.97 | $587.42 | 71 |
| trail 3 ATR | 35 | 5.7% | -11.2% | $-638.43 | 0.19 | -3.16 | -98.0% | $456.68 | $266.31 | 73 |
| bracket 1.5R | 21 | 9.5% | -66.5% | $-1,083.10 | 0.01 | -2.49 | -99.8% | $56.81 | $34,254.41 | 82 |
| bracket 2R | 21 | 9.5% | -66.5% | $-1,083.10 | 0.01 | -2.49 | -99.8% | $56.81 | $34,254.41 | 82 |
| bracket 3R | 21 | 9.5% | -66.5% | $-1,083.10 | 0.01 | -2.49 | -99.8% | $56.81 | $34,254.41 | 82 |

Highest out-of-sample scale expectancy in this regime: scale, premium stop -20%, $-531.16 on 42 trades, win rate 19.0%, average capture -23.1%, max drawdown -97.8%. It does not clear the old gate. The paired all-out row is all-out +30%, premium stop -20% expectancy $-532.42 on 42 trades. That label is not a new default.
32 hit 0, 2 hit 1, 2 hit 2, 5 hit 3, 1 hit 4. Runner +100%: 1. Runner stopped at break-even: 9. Armed after the first target: 10.

$1,000 account, delta 0.45, five contracts only when the debit fits

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 3 | 0.0% | -23.5% | $-157.45 | 0.00 | -10.03 | -54.5% | $527.64 | $528.37 | 118 |
| scale, premium stop -30% | 4 | 0.0% | -25.4% | $-163.39 | 0.00 | -13.08 | -70.1% | $346.43 | $583.72 | 117 |
| scale, premium stop -50% | 3 | 0.0% | -22.5% | $-156.80 | 0.00 | -9.01 | -54.3% | $529.59 | $186.08 | 118 |
| scale, underlying stop | 5 | 20.0% | -22.3% | $-137.13 | 0.08 | -2.97 | -72.9% | $314.33 | $298.64 | 114 |
| all-out +30%, premium stop -20% | 4 | 25.0% | -20.0% | $-122.46 | 0.30 | -10.20 | -57.7% | $510.15 | $528.37 | 117 |
| all-out +30%, premium stop -30% | 3 | 33.3% | -26.4% | $-153.79 | 0.31 | -9.43 | -55.4% | $538.63 | $539.46 | 118 |
| all-out +30%, premium stop -50% | 3 | 33.3% | -28.3% | $-167.61 | 0.29 | -10.07 | -58.8% | $497.18 | $422.62 | 118 |
| all-out +30%, underlying stop | 3 | 66.7% | -5.5% | $-213.13 | 0.40 | -1.91 | -74.8% | $360.60 | $277.51 | 118 |
| bracket, next level | 1 | 0.0% | -100.0% | $-690.50 | 0.00 | -0.83 | -75.2% | $309.50 | $75.81 | 119 |
| trail 5% | 11 | 9.1% | +19.4% | $-63.42 | 0.85 | 0.33 | -93.9% | $302.35 | $261.85 | 105 |
| trail 10% | 11 | 9.1% | +19.4% | $-63.42 | 0.85 | 0.33 | -93.9% | $302.35 | $261.85 | 105 |
| trail 15% | 11 | 9.1% | +19.4% | $-63.42 | 0.85 | 0.33 | -93.9% | $302.35 | $261.85 | 105 |
| trail 1.5 ATR | 14 | 7.1% | +13.8% | $-41.75 | 0.87 | 0.54 | -91.6% | $415.45 | $428.76 | 103 |
| trail 2 ATR | 14 | 7.1% | +11.8% | $-59.50 | 0.83 | 0.23 | -96.6% | $166.97 | $403.11 | 104 |
| trail 3 ATR | 12 | 8.3% | +18.8% | $-44.86 | 0.88 | 0.44 | -90.7% | $461.72 | $287.22 | 108 |
| bracket 1.5R | 1 | 0.0% | -100.0% | $-690.50 | 0.00 | -0.83 | -75.2% | $309.50 | $75.81 | 119 |
| bracket 2R | 1 | 0.0% | -100.0% | $-690.50 | 0.00 | -0.83 | -75.2% | $309.50 | $75.81 | 119 |
| bracket 3R | 1 | 0.0% | -100.0% | $-690.50 | 0.00 | -0.83 | -75.2% | $309.50 | $75.81 | 119 |

Highest out-of-sample scale expectancy in this regime: scale, underlying stop, $-137.13 on 5 trades, win rate 20.0%, average capture -22.3%, max drawdown -72.9%. It does not clear the old gate. The paired all-out row is all-out +30%, underlying stop expectancy $-213.13 on 3 trades. That label is not a new default.
1 hit 0, 1 hit 1, 2 hit 2, 1 hit 3, 0 hit 4. Runner +100%: 0. Runner stopped at break-even: 4. Armed after the first target: 4.

$1,000 account, delta 0.20

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 5 | 0.0% | -40.4% | $-167.55 | 0.00 | -39.77 | -83.8% | $162.24 | $157.30 | 113 |
| scale, premium stop -30% | 6 | 50.0% | -19.2% | $-132.23 | 0.32 | -6.84 | -79.7% | $206.61 | $102.44 | 111 |
| scale, premium stop -50% | 4 | 25.0% | -39.4% | $-211.39 | 0.19 | -71.22 | -84.6% | $154.45 | $181.79 | 112 |
| scale, underlying stop | 5 | 60.0% | -30.3% | $-186.18 | 0.20 | -6.02 | -93.2% | $69.11 | $173.20 | 110 |
| all-out +30%, premium stop -20% | 5 | 0.0% | -40.4% | $-167.55 | 0.00 | -39.77 | -83.8% | $162.24 | $157.30 | 113 |
| all-out +30%, premium stop -30% | 10 | 40.0% | -16.6% | $-85.15 | 0.30 | -8.48 | -85.2% | $148.49 | $146.31 | 106 |
| all-out +30%, premium stop -50% | 4 | 25.0% | -40.9% | $-219.74 | 0.16 | -67.00 | -87.9% | $121.03 | $47.98 | 112 |
| all-out +30%, underlying stop | 7 | 57.1% | -23.3% | $-128.49 | 0.40 | -4.74 | -90.8% | $100.54 | $12.84 | 107 |
| bracket, next level | 3 | 0.0% | -81.0% | $-313.48 | 0.00 | -2.05 | -94.0% | $59.55 | $6.53 | 111 |
| trail 5% | 6 | 0.0% | -31.3% | $-148.61 | 0.00 | -2.62 | -89.2% | $108.32 | $191.13 | 106 |
| trail 10% | 6 | 0.0% | -31.3% | $-148.61 | 0.00 | -2.62 | -89.2% | $108.32 | $191.13 | 106 |
| trail 15% | 6 | 0.0% | -31.3% | $-148.61 | 0.00 | -2.62 | -89.2% | $108.32 | $191.13 | 106 |
| trail 1.5 ATR | 7 | 0.0% | -27.3% | $-122.28 | 0.00 | -2.38 | -85.6% | $144.06 | $94.51 | 109 |
| trail 2 ATR | 6 | 0.0% | -30.6% | $-145.93 | 0.00 | -2.40 | -87.6% | $124.42 | $137.04 | 109 |
| trail 3 ATR | 6 | 0.0% | -31.3% | $-148.61 | 0.00 | -2.62 | -89.2% | $108.32 | $127.25 | 109 |
| bracket 1.5R | 2 | 0.0% | -91.4% | $-446.60 | 0.00 | -1.75 | -89.3% | $106.80 | $16.60 | 112 |
| bracket 2R | 2 | 0.0% | -91.4% | $-446.60 | 0.00 | -1.75 | -89.3% | $106.80 | $16.60 | 112 |
| bracket 3R | 2 | 0.0% | -91.4% | $-446.60 | 0.00 | -1.75 | -89.3% | $106.80 | $16.60 | 112 |

Highest out-of-sample scale expectancy in this regime: scale, premium stop -30%, $-132.23 on 6 trades, win rate 50.0%, average capture -19.2%, max drawdown -79.7%. It does not clear the old gate. The paired all-out row is all-out +30%, premium stop -30% expectancy $-85.15 on 10 trades. That label is not a new default.
3 hit 0, 0 hit 1, 0 hit 2, 1 hit 3, 2 hit 4. Runner +100%: 2. Runner stopped at break-even: 1. Armed after the first target: 3.

### C, daily Dow

1838 signals. Same daily entries. Calls, 45 DTE.

In-sample five-lot quotes: 967. Median debit $598.24, median ask $1.20, median delta 0.45. Median capital at a -20% stop $6,001.75, at -30% $8,991.90, at -50% $14,972.18, and at the underlying stop $13,011.29. The sized account is the -30% median, $8,991.90. The unused 90th percentile at -30% is $22,692.28.
Out of sample, 168 of 838 book-delta five-lots fit in $1,000 (median debit $2,245.17, median delta 0.45). At delta 0.20, 509 of 838 fit (median debit $760.05, median ask $1.52, median delta 0.20).

Sized account, $8,991.90, delta 0.45

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 41 | 17.1% | -21.3% | $-214.18 | 0.12 | -8.68 | -97.7% | $210.37 | $16.62 | 776 |
| scale, premium stop -30% | 41 | 29.3% | -22.2% | $-215.99 | 0.22 | -4.83 | -98.5% | $136.47 | $45.72 | 747 |
| scale, premium stop -50% | 52 | 53.8% | -15.9% | $-169.03 | 0.39 | -2.33 | -97.8% | $202.18 | $70.35 | 648 |
| scale, underlying stop | 44 | 54.5% | -16.0% | $-199.02 | 0.28 | -1.37 | -98.1% | $235.09 | $76.80 | 685 |
| all-out +30%, premium stop -20% | 39 | 7.7% | -24.5% | $-227.15 | 0.10 | -8.13 | -98.5% | $132.92 | $30.50 | 785 |
| all-out +30%, premium stop -30% | 54 | 29.6% | -17.7% | $-162.63 | 0.40 | -3.34 | -97.8% | $210.14 | $45.13 | 727 |
| all-out +30%, premium stop -50% | 62 | 54.8% | -9.5% | $-141.79 | 0.57 | -1.21 | -98.0% | $200.75 | $39.27 | 613 |
| all-out +30%, underlying stop | 42 | 59.5% | -7.9% | $-210.10 | 0.44 | -0.71 | -98.3% | $167.64 | $73.40 | 638 |
| bracket, next level | 41 | 19.5% | -20.3% | $-213.82 | 0.20 | -1.12 | -97.9% | $225.19 | $136.03 | 733 |
| trail 5% | 45 | 24.4% | -14.5% | $-195.47 | 0.72 | -0.25 | -98.7% | $195.78 | $42.40 | 473 |
| trail 10% | 10 | 20.0% | -66.4% | $-880.18 | 0.03 | -0.52 | -98.4% | $190.12 | $7,725.10 | 720 |
| trail 15% | 10 | 30.0% | -33.1% | $-894.50 | 0.26 | -0.58 | -99.6% | $46.93 | $18,156.01 | 703 |
| trail 1.5 ATR | 29 | 13.8% | -22.4% | $-304.11 | 0.10 | -1.17 | -98.2% | $172.58 | $34.65 | 726 |
| trail 2 ATR | 48 | 25.0% | -18.7% | $-184.22 | 0.65 | -0.44 | -99.0% | $149.21 | $99.56 | 520 |
| trail 3 ATR | 16 | 37.5% | -32.4% | $-547.79 | 0.20 | -0.68 | -98.1% | $227.33 | $125.67 | 676 |
| bracket 1.5R | 19 | 21.1% | -29.2% | $-468.28 | 0.35 | 0.14 | -99.2% | $94.59 | $49.81 | 625 |
| bracket 2R | 19 | 21.1% | -29.2% | $-468.28 | 0.35 | 0.14 | -99.2% | $94.59 | $49.81 | 625 |
| bracket 3R | 19 | 21.1% | -29.2% | $-468.28 | 0.35 | 0.14 | -99.2% | $94.59 | $49.81 | 625 |

Highest out-of-sample scale expectancy in this regime: scale, premium stop -50%, $-169.03 on 52 trades, win rate 53.8%, average capture -15.9%, max drawdown -97.8%. It does not clear the old gate. The paired all-out row is all-out +30%, premium stop -50% expectancy $-141.79 on 62 trades. That label is not a new default.
22 hit 0, 4 hit 1, 10 hit 2, 8 hit 3, 8 hit 4. Runner +100%: 8. Runner stopped at break-even: 22. Armed after the first target: 30.

$1,000 account, delta 0.45, five contracts only when the debit fits

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 8 | 25.0% | -22.0% | $-101.44 | 0.11 | -10.32 | -82.5% | $188.50 | $27.98 | 842 |
| scale, premium stop -30% | 11 | 36.4% | -19.9% | $-73.09 | 0.27 | -4.53 | -82.7% | $196.06 | $30.58 | 829 |
| scale, premium stop -50% | 16 | 56.2% | -8.4% | $-50.42 | 0.55 | -1.69 | -88.9% | $193.34 | $28.59 | 802 |
| scale, underlying stop | 6 | 33.3% | -31.7% | $-139.44 | 0.11 | -6.92 | -85.6% | $163.37 | $18.18 | 837 |
| all-out +30%, premium stop -20% | 7 | 0.0% | -29.5% | $-119.86 | 0.00 | -12.54 | -84.9% | $160.95 | $27.98 | 842 |
| all-out +30%, premium stop -30% | 17 | 41.2% | -14.0% | $-45.33 | 0.61 | -2.19 | -87.6% | $229.44 | $28.51 | 801 |
| all-out +30%, premium stop -50% | 11 | 45.5% | -16.8% | $-73.28 | 0.55 | -2.34 | -89.5% | $193.91 | $28.36 | 803 |
| all-out +30%, underlying stop | 14 | 50.0% | -11.5% | $-59.94 | 0.61 | -1.10 | -93.4% | $160.80 | $25.32 | 772 |
| bracket, next level | 16 | 31.2% | -14.7% | $-55.41 | 0.35 | -0.44 | -90.2% | $113.39 | $17.97 | 811 |
| trail 5% | 7 | 28.6% | -11.2% | $-131.01 | 0.64 | -0.09 | -96.8% | $82.95 | $24.22 | 767 |
| trail 10% | 3 | 33.3% | -48.3% | $-312.00 | 0.05 | -0.34 | -95.0% | $63.99 | $6.20 | 797 |
| trail 15% | 3 | 33.3% | -48.3% | $-312.00 | 0.05 | -0.34 | -95.0% | $63.99 | $19.37 | 797 |
| trail 1.5 ATR | 12 | 16.7% | -9.2% | $-68.32 | 0.48 | -0.30 | -92.9% | $180.13 | $17.23 | 795 |
| trail 2 ATR | 9 | 22.2% | +2.6% | $-92.44 | 0.65 | -0.23 | -94.1% | $168.02 | $21.21 | 787 |
| trail 3 ATR | 3 | 33.3% | -43.0% | $-285.20 | 0.05 | -0.18 | -88.7% | $144.40 | $12.49 | 802 |
| bracket 1.5R | 5 | 20.0% | -44.6% | $-179.33 | 0.05 | -0.18 | -91.9% | $103.33 | $18.88 | 800 |
| bracket 2R | 5 | 20.0% | -44.6% | $-179.33 | 0.05 | -0.18 | -91.9% | $103.33 | $18.88 | 800 |
| bracket 3R | 5 | 20.0% | -44.6% | $-179.33 | 0.05 | -0.18 | -91.9% | $103.33 | $18.88 | 800 |

Highest out-of-sample scale expectancy in this regime: scale, premium stop -50%, $-50.42 on 16 trades, win rate 56.2%, average capture -8.4%, max drawdown -88.9%. It does not clear the old gate. The paired all-out row is all-out +30%, premium stop -50% expectancy $-73.28 on 11 trades. That label is not a new default.
5 hit 0, 2 hit 1, 4 hit 2, 2 hit 3, 3 hit 4. Runner +100%: 3. Runner stopped at break-even: 8. Armed after the first target: 11.

$1,000 account, delta 0.20

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 14 | 0.0% | -34.7% | $-69.04 | 0.00 | -25.07 | -96.7% | $33.44 | $18.91 | 832 |
| scale, premium stop -30% | 16 | 25.0% | -26.4% | $-59.93 | 0.14 | -8.34 | -95.9% | $41.14 | $20.01 | 819 |
| scale, premium stop -50% | 21 | 42.9% | -19.7% | $-46.14 | 0.24 | -4.18 | -97.5% | $30.96 | $21.02 | 792 |
| scale, underlying stop | 17 | 41.2% | -28.1% | $-57.42 | 0.22 | -2.01 | -98.4% | $23.89 | $26.33 | 758 |
| all-out +30%, premium stop -20% | 14 | 0.0% | -34.7% | $-69.04 | 0.00 | -25.07 | -96.7% | $33.44 | $18.91 | 832 |
| all-out +30%, premium stop -30% | 15 | 20.0% | -28.8% | $-64.14 | 0.21 | -6.81 | -96.2% | $37.94 | $17.14 | 819 |
| all-out +30%, premium stop -50% | 12 | 25.0% | -37.0% | $-81.12 | 0.22 | -6.06 | -97.5% | $26.53 | $17.02 | 809 |
| all-out +30%, underlying stop | 13 | 38.5% | -33.5% | $-74.14 | 0.21 | -2.35 | -96.7% | $36.15 | $26.35 | 768 |
| bracket, next level | 20 | 20.0% | -22.5% | $-49.74 | 0.14 | -0.90 | -99.5% | $5.28 | $16.49 | 793 |
| trail 5% | 11 | 18.2% | -46.7% | $-85.85 | 0.47 | -0.17 | -97.3% | $55.63 | $8.49 | 730 |
| trail 10% | 4 | 0.0% | -98.1% | $-249.66 | 0.00 | -0.06 | -99.9% | $1.34 | $6.16 | 783 |
| trail 15% | 4 | 0.0% | -98.1% | $-249.66 | 0.00 | -0.06 | -99.9% | $1.34 | $24.13 | 783 |
| trail 1.5 ATR | 16 | 18.8% | -13.6% | $-59.76 | 0.37 | -0.23 | -97.0% | $43.82 | $5.31 | 778 |
| trail 2 ATR | 7 | 0.0% | -61.8% | $-137.57 | 0.00 | -0.75 | -96.8% | $37.00 | $27.82 | 797 |
| trail 3 ATR | 5 | 0.0% | -93.5% | $-194.55 | 0.00 | -0.38 | -97.3% | $27.26 | $8.23 | 791 |
| bracket 1.5R | 7 | 0.0% | -74.7% | $-138.95 | 0.00 | -0.41 | -97.3% | $27.38 | $18.39 | 778 |
| bracket 2R | 7 | 0.0% | -74.7% | $-138.95 | 0.00 | -0.41 | -97.3% | $27.38 | $18.39 | 778 |
| bracket 3R | 7 | 0.0% | -74.7% | $-138.95 | 0.00 | -0.41 | -97.3% | $27.38 | $18.39 | 778 |

Highest out-of-sample scale expectancy in this regime: scale, premium stop -50%, $-46.14 on 21 trades, win rate 42.9%, average capture -19.7%, max drawdown -97.5%. It does not clear the old gate. The paired all-out row is all-out +30%, premium stop -50% expectancy $-81.12 on 12 trades. That label is not a new default.
9 hit 0, 1 hit 1, 5 hit 2, 5 hit 3, 1 hit 4. Runner +100%: 1. Runner stopped at break-even: 11. Armed after the first target: 12.

### D, daily Dow

292 signals. Same daily entries. Calls and puts follow the setup direction. 45 DTE.

In-sample five-lot quotes: 171. Median debit $568.30, median ask $1.14, median delta 0.41. Median capital at a -20% stop $5,702.34, at -30% $8,542.80, at -50% $14,223.71, and at the underlying stop $11,328.60. The sized account is the -30% median, $8,542.80. The unused 90th percentile at -30% is $23,475.75.
Out of sample, 30 of 114 book-delta five-lots fit in $1,000 (median debit $2,334.12, median delta 0.42). At delta 0.20, 64 of 114 fit (median debit $777.41, median ask $1.55, median delta 0.17).

Sized account, $8,542.80, delta 0.45

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 28 | 3.6% | -28.2% | $-292.15 | 0.01 | -19.02 | -95.8% | $362.50 | $196.87 | 87 |
| scale, premium stop -30% | 29 | 24.1% | -27.3% | $-280.93 | 0.15 | -5.98 | -95.4% | $395.83 | $211.57 | 83 |
| scale, premium stop -50% | 19 | 26.3% | -38.3% | $-437.78 | 0.04 | -5.37 | -97.4% | $225.05 | $169.05 | 94 |
| scale, underlying stop | 36 | 27.8% | -24.5% | $-224.53 | 0.17 | -4.19 | -94.6% | $459.83 | $201.11 | 73 |
| all-out +30%, premium stop -20% | 30 | 3.3% | -27.1% | $-271.73 | 0.04 | -18.07 | -95.4% | $390.99 | $219.47 | 86 |
| all-out +30%, premium stop -30% | 27 | 14.8% | -28.5% | $-301.25 | 0.16 | -8.20 | -95.2% | $409.04 | $257.16 | 86 |
| all-out +30%, premium stop -50% | 25 | 28.0% | -33.6% | $-324.60 | 0.25 | -5.26 | -95.4% | $427.75 | $226.42 | 89 |
| all-out +30%, underlying stop | 28 | 17.9% | -31.0% | $-295.39 | 0.20 | -6.40 | -96.9% | $271.94 | $158.10 | 85 |
| bracket, next level | 35 | 17.1% | -17.3% | $-235.02 | 0.52 | -0.10 | -96.3% | $317.06 | $107.09 | 62 |
| trail 5% | 43 | 18.6% | -16.1% | $-190.71 | 0.50 | -0.16 | -96.1% | $342.06 | $16.96 | 51 |
| trail 10% | 23 | 13.0% | -31.6% | $-360.55 | 0.28 | -0.87 | -97.5% | $250.22 | $194.50 | 76 |
| trail 15% | 40 | 22.5% | -6.5% | $-120.95 | 0.78 | 0.25 | -94.0% | $3,704.91 | $14.43 | 31 |
| trail 1.5 ATR | 41 | 12.2% | -20.2% | $-197.76 | 0.36 | -0.88 | -95.2% | $434.84 | $257.24 | 69 |
| trail 2 ATR | 21 | 9.5% | -34.9% | $-387.37 | 0.13 | -1.11 | -95.2% | $407.98 | $194.97 | 90 |
| trail 3 ATR | 28 | 10.7% | -29.7% | $-291.40 | 0.35 | -0.75 | -95.7% | $383.56 | $362.95 | 76 |
| bracket 1.5R | 20 | 5.0% | -26.6% | $-408.67 | 0.24 | -0.76 | -95.7% | $369.49 | $215.03 | 93 |
| bracket 2R | 20 | 5.0% | -26.6% | $-408.67 | 0.24 | -0.76 | -95.7% | $369.49 | $215.03 | 93 |
| bracket 3R | 20 | 5.0% | -26.6% | $-408.67 | 0.24 | -0.76 | -95.7% | $369.49 | $215.03 | 93 |

Highest out-of-sample scale expectancy in this regime: scale, underlying stop, $-224.53 on 36 trades, win rate 27.8%, average capture -24.5%, max drawdown -94.6%. It does not clear the old gate. The paired all-out row is all-out +30%, underlying stop expectancy $-295.39 on 28 trades. That label is not a new default.
23 hit 0, 5 hit 1, 5 hit 2, 2 hit 3, 1 hit 4. Runner +100%: 1. Runner stopped at break-even: 12. Armed after the first target: 13.

$1,000 account, delta 0.45, five contracts only when the debit fits

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 6 | 0.0% | -32.0% | $-128.45 | 0.00 | -30.08 | -77.1% | $229.30 | $89.66 | 110 |
| scale, premium stop -30% | 8 | 37.5% | -22.2% | $-97.26 | 0.22 | -5.19 | -80.0% | $221.89 | $129.50 | 107 |
| scale, premium stop -50% | 7 | 42.9% | -29.5% | $-125.66 | 0.20 | -4.57 | -88.0% | $120.38 | $88.35 | 108 |
| scale, underlying stop | 9 | 44.4% | -22.4% | $-89.20 | 0.25 | -2.58 | -82.3% | $197.22 | $93.69 | 106 |
| all-out +30%, premium stop -20% | 6 | 0.0% | -32.0% | $-128.45 | 0.00 | -30.08 | -77.1% | $229.30 | $89.66 | 110 |
| all-out +30%, premium stop -30% | 7 | 28.6% | -22.8% | $-91.33 | 0.35 | -4.18 | -65.3% | $360.68 | $184.08 | 109 |
| all-out +30%, premium stop -50% | 5 | 20.0% | -44.5% | $-169.35 | 0.15 | -7.02 | -84.7% | $153.27 | $193.75 | 111 |
| all-out +30%, underlying stop | 5 | 20.0% | -36.7% | $-140.58 | 0.17 | -6.76 | -70.3% | $297.12 | $208.65 | 111 |
| bracket, next level | 13 | 23.1% | -1.7% | $-45.79 | 0.82 | 0.04 | -89.1% | $404.69 | $52.32 | 102 |
| trail 5% | 11 | 27.3% | -7.1% | $-53.58 | 0.58 | -0.16 | -73.7% | $410.63 | $41.99 | 102 |
| trail 10% | 9 | 33.3% | -10.3% | $-80.92 | 0.52 | -0.16 | -80.9% | $271.73 | $24.92 | 102 |
| trail 15% | 9 | 33.3% | -10.3% | $-80.92 | 0.52 | -0.16 | -80.9% | $271.73 | $19.65 | 102 |
| trail 1.5 ATR | 10 | 20.0% | -13.3% | $-59.29 | 0.23 | -0.35 | -66.7% | $407.07 | $63.87 | 105 |
| trail 2 ATR | 9 | 22.2% | -18.3% | $-86.11 | 0.31 | -0.24 | -81.0% | $225.00 | $57.59 | 105 |
| trail 3 ATR | 8 | 25.0% | -13.2% | $-112.53 | 0.46 | -0.26 | -93.7% | $99.79 | $53.39 | 104 |
| bracket 1.5R | 13 | 15.4% | -2.6% | $-49.07 | 0.82 | 0.04 | -90.1% | $362.05 | $9.26 | 101 |
| bracket 2R | 13 | 15.4% | -2.6% | $-49.07 | 0.82 | 0.04 | -90.1% | $362.05 | $9.26 | 101 |
| bracket 3R | 13 | 15.4% | -2.6% | $-49.07 | 0.82 | 0.04 | -90.1% | $362.05 | $9.26 | 101 |

Highest out-of-sample scale expectancy in this regime: scale, underlying stop, $-89.20 on 9 trades, win rate 44.4%, average capture -22.4%, max drawdown -82.3%. It does not clear the old gate. The paired all-out row is all-out +30%, underlying stop expectancy $-140.58 on 5 trades. That label is not a new default.
5 hit 0, 0 hit 1, 3 hit 2, 0 hit 3, 1 hit 4. Runner +100%: 1. Runner stopped at break-even: 3. Armed after the first target: 4.

$1,000 account, delta 0.20

| Exit | OOS trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | OOS ending | IS ending | Skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20% | 11 | 0.0% | -32.8% | $-83.53 | 0.00 | -26.96 | -91.9% | $81.14 | $28.36 | 105 |
| scale, premium stop -30% | 13 | 15.4% | -32.3% | $-70.78 | 0.06 | -9.86 | -92.0% | $79.91 | $41.05 | 101 |
| scale, premium stop -50% | 12 | 25.0% | -32.5% | $-76.71 | 0.06 | -7.73 | -92.1% | $79.47 | $35.10 | 102 |
| scale, underlying stop | 11 | 36.4% | -24.2% | $-83.96 | 0.08 | -5.36 | -92.4% | $76.45 | $14.05 | 103 |
| all-out +30%, premium stop -20% | 11 | 0.0% | -32.8% | $-83.53 | 0.00 | -26.96 | -91.9% | $81.14 | $28.36 | 105 |
| all-out +30%, premium stop -30% | 12 | 16.7% | -27.5% | $-76.53 | 0.16 | -8.85 | -91.8% | $81.69 | $19.52 | 103 |
| all-out +30%, premium stop -50% | 5 | 20.0% | -50.3% | $-181.85 | 0.04 | -2.87 | -90.9% | $90.76 | $56.98 | 110 |
| all-out +30%, underlying stop | 3 | 0.0% | -78.5% | $-303.81 | 0.00 | -3.17 | -91.1% | $88.56 | $40.17 | 112 |
| bracket, next level | 3 | 0.0% | -78.5% | $-303.81 | 0.00 | -0.33 | -91.1% | $88.56 | $37.14 | 112 |
| trail 5% | 16 | 6.2% | -26.1% | $-57.24 | 0.56 | -0.07 | -96.0% | $84.23 | $34.53 | 96 |
| trail 10% | 5 | 0.0% | -72.9% | $-181.75 | 0.00 | -0.41 | -90.9% | $91.24 | $41.99 | 108 |
| trail 15% | 5 | 0.0% | -73.1% | $-182.94 | 0.00 | -0.41 | -91.5% | $85.32 | $16.52 | 108 |
| trail 1.5 ATR | 10 | 0.0% | -32.9% | $-89.64 | 0.00 | -0.59 | -89.6% | $103.63 | $22.06 | 104 |
| trail 2 ATR | 3 | 0.0% | -80.9% | $-330.04 | 0.00 | -0.39 | -99.0% | $9.87 | $27.62 | 113 |
| trail 3 ATR | 15 | 6.7% | -31.7% | $-60.13 | 0.56 | -0.06 | -95.4% | $98.03 | $14.98 | 93 |
| bracket 1.5R | 3 | 0.0% | -78.5% | $-303.81 | 0.00 | -0.33 | -91.1% | $88.56 | $35.78 | 112 |
| bracket 2R | 3 | 0.0% | -78.5% | $-303.81 | 0.00 | -0.33 | -91.1% | $88.56 | $35.78 | 112 |
| bracket 3R | 3 | 0.0% | -78.5% | $-303.81 | 0.00 | -0.33 | -91.1% | $88.56 | $35.78 | 112 |

Highest out-of-sample scale expectancy in this regime: scale, premium stop -30%, $-70.78 on 13 trades, win rate 15.4%, average capture -32.3%, max drawdown -92.0%. It does not clear the old gate. The paired all-out row is all-out +30%, premium stop -30% expectancy $-76.53 on 12 trades. That label is not a new default.
10 hit 0, 0 hit 1, 2 hit 2, 1 hit 3, 0 hit 4. Runner +100%: 0. Runner stopped at break-even: 3. Armed after the first target: 3.

Every sized-account scale row loses money, and none clears the old gate. The -20% premium stop does not lose 20%. When the bar's adverse extreme prices the option through the stop, the fill is that bid, not the stop limit, so a wide bar can take most of the premium. The account then cannot buy the next five-lot, which is why the skip count is large. On the bounce, with the account at $10,081.40, the -20% ladder closed 39 out-of-sample trades: 35 at the initial stop, 3 runners at break-even, and 1 runner at +100%. Expectancy was -$253.75, win rate 10.3%, average capture -23.5%, max drawdown -98.2%, ending $185.10. The paired all-out row was -$254.06 on 39 trades. Hourly A, hourly B, daily C, and daily D are the same shape: the highest scale expectancy in each sized regime is negative, the runner rarely reaches +100%, and a first target usually ends at break-even. The trails and the brackets, on the same five contracts, also lose money. A $1,000 account fits five book-delta contracts on 227 of 1,207 bounce signals, 18 of 222 hourly A signals, 13 of 121 hourly B signals, 168 of 838 daily C signals, and 30 of 114 daily D signals. Delta 0.20 fits more often (714, 165, 93, 509, and 64 of those same signals) because the premium is cheaper. The contract still needs a larger underlying move to reach +15% of premium, and the 3 DTE hourly book has little time for that move. Those cheaper rows lose money as well.

Not added to `config/optional_strategies.json`. The published A-D books and the earlier exit labels are unchanged. The default book is still dual momentum.
<!-- CHART_READS_SCALE_END -->

<!-- CHART_READS_SCALE_CORRECTED_START -->
## Corrected options scale-out

DOES NOT CHANGE THE GATE. The earlier scale-out section scored a different rule: after the +15% tier, every remaining contract moved to break-even. This section is the correction, frozen before the re-score. Contracts 1-4 (2 at +15%, 1 at +20%, 1 at +30%) keep the initial premium stop for the whole trade. The runner keeps that stop until the +15% tier fills, then its stop moves to the entry ask, and its limit stays at +100%. A stop sells only the contracts that stop applies to. Nothing was sent to a broker. Live trading stays off.

The cell the gate reads is a -20% premium stop and 21 DTE, the midpoint of the stated 5-35 DTE band. -30%, 5 DTE, and 35 DTE are sensitivities and do not replace it. Longs are calls and shorts are puts, delta 0.45. The sized account is the in-sample median equity that puts the -20% stop at about 2% of the account, and at least the five-lot debit. The $1,000 book takes five contracts only when that debit fits. Random entries keep the symbols, directions, and count, shuffle the timestamps with seed 17, and use the same ladder. The holdout is the same window each book used before.

### Chop-v2 60-minute box breakout

283 signals on the named list, frozen chop-v2 box, no cell override. Calls and puts follow the setup. 21 DTE. This is the forward-test candidate.
Holdout 2025-10-13 through 2026-10-06. Signals 283, of which 139 are in the holdout. In-sample five-lot quotes: 139. Median debit $4,202.99. Quotes that fit five contracts in $1,000: 0 of 139. Sized account $42,052.22, the in-sample median that puts the -20% stop near 2% of equity. The -30% row uses that same account.

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE, in sample | in sample | 44 | 18.2% | -17.8% | $-920.50 | 0.09 | -8.75 | -96.3% | $1,550.24 | 56 |
| scale, premium stop -20%, 21 DTE | gate | 53 | 17.0% | -17.0% | $-764.20 | 0.24 | -6.69 | -96.3% | $1,549.57 | 50 |
| scale, premium stop -30%, 21 DTE | sensitivity | 45 | 33.3% | -17.1% | $-870.23 | 0.28 | -4.22 | -93.8% | $2,891.95 | 37 |
| all-out +30%, premium stop -20%, 21 DTE | comparison | 53 | 15.1% | -15.9% | $-767.32 | 0.29 | -8.08 | -96.7% | $1,384.00 | 58 |
| scale, premium stop -20%, 5 DTE | sensitivity | 67 | 14.9% | -22.1% | $-616.96 | 0.14 | -9.97 | -98.3% | $715.72 | 38 |
| scale, premium stop -20%, 35 DTE | sensitivity | 42 | 16.7% | -16.4% | $-950.78 | 0.19 | -7.93 | -95.0% | $2,119.54 | 67 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE | gate, $1,000 | 0 | 0.0% | n/a | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 | 139 |
| scale, premium stop -30%, 21 DTE | sensitivity, $1,000 | 0 | 0.0% | n/a | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 | 139 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random entries, same -20% ladder, 21 DTE | random | 38 | 21.1% | -17.2% | $-1,065.36 | 0.12 | -9.82 | -96.3% | $1,568.53 | 81 |
Gated holdout row: 53 trades, expectancy $-764.20, profit factor 0.24, Sharpe -6.69, max drawdown -96.3%, ending $1,549.57. It does not clear the old gate. It does not beat the random entries on Sharpe with a drawdown that is not worse.
43 hit 0, 1 hit 1, 0 hit 2, 8 hit 3, 1 hit 4. Runner +100%: 1. Runner stopped at break-even: 7. Armed after the first target: 10.

### Partial bounce, daily Dow

2508 signals. Same bounce entry. Calls, 21 DTE. Holdout 2019-01-01 through 2026-10-06.
Holdout 2019-01-01 through 2026-10-06. Signals 2508, of which 1223 are in the holdout. In-sample five-lot quotes: 1270. Median debit $474.48. Quotes that fit five contracts in $1,000: 1073 of 1270. Sized account $4,764.04, the in-sample median that puts the -20% stop near 2% of equity. The -30% row uses that same account.

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE, in sample | in sample | 44 | 4.5% | -37.6% | $-107.79 | 0.07 | -13.11 | -99.5% | $21.48 | 1166 |
| scale, premium stop -20%, 21 DTE | gate | 23 | 4.3% | -29.8% | $-203.82 | 0.02 | -14.33 | -98.4% | $76.25 | 1189 |
| scale, premium stop -30%, 21 DTE | sensitivity | 23 | 13.0% | -26.6% | $-202.79 | 0.12 | -6.90 | -97.9% | $99.94 | 1182 |
| all-out +30%, premium stop -20%, 21 DTE | comparison | 25 | 4.0% | -28.7% | $-187.14 | 0.05 | -15.64 | -98.2% | $85.42 | 1184 |
| scale, premium stop -20%, 5 DTE | sensitivity | 25 | 0.0% | -41.6% | $-190.02 | 0.00 | -14.28 | -99.7% | $13.45 | 1190 |
| scale, premium stop -20%, 35 DTE | sensitivity | 21 | 0.0% | -27.7% | $-221.20 | 0.00 | -18.05 | -97.5% | $118.78 | 1192 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE | gate, $1,000 | 9 | 0.0% | -33.8% | $-104.89 | 0.00 | -28.73 | -94.4% | $55.98 | 1209 |
| scale, premium stop -30%, 21 DTE | sensitivity, $1,000 | 11 | 9.1% | -28.6% | $-83.85 | 0.04 | -7.66 | -93.1% | $77.67 | 1200 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random entries, same -20% ladder, 21 DTE | random | 17 | 0.0% | -37.7% | $-278.57 | 0.00 | -16.14 | -99.4% | $28.38 | 1196 |
Gated holdout row: 23 trades, expectancy $-203.82, profit factor 0.02, Sharpe -14.33, max drawdown -98.4%, ending $76.25. It does not clear the old gate. It beats the random entries on Sharpe with a drawdown that is not worse.
22 hit 0, 0 hit 1, 0 hit 2, 1 hit 3, 0 hit 4. Runner +100%: 0. Runner stopped at break-even: 1. Armed after the first target: 1.

### A, 60-minute

457 continuation signals. Calls, 21 DTE.
Holdout 2025-10-13 through 2026-10-06. Signals 457, of which 222 are in the holdout. In-sample five-lot quotes: 225. Median debit $4,158.84. Quotes that fit five contracts in $1,000: 0 of 225. Sized account $41,610.65, the in-sample median that puts the -20% stop near 2% of equity. The -30% row uses that same account.

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE, in sample | in sample | 46 | 13.0% | -19.3% | $-877.00 | 0.14 | -8.83 | -97.0% | $1,268.78 | 134 |
| scale, premium stop -20%, 21 DTE | gate | 45 | 17.8% | -18.4% | $-879.84 | 0.10 | -8.38 | -95.9% | $2,017.99 | 142 |
| scale, premium stop -30%, 21 DTE | sensitivity | 39 | 28.2% | -21.5% | $-1,040.32 | 0.12 | -7.54 | -97.5% | $1,038.00 | 136 |
| all-out +30%, premium stop -20%, 21 DTE | comparison | 44 | 13.6% | -18.5% | $-913.32 | 0.14 | -7.65 | -96.6% | $1,424.58 | 149 |
| scale, premium stop -20%, 5 DTE | sensitivity | 78 | 14.1% | -23.4% | $-524.57 | 0.14 | -6.22 | -98.3% | $694.41 | 95 |
| scale, premium stop -20%, 35 DTE | sensitivity | 32 | 18.8% | -18.9% | $-1,232.29 | 0.04 | -11.83 | -94.8% | $2,177.35 | 156 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE | gate, $1,000 | 0 | 0.0% | n/a | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 | 222 |
| scale, premium stop -30%, 21 DTE | sensitivity, $1,000 | 0 | 0.0% | n/a | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 | 222 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random entries, same -20% ladder, 21 DTE | random | 49 | 20.4% | -17.2% | $-811.07 | 0.18 | -7.39 | -95.5% | $1,868.40 | 129 |
Gated holdout row: 45 trades, expectancy $-879.84, profit factor 0.10, Sharpe -8.38, max drawdown -95.9%, ending $2,017.99. It does not clear the old gate. It does not beat the random entries on Sharpe with a drawdown that is not worse.
35 hit 0, 3 hit 1, 0 hit 2, 6 hit 3, 1 hit 4. Runner +100%: 1. Runner stopped at break-even: 8. Armed after the first target: 10.

### B, 60-minute

235 failed-breakout signals. Calls and puts follow the setup. 21 DTE.
Holdout 2025-10-13 through 2026-10-06. Signals 235, of which 121 are in the holdout. In-sample five-lot quotes: 112. Median debit $4,039.31. Quotes that fit five contracts in $1,000: 0 of 112. Sized account $40,415.31, the in-sample median that puts the -20% stop near 2% of equity. The -30% row uses that same account.

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE, in sample | in sample | 48 | 14.6% | -17.6% | $-810.72 | 0.14 | -6.47 | -96.3% | $1,500.73 | 48 |
| scale, premium stop -20%, 21 DTE | gate | 39 | 10.3% | -20.9% | $-1,003.93 | 0.06 | -12.86 | -96.9% | $1,261.94 | 69 |
| scale, premium stop -30%, 21 DTE | sensitivity | 34 | 20.6% | -24.0% | $-1,156.58 | 0.11 | -7.83 | -97.4% | $1,091.46 | 64 |
| all-out +30%, premium stop -20%, 21 DTE | comparison | 37 | 8.1% | -21.5% | $-1,051.17 | 0.07 | -11.31 | -96.2% | $1,521.88 | 71 |
| scale, premium stop -20%, 5 DTE | sensitivity | 64 | 12.5% | -21.7% | $-619.64 | 0.06 | -11.17 | -98.1% | $758.58 | 43 |
| scale, premium stop -20%, 35 DTE | sensitivity | 27 | 7.4% | -22.3% | $-1,424.76 | 0.06 | -15.90 | -95.2% | $1,946.83 | 85 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE | gate, $1,000 | 0 | 0.0% | n/a | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 | 121 |
| scale, premium stop -30%, 21 DTE | sensitivity, $1,000 | 0 | 0.0% | n/a | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 | 121 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random entries, same -20% ladder, 21 DTE | random | 41 | 14.6% | -20.3% | $-939.49 | 0.15 | -9.36 | -95.3% | $1,896.07 | 66 |
Gated holdout row: 39 trades, expectancy $-1,003.93, profit factor 0.06, Sharpe -12.86, max drawdown -96.9%, ending $1,261.94. It does not clear the old gate. It does not beat the random entries on Sharpe with a drawdown that is not worse.
34 hit 0, 1 hit 1, 1 hit 2, 2 hit 3, 1 hit 4. Runner +100%: 1. Runner stopped at break-even: 4. Armed after the first target: 5.

### C, daily Dow

1838 signals. Same daily entries. Calls, 21 DTE.
Holdout 2019-01-01 through 2026-10-06. Signals 1838, of which 853 are in the holdout. In-sample five-lot quotes: 967. Median debit $423.10. Quotes that fit five contracts in $1,000: 858 of 967. Sized account $4,250.18, the in-sample median that puts the -20% stop near 2% of equity. The -30% row uses that same account.

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE, in sample | in sample | 42 | 0.0% | -36.3% | $-100.55 | 0.00 | -15.95 | -99.4% | $27.09 | 902 |
| scale, premium stop -20%, 21 DTE | gate | 29 | 10.3% | -25.9% | $-142.76 | 0.06 | -11.47 | -97.4% | $110.24 | 805 |
| scale, premium stop -30%, 21 DTE | sensitivity | 22 | 31.8% | -22.3% | $-190.06 | 0.13 | -5.22 | -98.4% | $68.82 | 795 |
| all-out +30%, premium stop -20%, 21 DTE | comparison | 33 | 15.2% | -23.4% | $-126.71 | 0.22 | -10.00 | -98.4% | $68.89 | 799 |
| scale, premium stop -20%, 5 DTE | sensitivity | 35 | 0.0% | -38.8% | $-121.02 | 0.00 | -14.89 | -99.7% | $14.61 | 800 |
| scale, premium stop -20%, 35 DTE | sensitivity | 24 | 12.5% | -24.2% | $-171.09 | 0.08 | -11.40 | -96.6% | $143.94 | 807 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE | gate, $1,000 | 8 | 0.0% | -40.9% | $-116.54 | 0.00 | -37.58 | -93.2% | $67.66 | 845 |
| scale, premium stop -30%, 21 DTE | sensitivity, $1,000 | 10 | 20.0% | -26.7% | $-90.33 | 0.13 | -10.08 | -90.3% | $96.67 | 837 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random entries, same -20% ladder, 21 DTE | random | 20 | 10.0% | -30.2% | $-208.11 | 0.07 | -16.36 | -97.9% | $87.98 | 826 |
Gated holdout row: 29 trades, expectancy $-142.76, profit factor 0.06, Sharpe -11.47, max drawdown -97.4%, ending $110.24. It does not clear the old gate. It beats the random entries on Sharpe with a drawdown that is not worse.
24 hit 0, 2 hit 1, 0 hit 2, 3 hit 3, 0 hit 4. Runner +100%: 0. Runner stopped at break-even: 3. Armed after the first target: 5.

### D, daily Dow

292 signals. Same daily entries. Calls and puts follow the setup. 21 DTE.
Holdout 2019-01-01 through 2026-10-06. Signals 292, of which 116 are in the holdout. In-sample five-lot quotes: 171. Median debit $399.92. Quotes that fit five contracts in $1,000: 149 of 171. Sized account $4,018.31, the in-sample median that puts the -20% stop near 2% of equity. The -30% row uses that same account.

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE, in sample | in sample | 40 | 0.0% | -34.3% | $-99.18 | 0.00 | -18.14 | -98.7% | $51.07 | 131 |
| scale, premium stop -20%, 21 DTE | gate | 17 | 5.9% | -33.3% | $-225.89 | 0.00 | -17.22 | -95.6% | $178.16 | 98 |
| scale, premium stop -30%, 21 DTE | sensitivity | 19 | 10.5% | -34.4% | $-199.67 | 0.04 | -11.89 | -94.6% | $224.66 | 95 |
| all-out +30%, premium stop -20%, 21 DTE | comparison | 19 | 5.3% | -31.0% | $-202.24 | 0.07 | -16.40 | -95.6% | $175.76 | 97 |
| scale, premium stop -20%, 5 DTE | sensitivity | 22 | 0.0% | -46.0% | $-181.69 | 0.00 | -14.20 | -99.5% | $21.12 | 94 |
| scale, premium stop -20%, 35 DTE | sensitivity | 17 | 5.9% | -29.3% | $-222.58 | 0.01 | -17.95 | -94.2% | $234.45 | 98 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scale, premium stop -20%, 21 DTE | gate, $1,000 | 7 | 0.0% | -35.3% | $-116.44 | 0.00 | -31.93 | -81.5% | $184.93 | 109 |
| scale, premium stop -30%, 21 DTE | sensitivity, $1,000 | 8 | 12.5% | -28.5% | $-110.56 | 0.12 | -8.87 | -88.4% | $115.54 | 107 |

| Cell | Role | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending | Skipped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random entries, same -20% ladder, 21 DTE | random | 21 | 4.8% | -29.9% | $-176.83 | 0.02 | -14.24 | -92.4% | $304.84 | 95 |
Gated holdout row: 17 trades, expectancy $-225.89, profit factor 0.00, Sharpe -17.22, max drawdown -95.6%, ending $178.16. It does not clear the old gate. It does not beat the random entries on Sharpe with a drawdown that is not worse.
16 hit 0, 0 hit 1, 0 hit 2, 1 hit 3, 0 hit 4. Runner +100%: 0. Runner stopped at break-even: 0. Armed after the first target: 1.

Every gated holdout row loses money, and none clears the old gate. Where a row beats the random entries, both Sharpes are negative. That comparison only requires a higher Sharpe, a drawdown that is not worse, and at least 20 trades.

Not added to `config/optional_strategies.json`. The published A-D books, the earlier scale-out numbers, and the share forward test are unchanged. The default book is still dual momentum.
<!-- CHART_READS_SCALE_CORRECTED_END -->

<!-- CHART_READS_ATM_EXIT_START -->
## ATM 14 DTE option exits

DOES NOT CHANGE THE GATE. This search was frozen before the holdout was scored. Longs buy calls and shorts buy puts, delta 0.50, 14 calendar days. Each book tried 1293 exit cells: ascending 3-rung and 2-rung ladders, runner targets at +50%, +75%, +100%, and +150%, all-out targets, one reference time-stop ladder, and runner trails of 10%, 15%, and 25% off the peak premium. Stops are -10%, -15%, -20%, -25%, -30%, and -40% of the premium. Contracts 1-4 keep that stop. The runner moves to break-even only after the first rung fills, and only at the end of that bar. A stop that gaps through fills at the worse bid. Costs are the spread haircut and the option fees. The grid was not enlarged after these numbers.

The cell is the highest training Sharpe among cells with at least 30 training trades. Higher expectancy, then a milder drawdown, then the label break a tie. If no cell has 30 trades, the same rule uses cells with at least 15. The sized account is the training median equity that puts that cell's stop near 2% of the account, and at least the five-lot debit. Random entries keep the symbols, directions, and count, shuffle the timestamps with seed 17, and use that same cell and equity. SPY buy and hold is whole shares of that equity, 6 bps of slippage each side. Walk-forward re-selects inside the training span. It does not replace the cell.

A time stop is N trading sessions, the same clock as the existing hold. Hourly books try 2, 5, and 10 sessions. Daily books try 3, 7, and 14. Expiry at 14 DTE still applies, so the earlier of the two exits wins. The reference ladder for the time stop and the trail is 2 at +15%, 1 at +25%, 1 at +40%, runner +100%, and it was fixed before the run. Other cells keep the book's existing session hold.

### Chop-v2 60-minute box breakout

283 signals on the named list, frozen chop-v2 box, no cell override. Calls and puts follow the setup. 14 DTE, delta 0.50. This is the forward-test candidate.
Holdout 2025-10-13 through 2026-10-06. Opened training quotes 139, failed opens 5. Median debit $3,970.80. Median delta 0.48. Quotes that fit five contracts in $1,000: 0 of 139. Cells tried: 1293. Cells with at least 30 training trades: 1048. Training cells with positive expectancy: 0.
Chosen on training only, before the holdout: `C all-out +100% stop -40%`. highest training Sharpe among cells with at least 30 training trades. Sized account $79,435.22.

| Sample | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| training, chosen cell | 52 | 23.1% | -16.7% | $-1,179.09 | 0.33 | -2.29 | -84.0% | $18,122.44 |
| holdout, chosen cell | 52 | 21.2% | -23.7% | $-1,440.98 | 0.37 | -3.23 | -94.3% | $4,504.36 |
| random entries, same cell | 43 | 16.3% | -30.8% | $-1,826.15 | 0.20 | -3.52 | -98.9% | $910.67 |
| SPY buy and hold | 1 | 100.0% | n/a | $15,291.17 | n/a | 1.48 | -8.9% | $94,726.39 |
| $1,000 holdout | 0 | 0.0% | n/a | $0.00 | 0.00 | 0.00 | 0.0% | $1,000.00 |

Holdout: 52 trades, expectancy $-1,440.98, profit factor 0.37, Sharpe -3.23, max drawdown -94.3%, ending $4,504.36. It does not clear the old gate. It beats the random entries. It does not beat SPY buy and hold on Sharpe with a drawdown that is not worse.
48 hit 0, 4 hit 1, 0 hit 2, 0 hit 3, 0 hit 4. Runner outcomes: all_out 4, initial_stop 39, time_stop 9. Armed after the first rung: 0.
Multiple testing: 1293 cells were tried. The training Sharpe is -2.29 annualized. The Sharpe expected from the best of 1293 zero-edge tries, on a sample of this length and shape, is about 4.68 annualized. The deflated Sharpe probability is 0.0% (skew 0.74, kurtosis 7.26, 146 return observations). A high training Sharpe with a deflated Sharpe near zero is what trying this many cells produces when there is no edge. This probability does not include the other books. Six books were selected, plus one pooled cell, so the chance that some book looks good is higher than one book's deflated Sharpe says.

Neighbors are the adjacent stop, runner, first rung, trail, or time stop inside the frozen grid. Their holdout numbers were not used to pick the cell.

| Neighbor | Train Sharpe | Train exp. | Train DD | Train trades | Holdout Sharpe | Holdout exp. | Holdout DD | Holdout trades | Holdout ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C all-out +100% stop -30% | -3.69 | $-1,056.95 | -97.6% | 55 | -2.13 | $-965.65 | -92.4% | 57 | $4,540.40 |
| C all-out +75% stop -40% | -2.41 | $-1,066.93 | -84.9% | 56 | -3.24 | $-1,373.94 | -93.4% | 54 | $5,242.19 |

0 of 2 neighbors have a positive training Sharpe. 0 of 2 have a positive holdout expectancy and an ending equity above the start.

Walk-forward pooled expectancy $-826.03 on 44 test trades. Each fold's cell was chosen on that fold's training window only.

| Fold train | Fold test | Cell chosen on that train | Test trades | Test exp. | Test Sharpe | Test DD | Test ending |
|---|---|---|---:|---:|---:|---:|---:|
| 2024-10-17 through 2025-01-15 | 2025-01-16 through 2025-04-15 | none | 0 | n/a | n/a | n/a | n/a |
| 2024-10-17 through 2025-04-15 | 2025-04-16 through 2025-07-15 | C all-out +75% stop -20% | 26 | $-1,392.70 | -22.41 | -85.8% | $6,002.08 |
| 2024-10-17 through 2025-07-15 | 2025-07-16 through 2025-10-10 | C all-out +100% stop -30% | 18 | $-7.49 | 0.15 | -15.3% | $64,455.96 |

Pooled training cell on this holdout: `C all-out +100% stop -40%`. 52 trades, expectancy $-1,440.98, Sharpe -3.23, max drawdown -94.3%, ending $4,504.36. The pooled cell does not replace this book's cell.

This cell does not meet the pre-registered hold-up bar. holdout expectancy is not positive after costs. holdout ending equity is not above the start. holdout Sharpe is not positive. walk-forward pooled expectancy is not positive.

### Partial bounce, daily Dow

2508 signals. Same bounce entry. Calls, 14 DTE, delta 0.50. Holdout 2019-01-01 through 2026-10-06.
Holdout 2019-01-01 through 2026-10-06. Opened training quotes 1270, failed opens 15. Median debit $464.06. Median delta 0.50. Quotes that fit five contracts in $1,000: 1097 of 1270. Cells tried: 1293. Cells with at least 30 training trades: 1078. Training cells with positive expectancy: 0.
Chosen on training only, before the holdout: `B stop -40% rungs +20%/+30% runner +150%`. highest training Sharpe among cells with at least 30 training trades. Sized account $9,298.27.

| Sample | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| training, chosen cell | 110 | 36.4% | -23.8% | $-84.29 | 0.26 | -1.96 | -99.7% | $26.78 |
| holdout, chosen cell | 36 | 33.3% | -20.2% | $-256.81 | 0.26 | -4.41 | -99.4% | $53.04 |
| random entries, same cell | 77 | 45.5% | -19.1% | $-120.54 | 0.48 | -2.93 | -99.8% | $16.31 |
| SPY buy and hold | 1 | 100.0% | n/a | $23,543.36 | n/a | 0.95 | -33.5% | $32,841.63 |
| $1,000 holdout | 10 | 10.0% | -30.4% | $-96.26 | 0.08 | -7.33 | -96.7% | $37.38 |

Holdout: 36 trades, expectancy $-256.81, profit factor 0.26, Sharpe -4.41, max drawdown -99.4%, ending $53.04. It does not clear the old gate. It does not beat the random entries. It does not beat SPY buy and hold on Sharpe with a drawdown that is not worse.
21 hit 0, 3 hit 1, 6 hit 2, 6 hit 3, 0 hit 4. Runner outcomes: breakeven 8, initial_stop 22, target 6. Armed after the first rung: 15.
Multiple testing: 1293 cells were tried. The training Sharpe is -1.96 annualized. The Sharpe expected from the best of 1293 zero-edge tries, on a sample of this length and shape, is about 3.39 annualized. The deflated Sharpe probability is 0.0% (skew 0.77, kurtosis 19.20, 283 return observations). A high training Sharpe with a deflated Sharpe near zero is what trying this many cells produces when there is no edge. This probability does not include the other books. Six books were selected, plus one pooled cell, so the chance that some book looks good is higher than one book's deflated Sharpe says.

Neighbors are the adjacent stop, runner, first rung, trail, or time stop inside the frozen grid. Their holdout numbers were not used to pick the cell.

| Neighbor | Train Sharpe | Train exp. | Train DD | Train trades | Holdout Sharpe | Holdout exp. | Holdout DD | Holdout trades | Holdout ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B stop -30% rungs +20%/+30% runner +150% | -7.47 | $-83.75 | -99.6% | 83 | -6.03 | $-160.00 | -98.6% | 43 | $99.05 |
| B stop -40% rungs +20%/+30% runner +100% | -2.69 | $-86.72 | -99.8% | 107 | -4.98 | $-263.52 | -99.2% | 35 | $74.98 |
| B stop -40% rungs +15%/+30% runner +150% | -3.04 | $-83.67 | -99.9% | 111 | -4.44 | $-236.48 | -99.2% | 39 | $75.66 |
| B stop -40% rungs +25%/+30% runner +150% | -2.88 | $-91.87 | -99.8% | 101 | -3.50 | $-249.29 | -99.2% | 37 | $74.43 |

0 of 4 neighbors have a positive training Sharpe. 0 of 4 have a positive holdout expectancy and an ending equity above the start.

Walk-forward pooled expectancy $-107.60 on 198 test trades. Each fold's cell was chosen on that fold's training window only.

| Fold train | Fold test | Cell chosen on that train | Test trades | Test exp. | Test Sharpe | Test DD | Test ending |
|---|---|---|---:|---:|---:|---:|---:|
| 2010-01-01 through 2012-12-31 | 2013-01-01 through 2014-12-31 | B stop -40% rungs +10%/+40% runner +150% | 79 | $-81.25 | -2.74 | -99.0% | $65.53 |
| 2010-01-01 through 2014-12-31 | 2015-01-01 through 2016-12-31 | B stop -40% rungs +25%/+30% runner +150% | 51 | $-137.76 | -4.77 | -99.2% | $53.71 |
| 2010-01-01 through 2016-12-31 | 2017-01-01 through 2018-12-31 | B stop -40% rungs +40%/+50% runner +150% | 68 | $-115.60 | -2.13 | -96.8% | $259.61 |

Pooled training cell on this holdout: `C all-out +100% stop -40%`. 36 trades, expectancy $-256.85, Sharpe -3.80, max drawdown -99.4%, ending $51.63. The pooled cell does not replace this book's cell.

This cell does not meet the pre-registered hold-up bar. holdout expectancy is not positive after costs. holdout ending equity is not above the start. holdout Sharpe is not positive. it does not beat random entries on Sharpe with a drawdown that is not worse. walk-forward pooled expectancy is not positive.

### A, 60-minute

457 continuation signals. Calls, 14 DTE, delta 0.50.
Holdout 2025-10-13 through 2026-10-06. Opened training quotes 225, failed opens 10. Median debit $3,903.52. Median delta 0.49. Quotes that fit five contracts in $1,000: 0 of 225. Cells tried: 1293. Cells with at least 30 training trades: 1078. Training cells with positive expectancy: 0.
Chosen on training only, before the holdout: `C all-out +100% stop -40%`. highest training Sharpe among cells with at least 30 training trades. Sized account $78,089.54.

| Sample | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| training, chosen cell | 72 | 22.2% | -17.8% | $-497.11 | 0.70 | -0.40 | -67.1% | $42,297.45 |
| holdout, chosen cell | 77 | 24.7% | -12.9% | $-721.28 | 0.62 | -1.70 | -74.2% | $22,551.10 |
| random entries, same cell | 88 | 28.4% | -13.1% | $-753.91 | 0.61 | -1.95 | -87.2% | $11,745.10 |
| SPY buy and hold | 1 | 100.0% | n/a | $15,038.42 | n/a | 1.48 | -8.9% | $93,127.96 |
| $1,000 holdout | 0 | 0.0% | n/a | $0.00 | 0.00 | 0.00 | 0.0% | $1,000.00 |

Holdout: 77 trades, expectancy $-721.28, profit factor 0.62, Sharpe -1.70, max drawdown -74.2%, ending $22,551.10. It does not clear the old gate. It beats the random entries. It does not beat SPY buy and hold on Sharpe with a drawdown that is not worse.
64 hit 0, 13 hit 1, 0 hit 2, 0 hit 3, 0 hit 4. Runner outcomes: all_out 13, initial_stop 51, time_stop 12, window_end 1. Armed after the first rung: 0.
Multiple testing: 1293 cells were tried. The training Sharpe is -0.40 annualized. The Sharpe expected from the best of 1293 zero-edge tries, on a sample of this length and shape, is about 4.12 annualized. The deflated Sharpe probability is 0.0% (skew 6.83, kurtosis 62.46, 195 return observations). A high training Sharpe with a deflated Sharpe near zero is what trying this many cells produces when there is no edge. This probability does not include the other books. Six books were selected, plus one pooled cell, so the chance that some book looks good is higher than one book's deflated Sharpe says.

Neighbors are the adjacent stop, runner, first rung, trail, or time stop inside the frozen grid. Their holdout numbers were not used to pick the cell.

| Neighbor | Train Sharpe | Train exp. | Train DD | Train trades | Holdout Sharpe | Holdout exp. | Holdout DD | Holdout trades | Holdout ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C all-out +100% stop -30% | -3.47 | $-1,151.72 | -98.3% | 50 | -2.52 | $-830.82 | -97.9% | 69 | $1,246.71 |
| C all-out +75% stop -40% | -2.02 | $-888.80 | -86.5% | 76 | -2.93 | $-997.93 | -97.2% | 76 | $2,246.69 |

0 of 2 neighbors have a positive training Sharpe. 0 of 2 have a positive holdout expectancy and an ending equity above the start.

Walk-forward pooled expectancy $-880.87 on 70 test trades. Each fold's cell was chosen on that fold's training window only.

| Fold train | Fold test | Cell chosen on that train | Test trades | Test exp. | Test Sharpe | Test DD | Test ending |
|---|---|---|---:|---:|---:|---:|---:|
| 2024-10-17 through 2025-01-15 | 2025-01-16 through 2025-04-15 | C all-out +15% stop -30% | 32 | $-1,264.25 | -9.10 | -71.2% | $16,392.29 |
| 2024-10-17 through 2025-04-15 | 2025-04-16 through 2025-07-15 | C all-out +75% stop -30% | 17 | $517.32 | 1.26 | -14.6% | $68,439.09 |
| 2024-10-17 through 2025-07-15 | 2025-07-16 through 2025-10-10 | C all-out +100% stop -40% | 21 | $-1,428.54 | -6.05 | -36.0% | $53,398.62 |

Pooled training cell on this holdout: `C all-out +100% stop -40%`. 77 trades, expectancy $-721.28, Sharpe -1.70, max drawdown -74.2%, ending $22,551.10. The pooled cell does not replace this book's cell.

This cell does not meet the pre-registered hold-up bar. holdout expectancy is not positive after costs. holdout ending equity is not above the start. holdout Sharpe is not positive. walk-forward pooled expectancy is not positive.

### B, 60-minute

235 failed-breakout signals. Calls and puts follow the setup. 14 DTE, delta 0.50.
Holdout 2025-10-13 through 2026-10-06. Opened training quotes 112, failed opens 2. Median debit $3,742.78. Median delta -0.49. Quotes that fit five contracts in $1,000: 0 of 112. Cells tried: 1293. Cells with at least 30 training trades: 1078. Training cells with positive expectancy: 0.
Chosen on training only, before the holdout: `C all-out +100% stop -30%`. highest training Sharpe among cells with at least 30 training trades. Sized account $56,162.17.

| Sample | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| training, chosen cell | 63 | 25.4% | -8.4% | $-235.83 | 0.82 | -0.67 | -46.4% | $41,304.97 |
| holdout, chosen cell | 37 | 10.8% | -25.6% | $-1,497.59 | 0.15 | -5.36 | -98.7% | $751.44 |
| random entries, same cell | 44 | 13.6% | -25.0% | $-1,238.62 | 0.26 | -5.73 | -97.0% | $1,662.79 |
| SPY buy and hold | 1 | 100.0% | n/a | $10,741.73 | n/a | 1.48 | -8.8% | $66,903.90 |
| $1,000 holdout | 0 | 0.0% | n/a | $0.00 | 0.00 | 0.00 | 0.0% | $1,000.00 |

Holdout: 37 trades, expectancy $-1,497.59, profit factor 0.15, Sharpe -5.36, max drawdown -98.7%, ending $751.44. It does not clear the old gate. It does not beat the random entries. It does not beat SPY buy and hold on Sharpe with a drawdown that is not worse.
35 hit 0, 2 hit 1, 0 hit 2, 0 hit 3, 0 hit 4. Runner outcomes: all_out 2, initial_stop 33, time_stop 2. Armed after the first rung: 0.
Multiple testing: 1293 cells were tried. The training Sharpe is -0.67 annualized. The Sharpe expected from the best of 1293 zero-edge tries, on a sample of this length and shape, is about 4.61 annualized. The deflated Sharpe probability is 0.0% (skew 2.69, kurtosis 17.49, 148 return observations). A high training Sharpe with a deflated Sharpe near zero is what trying this many cells produces when there is no edge. This probability does not include the other books. Six books were selected, plus one pooled cell, so the chance that some book looks good is higher than one book's deflated Sharpe says.

Neighbors are the adjacent stop, runner, first rung, trail, or time stop inside the frozen grid. Their holdout numbers were not used to pick the cell.

| Neighbor | Train Sharpe | Train exp. | Train DD | Train trades | Holdout Sharpe | Holdout exp. | Holdout DD | Holdout trades | Holdout ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C all-out +100% stop -25% | -1.66 | $-511.20 | -75.8% | 67 | -6.89 | $-1,295.98 | -96.9% | 35 | $1,446.75 |
| C all-out +100% stop -40% | -2.06 | $-709.80 | -57.7% | 50 | -2.61 | $-1,169.88 | -88.4% | 56 | $9,361.17 |
| C all-out +75% stop -30% | -2.27 | $-561.36 | -68.4% | 65 | -5.52 | $-1,127.81 | -98.5% | 49 | $899.60 |

0 of 3 neighbors have a positive training Sharpe. 0 of 3 have a positive holdout expectancy and an ending equity above the start.

Walk-forward pooled expectancy $-899.94 on 49 test trades. Each fold's cell was chosen on that fold's training window only.

| Fold train | Fold test | Cell chosen on that train | Test trades | Test exp. | Test Sharpe | Test DD | Test ending |
|---|---|---|---:|---:|---:|---:|---:|
| 2024-10-17 through 2025-01-15 | 2025-01-16 through 2025-04-15 | C all-out +75% stop -30% | 15 | $-166.23 | -0.00 | -23.4% | $49,207.03 |
| 2024-10-17 through 2025-04-15 | 2025-04-16 through 2025-07-15 | C all-out +75% stop -30% | 15 | $-1,930.21 | -5.09 | -49.0% | $30,882.34 |
| 2024-10-17 through 2025-07-15 | 2025-07-16 through 2025-10-10 | C all-out +100% stop -30% | 19 | $-665.81 | -4.32 | -21.1% | $47,842.81 |

Pooled training cell on this holdout: `C all-out +100% stop -40%`. 56 trades, expectancy $-1,169.88, Sharpe -2.61, max drawdown -88.4%, ending $9,361.17. The pooled cell does not replace this book's cell.

This cell does not meet the pre-registered hold-up bar. holdout expectancy is not positive after costs. holdout ending equity is not above the start. holdout Sharpe is not positive. it does not beat random entries on Sharpe with a drawdown that is not worse. walk-forward pooled expectancy is not positive.

### C, daily Dow

1838 signals. Same daily entries. Calls, 14 DTE, delta 0.50.
Holdout 2019-01-01 through 2026-10-06. Opened training quotes 967, failed opens 18. Median debit $408.04. Median delta 0.50. Quotes that fit five contracts in $1,000: 869 of 967. Cells tried: 1293. Cells with at least 30 training trades: 1078. Training cells with positive expectancy: 0.
Chosen on training only, before the holdout: `B stop -40% rungs +15%/+30% runner +100%`. highest training Sharpe among cells with at least 30 training trades. Sized account $8,177.78.

| Sample | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| training, chosen cell | 102 | 26.5% | -28.1% | $-79.91 | 0.15 | -3.55 | -99.7% | $26.88 |
| holdout, chosen cell | 42 | 28.6% | -27.3% | $-192.42 | 0.13 | -6.01 | -98.8% | $96.00 |
| random entries, same cell | 63 | 39.7% | -19.2% | $-127.62 | 0.41 | -2.20 | -98.5% | $137.88 |
| SPY buy and hold | 1 | 100.0% | n/a | $20,740.58 | n/a | 0.95 | -33.6% | $28,918.37 |
| $1,000 holdout | 11 | 27.3% | -30.3% | $-85.21 | 0.12 | -5.84 | -93.8% | $62.74 |

Holdout: 42 trades, expectancy $-192.42, profit factor 0.13, Sharpe -6.01, max drawdown -98.8%, ending $96.00. It does not clear the old gate. It does not beat the random entries. It does not beat SPY buy and hold on Sharpe with a drawdown that is not worse.
23 hit 0, 6 hit 1, 10 hit 2, 3 hit 3, 0 hit 4. Runner outcomes: breakeven 11, initial_stop 28, target 3. Armed after the first rung: 19.
Multiple testing: 1293 cells were tried. The training Sharpe is -3.55 annualized. The Sharpe expected from the best of 1293 zero-edge tries, on a sample of this length and shape, is about 2.56 annualized. The deflated Sharpe probability is 0.0% (skew -2.88, kurtosis 21.22, 260 return observations). A high training Sharpe with a deflated Sharpe near zero is what trying this many cells produces when there is no edge. This probability does not include the other books. Six books were selected, plus one pooled cell, so the chance that some book looks good is higher than one book's deflated Sharpe says.

Neighbors are the adjacent stop, runner, first rung, trail, or time stop inside the frozen grid. Their holdout numbers were not used to pick the cell.

| Neighbor | Train Sharpe | Train exp. | Train DD | Train trades | Holdout Sharpe | Holdout exp. | Holdout DD | Holdout trades | Holdout ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B stop -30% rungs +15%/+30% runner +100% | -5.99 | $-77.40 | -99.6% | 79 | -5.73 | $-137.77 | -98.8% | 44 | $76.60 |
| B stop -40% rungs +15%/+30% runner +75% | -5.72 | $-94.89 | -99.8% | 86 | -5.76 | $-175.82 | -98.9% | 46 | $89.88 |
| B stop -40% rungs +15%/+30% runner +150% | -4.83 | $-84.19 | -99.9% | 97 | -5.85 | $-193.25 | -99.3% | 42 | $61.38 |
| B stop -40% rungs +10%/+30% runner +100% | -4.28 | $-81.65 | -99.8% | 100 | -6.14 | $-192.94 | -99.1% | 42 | $74.17 |
| B stop -40% rungs +20%/+30% runner +100% | -3.63 | $-85.82 | -99.7% | 95 | -5.85 | $-213.25 | -99.1% | 38 | $74.14 |

0 of 5 neighbors have a positive training Sharpe. 0 of 5 have a positive holdout expectancy and an ending equity above the start.

Walk-forward pooled expectancy $-132.70 on 148 test trades. Each fold's cell was chosen on that fold's training window only.

| Fold train | Fold test | Cell chosen on that train | Test trades | Test exp. | Test Sharpe | Test DD | Test ending |
|---|---|---|---:|---:|---:|---:|---:|
| 2010-01-01 through 2012-12-31 | 2013-01-01 through 2014-12-31 | A stop -40% rungs +25%/+40%/+50% runner +150% | 52 | $-111.08 | -4.52 | -99.1% | $57.19 |
| 2010-01-01 through 2014-12-31 | 2015-01-01 through 2016-12-31 | C all-out +50% stop -40% | 49 | $-129.78 | -2.25 | -98.3% | $112.74 |
| 2010-01-01 through 2016-12-31 | 2017-01-01 through 2018-12-31 | B stop -40% rungs +10%/+20% runner +150% | 47 | $-159.67 | -6.09 | -99.4% | $48.34 |

Pooled training cell on this holdout: `C all-out +100% stop -40%`. 37 trades, expectancy $-218.49, Sharpe -3.62, max drawdown -98.9%, ending $93.63. The pooled cell does not replace this book's cell.

This cell does not meet the pre-registered hold-up bar. holdout expectancy is not positive after costs. holdout ending equity is not above the start. holdout Sharpe is not positive. it does not beat random entries on Sharpe with a drawdown that is not worse. walk-forward pooled expectancy is not positive.

### D, daily Dow

292 signals. Same daily entries. Calls and puts follow the setup. 14 DTE, delta 0.50.
Holdout 2019-01-01 through 2026-10-06. Opened training quotes 171, failed opens 5. Median debit $392.92. Median delta 0.41. Quotes that fit five contracts in $1,000: 152 of 171. Cells tried: 1293. Cells with at least 30 training trades: 863. Training cells with positive expectancy: 0.
Chosen on training only, before the holdout: `C all-out +100% stop -40%`. highest training Sharpe among cells with at least 30 training trades. Sized account $7,875.43.

| Sample | Trades | Win rate | Avg capture | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| training, chosen cell | 69 | 14.5% | -28.0% | $-112.44 | 0.24 | -2.39 | -98.6% | $116.90 |
| holdout, chosen cell | 25 | 8.0% | -39.4% | $-309.45 | 0.22 | -6.41 | -98.2% | $139.15 |
| random entries, same cell | 21 | 19.0% | -21.7% | $-364.46 | 0.14 | -6.63 | -97.3% | $221.79 |
| SPY buy and hold | 1 | 100.0% | n/a | $19,619.47 | n/a | 0.95 | -33.1% | $27,494.90 |
| $1,000 holdout | 10 | 20.0% | -20.9% | $-82.65 | 0.47 | -1.94 | -84.8% | $173.48 |

Holdout: 25 trades, expectancy $-309.45, profit factor 0.22, Sharpe -6.41, max drawdown -98.2%, ending $139.15. It does not clear the old gate. It does not beat the random entries. It does not beat SPY buy and hold on Sharpe with a drawdown that is not worse.
23 hit 0, 2 hit 1, 0 hit 2, 0 hit 3, 0 hit 4. Runner outcomes: all_out 2, initial_stop 23. Armed after the first rung: 0.
Multiple testing: 1293 cells were tried. The training Sharpe is -2.39 annualized. The Sharpe expected from the best of 1293 zero-edge tries, on a sample of this length and shape, is about 4.21 annualized. The deflated Sharpe probability is 0.0% (skew 0.69, kurtosis 14.66, 187 return observations). A high training Sharpe with a deflated Sharpe near zero is what trying this many cells produces when there is no edge. This probability does not include the other books. Six books were selected, plus one pooled cell, so the chance that some book looks good is higher than one book's deflated Sharpe says.

Neighbors are the adjacent stop, runner, first rung, trail, or time stop inside the frozen grid. Their holdout numbers were not used to pick the cell.

| Neighbor | Train Sharpe | Train exp. | Train DD | Train trades | Holdout Sharpe | Holdout exp. | Holdout DD | Holdout trades | Holdout ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C all-out +100% stop -30% | -5.87 | $-102.43 | -98.8% | 57 | -12.42 | $-299.92 | -96.4% | 19 | $213.41 |
| C all-out +75% stop -40% | -3.65 | $-109.79 | -99.0% | 71 | -4.68 | $-299.86 | -99.0% | 26 | $79.00 |

0 of 2 neighbors have a positive training Sharpe. 0 of 2 have a positive holdout expectancy and an ending equity above the start.

Walk-forward pooled expectancy $-157.30 on 74 test trades. Each fold's cell was chosen on that fold's training window only.

| Fold train | Fold test | Cell chosen on that train | Test trades | Test exp. | Test Sharpe | Test DD | Test ending |
|---|---|---|---:|---:|---:|---:|---:|
| 2010-01-01 through 2012-12-31 | 2013-01-01 through 2014-12-31 | B stop -40% rungs +40%/+50% runner +150% | 30 | $-125.02 | -3.58 | -73.8% | $1,648.51 |
| 2010-01-01 through 2014-12-31 | 2015-01-01 through 2016-12-31 | C all-out +100% stop -40% | 18 | $-298.47 | -9.12 | -93.6% | $368.17 |
| 2010-01-01 through 2016-12-31 | 2017-01-01 through 2018-12-31 | C all-out +100% stop -40% | 26 | $-96.81 | -0.93 | -40.9% | $4,008.38 |

Pooled training cell on this holdout: `C all-out +100% stop -40%`. 25 trades, expectancy $-309.45, Sharpe -6.41, max drawdown -98.2%, ending $139.15. The pooled cell does not replace this book's cell.

This cell does not meet the pre-registered hold-up bar. holdout expectancy is not positive after costs. holdout ending equity is not above the start. holdout Sharpe is not positive. it does not beat random entries on Sharpe with a drawdown that is not worse. walk-forward pooled expectancy is not positive.

### Pooled cell

The pooled cell is `C all-out +100% stop -40%`. It is the highest mean training Sharpe across books where that cell has at least 30 training trades, and it has to clear that bar on at least 4 books. highest training Sharpe among cells with at least 30 training trades. It was chosen before any holdout score. It is not wired unless it is also the chop book's own cell and that cell holds up.

No chosen cell is profitable on its untouched holdout after costs. Profit here means expectancy above zero and ending equity above the start. Costs are the spread haircut, the option fees, and a gap fill at the worse bid.

The chop book's cell does not hold up, so the sandbox options sub-book is unchanged. It is still the corrected ladder: 21 DTE, delta 0.45, contracts 1-4 at the -20% stop, runner break-even only after +15%, target +100%. Live trading stays off.

Not added to `config/optional_strategies.json`. The published scale-out numbers and the share forward test are unchanged. The default book is still dual momentum.
<!-- CHART_READS_ATM_EXIT_END -->
<!-- CHART_READS_HOLD_START -->
## Chop-hold retest

DOES NOT CHANGE THE GATE. This is the annotated NVDA sequence, frozen before the score: a breakout of a 10-session shelf, a rejection of the 2-standard-deviation VWAP band, then a low-volume chop pullback that holds the broken level, then a strong close out of that chop. The pullback is the chop flag already scored. That flag was not retuned. The stop is under the held level. The exits, if a fill exists, are the frozen five-contract scale-out, the all-out +30% comparison, the percent and ATR trails, and the brackets. Nothing was sent to a broker. `live_trading_enabled` stays false.

The shelf is the prior 10 sessions. Its high and its low each have to be touched in two of those sessions, within the frozen 0.50 ATR touch, and the height has to sit inside setup D's frozen ATR bounds. The breakout is a strong candle closing through that side by 0.10 ATR, on the breakout side of session VWAP. The chop zone is at least six contiguous chop bars inside the next 5 sessions, and it has to trade back to the broken level. No close may go back through the level, and no wick may exceed the 0.50 ATR touch. The next strong candle has to close out of the chop zone. One attempt per breakout. Short is the mirror. The 5-minute book is not in this run. Both clocks are inside the free Yahoo intraday cap.

Exit grid, unchanged from the scale-out study: scale, premium stop -20%, scale, premium stop -30%, scale, premium stop -50%, scale, underlying stop, all-out +30%, premium stop -20%, all-out +30%, premium stop -30%, all-out +30%, premium stop -50%, all-out +30%, underlying stop, bracket, next level, trail 5%, trail 10%, trail 15%, trail 1.5 ATR, trail 2 ATR, trail 3 ATR, bracket 1.5R, bracket 2R, bracket 3R.

### Chop-hold, 60-minute

0 signals (0 long, 0 short) on 2024-10-17 through 2026-10-06. In sample 2024-10-17 through 2025-10-10. Out of sample 2025-10-13 through 2026-10-06. Hold is up to 5 sessions. Calls and puts would be 3 DTE, delta 0.45, five contracts. The scan saw 132 breakouts, 0 of them with a six-bar chop run, 0 of those runs also rejecting the VWAP band while the hold was intact, 0 hold breaks, and 0 resumptions.

There is no fill, so the scale-out, the trails, and the brackets are not scored on this book. A five-lot cannot be sized, and there is no win rate, target distribution, or drawdown. The empty book does not clear the old gate.

### Chop-hold, 15-minute

0 signals (0 long, 0 short) on 2026-08-13 through 2026-10-06. In sample 2026-08-13 through 2026-09-09. Out of sample 2026-09-10 through 2026-10-06. Hold is flattened at the session close. Calls and puts would be 3 DTE, delta 0.45, five contracts. The scan saw 4 breakouts, 0 of them with a six-bar chop run, 0 of those runs also rejecting the VWAP band while the hold was intact, 0 hold breaks, and 0 resumptions.

There is no fill, so the scale-out, the trails, and the brackets are not scored on this book. A five-lot cannot be sized, and there is no win rate, target distribution, or drawdown. The empty book does not clear the old gate.

The annotated NVDA chart is a 20-session 60m window from 2026-09-09 through 2026-10-06 10:30:00-04:00. Yahoo's adjusted high in that window is $243.37, against the annotated high of $243.37. The last bar closes at $242.17; the annotation's price is $241.37. Friday 2026-10-02 trades $233.60 to $237.87 and closes $233.99. The drawn lines are 234.0, 232.5, 227.5, 221.5. The drawn pullback is 232.5 to 235.0.

On that hourly window the chop flag is on for 0 of 135 bars. Narrow is on for 86, quiet volume for 73, and VWAP has been crossed at least three times in 20 bars on 123. The tangled 9/20 EMA leg is on for 0. The hold scan marks 0 entries. The same 20 sessions on 15-minute bars have 8 chop bars, from $228.82 to $231.35, and 0 hold entries. 8 of those chop bars are before 2026-10-02 and 0 are on or after it. The chop dates are 2026-09-29, 2026-10-01. The rule was not loosened to force a mark.

Charts: `reports/setups/readHOLD_NVDA_60m.png` and `reports/setups/readHOLD_NVDA_15m.png`. Gold bars are the chop flag. Dotted lines are the annotated levels. The pale band is the annotated 232.5-235 pullback. The dashed vertical is Friday, October 2. No triangle is drawn, because the scan did not mark an entry.

Not added to `config/optional_strategies.json`. The published A-D books, the bounce, and the earlier exit labels are unchanged. The default book is still dual momentum.
<!-- CHART_READS_HOLD_END -->

<!-- CHART_READS_CHOP_V2_START -->
## Chop v2

DOES NOT CHANGE THE GATE. The v1 chop flag is unchanged. This flag drops the tangled-EMA requirement. Quiet volume is relative volume under 0.85, or a declining 20-bar average versus the 60-bar average while the bar is still at most 1.20 times its own average. Narrow range is ATR at or under 0.85 times its prior 120-bar average, or Bollinger bandwidth in the bottom 20% of 120 bars, or a 10-bar box inside 1.5 ATR. Rotation is three crosses of VWAP or of that box midpoint in 20 bars, or a stacked 9/20 EMA flag within 0.75 ATR and 1.5 ATR of price. The grid changes one of those round numbers at a time. The default above is the gated cell. A cell chosen on earlier data is a sensitivity. Nothing was sent to a broker. Live trading stays off.

SPY daily, 2026-08-01 through 2026-10-05, the 755-775 stretch. Chop v2 is on for 17 of 45 bars. 17 of those closes sit inside 755-775. The longest run is 7 bars. That is enough of a run inside the band to call the stretch marked. The threshold was not moved after this check.

NVDA 60-minute, 2026-09-09 through 2026-10-06. The window high is $243.37 against the annotated $243.37. The last close is $242.17 against $241.37. Friday trades $233.60 to $237.87 and closes $233.99. Chop v2 is on for 68 of 135 bars, 68 of them before Friday and 0 on or after Friday inside 232.5-235. The longest such pullback run is 0 bars. The annotated pullback is not marked as a six-bar chop zone. Hold entries in the window: 0. The rule was not retuned.

Merged swings keep every confirmed pivot in the last 250 daily bars and collapse prices within 0.5 ATR, weighted by touches. The old 120-bar set of six highs and six lows is unchanged.

| Drawn | Nearest merged swing | Touches | Distance | Within 0.5 ATR |
|---|---:|---:|---:|---|
| 781 | 775.05 | 17 | 5.95 | no |
| 768 | 775.05 | 17 | 7.05 | no |
| 760 | 758.35 | 19 | 1.65 | yes |
| 752 | 753.15 | 20 | 1.15 | yes |
| 740/735 | 737.68 | 35 | 0.18 | yes |
| 700 | 698.74 | 4 | 1.26 | yes |
| 690 | 691.41 | 20 | 1.41 | yes |
| 683 | 682.12 | 52 | 0.88 | yes |
| 675 | 676.56 | 59 | 1.56 | yes |
| 655 | 654.15 | 29 | 0.85 | yes |
| 632 | 626.11 | 1 | 5.89 | no |

SPY ATR on the last bar is $6.76. A hit is a merged swing within 0.5 ATR of the drawn line.

Time in chop, default cell, named list, daily bars from 2023-01-01 through 2026-10-06.

| Symbol | Bars | Chop bars | Share |
|---|---:|---:|---:|
| AAPL | 943 | 188 | 19.9% |
| AMD | 943 | 190 | 20.1% |
| IWM | 943 | 248 | 26.3% |
| META | 943 | 160 | 17.0% |
| MSFT | 943 | 147 | 15.6% |
| NVDA | 943 | 151 | 16.0% |
| QQQ | 943 | 151 | 16.0% |
| SPY | 943 | 187 | 19.8% |
| TSLA | 943 | 231 | 24.5% |
| UNH | 943 | 215 | 22.8% |

Dow daily holdout, median 19.0% of bars, 42 symbols.

Named list, 60-minute regular hours, the whole Yahoo window.

| Symbol | Bars | Chop bars | Share |
|---|---:|---:|---:|
| AAPL | 3417 | 852 | 24.9% |
| AMD | 3417 | 847 | 24.8% |
| IWM | 3416 | 786 | 23.0% |
| META | 3418 | 917 | 26.8% |
| MSFT | 3418 | 808 | 23.6% |
| NVDA | 3417 | 928 | 27.2% |
| QQQ | 3417 | 845 | 24.7% |
| SPY | 3416 | 870 | 25.5% |
| TSLA | 3417 | 921 | 27.0% |
| UNH | 3417 | 807 | 23.6% |

### Breakout, chop pullback, hold, resume

**Chop-hold v2, 60-minute, 2025-10-13 through 2026-10-06.** 0 signals.

| Exit | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| level target | 0 | 0.0% | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 |
| trail 15% | 0 | 0.0% | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 |
| bracket 2R | 0 | 0.0% | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 |
The gate reads the level-target row. It does not clear profit factor 1.10, Sharpe 0.40, drawdown no worse than -30%, and 300 trades.
Walk-forward on the level target, cell chosen inside each training fold: 0 trades, win 0.0%, expectancy $0.00, profit factor n/a, Sharpe 0.00, max drawdown 0.0%, ending $1,000.00. Cells: default, default, default.

**Chop-hold v2, 15-minute, 2026-08-13 through 2026-10-06.** 0 signals.

| Exit | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| level target | 0 | 0.0% | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 |
| trail 15% | 0 | 0.0% | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 |
| bracket 2R | 0 | 0.0% | $0.00 | n/a | 0.00 | 0.0% | $1,000.00 |
The gate reads the level-target row. It does not clear profit factor 1.10, Sharpe 0.40, drawdown no worse than -30%, and 300 trades.

60-minute counts on the full sample: {'breakouts': 139, 'rejected': 3, 'chop_runs': 34, 'hold_breaks': 17, 'signals': 1}. 15-minute counts: {'breakouts': 4, 'rejected': 0, 'chop_runs': 3, 'hold_breaks': 2, 'signals': 0}.

### Chop-box breakout, relative volume above 1.5

Daily Dow, default cell, 2023-01-01 through 2026-10-06.

**Daily Dow chop-v2 breakout, 2023-01-01 through 2026-10-06.** 107 signals.

| Exit | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| level target | 48 | 35.4% | $-7.78 | 0.52 | -0.71 | -56.4% | $626.54 |
| trail 15% | 22 | 54.5% | $-5.10 | 0.81 | -0.08 | -34.0% | $887.88 |
| bracket 2R | 44 | 31.8% | $-6.85 | 0.57 | -0.51 | -46.4% | $698.40 |

Random entries, same level-target exit: 49 trades, win 30.6%, expectancy $-9.39, profit factor 0.48, Sharpe -0.77, max drawdown -49.4%, ending $539.87.
Random entries, same 15% trail: 26 trades, win 50.0%, expectancy $-13.09, profit factor 0.66, Sharpe -0.32, max drawdown -56.5%, ending $659.64.
The gate reads the level-target row. It does not clear profit factor 1.10, Sharpe 0.40, drawdown no worse than -30%, and 300 trades.

The training window 2010-01-01 through 2022-12-31 chose box_bars 6 (76 trades, win 44.7%, expectancy $7.40, profit factor 1.39, Sharpe 0.38, max drawdown -31.1%, ending $1,562.09). On the holdout that cell is 21 trades, win 33.3%, expectancy $-4.17, profit factor 0.77, Sharpe -0.20, max drawdown -25.4%, ending $912.34. It does not replace the default.

SPY buy and hold, whole shares that fit in $1,000, 2023-01-01 through 2026-10-06: 2 shares, 1 trades, win 100.0%, expectancy $826.71, profit factor n/a, Sharpe 1.41, max drawdown -15.4%, ending $1,826.71.

Hourly named list, default cell, the second half of the Yahoo sample.

**60-minute chop-v2 breakout, 2025-10-13 through 2026-10-06.** 139 signals.

| Exit | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| level target | 64 | 43.8% | $-0.77 | 0.93 | -0.11 | -27.3% | $950.91 |
| trail 15% | 37 | 62.2% | $10.02 | 1.50 | 1.10 | -27.6% | $1,370.78 |
| bracket 2R | 56 | 37.5% | $-0.37 | 0.97 | 0.03 | -33.3% | $979.33 |

Random entries, same level-target exit: 77 trades, win 29.9%, expectancy $-6.21, profit factor 0.44, Sharpe -2.65, max drawdown -53.0%, ending $522.20.
Random entries, same 15% trail: 41 trades, win 41.5%, expectancy $-11.88, profit factor 0.34, Sharpe -2.47, max drawdown -48.7%, ending $512.86.
The gate reads the level-target row. It does not clear profit factor 1.10, Sharpe 0.40, drawdown no worse than -30%, and 300 trades.

Hourly walk-forward, level target: 65 trades, win 43.1%, expectancy $0.23, profit factor 1.03, Sharpe -0.07, max drawdown -27.4%, ending $962.69. Cells: rel_volume_max 1.0, rel_volume_max 0.75, rel_volume_max 0.75.

15-minute named list, default cell, the whole short Yahoo window. Anecdotal.

**15-minute chop-v2 breakout, 2026-08-13 through 2026-10-06.** 76 signals.

| Exit | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| level target | 18 | 27.8% | $-2.90 | 0.32 | -4.27 | -5.2% | $947.81 |
| trail 15% | 18 | 27.8% | $-2.75 | 0.40 | -4.17 | -5.0% | $950.43 |
| bracket 2R | 18 | 27.8% | $-2.32 | 0.46 | -2.90 | -4.2% | $958.17 |
The gate reads the level-target row. It does not clear profit factor 1.10, Sharpe 0.40, drawdown no worse than -30%, and 300 trades.

### No-trade filter on A-D and the bounce

Skip a signal when the default chop-v2 flag is on at the signal close. The flag helps only when out-of-sample expectancy is higher, losing trades are fewer, and at least 20 trades remain. That label does not change the gate. Daily rows are the 2023-2026 holdout. Hourly rows are the second half of the Yahoo sample.

| Book | Window | Baseline | Skip chop v2 | Inside | Helps |
|---|---|---|---|---:|---|
| A, 60-minute | 2025-10-13 through 2026-10-06 | 131 trades, win 31.3%, expectancy $-0.86, profit factor 0.86, Sharpe -0.65, max drawdown -14.0%, ending $886.97 | 99 trades, win 37.4%, expectancy $0.25, profit factor 1.04, Sharpe 0.24, max drawdown -11.8%, ending $1,024.39 | 70 | yes |
| B, 60-minute | 2025-10-13 through 2026-10-06 | 85 trades, win 28.2%, expectancy $-0.92, profit factor 0.86, Sharpe -0.36, max drawdown -23.8%, ending $921.86 | 53 trades, win 28.3%, expectancy $-0.13, profit factor 0.98, Sharpe 0.01, max drawdown -13.5%, ending $993.34 | 49 | yes |
| C, daily Dow | 2023-01-01 through 2026-10-06 | 98 trades, win 36.7%, expectancy $-1.86, profit factor 0.90, Sharpe -0.22, max drawdown -46.6%, ending $817.81 | 87 trades, win 39.1%, expectancy $1.12, profit factor 1.06, Sharpe 0.23, max drawdown -27.2%, ending $1,097.01 | 72 | yes |
| D, daily Dow | 2023-01-01 through 2026-10-06 | 37 trades, win 29.7%, expectancy $1.04, profit factor 1.07, Sharpe 0.14, max drawdown -23.2%, ending $1,038.43 | 33 trades, win 33.3%, expectancy $3.56, profit factor 1.23, Sharpe 0.31, max drawdown -21.2%, ending $1,117.52 | 7 | yes |
| Bounce, level target | 2023-01-01 through 2026-10-06 | 145 trades, win 57.2%, expectancy $6.91, profit factor 1.45, Sharpe 1.06, max drawdown -22.1%, ending $2,002.17 | 131 trades, win 58.0%, expectancy $9.43, profit factor 1.58, Sharpe 1.26, max drawdown -21.5%, ending $2,234.84 | 98 | yes |

A, 60-minute unfiltered still matches $886.97 on 131 trades.
B, 60-minute unfiltered still matches $921.86 on 85 trades.

### Bounce, 15% trail, regime and chop v2

The exit is the 15% trail, the bounce row that led the earlier exit study. Replaying that published window (2019-01-01 through 2026-10-06) produced 118 trades, win 55.1%, expectancy $13.63, profit factor 1.43, Sharpe 0.60, max drawdown -32.3%, ending $2,608.44. The gated writeup is $2,608.44 on 118 trades. This replay matches.

The new test keeps the 15% trail and adds two filters: the default chop-v2 flag is off, and the regime cell is the stock above its own 200-day average. SPY above its 200-day average, and both together, are the grid. The choice, if one is reported, comes from 2010 through 2022. The gate reads the stock-above-200 default on 2023-2026, not the best holdout row.

| Book | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| 15% trail, no new filter | 57 | 54.4% | $6.98 | 1.35 | 0.48 | -27.9% | $1,397.93 |
| 15% trail, stock above 200-day, chop v2 off | 49 | 51.0% | $2.64 | 1.16 | 0.26 | -26.2% | $1,129.54 |
| 15% trail, spy above 200-day, chop v2 off | 54 | 63.0% | $19.10 | 1.80 | 1.02 | -21.4% | $2,031.52 |
| 15% trail, both above 200-day, chop v2 off | 46 | 50.0% | $-2.44 | 0.87 | -0.06 | -31.1% | $887.68 |
| random entries, same 15% trail | 55 | 60.0% | $19.77 | 1.55 | 0.86 | -29.8% | $2,087.34 |

Training chose `stock` (154 trades, win 53.9%, expectancy $1.62, profit factor 1.09, Sharpe 0.19, max drawdown -59.5%, ending $1,249.02 in sample). That cell on the holdout is 49 trades, win 51.0%, expectancy $2.64, profit factor 1.16, Sharpe 0.26, max drawdown -26.2%, ending $1,129.54.

Random entries with the same 15% trail, matched to the default filtered signals: 55 trades, win 60.0%, expectancy $19.77, profit factor 1.55, Sharpe 0.86, max drawdown -29.8%, ending $2,087.34.
SPY buy and hold over the holdout: 2 shares, 1 trades, win 100.0%, expectancy $826.71, profit factor n/a, Sharpe 1.41, max drawdown -15.4%, ending $1,826.71.
Against those random entries the default book does not beat them on Sharpe with a drawdown that is not worse. Against SPY buy and hold it does not beat that comparison. The gate does not clear.

Charts: `reports/setups/readCHOPv2_SPY_1d.png` and `reports/setups/readCHOPv2_NVDA_60m.png`.

Not added to `config/optional_strategies.json`. The published A-D books, the v1 chop flag, the 120-bar level set, and the bounce's published trail are unchanged. The default book is still dual momentum.
<!-- CHART_READS_CHOP_V2_END -->
