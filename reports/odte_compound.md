# QQQ Aggressive Compound

Backtest only. Nothing was sent to a broker. Live trading stays off. The sandbox forward books were not changed.

QQQ Aggressive Compound spends a fixed fraction of current equity on premium. 10% is the primary fraction. The signal, the 1R stop and target, and the same-day 15:45 flatten match the other QQQ Aggressive scores. The account starts at $2,500.

The fixed 1-contract book and the 1-per-$2,500 tier clear the usual gate on both windows. No compound fraction clears both windows. Holdout gate only: 5% of equity 1 DTE.

At 10% and 1 DTE, Holdout $390,295 on 1128 trades, win 49.3%, profit factor 1.46, Sharpe 2.68, max drawdown -33.8%, 12-month median $18,417, 10th percentile $7,408, P($10k in 4/8/12 months) 7.9% / 60.2% / 86.2%, median days to $10k 230, P(ruin) 0.0%, gate no (drawdown -33.8%). Train $673,540 on 2873 trades, win 50.9%, profit factor 1.31, Sharpe 1.58, max drawdown -75.0%, 12-month median $8,728, 10th percentile $3,349, P($10k in 4/8/12 months) 8.6% / 32.6% / 49.7%, median days to $10k 232, P(ruin) 0.0%, gate no (drawdown -75.0%).

The fixed 1-contract 1 DTE book, on this same reach clock, Holdout $18,069 on 1128 trades, win 49.3%, profit factor 1.40, Sharpe 2.49, max drawdown -18.6%, 12-month median $8,247, 10th percentile $6,279, P($10k in 4/8/12 months) 0.0% / 11.4% / 20.0%, median days to $10k 310, P(ruin) 0.0%, gate yes. Train $19,797 on 2873 trades, win 50.9%, profit factor 1.31, Sharpe 1.92, max drawdown -27.2%, 12-month median $4,571, 10th percentile $3,108, P($10k in 4/8/12 months) 0.0% / 0.0% / 0.0%, median days to $10k n/a, P(ruin) 0.0%, gate yes.

The 1-contract-per-$2,500 tier, on this same reach clock, Holdout $61,877 on 1128 trades, win 49.3%, profit factor 1.42, Sharpe 2.57, max drawdown -24.8%, 12-month median $10,464, 10th percentile $6,816, P($10k in 4/8/12 months) 2.0% / 31.3% / 60.1%, median days to $10k 284, P(ruin) 0.0%, gate yes. Train $69,954 on 2873 trades, win 50.9%, profit factor 1.32, Sharpe 1.83, max drawdown -27.2%, 12-month median $4,571, 10th percentile $3,108, P($10k in 4/8/12 months) 1.6% / 5.5% / 16.7%, median days to $10k 290, P(ruin) 0.0%, gate yes.

The other 1 DTE fractions. 5% of equity, 1 DTE: holdout $50,939 on 1118 trades, drawdown -25.7%, gate yes. Train $304,432 on 2873 trades, drawdown -39.8%, gate no (drawdown -39.8%). 15% of equity, 1 DTE: holdout $515,943 on 1128 trades, drawdown -49.1%, gate no (drawdown -49.1%). Train $770,018 on 2873 trades, drawdown -88.6%, gate no (drawdown -88.6%). 20% of equity, 1 DTE: holdout $622,272 on 1128 trades, drawdown -61.0%, gate no (drawdown -61.0%). Train $773,765 on 2872 trades, drawdown -94.9%, gate no (drawdown -94.9%).

0 DTE at 1.67 times the prior close and a 1 cent market, same fractions. 5%: holdout $82,489 on 1128 trades, gate no (drawdown -54.4%); train $111,948 on 2804 trades, gate no (drawdown -88.1%). 10%: holdout $294,657 on 1128 trades, gate no (drawdown -85.1%); train $17.68 on 481 trades, gate no (PF 0.762<1.10, Sharpe -0.38<0.40, drawdown -99.3%). 15%: holdout $325,149 on 1128 trades, gate no (drawdown -90.4%); train $11.52 on 412 trades, gate no (PF 0.714<1.10, Sharpe -0.01<0.40, drawdown -99.5%). 20%: holdout $421,657 on 1128 trades, gate no (drawdown -93.2%); train $4.36 on 175 trades, gate no (trades 175<300, PF 0.550<1.10, Sharpe -0.58<0.40, drawdown -99.8%).

