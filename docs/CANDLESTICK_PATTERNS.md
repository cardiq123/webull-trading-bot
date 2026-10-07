# Candlestick patterns

These are the shapes the backtest measures. The thresholds were written down before any forward return. A later result does not change a definition.

The size of a body or a wick is compared with the Wilder ATR(14) of the bar that completes the pattern. A doji is a body of at most 0.10 ATR on a bar whose high-low range is at least 0.20 ATR, so a print with no range is not a doji. A hammer or inverted hammer has a body above 0.10 ATR and at most 0.40 ATR, so it does not also count as a doji. Its long wick is at least twice the body and at least 0.30 ATR, and the other wick is at most half the body.

The hammer column is only that lower-shadow shape. Hanging man is the same shape after the five closes before the bar have risen by at least 0.50 ATR. Inverted hammer and shooting star split the same way on the upper wick. Without the location filter, an uptrend bar with a long lower wick is both a hammer (a long) and a hanging man (a short). That overlap is the point of scoring the filter. A dragonfly doji is also a doji. A long-legged doji is a doji whose two wicks are each at least 0.30 ATR.

Trend is measured on the closes before the pattern, not on the pattern bars. For a pattern of S bars ending at bar i, the recent close is bar i−S and the earlier close is five bars before that. Down means the earlier close is at least 0.50 ATR above the recent close. Up is the mirror.

Location is 0.25 ATR. The bar is at a level when its range covers the level or the close is within 0.25 ATR of it. The lower band uses the 1 standard-deviation session band: the low is at or through that band plus 0.25 ATR, and the close is not more than 0.25 ATR under it. Swings are a two-bar fractal, confirmed two bars later, then carried forward. A bullish pattern's location is VWAP, the 9 EMA, the 20 EMA, the lower band, or a swing low. A bearish pattern uses VWAP, either EMA, the upper band, or a swing high.

On a daily bar every timestamp is midnight. Those bars are not run through the regular-hours session, because that filter would drop them. Session VWAP and both bands stay false. Daily location is the two EMAs and the swings.

Multi-bar patterns use consecutive rows in the frame, including the jump from one session's last bar to the next session's open. An opening gap can complete a star, a kicker, piercing line, dark cloud cover, or a tasuki gap.

Neutral patterns are measured both directions and cannot receive the edge label. They are not confirmation filters. Reversal patterns, including three white soldiers and three black crows, are the optional filter for the VWAP reversal and the 9/20 EMA rejection. Continuation patterns (the two marubozu, rising and falling three methods, and the two tasuki gaps) are the optional filter for the VWAP extension. The filter is research only. It is not in the live list.

Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

## Patterns

### Doji

**Id:** `doji`  
**Group:** single  
**Bias:** Neutral  
**Family:** indecision

**How it looks.** The open and the close are almost the same price, and the bar still has a real range.

**What it means.** Buyers and sellers traded to a standstill. The bar does not say who won.

**Where it matters.** Anywhere the bar prints. With the context filter on, it only counts when the bar is at VWAP, either EMA, a 1 SD band, or a confirmed swing. It has no trade direction, so it is not a confirmation filter and it cannot be labeled an edge.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Long-legged doji

**Id:** `long_legged_doji`  
**Group:** single  
**Bias:** Neutral  
**Family:** indecision

**How it looks.** A doji with a long wick above the open and a long wick below it.

**What it means.** Price traveled a long way in both directions and closed back where it started. Neither side kept control.

**Where it matters.** Anywhere the bar prints. With the context filter on, it only counts when the bar is at VWAP, either EMA, a 1 SD band, or a confirmed swing. It has no trade direction, so it is not a confirmation filter and it cannot be labeled an edge.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Dragonfly doji

**Id:** `dragonfly_doji`  
**Group:** single  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** The open, the high, and the close sit together, and a long lower wick hangs underneath.

**What it means.** Sellers pushed the bar down and buyers brought it all the way back. After a decline that is a rejection of lower prices.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Gravestone doji

**Id:** `gravestone_doji`  
**Group:** single  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** The open, the low, and the close sit together, and a long upper wick stands above them.

