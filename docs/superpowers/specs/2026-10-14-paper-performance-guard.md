# Paper Performance Guard

## Purpose

Add continuous, per-asset/per-regime scorecards for settled paper outcomes and provide a strict response when recent accuracy deteriorates.

## Measurement

- Read durable journal rows marked as live paper fills; warm-up replay rows are excluded.
- Combine every partial exit for a lot and count that lot once after all contracts are closed.
- Measure success as net positive realized profit after the emulator's modeled costs.
- Keep the most recent 30 fully closed lots per asset and entry regime. Require 12 observations before assigning a health state.
- Track average hold duration in chart bars and seconds, net P&L and profit factor alongside win rate.
- Capture regime from the last closed strategy state when the entry fills. Older rows without this provenance stay labeled unknown.

## Response

- Below 85%: `WATCH`, visible in the per-asset dashboard.
- Below 75% with at least 12 settled lots: `PRESSURE`; pause that asset's new entries and cancel its pending entry intents. Existing positions keep their protective exits.
- Resuming while in pressure is blocked. The supported recovery path is a freshly qualified, reviewed paper activation. Activation checkpoints the guard so outcomes from the prior configuration do not contaminate the new configuration's sample.
- The guard never edits inputs, authorizes brokerage execution, or claims a win-rate guarantee. A separate qualification study and the existing activation boundary remain required.

## Limits

Regime labels come from the strategy's entry-fill snapshot, but the rate estimate is still a small rolling sample and should be read with profit factor, net P&L, and duration. A 12-lot minimum makes the guard responsive; it does not provide strong statistical confidence. The configured 83% redeployment objective remains a qualification goal, not an automatic guarantee.
