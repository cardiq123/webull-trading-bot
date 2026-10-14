# Neckline break

Backtests only. Nothing was sent to a broker. Live trading stays off. The sandbox forward books were not changed. The rules in `reports/neckline_rules.json` were written before any metric. Paul's 2026-10-08 chart is an illustration, not a trial.

The quick scalp does not clear the gate on SPY or QQQ, in shares or in 0 DTE. Its planned reward-to-risk is wider than the confirmed 1R entry when the target is the neckline, and it is 2.0 when that is the target, but the win rate is lower and the $2,500 account finishes below the start on every scalp cell. The confirmed-close books are the comparison, not a stack with the scalp. A holdout account that finishes above $2,500 still fails when the training account dies, the drawdown is past -30%, or the q-value and deflated Sharpe miss the line.

One pre-registered cell cleared every line of the gate: QQQ_confirmed_short_r1_0dte. It is the QQQ short mirror, one at-the-money 0 DTE put, with the 1R exit. It is not the scalp and it is not the long neckline close. It was not added to the live list and no sandbox book was created. The option price is Black-Scholes, not a listed chain.

Training account first, then the fresh holdout, for the scalp and the confirmed base entry:

SPY 0dte scalp neckline train: 1251 trades, win 17.7%, planned R:R 8.07, profit factor 0.46, Sharpe -1.98, max drawdown -100.0%, ending $0 from $2,500, random ending $4. SPY 0dte scalp neckline holdout: 1176 trades, win 21.3%, planned R:R 9.85, profit factor 0.78, Sharpe -2.06, max drawdown -82.5%, ending $496 from $2,500, random ending $12.
SPY 0dte scalp r2 train: 1134 trades, win 21.1%, planned R:R 2.00, profit factor 0.36, Sharpe -2.06, max drawdown -100.0%, ending $0 from $2,500, random ending $1. SPY 0dte scalp r2 holdout: 1192 trades, win 28.3%, planned R:R 2.00, profit factor 0.76, Sharpe -2.29, max drawdown -79.2%, ending $545 from $2,500, random ending $57.
SPY 0dte confirmed r1 train: 887 trades, win 36.0%, planned R:R 1.00, profit factor 0.81, Sharpe -0.59, max drawdown -100.0%, ending $1 from $2,500, random ending $0. SPY 0dte confirmed r1 holdout: 626 trades, win 39.9%, planned R:R 1.00, profit factor 1.22, Sharpe 1.10, max drawdown -37.2%, ending $5,919 from $2,500, random ending $1,112.
SPY 0dte confirmed measured train: 1007 trades, win 38.7%, planned R:R 1.07, profit factor 0.83, Sharpe -1.09, max drawdown -99.9%, ending $2 from $2,500, random ending $0. SPY 0dte confirmed measured holdout: 625 trades, win 40.2%, planned R:R 1.09, profit factor 2.28, Sharpe 0.61, max drawdown -27.3%, ending $21,539 from $2,500, random ending $1,112.
SPY 0dte confirmed vwap2 train: 878 trades, win 28.4%, planned R:R 0.65, profit factor 0.69, Sharpe -0.77, max drawdown -99.9%, ending $3 from $2,500, random ending $0. SPY 0dte confirmed vwap2 holdout: 722 trades, win 31.4%, planned R:R 0.72, profit factor 0.89, Sharpe -0.19, max drawdown -76.6%, ending $1,297 from $2,500, random ending $829.
SPY shares scalp neckline train: 1412 trades, win 4.8%, planned R:R 8.95, profit factor 0.03, Sharpe -18.69, max drawdown -75.0%, ending $626 from $2,500, random ending $574. SPY shares scalp neckline holdout: 597 trades, win 4.4%, planned R:R 8.48, profit factor 0.03, Sharpe -22.01, max drawdown -44.6%, ending $1,386 from $2,500, random ending $1,347.
SPY shares scalp r2 train: 1415 trades, win 3.3%, planned R:R 2.00, profit factor 0.02, Sharpe -21.40, max drawdown -75.5%, ending $613 from $2,500, random ending $592. SPY shares scalp r2 holdout: 597 trades, win 2.7%, planned R:R 2.00, profit factor 0.02, Sharpe -23.27, max drawdown -44.3%, ending $1,392 from $2,500, random ending $1,336.
SPY shares confirmed r1 train: 1254 trades, win 31.9%, planned R:R 1.00, profit factor 0.28, Sharpe -5.61, max drawdown -70.7%, ending $732 from $2,500, random ending $659. SPY shares confirmed r1 holdout: 487 trades, win 31.4%, planned R:R 1.00, profit factor 0.26, Sharpe -6.88, max drawdown -37.4%, ending $1,567 from $2,500, random ending $1,507.
QQQ 0dte scalp neckline train: 1418 trades, win 18.1%, planned R:R 8.24, profit factor 0.54, Sharpe -0.77, max drawdown -100.0%, ending $1 from $2,500, random ending $-0. QQQ 0dte scalp neckline holdout: 1070 trades, win 20.8%, planned R:R 9.85, profit factor 0.97, Sharpe -0.04, max drawdown -36.6%, ending $2,264 from $2,500, random ending $923.
QQQ 0dte scalp r2 train: 1214 trades, win 20.5%, planned R:R 2.00, profit factor 0.36, Sharpe -1.45, max drawdown -100.0%, ending $1 from $2,500, random ending $1. QQQ 0dte scalp r2 holdout: 1084 trades, win 28.6%, planned R:R 2.00, profit factor 0.90, Sharpe -0.65, max drawdown -40.2%, ending $1,710 from $2,500, random ending $20,190.
QQQ 0dte confirmed r1 train: 1370 trades, win 39.0%, planned R:R 1.00, profit factor 5.42, Sharpe 0.40, max drawdown -25.1%, ending $91,009 from $2,500, random ending $0. QQQ 0dte confirmed r1 holdout: 537 trades, win 38.9%, planned R:R 1.00, profit factor 5.12, Sharpe 0.70, max drawdown -20.6%, ending $56,494 from $2,500, random ending $1,823.
QQQ 0dte confirmed measured train: 1381 trades, win 40.8%, planned R:R 0.94, profit factor 5.59, Sharpe 0.39, max drawdown -39.7%, ending $88,070 from $2,500, random ending $0. QQQ 0dte confirmed measured holdout: 546 trades, win 40.8%, planned R:R 0.98, profit factor 6.14, Sharpe 0.70, max drawdown -22.4%, ending $66,892 from $2,500, random ending $1,823.
QQQ 0dte confirmed vwap2 train: 1492 trades, win 33.2%, planned R:R 0.82, profit factor 8.64, Sharpe 0.40, max drawdown -48.1%, ending $122,568 from $2,500, random ending $38,827. QQQ 0dte confirmed vwap2 holdout: 588 trades, win 37.6%, planned R:R 0.81, profit factor 6.10, Sharpe 0.67, max drawdown -24.3%, ending $52,084 from $2,500, random ending $26,971.
QQQ shares scalp neckline train: 1288 trades, win 9.0%, planned R:R 8.30, profit factor 0.07, Sharpe -14.72, max drawdown -73.6%, ending $660 from $2,500, random ending $563. QQQ shares scalp neckline holdout: 555 trades, win 6.7%, planned R:R 9.66, profit factor 0.06, Sharpe -17.53, max drawdown -44.0%, ending $1,400 from $2,500, random ending $1,364.
QQQ shares scalp r2 train: 1289 trades, win 4.8%, planned R:R 2.00, profit factor 0.03, Sharpe -16.25, max drawdown -74.7%, ending $631 from $2,500, random ending $575. QQQ shares scalp r2 holdout: 557 trades, win 5.4%, planned R:R 2.00, profit factor 0.04, Sharpe -18.82, max drawdown -43.9%, ending $1,401 from $2,500, random ending $1,643.
QQQ shares confirmed r1 train: 1180 trades, win 36.2%, planned R:R 1.00, profit factor 1.03, Sharpe 0.18, max drawdown -57.2%, ending $2,602 from $2,500, random ending $721. QQQ shares confirmed r1 holdout: 457 trades, win 34.1%, planned R:R 1.00, profit factor 1.18, Sharpe 0.30, max drawdown -25.0%, ending $2,907 from $2,500, random ending $1,557.

