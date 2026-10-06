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

