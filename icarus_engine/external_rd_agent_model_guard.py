"""Offline, fail-closed RD-Agent local model *plan* admission (never executes models).

This checks proposed loopback-only chat/embedding endpoints against a local
RD-Agent host preflight. A successful structural review is not a runtime,
license, provenance, model-compatibility, or execution authorization.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

GIB = 1024 ** 3
MAX_INTEGER = 2**53 - 1
PLAN_KEYS = frozenset({
    "schema_version", "target", "concurrent_requests", "chat", "embedding",
    "estimated_peak_memory_bytes", "required_free_disk_bytes",
})
MODEL_KEYS = frozenset({"model_id", "endpoint", "estimated_memory_bytes"})
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z", re.ASCII)


def _positive_integer(value: object) -> bool:
    return type(value) is int and 0 < value <= MAX_INTEGER


def _nonnegative_integer(value: object) -> bool:
    return type(value) is int and 0 <= value <= MAX_INTEGER


def _local_endpoint(value: object) -> bool:
    if not isinstance(value, str) or not value or any(
        ord(ch) <= 32 or ord(ch) > 126 or ch in "\\%" for ch in value
    ):
        return False
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "http" or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment
                or parsed.path not in ("/v1", "/v1/") or parsed.port is None):
            return False
        host = parsed.hostname
        return host is not None and ipaddress.ip_address(host) in (
            ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")
        ) and 1 <= parsed.port <= 65535
    except (ValueError, TypeError):
        return False


def assess_plan(preflight: object, plan: object) -> dict:
    """Return only bounded, non-sensitive verdict codes, never input values."""
    failures: list[str] = []
    if not isinstance(preflight, dict) or preflight.get("schema_version") != "icarus-rdagent-host-preflight-v1":
        failures.append("PREFLIGHT_SCHEMA_INVALID")
    if not isinstance(plan, dict) or set(plan) != PLAN_KEYS or plan.get("schema_version") != "icarus-rdagent-local-model-plan-v1":
        failures.append("PLAN_SCHEMA_INVALID")
    if failures:
        return _result(failures)

    assert isinstance(preflight, dict) and isinstance(plan, dict)
    memory = preflight.get("memory_bytes")
    disk = preflight.get("disk_bytes")
    if not isinstance(memory, dict) or not isinstance(disk, dict):
        failures.append("HOST_CAPACITY_MISSING")
    else:
        total = memory.get("effective_total")
        available = memory.get("effective_available")
        disk_free = disk.get("available")
        if (not _positive_integer(total) or not _nonnegative_integer(available)
                or not _nonnegative_integer(disk_free) or available > total):
            failures.append("HOST_CAPACITY_INCONSISTENT")
        elif (preflight.get("resource_state") != "CAPACITY_MEASURED_NOT_MODEL_QUALIFIED"
              or available < 12 * GIB or disk_free < 25 * GIB):
            failures.append("HOST_CAPACITY_CONSTRAINED")
    if (plan.get("target") != "WSL2" or preflight.get("os") != "Linux"
            or preflight.get("wsl") is not True):
        failures.append("TARGET_HOST_NOT_WSL2")
    if plan.get("concurrent_requests") != 1 or type(plan.get("concurrent_requests")) is not int:
        failures.append("CONCURRENCY_NOT_ISOLATED")
    if (not _positive_integer(plan.get("estimated_peak_memory_bytes"))
            or not _positive_integer(plan.get("required_free_disk_bytes"))):
        failures.append("RESOURCE_ESTIMATES_INVALID")

    estimates: list[int] = []
    for role in ("chat", "embedding"):
        model = plan.get(role)
        if not isinstance(model, dict) or set(model) != MODEL_KEYS:
            failures.append(f"{role.upper()}_MODEL_SCHEMA_INVALID")
            continue
        if not isinstance(model.get("model_id"), str) or not MODEL_ID.fullmatch(model["model_id"]):
            failures.append(f"{role.upper()}_MODEL_ID_INVALID")
        if not _local_endpoint(model.get("endpoint")):
            failures.append(f"{role.upper()}_ENDPOINT_NOT_STRICT_LOOPBACK")
        estimate = model.get("estimated_memory_bytes")
        if not _positive_integer(estimate):
            failures.append(f"{role.upper()}_MEMORY_ESTIMATE_INVALID")
        else:
            estimates.append(estimate)

    if len(estimates) == 2 and _positive_integer(plan.get("estimated_peak_memory_bytes")):
        if sum(estimates) + 2 * GIB > plan["estimated_peak_memory_bytes"]:
            failures.append("PEAK_ESTIMATE_OMITS_OVERHEAD")
    if not failures:
        assert isinstance(memory, dict) and isinstance(disk, dict)
        if plan["estimated_peak_memory_bytes"] + 2 * GIB > memory["effective_available"]:
            failures.append("INSUFFICIENT_RAM_HEADROOM")
        if plan["required_free_disk_bytes"] + 5 * GIB > disk["available"]:
            failures.append("INSUFFICIENT_DISK_HEADROOM")
    return _result(failures)


def _result(failures: list[str]) -> dict:
    return {
        "schema_version": "icarus-rdagent-model-plan-assessment-v1",
        "verdict": "REJECTED" if failures else "STRUCTURALLY_PLAUSIBLE_NOT_VERIFIED",
        "reason_codes": sorted(set(failures)),
        "host_identity_verified": False,
        "endpoint_reachable_verified": False,
        "model_files_verified": False,
        "model_license_verified": False,
        "model_memory_estimate_verified": False,
        "rdagent_model_compatibility_verified": False,
        "model_execution_authorized": False,
        "training_authorized": False,
        "execution_authorized": False,
        "note": "Offline proposal review only; run preflight on actual owner WSL2 host and independently verify model files, rights, runtime and memory before any separately authorized execution.",
    }


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON keys forbidden")
        result[key] = value
    return result


def _read_json(path: Path) -> object:
    # Do not follow symlinks to credentials or read unbounded local data.
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("input must be a regular non-symlink JSON file <= 64 KiB")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON value")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = assess_plan(_read_json(args.preflight), _read_json(args.plan))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        report = _result(["INPUT_FILE_INVALID"])
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verdict"] == "STRUCTURALLY_PLAUSIBLE_NOT_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