1 DTE at 10%, with the prior close moved 20% either way. 0.80x holdout $786,732 on 1128 trades (gate no (drawdown -35.3%)), train $1,075,099 on 2873 trades (gate no (drawdown -77.5%)). base holdout $390,295 on 1128 trades (gate no (drawdown -33.8%)), train $673,540 on 2873 trades (gate no (drawdown -75.0%)). 1.20x holdout $70,167 on 1128 trades (gate no (drawdown -35.9%)), train $266,286 on 2873 trades (gate no (drawdown -71.0%)).

The 50-contract cap binds on these cells. 5% of equity 1 DTE: holdout 0 of 1118 fills (0.0%) stopped at 50 contracts, train 382 of 2873 fills (13.3%) stopped at 50 contracts. 10% of equity 1 DTE: holdout 258 of 1128 fills (22.9%) stopped at 50 contracts, train 1353 of 2873 fills (47.1%) stopped at 50 contracts. 15% of equity 1 DTE: holdout 461 of 1128 fills (40.9%) stopped at 50 contracts, train 2015 of 2873 fills (70.1%) stopped at 50 contracts. 20% of equity 1 DTE: holdout 677 of 1128 fills (60.0%) stopped at 50 contracts, train 2050 of 2872 fills (71.4%) stopped at 50 contracts. 5% of equity 0 DTE: holdout 57 of 1128 fills (5.1%) stopped at 50 contracts, train 100 of 2804 fills (3.6%) stopped at 50 contracts. 10% of equity 0 DTE: holdout 268 of 1128 fills (23.8%) stopped at 50 contracts, train 4 of 481 fills (0.8%) stopped at 50 contracts. 15% of equity 0 DTE: holdout 399 of 1128 fills (35.4%) stopped at 50 contracts, train 5 of 412 fills (1.2%) stopped at 50 contracts. 20% of equity 0 DTE: holdout 637 of 1128 fills (56.5%) stopped at 50 contracts, train 4 of 175 fills (2.3%) stopped at 50 contracts.

## The rule, written down first

QQQ Aggressive Compound. The signal is the QQQ 15-minute 2 SD VWAP continuation, a 1R underlying stop and target, a 10-minute entry window, and a sale the same day at the stop, the target, or the 15:45 bar. The scored fill is the next open. One position. At most 5 fills a day. Fresh $2,500. The primary expiry is 1 DTE at the unscaled prior close and a 1 cent market, the same pricing as the live 1 DTE book. 0 DTE at 1.67 times the prior close and a 1 cent market is the reference. Each fill spends a fixed fraction f of current equity on premium. Current equity is settled cash plus credits due. Credits due are sale proceeds that have not settled. Credits whose settlement date is this session are added to settled cash first, before this fill's debit is subtracted. contracts = floor(f * equity / (ask * 100)). If that rounds to 0, buy 1 contract when 1 contract costs at most 2f of equity, otherwise skip. Cost is ask * 100. Cap at 50 contracts. If the whole ticket does not fit settled cash, skip it. The size is not cut down. The fractions are 5%, 10%, 15%, and 20%. 10% is the primary. The 1 DTE 10% cell is also scored at 0.80 times and at 1.20 times the prior close.

Train is 2017-02-16 through 2023-12-31. Holdout is a fresh account from 2024-01-01 through 2026-10-06. Ending, win rate, profit factor, Sharpe, max drawdown, and the gate are that one account. The median, the 10th percentile, the three reach rates, the median days, and P(ruin) start a fresh $2,500 on every later session that still has that many months inside the window. Median days counts the starts that do reach $10,000 inside 12 months. Reach is equity of $10,000. Ruin is equity under $500. The usual gate is at least 300 trades, profit factor at least 1.10, Sharpe at least 0.40, and max drawdown no worse than -30%. The formal pass is the holdout row.

