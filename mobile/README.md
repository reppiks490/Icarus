# ICARUS Mobile

Native iOS/Android command-and-observation client for the canonical reppiks490/Icarus runtime.

## Phase 1 boundary

This app is deliberately read-only for trading/execution. It consumes the existing engine surfaces:

- /healthz
- /status/public
- /api/briefing
- /api/system/audit
- authenticated /api/brain
- authenticated /api/apex
- authenticated /api/learning/health
- authenticated /api/engine-control

The engine currently protects itself by binding to loopback and rejecting non-loopback Host values. Keep that behavior. Mobile should reach ICARUS through a hardened HTTPS gateway/reverse proxy that terminates TLS and forwards to the local engine. Do not open port 8791 directly to the internet.

## Stack

- Expo SDK 57 stable
- React Native 0.86
- React 19.2
- TypeScript 6
- Expo SecureStore for gateway URL and admin token

SDK 57 is used intentionally instead of the SDK 58 beta line.

## Run

1. Change into the mobile directory.
2. Run npm install.
3. Run npm run typecheck.
4. Run npm run start.
5. Open Settings in the app and enter the HTTPS gateway URL plus the ICARUS admin token.

The app tests /healthz before persisting the connection.

## Security invariants

1. Never embed the ICARUS admin token in source, app config, EAS config, or repository-delivered client configuration.
2. Keep execution controls server-side and authenticated.
3. Do not weaken _host_ok() or the loopback bind merely to make phone connectivity convenient.
4. Production transport must use HTTPS.
5. The first mobile release remains observation-only. Execution controls require a later explicit threat-model, authorization, and audit gate.

## Next integration slice

- Mobile gateway service with scoped, short-lived mobile sessions instead of shipping the engine admin token to the client.
- WebSocket or SSE event stream for status, signal, loop, and system-health updates.
- Native charts and time-series drilldown using /api/chart/<SYM>.
- Push notifications for user-selected conditions.
- Backtest and research views.
- Controlled operator actions only after explicit mobile authorization design and audit logging.
