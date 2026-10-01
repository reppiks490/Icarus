"""Durable provenance ledger for ICARUS Ψ optional force evidence.

This module is intentionally storage-only. It does not score evidence, infer market
state, or authorize production decisions/execution. Causal validity (future/stale
receipt rejection) remains owned by PossibilityEngine before records enter here.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "icarus-psi-evidence-v1"


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


class PsiEvidenceLedger:
    """Append-only, idempotent evidence receipts with deterministic as-of selection."""

    def __init__(self, base_dir: str | Path | None):
        self._lock = threading.RLock()
        self.path = (Path(base_dir) / "research" / "psi_evidence.sqlite3") if base_dir else None
        self._memory: dict[str, dict[str, Any]] = {}
        self._integrity_cache: tuple[float, dict[str, Any]] = (0.0, {})
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._init_store()

    @property
    def durable(self) -> bool:
        return self.path is not None

    def _connect(self) -> sqlite3.Connection:
        if self.path is None:
            raise RuntimeError("durable Psi evidence store unavailable")
        con = sqlite3.connect(str(self.path), timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        return con

    def _init_store(self) -> None:
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    feature TEXT NOT NULL,
                    value REAL NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    observed_ts REAL NOT NULL,
                    received_ts REAL NOT NULL,
                    expires_ts REAL NOT NULL,
                    ttl_seconds REAL NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_psi_evidence_asset_feature_time
                    ON evidence(asset, feature, observed_ts DESC, received_ts DESC);
                CREATE INDEX IF NOT EXISTS idx_psi_evidence_expiry
                    ON evidence(expires_ts);
                """
            )
            columns = {
                str(row["name"])
                for row in con.execute("PRAGMA table_info(evidence)").fetchall()
            }
            expected = {
                "evidence_id", "schema_version", "asset", "feature", "value",
                "confidence", "source", "observed_at", "observed_ts", "received_ts",
                "expires_ts", "ttl_seconds", "payload_hash", "created_at",
            }
            missing = expected - columns
            if missing:
                raise RuntimeError(
                    "Psi evidence schema is incompatible; missing columns: "
                    + ", ".join(sorted(missing))
                )

    @staticmethod
    def _identity(row: Mapping[str, Any]) -> tuple[str, str]:
        identity = {
            "schema_version": SCHEMA_VERSION,
            "asset": str(row["asset"]).upper(),
            "feature": str(row["feature"]),
            "value": float(row["value"]),
            "confidence": float(row["confidence"]),
            "source": str(row["source"]),
            "observed_at": str(row["observed_at"]),
            "ttl_seconds": float(row["ttl_seconds"]),
        }
        raw = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return "psi-" + digest[:32], digest

    def _prepare(self, row: Mapping[str, Any]) -> dict[str, Any]:
        required = {
            "asset", "feature", "value", "confidence", "source", "observed_at",
            "observed_ts", "received_ts", "expires_ts", "ttl_seconds", "created_at",
        }
        missing = required - set(row)
        if missing:
            raise ValueError("missing Psi evidence fields: " + ", ".join(sorted(missing)))

        evidence_id, payload_hash = self._identity(row)
        stored = {
            "evidence_id": evidence_id,
            "schema_version": SCHEMA_VERSION,
            "asset": str(row["asset"]).upper(),
            "feature": str(row["feature"]),
            "value": float(row["value"]),
            "confidence": float(row["confidence"]),
            "source": str(row["source"]),
            "observed_at": str(row["observed_at"]),
            "observed_ts": float(row["observed_ts"]),
            "received_ts": float(row["received_ts"]),
            "expires_ts": float(row["expires_ts"]),
            "ttl_seconds": float(row["ttl_seconds"]),
            "payload_hash": payload_hash,
            "created_at": str(row["created_at"]),
        }
        for field in ("value", "confidence", "observed_ts", "received_ts", "expires_ts", "ttl_seconds"):
            if _finite(stored[field]) is None:
                raise ValueError(f"{field} must be finite")
        return stored

    def record_many(self, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Atomically record one evidence submission.

        SQLite commits all prepared receipts in one transaction. The in-memory
        fallback stages new rows and publishes them only after every row is prepared.
        """
        prepared = [self._prepare(row) for row in rows]
        if not prepared:
            return []

        with self._lock:
            if self.path is None:
                staged = dict(self._memory)
                results: list[dict[str, Any]] = []
                for stored in prepared:
                    evidence_id = stored["evidence_id"]
                    existing = staged.get(evidence_id)
                    if existing is not None:
                        results.append({**dict(existing), "inserted": False})
                    else:
                        staged[evidence_id] = dict(stored)
                        results.append({**stored, "inserted": True})
                self._memory = staged
                self._integrity_cache = (0.0, {})
                return results

            results = []
            with self._connect() as con:
                for stored in prepared:
                    cur = con.execute(
                        """INSERT OR IGNORE INTO evidence(
                               evidence_id,schema_version,asset,feature,value,confidence,source,
                               observed_at,observed_ts,received_ts,expires_ts,ttl_seconds,
                               payload_hash,created_at
                           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            stored["evidence_id"], stored["schema_version"], stored["asset"],
                            stored["feature"], stored["value"], stored["confidence"], stored["source"],
                            stored["observed_at"], stored["observed_ts"], stored["received_ts"],
                            stored["expires_ts"], stored["ttl_seconds"], stored["payload_hash"],
                            stored["created_at"],
                        ),
                    )
                    if cur.rowcount > 0:
                        results.append({**stored, "inserted": True})
                        continue
                    existing = con.execute(
                        """SELECT evidence_id,schema_version,asset,feature,value,confidence,source,
                                  observed_at,observed_ts,received_ts,expires_ts,ttl_seconds,
                                  payload_hash,created_at
                           FROM evidence WHERE evidence_id=?""",
                        (stored["evidence_id"],),
                    ).fetchone()
                    if existing is None:
                        raise RuntimeError("idempotent Psi evidence receipt disappeared after INSERT OR IGNORE")
                    results.append({**dict(existing), "inserted": False})
            self._integrity_cache = (0.0, {})
            return results

    def record(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return self.record_many([row])[0]

    @staticmethod
    def _select(
        rows: Sequence[Mapping[str, Any]],
        *,
        as_of_ts: float,
        asset_filter: str,
    ) -> dict[str, dict[str, Any]]:
        ordered = sorted(
            (dict(row) for row in rows),
            key=lambda row: (
                float(row.get("observed_ts") or -1.0),
                float(row.get("received_ts") or -1.0),
                str(row.get("evidence_id") or ""),
            ),
            reverse=True,
        )
        selected: dict[str, dict[str, Any]] = {}
        for row in ordered:
            observed_ts = _finite(row.get("observed_ts"))
            expires_ts = _finite(row.get("expires_ts"))
            if observed_ts is None or expires_ts is None:
                continue
            received_ts = _finite(row.get("received_ts"))
            if received_ts is None:
                continue
            if not (observed_ts <= as_of_ts and received_ts <= as_of_ts < expires_ts):
                continue
            feature = str(row.get("feature") or "")
            asset = str(row.get("asset") or "").upper()
            key = feature if asset_filter else f"{asset}:{feature}"
            if feature and key not in selected:
                selected[key] = row
        return selected

    def _memory_rows(self, asset: str, as_of_ts: float, include_expired: bool) -> list[dict[str, Any]]:
        rows = []
        for row in self._memory.values():
            if asset and row["asset"] != asset:
                continue
            if row["observed_ts"] > as_of_ts or row["received_ts"] > as_of_ts:
                continue
            if not include_expired and row["expires_ts"] <= as_of_ts:
                continue
            rows.append(dict(row))
        rows.sort(
            key=lambda row: (row["observed_ts"], row["received_ts"], row["evidence_id"]),
            reverse=True,
        )
        return rows

    def _active_rows(self, asset: str, as_of_ts: float) -> list[dict[str, Any]]:
        asset = str(asset or "").strip().upper()
        if self.path is None:
            return self._memory_rows(asset, as_of_ts, include_expired=False)
        with self._connect() as con:
            return [
                dict(row) for row in con.execute(
                    """SELECT evidence_id,schema_version,asset,feature,value,confidence,source,
                              observed_at,observed_ts,received_ts,expires_ts,ttl_seconds,
                              payload_hash,created_at
                       FROM evidence
                       WHERE asset=? AND observed_ts<=? AND received_ts<=? AND expires_ts>?
                       ORDER BY observed_ts DESC, received_ts DESC, evidence_id DESC""",
                    (asset, as_of_ts, as_of_ts, as_of_ts),
                ).fetchall()
            ]

    def active(self, asset: str, *, as_of_ts: float | None = None) -> dict[str, dict[str, Any]]:
        asset = str(asset or "").strip().upper()
        ts = time.time() if as_of_ts is None else float(as_of_ts)
        rows = self._active_rows(asset, ts)
        return self._select(rows, as_of_ts=ts, asset_filter=asset)

    def active_by_source(self, asset: str, *, as_of_ts: float | None = None) -> dict[str, list[dict[str, Any]]]:
        """Latest causally-active receipt per feature and source."""
        asset = str(asset or "").strip().upper()
        ts = time.time() if as_of_ts is None else float(as_of_ts)
        rows = self._active_rows(asset, ts)
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            key = (str(row.get("feature") or ""), str(row.get("source") or ""))
            if not key[0] or not key[1] or key in latest:
                continue
            latest[key] = dict(row)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for (feature, _source), row in latest.items():
            grouped[feature].append(row)
        for feature in grouped:
            grouped[feature].sort(key=lambda row: str(row.get("source") or ""))
        return dict(grouped)

    def disagreement(self, asset: str, *, as_of_ts: float | None = None) -> dict[str, dict[str, Any]]:
        groups = self.active_by_source(asset, as_of_ts=as_of_ts)
        out: dict[str, dict[str, Any]] = {}
        for feature, rows in groups.items():
            values = [float(row["value"]) for row in rows]
            weights = [max(0.0, float(row["confidence"])) for row in rows]
            total = sum(weights)
            mean = sum(v * w for v, w in zip(values, weights)) / total if total > 0 else sum(values) / len(values)
            variance = (
                sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / total
                if total > 0 else sum((v - mean) ** 2 for v in values) / len(values)
            )
            spread = max(values) - min(values) if values else 0.0
            sign_conflict = any(v > 0.10 for v in values) and any(v < -0.10 for v in values)
            out[feature] = {
                "source_count": len(rows),
                "sources": [str(row["source"]) for row in rows],
                "weighted_mean": mean,
                "weighted_std": variance ** 0.5,
                "range": spread,
                "sign_conflict": sign_conflict,
            }
        return out

    def snapshot(
        self,
        asset: str = "",
        *,
        as_of_ts: float | None = None,
        as_of: str,
        limit: int = 100,
        include_expired: bool = False,
    ) -> dict[str, Any]:
        asset = str(asset or "").strip().upper()
        ts = time.time() if as_of_ts is None else float(as_of_ts)
        limit = max(1, min(1000, int(limit)))

        if self.path is None:
            history = self._memory_rows(asset, ts, include_expired)[:limit]
            all_causal = self._memory_rows(asset, ts, include_expired=True)
            selected = self._select(all_causal, as_of_ts=ts, asset_filter=asset)
            total = len(all_causal)
        else:
            where = ["observed_ts<=?", "received_ts<=?"]
            params: list[Any] = [ts, ts]
            if asset:
                where.append("asset=?")
                params.append(asset)
            if not include_expired:
                where.append("expires_ts>?")
                params.append(ts)
            with self._connect() as con:
                history = [
                    dict(row) for row in con.execute(
                        f"""SELECT evidence_id,schema_version,asset,feature,value,confidence,source,
                                   observed_at,observed_ts,received_ts,expires_ts,ttl_seconds,
                                   payload_hash,created_at
                            FROM evidence
                            WHERE {" AND ".join(where)}
                            ORDER BY observed_ts DESC, received_ts DESC, evidence_id DESC
                            LIMIT ?""",
                        (*params, limit),
                    ).fetchall()
                ]
                active_where = ["observed_ts<=?", "received_ts<=?", "expires_ts>?"]
                active_params: list[Any] = [ts, ts, ts]
                if asset:
                    active_where.append("asset=?")
                    active_params.append(asset)
                active_rows = [
                    dict(row) for row in con.execute(
                        f"""SELECT evidence_id,schema_version,asset,feature,value,confidence,source,
                                   observed_at,observed_ts,received_ts,expires_ts,ttl_seconds,
                                   payload_hash,created_at
                            FROM evidence
                            WHERE {" AND ".join(active_where)}
                            ORDER BY observed_ts DESC, received_ts DESC, evidence_id DESC""",
                        tuple(active_params),
                    ).fetchall()
                ]
                count_where = ["observed_ts<=?", "received_ts<=?"]
                count_params: list[Any] = [ts, ts]
                if asset:
                    count_where.append("asset=?")
                    count_params.append(asset)
                total = int(con.execute(
                    f"SELECT COUNT(*) AS n FROM evidence WHERE {' AND '.join(count_where)}",
                    tuple(count_params),
                ).fetchone()["n"])
            selected = self._select(active_rows, as_of_ts=ts, asset_filter=asset)

        return {
            "schema_version": SCHEMA_VERSION,
            "asset": asset or None,
            "as_of": as_of,
            "durable": self.durable,
            "active_count": len(selected),
            "active": {key: dict(value) for key, value in sorted(selected.items())},
            "history": history,
            "total_history_count": total,
            "disagreement": self.disagreement(asset, as_of_ts=ts) if asset else {},
            "integrity": self.integrity(),
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def integrity(self, *, max_age_seconds: float = 60.0) -> dict[str, Any]:
        now = time.time()
        cached_at, cached = self._integrity_cache
        if cached and now - cached_at <= max(0.0, float(max_age_seconds)):
            return dict(cached)

        with self._lock:
            if self.path is None:
                rows = [dict(row) for row in self._memory.values()]
                quick_check = "memory"
            else:
                with self._connect() as con:
                    check_row = con.execute("PRAGMA quick_check").fetchone()
                    quick_check = str(check_row[0] if check_row is not None else "unknown")
                    rows = [
                        dict(row) for row in con.execute(
                            """SELECT evidence_id,schema_version,asset,feature,value,confidence,source,
                                      observed_at,observed_ts,received_ts,expires_ts,ttl_seconds,
                                      payload_hash,created_at
                               FROM evidence
                               ORDER BY received_ts, evidence_id"""
                        ).fetchall()
                    ]

            invalid = []
            digest_parts = []
            for row in rows:
                try:
                    expected_id, expected_hash = self._identity(row)
                except Exception as ex:
                    invalid.append({
                        "evidence_id": str(row.get("evidence_id") or ""),
                        "reason": f"identity_recompute:{type(ex).__name__}",
                    })
                    continue
                if row.get("schema_version") != SCHEMA_VERSION:
                    invalid.append({
                        "evidence_id": str(row.get("evidence_id") or ""),
                        "reason": "schema_version",
                    })
                if row.get("evidence_id") != expected_id:
                    invalid.append({
                        "evidence_id": str(row.get("evidence_id") or ""),
                        "reason": "evidence_id",
                    })
                if row.get("payload_hash") != expected_hash:
                    invalid.append({
                        "evidence_id": str(row.get("evidence_id") or ""),
                        "reason": "payload_hash",
                    })
                digest_parts.append(json.dumps({
                    "evidence_id": row.get("evidence_id"),
                    "schema_version": row.get("schema_version"),
                    "asset": row.get("asset"),
                    "feature": row.get("feature"),
                    "value": row.get("value"),
                    "confidence": row.get("confidence"),
                    "source": row.get("source"),
                    "observed_at": row.get("observed_at"),
                    "observed_ts": row.get("observed_ts"),
                    "received_ts": row.get("received_ts"),
                    "expires_ts": row.get("expires_ts"),
                    "ttl_seconds": row.get("ttl_seconds"),
                    "payload_hash": row.get("payload_hash"),
                    "created_at": row.get("created_at"),
                }, sort_keys=True, separators=(",", ":"), allow_nan=False))

            digest = hashlib.sha256("\n".join(digest_parts).encode("utf-8")).hexdigest()
            ok = quick_check in {"ok", "memory"} and not invalid
            result = {
                "ok": ok,
                "storage": "sqlite" if self.path is not None else "memory",
                "quick_check": quick_check,
                "receipt_count": len(rows),
                "invalid_receipt_count": len(invalid),
                "invalid_receipts": invalid[:20],
                "ledger_digest_sha256": digest,
                "schema_version": SCHEMA_VERSION,
                "checked_at": now,
            }
            self._integrity_cache = (now, dict(result))
            return result

    def health(self, asset: str) -> dict[str, Any]:
        now = time.time()
        snap = self.snapshot(
            asset,
            as_of_ts=now,
            as_of="current",
            limit=1,
            include_expired=True,
        )
        history = snap.get("history") or []
        integrity = self.integrity()
        return {
            "durable": self.durable,
            "storage_integrity_ok": bool(integrity.get("ok")),
            "ledger_digest_sha256": integrity.get("ledger_digest_sha256"),
            "invalid_receipt_count": int(integrity.get("invalid_receipt_count") or 0),
            "active_count": int(snap.get("active_count") or 0),
            "total_history_count": int(snap.get("total_history_count") or 0),
            "latest_observed_at": history[0].get("observed_at") if history else None,
            "conflicting_feature_count": sum(1 for row in (snap.get("disagreement") or {}).values() if row.get("sign_conflict")),
            "schema_version": SCHEMA_VERSION,
        }