## 1 DTE compared with one contract and the $2,500 tier

| Sizing | Expiry | IV | Fraction | Window | Trades | Win | PF | Sharpe | Max DD | Ending | Median 12m | P10 12m | P($10k 4m) | P($10k 8m) | P($10k 12m) | Median days | P(ruin) | Gate |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 contract | 1 DTE | prior close, 1 cent | 1 contract | train | 2873 | 50.9% | 1.31 | 1.92 | -27.2% | $19,797 | $4,571 | $3,108 | 0.0% | 0.0% | 0.0% | n/a | 0.0% | yes |
| 1 contract | 1 DTE | prior close, 1 cent | 1 contract | holdout | 1128 | 49.3% | 1.40 | 2.49 | -18.6% | $18,069 | $8,247 | $6,279 | 0.0% | 11.4% | 20.0% | 310 | 0.0% | yes |
| 1 per $2,500 | 1 DTE | prior close, 1 cent | 1 per $2,500 | train | 2873 | 50.9% | 1.32 | 1.83 | -27.2% | $69,954 | $4,571 | $3,108 | 1.6% | 5.5% | 16.7% | 290 | 0.0% | yes |
| 1 per $2,500 | 1 DTE | prior close, 1 cent | 1 per $2,500 | holdout | 1128 | 49.3% | 1.42 | 2.57 | -24.8% | $61,877 | $10,464 | $6,816 | 2.0% | 31.3% | 60.1% | 284 | 0.0% | yes |
| 5% of equity | 1 DTE | prior close, 1 cent | 5% | train | 2873 | 50.9% | 1.35 | 2.05 | -39.8% | $304,432 | $4,980 | $2,872 | 0.0% | 0.1% | 11.9% | 330 | 0.0% | no (drawdown -39.8%) |
| 5% of equity | 1 DTE | prior close, 1 cent | 5% | holdout | 1118 | 49.3% | 1.35 | 2.62 | -25.7% | $50,939 | $7,752 | $5,603 | 0.0% | 10.8% | 23.3% | 297 | 0.0% | yes |
| 10% of equity | 1 DTE | prior close, 1 cent | 10% | train | 2873 | 50.9% | 1.31 | 1.58 | -75.0% | $673,540 | $8,728 | $3,349 | 8.6% | 32.6% | 49.7% | 232 | 0.0% | no (drawdown -75.0%) |
| 10% of equity | 1 DTE | prior close, 1 cent | 10% | holdout | 1128 | 49.3% | 1.46 | 2.68 | -33.8% | $390,295 | $18,417 | $7,408 | 7.9% | 60.2% | 86.2% | 230 | 0.0% | no (drawdown -33.8%) |
| 15% of equity | 1 DTE | prior close, 1 cent | 15% | train | 2873 | 50.9% | 1.32 | 1.41 | -88.6% | $770,018 | $14,013 | $2,990 | 23.6% | 46.3% | 60.3% | 178 | 3.0% | no (drawdown -88.6%) |
| 15% of equity | 1 DTE | prior close, 1 cent | 15% | holdout | 1128 | 49.3% | 1.41 | 2.33 | -49.1% | $515,943 | $46,197 | $11,479 | 36.1% | 77.6% | 97.5% | 172 | 0.0% | no (drawdown -49.1%) |
| 20% of equity | 1 DTE | prior close, 1 cent | 20% | train | 2872 | 50.9% | 1.32 | 1.29 | -94.9% | $773,765 | $21,648 | $2,448 | 33.3% | 53.4% | 64.4% | 145 | 12.5% | no (drawdown -94.9%) |
| 20% of equity | 1 DTE | prior close, 1 cent | 20% | holdout | 1128 | 49.3% | 1.41 | 2.23 | -61.0% | $622,272 | $95,873 | $11,902 | 51.0% | 88.6% | 100.0% | 147 | 0.0% | no (drawdown -61.0%) |

## All pre-registered fractions

1 DTE uses the unscaled prior close. 0 DTE uses 1.67 times that close. Both use a 1 cent market.

