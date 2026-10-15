"""Read-only existing-provider evidence, never a second acquisition engine."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Callable, Iterable
from urllib.parse import urlsplit

from .contracts import Candidate, ProviderLink, QualificationEvent, QualificationState, utc_iso
from .normalize import normalize_name, normalize_url


PROVIDER_DOMAINS = {
    "massive": ("api.massive.com", "massive.com", "polygon.io"),
    "twelve": ("api.twelvedata.com", "twelvedata.com"),
    "fmp": ("financialmodelingprep.com",), "eodhd": ("eodhd.com",),
    "tiingo": ("api.tiingo.com", "tiingo.com"),
    "intrinio": ("api-v2.intrinio.com", "intrinio.com"),
    "quiver": ("api.quiverquant.com", "quiverquant.com"),
    "fred": ("api.stlouisfed.org", "fred.stlouisfed.org", "stlouisfed.org"),
    "alpaca": ("data.alpaca.markets", "alpaca.markets"),
    "bybit": ("api.bybit.com", "bybit.com"),
    "tickstream": ("api.tick-stream.xyz", "tick-stream.xyz"),
}
_NAMES = {
    "massive": "massive", "polygon": "massive", "polygon.io": "massive",
    "twelve": "twelve", "twelve data": "twelve", "twelvedata": "twelve",
    "fmp": "fmp", "financial modeling prep": "fmp", "financialmodelingprep": "fmp",
    "eodhd": "eodhd", "tiingo": "tiingo", "intrinio": "intrinio",
    "quiver": "quiver", "quiver quantitative": "quiver", "fred": "fred",
    "alpaca": "alpaca", "bybit": "bybit", "tickstream": "tickstream", "tick stream": "tickstream",
}
_BLOCKERS = {"BLOCKED_MISSING_CREDENTIAL", "BLOCKED_AUTHENTICATION", "QUOTA_OR_RATE_LIMIT_PAUSED",
             "BLOCKED", "NO_READY_JOBS", "PENDING"}
_BLOCKER_CODES = {"401", "402", "403", "429", "REDIRECT_BLOCKED", "PAYLOAD_LIMIT_INCOMPLETE",
    "PROVIDER_ERROR", "UNSUPPORTED_RESPONSE_FORMAT", "PAGINATION_REPEAT_INCOMPLETE",
    "PAGINATION_DID_NOT_ADVANCE", "HTTPError", "URLError", "TimeoutError", "ConnectionError",
    "JSONDecodeError", "ValueError", "OSError", "SSLError", "IncompleteRead"}
FEDERATION_REVISION = "registry-federation-v3"


def _normalized_path(path: str) -> str:
    """Compare endpoint paths without treating a trailing slash as a new route."""
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("provider operation path must be absolute")
    normalized = path.rstrip("/")
    return normalized or "/"


def _operation_path_match(operation_path: str, candidate_path: str) -> str | None:
    """Match literal OpenAPI paths or one-segment `{parameter}` templates."""
    operation_parts = operation_path.split("/")
    candidate_parts = candidate_path.split("/")
    if len(operation_parts) != len(candidate_parts):
        return None
    has_template = False
    for operation_part, candidate_part in zip(operation_parts, candidate_parts):
        if re.fullmatch(r"\{[A-Za-z_][A-Za-z0-9_.-]*\}", operation_part):
            if not candidate_part:
                return None
            has_template = True
        elif operation_part != candidate_part:
            return None
    return "TEMPLATE" if has_template else "EXACT"


def _strict_json(raw: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError("nonfinite JSON value")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


class ProviderFederator:
    def __init__(self, endpoint_catalog_path: Path, latest_dir: Path,
                 *, now: Callable[[], datetime] | None = None):
        self.endpoint_catalog_path = Path(endpoint_catalog_path)
        self.latest_dir = Path(latest_dir)
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _receipt(self, provider: str) -> dict:
        path = self.latest_dir / (provider + ".json")
        result = {"receipt_path": str(path), "receipt_sha256": None,
                  "status": "MISSING_PROVIDER_EVIDENCE", "completed_at_utc": None,
                  "collected_pages": 0, "substantive_work_performed": False,
                  "verified_operations": (), "operation_blockers": {}}
        try:
            with path.open("rb") as handle:
                raw = handle.read(1_000_001)
            result["receipt_sha256"] = hashlib.sha256(raw).hexdigest()
            if len(raw) > 1_000_000:
                raise ValueError("provider receipt limit")
            receipt = _strict_json(raw)
            entry = receipt["providers"][provider]
            if not isinstance(entry, dict):
                raise ValueError("malformed provider entry")
            completed = utc_iso(receipt["completed_at_utc"])
            pages = entry["collected_pages"]
            substantive = entry.get("substantive_work_performed", False)
            if isinstance(pages, bool) or not isinstance(pages, int) or pages < 0:
                raise ValueError("malformed pages")
            if not isinstance(substantive, bool):
                raise ValueError("malformed substantive flag")
            verified = entry.get("verified_operations", [])
            if not isinstance(verified, list) or len(verified) > 10_000:
                raise ValueError("malformed verified operations")
            verified_operations = set()
            for operation in verified:
                if (not isinstance(operation, str) or not operation.startswith(provider + ":")
                        or len(operation) > 2048):
                    raise ValueError("wrong provider verified operation")
                verified_operations.add(operation)
            status = entry["status"]
            if status not in _BLOCKERS | {"COLLECTED_PARTIAL"}:
                raise ValueError("unrecognized collector status")
            blocked = entry.get("blocked", [])
            if not isinstance(blocked, list) or len(blocked) > 10_000:
                raise ValueError("malformed operation blockers")
            operation_blockers = {}
            for blocker in blocked:
                if not isinstance(blocker, dict) or not isinstance(blocker.get("operation"), str):
                    raise ValueError("malformed operation blocker")
                operation = blocker["operation"]
                if not operation.startswith(provider + ":") or len(operation) > 2048:
                    raise ValueError("wrong provider operation blocker")
                code = blocker.get("failure_code")
                safe_code = str(code) if isinstance(code, (str, int)) and str(code) in _BLOCKER_CODES else "OTHER_PROVIDER_FAILURE"
                operation_blockers.setdefault(operation, set()).add(safe_code)
            age = (self._now() - datetime.fromisoformat(completed.replace("Z", "+00:00"))).total_seconds()
            if age < 0:
                raise ValueError("future receipt")
            result.update(completed_at_utc=completed, collected_pages=pages,
                          substantive_work_performed=substantive,
                          verified_operations=tuple(sorted(verified_operations)),
                          operation_blockers={operation: sorted(codes) for operation, codes in operation_blockers.items()},
                          status="STALE_PROVIDER_EVIDENCE" if age > 21600 else status)
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, KeyError):
            result["status"] = "MALFORMED_PROVIDER_EVIDENCE"
        return result

    def _operations(self) -> dict[str, tuple[dict[str, str], ...]]:
        with self.endpoint_catalog_path.open("rb") as handle:
            raw = handle.read(20_000_001)
        if len(raw) > 20_000_000:
            raise ValueError("provider catalog limit")
        catalog = _strict_json(raw)
        result: dict[str, dict[str, str]] = {}
        for operation in catalog["operations"]:
            operation_id = operation.get("id")
            if not isinstance(operation_id, str) or ":" not in operation_id:
                raise ValueError("malformed provider operation")
            provider = operation.get("provider") or operation_id.split(":", 1)[0]
            if provider in PROVIDER_DOMAINS and operation_id.startswith(provider + ":"):
                path = _normalized_path(operation.get("path"))
                method = operation.get("method")
                if not isinstance(method, str) or not method:
                    raise ValueError("malformed provider operation method")
                result.setdefault(provider, {})[operation_id] = {"path": path, "method": method.upper()}
        return {provider: tuple(
            {"id": operation_id, **details}
            for operation_id, details in sorted(entries.items())
        ) for provider, entries in result.items()}

    def links_for(self, candidates: Iterable[Candidate]) -> tuple[ProviderLink, ...]:
        operations = self._operations()
        receipts = {}
        links = []
        now = self._now().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        for candidate in sorted(candidates, key=lambda c: c.candidate_id):
            normalized = normalize_url(candidate.endpoint_or_tool_url)
            domain = normalized.domain
            transport = urlsplit(normalized.identity_url)
            provider = next((provider for provider, domains in PROVIDER_DOMAINS.items() if domain in domains), None)
            exact_domain = provider is not None
            if provider is None:
                provider = _NAMES.get(normalize_name(candidate.provider_name or candidate.canonical_name).casefold())
            if provider not in operations:
                continue
            if provider not in receipts:
                receipts[provider] = self._receipt(provider)
            receipt = receipts[provider]
            candidate_path = _normalized_path(urlsplit(normalized.identity_url).path or "/")
            metadata = {key: value for key, value in receipt.items() if key != "operation_blockers"} | {
                "match_basis": "EXACT_DOMAIN" if exact_domain else "CANONICAL_PROVIDER_NAME",
                "transport_access_evidence": exact_domain and transport.scheme == "https"
                    and transport.hostname in PROVIDER_DOMAINS[provider]
                    and transport.port in {None, 443} and not candidate.capability_only,
                "qualification_scope": "operation_specific_access_only", "federation_revision": FEDERATION_REVISION}
            for operation in operations[provider]:
                operation_id = operation["id"]
                path_match = _operation_path_match(operation["path"], candidate_path)
                if path_match is None:
                    continue
                operation_metadata = metadata | {
                    "candidate_path": candidate_path,
                    "operation_path": operation["path"],
                    "operation_method": operation["method"],
                    "operation_path_match": path_match,
                    "operation_verified": operation_id in receipt["verified_operations"],
                    "operation_blockers": receipt["operation_blockers"].get(operation_id, []),
                }
                material = "\0".join((FEDERATION_REVISION, candidate.candidate_id, provider, operation_id,
                    candidate_path, receipt["receipt_sha256"] or "missing", receipt["status"], metadata["match_basis"]))
                links.append(ProviderLink(candidate_id=candidate.candidate_id, provider_id=provider,
                    operation_id=operation_id, linked_at=receipt["completed_at_utc"] or now,
                    evidence_ref=receipt["receipt_path"], link_id=hashlib.sha256(material.encode()).hexdigest(),
                    metadata=operation_metadata))
        return tuple(links)

    def evidence_events(self, links: Iterable[ProviderLink]) -> tuple[QualificationEvent, ...]:
        events, receipts = {}, {}
        for link in links:
            if link.provider_id not in PROVIDER_DOMAINS or link.metadata.get("transport_access_evidence") is not True:
                continue
            if link.provider_id not in receipts:
                receipts[link.provider_id] = self._receipt(link.provider_id)
            receipt = receipts[link.provider_id]
            if (receipt["receipt_sha256"] != link.metadata.get("receipt_sha256")
                or receipt["receipt_path"] != link.evidence_ref
                or receipt["status"] in _BLOCKERS
                or receipt["collected_pages"] < 1
                or receipt["substantive_work_performed"] is not True
                or receipt["status"] != "COLLECTED_PARTIAL"):
                continue
            if (link.metadata.get("operation_path_match") not in {"EXACT", "TEMPLATE"}
                or link.operation_id not in receipt["verified_operations"]
                or receipt["operation_blockers"].get(link.operation_id)):
                continue
            material = "\0".join((link.candidate_id, link.provider_id, link.operation_id,
                                   receipt["receipt_sha256"], "ACCESS_TESTED"))
            events.setdefault(link.candidate_id, QualificationEvent(candidate_id=link.candidate_id,
                old_state=QualificationState.DISCOVERED, new_state=QualificationState.ACCESS_TESTED,
                occurred_at=receipt["completed_at_utc"], evidence_ref=receipt["receipt_path"],
                event_id=hashlib.sha256(material.encode()).hexdigest(), reason_code="EXISTING_PROVIDER_ACCESS_EVIDENCE",
                metadata={"provider_id": link.provider_id, "receipt_sha256": receipt["receipt_sha256"],
                          "operation_id": link.operation_id,
                          "qualification_scope": "operation_specific_access_only"}))
        return tuple(events[key] for key in sorted(events))


__all__ = ["ProviderFederator", "PROVIDER_DOMAINS"]
