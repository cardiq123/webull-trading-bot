<!-- INDICATOR_SURVEY_START -->
### Indicator and pattern survey

Backtests only. Nothing was sent to a broker. Live trading stays off. No sandbox book was added. The chop-breakout order rules were not changed.

No strategy passed every check. 106 combinations were counted, across round 1 (63), round 2 (42), and round 3 (1). 4 cleared the profit, Sharpe, drawdown, and trade-count gates on both the selection window and the prior years, and still failed the multiple-testing bar. The gate was not loosened after the scores.

Selection is 2025-10-08 through 2026-07-06. Prior years are 2018-01-01 through 2025-10-07, with the rules frozen. The holdout is 2026-07-07 through 2026-10-06 and was scored once, after the rounds. A cell needs 20 selection trades and 80 prior-year trades, profit factor 1.10, Sharpe 0.40, max drawdown no worse than -30%, and ending equity above the start. The share book is long-only, whole shares, 1% of equity to the stop, at most three new entries a day, cash settlement the next session. Costs are 5 bps slippage, 1 bp half-spread, SEC $20.60 per million dollars sold, and FINRA TAF $0.000195 per share capped at $9.79.

Yahoo 15-minute history is about 60 days and falls inside the holdout, so 15-minute bars were not scored. Yahoo hourly history starts in October 2024. Those four cells are in the trial count and cannot pass the 2018 prior-year check.

Universe, ranked by trailing dollar volume before any signal was scored: SPY, the Magnificent Seven (AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA), growth PLTR, MSTR, HOOD, and tech MU, AMD, AVGO.

Growth, average daily dollar volume, 2025-10-08 through 2026-10-06:
- PLTR: $6.84 billion frozen
- MSTR: $3.04 billion frozen
- HOOD: $2.70 billion frozen
- APP: $2.48 billion
- COIN: $2.06 billion
Tech:
- MU: $23.99 billion frozen
- AMD: $11.78 billion frozen
- AVGO: $9.46 billion frozen
- INTC: $8.49 billion
- ORCL: $4.93 billion

A cash account does not use the margin pattern-day-trade block. Same-day round trips are still counted. Under $25,000, a margin account would be limited; this test does not refuse the fourth day trade.

There is no search survivor.

These cleared both windows (20 and 80 trades, profit factor 1.10, Sharpe 0.40, drawdown no worse than -30%, ending above the start) and then missed q ≤ 0.10 or deflated Sharpe ≥ 0.95, or they did not beat the random book:

| Strategy | Sel trades | Sel PF | Sel Sharpe | Sel $1,000 | Sel $5,000 | Prior PF | Prior Sharpe | Prior $1,000 | q | DSR | Random Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| macd_cross__exit | 25 | 2.16 | 1.91 | $1,078 | $4,979 | 1.51 | 1.19 | $2,674 | 0.739 | 0.183 | 0.81 |
| obv_break | 21 | 1.32 | 0.52 | $1,029 | $4,773 | 1.55 | 1.17 | $3,543 | 0.968 | 0.017 | 1.45 |
| prior_week_high__sma200 | 20 | 2.10 | 1.67 | $1,087 | $5,153 | 1.54 | 1.14 | $3,137 | 0.739 | 0.126 | 0.85 |
| swing_retest | 22 | 1.31 | 0.64 | $1,030 | $4,568 | 1.29 | 0.83 | $2,520 | 0.987 | 0.023 | 1.13 |

Buy the next open after the MACD line crosses above its signal line. Stop is the signal low minus 1 ATR. Target is 1R. Time stop is 15 bars. Up to three new entries a day.

Buy the next open when on-balance volume makes a 20-day high and the close breaks the prior high. Stop is the signal low minus 1 ATR. Target is 2R. Time stop is 15 bars. Up to three new entries a day.

Buy the next open after the close breaks the prior week's high. Stop is the signal low minus 1 ATR. Target is 2R. Time stop is 15 bars. A close above the 200-day average is required. Up to three new entries a day.

