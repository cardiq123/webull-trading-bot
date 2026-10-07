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

The chop book's cell does not hold up, so the exit ladder is unchanged. It is still the corrected ladder: contracts 1-4 at the -20% stop, runner break-even only after +15%, target +100%. The contract is 14 DTE at the nearest strike. Live trading stays off.

Not added to `config/optional_strategies.json`. The published scale-out numbers and the share forward test are unchanged. The default book is still dual momentum.
<!-- CHART_READS_ATM_EXIT_END -->

<!-- CHART_READS_ATM_UNIVERSE_START -->
## ATM exits on the liquid list and the Dow gate

DOES NOT CHANGE THE EXIT GRID. The 1,293 cells were already frozen. This run only changes the symbol universe. The liquid list was written down before the holdout was scored: NVDA, AAPL, UNH, MSFT, AMZN, META, GOOGL, JPM, AMD, TSLA, AVGO, COST, V, MA, LLY, XOM, SPY, QQQ. SPY and QQQ are index references. That list is a 2026 snapshot and is survivorship-biased. The gate is point-in-time Dow membership on the signal day, from `universe_dow`. There is no point-in-time S&P 500 file here, so a name that was never in the Dow is reported on the liquid list and cannot pass the gate by itself. The cell is the highest training Sharpe on the Dow book among cells with at least 30 training trades. The liquid list is then scored with that same cell, pooled and per symbol. A cell chosen on the liquid list's own training is a sensitivity. It is not the gate. Per-symbol rows were not used to pick the cell. Costs are the spread haircut, the option fees, and a gap fill at the worse bid.

### Dow point-in-time gate

Chop-v2 60-minute, Dow point-in-time: `A stop -30% rungs +20%/+25%/+30% runner +150%` on 91 holdout trades, expectancy $-417.36, profit factor 0.42, Sharpe -3.74, max drawdown -96.7%, ending $1,638.54. does not clear the old gate

Holdout by symbol, same Dow cell and the Dow sized equity. A zero means that name had no holdout trade.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| AAPL | 10 | 40.0% | $-377.65 | 0.40 | -3.82 | -9.8% | $35,841.94 |
| AMGN | 6 | 50.0% | $-769.96 | 0.24 | -5.07 | -11.7% | $34,998.63 |
| AMZN | 10 | 40.0% | $-340.76 | 0.46 | -2.68 | -15.2% | $36,210.79 |
| AXP | 9 | 11.1% | $-1,342.33 | 0.01 | -13.92 | -30.5% | $27,537.49 |
| BA | 18 | 16.7% | $-788.12 | 0.19 | -7.60 | -36.8% | $25,432.32 |
| CAT | 13 | 46.2% | $-1,006.04 | 0.60 | -0.09 | -61.5% | $26,539.84 |
| CRM | 14 | 14.3% | $-1,400.81 | 0.07 | -14.06 | -49.5% | $20,007.15 |
| CSCO | 8 | 25.0% | $-310.06 | 0.19 | -5.72 | -6.8% | $37,137.92 |
| CVX | 10 | 30.0% | $-328.60 | 0.39 | -5.19 | -13.3% | $36,332.40 |
| DIS | 8 | 25.0% | $-333.79 | 0.22 | -6.71 | -8.0% | $36,948.11 |
| GOOGL | 6 | 16.7% | $-1,977.81 | 0.05 | -11.77 | -31.7% | $27,751.56 |
| GS | 12 | 50.0% | $-1,022.13 | 0.54 | -2.13 | -42.0% | $27,352.89 |
| HD | 9 | 22.2% | $-838.27 | 0.14 | -8.04 | -20.8% | $32,073.97 |
| HON | 10 | 20.0% | $-549.75 | 0.12 | -9.68 | -15.4% | $34,120.97 |
| IBM | 14 | 35.7% | $-1,064.00 | 0.32 | -5.75 | -40.7% | $24,722.48 |
| JNJ | 3 | 66.7% | $243.80 | 3.49 | 8.45 | -0.7% | $40,349.80 |
| JPM | 11 | 18.2% | $-826.88 | 0.18 | -10.02 | -23.0% | $30,522.69 |
| KO | 8 | 25.0% | $-155.45 | 0.17 | -11.45 | -3.1% | $38,374.83 |
| MCD | 14 | 21.4% | $-501.90 | 0.18 | -9.09 | -17.7% | $32,591.84 |
| MMM | 12 | 8.3% | $-763.82 | 0.02 | -19.03 | -23.3% | $30,452.57 |
| MRK | 7 | 28.6% | $-425.31 | 0.20 | -6.93 | -10.0% | $36,641.26 |
| MSFT | 13 | 46.2% | $-1,278.89 | 0.28 | -4.92 | -42.0% | $22,992.89 |
| NKE | 10 | 20.0% | $-149.98 | 0.36 | -5.10 | -5.0% | $38,118.64 |
| NVDA | 12 | 16.7% | $-1,117.46 | 0.14 | -7.22 | -40.3% | $26,208.92 |
| PG | 7 | 28.6% | $-195.71 | 0.39 | -4.30 | -5.4% | $38,248.44 |
| SHW | 4 | 50.0% | $-179.94 | 0.63 | -1.87 | -5.7% | $38,898.65 |
| TRV | 5 | 40.0% | $-740.09 | 0.18 | -9.20 | -11.2% | $35,917.97 |
| UNH | 11 | 27.3% | $-947.23 | 0.26 | -5.97 | -26.3% | $29,198.89 |
| V | 10 | 40.0% | $-484.02 | 0.36 | -6.34 | -14.2% | $34,778.25 |
| VZ | 6 | 16.7% | $-144.23 | 0.10 | -12.82 | -2.4% | $38,753.07 |
| WMT | 11 | 36.4% | $-245.64 | 0.23 | -6.36 | -7.4% | $36,916.36 |

Partial bounce, Dow point-in-time: `B stop -40% rungs +20%/+30% runner +150%` on 36 holdout trades, expectancy $-256.81, profit factor 0.26, Sharpe -4.41, max drawdown -99.4%, ending $53.04. does not clear the old gate

Holdout by symbol, same Dow cell and the Dow sized equity. A zero means that name had no holdout trade.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| AA | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| AAPL | 21 | 42.9% | $-354.31 | 0.27 | -3.78 | -81.6% | $1,857.71 |
| AMGN | 18 | 44.4% | $-402.43 | 0.27 | -3.39 | -79.8% | $2,054.51 |
| AMZN | 11 | 45.5% | $-325.34 | 0.52 | -1.89 | -39.7% | $5,719.50 |
| AXP | 32 | 53.1% | $-216.23 | 0.60 | -1.90 | -80.7% | $2,378.94 |
| BA | 5 | 0.0% | $-1,561.28 | 0.00 | -10.52 | -84.0% | $1,491.85 |
| BAC | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| CAT | 11 | 9.1% | $-707.33 | 0.05 | -10.43 | -84.4% | $1,517.59 |
| CRM | 6 | 0.0% | $-1,449.80 | 0.00 | -20.89 | -93.6% | $599.47 |
| CSCO | 38 | 23.7% | $-192.25 | 0.16 | -5.05 | -81.2% | $1,992.87 |
| CVX | 39 | 43.6% | $-219.56 | 0.32 | -2.96 | -92.1% | $735.60 |
| DD | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| DIS | 26 | 42.3% | $-331.61 | 0.34 | -4.74 | -93.3% | $676.43 |
| DOW | 26 | 34.6% | $-120.36 | 0.28 | -5.66 | -36.2% | $6,168.85 |
| GE | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| GOOGL | 4 | 75.0% | $82.52 | 1.14 | 1.27 | -19.6% | $9,628.34 |
| GS | 16 | 43.8% | $-439.66 | 0.45 | -2.63 | -79.7% | $2,263.65 |
| HD | 15 | 40.0% | $-530.16 | 0.26 | -3.73 | -85.6% | $1,345.85 |
| HON | 24 | 41.7% | $-331.89 | 0.32 | -5.10 | -86.7% | $1,332.98 |
| HPQ | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| IBM | 36 | 38.9% | $-191.75 | 0.42 | -1.99 | -75.7% | $2,395.12 |
| INTC | 33 | 42.4% | $-129.80 | 0.29 | -4.57 | -49.8% | $5,014.85 |
| JNJ | 35 | 40.0% | $-227.90 | 0.31 | -3.84 | -86.5% | $1,321.85 |
| JPM | 30 | 43.3% | $-243.23 | 0.46 | -2.06 | -78.7% | $2,001.47 |
| KO | 30 | 20.0% | $-171.78 | 0.13 | -8.41 | -55.4% | $4,144.80 |
| MCD | 11 | 9.1% | $-775.42 | 0.03 | -9.80 | -91.7% | $768.62 |
| MMM | 31 | 38.7% | $-268.92 | 0.25 | -6.16 | -90.0% | $961.79 |
| MRK | 38 | 42.1% | $-140.08 | 0.41 | -2.49 | -67.6% | $3,975.24 |
| MSFT | 14 | 50.0% | $-480.11 | 0.42 | -1.62 | -73.4% | $2,576.76 |
| NKE | 39 | 43.6% | $-157.41 | 0.46 | -2.55 | -67.0% | $3,159.43 |
| NVDA | 14 | 42.9% | $-466.78 | 0.32 | -2.19 | -72.2% | $2,763.35 |
| PFE | 8 | 25.0% | $-85.18 | 0.17 | -6.49 | -7.3% | $8,616.82 |
| PG | 44 | 45.5% | $-192.08 | 0.34 | -2.56 | -90.9% | $846.77 |
| RTX | 2 | 50.0% | $-64.89 | 0.78 | -1.16 | -7.0% | $9,168.49 |
| SHW | 9 | 33.3% | $-702.52 | 0.37 | -5.15 | -74.3% | $2,975.55 |
| T | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| TRV | 33 | 45.5% | $-244.70 | 0.43 | -3.33 | -86.8% | $1,223.15 |
| UNH | 7 | 14.3% | $-1,094.75 | 0.04 | -12.65 | -83.8% | $1,635.02 |
| V | 17 | 41.2% | $-470.54 | 0.29 | -4.67 | -88.1% | $1,299.14 |
| VZ | 48 | 25.0% | $-97.41 | 0.16 | -6.24 | -51.0% | $4,622.59 |
| WMT | 39 | 46.2% | $-83.42 | 0.46 | -2.65 | -45.2% | $6,045.07 |
| XOM | 11 | 27.3% | $-138.09 | 0.25 | -4.47 | -20.4% | $7,779.27 |

A, 60-minute, Dow point-in-time: `A stop -40% rungs +15%/+30%/+40% runner +75%` on 73 holdout trades, expectancy $-653.75, profit factor 0.21, Sharpe -4.70, max drawdown -99.2%, ending $366.43. does not clear the old gate

Holdout by symbol, same Dow cell and the Dow sized equity. A zero means that name had no holdout trade.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| AAPL | 23 | 34.8% | $-754.54 | 0.23 | -7.31 | -37.3% | $30,735.53 |
| AMGN | 16 | 37.5% | $-932.18 | 0.24 | -4.81 | -31.7% | $33,175.13 |
| AMZN | 18 | 22.2% | $-1,019.08 | 0.11 | -7.61 | -38.1% | $29,746.54 |
| AXP | 18 | 27.8% | $-1,008.85 | 0.13 | -6.82 | -39.8% | $29,930.74 |
| BA | 21 | 38.1% | $-640.03 | 0.28 | -5.05 | -28.3% | $34,649.27 |
| CAT | 11 | 27.3% | $-3,224.94 | 0.13 | -8.58 | -75.3% | $12,615.65 |
| CRM | 20 | 30.0% | $-1,095.32 | 0.23 | -5.78 | -45.6% | $26,183.53 |
| CSCO | 24 | 37.5% | $-246.76 | 0.37 | -3.94 | -14.2% | $42,167.84 |
| CVX | 15 | 40.0% | $-206.23 | 0.50 | -2.67 | -8.8% | $44,996.59 |
| DIS | 14 | 21.4% | $-411.08 | 0.10 | -10.19 | -13.1% | $42,334.84 |
| DOW | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| GOOGL | 3 | 0.0% | $-2,245.16 | 0.00 | -42.31 | -14.0% | $41,354.51 |
| GS | 15 | 40.0% | $-2,430.19 | 0.30 | -5.24 | -79.1% | $11,637.20 |
| HD | 18 | 33.3% | $-728.43 | 0.28 | -4.55 | -28.6% | $34,978.25 |
| HON | 19 | 42.1% | $-467.23 | 0.33 | -4.87 | -22.3% | $39,212.66 |
| IBM | 20 | 35.0% | $-780.19 | 0.34 | -3.78 | -33.7% | $32,486.11 |
| INTC | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| JNJ | 21 | 42.9% | $-357.18 | 0.43 | -3.35 | -16.8% | $40,589.25 |
| JPM | 15 | 40.0% | $-614.39 | 0.27 | -4.41 | -20.2% | $38,874.13 |
| KO | 23 | 34.8% | $-125.10 | 0.31 | -5.53 | -6.0% | $45,212.67 |
| MCD | 25 | 16.0% | $-795.14 | 0.10 | -7.65 | -42.4% | $28,211.58 |
| MMM | 13 | 53.8% | $-123.88 | 0.54 | -1.65 | -6.4% | $46,479.57 |
| MRK | 15 | 40.0% | $-267.55 | 0.34 | -4.27 | -10.5% | $44,076.70 |
| MSFT | 21 | 38.1% | $-1,270.15 | 0.27 | -4.70 | -55.5% | $21,416.93 |
| NKE | 16 | 31.2% | $-146.44 | 0.29 | -4.79 | -5.8% | $45,746.96 |
| NVDA | 16 | 43.8% | $-532.18 | 0.35 | -3.65 | -20.6% | $39,575.13 |
| PG | 15 | 33.3% | $-293.87 | 0.29 | -6.21 | -9.5% | $43,681.92 |
| SHW | 11 | 36.4% | $-771.89 | 0.26 | -4.34 | -19.6% | $39,599.25 |
| TRV | 17 | 29.4% | $-701.76 | 0.18 | -5.58 | -26.8% | $36,160.05 |
| UNH | 21 | 28.6% | $-1,572.17 | 0.13 | -9.97 | -69.1% | $15,074.52 |
| V | 17 | 41.2% | $-538.28 | 0.24 | -3.88 | -21.8% | $38,939.29 |
| VZ | 12 | 25.0% | $-160.98 | 0.20 | -7.37 | -4.1% | $46,158.21 |
| WMT | 18 | 38.9% | $-257.33 | 0.28 | -5.69 | -9.8% | $43,458.11 |

B, 60-minute, Dow point-in-time: `C all-out +75% stop -40%` on 72 holdout trades, expectancy $-651.75, profit factor 0.27, Sharpe -4.54, max drawdown -99.3%, ending $325.12. does not clear the old gate

Holdout by symbol, same Dow cell and the Dow sized equity. A zero means that name had no holdout trade.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| AAPL | 12 | 25.0% | $-235.89 | 0.72 | -1.09 | -19.8% | $44,420.10 |
| AMGN | 10 | 10.0% | $-1,405.38 | 0.20 | -6.56 | -33.2% | $33,196.96 |
| AMZN | 7 | 14.3% | $-1,543.99 | 0.11 | -6.96 | -27.6% | $36,442.88 |
| AXP | 10 | 0.0% | $-1,951.74 | 0.00 | -9.96 | -41.3% | $27,733.37 |
| BA | 13 | 30.8% | $-392.96 | 0.58 | -2.14 | -21.6% | $42,142.35 |
| CAT | 11 | 18.2% | $-3,747.65 | 0.18 | -6.00 | -88.1% | $6,026.60 |
| CRM | 15 | 26.7% | $-770.95 | 0.50 | -3.24 | -32.2% | $35,686.55 |
| CSCO | 16 | 18.8% | $-383.28 | 0.26 | -5.14 | -16.4% | $41,118.32 |
| CVX | 8 | 12.5% | $-821.27 | 0.02 | -10.71 | -13.9% | $40,680.60 |
| DIS | 11 | 18.2% | $-296.18 | 0.28 | -4.98 | -7.5% | $43,992.81 |
| GS | 9 | 11.1% | $-4,527.62 | 0.16 | -2.64 | -87.2% | $6,502.23 |
| HD | 7 | 42.9% | $237.88 | 1.25 | 1.25 | -9.8% | $48,915.95 |
| HON | 14 | 14.3% | $-908.74 | 0.15 | -6.71 | -26.9% | $34,528.40 |
| IBM | 13 | 46.2% | $-498.99 | 0.63 | -1.46 | -16.4% | $40,763.96 |
| INTC | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| JNJ | 12 | 33.3% | $-45.93 | 0.93 | -0.14 | -10.2% | $46,699.58 |
| JPM | 13 | 30.8% | $-180.27 | 0.80 | -0.96 | -13.8% | $44,907.29 |
| KO | 9 | 22.2% | $-182.83 | 0.30 | -5.76 | -4.5% | $45,605.32 |
| MCD | 9 | 33.3% | $-324.24 | 0.56 | -1.96 | -11.1% | $44,332.61 |
| MMM | 9 | 22.2% | $-565.25 | 0.24 | -5.80 | -12.2% | $42,163.58 |
| MRK | 4 | 25.0% | $-177.49 | 0.61 | -2.07 | -4.0% | $46,540.83 |
| MSFT | 9 | 44.4% | $-253.53 | 0.82 | -0.43 | -22.6% | $44,969.02 |
| NKE | 8 | 37.5% | $-17.81 | 0.87 | -0.28 | -2.4% | $47,108.30 |
| NVDA | 8 | 50.0% | $-230.52 | 0.74 | -0.92 | -10.9% | $45,406.67 |
| PG | 10 | 30.0% | $-272.40 | 0.49 | -4.15 | -7.8% | $44,526.75 |
| SHW | 13 | 30.8% | $-196.10 | 0.84 | -0.59 | -17.3% | $44,701.50 |
| TRV | 10 | 30.0% | $-389.55 | 0.54 | -2.57 | -9.7% | $43,355.32 |
| UNH | 11 | 27.3% | $-1,022.19 | 0.45 | -4.36 | -25.6% | $36,006.73 |
| V | 13 | 15.4% | $-1,177.57 | 0.16 | -6.69 | -33.2% | $31,942.43 |
| VZ | 7 | 14.3% | $-149.12 | 0.22 | -4.53 | -2.6% | $46,206.97 |
| WMT | 14 | 28.6% | $-225.08 | 0.49 | -3.76 | -7.8% | $44,099.74 |

C, daily, Dow point-in-time: `B stop -40% rungs +15%/+30% runner +100%` on 42 holdout trades, expectancy $-192.42, profit factor 0.13, Sharpe -6.01, max drawdown -98.8%, ending $96.00. does not clear the old gate

Holdout by symbol, same Dow cell and the Dow sized equity. A zero means that name had no holdout trade.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| AA | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| AAPL | 27 | 48.1% | $-210.86 | 0.44 | -3.11 | -75.3% | $2,484.63 |
| AMGN | 21 | 52.4% | $-309.56 | 0.46 | -2.97 | -80.0% | $1,677.00 |
| AMZN | 7 | 57.1% | $-171.01 | 0.71 | -0.43 | -45.5% | $6,980.69 |
| AXP | 27 | 59.3% | $-249.03 | 0.42 | -2.08 | -84.9% | $1,453.97 |
| BA | 10 | 40.0% | $-693.20 | 0.34 | -3.72 | -85.6% | $1,245.77 |
| BAC | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| CAT | 11 | 18.2% | $-584.75 | 0.14 | -6.90 | -79.4% | $1,745.49 |
| CRM | 14 | 42.9% | $-345.35 | 0.50 | -2.50 | -63.6% | $3,342.89 |
| CSCO | 26 | 46.2% | $-96.07 | 0.43 | -2.79 | -35.8% | $5,679.93 |
| CVX | 21 | 38.1% | $-361.10 | 0.19 | -5.20 | -93.0% | $594.67 |
| DD | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| DIS | 15 | 60.0% | $-153.67 | 0.44 | -2.51 | -28.3% | $5,872.80 |
| DOW | 24 | 37.5% | $-105.10 | 0.31 | -6.02 | -32.4% | $5,655.37 |
| GE | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| GOOGL | 1 | 0.0% | $-2,382.37 | 0.00 | -36.20 | -29.1% | $5,795.41 |
| GS | 18 | 55.6% | $-375.13 | 0.56 | -1.87 | -88.1% | $1,425.37 |
| HD | 18 | 38.9% | $-346.47 | 0.37 | -2.92 | -78.3% | $1,941.33 |
| HON | 18 | 33.3% | $-401.48 | 0.28 | -5.29 | -88.4% | $951.21 |
| HPQ | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| IBM | 28 | 35.7% | $-184.55 | 0.42 | -1.82 | -73.1% | $3,010.27 |
| INTC | 24 | 33.3% | $-146.52 | 0.17 | -5.35 | -44.5% | $4,661.34 |
| JNJ | 29 | 41.4% | $-216.18 | 0.31 | -3.24 | -82.3% | $1,908.55 |
| JPM | 24 | 54.2% | $-255.36 | 0.35 | -3.58 | -76.0% | $2,049.07 |
| KO | 27 | 25.9% | $-166.07 | 0.07 | -8.36 | -55.4% | $3,694.00 |
| MCD | 14 | 28.6% | $-520.79 | 0.13 | -6.72 | -89.2% | $886.66 |
| MMM | 14 | 35.7% | $-527.15 | 0.14 | -6.41 | -90.6% | $797.63 |
| MRK | 26 | 34.6% | $-238.23 | 0.16 | -6.57 | -75.8% | $1,983.89 |
| MSFT | 13 | 53.8% | $-474.31 | 0.32 | -4.43 | -76.8% | $2,011.74 |
| NKE | 27 | 37.0% | $-284.41 | 0.21 | -4.25 | -94.1% | $498.63 |
| NVDA | 8 | 25.0% | $-687.02 | 0.14 | -5.62 | -67.2% | $2,681.65 |
| PFE | 7 | 14.3% | $-81.27 | 0.09 | -16.14 | -7.0% | $7,608.90 |
| PG | 24 | 45.8% | $-282.51 | 0.26 | -4.90 | -83.5% | $1,397.66 |
| RTX | 5 | 20.0% | $-413.24 | 0.22 | -7.44 | -25.3% | $6,111.59 |
| SHW | 3 | 0.0% | $-1,676.31 | 0.00 | -17.19 | -61.5% | $3,148.87 |
| T | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| TRV | 24 | 37.5% | $-273.27 | 0.27 | -5.04 | -83.1% | $1,619.18 |
| UNH | 17 | 47.1% | $-323.87 | 0.54 | -1.47 | -71.5% | $2,671.93 |
| V | 14 | 28.6% | $-505.90 | 0.14 | -6.60 | -86.6% | $1,095.16 |
| VZ | 28 | 14.3% | $-133.54 | 0.04 | -10.24 | -45.7% | $4,438.80 |
| WMT | 31 | 45.2% | $-95.19 | 0.42 | -2.99 | -36.4% | $5,226.97 |
| XOM | 6 | 16.7% | $-158.93 | 0.23 | -7.65 | -13.4% | $7,224.19 |

D, daily, Dow point-in-time: `C all-out +100% stop -40%` on 25 holdout trades, expectancy $-309.45, profit factor 0.22, Sharpe -6.41, max drawdown -98.2%, ending $139.15. does not clear the old gate

Holdout by symbol, same Dow cell and the Dow sized equity. A zero means that name had no holdout trade.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| AA | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| AAPL | 5 | 20.0% | $-488.76 | 0.39 | -3.10 | -50.8% | $5,431.65 |
| AMGN | 3 | 0.0% | $-1,371.83 | 0.00 | -17.42 | -52.3% | $3,759.94 |
| AMZN | 1 | 0.0% | $-896.44 | 0.00 | -4.42 | -16.2% | $6,978.99 |
| AXP | 3 | 33.3% | $557.68 | 2.00 | 3.14 | -26.9% | $9,548.48 |
| BA | 4 | 0.0% | $-1,552.47 | 0.00 | -3.24 | -82.5% | $1,665.56 |
| BAC | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| CAT | 1 | 100.0% | $4,233.12 | n/a | 46.18 | 0.0% | $12,108.55 |
| CRM | 3 | 0.0% | $-2,008.82 | 0.00 | -6.68 | -76.5% | $1,848.96 |
| CSCO | 3 | 33.3% | $-68.89 | 0.58 | -1.53 | -6.9% | $7,668.77 |
| CVX | 1 | 100.0% | $1,312.02 | n/a | 23.36 | -0.2% | $9,187.45 |
| DD | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| DIS | 10 | 10.0% | $-491.37 | 0.28 | -3.69 | -62.7% | $2,961.70 |
| DOW | 7 | 28.6% | $-22.34 | 0.89 | -0.30 | -13.5% | $7,719.06 |
| GE | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| GS | 2 | 0.0% | $-2,026.74 | 0.00 | -84.89 | -51.5% | $3,821.95 |
| HD | 2 | 0.0% | $-2,059.76 | 0.00 | -5.08 | -53.0% | $3,755.91 |
| HON | 1 | 100.0% | $1,471.44 | n/a | 53.67 | 0.0% | $9,346.87 |
| HPQ | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| IBM | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| INTC | 2 | 0.0% | $-317.41 | 0.00 | -35.57 | -8.1% | $7,240.62 |
| JNJ | 2 | 50.0% | $161.81 | 1.32 | 1.30 | -14.4% | $8,199.04 |
| JPM | 3 | 0.0% | $-1,452.44 | 0.00 | -6.89 | -57.5% | $3,518.11 |
| KO | 8 | 0.0% | $-299.64 | 0.00 | -15.76 | -30.4% | $5,478.31 |
| MCD | 7 | 14.3% | $-853.47 | 0.02 | -4.81 | -76.9% | $1,901.12 |
| MMM | 3 | 0.0% | $-724.91 | 0.00 | -4.91 | -30.1% | $5,700.72 |
| MRK | 1 | 0.0% | $-243.96 | 0.00 | 0.00 | -3.1% | $7,631.47 |
| MSFT | 1 | 0.0% | $-1,550.72 | 0.00 | 0.00 | -19.7% | $6,324.71 |
| NKE | 1 | 0.0% | $-284.61 | 0.00 | 0.00 | -3.6% | $7,590.82 |
| NVDA | 2 | 0.0% | $-1,667.20 | 0.00 | -6.37 | -51.9% | $4,541.03 |
| PFE | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| PG | 2 | 0.0% | $-744.91 | 0.00 | -14.85 | -18.9% | $6,385.62 |
| RTX | 1 | 0.0% | $-746.17 | 0.00 | -23.85 | -9.5% | $7,129.26 |
| SHW | 1 | 0.0% | $-2,915.44 | 0.00 | -6.56 | -44.9% | $4,959.99 |
| T | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| TRV | 1 | 0.0% | $-956.08 | 0.00 | 0.00 | -12.1% | $6,919.35 |
| UNH | 1 | 0.0% | $-1,452.65 | 0.00 | -12.20 | -18.8% | $6,422.78 |
| V | 2 | 50.0% | $312.50 | 1.57 | 2.39 | -18.7% | $8,500.44 |
| VZ | 7 | 0.0% | $-164.58 | 0.00 | -12.45 | -14.6% | $6,723.37 |
| WMT | 4 | 25.0% | $-26.55 | 0.73 | -1.17 | -4.0% | $7,769.23 |
| XOM | 0 | n/a | n/a | n/a | n/a | n/a | n/a |

Pooled cell across the six Dow books, chosen before the holdout: `C all-out +100% stop -40%`. It does not replace a book's cell.

### Liquid list, same Dow cell

Each row uses the Dow book's chosen cell and the liquid list's own training equity at that cell's stop. This is the survivor snapshot. It is not the gate.

