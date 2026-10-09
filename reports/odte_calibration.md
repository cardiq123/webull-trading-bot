# 0DTE volatility check, 2026-10-09

Backtest only. Nothing was sent to a broker. Live trading stays off. The sandbox forward books were not changed.

The 11:36 SPY 777 call mid is $1.135. Black-Scholes at the Oct 8 VIX1D close of 10.24 prices it at $0.659. Matching the mid takes 1.67 times that close, 17.1% instead of 10.24, or +6.9 volatility points. The morning $1.05 fill implies 1.48 times the same close. The logged model near $0.55 lines up with the Oct 6 VIX1D close of 8.69, not with 10.24, so the live log looked closer to half the market than the prior-close formula does. On the holdout, QQQ Aggressive at the published model ends at $96,136 (1128 trades, profit factor 1.98). At 1.67 times volatility and a 1 cent market, it ends at $40,755 (1128 trades, profit factor 1.30). At twice volatility it ends at $13.88 (170 trades, profit factor 0.84). The 12-month chance of reaching $10,000 goes from 100.0% on the published model to 91.7% at the calibrated vol, and the chance of falling under $500 goes from 0.0% to 8.8%. QQQ Trapdoor goes from $12,265 to $2,715. SPY VWAP, one contract from $1,000, goes from $19,137 to $12.42. A 1 cent or 2 cent spread is a small change next to the volatility. 1 DTE and 2 DTE were already richer in the model than in the market, so this bump is only for the 0 DTE price.

## What the quote implies

At 11:36 ET, SPY 776.885, the 777 call was 1.13 / 1.14, mid $1.135. The Oct 8 VIX1D close is 10.24. The same Black-Scholes the books use prices that call at $0.659. The vol that matches the mid is 17.1%, which is 1.67 times that VIX1D close, or +6.9 volatility points.

The morning 776 call fill of $1.05, with SPY at 775.63 at 10:05:30, implies 15.2% and 1.48 times the same VIX1D close if that fill is taken as the price.

The book clock at 11:36 has 264 minutes left until 16:00. Making the Oct 8 VIX1D close match the $1.135 mid would take 728 minutes, about 12.1 hours. That is not a session clock. The cheap 0 DTE price is the volatility, not an early expiry.

The four model prices in the live log, $0.548, $2.51, $2.90, and $3.25, match about 8.7% vol. The Oct 6 VIX1D close is 8.69 and prices this call at $0.552. The Oct 8 close of 10.24 prices it at $0.659. A cache that stopped on Oct 6 would print the logged model. The re-score below still scales each day's own prior close, which is what the backtest already does.

Longer expiries at the same 11:36 spot, using the Oct 8 close of 10.24:

| Expiry | Market | Model at 10.24 | Logged model |
| --- | ---: | ---: | ---: |
| 0DTE | $1.135 | $0.659 | $0.548 |
| 1DTE | $2.155 | $2.974 | $2.510 |
| 2DTE | $2.800 | $3.429 | $2.900 |
| 3DTE | $3.675 | $3.835 | $3.250 |

1 DTE and 2 DTE are richer in the model than in the market. 3 DTE is close. The cheap print is the 0 DTE contract. These three books trade only 0 DTE, so the scale is applied only there.

## How the re-score is run

Train is 2017-02-16 through 2023-12-31. Holdout is a fresh account from 2024-01-01 through 2026-10-06. The signals are the frozen ones: SPY and QQQ 15-minute 2 SD continuation, and the QQQ Trapdoor short. The fill is still the next open, the stop and the 1R target are unchanged, and the option is still flat at 15:45. x1.0 with the book spread is the published model: half-spread the greater of $0.01 and 1.5% of the mid. The other rows keep that volatility scale and charge a 1 cent or 2 cent bid-ask, which is the width on the live 777 call. A ticket that does not fit settled cash is skipped whole. QQQ Aggressive is not cut from 3 contracts to 1. The one-position lock ends with the session, the same way the original score does, because the option is flat by the close.

QQQ Aggressive also replays every session that still has 12 months inside the window, from a fresh $2,500. Reach is equity of $10,000. Ruin is equity under $500.

## SPY VWAP

One at-the-money 0 DTE contract, 1R, $1,000, no daily count cap.