Buy the next open after a swing-high break retests that level within half an ATR and closes back above it. Stop is the signal low minus 1 ATR. Target is 2R. Time stop is 15 bars. Up to three new entries a day.

The holdout was scored once, on month_6, the daily cell with the highest prior-year Sharpe, because nothing had passed. That score is not a pass and was not used to pick a refinement.
month_6 buys only in June, about three trades a year, and the account otherwise sits in cash, so its Sharpe can rank first without reaching 80 trades. July through October contains no June, so the holdout book is empty.

| Strategy | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| month_6 | 0 | 0.0% | n/a | n/a | 0.00 | 0.0% | $1,000 | $5,000 |

Buy and hold, same costs, whole shares:

- Selection SPY $1,000 ends $1,085, Sharpe 1.26.
- Selection equal-weight basket $1,000 ends $1,000 because one fourteenth of $1,000 does not buy a share of these names in 2025-2026. The $5,000 basket ends $6,040, Sharpe 1.39.
- Prior SPY $1,000 ends $2,707, Sharpe 0.78.
- Prior equal-weight basket $1,000 ends $10,499, Sharpe 1.08, max drawdown -54.9%. The $5,000 basket ends $61,042.
- Holdout SPY $1,000 ends $1,030, Sharpe 1.44.
- Holdout equal-weight basket $1,000 stays in cash for the same share-price reason. The $5,000 basket ends $5,368, Sharpe 2.28.

Near-misses refined in round 2, ranked by prior-year Sharpe:

| Strategy | Window | Trades | Trades/yr | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| donchian20 | selection | 16 | 21.5 | 37.5% | 35.2% | 1.10 | 0.21 | -5.0% | $1,008 | $5,048 |
| donchian20 | prior | 693 | 89.3 | 52.2% | 40.6% | 1.60 | 1.27 | -16.1% | $3,575 | $15,925 |
| prior_day_high | selection | 53 | 71.2 | 37.7% | 31.3% | 1.33 | 0.97 | -9.9% | $1,077 | $5,458 |
| prior_day_high | prior | 1385 | 178.4 | 49.7% | 40.7% | 1.44 | 1.18 | -36.8% | $5,231 | $25,328 |
| prior_week_high | selection | 29 | 38.9 | 48.3% | 34.0% | 1.81 | 1.47 | -4.6% | $1,098 | $4,990 |
| prior_week_high | prior | 1010 | 130.1 | 50.3% | 40.9% | 1.46 | 1.15 | -31.2% | $3,972 | $17,688 |
| macd_cross | selection | 22 | 29.5 | 50.0% | 28.3% | 2.53 | 1.64 | -6.0% | $1,123 | $5,347 |
| macd_cross | prior | 693 | 89.3 | 48.6% | 39.6% | 1.44 | 0.99 | -34.4% | $2,847 | $15,946 |
| swing_break | selection | 27 | 36.3 | 44.4% | 37.3% | 1.35 | 0.76 | -4.6% | $1,039 | $5,121 |
| swing_break | prior | 1008 | 129.8 | 50.5% | 42.9% | 1.36 | 0.96 | -33.8% | $3,153 | $16,318 |
| stoch_cross | selection | 28 | 37.6 | 42.9% | 38.5% | 1.20 | 0.47 | -7.0% | $1,023 | $4,924 |
| stoch_cross | prior | 788 | 101.5 | 49.4% | 42.9% | 1.30 | 0.78 | -37.1% | $2,420 | $11,343 |
| cci_cross | selection | 19 | 25.5 | 42.1% | 36.2% | 1.28 | 0.52 | -6.2% | $1,020 | $4,638 |
| cci_cross | prior | 449 | 57.8 | 47.9% | 39.9% | 1.39 | 0.76 | -23.5% | $1,907 | $9,407 |

Highest prior-year Sharpe, daily cells, whether or not they were near-misses:

