# 4hr refinement

Refining this cell does not make it better. The chop filter is the only train winner, and the margin is thin: mean yearly Sharpe 1.77 against the base 1.72, with 2020 and 2021 a bit worse and 2022 and 2023 a bit better. The one 2020-2023 account, which was not the selection score, has a slightly lower Sharpe (1.30 against 1.31) and a slightly higher ending ($13,088 against $12,699). Scored once on the holdout, the chop filter ends at $18,527 on 1,209 trades, profit factor 1.39, Sharpe 2.31, max drawdown -23.5%. The base holdout is $19,204 on 1,241 trades, profit factor 1.40, Sharpe 2.35, max drawdown -22.2%. The chop filter gives a little back on every one of those figures. Gate: no (DSR 0.897<0.95). No other refinement won the walk-forward, so there is no combination.

The choice used the mean of four fresh yearly Sharpes, 2020 through 2023. A refinement had to beat the base mean and collect at least 80 trades across those years. The holdout column was computed after that choice and did not vote.

Family size for this round is 80: the original 72 cells, these 8 single changes, and no combination, because fewer than two refinements won. The base cell is already inside the original 72, so it is not counted again. Deflated Sharpe uses that expanded count. The original published deflated Sharpe of 0.905 used 72 trials and is a little easier than the number in this table. The gate is the original one, including full-train Sharpe against seed 17, the expanded q, and full-train deflated Sharpe. The drawdown line and the 0.95 line were not moved.

Dukascopy volume is a bid-tick count. The dead-tape filter uses VIX1D only. That cache starts 2023-04-24, and 252 prior closes do not exist anywhere in 2017-2023, so on the train and on the walk-forward the dead-tape book is the base book.

## Walk-forward selection

Mean is the average of the four yearly Sharpes. Trades are the four years added together. A winner is marked yes.

| Rule | Mean Sharpe | 2020 | 2021 | 2022 | 2023 | Trades | Winner |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Base | 1.72 | 0.41 | 1.31 | 2.58 | 2.56 | 1902 |  |
| Chop filter | 1.77 | 0.40 | 1.16 | 2.76 | 2.74 | 1867 | yes |
| Time filter | 1.23 | 0.13 | 0.31 | 2.22 | 2.26 | 1701 |  |
| Volume filter | 1.51 | 0.10 | 1.21 | 1.82 | 2.89 | 1367 |  |
| Hold VWAP | 1.65 | 1.39 | 1.00 | 1.79 | 2.43 | 1317 |  |
| 4h slope 0.15% | 1.52 | 0.12 | 0.80 | 2.49 | 2.68 | 1609 |  |
| Dead tape | 1.72 | 0.41 | 1.31 | 2.58 | 2.56 | 1902 |  |
| Breakeven at 0.5R, target 1.5R | 0.79 | -1.58 | 0.48 | 2.17 | 2.08 | 2136 |  |
| Max 2 a day | 1.43 | 0.37 | 1.19 | 1.72 | 2.43 | 1305 |  |

## Walk-forward account, 2020-2023, one fresh $2,500

This is one account across the four years, which is not the same object as the mean of four fresh years. Deflated Sharpe here uses this account's daily returns and the expanded trial count. The breakeven book shows 2,136 trades across the four fresh years and 934 trades in this single account: the single account's drawdown leaves it unable to buy, which is already a worse result than the base and was not a train winner.

| Rule | Trades | Win | PF | Sharpe | Max DD | Ending | Deflated Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | 1902 | 50.1% | 1.19 | 1.31 | -48.1% | $12,699 | 0.550 |
| Chop filter | 1867 | 50.2% | 1.20 | 1.30 | -48.0% | $13,088 | 0.545 |
| Time filter | 1701 | 49.3% | 1.15 | 0.98 | -55.9% | $9,500 | 0.313 |
| Volume filter | 1367 | 48.8% | 1.19 | 1.12 | -55.2% | $10,056 | 0.412 |
| Hold VWAP | 1317 | 50.1% | 1.23 | 1.45 | -39.8% | $10,918 | 0.664 |
| 4h slope 0.15% | 1608 | 49.4% | 1.18 | 1.13 | -57.2% | $10,815 | 0.418 |
| Dead tape | 1902 | 50.1% | 1.19 | 1.31 | -48.1% | $12,699 | 0.550 |
| Breakeven at 0.5R, target 1.5R | 934 | 24.5% | 1.00 | 0.68 | -97.1% | $2,517 | 0.219 |
| Max 2 a day | 1305 | 49.9% | 1.19 | 1.15 | -39.2% | $10,046 | 0.436 |

## Holdout, 2024-01-01 through 2026-10-06, one fresh $2,500

Scored once after selection. Deflated Sharpe here uses the holdout daily returns and the same trial count. The gate's deflated-Sharpe leg is the full 2017-2023 train, shown in the last table. No row clears that gate. A few holdout deflated-Sharpe figures sit above 0.95. Those rows lost the walk-forward, and their full-train deflated Sharpe is below 0.95.

