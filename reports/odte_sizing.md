# Contract size and one-minute checks

Backtest only. Nothing was sent to a broker. Live trading stays off. The sandbox forward books were not changed.

At x1.67 0 DTE volatility and a 1 cent market, QQQ Aggressive at 3 contracts still matches the earlier score: holdout $40,755 on 1128 trades, profit factor 1.30, max drawdown -58.3%, 12-month median $15,664, P(reach $10k) 91.7%, P(ruin) 8.8%. The train account is spent, ending $0.97 after 587 trades, with P(ruin) 36.4%. Five, ten, and fifteen contracts make the 0 DTE ticket too expensive for a $2,500 start. The 15-contract holdout takes 29 trades and ends at $56.65, and P(ruin) is 68.0%. QQQ Trapdoor at 15 of those 0 DTE contracts ends the holdout at $178 on 175 trades. The same Trapdoor signals on an unscaled 1 DTE contract do fit 15 lots on the holdout: 525 trades, ending $44,885, profit factor 1.18, but the typical 12-month start ends at $891 and P(reach $10k) is 23.5%. Aggressive at 3 unscaled 1 DTE contracts keeps every signal and ends the holdout at $49,206 and the train at $54,390. Checking every minute instead of every 5 or 15 minutes changes the underlying exit price on 26 of 4797 Aggressive signals, 5 of 2081 Trapdoor signals, and 33 of 5484 SPY signals. The clearest same-trade comparison is Trapdoor 1 DTE at 15 contracts: the holdout goes from $44,885 on the current bar to $44,505 on the minute. A 1-minute bar approximates a 5-second check. This cache has no 5-second bars. 1 DTE and 2 DTE use the unscaled prior close.

## How this is scored

Train is 2017-02-16 through 2023-12-31. Holdout is a fresh account from 2024-01-01 through 2026-10-06. QQQ Aggressive and QQQ Trapdoor start at $2,500. SPY VWAP starts at $1,000. Aggressive still takes at most 5 fills a day. Trapdoor still takes at most 3. SPY has no daily count cap. One position. The whole ticket is bought or the signal is skipped. A 15-lot is not cut down to whatever cash can afford.

The 0 DTE rows use each day's prior VIX1D close, or the prior VIX close when that print is missing, times x1.67 (the unrounded ratio is 1.6699), and a 1 cent bid-ask. That is half a cent on the bid and half a cent on the ask. The 1 DTE and 2 DTE rows use the same prior close with no multiplier. At the 11:36 SPY quote the model was already richer than the market on those two expiries, so the 0 DTE bump is not applied again. 1 DTE expires at 16:00 on the next trading session. 2 DTE expires two trading sessions out. A Friday signal's 1 DTE contract expires Monday. The underlying stop, the 1R target, and the 15:45 flat are unchanged, so the longer contract still has time value when it is sold.

Reach is equity of $10,000. Ruin is equity under $500. Ending is one account started at the first session of that window. The median and the two probabilities start a fresh account on every later session that still has a full 12 months inside the window. An account that goes broke stops taking the later signals. A fresh account started the next year still takes them. That is why one holdout path can end near zero while the typical 12-month start does not, and the reverse.

There are no 5-second bars. The finest Dukascopy file here is 1 minute, for SPY and QQQ, from 2017-02-16 09:30:00-05:00 through 2026-10-06 15:59:00-04:00. A 1-minute bar approximates a 5-second check. The entry is the first 1-minute open at the signal's fill time. On this file that open is the same price as the next 5-minute or 15-minute open, so the entry matches the current backtest except where a minute is missing. The exit is the first 1-minute bar that touches the stop or the target, instead of waiting for the 5-minute or 15-minute bar. When both levels trade inside one of those coarser bars, the earlier minute decides. When both trade inside the same minute, the stop still wins.

What the 1-minute file changed, before pricing: spy_vwap: 5482 of 5484 signals kept, 1 entries changed, 33 exit prices changed, 19 exit reasons changed, 0 skipped because the first minute opened through the stop, 2 missing a minute. qqq_aggr: 4796 of 4797 signals kept, 2 entries changed, 26 exit prices changed, 15 exit reasons changed, 0 skipped because the first minute opened through the stop, 1 missing a minute. trapdoor: 2081 of 2081 signals kept, 1 entries changed, 5 exit prices changed, 3 exit reasons changed, 0 skipped because the first minute opened through the stop, 0 missing a minute.

## Fixed size at the current bar timing

QQQ Aggressive and QQQ Trapdoor. The signal and the exit bar are unchanged. Only the contract count, and on the later rows the expiry, change.

