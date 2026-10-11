"""Bounded public catalog retrieval only. Never probes discovered services."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zlib
from typing import Callable, Sequence
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from icarus_engine.discovery_registry.contracts import CatalogSnapshot, validate_commit_sha
from icarus_engine.discovery_registry.service import DiscoveryRegistryService
from icarus_engine.discovery_registry.normalize import contains_credential_metadata


MAX_CATALOG_BYTES = 20_000_000
PARSER_REVISION = "catalog-registry-v3"
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SOURCES = {
    "api-mega-list": ("cporter202/API-mega-list", "api_mega", False),
    "scraping-apis-for-devs": ("cporter202/scraping-apis-for-devs", "scraping_apis", False),
    "ai-agent-tools": ("cporter202/ai-agent-tools", "ai_agent_tools", True),
}
_ERROR_CODES = frozenset({"INVALID_TARGET", "INVALID_COMMIT", "INVALID_REF_RESPONSE",
    "CATALOG_PAYLOAD_LIMIT", "NETWORK_FAILURE", "INVALID_UTF8", "INVALID_PAYLOAD", "IMPORT_FAILED",
    "CREDENTIAL_BEARING_METADATA", "UNRECOGNIZED_CATALOG_FORMAT", "CACHE_PERSISTENCE_FAILED"})
RECEIPT_ROOT = Path("automation_intelligence/catalog_registry_v1")


class CatalogFetchError(RuntimeError):
    def __init__(self, code: str):
        self.code = code if code in _ERROR_CODES else "NETWORK_FAILURE"
        super().__init__(self.code)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect cannot silently escape the approved host/repository boundary.
        return None


class GitHubPublicCatalogClient:
    def __init__(self, *, opener: Callable | None = None):
        self._open = opener or build_opener(ProxyHandler({}), _NoRedirect()).open

    @staticmethod
    def _repo(repo: str) -> None:
        if not isinstance(repo, str) or not _REPO.fullmatch(repo) or repo not in {s[0] for s in _SOURCES.values()}:
            raise CatalogFetchError("INVALID_TARGET")

    def _read(self, url: str, limit: int) -> bytes:
        request = Request(url, headers={"User-Agent": "ICARUS-catalog-registry/1", "Accept": "application/json"})
        try:
            with self._open(request, timeout=30) as response:
                data = response.read(limit + 1)
        except Exception as exc:
            # Exception URLs/messages may contain sensitive content; never serialize them.
            raise CatalogFetchError("NETWORK_FAILURE") from exc
        if len(data) > limit:
            raise CatalogFetchError("CATALOG_PAYLOAD_LIMIT")
        return data

    def resolve_ref(self, repo: str, ref: str = "main") -> str:
        self._repo(repo)
        if ref != "main":
            try:
                validate_commit_sha(ref)
            except ValueError as exc:
                raise CatalogFetchError("INVALID_TARGET") from exc
        payload = self._read(f"https://api.github.com/repos/{repo}/commits/{ref}", 1_000_000)
        try:
            return validate_commit_sha(json.loads(payload)["sha"])
        except (ValueError, KeyError, TypeError) as exc:
            raise CatalogFetchError("INVALID_REF_RESPONSE") from exc

    def fetch_text(self, repo: str, commit: str, path: str) -> bytes:
        self._repo(repo)
        try:
            commit = validate_commit_sha(commit)
        except ValueError as exc:
            raise CatalogFetchError("INVALID_COMMIT") from exc
        # These approved catalogs have one declared file; arbitrary paths are not a fetch API.
        if path != "README.md":
            raise CatalogFetchError("INVALID_TARGET")
        return self._read(f"https://raw.githubusercontent.com/{repo}/{commit}/{path}", MAX_CATALOG_BYTES)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, allow_nan=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".registry-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, value: object) -> None:
    _atomic_bytes(path, _json_bytes(value))


def _cache_snapshot(path: Path, data: bytes, digest: str) -> None:
    if path.is_symlink():
        raise CatalogFetchError("CACHE_PERSISTENCE_FAILED")
    if path.exists():
        try:
            with gzip.open(path, "rb") as handle:
                cached = handle.read(MAX_CATALOG_BYTES + 1)
            if len(cached) == len(data) and hashlib.sha256(cached).hexdigest() == digest:
                return
        except (OSError, EOFError, zlib.error):
            pass
    # A fetched immutable snapshot safely repairs an interrupted/corrupt cache.
    _atomic_bytes(path, gzip.compress(data, mtime=0))


def _sources(root: Path) -> dict[str, dict]:
    path = root / "config/catalog_registry_sources.json"
    if not path.exists():
        path = Path(__file__).resolve().parents[1] / "config/catalog_registry_sources.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    sources = config.get("sources")
    if not isinstance(sources, list) or len(sources) != 3:
        raise ValueError("source config must declare exactly the three approved catalogs")
    result = {}
    for source in sources:
        catalog_id = source.get("catalog_id")
        if catalog_id not in _SOURCES or catalog_id in result:
            raise ValueError("invalid or duplicate catalog config")
        repo, importer, capability_only = _SOURCES[catalog_id]
        if (source.get("upstream_repo") != repo or source.get("upstream_path") != "README.md"
            or source.get("importer") != importer or source.get("enabled") is not True
            or source.get("capability_only") is not capability_only):
            raise ValueError("source config does not match the approved catalog boundary")
        result[catalog_id] = source
    return result


def run(root: Path, *, run_id: str, catalog_ids: Sequence[str] | None = None,
        client: GitHubPublicCatalogClient | None = None) -> dict[str, object]:
    root = Path(root)
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise ValueError("unsafe run ID")
    sources = _sources(root)
    selected = list(dict.fromkeys(catalog_ids if catalog_ids is not None else sources))
    if not selected or any(catalog_id not in sources for catalog_id in selected):
        raise ValueError("unknown catalog selection")
    cycle_dir = root / RECEIPT_ROOT / "cycles" / run_id
    cycle_dir.mkdir(parents=True, exist_ok=False)
    receipt_path = RECEIPT_ROOT / "cycles" / run_id / "receipt.json"
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = {"schema_version": "icarus-catalog-registry-receipt-v1", "run_id": run_id,
              "started_at_utc": now, "receipt_path": receipt_path.as_posix(),
              "catalogs": {}, "errors": [], "execution_authorized": False,
              "production_decision_authorized": False, "chatgpt_tokens_used": 0, "paid_model_calls": 0}
    client = client or GitHubPublicCatalogClient()
    service = DiscoveryRegistryService(root)
    try:
        for catalog_id in selected:
            source = sources[catalog_id]
            try:
                try:
                    commit = validate_commit_sha(client.resolve_ref(source["upstream_repo"]))
                except ValueError as exc:
                    raise CatalogFetchError("INVALID_COMMIT") from exc
                data = client.fetch_text(source["upstream_repo"], commit, source["upstream_path"])
                if not isinstance(data, bytes):
                    raise CatalogFetchError("INVALID_PAYLOAD")
                if len(data) > MAX_CATALOG_BYTES:
                    raise CatalogFetchError("CATALOG_PAYLOAD_LIMIT")
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise CatalogFetchError("INVALID_UTF8") from exc
                if contains_credential_metadata(text):
                    raise CatalogFetchError("CREDENTIAL_BEARING_METADATA")
                digest = hashlib.sha256(data).hexdigest()
                snapshot = CatalogSnapshot(catalog_id=catalog_id, upstream_repo=source["upstream_repo"],
                    upstream_commit=commit, upstream_path=source["upstream_path"], content_sha256=digest,
                    retrieved_at=now, parser_revision=PARSER_REVISION)
                summary = service.import_snapshot(snapshot, text, importer_name=source["importer"])
                if summary.raw_count < 1 or summary.imported_entries < 1:
                    raise CatalogFetchError("UNRECOGNIZED_CATALOG_FORMAT")
                snapshot = service.store.catalog_snapshot(snapshot.snapshot_id)
                cache = root / ".catalog_registry_cache/raw" / catalog_id / commit / (digest + ".md.gz")
                _cache_snapshot(cache, data, digest)
                # Deliberately omit snapshot.parse_failures and every raw entry/description.
                item = {key: getattr(snapshot, key) for key in (
                    "catalog_id", "snapshot_id", "upstream_repo", "upstream_commit", "upstream_path",
                    "content_sha256", "parser_revision", "retrieved_at")}
                item.update(status="SUCCESS", import_summary=summary.to_dict(), execution_authorized=False,
                            production_decision_authorized=False)
                result["catalogs"][catalog_id] = item
                _atomic_json(root / RECEIPT_ROOT / "latest" / (catalog_id + ".json"), item)
            except Exception as exc:
                code = exc.code if isinstance(exc, CatalogFetchError) else "IMPORT_FAILED"
                result["errors"].append({"catalog_id": catalog_id, "error_code": code})
        provider_catalog = root / "config/provider_endpoint_catalog.json"
        if provider_catalog.is_file():
            try:
                result["provider_federation"] = service.federate_existing_providers(
                    provider_catalog, root / "automation_intelligence/provider_collection_v1/latest")
            except Exception:
                result["provider_federation"] = {"status": "FAILED", "error_code": "INVALID_PROVIDER_EVIDENCE",
                    "execution_authorized": False, "production_decision_authorized": False}
                result["errors"].append({"component": "provider_federation", "error_code": "INVALID_PROVIDER_EVIDENCE"})
        else:
            result["provider_federation"] = {"status": "NOT_AVAILABLE",
                "execution_authorized": False, "production_decision_authorized": False}
        result["registry_summary"] = service.snapshot()
    finally:
        service.close()
    result["completed_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result["status"] = "SUCCESS" if not result["errors"] else "PARTIAL" if result["catalogs"] else "FAILED"
    with (root / receipt_path).open("xb") as handle:
        handle.write(_json_bytes(result))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--catalog", choices=["all", *_SOURCES], default="all")
    args = parser.parse_args(argv)
    result = run(args.root, run_id=args.run_id,
                 catalog_ids=None if args.catalog == "all" else [args.catalog])
    print(json.dumps({key: result[key] for key in ("status", "receipt_path", "errors")}, sort_keys=True))
    return 0 if result["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
