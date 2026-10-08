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

**Daily setup C, descending-trendline breakout: does not pass.** The Oct 6, 2026 UNH daily chart was turned into a frozen rule before scoring. The detector draws the line from 2026-07-29 at 429.04 through 2026-09-09 at 404.04 and tags the late-July and September 3, 8, and 9 rejections. A $1,000 Dow point-in-time stock account ended the out-of-sample window (2019-01-01 through 2026-10-06) at $746.56 on 207 trades (profit factor 0.92, Sharpe -0.12), behind a random entry ($923.94) and four SPY shares ($3,242.23). The same signals as 45 DTE calls ended at $281.24, with 759 skipped because the contract did not fit. The named large-cap stock diagnostic ended at $2,344.05 and is survivorship-biased, under 300 trades, and still behind buy and hold. SPY/QQQ debit spreads ended at $981.23 on 1 trade. Rejection shorts on the Dow ended at $108.74 out of sample, and the full short path ended at $48.89. It is not optional. The chart is in `reports/setups/read1d_UNH_2026.png`. Nothing was sent to a broker. Full table in [RESULTS.md](RESULTS.md).

**Setup D, three breakout types: does not pass.** The diagram's descending triangle (down only), ascending triangle (up only), and horizontal range (either way) were frozen before scoring. A $1,000 Dow point-in-time stock account ended the out-of-sample window at $919.45 on 73 trades (profit factor 0.92, Sharpe -0.03). It beat a random entry ($794.46) and still lost money, and it trails four SPY shares at $3,242.23. The same signals as 45 DTE calls ended at $435.61, with 93 skipped. The named large-cap stock diagnostic ended at $1,174.40 on 35 trades and is survivorship-biased, under a 0.40 Sharpe, and past a 30% drawdown. SPY/QQQ debit spreads took no out-of-sample trades. The 15-minute and 60-minute books are inside the free Yahoo cap (12 and 38 stock trades). It is not optional. Example charts are in `reports/setups/`. Nothing was sent to a broker. Full table in [RESULTS.md](RESULTS.md).

**Support and resistance level set: does not change the gate.** Horizontal pivots, classic floor pivots, prior-day high and low, demand and supply zones, Fibonacci 38.2/50/61.8, trendlines, and flipped levels were frozen before scoring and used only as the profit target on the existing A-D signals. A row had to beat the published target out of sample on ending equity and profit factor, without a drawdown more than five points worse, with at least 20 trades and the level present on at least 30% of signals. Six rows met that test. The largest was setup C with flipped levels, $939.99 against $746.56, profit factor 0.98, and its in-sample book was worse. Setup D confluence ended at $970.48 against $919.45. Setup A floor pivots ended at $928.24 against $886.97 on the hourly continuation book, and the same target made the combined A and B book worse ($935.40 against $967.77). None of the six clears a 1.10 profit factor, a 0.40 Sharpe, a 30% drawdown limit, and 300 trades. They are not the new default. The chart of the live SPY levels is `reports/setups/readSR_SPY_1d.png`. Nothing was sent to a broker. Full table in [RESULTS.md](RESULTS.md).

**Chop filter: does not change the gate.** A bar is chop only when volume is quiet, the range is narrow, the 9 and 20 EMAs are flat and tangled, and price has crossed VWAP at least three times in 20 bars. ADX under 20 or a choppiness index above 61.8 is a stricter sensitivity, not the default. Skipping those bars helps a book only when out-of-sample expectancy rises, losing trades fall, and at least 20 trades remain. That happened on one book. Daily setup C went from $746.56 to $778.23 by dropping one losing trade (expectancy -$1.22 to -$1.08, 126 losers to 125, profit factor 0.93). The in-sample ending was worse, $1,105.06 against $1,129.36, and the stricter cut was the same book. The trades taken while chop, on their own account, lost money: three out-of-sample trades, expectancy -$14.04. Hourly A and B together got worse when chop was skipped ($939.08 against $967.77) even though the losers stayed at 111. The 12 hourly failed-breakout trades taken inside chop had expectancy -$1.24 and ended at $985.07; skipping them left the published B book at $919.25 against $921.86. The 15-minute and 5-minute books did not change, because the trades they took were outside chop. Setup D had no out-of-sample signal inside chop. A breakout from a chop box on relative volume above 1.5 took 4 out-of-sample Dow trades and ended at $1,058.11 (profit factor 2.55, Sharpe 0.25), against setup D at $919.45 on 73 trades. Four trades is not a gate. The 60-minute, 15-minute, and 5-minute breakout books took no out-of-sample trades. Daily bars spend about 0.9% of the time in chop (out-of-sample median 1.0%). The same share on the hourly named list is 0.9%. Example windows are `reports/setups/readCHOP_AAPL_1d.png` (2015-04-01 through 2015-04-14), `reports/setups/readCHOP_META_60m.png` (2025-10-16, 10:30 through 15:30 ET), and `reports/setups/readCHOP_UNH_15m.png` (2026-09-17, 12:00 through 13:15 ET). Nothing was sent to a broker. Full table in [RESULTS.md](RESULTS.md).