Chop-v2 60-minute, liquid list: 61 holdout trades, expectancy $-966.13, profit factor 0.37, Sharpe -2.61, max drawdown -96.6%, ending $2,055.93.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| NVDA | 12 | 16.7% | $-1,117.46 | 0.14 | -7.80 | -26.2% | $47,580.32 |
| AAPL | 10 | 40.0% | $-377.65 | 0.40 | -3.86 | -6.4% | $57,213.34 |
| UNH | 11 | 27.3% | $-947.23 | 0.26 | -6.03 | -17.1% | $50,570.30 |
| MSFT | 13 | 46.2% | $-1,278.89 | 0.28 | -4.96 | -27.3% | $44,364.29 |
| AMZN | 10 | 40.0% | $-340.76 | 0.46 | -2.76 | -10.0% | $57,582.19 |
| META | 14 | 57.1% | $-325.74 | 0.81 | -0.56 | -17.9% | $56,429.48 |
| GOOGL | 16 | 18.8% | $-1,467.12 | 0.09 | -11.49 | -38.5% | $37,515.83 |
| JPM | 11 | 18.2% | $-826.88 | 0.18 | -10.07 | -14.9% | $51,894.09 |
| AMD | 10 | 20.0% | $-3,525.30 | 0.04 | -14.02 | -57.8% | $25,736.81 |
| TSLA | 26 | 38.5% | $-1,338.32 | 0.31 | -4.29 | -64.1% | $26,193.50 |
| AVGO | 16 | 31.2% | $-1,414.85 | 0.18 | -5.40 | -39.8% | $38,352.21 |
| COST | 11 | 27.3% | $-1,585.70 | 0.26 | -6.52 | -29.4% | $43,547.16 |
| V | 10 | 40.0% | $-484.02 | 0.36 | -6.35 | -9.3% | $56,149.66 |
| MA | 5 | 60.0% | $207.97 | 1.27 | 1.38 | -4.3% | $62,029.66 |
| LLY | 9 | 11.1% | $-5,657.85 | 0.09 | -10.54 | -83.5% | $10,069.14 |
| XOM | 5 | 40.0% | $-236.89 | 0.30 | -5.54 | -2.5% | $59,805.38 |
| SPY | 11 | 27.3% | $-768.93 | 0.26 | -6.68 | -13.9% | $52,531.60 |
| QQQ | 11 | 18.2% | $-1,330.51 | 0.18 | -9.73 | -24.0% | $46,354.23 |

Sensitivity, cell chosen on this list's training only: `B stop -30% rungs +40%/+50% runner +150%`. Holdout 67 trades, expectancy $-881.30, Sharpe -2.59, max drawdown -96.8%, ending $1,942.49. Not used for the gate.

Partial bounce, liquid list: 35 holdout trades, expectancy $-222.21, profit factor 0.18, Sharpe -3.63, max drawdown -97.6%, ending $190.96.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| NVDA | 27 | 22.2% | $-228.16 | 0.15 | -4.40 | -77.3% | $1,808.23 |
| AAPL | 19 | 42.1% | $-366.68 | 0.26 | -3.64 | -88.6% | $1,001.55 |
| UNH | 6 | 16.7% | $-996.87 | 0.06 | -11.92 | -77.3% | $1,987.24 |
| MSFT | 9 | 44.4% | $-602.79 | 0.29 | -1.95 | -69.5% | $2,543.34 |
| AMZN | 18 | 44.4% | $-365.97 | 0.33 | -4.47 | -83.3% | $1,381.03 |
| META | 12 | 33.3% | $-327.47 | 0.57 | -1.54 | -55.9% | $4,038.77 |
| GOOGL | 23 | 56.5% | $-254.82 | 0.39 | -1.79 | -75.0% | $2,107.61 |
| JPM | 28 | 42.9% | $-219.25 | 0.42 | -1.60 | -77.3% | $1,829.36 |
| AMD | 19 | 42.1% | $-370.06 | 0.27 | -3.96 | -88.8% | $937.32 |
| TSLA | 10 | 20.0% | $-576.69 | 0.04 | -6.71 | -72.4% | $2,201.54 |
| AVGO | 28 | 50.0% | $-125.65 | 0.67 | -0.76 | -62.9% | $4,450.21 |
| COST | 12 | 58.3% | $-212.26 | 0.64 | 0.65 | -61.4% | $5,421.32 |
| V | 15 | 40.0% | $-473.07 | 0.28 | -4.75 | -90.9% | $872.39 |
| MA | 14 | 57.1% | $-455.56 | 0.53 | -1.92 | -83.8% | $1,590.68 |
| LLY | 13 | 30.8% | $-369.67 | 0.23 | -5.67 | -60.3% | $3,162.72 |
| XOM | 40 | 40.0% | $-158.66 | 0.38 | -2.51 | -85.4% | $1,621.88 |
| SPY | 17 | 52.9% | $-392.16 | 0.56 | -2.30 | -88.8% | $1,301.79 |
| QQQ | 7 | 28.6% | $-802.67 | 0.13 | -5.00 | -70.5% | $2,349.79 |

Sensitivity, cell chosen on this list's training only: `C all-out +100% stop -40%`. Holdout 38 trades, expectancy $-204.33, Sharpe -2.03, max drawdown -97.5%, ending $203.89. Not used for the gate.

A, 60-minute, liquid list: 55 holdout trades, expectancy $-1,392.11, profit factor 0.13, Sharpe -4.22, max drawdown -97.9%, ending $2,051.28.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| NVDA | 16 | 43.8% | $-532.18 | 0.35 | -3.63 | -12.8% | $70,102.73 |
| AAPL | 23 | 34.8% | $-754.54 | 0.23 | -7.23 | -23.0% | $61,263.13 |
| UNH | 21 | 28.6% | $-1,572.17 | 0.13 | -9.99 | -42.6% | $45,602.12 |
| MSFT | 21 | 38.1% | $-1,270.15 | 0.27 | -4.78 | -33.9% | $51,944.53 |
| AMZN | 18 | 22.2% | $-1,019.08 | 0.11 | -7.79 | -23.3% | $60,274.14 |
| META | 11 | 36.4% | $-1,274.45 | 0.48 | -2.39 | -23.3% | $64,598.61 |
| GOOGL | 15 | 26.7% | $-1,077.94 | 0.25 | -7.04 | -21.2% | $62,448.48 |
| JPM | 15 | 40.0% | $-614.39 | 0.27 | -4.53 | -12.3% | $69,401.73 |
| AMD | 18 | 55.6% | $-1,299.13 | 0.45 | -2.32 | -38.7% | $55,233.27 |
| TSLA | 17 | 23.5% | $-2,273.40 | 0.11 | -7.68 | -49.4% | $39,969.72 |
| AVGO | 20 | 25.0% | $-2,149.10 | 0.19 | -5.76 | -54.7% | $35,635.62 |
| COST | 19 | 42.1% | $-1,403.16 | 0.34 | -3.73 | -33.9% | $51,957.55 |
| V | 17 | 41.2% | $-538.28 | 0.24 | -4.07 | -13.4% | $69,466.89 |
| MA | 14 | 28.6% | $-1,658.85 | 0.15 | -9.01 | -30.8% | $55,393.74 |
| LLY | 13 | 7.7% | $-5,476.48 | 0.02 | -6.88 | -90.6% | $7,423.31 |
| XOM | 10 | 60.0% | $-30.34 | 0.89 | -0.36 | -1.9% | $78,314.20 |
| SPY | 17 | 35.3% | $-1,065.38 | 0.20 | -5.77 | -23.0% | $60,506.09 |
| QQQ | 18 | 38.9% | $-651.07 | 0.52 | -2.94 | -14.9% | $66,898.41 |

Sensitivity, cell chosen on this list's training only: `C all-out +100% stop -20%`. Holdout 44 trades, expectancy $-859.27, Sharpe -3.98, max drawdown -96.5%, ending $1,513.24. Not used for the gate.

B, 60-minute, liquid list: 65 holdout trades, expectancy $-1,176.28, profit factor 0.42, Sharpe -2.72, max drawdown -97.9%, ending $1,898.06.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| NVDA | 8 | 50.0% | $-230.52 | 0.74 | -1.00 | -6.6% | $76,512.11 |
| AAPL | 12 | 25.0% | $-235.89 | 0.72 | -1.20 | -12.2% | $75,525.54 |
| UNH | 11 | 27.3% | $-1,022.19 | 0.45 | -4.35 | -15.6% | $67,112.17 |
| MSFT | 9 | 44.4% | $-253.53 | 0.82 | -0.50 | -14.7% | $76,074.46 |
| AMZN | 7 | 14.3% | $-1,543.99 | 0.11 | -7.16 | -16.7% | $67,548.32 |
| META | 8 | 0.0% | $-4,612.06 | 0.00 | -11.77 | -48.1% | $41,459.72 |
| GOOGL | 7 | 14.3% | $-1,467.72 | 0.16 | -7.61 | -15.2% | $68,082.16 |
| JPM | 13 | 30.8% | $-180.27 | 0.80 | -1.04 | -8.4% | $76,012.73 |
| AMD | 11 | 27.3% | $-3,869.30 | 0.18 | -2.68 | -68.3% | $35,793.96 |
| TSLA | 9 | 0.0% | $-3,424.83 | 0.00 | -8.81 | -39.3% | $47,532.73 |
| AVGO | 13 | 38.5% | $-344.97 | 0.86 | -0.24 | -25.4% | $73,871.62 |
| COST | 15 | 26.7% | $-1,471.69 | 0.53 | -2.49 | -35.5% | $56,280.87 |
| V | 13 | 15.4% | $-1,177.57 | 0.16 | -6.66 | -20.1% | $63,047.87 |
| MA | 11 | 18.2% | $-1,809.03 | 0.17 | -6.66 | -26.2% | $58,456.89 |
| LLY | 9 | 0.0% | $-7,570.78 | 0.00 | -12.89 | -87.3% | $10,219.25 |
| XOM | 13 | 7.7% | $-573.38 | 0.14 | -8.75 | -9.5% | $70,902.30 |
| SPY | 14 | 35.7% | $-489.99 | 0.62 | -2.05 | -10.4% | $71,496.37 |
| QQQ | 16 | 37.5% | $-552.95 | 0.70 | -1.08 | -18.8% | $69,508.96 |

Sensitivity, cell chosen on this list's training only: `C all-out +100% stop -30%`. Holdout 73 trades, expectancy $-778.09, Sharpe -1.00, max drawdown -97.2%, ending $1,972.97. Not used for the gate.

C, daily, liquid list: 47 holdout trades, expectancy $-156.03, profit factor 0.39, Sharpe -3.11, max drawdown -98.1%, ending $169.41.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| NVDA | 30 | 36.7% | $-162.84 | 0.33 | -2.43 | -65.2% | $2,617.65 |
| AAPL | 27 | 48.1% | $-210.86 | 0.44 | -3.05 | -80.8% | $1,809.75 |
| UNH | 17 | 47.1% | $-300.32 | 0.56 | -1.08 | -72.4% | $2,397.39 |
| MSFT | 13 | 53.8% | $-451.82 | 0.33 | -4.10 | -79.7% | $1,629.28 |
| AMZN | 26 | 50.0% | $-209.63 | 0.45 | -2.66 | -75.5% | $2,052.62 |
| META | 7 | 14.3% | $-886.63 | 0.05 | -11.08 | -83.6% | $1,296.49 |
| GOOGL | 15 | 13.3% | $-401.02 | 0.06 | -6.44 | -80.2% | $1,487.66 |
| JPM | 25 | 52.0% | $-193.38 | 0.40 | -2.98 | -66.1% | $2,668.29 |
| AMD | 21 | 47.6% | $-238.21 | 0.42 | -1.77 | -73.0% | $2,500.41 |
| TSLA | 11 | 36.4% | $-546.60 | 0.15 | -7.57 | -81.5% | $1,490.25 |
| AVGO | 22 | 45.5% | $-213.06 | 0.36 | -2.35 | -62.5% | $2,815.52 |
| COST | 9 | 44.4% | $-664.62 | 0.29 | -4.28 | -82.9% | $1,521.29 |
| V | 13 | 30.8% | $-487.61 | 0.16 | -6.06 | -84.5% | $1,164.03 |
| MA | 5 | 0.0% | $-1,198.24 | 0.00 | -20.72 | -79.9% | $1,511.70 |
| LLY | 16 | 50.0% | $-255.54 | 0.56 | -1.52 | -59.3% | $3,414.29 |
| XOM | 34 | 41.2% | $-163.49 | 0.36 | -2.67 | -82.3% | $1,944.41 |
| SPY | 10 | 30.0% | $-594.33 | 0.12 | -5.28 | -80.2% | $1,559.62 |
| QQQ | 12 | 33.3% | $-417.10 | 0.20 | -3.34 | -68.4% | $2,497.70 |

Sensitivity, cell chosen on this list's training only: `B stop -40% rungs +25%/+30% runner +100%`. Holdout 46 trades, expectancy $-158.89, Sharpe -2.22, max drawdown -97.8%, ending $194.01. Not used for the gate.

D, daily, liquid list: 14 holdout trades, expectancy $-584.96, profit factor 0.17, Sharpe -7.30, max drawdown -95.1%, ending $419.54.

| Symbol | Trades | Win rate | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|
| NVDA | 5 | 0.0% | $-951.99 | 0.00 | -6.35 | -56.0% | $3,849.00 |
| AAPL | 5 | 20.0% | $-488.76 | 0.39 | -3.38 | -46.4% | $6,165.16 |
| UNH | 2 | 0.0% | $-2,359.37 | 0.00 | -21.64 | -55.0% | $3,890.20 |
| MSFT | 1 | 0.0% | $-1,550.72 | 0.00 | 0.00 | -18.0% | $7,058.21 |
| AMZN | 3 | 0.0% | $-697.18 | 0.00 | -5.17 | -24.3% | $6,517.39 |
| META | 3 | 0.0% | $-2,209.22 | 0.00 | -7.95 | -77.0% | $1,981.28 |
| GOOGL | 2 | 0.0% | $-958.82 | 0.00 | -21.08 | -22.3% | $6,691.29 |
| JPM | 3 | 0.0% | $-1,452.44 | 0.00 | -6.83 | -52.8% | $4,251.61 |
| AMD | 4 | 0.0% | $-782.08 | 0.00 | -23.94 | -36.7% | $5,480.62 |
| TSLA | 1 | 0.0% | $-3,600.51 | 0.00 | 0.00 | -41.8% | $5,008.42 |
| AVGO | 3 | 0.0% | $-249.55 | 0.00 | -34.65 | -8.7% | $7,860.28 |
| COST | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| V | 2 | 50.0% | $312.50 | 1.57 | 2.31 | -17.5% | $9,233.94 |
| MA | 3 | 33.3% | $-124.13 | 0.93 | 2.25 | -35.9% | $8,236.54 |
| LLY | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| XOM | 3 | 33.3% | $-55.03 | 0.84 | -0.29 | -14.7% | $8,443.83 |
| SPY | 3 | 0.0% | $-1,411.08 | 0.00 | -4.98 | -49.8% | $4,375.71 |
| QQQ | 4 | 50.0% | $1,496.22 | 2.38 | 4.10 | -42.8% | $14,593.82 |

Sensitivity, cell chosen on this list's training only: `C all-out +75% stop -40%`. Holdout 14 trades, expectancy $-584.90, Sharpe -8.06, max drawdown -95.1%, ending $420.32. Not used for the gate.

### Wiring

The Dow chop book's cell does not hold up (holdout expectancy is not positive after costs. holdout ending equity is not above the start. holdout Sharpe is not positive. walk-forward pooled expectancy is not positive). The sandbox options sub-book stays the corrected ladder: contracts 1-4 at the -20% stop, runner break-even only after +15%, target +100%. The contract is 14 DTE at the nearest strike. It now scans the liquid list above. The share book stays on the named list. Live trading stays off.

No Dow-gate cell is profitable out of sample after costs. No liquid-list pool is either. No symbol on either list has a positive holdout expectancy on 20 or more trades. The positive symbol rows are 1 to 7 trades and were not used to pick the cell. The earlier ATM section, on the named hourly list and the Dow daily books, is unchanged.

Not added to `config/optional_strategies.json`. The default book is still dual momentum.
<!-- CHART_READS_ATM_UNIVERSE_END -->
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

<!-- CHART_READS_PULLBACK_START -->
## Strong-trend pullback continuation

BACKTESTS ONLY. The rules were written down before this score, in `reports/pullback_rules.json`. Nothing was sent to a broker. The sandbox forward test was not changed, and live trading stays off.

A long needs EMA 9 above EMA 20 above EMA 50, each higher than it was 3 bars ago, the close above the 200 EMA and above VWAP, and either ADX(14) above 25 or a higher-high and higher-low swing. The bar then touches the 9 EMA, the 20 EMA, VWAP, or the previous swing low within 0.25 ATR, closes back at or above that level, and does not trade below the previous swing low. The close is up from the open and up from the prior close. The previous bar was already in that trend and was not itself an entry. Short is the mirror, and it buys a put. The fill is the next bar's open. Intraday VWAP is the session VWAP. Daily VWAP is the 20-session volume-weighted typical price.

The contract is the listed strike nearest the spot, so the model delta is about 0.50. The reported exit is +15% of the entry ask and -30% of that ask, 14 calendar days. Before costs that payoff breaks even at a 66.7% win rate. A limit fills at the limit. A stop that gaps through fills at the open bid. The same bar cannot take the target if it also hits the stop. Spreads are the Black-Scholes haircut and the option fees. +20%/-20%, +15%/-15%, a time stop, and 7 or 30 DTE are sensitivities. They were not used to pick an exit.

The universe is the pre-registered liquid list: NVDA, AAPL, UNH, MSFT, AMZN, META, GOOGL, JPM, AMD, TSLA, AVGO, COST, V, MA, LLY, XOM, SPY, QQQ. The verdict is the point-in-time Dow gate on the signal day. Names that were never in the Dow stay in the liquid table and cannot pass the gate. The $1,000 book buys two contracts when the debit fits in $1,000, otherwise one, and it skips a larger debit. The sized book is one contract at the training median equity that puts the -30% loss near 2% of the account. The share control uses the same entries, a stop at the swing, a 1.5R target, and the clock's time stop.

### Daily

Window train 2010-01-01 through 2018-12-31, holdout 2019-01-01 through 2026-10-06. 3967 liquid signals, 1169 after the Dow gate, 3967 priced at 14 DTE.

Daily, $1,000, 14 DTE, +15%/-30%: realized win rate 35.7% against an after-cost break-even of 66.3%. The win rate does not clear that rate. The before-cost break-even is 66.7%. On the holdout it is not profitable ($-32.16 expectancy, ending $99.64 from $1,000.00, 28 trades).

Daily, sized at $1,280.80, one contract: realized win rate 36.2% against an after-cost break-even of 68.0%. The win rate does not clear that rate. The before-cost break-even is 66.7%. On the holdout it is not profitable ($-25.51 expectancy, ending $81.70 from $1,280.80, 47 trades).

Daily shares, $1,000, swing stop and 1.5R: realized win rate 49.5% against an after-cost break-even of 50.3%. The win rate does not clear that rate. The before-cost break-even is 40.0%. On the holdout it is not profitable ($-0.12 expectancy, ending $976.29 from $1,000.00, 204 trades).

| Book | Trades | Win rate | After-cost BE | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| $1,000 train, +15%/-30% | 43 | 14.0% | 56.7% | $-22.91 | 0.12 | -13.74 | -98.5% | $14.66 |
| $1,000 holdout, +15%/-30% | 28 | 35.7% | 66.3% | $-32.16 | 0.28 | -6.71 | -90.9% | $99.64 |
| sized holdout, +15%/-30% | 47 | 36.2% | 68.0% | $-25.51 | 0.27 | -6.04 | -94.1% | $81.70 |
| liquid list holdout, not the gate | 39 | 28.2% | 54.5% | $-25.39 | 0.33 | -11.14 | -99.1% | $9.97 |
| random entries, same exit | 24 | 37.5% | 75.3% | $-39.77 | 0.20 | -6.93 | -95.5% | $45.42 |
| +20%/-20% | 25 | 12.0% | 40.4% | $-36.74 | 0.20 | -14.62 | -92.8% | $81.47 |
| +15%/-15% | 24 | 4.2% | 61.3% | $-38.69 | 0.03 | -25.00 | -92.9% | $71.42 |
| time stop 5 bars, stop -30% | 21 | 9.5% | 31.2% | $-44.07 | 0.23 | -2.54 | -94.0% | $74.46 |
| 7 DTE, +15%/-30% | 28 | 28.6% | 59.2% | $-33.77 | 0.28 | -7.80 | -95.2% | $54.40 |
| 30 DTE, +15%/-30% | 19 | 31.6% | 65.9% | $-47.28 | 0.24 | -7.05 | -91.1% | $101.64 |
| shares train | 238 | 52.1% | 54.8% | $-0.31 | 0.90 | -0.48 | -17.7% | $927.32 |
| shares holdout | 204 | 49.5% | 50.3% | $-0.12 | 0.97 | -0.11 | -14.6% | $976.29 |
| shares, random entries | 255 | 51.4% | 51.1% | $0.06 | 1.01 | 0.17 | -27.7% | $1,015.08 |

Walk-forward inside the training span, frozen +15%/-30% rule, no re-selection: 101 trades, pooled expectancy $-28.97.

Holdout by symbol on the $1,000 Dow-gated option book. A zero means that name had no holdout trade.

| Symbol | Trades | Win rate | Expectancy | Sum of P&L |
|---|---:|---:|---:|---:|
| NVDA | 0 | n/a | n/a | n/a |
| AAPL | 5 | 20.0% | $-40.86 | $-204.28 |
| UNH | 2 | 50.0% | $-48.40 | $-96.80 |
| MSFT | 4 | 50.0% | $-29.83 | $-119.33 |
| AMZN | 0 | n/a | n/a | n/a |
| META | 0 | n/a | n/a | n/a |
| GOOGL | 0 | n/a | n/a | n/a |
| JPM | 3 | 66.7% | $3.62 | $10.87 |
| AMD | 0 | n/a | n/a | n/a |
| TSLA | 0 | n/a | n/a | n/a |
| AVGO | 0 | n/a | n/a | n/a |
| COST | 0 | n/a | n/a | n/a |
| V | 4 | 25.0% | $-55.65 | $-222.61 |
| MA | 0 | n/a | n/a | n/a |
| LLY | 0 | n/a | n/a | n/a |
| XOM | 10 | 30.0% | $-26.82 | $-268.22 |
| SPY | 0 | n/a | n/a | n/a |
| QQQ | 0 | n/a | n/a | n/a |

Median model delta on the trades that filled: 0.49. Skipped 519, PDT blocked 2, overlapped 8. Exit reasons: {'target': 10, 'stop': 18}.

### 60-minute

Window train 2024-10-17 through 2025-10-10, holdout 2025-10-13 through 2026-10-06. 3671 liquid signals, 1429 after the Dow gate, 3671 priced at 14 DTE.

60-minute, $1,000, 14 DTE, +15%/-30%: realized win rate 30.0% against an after-cost break-even of 71.4%. The win rate does not clear that rate. The before-cost break-even is 66.7%. On the holdout it is not profitable ($-77.89 expectancy, ending $221.15 from $1,000.00, 10 trades).

60-minute, sized at $9,365.35, one contract: realized win rate 31.9% against an after-cost break-even of 68.6%. The win rate does not clear that rate. The before-cost break-even is 66.7%. On the holdout it is not profitable ($-130.45 expectancy, ending $364.22 from $9,365.35, 69 trades).

60-minute shares, $1,000, swing stop and 1.5R: realized win rate 43.6% against an after-cost break-even of 53.5%. The win rate does not clear that rate. The before-cost break-even is 40.0%. On the holdout it is not profitable ($-1.20 expectancy, ending $801.20 from $1,000.00, 165 trades).

| Book | Trades | Win rate | After-cost BE | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| $1,000 train, +15%/-30% | 12 | 33.3% | 64.5% | $-66.51 | 0.27 | -16.91 | -79.8% | $201.88 |
| $1,000 holdout, +15%/-30% | 10 | 30.0% | 71.4% | $-77.89 | 0.17 | -18.73 | -77.9% | $221.15 |
| sized holdout, +15%/-30% | 69 | 31.9% | 68.6% | $-130.45 | 0.21 | -7.01 | -96.1% | $364.22 |
| liquid list holdout, not the gate | 10 | 20.0% | 63.7% | $-85.82 | 0.14 | -13.51 | -85.8% | $141.81 |
| random entries, same exit | 13 | 46.2% | 66.1% | $-56.19 | 0.44 | -7.40 | -79.8% | $269.58 |
| +20%/-20% | 14 | 28.6% | 55.3% | $-48.88 | 0.32 | -10.61 | -73.3% | $315.66 |
| +15%/-15% | 14 | 7.1% | 44.2% | $-56.75 | 0.10 | -38.72 | -79.5% | $205.49 |
| time stop 8 bars, stop -30% | 22 | 27.3% | 33.6% | $-29.40 | 0.74 | 0.82 | -74.5% | $353.15 |
| 7 DTE, +15%/-30% | 16 | 37.5% | 62.4% | $-53.76 | 0.36 | -9.38 | -86.0% | $139.86 |
| 30 DTE, +15%/-30% | 6 | 33.3% | 70.3% | $-109.74 | 0.21 | -9.91 | -69.5% | $341.56 |
| shares train | 154 | 49.4% | 49.6% | $-0.03 | 0.99 | 0.01 | -8.1% | $995.31 |
| shares holdout | 165 | 43.6% | 53.5% | $-1.20 | 0.67 | -2.15 | -22.7% | $801.20 |
| shares, random entries | 181 | 43.6% | 51.9% | $-1.23 | 0.72 | -1.81 | -29.3% | $776.58 |

Walk-forward inside the training span, frozen +15%/-30% rule, no re-selection: 41 trades, pooled expectancy $-45.55.

Holdout by symbol on the $1,000 Dow-gated option book. A zero means that name had no holdout trade.

| Symbol | Trades | Win rate | Expectancy | Sum of P&L |
|---|---:|---:|---:|---:|
| NVDA | 0 | n/a | n/a | n/a |
| AAPL | 6 | 33.3% | $-52.68 | $-316.09 |
| UNH | 0 | n/a | n/a | n/a |
| MSFT | 0 | n/a | n/a | n/a |
| AMZN | 3 | 33.3% | $-87.47 | $-262.40 |
| META | 0 | n/a | n/a | n/a |
| GOOGL | 0 | n/a | n/a | n/a |
| JPM | 0 | n/a | n/a | n/a |
| AMD | 0 | n/a | n/a | n/a |
| TSLA | 0 | n/a | n/a | n/a |
| AVGO | 0 | n/a | n/a | n/a |
| COST | 0 | n/a | n/a | n/a |
| V | 1 | 0.0% | $-200.36 | $-200.36 |
| MA | 0 | n/a | n/a | n/a |
| LLY | 0 | n/a | n/a | n/a |
| XOM | 0 | n/a | n/a | n/a |
| SPY | 0 | n/a | n/a | n/a |
| QQQ | 0 | n/a | n/a | n/a |

Median model delta on the trades that filled: 0.49. Skipped 644, PDT blocked 4, overlapped 16. Exit reasons: {'target': 3, 'stop': 7}.

### 15-minute

Window train 2026-08-13 through 2026-09-09, holdout 2026-09-10 through 2026-10-06. 992 liquid signals, 425 after the Dow gate, 992 priced at 14 DTE.

15-minute, $1,000, 14 DTE, +15%/-30%: realized win rate 25.0% against an after-cost break-even of 74.0%. The win rate does not clear that rate. The before-cost break-even is 66.7%. On the holdout it is not profitable ($-140.82 expectancy, ending $436.74 from $1,000.00, 4 trades).

15-minute, sized at $11,901.91, one contract: realized win rate 41.2% against an after-cost break-even of 74.3%. The win rate does not clear that rate. The before-cost break-even is 66.7%. On the holdout it is not profitable ($-125.11 expectancy, ending $9,774.97 from $11,901.91, 17 trades).

15-minute shares, $1,000, swing stop and 1.5R: realized win rate 21.4% against an after-cost break-even of 68.5%. The win rate does not clear that rate. The before-cost break-even is 40.0%. On the holdout it is not profitable ($-2.99 expectancy, ending $958.19 from $1,000.00, 14 trades).

| Book | Trades | Win rate | After-cost BE | Expectancy | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| $1,000 train, +15%/-30% | 3 | 33.3% | 78.7% | $-195.94 | 0.14 | -9.54 | -62.3% | $412.19 |
| $1,000 holdout, +15%/-30% | 4 | 25.0% | 74.0% | $-140.82 | 0.12 | -34.33 | -56.3% | $436.74 |
| sized holdout, +15%/-30% | 17 | 41.2% | 74.3% | $-125.11 | 0.24 | -9.13 | -17.9% | $9,774.97 |
| liquid list holdout, not the gate | 9 | 44.4% | 74.4% | $-80.35 | 0.28 | -11.01 | -72.3% | $276.84 |
| random entries, same exit | 6 | 33.3% | 68.7% | $-107.32 | 0.23 | -18.82 | -64.4% | $356.07 |
| +20%/-20% | 8 | 25.0% | 55.0% | $-71.69 | 0.27 | -8.38 | -60.6% | $426.46 |
| +15%/-15% | 6 | 0.0% | 100.0% | $-96.42 | 0.00 | -48.52 | -57.9% | $421.45 |
| time stop 16 bars, stop -30% | 14 | 35.7% | 45.8% | $-26.59 | 0.66 | -3.69 | -52.6% | $627.72 |
| 7 DTE, +15%/-30% | 4 | 0.0% | 100.0% | $-179.24 | 0.00 | -32.50 | -71.7% | $283.03 |
| 30 DTE, +15%/-30% | 3 | 33.3% | 69.8% | $-129.69 | 0.22 | -24.36 | -38.9% | $610.93 |
| shares train | 9 | 33.3% | 57.4% | $-1.68 | 0.37 | -6.48 | -2.0% | $984.88 |
| shares holdout | 14 | 21.4% | 68.5% | $-2.99 | 0.13 | -12.74 | -4.2% | $958.19 |
| shares, random entries | 15 | 20.0% | 69.7% | $-5.55 | 0.11 | -13.37 | -8.5% | $916.69 |

