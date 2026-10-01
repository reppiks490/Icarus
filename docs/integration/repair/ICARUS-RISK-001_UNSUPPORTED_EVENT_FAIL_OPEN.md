# ICARUS-RISK-001 — fail closed on unsupported alert events

## Root cause

Pinned revision: `007e70189945b8e112904cf92b2b1a12e43792d6`.

The bridge accepts an authenticated payload into an `Alert`. `ExecutionEngine.handle_alert()` explicitly handles `text` and `stop_update`; the remaining path is treated as an order-fill/reconciliation event. The allowed event vocabulary is therefore not enforced as a closed set at the boundary.

This creates a fail-open dispatch condition: a syntactically/authentication-valid but semantically unsupported event can reach fill logic.

## TDD repair sequence

### RED — regression first

Add a negative regression that:

1. creates a normal shadow/test configuration with a mapped ticker;
2. submits an authenticated payload whose `event` is a value such as `unexpected_event`;
3. supplies otherwise plausible fill fields so the old fall-through would be capable of producing an action;
4. asserts the request/result is rejected/journaled as unsupported;
5. asserts no broker order/fill/position mutation occurs.

Add a second unit-level test constructing an `Alert(event="unexpected_event", ...)` directly and passing it to `handle_alert()`, proving the dispatcher itself fails closed even if the parser is bypassed.

The test oracle must be **absence of broker mutation plus explicit unsupported-event result**, not merely a copied implementation branch.

### GREEN — smallest fix

Enforce the closed event set in the parser:

```python
ALLOWED_EVENTS = {"order_fill", "stop_update", "text"}
if event not in ALLOWED_EVENTS:
    raise AlertParseError(f"unsupported event: {event}")
```

Also defend in the dispatcher before any fill path:

```python
if alert.event not in {"order_fill", "stop_update", "text"}:
    self._log("WARN", f"unsupported alert event: {alert.event}")
    return Result(status="rejected", note="unsupported event", symbol=symbol)
```

Exact placement/return shape should match the repository's existing `Alert`, `Result`, and journal conventions.

### REFACTOR

Only after RED→GREEN:
- centralize the event vocabulary if doing so does not widen the patch;
- keep behavior for `order_fill`, `stop_update`, and `text` byte/semantic compatible;
- do not change sizing, broker adapters, symbol mapping, or Pulse.

## Verification required before integration

- the two new negative tests pass;
- existing bridge tests pass;
- focused execution-control tests pass;
- full applicable test suite passes;
- no broker/network dependency is required for the negative regression (ShadowBroker is sufficient);
- diff inspection confirms no execution-authority change.

## Current status

Repair package only. No production code has been modified by this handoff and no RED/GREEN run is claimed.
