<!-- SCALE_OUT_START -->
### Scale-out exit, and a $2,500 start

Backtests only. Nothing was sent to a broker. Live trading stays off. No sandbox book was added.

Paul asked for the account to start at $2,500. The $1,000 and $5,000 columns are the same rules with a different starting cash. They are not extra trials. The scale-out comparison counts 18 exit books on the $2,500 account.

Three contracts, or nothing. Two are sold when the underlying touches the session VWAP outer 2 SD band in the trade direction. Until that touch, the original stop closes all three. The remaining contract is the runner: stop at 90% of the entry premium, or back at the entry premium, or when the whole position is down 10% of the debit. The runner's target is 50% above the entry premium. Anything still open is sold at the 15:45 open. The comparisons are selling all three at the band, at 1R, or at a 50% premium. Prices are Black-Scholes, at the money, 0 DTE, with the prior VIX close.

A continuation that is already outside the 2 SD band can sell the two-thirds on the fill. That rate is in the table. It is the rule, not a second target.

Open versus support, same cells as the published search, rerun from $2,500. The search was not repeated and the holdout cell was not changed. Paul's rule is the training column. The holdout column is only `both_swing10_structure_level_vwap`, the one cell that was scored before. A $2,500 path is a sizing note, not a pass.

The trade counts are not the same at every stake. A wider stop often cannot buy one share in $1,000, and that trade appears once the account is $2,500 or $5,000. The $1,000 and $5,000 endings below match the published search. Win rate, profit factor, Sharpe, and drawdown are the $2,500 book.

| Cell | Window | $1k trades | $2,500 trades | $5k trades | Win | PF | Sharpe | Max DD | $1,000 | $2,500 | $5,000 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| both_prior_day_ema20_level_r1 | train | 790 | 979 | 995 | 46.1% | 0.63 | -1.86 | -48.5% | $608 | $1,305 | $2,477 |
| both_swing10_structure_level_vwap | train | 45 | 185 | 356 | 48.1% | 0.75 | -0.30 | -5.4% | $978 | $2,410 | $4,742 |
| both_swing10_structure_level_vwap | holdout | 1 | 2 | 3 | 50.0% | 1.57 | 0.61 | -0.4% | $1,005 | $2,505 | $5,006 |

Paul's rule from $2,500 takes 979 training trades and ends at $1,305, against $608 from the published $1,000 book (790 trades) and $2,477 from $5,000 (995 trades). The least-bad cell, rerun from $2,500, takes 185 training trades and ends at $2,410. Its holdout, still that one cell, takes 2 trades and ends at $2,505. None of these share books is a pass.

Three-contract debit on those share fills, 0 DTE, before later trades spend the cash:

- both_prior_day_ema20_level_r1 train 0 DTE: 979 of 979 three-lots fit in $2,500, 979 fit in $1,000, 979 fit in $5,000. Median three-lot debit $232. The one-contract model on these $2,500 share fills filled 979, skipped 0, P&L $18,582, ending $21,082.
- both_swing10_structure_level_vwap train 0 DTE: 185 of 185 three-lots fit in $2,500, 185 fit in $1,000, 185 fit in $5,000. Median three-lot debit $165. The one-contract model on these $2,500 share fills filled 185, skipped 0, P&L $7,818, ending $10,318.
- both_swing10_structure_level_vwap holdout 0 DTE: 2 of 2 three-lots fit in $2,500, 2 fit in $1,000, 2 fit in $5,000. Median three-lot debit $469. The one-contract model on these $2,500 share fills filled 2, skipped 0, P&L $295, ending $2,795.
- both_prior_day_ema20_level_r1 train 7 DTE: 970 of 979 three-lots fit in $2,500, 302 fit in $1,000, 979 fit in $5,000. Median three-lot debit $1,223. The one-contract model on these $2,500 share fills filled 903, skipped 76, P&L $-2,018, ending $482.
- both_swing10_structure_level_vwap train 7 DTE: 176 of 185 three-lots fit in $2,500, 109 fit in $1,000, 185 fit in $5,000. Median three-lot debit $801. The one-contract model on these $2,500 share fills filled 185, skipped 0, P&L $1,721, ending $4,221.