| Sizing | Expiry | IV | Fraction | Window | Trades | Win | PF | Sharpe | Max DD | Ending | Median 12m | P10 12m | P($10k 4m) | P($10k 8m) | P($10k 12m) | Median days | P(ruin) | Gate |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 5% of equity | 1 DTE | prior close, 1 cent | 5% | train | 2873 | 50.9% | 1.35 | 2.05 | -39.8% | $304,432 | $4,980 | $2,872 | 0.0% | 0.1% | 11.9% | 330 | 0.0% | no (drawdown -39.8%) |
| 5% of equity | 1 DTE | prior close, 1 cent | 5% | holdout | 1118 | 49.3% | 1.35 | 2.62 | -25.7% | $50,939 | $7,752 | $5,603 | 0.0% | 10.8% | 23.3% | 297 | 0.0% | yes |
| 10% of equity | 1 DTE | prior close, 1 cent | 10% | train | 2873 | 50.9% | 1.31 | 1.58 | -75.0% | $673,540 | $8,728 | $3,349 | 8.6% | 32.6% | 49.7% | 232 | 0.0% | no (drawdown -75.0%) |
| 10% of equity | 1 DTE | prior close, 1 cent | 10% | holdout | 1128 | 49.3% | 1.46 | 2.68 | -33.8% | $390,295 | $18,417 | $7,408 | 7.9% | 60.2% | 86.2% | 230 | 0.0% | no (drawdown -33.8%) |
| 15% of equity | 1 DTE | prior close, 1 cent | 15% | train | 2873 | 50.9% | 1.32 | 1.41 | -88.6% | $770,018 | $14,013 | $2,990 | 23.6% | 46.3% | 60.3% | 178 | 3.0% | no (drawdown -88.6%) |
| 15% of equity | 1 DTE | prior close, 1 cent | 15% | holdout | 1128 | 49.3% | 1.41 | 2.33 | -49.1% | $515,943 | $46,197 | $11,479 | 36.1% | 77.6% | 97.5% | 172 | 0.0% | no (drawdown -49.1%) |
| 20% of equity | 1 DTE | prior close, 1 cent | 20% | train | 2872 | 50.9% | 1.32 | 1.29 | -94.9% | $773,765 | $21,648 | $2,448 | 33.3% | 53.4% | 64.4% | 145 | 12.5% | no (drawdown -94.9%) |
| 20% of equity | 1 DTE | prior close, 1 cent | 20% | holdout | 1128 | 49.3% | 1.41 | 2.23 | -61.0% | $622,272 | $95,873 | $11,902 | 51.0% | 88.6% | 100.0% | 147 | 0.0% | no (drawdown -61.0%) |
| 5% of equity | 0 DTE | x1.67 prior close, 1 cent | 5% | train | 2804 | 47.3% | 1.31 | 1.04 | -88.1% | $111,948 | $3,806 | $924 | 8.5% | 18.2% | 31.9% | 252 | 0.9% | no (drawdown -88.1%) |
| 5% of equity | 0 DTE | x1.67 prior close, 1 cent | 5% | holdout | 1128 | 46.0% | 1.18 | 1.90 | -54.4% | $82,489 | $8,529 | $3,364 | 9.4% | 22.1% | 53.0% | 280 | 0.0% | no (drawdown -54.4%) |
| 10% of equity | 0 DTE | x1.67 prior close, 1 cent | 10% | train | 481 | 42.0% | 0.76 | -0.38 | -99.3% | $17.68 | $1,646 | $302 | 25.6% | 38.0% | 43.5% | 128 | 51.4% | no (PF 0.762<1.10, Sharpe -0.38<0.40, drawdown -99.3%) |
| 10% of equity | 0 DTE | x1.67 prior close, 1 cent | 10% | holdout | 1128 | 46.0% | 1.27 | 1.87 | -85.1% | $294,657 | $15,079 | $3,032 | 34.8% | 76.0% | 89.6% | 169 | 1.8% | no (drawdown -85.1%) |
| 15% of equity | 0 DTE | x1.67 prior close, 1 cent | 15% | train | 412 | 42.5% | 0.71 | -0.01 | -99.5% | $11.52 | $243 | $72.07 | 31.4% | 41.8% | 42.9% | 91 | 67.1% | no (PF 0.714<1.10, Sharpe -0.01<0.40, drawdown -99.5%) |
| 15% of equity | 0 DTE | x1.67 prior close, 1 cent | 15% | holdout | 1128 | 46.0% | 1.24 | 1.82 | -90.4% | $325,149 | $25,794 | $1,450 | 52.5% | 83.4% | 92.2% | 146 | 9.4% | no (drawdown -90.4%) |
| 20% of equity | 0 DTE | x1.67 prior close, 1 cent | 20% | train | 175 | 40.0% | 0.55 | -0.58 | -99.8% | $4.36 | $85.64 | $27.65 | 32.4% | 39.6% | 40.1% | 62 | 71.5% | no (trades 175<300, PF 0.550<1.10, Sharpe -0.58<0.40, drawdown -99.8%) |
| 20% of equity | 0 DTE | x1.67 prior close, 1 cent | 20% | holdout | 1128 | 46.0% | 1.26 | 1.85 | -93.2% | $421,657 | $22,914 | $275 | 59.0% | 82.8% | 81.6% | 82 | 55.1% | no (drawdown -93.2%) |