| Strategy | Window | Trades | Trades/yr | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| month_6 | prior | 23 | 3.0 | 78.3% | 26.9% | 9.78 | 1.34 | -2.4% | $1,237 | $5,869 |
| month_6 selection | q 1.000 | DSR n/a | random Sharpe 0.00 | selection Sharpe 0.00 | PF n/a | trades 0 | prior pass False | selection pass False | | |
| prior_day_high__sma200 | prior | 1080 | 139.1 | 50.4% | 40.6% | 1.48 | 1.30 | -25.7% | $4,393 | $19,708 |
| prior_day_high__sma200 selection | q 1.000 | DSR 0.009 | random Sharpe 0.96 | selection Sharpe 0.22 | PF 1.06 | trades 38 | prior pass True | selection pass False | | |
| relvol_breakout | prior | 338 | 43.5 | 54.4% | 39.8% | 1.81 | 1.29 | -11.4% | $2,330 | $11,511 |
| relvol_breakout selection | q 1.000 | DSR 0.049 | random Sharpe -1.60 | selection Sharpe 0.96 | PF 3.03 | trades 2 | prior pass True | selection pass False | | |
| donchian20__cap5 | prior | 696 | 89.6 | 52.2% | 40.4% | 1.61 | 1.28 | -15.9% | $3,585 | $16,943 |
| donchian20__cap5 selection | q 0.987 | DSR 0.009 | random Sharpe -1.86 | selection Sharpe 0.21 | PF 1.10 | trades 16 | prior pass True | selection pass False | | |
| macd_sma200 | prior | 494 | 63.6 | 51.6% | 38.6% | 1.70 | 1.28 | -11.0% | $2,853 | $13,476 |
| macd_sma200 selection | q 1.000 | DSR 0.009 | random Sharpe 1.04 | selection Sharpe 0.23 | PF 1.15 | trades 14 | prior pass True | selection pass False | | |
| macd_cross__sma200 | prior | 494 | 63.6 | 51.6% | 38.6% | 1.70 | 1.28 | -11.0% | $2,853 | $13,476 |
| macd_cross__sma200 selection | q 1.000 | DSR 0.009 | random Sharpe 1.04 | selection Sharpe 0.23 | PF 1.15 | trades 14 | prior pass True | selection pass False | | |
| donchian20 | prior | 693 | 89.3 | 52.2% | 40.6% | 1.60 | 1.27 | -16.1% | $3,575 | $15,925 |
| donchian20 selection | q 0.987 | DSR 0.009 | random Sharpe -1.86 | selection Sharpe 0.21 | PF 1.10 | trades 16 | prior pass True | selection pass False | | |
| prior_day_high__liquid6 | prior | 751 | 96.7 | 48.9% | 38.8% | 1.50 | 1.19 | -31.0% | $3,710 | $21,348 |
| prior_day_high__liquid6 selection | q 0.739 | DSR 0.097 | random Sharpe 0.19 | selection Sharpe 1.41 | PF 1.80 | trades 26 | prior pass False | selection pass True | | |

Year by year, each year a fresh $1,000. These slices were not new trials and were not refit.

