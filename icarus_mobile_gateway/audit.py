from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any


class GatewayAuditLog:
    """Append-only, secret-free gateway security and analysis receipts."""

    def __init__(self, path: str | os.PathLike[str], max_bytes: int = 2 * 1024 * 1024) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max(64 * 1024, int(max_bytes))
        self._lock = threading.RLock()

    @staticmethod
    def _text(value: Any, limit: int) -> str:
        return " ".join(str(value or "").split())[:limit]

    def record(
        self,
        event: str,
        *,
        status: str = "ok",
        device_id: str = "",
        detail: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        row = {
            "ts": time.time(),
            "event": self._text(event, 80),
            "status": self._text(status, 40),
        }
        if device_id:
            row["device_id"] = self._text(device_id, 128)
        if detail:
            row["detail"] = self._text(detail, 500)
        if metadata:
            safe = json.loads(json.dumps(metadata, allow_nan=False, default=str))
            encoded = json.dumps(safe, separators=(",", ":"), sort_keys=True)
            row["metadata"] = json.loads(encoded[:4096]) if len(encoded) <= 4096 else {"truncated": True}

        line = json.dumps(row, separators=(",", ":"), sort_keys=True, allow_nan=False) + "\n"
        with self._lock:
            if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                rotated = self.path.with_suffix(self.path.suffix + ".1")
                try:
                    rotated.unlink()
                except FileNotFoundError:
                    pass
                os.replace(self.path, rotated)
                try:
                    os.chmod(rotated, 0o600)
                except OSError:
                    pass
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def tail(self, limit: int = 100) -> list[dict[str, Any]]:
        count = max(1, min(int(limit), 500))
        with self._lock:
            try:
                lines = self.path.read_text(encoding="utf-8").splitlines()[-count:]
            except FileNotFoundError:
                return []
        out: list[dict[str, Any]] = []
        for line in lines:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                out.append(row)
        return out