Walk-forward inside the training span, frozen +15%/-30% rule, no re-selection: 10 trades, pooled expectancy $-109.26.

Holdout by symbol on the $1,000 Dow-gated option book. A zero means that name had no holdout trade.

| Symbol | Trades | Win rate | Expectancy | Sum of P&L |
|---|---:|---:|---:|---:|
| NVDA | 1 | 0.0% | $-318.72 | $-318.72 |
| AAPL | 0 | n/a | n/a | n/a |
| UNH | 0 | n/a | n/a | n/a |
| MSFT | 0 | n/a | n/a | n/a |
| AMZN | 0 | n/a | n/a | n/a |
| META | 0 | n/a | n/a | n/a |
| GOOGL | 1 | 0.0% | $-177.96 | $-177.96 |
| JPM | 2 | 50.0% | $-33.29 | $-66.58 |
| AMD | 0 | n/a | n/a | n/a |
| TSLA | 0 | n/a | n/a | n/a |
| AVGO | 0 | n/a | n/a | n/a |
| COST | 0 | n/a | n/a | n/a |
| V | 0 | n/a | n/a | n/a |
| MA | 0 | n/a | n/a | n/a |
| LLY | 0 | n/a | n/a | n/a |
| XOM | 0 | n/a | n/a | n/a |
| SPY | 0 | n/a | n/a | n/a |
| QQQ | 0 | n/a | n/a | n/a |

Median model delta on the trades that filled: 0.49. Skipped 157, PDT blocked 49, overlapped 32. Exit reasons: {'stop': 3, 'target': 1}.

### Verdict

Daily: realized win rate 35.7% against an after-cost break-even of 66.3%. The win rate does not clear that rate. The before-cost break-even is 66.7%. On the holdout it is not profitable ($-32.16 expectancy, ending $99.64 from $1,000.00, 28 trades).

60-minute: realized win rate 30.0% against an after-cost break-even of 71.4%. The win rate does not clear that rate. The before-cost break-even is 66.7%. On the holdout it is not profitable ($-77.89 expectancy, ending $221.15 from $1,000.00, 10 trades).

15-minute: realized win rate 25.0% against an after-cost break-even of 74.0%. The win rate does not clear that rate. The before-cost break-even is 66.7%. On the holdout it is not profitable ($-140.82 expectancy, ending $436.74 from $1,000.00, 4 trades).

Holdout rows above the starting equity: Daily random shares, $1,015.08 on 255 trades. A random-entry row is the baseline. It was not used to change the rule.

No sensitivity was promoted after the score. No cell was wired into the sandbox, and the forward-test code was left as it is. Not added to `config/optional_strategies.json`. The default book is still dual momentum.

Charts, most recent long and short the detector marked, not chosen for P&L: `reports/setups/pullback_long_60m.png`, `reports/setups/pullback_short_60m.png`.

SPY buy and hold over 2019-01-01 through 2026-10-06, $1,000 whole shares: 4 shares, ending $3,242.23, Sharpe 0.95, max drawdown -30.7%.
<!-- CHART_READS_PULLBACK_END -->

<!-- CHART_READS_ORB5_START -->
## First-candle opening range, 09:30-09:35

Backtests only. The rule was frozen before the score. Nothing was sent to a broker. The sandbox forward test was not changed, and live trading stays off.

The opening range is only the first regular-session candle. On the 5-minute chart that is the 09:30 bar, covering 09:30-09:35 ET. The rest of the open does not move the high or the low. A long is the first later 5-minute close above that high. A short is the first close below that low. The fill is the next bar's open. One signal per symbol per session. The confirming-candle variant and the retest-and-hold variant are reported below and were not used to pick an entry.

The primary share stop is the other side of that candle. The midpoint is a sensitivity. The primary share target is 1R, then the session close if neither side has traded. 2R and a session-close exit with no R target are sensitivities. The primary option is the listed strike nearest the spot, 0 DTE, at +15% and -30% of premium. Before costs that needs a 66.7% win rate. 1 DTE, 7 DTE, and the five-contract ladder (2 at +15%, 1 at +20%, 1 at +30%, runner at +100%, initial stop -30%) are sensitivities. The $1,000 book is capped at the legacy pattern-day-trader count, 3 day trades in 5 sessions, because the account is under $25,000 and these dates sit in the 2026-2027 phase-in. Blocked entries are counted and not filled.

Yahoo's 5-minute file runs 2026-08-13 through 2026-10-06, 38 sessions. The loader's cap is 55 calendar days, so this is a short sample. It is not a durable edge and it is under 300 trades. The holdout is the second half of those sessions. The rule was not refit on it.

Chart Fanatics spec 7 was a different opening-range breakout. Its default used a 5-minute range on NQ and ES, a volume filter, an ATR band on the range, a midpoint stop, a 2R target, and a flat by 11:30. The gated proxy row was 7 trades, win rate 0.0%, average R -10.403, and the verdict was inconclusive. This study does not use those filters and it does not replace that row. The hourly opening-range breakout already in the strategy library uses the first hour, not this candle.

### Oct 6, 2026, and the recent sessions

2026-10-01 (5m): first-candle high $765.26, low $763.39. after that candle the session traded $765.65 to $758.79 and closed $764.02. Primary signal: short. Chart: `reports/setups/orb5_spy_2026-10-01.png`.
2026-10-02 (5m): first-candle high $770.84, low $769.49. after that candle the session traded $772.65 to $767.15 and closed $769.67. Primary signal: long. Chart: `reports/setups/orb5_spy_2026-10-02.png`.
2026-10-05 (5m): first-candle high $770.93, low $769.63. after that candle the session traded $776.60 to $769.98 and closed $774.94. Primary signal: long. Chart: `reports/setups/orb5_spy_2026-10-05.png`.
2026-10-06 (5m): first-candle high $778.73, low $777.97. after that candle the session traded $781.62 to $777.96 and closed $779.14. Primary signal: long. Chart: `reports/setups/orb5_spy_2026-10-06.png`.
2026-10-06 (1m): first-candle high $778.73, low $777.97. after that candle the session traded $781.62 to $777.96 and closed $779.14. Primary signal: long. Chart: `reports/setups/orb5_spy_2026-10-06_1m.png`.

### 1-minute check

The 1-minute high and low from 09:30 through 09:34 match the 5-minute 09:30 bar on 4 of 4 overlapping sessions, within two cents. The 1-minute window is about a week. A score on it is anecdotal and is not the verdict.

| Date | 5m high | 5m low | 1m high | 1m low | Match |
|---|---:|---:|---:|---:|---|
| 2026-10-01 | $765.26 | $763.39 | $765.26 | $763.39 | yes |
| 2026-10-02 | $770.84 | $769.49 | $770.84 | $769.49 | yes |
| 2026-10-05 | $770.93 | $769.63 | $770.93 | $769.63 | yes |
| 2026-10-06 | $778.73 | $777.97 | $778.73 | $777.97 | yes |

1-minute SPY, same primary share rule, the whole short window: 3 trades, win 33.3%, after-cost break-even 88.5%, expectancy $-2.14, profit factor 0.07, Sharpe -18.42, max drawdown -0.7%, ending $993.58, PDT blocked 1.
1-minute SPY, 0 DTE +15%/-30%, the whole short window: 3 trades, win 0.0%, after-cost break-even 100.0%, expectancy $-66.96, profit factor 0.00, Sharpe -488.77, max drawdown -20.1%, ending $799.11, PDT blocked 1.

### SPY holdout, 2026-09-10 through 2026-10-06

The verdict is the first row of each table. The other rows were frozen before the score and were not promoted.

| Book | Trades | Win rate | After-cost BE | Expectancy | PF | Sharpe | Max DD | Ending | PDT blocked |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| shares, opposite stop, 1R | 12 | 33.3% | 69.3% | $-1.35 | 0.22 | -9.57 | -1.8% | $983.78 | 7 |
| shares, midpoint stop, 1R | 12 | 16.7% | 68.5% | $-1.42 | 0.09 | -16.37 | -1.8% | $983.00 | 7 |
| shares, opposite stop, 2R | 12 | 33.3% | 65.0% | $-1.70 | 0.27 | -9.68 | -2.5% | $979.59 | 7 |
| shares, opposite stop, session close | 12 | 16.7% | 38.9% | $-1.88 | 0.31 | -8.71 | -2.5% | $977.42 | 7 |
| shares, confirming candle, 1R | 12 | 33.3% | 69.3% | $-1.35 | 0.22 | -9.57 | -1.8% | $983.78 | 7 |
| shares, retest, 1R | 12 | 41.7% | 78.1% | $-1.38 | 0.20 | -9.95 | -1.7% | $983.38 | 4 |
| shares, random entries, 1R | 11 | 9.1% | 81.9% | $-2.34 | 0.02 | -29.77 | -2.6% | $974.21 | 6 |

| Option book | Trades | Win rate | After-cost BE | Expectancy | PF | Sharpe | Max DD | Ending | PDT blocked |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 DTE, +15%/-30%, $1,000 | 12 | 16.7% | 72.2% | $-48.67 | 0.08 | -22.60 | -58.4% | $415.92 | 7 |
| 1 DTE, +15%/-30%, $1,000 | 12 | 33.3% | 66.9% | $-56.14 | 0.25 | -9.23 | -70.7% | $326.36 | 7 |
| 7 DTE, +15%/-30%, $1,000 | 13 | 69.2% | 68.9% | $0.79 | 1.01 | 1.04 | -28.0% | $1,010.33 | 5 |
| 0 DTE, five-contract ladder, $1,000 | 5 | 40.0% | 86.4% | $-125.18 | 0.11 | -12.51 | -62.6% | $374.12 | 1 |
| 0 DTE, +15%/-30%, sized | 12 | 16.7% | 72.2% | $-24.34 | 0.08 | -23.51 | -16.5% | $1,483.55 | 7 |
| 0 DTE, random entries, +15%/-30% | 11 | 0.0% | 100.0% | $-42.71 | 0.00 | -34.07 | -47.0% | $530.23 | 8 |

SPY shares: realized win rate 33.3% against an after-cost break-even of 69.3%. The win rate does not clear that rate. The before-cost break-even is 50.0%. It is not profitable out of sample ($-1.35 expectancy, ending $983.78 from $1,000.00, 12 trades). PDT blocked 7.

SPY 0 DTE options: realized win rate 16.7% against an after-cost break-even of 72.2%. The win rate does not clear that rate. The before-cost break-even is 66.7%. It is not profitable out of sample ($-48.67 expectancy, ending $415.92 from $1,000.00, 12 trades). PDT blocked 7.

SPY 7 DTE, a sensitivity: realized win rate 69.2% against an after-cost break-even of 68.9%. The win rate clears that rate. The before-cost break-even is 66.7%. It is profitable out of sample ($0.79 expectancy, ending $1,010.33 from $1,000.00, 13 trades). PDT blocked 5.
That row was frozen before the score as a sensitivity. It was not promoted. 13 trades in a 38-session file is not a durable edge.

The sized 0 DTE book: realized win rate 16.7% against an after-cost break-even of 72.2%. The win rate does not clear that rate. The before-cost break-even is 66.7%. It is not profitable out of sample ($-24.34 expectancy, ending $1,483.55 from $1,775.65, 12 trades). PDT blocked 7.
Its starting equity is the training median, not $1,000.

The five-contract ladder skipped 13 holdout signals because five contracts did not fit in $1,000. The ladder: realized win rate 40.0% against an after-cost break-even of 86.4%. The win rate does not clear that rate. It is not profitable out of sample ($-125.18 expectancy, ending $374.12 from $1,000.00, 5 trades). PDT blocked 1.

SPY had a primary signal on 38 of 38 sessions. The first candle is narrow, so a later close leaves it on most days in this file. The confirming-candle variant marked 38 SPY signals, against 38 plain closes.

Training, 2026-08-13 through 2026-09-09, same primary rules: shares 12 trades, win 50.0%, after-cost break-even 75.8%, expectancy $-0.98, profit factor 0.32, Sharpe -7.18, max drawdown -1.5%, ending $988.20, PDT blocked 7. 0 DTE 12 trades, win 33.3%, after-cost break-even 68.1%, expectancy $-36.95, profit factor 0.23, Sharpe -9.92, max drawdown -50.2%, ending $556.61, PDT blocked 7.

Walk-forward inside training, frozen rule, no re-selection: 9 share trades, pooled expectancy $-1.51.

Sized 0 DTE equity, frozen from the training median that puts the -30% loss near 2% of the account: $1,775.65.

SPY buy and hold over the holdout, $1,000 whole shares: 1 share, ending $1,023.59, Sharpe 4.13, max drawdown -1.1%.

### QQQ and the liquid list

These rows are secondary. They were not used to change the SPY rule.

QQQ shares: 12 trades, win 58.3%, after-cost break-even 68.4%, expectancy $-0.63, profit factor 0.65, Sharpe -3.06, max drawdown -1.1%, ending $992.49, PDT blocked 7.

QQQ 0 DTE, +15%/-30%: 12 trades, win 50.0%, after-cost break-even 66.7%, expectancy $-21.35, profit factor 0.50, Sharpe -4.40, max drawdown -30.2%, ending $743.83, PDT blocked 7.

Liquid list, one account, primary entry, shares: 12 trades, win 33.3%, after-cost break-even 44.4%, expectancy $-1.63, profit factor 0.63, Sharpe -3.49, max drawdown -2.3%, ending $980.45, PDT blocked 140.

Liquid list, one account, 0 DTE, +15%/-30%: 12 trades, win 41.7%, after-cost break-even 52.3%, expectancy $-13.96, profit factor 0.65, Sharpe -3.95, max drawdown -18.5%, ending $832.50, PDT blocked 290.

Signals on the full 5-minute file, primary entry: SPY 38, QQQ 38, liquid list 674. Confirming candle 38. Retest 30.

No sensitivity was promoted after the score. The strategy was not added to `config/optional_strategies.json`. The default book is still dual momentum.

```
python3 -m webull_bot.chart_reads.research_orb5
```
<!-- CHART_READS_ORB5_END -->

<!-- CHART_READS_ORB_MWF_START -->
## Monday, Wednesday, and Friday opening range

Backtests only. This rule replaces the earlier first-candle test as the pre-registered default. It was frozen before the score. Nothing was sent to a broker. The sandbox forward test was not changed, and live trading stays off. The earlier first-candle numbers are a different rule and stay as scored.

The range is only the 09:30-09:35 ET candle. A long break of that high buys the at-the-money 0 DTE call. A short break of that low buys the at-the-money 0 DTE put. The break is the first later bar that trades through the level. A print equal to the level is not a break. One trade a day. The default fill prices the underlying at the level plus stock slippage, then buys the option at the ask. A bar that opens through the level fills at that open. The next bar's open is a sensitivity.

The book trades Monday, Wednesday, and Friday only, and it skips CPI, the Employment Situation, and FOMC decision days. The dates are the real release day or the statement day. Friday SPY expirations were already listed before 2016. Wednesday expirations start August 31, 2016. Monday expirations start February 26, 2018. Tuesday and Thursday expirations start in November 2022 and are not traded. There is no stop. A call is a win at +100% of the entry ask or whatever the 15:30 bid is worth. A put is a win at +50% of the entry ask or whatever the 15:30 bid is worth. That bid can be near zero. Risk is the full premium, sized at $100 on a $1,000 cash account. One contract that costs more than $100 is skipped. $200 and $500 are sensitivities. No adds and no rolls.

There is no historical option chain. Prices are Black-Scholes with minutes left until 16:00 ET. Implied volatility is the prior session's VIX1D close when that print exists, otherwise the prior VIX close. The half-spread is the greater of one cent and 1.5% of the mid. The model is the main source of uncertainty. A 1.3x volatility multiple is a sensitivity, not a new rule. An earlier score of this same study used a -50% stop. That stop is not this rule, and those dollars are not reused.

The sample is Dukascopy's public SPYUSUSD bid 1-minute candles, no account, from 2017-02-17 through 2026-10-06, 1431 sessions with a bar. Prices are bids, about a penny under the consolidated mid, and they are unadjusted. SPY did not split in this window. Dukascopy volume is unused. Tuesday and Thursday were not downloaded, except 2026-10-06 for the chart. Yahoo's 5-minute opening high and low on 23 overlapping sessions differed by a median of $0.0240. The pre-registered gate is $0.05, and this file passed, so the default break is the first 1-minute bar through the 09:30-09:35 range. Yahoo returned no 5-minute SPY bars for January 2026. No Alpaca, Polygon, or other intraday key is in this environment, and a paid archive was not bought. A 60-minute bar does not contain the 09:30-09:35 high and low, so it was not used. The shared holiday list treats Juneteenth as closed in every year, so 2019-06-19 and 2020-06-19 are missing even though the NYSE was open. 2019-06-19 was also an FOMC statement day. Session marks: {"break": 1138, "no_0dte": 45, "event": 234, "both_sides": 4, "no_range": 9, "weekday": 1}. Skipped releases inside the file: {"NFP": 107, "CPI+FOMC": 6, "FOMC": 67, "CPI": 54}. The dates are the 2017-2026 calendar. No regular-session bars on 2018-12-05. December 5, 2018 was a national day of mourning and the NYSE was closed.

Cash account, $100 risk, fill at the level: 43 trades, win rate 39.5%, calls at +100% 31.6% of 19, puts at +50% 37.5% of 24, 15:30 on 65.1%, average value $0.08 (21.4% of the entry ask), expectancy $-23.15, profit factor 0.48, Sharpe -1.03, max drawdown -99.6%, longest losing streak 10, ending $4.65. Premium skips 1095. Settlement skips 0. PDT blocked 0.

Before costs, a call that doubles against a worthless miss needs a 50% win rate, and a put that gains 50% against a worthless miss needs a 66.7% win rate. A 15:30 exit still has whatever bid the model gives it, so it is not automatically a total loss. After the spread and the fees, the realized wins and losses in this sample need 57.8%. The realized win rate is 39.5%.

The win rate does not clear that rate. The default book is not profitable on this sample.

28 of 43 default trades reached 15:30. Their average bid was $0.08, 21.4% of the entry ask.

The same signals at $200 risk: 36 trades, win rate 47.2%, calls at +100% 35.3% of 17, puts at +50% 47.4% of 19, 15:30 on 58.3%, average value $0.10 (25.9% of the entry ask), expectancy $-27.49, profit factor 0.67, Sharpe -0.38, max drawdown -99.2%, longest losing streak 3, ending $10.46. Premium skips 1102. Settlement skips 0. PDT blocked 0.

The $200 book is a sensitivity. It does not replace the $100 cash rule.

The same signals at $500 risk: 12 trades, win rate 41.7%, calls at +100% 28.6% of 7, puts at +50% 20.0% of 5, 15:30 on 75.0%, average value $0.17 (42.7% of the entry ask), expectancy $-82.93, profit factor 0.53, Sharpe -0.29, max drawdown -99.7%, longest losing streak 3, ending $4.79. Premium skips 1126. Settlement skips 0. PDT blocked 0.

Next-bar open, $100, cash: 48 trades, win rate 41.7%, calls at +100% 34.8% of 23, puts at +50% 40.0% of 25, 15:30 on 62.5%, average value $0.08 (20.2% of the entry ask), expectancy $-20.73, profit factor 0.50, Sharpe -0.53, max drawdown -99.5%, longest losing streak 7, ending $5.15. Premium skips 1090. Settlement skips 0. PDT blocked 0.

Volatility at 1.3 times the prior close, $100, cash: 37 trades, win rate 32.4%, calls at +100% 16.7% of 18, puts at +50% 36.8% of 19, 15:30 on 73.0%, average value $0.14 (30.3% of the entry ask), expectancy $-26.76, profit factor 0.37, Sharpe -0.93, max drawdown -99.1%, longest losing streak 7, ending $9.95. Premium skips 1101. Settlement skips 0. PDT blocked 0. That row was not promoted.

The same ticks aggregated to 5-minute bars, cash, $100: 44 trades, win rate 43.2%, calls at +100% 38.1% of 21, puts at +50% 39.1% of 23, 15:30 on 61.4%, average value $0.07 (17.4% of the entry ask), expectancy $-22.62, profit factor 0.49, Sharpe -0.55, max drawdown -99.6%, longest losing streak 10, ending $4.91. Premium skips 1025. Settlement skips 0. PDT blocked 0. That aggregation is a sensitivity, not the verdict.

A $1,000 account is under the $2,000 minimum to use margin, so the default is cash and the pattern-day-trader rule does not apply. Sale proceeds settle the next session. The same signals on a hypothetical margin account under $25,000: 43 trades, win rate 39.5%, calls at +100% 31.6% of 19, puts at +50% 37.5% of 24, 15:30 on 65.1%, average value $0.08 (21.4% of the entry ask), expectancy $-23.15, profit factor 0.48, Sharpe -1.03, max drawdown -99.6%, longest losing streak 10, ending $4.65. Premium skips 1095. Settlement skips 0. PDT blocked 0. Three Monday/Wednesday/Friday trades fit in five business days. A fourth appears only when a Tuesday or Thursday holiday pulls another one of those weekdays into the window. This file blocked no margin trades. Once the cash account was below the cost of one contract, later signals were premium skips, so a holiday week did not add a fourth trade to the counter.

Random call-or-put at the same break, seed 17, same exits: 51 trades, win rate 39.2%, calls at +100% 23.1% of 26, puts at +50% 52.0% of 25, 15:30 on 62.7%, average value $0.09 (22.5% of the entry ask), expectancy $-19.38, profit factor 0.51, Sharpe -1.03, max drawdown -98.9%, longest losing streak 10, ending $11.52. Premium skips 1087. Settlement skips 0. PDT blocked 0.

First half of the break days, replayed from a fresh $1,000: 43 trades, win rate 39.5%, calls at +100% 31.6% of 19, puts at +50% 37.5% of 24, 15:30 on 65.1%, average value $0.08 (21.4% of the entry ask), expectancy $-23.15, profit factor 0.48, Sharpe -1.43, max drawdown -99.6%, longest losing streak 10, ending $4.65. Premium skips 526. Settlement skips 0. PDT blocked 0. The full sample took no further trades after this half. The account was already below the cost of one contract, so the later signals are premium skips in the full book.

Second half of the break days, also from a fresh $1,000 and not from the equity left after the first half: 359 trades, win rate 61.6%, calls at +100% 52.3% of 199, puts at +50% 68.1% of 160, 15:30 on 40.1%, average value $0.08 (9.4% of the entry ask), expectancy $7.41, profit factor 1.27, Sharpe 1.60, max drawdown -26.5%, longest losing streak 5, ending $3,659.51. Premium skips 210. Settlement skips 0. PDT blocked 0. That half's after-cost break-even is 55.8% and its win rate is 61.6%. That half was not used to change the rule. A second-half row that finishes above $1,000 was not promoted.

SPY buy and hold, 4 shares from the first open to the last close of the scored file, ended at $3,178.79.

Overlap check: 23 sessions, median absolute difference $0.0240 on the 09:30-09:35 high and the low. Gate $0.05. Passed.

Charts, examples only: 2026-10-06 5m high 778.72 low 777.94, no trade, after that candle 777.94-781.61, close 779.27; 2026-10-05 5m high 770.92 low 769.65, break traded, after that candle 769.97-776.60, close 774.61; 2026-10-02 5m high 770.80 low 769.46, no trade, NFP, after that candle 767.13-772.64, close 769.60; 2026-09-30 5m high 767.27 low 766.22, break traded, after that candle 762.40-769.40, close 762.47; 2026-09-25 5m high 769.51 low 767.74, break traded, after that candle 766.27-772.27, close 771.31; 2026-10-06 1m high 778.72 low 777.94, no trade, after that candle 777.94-781.61, close 779.27.

Not added to `config/optional_strategies.json`. The default book is still dual momentum.

```
python3 -m webull_bot.chart_reads.research_orb_mwf
```
<!-- CHART_READS_ORB_MWF_END -->

<!-- ACCOUNT_WINNERS_START -->
## Three account-sized books

Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox forward test was not changed. The three rules were frozen before this score. A neighbor that looks better was not promoted.

The account is $1,000 or $5,000. Shares are fractional, which these ETFs need at recent prices. The default is a cash account: the signal is the month-end close, the sale is the next session's open, and the buy is the session after that, because the sale has not settled. Cash earns zero, which is harsh in years when Treasury bills paid interest. Costs are the Webull stock schedule already in this repo: no commission, the SEC fee and FINRA TAF on sells, and 5 bps of slippage plus 1 bp of half-spread on each fill. Taxes are ignored. A monthly book realizes short-term gains. A buy-and-hold of SPY defers them, so a taxable account would look worse for the active books than these tables do. The pattern-day-trader rule does not come up. These are monthly swings, and the cash book does not buy and sell the same name on the same day.

The list is SPY, EFA, IEF, GLD, QQQ, IWM, EEM, TLT, BIL, and TQQQ. They are the funds that still exist. A fund is not held before Yahoo has a price for it. This is not a stock scan and it is not a point-in-time membership file. Prices are Yahoo's adjusted daily bars, so dividends are in the result and splits are taken out.

A book beats SPY, on the holdout that starts 2017-01-01, only when training also made money and either its Sharpe and Calmar are both higher than SPY, or its CAGR is within three points of SPY and its max drawdown is at least ten points milder. The high-risk book is also compared with buying and holding TQQQ. Beating that fund on Sharpe and drawdown does not, by itself, make it the book to fund ahead of SPY.

### Rules

Conservative. Equal slice of SPY, EFA, IEF, and GLD once each has a 10-month average. Hold that slice when the month-end close is strictly above the average, else cash. A fund that is not listed yet is not in that month's count. It rebalances monthly. On the full sample it changed a sleeve about 3.6 times per year and turned over 1.9 times equity per year.

Moderate. SPY, QQQ, IWM, EFA, EEM, TLT, GLD. Hold the one with the best 12-1 month return if its full 12-month return is strictly above BIL's 12-month return. Otherwise cash. Before BIL has 12 months the hurdle is zero. No trailing stop. It changed holdings about 3.2 times per year and turned over 6.3 times equity per year. This is the published monthly process. The bot's dual momentum is the same idea with a 21-session lookback, a 20 percent trail, and a position that risks 0.75 percent of equity.

High risk. Hold TQQQ when its month-end close is strictly above its 10-month average, else cash. The same filter on QQQ is a labeled unlevered check, not the pick. It changed state about 0.8 times per year and turned over 1.3 times equity per year. TQQQ resets its leverage every day, so a choppy tape can grind the fund down while the filter still says to hold it.

### Full sample, $1,000

Each book starts the day of its first fill on or after 2005-01-01. SPY and QQQ on that row are bought on the book's own first day, so the rows do not share one start. The common window is the overlap.

| Book | CAGR | Max DD | Sharpe | Calmar | Positive months | Ending | Entries |
|---|---:|---:|---:|---:|---:|---:|---:|
| conservative | 6.2% | -11.2% | 0.83 | 0.55 | 61.6% | $3,670 | 79 |
| SPY, same dates as conservative | 10.9% | -55.2% | 0.64 | 0.20 | 66.2% | $9,516 | — |
| QQQ, same dates as conservative | 15.3% | -53.4% | 0.77 | 0.29 | 60.8% | $22,275 | — |
| moderate | 9.0% | -39.8% | 0.51 | 0.23 | 54.0% | $6,492 | 70 |
| SPY, same dates as moderate | 10.9% | -55.2% | 0.64 | 0.20 | 66.2% | $9,516 | — |
| QQQ, same dates as moderate | 15.3% | -53.4% | 0.77 | 0.29 | 60.8% | $22,275 | — |
| high_risk | 22.8% | -69.9% | 0.67 | 0.33 | 51.0% | $26,022 | 13 |
| SPY, same dates as high_risk | 14.5% | -33.7% | 0.89 | 0.43 | 68.8% | $8,579 | — |
| QQQ, same dates as high_risk | 19.3% | -35.1% | 0.96 | 0.55 | 63.0% | $16,463 | — |
| SPY, EFA, IEF, GLD, always on | 8.3% | -30.1% | 0.79 | 0.27 | 62.0% | $5,646 | 4 |
| TQQQ buy and hold, high-risk dates | 41.8% | -81.7% | 0.88 | 0.51 | 60.4% | $252,990 | 1 |
| QQQ with the same 10-month filter | 11.0% | -28.6% | 0.71 | 0.38 | 52.9% | $9,651 | 21 |

