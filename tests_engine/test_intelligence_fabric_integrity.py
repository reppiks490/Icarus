from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from icarus_engine.intelligence_fabric import IntelligenceEvent, IntelligenceFabric


class _ChangingPayload(Mapping):
    """Return a different value each time the mapping is materialized."""

    def __init__(self) -> None:
        self._reads = 0

    def __iter__(self):
        return iter(("revision",))

    def __len__(self) -> int:
        return 1

    def __getitem__(self, key: str) -> int:
        if key != "revision":
            raise KeyError(key)
        self._reads += 1
        return self._reads


def _event(payload: Mapping) -> IntelligenceEvent:
    return IntelligenceEvent(
        event_type="system",
        source="integrity-test",
        source_kind="system",
        channel="system",
        thread_key="integrity:hash-once",
        title="Envelope integrity probe",
        body="The durable envelope and event identity must describe the same bytes.",
        observed_at="2026-10-13T01:00:00Z",
        received_at="2026-10-13T01:00:01Z",
        severity=1,
        urgency=0.1,
        payload=payload,
    )


def test_publish_hashes_the_exact_envelope_it_persists() -> None:
    with IntelligenceFabric(":memory:") as fabric:
        receipt = fabric.publish(_event(_ChangingPayload()))
        stored = fabric.get(receipt["event_id"])

    assert stored is not None
    envelope = {
        key: value
        for key, value in stored.items()
        if key not in {"sequence", "event_id", "attention_score"}
    }
    expected = hashlib.sha256(
        json.dumps(envelope, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    assert receipt["event_id"] == expected
