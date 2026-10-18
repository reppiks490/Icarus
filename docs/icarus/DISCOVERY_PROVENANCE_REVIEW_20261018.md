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
an additional ambiguity regression failed before its conservative guard was
added. The registry and catalog CLI suite subsequently passed 131 tests:

```bash
python -m pytest -p no:cacheprovider tests_engine/test_discovery_registry_*.py tests/test_catalog_registry_ingest.py -o addopts='' -q
```

Coverage includes spot versus option, missing/empty/duplicate query bindings,
indistinguishable descriptors, an ID-qualified singleton, API versus marketing
host, effective HTTPS port, legacy v3 links, and CLI persistence. No provider
request, discovered-service probe, entitlement change or live broker arming is
part of this work.
