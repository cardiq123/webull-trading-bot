# $2,500 lots at 3 and 5 contracts

Backtest only. Nothing was sent to a broker. Live trading stays off. The sandbox forward books were not changed.

Ranked by a holdout that finishes above the $2,500 start together with a train account that also finishes above that start. A cell whose train account ends under $500 fails that check, even when the holdout is large.

The cells that clear the usual gate on both windows: QQQ Aggressive 1 contract 1 DTE.

The overlapping 1-, 3-, and 5-contract QQQ Aggressive and QQQ Trapdoor rows match the earlier report, including Aggressive at 3 contracts, 0 DTE, holdout: 1128 trades and $40,755.

These finish above $2,500 on the train and on the holdout. Holdout gate-passers come first.

1. QQQ Aggressive, 1 contract, 1 DTE. Holdout $18,069 on 1128 trades, profit factor 1.40, max drawdown -18.6%, 12-month median $8,247, P(reach $10k) 20.0%, P(ruin) 0.0%, gate yes. Train $19,797 on 2873 trades, profit factor 1.31, max drawdown -27.2%, 12-month median $4,571, P(reach $10k) 0.0%, P(ruin) 0.0%, gate yes.

2. QQQ Aggressive, 1 contract, 0 DTE. Holdout $15,252 on 1128 trades, profit factor 1.30, max drawdown -22.9%, 12-month median $6,888, P(reach $10k) 16.4%, P(ruin) 0.0%, gate yes. Train $11,848 on 2873 trades, profit factor 1.15, max drawdown -65.5%, 12-month median $3,628, P(reach $10k) 0.0%, P(ruin) 7.0%, gate no (drawdown -65.5%).

3. SPY VWAP, 1 contract, 1 DTE. Holdout $11,512 on 1373 trades, profit factor 1.23, max drawdown -29.0%, 12-month median $6,702, P(reach $10k) 0.0%, P(ruin) 0.0%, gate yes. Train $10,120 on 3282 trades, profit factor 1.12, max drawdown -72.5%, 12-month median $3,614, P(reach $10k) 0.0%, P(ruin) 16.7%, gate no (drawdown -72.5%).

4. QQQ Trapdoor, 1 contract, 1 DTE. Holdout $5,326 on 525 trades, profit factor 1.18, max drawdown -17.8%, 12-month median $4,143, P(reach $10k) 0.0%, P(ruin) 0.0%, gate yes. Train $6,292 on 1167 trades, profit factor 1.18, max drawdown -42.1%, 12-month median $2,740, P(reach $10k) 0.0%, P(ruin) 0.0%, gate no (drawdown -42.1%).

5. QQQ Aggressive, 3 contracts, 1 DTE. Holdout $49,206 on 1128 trades, profit factor 1.40, max drawdown -54.2%, 12-month median $19,597, P(reach $10k) 100.0%, P(ruin) 0.0%, gate no (drawdown -54.2%). Train $54,390 on 2873 trades, profit factor 1.31, max drawdown -54.3%, 12-month median $8,575, P(reach $10k) 41.2%, P(ruin) 3.8%, gate no (drawdown -54.3%).

6. QQQ Trapdoor, 3 contracts, 1 DTE. Holdout $10,977 on 525 trades, profit factor 1.18, max drawdown -31.8%, 12-month median $7,392, P(reach $10k) 27.6%, P(ruin) 17.3%, gate no (drawdown -31.8%). Train $13,536 on 1165 trades, profit factor 1.17, max drawdown -80.9%, 12-month median $3,108, P(reach $10k) 5.6%, P(ruin) 15.8%, gate no (drawdown -80.9%).

QQQ Aggressive at 3 contracts, 1 DTE, is the largest account that still takes every signal (2873 train, 1128 holdout). It misses the usual gate on drawdown: -54.3% on the train and -54.2% on the holdout.

These holdout accounts finish above $2,500 while the train account ends under $500.

QQQ Trapdoor, 5 contracts, 1 DTE: holdout $16,628 on 525 trades, train $180 on 714 trades, train P(ruin) 26.5%.

SPY VWAP, 3 contracts, 1 DTE: holdout $29,543 on 1366 trades, train $130 on 1568 trades, train P(ruin) 34.9%.

QQQ Trapdoor, 3 contracts, 0 DTE: holdout $3,144 on 525 trades, train $7.82 on 579 trades, train P(ruin) 54.1%.

QQQ Trapdoor, 1 contract, 0 DTE: holdout $2,715 on 525 trades, train $5.05 on 755 trades, train P(ruin) 7.1%.

QQQ Aggressive, 3 contracts, 0 DTE: holdout $40,755 on 1128 trades, train $0.97 on 587 trades, train P(ruin) 36.4%.

SPY VWAP, 1 contract, 0 DTE: holdout $4,067 on 1373 trades, train $0.78 on 1235 trades, train P(ruin) 42.2%.

