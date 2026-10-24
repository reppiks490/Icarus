# NEXUS and AION runtime connections

Owner asks for two most beneficial subsystem connections in the next restart and delegates selection. This design selects NEXUS source-health monitoring and AION receipt-time history because the immediate goals are input visibility, runtime continuity and observable recovery.

## Scope and source

Use the actual native cores from divine-providence commit 27ae69c593ede3019957100cd401625bd2424f43. Embed unchanged contracts/source_health from NEXUS and contracts/store from AION under icarus_engine.native_subsystems._divine. Record source paths, Git blobs and SHA-256 in a manifest; a private namespace initializer is an ICARUS loading adapter, not the upstream eager initializer. No numpy/pandas or new service is needed for this four-file stdlib closure. Upstream packages declare Python 3.11; this embedded subset must pass actual Python 3.10 verification before the supported ICARUS floor is claimed.

The verified c8bd8d4 release remains the baseline. Its eight automatic workflows now pass, including Windows. Do not claim that a new candidate or the owner's PC is verified by that baseline.

## Runtime contract

NativeSubsystemConnections(base_dir, *, workspace_id, snapshot_supplier, interval=5.0, clock_ns=time.time_ns) owns one background worker and native SQLite state per Main/CC runtime. Methods: start(), close(), tick(), snapshot(). Constructor and snapshot do no database or provider I/O. tick performs actual native NEXUS processing and AION persistence. start is idempotent; close drains before an outgoing CC lifecycle is retired. A failed diagnostic connection never stops paper trading or another workspace.

capture_portfolio(portfolio) reads only existing published runner summaries, selecting bounded metadata; it never calls feed/summary/history/provider methods or copies chart histories. It adjusts relative ages by the summary capture age and exposes missing/stale cache explicitly. Do not persist raw prices, provider payloads, credentials or raw error strings. This is runtime feed telemetry, not new market-data acquisition.

Only changed source observations/health-state transitions are appended, with a bounded heartbeat if justified. Unchanged five-second polls do not create unbounded duplicate records. AION stores native NEXUS health-plane/context receipts and reconstructs those observations across restart. This does not reconstruct open positions, raw market history or profitable decisions.

Snapshot schema: icarus-nexus-aion-v1; workspace_id; state; observed_at_ns; capture_age_seconds; assets; warnings; nexus; aion; source_revision; execution_authorized=false; production_decision_authorized=false. States include STARTING, OBSERVING, DEGRADED, UNAVAILABLE and STOPPED. nexus exposes state, plane_hash, stream_count, unknown_slo_streams and native source identity. aion exposes state, event_count, chain_verified, last_persisted_ns and recovered_event_count. Source-health interpretation must explicitly identify adapter-local observation sequences; upstream provider sequences/SLOs remain unknown unless independently supplied. Never infer reviewed provider health from a zero local receipt lag.

Native AION observations use kind=context, the lowest native evidence tier, truthful origin=icarus_runtime_monitor, research plane, and observed_receipt availability with available_ns==ingested_ns at actual local receipt. Source event time is separate. No availability backdating, true-depth/trade claims, production authority or qualification promotion. Validate native plane hashes and chain consistency; tampering produces an unavailable diagnostic without altering the stored evidence.

Cached HTTP snapshots remain bounded and fast while SQLite/native processing is slow. A stale cached monitor result cannot claim current health. Capture errors and shutdown races remain visible. No new background worker can resurrect an OFF or replaced CC generation.

## API and UI

Main GET /api/subsystem-connections and selected /api/command-centers/<id>/panels/subsystem-connections use existing authentication, selected identity and permission boundaries. Reads return cached snapshots; no caller-triggered sampling or persistence. Main and CCs have separate native state. Reject foreign/unknown selectors through the existing panel dispatcher.

Add a Subsystems view through a small subsystem-connections-ui.js component with mount(container, client) and dispose(). It uses the page-owned client and its selected route, polls only while mounted/visible/powered on, cancels on disposal, preserves current content on ordinary refresh, and shows source time/identity plus explicit unknown/unavailable states. Existing asset-chart rendering and deadlines are unchanged.

## Choices and limits

Considered: native core embedding, a separate Divine service/interpreter, or consuming only existing remote catalog receipts. Embed the small pinned core so the restart has an actual local connection without new service/dependency setup. Remote catalog receipts alone do not prove runtime consumption. DAEDALUS scientific-evaluator integration remains valuable later and is outside this reliability-focused pair.

Existing SourceReliabilityStore remains the research-quality measurement boundary. Do not fabricate provider SLOs or fill its mandatory freshness/independent-agreement inputs from monitor heartbeat data. AION chain/as-of monitoring adds native verified continuity, not an invented scientific qualification.

## Acceptance

Actual native classes run through the ICARUS service and API/UI. Tests cover unchanged-observation deduplication, clock inversion/future metadata, unknown SLO visibility, malformed/tampered planes, corrupted AION chains, unavailable storage, busy sampling, concurrent reads, close/reopen persistence, receipt-time invisibility, Main/CC isolation, OFF/ON and replacement races, no provider calls, and retained Main chart responsiveness. Run actual Python 3.10 smoke and Linux/Windows/Chromium checks. Current guide is replaced and prior bytes archived only after the successor is concretely tested. No zero-error future guarantee or owner-PC success is inferred.
## Owner's subsequent full-restart requirements

The same delivery must include the recurring request-deadline repair and a stopped-state settings migration. Every Main and selected-CC asset receives the owner's actual Main NQ strategy/chart defaults. ETH / COINBASE:ETHUSD and SOL / COINBASE:SOLUSD have exactly three exceptions: 30-minute charts, `use_session=false`, and `qty_contracts=25`. Asset contract economics, selected asset lists, journals and worker power settings stay independent. Future assets inherit the saved template; later explicit per-asset edits retain precedence.

Preparation reads actual authenticated Main NQ settings when the engine is running. If it is already stopped, actual saved NQ and preset records are mandatory; stock values are never silently substituted. The private template, its source hashes and stopped-state backup make the operation reviewable. Source changes after planning abort before mutation; failed writes roll back. Document this as highly important in GitHub and provide complete commands in chat. Phone reconnection follows a confirmed PC restart.

Reproduced deadline causes are synchronous authentication activity writes and journal/runner recomputation in purportedly nonblocking status reads. Authentication uses authoritative bounded read-only SQLite queries, while activity writes run in bounded batches outside the request path. Runtime readers use published snapshots; workers update them outside requests. Dirty, missing, expired or future accounting stays unknown while current assets remain observable. Composite valuation receipt times and individual source capture times remain distinct. Do not widen deadlines or relabel old observations as fresh.