**What it means.** Buyers pushed the bar up and sellers brought it all the way back. After a rally that is a rejection of higher prices.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Hammer

**Id:** `hammer`  
**Group:** single  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A small real body at the top of the bar and a lower wick at least twice that body. The upper wick is short. The column is this shape only. It does not require a downtrend.

**What it means.** Sellers drove price down during the bar and buyers closed it back near the high. After a decline, the story is that the decline was refused.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Hanging man

**Id:** `hanging_man`  
**Group:** single  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** The same lower-shadow shape as a hammer, and the five closes before the bar are an uptrend.

**What it means.** The bar looks like a hammer, but it prints after a rally. Buyers are no longer getting an easy close at the high of a rising market. The long lower wick is supply showing up overhead.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Inverted hammer

**Id:** `inverted_hammer`  
**Group:** single  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A small real body at the bottom of the bar and an upper wick at least twice that body. The lower wick is short. The column is this shape only.

**What it means.** Buyers tried to lift the bar and the close gave a lot of it back. After a decline, the long upper wick is the first sign that buyers can reach higher prices.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Shooting star

**Id:** `shooting_star`  
**Group:** single  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** The same upper-shadow shape as an inverted hammer, and the five closes before the bar are an uptrend.

**What it means.** After a rally, buyers ran the bar up and sellers closed it back near the low. The long upper wick is a rejection of the new high.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Spinning top

**Id:** `spinning_top`  
**Group:** single  
**Bias:** Neutral  
**Family:** indecision

**How it looks.** A small real body, larger than a doji, with a wick on each side at least as long as the body.

**What it means.** Both sides pushed and neither one finished the bar in control. It is pause, not a direction.

**Where it matters.** Anywhere the bar prints. With the context filter on, it only counts when the bar is at VWAP, either EMA, a 1 SD band, or a confirmed swing. It has no trade direction, so it is not a confirmation filter and it cannot be labeled an edge.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bullish marubozu

**Id:** `marubozu_bull`  
**Group:** continuation  
**Bias:** Bullish  
**Family:** continuation

**How it looks.** A long bullish body with almost no wick on either end.

**What it means.** Buyers paid the low and kept paying through the close. In an uptrend it says the push is still one-sided.

**Where it matters.** During an uptrend. The location flag uses the same support set as a bullish reversal (VWAP, either EMA, the lower band, or a swing low). It does not switch over to the upper band.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bearish marubozu

**Id:** `marubozu_bear`  
**Group:** continuation  
**Bias:** Bearish  
**Family:** continuation

**How it looks.** A long bearish body with almost no wick on either end.

**What it means.** Sellers hit the open and kept hitting through the close. In a downtrend it says the push is still one-sided.

**Where it matters.** During a downtrend. The location flag uses the same resistance set as a bearish reversal (VWAP, either EMA, the upper band, or a swing high). It does not switch over to the lower band.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bullish engulfing

**Id:** `bullish_engulfing`  
**Group:** two-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A bearish body, then a larger bullish body that opens below the prior close and closes above the prior open.

**What it means.** The second bar's buyers did not just stop the decline. They traded through the entire prior body.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bearish engulfing

**Id:** `bearish_engulfing`  
**Group:** two-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** A bullish body, then a larger bearish body that opens above the prior close and closes below the prior open.

**What it means.** The second bar's sellers traded through the entire prior body. The rally's last up bar was given back.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bullish harami

**Id:** `bullish_harami`  
**Group:** two-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A long bearish body, then a smaller bullish body that sits strictly inside it.

**What it means.** The decline's wide bar is followed by a bar that cannot leave that range. Selling stalled, and the close turned up inside the prior body.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bearish harami

**Id:** `bearish_harami`  
**Group:** two-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** A long bullish body, then a smaller bearish body that sits strictly inside it.

**What it means.** The rally's wide bar is followed by a bar that cannot leave that range. Buying stalled, and the close turned down inside the prior body.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bullish harami cross

**Id:** `bullish_harami_cross`  
**Group:** two-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A long bearish body with a doji sitting strictly inside it.

**What it means.** After a strong down bar, the next bar cannot choose a direction at all. The cross is the stall. It is a harami whose second body is a doji.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bearish harami cross

