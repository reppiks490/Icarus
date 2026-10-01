from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any


EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_TOKEN = re.compile(r"^(?:Expo|Exponent)PushToken\[[A-Za-z0-9_-]{8,256}\]$")


def validate_push_token(token: str) -> str:
    value = str(token or "").strip()
    if not _TOKEN.fullmatch(value):
        raise ValueError("invalid Expo push token")
    return value


def system_alerts(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    if not previous:
        return []
    alerts: list[dict[str, Any]] = []
    if not previous.get("error") and current.get("error"):
        alerts.append({
            "title": "ICARUS gateway degraded",
            "body": "The mobile gateway cannot refresh the ICARUS snapshot.",
            "data": {"kind": "gateway_error"},
        })

    prev_audit = str((previous.get("audit") or {}).get("status") or "").lower()
    next_audit = str((current.get("audit") or {}).get("status") or "").lower()
    bad = {"red", "failed", "failure", "critical", "degraded"}
    if next_audit in bad and next_audit != prev_audit:
        alerts.append({
            "title": "ICARUS system alert",
            "body": f"System audit changed to {next_audit}.",
            "data": {"kind": "system_audit", "status": next_audit},
        })

    prev_status = previous.get("status") if isinstance(previous.get("status"), dict) else {}
    next_status = current.get("status") if isinstance(current.get("status"), dict) else {}
    if not prev_status.get("paused") and next_status.get("paused"):
        alerts.append({
            "title": "ICARUS paused",
            "body": "The engine reports a global pause state.",
            "data": {"kind": "engine_paused"},
        })
    if prev_status.get("all_warm") is True and next_status.get("all_warm") is False:
        alerts.append({
            "title": "ICARUS warm state changed",
            "body": "One or more running assets are no longer fully warm.",
            "data": {"kind": "warm_state_lost"},
        })

    prev_assets = {
        str(row.get("symbol") or ""): row
        for row in (prev_status.get("assets") or [])
        if isinstance(row, dict)
    }
    for row in next_status.get("assets") or []:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        err = str(row.get("last_error") or "").strip()
        before = prev_assets.get(symbol, {})
        old_err = str(before.get("last_error") or "").strip() if isinstance(before, dict) else ""
        if symbol and err and err != old_err:
            alerts.append({
                "title": f"{symbol} runtime alert",
                "body": err[:180],
                "data": {"kind": "asset_error", "asset": symbol},
            })
    return alerts[:8]


class ExpoPushClient:
    def __init__(self, access_token: str = "", timeout: float = 5.0) -> None:
        self.access_token = str(access_token or "").strip()
        self.timeout = max(1.0, min(float(timeout), 15.0))

    def send(self, tokens: list[str], *, title: str, body: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        clean: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            try:
                value = validate_push_token(token)
            except ValueError:
                continue
            if value not in seen:
                seen.add(value)
                clean.append(value)
        if not clean:
            return {"ok": True, "sent": 0}
        messages = [{
            "to": token,
            "title": str(title)[:100],
            "body": str(body)[:500],
            "data": data or {},
            "sound": "default",
            "channelId": "system",
        } for token in clean[:100]]
        raw = json.dumps(messages, separators=(",", ":"), allow_nan=False).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "icarus-mobile-gateway/0.1",
        }
        if self.access_token:
            headers["Authorization"] = "Bearer " + self.access_token
        req = urllib.request.Request(EXPO_PUSH_URL, data=raw, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = response.read(1024 * 1024)
                decoded = json.loads(payload.decode("utf-8")) if payload else {}
                return {"ok": True, "sent": len(messages), "response": decoded}
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as ex:
            return {"ok": False, "sent": 0, "error": f"{type(ex).__name__}: {ex}"[:500]}
