# ICARUS Mobile gateway on Windows

The engine remains on `127.0.0.1:8791`. The mobile gateway runs separately on `127.0.0.1:8792` and should be published only through a TLS/private-network layer.

## Start from Command Prompt

From the ICARUS repository:

```bat
set ICARUS_ADMIN_TOKEN=YOUR_EXISTING_ENGINE_ADMIN_TOKEN
set ICARUS_MOBILE_PAIRING_SECRET=USE_A_LONG_RANDOM_SECRET
start-mobile-gateway.bat
```

The launcher runs `icarus-mobile-gateway doctor` first and refuses to start if the engine, admin token, or pairing secret is missing.

## Start from PowerShell

```powershell
$env:ICARUS_ADMIN_TOKEN = "YOUR_EXISTING_ENGINE_ADMIN_TOKEN"
$env:ICARUS_MOBILE_PAIRING_SECRET = "USE_A_LONG_RANDOM_SECRET"
.\start-mobile-gateway.bat
```

Do not paste real credentials into tracked files. The gateway creates `mobile_gateway/session.key`, `mobile_gateway/devices.json`, and `mobile_gateway/audit.jsonl` beneath `ICARUS_HOME`.

## Phone connectivity

Keep ports 8791 and 8792 private. Put HTTPS or a private overlay/VPN in front of the gateway. The app validates that it is connecting to ICARUS Mobile API v1 and refuses an incompatible endpoint.