**Id:** `bearish_harami_cross`  
**Group:** two-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** A long bullish body with a doji sitting strictly inside it.

**What it means.** After a strong up bar, the next bar cannot choose a direction. The rally paused inside its own range.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Piercing line

**Id:** `piercing_line`  
**Group:** two-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A long bearish bar, then a bullish bar that opens below the prior low and closes above the prior midpoint without taking out the prior open.

**What it means.** The second bar gaps down, which looks like more selling, then buyers reclaim more than half of the prior body. They do not erase the whole bar.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Dark cloud cover

**Id:** `dark_cloud_cover`  
**Group:** two-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** A long bullish bar, then a bearish bar that opens above the prior high and closes below the prior midpoint without taking out the prior open.

**What it means.** The second bar gaps up, which looks like more buying, then sellers take back more than half of the prior body.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Tweezer bottom

**Id:** `tweezer_bottom`  
**Group:** two-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** Two bars share a low, within a tenth of an ATR. The first is bearish. The second is bullish and its lower wick is at least as long as its body.

**What it means.** Both bars found the same floor. The second one bounced off it. The matching lows are the test.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Tweezer top

**Id:** `tweezer_top`  
**Group:** two-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** Two bars share a high, within a tenth of an ATR. The first is bullish. The second is bearish and its upper wick is at least as long as its body.

**What it means.** Both bars found the same ceiling. The second one sold off it. The matching highs are the test.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bullish kicker

**Id:** `bullish_kicker`  
**Group:** two-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A long bearish bar, then a long bullish bar whose entire range gaps above the prior high.

**What it means.** The market did not overlap the prior bar at all. Buyers repriced the instrument above the whole of the last down bar.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bearish kicker

**Id:** `bearish_kicker`  
**Group:** two-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** A long bullish bar, then a long bearish bar whose entire range gaps below the prior low.

**What it means.** Sellers repriced the instrument under the whole of the last up bar. The two ranges do not touch.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Morning star

**Id:** `morning_star`  
**Group:** three-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A long bearish bar, a small bar that gaps below that close, and a long bullish bar that closes above the first bar's midpoint. The second gap is not required.

**What it means.** Selling, then a stall under the decline, then buyers take back more than half of the first bar. The small middle bar is the turn.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Evening star

**Id:** `evening_star`  
**Group:** three-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** A long bullish bar, a small bar that gaps above that close, and a long bearish bar that closes below the first bar's midpoint. The second gap is not required.

**What it means.** Buying, then a stall above the rally, then sellers take back more than half of the first bar.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Morning doji star

**Id:** `morning_doji_star`  
**Group:** three-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A morning star whose middle bar is a doji: the middle body is at most a tenth of an ATR.

**What it means.** The stall in the middle is complete indecision, not a small trend bar. Buyers still have to close the third bar back through the first midpoint.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Evening doji star

**Id:** `evening_doji_star`  
**Group:** three-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** An evening star whose middle bar is a doji.

**What it means.** The stall above the rally is a doji. Sellers still have to close the third bar back through the first midpoint.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Three white soldiers

**Id:** `three_white_soldiers`  
**Group:** three-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** Three bullish bars, each with a real body, each close higher, each open inside the prior body, and no long upper wick.

**What it means.** Buyers closed higher three times in a row and did not leave a tall wick of rejection. It is scored as a reversal of a prior decline, which is the three-bar group it belongs to.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Three black crows

**Id:** `three_black_crows`  
**Group:** three-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** Three bearish bars, each with a real body, each close lower, each open inside the prior body, and no long lower wick.

**What it means.** Sellers closed lower three times and did not leave a tall wick of demand. It is scored as a reversal of a prior rally.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Three inside up

**Id:** `three_inside_up`  
**Group:** three-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A bullish harami, then a third bullish bar that closes above the high of the first bar.

**What it means.** The harami said selling stalled. The third bar is the buyers leaving the first bar's range.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Three inside down

**Id:** `three_inside_down`  
**Group:** three-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** A bearish harami, then a third bearish bar that closes below the low of the first bar.

**What it means.** The harami said buying stalled. The third bar is the sellers leaving the first bar's range.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Three outside up

