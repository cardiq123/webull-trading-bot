# QQQ Aggressive Compound, realistic fills

Backtest only. Nothing was sent to a broker. Live trading stays off. The sandbox forward books were not changed.

QQQ Aggressive Compound still spends a fixed fraction of current equity on the 1 DTE premium. The signal, the 1R stop and target, and the same-day 15:45 flatten match the earlier score. The account starts at $2,500. This pass charges a size slippage and caps the ticket on a liquidity assumption.

The liquidity number is an assumption, not a print from a QQQ 1 DTE quote tape. Inside displayed size is 100 contracts. A few levels means 3 levels (the inside quote plus the next 2), each assumed equal to that size. Participation is 10%. The realistic cap is min(50, floor(0.10 * 100 * 3)) = 30 contracts. Caps of 10 and 25 are scored beside it. The sweet spot uses the realistic cap only.

No fraction clears the gate on both windows at 1.20x with the 30-contract cap. 5% has the highest holdout 12-month median among fractions whose max drawdown is no worse than -40% on both windows.

Recommended fraction: 5%. At 1.20 times the prior close and the 30-contract cap, Holdout ends at $13,317 on 1033 trades, max drawdown -33.3%, Sharpe 1.73, profit factor 1.23, 12-month median $6,113, 10th percentile $4,188, P($10k in 4/8/12 months) 0.0% / 0.2% / 6.9%, P(ruin) 0.0%, gate no (drawdown -33.3%). Train ends at $50,184 on 2872 trades, max drawdown -35.9%, Sharpe 1.57, profit factor 1.28, 12-month median $3,833, 10th percentile $2,221, P($10k in 4/8/12 months) 0.0% / 0.0% / 0.0%, P(ruin) 0.0%, gate no (drawdown -35.9%).

The same 5% at the unscaled prior close, same cap and slippage: Holdout ends at $49,434 on 1118 trades, max drawdown -25.7%, Sharpe 2.59, profit factor 1.34, 12-month median $7,752, 10th percentile $5,603, P($10k in 4/8/12 months) 0.0% / 10.8% / 23.3%, P(ruin) 0.0%, gate yes. Train ends at $157,905 on 2873 trades, max drawdown -39.8%, Sharpe 1.81, profit factor 1.23, 12-month median $4,980, 10th percentile $2,872, P($10k in 4/8/12 months) 0.0% / 0.1% / 11.9%, P(ruin) 0.0%, gate no (drawdown -39.8%).

Every fraction at 1.20 times the prior close, the 30-contract cap, and size slippage. 2%: holdout $2,701, drawdown -8.4%, Sharpe 0.44, profit factor 1.16, median $2,500, gate no (trades 64<300). Train $6,406, drawdown -30.7%, Sharpe 1.00, profit factor 1.22, median $2,500, gate no (drawdown -30.7%). 3%: holdout $11,139, drawdown -21.7%, Sharpe 1.96, profit factor 1.35, median $2,899, gate yes. Train $21,715, drawdown -35.1%, Sharpe 1.56, profit factor 1.27, median $2,723, gate no (drawdown -35.1%). 4%: holdout $12,306, drawdown -27.1%, Sharpe 1.84, profit factor 1.25, median $5,114, gate yes. Train $38,191, drawdown -34.4%, Sharpe 1.69, profit factor 1.30, median $3,456, gate no (drawdown -34.4%). 5%: holdout $13,317, drawdown -33.3%, Sharpe 1.73, profit factor 1.23, median $6,113, gate no (drawdown -33.3%). Train $50,184, drawdown -35.9%, Sharpe 1.57, profit factor 1.28, median $3,833, gate no (drawdown -35.9%). 6%: holdout $22,137, drawdown -27.9%, Sharpe 2.02, profit factor 1.25, median $6,585, gate yes. Train $69,765, drawdown -46.9%, Sharpe 1.48, profit factor 1.25, median $3,899, gate no (drawdown -46.9%). 7%: holdout $26,906, drawdown -26.6%, Sharpe 1.96, profit factor 1.23, median $6,627, gate yes. Train $84,209, drawdown -52.3%, Sharpe 1.39, profit factor 1.18, median $4,274, gate no (drawdown -52.3%). 8%: holdout $36,099, drawdown -32.4%, Sharpe 1.95, profit factor 1.22, median $7,030, gate no (drawdown -32.4%). Train $84,731, drawdown -62.0%, Sharpe 1.27, profit factor 1.16, median $4,309, gate no (drawdown -62.0%). 10%: holdout $60,843, drawdown -36.4%, Sharpe 1.97, profit factor 1.20, median $8,217, gate no (drawdown -36.4%). Train $103,557, drawdown -71.0%, Sharpe 1.19, profit factor 1.13, median $4,973, gate no (drawdown -71.0%). 12%: holdout $93,761, drawdown -41.8%, Sharpe 1.98, profit factor 1.24, median $9,547, gate no (drawdown -41.8%). Train $106,262, drawdown -78.6%, Sharpe 1.12, profit factor 1.13, median $5,215, gate no (drawdown -78.6%).

