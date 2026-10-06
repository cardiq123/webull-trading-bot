# Webull trading bot

A research-first day and swing trading system for a Webull brokerage account.
It paper-trades by default. It will not send a live order unless the config
flag is on **and** you type a confirmation phrase at startup. No strategy in
this repository is guaranteed to make money. The default book is whatever
survived a walk-forward test on free data, and that answer can be "cash."

## What it will not pretend

Published trading rules are hypotheses. This project implements a set of
well-known ones, then asks the data whether they still have a positive
expectancy after costs, on data the parameters were not fit to. The gates
are in `src/webull_bot/backtest/assessment.py`. A strategy is eligible for
the default book only when all of these are true:

- Default parameters (not a mined neighbor) make money from 2017 onward.
- Profit factor is at least 1.10, Sharpe at least 0.40, at least 20 trades,
  and the drawdown is no worse than -30%.
- The in-sample parameter grid is not fragile, and walk-forward choices do
  not flip the sign of the result.
- The test universe is ETFs. A list of today's surviving stocks is reported
  as a diagnostic and is not allowed to set the default.
- The result still has a profit factor above 1.0 at 15 bps of slippage.

The numbers from the run that produced `config/selected_strategies.json` are
in [RESULTS.md](RESULTS.md) and are repeated below after that file exists.
Re-run `python -m webull_bot research` before you trust an old table.

## Setup

Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

`pip install -r requirements.txt` is the same set of packages. Tests:

```bash
pytest
```

Configuration is `config/default.yaml`. Secrets are environment variables
only. A local `.env` is loaded if present and is gitignored. Nothing in
`.env.example` is a real credential.

## Webull API access

Use the official OpenAPI, not an unofficial client. The adapter is
`src/webull_bot/broker/webull.py` and talks to
`webull-openapi-python-sdk`.

1. Open a Webull brokerage account. The API application is rejected until
   the account is open.
2. Apply under OpenAPI Management:
   <https://www.webull.com/center#openApiManagement>.
   The published review time is 1–2 business days.
   Docs: <https://developer.webull.com/apis/docs/getting-started>.
3. After approval, generate an app key and app secret. Put them in the
   environment as `WEBULL_APP_KEY` and `WEBULL_APP_SECRET`.
   `WEBULL_ACCOUNT_ID` is the internal `account_id` from the account list
   (about 26 characters). It is not the `DEVxxxx` `account_number`.
   Calling the trade API with the account number returns HTTP 403
   `ACCOUNT_ACCESS_DENIED`. The adapter accepts either form and maps an
   account number to the internal id. Leave `WEBULL_ACCOUNT_ID` empty to
   select by `WEBULL_ACCOUNT_CLASS`: `INDIVIDUAL_MARGIN` (the default) or
   `INDIVIDUAL_CASH`. A sandbox key can see futures, events, and crypto
   accounts as well; those classes are not selected by that default.
4. Sandbox trade host: `api.sandbox.webull.com` (`WEBULL_ENV=sandbox`).
   Sandbox quote streaming host: `data-api.sandbox.webull.com`.
   Sandbox events host: `events-api.sandbox.webull.com`.
   Production trading host: `api.webull.com`, and only when
   `WEBULL_ENV=production` is set explicitly. An unset `WEBULL_ENV` does
   not mean production. The SDK already knows the production map; this
   code only overrides hosts for the sandbox. The SDK session token is
   stored under `~/.webull-openapi-token` (`WEBULL_OPENAPI_TOKEN_DIR`
   overrides that), not in `./conf`. SDK logs are set to WARNING and a
   filter redacts the app key, secret, and token.
5. US equity orders used here are `MARKET`, `LIMIT`, `STOP_LOSS`, and
   `STOP_LOSS_LIMIT`, day or GTC, core session, quantity entrust.
   `MARKET_ON_OPEN` and `MARKET_ON_CLOSE` are documented as institutional
   only and are not sent.
6. Market data is a **separate** OpenAPI subscription. Without it, history
   and streaming quotes return 403. The bot backtests and paper-trades on
   Yahoo Finance so you can work before that subscription exists. Live
   order routing still uses Webull; the quote source in the live loop is
   Yahoo unless you point a `WebullDataProvider` at a subscribed client.