| Book | Expiry | IV | Contracts | Window | Ending | Max DD | Median 12m | P(reach $10k) | P(ruin) | Trades | Win | PF |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 3 | train | $0.97 | -100.0% | $2,801 | 23.0% | 36.4% | 587 | 43.1% | 0.86 |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 3 | holdout | $40,755 | -58.3% | $15,664 | 91.7% | 8.8% | 1128 | 46.0% | 1.30 |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 5 | train | $1.10 | -100.0% | $106 | 27.2% | 58.2% | 538 | 43.5% | 0.91 |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 5 | holdout | $14.45 | -99.4% | $23,215 | 80.4% | 27.4% | 59 | 39.0% | 0.69 |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 10 | train | $2.83 | -99.9% | $110 | 26.3% | 75.8% | 80 | 38.8% | 0.58 |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 10 | holdout | $53.90 | -97.8% | $211 | 46.3% | 56.5% | 26 | 38.5% | 0.57 |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 15 | train | $2.51 | -99.9% | $147 | 28.1% | 82.8% | 67 | 40.3% | 0.65 |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 15 | holdout | $56.65 | -99.1% | $242 | 35.5% | 68.0% | 29 | 37.9% | 0.79 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 1 | train | $19,797 | -27.2% | $4,571 | 0.0% | 0.0% | 2873 | 50.9% | 1.31 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 1 | holdout | $18,069 | -18.6% | $8,247 | 20.0% | 0.0% | 1128 | 49.3% | 1.40 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 3 | train | $54,390 | -54.3% | $8,575 | 41.2% | 3.8% | 2873 | 50.9% | 1.31 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 3 | holdout | $49,206 | -54.2% | $19,597 | 100.0% | 0.0% | 1128 | 49.3% | 1.40 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 5 | train | $88,984 | -67.8% | $11,172 | 63.5% | 12.5% | 2873 | 50.9% | 1.31 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 5 | holdout | $180 | -92.8% | $28,649 | 87.3% | 14.1% | 64 | 40.6% | 0.71 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 10 | train | $174,991 | -87.0% | $4,329 | 50.2% | 14.2% | 2867 | 50.9% | 1.31 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 10 | holdout | $402 | -86.2% | $42,543 | 56.5% | 15.2% | 15 | 40.0% | 0.46 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 15 | train | $78.82 | -97.6% | $1,421 | 34.7% | 19.3% | 150 | 44.7% | 0.83 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 15 | holdout | $571 | -88.5% | $1,055 | 36.6% | 7.1% | 40 | 45.0% | 0.87 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 1 | train | $15,900 | -32.9% | $4,143 | 0.0% | 0.0% | 2873 | 51.1% | 1.24 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 1 | holdout | $14,360 | -23.0% | $6,934 | 16.1% | 0.0% | 1128 | 49.8% | 1.29 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 3 | train | $42,699 | -68.4% | $7,052 | 29.4% | 8.4% | 2873 | 51.1% | 1.24 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 3 | holdout | $88.68 | -96.5% | $14,729 | 90.6% | 9.9% | 72 | 41.7% | 0.66 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 5 | train | $69,371 | -87.8% | $6,694 | 38.1% | 11.7% | 2870 | 51.1% | 1.24 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 5 | holdout | $313 | -88.3% | $18,467 | 59.0% | 23.5% | 55 | 41.8% | 0.73 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 10 | train | $480 | -94.1% | $1,507 | 34.4% | 13.4% | 503 | 46.9% | 0.96 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 10 | holdout | $644 | -80.2% | $1,087 | 30.6% | 4.1% | 13 | 46.2% | 0.49 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 15 | train | $379 | -89.4% | $2,136 | 38.7% | 9.8% | 114 | 45.6% | 0.80 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 15 | holdout | $462 | -93.7% | $1,370 | 15.4% | 0.5% | 41 | 46.3% | 0.88 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 3 | train | $7.82 | -99.8% | $429 | 2.8% | 54.1% | 579 | 36.8% | 0.89 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 3 | holdout | $3,144 | -66.8% | $5,124 | 0.0% | 36.2% | 525 | 38.3% | 1.01 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 5 | train | $0.09 | -100.0% | $120 | 6.9% | 64.8% | 557 | 36.8% | 0.93 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 5 | holdout | $3,574 | -74.7% | $96.90 | 34.6% | 65.4% | 525 | 38.3% | 1.01 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 10 | train | $4.09 | -99.9% | $67.04 | 21.7% | 79.3% | 136 | 37.5% | 0.73 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 10 | holdout | $4,648 | -87.0% | $104 | 17.3% | 84.3% | 525 | 38.3% | 1.01 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 15 | train | $-0.12 | -100.0% | $71.75 | 23.8% | 83.8% | 102 | 35.3% | 0.74 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 15 | holdout | $178 | -98.7% | $132 | 19.8% | 91.9% | 175 | 37.1% | 0.97 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 1 | train | $6,292 | -42.1% | $2,740 | 0.0% | 0.0% | 1167 | 45.2% | 1.18 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 1 | holdout | $5,326 | -17.8% | $4,143 | 0.0% | 0.0% | 525 | 44.2% | 1.18 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 3 | train | $13,536 | -80.9% | $3,108 | 5.6% | 15.8% | 1165 | 45.2% | 1.17 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 3 | holdout | $10,977 | -31.8% | $7,392 | 27.6% | 17.3% | 525 | 44.2% | 1.18 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 5 | train | $180 | -97.4% | $2,660 | 18.2% | 26.5% | 714 | 42.0% | 0.95 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 5 | holdout | $16,628 | -39.1% | $5,932 | 39.4% | 28.3% | 525 | 44.2% | 1.18 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 10 | train | $370 | -96.7% | $974 | 19.4% | 30.1% | 665 | 42.0% | 0.98 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 10 | holdout | $30,757 | -47.4% | $650 | 27.2% | 37.3% | 525 | 44.2% | 1.18 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 15 | train | $270 | -94.4% | $1,191 | 24.5% | 33.0% | 143 | 42.7% | 0.82 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 15 | holdout | $44,885 | -51.0% | $891 | 23.5% | 3.0% | 525 | 44.2% | 1.18 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 1 | train | $4,848 | -56.6% | $2,605 | 0.0% | 0.0% | 1167 | 45.4% | 1.11 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 1 | holdout | $4,035 | -24.9% | $3,664 | 0.0% | 0.0% | 525 | 44.6% | 1.10 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 3 | train | $173 | -95.9% | $2,525 | 0.6% | 18.3% | 668 | 42.4% | 0.92 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 3 | holdout | $7,106 | -44.8% | $5,750 | 0.0% | 11.8% | 525 | 44.6% | 1.10 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 5 | train | $363 | -93.2% | $2,165 | 13.8% | 18.9% | 603 | 43.3% | 0.94 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 5 | holdout | $9,733 | -63.6% | $1,879 | 32.9% | 19.6% | 524 | 44.5% | 1.09 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 10 | train | $750 | -91.2% | $1,331 | 7.8% | 24.4% | 521 | 43.2% | 0.97 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 10 | holdout | $17,732 | -73.5% | $870 | 22.4% | 0.0% | 521 | 44.5% | 1.10 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 15 | train | $569 | -87.8% | $1,555 | 11.0% | 9.3% | 137 | 43.1% | 0.83 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 15 | holdout | $979 | -91.9% | $1,251 | 13.6% | 0.0% | 117 | 41.0% | 0.96 |

