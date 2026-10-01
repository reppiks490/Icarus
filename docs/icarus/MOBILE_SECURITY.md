# ICARUS Mobile security contract

## Non-negotiable boundaries

- Engine port 8791 stays loopback-only.
- Mobile never stores the ICARUS engine admin token.
- The gateway does not expose `/admin/*` or arbitrary upstream paths.
- The first mobile release is observation-only.
- Production phone-to-gateway traffic uses HTTPS.
- Pairing secrets, engine admin tokens, signing keys, refresh credentials, and store credentials are never committed.

## Credential model

The pairing secret is an enrollment factor, not a long-lived device session. A successful pair creates a random refresh credential. Refresh credentials are stored only as SHA-256 hashes server-side and rotate on each refresh. Mobile stores its current refresh credential using Expo SecureStore.

Session tokens are HMAC-SHA256 signed, carry a device subject, issue time, expiry, and nonce, and default to 15 minutes. Even a cryptographically valid session is rejected after its device is revoked.

The signing key is generated with `secrets.token_bytes(32)` and persisted with best-effort mode 0600.

## Abuse controls

- Pairing attempts are rate-limited per immediate peer.
- Request JSON is capped at 64 KiB.
- Upstream JSON responses are capped at 4 MiB.
- Dynamic asset identifiers are allowlisted by syntax.
- Chart/trade limits are clamped.
- Gateway non-loopback binding requires an explicit override.
- Security headers disable framing, MIME sniffing, referrer leakage, camera, microphone, and geolocation permissions.

## Threats not solved by application code alone

A production deployment still needs OS patching, TLS certificate management, firewall policy, secure secret injection, device lock/biometric policy, Apple/Google signing protection, and monitoring of the public ingress layer.

If remote access is not required, a private overlay network or device VPN is preferable to a public hostname.
