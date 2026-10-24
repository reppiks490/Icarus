"""Loopback-only HTTP router for the private ICARUS phone Site tunnel.

This is not an Internet-facing server. Cloudflare Tunnel connects to this
loopback listener; it routes the trading dashboard to port 8791 and the
semantic command console to the gateway on port 8792 while restoring the
loopback Host header expected by both services.
"""
from __future__ import annotations

import argparse
import http.client
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

LOG = logging.getLogger("icarus.phone_access_proxy")
_MAX_REQUEST_BYTES = 8 * 1024 * 1024
_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
_PHONE_ORIGIN = "https://icarus-command-center-mobile.cloudyrook1.chatgpt.site"
_CORS_METHODS = "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS"
_CORS_HEADERS = {
    "authorization", "content-type", "x-icarus-workspace", "x-icarus-config-revision",
}
_CORS_EXPOSE_HEADERS = "X-Icarus-Workspace, X-Icarus-Config-Revision"
_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length",
}
_PRIVATE_REQUEST_HEADERS = {
    "cookie", "origin", "referer", "cf-connecting-ip", "cf-ray",
    "x-forwarded-for", "x-forwarded-host", "x-real-ip",
}


def _gateway_path(path: str) -> bool:
    return (
        path == "/command" or path.startswith("/command/")
        or path == "/healthz" or path.startswith("/v1/")
    )


def _requires_bearer(path: str) -> bool:
    """Keep the dashboard shell public so it can collect a token; protect APIs."""
    return path.startswith(("/api/", "/admin/", "/command", "/v1/")) or path in {
        "/status/public", "/healthz", "/v1",
    }


def _engine_accepts_bearer(engine_port: int, bearer: str) -> bool | None:
    """Validate the supplied token against the engine's access registry.

    Returns None only when the local engine cannot be reached. The relay must
    fail closed in that case rather than treating token presence as identity.
    """
    conn = http.client.HTTPConnection("127.0.0.1", engine_port, timeout=5)
    try:
        conn.request("GET", "/_internal/access/validate", headers={
            "Authorization": f"Bearer {bearer}",
            "Host": f"127.0.0.1:{engine_port}",
            "Connection": "close",
        })
        response = conn.getresponse()
        response.read(1024 * 1024)
        return response.status == 200
    except (OSError, http.client.HTTPException):
        return None
    finally:
        conn.close()


