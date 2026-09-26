"""Deterministic, strict JSON canonicalization for ICARUS receipts."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented by the ICARUS v1 canonical form."""


def _reject_constant(value: str) -> None:
    raise CanonicalizationError(f"non-finite JSON number is forbidden: {value}")


def _reject_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise CanonicalizationError(f"duplicate JSON object key: {key}")
        out[key] = value
    return out


def _validate(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError(f"non-finite number at {path}")
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            _validate(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(f"non-string object key at {path}: {key!r}")
            _validate(item, f"{path}.{key}")
        return
    raise CanonicalizationError(
        f"unsupported canonical JSON type at {path}: {type(value).__name__}"
    )


def canonical_json(value: Any) -> str:
    """Return the v1 canonical JSON representation.

    Object keys are sorted recursively, arrays retain order, separators are compact,
    UTF-8 characters remain unescaped, and non-finite numbers are forbidden.
    """
    _validate(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def sha256_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def receipt_digest(receipt: dict[str, Any]) -> str:
    """Digest a receipt while excluding only its self-referential digest field."""
    if not isinstance(receipt, dict):
        raise CanonicalizationError("receipt must be a JSON object")
    payload = dict(receipt)
    payload.pop("receipt_digest", None)
    return sha256_digest(payload)


def loads_strict(text: str) -> Any:
    """Parse JSON without duplicate keys or NaN/Infinity extensions."""
    try:
        return json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except CanonicalizationError:
        raise
    except json.JSONDecodeError as exc:
        raise CanonicalizationError(str(exc)) from exc


def load_json(path: str | Path) -> Any:
    return loads_strict(Path(path).read_text(encoding="utf-8"))
