# Macro Regime Data Grid — historical loop handoff

SOURCE_LOOP=Macro Regime Data Grid
PRODUCER=ChatGPT historical-loop migration
CAPTURE_DATE=2026-09-28
PINNED_REPO_REVISION=425d8c66b30c93d91b13c6ed3ad35067be6c612e
EXECUTION_AUTHORIZED=false
SENSITIVITY=PUBLIC_SAFE
CLASSIFICATION=COLLECTION_PIPELINE
SNAPSHOT_STATUS=ACTIVE_AT_MASTER_HANDOFF
OWNERSHIP=Macro/fundamental/cross-asset/public-equity collection; preserve macro vs fundamental children

## Mission
Collect point-in-time macro, liquidity, rates, Treasury/Fed, public-equity and cross-asset state for later research without directional conclusions.

## Recovered routing
Migration evidence observed Icarus-engine automation_intelligence/macro/ and automation_intelligence/fundamental/. The workflow spans both but must not erase separate state boundaries.

## Latest recovered checkpoint
- Sep 28 ON RRP: ~ $851M.
- morning SRP: $0; afternoon SRP was still IN_PROGRESS at that collection moment.
- Daily Treasury Statement through Sep 24: TGA ~ $924.627B.
- FR2004 latest verified Sep 16:
  - dealer net $454.557B
  - repo $3.065T
  - reverse repo $2.747T
  - fails-to-deliver $161.712B
  - fails-to-receive $158.653B
- quarter-only operating cash flow collected:
  - NVDA $24.077B
  - AAPL $34.369B
  - AMZN $45.387B
  - GOOGL $39.069B
  - META $31.862B
  - MSFT $55.441B

Publication date, observation period and retrieval time stay distinct. In-progress/unpublished values are never rewritten by later releases.

## Preservation boundary
Repository evidence outranks chat summaries. Historical tests/hashes remain historical evidence until re-run or repo-correlated. No sibling ownership is merged. EXECUTION_AUTHORIZED=false.
