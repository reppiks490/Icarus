from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


_SYMBOL = re.compile(r"^[A-Z0-9!._-]{1,24}$")


class UpstreamError(RuntimeError):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = int(status)
        self.detail = detail[:500]


class UpstreamClient:
    STATIC_ROUTES: dict[str, tuple[str, bool]] = {
        "/v1/status": ("/status/public", False),
        "/v1/briefing": ("/api/briefing", False),
        "/v1/system/audit": ("/api/system/audit", False),
        "/v1/brain": ("/api/brain", True),
        "/v1/apex": ("/api/apex", True),
        "/v1/learning/health": ("/api/learning/health", True),
        "/v1/engine-control": ("/api/engine-control", True),
        "/v1/integrity": ("/api/integrity", True),
        "/v1/research": ("/api/research", True),
        "/v1/possibility": ("/api/possibility", True),
        "/v1/chronofold": ("/api/chronofold", True),
        "/v1/commissioning": ("/api/commissioning", True),
        "/v1/pantheon": ("/api/pantheon", True),
        "/v1/sibyl": ("/api/sibyl", True),
        "/v1/performance-proof": ("/api/performance-proof", True),
        "/v1/latency": ("/api/latency", True),
        "/v1/source-reliability": ("/api/source-reliability", True),
    }

    def __init__(self, base_url: str, admin_token: str = "", timeout: float = 6.0) -> None:
        value = str(base_url or "").strip().rstrip("/")
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("invalid ICARUS engine URL")
        self.base_url = value
        self.admin_token = str(admin_token or "")
        self.timeout = max(1.0, min(float(timeout), 30.0))

    def _get(self, path: str, authenticated: bool = False, query: dict[str, str] | None = None) -> Any:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        headers = {"Accept": "application/json", "User-Agent": "icarus-mobile-gateway/0.1"}
        if authenticated:
            if not self.admin_token:
                raise UpstreamError(503, "gateway has no ICARUS admin token configured")
            headers["Authorization"] = "Bearer " + self.admin_token
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise UpstreamError(502, "ICARUS response exceeded gateway limit")
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as ex:
            raw = ex.read(65536)
            detail = f"ICARUS upstream returned HTTP {ex.code}"
            try:
                payload = json.loads(raw.decode("utf-8"))
                if isinstance(payload, dict):
                    detail = str(payload.get("detail") or payload.get("error") or detail)
            except Exception:
                pass
            raise UpstreamError(ex.code, detail) from ex
        except urllib.error.URLError as ex:
            raise UpstreamError(502, f"ICARUS upstream unavailable: {ex.reason}") from ex
        except json.JSONDecodeError as ex:
            raise UpstreamError(502, "ICARUS upstream returned invalid JSON") from ex

    def health(self) -> Any:
        return self._get("/healthz", False)

    @staticmethod
    def _clamped_int(query: dict[str, list[str]], key: str, default: int, lo: int, hi: int) -> str:
        try:
            value = int((query.get(key) or [str(default)])[0])
        except (TypeError, ValueError):
            value = default
        return str(max(lo, min(hi, value)))

    def mobile_get(self, path: str, query: dict[str, list[str]]) -> Any:
        static = self.STATIC_ROUTES.get(path)
        if static:
            upstream, auth = static
            forwarded: dict[str, str] = {}
            if path in {"/v1/possibility", "/v1/chronofold", "/v1/commissioning", "/v1/sibyl"}:
                asset = str((query.get("asset") or [""])[0]).strip().upper()
                if asset:
                    if not _SYMBOL.fullmatch(asset):
                        raise UpstreamError(400, "invalid asset")
                    forwarded["asset"] = asset
            return self._get(upstream, auth, forwarded)

        for prefix, upstream_prefix, key, default, lo, hi in (
            ("/v1/chart/", "/api/chart/", "n", 180, 20, 800),
            ("/v1/trades/", "/api/trades/", "limit", 100, 1, 500),
        ):
            if path.startswith(prefix):
                symbol = path[len(prefix):].strip().upper()
                if not _SYMBOL.fullmatch(symbol):
                    raise UpstreamError(400, "invalid asset")
                return self._get(
                    upstream_prefix + urllib.parse.quote(symbol, safe="!._-"),
                    False,
                    {key: self._clamped_int(query, key, default, lo, hi)},
                )
        raise UpstreamError(404, "unknown mobile resource")

    def snapshot(self) -> dict[str, Any]:
        payload = {
            "status": self._get("/status/public", False),
            "audit": self._get("/api/system/audit", False),
            "briefing": self._get("/api/briefing", False),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return {
            "cursor": hashlib.sha256(canonical).hexdigest()[:24],
            "generated_at": time.time(),
            **payload,
        }