**Id:** `three_outside_up`  
**Group:** three-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A bullish engulfing pattern, then a third bullish bar that closes above the engulfing bar's close.

**What it means.** The engulfing bar took the prior body. The next bar's buyers pushed the close still higher.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Three outside down

**Id:** `three_outside_down`  
**Group:** three-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** A bearish engulfing pattern, then a third bearish bar that closes below the engulfing bar's close.

**What it means.** The engulfing bar took the prior body. The next bar's sellers pushed the close still lower.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bullish abandoned baby

**Id:** `abandoned_baby_bull`  
**Group:** three-bar  
**Bias:** Bullish  
**Family:** reversal

**How it looks.** A long bearish bar, a doji that gaps below that bar's low, and a bullish bar that gaps above the doji and closes above the first midpoint.

**What it means.** The middle bar is left alone, with a gap on both sides. Price abandoned the low and the next bar did not come back to it.

**Where it matters.** After a decline, and at support: session VWAP, the 9 or 20 EMA, the lower 1 SD VWAP band, or a confirmed swing low. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Bearish abandoned baby

**Id:** `abandoned_baby_bear`  
**Group:** three-bar  
**Bias:** Bearish  
**Family:** reversal

**How it looks.** A long bullish bar, a doji that gaps above that bar's high, and a bearish bar that gaps below the doji and closes below the first midpoint.

**What it means.** The middle bar is left alone above the rally. The next bar gaps away from it and does not come back.

**Where it matters.** After a rally, and at resistance: session VWAP, the 9 or 20 EMA, the upper 1 SD VWAP band, or a confirmed swing high. A daily bar has no session VWAP, so the location there is the 9 EMA, the 20 EMA, or a swing.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Rising three methods

**Id:** `rising_three_methods`  
**Group:** continuation  
**Bias:** Bullish  
**Family:** continuation

**How it looks.** A long bullish bar, three small bars that stay inside its high and low (at least two of them bearish), and a bullish bar that closes above the first close.

**What it means.** The trend bar pauses while small bars drift inside it, then the next bullish bar resumes above the first close. The pause did not break the first bar's range.

**Where it matters.** During an uptrend. The location flag uses the same support set as a bullish reversal (VWAP, either EMA, the lower band, or a swing low). It does not switch over to the upper band.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Falling three methods

**Id:** `falling_three_methods`  
**Group:** continuation  
**Bias:** Bearish  
**Family:** continuation

**How it looks.** A long bearish bar, three small bars that stay inside its high and low (at least two of them bullish), and a bearish bar that closes below the first close.

**What it means.** The decline pauses inside its own bar, then selling resumes below the first close.

**Where it matters.** During a downtrend. The location flag uses the same resistance set as a bearish reversal (VWAP, either EMA, the upper band, or a swing high). It does not switch over to the lower band.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Upside tasuki gap

**Id:** `upside_tasuki_gap`  
**Group:** continuation  
**Bias:** Bullish  
**Family:** continuation

**How it looks.** Two bullish bars with a gap between them, then a bearish bar that opens inside the second body and closes back into the gap without filling it.

**What it means.** The pullback sells into the gap and stops short of closing it. The unfilled gap is the continuation.

**Where it matters.** During an uptrend. The location flag uses the same support set as a bullish reversal (VWAP, either EMA, the lower band, or a swing low). It does not switch over to the upper band.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

### Downside tasuki gap

**Id:** `downside_tasuki_gap`  
**Group:** continuation  
**Bias:** Bearish  
**Family:** continuation

**How it looks.** Two bearish bars with a gap between them, then a bullish bar that opens inside the second body and closes back into the gap without filling it.

**What it means.** The bounce buys into the gap and stops short of closing it. The unfilled gap is the continuation.

**Where it matters.** During a downtrend. The location flag uses the same resistance set as a bearish reversal (VWAP, either EMA, the upper band, or a swing high). It does not switch over to the lower band.

**Confirmation.** Enter at the next bar's open, in the pattern's direction. The old rule that the next bar must close in that direction is the one-bar forward result, not a second filter in front of the fill.

The drawing of each shape is `reports/candlestick_patterns.png`. The candles there are a schematic, not a fit to a backtest.