def create_handler(*, engine_port: int, gateway_port: int):
    class PhoneAccessHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "ICARUSPhoneRelay"
        sys_version = ""

        def log_message(self, fmt: str, *args) -> None:
            # Avoid logging request headers, query values, or bearer credentials.
            LOG.info("%s %s", self.command, urlsplit(self.path).path)

        def _host_is_loopback(self) -> bool:
            host = self.headers.get("Host", "").rsplit(":", 1)[0].strip("[]").lower()
            return host in {"127.0.0.1", "localhost", "::1"}

        def _respond(self, status: int, payload: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            origin = self.headers.get("Origin")
            if origin == _PHONE_ORIGIN:
                self.send_header("Access-Control-Allow-Origin", _PHONE_ORIGIN)
                self.send_header("Access-Control-Expose-Headers", _CORS_EXPOSE_HEADERS)
                self.send_header("Vary", "Origin")
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        def _preflight(self) -> None:
            if not self._host_is_loopback():
                self._respond(400, b"host rejected")
                return
            if self.headers.get("Origin") != _PHONE_ORIGIN:
                self._respond(403, b"origin rejected")
                return
            method = self.headers.get("Access-Control-Request-Method", "").upper()
            if method not in set(_CORS_METHODS.split(", ")) - {"OPTIONS"}:
                self._respond(405, b"preflight method rejected")
                return
            requested_headers = {
                value.strip().lower()
                for value in self.headers.get("Access-Control-Request-Headers", "").split(",")
                if value.strip()
            }
            if not requested_headers.issubset(_CORS_HEADERS):
                self._respond(400, b"preflight headers rejected")
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", _PHONE_ORIGIN)
            self.send_header("Access-Control-Allow-Methods", _CORS_METHODS)
            self.send_header("Access-Control-Allow-Headers", ", ".join(sorted(_CORS_HEADERS)))
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()

        def _proxy(self) -> None:
            if not self._host_is_loopback():
                self._respond(400, b"host rejected")
                return
            origin = self.headers.get("Origin")
            if origin and origin != _PHONE_ORIGIN:
                self._respond(403, b"origin rejected")
                return
            if self.headers.get("Upgrade", "").lower() == "websocket":
                self._respond(501, b"websocket relay is not supported")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._respond(400, b"invalid content length")
                return
            if length < 0 or length > _MAX_REQUEST_BYTES:
                self._respond(413, b"request too large")
                return
            scheme, _, bearer = self.headers.get("Authorization", "").partition(" ")
            parsed = urlsplit(self.path)
            if parsed.path == "/_internal/access/validate":
                self._respond(404, b"not found")
                return
            if _requires_bearer(parsed.path) and (scheme.lower() != "bearer" or not bearer.strip()):
                self._respond(401, b"bearer token required")
                return
            if scheme.lower() == "bearer" and bearer.strip() == "icarus":
                self._respond(428, b"configure a strong, unique ICARUS token before enabling phone access")
                return
            if _requires_bearer(parsed.path):
                authenticated = _engine_accepts_bearer(engine_port, bearer.strip())
                if authenticated is None:
                    self._respond(503, b"engine authentication service unavailable")
                    return
                if not authenticated:
                    self._respond(401, b"invalid bearer token")
                    return

            if not parsed.path.startswith("/") or parsed.path.startswith("//"):
                self._respond(400, b"invalid path")
                return
            port = gateway_port if _gateway_path(parsed.path) else engine_port
            body = self.rfile.read(length) if length else None
            headers = {
                key: value for key, value in self.headers.items()
                if key.lower() not in _HOP_HEADERS | _PRIVATE_REQUEST_HEADERS
            }
            headers["Host"] = f"127.0.0.1:{port}"
            headers["Connection"] = "close"
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
            try:
                conn.request(self.command, self.path, body=body, headers=headers)
                upstream = conn.getresponse()
                payload = upstream.read(_MAX_RESPONSE_BYTES + 1)
                if len(payload) > _MAX_RESPONSE_BYTES:
                    self._respond(502, b"upstream response too large")
                    return
                self.send_response(upstream.status)
                for key, value in upstream.getheaders():
                    low = key.lower()
                    if (low not in _HOP_HEADERS | {"set-cookie", "server", "content-length"}
                            and not low.startswith("access-control-")):
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                if origin == _PHONE_ORIGIN:
                    self.send_header("Access-Control-Allow-Origin", _PHONE_ORIGIN)
                    self.send_header("Access-Control-Expose-Headers", _CORS_EXPOSE_HEADERS)
                    self.send_header("Vary", "Origin")
                self.send_header("Connection", "close")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(payload)
            except (OSError, http.client.HTTPException) as exc:
                LOG.warning("upstream unavailable (%s)", type(exc).__name__)
                self._respond(502, b"ICARUS local service unavailable")
            finally:
                conn.close()

        do_GET = _proxy
        do_HEAD = _proxy
        do_OPTIONS = _preflight
        do_POST = _proxy
        do_PUT = _proxy
        do_PATCH = _proxy
        do_DELETE = _proxy

    return PhoneAccessHandler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Loopback router for ICARUS private phone access")
    parser.add_argument("--host", default="127.0.0.1", help="must remain loopback")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--engine-port", type=int, default=8791)
    parser.add_argument("--gateway-port", type=int, default=8792)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("phone relay must bind to loopback")
    if any(not 1 <= port <= 65535 for port in (args.port, args.engine_port, args.gateway_port)):
        parser.error("ports must be in 1..65535")
    server = ThreadingHTTPServer((args.host, args.port), create_handler(
        engine_port=args.engine_port, gateway_port=args.gateway_port,
    ))
    LOG.info("loopback phone relay listening at http://%s:%s", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