## Fifteen contracts, current timing next to one-minute checks

Same 15-contract ticket. Current timing is the bar the book already uses: 15 minutes for the VWAP books, 5 minutes for Trapdoor. One-minute timing enters on the first minute after the signal bar and exits on the first minute that touches the stop or the target.

| Book | Expiry | IV | Check | Window | Ending | Max DD | Median 12m | P(reach $10k) | P(ruin) | Trades | Win | PF |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | current | train | $2.51 | -99.9% | $147 | 28.1% | 82.8% | 67 | 40.3% | 0.65 |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | current | holdout | $56.65 | -99.1% | $242 | 35.5% | 68.0% | 29 | 37.9% | 0.79 |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 1-minute | train | $14.86 | -99.4% | $131 | 24.3% | 85.1% | 70 | 40.0% | 0.65 |
| QQQ Aggressive | 0 DTE | x1.67 prior close, 1 cent | 1-minute | holdout | $29.10 | -99.5% | $209 | 31.1% | 73.5% | 24 | 37.5% | 0.76 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | current | train | $78.82 | -97.6% | $1,421 | 34.7% | 19.3% | 150 | 44.7% | 0.83 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | current | holdout | $571 | -88.5% | $1,055 | 36.6% | 7.1% | 40 | 45.0% | 0.87 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 1-minute | train | $149 | -95.4% | $1,479 | 36.2% | 20.6% | 132 | 44.7% | 0.81 |
| QQQ Aggressive | 1 DTE | prior close, 1 cent | 1-minute | holdout | $813 | -83.5% | $1,016 | 34.1% | 7.6% | 41 | 46.3% | 0.88 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | current | train | $379 | -89.4% | $2,136 | 38.7% | 9.8% | 114 | 45.6% | 0.80 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | current | holdout | $462 | -93.7% | $1,370 | 15.4% | 0.5% | 41 | 46.3% | 0.88 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 1-minute | train | $341 | -89.7% | $2,132 | 39.0% | 9.4% | 129 | 45.0% | 0.82 |
| QQQ Aggressive | 2 DTE | prior close, 1 cent | 1-minute | holdout | $1,154 | -84.3% | $1,358 | 14.3% | 1.8% | 41 | 48.8% | 0.92 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | current | train | $-0.12 | -100.0% | $71.75 | 23.8% | 83.8% | 102 | 35.3% | 0.74 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | current | holdout | $178 | -98.7% | $132 | 19.8% | 91.9% | 175 | 37.1% | 0.97 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 1-minute | train | $8.30 | -99.8% | $67.13 | 23.4% | 84.6% | 92 | 35.9% | 0.73 |
| QQQ Trapdoor | 0 DTE | x1.67 prior close, 1 cent | 1-minute | holdout | $58.31 | -99.6% | $124 | 18.9% | 92.6% | 173 | 37.0% | 0.97 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | current | train | $270 | -94.4% | $1,191 | 24.5% | 33.0% | 143 | 42.7% | 0.82 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | current | holdout | $44,885 | -51.0% | $891 | 23.5% | 3.0% | 525 | 44.2% | 1.18 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 1-minute | train | $248 | -94.8% | $1,196 | 25.1% | 31.5% | 143 | 42.7% | 0.82 |
| QQQ Trapdoor | 1 DTE | prior close, 1 cent | 1-minute | holdout | $44,505 | -51.2% | $883 | 22.4% | 4.6% | 525 | 44.2% | 1.18 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | current | train | $569 | -87.8% | $1,555 | 11.0% | 9.3% | 137 | 43.1% | 0.83 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | current | holdout | $979 | -91.9% | $1,251 | 13.6% | 0.0% | 117 | 41.0% | 0.96 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 1-minute | train | $660 | -85.9% | $1,552 | 12.2% | 8.8% | 135 | 43.0% | 0.84 |
| QQQ Trapdoor | 2 DTE | prior close, 1 cent | 1-minute | holdout | $935 | -92.3% | $1,251 | 13.6% | 0.0% | 117 | 41.0% | 0.96 |
| SPY VWAP | 0 DTE | x1.67 prior close, 1 cent | current | train | $9.51 | -99.0% | $128 | 3.5% | 99.5% | 13 | 23.1% | 0.37 |
| SPY VWAP | 0 DTE | x1.67 prior close, 1 cent | current | holdout | $138 | -88.9% | $203 | 10.0% | 94.1% | 4 | 50.0% | 0.32 |
| SPY VWAP | 0 DTE | x1.67 prior close, 1 cent | 1-minute | train | $12.63 | -98.7% | $124 | 2.3% | 100.0% | 13 | 23.1% | 0.37 |
| SPY VWAP | 0 DTE | x1.67 prior close, 1 cent | 1-minute | holdout | $167 | -86.6% | $210 | 4.1% | 95.9% | 3 | 33.3% | 0.23 |
| SPY VWAP | 1 DTE | prior close, 1 cent | current | train | $471 | -83.5% | $1,000 | 0.1% | 8.1% | 51 | 51.0% | 0.91 |
| SPY VWAP | 1 DTE | prior close, 1 cent | current | holdout | $1,000 | 0.0% | $1,000 | 0.0% | 0.0% | 0 | 0.0% | n/a |
| SPY VWAP | 1 DTE | prior close, 1 cent | 1-minute | train | $440 | -84.4% | $1,000 | 0.5% | 9.5% | 50 | 52.0% | 0.90 |
| SPY VWAP | 1 DTE | prior close, 1 cent | 1-minute | holdout | $1,000 | 0.0% | $1,000 | 0.0% | 0.0% | 0 | 0.0% | n/a |
| SPY VWAP | 2 DTE | prior close, 1 cent | current | train | $684 | -31.6% | $1,000 | 0.0% | 0.0% | 2 | 0.0% | 0.00 |
| SPY VWAP | 2 DTE | prior close, 1 cent | current | holdout | $1,000 | 0.0% | $1,000 | 0.0% | 0.0% | 0 | 0.0% | n/a |
| SPY VWAP | 2 DTE | prior close, 1 cent | 1-minute | train | $683 | -31.7% | $1,000 | 0.0% | 0.0% | 2 | 0.0% | 0.00 |
| SPY VWAP | 2 DTE | prior close, 1 cent | 1-minute | holdout | $1,000 | 0.0% | $1,000 | 0.0% | 0.0% | 0 | 0.0% | n/a |

The cash mirror in the sandbox still uses the unscaled 0 DTE model and the book's fixed lot. This score does not change an order. QQQ Trapdoor's daily cap stays 3.
