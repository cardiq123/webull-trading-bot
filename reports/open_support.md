<!-- OPEN_SUPPORT_START -->
### Open versus support

Backtests only. Nothing was sent to a broker. Live trading stays off. No sandbox book was added.

No cell passed every training check. 141 combinations were counted. The gate was not loosened after the scores.

The rule is Paul's: when the stock opens above support in an uptrend, go long; when it opens below support in a downtrend, go short. The first 5-minute candle has to close in that direction and beyond the level. The fill is the 09:35 open. Support is the prior-day low or the last confirmed 3, 5, or 10 day swing. Trend is the daily 20 EMA, the 50 EMA, or higher-high/higher-low structure. Stops are the crossed level or the first candle. Targets are 1R, 2R, the prior close, the prior session VWAP, or the session close. A long-only open above resistance is a separate family. One extra cell allows five entries a day.

Training is 2018-01-01 through 2026-07-06. The holdout is 2026-07-07 through 2026-10-06 and was scored once. A pass needs 80 training trades, profit factor 1.10, Sharpe 0.40, max drawdown no worse than -30%, ending equity above the start, q ≤ 0.10, deflated Sharpe ≥ 0.95, and a training Sharpe above the seed-17 random book. The share book is whole shares, 1% of equity to the stop, at most three new entries a day. Costs are 5 bps slippage, 1 bp half-spread, SEC $20.60 per million dollars sold, and FINRA TAF. A cash account cannot short. The short share book is the research expression. Puts are the account expression. Every one of these is a day trade. The count is reported and the trade is not refused.

SPY and QQQ use Dukascopy 1-minute bids from 2017-02-16 through 2026-10-06, resampled to 5 minutes. Those bids are the gate. The other names have about 60 Yahoo 5-minute days, which sit inside the holdout, so they are not in the trial count. That short book is one look at the cell the training search already picked.

There is no training survivor. Every cell that traded finished the $1,000 book below the start. Two long-only cells never traded: after a gap above the prior high, the prior close and the prior VWAP sit on the wrong side of the fill, so those targets are skipped.

Paul's wording, frozen as `both_prior_day_ema20_level_r1`: prior-day low, daily 20 EMA, stop at that low, 1R target. Training took 790 trades (718 long, 72 short), win rate 46.3% against a break-even 57.6%, profit factor 0.63, Sharpe -1.65, max drawdown -40.5%, $1,000 ends $608, $5,000 ends $2,477. q is 1.000, deflated Sharpe is 0.00, and the matched random Sharpe is -1.07.

| Strategy | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 | q | DSR | Random |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| both_swing10_structure_level_vwap | 45 | 46.7% | 54.6% | 0.73 | -0.24 | -4.5% | $978 | $4,742 | 1.000 | 0.000 | -0.62 |
| both_swing10_structure_level_prior_close | 40 | 52.5% | 64.2% | 0.62 | -0.33 | -3.6% | $981 | $4,761 | 1.000 | 0.000 | -0.49 |
| both_swing10_ema50_level_prior_close | 57 | 50.9% | 61.9% | 0.64 | -0.40 | -4.1% | $973 | $4,590 | 1.000 | 0.000 | -0.79 |
| both_swing10_ema20_level_vwap | 43 | 41.9% | 56.7% | 0.55 | -0.42 | -4.7% | $968 | $4,646 | 1.000 | 0.000 | -0.63 |
| both_swing5_ema20_level_r1 | 240 | 46.7% | 52.7% | 0.79 | -0.44 | -7.1% | $935 | $4,005 | 1.000 | 0.000 | -0.68 |
| both_swing10_ema50_level_vwap | 54 | 42.6% | 57.1% | 0.56 | -0.46 | -5.3% | $963 | $4,547 | 1.000 | 0.000 | -0.73 |
| both_swing5_structure_level_r1 | 261 | 45.6% | 52.0% | 0.77 | -0.48 | -10.3% | $922 | $4,140 | 1.000 | 0.000 | -1.43 |
| both_swing5_structure_level_vwap | 116 | 44.8% | 55.7% | 0.65 | -0.49 | -6.3% | $944 | $4,580 | 1.000 | 0.000 | -0.79 |