**SPY daily chart check: reference only.** The Oct 6, 2026 thinkorswim daily was compared with the frozen detectors and did not change them. Yahoo's adjusted bar that day has the same high, 781.62, a close of 780.66, RSI 63.7, and a MACD line of 2.91 turning up. The 200 EMA is 722.13. The chop flag does not mark the August-October sideways stretch. The range was narrow and VWAP was crossed, but the 9 and 20 EMAs changed order only three times, so the tangled-EMA leg stays off. The only chop bars in the last year are 2026-02-19 and 2026-02-25. The live horizontal set matches the recent drawn lines at 760, 752, and the 740/735 zone. 768 is about five points under the nearest confirmed high, and 781 is not a pivot yet. The lower lines (700, 690, 683, 675, 655, and the March low) are the same kind of swing, outside the six-level, 120-bar set used as a target. The chart is `reports/setups/readSPY_chop_levels_1d.png`. Nothing was sent to a broker.

**Partial reversal bounce: does not pass.** A daily long tags a prior pivot low with a confirming candle and RSI oversold or turning up from 45, stops 0.25 ATR under that low, and takes the next pivot high, the 20 or 50 EMA, or the short descending trendline. A fixed 1R exit and a farther full-reversal hold are the comparisons. On the Dow point-in-time book, the next-level stock account ended the out-of-sample window at $1,502.90 on 286 trades (win rate 50.7%, average move +0.2%, expectancy $1.76, profit factor 1.13, Sharpe 0.36, max drawdown -46.9%). Fixed 1R ended at $1,062.31 on 301 trades. Holding for the farther reversal ended at $1,724.59 on 204 trades, and the in-sample book ended at $868.65. Random dates with a 1R target ended at $3,502.34. Four SPY shares ended at $3,242.23. Seven, 30, 45, and 60 DTE calls all lost money. The most that finished was 60 DTE at $387.79 on 35 trades, after more than a thousand skips because the contract did not fit the $1,000 account. On the Oct 6, 2026 UNH chart the rule marked the July 11, 2025 retest of 288.45 and did not mark a 330-350 test. Its trendline that day is 356.22, under the close. Setup C's line is 387.67, near the drawn 390-400 line, and this study did not switch to it. The chart is `reports/setups/readBOUNCE_UNH_1d.png`. Nothing was sent to a broker. Full table in [RESULTS.md](RESULTS.md).