| Strategy | Year | Trades | PF | Sharpe | Max DD | Ending |
|---|---:|---:|---:|---:|---:|---:|
| donchian20 | 2018 | 73 | 1.27 | 0.79 | -8.1% | $1,074 |
| donchian20 | 2019 | 86 | 1.95 | 1.65 | -5.9% | $1,194 |
| donchian20 | 2020 | 102 | 1.94 | 1.86 | -14.6% | $1,329 |
| donchian20 | 2021 | 70 | 1.69 | 1.48 | -7.5% | $1,150 |
| donchian20 | 2022 | 39 | 0.45 | -0.97 | -14.5% | $894 |
| donchian20 | 2023 | 93 | 1.72 | 1.42 | -12.3% | $1,227 |
| donchian20 | 2024 | 77 | 1.61 | 1.46 | -9.2% | $1,181 |
| swing_retest | 2018 | 95 | 0.71 | -0.82 | -19.6% | $886 |
| swing_retest | 2019 | 111 | 1.38 | 0.95 | -5.8% | $1,134 |
| swing_retest | 2020 | 116 | 2.44 | 2.58 | -8.0% | $1,559 |
| swing_retest | 2021 | 106 | 1.28 | 1.00 | -6.3% | $1,118 |
| swing_retest | 2022 | 88 | 0.45 | -1.58 | -26.3% | $763 |
| swing_retest | 2023 | 119 | 1.95 | 2.21 | -7.9% | $1,397 |
| swing_retest | 2024 | 95 | 1.60 | 1.60 | -6.8% | $1,218 |
| obv_break | 2018 | 86 | 0.78 | -0.65 | -14.0% | $917 |
| obv_break | 2019 | 95 | 1.93 | 1.85 | -6.3% | $1,251 |
| obv_break | 2020 | 111 | 2.14 | 2.44 | -9.3% | $1,446 |
| obv_break | 2021 | 80 | 1.16 | 0.50 | -12.5% | $1,049 |
| obv_break | 2022 | 56 | 0.66 | -0.69 | -13.5% | $910 |
| obv_break | 2023 | 105 | 1.69 | 1.46 | -13.8% | $1,254 |
| obv_break | 2024 | 82 | 1.98 | 2.13 | -4.2% | $1,282 |
| prior_week_high__sma200 | 2018 | 100 | 0.99 | 0.04 | -11.3% | $998 |
| prior_week_high__sma200 | 2019 | 102 | 1.71 | 1.51 | -5.3% | $1,180 |
| prior_week_high__sma200 | 2020 | 120 | 2.01 | 2.15 | -11.9% | $1,376 |
| prior_week_high__sma200 | 2021 | 95 | 1.52 | 1.29 | -8.5% | $1,174 |
| prior_week_high__sma200 | 2022 | 22 | 0.50 | -0.77 | -8.8% | $938 |
| prior_week_high__sma200 | 2023 | 112 | 2.00 | 2.09 | -10.1% | $1,344 |
| prior_week_high__sma200 | 2024 | 95 | 1.45 | 1.27 | -6.9% | $1,172 |
| macd_cross__exit | 2018 | 96 | 0.84 | -0.51 | -14.2% | $942 |
| macd_cross__exit | 2019 | 90 | 1.70 | 1.76 | -4.4% | $1,180 |
| macd_cross__exit | 2020 | 78 | 1.88 | 1.72 | -4.5% | $1,185 |
| macd_cross__exit | 2021 | 88 | 1.00 | 0.06 | -7.7% | $1,001 |
| macd_cross__exit | 2022 | 76 | 0.81 | -0.57 | -7.4% | $937 |
| macd_cross__exit | 2023 | 100 | 1.88 | 2.03 | -8.0% | $1,237 |
| macd_cross__exit | 2024 | 76 | 2.60 | 3.19 | -3.6% | $1,303 |

Option prices are Black-Scholes, volatility is the prior close of VIX, strikes are listed, and the half-spread is the larger of $0.01 and 1.5% of the mid. One contract is bought when the debit fits. 0 DTE is priced only when the share trade exits the same session. Multi-day holds use 7 and 14 calendar days. These dollars did not add trials and cannot promote a book that failed the share checks.

macd_cross__exit selection $1,000:
- call_0: 6 filled, skipped 0, P&L $1,375, ending $2,375.
- call_7: 19 filled, skipped 0, P&L $6,885, ending $7,885.
- call_14: 19 filled, skipped 0, P&L $6,471, ending $7,471.
- vertical_7: 19 filled, skipped 0, P&L $1,865, ending $2,865.
- vertical_14: 19 filled, skipped 0, P&L $1,351, ending $2,351.

macd_cross__exit selection $5,000:
- call_0: 6 filled, skipped 0, P&L $1,375, ending $6,375.
- call_7: 19 filled, skipped 0, P&L $6,885, ending $11,885.
- call_14: 19 filled, skipped 0, P&L $6,471, ending $11,471.
- vertical_7: 19 filled, skipped 0, P&L $1,865, ending $6,865.
- vertical_14: 19 filled, skipped 0, P&L $1,351, ending $6,351.

