# Champion Paper Activation Handoff

## Goal

Keep best-observed Tactical Autopilot champions scoped by asset and current regime, and give each champion an explicit route into Icarus's existing evidence-gated research and paper activation workflow.

## Flow

`shadow champion -> fresh bounded research study -> specialist review -> qualified proposal -> versioned paper overlay`

For live paper monitoring, the companion [Paper Performance Guard](2026-10-14-paper-performance-guard.md) observes settled lot outcomes by asset and entry regime. A pressure pause can only begin collecting a fresh performance cohort after the normal reviewed activation path installs a replacement.

The handoff starts a new study on frozen, cached bars with one exact champion input configuration. It records the champion ID and both champion-time and study-time regime snapshots on the study and its resulting proposal. That study still needs new non-overlapping holdout data, minimum sample and after-cost hurdles, current evidence, independent specialist recommendations, proposal creation, and the existing locked paper runtime activation boundary.

## Boundaries

- No champion is activated directly and no live/Pine/broker configuration is changed.
- Existing active positions retain their exits; activation remains subject to current runtime safeguards.
- A champion whose chart/session context differs from the current paper runtime is blocked until research supports paired context overrides.
- If the current cached data cannot form a fresh holdout or the input snapshot has changed, the study is blocked.
- Regime-scoped champion selection prevents a candidate found in one regime from becoming the search seed for another. Each underlying replay still evaluates its configured historical windows; regime tags are scope and provenance, not proof that every trade in that replay belonged to one regime.

## UI and API

Add a per-champion action in Tactical Autopilot and an authenticated research endpoint. The action creates a normal ResearchWorkspace study with a single fixed configuration. The resulting study continues through the already existing research analysis, proposal, export, and activation operations.

## Checks

Test exact input mapping, stale/mismatched champions, unsupported context, fresh-window generation and persisted champion provenance. Verify the activation boundary still rejects direct or unreviewed artifacts. Run focused tests and the full Python suite.