**Exit styles: the gate does not change.** The same bounce and A-D entries were scored with a frozen grid: 5%, 10%, and 15% trails, 1.5x, 2x, and 3x ATR trails, a bracket at the next level and at 1.5R, 2R, and 3R, and one hybrid that sells half at the first level and trails the rest at 2x ATR. A row beats the level-target baseline only on the out-of-sample stock book, with a higher expectancy, a profit factor that is not lower, a drawdown no more than five points worse, and at least 20 trades. The bounce label is the 15% trail, ending at $2,608.44 on 118 trades (win rate 55.1%, average capture +1.1%, expectancy $13.63, profit factor 1.43, Sharpe 0.60, max drawdown -32.3%). 109 of those exits were the 15-session time stop and 8 were the trail, so the wide stop rarely ratcheted inside the hold. Hourly B's label is the same 15% trail, expectancy $2.64 on 36 trades, 34 of them time stops. Hourly A and daily C keep the level target. Daily C's level target with the EMA trail off ended at $2,522.01 on 163 trades, which is not the published $746.56 on 207 trades, and it still fails the drawdown and trade-count gates. Daily D's label is the 1.5R bracket, expectancy -$1.46 on 73 trades. The published stock rows still match $886.97, $921.86, $746.56, and $919.45. Calls are bot-managed on the underlying because the options trade page has no trailing stop and no OTO, OCO, or OTOCO. The only call book that finished ahead was the bounce's 10% trail, $1,584.44 on 96 trades, drawdown -70.5%, and options do not pick the label. Equity trails and the MASTER plus take-profit plus stop-loss bracket can be staged on the paper broker. Live trading stays off. Nothing was sent to a broker. Full table in [RESULTS.md](RESULTS.md).

**Options scale-out: does not pass.** A frozen options ladder buys 5 contracts, sells 2 at +15% of the premium, 1 at +20%, and 1 at +30%, and leaves a runner with a limit at +100%. After the +15% fill, the rest stop at the entry premium. Before that, the stop is -20%, -30%, -50%, or the setup stop on the underlying. The same five-contract entries are also closed all-out at +30%, with the percent and ATR trails, and with brackets at the next level and at 1.5R, 2R, and 3R. The sized account is the in-sample median capital that puts the -30% stop at about 2% of equity: $10,081 on the bounce, $23,236 on hourly A, $22,802 on hourly B, $8,992 on daily C, and $8,543 on daily D. Every scale row on that account loses money. On the bounce the -20% ladder closed 39 out-of-sample trades, 35 at the initial stop, 3 runners at break-even, and 1 runner at +100%, expectancy -$253.75, win rate 10.3%, average capture -23.5%, max drawdown -98.2%, ending $185.10. A wide bar fills the stop at the option bid of the adverse extreme, so the loss is larger than the stop percent and the account cannot fund the next five-lot. The paired all-out row was -$254.06. A $1,000 account fits five 0.45-delta contracts on 227 of 1,207 bounce signals and five 0.20-delta contracts on 714 of those signals. The cheaper contracts need a larger underlying move to reach +15% of premium, and they lose money too. Webull can rest each tier as its own option limit sell. OTOCO is not available on options, so the break-even stop is bot-managed. Those orders are not sent, and live trading stays off. Nothing was added to the optional list. Full table in [RESULTS.md](RESULTS.md).

**Chop-hold retest: does not pass.** After a breakout of a 10-session shelf, the frozen chop flag has to mark a pullback that holds the old level, and the entry is the strong close out of that chop, with the stop under the level. On the named list that sequence fired 0 times on the 60-minute book and 0 times on the 15-minute book. The exits were the five-contract scale-out, the trails, and the brackets; with no fill they are not scored. On the Oct 6, 2026 NVDA 20-session hourly chart, Yahoo's high is $243.37 against the annotated $243.37, and the last close is $242.17 against $241.37. The chop flag is on for 0 hourly bars in that window because the 9 and 20 EMAs are tangled on 0 of them. The 15-minute window has 8 chop bars and 0 hold entries. 8 of those chop bars are before 2026-10-02 and 0 are on or after it. The chop dates are 2026-09-29, 2026-10-01. The chop rule was not retuned. Charts are in `reports/setups/readHOLD_NVDA_60m.png` and `reports/setups/readHOLD_NVDA_15m.png`. Nothing was sent to a broker. Live trading stays off. The default book is still dual momentum. Full table in [RESULTS.md](RESULTS.md).

**Chop v2: does not pass.** The tangled-EMA leg is gone. Chop is quiet volume, a narrow range, and either several crosses of VWAP or the box midpoint, or a stacked EMA flag. On SPY from 2026-08-01 through 2026-10-05 the flag is on for 17 of 45 bars and marks the 755-775 stretch. On the NVDA hourly window it is on for 68 of 135 bars, with 0 on or after Friday inside 232.5-235 so the annotated pullback is not marked. The bounce with the 15% trail, the stock above its 200-day average, and chop v2 off is 49 trades, win 51.0%, expectancy $2.64, profit factor 1.16, Sharpe 0.26, max drawdown -26.2%, ending $1,129.54 on the 2023-2026 holdout. The longer swing list keeps 250 daily bars and merges levels within 0.5 ATR. Nothing was added to the optional list. The default book is still dual momentum. Full table in [RESULTS.md](RESULTS.md).

