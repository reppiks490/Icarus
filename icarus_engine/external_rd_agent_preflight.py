"""Read-only host-capacity preflight for RD-Agent's local chat and embedding models.

No network, model execution, provider requests, GPU commands, credential reads,
machine configuration changes or inferences about the owner's remote PC.
"""
from __future__ import annotations

import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil

GIB = 1024 ** 3


def _integer(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="ascii").strip()
        n = int(raw)
        return n if n >= 0 else None
    except (OSError, ValueError, UnicodeError):
        return None


def _linux_memory(meminfo: Path = Path("/proc/meminfo")) -> tuple[int | None, int | None]:
    try:
        lines = meminfo.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError):
        return None, None
    values = {}
    for line in lines:
        key, _, val = line.partition(":")
        parts = val.split()
        if key in ("MemTotal", "MemAvailable") and len(parts) == 2:
            if parts[0].isdigit() and parts[1] == "kB":
                values[key] = int(parts[0]) * 1024
    return values.get("MemTotal"), values.get("MemAvailable")


def _windows_memory() -> tuple[int | None, int | None]:
    if platform.system() != "Windows":
        return None, None
    try:
        import ctypes
        from ctypes import wintypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None, None
        return int(status.ullTotalPhys), int(status.ullAvailPhys)
    except (AttributeError, OSError):
        return None, None


def _cgroup_memory(root: Path = Path("/sys/fs/cgroup")) -> tuple[int | None, int | None]:
    limit = _integer(root / "memory.max")
    used = _integer(root / "memory.current")
    if limit is None:
        limit = _integer(root / "memory/memory.limit_in_bytes")
        used = _integer(root / "memory/memory.usage_in_bytes")
    if limit is not None and limit > 1 << 60:
        limit = None
    return limit, used


def probe_host(
    workspace: Path, *,
    memory_total: int | None = None,
    memory_available: int | None = None,
    cgroup_limit: int | None = None,
    cgroup_used: int | None = None,
) -> dict:
    """A host-capacity record, never a model recommendation or training grant."""
    workspace = Path(workspace)
    if not workspace.is_dir():
        raise ValueError("workspace must be an existing directory")
    system = platform.system()
    if memory_total is None or memory_available is None:
        host_total, host_available = (
            _windows_memory() if system == "Windows" else _linux_memory()
        )
        if memory_total is None:
            memory_total = host_total
        if memory_available is None:
            memory_available = host_available
    if cgroup_limit is None and cgroup_used is None and system == "Linux":
        cgroup_limit, cgroup_used = _cgroup_memory()
    for name, value in {
        "memory_total": memory_total, "memory_available": memory_available,
        "cgroup_limit": cgroup_limit, "cgroup_used": cgroup_used,
    }.items():
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"invalid {name}")
    effective_total = memory_total
    effective_available = memory_available
    if cgroup_limit is not None:
        effective_total = (
            cgroup_limit if effective_total is None
            else min(effective_total, cgroup_limit)
        )
        # Without cgroup consumption there is no trustworthy available RAM.
        if cgroup_used is None:
            effective_available = None
        else:
            remaining = max(0, cgroup_limit - cgroup_used)
            effective_available = (
                remaining if effective_available is None
                else min(effective_available, remaining)
            )
    total_disk, _, free_disk = shutil.disk_usage(workspace)
    if effective_available is None:
        state = "UNKNOWN_MEMORY_HEADROOM"
    elif effective_available < 4 * GIB or free_disk < 10 * GIB:
        state = "RESOURCE_BLOCKED"
    elif effective_available < 12 * GIB or free_disk < 25 * GIB:
        state = "RESOURCE_CONSTRAINED"
    else:
        state = "CAPACITY_MEASURED_NOT_MODEL_QUALIFIED"
    is_wsl = system == "Linux" and (
        "microsoft" in platform.release().lower()
        or bool(os.environ.get("WSL_DISTRO_NAME"))
    )
    try:
        version = metadata.version("rdagent")
    except metadata.PackageNotFoundError:
        version = None
    return {
        "schema_version": "icarus-rdagent-host-preflight-v1",
        "os": system,
        "wsl": is_wsl,
        "python_version": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
        "memory_bytes": {
            "host_total": memory_total, "host_available": memory_available,
            "cgroup_limit": cgroup_limit, "cgroup_used": cgroup_used,
            "effective_total": effective_total,
            "effective_available": effective_available,
        },
        "disk_bytes": {"total": total_disk, "available": free_disk},
        "rdagent_distribution_metadata_version": version,
        "rdagent_runtime_verified": False,
        "gpu_memory_verified": False,
        "chat_model_endpoint_verified": False,
        "embedding_model_endpoint_verified": False,
        "model_compatibility_verified": False,
        "model_download_authorized": False,
        "model_execution_authorized": False,
        "training_authorized": False,
        "execution_authorized": False,
        "resource_state": state,
        "note": "Run on the owner's actual target Windows/WSL2 host; a GitHub "
                "runner/container readout does not establish owner hardware.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = probe_host(args.workspace)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