### Common window, growth of $1,000

All three books and SPY, rebased to $1,000 on 2010-12-01. This is the chart. It does not include 2008, because TQQQ was not listed yet.

| Book | CAGR | Max DD | Sharpe | Calmar | Positive months | Ending |
|---|---:|---:|---:|---:|---:|---:|
| Conservative | 5.1% | -10.5% | 0.74 | 0.48 | 62.0% | $2,193 |
| Moderate | 7.8% | -37.6% | 0.48 | 0.21 | 50.0% | $3,268 |
| High risk | 22.7% | -69.9% | 0.67 | 0.32 | 51.0% | $25,604 |
| SPY | 14.5% | -33.7% | 0.88 | 0.43 | 68.8% | $8,526 |

### Holdout from 2017-01-01, fresh $1,000

This is the verdict window. Training, through 2016-12-31, is the check that the same rule had already made money. Neither window was used to change a lookback.

| Book | CAGR | Max DD | Sharpe | Calmar | Positive months | Ending | Entries |
|---|---:|---:|---:|---:|---:|---:|---:|
| conservative holdout | 6.9% | -10.5% | 0.96 | 0.66 | 65.3% | $1,925 | 40 |
| SPY, holdout, conservative window | 15.3% | -33.7% | 0.88 | 0.46 | 69.5% | $4,028 | — |
| moderate holdout | 8.4% | -37.6% | 0.49 | 0.22 | 50.0% | $2,192 | 30 |
| SPY, holdout, moderate window | 15.3% | -33.7% | 0.88 | 0.46 | 69.5% | $4,028 | — |
| high_risk holdout | 25.6% | -69.9% | 0.70 | 0.37 | 51.7% | $9,255 | 8 |
| SPY, holdout, high_risk window | 15.3% | -33.7% | 0.88 | 0.46 | 69.5% | $4,028 | — |
| TQQQ buy and hold, holdout | 43.0% | -81.7% | 0.87 | 0.53 | 61.0% | $32,854 | 1 |
| static four-fund mix, holdout | 10.1% | -19.8% | 1.00 | 0.51 | 65.3% | $2,568 | 4 |

Training, fresh $1,000, first fill through 2016-12-31.

| Book | CAGR | Max DD | Sharpe | Calmar | Positive months | Ending | Years |
|---|---:|---:|---:|---:|---:|---:|---:|
| conservative | 5.5% | -11.2% | 0.72 | 0.49 | 58.6% | $1,903 | 12.0 |
| SPY, conservative train | 7.4% | -55.2% | 0.46 | 0.13 | 63.4% | $2,345 | 12.0 |
| moderate | 9.5% | -39.8% | 0.52 | 0.24 | 57.2% | $2,953 | 12.0 |
| SPY, moderate train | 7.4% | -55.2% | 0.46 | 0.13 | 63.4% | $2,345 | 12.0 |
| high_risk | 18.1% | -59.4% | 0.61 | 0.31 | 50.0% | $2,758 | 6.1 |
| SPY, high_risk train | 13.1% | -18.6% | 0.90 | 0.70 | 67.6% | $2,114 | 6.1 |

### Rolling windows

Each window starts at a month-end with the stake and ends 6 or 12 months later. The dollar figure is what that stake is worth, not a profit subtracted from it. SPY on the same dates pays the entry and exit friction. The $5,000 figure is the same return on a $5,000 stake. A paired $5,000 run of the conservative book matched the $1,000 CAGR. The fee gap was under one basis point.

**conservative.** 2005-01-03 through 2026-10-06.

6-month windows: 257. Median ending $1,031 (SPY $1,064), bad case $973 (SPY $934), good case $1,097 (SPY $1,165). 28.4% of the book's windows lost money, against 20.6% for SPY.

On $5,000: 6-month windows: 257. Median ending $5,156 (SPY $5,320), bad case $4,863 (SPY $4,671), good case $5,487 (SPY $5,827). 28.4% of the book's windows lost money, against 20.6% for SPY.


12-month windows: 251. Median ending $1,065 (SPY $1,147), bad case $971 (SPY $930), good case $1,165 (SPY $1,295). 21.5% of the book's windows lost money, against 16.3% for SPY.

On $5,000: 12-month windows: 251. Median ending $5,326 (SPY $5,733), bad case $4,855 (SPY $4,650), good case $5,824 (SPY $6,473). 21.5% of the book's windows lost money, against 16.3% for SPY.

**moderate.** 2005-01-03 through 2026-10-06.

6-month windows: 257. Median ending $1,057 (SPY $1,064), bad case $865 (SPY $934), good case $1,230 (SPY $1,165). 37.0% of the book's windows lost money, against 20.6% for SPY.

On $5,000: 6-month windows: 257. Median ending $5,287 (SPY $5,320), bad case $4,324 (SPY $4,671), good case $6,152 (SPY $5,827). 37.0% of the book's windows lost money, against 20.6% for SPY.


12-month windows: 251. Median ending $1,083 (SPY $1,147), bad case $867 (SPY $930), good case $1,405 (SPY $1,295). 37.8% of the book's windows lost money, against 16.3% for SPY.

On $5,000: 12-month windows: 251. Median ending $5,414 (SPY $5,733), bad case $4,335 (SPY $4,650), good case $7,026 (SPY $6,473). 37.8% of the book's windows lost money, against 16.3% for SPY.

**high_risk.** 2010-12-01 through 2026-10-06.

6-month windows: 186. Median ending $1,144 (SPY $1,078), bad case $757 (SPY $968), good case $1,489 (SPY $1,162). 31.2% of the book's windows lost money, against 17.2% for SPY.

On $5,000: 6-month windows: 186. Median ending $5,720 (SPY $5,391), bad case $3,787 (SPY $4,838), good case $7,445 (SPY $5,810). 31.2% of the book's windows lost money, against 17.2% for SPY.


12-month windows: 180. Median ending $1,195 (SPY $1,158), bad case $749 (SPY $994), good case $1,992 (SPY $1,298). 31.1% of the book's windows lost money, against 10.6% for SPY.

On $5,000: 12-month windows: 180. Median ending $5,975 (SPY $5,792), bad case $3,745 (SPY $4,969), good case $9,960 (SPY $6,490). 31.1% of the book's windows lost money, against 10.6% for SPY.

### Stress years

Calendar-year total return. A blank means the book was not running.

| Book | 2008 | 2020 | 2022 |
|---|---:|---:|---:|
| conservative | 3.6% | 12.9% | -8.7% |
| moderate | -11.9% | 5.0% | -13.9% |
| high_risk | n/a | 11.5% | -25.0% |
| spy_long | -36.8% | 18.3% | -18.2% |
| static | -15.7% | 16.4% | -11.9% |
| qqq_filter | -20.4% | 27.7% | -8.5% |

### Folds of the frozen rule

Each fold starts over at $1,000. A fold is too short to pick a rule. It shows whether one stretch carried the holdout.

| Book | Fold | CAGR | Max DD | Sharpe | Ending |
|---|---|---:|---:|---:|---:|
| conservative | 2017-2018 | 3.8% | -8.2% | 0.76 | $1,078 |
| conservative | 2019-2020 | 11.1% | -7.1% | 1.53 | $1,233 |
| conservative | 2021-2022 | -2.7% | -10.3% | -0.44 | $948 |
| conservative | 2023-2026 | 11.7% | -9.0% | 1.29 | $1,517 |
| moderate | 2017-2018 | 1.7% | -28.4% | 0.18 | $1,034 |
| moderate | 2019-2020 | 5.1% | -28.6% | 0.32 | $1,105 |
| moderate | 2021-2022 | -5.2% | -20.5% | -0.21 | $900 |
| moderate | 2023-2026 | 22.9% | -27.9% | 1.10 | $2,168 |
| high_risk | 2017-2018 | 56.3% | -35.0% | 1.23 | $2,435 |
| high_risk | 2019-2020 | 12.3% | -69.9% | 0.54 | $1,261 |
| high_risk | 2021-2022 | 16.5% | -41.8% | 0.57 | $1,355 |
| high_risk | 2023-2026 | 23.3% | -43.4% | 0.68 | $2,197 |

### Checks that were not allowed to change the rule

Random timing keeps each month's weights and shuffles the dates, seed 17. The static mix holds the four conservative funds in equal slices whenever they have a 10-month average, with no trend test. The 8-month and 12-month averages, and the other dual-momentum lookbacks, are neighbors.

| Check | CAGR | Max DD | Sharpe | Ending |
|---|---:|---:|---:|---:|
| conservative 8-month holdout | 8.6% | -9.0% | 1.20 | $2,239 |
| high risk 8-month holdout | 24.7% | -69.9% | 0.69 | $8,588 |
| conservative 12-month holdout | 6.8% | -9.7% | 0.94 | $1,897 |
| high risk 12-month holdout | 32.3% | -69.9% | 0.80 | $15,342 |
| moderate 9-1 holdout | 11.3% | -31.3% | 0.63 | $2,833 |
| moderate 6-1 holdout | 8.8% | -28.6% | 0.52 | $2,283 |
| moderate 12-0 holdout | 10.1% | -34.9% | 0.58 | $2,548 |
| conservative shuffled dates, full sample | 5.5% | -22.2% | 0.63 | $3,231 |
| conservative shuffled dates, holdout | 4.6% | -22.2% | 0.57 | $1,552 |
| moderate shuffled dates, full sample | 9.5% | -44.8% | 0.55 | $7,178 |
| moderate shuffled dates, holdout | 9.8% | -38.5% | 0.60 | $2,486 |
| high_risk shuffled dates, full sample | 47.5% | -69.9% | 1.00 | $475,453 |
| high_risk shuffled dates, holdout | 50.3% | -69.9% | 0.99 | $53,181 |
| conservative cash in BIL, full sample | 6.4% | -11.2% | 0.86 | $3,892 |
| conservative margin same-day buy, holdout | 6.9% | -10.5% | 0.96 | $1,925 |
| moderate cash in BIL, full sample | 9.1% | -39.8% | 0.51 | $6,658 |
| moderate margin same-day buy, holdout | 9.4% | -33.7% | 0.54 | $2,399 |
| high_risk cash in BIL, full sample | 23.2% | -69.9% | 0.68 | $27,383 |
| high_risk margin same-day buy, holdout | 25.6% | -69.9% | 0.70 | $9,255 |

### Wired bot

The default book in this repo is dual momentum. On a $100,000 test from 2017 it finished at $104,429.23 because the sizer risks 0.75 percent of equity against a 20 percent stop, so about 3.75 percent of the account is invested, and a 20 percent trail can knock the position out between month-ends. That is not the fully invested moderate book above. This study did not change the sizer, the trail, or the strategy list. $1,000 whole shares, 2017-2026: 1 trades, CAGR 0.0%, max drawdown -0.5%, Sharpe 0.14, ending $1,002. Rejections: {'position size rounded to zero': 104}. $5,000 whole shares, 2017-2026: 19 trades, CAGR 0.0%, max drawdown -0.9%, Sharpe 0.11, ending $5,018. Rejections: {'position size rounded to zero': 60}. $1,000 fractional, same 0.75% risk, 2017-2026: 30 trades, CAGR 0.5%, max drawdown -2.0%, Sharpe 0.55, ending $1,046. Rejections: none. $5,000 fractional, same 0.75% risk, 2017-2026: 30 trades, CAGR 0.5%, max drawdown -2.0%, Sharpe 0.55, ending $5,231. Rejections: none.

### Verdict

QQQ buy and hold finished the holdout at $6,791. SPY finished at $4,028. The conservative and moderate books finished behind both. The high-risk filter finished at $9,255, ahead of SPY and QQQ on raw dollars and behind raw TQQQ at $32,854. Raw TQQQ's max drawdown was -81.7% and its Sharpe was 0.87. The filter's drawdown was -69.9% and its Sharpe was 0.70. It did not clear a higher Sharpe and a milder drawdown than raw TQQQ. One shuffle of its invested months, seed 17, finished the holdout far ahead of the filter. That is one draw, and it does not show that the filter's timing was special. A book that has already fallen about 70 percent is not the one I would fund with $1,000. The moderate book finished at $2,192. Its holdout drawdown was -37.6% against SPY's -33.7%, and its Sharpe was 0.49 against 0.88. Training had beaten SPY. The holdout did not. Shuffling its monthly choices, seed 17, finished the holdout ahead of the real timing. The other lookbacks also finished below SPY and were not promoted. The bot already runs dual momentum, but not this fully invested version. At the bot's 0.75 percent risk, the $1,000 fractional account and the $5,000 fractional account are the wired-bot rows above. Whole shares on $1,000 were usually too small to send. The conservative book is the only pick that cleared the frozen test against SPY: Sharpe 0.96 against 0.88, Calmar 0.66 against 0.46, after a training window that also made money. It did not beat SPY on dollars. The holdout ended at $1,925 against SPY's $4,028 and QQQ's $6,791. Positive months were 65.3%, below SPY's 69.5%. Of its 12-month windows, 21.5% lost money, against 16.3% for SPY. The bad 12-month case turned $1,000 into $971, against $930 for SPY. The median case was $1,065 against SPY's $1,147. In 2008 the sleeve made money while SPY did not. In 2022 it lost less than SPY. The same four funds, held all the time, finished the holdout at $2,568, Sharpe 1.00, max drawdown -19.8%. The filter's Sharpe was lower than that mix, and so was its ending stake. What the filter added was the smaller drawdown. The 8-month neighbor made more on the holdout and was not used. Shuffling the filter's own months, seed 17, had a deeper drawdown and a lower Sharpe than the real timing. If the goal is more dollars and a 30 percent decline is acceptable, own SPY or QQQ. QQQ made more than SPY. If the goal is a smaller crash and slow growth is acceptable, the conservative 10-month sleeve is the one of these three I would fund. It is not in the bot. I would not fund the moderate book or the TQQQ filter for this account. A $5,000 stake is five times the $1,000 result. This is a simulation, not a forecast.

Chart: `reports/account_winners_equity.png`.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum, at the bot's existing size. Live trading stays off.

```
python3 -m webull_bot.research_account_winners
```
<!-- ACCOUNT_WINNERS_END -->

<!-- ACCOUNT_HUNT_START -->
## Second search for a small-account book

Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox forward test was not changed. The rules were frozen before this score. A neighbor that looks better was not promoted. The earlier 10-month sleeve, the fully invested dual-momentum book, and the monthly TQQQ filter keep the numbers already published.

Cash earns zero. A cash account sells at the next open and buys the session after that. Costs are the Webull stock schedule. Taxes are ignored, so a monthly or daily book that realizes short-term gains looks better here than it would in a taxable account. Fractional shares. The pattern-day-trader rule does not come up, because these are overnight holds and the cash book does not round-trip the same name the same day.

Post-earnings drift was skipped. The free Yahoo earnings calendar for AAPL starts 2014-07-22, which does not cover a training window back through 2008. A short recent list would be a different study.

Stock momentum uses the point-in-time Dow (42 names had Yahoo prices). Missing Yahoo history, so those membership dates cannot be held: DWDP, KFT, UTX, WBA. That hole can hide a name that was removed and then stopped trading. It is not a survivor list, and it is not the S&P 100. A free point-in-time S&P 100 file was not in this repo. The current-member Dow book is the survivor diagnostic in the checks table. The gap between that diagnostic and the point-in-time book is the haircut estimate. It was not applied as a new return.

The risk-sized Connors RSI(2) book already published on ETFs had a Sharpe of 0.07 and a walk-forward Sharpe of -0.09. The risk-sized sector rotation had a Sharpe of 0.06. Those books use the 0.75 percent sizer and a hard stop. The books below are fully invested versions of different rules. They do not replace those rows.

### Holdout from 2017-01-01, fresh $1,000

SPY and QQQ on each row are bought on that book's own holdout dates. A yes under SPY risk means the frozen test: profitable training, and either a higher holdout Sharpe and Calmar than SPY, or a CAGR within three points of SPY with a drawdown at least ten points milder. Rows marked $5,000 are the option books. One contract does not fit the story of a $1,000 account, so those rows, and the SPY and QQQ numbers beside them, start at $5,000.

| Book | CAGR | Max DD | Sharpe | Positive months | Ending | SPY ending | QQQ ending | Beats SPY risk | Beats SPY raw |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| rsi2_equal | 1.0% | -22.2% | 0.15 | 51.7% | $1,105 | $4,028 | $6,791 | no | no |
| ibs_equal | 1.2% | -26.5% | 0.16 | 54.2% | $1,127 | $4,028 | $6,791 | no | no |
| three_down | 1.0% | -29.0% | 0.14 | 55.9% | $1,105 | $4,028 | $6,791 | no | no |
| rsi2_qqq_overlay | 8.2% | -31.6% | 0.51 | 55.9% | $2,148 | $4,028 | $6,791 | no | no |
| tqqq_sma200 | 27.6% | -57.8% | 0.76 | 42.4% | $10,774 | $4,028 | $6,791 | no | yes |
| tqqq_band3 | 32.7% | -62.1% | 0.84 | 42.4% | $15,806 | $4,028 | $6,791 | no | yes |
| tqqq_vol20 | 30.3% | -50.5% | 0.83 | 47.5% | $13,192 | $4,028 | $6,791 | no | yes |
| tqqq_half | 18.6% | -40.3% | 0.71 | 42.4% | $5,304 | $4,028 | $6,791 | no | yes |
| qqq_tqqq_blend | 22.2% | -44.5% | 0.75 | 43.2% | $7,062 | $4,028 | $6,791 | no | yes |
| upro_sma200 | 16.6% | -50.0% | 0.63 | 43.2% | $4,467 | $4,028 | $6,791 | no | yes |
| spy_vol15_weekly | 9.7% | -21.5% | 0.79 | 56.8% | $2,469 | $4,028 | $6,791 | no | no |
| qqq_vol15_weekly | 14.1% | -22.5% | 0.96 | 60.2% | $3,627 | $4,028 | $6,791 | yes | no |
| spy_vol15_weekly_sma | 7.9% | -16.1% | 0.77 | 50.8% | $2,103 | $4,028 | $6,791 | no | no |
| qqq_vol15_weekly_sma | 13.2% | -17.0% | 0.99 | 55.1% | $3,358 | $4,028 | $6,791 | yes | no |
| sector_top3_12m | 14.5% | -30.2% | 0.86 | 66.1% | $3,756 | $4,028 | $6,791 | no | no |
| dow_mom_top5 | 5.1% | -26.8% | 0.38 | 50.8% | $1,621 | $4,028 | $6,791 | no | no |
| spy_tom | 2.9% | -11.2% | 0.40 | 63.6% | $1,317 | $4,028 | $6,791 | no | no |
| spy_pre_holiday | -1.0% | -10.2% | -0.33 | 32.2% | $910 | $4,028 | $6,791 | no | no |
| spy_calendar_both | 2.4% | -14.3% | 0.33 | 57.6% | $1,259 | $4,028 | $6,791 | no | no |
| spy_calendar_blend | 8.9% | -15.4% | 0.81 | 61.9% | $2,303 | $4,028 | $6,791 | no | no |
| qqq_tom | 3.3% | -14.8% | 0.38 | 56.8% | $1,376 | $4,028 | $6,791 | no | no |
| qqq_pre_holiday | -1.4% | -15.9% | -0.36 | 34.7% | $870 | $4,028 | $6,791 | no | no |
| qqq_calendar_both | 2.8% | -19.3% | 0.31 | 57.6% | $1,305 | $4,028 | $6,791 | no | no |
| qqq_calendar_blend | 12.2% | -23.8% | 0.87 | 62.7% | $3,077 | $4,028 | $6,791 | no | no |
| wheel_f ($5,000) | 0.5% | -13.2% | 0.14 | 64.4% | $5,260 | $20,139 | $33,957 | no | no |
| covered_f ($5,000) | 0.6% | -17.1% | 0.14 | 59.3% | $5,305 | $20,139 | $33,957 | no | no |
| gtaa_10m | 6.9% | -10.5% | 0.96 | 65.3% | $1,925 | $4,028 | $6,791 | yes | no |
| dual_invested | 8.4% | -37.6% | 0.49 | 50.0% | $2,192 | $4,028 | $6,791 | no | no |
| tqqq_monthly | 25.6% | -69.9% | 0.70 | 51.7% | $9,255 | $4,028 | $6,791 | no | yes |

### What each frozen book does

**rsi2_equal.** Equal-weight the liquid ETFs whose RSI(2) is below 10 and whose close is above the 200-day average. Exit a name when its close is above the 5-day average. Otherwise cash. About 105.1 new positions a year and 88.3 rebalances a year. Full-sample CAGR 1.6%, max drawdown -22.2%, Sharpe 0.20, positive months 51.3%, ending $1,404.

**ibs_equal.** Equal-weight the liquid ETFs whose internal bar strength is below 0.2 and whose close is above the 200-day average. Exit when IBS is above 0.8. Otherwise cash. About 270.0 new positions a year and 168.3 rebalances a year. Full-sample CAGR 2.8%, max drawdown -26.5%, Sharpe 0.30, positive months 55.1%, ending $1,837.

**three_down.** Equal-weight the liquid ETFs with three lower closes in a row and a close above the 200-day average. Exit when the close is above the 5-day average. Otherwise cash. About 105.8 new positions a year and 94.1 rebalances a year. Full-sample CAGR 1.4%, max drawdown -29.0%, Sharpe 0.18, positive months 54.8%, ending $1,359.

**rsi2_qqq_overlay.** Hold the RSI(2) sleeve when any of those ETFs is on. Otherwise hold QQQ. About 117.8 new positions a year and 87.8 rebalances a year. Full-sample CAGR 5.7%, max drawdown -51.0%, Sharpe 0.39, positive months 55.1%, ending $3,317.

**tqqq_sma200.** Hold TQQQ when QQQ's close is above its 200-day average. Otherwise cash. Checked every day. About 3.1 new positions a year and 6.1 rebalances a year. Full-sample CAGR 28.7%, max drawdown -59.8%, Sharpe 0.77, positive months 55.4%, ending $66,903.

**tqqq_band3.** Hold TQQQ only after QQQ closes 3 percent above its 200-day average. Exit only after a close 3 percent below it. About 0.8 new positions a year and 1.6 rebalances a year. Full-sample CAGR 30.9%, max drawdown -62.1%, Sharpe 0.81, positive months 54.5%, ending $88,116.

**tqqq_vol20.** Hold TQQQ only while QQQ is above its 200-day average, and scale the weight to min(1, 0.20 / 20-day realized vol). About 3.1 new positions a year and 51.9 rebalances a year. Full-sample CAGR 30.7%, max drawdown -59.1%, Sharpe 0.84, positive months 55.9%, ending $85,975.

**tqqq_half.** Hold 50 percent TQQQ when QQQ is above its 200-day average. The rest is cash. About 3.1 new positions a year and 6.1 rebalances a year. Full-sample CAGR 19.4%, max drawdown -45.1%, Sharpe 0.72, positive months 55.4%, ending $19,041.

**qqq_tqqq_blend.** Hold 50 percent QQQ and 50 percent TQQQ when QQQ is above its 200-day average. Otherwise cash. About 6.1 new positions a year and 6.1 rebalances a year. Full-sample CAGR 22.8%, max drawdown -48.9%, Sharpe 0.76, positive months 55.9%, ending $30,387.

**upro_sma200.** Hold UPRO when SPY's close is above its 200-day average. Otherwise cash. About 2.7 new positions a year and 5.3 rebalances a year. Full-sample CAGR 22.0%, max drawdown -58.2%, Sharpe 0.73, positive months 58.1%, ending $31,026.

**spy_vol15_weekly.** Hold SPY at min(1, 0.15 / 20-day realized vol). Rebalance weekly. No leverage. About 0.0 new positions a year and 22.3 rebalances a year. Full-sample CAGR 9.8%, max drawdown -35.9%, Sharpe 0.77, positive months 65.6%, ending $7,389.

**qqq_vol15_weekly.** Hold QQQ at min(1, 0.15 / 20-day realized vol). Rebalance weekly. No leverage. About 0.0 new positions a year and 33.1 rebalances a year. Full-sample CAGR 12.7%, max drawdown -31.5%, Sharpe 0.89, positive months 61.2%, ending $13,455.

**spy_vol15_weekly_sma.** The weekly 15 percent SPY vol target, and only while SPY is above its 200-day average. About 1.6 new positions a year and 14.0 rebalances a year. Full-sample CAGR 7.4%, max drawdown -19.1%, Sharpe 0.71, positive months 56.2%, ending $4,625.

**qqq_vol15_weekly_sma.** The weekly 15 percent QQQ vol target, and only while QQQ is above its 200-day average. About 1.5 new positions a year and 25.1 rebalances a year. Full-sample CAGR 9.7%, max drawdown -22.2%, Sharpe 0.78, positive months 55.1%, ending $7,452.

**sector_top3_12m.** Each month give one third to each of the three sector SPDRs with the best 12-month return, and only if that return is positive. About 7.7 new positions a year and 7.0 rebalances a year. Full-sample CAGR 9.7%, max drawdown -30.2%, Sharpe 0.64, positive months 59.7%, ending $7,569.

**dow_mom_top5.** Each month hold the top 5 point-in-time Dow names by 12-1 month return, and only while SPY is above its 200-day average. About 18.1 new positions a year and 9.8 rebalances a year. Full-sample CAGR 6.4%, max drawdown -26.8%, Sharpe 0.46, positive months 51.2%, ending $2,926.

**spy_tom.** Hold SPY on the last session of the month and the first three sessions. Otherwise cash. About 12.0 new positions a year and 24.0 rebalances a year. Full-sample CAGR 0.8%, max drawdown -24.9%, Sharpe 0.14, positive months 55.9%, ending $1,178.

**spy_pre_holiday.** Hold SPY on the session before an NYSE weekday holiday. Otherwise cash. About 9.1 new positions a year and 18.2 rebalances a year. Full-sample CAGR -0.5%, max drawdown -15.3%, Sharpe -0.15, positive months 32.7%, ending $890.

**spy_calendar_both.** Hold SPY when either the turn-of-month window or the pre-holiday session is on. Otherwise cash. About 17.2 new positions a year and 34.3 rebalances a year. Full-sample CAGR 0.8%, max drawdown -27.8%, Sharpe 0.14, positive months 53.2%, ending $1,186.

**spy_calendar_blend.** Keep half in SPY all the time. Add the other half only in the combined calendar window. About 0.0 new positions a year and 34.4 rebalances a year. Full-sample CAGR 6.0%, max drawdown -42.2%, Sharpe 0.56, positive months 62.4%, ending $3,584.

**qqq_tom.** Hold QQQ on the last session of the month and the first three sessions. Otherwise cash. About 12.0 new positions a year and 24.0 rebalances a year. Full-sample CAGR 1.3%, max drawdown -28.9%, Sharpe 0.19, positive months 55.5%, ending $1,325.

**qqq_pre_holiday.** Hold QQQ on the session before an NYSE weekday holiday. Otherwise cash. About 9.1 new positions a year and 18.2 rebalances a year. Full-sample CAGR -0.5%, max drawdown -16.4%, Sharpe -0.12, positive months 36.1%, ending $890.

**qqq_calendar_both.** Hold QQQ when either the turn-of-month window or the pre-holiday session is on. Otherwise cash. About 17.2 new positions a year and 34.3 rebalances a year. Full-sample CAGR 1.4%, max drawdown -29.4%, Sharpe 0.19, positive months 54.4%, ending $1,347.

**qqq_calendar_blend.** Keep half in QQQ all the time. Add the other half only in the combined calendar window. About 0.0 new positions a year and 34.4 rebalances a year. Full-sample CAGR 8.6%, max drawdown -39.2%, Sharpe 0.67, positive months 60.5%, ending $6,022.

**wheel_f.** On F, sell one 30-day 0.30-delta cash-secured put. If assigned, sell a 0.30-delta covered call until the shares are called away. Black-Scholes, not a chain. Opened 261 option cycles. Assigned 37. Called away 36. Skipped 0 cycles when the cash was short of the strike or the credit did not cover the fee. Full-sample CAGR 0.3%, max drawdown -12.9%, Sharpe 0.11, positive months 62.4%, ending $5,371.

**covered_f.** Buy 100 shares of F when they fit, and sell a 30-day 0.30-delta call against them. Opened 261 option cycles. Assigned 0. Called away 65. Skipped 0 cycles when the cash was short of the strike or the credit did not cover the fee. Full-sample CAGR 0.3%, max drawdown -17.1%, Sharpe 0.09, positive months 56.3%, ending $5,323.

