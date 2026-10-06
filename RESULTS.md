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