| Rule | Trades | Win | PF | Sharpe | Max DD | Ending | Deflated Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | 1241 | 50.4% | 1.40 | 2.35 | -22.2% | $19,204 | 0.949 |
| Chop filter | 1209 | 50.1% | 1.39 | 2.31 | -23.5% | $18,527 | 0.939 |
| Time filter | 1105 | 50.5% | 1.37 | 2.12 | -28.2% | $15,887 | 0.899 |
| Volume filter | 816 | 51.7% | 1.52 | 2.41 | -21.4% | $18,171 | 0.957 |
| Hold VWAP | 861 | 51.0% | 1.44 | 2.03 | -26.5% | $15,647 | 0.835 |
| 4h slope 0.15% | 982 | 50.6% | 1.40 | 2.37 | -18.1% | $15,711 | 0.958 |
| Dead tape | 1123 | 50.8% | 1.39 | 2.29 | -22.2% | $17,993 | 0.939 |
| Breakeven at 0.5R, target 1.5R | 1429 | 26.8% | 1.36 | 1.86 | -40.4% | $14,943 | 0.793 |
| Max 2 a day | 898 | 51.2% | 1.46 | 2.39 | -21.8% | $17,584 | 0.954 |

## Gate, full train 2017-2023

| Rule | Train trades | Train Sharpe | Train ending | Full-train DSR | q | Seed-17 train Sharpe | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Base | 3148 | 1.42 | $15,189 | 0.898 | 0.002 | -1.00 | no (DSR 0.898<0.95) |
| Chop filter | 3094 | 1.42 | $15,567 | 0.897 | 0.001 | -1.96 | no (DSR 0.897<0.95) |
| Time filter | 2842 | 1.00 | $10,985 | 0.571 | 0.016 | -1.74 | no (DSR 0.571<0.95) |
| Volume filter | 2369 | 0.94 | $10,824 | 0.513 | 0.016 | -1.79 | no (DSR 0.513<0.95) |
| Hold VWAP | 2218 | 1.44 | $13,239 | 0.919 | 0.002 | -1.03 | no (DSR 0.919<0.95) |
| 4h slope 0.15% | 2591 | 1.06 | $11,993 | 0.628 | 0.009 | -1.92 | no (DSR 0.628<0.95) |
| Dead tape | 3148 | 1.42 | $15,189 | 0.898 | 0.002 | -1.00 | no (DSR 0.898<0.95) |
| Breakeven at 0.5R, target 1.5R | 3605 | 0.66 | $9,457 | 0.250 | 0.089 | -0.92 | no (drawdown -40.4%, DSR 0.250<0.95) |
| Max 2 a day | 2217 | 1.30 | $12,510 | 0.841 | 0.004 | -0.74 | no (DSR 0.841<0.95) |

## Overlap with QQQ Aggressive

The two books show up on the same days and rarely on the same bar. On the holdout, 89.0% of 4hr signal days are also QQQ Aggressive signal days, while 11.0% of filled 4hr trades share a 15-minute bucket with a filled Aggressive trade. Daily filled-trade P&L correlation is 0.12 across every holdout session and 0.12 on sessions where at least one book traded. The train figures are 90.6% of signal days in common, 9.6% of filled trades in the same 15-minute bucket, and a daily P&L correlation of 0.09. Running both is not the same fill twice. The day calendars overlap, and the profits are only loosely tied.

| Window | 4hr signal days | Aggressive signal days | Days in common | Share of 4hr days | Share of Aggressive days | 4hr trades | Aggressive trades | 4hr trades on an Aggressive day | 4hr trades in the same 15-minute bucket | Corr, all days | Corr, days either traded |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 1345 | 1524 | 1218 | 90.6% | 79.9% | 3148 | 2873 | 91.0% | 9.6% | 0.09 | 0.09 |
| holdout | 546 | 603 | 486 | 89.0% | 80.6% | 1241 | 1128 | 90.5% | 11.0% | 0.12 | 0.12 |

Daily P&L for the correlation is the sum of that day's filled-trade P&L, and zero when the book did not trade. QQQ Aggressive was rebuilt on the same caches: 15-minute 2 SD continuation, 1R, unscaled 1 DTE, 1 cent, one contract, cap 5.

Selected rule: Chop filter. Holdout ending $18,527 on 1209 trades, profit factor 1.39, Sharpe 2.31, max drawdown -23.5%. Base holdout ending $19,204 on 1241 trades, profit factor 1.40, Sharpe 2.35, max drawdown -22.2%. Gate for the selected rule: no (DSR 0.897<0.95).

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. Nothing was sent to a broker.

```
PYTHONPATH=src python3 -m webull_bot.chart_reads.research_four_hour_refine
```
