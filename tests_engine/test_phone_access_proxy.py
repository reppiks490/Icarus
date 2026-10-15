from __future__ import annotations

from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest

from icarus_engine.phone_access_proxy import create_handler

PHONE_ORIGIN = "https://icarus-command-center-mobile.cloudyrook1.chatgpt.site"
_TOKEN = "unique-phone-test-token-that-is-not-the-default"


class _StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    records: dict[str, list[dict]] = {}

    def _record(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        if self.path == "/api/access":
            status = 200 if self.headers.get("Authorization") == f"Bearer {_TOKEN}" else 401
            payload = b"{}"
        else:
            self.records[self.server.label].append({
                "method": self.command,
                "path": self.path,
                "headers": dict(self.headers.items()),
                "body": body,
            })
            status = 200
            payload = f"{self.server.label}:{self.path}".encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Set-Cookie", "upstream=private")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _record
    do_POST = _record
    do_PUT = _record
    do_PATCH = _record
    do_DELETE = _record

    def log_message(self, *_args):
        pass


@pytest.fixture
def phone_proxy():
    _StubHandler.records = {"engine": [], "gateway": []}
    servers = []
    threads = []
    try:
        ports = {}
        for label in ("engine", "gateway"):
            server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
            server.label = label
            servers.append(server)
            ports[label] = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            threads.append((server, thread))

        proxy = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(
            engine_port=ports["engine"], gateway_port=ports["gateway"],
        ))
        servers.append(proxy)
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        threads.append((proxy, thread))

        yield {
            "port": proxy.server_address[1],
            "ports": ports,
            "records": _StubHandler.records,
        }
    finally:
        for server in reversed(servers):
            server.shutdown()
            server.server_close()
        for _server, thread in threads:
            thread.join(timeout=2)


def _request(proxy_port: int, method: str, path: str, *, headers=None, body=None):
    conn = HTTPConnection("127.0.0.1", proxy_port, timeout=3)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ("/", "engine"),
        ("/api/state?asset=MNQ", "engine"),
        ("/command", "gateway"),
        ("/command/execute?name=flatten", "gateway"),
        ("/healthz", "gateway"),
        ("/v1/actions?limit=2", "gateway"),
        ("/v1", "engine"),
    ],
)
def test_routes_dashboard_and_command_console_to_the_intended_loopback_service(
    phone_proxy, path, target,
):
    status, headers, payload = _request(
        phone_proxy["port"], "GET", path,
        headers={"Host": f"localhost:{phone_proxy['port']}", "Authorization": f"Bearer {_TOKEN}"},
    )

    assert status == 200
    assert payload == f"{target}:{path}".encode()
    record = phone_proxy["records"][target][-1]
    assert record["headers"]["Host"] == f"127.0.0.1:{phone_proxy['ports'][target]}"
    assert headers["Cache-Control"] == "no-store"
    assert "Set-Cookie" not in headers


def test_dashboard_shell_bootstraps_without_a_token(phone_proxy):
    status, _headers, payload = _request(phone_proxy["port"], "GET", "/")

    assert status == 200
    assert payload == b"engine:/"


def test_forwards_command_body_and_safe_headers_but_strips_browser_and_proxy_identity(
    phone_proxy,
):
    body = b'{"command":"status"}'
    status, response_headers, payload = _request(
        phone_proxy["port"], "POST", "/command?source=phone", body=body,
        headers={
            "Host": f"127.0.0.1:{phone_proxy['port']}",
            "Authorization": f"Bearer {_TOKEN}",
            "Content-Type": "application/json",
            "Cookie": "session=browser-secret",
            "Origin": PHONE_ORIGIN,
            "Referer": "https://untrusted.example/page",
            "CF-Connecting-IP": "203.0.113.8",
            "CF-Ray": "private-ray-id",
            "X-Forwarded-For": "203.0.113.8",
            "X-Forwarded-Host": "untrusted.example",
            "X-Real-IP": "203.0.113.8",
            "X-Test-Trace": "keep-this",
        },
    )

    assert status == 200
    assert payload == b"gateway:/command?source=phone"
    assert response_headers["Access-Control-Allow-Origin"] == PHONE_ORIGIN
    assert "Access-Control-Allow-Credentials" not in response_headers
    record = phone_proxy["records"]["gateway"][-1]
    assert record["body"] == body
    assert record["headers"]["Authorization"] == f"Bearer {_TOKEN}"
    assert record["headers"]["Content-Type"] == "application/json"
    assert record["headers"]["X-Test-Trace"] == "keep-this"
    assert record["headers"]["Host"] == f"127.0.0.1:{phone_proxy['ports']['gateway']}"
    for private_header in (
        "Cookie", "Origin", "Referer", "CF-Connecting-IP", "CF-Ray",
        "X-Forwarded-For", "X-Forwarded-Host", "X-Real-IP",
    ):
        assert private_header not in record["headers"]