| Case | Window | Trades | Win | PF | Sharpe | Max DD | Ending |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| x1.0, book spread | train | 255 | 36.5% | 0.56 | -0.93 | -99.9% | $0.75 |
| x1.0, book spread | holdout | 1373 | 48.3% | 1.51 | 2.81 | -18.4% | $19,137 |
| x1.0, 1 cent wide | train | 3282 | 48.0% | 1.36 | 1.24 | -76.6% | $22,203 |
| x1.0, 1 cent wide | holdout | 1373 | 48.4% | 1.60 | 3.16 | -17.8% | $21,902 |
| x1.0, 2 cents wide | train | 257 | 36.6% | 0.57 | -0.81 | -99.9% | $0.60 |
| x1.0, 2 cents wide | holdout | 1373 | 48.3% | 1.55 | 2.93 | -18.4% | $20,557 |
| x1.5, 1 cent wide | train | 183 | 36.1% | 0.46 | -0.51 | -100.0% | $0.28 |
| x1.5, 1 cent wide | holdout | 1373 | 47.3% | 1.14 | 1.22 | -57.1% | $6,815 |
| x1.5, 2 cents wide | train | 137 | 32.8% | 0.35 | -1.46 | -99.8% | $1.64 |
| x1.5, 2 cents wide | holdout | 1371 | 47.2% | 1.10 | 1.07 | -77.6% | $5,433 |
| x2.0, 1 cent wide | train | 103 | 32.0% | 0.29 | -1.56 | -99.8% | $2.09 |
| x2.0, 1 cent wide | holdout | 154 | 42.9% | 0.72 | -1.29 | -98.5% | $15.30 |
| x2.0, 2 cents wide | train | 97 | 33.0% | 0.27 | -1.57 | -99.8% | $2.41 |
| x2.0, 2 cents wide | holdout | 149 | 43.6% | 0.72 | -0.21 | -97.9% | $20.70 |
| x1.67 calibrated, 1 cent wide | train | 163 | 36.2% | 0.43 | -0.09 | -100.0% | $0.20 |
| x1.67 calibrated, 1 cent wide | holdout | 311 | 44.7% | 0.86 | -0.65 | -98.9% | $12.42 |
| x1.67 calibrated, 2 cents wide | train | 123 | 33.3% | 0.32 | -1.46 | -99.8% | $1.72 |
| x1.67 calibrated, 2 cents wide | holdout | 258 | 43.8% | 0.84 | -0.50 | -99.9% | $1.24 |

## QQQ Aggressive

Three at-the-money 0 DTE contracts, 1R, $2,500, at most 5 fills a day.

| Case | Window | Trades | Win | PF | Sharpe | Max DD | Ending |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| x1.0, book spread | train | 2873 | 48.7% | 1.71 | 2.38 | -34.3% | $104,070 |
| x1.0, book spread | holdout | 1128 | 47.5% | 1.98 | 3.48 | -25.1% | $96,136 |
| x1.0, 1 cent wide | train | 2873 | 49.0% | 1.82 | 2.86 | -28.4% | $115,935 |
| x1.0, 1 cent wide | holdout | 1128 | 47.6% | 2.08 | 3.69 | -22.8% | $103,296 |
| x1.0, 2 cents wide | train | 2873 | 48.7% | 1.74 | 2.41 | -34.3% | $107,699 |
| x1.0, 2 cents wide | holdout | 1128 | 47.6% | 2.03 | 3.53 | -24.7% | $100,048 |
| x1.5, 1 cent wide | train | 2873 | 47.7% | 1.27 | 1.29 | -65.0% | $49,589 |
| x1.5, 1 cent wide | holdout | 1128 | 46.3% | 1.43 | 2.08 | -47.0% | $54,456 |
| x1.5, 2 cents wide | train | 569 | 42.7% | 0.85 | -0.82 | -99.9% | $2.44 |
| x1.5, 2 cents wide | holdout | 1128 | 46.3% | 1.40 | 1.93 | -51.1% | $51,130 |
| x2.0, 1 cent wide | train | 400 | 42.2% | 0.78 | 0.03 | -99.9% | $3.37 |
| x2.0, 1 cent wide | holdout | 170 | 42.9% | 0.84 | -0.29 | -99.4% | $13.88 |
| x2.0, 2 cents wide | train | 281 | 42.3% | 0.66 | -0.82 | -99.8% | $5.45 |
| x2.0, 2 cents wide | holdout | 66 | 42.4% | 0.59 | -0.75 | -99.2% | $36.84 |
| x1.67 calibrated, 1 cent wide | train | 587 | 43.1% | 0.86 | -0.67 | -100.0% | $0.97 |
| x1.67 calibrated, 1 cent wide | holdout | 1128 | 46.0% | 1.30 | 1.65 | -58.3% | $40,755 |
| x1.67 calibrated, 2 cents wide | train | 514 | 43.0% | 0.84 | -0.50 | -99.9% | $2.64 |
| x1.67 calibrated, 2 cents wide | holdout | 1128 | 46.0% | 1.27 | 1.51 | -64.5% | $37,420 |