**Forward test, sandbox only.** `chop_breakout_60m` is the frozen 60-minute chop-v2 box breakout (relative volume above 1.5, confirming candle, 15% trail, five-session time stop) on the named list. It is not in the selected book. Live trading refuses it, and `allow_unproven_strategies` does not enable it. OpenAPI equity orders are whole-share quantities, so the sandbox sub-book is $10,000 with at most 3 positions. The same cycle runs a separate $25,000 options sub-book on the pre-registered liquid list (NVDA, AAPL, UNH, MSFT, AMZN, META, GOOGL, JPM, AMD, TSLA, AVGO, COST, V, MA, LLY, XOM, plus SPY and QQQ as references). The share book stays on the named list. Five contracts, 14 DTE, the listed strike nearest the spot (delta about 0.50). A five-lot is skipped only when its debit is above $10,000. Contracts 1-4 keep the -20% premium stop. The runner moves to break-even only after the +15% limit fills, and it targets +100%. Each tier is its own option LIMIT sell. Stops are bot-managed, with no option OCO, and a stop sells only contracts still open. The entry uses a Webull sandbox option quote when the API returns an ask, and the Black-Scholes model when it does not. The journal records which price was used. One cycle, 10:35–15:45 ET: `WEBULL_ENV=sandbox python -m webull_bot forward-test chop_breakout_60m`. `--dry-run` prints both books and does not connect. The journal report is `python -m webull_bot forward-report chop_breakout_60m`.

**VWAP band continuation, sandbox only.** `vwap_band_15m` is the frozen 15-minute 2 SD session-VWAP continuation that cleared the holdout as one at-the-money 0 DTE SPY contract: fill on the next open, 1R target, stop one cent beyond the signal bar, flat at 15:45 ET. It is not in the selected book. Live trading refuses it, and `allow_unproven_strategies` does not enable it. The same host allowlist applies (`*.sandbox.webull.com`). Webull options have no OCO, so each cycle sells the contract with a marketable limit when the underlying hits the stop or the 1R target, and the 15:45 flatten is mandatory. A 5-minute bar can exit before the 15-minute bar that contains both levels. CPI, NFP, and FOMC days are not skipped, because the scored backtest did not skip them. The order is sent on the first cycle after the signal bar closes when the price is still between the stop and the 1R target, and that cycle is within 10 minutes of the signal bar's close. `VWAP_MAX_ENTRY_DELAY_MIN` changes the cap. A later cycle journals the signal as expired, late, and does not enter. A position already open still exits at the stop, the target, or 15:45, and the report marks it as an off-plan late entry. Those levels stay on the modeled next open. A stop or target that traded before the order is not a reason to skip, and exits are measured only on 5-minute bars that start at or after the actual entry. The journal records both prices. One cycle, every 5 minutes from 09:50 through 15:50 ET. Run it a few seconds after each boundary so the bar that just closed is in the file: systemd `Mon..Fri *-*-* 09..15:00/5:30` in `America/New_York`, or minute cron `1,6,11,16,21,26,31,36,41,46,51,56 9-15 * * 1-5`. A clock at only :00:30 and :15:30 would leave the 5-minute stop unmanaged between those marks. `vwap_band_15m_qqq` is the same rule on one at-the-money 0 DTE QQQ contract, with its own journal key and its own report. Both books can run in one cycle: `WEBULL_ENV=sandbox python -m webull_bot forward-test vwap_band_15m vwap_band_15m_qqq`. Each book alone is `python -m webull_bot forward-test vwap_band_15m` or `python -m webull_bot forward-test vwap_band_15m_qqq`. The variables are `WEBULL_APP_KEY`, `WEBULL_APP_SECRET`, and `WEBULL_ENV=sandbox` (`WEBULL_ACCOUNT_ID` optional). Keys are not printed. `--dry-run` prints the signal and the model price and does not connect or write the journal. A stale 15-minute or 5-minute bar is refused. Volatility for the cash mirror is the prior VIX1D close, then the prior VIX close, then the last cached close, then a Webull sandbox option quote. The journal line names the source. A missing print does not skip the trade while one of those sources has a number. A Yahoo download that comes back empty is retried and, if it is still empty, the last cached file is used so the cycle does not crash. That file is still refused when it does not cover the bar that just closed. Reports: `python -m webull_bot forward-report vwap_band_15m` and `python -m webull_bot forward-report vwap_band_15m_qqq`. Both keys live in the configured journal database.