### Rolling windows versus SPY and QQQ

Each window starts at a month-end. The dollar figure is what the stake is worth at the end. SPY and QQQ pay entry and exit friction. The $5,000 figure is the same return on a $5,000 stake. For the wheel and the covered call, the $1,000 lines scale that $5,000 path. One contract does not scale that way. The separate $1,000 wheel is in the checks table.

**rsi2_equal.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,006 (SPY $1,064), bad case $939 (SPY $934), good case $1,086 (SPY $1,165). 45.9% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,006 (QQQ $1,099), bad case $939 (QQQ $939), good case $1,086 (QQQ $1,214). 45.9% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,031 (SPY $5,320), bad case $4,695 (SPY $4,671), good case $5,429 (SPY $5,827). 45.9% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,031 (QQQ $5,495), bad case $4,695 (QQQ $4,695), good case $5,429 (QQQ $6,068). 45.9% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,017 (SPY $1,147), bad case $907 (SPY $930), good case $1,141 (SPY $1,295). 45.0% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,017 (QQQ $1,194), bad case $907 (QQQ $945), good case $1,141 (QQQ $1,387). 45.0% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,084 (SPY $5,733), bad case $4,537 (SPY $4,650), good case $5,705 (SPY $6,473). 45.0% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,084 (QQQ $5,972), bad case $4,537 (QQQ $4,727), good case $5,705 (QQQ $6,934). 45.0% lost money, against 13.5% for QQQ.

**ibs_equal.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,015 (SPY $1,064), bad case $929 (SPY $934), good case $1,091 (SPY $1,165). 38.5% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,015 (QQQ $1,099), bad case $929 (QQQ $939), good case $1,091 (QQQ $1,214). 38.5% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,073 (SPY $5,320), bad case $4,645 (SPY $4,671), good case $5,456 (SPY $5,827). 38.5% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,073 (QQQ $5,495), bad case $4,645 (QQQ $4,695), good case $5,456 (QQQ $6,068). 38.5% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,033 (SPY $1,147), bad case $917 (SPY $930), good case $1,137 (SPY $1,295). 37.8% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,033 (QQQ $1,194), bad case $917 (QQQ $945), good case $1,137 (QQQ $1,387). 37.8% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,165 (SPY $5,733), bad case $4,584 (SPY $4,650), good case $5,683 (SPY $6,473). 37.8% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,165 (QQQ $5,972), bad case $4,584 (QQQ $4,727), good case $5,683 (QQQ $6,934). 37.8% lost money, against 13.5% for QQQ.

**three_down.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,012 (SPY $1,064), bad case $927 (SPY $934), good case $1,088 (SPY $1,165). 39.7% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,012 (QQQ $1,099), bad case $927 (QQQ $939), good case $1,088 (QQQ $1,214). 39.7% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,061 (SPY $5,320), bad case $4,637 (SPY $4,671), good case $5,438 (SPY $5,827). 39.7% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,061 (QQQ $5,495), bad case $4,637 (QQQ $4,695), good case $5,438 (QQQ $6,068). 39.7% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,017 (SPY $1,147), bad case $923 (SPY $930), good case $1,116 (SPY $1,295). 39.8% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,017 (QQQ $1,194), bad case $923 (QQQ $945), good case $1,116 (QQQ $1,387). 39.8% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,084 (SPY $5,733), bad case $4,613 (SPY $4,650), good case $5,582 (SPY $6,473). 39.8% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,084 (QQQ $5,972), bad case $4,613 (QQQ $4,727), good case $5,582 (QQQ $6,934). 39.8% lost money, against 13.5% for QQQ.

**rsi2_qqq_overlay.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,044 (SPY $1,064), bad case $916 (SPY $934), good case $1,143 (SPY $1,165). 32.7% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,044 (QQQ $1,099), bad case $916 (QQQ $939), good case $1,143 (QQQ $1,214). 32.7% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,219 (SPY $5,320), bad case $4,578 (SPY $4,671), good case $5,717 (SPY $5,827). 32.7% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,219 (QQQ $5,495), bad case $4,578 (QQQ $4,695), good case $5,717 (QQQ $6,068). 32.7% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,077 (SPY $1,147), bad case $903 (SPY $930), good case $1,227 (SPY $1,295). 27.5% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,077 (QQQ $1,194), bad case $903 (QQQ $945), good case $1,227 (QQQ $1,387). 27.5% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,384 (SPY $5,733), bad case $4,516 (SPY $4,650), good case $6,134 (SPY $6,473). 27.5% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,384 (QQQ $5,972), bad case $4,516 (QQQ $4,727), good case $6,134 (QQQ $6,934). 27.5% lost money, against 13.5% for QQQ.

**tqqq_sma200.**
6-month, $1,000 versus SPY: 196 windows. Median ending $1,186 (SPY $1,080), bad case $727 (SPY $968), good case $1,594 (SPY $1,166). 30.1% lost money, against 17.3% for SPY.
6-month, $1,000 versus QQQ: 196 windows. Median ending $1,186 (QQQ $1,105), bad case $727 (QQQ $963), good case $1,594 (QQQ $1,212). 30.1% lost money, against 18.9% for QQQ.
6-month, $5,000 versus SPY: 196 windows. Median ending $5,929 (SPY $5,401), bad case $3,637 (SPY $4,838), good case $7,971 (SPY $5,828). 30.1% lost money, against 17.3% for SPY.
6-month, $5,000 versus QQQ: 196 windows. Median ending $5,929 (QQQ $5,525), bad case $3,637 (QQQ $4,813), good case $7,971 (QQQ $6,061). 30.1% lost money, against 18.9% for QQQ.
12-month, $1,000 versus SPY: 190 windows. Median ending $1,381 (SPY $1,158), bad case $694 (SPY $994), good case $2,122 (SPY $1,298). 31.6% lost money, against 10.5% for SPY.
12-month, $1,000 versus QQQ: 190 windows. Median ending $1,381 (QQQ $1,217), bad case $694 (QQQ $1,014), good case $2,122 (QQQ $1,387). 31.6% lost money, against 8.4% for QQQ.
12-month, $5,000 versus SPY: 190 windows. Median ending $6,906 (SPY $5,792), bad case $3,468 (SPY $4,969), good case $10,610 (SPY $6,490). 31.6% lost money, against 10.5% for SPY.
12-month, $5,000 versus QQQ: 190 windows. Median ending $6,906 (QQQ $6,084), bad case $3,468 (QQQ $5,071), good case $10,610 (QQQ $6,935). 31.6% lost money, against 8.4% for QQQ.

**tqqq_band3.**
6-month, $1,000 versus SPY: 196 windows. Median ending $1,185 (SPY $1,080), bad case $751 (SPY $968), good case $1,589 (SPY $1,166). 28.1% lost money, against 17.3% for SPY.
6-month, $1,000 versus QQQ: 196 windows. Median ending $1,185 (QQQ $1,105), bad case $751 (QQQ $963), good case $1,589 (QQQ $1,212). 28.1% lost money, against 18.9% for QQQ.
6-month, $5,000 versus SPY: 196 windows. Median ending $5,927 (SPY $5,401), bad case $3,756 (SPY $4,838), good case $7,944 (SPY $5,828). 28.1% lost money, against 17.3% for SPY.
6-month, $5,000 versus QQQ: 196 windows. Median ending $5,927 (QQQ $5,525), bad case $3,756 (QQQ $4,813), good case $7,944 (QQQ $6,061). 28.1% lost money, against 18.9% for QQQ.
12-month, $1,000 versus SPY: 190 windows. Median ending $1,303 (SPY $1,158), bad case $773 (SPY $994), good case $2,071 (SPY $1,298). 26.3% lost money, against 10.5% for SPY.
12-month, $1,000 versus QQQ: 190 windows. Median ending $1,303 (QQQ $1,217), bad case $773 (QQQ $1,014), good case $2,071 (QQQ $1,387). 26.3% lost money, against 8.4% for QQQ.
12-month, $5,000 versus SPY: 190 windows. Median ending $6,514 (SPY $5,792), bad case $3,865 (SPY $4,969), good case $10,354 (SPY $6,490). 26.3% lost money, against 10.5% for SPY.
12-month, $5,000 versus QQQ: 190 windows. Median ending $6,514 (QQQ $6,084), bad case $3,865 (QQQ $5,071), good case $10,354 (QQQ $6,935). 26.3% lost money, against 8.4% for QQQ.

**tqqq_vol20.**
6-month, $1,000 versus SPY: 196 windows. Median ending $1,179 (SPY $1,080), bad case $738 (SPY $968), good case $1,589 (SPY $1,166). 30.1% lost money, against 17.3% for SPY.
6-month, $1,000 versus QQQ: 196 windows. Median ending $1,179 (QQQ $1,105), bad case $738 (QQQ $963), good case $1,589 (QQQ $1,212). 30.1% lost money, against 18.9% for QQQ.
6-month, $5,000 versus SPY: 196 windows. Median ending $5,893 (SPY $5,401), bad case $3,691 (SPY $4,838), good case $7,947 (SPY $5,828). 30.1% lost money, against 17.3% for SPY.
6-month, $5,000 versus QQQ: 196 windows. Median ending $5,893 (QQQ $5,525), bad case $3,691 (QQQ $4,813), good case $7,947 (QQQ $6,061). 30.1% lost money, against 18.9% for QQQ.
12-month, $1,000 versus SPY: 190 windows. Median ending $1,386 (SPY $1,158), bad case $752 (SPY $994), good case $2,070 (SPY $1,298). 26.8% lost money, against 10.5% for SPY.
12-month, $1,000 versus QQQ: 190 windows. Median ending $1,386 (QQQ $1,217), bad case $752 (QQQ $1,014), good case $2,070 (QQQ $1,387). 26.8% lost money, against 8.4% for QQQ.
12-month, $5,000 versus SPY: 190 windows. Median ending $6,928 (SPY $5,792), bad case $3,760 (SPY $4,969), good case $10,351 (SPY $6,490). 26.8% lost money, against 10.5% for SPY.
12-month, $5,000 versus QQQ: 190 windows. Median ending $6,928 (QQQ $6,084), bad case $3,760 (QQQ $5,071), good case $10,351 (QQQ $6,935). 26.8% lost money, against 8.4% for QQQ.

**tqqq_half.**
6-month, $1,000 versus SPY: 196 windows. Median ending $1,130 (SPY $1,080), bad case $819 (SPY $968), good case $1,363 (SPY $1,166). 29.6% lost money, against 17.3% for SPY.
6-month, $1,000 versus QQQ: 196 windows. Median ending $1,130 (QQQ $1,105), bad case $819 (QQQ $963), good case $1,363 (QQQ $1,212). 29.6% lost money, against 18.9% for QQQ.
6-month, $5,000 versus SPY: 196 windows. Median ending $5,650 (SPY $5,401), bad case $4,094 (SPY $4,838), good case $6,815 (SPY $5,828). 29.6% lost money, against 17.3% for SPY.
6-month, $5,000 versus QQQ: 196 windows. Median ending $5,650 (QQQ $5,525), bad case $4,094 (QQQ $4,813), good case $6,815 (QQQ $6,061). 29.6% lost money, against 18.9% for QQQ.
12-month, $1,000 versus SPY: 190 windows. Median ending $1,212 (SPY $1,158), bad case $819 (SPY $994), good case $1,661 (SPY $1,298). 28.4% lost money, against 10.5% for SPY.
12-month, $1,000 versus QQQ: 190 windows. Median ending $1,212 (QQQ $1,217), bad case $819 (QQQ $1,014), good case $1,661 (QQQ $1,387). 28.4% lost money, against 8.4% for QQQ.
12-month, $5,000 versus SPY: 190 windows. Median ending $6,059 (SPY $5,792), bad case $4,094 (SPY $4,969), good case $8,304 (SPY $6,490). 28.4% lost money, against 10.5% for SPY.
12-month, $5,000 versus QQQ: 190 windows. Median ending $6,059 (QQQ $6,084), bad case $4,094 (QQQ $5,071), good case $8,304 (QQQ $6,935). 28.4% lost money, against 8.4% for QQQ.

**qqq_tqqq_blend.**
6-month, $1,000 versus SPY: 196 windows. Median ending $1,142 (SPY $1,080), bad case $790 (SPY $968), good case $1,417 (SPY $1,166). 29.1% lost money, against 17.3% for SPY.
6-month, $1,000 versus QQQ: 196 windows. Median ending $1,142 (QQQ $1,105), bad case $790 (QQQ $963), good case $1,417 (QQQ $1,212). 29.1% lost money, against 18.9% for QQQ.
6-month, $5,000 versus SPY: 196 windows. Median ending $5,711 (SPY $5,401), bad case $3,948 (SPY $4,838), good case $7,083 (SPY $5,828). 29.1% lost money, against 17.3% for SPY.
6-month, $5,000 versus QQQ: 196 windows. Median ending $5,711 (QQQ $5,525), bad case $3,948 (QQQ $4,813), good case $7,083 (QQQ $6,061). 29.1% lost money, against 18.9% for QQQ.
12-month, $1,000 versus SPY: 190 windows. Median ending $1,282 (SPY $1,158), bad case $785 (SPY $994), good case $1,791 (SPY $1,298). 29.5% lost money, against 10.5% for SPY.
12-month, $1,000 versus QQQ: 190 windows. Median ending $1,282 (QQQ $1,217), bad case $785 (QQQ $1,014), good case $1,791 (QQQ $1,387). 29.5% lost money, against 8.4% for QQQ.
12-month, $5,000 versus SPY: 190 windows. Median ending $6,410 (SPY $5,792), bad case $3,927 (SPY $4,969), good case $8,957 (SPY $6,490). 29.5% lost money, against 10.5% for SPY.
12-month, $5,000 versus QQQ: 190 windows. Median ending $6,410 (QQQ $6,084), bad case $3,927 (QQQ $5,071), good case $8,957 (QQQ $6,935). 29.5% lost money, against 8.4% for QQQ.

**upro_sma200.**
6-month, $1,000 versus SPY: 204 windows. Median ending $1,146 (SPY $1,081), bad case $757 (SPY $967), good case $1,467 (SPY $1,166). 29.4% lost money, against 17.2% for SPY.
6-month, $1,000 versus QQQ: 204 windows. Median ending $1,146 (QQQ $1,105), bad case $757 (QQQ $963), good case $1,467 (QQQ $1,213). 29.4% lost money, against 18.6% for QQQ.
6-month, $5,000 versus SPY: 204 windows. Median ending $5,732 (SPY $5,406), bad case $3,785 (SPY $4,836), good case $7,337 (SPY $5,830). 29.4% lost money, against 17.2% for SPY.
6-month, $5,000 versus QQQ: 204 windows. Median ending $5,732 (QQQ $5,525), bad case $3,785 (QQQ $4,813), good case $7,337 (QQQ $6,063). 29.4% lost money, against 18.6% for QQQ.
12-month, $1,000 versus SPY: 198 windows. Median ending $1,198 (SPY $1,157), bad case $775 (SPY $1,000), good case $1,824 (SPY $1,297). 34.3% lost money, against 10.1% for SPY.
12-month, $1,000 versus QQQ: 198 windows. Median ending $1,198 (QQQ $1,212), bad case $775 (QQQ $1,021), good case $1,824 (QQQ $1,379). 34.3% lost money, against 8.1% for QQQ.
12-month, $5,000 versus SPY: 198 windows. Median ending $5,991 (SPY $5,785), bad case $3,877 (SPY $5,001), good case $9,120 (SPY $6,485). 34.3% lost money, against 10.1% for SPY.
12-month, $5,000 versus QQQ: 198 windows. Median ending $5,991 (QQQ $6,061), bad case $3,877 (QQQ $5,106), good case $9,120 (QQQ $6,896). 34.3% lost money, against 8.1% for QQQ.

**spy_vol15_weekly.**
6-month, $1,000 versus SPY: 253 windows. Median ending $1,062 (SPY $1,068), bad case $927 (SPY $934), good case $1,147 (SPY $1,166). 25.3% lost money, against 20.9% for SPY.
6-month, $1,000 versus QQQ: 253 windows. Median ending $1,062 (QQQ $1,100), bad case $927 (QQQ $938), good case $1,147 (QQQ $1,214). 25.3% lost money, against 22.1% for QQQ.
6-month, $5,000 versus SPY: 253 windows. Median ending $5,310 (SPY $5,341), bad case $4,635 (SPY $4,668), good case $5,733 (SPY $5,831). 25.3% lost money, against 20.9% for SPY.
6-month, $5,000 versus QQQ: 253 windows. Median ending $5,310 (QQQ $5,500), bad case $4,635 (QQQ $4,690), good case $5,733 (QQQ $6,069). 25.3% lost money, against 22.1% for QQQ.
12-month, $1,000 versus SPY: 247 windows. Median ending $1,117 (SPY $1,147), bad case $936 (SPY $930), good case $1,257 (SPY $1,295). 19.0% lost money, against 16.6% for SPY.
12-month, $1,000 versus QQQ: 247 windows. Median ending $1,117 (QQQ $1,195), bad case $936 (QQQ $944), good case $1,257 (QQQ $1,387). 19.0% lost money, against 13.8% for QQQ.
12-month, $5,000 versus SPY: 247 windows. Median ending $5,583 (SPY $5,735), bad case $4,682 (SPY $4,650), good case $6,284 (SPY $6,477). 19.0% lost money, against 16.6% for SPY.
12-month, $5,000 versus QQQ: 247 windows. Median ending $5,583 (QQQ $5,976), bad case $4,682 (QQQ $4,719), good case $6,284 (QQQ $6,936). 19.0% lost money, against 13.8% for QQQ.

**qqq_vol15_weekly.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,072 (SPY $1,064), bad case $951 (SPY $934), good case $1,167 (SPY $1,165). 22.6% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,072 (QQQ $1,099), bad case $951 (QQQ $939), good case $1,167 (QQQ $1,214). 22.6% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,361 (SPY $5,320), bad case $4,753 (SPY $4,671), good case $5,834 (SPY $5,827). 22.6% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,361 (QQQ $5,495), bad case $4,753 (QQQ $4,695), good case $5,834 (QQQ $6,068). 22.6% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,151 (SPY $1,147), bad case $958 (SPY $930), good case $1,282 (SPY $1,295). 13.9% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,151 (QQQ $1,194), bad case $958 (QQQ $945), good case $1,282 (QQQ $1,387). 13.9% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,757 (SPY $5,733), bad case $4,788 (SPY $4,650), good case $6,411 (SPY $6,473). 13.9% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,757 (QQQ $5,972), bad case $4,788 (QQQ $4,727), good case $6,411 (QQQ $6,934). 13.9% lost money, against 13.5% for QQQ.

**spy_vol15_weekly_sma.**
6-month, $1,000 versus SPY: 254 windows. Median ending $1,040 (SPY $1,067), bad case $937 (SPY $934), good case $1,134 (SPY $1,166). 27.2% lost money, against 20.9% for SPY.
6-month, $1,000 versus QQQ: 254 windows. Median ending $1,040 (QQQ $1,101), bad case $937 (QQQ $938), good case $1,134 (QQQ $1,214). 27.2% lost money, against 22.0% for QQQ.
6-month, $5,000 versus SPY: 254 windows. Median ending $5,199 (SPY $5,335), bad case $4,687 (SPY $4,669), good case $5,672 (SPY $5,830). 27.2% lost money, against 20.9% for SPY.
6-month, $5,000 versus QQQ: 254 windows. Median ending $5,199 (QQQ $5,503), bad case $4,687 (QQQ $4,691), good case $5,672 (QQQ $6,069). 27.2% lost money, against 22.0% for QQQ.
12-month, $1,000 versus SPY: 248 windows. Median ending $1,085 (SPY $1,147), bad case $913 (SPY $930), good case $1,228 (SPY $1,295). 29.0% lost money, against 16.5% for SPY.
12-month, $1,000 versus QQQ: 248 windows. Median ending $1,085 (QQQ $1,196), bad case $913 (QQQ $944), good case $1,228 (QQQ $1,387). 29.0% lost money, against 13.7% for QQQ.
12-month, $5,000 versus SPY: 248 windows. Median ending $5,424 (SPY $5,736), bad case $4,567 (SPY $4,650), good case $6,140 (SPY $6,476). 29.0% lost money, against 16.5% for SPY.
12-month, $5,000 versus QQQ: 248 windows. Median ending $5,424 (QQQ $5,980), bad case $4,567 (QQQ $4,721), good case $6,140 (QQQ $6,936). 29.0% lost money, against 13.7% for QQQ.

**qqq_vol15_weekly_sma.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,060 (SPY $1,064), bad case $937 (SPY $934), good case $1,156 (SPY $1,165). 25.3% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,060 (QQQ $1,099), bad case $937 (QQQ $939), good case $1,156 (QQQ $1,214). 25.3% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,298 (SPY $5,320), bad case $4,685 (SPY $4,671), good case $5,778 (SPY $5,827). 25.3% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,298 (QQQ $5,495), bad case $4,685 (QQQ $4,695), good case $5,778 (QQQ $6,068). 25.3% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,118 (SPY $1,147), bad case $935 (SPY $930), good case $1,260 (SPY $1,295). 21.5% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,118 (QQQ $1,194), bad case $935 (QQQ $945), good case $1,260 (QQQ $1,387). 21.5% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,591 (SPY $5,733), bad case $4,677 (SPY $4,650), good case $6,300 (SPY $6,473). 21.5% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,591 (QQQ $5,972), bad case $4,677 (QQQ $4,727), good case $6,300 (QQQ $6,934). 21.5% lost money, against 13.5% for QQQ.

**sector_top3_12m.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,055 (SPY $1,064), bad case $949 (SPY $934), good case $1,157 (SPY $1,165). 25.7% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,055 (QQQ $1,099), bad case $949 (QQQ $939), good case $1,157 (QQQ $1,214). 25.7% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,275 (SPY $5,320), bad case $4,746 (SPY $4,671), good case $5,785 (SPY $5,827). 25.7% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,275 (QQQ $5,495), bad case $4,746 (QQQ $4,695), good case $5,785 (QQQ $6,068). 25.7% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,096 (SPY $1,147), bad case $954 (SPY $930), good case $1,253 (SPY $1,295). 21.9% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,096 (QQQ $1,194), bad case $954 (QQQ $945), good case $1,253 (QQQ $1,387). 21.9% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,480 (SPY $5,733), bad case $4,771 (SPY $4,650), good case $6,265 (SPY $6,473). 21.9% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,480 (QQQ $5,972), bad case $4,771 (QQQ $4,727), good case $6,265 (QQQ $6,934). 21.9% lost money, against 13.5% for QQQ.

**dow_mom_top5.**
6-month, $1,000 versus SPY: 203 windows. Median ending $1,022 (SPY $1,080), bad case $915 (SPY $967), good case $1,148 (SPY $1,164). 39.4% lost money, against 17.2% for SPY.
6-month, $1,000 versus QQQ: 203 windows. Median ending $1,022 (QQQ $1,105), bad case $915 (QQQ $963), good case $1,148 (QQQ $1,210). 39.4% lost money, against 18.7% for QQQ.
6-month, $5,000 versus SPY: 203 windows. Median ending $5,108 (SPY $5,402), bad case $4,575 (SPY $4,836), good case $5,741 (SPY $5,821). 39.4% lost money, against 17.2% for SPY.
6-month, $5,000 versus QQQ: 203 windows. Median ending $5,108 (QQQ $5,524), bad case $4,575 (QQQ $4,813), good case $5,741 (QQQ $6,052). 39.4% lost money, against 18.7% for QQQ.
12-month, $1,000 versus SPY: 197 windows. Median ending $1,056 (SPY $1,157), bad case $875 (SPY $999), good case $1,253 (SPY $1,297). 37.6% lost money, against 10.2% for SPY.
12-month, $1,000 versus QQQ: 197 windows. Median ending $1,056 (QQQ $1,213), bad case $875 (QQQ $1,020), good case $1,253 (QQQ $1,380). 37.6% lost money, against 8.1% for QQQ.
12-month, $5,000 versus SPY: 197 windows. Median ending $5,280 (SPY $5,786), bad case $4,374 (SPY $4,997), good case $6,265 (SPY $6,486). 37.6% lost money, against 10.2% for SPY.
12-month, $5,000 versus QQQ: 197 windows. Median ending $5,280 (QQQ $6,063), bad case $4,374 (QQQ $5,101), good case $6,265 (QQQ $6,901). 37.6% lost money, against 8.1% for QQQ.

**spy_tom.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,002 (SPY $1,064), bad case $946 (SPY $934), good case $1,065 (SPY $1,165). 47.1% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,002 (QQQ $1,099), bad case $946 (QQQ $939), good case $1,065 (QQQ $1,214). 47.1% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,012 (SPY $5,320), bad case $4,732 (SPY $4,671), good case $5,325 (SPY $5,827). 47.1% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,012 (QQQ $5,495), bad case $4,732 (QQQ $4,695), good case $5,325 (QQQ $6,068). 47.1% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $999 (SPY $1,147), bad case $929 (SPY $930), good case $1,095 (SPY $1,295). 50.6% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $999 (QQQ $1,194), bad case $929 (QQQ $945), good case $1,095 (QQQ $1,387). 50.6% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $4,996 (SPY $5,733), bad case $4,647 (SPY $4,650), good case $5,475 (SPY $6,473). 50.6% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $4,996 (QQQ $5,972), bad case $4,647 (QQQ $4,727), good case $5,475 (QQQ $6,934). 50.6% lost money, against 13.5% for QQQ.

**spy_pre_holiday.**
6-month, $1,000 versus SPY: 257 windows. Median ending $998 (SPY $1,064), bad case $973 (SPY $934), good case $1,022 (SPY $1,165). 56.0% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $998 (QQQ $1,099), bad case $973 (QQQ $939), good case $1,022 (QQQ $1,214). 56.0% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $4,991 (SPY $5,320), bad case $4,865 (SPY $4,671), good case $5,108 (SPY $5,827). 56.0% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $4,991 (QQQ $5,495), bad case $4,865 (QQQ $4,695), good case $5,108 (QQQ $6,068). 56.0% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $996 (SPY $1,147), bad case $961 (SPY $930), good case $1,031 (SPY $1,295). 60.6% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $996 (QQQ $1,194), bad case $961 (QQQ $945), good case $1,031 (QQQ $1,387). 60.6% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $4,979 (SPY $5,733), bad case $4,807 (SPY $4,650), good case $5,153 (SPY $6,473). 60.6% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $4,979 (QQQ $5,972), bad case $4,807 (QQQ $4,727), good case $5,153 (QQQ $6,934). 60.6% lost money, against 13.5% for QQQ.

**spy_calendar_both.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,001 (SPY $1,064), bad case $941 (SPY $934), good case $1,068 (SPY $1,165). 49.4% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,001 (QQQ $1,099), bad case $941 (QQQ $939), good case $1,068 (QQQ $1,214). 49.4% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,003 (SPY $5,320), bad case $4,705 (SPY $4,671), good case $5,340 (SPY $5,827). 49.4% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,003 (QQQ $5,495), bad case $4,705 (QQQ $4,695), good case $5,340 (QQQ $6,068). 49.4% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,002 (SPY $1,147), bad case $911 (SPY $930), good case $1,112 (SPY $1,295). 48.2% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,002 (QQQ $1,194), bad case $911 (QQQ $945), good case $1,112 (QQQ $1,387). 48.2% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,008 (SPY $5,733), bad case $4,553 (SPY $4,650), good case $5,562 (SPY $6,473). 48.2% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,008 (QQQ $5,972), bad case $4,553 (QQQ $4,727), good case $5,562 (QQQ $6,934). 48.2% lost money, against 13.5% for QQQ.

**spy_calendar_blend.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,033 (SPY $1,064), bad case $959 (SPY $934), good case $1,106 (SPY $1,165). 23.7% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,033 (QQQ $1,099), bad case $959 (QQQ $939), good case $1,106 (QQQ $1,214). 23.7% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,167 (SPY $5,320), bad case $4,794 (SPY $4,671), good case $5,532 (SPY $5,827). 23.7% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,167 (QQQ $5,495), bad case $4,794 (QQQ $4,695), good case $5,532 (QQQ $6,068). 23.7% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,070 (SPY $1,147), bad case $939 (SPY $930), good case $1,172 (SPY $1,295). 19.9% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,070 (QQQ $1,194), bad case $939 (QQQ $945), good case $1,172 (QQQ $1,387). 19.9% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,350 (SPY $5,733), bad case $4,696 (SPY $4,650), good case $5,861 (SPY $6,473). 19.9% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,350 (QQQ $5,972), bad case $4,696 (QQQ $4,727), good case $5,861 (QQQ $6,934). 19.9% lost money, against 13.5% for QQQ.

