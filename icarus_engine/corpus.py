"""Local Databento corpus export for ICARUS continuous futures.

The exporter reuses the existing icarus_engine.feeds.databento adapter; it does
not introduce another market-data client. Raw historical rows stay on the
operator machine. No API key is ever written to output files.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .assets import REGISTRY, resolve
from .feeds.databento import Databento


SCHEMA = "icarus-databento-corpus-v1"


def _utc_ts(value: str | int | float | datetime) -> int:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("timestamp is required")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.astimezone(timezone.utc).timestamp())


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), timezone.utc).isoformat().replace("+00:00", "Z")


def registered_futures() -> list[str]:
    """Return one canonical ICARUS token for every registered futures root."""
    seen: set[str] = set()
    out: list[str] = []
    for spec in REGISTRY.values():
        if spec.kind != "futures":
            continue
        root = str(spec.ticker).upper()
        if root.endswith("=F"):
            root = root[:-2]
        if root in seen:
            continue
        seen.add(root)
        out.append(spec.symbol)
    return sorted(out)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _csv_bytes(bars) -> bytes:
    rows = ["ts,open,high,low,close,volume"]
    for bar in bars:
        rows.append(
            f"{_iso(bar.ts)},{bar.o:.12g},{bar.h:.12g},{bar.l:.12g},{bar.c:.12g},{bar.v:.12g}"
        )
    return ("\n".join(rows) + "\n").encode("utf-8")


def build_databento_corpus(
    out_dir: str | os.PathLike,
    *,
    start: str | int | float | datetime,
    end: str | int | float | datetime,
    minutes: int = 5,
    assets: Optional[Iterable[str]] = None,
    api_key: Optional[str] = None,
    roll_rule: Optional[str] = None,
) -> dict:
    """Export continuous-futures OHLCV and a provenance manifest.

    End is exclusive. One asset failure is recorded without erasing successful
    siblings. The Databento API key is consumed only by the adapter and is never
    persisted.
    """
    start_ts = _utc_ts(start)
    end_ts = _utc_ts(end)
    if end_ts <= start_ts:
        raise ValueError("end must be after start")
    minutes = int(minutes)
    if minutes <= 0:
        raise ValueError("minutes must be positive")
    granularity = minutes * 60

    requested = [str(x).strip() for x in (assets or registered_futures()) if str(x).strip()]
    if not requested:
        raise ValueError("at least one asset is required")

    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    feed = Databento(api_key=api_key, roll_rule=roll_rule)
    manifest = {
        "schema_version": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "provider": "databento",
        "dataset": feed.dataset,
        "roll_rule": feed.roll_rule,
        "start": _iso(start_ts),
        "end_exclusive": _iso(end_ts),
        "minutes": minutes,
        "timestamp_semantics": "bar_open_utc",
        "execution_authorized": False,
        "assets": {},
    }

    try:
        for token in requested:
            entry = {"requested": token, "status": "ERROR"}
            try:
                spec = resolve(token)
                if spec.kind != "futures":
                    raise ValueError(f"{token}: only registered futures are eligible")
                bars = feed.candles(token, granularity, start_ts, end_ts)
                if not bars:
                    raise ValueError("no bars returned")
                root = Databento.root(token)
                name = f"{root.lower()}_{minutes}m.csv"
                payload = _csv_bytes(bars)
                path = dest / name
                _atomic_text(path, payload.decode("utf-8"))
                entry.update(
                    status="OK",
                    symbol=spec.symbol,
                    tv_symbol=spec.tv_symbol,
                    provider_ticker=spec.ticker,
                    databento_symbol=feed.continuous_symbol(token, feed.roll_rule),
                    file=name,
                    rows=len(bars),
                    first=_iso(bars[0].ts),
                    last=_iso(bars[-1].ts),
                    sha256=hashlib.sha256(payload).hexdigest(),
                )
            except Exception as ex:
                entry["error"] = f"{type(ex).__name__}: {ex}"[:500]
            manifest["assets"][token] = entry
    finally:
        try:
            feed.close()
        except Exception:
            pass

    manifest["ok_count"] = sum(1 for row in manifest["assets"].values() if row.get("status") == "OK")
    manifest["error_count"] = len(manifest["assets"]) - manifest["ok_count"]
    _atomic_text(dest / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
