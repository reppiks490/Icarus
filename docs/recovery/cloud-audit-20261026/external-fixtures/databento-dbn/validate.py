"""Verify pinned fixture bytes and exercise the installed Icarus/DBN adapters offline."""
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path

import databento
from icarus_engine.feeds.databento import Databento


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "manifest.json").read_text())
    results = []
    for item in manifest["files"]:
        path = root / item["file"]
        if path.parent != root or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Fixture path/hash mismatch")
        if path.suffix != ".dbn":
            continue
        normalized = []
        for record in databento.DBNStore.from_file(path):
            if type(record).__name__ in ("MBOMsg", "MBP10Msg"):
                normalized.append(Databento._event_record(record))
            elif type(record).__name__ == "OHLCVMsg":
                normalized.append(asdict(Databento._ohlcv_record(record)))
            else:
                raise ValueError("Unexpected fixture record schema")
        if not normalized:
            raise ValueError("Fixture contains no adapter-consumable records")
        results.append({"file": path.name, "normalized_records": normalized})
    print(json.dumps({"authority": "OFFLINE_PARSER_COMPATIBILITY_ONLY",
                      "execution_authorized": False,
                      "databento_version": importlib.metadata.version("databento"),
                      "files": results}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