A 0 DTE three-lot fits in $2,500 on every one of these share fills, and it fits in $1,000 as well. A 7 DTE three-lot is the one that strains the account: the headline median is about $1,223, so 970 of 979 fit in $2,500 and 302 of 979 fit in $1,000. The one-contract dollars above are a model on the $2,500 share fills. They are not a new trial and they do not replace the published one-contract book.

Tendency: 768 cells, 0 mean-reverting. No share book and no option book was built at $1,000, $2,500, or $5,000. The stake does not change that label. Three-contract feasibility has no entry to price. The holdout was not opened.

Scale-out books. Open-versus-support training is 2018-01-01 through 2026-07-06 and its holdout is 2026-07-07 through 2026-10-06. The VWAP continuation training ends 2021-12-31 and its holdout is 2022-01-01 through 2026-10-06. q is the training false-discovery rate across these exit books.

| Book | Exit | Train n | /day | Win | PF | Sharpe | DD | $1,000 | $2,500 | $5,000 | Hold n | /day | Win | PF | Sharpe | DD | Hold $1,000 | Hold $2,500 | Hold $5,000 | q | Fill scale |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| open_support | all_band | 1206 | 0.566 | 53.0% | 1.41 | 1.31 | -12.4% | $12,082 | $13,582 | $16,082 | 25 | 0.385 | 56.0% | 2.62 | 2.93 | -10.0% | $1,957 | $3,457 | $5,957 | 7.7e-05 | 6.0% |
| open_support | r1 | 1206 | 0.566 | 43.1% | 1.56 | 1.65 | -22.9% | $73,327 | $74,827 | $77,327 | 25 | 0.385 | 40.0% | 1.31 | 1.57 | -70.3% | $192 | $3,835 | $6,335 | 1.9e-08 | 0.0% |
| open_support | pct50 | 1206 | 0.566 | 70.4% | 1.28 | 1.47 | -37.1% | $20,159 | $21,659 | $24,159 | 25 | 0.385 | 72.0% | 1.13 | 1.05 | -39.8% | $1,393 | $2,870 | $5,370 | 7.7e-05 | 0.0% |
| open_support | scale_prem10 | 1206 | 0.566 | 51.4% | 1.39 | 1.32 | -12.7% | $12,517 | $14,017 | $16,517 | 25 | 0.385 | 60.0% | 2.52 | 2.85 | -11.1% | $2,029 | $3,529 | $6,029 | 7.8e-05 | 6.0% |
| open_support | scale_be | 1206 | 0.566 | 51.3% | 1.39 | 1.30 | -13.8% | $12,023 | $13,523 | $16,023 | 25 | 0.385 | 56.0% | 2.65 | 2.91 | -10.8% | $2,007 | $3,507 | $6,007 | 1.1e-04 | 6.0% |
| open_support | scale_full10 | 1206 | 0.566 | 50.1% | 1.42 | 1.51 | -11.4% | $14,850 | $16,350 | $18,850 | 25 | 0.385 | 48.0% | 2.05 | 2.52 | -9.7% | $1,913 | $3,413 | $5,913 | 1.1e-05 | 6.0% |
| vwap_SPY | all_band | 279 | 0.228 | 0.0% | 0.00 | -2.42 | -99.9% | $0 | $3 | $3 | 92 | 0.077 | 0.0% | 0.00 | -1.79 | -99.6% | $8 | $11 | $10 | 1.000 | 90.7% |
| vwap_SPY | r1 | 197 | 0.161 | 36.0% | 0.54 | -1.38 | -100.0% | $1 | $0 | $12,744 | 2355 | 1.972 | 49.7% | 1.39 | 2.38 | -16.6% | $73,451 | $74,951 | $77,451 | 1.000 | 0.0% |
| vwap_SPY | pct50 | 351 | 0.287 | 45.3% | 0.67 | -1.07 | -99.9% | $2 | $2 | $5 | 2493 | 2.088 | 59.6% | 1.15 | 1.91 | -26.0% | $23,357 | $24,857 | $27,357 | 1.000 | 0.0% |
| vwap_SPY | scale_prem10 | 280 | 0.229 | 12.5% | 0.10 | -2.41 | -99.9% | $1 | $3 | $1 | 97 | 0.081 | 14.4% | 0.18 | -1.49 | -99.6% | $9 | $10 | $8 | 1.000 | 90.7% |
| vwap_SPY | scale_be | 284 | 0.232 | 1.1% | 0.01 | -2.18 | -100.0% | $3 | $0 | $5 | 112 | 0.094 | 1.8% | 0.05 | -2.25 | -99.6% | $11 | $11 | $11 | 1.000 | 90.8% |
| vwap_SPY | scale_full10 | 269 | 0.220 | 8.6% | 0.10 | -2.15 | -100.0% | $0 | $0 | $2 | 98 | 0.082 | 25.5% | 0.26 | -1.54 | -99.7% | $9 | $8 | $10 | 1.000 | 90.7% |
| vwap_QQQ | all_band | 303 | 0.254 | 0.0% | 0.00 | -2.13 | -100.0% | $1 | $0 | $3 | 116 | 0.099 | 0.0% | 0.00 | -2.15 | -99.7% | $7 | $8 | $7 | 1.000 | 89.8% |
| vwap_QQQ | r1 | 2025 | 1.696 | 48.0% | 1.55 | 2.31 | -34.3% | $47,422 | $48,922 | $51,422 | 1979 | 1.690 | 48.3% | 1.73 | 2.77 | -9.3% | $123,607 | $125,107 | $127,607 | 7.1e-08 | 0.0% |
| vwap_QQQ | pct50 | 2260 | 1.893 | 61.8% | 1.26 | 1.11 | -63.2% | $0 | $18,049 | $20,549 | 2233 | 1.907 | 67.4% | 1.31 | 2.54 | -17.4% | $36,113 | $37,613 | $40,113 | 1.000 | 0.0% |
| vwap_QQQ | scale_prem10 | 300 | 0.251 | 8.0% | 0.07 | -2.22 | -99.9% | $1 | $2 | $0 | 103 | 0.088 | 5.8% | 0.07 | -2.07 | -99.7% | $7 | $7 | $7 | 1.000 | 89.7% |
| vwap_QQQ | scale_be | 306 | 0.256 | 1.0% | 0.01 | -2.31 | -100.0% | $2 | $1 | $0 | 115 | 0.098 | 0.0% | 0.00 | -2.15 | -99.5% | $7 | $13 | $7 | 1.000 | 89.9% |
| vwap_QQQ | scale_full10 | 296 | 0.248 | 5.7% | 0.08 | -2.36 | -99.9% | $0 | $2 | $3 | 96 | 0.082 | 11.5% | 0.12 | -1.90 | -99.7% | $7 | $8 | $11 | 1.000 | 89.5% |

