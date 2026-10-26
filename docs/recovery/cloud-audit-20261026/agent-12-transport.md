# Agent 12 — supplemental transport patch

Prepared against `/workspace/publish/Icarus-engine`; source files remain unchanged. Root owns integration and coordination publication.

Cause: `core.SECRET` matches resource name `list_tokens`, rejecting the admitted UW discovery endpoint before HTTP.

The patch validates UW endpoint structure independently from credential field names. It admits `/api/crypto/list_tokens`, rejects inline queries/fragments, URL authorities, traversal, percent-encoded forms, backslashes and control/whitespace, and retains header-only bearer authentication, query-secret filtering, the documented `next_token` exception and redirect refusal. Percent-encoded endpoint paths deliberately fail closed; ordinary catalog paths are unaffected. Other providers still delegate unchanged.

Offline verification used temporary source copies and a fake urllib opener; no network/provider calls, credentials, commits or repository source mutation. Original code: 12 failures, 20 passes, including the expected `list_tokens` failure. Candidate: 32 transport tests passed; combined transport/core collection suite: **65 passed** in 0.43s. The full repository suite was not run in this bounded task.

Reproduce after integration with the configured Engine venv: `python -B -m pytest -q -p no:cacheprovider tests/test_provider_supplemental_transport.py tests/test_provider_exhaustive_collection.py`.

Authentication/entitlement blockers remain external and are not fixed by this patch.
