from __future__ import annotations

import sqlite3


def _body(*, observed="2026-10-01T14:00:00Z", received="2026-10-01T14:00:01Z", subject="NQ:trade"):
    return {
        "kind": "observed",
        "subject": subject,
        "value": {"price": 25001.0, "size": 2.0},
        "source": {
            "subsystem": "argus",
            "source_repo": "reppiks490/Icarus",
            "source_commit": "a" * 40,
            "source_record_id": f"{subject}:{observed}:{received}",
        },
        "observed_at": observed,
        "received_at": received,
        "calculated_at": received,
        "valid_from": observed,
        "valid_until": None,
        "confidence": 0.9,
        "quality": 0.95,
        "dependencies": [],
        "contradictions": [],
        "falsifiers": ["source correction"],
    }


def test_apex_store_is_wal_idempotent_and_reopens_deterministically(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store = ApexStore(tmp_path)
    assert store.journal_mode == "wal"
    first = store.record_evidence(_body())
    second = store.record_evidence(_body())
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert first["evidence"]["evidence_id"] == second["evidence"]["evidence_id"]
    before = store.evidence_as_of("2026-10-01T14:10:00Z")
    assert len(before) == 1
    store.close()
    reopened = ApexStore(tmp_path)
    assert reopened.evidence_as_of("2026-10-01T14:10:00Z") == before
    assert reopened.integrity_status()["evidence_rows"] == 1
    reopened.close()


def test_as_of_requires_both_observed_and_received_time_not_after_boundary(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store = ApexStore(tmp_path)
    store.record_evidence(_body(observed="2026-10-01T14:00:00Z", received="2026-10-01T14:05:00Z"))
    assert store.evidence_as_of("2026-10-01T14:04:59Z") == []
    assert len(store.evidence_as_of("2026-10-01T14:05:00Z")) == 1


def test_future_received_at_is_not_visible_even_if_observed_at_is_old(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store = ApexStore(tmp_path)
    store.record_evidence(_body(observed="2026-09-30T12:00:00Z", received="2026-10-01T16:00:00Z"))
    assert store.evidence_as_of("2026-10-01T15:59:59Z") == []


def test_corrupt_evidence_row_is_quarantined_and_reported(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store = ApexStore(tmp_path)
    result = store.record_evidence(_body())
    evidence_id = result["evidence"]["evidence_id"]
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE evidence SET semantic_json = ? WHERE evidence_id = ?", ('{"broken":', evidence_id))
        conn.commit()
    assert store.evidence_as_of("2026-10-01T14:10:00Z") == []
    status = store.integrity_status()
    assert status["integrity_ok"] is False
    assert status["corrupt_rows"] == 1
    assert status["quarantined_evidence_ids"] == [evidence_id]


def test_duplicate_retry_returns_same_evidence_id_without_second_row(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store = ApexStore(tmp_path)
    one = store.record_evidence(_body())
    two = store.record_evidence(_body())
    assert one["evidence"]["evidence_id"] == two["evidence"]["evidence_id"]
    assert store.integrity_status()["evidence_rows"] == 1


def test_subject_filter_is_applied_after_causal_time_gate(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store = ApexStore(tmp_path)
    store.record_evidence(_body(subject="NQ:trade"))
    store.record_evidence(_body(subject="ES:trade"))
    rows = store.evidence_as_of("2026-10-01T14:10:00Z", subject="NQ:trade")
    assert [row["subject"] for row in rows] == ["NQ:trade"]


def test_local_receipt_gate_prevents_backdated_network_style_evidence(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store = ApexStore(tmp_path)
    body = _body(
        observed="2000-01-01T00:00:00Z",
        received="2000-01-01T00:00:01Z",
    )
    saved = store.record_evidence(body, local_received_at="2026-10-01T18:00:00Z")
    assert saved["idempotent"] is False
    assert store.evidence_as_of("2000-01-01T00:10:00Z") == []
    assert len(store.evidence_as_of("2026-10-01T18:00:00Z")) == 1


def test_apex_store_migrates_pre_local_receipt_schema(tmp_path):
    from pathlib import Path
    from icarus_engine.apex.store import ApexStore

    research = Path(tmp_path) / "research"
    research.mkdir(parents=True)
    db = research / "apex.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """CREATE TABLE evidence (
                evidence_id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                kind TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                calculated_at TEXT NOT NULL,
                observed_ts REAL NOT NULL,
                received_ts REAL NOT NULL,
                semantic_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            )"""
        )
        conn.commit()

    store = ApexStore(tmp_path)
    with sqlite3.connect(store.path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(evidence)").fetchall()}
    assert "local_received_ts" in columns
