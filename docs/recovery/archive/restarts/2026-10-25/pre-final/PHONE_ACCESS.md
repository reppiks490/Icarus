> **Archived phone relay instructions — superseded 2026-10-25.** Do not run these commands; they target a retired relay/tunnel flow. Use [current phone access notes](../../../../../PHONE_ACCESS.md) and the [mobile gateway guide](../../../../../icarus/MOBILE_WINDOWS.md).

# ICARUS phone connection — current working-engine path

Keep the existing desktop engine and its launcher running. These commands start phone access independently; they do not switch the checkout, apply Inputs, reinstall Python packages or restart the engine.

Phone relay source: `8ec6199d0133db345b4ea81ef89f7519b3bf238f`, file `icarus_engine/phone_access_proxy.py`, SHA256 `568e11f718a202609c81309f90b7ff76d4a54d6156d89dd81ac032e243636464`. Fetch branch `prime/as-is-restart-20261022`. The launch block executes that verified standard-library-only file directly from Git, so a running PC does not need a source update to receive the mobile compatibility correction.

## 1. Prepare a phone token on the PC

Open Main at <http://127.0.0.1:8791/>. For observation, use **Access → Add viewer**, label it **Phone**, and copy the newly generated token privately. It appears once. A viewer has read-only dashboard access. An existing strong, active token also works. The default token `icarus` is rejected by the relay; no credential rotation or restart is performed by this procedure.

## 2. Start the relay in a new Git Bash window

The known source is `C:/Users/tripl/Icarus-as-is`; the existing interpreter is `.venv/Scripts/python.exe`. Paste the entire block, then enter the phone token at the hidden prompt. The block verifies warm engine health, authenticated status, source bytes and relay-port availability before serving. If any check fails, keep its output for diagnosis. It does not kill an existing process.

```bash
(
set +x
set -euo pipefail
cd /c/Users/tripl/Icarus-as-is
ICARUS_PHONE_REV='8ec6199d0133db345b4ea81ef89f7519b3bf238f'
ICARUS_PHONE_DIGEST='568e11f718a202609c81309f90b7ff76d4a54d6156d89dd81ac032e243636464'
ICARUS_PHONE_PY="$PWD/.venv/Scripts/python.exe"
test -f "$ICARUS_PHONE_PY"
git fetch --quiet origin prime/as-is-restart-20261022
read -r -s -p 'Phone viewer token (hidden): ' ICARUS_PHONE_CHECK_TOKEN </dev/tty
printf '\n'
export ICARUS_PHONE_CHECK_TOKEN
git show "${ICARUS_PHONE_REV}:icarus_engine/phone_access_proxy.py" |
  PYTHONUTF8=1 "$ICARUS_PHONE_PY" -c '
import hashlib, http.client, json, os, socket, sys
source = sys.stdin.buffer.read()
if hashlib.sha256(source).hexdigest() != sys.argv[1]:
    raise SystemExit("STOP: phone relay source verification failed.")
token = os.environ.pop("ICARUS_PHONE_CHECK_TOKEN", "").strip()
if not token or token == "icarus":
    raise SystemExit("STOP: use the strong Phone viewer token from Main > Access > Add viewer.")
def probe(path, authenticated=False):
    conn = http.client.HTTPConnection("127.0.0.1", 8791, timeout=10)
    try:
        headers = {"Authorization": "Bearer " + token} if authenticated else {}
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        if response.status != 200:
            raise SystemExit("STOP: engine " + path + " returned HTTP " + str(response.status))
        return json.loads(response.read(32 * 1024 * 1024))
    except (OSError, http.client.HTTPException, ValueError):
        raise SystemExit("STOP: local engine is unavailable or did not answer within 10 seconds. Keep the desktop launcher open.") from None
    finally:
        conn.close()
health = probe("/healthz")
if not isinstance(health, dict) or health.get("ok") is not True or health.get("warm") is not True or not health.get("assets"):
    raise SystemExit("STOP: engine is not ready yet. Leave it running and retry after warmup.")
if not isinstance(probe("/status/public", True), dict):
    raise SystemExit("STOP: authenticated engine status was invalid.")
del token
with socket.socket() as port:
    if os.name != "nt":
        port.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        port.bind(("127.0.0.1", 8790))
    except OSError:
        raise SystemExit("STOP: phone port 8790 is occupied. Keep the output; do not stop the desktop engine.") from None
print("Engine ready; authenticated status HTTP 200. Starting verified phone relay on 8790; keep this window open.", flush=True)
sys.argv = ["icarus-phone-relay", "--host", "127.0.0.1", "--port", "8790"]
exec(compile(source, "verified-phone-access-proxy", "exec"), {"__name__": "__main__"})
' "$ICARUS_PHONE_DIGEST"
)
```

