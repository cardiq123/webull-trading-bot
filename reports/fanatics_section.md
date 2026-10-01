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
