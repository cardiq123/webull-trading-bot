# QQQ Trapdoor, more aggressive puts and sizes

The unchanged at-the-money 1-contract Trapdoor reaches $10,000 on 0.0% of 434 holdout starts that still have a full 12 months, and on 0.0% of the 2017–2023 starts. Holdout ruin is 0.0%. The median of those 12-month endings is $6,648 (weak tenth $4,925). One account left running across the whole holdout ends at $12,265 on 525 trades, profit factor 1.77, Sharpe 2.99, max drawdown -6.5%. It clears the gate. The six highest holdout chances of reaching $10,000 are fixed-fraction bets. Their holdout reach is high and their holdout ruin is near zero because a cheap 0 DTE premium, reinvested, compounds into millions inside the model before a drawdown can print as ruin under $500. None of those six clear the gate. On 2017–2023 starts those Trapdoor fraction bets fall under $500 on 34.0% to 64.7% of paths. Totals past about $10 million in this table are a model artifact, and the exact figures stay in the JSON. With the skew bump on, the cells that still clear the gate are: QQQ Trapdoor, about a 0.40 delta, 1R, 1 contract, skew bump on; QQQ Trapdoor, about a 0.40 delta, 1R, 3 contracts, skew bump on; QQQ Trapdoor, about a 0.40 delta, 1R, 5 contracts, skew bump on; QQQ Trapdoor, about a 0.40 delta, 1R, 7 contracts, skew bump on; QQQ Trapdoor, about a 0.40 delta, 1R, 10 contracts, skew bump on. The first cells in this same sort that clear the gate and still finish a typical year in ordinary dollars are: QQQ VWAP 2 SD, at the money, 1R, 3 contracts (holdout reach 100.0%, ruin 0.0%, median 12-month ending $35,316, 2017–2023 reach 83.5%, 2017–2023 ruin 0.0%); QQQ Trapdoor, about a 0.20 delta, 1R, 10 contracts, skew bump off (holdout reach 100.0%, ruin 0.0%, median 12-month ending $31,102, 2017–2023 reach 37.5%, 2017–2023 ruin 14.2%).

The entry is the QQQ Trapdoor that already cleared: a double top, then a 5-minute close below the neckline and below both the 9 and 20 EMA. That signal was not retuned. This pass only changes the put and how many contracts the $2,500 account buys.

At the money is the baseline, held to the 1R underlying target. One, two, and three strikes out of the money, and puts aimed at a 0.40, 0.30, or 0.20 delta, are each held to that same 1R target and to a 2R target. The stop stays one cent above the second high. Everything is flat at the 15:45 open. Trapdoor still takes at most 3 fills a day. The VWAP comparison takes at most 5.

Size is either a fixed 1, 3, 5, 7, or 10 contracts, or 10%, 20%, 30%, or 50% of equity. If the whole ticket costs more than the settled cash, the trade is skipped. It is not cut down to a smaller lot. A sale can be spent the next session.

The price is Black-Scholes with the prior VIX1D close, or the prior VIX close when VIX1D is missing. Out-of-the-money puts are scored twice: once at that IV, and once with a skew bump of 1.5 volatility points per 0.10 of delta below 0.50. Those puts also pay a wider half-spread, max($0.02, 8% of the mid), on the way in and on the way out, when the listed strike is below at the money. At-the-money keeps the original half-spread, max($0.01, 1.5% of the mid). A cheap 0 DTE premium is where this model is least trustworthy, because a one-cent error is a large share of a price that is only a few cents. Strikes two and three out, and the 0.30 and 0.20 delta targets, are flagged, as is any cell whose median ask is under $0.50.

The chance of reaching $10,000 is a fresh $2,500 at every session that still has 12 months of data inside the window. The 4-month and 8-month chances use those same starts. Train is 2017-02-16 through 2023-12-31. Holdout is 2024-01-01 through 2026-10-06. A train start never sees 2024. The family is 234 cells. The false-discovery gate is the usual one, on the full holdout account. The $10,000 chance sorts the table. It is the question Paul asked, and it leaves the entry rule alone.

QQQ 5-minute bids are the same Dukascopy cache the neckline study used (/workspace/data/cache/open_support/QQQ_duka_5m.pkl), 2017-02-16 through 2026-10-06. The VWAP comparison is those bars rolled up to 15 minutes. No chain history. The option price is a model.

Cells that clear the frozen holdout gate (profit factor 1.10, Sharpe 0.40, drawdown no worse than -30%, at least 300 trades, q at or under 0.10, deflated Sharpe at least 0.95): QQQ Trapdoor, at the money, 1R, 1 contract; QQQ Trapdoor, at the money, 1R, 3 contracts; QQQ Trapdoor, at the money, 1R, 5 contracts; QQQ Trapdoor, at the money, 1R, 7 contracts; QQQ Trapdoor, at the money, 1R, 10 contracts; QQQ Trapdoor, 1 strike out of the money, 1R, 1 contract, skew bump off; QQQ Trapdoor, 1 strike out of the money, 1R, 3 contracts, skew bump off; QQQ Trapdoor, 1 strike out of the money, 1R, 5 contracts, skew bump off; QQQ Trapdoor, 1 strike out of the money, 1R, 7 contracts, skew bump off; QQQ Trapdoor, 1 strike out of the money, 1R, 10 contracts, skew bump off; QQQ Trapdoor, 1 strike out of the money, 2R, 1 contract, skew bump off; QQQ Trapdoor, 1 strike out of the money, 2R, 3 contracts, skew bump off; QQQ Trapdoor, 1 strike out of the money, 2R, 5 contracts, skew bump off; QQQ Trapdoor, 1 strike out of the money, 2R, 7 contracts, skew bump off; QQQ Trapdoor, 1 strike out of the money, 2R, 10 contracts, skew bump off; QQQ Trapdoor, 2 strikes out of the money, 1R, 1 contract, skew bump off; QQQ Trapdoor, 2 strikes out of the money, 1R, 3 contracts, skew bump off; QQQ Trapdoor, 2 strikes out of the money, 1R, 5 contracts, skew bump off; QQQ Trapdoor, 2 strikes out of the money, 1R, 7 contracts, skew bump off; QQQ Trapdoor, 2 strikes out of the money, 1R, 10 contracts, skew bump off; QQQ Trapdoor, 2 strikes out of the money, 2R, 1 contract, skew bump off; QQQ Trapdoor, 2 strikes out of the money, 2R, 3 contracts, skew bump off; QQQ Trapdoor, 2 strikes out of the money, 2R, 5 contracts, skew bump off; QQQ Trapdoor, 2 strikes out of the money, 2R, 7 contracts, skew bump off; QQQ Trapdoor, 2 strikes out of the money, 2R, 10 contracts, skew bump off; QQQ Trapdoor, 3 strikes out of the money, 2R, 1 contract, skew bump off; QQQ Trapdoor, 3 strikes out of the money, 2R, 3 contracts, skew bump off; QQQ Trapdoor, 3 strikes out of the money, 2R, 5 contracts, skew bump off; QQQ Trapdoor, about a 0.40 delta, 1R, 1 contract, skew bump off; QQQ Trapdoor, about a 0.40 delta, 1R, 1 contract, skew bump on; QQQ Trapdoor, about a 0.40 delta, 1R, 3 contracts, skew bump off; QQQ Trapdoor, about a 0.40 delta, 1R, 3 contracts, skew bump on; QQQ Trapdoor, about a 0.40 delta, 1R, 5 contracts, skew bump off; QQQ Trapdoor, about a 0.40 delta, 1R, 5 contracts, skew bump on; QQQ Trapdoor, about a 0.40 delta, 1R, 7 contracts, skew bump off; QQQ Trapdoor, about a 0.40 delta, 1R, 7 contracts, skew bump on; QQQ Trapdoor, about a 0.40 delta, 1R, 10 contracts, skew bump off; QQQ Trapdoor, about a 0.40 delta, 1R, 10 contracts, skew bump on; QQQ Trapdoor, about a 0.40 delta, 2R, 1 contract, skew bump off; QQQ Trapdoor, about a 0.40 delta, 2R, 3 contracts, skew bump off; QQQ Trapdoor, about a 0.40 delta, 2R, 5 contracts, skew bump off; QQQ Trapdoor, about a 0.40 delta, 2R, 7 contracts, skew bump off; QQQ Trapdoor, about a 0.40 delta, 2R, 10 contracts, skew bump off; QQQ Trapdoor, about a 0.30 delta, 1R, 1 contract, skew bump off; QQQ Trapdoor, about a 0.30 delta, 1R, 3 contracts, skew bump off; QQQ Trapdoor, about a 0.30 delta, 1R, 5 contracts, skew bump off; QQQ Trapdoor, about a 0.30 delta, 1R, 7 contracts, skew bump off; QQQ Trapdoor, about a 0.30 delta, 1R, 10 contracts, skew bump off; QQQ Trapdoor, about a 0.30 delta, 2R, 1 contract, skew bump off; QQQ Trapdoor, about a 0.30 delta, 2R, 3 contracts, skew bump off; QQQ Trapdoor, about a 0.30 delta, 2R, 5 contracts, skew bump off; QQQ Trapdoor, about a 0.30 delta, 2R, 7 contracts, skew bump off; QQQ Trapdoor, about a 0.30 delta, 2R, 10 contracts, skew bump off; QQQ Trapdoor, about a 0.20 delta, 1R, 1 contract, skew bump off; QQQ Trapdoor, about a 0.20 delta, 1R, 3 contracts, skew bump off; QQQ Trapdoor, about a 0.20 delta, 1R, 5 contracts, skew bump off; QQQ Trapdoor, about a 0.20 delta, 1R, 7 contracts, skew bump off; QQQ Trapdoor, about a 0.20 delta, 1R, 10 contracts, skew bump off; QQQ Trapdoor, about a 0.20 delta, 2R, 1 contract, skew bump off; QQQ Trapdoor, about a 0.20 delta, 2R, 3 contracts, skew bump off; QQQ Trapdoor, about a 0.20 delta, 2R, 5 contracts, skew bump off; QQQ Trapdoor, about a 0.20 delta, 2R, 7 contracts, skew bump off; QQQ Trapdoor, about a 0.20 delta, 2R, 10 contracts, skew bump off; QQQ VWAP 2 SD, at the money, 1R, 1 contract; QQQ VWAP 2 SD, at the money, 1R, 3 contracts.