7. The first `TradeClient` construction can require an in-app 2FA / device
   approval. Balances use `total_net_liquidation_value` and
   `total_cash_balance`. Buying power is read from
   `account_currency_assets[0]` (`day_buying_power`, then `buying_power`,
   then `overnight_buying_power`). Account type comes from the account
   list (`CASH` or `MARGIN`), not a hard-coded margin flag. History bars
   use `get_batch_history_bar` with timespans `M1`, `M5`, `M15`, `M30`,
   `M60`, `M120`, `M240`, `D`, `W`, `M`, and `Y`. The tests for those
   shapes are offline. This process does not call the API.

Webull US stock and ETF trades are commission-free. Sells still pick up the
SEC Section 31 fee and the FINRA trading activity fee. From April 4, 2026
the Section 31 rate is $20.60 per million dollars of covered sales. The
2026 FINRA TAF on equities is $0.000195 per share, capped at $9.79 per
trade. FINRA set that fee to $0 for transactions from October 1, 2026
through December 31, 2026. Research uses the statutory rate so a three-month
holiday does not flatter the test.

## Data

`data.provider` defaults to `yfinance`.

| Feed | What you get | What you do not get |
|---|---|---|
| Yahoo daily | Multi-year adjusted OHLCV, no key | Consolidated-tape fidelity. Delisted names. A survivor-free universe. |
| Yahoo 1-minute | About 7 days | A serious intraday sample |
| Yahoo 5- and 15-minute | About 60 days | A serious intraday sample |
| Yahoo hourly | About 730 days | Enough history to claim a durable day-trading edge |
| CSV | Your own files in a directory, `{SYMBOL}.csv` | Nothing automatic |
| Webull OpenAPI | Historical bars and streaming quotes when subscribed | A free ride. 403 without the market-data subscription. Depth of history was not verified without keys. |

Adjusted prices are the right input for a total-return test and a bad input
for a literal "what was the print" gap. The gap rule drops gaps above 20%
so a bad adjustment does not become a trade. Breadth is the share of the
survivor stock list above its 50-day average, which overstates historical
breadth. Treat stock-only results as biased upward.

## Strategies

Each one cites the idea it borrows. The hard stop is this system's rule,
including where the original author did not use one.

**Day**