Go long when the open is above the last 10-day swing low in an uptrend, and short when the open is below it in a downtrend. Trend means the last two confirmed swings are higher highs and higher lows, or lower highs and lower lows. The first 5-minute candle has to close in that direction and beyond the level. Buy or sell the 09:35 open. Stop is the level that was crossed. Target is the prior session VWAP, when that price is on the profit side. Flat by the 15:55 close. At most 3 new entries a day.
both_swing10_structure_level_vwap took 32 longs and 13 shorts, 45 day trades, and 0 five-session windows with more than three.

Go long when the open is above the last 10-day swing low in an uptrend, and short when the open is below it in a downtrend. Trend means the last two confirmed swings are higher highs and higher lows, or lower highs and lower lows. The first 5-minute candle has to close in that direction and beyond the level. Buy or sell the 09:35 open. Stop is the level that was crossed. Target is the prior close, when that price is on the profit side. Flat by the 15:55 close. At most 3 new entries a day.
both_swing10_structure_level_prior_close took 27 longs and 13 shorts, 40 day trades, and 0 five-session windows with more than three.

Go long when the open is above the last 10-day swing low in an uptrend, and short when the open is below it in a downtrend. Trend means the daily 50 EMA is sloping that way and price is on that side of it. The first 5-minute candle has to close in that direction and beyond the level. Buy or sell the 09:35 open. Stop is the level that was crossed. Target is the prior close, when that price is on the profit side. Flat by the 15:55 close. At most 3 new entries a day.
both_swing10_ema50_level_prior_close took 22 longs and 35 shorts, 57 day trades, and 0 five-session windows with more than three.

Go long when the open is above the last 10-day swing low in an uptrend, and short when the open is below it in a downtrend. Trend means the daily 20 EMA is sloping that way and price is on that side of it. The first 5-minute candle has to close in that direction and beyond the level. Buy or sell the 09:35 open. Stop is the level that was crossed. Target is the prior session VWAP, when that price is on the profit side. Flat by the 15:55 close. At most 3 new entries a day.
both_swing10_ema20_level_vwap took 15 longs and 28 shorts, 43 day trades, and 0 five-session windows with more than three.

Holdout, scored once, not a pass:

| Strategy | Trades | Win | Break-even | PF | Sharpe | Max DD | $1,000 | $5,000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| both_swing10_structure_level_vwap | 1 | 100.0% | n/a | n/a | 1.98 | 0.0% | $1,005 | $5,006 |

Yahoo 5-minute book for the other names, `both_swing10_structure_level_vwap` only, through 2026-10-06: the $1,000 account took 0 trades and ended $1,000. The $5,000 account took 24 trades, profit factor 0.37, Sharpe -4.07, and ended $4,979. A wide stop often does not fit one share in $1,000. This sample cannot pass.

Buy and hold on the Dukascopy bid, same costs, whole shares:

- Train SPY $1,000 ends $2,448, Sharpe 0.75.
- Train QQQ $1,000 ends $4,394, Sharpe 0.91.
- Holdout SPY $1,000 ends $1,028, Sharpe 1.37.

Option prices are Black-Scholes, one contract, volatility the prior close of VIX. The half-spread is the larger of $0.01 and 1.5% of the mid, plus the option regulatory schedule. These dollars did not add trials and cannot promote a book that failed the share checks.

both_swing10_structure_level_vwap:
- train_callput_0: 45 filled, skipped 0, P&L $2,418, ending $3,418.
- train_callput_7: 45 filled, skipped 0, P&L $431, ending $1,431.
- holdout_0: 1 filled, skipped 0, P&L $467, ending $1,467.
- holdout_7: 1 filled, skipped 0, P&L $309, ending $1,309.
- yahoo_0: 0 filled, skipped 0, P&L $0, ending $1,000.

Example chart `reports/open_support_intc.png`: the headline rule did not fire. Open 109.54, first close 110.53, prior low 111.14, 20 EMA trend up. The session is partial.

The equity chart is `reports/open_support_equity.png`. The machine-readable summary is `reports/open_support.json`.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.

```
python3 -m webull_bot.chart_reads.research_open_support
```
<!-- OPEN_SUPPORT_END -->