## Top configurations by the chance of reaching $10,000 in 12 months

1. QQQ Trapdoor, about a 0.20 delta, 1R, 10% of equity, skew bump off. Of 434 holdout starts, 100.0% reach $10,000 within 12 months (100.0% within 8, 98.8% within 4) and 0.0% fall under $500 inside those 12 months. In 2017–2023 the same fresh starts reach $10,000 66.0% of the time and fall under $500 37.4% of the time. That holdout ruin rate stays near zero because the modeled account is already huge, so a deep drawdown still leaves it above $500. When a start does get to $10,000 inside 12 months, the median time is 44 days. The median 12-month ending balance is $651.6 million, and the weak tenth ends at $26.4 million. The median 12-month drawdown is -64.4%; the weak tenth is -64.9%. One account run across the whole holdout ends at $14.5 quadrillion on 525 trades, profit factor 1.13, Sharpe 2.96, max drawdown -77.9%. Does not clear the frozen gate. The model is least trustworthy on this put: cheap 0 DTE premium, where a one-cent error is a large share of the price. Median ask $0.13.

2. QQQ VWAP 2 SD, at the money, 1R, 10% of equity. Of 434 holdout starts, 100.0% reach $10,000 within 12 months (100.0% within 8, 90.1% within 4) and 0.0% fall under $500 inside those 12 months. In 2017–2023 the same fresh starts reach $10,000 100.0% of the time and fall under $500 3.7% of the time. That holdout ruin rate stays near zero because the modeled account is already huge, so a deep drawdown still leaves it above $500. When a start does get to $10,000 inside 12 months, the median time is 47 days. The median 12-month ending balance is $570.9 million, and the weak tenth ends at $35.0 million. The median 12-month drawdown is -63.7%; the weak tenth is -66.2%. One account run across the whole holdout ends at $2.2 quintillion on 1128 trades, profit factor 1.17, Sharpe 5.00, max drawdown -62.5%. Does not clear the frozen gate. The model is least trustworthy on this contract: cheap 0 DTE premium, where a one-cent error is a large share of the price. Median ask $0.48.

3. QQQ Trapdoor, about a 0.20 delta, 2R, 10% of equity, skew bump off. Of 434 holdout starts, 100.0% reach $10,000 within 12 months (100.0% within 8, 98.4% within 4) and 0.0% fall under $500 inside those 12 months. In 2017–2023 the same fresh starts reach $10,000 65.2% of the time and fall under $500 46.0% of the time. That holdout ruin rate stays near zero because the modeled account is already huge, so a deep drawdown still leaves it above $500. When a start does get to $10,000 inside 12 months, the median time is 48 days. The median 12-month ending balance is $72.5 million, and the weak tenth ends at $5.8 million. The median 12-month drawdown is -71.2%; the weak tenth is -72.3%. One account run across the whole holdout ends at $303.0 trillion on 497 trades, profit factor 1.09, Sharpe 3.15, max drawdown -86.7%. Does not clear the frozen gate. The model is least trustworthy on this put: cheap 0 DTE premium, where a one-cent error is a large share of the price. Median ask $0.13.

4. QQQ Trapdoor, 1 strike out of the money, 1R, 10% of equity, skew bump off. Of 434 holdout starts, 100.0% reach $10,000 within 12 months (100.0% within 8, 85.7% within 4) and 0.0% fall under $500 inside those 12 months. In 2017–2023 the same fresh starts reach $10,000 43.3% of the time and fall under $500 64.7% of the time. That holdout ruin rate stays near zero because the modeled account is already huge, so a deep drawdown still leaves it above $500. When a start does get to $10,000 inside 12 months, the median time is 56 days. The median 12-month ending balance is $64.1 million, and the weak tenth ends at $6.4 million. The median 12-month drawdown is -68.0%; the weak tenth is -78.7%. One account run across the whole holdout ends at $42.5 trillion on 525 trades, profit factor 1.08, Sharpe 2.61, max drawdown -87.5%. Does not clear the frozen gate. The model is least trustworthy on this put: cheap 0 DTE premium, where a one-cent error is a large share of the price. Median ask $0.06.

5. QQQ Trapdoor, about a 0.30 delta, 1R, 10% of equity, skew bump off. Of 434 holdout starts, 100.0% reach $10,000 within 12 months (100.0% within 8, 100.0% within 4) and 0.0% fall under $500 inside those 12 months. In 2017–2023 the same fresh starts reach $10,000 65.4% of the time and fall under $500 34.0% of the time. That holdout ruin rate stays near zero because the modeled account is already huge, so a deep drawdown still leaves it above $500. When a start does get to $10,000 inside 12 months, the median time is 48 days. The median 12-month ending balance is $56.9 million, and the weak tenth ends at $4.8 million. The median 12-month drawdown is -63.6%; the weak tenth is -66.5%. One account run across the whole holdout ends at $35.6 trillion on 525 trades, profit factor 1.11, Sharpe 3.19, max drawdown -81.1%. Does not clear the frozen gate. The model is least trustworthy on this put: cheap 0 DTE premium, where a one-cent error is a large share of the price. Median ask $0.20.

6. QQQ Trapdoor, about a 0.30 delta, 2R, 10% of equity, skew bump off. Of 434 holdout starts, 100.0% reach $10,000 within 12 months (100.0% within 8, 94.9% within 4) and 0.0% fall under $500 inside those 12 months. In 2017–2023 the same fresh starts reach $10,000 63.7% of the time and fall under $500 40.7% of the time. That holdout ruin rate stays near zero because the modeled account is already huge, so a deep drawdown still leaves it above $500. When a start does get to $10,000 inside 12 months, the median time is 59 days. The median 12-month ending balance is $14.5 million, and the weak tenth ends at $1.9 million. The median 12-month drawdown is -67.2%; the weak tenth is -71.6%. One account run across the whole holdout ends at $1.2 trillion on 497 trades, profit factor 1.10, Sharpe 2.85, max drawdown -84.6%. Does not clear the frozen gate. The model is least trustworthy on this put: cheap 0 DTE premium, where a one-cent error is a large share of the price. Median ask $0.20.