The 1-per-$2,500 tier under the same slippage. Its lot stays between 1 and 5, so the extra slippage is zero and the cap does not bind. prior close, 1 cent: Holdout ends at $61,877 on 1128 trades, max drawdown -24.8%, Sharpe 2.57, profit factor 1.42, 12-month median $10,464, 10th percentile $6,816, P($10k in 4/8/12 months) 2.0% / 31.3% / 60.1%, P(ruin) 0.0%, gate yes. Train ends at $69,954 on 2873 trades, max drawdown -27.2%, Sharpe 1.83, profit factor 1.32, 12-month median $4,571, 10th percentile $3,108, P($10k in 4/8/12 months) 1.6% / 5.5% / 16.7%, P(ruin) 0.0%, gate yes. 1.20x prior close, 1 cent: Holdout ends at $40,055 on 1128 trades, max drawdown -32.5%, Sharpe 2.08, profit factor 1.33, 12-month median $7,992, 10th percentile $4,756, P($10k in 4/8/12 months) 0.0% / 25.0% / 46.5%, P(ruin) 0.0%, gate no (drawdown -32.5%). Train ends at $40,778 on 2873 trades, max drawdown -33.0%, Sharpe 1.40, profit factor 1.23, 12-month median $4,088, 10th percentile $2,793, P($10k in 4/8/12 months) 0.0% / 0.0% / 4.8%, P(ruin) 0.0%, gate no (drawdown -33.0%).

Cells that clear the gate on both windows: 1 per $2,500, cap 30, prior close, 1 cent; 3%, cap 10, prior close, 1 cent; 3%, cap 25, prior close, 1 cent; 3%, cap 30, prior close, 1 cent.

The live QQQ Aggressive 1 DTE book stays one contract. This table does not change an order.

## The rule, written down first

QQQ Aggressive Compound, realistic fills. The signal is the QQQ 15-minute 2 SD VWAP continuation, a 1R underlying stop and target, a 10-minute entry window, and a sale the same day at the stop, the target, or the 15:45 bar. The scored fill is the next open. One position. At most 5 fills a day. Fresh $2,500. Expiry is 1 DTE. Pricing is the unscaled prior close and a 1 cent market, and the same structures at 1.20 times that close. contracts = floor(f * equity / (ask * 100)), using the unslipped ask. If that rounds to 0, buy 1 contract when 1 contract costs at most 2f of equity, otherwise skip. The size is decided once, from that ask. Size slippage is then added on the entry and on the exit. If the slipped ticket does not fit settled cash, skip the whole ticket. The size is not cut down and is not recomputed after slippage. Current equity is settled cash plus credits due. Credits whose settlement date is this session are added to settled cash first, before this fill's debit is subtracted. The half-spread is the 1 cent market. Size slippage is an extra $0.01 per share for every 10 contracts beyond the first 10, on the way in and on the way out. The charge is 0.01 * (contracts - 10) / 10 once the ticket is larger than 10. Ten contracts pay the half-spread only. Fractions: 2%, 3%, 4%, 5%, 6%, 7%, 8%, 10%, 12%. Liquidity assumption, not a measured QQQ quote tape: the inside displayed size is 100 contracts. A few levels means the inside quote plus the next 2, and each of those 3 levels is assumed equal to that inside size. The book takes 10% of that displayed size. Realistic cap = min(50, floor(0.10 * 100 * 3)) = 30 contracts. The same fractions are also scored at caps of 10 and of 25. The sweet spot uses only the realistic cap of 30, with size slippage, at 1.20 times the prior close. It is the largest fraction that clears the gate on both the train window and the holdout window. The gate is at least 300 trades, profit factor at least 1.10, Sharpe at least 0.40, and max drawdown no worse than -30%. If no fraction clears that gate on both windows, the sweet spot is the fraction with the highest holdout 12-month median ending among those whose max drawdown is no worse than -40% on both windows. A tie on that holdout median goes to the higher train 12-month median, then to the larger fraction. If none stay inside that drawdown on both windows, no fraction is recommended. The 1-per-$2,500 tier is scored under the same slippage and the same two volatilities. Its lot is 1 to 5, so these caps and the extra slippage do not change its fill. This score does not change the sandbox book.

Train is 2017-02-16 through 2023-12-31. Holdout is a fresh account from 2024-01-01 through 2026-10-06. Ending, profit factor, Sharpe, max drawdown, and the gate are that one account. The median, the 10th percentile, the three reach rates, and P(ruin) start a fresh $2,500 on every later session that still has that many months inside the window. Reach is equity of $10,000. Ruin is equity under $500. The usual gate is at least 300 trades, profit factor at least 1.10, Sharpe at least 0.40, and max drawdown no worse than -30%. A both-window pass needs that gate on the train row and the holdout row.

## Decision grid: 1.20x, cap 30

