# Claude (Opus 5.5) — 2026-09-27. Plumbing shared by the slot trainers and their validators: digests, the
# execution lock, atomic writes and strict JSON reading.
from __future__ import annotations
import hashlib, json, math, os
from pathlib import Path

TOL = 1e-12                       # replayed numbers must match the report to this

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def code_digest(files) -> str:
    """Digest of source files under icarus_engine/, line endings normalised so checkouts agree."""
    root = Path(__file__).resolve().parents[1]
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode() + b"\0" + (root / rel).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()

def lock(report):
    report["execution_authorized"] = False
    report["accuracy_guaranteed"] = False
    return report

def write_json_atomic(path: Path, obj):
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, indent=2, allow_nan=False))
    os.replace(tmp, path)

def _no_constants(name):
    raise ValueError(f"non-finite number {name}")

def read_json(path: Path):
    """Parsed JSON, refusing NaN and Infinity. Raises OSError/ValueError."""
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=_no_constants)

def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

def close(a, b):
    return finite(a) and finite(b) and abs(a - b) <= TOL