The confirmed entry buys the next open after a 5-minute close strictly above the neckline, the 9 EMA, and the 20 EMA. The quick scalp is a separate long-only book inside the same double bottom, before any close above the neckline: a down-close bar after an earlier bar has reclaimed the 9 EMA, with that red bar holding above the second low and above the lower of the 9 and 20 EMA. The scalp stop is one cent under the red bar. Its targets, scored separately, are the neckline and 2R. The confirmed stop is one cent under the second swing low. Confirmed targets, scored separately, are 1R, the measured move, and the prior bar's outer session-VWAP band. Both books are flat at the 15:45 open. They are not stacked into one 'scalp, then add on the close' strategy.

A swing is a strict 2-bar fractal in the same session, known two bars later. The first swing has to be at least 0.5 ATR(14) beyond the prior 12 bars. The two swings are 6 to 30 bars apart and within the larger of 0.15% and 0.5 ATR. The neckline is the highest high strictly between the swing lows, or the lowest low between swing highs on the short mirror. A close through the cluster extreme kills it. One cluster is active at a time. EMAs and the MACD histogram use the continuous regular-hours series. Session VWAP resets at 9:30.

Each cell starts a fresh $2,500 cash account. Train is 2017-02-16 through 2023-12-31. Holdout is 2024-01-01 through 2026-10-06. One position, at most three new trades a day. Shares risk 1% of start-of-day equity to the stop, in whole shares. Options are one at-the-money 0 DTE contract, Black-Scholes, prior VIX1D close or else the prior VIX close, rate 2%, dividend 0, half-spread the greater of one cent and 1.5% of the mid. A missing print skips the option trade. There is no quote fallback in this research. The false-discovery family is all 68 cells, including the eight scalp cells. The random baseline draws the same number of bars with seed 17 and the same direction. Its stop is one cent beyond that bar. A 1R, 2R, or VWAP-band exit is used as-is. A neckline or measured-move exit falls back to 1R, because a random bar has no neckline. The same cash rules then decide which of those bars fill.