def test_allows_preflight_from_the_hosted_phone_site_without_contacting_upstream(phone_proxy):
    before = sum(map(len, phone_proxy["records"].values()))

    status, headers, payload = _request(
        phone_proxy["port"], "OPTIONS", "/command",
        headers={
            "Host": f"127.0.0.1:{phone_proxy['port']}",
            "Origin": PHONE_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )

    assert status == 204
    assert payload == b""
    assert headers["Access-Control-Allow-Origin"] == PHONE_ORIGIN
    assert headers["Access-Control-Allow-Methods"] == "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS"
    assert headers["Access-Control-Allow-Headers"] == "authorization, content-type"
    assert headers["Vary"] == "Origin"
    assert sum(map(len, phone_proxy["records"].values())) == before


def test_rejects_untrusted_cross_origin_requests(phone_proxy):
    before = sum(map(len, phone_proxy["records"].values()))

    status, _headers, payload = _request(
        phone_proxy["port"], "GET", "/api/state",
        headers={
            "Host": f"127.0.0.1:{phone_proxy['port']}",
            "Origin": "https://untrusted.example",
        },
    )

    assert status == 403
    assert payload == b"origin rejected"
    assert sum(map(len, phone_proxy["records"].values())) == before


@pytest.mark.parametrize(
    ("method", "headers", "expected_status"),
    [
        ("TRACE", "authorization", 405),
        ("POST", "authorization, x-forwarded-for", 400),
    ],
)
def test_preflight_rejects_unsupported_methods_and_headers(phone_proxy, method, headers, expected_status):
    status, _response_headers, payload = _request(
        phone_proxy["port"], "OPTIONS", "/command",
        headers={
            "Host": f"127.0.0.1:{phone_proxy['port']}",
            "Origin": PHONE_ORIGIN,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        },
    )

    assert status == expected_status
    assert payload


@pytest.mark.parametrize("host", ["evil.example", "127.0.0.1.evil.example", "[::1].evil:8790"])
def test_rejects_non_loopback_host_without_contacting_an_upstream(phone_proxy, host):
    before = sum(map(len, phone_proxy["records"].values()))

    status, _headers, payload = _request(
        phone_proxy["port"], "GET", "/api/state", headers={"Host": host},
    )

    assert status == 400
    assert payload == b"host rejected"
    assert sum(map(len, phone_proxy["records"].values())) == before


def test_rejects_default_token_before_routing(phone_proxy):
    before = sum(map(len, phone_proxy["records"].values()))

    status, _headers, payload = _request(
        phone_proxy["port"], "POST", "/command",
        headers={
            "Host": f"127.0.0.1:{phone_proxy['port']}",
            "Authorization": "bEaReR icarus",
        },
        body=b"{}",
    )

    assert status == 428
    assert b"strong, unique" in payload
    assert sum(map(len, phone_proxy["records"].values())) == before


@pytest.mark.parametrize("path", ["/status/public", "/api/state", "/command", "/v1/actions"])
@pytest.mark.parametrize("authorization", [None, "Basic abc", "Bearer   "])
def test_rejects_missing_or_empty_bearer_on_data_and_command_routes(
    phone_proxy, path, authorization,
):
    before = sum(map(len, phone_proxy["records"].values()))
    headers = {"Host": f"127.0.0.1:{phone_proxy['port']}"}
    if authorization is not None:
        headers["Authorization"] = authorization

    status, _headers, payload = _request(phone_proxy["port"], "GET", path, headers=headers)

    assert status == 401
    assert payload == b"bearer token required"
    assert sum(map(len, phone_proxy["records"].values())) == before


def test_rejects_invalid_bearer_after_engine_registry_check(phone_proxy):
    before = sum(map(len, phone_proxy["records"].values()))

    status, _headers, payload = _request(
        phone_proxy["port"], "GET", "/status/public",
        headers={
            "Host": f"127.0.0.1:{phone_proxy['port']}",
            "Authorization": "Bearer attacker-chosen-token",
        },
    )

    assert status == 401
    assert payload == b"invalid bearer token"
    assert sum(map(len, phone_proxy["records"].values())) == before


@pytest.mark.parametrize(
    ("headers", "expected_status", "expected_body"),
    [
        ({"Content-Length": "not-a-number"}, 400, b"invalid content length"),
        ({"Content-Length": "8388609"}, 413, b"request too large"),
        ({"Upgrade": "websocket"}, 501, b"websocket relay is not supported"),
    ],
)
def test_rejects_invalid_large_or_websocket_requests_without_upstream_contact(
    phone_proxy, headers, expected_status, expected_body,
):
    before = sum(map(len, phone_proxy["records"].values()))
    request_headers = {
        "Host": f"127.0.0.1:{phone_proxy['port']}",
        "Authorization": f"Bearer {_TOKEN}",
        **headers,
    }

    status, _response_headers, payload = _request(
        phone_proxy["port"], "GET", "/v1/actions", headers=request_headers,
    )

    assert status == expected_status
    assert payload == expected_body
    assert sum(map(len, phone_proxy["records"].values())) == before