| Case | Window | Starts | Median ending | P(reach $10k) | P(ruin) |
| --- | --- | ---: | ---: | ---: | ---: |
| x1.0, book spread | train | 1440 | $14,347 | 83.5% | 0.0% |
| x1.0, book spread | holdout | 434 | $35,316 | 100.0% | 0.0% |
| x1.0, 1 cent wide | train | 1440 | $15,980 | 84.8% | 0.0% |
| x1.0, 1 cent wide | holdout | 434 | $37,863 | 100.0% | 0.0% |
| x1.0, 2 cents wide | train | 1440 | $14,739 | 83.5% | 0.0% |
| x1.0, 2 cents wide | holdout | 434 | $36,672 | 100.0% | 0.0% |
| x1.5, 1 cent wide | train | 1440 | $5,470 | 33.3% | 22.6% |
| x1.5, 1 cent wide | holdout | 434 | $20,359 | 93.1% | 6.9% |
| x1.5, 2 cents wide | train | 1440 | $4,041 | 27.4% | 29.9% |
| x1.5, 2 cents wide | holdout | 434 | $19,181 | 92.6% | 7.8% |
| x2.0, 1 cent wide | train | 1440 | $53.77 | 4.0% | 74.6% |
| x2.0, 1 cent wide | holdout | 434 | $6,038 | 59.4% | 48.2% |
| x2.0, 2 cents wide | train | 1440 | $45.86 | 3.1% | 79.2% |
| x2.0, 2 cents wide | holdout | 434 | $2,461 | 41.5% | 68.7% |
| x1.67 calibrated, 1 cent wide | train | 1440 | $2,801 | 23.0% | 36.4% |
| x1.67 calibrated, 1 cent wide | holdout | 434 | $15,664 | 91.7% | 8.8% |
| x1.67 calibrated, 2 cents wide | train | 1440 | $1,312 | 18.5% | 51.6% |
| x1.67 calibrated, 2 cents wide | holdout | 434 | $14,426 | 91.0% | 9.9% |

## QQQ Trapdoor

One at-the-money 0 DTE put, 1R, $2,500, at most 3 fills a day.

| Case | Window | Trades | Win | PF | Sharpe | Max DD | Ending |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| x1.0, book spread | train | 1167 | 40.5% | 1.67 | 2.01 | -16.2% | $14,425 |
| x1.0, book spread | holdout | 525 | 40.6% | 1.77 | 2.99 | -6.5% | $12,265 |
| x1.0, 1 cent wide | train | 1167 | 41.0% | 1.77 | 2.28 | -13.4% | $15,799 |
| x1.0, 1 cent wide | holdout | 525 | 41.1% | 1.85 | 3.17 | -5.9% | $13,081 |
| x1.0, 2 cents wide | train | 1167 | 40.5% | 1.68 | 2.04 | -15.8% | $14,765 |
| x1.0, 2 cents wide | holdout | 525 | 40.6% | 1.79 | 3.05 | -6.4% | $12,609 |
| x1.5, 1 cent wide | train | 1167 | 39.8% | 1.14 | 0.49 | -82.9% | $5,718 |
| x1.5, 1 cent wide | holdout | 525 | 38.9% | 1.15 | 1.04 | -21.0% | $5,130 |
| x1.5, 2 cents wide | train | 805 | 37.0% | 0.83 | -0.95 | -99.9% | $3.50 |
| x1.5, 2 cents wide | holdout | 525 | 38.5% | 1.12 | 0.88 | -23.8% | $4,631 |
| x2.0, 1 cent wide | train | 579 | 36.1% | 0.72 | -1.22 | -99.8% | $5.13 |
| x2.0, 1 cent wide | holdout | 436 | 38.1% | 0.85 | -0.93 | -99.4% | $17.41 |
| x2.0, 2 cents wide | train | 558 | 36.0% | 0.71 | -0.82 | -99.8% | $6.26 |
| x2.0, 2 cents wide | holdout | 416 | 37.7% | 0.84 | -1.29 | -99.2% | $22.21 |
| x1.67 calibrated, 1 cent wide | train | 755 | 36.8% | 0.81 | -0.69 | -99.9% | $5.05 |
| x1.67 calibrated, 1 cent wide | holdout | 525 | 38.3% | 1.01 | 0.26 | -43.7% | $2,715 |
| x1.67 calibrated, 2 cents wide | train | 668 | 36.5% | 0.78 | -1.01 | -99.8% | $5.20 |
| x1.67 calibrated, 2 cents wide | holdout | 525 | 37.7% | 0.98 | 0.09 | -51.3% | $2,210 |

The cash mirror in the sandbox still uses the unscaled model. This score does not change an order.