The gate, all of it, is holdout trades at least 300, profit factor at least 1.10, Sharpe at least 0.40, max drawdown no worse than -30%, ending above $2,500, training Sharpe above that cell's random training Sharpe, a Benjamini-Hochberg q at or under 0.10 on the training trade P&L, and a deflated Sharpe at least 0.95. The q values use every training p-value in the family of 68. The deflated Sharpe uses that cell's training daily returns and the same 68 trials.

SPY is Dukascopy 5-minute bids from 2017-02-16 through 2026-10-06, 2416 sessions, 187540 bars, file `/workspace/data/cache/open_support/SPY_duka_5m.pkl`. Volume is a bid-tick count. Prices are bids and omit dividends.
QQQ is Dukascopy 5-minute bids from 2017-02-16 through 2026-10-06, 2365 sessions, 183636 bars, file `/workspace/data/cache/open_support/QQQ_duka_5m.pkl`. Volume is a bid-tick count. Prices are bids and omit dividends.

## Scalp against the confirmed close

This is the comparison that was registered with the scalp: planned R:R, win rate, profit factor, and the $2,500 ending, in train and in holdout, against the seed-17 random book. Confirmed rows are the base filter. The VWAP, 200 EMA, MACD, and short filters are in the full table.

| Book | Window | Trades | Win | R:R | PF | Sharpe | Max DD | Ending | Random ending |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY confirmed base r1 shares | train | 1254 | 31.9% | 1.00 | 0.28 | -5.61 | -70.7% | $732 | $659 |
| SPY confirmed base r1 shares | holdout | 487 | 31.4% | 1.00 | 0.26 | -6.88 | -37.4% | $1,567 | $1,507 |
| SPY confirmed base r1 0dte | train | 887 | 36.0% | 1.00 | 0.81 | -0.59 | -100.0% | $1 | $0 |
| SPY confirmed base r1 0dte | holdout | 626 | 39.9% | 1.00 | 1.22 | 1.10 | -37.2% | $5,919 | $1,112 |
| SPY confirmed base measured shares | train | 1248 | 33.5% | 1.02 | 0.40 | -0.70 | -69.4% | $1,023 | $659 |
| SPY confirmed base measured shares | holdout | 484 | 32.9% | 1.06 | 0.63 | -0.50 | -24.7% | $1,962 | $1,507 |
| SPY confirmed base measured 0dte | train | 1007 | 38.7% | 1.07 | 0.83 | -1.09 | -99.9% | $2 | $0 |
| SPY confirmed base measured 0dte | holdout | 625 | 40.2% | 1.09 | 2.28 | 0.61 | -27.3% | $21,539 | $1,112 |
| SPY confirmed base vwap2 shares | train | 1255 | 19.0% | 0.83 | 0.18 | -7.00 | -71.9% | $703 | $694 |
| SPY confirmed base vwap2 shares | holdout | 487 | 15.4% | 0.88 | 0.14 | -9.42 | -39.8% | $1,507 | $1,486 |
| SPY confirmed base vwap2 0dte | train | 878 | 28.4% | 0.65 | 0.69 | -0.77 | -99.9% | $3 | $0 |
| SPY confirmed base vwap2 0dte | holdout | 722 | 31.4% | 0.72 | 0.89 | -0.19 | -76.6% | $1,297 | $829 |
| SPY scalp scalp neckline shares | train | 1412 | 4.8% | 8.95 | 0.03 | -18.69 | -75.0% | $626 | $574 |
| SPY scalp scalp neckline shares | holdout | 597 | 4.4% | 8.48 | 0.03 | -22.01 | -44.6% | $1,386 | $1,347 |
| SPY scalp scalp neckline 0dte | train | 1251 | 17.7% | 8.07 | 0.46 | -1.98 | -100.0% | $0 | $4 |
| SPY scalp scalp neckline 0dte | holdout | 1176 | 21.3% | 9.85 | 0.78 | -2.06 | -82.5% | $496 | $12 |
| SPY scalp scalp r2 shares | train | 1415 | 3.3% | 2.00 | 0.02 | -21.40 | -75.5% | $613 | $592 |
| SPY scalp scalp r2 shares | holdout | 597 | 2.7% | 2.00 | 0.02 | -23.27 | -44.3% | $1,392 | $1,336 |
| SPY scalp scalp r2 0dte | train | 1134 | 21.1% | 2.00 | 0.36 | -2.06 | -100.0% | $0 | $1 |
| SPY scalp scalp r2 0dte | holdout | 1192 | 28.3% | 2.00 | 0.76 | -2.29 | -79.2% | $545 | $57 |
| QQQ confirmed base r1 shares | train | 1180 | 36.2% | 1.00 | 1.03 | 0.18 | -57.2% | $2,602 | $721 |
| QQQ confirmed base r1 shares | holdout | 457 | 34.1% | 1.00 | 1.18 | 0.30 | -25.0% | $2,907 | $1,557 |
| QQQ confirmed base r1 0dte | train | 1370 | 39.0% | 1.00 | 5.42 | 0.40 | -25.1% | $91,009 | $0 |
| QQQ confirmed base r1 0dte | holdout | 537 | 38.9% | 1.00 | 5.12 | 0.70 | -20.6% | $56,494 | $1,823 |
| QQQ confirmed base measured shares | train | 1172 | 36.4% | 0.94 | 1.03 | 0.18 | -56.9% | $2,607 | $721 |
| QQQ confirmed base measured shares | holdout | 456 | 33.1% | 0.96 | 1.39 | 0.46 | -21.5% | $3,419 | $1,557 |
| QQQ confirmed base measured 0dte | train | 1381 | 40.8% | 0.94 | 5.59 | 0.39 | -39.7% | $88,070 | $0 |
| QQQ confirmed base measured 0dte | holdout | 546 | 40.8% | 0.98 | 6.14 | 0.70 | -22.4% | $66,892 | $1,823 |
| QQQ confirmed base vwap2 shares | train | 1180 | 23.1% | 0.93 | 1.75 | 0.37 | -58.0% | $5,226 | $1,131 |
| QQQ confirmed base vwap2 shares | holdout | 457 | 21.9% | 0.95 | 1.16 | 0.27 | -27.1% | $2,836 | $2,058 |
| QQQ confirmed base vwap2 0dte | train | 1492 | 33.2% | 0.82 | 8.64 | 0.40 | -48.1% | $122,568 | $38,827 |
| QQQ confirmed base vwap2 0dte | holdout | 588 | 37.6% | 0.81 | 6.10 | 0.67 | -24.3% | $52,084 | $26,971 |
| QQQ scalp scalp neckline shares | train | 1288 | 9.0% | 8.30 | 0.07 | -14.72 | -73.6% | $660 | $563 |
| QQQ scalp scalp neckline shares | holdout | 555 | 6.7% | 9.66 | 0.06 | -17.53 | -44.0% | $1,400 | $1,364 |
| QQQ scalp scalp neckline 0dte | train | 1418 | 18.1% | 8.24 | 0.54 | -0.77 | -100.0% | $1 | $-0 |
| QQQ scalp scalp neckline 0dte | holdout | 1070 | 20.8% | 9.85 | 0.97 | -0.04 | -36.6% | $2,264 | $923 |
| QQQ scalp scalp r2 shares | train | 1289 | 4.8% | 2.00 | 0.03 | -16.25 | -74.7% | $631 | $575 |
| QQQ scalp scalp r2 shares | holdout | 557 | 5.4% | 2.00 | 0.04 | -18.82 | -43.9% | $1,401 | $1,643 |
| QQQ scalp scalp r2 0dte | train | 1214 | 20.5% | 2.00 | 0.36 | -1.45 | -100.0% | $1 | $1 |
| QQQ scalp scalp r2 0dte | holdout | 1084 | 28.6% | 2.00 | 0.90 | -0.65 | -40.2% | $1,710 | $20,190 |