| Sizing | Cap | IV | Window | Trades | PF | Sharpe | Max DD | Ending | Median 12m | P10 12m | P($10k 4/8/12m) | P(ruin) | Gate |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| 2% | 30 | 1.20x prior close, 1 cent | train | 1457 | 1.22 | 1.00 | -30.7% | $6,406 | $2,500 | $2,375 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -30.7%) |
| 2% | 30 | 1.20x prior close, 1 cent | holdout | 64 | 1.16 | 0.44 | -8.4% | $2,701 | $2,500 | $2,336 | 0.0% / 0.0% / 0.0% | 0.0% | no (trades 64<300) |
| 3% | 30 | 1.20x prior close, 1 cent | train | 2762 | 1.27 | 1.56 | -35.1% | $21,715 | $2,723 | $2,372 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -35.1%) |
| 3% | 30 | 1.20x prior close, 1 cent | holdout | 741 | 1.35 | 1.96 | -21.7% | $11,139 | $2,899 | $2,466 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 4% | 30 | 1.20x prior close, 1 cent | train | 2863 | 1.30 | 1.69 | -34.4% | $38,191 | $3,456 | $1,997 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -34.4%) |
| 4% | 30 | 1.20x prior close, 1 cent | holdout | 971 | 1.25 | 1.84 | -27.1% | $12,306 | $5,114 | $2,412 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 5% | 30 | 1.20x prior close, 1 cent | train | 2872 | 1.28 | 1.57 | -35.9% | $50,184 | $3,833 | $2,221 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -35.9%) |
| 5% | 30 | 1.20x prior close, 1 cent | holdout | 1033 | 1.23 | 1.73 | -33.3% | $13,317 | $6,113 | $4,188 | 0.0% / 0.2% / 6.9% | 0.0% | no (drawdown -33.3%) |
| 6% | 30 | 1.20x prior close, 1 cent | train | 2872 | 1.25 | 1.48 | -46.9% | $69,765 | $3,899 | $2,130 | 0.0% / 0.0% / 1.0% | 0.0% | no (drawdown -46.9%) |
| 6% | 30 | 1.20x prior close, 1 cent | holdout | 1107 | 1.25 | 2.02 | -27.9% | $22,137 | $6,585 | $4,484 | 0.0% / 0.2% / 17.7% | 0.0% | yes |
| 7% | 30 | 1.20x prior close, 1 cent | train | 2873 | 1.18 | 1.39 | -52.3% | $84,209 | $4,274 | $2,265 | 0.0% / 0.3% / 10.8% | 0.0% | no (drawdown -52.3%) |
| 7% | 30 | 1.20x prior close, 1 cent | holdout | 1123 | 1.23 | 1.96 | -26.6% | $26,906 | $6,627 | $4,721 | 0.0% / 7.5% / 19.6% | 0.0% | yes |
| 8% | 30 | 1.20x prior close, 1 cent | train | 2873 | 1.16 | 1.27 | -62.0% | $84,731 | $4,309 | $2,445 | 0.0% / 3.6% / 18.8% | 0.0% | no (drawdown -62.0%) |
| 8% | 30 | 1.20x prior close, 1 cent | holdout | 1127 | 1.22 | 1.95 | -32.4% | $36,099 | $7,030 | $4,524 | 0.0% / 11.4% / 21.2% | 0.0% | no (drawdown -32.4%) |
| 10% | 30 | 1.20x prior close, 1 cent | train | 2873 | 1.13 | 1.19 | -71.0% | $103,557 | $4,973 | $2,382 | 2.3% / 13.6% / 31.1% | 0.0% | no (drawdown -71.0%) |
| 10% | 30 | 1.20x prior close, 1 cent | holdout | 1128 | 1.20 | 1.97 | -36.4% | $60,843 | $8,217 | $5,056 | 0.0% / 21.5% / 45.4% | 0.0% | no (drawdown -36.4%) |
| 12% | 30 | 1.20x prior close, 1 cent | train | 2873 | 1.13 | 1.12 | -78.6% | $106,262 | $5,215 | $2,067 | 5.0% / 24.5% / 40.6% | 0.0% | no (drawdown -78.6%) |
| 12% | 30 | 1.20x prior close, 1 cent | holdout | 1128 | 1.24 | 1.98 | -41.8% | $93,761 | $9,547 | $4,862 | 2.5% / 33.7% / 68.9% | 0.0% | no (drawdown -41.8%) |

## Realistic cap 30, both volatilities

