from __future__ import annotations

import json
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from icarus_engine.brain import _stored_event, brain_snapshot, record_brain_event
from icarus_engine.brain_sync import BrainRemoteSync
from tests_engine.test_brain_sync import (
    _consumer_contract,
    _fixture,
    _historical_context_contract,
    _historical_docs,
    _remote_event,
)


def _run_gate(receipt_count, mutation=None):
    consumer = _consumer_contract(historical_context=_historical_context_contract())
    remote = _fixture(_remote_event(), consumer=consumer, historical_docs=_historical_docs())

    def fixture_sync(base_dir, **kwargs):
        sync = BrainRemoteSync(
            base_dir, fetch_json=remote["fetch_json"], fetch_bytes=remote["fetch_bytes"],
            now_utc=remote["now_utc"],
        )

        def sync_once():
            state = sync.sync_once()
            for number in range(receipt_count):
                record_brain_event(base_dir, {
                    "kind": "agent", "subject": "flow", "status": "observed",
                    "summary": f"Later ordinary receipt {number}",
                })
            if mutation:
                path = Path(base_dir) / "audit" / "brain_events.jsonl"
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                mutation(rows)
                path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            return state

        return SimpleNamespace(sync_once=sync_once)

    # Execute CI's actual ingest/readback/assertion block so a regression to the
    # bounded snapshot cannot be hidden by a separate test implementation.
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/live-engine-historical-context-gate.yml"
    python_block = textwrap.dedent(
        workflow.read_text().split("python - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
    )
    gate_block = python_block[python_block.index("with tempfile.TemporaryDirectory() as tmp:"):]
    gate_block = gate_block.split("\nreport = {", 1)[0]
    namespace = {
        "BrainRemoteSync": fixture_sync, "brain_snapshot": brain_snapshot,
        "_stored_event": _stored_event, "consumer": consumer, "json": json,
        "tempfile": tempfile, "datetime": datetime, "timezone": timezone, "Path": Path,
        "fetch_json": remote["fetch_json"], "fetch_bytes": remote["fetch_bytes"],
    }
    exec(compile(gate_block, f"{workflow} (inline Python)", "exec"), namespace)
    return namespace


@pytest.mark.parametrize("receipt_count", [200, 1001])
def test_historical_context_gate_checks_journal_beyond_snapshot_window(receipt_count):
    result = _run_gate(receipt_count)

    assert result["state"]["historical_context_ingested_total"] == 4
    assert len(result["historical_events"]) == 4
    assert len(result["snap"]["events"]) == 200
    assert not any(
        row["details"].get("foreign_historical_context") is True
        for row in result["snap"]["events"]
    )


@pytest.mark.parametrize("mutation", [lambda rows: rows.pop(0), lambda rows: rows.append(rows[0])])
def test_historical_context_gate_rejects_missing_or_duplicate_durable_records(mutation):
    with pytest.raises(AssertionError, match="durable historical event count"):
        _run_gate(200, mutation)


@pytest.mark.parametrize(
    "field, value, error",
    [("summary", "tampered", "semantic payload"),
     ("execution_authorized", True, "cannot authorize")],
)
def test_historical_context_gate_rejects_tampered_records_outside_snapshot(field, value, error):
    def tamper(rows):
        rows[0][field] = value

    with pytest.raises(ValueError, match=error):
        _run_gate(200, tamper)


def test_historical_context_gate_rejects_malformed_record_outside_snapshot():
    with pytest.raises(ValueError, match="stored brain event must be an object"):
        _run_gate(200, lambda rows: rows.insert(0, None))