## Full family

| Cell | Train trades | Train PF | Train ending | Holdout trades | Holdout win | Holdout R:R | Holdout PF | Holdout Sharpe | Holdout DD | Holdout ending | Random holdout ending | q | DSR | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SPY_confirmed_base_r1_shares | 1254 | 0.28 | $732 | 487 | 31.4% | 1.00 | 0.26 | -6.88 | -37.4% | $1,567 | $1,507 | 1.000 | 0.000 | no |
| SPY_confirmed_base_r1_0dte | 887 | 0.81 | $1 | 626 | 39.9% | 1.00 | 1.22 | 1.10 | -37.2% | $5,919 | $1,112 | 1.000 | 0.000 | no |
| SPY_confirmed_base_measured_shares | 1248 | 0.40 | $1,023 | 484 | 32.9% | 1.06 | 0.63 | -0.50 | -24.7% | $1,962 | $1,507 | 1.000 | 0.000 | no |
| SPY_confirmed_base_measured_0dte | 1007 | 0.83 | $2 | 625 | 40.2% | 1.09 | 2.28 | 0.61 | -27.3% | $21,539 | $1,112 | 1.000 | 0.000 | no |
| SPY_confirmed_base_vwap2_shares | 1255 | 0.18 | $703 | 487 | 15.4% | 0.88 | 0.14 | -9.42 | -39.8% | $1,507 | $1,486 | 1.000 | 0.000 | no |
| SPY_confirmed_base_vwap2_0dte | 878 | 0.69 | $3 | 722 | 31.4% | 0.72 | 0.89 | -0.19 | -76.6% | $1,297 | $829 | 1.000 | 0.000 | no |
| SPY_confirmed_vwap_r1_shares | 1120 | 0.69 | $1,555 | 426 | 30.8% | 1.00 | 0.25 | -6.38 | -32.5% | $1,690 | $1,530 | 1.000 | 0.006 | no |
| SPY_confirmed_vwap_r1_0dte | 1370 | 2.78 | $44,618 | 546 | 40.5% | 1.00 | 1.23 | 0.97 | -33.9% | $5,508 | $879 | 0.509 | 0.325 | no |
| SPY_confirmed_vwap_measured_shares | 1115 | 1.00 | $2,489 | 423 | 32.6% | 1.08 | 0.67 | -0.37 | -22.3% | $2,087 | $1,530 | 1.000 | 0.025 | no |
| SPY_confirmed_vwap_measured_0dte | 1365 | 4.30 | $75,590 | 546 | 39.7% | 1.11 | 2.42 | 0.61 | -20.9% | $20,846 | $879 | 0.344 | 0.336 | no |
| SPY_confirmed_vwap_vwap2_shares | 1121 | 0.15 | $781 | 426 | 13.6% | 0.58 | 0.11 | -9.45 | -35.1% | $1,626 | $1,513 | 1.000 | 0.000 | no |
| SPY_confirmed_vwap_vwap2_0dte | 842 | 0.65 | $3 | 651 | 31.8% | 0.50 | 0.89 | -0.16 | -69.1% | $1,591 | $597 | 1.000 | 0.000 | no |
| SPY_confirmed_ema200_r1_shares | 925 | 0.70 | $1,713 | 370 | 30.0% | 1.00 | 0.23 | -5.97 | -29.3% | $1,769 | $1,556 | 1.000 | 0.007 | no |
| SPY_confirmed_ema200_r1_0dte | 496 | 0.56 | $0 | 477 | 40.5% | 1.00 | 1.20 | 0.80 | -27.6% | $4,670 | $964 | 1.000 | 0.000 | no |
| SPY_confirmed_ema200_measured_shares | 915 | 1.18 | $2,976 | 366 | 30.6% | 1.09 | 0.69 | -0.31 | -20.9% | $2,153 | $1,556 | 0.931 | 0.042 | no |
| SPY_confirmed_ema200_measured_0dte | 496 | 0.55 | $2 | 475 | 39.4% | 1.13 | 2.58 | 0.61 | -18.5% | $19,778 | $964 | 1.000 | 0.000 | no |
| SPY_confirmed_ema200_vwap2_shares | 925 | 0.11 | $926 | 369 | 11.4% | 0.60 | 0.08 | -9.49 | -31.8% | $1,704 | $1,541 | 1.000 | 0.000 | no |
| SPY_confirmed_ema200_vwap2_0dte | 685 | 0.55 | $1 | 570 | 30.9% | 0.52 | 0.74 | -0.99 | -79.7% | $732 | $385 | 1.000 | 0.000 | no |
| SPY_confirmed_macd_r1_shares | 1106 | 0.29 | $827 | 410 | 31.5% | 1.00 | 0.26 | -6.36 | -33.9% | $1,655 | $1,550 | 1.000 | 0.000 | no |
| SPY_confirmed_macd_r1_0dte | 1282 | 1.18 | $6,444 | 488 | 37.3% | 1.00 | 1.28 | 1.10 | -42.4% | $6,031 | $228 | 0.344 | 0.176 | no |
| SPY_confirmed_macd_measured_shares | 1100 | 0.41 | $1,143 | 407 | 30.2% | 1.07 | 0.24 | -6.71 | -34.2% | $1,648 | $1,550 | 1.000 | 0.000 | no |
| SPY_confirmed_macd_measured_0dte | 1293 | 2.69 | $37,758 | 490 | 38.2% | 1.07 | 1.13 | 0.70 | -46.8% | $4,005 | $228 | 0.509 | 0.459 | no |
| SPY_confirmed_macd_vwap2_shares | 1106 | 0.18 | $778 | 410 | 15.1% | 0.96 | 0.13 | -8.68 | -36.5% | $1,591 | $1,586 | 1.000 | 0.000 | no |
| SPY_confirmed_macd_vwap2_0dte | 832 | 0.70 | $1 | 548 | 28.5% | 0.82 | 0.85 | -0.33 | -68.1% | $1,235 | $1,157 | 1.000 | 0.000 | no |
| SPY_confirmed_short_r1_shares | 271 | 0.05 | $-1,766 | 438 | 34.5% | 1.00 | 0.27 | -6.26 | -36.5% | $1,588 | $1,535 | 1.000 | 0.000 | no |
| SPY_confirmed_short_r1_0dte | 1364 | 1.20 | $7,888 | 532 | 43.2% | 1.00 | 1.45 | 2.07 | -11.2% | $8,436 | $593 | 0.123 | 0.407 | no |
| SPY_confirmed_short_measured_shares | 270 | 0.03 | $-1,756 | 434 | 31.6% | 0.94 | 0.22 | -6.92 | -36.8% | $1,580 | $1,535 | 1.000 | 0.000 | no |
| SPY_confirmed_short_measured_0dte | 1001 | 0.85 | $1 | 544 | 45.0% | 0.94 | 1.37 | 1.82 | -12.3% | $7,111 | $593 | 1.000 | 0.000 | no |
| SPY_confirmed_short_vwap2_shares | 453 | 0.05 | $-384 | 438 | 20.3% | 1.12 | 0.20 | -7.31 | -34.6% | $1,638 | $1,619 | 1.000 | 0.000 | no |
| SPY_confirmed_short_vwap2_0dte | 982 | 0.77 | $1 | 589 | 36.8% | 0.95 | 1.31 | 1.33 | -15.1% | $5,195 | $2,737 | 1.000 | 0.000 | no |
| SPY_scalp_scalp_neckline_shares | 1412 | 0.03 | $626 | 597 | 4.4% | 8.48 | 0.03 | -22.01 | -44.6% | $1,386 | $1,347 | 1.000 | 0.000 | no |
| SPY_scalp_scalp_neckline_0dte | 1251 | 0.46 | $0 | 1176 | 21.3% | 9.85 | 0.78 | -2.06 | -82.5% | $496 | $12 | 1.000 | 0.000 | no |
| SPY_scalp_scalp_r2_shares | 1415 | 0.02 | $613 | 597 | 2.7% | 2.00 | 0.02 | -23.27 | -44.3% | $1,392 | $1,336 | 1.000 | 0.000 | no |
| SPY_scalp_scalp_r2_0dte | 1134 | 0.36 | $0 | 1192 | 28.3% | 2.00 | 0.76 | -2.29 | -79.2% | $545 | $57 | 1.000 | 0.000 | no |
| QQQ_confirmed_base_r1_shares | 1180 | 1.03 | $2,602 | 457 | 34.1% | 1.00 | 1.18 | 0.30 | -25.0% | $2,907 | $1,557 | 1.000 | 0.033 | no |
| QQQ_confirmed_base_r1_0dte | 1370 | 5.42 | $91,009 | 537 | 38.9% | 1.00 | 5.12 | 0.70 | -20.6% | $56,494 | $1,823 | 0.344 | 0.389 | no |
| QQQ_confirmed_base_measured_shares | 1172 | 1.03 | $2,607 | 456 | 33.1% | 0.96 | 1.39 | 0.46 | -21.5% | $3,419 | $1,557 | 1.000 | 0.033 | no |
| QQQ_confirmed_base_measured_0dte | 1381 | 5.59 | $88,070 | 546 | 40.8% | 0.98 | 6.14 | 0.70 | -22.4% | $66,892 | $1,823 | 0.344 | 0.374 | no |
| QQQ_confirmed_base_vwap2_shares | 1180 | 1.75 | $5,226 | 457 | 21.9% | 0.95 | 1.16 | 0.27 | -27.1% | $2,836 | $2,058 | 0.635 | 0.141 | no |
| QQQ_confirmed_base_vwap2_0dte | 1492 | 8.64 | $122,568 | 588 | 37.6% | 0.81 | 6.10 | 0.67 | -24.3% | $52,084 | $26,971 | 0.344 | 0.409 | no |
| QQQ_confirmed_vwap_r1_shares | 1036 | 1.19 | $3,163 | 394 | 34.5% | 1.00 | 1.38 | 0.42 | -21.8% | $3,285 | $1,526 | 0.931 | 0.052 | no |
| QQQ_confirmed_vwap_r1_0dte | 1196 | 6.11 | $89,598 | 469 | 39.7% | 1.00 | 5.74 | 0.71 | -12.1% | $55,749 | $1,440 | 0.344 | 0.372 | no |
| QQQ_confirmed_vwap_measured_shares | 1027 | 1.21 | $3,184 | 393 | 33.1% | 0.99 | 1.63 | 0.57 | -17.7% | $3,890 | $1,526 | 0.931 | 0.053 | no |
| QQQ_confirmed_vwap_measured_0dte | 1205 | 6.41 | $87,235 | 477 | 41.3% | 1.00 | 6.99 | 0.71 | -12.8% | $66,587 | $1,440 | 0.344 | 0.363 | no |
| QQQ_confirmed_vwap_vwap2_shares | 1035 | 1.19 | $3,040 | 394 | 21.1% | 0.62 | 1.41 | 0.41 | -23.0% | $3,241 | $1,553 | 0.931 | 0.048 | no |
| QQQ_confirmed_vwap_vwap2_0dte | 1329 | 7.68 | $84,301 | 523 | 38.6% | 0.55 | 7.26 | 0.65 | -27.8% | $51,037 | $3,279 | 0.344 | 0.369 | no |
| QQQ_confirmed_ema200_r1_shares | 849 | 0.95 | $2,350 | 342 | 34.2% | 1.00 | 1.51 | 0.46 | -20.5% | $3,412 | $1,619 | 1.000 | 0.022 | no |
| QQQ_confirmed_ema200_r1_0dte | 989 | 4.63 | $50,073 | 408 | 39.5% | 1.00 | 6.50 | 0.72 | -12.8% | $54,420 | $1,500 | 0.509 | 0.325 | no |
| QQQ_confirmed_ema200_measured_shares | 839 | 0.97 | $2,406 | 340 | 32.1% | 1.00 | 1.81 | 0.62 | -14.1% | $4,036 | $1,619 | 1.000 | 0.023 | no |
| QQQ_confirmed_ema200_measured_0dte | 995 | 4.82 | $48,507 | 417 | 40.3% | 1.01 | 7.81 | 0.72 | -9.2% | $64,996 | $1,500 | 0.509 | 0.326 | no |
| QQQ_confirmed_ema200_vwap2_shares | 849 | 1.64 | $4,341 | 342 | 19.6% | 0.72 | 1.53 | 0.44 | -22.4% | $3,338 | $1,650 | 0.788 | 0.105 | no |
| QQQ_confirmed_ema200_vwap2_0dte | 1105 | 9.49 | $84,445 | 457 | 37.0% | 0.62 | 7.77 | 0.66 | -21.8% | $49,833 | $3,942 | 0.344 | 0.357 | no |
| QQQ_confirmed_macd_r1_shares | 1003 | 1.17 | $3,115 | 366 | 30.6% | 1.00 | 0.30 | -5.22 | -34.4% | $1,641 | $1,625 | 0.931 | 0.050 | no |
| QQQ_confirmed_macd_r1_0dte | 1108 | 6.29 | $90,450 | 409 | 36.2% | 1.00 | 1.56 | 1.25 | -28.2% | $8,226 | $1,811 | 0.344 | 0.414 | no |
| QQQ_confirmed_macd_measured_shares | 993 | 1.19 | $3,139 | 366 | 29.5% | 0.98 | 0.22 | -6.28 | -37.2% | $1,571 | $1,625 | 0.931 | 0.051 | no |
| QQQ_confirmed_macd_measured_0dte | 1110 | 6.56 | $87,956 | 407 | 36.6% | 0.97 | 1.20 | 0.81 | -35.4% | $4,483 | $1,811 | 0.344 | 0.399 | no |
| QQQ_confirmed_macd_vwap2_shares | 1002 | 1.84 | $5,352 | 366 | 18.0% | 1.00 | 0.19 | -6.69 | -35.7% | $1,609 | $1,656 | 0.631 | 0.149 | no |
| QQQ_confirmed_macd_vwap2_0dte | 1200 | 10.19 | $122,106 | 449 | 34.3% | 0.87 | 1.17 | 0.62 | -43.9% | $3,769 | $4,223 | 0.344 | 0.421 | no |
| QQQ_confirmed_short_r1_shares | 264 | 0.05 | $-4,702 | 446 | 35.4% | 1.00 | 0.36 | -5.41 | -38.5% | $1,541 | $1,576 | 1.000 | 0.000 | no |
| QQQ_confirmed_short_r1_0dte | 1167 | 1.67 | $14,425 | 525 | 40.6% | 1.00 | 1.77 | 2.99 | -6.5% | $12,265 | $3,000 | 0.000 | 1.000 | yes |
| QQQ_confirmed_short_measured_shares | 262 | 0.03 | $-4,779 | 439 | 37.6% | 0.89 | 0.36 | -5.26 | -34.8% | $1,629 | $1,576 | 1.000 | 0.000 | no |
| QQQ_confirmed_short_measured_0dte | 1199 | 1.41 | $9,276 | 524 | 46.2% | 0.89 | 1.76 | 3.41 | -6.1% | $10,925 | $3,000 | 0.000 | 0.910 | no |
| QQQ_confirmed_short_vwap2_shares | 563 | 0.12 | $-589 | 447 | 24.4% | 1.39 | 0.23 | -6.97 | -39.2% | $1,524 | $1,577 | 1.000 | 0.000 | no |
| QQQ_confirmed_short_vwap2_0dte | 1230 | 1.35 | $7,441 | 543 | 38.9% | 1.26 | 1.42 | 1.78 | -12.8% | $6,497 | $2,943 | 0.037 | 0.627 | no |
| QQQ_scalp_scalp_neckline_shares | 1288 | 0.07 | $660 | 555 | 6.7% | 9.66 | 0.06 | -17.53 | -44.0% | $1,400 | $1,364 | 1.000 | 0.000 | no |
| QQQ_scalp_scalp_neckline_0dte | 1418 | 0.54 | $1 | 1070 | 20.8% | 9.85 | 0.97 | -0.04 | -36.6% | $2,264 | $923 | 1.000 | 0.000 | no |
| QQQ_scalp_scalp_r2_shares | 1289 | 0.03 | $631 | 557 | 5.4% | 2.00 | 0.04 | -18.82 | -43.9% | $1,401 | $1,643 | 1.000 | 0.000 | no |
| QQQ_scalp_scalp_r2_0dte | 1214 | 0.36 | $1 | 1084 | 28.6% | 2.00 | 0.90 | -0.65 | -40.2% | $1,710 | $20,190 | 1.000 | 0.000 | no |

