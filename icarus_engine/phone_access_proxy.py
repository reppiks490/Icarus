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
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        def _proxy(self) -> None:
            if not self._host_is_loopback():
                self._respond(400, b"host rejected")
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

            parsed = urlsplit(self.path)
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
                    if low not in _HOP_HEADERS | {"set-cookie", "server", "content-length"}:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
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