## 1 DTE at 10%, prior close moved 20%

| Sizing | Expiry | IV | Fraction | Window | Trades | Win | PF | Sharpe | Max DD | Ending | Median 12m | P10 12m | P($10k 4m) | P($10k 8m) | P($10k 12m) | Median days | P(ruin) | Gate |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 10% of equity | 1 DTE | prior close, 1 cent | 10% | train | 2873 | 50.9% | 1.31 | 1.58 | -75.0% | $673,540 | $8,728 | $3,349 | 8.6% | 32.6% | 49.7% | 232 | 0.0% | no (drawdown -75.0%) |
| 10% of equity | 1 DTE | prior close, 1 cent | 10% | holdout | 1128 | 49.3% | 1.46 | 2.68 | -33.8% | $390,295 | $18,417 | $7,408 | 7.9% | 60.2% | 86.2% | 230 | 0.0% | no (drawdown -33.8%) |
| 10% of equity | 1 DTE | 0.80x prior close, 1 cent | 10% | train | 2873 | 51.1% | 1.45 | 1.65 | -77.5% | $1,075,099 | $27,849 | $5,406 | 22.1% | 51.9% | 73.3% | 188 | 0.0% | no (drawdown -77.5%) |
| 10% of equity | 1 DTE | 0.80x prior close, 1 cent | 10% | holdout | 1128 | 49.7% | 1.57 | 3.01 | -35.3% | $786,732 | $84,814 | $22,209 | 43.0% | 85.1% | 100.0% | 166 | 0.0% | no (drawdown -35.3%) |
| 10% of equity | 1 DTE | 1.20x prior close, 1 cent | 10% | train | 2873 | 50.7% | 1.25 | 1.42 | -71.0% | $266,286 | $4,982 | $2,437 | 2.3% | 13.6% | 31.1% | 262 | 0.0% | no (drawdown -71.0%) |
| 10% of equity | 1 DTE | 1.20x prior close, 1 cent | 10% | holdout | 1128 | 49.0% | 1.21 | 2.01 | -35.9% | $70,167 | $8,217 | $5,056 | 0.0% | 21.5% | 45.4% | 310 | 0.0% | no (drawdown -35.9%) |

## Where the 50-contract cap binds