On the open, a 0 DTE three-lot fits in $2,500 on every signal (median debit about $228), and it fits in $1,000 too. Selling all three at 1R finishes the $2,500 training account at $74,827. The three scale-out stops finish between $13,523 and $16,350. All-out at the band finishes at $13,582, and all-out at a 50% premium finishes at $21,659. Training q on these open-support option books is below 0.10 inside this 18-book family. The share book at $2,500 still ends at $1,305. The option figure is a Black-Scholes model with the prior VIX close, not a listed fill, and it is not a book to trade.

On the 2 SD continuation, about 90% of the scale-out trades sell the two-thirds on the fill, because that entry is already through the band. Those $2,500 books end at a few dollars in training and in the holdout. The original 1R exit is the comparison: QQQ finishes training at $48,922 from $2,500, while SPY's training account goes to about $0 and then skips the later signals. SPY's fresh 1R holdout has 2,355 trades, the same count as the published one-contract book, and finishes at $74,951 from $2,500. Before any loss, every continuation three-lot fits in $2,500 (median debit about $148 on SPY and $111 on QQQ). The skips in the SPY training book are the account after it has already lost the cash. QQQ here is the long Dukascopy 5-minute cache resampled to 15 minutes, which is a longer tape than the earlier VWAP report.

Fill scale is the share of $2,500 training trades that sold the two-thirds on the entry bar. A blank band, or an exit that is not the band, stays at zero. The chart is `reports/scale_out_equity.png`.

Not added to `config/optional_strategies.json` or `config/selected_strategies.json`. The default book is still dual momentum.

```
python3 -m webull_bot.chart_reads.research_scale_out
```
<!-- SCALE_OUT_END -->