| Sizing | Cap | IV | Window | Trades | PF | Sharpe | Max DD | Ending | Median 12m | P10 12m | P($10k 4/8/12m) | P(ruin) | Gate |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| 2% | 30 | prior close, 1 cent | train | 2685 | 1.37 | 1.96 | -33.5% | $26,386 | $2,634 | $2,499 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -33.5%) |
| 2% | 30 | prior close, 1 cent | holdout | 576 | 1.34 | 1.88 | -16.5% | $8,393 | $2,541 | $2,268 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 3% | 30 | prior close, 1 cent | train | 2868 | 1.39 | 2.20 | -27.1% | $64,228 | $3,815 | $2,303 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 3% | 30 | prior close, 1 cent | holdout | 984 | 1.37 | 2.49 | -17.6% | $17,633 | $5,110 | $2,391 | 0.0% / 0.0% / 3.2% | 0.0% | yes |
| 4% | 30 | prior close, 1 cent | train | 2873 | 1.30 | 1.98 | -36.1% | $113,245 | $4,490 | $2,622 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -36.1%) |
| 4% | 30 | prior close, 1 cent | holdout | 1075 | 1.36 | 2.53 | -23.2% | $28,243 | $7,340 | $4,992 | 0.0% / 5.8% / 15.0% | 0.0% | yes |
| 5% | 30 | prior close, 1 cent | train | 2873 | 1.23 | 1.81 | -39.8% | $157,905 | $4,980 | $2,872 | 0.0% / 0.1% / 11.9% | 0.0% | no (drawdown -39.8%) |
| 5% | 30 | prior close, 1 cent | holdout | 1118 | 1.34 | 2.59 | -25.7% | $49,434 | $7,752 | $5,603 | 0.0% / 10.8% / 23.3% | 0.0% | yes |
| 6% | 30 | prior close, 1 cent | train | 2873 | 1.22 | 1.66 | -52.0% | $190,933 | $5,298 | $3,065 | 0.0% / 5.1% / 26.5% | 0.0% | no (drawdown -52.0%) |
| 6% | 30 | prior close, 1 cent | holdout | 1127 | 1.31 | 2.55 | -25.9% | $75,237 | $8,999 | $5,834 | 0.0% / 14.7% / 43.1% | 0.0% | yes |
| 7% | 30 | prior close, 1 cent | train | 2873 | 1.22 | 1.54 | -58.8% | $207,954 | $6,637 | $3,180 | 1.2% / 15.6% / 39.2% | 0.0% | no (drawdown -58.8%) |
| 7% | 30 | prior close, 1 cent | holdout | 1128 | 1.33 | 2.59 | -26.7% | $114,002 | $10,129 | $6,292 | 0.0% / 22.8% / 59.0% | 0.0% | yes |
| 8% | 30 | prior close, 1 cent | train | 2873 | 1.21 | 1.43 | -64.9% | $215,981 | $6,987 | $3,081 | 3.8% / 23.2% / 45.0% | 0.0% | no (drawdown -64.9%) |
| 8% | 30 | prior close, 1 cent | holdout | 1128 | 1.39 | 2.67 | -29.1% | $183,069 | $12,667 | $7,099 | 0.0% / 35.8% / 73.5% | 0.0% | yes |
| 10% | 30 | prior close, 1 cent | train | 2873 | 1.20 | 1.28 | -73.6% | $218,350 | $8,151 | $2,993 | 8.6% / 31.6% / 49.4% | 0.0% | no (drawdown -73.6%) |
| 10% | 30 | prior close, 1 cent | holdout | 1128 | 1.36 | 2.44 | -39.8% | $219,417 | $18,188 | $7,408 | 7.9% / 60.2% / 86.2% | 0.0% | no (drawdown -39.8%) |
| 12% | 30 | prior close, 1 cent | train | 2873 | 1.19 | 1.19 | -79.7% | $216,325 | $8,336 | $2,845 | 12.9% / 39.2% / 51.8% | 0.2% | no (drawdown -79.7%) |
| 12% | 30 | prior close, 1 cent | holdout | 1128 | 1.34 | 2.23 | -49.5% | $227,227 | $24,890 | $7,606 | 20.7% / 64.2% / 88.9% | 0.0% | no (drawdown -49.5%) |
| 2% | 30 | 1.20x prior close, 1 cent | train | 1457 | 1.22 | 1.00 | -30.7% | $6,406 | $2,500 | $2,375 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -30.7%) |
| 2% | 30 | 1.20x prior close, 1 cent | holdout | 64 | 1.16 | 0.44 | -8.4% | $2,701 | $2,500 | $2,336 | 0.0% / 0.0% / 0.0% | 0.0% | no (trades 64<300) |
| 3% | 30 | 1.20x prior close, 1 cent | train | 2762 | 1.27 | 1.56 | -35.1% | $21,715 | $2,723 | $2,372 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -35.1%) |
| 3% | 30 | 1.20x prior close, 1 cent | holdout | 741 | 1.35 | 1.96 | -21.7% | $11,139 | $2,899 | $2,466 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 4% | 30 | 1.20x prior close, 1 cent | train | 2863 | 1.30 | 1.69 | -34.4% | $38,191 | $3,456 | $1,997 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -34.4%) |
| 4% | 30 | 1.20x prior close, 1 cent | holdout | 971 | 1.25 | 1.84 | -27.1% | $12,306 | $5,114 | $2,412 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 5% | 30 | 1.20x prior close, 1 cent | train | 2872 | 1.28 | 1.57 | -35.9% | $50,184 | $3,833 | $2,221 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -35.9%) |
| 5% | 30 | 1.20x prior close, 1 cent | holdout | 1033 | 1.23 | 1.73 | -33.3% | $13,317 | $6,113 | $4,188 | 0.0% / 0.2% / 6.9% | 0.0% | no (drawdown -33.3%) |
| 6% | 30 | 1.20x prior close, 1 cent | train | 2872 | 1.25 | 1.48 | -46.9% | $69,765 | $3,899 | $2,130 | 0.0% / 0.0% / 1.0% | 0.0% | no (drawdown -46.9%) |
| 6% | 30 | 1.20x prior close, 1 cent | holdout | 1107 | 1.25 | 2.02 | -27.9% | $22,137 | $6,585 | $4,484 | 0.0% / 0.2% / 17.7% | 0.0% | yes |
| 7% | 30 | 1.20x prior close, 1 cent | train | 2873 | 1.18 | 1.39 | -52.3% | $84,209 | $4,274 | $2,265 | 0.0% / 0.3% / 10.8% | 0.0% | no (drawdown -52.3%) |
| 7% | 30 | 1.20x prior close, 1 cent | holdout | 1123 | 1.23 | 1.96 | -26.6% | $26,906 | $6,627 | $4,721 | 0.0% / 7.5% / 19.6% | 0.0% | yes |
| 8% | 30 | 1.20x prior close, 1 cent | train | 2873 | 1.16 | 1.27 | -62.0% | $84,731 | $4,309 | $2,445 | 0.0% / 3.6% / 18.8% | 0.0% | no (drawdown -62.0%) |
| 8% | 30 | 1.20x prior close, 1 cent | holdout | 1127 | 1.22 | 1.95 | -32.4% | $36,099 | $7,030 | $4,524 | 0.0% / 11.4% / 21.2% | 0.0% | no (drawdown -32.4%) |
| 10% | 30 | 1.20x prior close, 1 cent | train | 2873 | 1.13 | 1.19 | -71.0% | $103,557 | $4,973 | $2,382 | 2.3% / 13.6% / 31.1% | 0.0% | no (drawdown -71.0%) |
| 10% | 30 | 1.20x prior close, 1 cent | holdout | 1128 | 1.20 | 1.97 | -36.4% | $60,843 | $8,217 | $5,056 | 0.0% / 21.5% / 45.4% | 0.0% | no (drawdown -36.4%) |
| 12% | 30 | 1.20x prior close, 1 cent | train | 2873 | 1.13 | 1.12 | -78.6% | $106,262 | $5,215 | $2,067 | 5.0% / 24.5% / 40.6% | 0.0% | no (drawdown -78.6%) |
| 12% | 30 | 1.20x prior close, 1 cent | holdout | 1128 | 1.24 | 1.98 | -41.8% | $93,761 | $9,547 | $4,862 | 2.5% / 33.7% / 68.9% | 0.0% | no (drawdown -41.8%) |

