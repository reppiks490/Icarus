from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from icarus_engine import corpus


class FakeFeed:
    dataset = "GLBX.MDP3"
    roll_rule = "v"

    def __init__(self, api_key=None, roll_rule=None):
        self.roll_rule = roll_rule or "v"

    @staticmethod
    def root(symbol):
        return {"NQ": "NQ", "ES": "ES"}[symbol]

    def continuous_symbol(self, symbol, roll_rule=None):
        return f"{self.root(symbol)}.{roll_rule or self.roll_rule}.0"

    def candles(self, symbol, granularity, start_ts, end_ts):
        if symbol == "ES":
            raise RuntimeError("entitlement missing")
        assert granularity == 300
        return [
            SimpleNamespace(ts=start_ts, o=1.0, h=2.0, l=0.5, c=1.5, v=10),
            SimpleNamespace(ts=start_ts + 300, o=1.5, h=2.5, l=1.0, c=2.0, v=12),
        ]

    def close(self):
        return None


def test_databento_corpus_writes_rows_manifest_and_never_secret(monkeypatch, tmp_path):
    monkeypatch.setattr(corpus, "Databento", FakeFeed)
    out = corpus.build_databento_corpus(
        tmp_path,
        start="2026-10-01T00:00:00Z",
        end="2026-10-02T00:00:00Z",
        minutes=5,
        assets=["NQ", "ES"],
        api_key="SECRET-DO-NOT-WRITE",
    )

    assert out["schema_version"] == "icarus-databento-corpus-v1"
    assert out["assets"]["NQ"]["status"] == "OK"
    assert out["assets"]["NQ"]["rows"] == 2
    assert out["assets"]["NQ"]["databento_symbol"] == "NQ.v.0"
    assert out["assets"]["ES"]["status"] == "ERROR"
    assert out["ok_count"] == 1 and out["error_count"] == 1

    csv_text = (tmp_path / "nq_5m.csv").read_text()
    assert csv_text.startswith("ts,open,high,low,close,volume\n")
    manifest = (tmp_path / "manifest.json").read_text()
    assert "SECRET-DO-NOT-WRITE" not in manifest
    assert "SECRET-DO-NOT-WRITE" not in csv_text
    assert json.loads(manifest)["timestamp_semantics"] == "bar_open_utc"


def test_registered_futures_are_unique_roots():
    rows = corpus.registered_futures()
    assert "NQ" in rows
    assert len(rows) == len(set(rows))


@pytest.mark.parametrize("start,end", [
    ("2026-10-02T00:00:00Z", "2026-10-01T00:00:00Z"),
    ("2026-10-01T00:00:00Z", "2026-10-01T00:00:00Z"),
])
def test_corpus_rejects_invalid_window(monkeypatch, tmp_path, start, end):
    monkeypatch.setattr(corpus, "Databento", FakeFeed)
    with pytest.raises(ValueError, match="end must be after start"):
        corpus.build_databento_corpus(tmp_path, start=start, end=end, assets=["NQ"])