macd_cross__exit prior $1,000:
- call_0: 37 filled, skipped 0, P&L $6,546, ending $7,546.
- call_7: 701 filled, skipped 0, P&L $80,580, ending $81,580.
- call_14: 701 filled, skipped 0, P&L $98,569, ending $99,569.
- vertical_7: 701 filled, skipped 0, P&L $18,176, ending $19,176.
- vertical_14: 701 filled, skipped 0, P&L $11,451, ending $12,451.

obv_break selection $1,000:
- call_0: 4 filled, skipped 0, P&L $-320, ending $680.
- call_7: 17 filled, skipped 0, P&L $5,549, ending $6,549.
- call_14: 17 filled, skipped 0, P&L $5,585, ending $6,585.
- vertical_7: 17 filled, skipped 0, P&L $832, ending $1,832.
- vertical_14: 17 filled, skipped 0, P&L $333, ending $1,333.

obv_break selection $5,000:
- call_0: 4 filled, skipped 0, P&L $-320, ending $4,680.
- call_7: 17 filled, skipped 0, P&L $5,549, ending $10,549.
- call_14: 17 filled, skipped 0, P&L $5,585, ending $10,585.
- vertical_7: 17 filled, skipped 0, P&L $832, ending $5,832.
- vertical_14: 17 filled, skipped 0, P&L $333, ending $5,333.

obv_break prior $1,000:
- call_0: 19 filled, skipped 11, P&L $-999, ending $1.
- call_7: 743 filled, skipped 0, P&L $98,655, ending $99,655.
- call_14: 743 filled, skipped 0, P&L $134,983, ending $135,983.
- vertical_7: 743 filled, skipped 0, P&L $13,155, ending $14,155.
- vertical_14: 91 filled, skipped 652, P&L $-999, ending $1.

prior_week_high__sma200 selection $1,000:
- call_0: 1 filled, skipped 0, P&L $-117, ending $883.
- call_7: 16 filled, skipped 3, P&L $4,442, ending $5,442.
- call_14: 18 filled, skipped 1, P&L $10,067, ending $11,067.
- vertical_7: 19 filled, skipped 0, P&L $56, ending $1,056.
- vertical_14: 19 filled, skipped 0, P&L $1,503, ending $2,503.

prior_week_high__sma200 selection $5,000:
- call_0: 1 filled, skipped 0, P&L $-117, ending $4,883.
- call_7: 19 filled, skipped 0, P&L $6,920, ending $11,920.
- call_14: 19 filled, skipped 0, P&L $9,629, ending $14,629.
- vertical_7: 19 filled, skipped 0, P&L $56, ending $5,056.
- vertical_14: 19 filled, skipped 0, P&L $1,503, ending $6,503.

prior_week_high__sma200 prior $1,000:
- call_0: 20 filled, skipped 0, P&L $-667, ending $333.
- call_7: 768 filled, skipped 0, P&L $98,780, ending $99,780.
- call_14: 768 filled, skipped 0, P&L $111,976, ending $112,976.
- vertical_7: 768 filled, skipped 0, P&L $15,420, ending $16,420.
- vertical_14: 661 filled, skipped 107, P&L $3,813, ending $4,813.

month_6 holdout $1,000 (not a selection input):
- call_0: No same-session share exit, so 0 DTE is not priced.
- call_7: 0 filled, skipped 0, P&L $0, ending $1,000.
- call_14: 0 filled, skipped 0, P&L $0, ending $1,000.
- vertical_7: 0 filled, skipped 0, P&L $0, ending $1,000.
- vertical_14: 0 filled, skipped 0, P&L $0, ending $1,000.

Buy the first session of month 6 and sell the last session of that month. Stop is the fill minus 3 ATR. Exit at the end of the seasonal window, with no profit target. Up to three new entries a day.
On the $1,000 selection book, month_6 logged 0 same-day round trips and 0 rolling five-session windows with more than three of them.

The chart is `reports/indicator_survey_equity.png`. The machine-readable summary is `reports/indicator_survey.json`.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.

```
python3 -m webull_bot.chart_reads.research_indicator_survey
```
<!-- INDICATOR_SURVEY_END -->