QQQ Trapdoor, 5 contracts, 0 DTE: holdout $3,574 on 525 trades, train $0.09 on 557 trades, train P(ruin) 64.8%.

The remaining cells finish the holdout at or under $2,500, or the train ends between $500 and the start.

QQQ Aggressive, 5 contracts, 1 DTE: holdout $180 on 64 trades (gate no (trades 64<300, PF 0.714<1.10, Sharpe -0.05<0.40, drawdown -92.8%)), train $88,984 on 2873 trades.

SPY VWAP, 5 contracts, 1 DTE: holdout $198 on 150 trades (gate no (trades 150<300, PF 0.857<1.10, Sharpe -0.06<0.40, drawdown -94.2%)), train $155 on 131 trades.

SPY VWAP, 5 contracts, 0 DTE: holdout $55.65 on 138 trades (gate no (trades 138<300, PF 0.834<1.10, Sharpe -0.37<0.40, drawdown -98.1%)), train $5.92 on 70 trades.

SPY VWAP, 3 contracts, 0 DTE: holdout $9.81 on 274 trades (gate no (trades 274<300, PF 0.870<1.10, Sharpe -0.31<0.40, drawdown -99.7%)), train $4.98 on 106 trades.

QQQ Aggressive, 5 contracts, 0 DTE: holdout $14.45 on 59 trades (gate no (trades 59<300, PF 0.689<1.10, Sharpe 0.17<0.40, drawdown -99.4%)), train $1.10 on 538 trades.

The unscaled 1 DTE price rests on one session of live quotes, 2026-10-09 at 11:36 ET: the SPY 1 DTE call market mid was $2.155 and the model at the Oct 8 VIX1D close of 10.24 was $2.974. The same signals scored at 0.80 times and at 1.20 times that prior close, still with a 1 cent market and a same-day 15:45 flat, move as follows.

SPY VWAP, 1 contract. Holdout 0.80x $14,826 on 1373 trades, base $11,512 on 1373 trades, 1.20x $9,017 on 1373 trades. Train 0.80x $15,140 on 3282 trades, base $10,120 on 3282 trades, 1.20x $59.69 on 1762 trades. The 1.20x train ends under $500. The 1.20x holdout misses the usual gate.

SPY VWAP, 3 contracts. Holdout 0.80x $39,477 on 1373 trades, base $29,543 on 1366 trades, 1.20x $14,467 on 1241 trades. Train 0.80x $40,480 on 3281 trades, base $130 on 1568 trades, 1.20x $128 on 210 trades. The 0.80x train finishes above the $2,500 start.

SPY VWAP, 5 contracts. Holdout 0.80x $64,637 on 1371 trades, base $198 on 150 trades, 1.20x $454 on 169 trades. Train 0.80x $101 on 141 trades, base $155 on 131 trades, 1.20x $203 on 123 trades. The 0.80x holdout is the vol at which that ticket fits.

QQQ Aggressive, 1 contract. Holdout 0.80x $22,371 on 1128 trades, base $18,069 on 1128 trades, 1.20x $14,878 on 1128 trades. Train 0.80x $25,176 on 2873 trades, base $19,797 on 2873 trades, 1.20x $15,753 on 2873 trades.

QQQ Aggressive, 3 contracts. Holdout 0.80x $62,113 on 1128 trades, base $49,206 on 1128 trades, 1.20x $180 on 59 trades. Train 0.80x $70,527 on 2873 trades, base $54,390 on 2873 trades, 1.20x $42,260 on 2873 trades. The 1.20x holdout takes fewer than half the base trades, so the dearer ticket stops fitting.

QQQ Aggressive, 5 contracts. Holdout 0.80x $101,448 on 1105 trades, base $180 on 64 trades, 1.20x $314 on 47 trades. Train 0.80x $115,879 on 2873 trades, base $88,984 on 2873 trades, 1.20x $68,881 on 2872 trades. The 0.80x holdout is the vol at which that ticket fits.

QQQ Trapdoor, 1 contract. Holdout 0.80x $6,973 on 525 trades, base $5,326 on 525 trades, 1.20x $4,083 on 525 trades. Train 0.80x $8,377 on 1167 trades, base $6,292 on 1167 trades, 1.20x $4,673 on 1167 trades. The 1.20x holdout misses the usual gate.

QQQ Trapdoor, 3 contracts. Holdout 0.80x $15,919 on 525 trades, base $10,977 on 525 trades, 1.20x $7,249 on 525 trades. Train 0.80x $20,130 on 1167 trades, base $13,536 on 1165 trades, 1.20x $190 on 661 trades. The 1.20x train ends under $500. The 0.80x holdout clears the usual gate.

