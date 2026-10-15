# ICARUS phone command center

The hosted phone UI is intended for the Site owner. The Cloudflare Quick Tunnel
URL is publicly reachable by anyone who has it; it does not create a Cloudflare
Access policy.

<https://icarus-command-center-mobile.cloudyrook1.chatgpt.site>

It bundles the same responsive dashboard served by `icarus_engine.server` and
adds the Divine Providence Observatory and semantic command-console links. The
Site never fabricates market, account, or engine data. It shows a disconnected
state until the local services are paired.

## Start a private phone connection

The existing dashboard must already be running on `127.0.0.1:8791`. Start the
loopback router from the Icarus repository in Git Bash:

```bash
python -m icarus_engine.phone_access_proxy
```

In a second Git Bash window, start a Cloudflare Quick Tunnel to the router:

```bash
cloudflared tunnel --url http://127.0.0.1:8790 --http-host-header 127.0.0.1:8790
```

Cloudflared prints an HTTPS `trycloudflare.com` URL. Open the hosted command
center on the phone, expand **Connect this phone to the engine**, paste that
URL, and choose **Connect**. The route is saved in a secure, same-site browser
cookie and local storage; it is not placed in the page URL. Enter a strong,
unique engine bearer token in **⚙︎ Token**. The relay requires a bearer token
for API and command routes and validates it against the engine access registry
before forwarding; the engine also authenticates `/status/public`. Static
dashboard files may load without a token so the phone can display its token
entry control. The default token `icarus` is rejected. Configure the gateway's
`ICARUS_INTELLIGENCE_GATEWAY_TOKEN` to the same bearer token if phone commands
should work; its command identity must also be configured.

The router binds only to loopback and restores the loopback Host header for the
engine's existing DNS-rebinding guard. It checks every API/command bearer
against the engine before forwarding; invalid tokens and an unavailable engine
auth service fail closed. `/command` and `/v1/*` then route to the loopback
gateway on port 8792; dashboard and market APIs route to port 8791. The relay
accepts cross-origin requests only from the hosted phone-site origin
`https://icarus-command-center-mobile.cloudyrook1.chatgpt.site`; bearer-token
and JSON requests use a narrow HTTP preflight. It does not enable browser
cookies or allow arbitrary origins. The gateway command console appears only
if its server-side command identity is configured. The relay does not support
the separate intelligence WebSocket transport; the dashboard and semantic
command console use HTTP routes.

The tunnel URL changes when Cloudflare restarts the Quick Tunnel. Paste the new
URL into the phone's connection panel after restarting. Stopping the Git Bash
tunnel disconnects the phone. This does not change broker mode, authorize live
orders, or make the engine Internet-bound.
