from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from .contracts import (
    Candidate,
    CatalogEntry,
    CatalogSnapshot,
    CostModel,
    DataClass,
    Disposition,
    DuplicateGroup,
    PolicyDecision,
    PolicyState,
    ProviderLink,
    QualificationEvent,
    QualificationState,
    SourceClass,
)


def _json(value: object) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _candidate_from_json(payload: str) -> Candidate:
    raw = json.loads(payload)
    raw["data_class"] = tuple(DataClass(value) for value in raw.get("data_class", [DataClass.OTHER.value]))
    raw["asset_classes"] = tuple(raw.get("asset_classes", ()))
    raw["protocols"] = tuple(raw.get("protocols", ()))
    raw["upstream_catalog_refs"] = tuple(raw.get("upstream_catalog_refs", ()))
    raw["upstream_entry_hashes"] = tuple(raw.get("upstream_entry_hashes", ()))
    raw["source_class"] = SourceClass(raw.get("source_class", SourceClass.UNKNOWN.value))
    raw["policy_state"] = PolicyState(raw.get("policy_state", PolicyState.UNKNOWN.value))
    raw["estimated_cost_model"] = CostModel(raw.get("estimated_cost_model", CostModel.UNKNOWN.value))
    raw["qualification_state"] = QualificationState(raw.get("qualification_state", QualificationState.DISCOVERED.value))
    raw["disposition"] = Disposition(raw.get("disposition", Disposition.ACTIVE.value))
    return Candidate(**raw)


class RegistryStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.db_path = self.base_dir / "research" / "capability_registry.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_schema()

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS catalog_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS catalog_entries (
                entry_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL REFERENCES catalog_snapshots(snapshot_id),
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id TEXT PRIMARY KEY,
                qualification_state TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS candidate_catalog_links (
                candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
                entry_id TEXT NOT NULL REFERENCES catalog_entries(entry_id),
                PRIMARY KEY (candidate_id, entry_id)
            );
            CREATE TABLE IF NOT EXISTS duplicate_groups (
                group_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS duplicate_members (
                group_id TEXT NOT NULL REFERENCES duplicate_groups(group_id) ON DELETE CASCADE,
                candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
                PRIMARY KEY (group_id, candidate_id)
            );
            CREATE TABLE IF NOT EXISTS qualification_events (
                event_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
                old_state TEXT NOT NULL,
                new_state TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS policy_reviews (
                decision_id TEXT PRIMARY KEY,
                candidate_id TEXT,
                entry_id TEXT,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS provider_links (
                link_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
                provider_id TEXT NOT NULL,
                operation_id TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def pragma_journal_mode(self) -> str:
        row = self._conn.execute("PRAGMA journal_mode").fetchone()
        return str(row[0]).lower()

    def record_snapshot(self, snapshot: CatalogSnapshot) -> None:
        assert snapshot.snapshot_id is not None
        payload = _json(snapshot.to_dict())
        row = self._conn.execute(
            "SELECT payload_json FROM catalog_snapshots WHERE snapshot_id=?", (snapshot.snapshot_id,)
        ).fetchone()
        if row is not None:
            if row["payload_json"] != payload:
                raise ValueError("snapshot identity already exists with different content")
            return
        with self._conn:
            self._conn.execute(
                "INSERT INTO catalog_snapshots(snapshot_id,payload_json) VALUES (?,?)",
                (snapshot.snapshot_id, payload),
            )

    def record_entries(self, snapshot_id: str, entries: Iterable[CatalogEntry]) -> int:
        inserted = 0
        seen: set[str] = set()
        with self._conn:
            for entry in entries:
                if entry.entry_id in seen:
                    continue
                seen.add(entry.entry_id)
                if entry.snapshot_id != snapshot_id:
                    raise ValueError("catalog entry snapshot does not match target snapshot")
                payload = _json(entry.to_dict())
                row = self._conn.execute(
                    "SELECT snapshot_id,payload_json FROM catalog_entries WHERE entry_id=?", (entry.entry_id,)
                ).fetchone()
                if row is not None:
                    if row["snapshot_id"] != snapshot_id or row["payload_json"] != payload:
                        raise ValueError("catalog entry identity conflict")
                    continue
                self._conn.execute(
                    "INSERT INTO catalog_entries(entry_id,snapshot_id,payload_json) VALUES (?,?,?)",
                    (entry.entry_id, snapshot_id, payload),
                )
                inserted += 1
        return inserted

    def upsert_candidates(self, candidates: Iterable[Candidate]) -> int:
        changed = 0
        seen: set[str] = set()
        with self._conn:
            for candidate in candidates:
                if candidate.candidate_id in seen:
                    continue
                seen.add(candidate.candidate_id)
                payload = _json(candidate.to_dict())
                row = self._conn.execute(
                    "SELECT payload_json FROM candidates WHERE candidate_id=?", (candidate.candidate_id,)
                ).fetchone()
                if row is None:
                    self._conn.execute(
                        "INSERT INTO candidates(candidate_id,qualification_state,payload_json) VALUES (?,?,?)",
                        (candidate.candidate_id, candidate.qualification_state.value, payload),
                    )
                    changed += 1
                elif row["payload_json"] != payload:
                    existing = _candidate_from_json(row["payload_json"])
                    if existing.qualification_state is not candidate.qualification_state:
                        raise ValueError("candidate lifecycle state may change only through record_transition")
                    self._conn.execute(
                        "UPDATE candidates SET payload_json=? WHERE candidate_id=?",
                        (payload, candidate.candidate_id),
                    )
                    changed += 1
        return changed

    def link_candidate(self, candidate_id: str, entry_id: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO candidate_catalog_links(candidate_id,entry_id) VALUES (?,?)",
                (candidate_id, entry_id),
            )

    def record_policy(self, decision: PolicyDecision) -> None:
        payload = _json(decision.to_dict())
        decision_id = _digest(payload)
        row = self._conn.execute(
            "SELECT payload_json FROM policy_reviews WHERE decision_id=?", (decision_id,)
        ).fetchone()
        if row is not None:
            if row["payload_json"] != payload:
                raise ValueError("policy decision identity conflict")
            return
        with self._conn:
            self._conn.execute(
                "INSERT INTO policy_reviews(decision_id,candidate_id,entry_id,payload_json) VALUES (?,?,?,?)",
                (decision_id, decision.candidate_id, decision.entry_id, payload),
            )

    def record_transition(self, event: QualificationEvent) -> None:
        current = self.candidate(event.candidate_id)
        if current is None:
            raise ValueError("candidate does not exist")
        event_payload = _json(event.to_dict())
        event_id = event.event_id or _digest(event_payload)
        existing_event = self._conn.execute(
            "SELECT payload_json FROM qualification_events WHERE event_id=?", (event_id,)
        ).fetchone()
        if existing_event is not None:
            if existing_event["payload_json"] != event_payload:
                raise ValueError("qualification event identity conflict")
            return
        if current.qualification_state is not event.old_state:
            raise ValueError(
                f"candidate state mismatch: current={current.qualification_state.value}, event={event.old_state.value}"
            )
        updated = replace(current, qualification_state=event.new_state)
        updated_payload = _json(updated.to_dict())
        with self._conn:
            self._conn.execute(
                "INSERT INTO qualification_events(event_id,candidate_id,old_state,new_state,payload_json) VALUES (?,?,?,?,?)",
                (event_id, event.candidate_id, event.old_state.value, event.new_state.value, event_payload),
            )
            self._conn.execute(
                "UPDATE candidates SET qualification_state=?,payload_json=? WHERE candidate_id=?",
                (event.new_state.value, updated_payload, event.candidate_id),
            )

    def replace_duplicate_groups(self, groups: Iterable[DuplicateGroup]) -> None:
        supplied = tuple(groups)
        with self._conn:
            self._conn.execute("DELETE FROM duplicate_members")
            self._conn.execute("DELETE FROM duplicate_groups")
            for group in supplied:
                self._conn.execute(
                    "INSERT INTO duplicate_groups(group_id,payload_json) VALUES (?,?)",
                    (group.group_id, _json(group.to_dict())),
                )
                for candidate_id in group.member_ids:
                    self._conn.execute(
                        "INSERT INTO duplicate_members(group_id,candidate_id) VALUES (?,?)",
                        (group.group_id, candidate_id),
                    )

    def record_provider_links(self, links: Iterable[ProviderLink]) -> int:
        inserted = 0
        seen: set[str] = set()
        with self._conn:
            for link in links:
                payload = _json(link.to_dict())
                link_id = link.link_id or _digest(payload)
                if link_id in seen:
                    continue
                seen.add(link_id)
                row = self._conn.execute(
                    "SELECT payload_json FROM provider_links WHERE link_id=?", (link_id,)
                ).fetchone()
                if row is not None:
                    if row["payload_json"] != payload:
                        raise ValueError("provider link identity conflict")
                    continue
                self._conn.execute(
                    "INSERT INTO provider_links(link_id,candidate_id,provider_id,operation_id,payload_json) VALUES (?,?,?,?,?)",
                    (link_id, link.candidate_id, link.provider_id, link.operation_id, payload),
                )
                inserted += 1
        return inserted

    def candidate(self, candidate_id: str) -> Candidate | None:
        row = self._conn.execute(
            "SELECT payload_json FROM candidates WHERE candidate_id=?", (candidate_id,)
        ).fetchone()
        return None if row is None else _candidate_from_json(row["payload_json"])

    def candidates(self) -> list[Candidate]:
        rows = self._conn.execute(
            "SELECT payload_json FROM candidates ORDER BY candidate_id"
        ).fetchall()
        return [_candidate_from_json(row["payload_json"]) for row in rows]

    def summary(self) -> dict[str, object]:
        tables = (
            "catalog_snapshots",
            "catalog_entries",
            "candidates",
            "candidate_catalog_links",
            "duplicate_groups",
            "duplicate_members",
            "qualification_events",
            "policy_reviews",
            "provider_links",
        )
        result: dict[str, object] = {}
        for table in tables:
            result[table] = int(self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        result["execution_authorized"] = False
        result["production_decision_authorized"] = False
        return result

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "RegistryStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


__all__ = ["RegistryStore"]
