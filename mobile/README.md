# ICARUS Mobile

Native iOS/Android observation client for the canonical `reppiks490/Icarus` runtime.

## What exists now

- Expo SDK 57 / React Native 0.86 client.
- Device pairing through the dedicated read-only ICARUS mobile gateway.
- Rotating per-device refresh credentials stored with Expo SecureStore.
- Short-lived signed sessions; the phone never receives the engine admin token.
- Long-poll live snapshots for engine status, system audit, and briefing.
- Native candlestick chart and recent closed-trade drilldown.
- Authenticated Adaptive Brain, APEX Ω, Learning Health, Possibility Ψ, Engine Control, and Data Integrity readouts.
- Per-device revocation.
- EAS build profiles for development, internal preview, and production.

Trade-state mutations remain intentionally absent from the mobile gateway.

## Development

Requires Node.js 22.13.x or later for Expo SDK 57.

```bash
cd mobile
npm install
npx expo install --check
npm run typecheck
npm run start
```

The repository CI also bundles the iOS and Android JavaScript exports.

## Pairing

Start the engine normally on loopback, then set gateway secrets outside the repository:

```bash
export ICARUS_ADMIN_TOKEN='<engine admin token>'
export ICARUS_MOBILE_PAIRING_SECRET='<long random secret>'
icarus-mobile-gateway doctor
icarus-mobile-gateway serve
```

The gateway binds to `127.0.0.1:8792` by default. Put TLS in front of it with a local reverse proxy such as the sample Caddy configuration under `deploy/`. Do not expose engine port 8791.

In the app, open Settings, enter the HTTPS gateway URL, a device label, and the pairing secret. The secret is used for that pairing request and is not retained after success.

## Device operations

```bash
icarus-mobile-gateway devices
icarus-mobile-gateway revoke <device-id>
```

The app can also revoke its own current credential.

## Remaining release dependencies

A store-signed install still requires the operator's Apple/Google developer credentials and the final public/private gateway hostname. Those credentials are deliberately not committed or requested by the codebase.
