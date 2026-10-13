# Phase 3 SSE test-harness debugging note

Date: 2026-10-13

Observed on push run `38479921585` at implementation head `36bf6480fc3029192ced4549d978c9dc31d76068`:

- Windows completed successfully.
- Linux full-suite execution did not complete after entering the new SSE integration tests.
- Root cause investigation inspected Starlette `_TestClientTransport.handle_request`: the transport accumulates `http.response.body` chunks in a `BytesIO` and does not return an `httpx.Response` until ASGI sends a body message with `more_body=False`.
- ICARUS SSE is deliberately long-lived and continues sending with `more_body=True`; therefore `TestClient.stream()` cannot serve as a finite integration harness for this endpoint and deadlocks by design.
- Production SSE semantics were left unchanged.
- Commit `5b4a5e19fc2b116b0afc11a168fd0f82f8b42200` replaces only the affected test harness with a raw ASGI driver that injects `http.disconnect` after the target SSE event, preserving real StreamingResponse routing/framing while making the test finite.

Ruling: treat the hang as a test-harness defect, not a gateway-runtime defect. Do not make production SSE finite merely to satisfy Starlette TestClient.