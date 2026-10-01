from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class DeviceStore:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.path.exists():
            self._write({"version": 1, "devices": {}})

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            value = {"version": 1, "devices": {}}
        if not isinstance(value, dict) or not isinstance(value.get("devices"), dict):
            raise ValueError("mobile device store is corrupt")
        return value

    def _write(self, value: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def pair(self, name: str) -> tuple[str, str]:
        label = " ".join(str(name or "").strip().split())[:80] or "ICARUS Mobile"
        device_id = secrets.token_urlsafe(12)
        refresh = secrets.token_urlsafe(32)
        now = int(time.time())
        with self._lock:
            state = self._read()
            devices = state["devices"]
            active_count = sum(1 for row in devices.values() if not row.get("revoked_at"))
            if active_count >= 64:
                raise ValueError("mobile device limit reached")
            devices[device_id] = {
                "name": label,
                "refresh_hash": _hash_refresh(refresh),
                "created_at": now,
                "last_refresh_at": now,
                "revoked_at": None,
            }
            self._write(state)
        return device_id, refresh

    def rotate_refresh(self, device_id: str, refresh_token: str) -> str:
        with self._lock:
            state = self._read()
            row = state["devices"].get(device_id)
            if not isinstance(row, dict) or row.get("revoked_at"):
                raise ValueError("unknown or revoked device")
            expected = str(row.get("refresh_hash") or "")
            supplied = _hash_refresh(str(refresh_token or ""))
            if not expected or not hmac.compare_digest(expected, supplied):
                raise ValueError("invalid refresh credential")
            new_token = secrets.token_urlsafe(32)
            row["refresh_hash"] = _hash_refresh(new_token)
            row["last_refresh_at"] = int(time.time())
            self._write(state)
            return new_token

    def active(self, device_id: str) -> bool:
        with self._lock:
            row = self._read()["devices"].get(device_id)
            return isinstance(row, dict) and not bool(row.get("revoked_at"))

    def revoke(self, device_id: str) -> bool:
        with self._lock:
            state = self._read()
            row = state["devices"].get(device_id)
            if not isinstance(row, dict) or row.get("revoked_at"):
                return False
            row["revoked_at"] = int(time.time())
            self._write(state)
            return True

    def list_devices(self) -> list[dict[str, Any]]:
        with self._lock:
            devices = self._read()["devices"]
            out = []
            for device_id, row in devices.items():
                out.append({
                    "device_id": device_id,
                    "name": row.get("name"),
                    "created_at": row.get("created_at"),
                    "last_refresh_at": row.get("last_refresh_at"),
                    "revoked_at": row.get("revoked_at"),
                    "active": not bool(row.get("revoked_at")),
                })
            return sorted(out, key=lambda row: int(row.get("created_at") or 0), reverse=True)