## 2026-10-08, about 14:15 to 14:25 ET

The illustration is Yahoo 5-minute SPY, not the thinkorswim print. The last bar that has closed by 14:25 ET starts at 14:20 and closes five minutes later. Close 773.45, 9 EMA 772.59, 20 EMA 772.76, 200 EMA 775.21, VWAP 774.51, MACD histogram 0.235. On or before that bar the detector marks a confirmed long at 12:20, fill 12:25, neckline 775.45, second swing 774.15, stop 774.14. On or before that bar the detector marks a confirmed short at 12:45, fill 12:50, neckline 774.15, second swing 777.09, stop 777.10. Session swing lows into that bar include 11:55 at 774.15, 13:05 at 771.80, 13:25 at 770.43, 13:50 at 771.27. The 13:25 low is 5 bars before the 13:50 low, short of the 6-bar minimum, so those two are not the pair. The active long cluster has a mechanical neckline at 773.49 against the drawn line near 773.1. The second low is 771.27 and the cluster extreme is 771.27. The 9 EMA has been reclaimed: true. A close has already gone through the neckline: false. The scalp has already been taken: false. The next bar, which opens at 14:25 and closes five minutes after the requested window, is a scalp long signal. Its fill would be 14:30, stop 773.19, neckline 773.49. That bar was not required to call the 14:15-14:25 read. 2026-10-08 is not in the scored sample. The tolerances were not changed after this reading.

Chart: `reports/neckline_equity.png`. Machine-readable summary: `reports/neckline.json`.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.

```
PYTHONPATH=src python3 -m webull_bot.chart_reads.research_neckline
```