- Opening range breakout. Toby Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990). First bar is the range; a later close through the high, with relative volume, fills on the next bar. Flat by the session close. On hourly bars the "opening range" is the first hour.
- VWAP pullback. Brian Shannon, *Technical Analysis Using Multiple Timeframes*. A push off the open, a tag of session VWAP, a close back above it. Next-bar fill, flat by the close.
- Gap-and-go. The public momentum-scanner shape (gap plus relative volume; a widely published retail version is Ross Cameron's). Only information known at the open is used: today's open versus yesterday's close, and yesterday's volume versus its own average. The stop is a gap fill. Flat at the close.
- End-of-day weakness. Larry Connors' short-term washout, held overnight. The signal is the close; the fill is the **next** open, so the close that defined the signal is not the fill.

**Swing**

- 10/20 EMA pullback in a stage-2 uptrend. Mark Minervini's trend template, and the short-average pullback used in that swing tradition.
- Volatility-contraction breakout. Minervini's VCP and O'Neil's CAN SLIM base, measured only on price and volume. Earnings, float, and sponsorship are not in the data, so this is not full CAN SLIM.
- Connors RSI(2). *Short Term Trading Strategies That Work*. Long above the 200-day average when RSI(2) is washed out; exit above a short average. A 2.5 ATR catastrophic stop is added.
- Relative-strength rotation. Jegadeesh and Titman (Journal of Finance, 1993) and O'Neil relative strength. Monthly, skip-a-month return, top ETFs.
- Dual momentum. Gary Antonacci, *Dual Momentum Investing*. Relative momentum across SPY, QQQ, IWM, EFA, EEM, TLT, and GLD, held only when it beats BIL's trailing return. Otherwise cash, which earns zero here (slightly pessimistic versus holding bills). A 20% trail is the hard stop Antonacci's monthly process does not use.
- Blue-chip reversal. Point-in-time Dow 30 membership (effective-dated component changes, not a 2026 survivor list). Daily swing: a tag of a confirmed swing low or the 200-day EMA, RSI washed out, RSI(14) bullish divergence, then a 10-day EMA reclaim. Stop under the swing low, target at the last swing high, 15-session time stop. The parameter grid is six pre-registered variants. Long calls and bull call spreads in the research report are Black-Scholes estimates (realized volatility times 1.15, bid/ask, and the Webull option fee schedule). They are not historical prints, and paper mode fills the stock. The Webull adapter can build the official single-leg and vertical option payloads and does not send them.
- Support reversal. Same Dow membership. A 20-day, monthly, or year-to-date low that sits on horizontal pivot support or a rising pivot trendline, then a bullish candle. The published default is the 20-day low plus the horizontal zone. Calls in the research report exit at +30% of premium in the model. Paper, if it were enabled, would buy the stock.
- Wedge breakout. Same Dow membership. A close beyond a converging wedge, triangle, or prior-window range, confirmed by a wide-body candle. Bullish breaks are long stock and calls. Bearish breaks are a research short-stock and long-put baseline. Paper does not sell short and does not send option orders.

**Regime filter.** A long momentum or breakout signal also needs the tape.
`risk_on` requires SPY above its 200-day average, VIX under 30, and at least
40% of the stock list above the 50-day average. `aggressive_ok` also requires
QQQ above its 200-day, VIX under 25, and breadth of at least 45%. Open-time
strategies use yesterday's reading. Dual momentum carries its own absolute-
momentum switch and does not wait for this flag.

## Risk

- Size is `floor(equity * risk_per_trade / (entry - stop))`, default risk
  0.75% of equity, then capped at 20% of equity. If the cap binds, the trade
  risks less, never more. A stop that is not below the entry is rejected.
  One share that would risk more than the budget is skipped.
- Every position has a hard stop. A gap through the stop fills at the open.
- Daily loss default 2% of the session's starting equity. New entries stop.
  With `flatten_on_daily_loss` the book is sold.
- Drawdown default 15% from the equity peak. The halt stays on until you
  clear it. It does not silently reset because the market bounced.
- Caps on concurrent positions, sector weight, and pairwise correlation.
- Long-only. Shorts exist on the Webull payload and stay off in config.
- Pattern day trader logic follows the rule as of September 2026. FINRA
  Regulatory Notice 26-10 (April 20, 2026) removed the pattern day trader
  label, the four-day-trades-in-five-sessions test, and the $25,000 minimum,
  effective June 4, 2026, with a phase-in through October 20, 2027. The
  $2,000 floor to use margin was not removed. `pdt.mode: auto` still enforces
  the legacy test during the phase-in, because this code cannot see whether
  Webull has finished migrating. It also blocks new exposure that would
  create a simplified intraday margin deficit (25% of gross long market
  value against equity). Cash accounts are not pattern day traders; sale
  proceeds settle the next session (T+1).

`python -m webull_bot kill` cancels open paper orders. `--flatten` also
exits paper positions at the last mark. `--mode live` refuses to run unless
`WEBULL_LIVE_CONFIRM` is exactly `I UNDERSTAND LIVE TRADING RISK`.

## Run

Backtest the selected book (or `--strategy connors_rsi2` and repeat the flag):

```bash
python -m webull_bot backtest --config config/default.yaml
```

The report is `reports/backtest.html`.

Paper, which is the default and does not touch Webull:

```bash
python -m webull_bot paper --replay --max-cycles 5
```

That replays the last five daily sessions through the paper broker, writes
`data/journal.sqlite`, and prints equity. Omit `--replay` to poll during
NYSE hours (America/New_York, weekends and full-day holidays idle) and run
one after-close pass. `--max-cycles` stops an unattended loop.
`--max-cycles 45` replays the last 45 daily sessions of the selected book.

To replay every implemented strategy (dual momentum, the other stock rules,
and the eight Chart Fanatics specs) through that same paper broker and
compare each one to a backtest of the same sessions:

```bash
python -m webull_bot paper-sim
```

`paper-sim` writes the comparison into `RESULTS.md`. It uses simulated
fills, protective stops, the daily-loss flatten, and the kill-switch
flatten. It does not place an order at a broker. Chart Fanatics specs that
are futures or crypto are rehearsed on the paper ledger with margin
reserved so a contract-sized print can exist; shorts are not sent, and
those specs are not added to the Webull stock config.

### Pointing the bot at a Webull paper account

`paper` without `--broker`, and `paper-sim`, never call Webull, even if
API keys are set. They fill inside this process.

Webull's OpenAPI test host is the sandbox. After the API application is
approved, put the keys in the environment:

```bash
export WEBULL_APP_KEY=... WEBULL_APP_SECRET=...
export WEBULL_ACCOUNT_ID=...   # internal account_id, not the DEVxxxx account_number
export WEBULL_ENV=sandbox
export WEBULL_ACCOUNT_CLASS=INDIVIDUAL_MARGIN   # or INDIVIDUAL_CASH
```

Read-only check (accounts, balances, positions, open orders, SPY quote and bars). Secrets are redacted. It does not send an order:

```bash
python -m webull_bot check --env sandbox
```

One cycle of the default book (dual momentum) against the paper sandbox. This sends real orders, but only to `*.sandbox.webull.com`. It does not read `live_trading_enabled` and it does not ask for the live confirmation phrase. Risk limits and the kill switch still apply.

```bash
python -m webull_bot paper --broker webull-sandbox --max-cycles 1
```

Build those orders and do not send them:

```bash
python -m webull_bot paper --broker webull-sandbox --dry-run --max-cycles 1
```

Each cycle prints and journals one line per strategy and symbol. A dry run still does this when the market is closed, and it does not send. The line is the order (`would BUY EEM qty N MARKET DAY + STOP_LOSS GTC @ X.XX`, or `sent BUY ...` when it is not a dry run) or the reason for no order (`no signal: dual_momentum target EEM already held`, `outside rebalance`). Dual momentum and the other rotation book reconcile the latest month-end target with broker positions on every cycle, not only on the signal day. A held name that is no longer a target is a market sell, and its protective stop is cancelled first. The stop trails the position peak the same way the backtest does. That peak is stored in the journal and reused after a restart. The stop is not lowered.

Cancel and flatten sandbox orders without the live phrase:

```bash
python -m webull_bot kill --mode sandbox --flatten
```

The sandbox command refuses any host other than `*.sandbox.webull.com`, including `api.webull.com`. `paper-sim` and `paper --replay` stay on the local simulator.

Local paper kill, which does not call Webull:

```bash
python -m webull_bot kill --flatten
```

Research, which rewrites `RESULTS.md`, the HTML reports, and
`config/selected_strategies.json`:

```bash
python -m webull_bot research
```

Live. Both gates are required. The config default is `live_trading_enabled: false`.

```bash
# edit config/default.yaml and set live_trading_enabled: true
export WEBULL_APP_KEY=... WEBULL_APP_SECRET=... WEBULL_ACCOUNT_ID=...
export WEBULL_ENV=production
python -m webull_bot live
# type: I UNDERSTAND LIVE TRADING RISK
```

`WEBULL_ENV` must be the explicit value `production`. If it is unset, `live` exits. It does not default to production. Sandbox orders use `paper --broker webull-sandbox` instead.

A non-interactive shell must set `WEBULL_LIVE_CONFIRM` to that same phrase.
If research has not selected a strategy, live exits unless
`allow_unproven_strategies` is true. Leave that false.

Optional `WEBHOOK_URL` receives JSON for fills, stops, and the daily summary.

## Backtester

Signals from the close of bar *t* fill at the open of bar *t+1*. The last
bar in the file cannot fill a next-open order. While the open is being
decided, positions are marked at the open, not at that bar's close. If a
bar trades both the stop and a target, the stop is assumed first. A trail
that the bar's high would tighten is allowed to stop out on that bar's low
(high before low). Day trades are flattened at the session close. Costs are
commission zero, regulatory fees on sells, plus slippage and half the spread
on the fill price.

Walk-forward folds are 2013–2016 / 2017–2018, 2015–2018 / 2019–2020,
2017–2020 / 2021–2022, and 2019–2022 / 2023 through the sample end. Training
windows are not given the test years.

## Results

The research run writes the full table to [RESULTS.md](RESULTS.md). Read
that file for the per-strategy figures. The README section below is updated
from the same run so the default book and the table cannot drift into a
story the backtest did not produce.

<!-- RESULTS_START -->
Research run on 2026-09-25. Daily bars from 2011 for indicators. Scored window
**2017-01-01 through 2026-09-25**. Starting equity $100,000. Commission $0,
SEC fee $20.60 per million dollars sold, FINRA TAF $0.000195 per share sold,
5 bps slippage and 1 bp half-spread. Risk 0.75% of equity per trade.

The default book is **dual momentum** (Antonacci, ETFs: SPY, QQQ, IWM, EFA,
EEM, TLT, GLD, with BIL as the cash hurdle). It was the only strategy that
cleared every gate.

| | Dual momentum, default params | Walk-forward | SPY buy and hold |
|---|---:|---:|---:|
| CAGR | 0.45% | 0.71% | 15.26% |
| Total return | 4.43% | 7.14% | 298.25% |
| Win rate | 54.84% | 59.09% | n/a (one hold) |
| Profit factor | 2.80 | 2.56 | n/a |
| Expectancy | $142.88 | $106.27 | n/a |
| Max drawdown | -1.89% | -1.97% | -33.72% |
| Sharpe | 0.55 | 0.69 | 0.88 |
| Sortino | 0.74 | 0.95 | 1.24 |
| Exposure | 3.47% | 6.02% | 100% |
| Trades | 31 | 66 | 1 |

At 15 bps slippage and 2 bps half-spread the same default-parameter test
still had Sharpe 0.52 and profit factor 2.62. The combined portfolio is
this one strategy, so its figures match the first column. Ending equity
was $104,429.23.

That is not a claim of a better investment than owning SPY. The 20% trail
stop, with 0.75% of equity at risk, sizes the position at about 3.75% of
the account before the 20% cap. Most of the account sits in cash at a zero
yield in this test, which is why the CAGR is under half a percent while
the profit factor on the trades themselves is high. Sharpe here is the
Sharpe of that mostly-cash account. SPY's Sharpe over the same window was
0.88. The strategy cleared the precommitted gates. It did not beat
buy-and-hold on return or on Sharpe.

Nothing else was selected.

**Blue-chip reversal does not pass.** Point-in-time Dow 30, default parameters, same 2017-01-01 through 2026-09-25 window. The pre-registered rule (RSI(2) < 10, RSI(14) divergence, 10-day EMA reclaim) took 5 out-of-sample trades, CAGR -0.06%, total return -0.56%, win rate 40%, profit factor 0.70, max drawdown -2.07%, Sharpe -0.13, exposure 0.26%, average hold 7.0 sessions. The 2013–2016 sample took 0 trades. At 15 bps slippage Sharpe was -0.17 and profit factor 0.62. Flags: parameter_fragile, insufficient_trades, profit factor below 1, negative Sharpe, sharpe_decay, cost_fragile. It is not optional and not the default.

The walk-forward stock path, which is allowed to leave the default for another pre-registered cell, had Sharpe 0.59, profit factor 1.24, and 630 trades. That is not a pass. The gate uses the published default, and the grid did not agree with itself. The same walk-forward trades, repriced as a Black-Scholes estimate, lost money: long calls CAGR -2.48% (Sharpe -0.52), bull call spreads CAGR -11.37% (Sharpe -3.48). Default-parameter calls and spreads were also negative. Modeled option profits are an estimate (no historical chain) and are not a separate gate. Missing Yahoo history: DWDP, KFT, WBA. UTX reuses the RTX series. Full table in [RESULTS.md](RESULTS.md).

**Support reversal does not have an out-of-sample edge.** The pre-registered default (20-day low at horizontal pivot support, bullish candle) on the point-in-time Dow 30, 2017-01-01 through 2026-09-25:

| Book | CAGR | Total | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Trades | +30% hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Long stock, default | 2.40% | 25.97% | 42.28% | $717 | $-472 | $31 | 1.11 | -15.43% | 0.35 | 842 | n/a |
| Long stock, walk-forward | 0.64% | 6.45% | 45.49% | $484 | $-384 | $11 | 1.05 | -12.68% | 0.14 | 677 | n/a |
| Long stock, 15 bps | 0.25% | 2.49% | 42.38% | $603 | $-437 | $4 | 1.01 | -15.44% | 0.07 | 689 | n/a |
| Calls, +30% premium target | -1.01% | -14.79% | 44.09% | $375 | $-580 | $-159 | 0.51 | -15.38% | -0.64 | 93 | 40.86% |

Flags: parameter_fragile, oos_sharpe_below_0_40. The +30% premium target was hit on 40.86% of the default option trades (close-based path 38.46%; 21 DTE 44.83%; 45 DTE 45.10%; delta 0.50 38.81%; premium stop -30% 33.33%; IV 1.00x 41.67%; IV 1.30x 46.72%; doubled bid/ask 34.38%). Every option column lost money. It is not optional and not the default.

**Wedge breakout does not have an out-of-sample edge.** The pre-registered default (converging wedge or triangle, both directions, 0.25 ATR buffer, wide-body candle), same window:

| Book | CAGR | Total | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD | Sharpe | Trades | +30% hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Long stock, default | -0.31% | -2.98% | 54.36% | $225 | $-274 | $-3 | 0.98 | -10.10% | -0.06 | 1010 | n/a |
| Long stock, walk-forward | 1.16% | 11.89% | 42.70% | $177 | $-107 | $14 | 1.23 | -3.34% | 0.57 | 829 | n/a |
| Short stock, default | -15.27% | -80.04% | 40.00% | $99 | $-194 | $-77 | 0.34 | -80.04% | -0.32 | 5 | n/a |
| Calls, +30% target | -0.82% | -12.17% | 55.56% | $392 | $-692 | $-90 | 0.71 | -16.52% | -0.37 | 135 | 52.59% |
| Puts, +30% target | -1.09% | -15.78% | 34.48% | $384 | $-617 | $-272 | 0.33 | -15.78% | -0.88 | 58 | 32.76% |
| Calls and puts, one account | -0.92% | -13.58% | 49.52% | $375 | $-625 | $-129 | 0.59 | -15.44% | -0.54 | 105 | 45.71% |

Flags: parameter_fragile, oos_profit_factor_below_1, oos_sharpe_negative, sharpe_decay. The walk-forward stock Sharpe of 0.57 is the training-window picker leaving the default. It is not the gated book. The combined option book's +30% hit rate was 45.71% (calls 52.59%, puts 32.76%). Close-based marks hit 35.64%. 21 DTE hit 48.98%, 45 DTE 35.35%, delta 0.50 43.48%, premium stop -30% 38.38%, IV 1.00x 47.41%, IV 1.30x 39.00%, doubled bid/ask 34.92%. Every option column lost money: the target is reached often, and the losers are larger than the winners. Short stock is a research baseline on its own $100,000 account and does not charge borrow. It is not optional and not the default.

Example charts of what the detectors mark as a rising trendline and a wedge are in `reports/setups/`. Neither strategy joins the config. The default book is still dual momentum.

**Multi-timeframe VWAP test: does not pass.** A 15-minute trend-and-VWAP options rule for a $1,000 account (calls in an uptrend, puts in a downtrend, delta 0.50, 14 DTE, one contract capped at 25% of equity) found 1 signal in about 60 days of Yahoo 15-minute bars and 6 signals in about two years of hourly bars. Every default contract cost more than the cap, so the option account stayed at $1,000. The rough 0 DTE sensitivity lost both trades it could afford and ended at $651. The same hourly signals as whole shares ended at $992.89, behind one SPY share held over the out-of-sample window ($1,126.37). Under 300 trades, and inside the free Yahoo intraday cap, so it is not optional. Charts of the detected tests are in `reports/setups/`. Nothing was sent to a broker. Full table in [RESULTS.md](RESULTS.md).

**Chart-read EMA and VWAP test: does not pass.** The three Oct 6, 2026 charts (UNH 5-minute failed breakout and 9/20 cross, SPY 5-minute breakout retest, SPY 15-minute retest at 778.57) were turned into frozen rules and the detector marked all three before scoring. A $1,000 fractional-stock account on the 5-minute book ended the out-of-sample window at $978.07 (11 trades), behind a random entry ($986.79) and one SPY share ($1,021.67). Rough 3 DTE singles ended at $839.47. SPY/QQQ debit spreads ended at $621.78. The longer hourly stock sample took 164 out-of-sample trades and ended at $967.77 (profit factor 0.97, Sharpe -0.03), behind buy and hold at $1,126.37. Under 300 trades and inside the free Yahoo intraday cap, so it is not optional. Comparison charts are in `reports/setups/`. Nothing was sent to a broker. Full table in [RESULTS.md](RESULTS.md).

**Chart Fanatics specs: none joins the book.** Eight rules from prop-firm scalpers were scored on the pre-registered default, with walk-forward only inside that grid. Spec 8 (SPY and QQQ, buy the close and sell the next open, 2017-01-01 through 2026-09-30, 2,448 trades) has a positive gross overnight drift and a negative traded result after 5 bps slippage and 1 bp half-spread: Sharpe -1.54, profit factor 0.71, max drawdown -85.64%. Specs 1 and 4 on a Binance BTC/ETH proxy cleared 300 trades and lost money (no edge on that proxy, not a verdict on NQ). Specs 2, 3, 5, 6, and 7 stayed under 300 trades. Yahoo NQ=F and ES=F 5-minute history is about 70 days. Dukascopy's free 1-minute host throttled, so there is no multi-year CME sample. Nothing was added to the optional list. The default is still dual momentum. Full table in [RESULTS.md](RESULTS.md).

- Gap-and-go on ETFs took 1 trade and lost money (Sharpe -0.32). The stock
  diagnostic also lost money (Sharpe -0.41, 67 trades) and is survivorship-biased.
- End-of-day mean reversion on ETFs was slightly profitable (Sharpe 0.15,
  profit factor 1.07, 502 trades) and missed both the 0.40 Sharpe gate and
  the 1.10 profit-factor gate.
- EMA pullback on ETFs was similar (Sharpe 0.26, profit factor 1.11, 594
  trades, max drawdown -14.35%). Sharpe was below 0.40.
- VCP / CAN SLIM-style breakouts produced 0 trades on this ETF universe and
  0 trades on the survivor stock list. The template is strict on daily bars
  of diversified funds, and the stock list did not trigger it either.
- Connors RSI(2) on ETFs had a walk-forward sign flip (walk-forward Sharpe
  -0.09) and a default-parameter Sharpe of 0.07.
- Relative-strength rotation on ETFs did not clear the gates (Sharpe 0.06,
  profit factor 1.06). The stock diagnostic looked strong (Sharpe 1.02,
  profit factor 2.39, 144 trades) and is rejected because the universe is
  a 2026 survivor list.
- Opening-range breakout and VWAP pullback were tested on about two years
  of hourly Yahoo bars. Both lost money out of sample (ORB ETF Sharpe -1.88,
  16 trades; VWAP ETF Sharpe -4.84, 149 trades). A sample that short is
  never eligible, and these runs would have failed on the numbers anyway.

Full tables, including the stock diagnostics, are in [RESULTS.md](RESULTS.md).
Charts are under `reports/`.
<!-- RESULTS_END -->

## Layout

```
src/webull_bot/
  broker/        paper broker and the official Webull adapter
  data/          yfinance, CSV, Webull market data
  strategies/    the library above
  backtest/      engine, walk-forward gates, HTML report
  risk/          sizing, circuit breakers, PDT / intraday margin
  execution/     replay, poll loop, live orders, kill switch
  journal/       SQLite
config/default.yaml
```

## Disclaimer

This is software for research and for paper trading. It is not investment
advice, not a solicitation, and not a claim that any rule will be profitable
in the future. Markets change, costs change, and a backtest that survived
one sample can fail the next. Trade only money you can afford to lose, and
only after you have read `RESULTS.md` and re-run the research yourself.