The chart is `reports/trapdoor_aggressive_reach.png`. Each dot is one cell on the holdout starts. Across is the chance of reaching $10,000 within 12 months. Up is the chance of falling under $500. The labeled dots are the six above. They sit at the bottom right, high reach and low ruin, because the fraction bets get large before they draw down, so the holdout ruin count stays near zero. The 2017–2023 starts for those same cells often do fall under $500.

## Every cell

| Cell | Holdout reach 12m | Ruin | Median end | Full ending | PF | Sharpe | DD | Trades | q | Survives | Train reach | Train ruin |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| trapdoor_d20_r1_f10_off | 100.0% | 0.0% | $651.6 million | $14.5 quadrillion | 1.13 | 2.96 | -77.9% | 525 | 0.700 | no | 66.0% | 37.4% |
| vwap_atm_r1_f10_off | 100.0% | 0.0% | $570.9 million | $2.2 quintillion | 1.17 | 5.00 | -62.5% | 1128 | 0.477 | no | 100.0% | 3.7% |
| trapdoor_d20_r2_f10_off | 100.0% | 0.0% | $72.5 million | $303.0 trillion | 1.09 | 3.15 | -86.7% | 497 | 0.700 | no | 65.2% | 46.0% |
| trapdoor_otm1_r1_f10_off | 100.0% | 0.0% | $64.1 million | $42.5 trillion | 1.08 | 2.61 | -87.5% | 525 | 0.700 | no | 43.3% | 64.7% |
| trapdoor_d30_r1_f10_off | 100.0% | 0.0% | $56.9 million | $35.6 trillion | 1.11 | 3.19 | -81.1% | 525 | 0.700 | no | 65.4% | 34.0% |
| trapdoor_d30_r2_f10_off | 100.0% | 0.0% | $14.5 million | $1.2 trillion | 1.10 | 2.85 | -84.6% | 497 | 0.700 | no | 63.7% | 40.7% |
| trapdoor_d40_r1_f10_off | 100.0% | 0.0% | $7.4 million | $216.5 billion | 1.10 | 3.08 | -83.3% | 525 | 0.700 | no | 63.3% | 25.8% |
| trapdoor_atm_r1_f10_off | 100.0% | 0.0% | $2.4 million | $10.4 billion | 1.11 | 2.91 | -80.6% | 525 | 0.677 | no | 63.1% | 18.0% |
| trapdoor_d40_r2_f10_off | 100.0% | 0.0% | $1.5 million | $10.5 billion | 1.12 | 2.64 | -81.0% | 497 | 0.700 | no | 56.2% | 33.5% |
| trapdoor_d40_r1_f10_on | 100.0% | 0.0% | $225,226 | $27.9 million | 1.07 | 2.27 | -84.8% | 525 | 0.700 | no | 47.8% | 35.1% |
| trapdoor_d30_r1_f10_on | 100.0% | 0.0% | $106,427 | $3.2 million | 1.05 | 1.95 | -87.3% | 525 | 0.700 | no | 51.9% | 47.3% |
| vwap_atm_r1_c3_off | 100.0% | 0.0% | $35,316 | $96,136 | 1.98 | 3.48 | -25.1% | 1128 | 0.000 | yes | 83.5% | 0.0% |
| trapdoor_d20_r1_c10_off | 100.0% | 0.0% | $31,102 | $70,704 | 2.29 | 2.59 | -19.8% | 525 | 0.000 | yes | 37.5% | 14.2% |
| trapdoor_otm2_r2_c10_off | 100.0% | 0.0% | $30,294 | $67,631 | 3.32 | 2.07 | -27.4% | 497 | 0.000 | yes | 31.2% | 7.8% |
| trapdoor_d20_r2_c7_off | 100.0% | 0.0% | $30,073 | $68,106 | 2.61 | 2.32 | -19.6% | 497 | 0.000 | yes | 40.1% | 1.0% |
| trapdoor_d20_r1_c7_off | 100.0% | 0.0% | $22,522 | $50,243 | 2.29 | 2.78 | -14.3% | 525 | 0.000 | yes | 30.8% | 2.7% |
| trapdoor_d20_r2_c5_off | 100.0% | 0.0% | $22,195 | $49,362 | 2.61 | 2.47 | -16.2% | 497 | 0.000 | yes | 30.8% | 0.0% |
| trapdoor_d30_r2_c5_off | 100.0% | 0.0% | $22,002 | $49,836 | 2.08 | 2.20 | -21.5% | 497 | 0.000 | yes | 30.4% | 0.1% |
| trapdoor_otm1_r2_c5_off | 100.0% | 0.0% | $21,573 | $47,816 | 2.41 | 2.57 | -14.4% | 497 | 0.000 | yes | 30.2% | 0.0% |
| trapdoor_d30_r1_c5_off | 100.0% | 0.0% | $18,508 | $39,922 | 1.92 | 2.64 | -13.7% | 525 | 0.000 | yes | 30.8% | 1.6% |
| trapdoor_d20_r1_c5_off | 100.0% | 0.0% | $16,801 | $36,602 | 2.29 | 2.92 | -10.5% | 525 | 0.000 | yes | 24.8% | 0.0% |
| trapdoor_d40_r2_c3_off | 100.0% | 0.0% | $14,201 | $31,457 | 1.87 | 2.35 | -16.3% | 497 | 0.000 | yes | 21.9% | 0.0% |
| vwap_atm_r1_c1_off | 100.0% | 0.0% | $13,439 | $33,712 | 1.98 | 4.56 | -11.3% | 1128 | 0.000 | yes | 30.2% | 0.0% |
| trapdoor_otm1_r2_f10_off | 100.0% | 0.2% | $45.1 million | $37.1 trillion | 1.07 | 2.77 | -89.8% | 497 | 0.700 | no | 55.9% | 57.4% |
| trapdoor_otm1_r1_c7_off | 100.0% | 0.7% | $20,651 | $45,751 | 2.05 | 2.78 | -9.9% | 525 | 0.000 | yes | 30.9% | 4.9% |
| trapdoor_d20_r2_c10_off | 100.0% | 1.6% | $41,890 | $96,224 | 2.61 | 2.16 | -23.4% | 497 | 0.000 | yes | 51.6% | 14.6% |
| trapdoor_otm1_r2_c7_off | 100.0% | 1.6% | $29,203 | $65,942 | 2.41 | 2.43 | -17.1% | 497 | 0.000 | yes | 31.7% | 2.6% |
| trapdoor_d30_r1_c7_off | 100.0% | 1.6% | $24,911 | $54,891 | 1.92 | 2.51 | -18.1% | 525 | 0.000 | yes | 34.4% | 5.7% |
| trapdoor_d40_r1_c5_off | 100.0% | 1.6% | $20,205 | $44,712 | 1.81 | 2.75 | -13.7% | 525 | 0.000 | yes | 35.1% | 5.5% |
| trapdoor_d30_r2_c7_off | 100.0% | 2.1% | $29,803 | $68,770 | 2.08 | 2.06 | -25.5% | 497 | 0.000 | yes | 40.1% | 7.1% |
| trapdoor_atm_r1_f20_off | 100.0% | 2.8% | $19.8 million | $180.0 billion | 1.01 | 2.80 | -97.6% | 525 | 0.700 | no | 63.1% | 60.1% |
| vwap_atm_r1_f20_off | 100.0% | 4.4% | $160.1 billion | $9.92×10^23 | 1.04 | 4.88 | -90.6% | 1122 | 0.700 | no | 95.2% | 31.9% |
| trapdoor_d40_r1_f20_off | 100.0% | 5.3% | $93.5 million | $3.8 trillion | 1.01 | 2.98 | -98.4% | 525 | 0.700 | no | 64.3% | 60.8% |
| trapdoor_d30_r1_f20_off | 100.0% | 5.5% | $1.1 billion | $2.3 quadrillion | 1.01 | 3.09 | -98.4% | 524 | 0.700 | no | 64.6% | 70.4% |
| trapdoor_d20_r1_f20_off | 100.0% | 9.2% | $15.5 billion | $2.0 quintillion | 1.01 | 2.65 | -98.3% | 524 | 0.700 | no | 63.1% | 70.9% |
| trapdoor_d40_r1_f20_on | 100.0% | 13.4% | $371,397 | $4.3 million | 1.00 | 2.20 | -98.6% | 525 | 0.700 | no | 50.5% | 68.4% |
| trapdoor_d30_r2_f20_off | 100.0% | 17.5% | $6.4 million | $23.1 billion | 1.01 | 2.82 | -98.8% | 497 | 0.700 | no | 56.4% | 75.6% |
| vwap_atm_r1_f30_off | 100.0% | 24.4% | $528.4 billion | $1.15×10^25 | 1.01 | 4.97 | -98.4% | 1060 | 0.700 | no | 83.8% | 68.8% |
| trapdoor_d20_r2_f20_off | 100.0% | 24.9% | $19.4 million | $2.6 trillion | 1.01 | 3.13 | -99.2% | 497 | 0.700 | no | 53.4% | 76.3% |
| trapdoor_d40_r1_f30_off | 100.0% | 33.6% | $10.2 million | $720.4 million | 1.00 | 2.88 | -99.9% | 520 | 0.700 | no | 51.5% | 80.1% |
| trapdoor_d30_r1_f30_off | 100.0% | 34.8% | $26.0 million | $23.6 billion | 1.00 | 3.15 | -99.9% | 515 | 0.700 | no | 59.2% | 80.5% |
| trapdoor_atm_r1_f30_off | 100.0% | 36.6% | $8.7 million | $508.1 million | 1.00 | 2.71 | -99.8% | 522 | 0.700 | no | 55.9% | 79.4% |
| trapdoor_otm2_r2_c7_off | 99.3% | 0.0% | $21,956 | $48,092 | 3.32 | 2.22 | -21.8% | 497 | 0.000 | yes | 27.0% | 1.4% |
| trapdoor_d40_r2_c5_off | 99.1% | 2.3% | $22,002 | $50,762 | 1.87 | 2.22 | -21.6% | 497 | 0.000 | yes | 36.0% | 4.4% |
| trapdoor_d40_r1_c5_on | 99.1% | 2.3% | $16,922 | $34,664 | 1.54 | 2.28 | -18.6% | 525 | 0.000 | yes | 29.7% | 9.4% |
| trapdoor_d20_r1_f30_off | 98.8% | 43.8% | $68.8 million | $957.3 billion | 1.00 | 3.44 | -99.9% | 515 | 0.700 | no | 51.5% | 81.8% |
| vwap_atm_r1_c5_off | 98.6% | 1.8% | $57,194 | $158,561 | 1.98 | 2.88 | -39.3% | 1128 | 0.000 | no | 87.4% | 3.3% |
| trapdoor_otm1_r1_c10_off | 98.4% | 2.5% | $28,429 | $64,287 | 2.05 | 2.66 | -11.3% | 525 | 0.000 | yes | 31.6% | 16.7% |
| trapdoor_d40_r1_c7_off | 98.4% | 2.5% | $27,287 | $61,597 | 1.81 | 2.61 | -18.1% | 525 | 0.000 | yes | 40.7% | 8.8% |
| trapdoor_d40_r2_c5_on | 98.4% | 2.5% | $18,165 | $39,215 | 1.57 | 1.81 | -28.7% | 497 | 0.003 | no | 32.8% | 18.4% |
| trapdoor_otm1_r1_f20_off | 98.4% | 36.4% | $126.9 million | $40.6 trillion | 1.00 | 2.36 | -99.3% | 524 | 0.700 | no | 42.4% | 82.0% |
| trapdoor_otm1_r2_f20_off | 98.2% | 37.8% | $7.7 million | $18.6 billion | 1.00 | 2.72 | -99.5% | 497 | 0.700 | no | 44.2% | 83.5% |
| trapdoor_d40_r1_c7_on | 97.9% | 5.5% | $22,675 | $47,529 | 1.54 | 2.20 | -21.9% | 525 | 0.000 | yes | 33.8% | 24.1% |
| trapdoor_atm_r1_c5_off | 97.7% | 2.5% | $23,242 | $51,325 | 1.77 | 2.62 | -16.8% | 525 | 0.000 | yes | 31.9% | 8.6% |
| vwap_atm_r1_c7_off | 97.7% | 7.6% | $78,989 | $220,985 | 1.98 | 2.46 | -55.0% | 1128 | 0.000 | no | 93.1% | 11.4% |
| trapdoor_d30_r1_c10_off | 97.5% | 2.5% | $34,516 | $77,345 | 1.92 | 2.33 | -23.8% | 525 | 0.000 | yes | 41.7% | 17.4% |
| trapdoor_atm_r1_c7_off | 97.5% | 4.6% | $31,538 | $70,854 | 1.77 | 2.46 | -22.0% | 525 | 0.000 | yes | 36.7% | 23.1% |
| trapdoor_d40_r2_c7_off | 97.5% | 4.6% | $29,803 | $70,067 | 1.87 | 2.11 | -25.1% | 497 | 0.000 | yes | 45.0% | 21.0% |
| trapdoor_otm1_r2_c10_off | 97.2% | 2.8% | $40,647 | $93,131 | 2.41 | 2.28 | -19.9% | 497 | 0.000 | yes | 37.7% | 15.8% |
| trapdoor_d40_r2_f20_off | 96.1% | 22.4% | $772,465 | $340.7 million | 1.01 | 2.59 | -98.1% | 497 | 0.700 | no | 54.5% | 71.5% |
| trapdoor_d40_r1_f30_on | 96.1% | 68.2% | $34,567 | $401 | 1.00 | 2.14 | -100.0% | 517 | 0.700 | no | 43.1% | 82.2% |
| trapdoor_d30_r1_c7_on | 95.9% | 3.5% | $18,076 | $33,157 | 1.42 | 1.81 | -26.2% | 525 | 0.006 | no | 26.2% | 24.3% |
| trapdoor_d40_r1_c10_off | 95.6% | 8.8% | $37,711 | $86,924 | 1.81 | 2.42 | -23.8% | 525 | 0.000 | yes | 54.5% | 21.7% |
| trapdoor_atm_r1_c3_off | 95.2% | 0.0% | $14,945 | $31,795 | 1.77 | 2.81 | -12.8% | 525 | 0.000 | yes | 27.6% | 1.4% |
| trapdoor_d30_r2_c10_off | 94.2% | 6.9% | $41,245 | $97,172 | 2.08 | 1.91 | -29.6% | 497 | 0.000 | yes | 45.3% | 23.5% |
| trapdoor_d30_r2_c7_on | 94.0% | 10.4% | $20,937 | $42,835 | 1.50 | 1.47 | -48.7% | 497 | 0.008 | no | 31.0% | 32.8% |
| trapdoor_d30_r1_f20_on | 93.8% | 32.3% | $60,293 | $33,590 | 1.00 | 1.88 | -99.0% | 525 | 0.700 | no | 53.9% | 73.8% |
| trapdoor_d20_r1_f10_on | 93.3% | 1.4% | $58,322 | $311,409 | 1.03 | 1.58 | -87.7% | 525 | 0.700 | no | 49.9% | 58.8% |
| trapdoor_d20_r2_c3_off | 93.1% | 0.0% | $14,317 | $30,617 | 2.61 | 2.68 | -11.5% | 497 | 0.000 | yes | 12.0% | 0.0% |
| trapdoor_d30_r2_f30_off | 93.1% | 77.2% | $64,166 | $19,939 | 1.00 | 2.67 | -99.9% | 452 | 0.700 | no | 52.2% | 83.4% |
| trapdoor_d40_r2_c7_on | 92.4% | 10.6% | $24,167 | $53,901 | 1.57 | 1.75 | -33.8% | 497 | 0.003 | no | 35.9% | 36.2% |
| trapdoor_otm2_r2_f10_off | 92.4% | 19.8% | $208.6 million | $701.5 billion | 1.09 | 2.42 | -99.6% | 491 | 0.700 | no | 36.3% | 77.6% |
| trapdoor_atm_r1_c10_off | 92.2% | 14.7% | $42,204 | $100,149 | 1.77 | 2.27 | -28.9% | 525 | 0.000 | yes | 50.1% | 37.7% |
| trapdoor_d40_r2_c10_off | 92.2% | 15.7% | $40,750 | $99,024 | 1.87 | 1.97 | -28.5% | 497 | 0.000 | yes | 44.9% | 36.5% |
| trapdoor_otm1_r1_c5_off | 91.9% | 0.0% | $15,465 | $33,394 | 2.05 | 2.87 | -8.5% | 525 | 0.000 | yes | 23.5% | 0.4% |
| trapdoor_d30_r2_c3_off | 91.7% | 0.0% | $14,201 | $30,902 | 2.08 | 2.38 | -15.8% | 497 | 0.000 | yes | 12.0% | 0.0% |
| trapdoor_d40_r2_f10_on | 91.0% | 1.6% | $61,379 | $1.5 million | 1.08 | 1.90 | -86.0% | 497 | 0.700 | no | 48.8% | 39.7% |
| trapdoor_d40_r1_c3_off | 90.8% | 0.0% | $13,123 | $27,827 | 1.81 | 2.89 | -10.3% | 525 | 0.000 | yes | 17.8% | 0.2% |
| trapdoor_d30_r2_f10_on | 90.1% | 6.2% | $38,646 | $170,418 | 1.06 | 1.64 | -88.1% | 497 | 0.700 | no | 49.2% | 51.9% |
| vwap_atm_r1_c10_off | 89.6% | 17.3% | $109,034 | $315,213 | 1.98 | 2.07 | -78.5% | 1126 | 0.000 | no | 82.6% | 24.3% |
| trapdoor_d30_r1_c10_on | 89.2% | 16.1% | $21,691 | $46,296 | 1.42 | 1.77 | -28.9% | 525 | 0.006 | no | 29.4% | 49.9% |
| trapdoor_d20_r1_c10_on | 88.9% | 6.0% | $18,578 | $32,230 | 1.34 | 1.55 | -37.3% | 525 | 0.020 | no | 18.8% | 50.3% |
| trapdoor_d30_r2_c5_on | 88.5% | 0.7% | $15,720 | $31,311 | 1.50 | 1.52 | -40.3% | 497 | 0.008 | no | 25.7% | 11.0% |
| trapdoor_d40_r1_c10_on | 88.5% | 16.6% | $28,964 | $66,827 | 1.54 | 2.09 | -28.7% | 525 | 0.000 | yes | 42.9% | 40.2% |
| trapdoor_otm1_r1_f30_off | 87.1% | 60.6% | $1.4 million | $2.5 million | 1.00 | 2.53 | -100.0% | 512 | 0.700 | no | 36.5% | 87.0% |
| trapdoor_d20_r2_c7_on | 86.2% | 10.8% | $19,334 | $34,367 | 1.47 | 1.16 | -72.2% | 497 | 0.017 | no | 20.8% | 43.5% |
| trapdoor_d20_r2_f10_on | 85.9% | 13.1% | $17,902 | $27,675 | 1.04 | 1.44 | -92.5% | 496 | 0.700 | no | 43.8% | 56.9% |
| trapdoor_otm2_r2_c5_off | 85.5% | 0.0% | $16,397 | $35,065 | 3.32 | 2.35 | -17.1% | 497 | 0.000 | yes | 5.4% | 0.0% |
| trapdoor_otm2_r1_f10_off | 84.8% | 39.6% | $4.2 million | $19 | 0.87 | -0.30 | -99.8% | 150 | 0.771 | no | 28.7% | 85.4% |
| trapdoor_d30_r2_c10_on | 84.3% | 19.8% | $27,853 | $60,121 | 1.50 | 1.42 | -57.8% | 497 | 0.008 | no | 31.1% | 51.2% |
| trapdoor_d40_r2_f20_on | 84.1% | 43.8% | $11,691 | $9,979 | 1.00 | 1.90 | -98.8% | 486 | 0.700 | no | 43.7% | 75.0% |
| vwap_atm_r1_f50_off | 83.4% | 78.8% | $7.7 million | $14 | 0.87 | 1.01 | -99.7% | 123 | 0.792 | no | 61.8% | 94.6% |
| trapdoor_d20_r2_f30_off | 83.2% | 82.5% | $28,373 | $6.05 | 0.97 | 1.01 | -100.0% | 107 | 0.713 | no | 44.9% | 84.6% |
| trapdoor_d40_r2_c10_on | 82.9% | 22.6% | $31,945 | $75,930 | 1.57 | 1.68 | -39.0% | 497 | 0.003 | no | 35.8% | 49.7% |
| trapdoor_d20_r1_f20_on | 81.8% | 54.6% | $4,578 | $29 | 0.92 | 0.09 | -99.7% | 149 | 0.757 | no | 45.8% | 77.8% |
| trapdoor_otm1_r2_f30_off | 80.0% | 85.3% | $9,055 | $5.15 | 0.95 | 0.51 | -100.0% | 61 | 0.720 | no | 36.0% | 93.4% |
| trapdoor_d30_r1_f30_on | 79.7% | 82.3% | $524 | $20 | 0.94 | 0.13 | -99.9% | 93 | 0.746 | no | 44.6% | 83.6% |
| trapdoor_otm2_r2_f20_off | 79.3% | 69.6% | $2.2 million | $9.47 | 0.86 | 0.27 | -99.9% | 52 | 0.746 | no | 28.2% | 92.4% |
| trapdoor_otm1_r2_c3_off | 79.0% | 0.0% | $13,944 | $29,689 | 2.41 | 2.73 | -10.6% | 497 | 0.000 | yes | 7.9% | 0.0% |
| trapdoor_otm1_r1_f10_on | 79.0% | 20.3% | $12,011 | $42 | 0.84 | -0.92 | -99.2% | 187 | 0.853 | no | 34.0% | 69.7% |
| trapdoor_d20_r2_c10_on | 78.1% | 28.6% | $25,458 | $0.87 | 0.72 | -0.58 | -100.0% | 60 | 0.916 | no | 26.6% | 56.8% |
| trapdoor_d40_r2_f30_off | 77.9% | 83.4% | $9,144 | $25 | 0.91 | 1.04 | -99.8% | 151 | 0.746 | no | 46.0% | 82.3% |
| trapdoor_otm3_r2_c10_off | 76.3% | 0.0% | $18,776 | $37,765 | 3.26 | 1.28 | -41.8% | 497 | 0.001 | no | 2.6% | 24.5% |
| trapdoor_otm2_r1_c10_off | 75.8% | 0.0% | $16,395 | $34,165 | 2.25 | 1.87 | -20.0% | 525 | 0.000 | yes | 13.3% | 28.9% |
| trapdoor_d30_r1_c5_on | 75.8% | 0.0% | $13,626 | $24,398 | 1.42 | 1.84 | -23.4% | 525 | 0.006 | no | 25.8% | 8.1% |
| trapdoor_d30_r1_c3_off | 75.8% | 0.0% | $12,105 | $24,953 | 1.92 | 2.79 | -9.9% | 525 | 0.000 | yes | 2.4% | 0.0% |
| trapdoor_d20_r1_c7_on | 75.1% | 0.9% | $13,825 | $23,311 | 1.34 | 1.56 | -32.7% | 525 | 0.020 | no | 21.2% | 31.2% |
| trapdoor_otm2_r1_f20_off | 74.9% | 74.7% | $288,205 | $10 | 0.89 | -0.01 | -99.9% | 71 | 0.746 | no | 22.6% | 93.5% |
| trapdoor_otm3_r2_c7_off | 72.4% | 0.0% | $13,893 | $27,186 | 3.26 | 1.50 | -30.5% | 497 | 0.001 | no | 0.0% | 13.4% |
| trapdoor_otm3_r2_f10_off | 72.1% | 68.2% | $359,319 | $18 | 0.26 | -1.64 | -99.3% | 67 | 1.000 | no | 21.6% | 89.3% |
| trapdoor_d40_r2_c3_on | 70.7% | 0.0% | $11,899 | $24,529 | 1.57 | 1.89 | -21.2% | 497 | 0.003 | no | 13.1% | 0.3% |
| trapdoor_otm1_r2_f10_on | 70.7% | 20.7% | $8,624 | $35 | 0.67 | -0.57 | -99.2% | 138 | 0.931 | no | 39.0% | 70.8% |
| trapdoor_d20_r2_c5_on | 70.5% | 0.2% | $14,524 | $25,262 | 1.47 | 1.25 | -56.1% | 497 | 0.017 | no | 16.2% | 18.6% |
| trapdoor_otm1_r2_c10_on | 70.3% | 32.9% | $25,507 | $47,695 | 1.45 | 1.14 | -78.3% | 497 | 0.024 | no | 17.8% | 50.1% |
| trapdoor_d30_r1_f50_off | 70.3% | 97.0% | $12 | $2.91 | 0.98 | 1.35 | -100.0% | 99 | 0.713 | no | 43.8% | 91.9% |
| trapdoor_d30_r2_f20_on | 70.0% | 68.0% | $2,804 | $31 | 0.80 | -0.01 | -99.5% | 88 | 0.803 | no | 43.5% | 78.1% |
| trapdoor_d20_r1_c3_off | 69.4% | 0.0% | $11,081 | $22,961 | 2.29 | 3.10 | -6.6% | 525 | 0.000 | yes | 2.2% | 0.0% |
| trapdoor_otm2_r1_c7_off | 68.9% | 0.0% | $12,227 | $24,666 | 2.25 | 1.96 | -15.4% | 525 | 0.000 | yes | 0.6% | 19.2% |
| trapdoor_otm2_r2_c3_off | 68.4% | 0.0% | $10,838 | $22,039 | 3.32 | 2.52 | -11.4% | 497 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_otm1_r1_c10_on | 68.4% | 21.4% | $16,304 | $28,575 | 1.29 | 1.44 | -44.1% | 525 | 0.052 | no | 15.8% | 52.7% |
| trapdoor_otm3_r2_c5_off | 67.7% | 0.0% | $10,638 | $20,133 | 3.26 | 1.68 | -22.4% | 497 | 0.001 | yes | 0.0% | 0.0% |
| trapdoor_otm1_r2_c7_on | 65.2% | 21.9% | $18,983 | $34,136 | 1.45 | 1.25 | -63.8% | 497 | 0.024 | no | 18.0% | 33.5% |
| trapdoor_d40_r1_c3_on | 64.1% | 0.0% | $11,153 | $21,798 | 1.54 | 2.34 | -15.6% | 525 | 0.000 | yes | 10.4% | 0.8% |
| trapdoor_d30_r2_c3_on | 63.6% | 0.0% | $10,432 | $19,786 | 1.50 | 1.60 | -28.7% | 497 | 0.008 | no | 3.9% | 0.0% |
| trapdoor_otm1_r2_c5_on | 63.4% | 15.7% | $14,274 | $25,097 | 1.45 | 1.32 | -51.2% | 497 | 0.024 | no | 19.1% | 20.6% |
| trapdoor_d20_r1_f50_off | 63.4% | 97.9% | $4.40 | $3.26 | 1.00 | 1.52 | -100.0% | 100 | 0.700 | no | 38.8% | 92.8% |
| trapdoor_otm2_r2_f10_on | 62.4% | 67.3% | $2,789 | $20 | 0.58 | -1.48 | -99.6% | 79 | 0.919 | no | 25.3% | 80.5% |
| trapdoor_otm1_r1_f20_on | 59.7% | 77.4% | $502 | $11 | 0.87 | -0.61 | -99.9% | 103 | 0.781 | no | 32.7% | 86.0% |
| trapdoor_otm2_r2_c10_on | 58.3% | 28.8% | $19,024 | $32,520 | 1.49 | 0.97 | -79.6% | 497 | 0.043 | no | 18.5% | 34.5% |
| trapdoor_d20_r1_f30_on | 57.8% | 90.1% | $67 | $17 | 0.91 | 0.07 | -99.9% | 83 | 0.746 | no | 35.3% | 86.9% |
| trapdoor_atm_r1_f50_off | 57.1% | 97.7% | $21 | $13 | 0.96 | 1.28 | -99.9% | 100 | 0.720 | no | 43.5% | 91.8% |
| trapdoor_otm2_r2_c7_on | 56.9% | 20.7% | $14,067 | $23,514 | 1.49 | 1.10 | -60.1% | 497 | 0.043 | no | 8.1% | 18.5% |
| trapdoor_otm3_r2_c10_on | 56.9% | 32.9% | $13,715 | $21,840 | 1.55 | 0.94 | -58.9% | 497 | 0.065 | no | 0.3% | 36.7% |
| trapdoor_d20_r1_c5_on | 56.2% | 0.0% | $10,590 | $17,365 | 1.34 | 1.58 | -28.1% | 525 | 0.020 | no | 9.0% | 18.2% |
| trapdoor_otm1_r1_c7_on | 56.2% | 13.1% | $12,674 | $20,752 | 1.29 | 1.44 | -38.5% | 525 | 0.052 | no | 16.0% | 32.3% |
| trapdoor_otm2_r2_c5_on | 55.8% | 18.9% | $10,762 | $17,510 | 1.49 | 1.20 | -45.3% | 497 | 0.043 | no | 0.0% | 3.0% |
| trapdoor_otm3_r2_c7_on | 55.8% | 28.3% | $10,351 | $16,038 | 1.55 | 1.08 | -42.0% | 497 | 0.065 | no | 0.0% | 19.2% |
| trapdoor_otm1_r1_c3_off | 55.5% | 0.0% | $10,279 | $21,036 | 2.05 | 2.96 | -6.7% | 525 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_otm2_r1_c10_on | 55.5% | 36.4% | $9,477 | $12,690 | 1.19 | 0.95 | -60.2% | 525 | 0.219 | no | 1.9% | 54.8% |
| trapdoor_otm1_r1_c5_on | 55.1% | 0.9% | $9,767 | $15,537 | 1.29 | 1.43 | -32.9% | 525 | 0.052 | no | 3.0% | 13.4% |
| trapdoor_d20_r2_c3_on | 54.4% | 0.0% | $9,714 | $16,157 | 1.47 | 1.38 | -37.0% | 497 | 0.017 | no | 3.8% | 1.9% |
| trapdoor_otm1_r2_c3_on | 54.4% | 2.8% | $9,564 | $16,058 | 1.45 | 1.41 | -35.0% | 497 | 0.024 | no | 0.1% | 2.1% |
| trapdoor_d20_r2_f20_on | 54.4% | 91.0% | $257 | $25 | 0.74 | -0.58 | -99.6% | 60 | 0.805 | no | 38.0% | 81.3% |
| trapdoor_otm2_r2_f30_off | 54.4% | 97.0% | $6.22 | $6.62 | 0.87 | 0.44 | -100.0% | 36 | 0.733 | no | 21.1% | 96.3% |
| trapdoor_otm2_r1_f30_off | 54.1% | 94.0% | $6.43 | $5.18 | 0.85 | 0.22 | -99.9% | 51 | 0.758 | no | 20.3% | 94.9% |
| trapdoor_d40_r1_f50_off | 53.7% | 97.9% | $19 | $4.49 | 0.96 | 1.16 | -100.0% | 85 | 0.720 | no | 44.3% | 92.2% |
| trapdoor_otm2_r1_f10_on | 47.9% | 47.2% | $3,163 | $20 | 0.72 | -1.74 | -99.6% | 120 | 0.919 | no | 22.9% | 87.0% |
| trapdoor_d40_r2_f30_on | 47.0% | 96.5% | $56 | $18 | 0.82 | -0.14 | -99.8% | 46 | 0.771 | no | 37.9% | 84.4% |
| trapdoor_otm2_r1_c7_on | 46.8% | 30.9% | $7,444 | $9,633 | 1.19 | 0.94 | -47.6% | 525 | 0.219 | no | 0.0% | 33.3% |
| trapdoor_otm1_r1_f50_off | 46.8% | 100.0% | $3.19 | $2.48 | 0.99 | 1.03 | -100.0% | 58 | 0.703 | no | 27.8% | 98.1% |
| trapdoor_otm3_r2_f20_off | 46.3% | 93.5% | $9.59 | $8.72 | 0.09 | -0.80 | -99.7% | 38 | 1.000 | no | 17.2% | 94.9% |
| trapdoor_otm3_r2_f10_on | 43.8% | 84.6% | $76 | $19 | 0.36 | -1.84 | -99.4% | 67 | 1.000 | no | 14.2% | 90.7% |
| trapdoor_otm1_r2_f20_on | 43.8% | 91.0% | $71 | $13 | 0.72 | -0.21 | -99.8% | 75 | 0.806 | no | 32.4% | 91.7% |
| trapdoor_otm2_r1_c5_off | 42.6% | 0.0% | $9,448 | $18,333 | 2.25 | 2.05 | -11.7% | 525 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_d30_r2_f30_on | 41.7% | 98.4% | $40 | $17 | 0.79 | 0.12 | -99.8% | 56 | 0.776 | no | 36.2% | 90.1% |
| trapdoor_d20_r2_f50_off | 41.2% | 100.0% | $3.52 | $2.93 | 0.95 | 0.70 | -100.0% | 40 | 0.713 | no | 30.6% | 96.0% |
| trapdoor_d30_r1_c3_on | 40.1% | 0.0% | $9,176 | $15,639 | 1.42 | 1.86 | -18.6% | 525 | 0.006 | no | 0.0% | 0.5% |
| trapdoor_otm2_r2_f20_on | 40.1% | 100.0% | $11 | $10 | 0.67 | -0.67 | -99.9% | 43 | 0.803 | no | 18.8% | 94.1% |
| trapdoor_d30_r2_f50_off | 39.4% | 100.0% | $4.55 | $4.09 | 0.83 | 0.58 | -100.0% | 42 | 0.746 | no | 36.1% | 94.0% |
| trapdoor_otm3_r2_f30_off | 38.0% | 100.0% | $5.77 | $5.44 | 0.02 | -0.38 | -99.8% | 28 | 1.000 | no | 14.0% | 96.9% |
| trapdoor_otm1_r1_f30_on | 37.6% | 96.1% | $18 | $6.42 | 0.86 | -0.34 | -99.9% | 60 | 0.771 | no | 25.4% | 92.8% |
| trapdoor_d40_r1_f50_on | 37.1% | 100.0% | $19 | $19 | 0.90 | 0.85 | -99.9% | 62 | 0.746 | no | 38.6% | 93.0% |
| trapdoor_otm2_r1_f20_on | 36.9% | 90.1% | $44 | $8.86 | 0.79 | -1.03 | -99.9% | 61 | 0.806 | no | 17.0% | 93.5% |
| trapdoor_d40_r2_f50_off | 36.9% | 100.0% | $13 | $3.48 | 0.83 | 0.33 | -100.0% | 35 | 0.746 | no | 37.7% | 93.1% |
| trapdoor_otm1_r2_f50_off | 36.9% | 100.0% | $3.00 | $3.23 | 0.94 | 0.56 | -100.0% | 31 | 0.713 | no | 27.0% | 97.1% |
| trapdoor_otm3_r2_f20_on | 34.3% | 100.0% | $9.35 | $9.65 | 0.37 | -0.97 | -99.7% | 39 | 1.000 | no | 12.4% | 95.1% |
| trapdoor_otm1_r2_f30_on | 33.6% | 100.0% | $12 | $6.65 | 0.73 | 0.11 | -99.9% | 53 | 0.771 | no | 28.5% | 93.9% |
| trapdoor_d30_r1_f50_on | 32.9% | 100.0% | $12 | $7.55 | 0.90 | 0.66 | -99.9% | 54 | 0.746 | no | 33.7% | 93.3% |
| trapdoor_d20_r2_f30_on | 31.8% | 100.0% | $23 | $14 | 0.76 | -0.32 | -99.8% | 42 | 0.771 | no | 32.0% | 91.1% |
| trapdoor_otm2_r2_f50_off | 31.6% | 100.0% | $2.98 | $2.57 | 0.91 | 0.23 | -100.0% | 15 | 1.000 | no | 14.4% | 97.9% |
| trapdoor_otm2_r1_f50_off | 31.1% | 100.0% | $2.90 | $3.36 | 0.53 | 0.46 | -99.9% | 30 | 0.933 | no | 17.2% | 99.5% |
| trapdoor_otm2_r2_f30_on | 30.9% | 100.0% | $6.09 | $4.74 | 0.73 | -0.72 | -99.9% | 24 | 1.000 | no | 15.8% | 96.2% |
| trapdoor_otm3_r2_c5_on | 30.6% | 20.0% | $8,108 | $12,170 | 1.55 | 1.16 | -30.4% | 497 | 0.065 | no | 0.0% | 0.0% |
| trapdoor_otm3_r1_f10_off | 29.0% | 94.7% | $20 | $19 | 0.23 | -2.51 | -99.2% | 60 | 1.000 | no | 8.9% | 92.4% |
| trapdoor_d20_r1_f50_on | 28.6% | 100.0% | $9.47 | $8.35 | 0.85 | 0.48 | -99.9% | 47 | 0.757 | no | 32.6% | 95.3% |
| trapdoor_d40_r2_f50_on | 27.0% | 100.0% | $17 | $11 | 0.80 | 0.24 | -99.9% | 31 | 0.746 | no | 29.2% | 95.3% |
| trapdoor_d30_r2_f50_on | 26.3% | 100.0% | $12 | $6.81 | 0.80 | 0.16 | -99.9% | 31 | 0.746 | no | 29.4% | 95.8% |
| trapdoor_otm2_r1_f30_on | 26.3% | 100.0% | $5.97 | $5.00 | 0.79 | -0.50 | -99.9% | 49 | 0.803 | no | 15.7% | 94.7% |
| trapdoor_otm1_r1_f50_on | 25.8% | 100.0% | $4.57 | $4.64 | 0.73 | 0.19 | -99.9% | 36 | 0.803 | no | 20.6% | 99.2% |
| trapdoor_otm2_r1_f50_on | 23.3% | 100.0% | $3.06 | $3.97 | 0.65 | 0.04 | -99.9% | 28 | 1.000 | no | 14.5% | 99.5% |
| trapdoor_otm3_r1_f10_on | 23.0% | 89.2% | $61 | $20 | 0.42 | -2.57 | -99.2% | 72 | 1.000 | no | 6.8% | 91.9% |
| trapdoor_otm3_r1_f20_on | 23.0% | 100.0% | $9.38 | $9.65 | 0.38 | -1.47 | -99.6% | 48 | 1.000 | no | 7.7% | 94.1% |
| trapdoor_d20_r2_f50_on | 22.8% | 100.0% | $8.65 | $9.72 | 0.80 | -0.18 | -99.9% | 20 | 1.000 | no | 25.3% | 96.9% |
| trapdoor_otm3_r2_f50_off | 22.8% | 100.0% | $2.98 | $3.55 | 0.00 | -1.93 | -99.9% | 10 | 1.000 | no | 9.3% | 98.7% |
| trapdoor_otm3_r1_f20_off | 21.4% | 100.0% | $9.06 | $8.41 | 0.17 | -1.42 | -99.7% | 34 | 1.000 | no | 10.2% | 94.7% |
| trapdoor_otm3_r2_f30_on | 21.0% | 100.0% | $5.73 | $6.69 | 0.42 | -0.38 | -99.8% | 28 | 1.000 | no | 10.3% | 97.4% |
| trapdoor_otm2_r2_f50_on | 20.5% | 100.0% | $3.07 | $3.01 | 0.82 | -0.23 | -100.0% | 15 | 1.000 | no | 11.1% | 98.1% |
| trapdoor_otm1_r2_f50_on | 19.6% | 100.0% | $4.37 | $3.76 | 0.79 | -0.27 | -100.0% | 19 | 1.000 | no | 19.5% | 97.2% |
| trapdoor_otm3_r1_f30_off | 19.4% | 100.0% | $5.81 | $4.72 | 0.08 | -0.90 | -99.8% | 24 | 1.000 | no | 10.1% | 96.5% |
| trapdoor_otm3_r2_f50_on | 16.4% | 100.0% | $2.94 | $3.78 | 0.54 | -1.28 | -99.9% | 12 | 1.000 | no | 7.2% | 98.8% |
| trapdoor_otm3_r1_f30_on | 14.1% | 100.0% | $5.72 | $5.32 | 0.26 | -0.93 | -99.8% | 32 | 1.000 | no | 8.0% | 96.2% |
| trapdoor_otm3_r1_f50_on | 13.6% | 100.0% | $2.94 | $3.26 | 0.03 | -0.92 | -99.9% | 18 | 1.000 | no | 6.9% | 99.5% |
| trapdoor_otm3_r1_f50_off | 13.4% | 100.0% | $2.99 | $2.84 | 0.01 | -0.60 | -99.9% | 14 | 1.000 | no | 7.6% | 99.5% |
| trapdoor_otm3_r1_c10_on | 9.4% | 46.3% | $4,624 | $2,589 | 1.00 | 0.64 | -96.8% | 525 | 0.700 | no | 0.0% | 61.0% |
| trapdoor_otm2_r2_c3_on | 2.5% | 6.9% | $7,457 | $11,506 | 1.49 | 1.30 | -28.8% | 497 | 0.043 | no | 0.0% | 0.0% |
| trapdoor_otm3_r1_c10_off | 2.1% | 29.7% | $6,495 | $10,259 | 1.52 | 0.62 | -89.0% | 525 | 0.074 | no | 0.0% | 54.3% |
| trapdoor_otm3_r2_c3_off | 0.0% | 0.0% | $7,383 | $13,080 | 3.26 | 1.88 | -13.8% | 497 | 0.001 | yes | 0.0% | 0.0% |
| trapdoor_d20_r1_c3_on | 0.0% | 0.0% | $7,354 | $11,419 | 1.34 | 1.59 | -21.2% | 525 | 0.020 | no | 0.0% | 0.0% |
| trapdoor_otm1_r1_c3_on | 0.0% | 0.0% | $6,860 | $10,322 | 1.29 | 1.42 | -24.5% | 525 | 0.052 | no | 0.0% | 0.4% |
| trapdoor_otm2_r1_c3_off | 0.0% | 0.0% | $6,669 | $12,000 | 2.25 | 2.17 | -7.6% | 525 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_atm_r1_c1_off | 0.0% | 0.0% | $6,648 | $12,265 | 1.77 | 2.99 | -6.5% | 525 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_d20_r2_c1_off | 0.0% | 0.0% | $6,439 | $11,872 | 2.61 | 3.02 | -4.9% | 497 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_d40_r2_c1_off | 0.0% | 0.0% | $6,400 | $12,152 | 1.87 | 2.54 | -7.5% | 497 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_d30_r2_c1_off | 0.0% | 0.0% | $6,400 | $11,967 | 2.08 | 2.67 | -6.8% | 497 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_otm1_r2_c1_off | 0.0% | 0.0% | $6,315 | $11,563 | 2.41 | 2.92 | -4.5% | 497 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_d40_r1_c1_off | 0.0% | 0.0% | $6,041 | $10,942 | 1.81 | 2.99 | -6.0% | 525 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_otm3_r2_c3_on | 0.0% | 0.0% | $5,865 | $8,302 | 1.55 | 1.22 | -25.3% | 497 | 0.065 | no | 0.0% | 0.0% |
| trapdoor_d30_r1_c1_off | 0.0% | 0.0% | $5,702 | $9,984 | 1.92 | 2.96 | -4.7% | 525 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_d40_r2_c1_on | 0.0% | 0.0% | $5,633 | $9,843 | 1.57 | 1.99 | -9.2% | 497 | 0.003 | no | 0.0% | 0.0% |
| trapdoor_d40_r1_c1_on | 0.0% | 0.0% | $5,384 | $8,933 | 1.54 | 2.35 | -8.7% | 525 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_d20_r1_c1_off | 0.0% | 0.0% | $5,360 | $9,320 | 2.29 | 3.33 | -3.3% | 525 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_otm2_r2_c1_off | 0.0% | 0.0% | $5,279 | $9,013 | 3.32 | 2.73 | -4.3% | 497 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_d30_r2_c1_on | 0.0% | 0.0% | $5,144 | $8,262 | 1.50 | 1.73 | -11.8% | 497 | 0.008 | no | 0.0% | 0.0% |
| trapdoor_otm1_r1_c1_off | 0.0% | 0.0% | $5,093 | $8,679 | 2.05 | 3.01 | -4.7% | 525 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_d20_r2_c1_on | 0.0% | 0.0% | $4,905 | $7,052 | 1.47 | 1.54 | -13.7% | 497 | 0.017 | no | 0.0% | 0.0% |
| trapdoor_otm1_r2_c1_on | 0.0% | 0.0% | $4,855 | $7,019 | 1.45 | 1.50 | -13.6% | 497 | 0.024 | no | 0.0% | 0.0% |
| trapdoor_d30_r1_c1_on | 0.0% | 0.0% | $4,725 | $6,880 | 1.42 | 1.86 | -10.2% | 525 | 0.006 | no | 0.0% | 0.0% |
| trapdoor_otm2_r1_c3_on | 0.0% | 0.0% | $4,619 | $5,557 | 1.19 | 0.91 | -29.6% | 525 | 0.219 | no | 0.0% | 0.0% |
| trapdoor_otm3_r1_c5_off | 0.0% | 0.0% | $4,498 | $6,379 | 1.52 | 0.88 | -44.5% | 525 | 0.074 | no | 0.0% | 0.0% |
| trapdoor_otm2_r2_c1_on | 0.0% | 0.0% | $4,152 | $5,502 | 1.49 | 1.35 | -15.6% | 497 | 0.043 | no | 0.0% | 0.0% |
| trapdoor_otm3_r2_c1_off | 0.0% | 0.0% | $4,128 | $6,027 | 3.26 | 2.06 | -4.7% | 497 | 0.001 | yes | 0.0% | 0.0% |
| trapdoor_d20_r1_c1_on | 0.0% | 0.0% | $4,118 | $5,473 | 1.34 | 1.57 | -11.0% | 525 | 0.020 | no | 0.0% | 0.0% |
| trapdoor_otm1_r1_c1_on | 0.0% | 0.0% | $3,953 | $5,107 | 1.29 | 1.35 | -11.6% | 525 | 0.052 | no | 0.0% | 0.0% |
| trapdoor_otm2_r1_c1_off | 0.0% | 0.0% | $3,890 | $5,667 | 2.25 | 2.33 | -3.5% | 525 | 0.000 | yes | 0.0% | 0.0% |
| trapdoor_otm3_r1_c3_off | 0.0% | 0.0% | $3,699 | $4,828 | 1.52 | 0.97 | -26.7% | 525 | 0.074 | no | 0.0% | 0.0% |
| trapdoor_otm3_r2_c1_on | 0.0% | 0.0% | $3,622 | $4,434 | 1.55 | 1.21 | -15.1% | 497 | 0.065 | no | 0.0% | 0.0% |
| trapdoor_otm2_r1_c1_on | 0.0% | 0.0% | $3,206 | $3,519 | 1.19 | 0.82 | -16.8% | 525 | 0.219 | no | 0.0% | 0.0% |
| trapdoor_otm3_r1_c1_off | 0.0% | 0.0% | $2,900 | $3,276 | 1.52 | 1.04 | -9.8% | 525 | 0.074 | no | 0.0% | 0.0% |
| trapdoor_otm3_r1_c1_on | 0.0% | 0.0% | $2,712 | $2,509 | 1.00 | 0.07 | -22.7% | 525 | 0.700 | no | 0.0% | 0.0% |
| trapdoor_otm3_r1_c3_on | 0.0% | 1.2% | $3,137 | $2,527 | 1.00 | 0.19 | -49.7% | 525 | 0.700 | no | 0.0% | 0.0% |
| trapdoor_otm3_r1_c7_off | 0.0% | 1.6% | $5,297 | $7,931 | 1.52 | 0.78 | -62.3% | 525 | 0.074 | no | 0.0% | 28.1% |
| trapdoor_otm2_r1_c5_on | 0.0% | 26.5% | $6,032 | $7,595 | 1.19 | 0.94 | -37.3% | 525 | 0.219 | no | 0.0% | 5.9% |
| trapdoor_otm3_r1_c5_on | 0.0% | 32.7% | $3,562 | $2,545 | 1.00 | 0.30 | -65.3% | 525 | 0.700 | no | 0.0% | 5.6% |
| trapdoor_otm3_r1_c7_on | 0.0% | 33.4% | $3,987 | $2,562 | 1.00 | 0.43 | -75.3% | 525 | 0.700 | no | 0.0% | 41.7% |

Live trading stays off. Nothing was added to the selected book.