QQQ Trapdoor, 5 contracts. Holdout 0.80x $24,865 on 525 trades, base $16,628 on 525 trades, 1.20x $10,414 on 525 trades. Train 0.80x $31,884 on 1167 trades, base $180 on 714 trades, 1.20x $306 on 584 trades. The 0.80x train finishes above the $2,500 start.

## How this is scored

Train is 2017-02-16 through 2023-12-31. Holdout is a fresh account from 2024-01-01 through 2026-10-06. SPY VWAP, QQQ Aggressive, and QQQ Trapdoor each start at $2,500. Aggressive still takes at most 5 fills a day. Trapdoor still takes at most 3. SPY has no daily count cap. One position. The whole ticket is bought or the signal is skipped.

The signal is unchanged: SPY VWAP is the 15-minute 2 SD continuation, QQQ Aggressive is the same rule on QQQ, and QQQ Trapdoor is the neckline put. The fill is the next open. The stop and the 1R target are unchanged. Every position is sold on the underlying stop, the 1R target, or the 15:45 bar of the entry day. A 1 DTE contract expires at 16:00 on the next trading session, so it still has time value at that same-day sale. A Friday signal's 1 DTE contract expires Monday. The live QQQ Aggressive 1 DTE book uses this same flatten.

The 0 DTE rows use each day's prior VIX1D close, or the prior VIX close when that print is missing, times x1.67 (the unrounded ratio is 1.6699), and a 1 cent bid-ask. That is half a cent on the bid and half a cent on the ask. The 1 DTE rows use that prior close with no multiplier. The sensitivity rows reprice the same 1 DTE signals at 0.80 times and at 1.20 times the prior close.

Reach is equity of $10,000. Ruin is equity under $500. Ending is one account started at the first session of that window. The median and the two probabilities start a fresh account on every later session that still has a full 12 months inside the window. An account that goes broke stops taking the later signals. A fresh account started the next year still takes them.

The usual gate is the VWAP holdout gate: at least 300 trades, profit factor at least 1.10, Sharpe at least 0.40, and max drawdown no worse than -30%. The same numbers are shown on the train row. The formal pass is the holdout row. The earlier sizing report did not store Sharpe, so its rows have no gate column.

## Reference: 1- and 3-contract rows already published

Copied from reports/odte_sizing.md. QQQ Aggressive and QQQ Trapdoor already started at $2,500. That file has no 0 DTE 1-contract row. It has no SPY row at 1 or 3 contracts. The SPY rows there are 15 contracts from $1,000, so they are left in that report.

| Book | Expiry | Contracts | Window | Trades | Win | PF | Max DD | Ending | Median 12m | P(reach $10k) | P(ruin) |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ Aggressive | 0 DTE | 3 | train | 587 | 43.1% | 0.86 | -100.0% | $0.97 | $2,801 | 23.0% | 36.4% |
| QQQ Aggressive | 0 DTE | 3 | holdout | 1128 | 46.0% | 1.30 | -58.3% | $40,755 | $15,664 | 91.7% | 8.8% |
| QQQ Aggressive | 1 DTE | 1 | train | 2873 | 50.9% | 1.31 | -27.2% | $19,797 | $4,571 | 0.0% | 0.0% |
| QQQ Aggressive | 1 DTE | 1 | holdout | 1128 | 49.3% | 1.40 | -18.6% | $18,069 | $8,247 | 20.0% | 0.0% |
| QQQ Aggressive | 1 DTE | 3 | train | 2873 | 50.9% | 1.31 | -54.3% | $54,390 | $8,575 | 41.2% | 3.8% |
| QQQ Aggressive | 1 DTE | 3 | holdout | 1128 | 49.3% | 1.40 | -54.2% | $49,206 | $19,597 | 100.0% | 0.0% |
| QQQ Trapdoor | 0 DTE | 3 | train | 579 | 36.8% | 0.89 | -99.8% | $7.82 | $429 | 2.8% | 54.1% |
| QQQ Trapdoor | 0 DTE | 3 | holdout | 525 | 38.3% | 1.01 | -66.8% | $3,144 | $5,124 | 0.0% | 36.2% |
| QQQ Trapdoor | 1 DTE | 1 | train | 1167 | 45.2% | 1.18 | -42.1% | $6,292 | $2,740 | 0.0% | 0.0% |
| QQQ Trapdoor | 1 DTE | 1 | holdout | 525 | 44.2% | 1.18 | -17.8% | $5,326 | $4,143 | 0.0% | 0.0% |
| QQQ Trapdoor | 1 DTE | 3 | train | 1165 | 45.2% | 1.17 | -80.9% | $13,536 | $3,108 | 5.6% | 15.8% |
| QQQ Trapdoor | 1 DTE | 3 | holdout | 525 | 44.2% | 1.18 | -31.8% | $10,977 | $7,392 | 27.6% | 17.3% |

## Fresh $2,500, contracts 1, 3, and 5

