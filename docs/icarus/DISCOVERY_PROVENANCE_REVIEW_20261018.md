# Discovery qualification provenance repair — 2026-10-18

The read-only audit found two false access claims in the merged registry
foundation. A synthetic receipt verifying only Bybit's spot kline operation
qualified an option-category URL at the same path. A receipt from the approved
API collector also qualified URLs at a provider's marketing hostname. These
claims concern research qualification; registry execution and production-decision
authority remain false.

The repair starts from Icarus main
`c993130534126a352c766fb7abc0de3145fc110f` on branch
`codex/discovery-operation-provenance-20261018`. It preserves ancestry links,
requires the approved collector API origin, and binds query values that
distinguish same-route operation variants. Missing, duplicate, conflicting or
indistinguishable variant bindings fail closed. Positive API-origin and matching
variant cases remain eligible under the existing receipt/blocker/freshness gates.
The v4 link/event identity prevents replay of unbound v3 links as new evidence.

The reviewed source for the explicit API-origin mapping is
`tools/provider_exhaustive_collection.py:PROVIDERS`. The registry does not import
or invoke that collector. Changes to collector origins require a corresponding
review of the mapping. Qualification remains limited to operation access, and
does not establish every symbol, query cross-product, historical interval,
license, ToS condition or entitlement. Historical qualification events are
immutable and are not retroactively demoted by this change; requalification is
required before relying on historical v3 access claims as current v4 evidence.

## Superseded draft evidence

GitHub PR metadata and Git ancestry were checked during the audit. The original
draft branches remain preserved and are not changed by this repair.

| Draft | Original head | Verified replacement on main |
|---|---|---|
| #330, open draft at audit | `8b7cf387d23b3e6043304b501db5a107aff10da6` | Merged #369, `862a1ca38d4adcc11cb4ddc9093fcf857fe2e46f` |
| #332, open draft at audit | `71a726a3678d87b4c5b72350d944b71c38c3919f` | Merged #351, `982e5e58f06c283e7b3a7411dbc49940d1188825` |

The complete four-file #330 patch matches the #369 merge patch, SHA-256
`e713bfd4212272bcc49fe47d324db46d44cc7fc6f7d62230fe4a24b2b266f849`.
The #332 specification, implementation plan and contract tests are byte-identical
to audited main. Subsequent main corrections include #390 at
`07f6329c29c79761e7db1a04782a56aea76a5a05` and Brain chronology #433 at
`085c655580e4c98adda67da1ed7b52f9e3455338`. Draft closure is a separate owner action.

## Verification

All new cases use synthetic local receipts and catalog fixtures. The initial
federation regression run produced ten expected failures before implementation;
additional ambiguity and blank-descriptor regressions failed before their
conservative guards were added. The registry and catalog CLI suite subsequently
passed 133 tests:

```bash
python -m pytest -p no:cacheprovider tests_engine/test_discovery_registry_*.py tests/test_catalog_registry_ingest.py -o addopts='' -q
```

Coverage includes spot versus option, missing/empty/duplicate query bindings,
indistinguishable descriptors, an ID-qualified singleton, API versus marketing
host, effective HTTPS port, legacy v3 links, and CLI persistence. No provider
request, discovered-service probe, entitlement change or live broker arming is
part of this work.

The default project suite at initial repair head
`760e6539e5993312c46ac04b264c976ee0b628de` reported **2897 passed, 3 skipped,
111 subtests passed and 7 failed**. The same seven failures reproduce on untouched
base `c993130534126a352c766fb7abc0de3145fc110f` in a separate detached worktree
(7 failed, 16 passed when running those two modules). Verification used an
external temporary socket guard allowing localhost and blocking external
connections. The failures belong to the separately coordinated A200 lane:

- `test_a200_listing_crosswalk.py::test_crosswalk_reports_all_200_listing_identities_without_feed_qualification`
- `test_a200_listing_crosswalk.py::test_crosswalk_detects_listing_mismatch_without_promoting_it`
- `test_a200_runtime_feed.py::test_qualified_historical_batch_runs_pulse_in_signal_only_research_mode`
- `test_a200_runtime_feed.py::test_admission_and_session_creation_use_one_catalog_snapshot`
- `test_a200_runtime_feed.py::test_portfolio_entrypoint_keeps_a200_research_outside_live_asset_registry`
- `test_a200_runtime_feed.py::test_research_runtime_rejects_missing_bars_between_admitted_batches`
- `test_a200_runtime_feed.py::test_research_runtime_rejects_catalog_economics_change_mid_session`

The listing cases observe `STALE` rather than expected `CURRENT`; runtime cases
fail their admission assertion. The final small blank-descriptor guard and its
two regression cases are covered by the 133-test focused run above. A200 fixtures
and runtime code are unchanged by this PR.