## Cap 10, both volatilities

| Sizing | Cap | IV | Window | Trades | PF | Sharpe | Max DD | Ending | Median 12m | P10 12m | P($10k 4/8/12m) | P(ruin) | Gate |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| 2% | 10 | prior close, 1 cent | train | 2685 | 1.37 | 1.96 | -33.5% | $26,386 | $2,634 | $2,499 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -33.5%) |
| 2% | 10 | prior close, 1 cent | holdout | 576 | 1.34 | 1.88 | -16.5% | $8,393 | $2,541 | $2,268 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 3% | 10 | prior close, 1 cent | train | 2868 | 1.37 | 2.17 | -27.1% | $56,410 | $3,815 | $2,303 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 3% | 10 | prior close, 1 cent | holdout | 984 | 1.37 | 2.49 | -17.6% | $17,633 | $5,110 | $2,391 | 0.0% / 0.0% / 3.2% | 0.0% | yes |
| 4% | 10 | prior close, 1 cent | train | 2873 | 1.34 | 1.98 | -36.1% | $84,318 | $4,490 | $2,622 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -36.1%) |
| 4% | 10 | prior close, 1 cent | holdout | 1075 | 1.36 | 2.53 | -23.2% | $28,314 | $7,340 | $4,992 | 0.0% / 5.8% / 15.0% | 0.0% | yes |
| 5% | 10 | prior close, 1 cent | train | 2873 | 1.33 | 1.85 | -39.8% | $120,096 | $4,980 | $2,872 | 0.0% / 0.1% / 11.9% | 0.0% | no (drawdown -39.8%) |
| 5% | 10 | prior close, 1 cent | holdout | 1118 | 1.40 | 2.70 | -25.7% | $51,223 | $7,752 | $5,603 | 0.0% / 10.8% / 23.3% | 0.0% | yes |
| 6% | 10 | prior close, 1 cent | train | 2873 | 1.31 | 1.68 | -52.4% | $132,866 | $5,298 | $3,087 | 0.0% / 5.1% / 26.3% | 0.0% | no (drawdown -52.4%) |
| 6% | 10 | prior close, 1 cent | holdout | 1127 | 1.45 | 2.72 | -23.0% | $75,283 | $8,999 | $5,834 | 0.0% / 14.7% / 43.1% | 0.0% | yes |
| 7% | 10 | prior close, 1 cent | train | 2873 | 1.31 | 1.57 | -58.3% | $140,555 | $6,686 | $3,339 | 1.2% / 15.6% / 39.1% | 0.0% | no (drawdown -58.3%) |
| 7% | 10 | prior close, 1 cent | holdout | 1128 | 1.44 | 2.63 | -26.7% | $85,379 | $10,129 | $6,292 | 0.0% / 22.8% / 59.0% | 0.0% | yes |
| 8% | 10 | prior close, 1 cent | train | 2873 | 1.31 | 1.56 | -63.8% | $156,660 | $7,047 | $3,184 | 3.8% / 23.2% / 45.0% | 0.0% | no (drawdown -63.8%) |
| 8% | 10 | prior close, 1 cent | holdout | 1128 | 1.42 | 2.58 | -29.1% | $100,290 | $12,682 | $7,099 | 0.0% / 35.8% / 73.5% | 0.0% | yes |
| 10% | 10 | prior close, 1 cent | train | 2873 | 1.32 | 1.43 | -74.0% | $166,620 | $8,968 | $3,417 | 8.4% / 32.5% / 49.5% | 0.0% | no (drawdown -74.0%) |
| 10% | 10 | prior close, 1 cent | holdout | 1128 | 1.41 | 2.52 | -32.8% | $123,521 | $18,729 | $7,408 | 7.9% / 60.2% / 86.2% | 0.0% | no (drawdown -32.8%) |
| 12% | 10 | prior close, 1 cent | train | 2873 | 1.32 | 1.34 | -80.8% | $169,062 | $11,032 | $3,298 | 11.8% / 39.0% / 53.1% | 0.2% | no (drawdown -80.8%) |
| 12% | 10 | prior close, 1 cent | holdout | 1128 | 1.40 | 2.33 | -40.8% | $127,340 | $27,294 | $7,718 | 20.7% / 64.8% / 88.9% | 0.0% | no (drawdown -40.8%) |
| 2% | 10 | 1.20x prior close, 1 cent | train | 1457 | 1.22 | 1.00 | -30.7% | $6,406 | $2,500 | $2,375 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -30.7%) |
| 2% | 10 | 1.20x prior close, 1 cent | holdout | 64 | 1.16 | 0.44 | -8.4% | $2,701 | $2,500 | $2,336 | 0.0% / 0.0% / 0.0% | 0.0% | no (trades 64<300) |
| 3% | 10 | 1.20x prior close, 1 cent | train | 2762 | 1.27 | 1.56 | -35.1% | $21,715 | $2,723 | $2,372 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -35.1%) |
| 3% | 10 | 1.20x prior close, 1 cent | holdout | 741 | 1.35 | 1.96 | -21.7% | $11,139 | $2,899 | $2,466 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 4% | 10 | 1.20x prior close, 1 cent | train | 2863 | 1.30 | 1.68 | -34.4% | $36,928 | $3,456 | $1,997 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -34.4%) |
| 4% | 10 | 1.20x prior close, 1 cent | holdout | 971 | 1.25 | 1.84 | -27.1% | $12,306 | $5,114 | $2,412 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 5% | 10 | 1.20x prior close, 1 cent | train | 2872 | 1.27 | 1.55 | -35.9% | $43,676 | $3,833 | $2,221 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -35.9%) |
| 5% | 10 | 1.20x prior close, 1 cent | holdout | 1033 | 1.23 | 1.73 | -33.3% | $13,317 | $6,113 | $4,188 | 0.0% / 0.2% / 6.9% | 0.0% | no (drawdown -33.3%) |
| 6% | 10 | 1.20x prior close, 1 cent | train | 2872 | 1.25 | 1.45 | -46.9% | $53,407 | $3,899 | $2,130 | 0.0% / 0.0% / 1.0% | 0.0% | no (drawdown -46.9%) |
| 6% | 10 | 1.20x prior close, 1 cent | holdout | 1107 | 1.25 | 2.03 | -27.9% | $22,464 | $6,585 | $4,484 | 0.0% / 0.2% / 17.7% | 0.0% | yes |
| 7% | 10 | 1.20x prior close, 1 cent | train | 2873 | 1.24 | 1.42 | -52.3% | $70,331 | $4,274 | $2,260 | 0.0% / 0.3% / 10.8% | 0.0% | no (drawdown -52.3%) |
| 7% | 10 | 1.20x prior close, 1 cent | holdout | 1123 | 1.24 | 1.99 | -24.8% | $27,391 | $6,627 | $4,721 | 0.0% / 7.5% / 19.6% | 0.0% | yes |
| 8% | 10 | 1.20x prior close, 1 cent | train | 2873 | 1.24 | 1.33 | -61.9% | $77,241 | $4,309 | $2,450 | 0.0% / 3.7% / 18.8% | 0.0% | no (drawdown -61.9%) |
| 8% | 10 | 1.20x prior close, 1 cent | holdout | 1127 | 1.29 | 2.11 | -30.8% | $41,178 | $7,030 | $4,524 | 0.0% / 11.4% / 21.2% | 0.0% | no (drawdown -30.8%) |
| 10% | 10 | 1.20x prior close, 1 cent | train | 2873 | 1.23 | 1.25 | -70.9% | $94,995 | $4,968 | $2,466 | 2.3% / 13.8% / 31.1% | 0.0% | no (drawdown -70.9%) |
| 10% | 10 | 1.20x prior close, 1 cent | holdout | 1128 | 1.34 | 2.13 | -34.2% | $63,682 | $8,217 | $5,056 | 0.0% / 21.5% / 45.4% | 0.0% | no (drawdown -34.2%) |
| 12% | 10 | 1.20x prior close, 1 cent | train | 2873 | 1.23 | 1.13 | -79.5% | $88,152 | $5,286 | $2,262 | 5.0% / 24.6% / 40.5% | 0.0% | no (drawdown -79.5%) |
| 12% | 10 | 1.20x prior close, 1 cent | holdout | 1128 | 1.32 | 1.95 | -41.8% | $67,039 | $9,547 | $4,862 | 2.5% / 33.7% / 68.9% | 0.0% | no (drawdown -41.8%) |