**ATM 14 DTE exit search.** A frozen grid of 1,293 exit cells was scored on ATM options (delta 0.50, 14 DTE) for the chop-v2 hourly box, the bounce, and setups A–D. The cell on each book is the highest training Sharpe among cells with at least 30 training trades. Zero training cells had a positive expectancy. No chosen cell is profitable on the untouched holdout after spreads, fees, and gap fills at the adverse extreme. The exit stays the corrected ladder. The sandbox contract is 14 DTE at the nearest strike. Live trading stays off. Full table in [RESULTS.md](RESULTS.md).

**ATM universe.** The same grid was scored again on a pre-registered liquid list (NVDA, AAPL, UNH, MSFT, AMZN, META, GOOGL, JPM, AMD, TSLA, AVGO, COST, V, MA, LLY, XOM, plus SPY and QQQ). The pass/fail sample is the point-in-time Dow, so today's survivor list cannot decide the gate. No Dow book and no liquid-list pool is profitable out of sample. No symbol with 20 or more holdout trades has a positive expectancy. The options sub-book scans that liquid list on 14 DTE at the nearest strike. The exit stays the corrected ladder. The share book stays on the named list. Full table in [RESULTS.md](RESULTS.md).

**Strong-trend pullback.** A frozen rule buys the nearest listed strike, about 0.50 delta, 14 DTE, after a pullback into the 9/20 EMA, VWAP, or the prior swing that holds that level. The exit is +15% and -30% of premium. Before costs that needs about a 66.7% win rate. On the Dow-gated liquid list the holdout win rates were 35.7% daily (28 trades, ending $99.64), 30.0% on 60-minute bars (10 trades, ending $221.15), and 25.0% on 15-minute bars (4 trades, ending $436.74). None cleared the after-cost break-even rate. The sized one-contract books and the share control also finished below the start. The one holdout row above $1,000 was random daily shares, the baseline. Nothing was sent to a broker, and the sandbox forward test was not changed. Full table in [RESULTS.md](RESULTS.md).

**First-candle opening range.** The range is only the 09:30-09:35 candle. On SPY, holdout 2026-09-10 through 2026-10-06, the $1,000 share book took 12 trades, win rate 33.3% against an after-cost break-even of 69.3%, expectancy -$1.35, ending $983.78. The pattern-day-trader rule blocked 7. The 0 DTE at-the-money book at +15%/-30% took 12 trades, win rate 16.7% against 72.2%, expectancy -$48.67, ending $415.92. Neither win rate clears, and neither book is profitable out of sample. Yahoo's 5-minute file is 38 sessions, from 2026-08-13 through 2026-10-06, so the sample is short. A 7 DTE sensitivity finished at $1,010.33 on 13 trades and was not promoted. Charts are in `reports/setups/orb5_spy_2026-10-06.png` and the three sessions before it. Nothing was sent to a broker, and the sandbox forward test was not changed. Full table in [RESULTS.md](RESULTS.md).