Contract 1 is scored again so the gate can be read, and so 0 DTE has a 1-contract row. Contracts 3 and 5 are the sizing question. SPY uses $2,500 here.

| Book | Expiry | IV | Contracts | Window | Trades | Win | PF | Max DD | Ending | Median 12m | P(reach $10k) | P(ruin) | Gate |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| SPY VWAP | 0 DTE | x1.67 prior close, 1 cent | 1 | train | 1235 | 45.2% | 0.86 | -100.0% | $0.78 | $1,719 | 0.0% | 42.2% | no (PF 0.860<1.10, Sharpe -0.52<0.40, drawdown -100.0%) |
| SPY VWAP | 0 DTE | x1.67 prior close, 1 cent | 1 | holdout | 1373 | 47.1% | 1.03 | -51.1% | $4,067 | $4,044 | 0.0% | 3.8% | no (PF 1.035<1.10, drawdown -51.1%) |
| SPY VWAP | 0 DTE | x1.67 prior close, 1 cent | 3 | train | 106 | 33.0% | 0.37 | -99.8% | $4.98 | $67.38 | 0.0% | 74.7% | no (trades 106<300, PF 0.365<1.10, Sharpe -0.99<0.40, drawdown -99.8%) |
| SPY VWAP | 0 DTE | x1.67 prior close, 1 cent | 3 | holdout | 274 | 44.2% | 0.87 | -99.7% | $9.81 | $6,762 | 65.4% | 37.1% | no (trades 274<300, PF 0.870<1.10, Sharpe -0.31<0.40, drawdown -99.7%) |
| SPY VWAP | 0 DTE | x1.67 prior close, 1 cent | 5 | train | 70 | 34.3% | 0.38 | -99.8% | $5.92 | $75.75 | 1.0% | 85.4% | no (trades 70<300, PF 0.381<1.10, Sharpe -1.25<0.40, drawdown -99.8%) |
| SPY VWAP | 0 DTE | x1.67 prior close, 1 cent | 5 | holdout | 138 | 43.5% | 0.83 | -98.1% | $55.65 | $138 | 46.6% | 61.5% | no (trades 138<300, PF 0.834<1.10, Sharpe -0.37<0.40, drawdown -98.1%) |
| SPY VWAP | 1 DTE | prior close, 1 cent | 1 | train | 3282 | 50.2% | 1.12 | -72.5% | $10,120 | $3,614 | 0.0% | 16.7% | no (drawdown -72.5%) |
| SPY VWAP | 1 DTE | prior close, 1 cent | 1 | holdout | 1373 | 49.6% | 1.23 | -29.0% | $11,512 | $6,702 | 0.0% | 0.0% | yes |
| SPY VWAP | 1 DTE | prior close, 1 cent | 3 | train | 1568 | 47.4% | 0.97 | -98.5% | $130 | $5,266 | 21.8% | 34.9% | no (PF 0.968<1.10, Sharpe 0.17<0.40, drawdown -98.5%) |
| SPY VWAP | 1 DTE | prior close, 1 cent | 3 | holdout | 1366 | 49.6% | 1.23 | -60.5% | $29,543 | $13,909 | 76.7% | 9.5% | no (drawdown -60.5%) |
| SPY VWAP | 1 DTE | prior close, 1 cent | 5 | train | 131 | 42.7% | 0.60 | -94.3% | $155 | $1,687 | 29.1% | 8.9% | no (trades 131<300, PF 0.597<1.10, Sharpe -1.04<0.40, drawdown -94.3%) |
| SPY VWAP | 1 DTE | prior close, 1 cent | 5 | holdout | 150 | 42.7% | 0.86 | -94.2% | $198 | $18,652 | 61.3% | 37.6% | no (trades 150<300, PF 0.857<1.10, Sharpe -0.06<0.40, drawdown -94.2%) |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 1 | train | 2873 | 47.3% | 1.15 | -65.5% | $11,848 | $3,628 | 0.0% | 7.0% | no (drawdown -65.5%) |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 1 | holdout | 1128 | 46.0% | 1.30 | -22.9% | $15,252 | $6,888 | 16.4% | 0.0% | yes |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 3 | train | 587 | 43.1% | 0.86 | -100.0% | $0.97 | $2,801 | 23.0% | 36.4% | no (PF 0.859<1.10, Sharpe -0.67<0.40, drawdown -100.0%) |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 3 | holdout | 1128 | 46.0% | 1.30 | -58.3% | $40,755 | $15,664 | 91.7% | 8.8% | no (drawdown -58.3%) |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 5 | train | 538 | 43.5% | 0.91 | -100.0% | $1.10 | $106 | 27.2% | 58.2% | no (PF 0.905<1.10, Sharpe -0.27<0.40, drawdown -100.0%) |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 5 | holdout | 59 | 39.0% | 0.69 | -99.4% | $14.45 | $23,215 | 80.4% | 27.4% | no (trades 59<300, PF 0.689<1.10, Sharpe 0.17<0.40, drawdown -99.4%) |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 1 | train | 2873 | 50.9% | 1.31 | -27.2% | $19,797 | $4,571 | 0.0% | 0.0% | yes |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 1 | holdout | 1128 | 49.3% | 1.40 | -18.6% | $18,069 | $8,247 | 20.0% | 0.0% | yes |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 3 | train | 2873 | 50.9% | 1.31 | -54.3% | $54,390 | $8,575 | 41.2% | 3.8% | no (drawdown -54.3%) |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 3 | holdout | 1128 | 49.3% | 1.40 | -54.2% | $49,206 | $19,597 | 100.0% | 0.0% | no (drawdown -54.2%) |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 5 | train | 2873 | 50.9% | 1.31 | -67.8% | $88,984 | $11,172 | 63.5% | 12.5% | no (drawdown -67.8%) |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 5 | holdout | 64 | 40.6% | 0.71 | -92.8% | $180 | $28,649 | 87.3% | 14.1% | no (trades 64<300, PF 0.714<1.10, Sharpe -0.05<0.40, drawdown -92.8%) |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 1 | train | 755 | 36.8% | 0.81 | -99.9% | $5.05 | $2,481 | 0.0% | 7.1% | no (PF 0.813<1.10, Sharpe -0.69<0.40, drawdown -99.9%) |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 1 | holdout | 525 | 38.3% | 1.01 | -43.7% | $2,715 | $3,396 | 0.0% | 0.9% | no (PF 1.011<1.10, Sharpe 0.26<0.40, drawdown -43.7%) |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 3 | train | 579 | 36.8% | 0.89 | -99.8% | $7.82 | $429 | 2.8% | 54.1% | no (PF 0.894<1.10, Sharpe -0.73<0.40, drawdown -99.8%) |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 3 | holdout | 525 | 38.3% | 1.01 | -66.8% | $3,144 | $5,124 | 0.0% | 36.2% | no (PF 1.011<1.10, drawdown -66.8%) |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 5 | train | 557 | 36.8% | 0.93 | -100.0% | $0.09 | $120 | 6.9% | 64.8% | no (PF 0.931<1.10, Sharpe -0.21<0.40, drawdown -100.0%) |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 5 | holdout | 525 | 38.3% | 1.01 | -74.7% | $3,574 | $96.90 | 34.6% | 65.4% | no (PF 1.011<1.10, drawdown -74.7%) |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 1 | train | 1167 | 45.2% | 1.18 | -42.1% | $6,292 | $2,740 | 0.0% | 0.0% | no (drawdown -42.1%) |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 1 | holdout | 525 | 44.2% | 1.18 | -17.8% | $5,326 | $4,143 | 0.0% | 0.0% | yes |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 3 | train | 1165 | 45.2% | 1.17 | -80.9% | $13,536 | $3,108 | 5.6% | 15.8% | no (drawdown -80.9%) |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 3 | holdout | 525 | 44.2% | 1.18 | -31.8% | $10,977 | $7,392 | 27.6% | 17.3% | no (drawdown -31.8%) |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 5 | train | 714 | 42.0% | 0.95 | -97.4% | $180 | $2,660 | 18.2% | 26.5% | no (PF 0.954<1.10, Sharpe 0.02<0.40, drawdown -97.4%) |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 5 | holdout | 525 | 44.2% | 1.18 | -39.1% | $16,628 | $5,932 | 39.4% | 28.3% | no (drawdown -39.1%) |

