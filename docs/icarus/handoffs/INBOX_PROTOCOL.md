# ICARUS Loop Handoff Inbox Protocol

Use this protocol while the owner sends the remaining ICARUS/AEGIS/DAEDALUS/NEXUS/HELIOS
loop outputs into the repository.

## Destination
Each source loop gets one immutable first-pass handoff:

```
docs/icarus/handoffs/inbox/YYYY-MM-DD_<loop-name>_<source>.md
```

Do not overwrite another loop's handoff.

## Required header
```
# <Loop name> handoff
SOURCE_LOOP=
SOURCE_CHAT_OR_WORKSTREAM=
PRODUCER=
CAPTURE_DATE=
PINNED_REPO_REVISION=
POLICY_VERSION=
EXECUTION_AUTHORIZED=false
```

Unknown values are written as unknown, not guessed.

## Required sections
1. Purpose / original objective
2. What was actually done
3. Files/repo objects inspected
4. Verified findings
5. Hypotheses
6. Rejected/failed attempts
7. Open conflicts
8. Data/source limitations
9. Code changes actually made
10. Tests actually run
11. Exact next action
12. Artifact/file references

## Reconciliation states
Each imported claim receives one:
- `COMPATIBLE`
- `DUPLICATE`
- `DERIVED_DUPLICATE`
- `REVISION_CONFLICT`
- `CONFIG_CONFLICT`
- `EVIDENCE_CONFLICT`
- `STALE`
- `UNVERIFIED`
- `BLOCKED`

## Merge rules
- Never let a later handoff silently overwrite an earlier failed attempt.
- Do not merge claims across incompatible repository revisions without marking the boundary.
- Collapse derivative reports that share the same underlying evidence origin.
- Preserve negative results and abandoned hypotheses in the attempt ledger.
- A handoff can add evidence without increasing trading authority.
- Any production-code claim must name the exact file/revision and the test evidence.

## After all loops arrive
Create a dated convergence record under:
`docs/icarus/handoffs/convergence/`

The convergence record should identify:
- canonical claims;
- duplicates removed;
- conflicts still open;
- authoritative pinned revision;
- resulting S3 maturity changes;
- S4 architecture changes;
- remaining blockers.

Only then continue new loop research.
