"""Offline registry orchestration. Catalog links are metadata, never permissions."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
from pathlib import Path

from .contracts import Candidate, CatalogSnapshot, Disposition, PolicyState
from .dedupe import DuplicateResolver
from .importers import importer_for
from .normalize import candidate_identity, classify_data_class, normalize_url
from .policy import PolicyTriage
from .store import RegistryStore


_IMPORTERS = {"api-mega-list": "api_mega", "scraping-apis-for-devs": "scraping_apis",
              "ai-agent-tools": "ai_agent_tools"}


@dataclass(frozen=True, slots=True)
class ImportSummary:
    catalog_id: str
    snapshot_id: str
    raw_count: int
    imported_entries: int
    unique_candidates: int
    duplicate_groups: int
    rejected: int
    review_required: int
    parse_failures: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self) | {"execution_authorized": False, "production_decision_authorized": False}


class DiscoveryRegistryService:
    def __init__(self, base_dir: Path):
        self.store = RegistryStore(base_dir)

    def import_snapshot(self, snapshot: CatalogSnapshot, text: str, *, importer_name: str) -> ImportSummary:
        if _IMPORTERS.get(snapshot.catalog_id) != importer_name:
            raise ValueError("catalog and importer do not match")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != snapshot.content_sha256:
            raise ValueError("catalog content hash does not match pinned snapshot")
        parsed = importer_for(importer_name)(snapshot, text)
        failures = [dict(item) for item in parsed.parse_failures]
        entries, records, decisions = [], [], []
        triage = PolicyTriage(decided_at=snapshot.retrieved_at)
        for entry in parsed.entries:
            try:
                normalized = normalize_url(entry.endpoint_or_tool_url)
            except ValueError:
                failures.append({"reason": "INVALID_CATALOG_URL", "source_order": str(entry.source_order),
                                 "raw_row_sha256": entry.raw_row_sha256 or ""})
                continue
            # Separate observations share an identity/family, not a destructive candidate row.
            kind = entry.canonical_name
            identity = candidate_identity(canonical_name=entry.canonical_name,
                                          identity_url=normalized.identity_url, capability_kind=kind)
            observation_id = hashlib.sha256("\0".join((snapshot.catalog_id, identity,
                                                       entry.raw_row_sha256 or entry.entry_id)).encode()).hexdigest()
            ref = f"{snapshot.catalog_id}:{snapshot.snapshot_id}:{entry.entry_id}"
            defaults = triage.candidate_defaults(entry, catalog_id=snapshot.catalog_id)
            decision = replace(triage.evaluate(entry), candidate_id=observation_id)
            record = Candidate.minimum(
                candidate_id=observation_id, canonical_name=entry.canonical_name,
                endpoint_or_tool_url=entry.endpoint_or_tool_url, provider_name=normalized.domain,
                capability_kind=kind, data_class=classify_data_class(entry.category or "", entry.description),
                description=entry.description, upstream_catalog_refs=(ref,),
                upstream_entry_hashes=(entry.raw_row_sha256 or entry.entry_id,),
                first_seen_at=snapshot.retrieved_at, last_seen_at=snapshot.retrieved_at,
                disposition=Disposition.REJECTED if decision.policy_state is PolicyState.REJECTED else Disposition.ACTIVE,
                metadata={"identity_sha256": identity}, **defaults,
            )
            entries.append(entry)
            records.append(record)
            decisions.append(decision)
        completed = replace(snapshot, entry_count_raw=parsed.raw_count,
                            entry_count_normalized=len(entries), parse_failures=tuple(failures))
        with self.store.transaction():
            old_snapshot = self.store.catalog_snapshot(snapshot.snapshot_id)
            if old_snapshot is not None:
                # Retrieval time may differ on a re-fetch; pinned parse identity must agree.
                completed = replace(completed, retrieved_at=old_snapshot.retrieved_at)
                self.store.record_snapshot(completed)
                saved = self.store.import_summary(snapshot.snapshot_id)
                if saved is not None:
                    return ImportSummary(**saved)
            self.store.record_snapshot(completed)
            self.store.record_entries(snapshot.snapshot_id, entries)
            for record, entry, decision in zip(records, entries, decisions):
                old = self.store.candidate(record.candidate_id)
                if old is not None:
                    # Metadata import must never reset qualification, disposition or manual policy.
                    record = replace(old,
                        upstream_catalog_refs=tuple(sorted(set(old.upstream_catalog_refs + record.upstream_catalog_refs))),
                        upstream_entry_hashes=tuple(sorted(set(old.upstream_entry_hashes + record.upstream_entry_hashes))),
                        last_seen_at=max(old.last_seen_at or record.last_seen_at, record.last_seen_at),
                    )
                self.store.upsert_candidates([record])
                self.store.link_candidate(record.candidate_id, entry.entry_id)
                self.store.record_policy(decision)
            all_candidates = self.store.candidates()
            groups = DuplicateResolver().resolve(all_candidates)
            self.store.replace_duplicate_groups(groups)
            group_ids = {member: group.group_id for group in groups for member in group.member_ids}
            self.store.upsert_candidates([replace(c, duplicate_group_id=group_ids.get(c.candidate_id))
                                          for c in all_candidates])
            ids = {record.candidate_id for record in records}
            summary = ImportSummary(
                catalog_id=snapshot.catalog_id, snapshot_id=snapshot.snapshot_id,
                raw_count=completed.entry_count_raw, imported_entries=len(entries), unique_candidates=len(ids),
                duplicate_groups=sum(bool(ids.intersection(group.member_ids)) for group in groups),
                rejected=sum(d.policy_state is PolicyState.REJECTED for d in decisions),
                review_required=sum(d.policy_state is PolicyState.REVIEW_REQUIRED for d in decisions),
                parse_failures=len(completed.parse_failures),
            )
            self.store.record_import_summary(snapshot.snapshot_id, asdict(summary))
            return summary

    def snapshot(self) -> dict[str, object]:
        return self.store.summary()

    def close(self) -> None:
        self.store.close()


__all__ = ["DiscoveryRegistryService", "ImportSummary"]
