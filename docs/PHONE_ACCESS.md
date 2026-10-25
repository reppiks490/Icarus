# Current ICARUS phone access

The old viewer-token relay/tunnel flow is retired. Use the integrated native app and the dedicated observation gateway:

- [Current Prime restart and mobile observation boundary](recovery/PRIME_AS_IS_RESTART.md)
- [Mobile gateway on Windows](icarus/MOBILE_WINDOWS.md)
- [Native mobile app setup and pairing](../mobile/README.md)

The desktop engine stays private on `127.0.0.1:8791`; the optional mobile gateway runs separately on `127.0.0.1:8792`. Put only the gateway behind HTTPS or a private VPN. The phone receives device-scoped, revocable credentials and never receives the engine admin token. The gateway allows explicit rate-limited backtest starts but blocks trade-state mutations. Do not use archived relay, hosted-page, or temporary-tunnel commands.

Actual phone pairing requires the owner's PC and phone, a linked Expo project, and a reachable HTTPS/private-network gateway hostname. Distributable builds additionally require the owner's store accounts and signing credentials.