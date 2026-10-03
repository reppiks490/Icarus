# Verified takeover checkpoint — 2026-10-03

Canonical integrated source: main `d3fe3234de6721a217f6d58d42a92a817bc6024e`.
The original recovery notes are historical; this checkpoint supersedes their
pending verification statements for the three repairs below.

| Repair | Integrated PR | Verification |
| --- | --- | --- |
| Lost edits / configuration delivery | #304 | Eight actual HTTP regressions including wildcard selector consistency; hosted configuration contract and standard Linux/Windows checks successful |
| Recurring background subprocess consoles | #305 | Windows-only no-console flags; preserved process groups, output and logs; real Windows GetConsoleWindow test successful in hosted contract |
| UI status/chart stall during replay | #306 | Twelve configuration tests including timeout reproduction, capital metadata, internal-reader isolation, epoch retention and failed second-asset rollback; independent review has no remaining blocker |

Combined local engine suite: **1,859 passed, 2 platform skips in 94.85 seconds**.
Hosted exact source `0834e4d83f2c065c000f4bef7efbc50718f7f10f`: Linux full engine
suite and Windows standard selected suite successful, run `37107448158`;
configuration contract successful on both platforms, run `37107448150`.
Windows no-console contract: run `37105836394`. Tests include real executed
PowerShell launcher behavior on Windows. The Windows standard job is a selected
suite; it must not be described as all 1,859 Linux/local tests running on Windows.

All six UI-repair Git blobs match the tested local files. One draft publication
transfer mismatch was corrected before review qualification or merge. Dashboard
JavaScript syntax checks passed. Internal status/chart consumers retain locks;
public snapshots are detached display-only values, explicitly labeled while busy.
No strategy rewrite, market-data invention, schedule modification, credential
change, production-decision promotion or execution authorization occurred.

The immutable receipt at
`automation_intelligence/mcp_interface/events/20261003_takeover_config_windows_replay_repairs.json`
passes the production validator and was projected through the production evolution
synchronizer into System Intelligence and Adaptive Brain. A second ingest remains
one event, with both authority flags false. This verifies the receipt/consumer
contract; actual HTTP /api/system/audit, /api/evolution and /api/brain
responses also exposed this final receipt in an isolated server. The user's engine must run the updated source and its normal sync for
that event to appear on the user's own screen.

## Remaining boundaries and other owners

- The user's Windows desktop and installed Task Scheduler actions are inaccessible.
  Applying this source, restarting the engine and observing the original recurrence
  remain unverified. There is no repository Task Scheduler installer to repair.
- The cloud browser cannot open the local fixture (ERR_BLOCKED_BY_CLIENT), and
  the existing private Tailscale URL returned 502 / connection refused. Actual
  rendered UI behavior on that machine has not been observed. Endpoint, accounting,
  JavaScript and integration-contract checks are verified; visual proof is absent.
- Active ASCENDANCY #302, historical projection #301, Psi history #297, evolution
  migration #296, private runner hold #295, mobile draft #198 and satellite
  DAEDALUS/AEGIS registry/caller-chain work retain their owners. Their code has not
  been duplicated, merged, or claimed complete by this checkpoint. #302's observed
  failed CI expects an `action_id` message in its tampered-identity regression;
  this diagnostic is recorded for its owner rather than patched across their lane.
- Cross-repo research-only acceptance and shadow worker evidence remain separate
  from native substantive completion. Earlier packet reported zero substantive
  lanes; no self-learning/market-performance certification is inferred from tests
  or transport. New worker/dataset/holdout evidence must qualify independently.
- Satellite local process-identity failures arose from inconsistent PID/proc
  visibility. Production death/restart safety was preserved. Hosted/runtime
  qualification in the actual process environment is still required for that lane.

No claim that every possible feature or every future defect has been exhausted.
This is the exact verified scope and a durable handoff that prevents duplicate work.

Fresh satellite head `fa317babf3392a0807d61e8981574883f269615a` contains
a separate restored-five durability recovery across finalization states and
watchdog receipts. This concurrent work was observed and left intact.