**qqq_tom.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,006 (SPY $1,064), bad case $942 (SPY $934), good case $1,078 (SPY $1,165). 45.1% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,006 (QQQ $1,099), bad case $942 (QQQ $939), good case $1,078 (QQQ $1,214). 45.1% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,032 (SPY $5,320), bad case $4,712 (SPY $4,671), good case $5,388 (SPY $5,827). 45.1% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,032 (QQQ $5,495), bad case $4,712 (QQQ $4,695), good case $5,388 (QQQ $6,068). 45.1% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,005 (SPY $1,147), bad case $925 (SPY $930), good case $1,112 (SPY $1,295). 47.0% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,005 (QQQ $1,194), bad case $925 (QQQ $945), good case $1,112 (QQQ $1,387). 47.0% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,027 (SPY $5,733), bad case $4,625 (SPY $4,650), good case $5,560 (SPY $6,473). 47.0% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,027 (QQQ $5,972), bad case $4,625 (QQQ $4,727), good case $5,560 (QQQ $6,934). 47.0% lost money, against 13.5% for QQQ.

**qqq_pre_holiday.**
6-month, $1,000 versus SPY: 257 windows. Median ending $999 (SPY $1,064), bad case $967 (SPY $934), good case $1,025 (SPY $1,165). 50.6% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $999 (QQQ $1,099), bad case $967 (QQQ $939), good case $1,025 (QQQ $1,214). 50.6% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $4,995 (SPY $5,320), bad case $4,834 (SPY $4,671), good case $5,127 (SPY $5,827). 50.6% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $4,995 (QQQ $5,495), bad case $4,834 (QQQ $4,695), good case $5,127 (QQQ $6,068). 50.6% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $993 (SPY $1,147), bad case $961 (SPY $930), good case $1,041 (SPY $1,295). 57.0% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $993 (QQQ $1,194), bad case $961 (QQQ $945), good case $1,041 (QQQ $1,387). 57.0% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $4,965 (SPY $5,733), bad case $4,803 (SPY $4,650), good case $5,205 (SPY $6,473). 57.0% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $4,965 (QQQ $5,972), bad case $4,803 (QQQ $4,727), good case $5,205 (QQQ $6,934). 57.0% lost money, against 13.5% for QQQ.

**qqq_calendar_both.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,009 (SPY $1,064), bad case $948 (SPY $934), good case $1,079 (SPY $1,165). 44.4% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,009 (QQQ $1,099), bad case $948 (QQQ $939), good case $1,079 (QQQ $1,214). 44.4% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,047 (SPY $5,320), bad case $4,742 (SPY $4,671), good case $5,396 (SPY $5,827). 44.4% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,047 (QQQ $5,495), bad case $4,742 (QQQ $4,695), good case $5,396 (QQQ $6,068). 44.4% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,003 (SPY $1,147), bad case $922 (SPY $930), good case $1,132 (SPY $1,295). 47.8% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,003 (QQQ $1,194), bad case $922 (QQQ $945), good case $1,132 (QQQ $1,387). 47.8% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,015 (SPY $5,733), bad case $4,612 (SPY $4,650), good case $5,661 (SPY $6,473). 47.8% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,015 (QQQ $5,972), bad case $4,612 (QQQ $4,727), good case $5,661 (QQQ $6,934). 47.8% lost money, against 13.5% for QQQ.

**qqq_calendar_blend.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,051 (SPY $1,064), bad case $957 (SPY $934), good case $1,131 (SPY $1,165). 19.8% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,051 (QQQ $1,099), bad case $957 (QQQ $939), good case $1,131 (QQQ $1,214). 19.8% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,256 (SPY $5,320), bad case $4,787 (SPY $4,671), good case $5,655 (SPY $5,827). 19.8% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,256 (QQQ $5,495), bad case $4,787 (QQQ $4,695), good case $5,655 (QQQ $6,068). 19.8% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,102 (SPY $1,147), bad case $949 (SPY $930), good case $1,226 (SPY $1,295). 15.9% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,102 (QQQ $1,194), bad case $949 (QQQ $945), good case $1,226 (QQQ $1,387). 15.9% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,510 (SPY $5,733), bad case $4,745 (SPY $4,650), good case $6,128 (SPY $6,473). 15.9% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,510 (QQQ $5,972), bad case $4,745 (QQQ $4,727), good case $6,128 (QQQ $6,934). 15.9% lost money, against 13.5% for QQQ.

**wheel_f.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,005 (SPY $1,064), bad case $979 (SPY $934), good case $1,024 (SPY $1,165). 39.3% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,005 (QQQ $1,099), bad case $979 (QQQ $939), good case $1,024 (QQQ $1,214). 39.3% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,026 (SPY $5,320), bad case $4,893 (SPY $4,671), good case $5,121 (SPY $5,827). 39.3% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,026 (QQQ $5,495), bad case $4,893 (QQQ $4,695), good case $5,121 (QQQ $6,068). 39.3% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,007 (SPY $1,147), bad case $972 (SPY $930), good case $1,037 (SPY $1,295). 40.6% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,007 (QQQ $1,194), bad case $972 (QQQ $945), good case $1,037 (QQQ $1,387). 40.6% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,034 (SPY $5,733), bad case $4,858 (SPY $4,650), good case $5,185 (SPY $6,473). 40.6% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,034 (QQQ $5,972), bad case $4,858 (QQQ $4,727), good case $5,185 (QQQ $6,934). 40.6% lost money, against 13.5% for QQQ.

**covered_f.**
6-month, $1,000 versus SPY: 257 windows. Median ending $1,002 (SPY $1,064), bad case $976 (SPY $934), good case $1,033 (SPY $1,165). 44.4% lost money, against 20.6% for SPY.
6-month, $1,000 versus QQQ: 257 windows. Median ending $1,002 (QQQ $1,099), bad case $976 (QQQ $939), good case $1,033 (QQQ $1,214). 44.4% lost money, against 21.8% for QQQ.
6-month, $5,000 versus SPY: 257 windows. Median ending $5,011 (SPY $5,320), bad case $4,881 (SPY $4,671), good case $5,165 (SPY $5,827). 44.4% lost money, against 20.6% for SPY.
6-month, $5,000 versus QQQ: 257 windows. Median ending $5,011 (QQQ $5,495), bad case $4,881 (QQQ $4,695), good case $5,165 (QQQ $6,068). 44.4% lost money, against 21.8% for QQQ.
12-month, $1,000 versus SPY: 251 windows. Median ending $1,005 (SPY $1,147), bad case $969 (SPY $930), good case $1,055 (SPY $1,295). 43.0% lost money, against 16.3% for SPY.
12-month, $1,000 versus QQQ: 251 windows. Median ending $1,005 (QQQ $1,194), bad case $969 (QQQ $945), good case $1,055 (QQQ $1,387). 43.0% lost money, against 13.5% for QQQ.
12-month, $5,000 versus SPY: 251 windows. Median ending $5,025 (SPY $5,733), bad case $4,844 (SPY $4,650), good case $5,276 (SPY $6,473). 43.0% lost money, against 16.3% for SPY.
12-month, $5,000 versus QQQ: 251 windows. Median ending $5,025 (QQQ $5,972), bad case $4,844 (QQQ $4,727), good case $5,276 (QQQ $6,934). 43.0% lost money, against 13.5% for QQQ.

### Neighbors and checks that were not allowed to take a tier

| Check | Holdout CAGR | Max DD | Sharpe | Ending |
|---|---:|---:|---:|---:|
| rsi2_equal shuffle seed 17 | 1.0% | -32.9% | 0.14 | $1,104 |
| rsi2_entry5 | 0.4% | -23.4% | 0.09 | $1,038 |
| tqqq_band3 shuffle seed 17 | 2.0% | -86.7% | 0.29 | $1,212 |
| tqqq_band2 | 30.7% | -60.9% | 0.81 | $13,596 |
| spy_vol15_daily | 10.9% | -19.3% | 0.88 | $2,747 |
| qqq_vol15_daily | 15.3% | -21.5% | 1.04 | $3,999 |
| sector_top3_12m shuffle seed 17 | 10.1% | -39.7% | 0.59 | $2,555 |
| sector_top2_12m | 15.8% | -33.2% | 0.85 | $4,196 |
| sector_top3_6m | 8.7% | -31.4% | 0.57 | $2,255 |
| sector_top3_3m | 9.7% | -21.2% | 0.71 | $2,471 |
| dow_mom_top5 shuffle seed 17 | 18.9% | -32.8% | 1.00 | $5,420 |
| dow_mom_top10 | 6.2% | -21.9% | 0.51 | $1,797 |
| dow_mom_survivors | 12.7% | -36.2% | 0.73 | $3,221 |
| spy_calendar_both shuffle seed 17 | 2.7% | -33.7% | 0.26 | $1,295 |
| wheel_f $1,000 holdout | 4.2% | -30.4% | 0.33 | $1,496 |
| SPLG covered call. no prices | n/a | n/a | n/a | n/a |
| QQQM covered call. 100 shares at about $312.76 do not fit in $5,000 | n/a | n/a | n/a | n/a |

### What the score does and does not say