**Monday, Wednesday, and Friday opening range.** This is the pre-registered opening-range default. The range is only the 09:30-09:35 candle. The book trades those three weekdays, skips CPI, the jobs report, and FOMC decision days, and buys the at-the-money 0 DTE call or put on the first 1-minute break. There is no stop. A call takes profit at +100% of the option price and a put at +50%. Otherwise it is sold at the 15:30 ET bid, which can be near zero. An earlier score of this same study used a -50% stop. That stop is not this rule, and those dollars are not reused. On Dukascopy bid 1-minute bars from 2017-02-17 through 2026-10-06, 1,431 sessions, a $1,000 cash account risking $100 took 43 trades, win rate 39.5% against an after-cost break-even of 57.8%. Calls hit +100% on 31.6% of 19. Puts hit +50% on 37.5% of 24. 65.1% were still open at 15:30, average bid $0.08. Expectancy was -$23.15, ending equity $4.65, max drawdown -99.6%, longest losing streak 10. 1,095 signals were skipped because one contract cost more than the remaining budget. The pattern-day-trader count blocked none. The option price is a model, which is the main uncertainty. The second half, replayed from a fresh $1,000, finished at $3,659.51 and was not promoted. Charts are in `reports/setups/orb_mwf_spy_2026-10-06.png` and the sessions around it. Nothing was sent to a broker, and the sandbox forward test was not changed. Full table in [RESULTS.md](RESULTS.md).

**Account-sized books, $1,000 and $5,000.** Three rules were frozen before scoring, on Yahoo adjusted daily bars from 2005 where the fund existed, through 2026-10-06. Costs are the Webull stock schedule already in this repo. Cash earns zero. A cash account sells at the next open and buys the session after that. Taxes are ignored; a monthly book realizes short-term gains while SPY buy-and-hold defers them. The list is the ETFs that still exist, not a point-in-time stock scan. Conservative holds an equal slice of SPY, EFA, IEF, and GLD when the month-end close is strictly above the 10-month average, else that slice is cash. On a fresh $1,000 from 2017-01-01 it finished at $1,925 (CAGR 6.9%, max drawdown -10.5%, Sharpe 0.96, positive months 65.3%). SPY on the same window finished at $4,028 (CAGR 15.3%, drawdown -33.7%, Sharpe 0.88) and QQQ at $6,791. It cleared the frozen risk-adjusted test against SPY and did not beat either fund on dollars. The same four funds held all the time finished at $2,568, Sharpe 1.00, drawdown -19.8%. The filter's addition is the smaller drawdown. Moderate holds the one of SPY, QQQ, IWM, EFA, EEM, TLT, and GLD with the best 12-1 return when its 12-month return is strictly above BIL, else cash, with no trail. It finished at $2,192 (CAGR 8.4%, drawdown -37.6%, Sharpe 0.49). A shuffle of its monthly choices finished ahead of the real timing. The bot already runs dual momentum at 0.75% risk, so a $1,000 fractional account ended at $1,046 and whole shares at $1,002. That is not this fully invested book. High risk holds TQQQ above its 10-month average, else cash. TQQQ was not listed in 2008. It finished the holdout at $9,255 (CAGR 25.6%, drawdown -69.9%, Sharpe 0.70), ahead of SPY and QQQ on raw dollars and behind raw TQQQ at $32,854 (drawdown -81.7%, Sharpe 0.87). One shuffle of its invested months finished far ahead of the filter. If a decline near 30% is acceptable, SPY or QQQ made more than the conservative and moderate books, and QQQ made more than SPY. If a smaller crash and slow growth are acceptable, the conservative sleeve is the one of these three I would fund. It is not in the bot. I would not fund the moderate book or the TQQQ filter for this account. Nothing was added to the optional or selected lists. Live trading stays off. The sandbox forward test was not changed. The chart is `reports/account_winners_equity.png`. Full table in [RESULTS.md](RESULTS.md).

