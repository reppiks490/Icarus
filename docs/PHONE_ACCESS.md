# ICARUS phone command center

The hosted phone UI is private to the Site owner:

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
cookie and local storage; it is not placed in the page URL. The engine bearer
token is still required in **⚙︎ Token** and is sent only over HTTPS. The relay
rejects the default token `icarus`; configure a strong, unique owner token
before enabling the public tunnel.

The router binds only to loopback and restores the loopback Host header for the
engine's existing DNS-rebinding guard. `/command` and `/v1/*` route to the
loopback gateway on port 8792; dashboard and market APIs route to port 8791.
The gateway command console appears only if its server-side command identity
is configured. The relay does not support the separate intelligence WebSocket
transport; the dashboard and semantic command console use HTTP routes.

The tunnel URL changes when Cloudflare restarts the Quick Tunnel. Paste the new
URL into the phone's connection panel after restarting. Stopping the Git Bash
tunnel disconnects the phone. This does not change broker mode, authorize live
orders, or make the engine Internet-bound.