The daily TQQQ filter did not remove the crash the monthly filter took. On the full path, 2020 finished 91.6% for the plain 200-day rule, 79.9% for the 3 percent band, and 89.6% for the 20 percent vol target, because the rebound landed in the same year. 2022 finished -44.5%, -35.3%, and -36.7% on those three. The holdout max drawdown is still -57.8% for the plain daily rule, -62.1% for the 3 percent band, and -50.5% for the vol target, against -69.9% for the published monthly filter. Smaller than -70%, and still a crash. The 3 percent band made more holdout money ($15,806) than the vol target ($13,192). The frozen high-risk rule keeps the higher Calmar, so the band stays a candidate that was not the pick. Two neighbors looked better and were not promoted. The daily 15 percent QQQ vol target, which was not the weekly candidate, finished the holdout at $3,999 with a Sharpe of 1.04. The top-2 sector book finished at $4,196. The pre-registered books are the weekly vol target and the top 3. The point-in-time Dow momentum book lost to a shuffle of its own weights (seed 17 ended $5,420 against the real book's $1,621). The current-member Dow diagnostic ended $3,221. That gap is the survivorship haircut on this universe. It was not subtracted from another return, and this is not an S&P 100 test. The TQQQ 3 percent band beat its own shuffle, which ended $1,212. The wheel and the covered call are a Black-Scholes model on adjusted prices: no listed chain, no early assignment, and dividends are already inside the adjusted close so the formula uses a zero yield. On $5,000 the wheel finished the holdout at $5,260. The separate $1,000 wheel finished at $1,496. QQQM at about $312.76 needs about $31,276 for 100 shares, so it does not fit. Yahoo returned no SPLG prices here, so that fit check was not scored. On raw holdout dollars, the plain daily TQQQ rule ($10,774), the 3 percent band ($15,806), the vol target ($13,192), the QQQ/TQQQ blend ($7,062), and the published monthly filter ($9,255) beat both SPY ($4,028) and QQQ ($6,791). Half TQQQ ($5,304) and UPRO ($4,467) beat SPY and not QQQ. None of the levered books cleared the frozen risk-adjusted test against SPY. The vol target's Sharpe is 0.83 against SPY's 0.88 and QQQ's 0.98. The 10-month sleeve ($1,925), the weekly QQQ vol target with the 200-day filter ($3,358), and the weekly QQQ vol target without that filter ($3,627) cleared the SPY risk test. The filter version had the higher Calmar, so it took the moderate slot. All three finished behind SPY and QQQ on dollars. The moderate book's Sharpe is 0.99 against QQQ's 0.98. I would not call a one-hundredth of a Sharpe a win over QQQ. Its Calmar is higher because the drawdown is -17.0% against QQQ's -35.1%, and it made about half as much money. No book in this search beat QQQ buy-and-hold on both raw return and risk-adjusted return.

### Tiers across this search and the earlier three books

Conservative: gtaa_10m. The published 10-month sleeve: equal slices of SPY, EFA, IEF, and GLD, each held only above its 10-month average. Holdout CAGR 6.9%, max drawdown -10.5%, Sharpe 0.96, positive months 65.3%, ending $1,925. SPY on the same dates ended $4,028 (CAGR 15.3%, drawdown -33.7%, Sharpe 0.88). QQQ ended $6,791 (CAGR 21.7%, drawdown -35.1%, Sharpe 0.98). It did not beat SPY on raw holdout return. It did not beat QQQ on raw holdout return. It cleared the frozen risk-adjusted test against SPY. Moderate: qqq_vol15_weekly_sma. The weekly 15 percent QQQ vol target, and only while QQQ is above its 200-day average. Holdout CAGR 13.2%, max drawdown -17.0%, Sharpe 0.99, positive months 55.1%, ending $3,358. SPY on the same dates ended $4,028 (CAGR 15.3%, drawdown -33.7%, Sharpe 0.88). QQQ ended $6,791 (CAGR 21.7%, drawdown -35.1%, Sharpe 0.98). It did not beat SPY on raw holdout return. It did not beat QQQ on raw holdout return. It cleared the frozen risk-adjusted test against SPY. High risk: tqqq_vol20. Hold TQQQ only while QQQ is above its 200-day average, and scale the weight to min(1, 0.20 / 20-day realized vol). Holdout CAGR 30.3%, max drawdown -50.5%, Sharpe 0.83, positive months 47.5%, ending $13,192. SPY on the same dates ended $4,028 (CAGR 15.3%, drawdown -33.7%, Sharpe 0.88). QQQ ended $6,791 (CAGR 21.7%, drawdown -35.1%, Sharpe 0.98). It beat SPY on raw holdout return. It beat QQQ on raw holdout return. It did not clear the frozen risk-adjusted test against SPY.

The bounce and chop share books were not re-run. On their published Dow windows they finished behind SPY buy-and-hold (the 15 percent trail bounce ended at $2,608.44 against four SPY shares at $3,242.23; the next-level bounce ended at $1,502.90). They are not finalists.

Chart: `reports/account_hunt_equity.png`.

If the goal is the milder crash, the book to look at first is still gtaa_10m. It is not in the bot. The default book is still dual momentum at 0.75 percent of equity, which on $1,000 fractional shares ended the earlier test at $1,046 and on whole shares at $1,002. The moderate book is a weekly QQQ weight between zero and one. The high-risk book is a daily TQQQ weight scaled by 20-day realized vol. OpenAPI equity orders are whole shares, so a $1,000 or $5,000 account would skip most of these ETF orders. Fractional shares, or a paper notional large enough to buy whole shares, would be required. A cash account can hold any of them overnight. Adding one to the sandbox would be a new forward command: read the daily close, write the target weight, and send the order on a later session. That command was not added, and the chop-breakout forward test was not edited. Live trading stays off.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. Live trading stays off.

```
python3 -m webull_bot.research_account_hunt
```
<!-- ACCOUNT_HUNT_END -->

<!-- VWAP_BAND_START -->
## Session VWAP bands, 15-minute SPY and QQQ

Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox forward test was not changed. The rules were frozen before this score. The gate reads the 2 standard deviation default: continuation targets 1R, and the reversal targets VWAP. Bands at 2.5 and 3, and the reversal's 1 SD and 1R targets, are variants. A variant that looks better was not promoted. Train is a fresh account through 2021-12-31. The holdout is a fresh account from 2022-01-01 through 2026-10-06.

SPY is Dukascopy 1-minute bids resampled to 15 minutes, 2017-02-16 through 2026-10-06, 2416 sessions, 936992 minute bars, 0 days missing, 2 empty files. Volume is a bid-tick count. Dukascopy publishes QQQUSUSD, but this cache has 81 sessions and 2337 days still missing, short of the 2017+ file. The QQQ rows are Yahoo 15-minute bars from 2026-08-13 through 2026-10-07, about 60 days. That sample cannot clear 300 out-of-sample trades. It is not the gate.

The cash share book is long only. A $1,000 cash account cannot short. Calls and puts are long premium, so the option books take both directions. Shares risk 1% of equity to the stop, with fractional shares. Options are exactly one at-the-money contract when the debit fits in settled cash, so a $5,000 account does not buy more contracts. When the debit already fits in $1,000, the extra cash sits idle and the dollar profit matches. A sale settles the next session. The option price is Black-Scholes with the prior session's VIX1D close, or the prior VIX close before that print exists, a half-spread of the greater of one cent and 1.5% of the mid, and the repo's option fees. There is no listed chain. Time left uses the bar's left timestamp. QQQ, when it is scored, uses the same SPX volatility print. Dukascopy prices are bids and omit dividends, so that buy-and-hold is the lower reference. Yahoo adjusted daily SPY and QQQ include dividends. Taxes are ignored: these books realize short-term gains, and a buy-and-hold defers them.

| Book | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| extension_2sd_r_shares | 812 | 39.8% | 63.0% | 0.39 | -4.92 | -60.8% | $393 | $1,963 | no |
| reversal_2sd_vwap_shares | 908 | 13.1% | 58.5% | 0.11 | -12.08 | -70.3% | $297 | $1,487 | no |
| extension_2sd_r_0dte | 2355 | 50.0% | 39.3% | 1.55 | 2.66 | -16.2% | $32,844 | $36,844 | yes |
| reversal_2sd_vwap_0dte | 396 | 31.1% | 34.0% | 0.87 | -0.15 | -99.9% | $2 | $13 | no |
| extension_2sd_r_7dte | 42 | 38.1% | 57.5% | 0.45 | -0.75 | -82.6% | $174 | $178 | no |
| reversal_2sd_vwap_7dte | 59 | 25.4% | 55.4% | 0.27 | -1.84 | -82.8% | $183 | $185 | no |
| QQQ extension_2sd_r_shares | 28 | 39.3% | 78.6% | 0.18 | -8.93 | -4.6% | $954 | $4,769 | no |
| QQQ reversal_2sd_vwap_shares | 28 | 10.7% | 63.3% | 0.07 | -12.81 | -4.1% | $959 | $4,796 | no |
| QQQ extension_2sd_r_0dte | 65 | 41.5% | 41.9% | 0.99 | 1.27 | -78.5% | $968 | $4,968 | no |
| QQQ reversal_2sd_vwap_0dte | 134 | 36.6% | 32.9% | 1.18 | 2.32 | -39.7% | $1,458 | $5,458 | no |
| QQQ extension_2sd_r_7dte | 23 | 34.8% | 51.0% | 0.51 | -3.16 | -67.2% | $362 | $3,267 | no |
| QQQ reversal_2sd_vwap_7dte | 36 | 36.1% | 57.9% | 0.41 | -4.88 | -60.6% | $425 | $3,234 | no |

### Training account, through 2021-12-31

Fresh $1,000 and $5,000. This is not the gate. An option account that cannot pay for the next contract stops, and the rest of the signals are skips.

| Book | Trades | PF | Sharpe | Max DD | $1,000 | $5,000 |
|---|---:|---:|---:|---:|---:|---:|
| extension_2sd_r_shares | 813 | 0.29 | -5.40 | -61.8% | $384 | $1,918 |
| reversal_2sd_vwap_shares | 935 | 0.10 | -10.30 | -69.2% | $308 | $1,538 |
| extension_2sd_r_0dte | 255 | 0.56 | -1.11 | -99.9% | $1 | $7,554 |
| reversal_2sd_vwap_0dte | 446 | 0.54 | -1.74 | -100.0% | $0 | $0 |
| extension_2sd_r_7dte | 123 | 0.33 | -1.89 | -91.3% | $89 | $151 |
| reversal_2sd_vwap_7dte | 175 | 0.24 | -2.49 | -89.5% | $105 | $140 |
| QQQ extension_2sd_r_shares | 0 | n/a | 0.00 | 0.0% | $1,000 | $5,000 |
| QQQ reversal_2sd_vwap_shares | 0 | n/a | 0.00 | 0.0% | $1,000 | $5,000 |
| QQQ extension_2sd_r_0dte | 0 | n/a | 0.00 | 0.0% | $1,000 | $5,000 |
| QQQ reversal_2sd_vwap_0dte | 0 | n/a | 0.00 | 0.0% | $1,000 | $5,000 |
| QQQ extension_2sd_r_7dte | 0 | n/a | 0.00 | 0.0% | $1,000 | $5,000 |
| QQQ reversal_2sd_vwap_7dte | 0 | n/a | 0.00 | 0.0% | $1,000 | $5,000 |

The holdout gate is profit factor at least 1.10, Sharpe at least 0.40, max drawdown no worse than -30%, and at least 300 trades. These default books cleared it: extension_2sd_r_0dte. Clearing the gate is not the same thing as beating buy-and-hold. SPY buy-and-hold on the same bid series finished the holdout at $1,635 from $1,000 (Sharpe 0.69, max drawdown -25.3%) and $8,176 from $5,000. That series pays no dividends. Yahoo adjusted SPY, which includes dividends, finished at $1,737 (Sharpe 0.76, max drawdown -24.5%). Yahoo adjusted QQQ finished at $1,945 (Sharpe 0.72, max drawdown -34.9%).

### Rolling windows, full sample

One continuous account from the first SPY session, not a fresh holdout. Each window is that account's percentage change, restated from the starting stake. After a $1,000 option account dies, later windows are flat and show $1,000. The $5,000 continuation is the path that stayed open.

**extension_2sd_r_shares, $1,000, 6 months.** Versus SPY bids: 110 windows. Median ending $908 (SPY $1,078), bad $878 (SPY $958), good $933 (SPY $1,182). 100.0% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $908 (QQQ $1,117), bad $878 (QQQ $951), good $933 (QQQ $1,244). 100.0% lost money, against 19.1% for QQQ.

**extension_2sd_r_shares, $1,000, 12 months.** Versus SPY bids: 104 windows. Median ending $817 (SPY $1,143), bad $793 (SPY $936), good $850 (SPY $1,290). 100.0% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $817 (QQQ $1,235), bad $793 (QQQ $928), good $850 (QQQ $1,438). 100.0% lost money, against 13.5% for QQQ.

**extension_2sd_r_shares, $5,000, 6 months.** Versus SPY bids: 110 windows. Median ending $4,541 (SPY $5,392), bad $4,389 (SPY $4,791), good $4,665 (SPY $5,912). 100.0% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $4,541 (QQQ $5,587), bad $4,389 (QQQ $4,756), good $4,665 (QQQ $6,220). 100.0% lost money, against 19.1% for QQQ.

**extension_2sd_r_shares, $5,000, 12 months.** Versus SPY bids: 104 windows. Median ending $4,085 (SPY $5,714), bad $3,964 (SPY $4,682), good $4,249 (SPY $6,450). 100.0% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $4,085 (QQQ $6,176), bad $3,964 (QQQ $4,638), good $4,249 (QQQ $7,192). 100.0% lost money, against 13.5% for QQQ.

**reversal_2sd_vwap_shares, $1,000, 6 months.** Versus SPY bids: 110 windows. Median ending $884 (SPY $1,078), bad $862 (SPY $958), good $900 (SPY $1,182). 100.0% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $884 (QQQ $1,117), bad $862 (QQQ $951), good $900 (QQQ $1,244). 100.0% lost money, against 19.1% for QQQ.

**reversal_2sd_vwap_shares, $1,000, 12 months.** Versus SPY bids: 104 windows. Median ending $779 (SPY $1,143), bad $751 (SPY $936), good $814 (SPY $1,290). 100.0% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $779 (QQQ $1,235), bad $751 (QQQ $928), good $814 (QQQ $1,438). 100.0% lost money, against 13.5% for QQQ.

**reversal_2sd_vwap_shares, $5,000, 6 months.** Versus SPY bids: 110 windows. Median ending $4,419 (SPY $5,392), bad $4,311 (SPY $4,791), good $4,498 (SPY $5,912). 100.0% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $4,419 (QQQ $5,587), bad $4,311 (QQQ $4,756), good $4,498 (QQQ $6,220). 100.0% lost money, against 19.1% for QQQ.

**reversal_2sd_vwap_shares, $5,000, 12 months.** Versus SPY bids: 104 windows. Median ending $3,896 (SPY $5,714), bad $3,756 (SPY $4,682), good $4,070 (SPY $6,450). 100.0% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $3,896 (QQQ $6,176), bad $3,756 (QQQ $4,638), good $4,070 (QQQ $7,192). 100.0% lost money, against 13.5% for QQQ.

**extension_2sd_r_0dte, $1,000, 6 months.** Versus SPY bids: 110 windows. Median ending $1,000 (SPY $1,078), bad $1,000 (SPY $958), good $1,000 (SPY $1,182). 9.1% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $1,000 (QQQ $1,117), bad $1,000 (QQQ $951), good $1,000 (QQQ $1,244). 9.1% lost money, against 19.1% for QQQ.

**extension_2sd_r_0dte, $1,000, 12 months.** Versus SPY bids: 104 windows. Median ending $1,000 (SPY $1,143), bad $1,000 (SPY $936), good $1,000 (SPY $1,290). 9.6% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $1,000 (QQQ $1,235), bad $1,000 (QQQ $928), good $1,000 (QQQ $1,438). 9.6% lost money, against 13.5% for QQQ.

**extension_2sd_r_0dte, $5,000, 6 months.** Versus SPY bids: 110 windows. Median ending $5,571 (SPY $5,392), bad $4,714 (SPY $4,791), good $6,900 (SPY $5,912). 20.0% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $5,571 (QQQ $5,587), bad $4,714 (QQQ $4,756), good $6,900 (QQQ $6,220). 20.0% lost money, against 19.1% for QQQ.

**extension_2sd_r_0dte, $5,000, 12 months.** Versus SPY bids: 104 windows. Median ending $6,486 (SPY $5,714), bad $4,528 (SPY $4,682), good $8,578 (SPY $6,450). 15.4% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $6,486 (QQQ $6,176), bad $4,528 (QQQ $4,638), good $8,578 (QQQ $7,192). 15.4% lost money, against 13.5% for QQQ.

**reversal_2sd_vwap_0dte, $1,000, 6 months.** Versus SPY bids: 110 windows. Median ending $1,000 (SPY $1,078), bad $1,000 (SPY $958), good $1,000 (SPY $1,182). 5.5% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $1,000 (QQQ $1,117), bad $1,000 (QQQ $951), good $1,000 (QQQ $1,244). 5.5% lost money, against 19.1% for QQQ.

**reversal_2sd_vwap_0dte, $1,000, 12 months.** Versus SPY bids: 104 windows. Median ending $1,000 (SPY $1,143), bad $1,000 (SPY $936), good $1,000 (SPY $1,290). 5.8% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $1,000 (QQQ $1,235), bad $1,000 (QQQ $928), good $1,000 (QQQ $1,438). 5.8% lost money, against 13.5% for QQQ.

**reversal_2sd_vwap_0dte, $5,000, 6 months.** Versus SPY bids: 110 windows. Median ending $5,000 (SPY $5,392), bad $1,901 (SPY $4,791), good $5,000 (SPY $5,912). 30.0% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $5,000 (QQQ $5,587), bad $1,901 (QQQ $4,756), good $5,000 (QQQ $6,220). 30.0% lost money, against 19.1% for QQQ.

**reversal_2sd_vwap_0dte, $5,000, 12 months.** Versus SPY bids: 104 windows. Median ending $5,000 (SPY $5,714), bad $10 (SPY $4,682), good $5,000 (SPY $6,450). 31.7% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $5,000 (QQQ $6,176), bad $10 (QQQ $4,638), good $5,000 (QQQ $7,192). 31.7% lost money, against 13.5% for QQQ.

**extension_2sd_r_7dte, $1,000, 6 months.** Versus SPY bids: 110 windows. Median ending $1,000 (SPY $1,078), bad $1,000 (SPY $958), good $1,000 (SPY $1,182). 3.6% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $1,000 (QQQ $1,117), bad $1,000 (QQQ $951), good $1,000 (QQQ $1,244). 3.6% lost money, against 19.1% for QQQ.

**extension_2sd_r_7dte, $1,000, 12 months.** Versus SPY bids: 104 windows. Median ending $1,000 (SPY $1,143), bad $1,000 (SPY $936), good $1,000 (SPY $1,290). 3.8% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $1,000 (QQQ $1,235), bad $1,000 (QQQ $928), good $1,000 (QQQ $1,438). 3.8% lost money, against 13.5% for QQQ.

**extension_2sd_r_7dte, $5,000, 6 months.** Versus SPY bids: 110 windows. Median ending $5,000 (SPY $5,392), bad $2,449 (SPY $4,791), good $5,000 (SPY $5,912). 26.4% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $5,000 (QQQ $5,587), bad $2,449 (QQQ $4,756), good $5,000 (QQQ $6,220). 26.4% lost money, against 19.1% for QQQ.

**extension_2sd_r_7dte, $5,000, 12 months.** Versus SPY bids: 104 windows. Median ending $5,000 (SPY $5,714), bad $860 (SPY $4,682), good $5,000 (SPY $6,450). 27.9% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $5,000 (QQQ $6,176), bad $860 (QQQ $4,638), good $5,000 (QQQ $7,192). 27.9% lost money, against 13.5% for QQQ.

**reversal_2sd_vwap_7dte, $1,000, 6 months.** Versus SPY bids: 110 windows. Median ending $1,000 (SPY $1,078), bad $1,000 (SPY $958), good $1,000 (SPY $1,182). 6.4% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $1,000 (QQQ $1,117), bad $1,000 (QQQ $951), good $1,000 (QQQ $1,244). 6.4% lost money, against 19.1% for QQQ.

**reversal_2sd_vwap_7dte, $1,000, 12 months.** Versus SPY bids: 104 windows. Median ending $1,000 (SPY $1,143), bad $1,000 (SPY $936), good $1,000 (SPY $1,290). 6.7% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $1,000 (QQQ $1,235), bad $1,000 (QQQ $928), good $1,000 (QQQ $1,438). 6.7% lost money, against 13.5% for QQQ.

**reversal_2sd_vwap_7dte, $5,000, 6 months.** Versus SPY bids: 110 windows. Median ending $5,000 (SPY $5,392), bad $2,422 (SPY $4,791), good $5,000 (SPY $5,912). 16.4% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $5,000 (QQQ $5,587), bad $2,422 (QQQ $4,756), good $5,000 (QQQ $6,220). 16.4% lost money, against 19.1% for QQQ.

**reversal_2sd_vwap_7dte, $5,000, 12 months.** Versus SPY bids: 104 windows. Median ending $5,000 (SPY $5,714), bad $1,739 (SPY $4,682), good $5,000 (SPY $6,450). 17.3% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $5,000 (QQQ $6,176), bad $1,739 (QQQ $4,638), good $5,000 (QQQ $7,192). 17.3% lost money, against 13.5% for QQQ.

### Variants and the both-directions share baseline

These rows use the same holdout and the same $1,000 stake. They do not replace the 2 SD default.

| Book | Trades | Win | PF | Sharpe | Max DD | Ending | Clears the numbers |
|---|---:|---:|---:|---:|---:|---:|---|
| extension_2.5sd_r_shares | 572 | 40.4% | 0.38 | -4.06 | -47.8% | $523 | no |
| extension_3sd_r_shares | 365 | 38.1% | 0.36 | -3.23 | -34.9% | $651 | no |
| reversal_2.5sd_vwap_shares | 760 | 12.4% | 0.13 | -10.38 | -61.8% | $382 | no |
| reversal_3sd_vwap_shares | 549 | 9.7% | 0.10 | -8.56 | -51.9% | $481 | no |
| reversal_2sd_inner_shares | 908 | 4.0% | 0.02 | -18.25 | -71.8% | $282 | no |
| reversal_2sd_r_shares | 908 | 22.9% | 0.19 | -9.08 | -68.6% | $315 | no |
| reversal_2.5sd_vwap_0dte | 330 | 29.1% | 0.83 | -0.37 | -99.9% | $1 | no |
| reversal_3sd_vwap_0dte | 205 | 28.8% | 0.70 | 0.32 | -99.7% | $3 | no |
| reversal_2sd_inner_0dte | 205 | 30.7% | 0.64 | -0.56 | -99.7% | $3 | no |
| reversal_2sd_r_0dte | 3206 | 40.3% | 0.98 | -0.47 | -99.9% | $2 | no |
| extension_2sd_r_shares_both | 1320 | 43.6% | 0.44 | -5.31 | -70.6% | $295 | no |
| reversal_2sd_vwap_shares_both | 1288 | 11.2% | 0.09 | -17.59 | -80.1% | $199 | no |

Random entries use seed 17, the same count, and a 1R target. One draw. It was not used to change the rule.



**extension_2sd_r_shares.** Random holdout trades 554, ending $486, profit factor 0.14, Sharpe -7.64, max drawdown -51.4%.

**reversal_2sd_vwap_shares.** Random holdout trades 845, ending $333, profit factor 0.15, Sharpe -10.07, max drawdown -66.8%.

**extension_2sd_r_0dte.** Random holdout trades 1401, ending $6, profit factor 0.94, Sharpe 0.18, max drawdown -99.6%.

**reversal_2sd_vwap_0dte.** Random holdout trades 837, ending $1, profit factor 0.93, Sharpe -0.85, max drawdown -100.0%.

**extension_2sd_r_7dte.** Random holdout trades 59, ending $190, profit factor 0.42, Sharpe -1.13, max drawdown -81.0%.

**reversal_2sd_vwap_7dte.** Random holdout trades 79, ending $191, profit factor 0.50, Sharpe -0.97, max drawdown -80.9%.

Same holdout trades, split by the volatility print. VIX1D starts in 2023. Earlier sessions use the 30-day VIX as same-day vol. This split was not used to change the rule.



**extension_2sd_r_0dte.** VIX 623 trades, profit factor 1.60, dollar profit $10,035; VIX1D 1732 trades, profit factor 1.53, dollar profit $21,809. Largest trade $1,499 on 2025-04-09 (flat), 4.7% of that book's dollar profit.

**reversal_2sd_vwap_0dte.** VIX 396 trades, profit factor 0.87, dollar profit $-998. Largest trade $372 on 2022-01-24 (target), -37.2% of that book's dollar profit.

**extension_2sd_r_7dte.** VIX 26 trades, profit factor 0.38, dollar profit $-643; VIX1D 16 trades, profit factor 0.62, dollar profit $-183. Largest trade $107 on 2023-05-02 (target), -12.9% of that book's dollar profit.

**reversal_2sd_vwap_7dte.** VIX 48 trades, profit factor 0.32, dollar profit $-657; VIX1D 11 trades, profit factor 0.01, dollar profit $-160. Largest trade $66 on 2022-01-06 (target), -8.0% of that book's dollar profit.

Fractional share counts are a research fill. Webull equity orders in this repo are whole shares, so a $1,000 or $5,000 account would skip most of these ETF orders. No sandbox forward command was added.



**extension_2sd_r_shares.** 336 of 812 holdout trades were under one share.

**reversal_2sd_vwap_shares.** 438 of 908 holdout trades were under one share.

Charts: `reports/vwap_band_equity.png` and `reports/vwap_band_examples.png`. The equity chart has two linear panels so one option book does not hide the rest. The example panel is the first holdout reversal that hit its target, the first that hit its stop, and the first holdout continuation. They are illustrations, not a pick.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.

```
python3 -m webull_bot.chart_reads.research_vwap_band
```
<!-- VWAP_BAND_END -->

<!-- EMA_REJECT_START -->
## 9/20 EMA rejection, 5-minute SPY and QQQ

Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox forward test was not changed. The rules were frozen before this score. The gate is the chart that was pointed at: a 9/20 downtrend or its long mirror, a bar that tags the 9 EMA within 0.10 ATR and closes back on the trend side, with session VWAP within 0.10 ATR of the 9 EMA. The stop is one cent beyond the rejection bar. The target is the prior 5-bar swing. The 9 EMA alone, the intact 20 EMA, the 20 EMA stop, and the 1R, 2R, and 9 EMA cross exits are variants. A bar within 0.10 ATR of the 9 EMA cannot reach a 20 EMA that is at least 0.10 ATR away, so the intact-20 variant matches the 9 EMA variant. A variant that looks better was not promoted. Train is a fresh account through 2021-12-31. The holdout is a fresh account from 2022-01-01 through 2026-10-06. 2026-10-07 is the illustration, not part of the Dukascopy score.

SPY is Dukascopy 1-minute bids resampled to 5 minutes, 2017-02-16 through 2026-10-06, 2416 sessions, 936992 minute bars, 187540 five-minute bars, 0 days missing, 2 empty files. Volume is a bid-tick count. Dukascopy publishes QQQUSUSD, but this cache has 342 day files, short of the 2017+ file. The QQQ rows are Yahoo 5-minute bars from 2026-08-14 through 2026-10-07, about 60 days. That sample cannot clear 300 out-of-sample trades. It is not the gate.

The cash share book is long only. A $1,000 cash account cannot short, so it cannot express the short rejection on that chart. Calls and puts are long premium, so the 0 DTE book takes both directions. Shares risk 1% of equity to the stop, with fractional shares. Options are exactly one at-the-money contract when the debit fits in settled cash. A $5,000 account does not buy a second contract. A debit that fits in $5,000 and not in $1,000 is skipped on the smaller stake, so the two endings need not match. A sale settles the next session. The option price is Black-Scholes with the prior session's VIX1D close, or the prior VIX close before that print exists, a half-spread of the greater of one cent and 1.5% of the mid, and the repo's option fees. There is no listed chain. Time left uses the bar's left timestamp. QQQ uses the same SPX volatility print. The chop guard is on for every book: relative volume under 0.85 versus the prior 20 bars (chop v2), an EMA spread under 0.10 ATR, or a 9 EMA slope under 0.05 ATR. Chop v2's 0.75 ATR stack width is not used. Dukascopy volume is a bid-tick count. Dukascopy prices are bids and omit dividends, so that buy-and-hold is the lower reference. Yahoo adjusted daily SPY and QQQ include dividends. Taxes are ignored: these books realize short-term gains, and a buy-and-hold defers them.

| Book | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| vwap_swing_shares | 101 | 8.9% | 48.0% | 0.11 | -3.30 | -12.1% | $879 | $4,396 | no |
| vwap_swing_0dte | 242 | 31.4% | 41.2% | 0.65 | -0.43 | -95.8% | $75 | $3,725 | no |
| QQQ vwap_swing_shares | 3 | 0.0% | 100.0% | 0.00 | -4.36 | -0.3% | $997 | $4,983 | no |
| QQQ vwap_swing_0dte | 7 | 42.9% | 41.5% | 1.06 | 0.25 | -6.9% | $1,004 | $5,004 | no |

### Training account, through 2021-12-31

Fresh $1,000 and $5,000. This is not the gate. An option account that cannot pay for the next contract stops, and the rest of the signals are skips.

| Book | Trades | PF | Sharpe | Max DD | $1,000 | $5,000 |
|---|---:|---:|---:|---:|---:|---:|
| vwap_swing_shares | 49 | 0.26 | -1.16 | -4.8% | $953 | $4,765 |
| vwap_swing_0dte | 106 | 0.81 | -0.18 | -25.8% | $823 | $4,823 |
| QQQ vwap_swing_shares | 0 | n/a | 0.00 | 0.0% | $1,000 | $5,000 |
| QQQ vwap_swing_0dte | 0 | n/a | 0.00 | 0.0% | $1,000 | $5,000 |

No default book cleared the holdout gate (profit factor at least 1.10, Sharpe at least 0.40, max drawdown no worse than -30%, and at least 300 trades). SPY buy-and-hold on the same bid series finished the holdout at $1,635 from $1,000 (Sharpe 0.69, max drawdown -25.3%) and $8,176 from $5,000. That series pays no dividends. Yahoo adjusted SPY, which includes dividends, finished at $1,737 (Sharpe 0.76, max drawdown -24.5%). Yahoo adjusted QQQ finished at $1,945 (Sharpe 0.72, max drawdown -34.9%).

### Rolling windows, full sample

One continuous account from the first SPY session, not a fresh holdout. Each window is that account's percentage change, restated from the starting stake. When an option account can no longer pay for a contract, later windows use the equity that is left.

**vwap_swing_shares, $1,000, 6 months.** Versus SPY bids: 110 windows. Median ending $989 (SPY $1,078), bad $983 (SPY $958), good $1,000 (SPY $1,182). 84.5% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $989 (QQQ $1,117), bad $983 (QQQ $951), good $1,000 (QQQ $1,244). 84.5% lost money, against 19.1% for QQQ.

**vwap_swing_shares, $1,000, 12 months.** Versus SPY bids: 104 windows. Median ending $977 (SPY $1,143), bad $969 (SPY $936), good $998 (SPY $1,290). 94.2% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $977 (QQQ $1,235), bad $969 (QQQ $928), good $998 (QQQ $1,438). 94.2% lost money, against 13.5% for QQQ.

**vwap_swing_shares, $5,000, 6 months.** Versus SPY bids: 110 windows. Median ending $4,946 (SPY $5,392), bad $4,913 (SPY $4,791), good $5,000 (SPY $5,912). 84.5% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $4,946 (QQQ $5,587), bad $4,913 (QQQ $4,756), good $5,000 (QQQ $6,220). 84.5% lost money, against 19.1% for QQQ.

**vwap_swing_shares, $5,000, 12 months.** Versus SPY bids: 104 windows. Median ending $4,885 (SPY $5,714), bad $4,844 (SPY $4,682), good $4,988 (SPY $6,450). 94.2% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $4,885 (QQQ $6,176), bad $4,844 (QQQ $4,638), good $4,988 (QQQ $7,192). 94.2% lost money, against 13.5% for QQQ.

**vwap_swing_0dte, $1,000, 6 months.** Versus SPY bids: 110 windows. Median ending $952 (SPY $1,078), bad $609 (SPY $958), good $1,211 (SPY $1,182). 72.7% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $952 (QQQ $1,117), bad $609 (QQQ $951), good $1,211 (QQQ $1,244). 72.7% lost money, against 19.1% for QQQ.

**vwap_swing_0dte, $1,000, 12 months.** Versus SPY bids: 104 windows. Median ending $891 (SPY $1,143), bad $389 (SPY $936), good $1,163 (SPY $1,290). 79.8% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $891 (QQQ $1,235), bad $389 (QQQ $928), good $1,163 (QQQ $1,438). 79.8% lost money, against 13.5% for QQQ.

**vwap_swing_0dte, $5,000, 6 months.** Versus SPY bids: 110 windows. Median ending $4,945 (SPY $5,392), bad $4,663 (SPY $4,791), good $5,071 (SPY $5,912). 77.3% lost money, against 21.8% for SPY.

Versus Yahoo adjusted QQQ: 110 windows. Median ending $4,945 (QQQ $5,587), bad $4,663 (QQQ $4,756), good $5,071 (QQQ $6,220). 77.3% lost money, against 19.1% for QQQ.

**vwap_swing_0dte, $5,000, 12 months.** Versus SPY bids: 104 windows. Median ending $4,904 (SPY $5,714), bad $4,427 (SPY $4,682), good $5,124 (SPY $6,450). 82.7% lost money, against 15.4% for SPY.

Versus Yahoo adjusted QQQ: 104 windows. Median ending $4,904 (QQQ $6,176), bad $4,427 (QQQ $4,638), good $5,124 (QQQ $7,192). 82.7% lost money, against 13.5% for QQQ.

### Variants and the both-directions share baseline

These rows use the same holdout and the same $1,000 stake. They do not replace the VWAP-confluence default.

| Book | Trades | Win | PF | Sharpe | Max DD | Ending | Clears the numbers |
|---|---:|---:|---:|---:|---:|---:|---|
| ema_swing_shares | 898 | 11.7% | 0.12 | -11.93 | -66.2% | $338 | no |
| ema_swing_0dte | 237 | 30.4% | 0.67 | -0.32 | -99.9% | $1 | no |
| ema20_swing_shares | 898 | 11.7% | 0.12 | -11.93 | -66.2% | $338 | no |
| ema20_swing_0dte | 237 | 30.4% | 0.67 | -0.32 | -99.9% | $1 | no |
| vwap_ema20stop_swing_shares | 101 | 16.8% | 0.18 | -2.58 | -11.0% | $890 | no |
| vwap_ema20stop_swing_0dte | 269 | 49.8% | 1.05 | 0.28 | -49.7% | $1,215 | no |
| vwap_r1_shares | 101 | 7.9% | 0.06 | -3.49 | -13.6% | $864 | no |
| vwap_r1_0dte | 187 | 31.0% | 0.56 | -1.26 | -99.5% | $6 | no |
| vwap_r2_shares | 101 | 13.9% | 0.17 | -2.75 | -12.7% | $874 | no |
| vwap_r2_0dte | 195 | 19.5% | 0.68 | -0.49 | -99.7% | $4 | no |
| vwap_ema_shares | 101 | 14.9% | 0.25 | -2.44 | -11.6% | $885 | no |
| vwap_ema_0dte | 229 | 13.1% | 0.70 | -0.81 | -97.2% | $40 | no |
| vwap_swing_shares_both | 234 | 7.3% | 0.07 | -5.70 | -28.2% | $718 | no |

Random entries use seed 17, the same count of holdout signals that have a prior swing, and a 1R target. One draw. It was not used to change the rule.



**vwap_swing_shares.** Random holdout trades 57, ending $931, profit factor 0.03, Sharpe -2.84, max drawdown -6.9%.

**vwap_swing_0dte.** Random holdout trades 294, ending $722, profit factor 0.89, Sharpe -0.27, max drawdown -49.3%.

Same holdout trades, split by the volatility print. VIX1D starts in 2023. Earlier sessions use the 30-day VIX as same-day vol. This split was not used to change the rule.



**vwap_swing_0dte.** VIX 84 trades, profit factor 0.56, dollar profit -$512; VIX1D 158 trades, profit factor 0.72, dollar profit -$412. Largest trade $191 on 2024-05-02 (target). The book lost $925.

Fractional share counts are a research fill. Webull equity orders in this repo are whole shares, so a quantity under one share would not be sent. No sandbox forward command was added.



**vwap_swing_shares.** 0 of 101 holdout trades were under one share.

Charts: `reports/ema_reject_equity.png` and `reports/ema_reject_20261007.png`. The 2026-10-07 chart is Yahoo 5-minute, 2026-08-14 through 2026-10-07, because the Dukascopy file ends with the last complete session and does not include that day. EMAs on the chart are computed from those Yahoo bars, not from the 2017 bid series. The user read the 9 EMA and VWAP stacked near 775.05 at 10:20 ET. On these bars, 9 EMA 775.05, 20 EMA 776.32, VWAP 775.04, close 774.77, high 774.99. The frozen rule does not mark 10:20 as a gate signal. It failed: rel volume 0.43 is below 0.85; high is 0.11 ATR from the 9 EMA, or the close is not back below it. Relative volume would still exclude the bar if the tag were widened to the measured distance. The chart marks 0 other VWAP-confluence signal(s) that day. The tolerances were not changed after this reading.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.

```
python3 -m webull_bot.chart_reads.research_ema_reject
```
<!-- EMA_REJECT_END -->

<!-- CANDLES_START -->
## Candlestick patterns

Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox forward test was not changed. The shape rules were written to `reports/candles_rules.json` and `docs/CANDLESTICK_PATTERNS.md` before any forward return was measured. No pattern was added to the live list.

SPY is Dukascopy 1-minute bids resampled to 5 and 15 minutes, 2017-02-16 through 2026-10-06, 2,416 sessions, 0 days missing, 187,540 five-minute bars, 62,531 fifteen-minute bars. Volume is a bid-tick count. Prices are bids. Dukascopy publishes QQQUSUSD, but this cache has 833 day files, short of the 2017+ file. Yahoo 5-minute and 15-minute rows are about 60 days. They are not in the false-discovery family. Daily bars are Yahoo adjusted prices from 2016-01-01 through 2026-10-06 for NVDA, AAPL, UNH, MSFT, AMZN, META, GOOGL, JPM, AMD, TSLA, AVGO, COST, V, MA, LLY, XOM, SPY, QQQ. The pooled daily book weights each signal equally. A 1% NVDA day counts the same as a 1% SPY day. The list is a 2026 snapshot, so names that failed earlier are absent.

Each pattern is entered at the next bar's open and closed at the close 1, 3, or 6 bars later. On 5-minute and 15-minute bars the entry and the exit have to be in the same session as the signal, so a late-day pattern with no room is skipped. Costs are one share on the repo schedule: 5 bps slippage and 1 bp half-spread on each side, plus the 2026 SEC and FINRA sell fees. That is about 12 bps before the regulatory fee, so a one-bar scalp has to clear that friction. The random baseline is one seed-17 draw of the same number of holdout-eligible bars, in the pattern's direction. Neutral patterns are measured both ways and cannot be labeled an edge.

The false-discovery family is every directional pattern, on SPY 5-minute, SPY 15-minute, SPY daily, and the pooled liquid daily basket, at 1, 3, and 6 bars, with the context filter off and on. A cell needs 30 holdout trades to enter that test. This run tested 411 cells. The Benjamini-Hochberg q line is 0.10. The independent expected-max t bar is 2.82. Patterns overlap, so the tests are not independent. Treating them as independent raises that bar, which makes a pass harder, not easier. An edge also needs 300 holdout trades, a positive training mean, a positive holdout mean, a holdout mean and hit rate above the seed-17 draw, and, for the pooled basket, a positive SPY daily mean in both windows. The basket is the 2026 liquid list and is survivorship-biased. QQQ intraday is not in the family. Per-name daily rows are in `reports/candles.json` and are not the family.

No cell cleared the frozen edge rule. On 5-minute SPY, no directional cell with 300 trades had a positive after-cost mean. The best t-stat on that book is still negative: three white soldiers, 3 bars, context on, 74 trades, about -8 bp. Fifteen-minute SPY's best cell (three outside up, 6 bars, context on, 65 trades) is about +3 bp and the training mean is negative. SPY daily's best cell (bullish harami, 6 bars, context off, 34 trades) is about +13 bp and sits under the seed-17 random mean. The ranks below are led by the pooled daily basket, which is a 2026 snapshot. The first row, a dragonfly doji held 6 days, is +97 bp against a random +140 bp, so it did not beat a random hold, and it has 227 trades. The closest large cell is the hammer, 6 bars, context off: 450 trades, +58 bp against a random +53 bp, hit rate 58.4% against 57.8%, training mean also positive, t 2.71 against the 2.82 bar, q 0.70. That is not an edge. A positive t on a short sample is not a pass.

### Highest holdout t-stats in the family

Ranked by the holdout t-stat among cells with at least 30 trades. A high rank with a failed reason is not an edge.

| Pattern | Book | Bars | Context | Trades | Mean | Hit | t | Random mean | q | Why it stands here |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| Dragonfly doji | LIQUID_1d | 6 | off | 227 | 97.3 bp | 62.6% | 3.05 | 140.5 bp | 0.47 | fewer than 300 holdout trades |
| Hammer | LIQUID_1d | 6 | off | 450 | 58.1 bp | 58.4% | 2.71 | 53.2 bp | 0.70 | Benjamini-Hochberg q is above 0.10 |
| Inverted hammer | LIQUID_1d | 6 | off | 359 | 64.1 bp | 54.9% | 2.27 | 25.7 bp | 1.00 | Benjamini-Hochberg q is above 0.10 |
| Three inside up | LIQUID_1d | 3 | on | 46 | 138.4 bp | 63.0% | 2.27 | -16.1 bp | 1.00 | fewer than 300 holdout trades |
| Dragonfly doji | LIQUID_1d | 6 | on | 37 | 151.0 bp | 62.2% | 2.15 | -11.3 bp | 1.00 | fewer than 300 holdout trades |
| Three outside up | LIQUID_1d | 1 | on | 32 | 71.0 bp | 68.8% | 2.10 | -41.5 bp | 1.00 | fewer than 300 holdout trades |
| Inverted hammer | LIQUID_1d | 3 | off | 361 | 40.8 bp | 53.2% | 2.10 | 45.1 bp | 1.00 | holdout mean does not beat the seed-17 draw |
| Bullish marubozu | LIQUID_1d | 6 | on | 38 | 102.1 bp | 68.4% | 1.98 | -6.0 bp | 1.00 | fewer than 300 holdout trades |
| Dragonfly doji | LIQUID_1d | 3 | off | 228 | 42.6 bp | 61.4% | 1.96 | 59.5 bp | 1.00 | fewer than 300 holdout trades |
| Tweezer bottom | LIQUID_1d | 6 | off | 227 | 62.5 bp | 55.5% | 1.95 | 140.5 bp | 1.00 | fewer than 300 holdout trades |
| Bullish marubozu | LIQUID_1d | 3 | on | 38 | 66.3 bp | 71.1% | 1.91 | -31.6 bp | 1.00 | fewer than 300 holdout trades |
| Bearish harami | LIQUID_1d | 6 | on | 108 | 73.1 bp | 57.4% | 1.54 | -20.0 bp | 1.00 | fewer than 300 holdout trades |
| Hammer | LIQUID_1d | 6 | on | 79 | 65.3 bp | 62.0% | 1.50 | -66.5 bp | 1.00 | fewer than 300 holdout trades |
| Three white soldiers | LIQUID_1d | 6 | off | 52 | 67.8 bp | 67.3% | 1.41 | -3.4 bp | 1.00 | fewer than 300 holdout trades |
| Tweezer bottom | LIQUID_1d | 3 | off | 227 | 30.0 bp | 49.3% | 1.38 | 47.8 bp | 1.00 | fewer than 300 holdout trades |

### How often the shapes print on SPY

Raw rows are every completion. Traded rows are the ones with a same-session 1-bar exit in the holdout. A gap pattern can print and still have almost no trades.

| Pattern | 5-minute raw | 5-minute traded, context off | 5-minute traded, context on | Daily raw | Daily traded, context off |
|---|---:|---:|---:|---:|---:|
| Doji | 25413 | 12697 | 9274 | 432 | 179 |
| Long-legged doji | 4102 | 2112 | 1693 | 50 | 22 |
| Dragonfly doji | 2044 | 1045 | 210 | 30 | 14 |
| Gravestone doji | 1750 | 820 | 201 | 16 | 10 |
| Hammer | 4339 | 2151 | 527 | 64 | 22 |
| Hanging man | 1624 | 833 | 622 | 33 | 10 |
| Inverted hammer | 3609 | 1644 | 468 | 24 | 9 |
| Shooting star | 1371 | 595 | 379 | 11 | 4 |
| Spinning top | 14463 | 7392 | 5581 | 174 | 76 |
| Bullish marubozu | 2065 | 857 | 191 | 34 | 16 |
| Bearish marubozu | 1643 | 621 | 123 | 11 | 4 |
| Bullish engulfing | 4134 | 2052 | 654 | 28 | 18 |
| Bearish engulfing | 3974 | 2044 | 638 | 41 | 20 |
| Bullish harami | 7080 | 3578 | 704 | 78 | 34 |
| Bearish harami | 7205 | 3549 | 713 | 66 | 29 |
| Bullish harami cross | 1464 | 729 | 129 | 39 | 15 |
| Bearish harami cross | 1743 | 853 | 163 | 48 | 22 |
| Piercing line | 174 | 74 | 24 | 15 | 3 |
| Dark cloud cover | 169 | 85 | 21 | 12 | 6 |
| Tweezer bottom | 2428 | 1276 | 250 | 34 | 15 |
| Tweezer top | 2796 | 1382 | 307 | 34 | 12 |
| Bullish kicker | 92 | 43 | 18 | 1 | 1 |
| Bearish kicker | 55 | 29 | 15 | 2 | 1 |
| Morning star | 13 | 5 | 1 | 4 | 2 |
| Evening star | 12 | 4 | 2 | 5 | 2 |
| Morning doji star | 4 | 3 | 1 | 2 | 1 |
| Evening doji star | 5 | 3 | 2 | 2 | 0 |
| Three white soldiers | 675 | 286 | 76 | 7 | 2 |
| Three black crows | 561 | 246 | 55 | 1 | 1 |
| Three inside up | 1218 | 619 | 196 | 20 | 6 |
| Three inside down | 1226 | 574 | 167 | 24 | 15 |
| Three outside up | 1952 | 983 | 330 | 11 | 7 |
| Three outside down | 1871 | 961 | 310 | 12 | 6 |
| Bullish abandoned baby | 0 | 0 | 0 | 0 | 0 |
| Bearish abandoned baby | 0 | 0 | 0 | 0 | 0 |
| Rising three methods | 10 | 3 | 1 | 0 | 0 |
| Falling three methods | 15 | 4 | 1 | 0 | 0 |
| Upside tasuki gap | 39 | 17 | 6 | 6 | 3 |
| Downside tasuki gap | 28 | 11 | 4 | 1 | 1 |

### Optional confirmation on the published VWAP and EMA books

One filter was registered for each setup, before this score. The EMA book (VWAP confluence, rejection stop, swing target) and the VWAP 2 SD reversal keep a signal only when a reversal pattern of the same direction completes on the signal bar. The VWAP 2 SD extension keeps a signal only when a continuation pattern of the same direction completes on that bar. Context off is the shape. Context on also requires that pattern's trend and location. Shares stay long only. The 0 DTE books still take both directions. The unfiltered endings below are the published ones. They were not resimulated. A filter improves a book only when the holdout has at least 20 trades, ending equity is higher, profit factor is not lower, and max drawdown is not worse by more than 5 percentage points. Clearing that line does not add the book to the live list. It still has to pass the numeric gate, and this study does not promote it.

| Setup | Stake | Context | Trades | PF | Max DD | Ending | Published trades | Published PF | Published DD | Published ending | Improves | Gate |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| ema shares | $1,000 | off | 18 | 0.09 | -2.6% | $974 | 101 | 0.11 | -12.1% | $879 | no | no |
| ema shares | $5,000 | off | 18 | 0.09 | -2.6% | $4,870 | 101 | 0.11 | -12.1% | $4,396 | no | no |
| ema 0dte | $1,000 | off | 30 | 0.49 | -34.0% | $716 | 242 | 0.65 | -95.8% | $75 | no | no |
| ema 0dte | $5,000 | off | 30 | 0.49 | -6.8% | $4,716 | 283 | 0.64 | -26.1% | $3,725 | no | no |
| ema shares | $1,000 | on | 0 | n/a | 0.0% | $1,000 | 101 | 0.11 | -12.1% | $879 | no | no |
| ema shares | $5,000 | on | 0 | n/a | 0.0% | $5,000 | 101 | 0.11 | -12.1% | $4,396 | no | no |
| ema 0dte | $1,000 | on | 3 | 0.00 | -7.6% | $924 | 242 | 0.65 | -95.8% | $75 | no | no |
| ema 0dte | $5,000 | on | 3 | 0.00 | -1.5% | $4,924 | 283 | 0.64 | -26.1% | $3,725 | no | no |
| vwap_reversal shares | $1,000 | off | 457 | 0.13 | -47.5% | $525 | 908 | 0.11 | -70.3% | $297 | yes | no |
| vwap_reversal shares | $5,000 | off | 457 | 0.13 | -47.5% | $2,624 | 908 | 0.11 | -70.3% | $1,487 | yes | no |
| vwap_reversal 0dte | $1,000 | off | 1121 | 0.95 | -99.3% | $20 | 396 | 0.87 | -99.9% | $2 | yes | no |
| vwap_reversal 0dte | $5,000 | off | 1173 | 0.92 | -49.9% | $3,464 | 396 | 0.87 | -99.9% | $13 | yes | no |
| vwap_reversal shares | $1,000 | on | 222 | 0.10 | -28.7% | $713 | 908 | 0.11 | -70.3% | $297 | no | no |
| vwap_reversal shares | $5,000 | on | 222 | 0.10 | -28.7% | $3,566 | 908 | 0.11 | -70.3% | $1,487 | no | no |
| vwap_reversal 0dte | $1,000 | on | 462 | 0.88 | -98.9% | $22 | 396 | 0.87 | -99.9% | $2 | yes | no |
| vwap_reversal 0dte | $5,000 | on | 496 | 0.89 | -36.6% | $4,018 | 396 | 0.87 | -99.9% | $13 | yes | no |
| vwap_extension shares | $1,000 | off | 72 | 0.63 | -5.4% | $964 | 812 | 0.39 | -60.8% | $393 | yes | no |
| vwap_extension shares | $5,000 | off | 72 | 0.63 | -5.4% | $4,820 | 812 | 0.39 | -60.8% | $1,963 | yes | no |
| vwap_extension 0dte | $1,000 | off | 121 | 2.21 | -14.1% | $4,488 | 2355 | 1.55 | -16.2% | $32,844 | no | no |
| vwap_extension 0dte | $5,000 | off | 121 | 2.21 | -5.0% | $8,488 | 2355 | 1.55 | -16.2% | $36,844 | no | no |
| vwap_extension shares | $1,000 | on | 26 | 0.69 | -2.6% | $989 | 812 | 0.39 | -60.8% | $393 | yes | no |
| vwap_extension shares | $5,000 | on | 26 | 0.69 | -2.6% | $4,946 | 812 | 0.39 | -60.8% | $1,963 | yes | no |
| vwap_extension 0dte | $1,000 | on | 45 | 1.49 | -15.8% | $1,630 | 2355 | 1.55 | -16.2% | $32,844 | no | no |
| vwap_extension 0dte | $5,000 | on | 45 | 1.49 | -5.1% | $5,630 | 2355 | 1.55 | -16.2% | $36,844 | no | no |

A yes in the last columns is the frozen comparison, not a profit. Every yes book still finished below its starting stake. The published 2 SD continuation 0 DTE book, the one that had cleared the gate at $32,844 from $1,000 and $36,844 from $5,000, fell to $4,488 (121 trades, profit factor 2.21, context off) and $1,630 (45 trades, profit factor 1.49, context on). Both miss the trade count and the gate. The share filters lost less than the published share losses: reversal shares finished at $525 and $2,624 instead of $297 and $1,487, and extension shares finished at $964 and $4,820 instead of $393 and $1,963. Profit factors are 0.13 and 0.63. They miss the gate. The EMA location filter left 0 share trades and 3 option trades. A filter that only loses less on fewer than 20 trades is not an improvement. None of these books was added to the live list.

Training accounts, from the same filtered signal list, are in `reports/candles.json`. The published training accounts are the ones already in the VWAP and EMA sections above. They were not replaced.

The drawing of the shapes is `reports/candlestick_patterns.png`. The guide is `docs/CANDLESTICK_PATTERNS.md`.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.

```
python3 -m webull_bot.chart_reads.research_candles
```
<!-- CANDLES_END -->

<!-- EMA_REVERSAL_START -->
### Reversal through the 9 EMA, the 20 EMA, and VWAP

Backtests only. Nothing was sent to a broker. Live trading stays off. The chop-breakout order rules were not changed. This variant was frozen before this score and does not replace the VWAP-confluence rejection gate. A long needs the prior bar in the bearish stack (9 EMA below the 20 EMA, and that close below session VWAP), then a green bar whose close is above the 9 EMA, the 20 EMA, and VWAP, then a next bar that also closes green. The fill is the open after that confirmation. The short is the mirror and buys a put. The price stop is one cent beyond the breakout bar. The ema rows exit on a close back across the 9 EMA, and the price stop still fills first on that bar. Swing, 1R, and 2R are the other targets, the same menu as the rejection study. The chop guard is not part of this variant. The cash share book is long only. The 0 DTE book takes both directions.

| Book | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 | Train $1,000 | Clears |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| reversal_swing_shares | 432 | 16.0% | 54.7% | 0.16 | -5.70 | -45.4% | $546 | $2,730 | $602 | no |
| reversal_swing_0dte | 1084 | 52.4% | 51.4% | 1.04 | 0.49 | -45.6% | $1,783 | $5,783 | $872 | no |
| reversal_ema_shares | 435 | 17.2% | 45.1% | 0.25 | -5.03 | -42.7% | $573 | $2,867 | $568 | no |
| reversal_ema_0dte | 1165 | 27.6% | 21.1% | 1.42 | 1.12 | -61.0% | $10,757 | $14,757 | -$0 | no |
| reversal_r1_shares | 434 | 30.6% | 61.6% | 0.28 | -4.63 | -44.1% | $559 | n/a | $564 | no |
| reversal_r1_0dte | 1042 | 46.8% | 42.0% | 1.22 | 1.33 | -26.0% | $6,345 | n/a | $1,290 | yes, not promoted |
| reversal_r2_shares | 434 | 29.7% | 52.6% | 0.38 | -3.75 | -44.4% | $556 | n/a | $602 | no |
| reversal_r2_0dte | 991 | 33.9% | 27.3% | 1.37 | 1.19 | -33.4% | $12,073 | n/a | $3,746 | no |
| QQQ reversal_swing_shares | 14 | 14.3% | 68.4% | 0.08 | -8.02 | -2.8% | $972 | $4,862 | $1,000 | no |
| QQQ reversal_swing_0dte | 32 | 53.1% | 46.1% | 1.33 | 1.74 | -16.9% | $1,208 | $5,208 | $1,000 | no |

reversal_r1_0dte clears the holdout arithmetic and is not promoted. Training finished at $1,290, profit factor 1.02, under the 1.10 line. The swing target is the one the rejection gate uses, and that 0 DTE book misses the profit factor and the drawdown. The close-back-across-the-9 exit finished the holdout at $10,757 and wiped the training account. The 2R 0 DTE holdout misses the drawdown line. None of these replace the gate.

Holdout is a fresh account from 2022-01-01 through 2026-10-06. Train is a fresh account through 2021-12-31. QQQ stays off the gate while its Dukascopy file is short. Dukascopy publishes QQQUSUSD, but this cache has 1038 day files, short of the 2017+ file. The QQQ rows are Yahoo 5-minute bars from 2026-08-14 through 2026-10-07, about 60 days. That sample cannot clear 300 out-of-sample trades. It is not the gate.

reversal_swing_shares random holdout, seed 17, 255 trades, ending $716, profit factor 0.05, Sharpe -6.38. reversal_swing_0dte random holdout, seed 17, 575 trades, ending $6, profit factor 0.80, Sharpe -0.45.

On Yahoo 5-minute SPY for 2026-10-07 the reversal rule marks 0 signals. The session runs 09:30 through 12:10 ET. The rule was not loosened.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.

```
python3 -m webull_bot.chart_reads.research_ema_reject reversal
```
<!-- EMA_REVERSAL_END -->

<!-- VWAP_QUALITY_START -->
## VWAP continuation quality, caps, and confirmation

Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox book `vwap_band_15m` was not changed. The caps, quality filters, and confirmation rules were frozen before this score. Train is a fresh account through 2021-12-31. The holdout is a fresh account from 2022-01-01 through 2026-10-06. 2026-10-07 is the illustration, not part of the Dukascopy score.

SPY is Dukascopy 1-minute bids, 2017-02-16 through 2026-10-06, 2416 sessions, 0 days missing. QQQ Dukascopy starts 2017-02-16, and 96.7% of training signals have a QQQ bar. QQQ confirmation is in the family. Training medians, frozen before the account runs: stretch 0.1639 ATR, relative volume 0.7564, stop distance 0.9866 ATR (2703 training signals).

An end-of-day top-N would look ahead. It is not in the family. Thresholds are the training median, and both the tight and the wide stop were scored. The 5-minute follow-through walks 5-minute bars. Every other row walks 15-minute bars, the same path as the published extension book. A 2 SD extension close is already beyond the band, so it is already on that side of VWAP. The 9/20-plus-VWAP rule then asks only for the 9/20 stack. Both rows are still reported. False discovery is Benjamini-Hochberg on the holdout mean trade pnl, q at most 0.10. The original uncapped extension is the baseline and is not in that family.

Raw extension signals, train: mean 2.21 per session, 16.2% of sessions above 3, 1.1% above 5, max 7 (1222 sessions). Holdout signals: mean 2.33, 18.3% above 3, 1.3% above 5, max 8 (1194 sessions). The $1,000 0 DTE account, after overlap, IV, and premium skips, train: mean 0.21 trades per session, 0.3% of sessions above 3, 0.0% above 5. Holdout account: mean 1.97, 8.1% above 3, 0.1% above 5.

### Holdout, fresh $1,000

Trades per day use every session in the window, including sessions with no trade. Win rate is next to the break-even win rate. Gate is the published 300-trade, 1.10, 0.40, -30% test on this account.

| Book | Trades | Trades/day | >3 | >5 | Win | Break-even | PF | Sharpe | Max DD | $1,000 | Gate | q |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| baseline | 2355 | 1.97 | 8.1% | 0.1% | 50.0% | 39.3% | 1.55 | 2.66 | -16.2% | $32,844 | yes | n/a |
| cap3 | 2134 | 1.79 | 0.0% | 0.0% | 50.8% | 39.8% | 1.57 | 2.55 | -15.6% | $31,497 | yes | 0.000 |
| cap4 | 2284 | 1.91 | 5.4% | 0.0% | 50.3% | 39.3% | 1.56 | 2.55 | -17.0% | $32,722 | yes | 0.000 |
| cap5 | 2341 | 1.96 | 7.9% | 0.0% | 50.1% | 39.3% | 1.55 | 2.65 | -16.3% | $32,849 | yes | 0.000 |
| stop_two_losses | 2173 | 1.82 | 3.4% | 0.0% | 50.4% | 39.9% | 1.53 | 2.56 | -17.1% | $30,081 | yes | 0.000 |
| stop_first_win | 1674 | 1.40 | 1.6% | 0.0% | 50.1% | 40.1% | 1.50 | 2.31 | -19.9% | $23,078 | yes | 0.000 |
| stretch | 1203 | 1.01 | 0.8% | 0.0% | 50.0% | 36.0% | 1.78 | 2.41 | -20.2% | $24,798 | yes | 0.000 |
| relvol | 1917 | 1.61 | 3.4% | 0.0% | 49.6% | 38.7% | 1.56 | 2.64 | -18.1% | $30,034 | yes | 0.000 |
| ema_stack | 1634 | 1.37 | 2.3% | 0.0% | 49.7% | 39.0% | 1.54 | 2.58 | -9.8% | $21,900 | yes | 0.000 |
| htf60 | 1281 | 1.07 | 1.9% | 0.0% | 50.0% | 41.3% | 1.42 | 1.62 | -30.6% | $13,765 | no | 0.000 |
| qqq | 1322 | 1.11 | 1.1% | 0.0% | 48.6% | 37.3% | 1.59 | 2.29 | -11.3% | $23,048 | yes | 0.000 |
| skip_lunch | 1815 | 1.52 | 2.1% | 0.0% | 50.0% | 39.1% | 1.56 | 2.46 | -16.8% | $26,376 | yes | 0.000 |
| risk_tight | 1276 | 1.07 | 2.8% | 0.1% | 52.2% | 45.5% | 1.31 | 1.82 | -14.0% | $7,966 | yes | 0.000 |
| risk_wide | 1257 | 1.05 | 0.5% | 0.0% | 47.7% | 35.6% | 1.65 | 2.28 | -29.6% | $26,444 | yes | 0.000 |
| confirm_15m | 960 | 0.80 | 0.0% | 0.0% | 47.4% | 33.6% | 1.78 | 1.99 | -14.5% | $20,901 | yes | 0.000 |
| confirm_5m | 1724 | 1.44 | 1.3% | 0.0% | 49.5% | 36.9% | 1.68 | 2.52 | -10.7% | $31,747 | yes | 0.000 |
| ema_vwap | 1634 | 1.37 | 2.3% | 0.0% | 49.7% | 39.0% | 1.54 | 2.58 | -9.8% | $21,900 | yes | 0.000 |
| early_15m | 1706 | 1.43 | 2.7% | 0.1% | 49.8% | 38.1% | 1.62 | 2.49 | -10.4% | $25,681 | yes | 0.000 |
| stack | 703 | 0.59 | 0.3% | 0.0% | 50.2% | 41.3% | 1.43 | 1.56 | -19.1% | $7,577 | yes | 0.000 |
| stretch_relvol | 973 | 0.81 | 0.3% | 0.0% | 49.4% | 35.5% | 1.78 | 2.41 | -22.6% | $22,083 | yes | 0.000 |
| stack_cap3 | 695 | 0.58 | 0.0% | 0.0% | 50.5% | 41.4% | 1.44 | 1.57 | -19.1% | $7,671 | yes | 0.000 |
| stack_cap5 | 703 | 0.59 | 0.3% | 0.0% | 50.2% | 41.3% | 1.43 | 1.56 | -19.1% | $7,577 | yes | 0.000 |
| confirm15_cap3 | 958 | 0.80 | 0.0% | 0.0% | 47.3% | 33.5% | 1.78 | 1.99 | -14.5% | $20,834 | yes | 0.000 |
| ema_vwap_cap3 | 1556 | 1.30 | 0.0% | 0.0% | 49.9% | 39.1% | 1.55 | 2.51 | -15.8% | $21,579 | yes | 0.000 |

### Holdout, fresh $5,000

One contract either way. When the debit already fits in $1,000, the extra cash sits idle and the dollar profit matches.

| Book | Trades | Trades/day | >3 | >5 | Win | Break-even | PF | Sharpe | Max DD | $5,000 | Gate | q |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| baseline | 2355 | 1.97 | 8.1% | 0.1% | 50.0% | 39.3% | 1.55 | 3.24 | -9.7% | $36,844 | yes | n/a |
| cap3 | 2134 | 1.79 | 0.0% | 0.0% | 50.8% | 39.8% | 1.57 | 3.21 | -7.5% | $35,497 | yes | 0.000 |
| cap4 | 2284 | 1.91 | 5.4% | 0.0% | 50.3% | 39.3% | 1.56 | 3.19 | -10.0% | $36,722 | yes | 0.000 |
| cap5 | 2341 | 1.96 | 7.9% | 0.0% | 50.1% | 39.3% | 1.55 | 3.23 | -9.7% | $36,849 | yes | 0.000 |
| stop_two_losses | 2173 | 1.82 | 3.4% | 0.0% | 50.4% | 39.9% | 1.53 | 3.08 | -10.0% | $34,081 | yes | 0.000 |
| stop_first_win | 1674 | 1.40 | 1.6% | 0.0% | 50.1% | 40.1% | 1.50 | 2.83 | -10.1% | $27,078 | yes | 0.000 |
| stretch | 1203 | 1.01 | 0.8% | 0.0% | 50.0% | 36.0% | 1.78 | 2.97 | -10.7% | $28,798 | yes | 0.000 |
| relvol | 1917 | 1.61 | 3.4% | 0.0% | 49.6% | 38.7% | 1.56 | 3.10 | -10.6% | $34,034 | yes | 0.000 |
| ema_stack | 1634 | 1.37 | 2.3% | 0.0% | 49.7% | 39.0% | 1.54 | 2.98 | -5.0% | $25,900 | yes | 0.000 |
| htf60 | 1281 | 1.07 | 1.9% | 0.0% | 50.0% | 41.3% | 1.42 | 1.92 | -10.8% | $17,765 | yes | 0.000 |
| qqq | 1322 | 1.11 | 1.1% | 0.0% | 48.6% | 37.3% | 1.59 | 2.74 | -4.9% | $27,048 | yes | 0.000 |
| skip_lunch | 1815 | 1.52 | 2.1% | 0.0% | 50.0% | 39.1% | 1.56 | 2.93 | -9.2% | $30,376 | yes | 0.000 |
| risk_tight | 1276 | 1.07 | 2.8% | 0.1% | 52.2% | 45.5% | 1.31 | 1.93 | -8.4% | $11,966 | yes | 0.000 |
| risk_wide | 1257 | 1.05 | 0.5% | 0.0% | 47.7% | 35.6% | 1.65 | 2.78 | -15.0% | $30,444 | yes | 0.000 |
| confirm_15m | 960 | 0.80 | 0.0% | 0.0% | 47.4% | 33.6% | 1.78 | 2.74 | -6.3% | $24,901 | yes | 0.000 |
| confirm_5m | 1724 | 1.44 | 1.3% | 0.0% | 49.5% | 36.9% | 1.68 | 3.20 | -6.6% | $35,747 | yes | 0.000 |
| ema_vwap | 1634 | 1.37 | 2.3% | 0.0% | 49.7% | 39.0% | 1.54 | 2.98 | -5.0% | $25,900 | yes | 0.000 |
| early_15m | 1706 | 1.43 | 2.7% | 0.1% | 49.8% | 38.1% | 1.62 | 3.05 | -4.4% | $29,681 | yes | 0.000 |
| stack | 703 | 0.59 | 0.3% | 0.0% | 50.2% | 41.3% | 1.43 | 1.70 | -7.5% | $11,577 | yes | 0.000 |
| stretch_relvol | 973 | 0.81 | 0.3% | 0.0% | 49.4% | 35.5% | 1.78 | 2.86 | -11.8% | $26,083 | yes | 0.000 |
| stack_cap3 | 695 | 0.58 | 0.0% | 0.0% | 50.5% | 41.4% | 1.44 | 1.72 | -7.5% | $11,671 | yes | 0.000 |
| stack_cap5 | 703 | 0.59 | 0.3% | 0.0% | 50.2% | 41.3% | 1.43 | 1.70 | -7.5% | $11,577 | yes | 0.000 |
| confirm15_cap3 | 958 | 0.80 | 0.0% | 0.0% | 47.3% | 33.5% | 1.78 | 2.73 | -6.5% | $24,834 | yes | 0.000 |
| ema_vwap_cap3 | 1556 | 1.30 | 0.0% | 0.0% | 49.9% | 39.1% | 1.55 | 2.93 | -5.3% | $25,579 | yes | 0.000 |

### Training account, through 2021-12-31

The published extension book died here: the $1,000 training account stopped at $1. Survives means the $1,000 account never hit that stop and finished above $1. A cap of 3 finished at $1.22 with a -99.9% drawdown, so it did not trip the stop and it still fails the gate.

| Book | Trades | PF | Sharpe | Max DD | $1,000 | $5,000 | Gate | Survives |
|---|---:|---:|---:|---:|---:|---:|---|---|
| baseline | 255 | 0.56 | -1.11 | -99.9% | $1 | $7,554 | no | no |
| cap3 | 239 | 0.54 | -0.66 | -99.9% | $1 | $7,779 | no | yes |
| cap4 | 255 | 0.56 | -1.11 | -99.9% | $1 | $7,499 | no | no |
| cap5 | 255 | 0.56 | -1.11 | -99.9% | $1 | $7,265 | no | no |
| stop_two_losses | 241 | 0.55 | -1.24 | -99.9% | $1 | $7,553 | no | no |
| stop_first_win | 1710 | 1.03 | 0.49 | -76.8% | $1,779 | $5,779 | no | yes |
| stretch | 1223 | 1.10 | 0.73 | -73.7% | $3,300 | $7,300 | no | yes |
| relvol | 891 | 1.19 | 1.29 | -40.1% | $4,519 | $8,519 | no | yes |
| ema_stack | 1522 | 1.07 | 0.66 | -65.6% | $2,742 | $6,742 | no | yes |
| htf60 | 1243 | 0.99 | 0.42 | -86.8% | $875 | $4,836 | no | yes |
| qqq | 1167 | 1.19 | 1.06 | -52.6% | $5,100 | $9,100 | no | yes |
| skip_lunch | 1748 | 1.12 | 0.80 | -83.4% | $4,509 | $8,509 | no | yes |
| risk_tight | 1230 | 1.03 | 0.41 | -56.6% | $1,516 | $5,516 | no | yes |
| risk_wide | 1233 | 1.08 | 0.65 | -84.6% | $3,134 | $7,134 | no | yes |
| confirm_15m | 920 | 1.10 | 0.66 | -55.5% | $2,941 | $6,941 | no | yes |
| confirm_5m | 1632 | 1.07 | 0.83 | -40.8% | $3,307 | $7,307 | no | yes |
| ema_vwap | 1522 | 1.07 | 0.66 | -65.6% | $2,742 | $6,742 | no | yes |
| early_15m | 1731 | 1.08 | 0.69 | -73.3% | $3,216 | $7,216 | no | yes |
| stack | 670 | 0.96 | 0.27 | -92.8% | $663 | $4,663 | no | yes |
| stretch_relvol | 490 | 1.24 | 1.16 | -39.7% | $3,662 | $7,662 | no | yes |
| stack_cap3 | 667 | 0.92 | 0.15 | -96.4% | $304 | $4,593 | no | yes |
| stack_cap5 | 670 | 0.96 | 0.27 | -92.8% | $663 | $4,663 | no | yes |
| confirm15_cap3 | 916 | 1.11 | 0.69 | -53.3% | $3,091 | $7,091 | no | yes |
| ema_vwap_cap3 | 1473 | 1.08 | 0.67 | -67.9% | $2,813 | $6,813 | no | yes |

Every family member with at least 30 holdout trades has a false-discovery q far below 0.10. None clears the published gate on the fresh $1,000 training account. Training drawdown is worse than -30% on every row. The holdout gate is not what stops them. The sandbox forward test is unchanged. The baseline $1,000 training account finished at $1 and hit the bust stop. The mildest training drawdown among rows that otherwise clear the profit-factor, Sharpe, and trade-count legs is stretch plus relative volume, at -39.7%.

### 2026-10-07 confirmation

Yahoo 15-minute and 5-minute cache, the same tape as the sandbox dry run. This day is after the holdout and is not in the score. A filter keeps a signal when it still accepts it. A delayed fill is a different trade. The 13:30 long can pass the 15-minute follow-through only when the next 15-minute bar has closed.

| Signal | Side | 15m follow-through | 5m follow-through | 9/20 and VWAP | Before 10:30 needs 15m |
|---|---|---|---|---|---|
| 10:00 | short | no | no | yes | no |
| 10:30 | short | no | yes | yes | yes |
| 11:30 | long | no | yes | no | yes |
| 13:30 awaiting fill | long | no | yes | no | yes |

15-minute follow-through drops the 10:00 short, drops the 10:30 short, drops the 11:30 long, and drops the 13:30 long.
5-minute follow-through drops the 10:00 short, keeps the 10:30 short, keeps the 11:30 long, and keeps the 13:30 long.
9/20 plus VWAP keeps the 10:00 short, keeps the 10:30 short, drops the 11:30 long, and drops the 13:30 long.
Before-10:30 confirmation drops the 10:00 short, keeps the 10:30 short, keeps the 11:30 long, and keeps the 13:30 long.
No frozen confirmation rule removes both the 10:00 and 10:30 shorts and still accepts both the 11:30 and 13:30 longs. The definitions were not loosened after that count.

Seed 17 random baseline, matched to 2782 holdout extension signals: 1401 trades, profit factor 0.94, Sharpe 0.18, max drawdown -99.6%, $1,000 ended $6, $5,000 ended $3,460.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum. `vwap_band_15m` is unchanged.

```
python3 -m webull_bot.chart_reads.research_vwap_quality
```
<!-- VWAP_QUALITY_END -->

<!-- VWAP_EXPIRY_START -->
### VWAP extension by option expiry

Backtests only. Nothing was sent to a broker. Live trading stays off. The table is the original uncapped 2 SD continuation, 1R, one position. The quality filters are not crossed with it. No contract clears the published gate on both the train window and the holdout, after the seven-contract false-discovery check. 0dte-flat has the highest holdout Sharpe and is not a promotion. On that contract the $1,000 holdout finished at $32,844 (2355 trades, 1.97 a day, win 50.0% against break-even 39.3%, profit factor 1.55, Sharpe 2.66, drawdown -16.2%). Training finished at $1. From $5,000 the holdout finished at $36,844 and training at $7,554. Holdout same-day round trips 2355, overnight holds 0, worst same-day count in any five sessions 18, five-session windows over 3 day trades 1189 of 1190. A $1,000 or $5,000 margin account is under the $25,000 pattern-day-trader line. This test is a cash account: it does not refuse the fourth day trade, and a sale settles the next session. An overnight hold that closes on a later session is not a day trade. The debit stays invested until that exit. vwap_band_15m was not changed.

| Contract | Window | Trades/day | Win | Break-even | PF | Sharpe | Max DD | $1k end | $5k end | Gate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0dte-flat | train | 0.21 | 36.5% | 50.4% | 0.56 | -1.11 | -99.9% | $1 | $7,554 | no |
| 0dte-flat | holdout | 1.97 | 50.0% | 39.3% | 1.55 | 2.66 | -16.2% | $32,844 | $36,844 | yes |
| 1dte-flat | train | 0.17 | 41.9% | 59.7% | 0.49 | -1.47 | -97.2% | $29 | $130 | no |
| 1dte-flat | holdout | 1.97 | 50.8% | 49.7% | 1.04 | 0.76 | -77.2% | $3,985 | $8,081 | no |
| 1dte-overnight | train | 0.09 | 45.3% | 69.3% | 0.37 | -1.08 | -98.3% | $18 | $119 | no |
| 1dte-overnight | holdout | 0.18 | 50.5% | 53.1% | 0.90 | 0.07 | -97.7% | $57 | $80 | no |
| 3dte-flat | train | 0.14 | 42.9% | 63.1% | 0.44 | -1.52 | -93.0% | $71 | $177 | no |
| 3dte-flat | holdout | 0.09 | 49.1% | 54.2% | 0.81 | -0.30 | -87.3% | $192 | $190 | no |
| 3dte-overnight | train | 0.09 | 44.3% | 68.9% | 0.36 | -1.42 | -94.3% | $59 | $113 | no |
| 3dte-overnight | holdout | 0.11 | 54.8% | 58.5% | 0.86 | -0.17 | -93.6% | $97 | $187 | no |
| 7dte-flat | train | 0.09 | 39.6% | 68.3% | 0.30 | -2.03 | -88.2% | $119 | $201 | no |
| 7dte-flat | holdout | 0.02 | 42.3% | 67.1% | 0.36 | -0.78 | -72.1% | $279 | $332 | no |
| 7dte-overnight | train | 0.08 | 44.8% | 72.1% | 0.31 | -1.65 | -88.7% | $118 | $192 | no |
| 7dte-overnight | holdout | 0.02 | 35.0% | 63.6% | 0.31 | -0.84 | -72.3% | $277 | $288 | no |

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`.

```
python3 -m webull_bot.chart_reads.research_vwap_expiry
```
<!-- VWAP_EXPIRY_END -->