**Second small-account search.** Same holdout, costs, and cash-account lag. Rules were frozen before the score. Short-term mean reversion on SPY, QQQ, IWM, DIA, and the sector SPDRs (RSI(2) below 10, IBS below 0.2, or three down days, each above the 200-day average) finished near cash, about $1,105 to $1,127 from $1,000. Holding that RSI sleeve only when it is on, and QQQ otherwise, finished at $2,148 against QQQ at $6,791. A daily 200-day filter on TQQQ, with a 3 percent band or a 20 percent vol target, cut the published monthly filter's -69.9% holdout drawdown to -50.5% on the vol target and did not remove it. 2020 still finished up about 80% to 90% because the rebound was in the same year, and 2022 was about -35% to -44%. The vol target finished the holdout at $13,192 (CAGR 30.3%, Sharpe 0.83). It beat SPY and QQQ on dollars and failed the frozen risk test. The 3 percent band made more ($15,806) with a worse drawdown (-62.1%) and was not the pick. A weekly 15% vol target on QQQ, held only above the 200-day average and never levered, finished at $3,358 (CAGR 13.2%, drawdown -17.0%, Sharpe 0.99). It cleared the SPY risk test and made less than SPY ($4,028) and QQQ ($6,791). Its Sharpe is 0.99 against QQQ's 0.98, which is not a win I would fund. Sector rotation of the top 3 SPDRs finished at $3,756 and missed the risk test. Point-in-time Dow momentum, used because a free point-in-time S&P 100 file was not available, finished at $1,621 and lost to a shuffle that finished at $5,420. A current-member Dow list finished at $3,221, which is the survivorship gap, and that list was not a finalist. Turn-of-month and pre-holiday holds lost money relative to staying invested. Post-earnings drift was skipped: the free Yahoo earnings calendar for AAPL starts in 2014. A Black-Scholes wheel on Ford, one contract, finished at $5,260 from $5,000. QQQM at about $313 does not fit 100 shares in $5,000. Yahoo returned no SPLG prices. Across this search and the earlier three books, the conservative slot is still the 10-month sleeve at $1,925, the moderate slot is the weekly QQQ vol filter at $3,358, and the high-risk slot is the TQQQ vol target at $13,192. No book beat QQQ on both raw return and risk-adjusted return. None of them is in the bot. A sandbox run would be a new forward command, not an edit to the chop-breakout test. Live trading stays off. The chart is `reports/account_hunt_equity.png`. Full table in [RESULTS.md](RESULTS.md).

**Session VWAP bands.** 15-minute SPY and QQQ, backtest only. Rules were frozen before the score. The outer band is 2 standard deviations; 2.5 and 3 were scored and not promoted. Continuation buys or sells the next open after a close outside that band, with a 1R target. A reversal waits for a close back inside, then trades toward VWAP. Both exit by 15:45 ET. SPY is Dukascopy 1-minute bids from 2017-02-16 through 2026-10-06 (2,416 sessions, two empty files). Dukascopy publishes QQQ, but that download was still short, so the QQQ rows are about 60 Yahoo days and are not the gate. Share books lost money. The long-only continuation finished the holdout at $393 from $1,000 (812 trades, profit factor 0.39, max drawdown -60.8%). The long-only reversal finished at $297 (908 trades, profit factor 0.11, max drawdown -70.3%). Seven-day options lost most of the stake. The one book that cleared the gate (profit factor at least 1.10, Sharpe at least 0.40, drawdown no worse than -30%, at least 300 trades) is the 2 SD continuation held as one at-the-money 0 DTE contract: 2,355 holdout trades, 50.0% wins against a 39.3% break-even, profit factor 1.55, Sharpe 2.66, max drawdown -16.2%, ending $32,844 from $1,000 and $36,844 from $5,000. Size does not scale, so the extra $4,000 is idle cash. The same $1,000 account in training died at $1 after 255 trades. A $5,000 training account finished at $7,554 with a profit factor of 1.07, under the 1.10 line. Seed-17 random 0 DTE entries finished at $6. The holdout edge is in both the VIX years (profit factor 1.60) and the VIX1D years (1.53). On model dollars it beats Yahoo adjusted SPY ($1,737) and QQQ ($1,945), and the price is Black-Scholes, not a chain. Full-sample 12-month windows on the $5,000 continuation had a median of $6,486 against $5,714 for SPY bids and $6,176 for adjusted QQQ. No neighbor was promoted. Fractional fills would not be whole-share orders. Nothing was added to the live list. The same frozen 2 SD continuation, one at-the-money 0 DTE SPY contract, is the sandbox forward test `vwap_band_15m`. The default is still dual momentum.