## 1 DTE sensitivity to a 20% IV change

Same 1 DTE signals and the same 1 cent market. 0.80x and 1.20x replace the unscaled prior close. The base row is repeated so the three vols sit together.

| Book | Expiry | IV | Contracts | Window | Trades | Win | PF | Max DD | Ending | Median 12m | P(reach $10k) | P(ruin) | Gate |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| SPY VWAP | 1 DTE | prior close, 1 cent | 1 | train | 3282 | 50.2% | 1.12 | -72.5% | $10,120 | $3,614 | 0.0% | 16.7% | no (drawdown -72.5%) |
| SPY VWAP | 1 DTE | prior close, 1 cent | 1 | holdout | 1373 | 49.6% | 1.23 | -29.0% | $11,512 | $6,702 | 0.0% | 0.0% | yes |
| SPY VWAP | 1 DTE | prior close, 1 cent | 3 | train | 1568 | 47.4% | 0.97 | -98.5% | $130 | $5,266 | 21.8% | 34.9% | no (PF 0.968<1.10, Sharpe 0.17<0.40, drawdown -98.5%) |
| SPY VWAP | 1 DTE | prior close, 1 cent | 3 | holdout | 1366 | 49.6% | 1.23 | -60.5% | $29,543 | $13,909 | 76.7% | 9.5% | no (drawdown -60.5%) |
| SPY VWAP | 1 DTE | prior close, 1 cent | 5 | train | 131 | 42.7% | 0.60 | -94.3% | $155 | $1,687 | 29.1% | 8.9% | no (trades 131<300, PF 0.597<1.10, Sharpe -1.04<0.40, drawdown -94.3%) |
| SPY VWAP | 1 DTE | prior close, 1 cent | 5 | holdout | 150 | 42.7% | 0.86 | -94.2% | $198 | $18,652 | 61.3% | 37.6% | no (trades 150<300, PF 0.857<1.10, Sharpe -0.06<0.40, drawdown -94.2%) |
| SPY VWAP | 1 DTE | 0.80x prior close, 1 cent | 1 | train | 3282 | 50.2% | 1.20 | -40.5% | $15,140 | $4,062 | 0.0% | 5.9% | no (drawdown -40.5%) |
| SPY VWAP | 1 DTE | 0.80x prior close, 1 cent | 1 | holdout | 1373 | 49.7% | 1.33 | -16.6% | $14,826 | $8,014 | 4.8% | 0.0% | yes |
| SPY VWAP | 1 DTE | 0.80x prior close, 1 cent | 3 | train | 3281 | 50.2% | 1.20 | -71.8% | $40,480 | $7,051 | 33.9% | 26.7% | no (drawdown -71.8%) |
| SPY VWAP | 1 DTE | 0.80x prior close, 1 cent | 3 | holdout | 1373 | 49.7% | 1.33 | -36.7% | $39,477 | $18,710 | 92.1% | 7.9% | no (drawdown -36.7%) |
| SPY VWAP | 1 DTE | 0.80x prior close, 1 cent | 5 | train | 141 | 41.1% | 0.61 | -96.4% | $101 | $8,687 | 48.9% | 29.2% | no (trades 141<300, PF 0.610<1.10, Sharpe -1.12<0.40, drawdown -96.4%) |
| SPY VWAP | 1 DTE | 0.80x prior close, 1 cent | 5 | holdout | 1371 | 49.8% | 1.33 | -46.6% | $64,637 | $27,765 | 83.9% | 19.0% | no (drawdown -46.6%) |
| SPY VWAP | 1 DTE | 1.20x prior close, 1 cent | 1 | train | 1762 | 47.9% | 0.92 | -98.5% | $59.69 | $3,273 | 0.0% | 22.9% | no (PF 0.919<1.10, Sharpe -0.44<0.40, drawdown -98.5%) |
| SPY VWAP | 1 DTE | 1.20x prior close, 1 cent | 1 | holdout | 1373 | 49.5% | 1.16 | -39.2% | $9,017 | $5,717 | 0.0% | 0.5% | no (drawdown -39.2%) |
| SPY VWAP | 1 DTE | 1.20x prior close, 1 cent | 3 | train | 210 | 43.3% | 0.58 | -95.1% | $128 | $2,651 | 13.5% | 29.3% | no (trades 210<300, PF 0.581<1.10, Sharpe -0.98<0.40, drawdown -95.1%) |
| SPY VWAP | 1 DTE | 1.20x prior close, 1 cent | 3 | holdout | 1241 | 49.1% | 1.11 | -86.0% | $14,467 | $8,143 | 47.5% | 22.2% | no (drawdown -86.0%) |
| SPY VWAP | 1 DTE | 1.20x prior close, 1 cent | 5 | train | 123 | 43.1% | 0.58 | -92.5% | $203 | $883 | 10.7% | 10.0% | no (trades 123<300, PF 0.578<1.10, Sharpe -0.95<0.40, drawdown -92.5%) |
| SPY VWAP | 1 DTE | 1.20x prior close, 1 cent | 5 | holdout | 169 | 45.0% | 0.89 | -89.1% | $454 | $564 | 38.0% | 31.0% | no (trades 169<300, PF 0.888<1.10, Sharpe -0.05<0.40, drawdown -89.1%) |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 1 | train | 2873 | 50.9% | 1.31 | -27.2% | $19,797 | $4,571 | 0.0% | 0.0% | yes |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 1 | holdout | 1128 | 49.3% | 1.40 | -18.6% | $18,069 | $8,247 | 20.0% | 0.0% | yes |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 3 | train | 2873 | 50.9% | 1.31 | -54.3% | $54,390 | $8,575 | 41.2% | 3.8% | no (drawdown -54.3%) |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 3 | holdout | 1128 | 49.3% | 1.40 | -54.2% | $49,206 | $19,597 | 100.0% | 0.0% | no (drawdown -54.2%) |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 5 | train | 2873 | 50.9% | 1.31 | -67.8% | $88,984 | $11,172 | 63.5% | 12.5% | no (drawdown -67.8%) |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 5 | holdout | 64 | 40.6% | 0.71 | -92.8% | $180 | $28,649 | 87.3% | 14.1% | no (trades 64<300, PF 0.714<1.10, Sharpe -0.05<0.40, drawdown -92.8%) |
| QQQ Aggressive | 1 DTE | 0.80x prior close, 1 cent | 1 | train | 2873 | 51.1% | 1.43 | -20.5% | $25,176 | $5,257 | 6.1% | 0.0% | yes |
| QQQ Aggressive | 1 DTE | 0.80x prior close, 1 cent | 1 | holdout | 1128 | 49.7% | 1.54 | -16.4% | $22,371 | $9,753 | 47.9% | 0.0% | yes |
| QQQ Aggressive | 1 DTE | 0.80x prior close, 1 cent | 3 | train | 2873 | 51.1% | 1.43 | -38.4% | $70,527 | $10,808 | 67.8% | 0.2% | no (drawdown -38.4%) |
| QQQ Aggressive | 1 DTE | 0.80x prior close, 1 cent | 3 | holdout | 1128 | 49.7% | 1.54 | -43.8% | $62,113 | $24,235 | 99.5% | 0.5% | no (drawdown -43.8%) |
| QQQ Aggressive | 1 DTE | 0.80x prior close, 1 cent | 5 | train | 2873 | 51.1% | 1.43 | -46.6% | $115,879 | $15,580 | 78.8% | 8.7% | no (drawdown -46.6%) |
| QQQ Aggressive | 1 DTE | 0.80x prior close, 1 cent | 5 | holdout | 1105 | 49.8% | 1.54 | -88.1% | $101,448 | $38,251 | 93.8% | 7.4% | no (drawdown -88.1%) |
| QQQ Aggressive | 1 DTE | 1.20x prior close, 1 cent | 1 | train | 2873 | 50.7% | 1.23 | -33.0% | $15,753 | $4,088 | 0.0% | 0.0% | no (drawdown -33.0%) |
| QQQ Aggressive | 1 DTE | 1.20x prior close, 1 cent | 1 | holdout | 1128 | 49.0% | 1.31 | -22.4% | $14,878 | $7,115 | 16.8% | 0.0% | yes |
| QQQ Aggressive | 1 DTE | 1.20x prior close, 1 cent | 3 | train | 2873 | 50.7% | 1.23 | -69.7% | $42,260 | $6,857 | 29.4% | 8.3% | no (drawdown -69.7%) |
| QQQ Aggressive | 1 DTE | 1.20x prior close, 1 cent | 3 | holdout | 59 | 40.7% | 0.56 | -92.8% | $180 | $15,735 | 97.2% | 2.8% | no (trades 59<300, PF 0.560<1.10, Sharpe -0.93<0.40, drawdown -92.8%) |
| QQQ Aggressive | 1 DTE | 1.20x prior close, 1 cent | 5 | train | 2872 | 50.7% | 1.23 | -87.7% | $68,881 | $6,268 | 38.2% | 12.3% | no (drawdown -87.7%) |
| QQQ Aggressive | 1 DTE | 1.20x prior close, 1 cent | 5 | holdout | 47 | 42.6% | 0.66 | -87.5% | $314 | $21,342 | 77.2% | 15.9% | no (trades 47<300, PF 0.657<1.10, Sharpe -0.51<0.40, drawdown -87.5%) |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 1 | train | 1167 | 45.2% | 1.18 | -42.1% | $6,292 | $2,740 | 0.0% | 0.0% | no (drawdown -42.1%) |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 1 | holdout | 525 | 44.2% | 1.18 | -17.8% | $5,326 | $4,143 | 0.0% | 0.0% | yes |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 3 | train | 1165 | 45.2% | 1.17 | -80.9% | $13,536 | $3,108 | 5.6% | 15.8% | no (drawdown -80.9%) |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 3 | holdout | 525 | 44.2% | 1.18 | -31.8% | $10,977 | $7,392 | 27.6% | 17.3% | no (drawdown -31.8%) |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 5 | train | 714 | 42.0% | 0.95 | -97.4% | $180 | $2,660 | 18.2% | 26.5% | no (PF 0.954<1.10, Sharpe 0.02<0.40, drawdown -97.4%) |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 5 | holdout | 525 | 44.2% | 1.18 | -39.1% | $16,628 | $5,932 | 39.4% | 28.3% | no (drawdown -39.1%) |
| QQQ Trapdoor | 1 DTE | 0.80x prior close, 1 cent | 1 | train | 1167 | 45.3% | 1.29 | -26.9% | $8,377 | $2,988 | 0.0% | 0.0% | yes |
| QQQ Trapdoor | 1 DTE | 0.80x prior close, 1 cent | 1 | holdout | 525 | 44.6% | 1.31 | -13.8% | $6,973 | $4,743 | 0.0% | 0.0% | yes |
| QQQ Trapdoor | 1 DTE | 0.80x prior close, 1 cent | 3 | train | 1167 | 45.3% | 1.29 | -47.5% | $20,130 | $3,819 | 11.9% | 8.3% | no (drawdown -47.5%) |
| QQQ Trapdoor | 1 DTE | 0.80x prior close, 1 cent | 3 | holdout | 525 | 44.6% | 1.31 | -25.6% | $15,919 | $9,229 | 51.4% | 0.0% | yes |
| QQQ Trapdoor | 1 DTE | 0.80x prior close, 1 cent | 5 | train | 1167 | 45.3% | 1.29 | -56.0% | $31,884 | $3,955 | 26.9% | 25.4% | no (drawdown -56.0%) |
| QQQ Trapdoor | 1 DTE | 0.80x prior close, 1 cent | 5 | holdout | 525 | 44.6% | 1.31 | -30.9% | $24,865 | $12,578 | 64.3% | 13.4% | no (drawdown -30.9%) |
| QQQ Trapdoor | 1 DTE | 1.20x prior close, 1 cent | 1 | train | 1167 | 44.9% | 1.10 | -62.9% | $4,673 | $2,608 | 0.0% | 0.0% | no (PF 1.099<1.10, drawdown -62.9%) |
| QQQ Trapdoor | 1 DTE | 1.20x prior close, 1 cent | 1 | holdout | 525 | 44.0% | 1.10 | -25.7% | $4,083 | $3,693 | 0.0% | 0.0% | no (PF 1.098<1.10) |
| QQQ Trapdoor | 1 DTE | 1.20x prior close, 1 cent | 3 | train | 661 | 41.8% | 0.92 | -95.6% | $190 | $2,518 | 0.3% | 24.4% | no (PF 0.918<1.10, Sharpe -0.21<0.40, drawdown -95.6%) |
| QQQ Trapdoor | 1 DTE | 1.20x prior close, 1 cent | 3 | holdout | 525 | 44.0% | 1.10 | -43.2% | $7,249 | $5,785 | 1.2% | 26.7% | no (PF 1.098<1.10, drawdown -43.2%) |
| QQQ Trapdoor | 1 DTE | 1.20x prior close, 1 cent | 5 | train | 584 | 42.5% | 0.94 | -94.4% | $306 | $913 | 9.4% | 23.0% | no (PF 0.939<1.10, Sharpe -0.08<0.40, drawdown -94.4%) |
| QQQ Trapdoor | 1 DTE | 1.20x prior close, 1 cent | 5 | holdout | 525 | 44.0% | 1.10 | -54.2% | $10,414 | $758 | 31.6% | 30.6% | no (PF 1.098<1.10, drawdown -54.2%) |

