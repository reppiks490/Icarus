# ICARUS Live Intelligence Gateway Plan Addendum — Standalone Launcher

This addendum is part of `docs/superpowers/plans/2026-10-13-intelligence-gateway.md` and closes a plan self-review gap: the approved design requires a standalone gateway process, while the first plan revision only specified an ASGI app factory.

No design scope expands beyond `icarus_engine/intelligence_gateway.py` and the two Phase 3 test files.

## Launcher contract

Add to `icarus_engine/intelligence_gateway.py`:

- `def main(argv: Sequence[str] | None = None) -> int`
- `if __name__ == "__main__": raise SystemExit(main())`

Launch interface:

- required `--db <file-backed-sqlite-path>`
- optional `--host`, default `127.0.0.1`
- optional `--port`, default `8792`
- optional `--allow-remote`, default false
- optional repeatable `--allowed-host`
- optional repeatable `--allowed-origin`
- bearer token read only from environment variable `ICARUS_INTELLIGENCE_GATEWAY_TOKEN`
- no command-line bearer option, preventing the long-lived bearer from appearing in process listings/history
- missing/empty token fails startup before binding
- `validate_bind_host()` runs before `uvicorn.run()`
- app constructed with `create_intelligence_gateway_app(...)`
- gateway-managed Uvicorn launch uses `access_log=False`; application-level gateway logs remain sanitized through `redact_for_log()`

Phase 3 still does not generate or persist a long-lived credential. The environment variable is only an operator-supplied startup transport for the bearer described in the approved design.

## Additional TDD steps for Task 6

Before Task 6 is committed, add failing tests:

- `test_main_requires_gateway_token_environment_variable_before_uvicorn_start`
- `test_main_rejects_in_memory_database_path`
- `test_main_rejects_remote_bind_without_allow_remote`
- `test_main_passes_loopback_host_and_port_to_uvicorn`
- `test_main_disables_uvicorn_raw_access_log`
- `test_main_never_places_bearer_token_in_argv_or_loggable_uvicorn_kwargs`

Implement the minimal argparse/Uvicorn launcher only after those tests fail for the expected missing behavior. Mock `uvicorn.run` in unit tests; no live network bind is required for launcher unit coverage.

## Review-focus correction

The one-time SSE ticket remains a query capability in gateway protocol v1 because native `EventSource` cannot set the Authorization header. The gateway-managed launcher therefore disables raw Uvicorn access logging, and gateway application logging must never record raw request query strings. Tests must verify the application logger/redaction path never emits the ticket value.

External reverse proxies or alternative ASGI servers are outside Phase 3 deployment guarantees; exposing the gateway through one requires equivalent query-secret redaction as an operator deployment responsibility. This does not weaken the default loopback-only Phase 3 launch contract.
