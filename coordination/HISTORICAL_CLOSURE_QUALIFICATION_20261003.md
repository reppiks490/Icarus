# Historical import closure and real-export qualification

## Reproduced defects

The available September 30 export set contains 21 physical files and 11 distinct
manifest hashes: two chart files, two trade-list CSVs and seven strategy reports.
All bytes match the owner's intake manifest. This is the available export set,
not a qualification of the separate ten-archive corpus. Raw source files remain
private and are not committed. The CSV lab's scanner and active heartbeat lane
remain separately owned; this work tests ICARUS's existing historical importer.

Isolated imports at canonical `625bc306d620d0b890ec0795250dd70d3cac48f8`
produced 3,901 experiences in both import orders. A legitimate open tail caused
the semantic signature to be unavailable for an entire report, so its 463 closed
trades were counted again when the equivalent CSV arrived. Equal aggregate counts
between orders did not prove deduplication. Independent review also reproduced
partial/overclosed quantities, negative exit pieces, orphan exits and malformed
directions being admitted without complete closure proof.

## Repair

Historical signatures and both importers opt into strict trade-row validation.
The existing parity comparison keeps its default compatibility behavior. Strict
validation permits exit-before-entry row ordering and grouping legitimate partial
exits across entry numbers. It rejects missing/repeated entries, orphan exits,
unsupported types, direction disagreement, invalid numbers and exit timestamps
before their entry. Each exit quantity must be positive, and summed closed exits
must equal entered quantity within floating-point summation error.

Explicit OPEN tails are excluded from completed-trade semantics. They do not
disable equivalence for valid closed trades; an empty completed set provides no
equivalence proof. Invalid CSV tables now leave a durable diagnostic receipt.
Cached invalid/partial results retain their original visible status on retry.

New historical receipts identify admission version 2. Older receipts are surfaced
as needing requalification, including a Learning dashboard notice. Their durable
experiences and receipts are preserved; installing this fix does not silently
remove previously recorded duplicates or requalify an existing database.

## Verification

Synthetic CSV/XLSX regressions reproduced 22 failures before the repair. They cover
open-tail twins in both orders, partial/overclosed and negative quantities,
tiny/large quantity mismatch, direction/orphan/time errors, fractional partial
exits, grouped entries, legacy receipt preservation and executed UI notice refresh.

The repaired real set produces 3,438 unique closed experiences in both orders,
matching independent decimal-based source grouping. Both orders have identical
admitted trade multisets, two semantic twin deduplications, no import errors,
unchanged counts on repeated backfill, zero runtime-closure configuration records
and no training. The two chart files are catalogued only. Source timezone,
session/settings, availability clocks and market performance remain unqualified.
Independent review and exact published-head Linux/Windows hosted checks gate merge.

## Earlier continuation deliveries

Canonical #309 is merged at `625bc306d620d0b890ec0795250dd70d3cac48f8` after
all nine exact-head hosted workflows passed. Its fixed native worker performs
contract validation only; scientific smoke/null tests remain a subsequent stage.
Peer #63 and #65 are merged with receipt-bound heartbeats and Windows no-console
Git launches. Peer #66 merged at `5ad2f666c563b38a75fd2f98e66bc8749a6c28f7`.
Actual committed repair/qualification envelopes replayed into canonical Brain:
seven accepted events, zero rejected, five lane contract bindings, four local
source witnesses, three source contracts and four historical projections. Current
substantive-lane and historical candidate-evidence counts remain zero. The
acknowledgement is a prior-packet receipt, not current scientific qualification.

Existing owners #297/#296/#295/#198 and private satellite lanes are preserved.
User-machine deployment, actual desktop popup recurrence and live rendered UI
remain unobserved. No broker actions, schedules or trading authority changed.
