31/50 — read-only context audit; no network or tests.

Verified: sha256sum matches all three manifest hashes exactly. Manifest retrieval date is 2026-10-26, DataHub update date 2026-10-22; CSVs end 2026-10-20 (Brent115.22, WTI107.89, HenryHub3.1). Units match UI: oil USD/barrel, gas USD/MMBtu. All are six days old and therefore STALE under the five-day threshold. These checks establish bundled consistency, not upstream authenticity.

Missing handling is correct: gas CSV:3518 preserves 2018-01-05 blank; research_context.py:104-114 emits null/missing_price, selects latest nonmissing value, and counts missing rows. UI sources-ui.js:65 renders missing values without interpolation; its 30-row window excludes this historical gap.

Consumption: research_service.py:158 lazily constructs store; authenticated server.py:2249 exposes bounded snapshot; workspace_context.py:8 and workspace-client.js:23 allow shared reads; sources-ui.js:45 displays it. No EIA-store consumer exists in Brain/BrainResearchSync; the latter imports completed study artifacts. Optional useful additions: Brain research-only context summary and visible snapshot provenance/missing count (returned but undisplayed).

Concrete resilience gap: filesystem PermissionError/disappearance during manifest read/hash/CSV open (research_context.py:53-91) escapes; server.py:2263-2266 catches ValueError/TypeError/KeyError/RuntimeError only, causing a dropped request instead of structured unavailable status. CSV parser errors similarly lack normalization. No packaged corruption found.
