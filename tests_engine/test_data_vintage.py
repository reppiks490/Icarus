from __future__ import annotations

import sqlite3
from pathlib import Path

from icarus_plant.drop import ingest_file


_CSV = (
    "time,open,high,low,close,Volume\n"
    "2026-09-14T13:30:00Z,24700,24701,24699,24700.5,4\n"
    "2026-09-14T13:31:00Z,24700.5,24702,24700,24701,5\n"
)


def test_ingest_creates_append_only_market_data_observation_ledger(tmp_path):
    src = tmp_path / "CME_MINI_NQ1!, 1.csv"
    src.write_text(_CSV, encoding="utf-8")

    ingest_file(str(src), root=str(tmp_path))

    ledger = tmp_path / "history" / "vintage.sqlite3"
    assert ledger.is_file(), "market-data ingest must preserve an as-observed provenance ledger"

    with sqlite3.connect(ledger) as con:
        batches = con.execute(
            "SELECT source_sha256, symbol, minutes, row_count FROM ingest_batches"
        ).fetchall()
        observations = con.execute(
            "SELECT event_ts, disposition, value_sha256 FROM bar_observations ORDER BY event_ts"
        ).fetchall()

    assert len(batches) == 1
    assert batches[0][1:] == ("NQ", 1, 2)
    assert len(observations) == 2
    assert [row[1] for row in observations] == ["FIRST_CAPTURED", "FIRST_CAPTURED"]
    assert all(str(row[2]).startswith("sha256:") for row in observations)