## QQQ Aggressive 1 DTE, equity-tiered size

Pre-registered. The rule was written down before this score and was not changed after the numbers.

QQQ Aggressive, 1 DTE, unscaled prior close, 1 cent market, same-day 15:45 flat, fresh $2,500, daily cap 5. Each fill buys N contracts where N = min(5, max(1, floor(equity / 2500))). Equity is settled cash plus credits that are not due yet, after credits due this session have been added and before this fill's debit is subtracted. If N contracts do not fit settled cash, the signal is skipped. N is not cut down to a smaller lot.

This variant is not the sandbox book. The score does not send an order.

| Book | Expiry | IV | Contracts | Window | Trades | Win | PF | Max DD | Ending | Median 12m | P(reach $10k) | P(ruin) | Gate |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | tier | train | 2873 | 50.9% | 1.32 | -27.2% | $69,954 | $4,571 | 16.7% | 0.0% | yes |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | tier | holdout | 1128 | 49.3% | 1.42 | -24.8% | $61,877 | $10,464 | 60.1% | 0.0% | yes |

Holdout $61,877 on 1128 trades, win 49.3%, profit factor 1.42, max drawdown -24.8%, 12-month median $10,464, P(reach $10k) 60.1%, P(ruin) 0.0%, gate yes. Fills: 319 fills at 1 contract, 179 fills at 2 contracts, 34 fills at 3 contracts, 15 fills at 4 contracts, 581 fills at 5 contracts. Train $69,954 on 2873 trades, win 50.9%, profit factor 1.32, max drawdown -27.2%, 12-month median $4,571, P(reach $10k) 16.7%, P(ruin) 0.0%, gate yes. Fills: 958 fills at 1 contract, 321 fills at 2 contracts, 235 fills at 3 contracts, 188 fills at 4 contracts, 1171 fills at 5 contracts.

The cash mirror in the sandbox still uses the unscaled 0 DTE model and the book's fixed lot. This score does not change an order. QQQ Trapdoor's daily cap stays 3.
