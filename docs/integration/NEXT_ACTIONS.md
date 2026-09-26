# Next actions

The queue is ordered by downside and decision value, not by feature count.

## P0 — close ICARUS-RISK-001

Owner surface: ICARUS bridge.

- Add RED tests for authenticated unknown-event payload and direct `Alert` bypass.
- Confirm old behavior would reach the fill path without the fix.
- Implement parser + dispatcher fail-closed checks.
- Run focused bridge/execution tests and the full applicable suite.
- Record exact test commands/results and source revision.
- Do not merge until regression evidence is fresh.

## P1 — AION durable-state integrity design

Owner surface: AION.

- Select the cryptographic integrity model for gaps/predictions/settlements.
- Preserve event-chain/replay compatibility or explicitly version migration.
- Add tamper-detection tests for every claimed protected durable family.
- Keep the claim wording scoped until those tests pass.

## P1 — trainer calibration protocol approval

Owner surface: ICARUS trainer spec.

- Decide an untouched final evaluation protocol.
- Version the artifact/schema if split semantics change.
- Implement only after approval; no invented trainer slots/features.
- Track calibration/model-selection attempts in the research ledger.

## P1 — NEXUS corpus reconciliation/reseal

Owner surface: NEXUS source + evidence lab.

- Bring canonical NEXUS source into an auditable repository or immutable package reference.
- Emit the unified ten-ZIP manifest.
- Reconcile 659 members / 13,788,256 rows and distinct hashes.
- Regenerate and independently verify the release seal.

## P2 — sibling connection contracts

For AION, DAEDALUS, ATHENA, ARGUS, NEXUS and later ORACLE:
- commit one versioned admission descriptor per subsystem;
- include exact source revision/package digest;
- include schema/time/provenance/replay/failure/uncertainty contracts;
- add compatibility tests at the receiving ICARUS boundary;
- never infer responsibility from the subsystem name.

## ORACLE blocker

Do not assign ORACLE integration work until a canonical repository/package establishes its responsibility and interfaces. Prior non-repository handoff descriptions are provisional only.