**9/20 EMA rejection.** 5-minute SPY and QQQ, backtest only. Rules were frozen before the score. The gate is the confluence on the chart that was pointed at: the 9 EMA against the 20 EMA, both sloping the same way for 3 bars, price on that side, a bar that tags the 9 EMA within 0.10 ATR and closes back, and session VWAP within 0.10 ATR of the 9 EMA. The stop is one cent past the rejection bar. The target is the prior 5-bar swing. Trades are flat by 15:45. A chop guard skips quiet volume (under 0.85 of the prior 20 bars), a tight EMA spread, or a flat 9 EMA slope. SPY is Dukascopy 1-minute bids from 2017-02-16 through 2026-10-06, resampled to 5 minutes (2,416 sessions). The QQQ cache was still short, so those rows are about 60 Yahoo days and are not the gate. Neither default book cleared the gate. The long-only share book finished the holdout at $879 from $1,000 (101 trades, profit factor 0.11, Sharpe -3.30, max drawdown -12.1%) and $4,396 from $5,000. The 0 DTE book, which can buy puts on the short setup, finished at $75 from $1,000 (242 trades, profit factor 0.65, Sharpe -0.43, max drawdown -95.8%) and $3,725 from $5,000 (283 trades, profit factor 0.64, Sharpe -1.06, max drawdown -26.1%). Both are under 300 trades. The training accounts also lost money ($953 and $823 from $1,000). Seed-17 random entries lost as well, and the 0 DTE signals finished behind that draw ($722, profit factor 0.89). Same-window SPY bids finished at $1,635, Yahoo adjusted SPY at $1,737, and Yahoo adjusted QQQ at $1,945. No variant cleared the numeric gate. The 20 EMA stop on 0 DTE was the closest, at a 1.05 profit factor, and it still missed the trade count, the Sharpe, and the drawdown. On 2026-10-07 at 10:20 ET the Yahoo 5-minute bar has the 9 EMA at 775.05 and VWAP at 775.04. The frozen rule does not mark it: relative volume is 0.43, and the high is 0.11 ATR from the 9 EMA. Widening the tag would still leave the quiet bar out. Nothing was added to the live list. A reversal variant sits beside that gate and does not replace it. From a bearish stack (9 EMA under the 20 EMA, prior close under VWAP), a green bar that closes above the 9 EMA, the 20 EMA, and VWAP, confirmed by the next green bar, is bought on the open after that confirmation. The mirror buys the put. The stop is one cent beyond the breakout bar. Swing, 1R, 2R, and a close back across the 9 EMA are the same exits. Share books lost money. The swing 0 DTE book finished the holdout at $1,783 from $1,000 (1,084 trades, profit factor 1.04, Sharpe 0.49, drawdown -45.6%) and the training account finished at $872. The 1R 0 DTE book cleared the holdout arithmetic, $6,345, profit factor 1.22, Sharpe 1.33, drawdown -26.0%, 1,042 trades, and was not promoted. Its training profit factor was 1.02. The 9 EMA-cross 0 DTE holdout finished at $10,757 and wiped the training account. On Yahoo 5-minute SPY through 12:10 ET on 2026-10-07 the rule marks nothing. Full table in [RESULTS.md](RESULTS.md).

**Candlestick patterns.** Thirty-nine shapes, pure Python, no TA-Lib. The definitions were frozen before the score. SPY 5-minute and 15-minute bars are Dukascopy bids from 2017-02-16 through 2026-10-06, 2,416 sessions. Daily bars are Yahoo for SPY, QQQ, and the liquid list. A cell is an edge only with at least 300 holdout trades, a positive mean in both windows, a mean and a hit rate above a seed-17 random draw, and a false-discovery q at or under 0.10. No cell cleared that. On 5-minute SPY, no directional cell with 300 trades had a positive after-cost mean. The closest large cell is a hammer on the pooled daily basket, 6 bars, context off: 450 trades, mean 58 bp against a random 53 bp, t 2.71 against a 2.82 bar, q 0.70. That basket is a 2026 snapshot. Used as optional filters, the shapes did not help the published books. The 2 SD continuation 0 DTE book fell from $32,844 to $4,488 with the filter off (121 trades) and to $1,630 with the location filter on (45 trades). Share filters that lost less than the published share losses still finished under the stake and missed the gate. Nothing was added to the live list. The sandbox forward test was not changed. Full table in [RESULTS.md](RESULTS.md).

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
