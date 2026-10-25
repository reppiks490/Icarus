from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Callable


class AuthError(ValueError):
    pass


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode((text + pad).encode("ascii"))
    except Exception as ex:
        raise AuthError("malformed token") from ex


def load_or_create_key(path: str | os.PathLike[str]) -> bytes:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raw = target.read_bytes()
        if len(raw) < 32:
            raise AuthError("mobile gateway signing key is invalid")
        return raw
    raw = secrets.token_bytes(32)
    try:
        os.write(fd, raw)
    finally:
        os.close(fd)
    return raw


class SessionSigner:
    def __init__(
        self,
        key: bytes,
        ttl: int = 900,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if len(key) < 32:
            raise ValueError("session key must be at least 32 bytes")
        self.key = key
        self.ttl = max(60, min(int(ttl), 3600))
        self.clock = clock

    def issue(self, device_id: str) -> tuple[str, int]:
        if not device_id or len(device_id) > 128:
            raise AuthError("invalid device id")
        now = int(self.clock())
        payload = {
            "v": 1,
            "sub": device_id,
            "iat": now,
            "exp": now + self.ttl,
            "jti": secrets.token_urlsafe(9),
        }
        body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        sig = _b64e(hmac.new(self.key, body.encode("ascii"), hashlib.sha256).digest())
        return body + "." + sig, payload["exp"]

    def verify(self, token: str) -> dict[str, object]:
        body, dot, sig_text = str(token or "").partition(".")
        if not dot or not body or not sig_text:
            raise AuthError("malformed session")
        expected = hmac.new(self.key, body.encode("ascii"), hashlib.sha256).digest()
        supplied = _b64d(sig_text)
        if not hmac.compare_digest(expected, supplied):
            raise AuthError("invalid session signature")
        try:
            payload = json.loads(_b64d(body).decode("utf-8"))
        except Exception as ex:
            raise AuthError("invalid session payload") from ex
        if not isinstance(payload, dict) or payload.get("v") != 1:
            raise AuthError("unsupported session")
        sub = payload.get("sub")
        exp = payload.get("exp")
        iat = payload.get("iat")
        if not isinstance(sub, str) or not sub:
            raise AuthError("invalid session subject")
        if not isinstance(exp, int) or not isinstance(iat, int):
            raise AuthError("invalid session timestamps")
        now = int(self.clock())
        if iat > now + 30:
            raise AuthError("session issued in the future")
        if exp <= now:
            raise AuthError("session expired")
        return payload
