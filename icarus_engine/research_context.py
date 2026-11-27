"""Read-only, provenance-preserving historical macro context snapshots."""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit


_DATA_DIR = Path(__file__).parent / "data" / "research_context"
_SCHEMA = "icarus.market-context.v1"
_MAX_FILE_BYTES = 5 * 1024 * 1024
_MAX_ROWS = 50_000
_MAX_LIMIT = 365
_STALE_AFTER_DAYS = 5


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as ex:
        raise ValueError("market context dates must use YYYY-MM-DD") from ex


def _now(value=None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError("now must be an ISO timestamp or datetime")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _https(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


class MarketContextStore:
    """Loads a small fixed set of reviewed EIA snapshots, never a trading feed."""

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir is not None else _DATA_DIR

    def _manifest(self):
        path = self.data_dir / "manifest.json"
        if not path.is_file() or path.stat().st_size > _MAX_FILE_BYTES:
            raise ValueError("market context manifest is unavailable or too large")
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as ex:
            raise ValueError("market context manifest is invalid") from ex
        if not isinstance(manifest, dict) or manifest.get("schema_version") != _SCHEMA:
            raise ValueError("market context manifest schema is unsupported")
        datasets = manifest.get("datasets")
        if not isinstance(datasets, list) or not datasets:
            raise ValueError("market context datasets are missing")
        return manifest

    def _read_dataset(self, item, now, limit):
        if not isinstance(item, dict):
            raise ValueError("market context dataset metadata is invalid")
        for key in ("id", "name", "filename", "unit", "frequency", "source", "source_url",
                    "snapshot_url", "upstream_license", "catalog_status", "sha256"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"market context dataset field {key} is invalid")
        if item["catalog_status"] != "ACTIVE_RESEARCH_CONTEXT":
            raise ValueError("only reviewed research-context datasets may be loaded")
        if not _https(item["source_url"]) or not _https(item["snapshot_url"]):
            raise ValueError("market context source links must use HTTPS")
        filename = item["filename"]
        if Path(filename).name != filename or filename in (".", ".."):
            raise ValueError("market context filename is invalid")
        base = self.data_dir.resolve()
        path = (self.data_dir / filename).resolve()
        if path.parent != base or not path.is_file() or path.stat().st_size > _MAX_FILE_BYTES:
            raise ValueError("market context filename must resolve to a bounded snapshot file")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if item["sha256"] != digest:
            raise ValueError("market context snapshot SHA-256 does not match its manifest")

        observations = []
        previous = None
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames != ["Date", "Price"]:
                    raise ValueError("market context CSV must contain exactly Date,Price")
                for row in reader:
                    if len(observations) >= _MAX_ROWS:
                        raise ValueError("market context CSV has too many rows")
                    if None in row or set(row) != {"Date", "Price"}:
                        raise ValueError("market context CSV row shape is invalid")
                    day = _date(row["Date"])
                    if previous is not None and day <= previous:
                        raise ValueError("market context dates must be strictly increasing")
                    previous = day
                    raw = (row["Price"] or "").strip()
                    if raw:
                        try:
                            price = float(raw)
                        except ValueError as ex:
                            raise ValueError("market context price must be numeric or blank") from ex
                        if not math.isfinite(price):
                            raise ValueError("market context prices must be finite")
                        flags = []
                    else:
                        price, flags = None, ["missing_price"]
                    observations.append({"date": day.isoformat(), "price": price, "quality_flags": flags})
        except UnicodeDecodeError as ex:
            raise ValueError("market context CSV is not valid UTF-8") from ex
        if not observations:
            raise ValueError("market context CSV contains no observations")

        valid = [row for row in observations if row["price"] is not None]
        if not valid:
            raise ValueError("market context CSV contains no usable prices")
        latest = valid[-1]
        age = (now.date() - _date(latest["date"])).days
        return {
            "id": item["id"], "name": item["name"], "unit": item["unit"],
            "frequency": item["frequency"], "source": item["source"],
            "source_url": item["source_url"], "snapshot_url": item["snapshot_url"],
            "upstream_license": item["upstream_license"],
            "catalog_status": item["catalog_status"],
            "snapshot_retrieved_on": item.get("snapshot_retrieved_on"),
            "latest_observation_at": latest["date"], "latest_price": latest["price"],
            "freshness": "STALE" if age > _STALE_AFTER_DAYS else "RECENT",
            "latest_observation_age_days": max(0, age),
            "first_row_date": observations[0]["date"], "last_row_date": observations[-1]["date"],
            "observation_count": len(observations),
            "missing_value_count": sum(row["price"] is None for row in observations),
            "observations": observations[-limit:],
            "authority": "RESEARCH_CONTEXT_ONLY", "execution_authorized": False,
        }

    def snapshot(self, *, limit=90, now=None):
        if type(limit) is not int or not 1 <= limit <= _MAX_LIMIT:
            raise ValueError(f"limit must be an integer from 1 to {_MAX_LIMIT}")
        captured = _now(now)
        manifest = self._manifest()
        datasets = [self._read_dataset(item, captured, limit) for item in manifest["datasets"]]
        catalog = manifest.get("catalog")
        if not isinstance(catalog, dict) or not isinstance(catalog.get("sources"), list):
            raise ValueError("market context source catalog is invalid")
        sources = catalog["sources"]
        for item in sources:
            if (not isinstance(item, dict) or item.get("status") not in
                    ("ACTIVE_RESEARCH_CONTEXT", "QUARANTINED", "UNAVAILABLE")):
                raise ValueError("market context source catalog status is invalid")
            if (type(item.get("active_series")) is not int or item["active_series"] < 0
                    or not isinstance(item.get("id"), str) or not isinstance(item.get("name"), str)
                    or not isinstance(item.get("reason"), str) or not _https(item.get("source_url", ""))):
                raise ValueError("market context source catalog entry is invalid")
            if item["status"] != "ACTIVE_RESEARCH_CONTEXT" and item["active_series"] != 0:
                raise ValueError("quarantined sources cannot contribute active series")
        active_series = sum(item["active_series"] for item in sources)
        if active_series != len(datasets):
            raise ValueError("active source catalog entries must match reviewed dataset series")
        return {
            "schema_version": _SCHEMA,
            "snapshot_retrieved_on": manifest.get("snapshot_retrieved_on"),
            "catalog": {
                "sources": len(sources), "active_series": len(datasets),
                "quarantined_sources": sum(item["status"] != "ACTIVE_RESEARCH_CONTEXT" for item in sources),
                "reviewed_sources": sources,
            },
            "datasets": datasets,
            "authority": "RESEARCH_CONTEXT_ONLY", "execution_authorized": False,
            "note": "Historical source snapshots are separate from futures bars, signals, qualification, and orders.",
        }