- 5% of equity, 1 DTE, prior close, 1 cent, train: 382 of 2873 fills (13.3%) stopped at 50 contracts. Signals whose formula was above 50: 382. One-contract rescues: 5. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 10% of equity, 1 DTE, prior close, 1 cent, train: 1353 of 2873 fills (47.1%) stopped at 50 contracts. Signals whose formula was above 50: 1353. One-contract rescues: 0. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 10% of equity, 1 DTE, prior close, 1 cent, holdout: 258 of 1128 fills (22.9%) stopped at 50 contracts. Signals whose formula was above 50: 258. One-contract rescues: 3. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 15% of equity, 1 DTE, prior close, 1 cent, train: 2015 of 2873 fills (70.1%) stopped at 50 contracts. Signals whose formula was above 50: 2015. One-contract rescues: 0. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 15% of equity, 1 DTE, prior close, 1 cent, holdout: 461 of 1128 fills (40.9%) stopped at 50 contracts. Signals whose formula was above 50: 461. One-contract rescues: 0. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 20% of equity, 1 DTE, prior close, 1 cent, train: 2050 of 2872 fills (71.4%) stopped at 50 contracts. Signals whose formula was above 50: 2050. One-contract rescues: 6. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 1.
- 20% of equity, 1 DTE, prior close, 1 cent, holdout: 677 of 1128 fills (60.0%) stopped at 50 contracts. Signals whose formula was above 50: 677. One-contract rescues: 0. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 5% of equity, 0 DTE, x1.67 prior close, 1 cent, train: 100 of 2804 fills (3.6%) stopped at 50 contracts. Signals whose formula was above 50: 100. One-contract rescues: 280. Skips because one contract cost more than 2f: 91. Skips because the ticket did not fit settled cash: 0.
- 5% of equity, 0 DTE, x1.67 prior close, 1 cent, holdout: 57 of 1128 fills (5.1%) stopped at 50 contracts. Signals whose formula was above 50: 57. One-contract rescues: 6. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 10% of equity, 0 DTE, x1.67 prior close, 1 cent, train: 4 of 481 fills (0.8%) stopped at 50 contracts. Signals whose formula was above 50: 4. One-contract rescues: 136. Skips because one contract cost more than 2f: 2878. Skips because the ticket did not fit settled cash: 0.
- 10% of equity, 0 DTE, x1.67 prior close, 1 cent, holdout: 268 of 1128 fills (23.8%) stopped at 50 contracts. Signals whose formula was above 50: 268. One-contract rescues: 1. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 15% of equity, 0 DTE, x1.67 prior close, 1 cent, train: 5 of 412 fills (1.2%) stopped at 50 contracts. Signals whose formula was above 50: 5. One-contract rescues: 124. Skips because one contract cost more than 2f: 2955. Skips because the ticket did not fit settled cash: 0.
- 15% of equity, 0 DTE, x1.67 prior close, 1 cent, holdout: 399 of 1128 fills (35.4%) stopped at 50 contracts. Signals whose formula was above 50: 399. One-contract rescues: 0. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 20% of equity, 0 DTE, x1.67 prior close, 1 cent, train: 4 of 175 fills (2.3%) stopped at 50 contracts. Signals whose formula was above 50: 4. One-contract rescues: 40. Skips because one contract cost more than 2f: 3235. Skips because the ticket did not fit settled cash: 1.
- 20% of equity, 0 DTE, x1.67 prior close, 1 cent, holdout: 637 of 1128 fills (56.5%) stopped at 50 contracts. Signals whose formula was above 50: 637. One-contract rescues: 11. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 10% of equity, 1 DTE, 0.80x prior close, 1 cent, train: 2115 of 2873 fills (73.6%) stopped at 50 contracts. Signals whose formula was above 50: 2115. One-contract rescues: 0. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 10% of equity, 1 DTE, 0.80x prior close, 1 cent, holdout: 659 of 1128 fills (58.4%) stopped at 50 contracts. Signals whose formula was above 50: 659. One-contract rescues: 0. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 10% of equity, 1 DTE, 1.20x prior close, 1 cent, train: 497 of 2873 fills (17.3%) stopped at 50 contracts. Signals whose formula was above 50: 497. One-contract rescues: 6. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.
- 10% of equity, 1 DTE, 1.20x prior close, 1 cent, holdout: 15 of 1128 fills (1.3%) stopped at 50 contracts. Signals whose formula was above 50: 15. One-contract rescues: 37. Skips because one contract cost more than 2f: 0. Skips because the ticket did not fit settled cash: 0.

This score does not change an order. The live QQQ Aggressive 1 DTE book stays a fixed lot.
