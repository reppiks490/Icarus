# Local CSV source and data repair

Owner: this Codex continuation session. Baseline:
`11b2ac0618320861e0a47058cac8fd480ed6b7a7`.
Existing #297/#296/#295/#198 and private satellite lanes retain their owners.
This implements bounded parts of the existing SOURCE/DATA contract, not the
whole empirical qualification chain.

## Reproduced failures

Feed and trainer parsing rejected valid microsecond/nanosecond epoch encodings;
the feed also rejected year-2000 milliseconds accepted by the trainer. Numeric
and ISO upper bounds disagreed. Declared New York wall times guessed daylight
saving folds/gaps. FileFeed discarded a caller's declared timezone on reload.
Within-file feed conflicts silently used the last row, including impossible
OHLC. The trainer manufactured open/high/low from `time,close` and called that
file clean. Ambiguous selected headers could silently replace frozen features.

Catalog hashing and parsing reopened the same mutable path. Backfill could train
changed bytes under the earlier dataset identity. Re-registering an existing
raw hash discarded the new inspection, while cached old training reports could
appear current and hide from the automatic backlog. Shared parser code was not
included in protected study identities.

## Repair and compatibility

One timestamp kernel retains raw text, detected encoding, exact decimal seconds,
float seconds and timezone basis. Magnitude detection is a documented encoding
heuristic, not a provider attestation. Numeric and offset-aware ISO timestamps
use the same exclusive 1970/2100 bounds. The feed preserves its 2000 lower bound;
the trainer keeps older positive epochs and refuses naive times. Declared wall
times must have one round-tripping UTC identity. File reload preserves the
declared timezone.

The existing integer-second CSV runtime rejects subsecond clocks instead of
collapsing them. The trainer rejects distinct exact times that collide as floats.
These rules do not claim nanosecond runtime precision. Missing/nonfinite prices,
impossible geometry, invalid volume and ambiguous selected columns are blocked.
Unknown-time rows remain counted/dropped, identical duplicates collapse, zero
volume and feed semicolon inputs remain accepted. Incoming-wins merging across
successive valid exports is preserved. CLI rejection leaves existing history
unchanged, and failed FileFeed reload keeps its prior rows.

Registration and new backfill parse the exact hashed byte snapshot. Current
inspection metadata may refresh for the same raw identity; original declarations
and all training reports are preserved. Old OHLC parser receipts are visibly
`needs_requalification` in the API, health backlog and Learning UI. They do not
trigger automatic retraining or reuse protected evidence. XGB/rank code digests
include the shared kernel; rank also includes integrity parsing.

## Verification and limits

The initial synthetic regression suite produced 34 assertion failures across
14 tests before repair. Additional cache/snapshot/study/UI regressions also
failed before their repairs. Review also reproduced fine ISO fraction truncation,
wall-time overflow, float flooring and conflicting intake replacement. These
now have regressions; unsupported fractional UTC offsets are refused. Repeated
blocked backfills retain their blocked state. All 22 new tests and the 10 historical closure
regressions pass locally. Tests execute real parser, file reload, CLI, SQLite,
study digests and the shipped JavaScript. Mutable-path fault injection changes
actual bytes while preserving the real parser/trainer. Exact published-source
Linux/Windows and full engine CI must pass before integration.

This does not qualify provider auth/entitlements, source availability clocks,
chart transforms, irregular-bar completion, prediction lead, protected holdouts,
model value, economics or market performance. No real-data model was trained and
no live strategy, schedule, broker, or production/execution authority changed.
User-machine deployment and desktop popup recurrence remain unobserved.