## Cap 25, both volatilities

| Sizing | Cap | IV | Window | Trades | PF | Sharpe | Max DD | Ending | Median 12m | P10 12m | P($10k 4/8/12m) | P(ruin) | Gate |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| 2% | 25 | prior close, 1 cent | train | 2685 | 1.37 | 1.96 | -33.5% | $26,386 | $2,634 | $2,499 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -33.5%) |
| 2% | 25 | prior close, 1 cent | holdout | 576 | 1.34 | 1.88 | -16.5% | $8,393 | $2,541 | $2,268 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 3% | 25 | prior close, 1 cent | train | 2868 | 1.39 | 2.20 | -27.1% | $64,166 | $3,815 | $2,303 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 3% | 25 | prior close, 1 cent | holdout | 984 | 1.37 | 2.49 | -17.6% | $17,633 | $5,110 | $2,391 | 0.0% / 0.0% / 3.2% | 0.0% | yes |
| 4% | 25 | prior close, 1 cent | train | 2873 | 1.30 | 1.98 | -36.1% | $109,303 | $4,490 | $2,622 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -36.1%) |
| 4% | 25 | prior close, 1 cent | holdout | 1075 | 1.36 | 2.53 | -23.2% | $28,243 | $7,340 | $4,992 | 0.0% / 5.8% / 15.0% | 0.0% | yes |
| 5% | 25 | prior close, 1 cent | train | 2873 | 1.25 | 1.84 | -39.8% | $160,170 | $4,980 | $2,872 | 0.0% / 0.1% / 11.9% | 0.0% | no (drawdown -39.8%) |
| 5% | 25 | prior close, 1 cent | holdout | 1118 | 1.34 | 2.59 | -25.7% | $49,434 | $7,752 | $5,603 | 0.0% / 10.8% / 23.3% | 0.0% | yes |
| 6% | 25 | prior close, 1 cent | train | 2873 | 1.25 | 1.69 | -52.0% | $192,129 | $5,298 | $3,065 | 0.0% / 5.1% / 26.5% | 0.0% | no (drawdown -52.0%) |
| 6% | 25 | prior close, 1 cent | holdout | 1127 | 1.32 | 2.58 | -23.3% | $76,181 | $8,999 | $5,834 | 0.0% / 14.7% / 43.1% | 0.0% | yes |
| 7% | 25 | prior close, 1 cent | train | 2873 | 1.24 | 1.55 | -58.8% | $203,176 | $6,637 | $3,180 | 1.2% / 15.6% / 39.2% | 0.0% | no (drawdown -58.8%) |
| 7% | 25 | prior close, 1 cent | holdout | 1128 | 1.37 | 2.63 | -26.7% | $117,053 | $10,129 | $6,292 | 0.0% / 22.8% / 59.0% | 0.0% | yes |
| 8% | 25 | prior close, 1 cent | train | 2873 | 1.23 | 1.44 | -64.9% | $210,498 | $6,987 | $3,081 | 3.8% / 23.2% / 45.0% | 0.0% | no (drawdown -64.9%) |
| 8% | 25 | prior close, 1 cent | holdout | 1128 | 1.41 | 2.68 | -29.1% | $170,811 | $12,667 | $7,099 | 0.0% / 35.8% / 73.5% | 0.0% | yes |
| 10% | 25 | prior close, 1 cent | train | 2873 | 1.22 | 1.28 | -73.6% | $214,882 | $8,151 | $2,993 | 8.6% / 31.6% / 49.4% | 0.0% | no (drawdown -73.6%) |
| 10% | 25 | prior close, 1 cent | holdout | 1128 | 1.37 | 2.43 | -38.9% | $201,128 | $18,188 | $7,408 | 7.9% / 60.2% / 86.2% | 0.0% | no (drawdown -38.9%) |
| 12% | 25 | prior close, 1 cent | train | 2873 | 1.22 | 1.20 | -79.7% | $214,590 | $8,488 | $2,845 | 12.9% / 39.2% / 51.8% | 0.2% | no (drawdown -79.7%) |
| 12% | 25 | prior close, 1 cent | holdout | 1128 | 1.35 | 2.23 | -47.2% | $210,114 | $24,922 | $7,606 | 20.7% / 64.2% / 88.9% | 0.0% | no (drawdown -47.2%) |
| 2% | 25 | 1.20x prior close, 1 cent | train | 1457 | 1.22 | 1.00 | -30.7% | $6,406 | $2,500 | $2,375 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -30.7%) |
| 2% | 25 | 1.20x prior close, 1 cent | holdout | 64 | 1.16 | 0.44 | -8.4% | $2,701 | $2,500 | $2,336 | 0.0% / 0.0% / 0.0% | 0.0% | no (trades 64<300) |
| 3% | 25 | 1.20x prior close, 1 cent | train | 2762 | 1.27 | 1.56 | -35.1% | $21,715 | $2,723 | $2,372 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -35.1%) |
| 3% | 25 | 1.20x prior close, 1 cent | holdout | 741 | 1.35 | 1.96 | -21.7% | $11,139 | $2,899 | $2,466 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 4% | 25 | 1.20x prior close, 1 cent | train | 2863 | 1.30 | 1.69 | -34.4% | $38,191 | $3,456 | $1,997 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -34.4%) |
| 4% | 25 | 1.20x prior close, 1 cent | holdout | 971 | 1.25 | 1.84 | -27.1% | $12,306 | $5,114 | $2,412 | 0.0% / 0.0% / 0.0% | 0.0% | yes |
| 5% | 25 | 1.20x prior close, 1 cent | train | 2872 | 1.28 | 1.58 | -35.9% | $50,276 | $3,833 | $2,221 | 0.0% / 0.0% / 0.0% | 0.0% | no (drawdown -35.9%) |
| 5% | 25 | 1.20x prior close, 1 cent | holdout | 1033 | 1.23 | 1.73 | -33.3% | $13,317 | $6,113 | $4,188 | 0.0% / 0.2% / 6.9% | 0.0% | no (drawdown -33.3%) |
| 6% | 25 | 1.20x prior close, 1 cent | train | 2872 | 1.25 | 1.49 | -46.9% | $69,532 | $3,899 | $2,130 | 0.0% / 0.0% / 1.0% | 0.0% | no (drawdown -46.9%) |
| 6% | 25 | 1.20x prior close, 1 cent | holdout | 1107 | 1.25 | 2.02 | -27.9% | $22,137 | $6,585 | $4,484 | 0.0% / 0.2% / 17.7% | 0.0% | yes |
| 7% | 25 | 1.20x prior close, 1 cent | train | 2873 | 1.19 | 1.40 | -52.3% | $83,711 | $4,274 | $2,265 | 0.0% / 0.3% / 10.8% | 0.0% | no (drawdown -52.3%) |
| 7% | 25 | 1.20x prior close, 1 cent | holdout | 1123 | 1.23 | 1.96 | -26.6% | $26,906 | $6,627 | $4,721 | 0.0% / 7.5% / 19.6% | 0.0% | yes |
| 8% | 25 | 1.20x prior close, 1 cent | train | 2873 | 1.18 | 1.30 | -62.0% | $87,380 | $4,309 | $2,445 | 0.0% / 3.6% / 18.8% | 0.0% | no (drawdown -62.0%) |
| 8% | 25 | 1.20x prior close, 1 cent | holdout | 1127 | 1.22 | 1.96 | -32.3% | $36,181 | $7,030 | $4,524 | 0.0% / 11.4% / 21.2% | 0.0% | no (drawdown -32.3%) |
| 10% | 25 | 1.20x prior close, 1 cent | train | 2873 | 1.16 | 1.23 | -71.0% | $114,557 | $4,973 | $2,382 | 2.3% / 13.6% / 31.1% | 0.0% | no (drawdown -71.0%) |
| 10% | 25 | 1.20x prior close, 1 cent | holdout | 1128 | 1.23 | 2.03 | -34.2% | $65,884 | $8,217 | $5,056 | 0.0% / 21.5% / 45.4% | 0.0% | no (drawdown -34.2%) |
| 12% | 25 | 1.20x prior close, 1 cent | train | 2873 | 1.16 | 1.15 | -78.6% | $117,434 | $5,215 | $2,067 | 5.0% / 24.5% / 40.6% | 0.0% | no (drawdown -78.6%) |
| 12% | 25 | 1.20x prior close, 1 cent | holdout | 1128 | 1.28 | 2.01 | -41.8% | $98,331 | $9,547 | $4,862 | 2.5% / 33.7% / 68.9% | 0.0% | no (drawdown -41.8%) |

