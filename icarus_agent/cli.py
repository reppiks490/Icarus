# Grok (xAI) — 2026-09-21. Whole file. Loopback HTTP sidecar for Field Agent recipes.
"""icarus-agent serve — 127.0.0.1:8799. GET /healthz, POST /queue copies a recipe log.

Does not scrape TradingView. Does not place broker orders. Does not bind 0.0.0.0.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PORT = 8799
HOST = "127.0.0.1"


class H(BaseHTTPRequestHandler):
    server_version = "icarus-agent"
    sys_version = ""

    def log_message(self, *_a: Any) -> None:
        pass

    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "").rsplit(":", 1)[0].strip("[]").lower()
        return host in ("127.0.0.1", "localhost", "::1")

    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8791")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_ok():
            return self._send(403, {"detail": "loopback only"})
        if self.path.split("?", 1)[0] == "/healthz":
            return self._send(200, {"ok": True, "agent": "icarus-field", "broker_armed": False})
        return self._send(404, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._host_ok():
            return self._send(403, {"detail": "loopback only"})
        if self.path.split("?", 1)[0] != "/queue":
            return self._send(404, {"detail": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(n, 8192)).decode("utf-8", "replace")
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return self._send(400, {"detail": "bad json"})
        recipe = str(payload.get("id") or "unknown")[:40]
        print(f"queued {recipe} (not executed — confirm on the desk)", flush=True)
        return self._send(200, {"queued": recipe, "executed": False, "broker_armed": False})


def main(argv: list[str] | None = None) -> int:
    os.environ.setdefault("ICARUS_AGENT", "1")
    httpd = ThreadingHTTPServer((HOST, PORT), H)
    print(f"icarus-agent loopback http://{HOST}:{PORT}/healthz  Ctrl+C to stop", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
