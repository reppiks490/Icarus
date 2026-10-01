# ICARUS Mobile architecture

## Objective

ICARUS Mobile is a first-class native observation client for the existing ICARUS runtime. The computational engine remains authoritative. Mobile is not a second strategy engine and does not replicate market logic.

## Data path

```text
iPhone / Android
      |
      | HTTPS
      v
ICARUS Mobile Gateway :8792 (loopback by default)
      |
      | local HTTP + engine admin credential held server-side
      v
ICARUS Engine :8791 (loopback only)
      |
      +-- runtime / status
      +-- charts / trades
      +-- Adaptive Brain
      +-- APEX Ω
      +-- Learning / Possibility / Chronofold / Pantheon / Sibyl
      +-- control-plane state
```

The engine's existing Host check and loopback bind remain unchanged.

## Authentication lifecycle

1. Operator configures `ICARUS_MOBILE_PAIRING_SECRET` on the gateway host.
2. A device submits that secret once to `POST /v1/pair`.
3. Gateway creates a random device ID and high-entropy refresh credential.
4. Gateway returns a short-lived HMAC-signed session.
5. The app stores device/refresh/session material in SecureStore.
6. Before session expiry, `POST /v1/session` rotates the refresh credential and issues a new session.
7. Revocation marks the server-side device record inactive; all existing sessions immediately fail the active-device check.

The engine admin token never crosses the gateway.

## Live updates

The gateway maintains one shared snapshot cache over status, repository/loop audit, and briefing. Mobile clients use `GET /v1/events?cursor=...&wait=25`. The request blocks until the snapshot cursor changes or the wait window expires, reducing unnecessary polling while remaining compatible with standard React Native fetch.

## Read surface

Curated routes currently include status, briefing, system audit, charts, closed trades, Brain, APEX, Learning Health, Engine Control, Integrity, Research, Possibility, Chronofold, Commissioning, Pantheon, Sibyl, Performance Proof, Latency, and Source Reliability.

There is no generic proxy. The only permitted write-through operation is a tightly validated, rate-limited `/v1/backtest` analysis launch mapped to `/admin/backtest`; no trading-state mutation route is exposed.

## Packaging

`mobile/eas.json` defines development, internal-preview, and production profiles. Final TestFlight/App Store/Play builds require the operator's platform credentials and final identifiers/hostname.
