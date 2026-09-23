# Candidate qualification source (CA, 2026-09-22)

The operator's acceptance rules already exist in the separate `Icarus-engine`
repository. Source commit: `6e0da3524f20c859129fdd2e122a96be45d55cb4`;
source files: `tools/goal.py` and `tools/duration.py`. These are the rules to
recover and verify before publishing any qualified candidate. This note is a
locator and review aid; the source code at that commit is authoritative.

## Held-out trade requirements

- Win rate >= 82%, at least 120 trades, 0.5 to 4 trades/day, positive
  expectancy. The tune tape must also reach 82% and positive expectancy.
- Mean hold >= 4 bars, with the duration envelope in `tools/duration.py`:
  ceiling 240 minutes; fast-chart target 120 minutes at <= 5m; slow-chart
  target 240 minutes at >= 20m; floor 20 minutes and 6 bars; hold p90 <=
  1.5 times the bar ceiling; same-bar exits <= 5%.
- Winning hold / losing hold >= 1.2; hold drift <= 0.35; positive R/bar;
  overnight positions <= 5% and positive overnight profit share <= 25%.
- Single-contract/single-target trades may have no runner. Otherwise require
  >= 30 runner legs with runner win rate >= 90%; a breakeven runner fails.
  TP1 and TP2 fill rates must each be >= 8%; their held-out gap <= 6
  percentage points, tune gap <= 6 points and gap drift <= 5 points.
- Consistency >= 0.30; positive 25-trade blocks >= 60%; top decile profit
  share <= 65%; losing streak versus random <= 2; longest win/loss streak
  ratio >= 2; mean run ratio >= 1.3.
- Rank only after qualification using the source's uncapped monotone score.

## Review corrections before applying

`Goal.clears()` currently skips tune checks when `tune=None` despite
`require_tune_too=True`. Some missing fields fall back to zero and can pass
upper-bound checks. A production evaluator must require both tapes and an
explicit complete field set, or return `insufficient_evidence`. Do not turn
missing fields into zero. The source `shortfall()` and `clears()` need a
contract test for consistent explanations.

The rules describe strategy *trades*, including actual wall-clock entry and
exit times and realized legs. Next-bar sign accuracy, same-time stock/futures
correlation, a solitary profitable block, and unpriced bar forecasts cannot
qualify a candidate. For Renko/range/tick charts, bar counts cannot be
converted to minutes with a guessed clock interval; use recorded timestamps.

The separate repo's `HANDOFF.md` warns that its 2025-10-01 holdout has been
repeatedly inspected. Reusing that tape as an untouched selection holdout
would be false. Freeze a genuinely unseen final period or use a predeclared
forward paper window, and report search multiplicity and contract rolls.
