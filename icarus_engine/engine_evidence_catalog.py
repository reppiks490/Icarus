"""Read-only catalog over actual committed Icarus-engine evidence.

This module never calls providers, copies licensed raw payloads, trains models, changes
runtime state, or grants execution authority. It summarizes existing committed evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ENGINE_REPO = "reppiks490/Icarus-engine"
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_BYTES = 8 * 1024 * 1024

EVIDENCE = {
    "ingestion_manifest": "config/data_ingestion_manifest.json",
    "provider_context": "automation_intelligence/provider_collection_v1/research_context.json",
    "sentinel_health": "automation_intelligence/sentinel/data_health.json",
    "sec_edgar": "automation_intelligence/cl_lab/sec_edgar_manifest.json",
    "native_research": "automation_intelligence/native_research_v1/latest.json",
    "interrepo": "automation_intelligence/interrepo/latest.json",
}


class EvidenceCatalogError(ValueError):
    pass


def _reject_constant(value: str):
    raise EvidenceCatalogError(f"non-finite JSON constant: {value}")


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise EvidenceCatalogError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def _read_json(root: Path, relative: str) -> tuple[dict, str, int]:
    root = root.resolve()
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise EvidenceCatalogError(f"missing or symlinked evidence file: {relative}")
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise EvidenceCatalogError(f"evidence path escapes peer root: {relative}") from exc
    size = resolved.stat().st_size
    if size <= 0 or size > MAX_BYTES:
        raise EvidenceCatalogError(f"invalid evidence file size: {relative}")
    data = resolved.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceCatalogError(f"invalid JSON evidence: {relative}") from exc
    if not isinstance(value, dict):
        raise EvidenceCatalogError(f"evidence root must be object: {relative}")
    return value, digest, size


def _peer_head(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise EvidenceCatalogError("peer root must be a readable git checkout") from exc
    return proc.stdout.strip()


def _int(value, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise EvidenceCatalogError(f"invalid integer field: {field}")
    return value


def _false(value, field: str) -> None:
    if value is not False:
        raise EvidenceCatalogError(f"authority escalation in {field}")


def build_real_engine_evidence_catalog(peer_root: Path, *, expected_commit: str) -> dict:
    """Validate and summarize actual committed Engine evidence, without sampling raw rows."""
    if not COMMIT.fullmatch(expected_commit):
        raise EvidenceCatalogError("exact 40-character Engine commit required")
    peer_root = Path(peer_root)
    head = _peer_head(peer_root)
    if head != expected_commit:
        raise EvidenceCatalogError(f"Engine checkout mismatch: {head}")

    loaded = {}
    files = {}
    for name, relative in EVIDENCE.items():
        value, digest, size = _read_json(peer_root, relative)
        loaded[name] = value
        files[name] = {"path": relative, "sha256": digest, "bytes": size}

    manifest = loaded["ingestion_manifest"]
    if manifest.get("schema_version") != "icarus-data-ingestion-manifest-v1":
        raise EvidenceCatalogError("unsupported ingestion manifest")
    policy = manifest.get("policy")
    if not isinstance(policy, dict) or policy.get("required_for_every_ai_unit") is not True:
        raise EvidenceCatalogError("ingestion manifest is not federation-authoritative")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise EvidenceCatalogError("ingestion source ledger is empty")
    source_states = {}
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            raise EvidenceCatalogError("malformed ingestion source")
        sid = source["id"]
        if sid in source_states:
            raise EvidenceCatalogError(f"duplicate ingestion source: {sid}")
        source_states[sid] = {
            "credential_state": source.get("credential_state"),
            "ingestion_state": source.get("ingestion_state"),
            "consumption_state": source.get("consumption_state"),
            "runtime_status": source.get("runtime_status"),
            "blocker": source.get("blocker"),
        }

    provider = loaded["provider_context"]
    if provider.get("authority") != "RESEARCH_CONTEXT_ONLY":
        raise EvidenceCatalogError("provider context authority mismatch")
    _false(provider.get("automatic_model_promotion"), "provider automatic_model_promotion")
    _false(provider.get("execution_authorized"), "provider execution_authorized")
    _false(provider.get("production_decision_authorized"), "provider production_decision_authorized")
    providers = provider.get("providers")
    if not isinstance(providers, dict):
        raise EvidenceCatalogError("provider context missing providers")
    provider_summary = {}
    for name, item in sorted(providers.items()):
        if not isinstance(item, dict):
            raise EvidenceCatalogError(f"invalid provider context: {name}")
        provider_summary[name] = {
            "status": item.get("status"),
            "collected_rows": _int(item.get("collected_rows", 0), f"{name}.collected_rows"),
            "collected_pages": _int(item.get("collected_pages", 0), f"{name}.collected_pages"),
            "requests": _int(item.get("requests", 0), f"{name}.requests"),
            "completed_at_utc": item.get("completed_at_utc"),
            "substantive_work_performed": item.get("substantive_work_performed") is True,
        }

    sec = loaded["sec_edgar"]
    if sec.get("schema") != "icarus.sec_edgar/2" or sec.get("status") != "ok":
        raise EvidenceCatalogError("SEC/EDGAR evidence is not healthy schema v2")
    fact_rows = _int(sec.get("fact_rows"), "sec.fact_rows", minimum=1)
    filing_rows = _int(sec.get("filing_rows"), "sec.filing_rows", minimum=1)
    for field in ("facts_sha256", "filing_sha256"):
        if not SHA256.fullmatch(str(sec.get(field, ""))):
            raise EvidenceCatalogError(f"SEC/EDGAR digest missing: {field}")
    tickers = sec.get("tickers")
    if not isinstance(tickers, dict) or not tickers:
        raise EvidenceCatalogError("SEC/EDGAR ticker ledger empty")

    native = loaded["native_research"]
    _false(native.get("execution_authorized"), "native research execution_authorized")
    _int(native.get("chatgpt_tokens_used", 0), "native.chatgpt_tokens_used")
    _int(native.get("paid_model_calls", 0), "native.paid_model_calls")
    lanes = native.get("lanes")
    if not isinstance(lanes, dict) or not lanes:
        raise EvidenceCatalogError("native research lane ledger empty")
    native_lanes = {
        name: {
            "status": item.get("status"),
            "substantive_work_performed": item.get("substantive_work_performed") is True,
            "receipt_path": item.get("receipt_path"),
            "event_path": item.get("event_path"),
        }
        for name, item in sorted(lanes.items()) if isinstance(item, dict)
    }

    interrepo = loaded["interrepo"]
    _false(interrepo.get("execution_authorized"), "interrepo execution_authorized")
    acceptance = interrepo.get("canonical_acceptance")
    if not isinstance(acceptance, dict):
        raise EvidenceCatalogError("interrepo canonical acceptance missing")
    for field in ("execution_authorized", "automatic_model_promotion", "production_decision_authorized"):
        _false(acceptance.get(field), f"interrepo.{field}")
    if acceptance.get("authority") != "RESEARCH" or acceptance.get("producer_repository") != ENGINE_REPO:
        raise EvidenceCatalogError("interrepo acceptance authority mismatch")

    sentinel = loaded["sentinel_health"]
    counts = sentinel.get("counts")
    if not isinstance(counts, dict):
        raise EvidenceCatalogError("Sentinel counts missing")
    sentinel_counts = {name: _int(value, f"sentinel.{name}") for name, value in counts.items()}

    current_real_rows = sum(v["collected_rows"] for v in provider_summary.values())
    substantive_providers = sorted(
        name for name, value in provider_summary.items()
        if value["substantive_work_performed"] and value["collected_rows"] > 0
    )
    return {
        "schema_version": "icarus-real-engine-evidence-catalog-v1",
        "producer_repository": ENGINE_REPO,
        "producer_commit": expected_commit,
        "evidence_files": files,
        "source_count": len(source_states),
        "source_states": source_states,
        "provider_snapshot": {
            "snapshot_at_utc": provider.get("snapshot_at_utc"),
            "provider_count": len(provider_summary),
            "current_collected_rows": current_real_rows,
            "substantive_providers": substantive_providers,
            "providers": provider_summary,
        },
        "sec_edgar": {
            "generated_at": sec.get("generated_at"),
            "fact_rows": fact_rows,
            "filing_rows": filing_rows,
            "ticker_count": len(tickers),
            "facts_sha256": sec["facts_sha256"],
            "filing_sha256": sec["filing_sha256"],
        },
        "native_research": {
            "at_utc": native.get("at_utc"),
            "run_id": native.get("run_id"),
            "qualification": native.get("qualification"),
            "lanes": native_lanes,
        },
        "interrepo_acceptance": {
            "status": acceptance.get("status"),
            "accepted_by_icarus_commit": acceptance.get("accepted_by_icarus_commit"),
            "accepted_peer_packet_id": acceptance.get("accepted_peer_packet_id"),
            "accepted_peer_source_commit": acceptance.get("accepted_peer_source_commit"),
            "peer_source_commit_relation": acceptance.get("peer_source_commit_relation"),
        },
        "sentinel_counts": sentinel_counts,
        "raw_payloads_copied": False,
        "provider_requests_made": 0,
        "new_collection_performed": False,
        "automatic_model_promotion": False,
        "production_decision_authorized": False,
        "execution_authorized": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", required=True, type=Path)
    parser.add_argument("--engine-commit", required=True)
    args = parser.parse_args(argv)
    result = build_real_engine_evidence_catalog(args.engine_root, expected_commit=args.engine_commit)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