## 1 per $2,500 under the same slippage

| Sizing | Cap | IV | Window | Trades | PF | Sharpe | Max DD | Ending | Median 12m | P10 12m | P($10k 4/8/12m) | P(ruin) | Gate |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| 1 per $2,500 | 30 | prior close, 1 cent | train | 2873 | 1.32 | 1.83 | -27.2% | $69,954 | $4,571 | $3,108 | 1.6% / 5.5% / 16.7% | 0.0% | yes |
| 1 per $2,500 | 30 | prior close, 1 cent | holdout | 1128 | 1.42 | 2.57 | -24.8% | $61,877 | $10,464 | $6,816 | 2.0% / 31.3% / 60.1% | 0.0% | yes |
| 1 per $2,500 | 30 | 1.20x prior close, 1 cent | train | 2873 | 1.23 | 1.40 | -33.0% | $40,778 | $4,088 | $2,793 | 0.0% / 0.0% / 4.8% | 0.0% | no (drawdown -33.0%) |
| 1 per $2,500 | 30 | 1.20x prior close, 1 cent | holdout | 1128 | 1.33 | 2.08 | -32.5% | $40,055 | $7,992 | $4,756 | 0.0% / 25.0% / 46.5% | 0.0% | no (drawdown -32.5%) |

This score does not change an order. The live QQQ Aggressive 1 DTE book stays one contract.