Leave this window open. Success prints **Engine ready; authenticated status HTTP 200** and **phone relay listening** on loopback port 8790. A busy 8790 may mean a previous relay is still running; identify that relay rather than stopping the engine. If Icarus is stopped, its existing launcher must run before phone pairing can continue.

## 3. Start the tunnel in another Git Bash window

```bash
(
set -euo pipefail
curl --noproxy 127.0.0.1 --fail --silent --show-error --max-time 10 -o /dev/null http://127.0.0.1:8790/
cloudflared tunnel --url http://127.0.0.1:8790 --http-host-header 127.0.0.1:8790
)
```

Leave this window open too. Cloudflared prints a fresh HTTPS `https://….trycloudflare.com` address. If `cloudflared` is not found, install the official Windows package with `winget install --id Cloudflare.cloudflared --exact --source winget`, reopen this extra terminal, and retry the tunnel block. Installation is needed only when the existing executable is absent.

## 4. Pair the phone

Open <https://icarus-command-center-mobile.cloudyrook1.chatgpt.site> in the phone browser using the account that owns the private Site. Open **Connect this phone to the engine**, paste the new tunnel URL, and choose **Connect**. Enter the same phone token through **Token** on the dashboard. Keep tokens out of chat, screenshots and URLs.

Confirm an asset observation updates and try one CC view before opening more views. Closing or refreshing the mobile page does not restart the engine. Keep the PC awake, and keep the engine, relay and tunnel windows open. Restarting the Quick Tunnel changes its URL, which must be paired again.

The hosted Site supplies its own UI bundle; this cloud session cannot verify its private logged-in page or certify that every newly added desktop panel is present there. If it refuses access or the observation remains disconnected, retain the visible message and tunnel output. Actual phone pairing is not yet certified by the cloud checks.

## Routing and authentication

Engine health is `http://127.0.0.1:8791/healthz`. Relay readiness is `http://127.0.0.1:8790/`; relay `/healthz` routes to the optional command gateway on 8792 and is not an engine-readiness check. Dashboard observation needs only engine 8791. Commands need separately configured gateway 8792 identity and authorization; this procedure does not enable it.

Use the hosted Site's pairing panel. Directly opening the tunnel URL can load a dashboard shell but its mutation Origin differs from the relay's configured hosted-Site Origin. The relay keeps the exact hosted Origin, bearer authentication and authoritative engine validation. Updated CORS permits only authorization, content-type, X-Icarus-Workspace and X-Icarus-Config-Revision; CSV responses expose their two workspace identity headers. It does not forward cookies or enable credentialed CORS. The relay remains loopback-only; the tunnel URL is publicly reachable and does not create a Cloudflare Access policy. Protected APIs require an active strong token.

## Verification and stopping point

The relay correction passed all 37 real HTTP proxy checks, including three regressions reproduced against the prior source, plus an independent three-case regression rerun. The actual Python 3.10 launch rehearsal passed seven cases covering credential refusal, warmup refusal, workspace preflights and authenticated relay access. Shell syntax and embedded Python 3.10 compilation passed. These checks do not establish physical PC/phone connectivity.

The current paper restart release gate and exact source revision are in the [Prime as-is restart guide](../../../../PRIME_AS_IS_RESTART.md). Its candidate contains the same phone relay source pinned above. Complete the desktop restart and health/warm checks there before pairing; do not use this phone-only procedure to switch code or restart a working engine. Physical phone pairing remains an owner-PC verification. No live broker authority, new provider subscription or permanent network configuration is changed.
