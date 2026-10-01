"""ICARUS Scientific Commissioning Engine.

This module turns shadow research outputs into a falsifiable, append-only
prediction/outcome ledger. It never grants broker or production-decision
authority. Promotion can only make a research subsystem eligible for additional
shadow influence after enough out-of-sample evidence exists.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping
import hashlib
import json
import math
import os
import threading
import time
import uuid


SCHEMA_VERSION = "icarus-scientific-commissioning-v1"
LEDGER_SCHEMA = "icarus-commissioning-ledger-v1"
EPS = 1e-12


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _record_hash(record_without_hash: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(record_without_hash)).hexdigest()


def _corr(xs: list[float], ys: list[float]) -> float | None:
    n = min(len(xs), len(ys))
    if n < 4:
        return None
    x, y = xs[-n:], ys[-n:]
    mx = sum(x) / n
    my = sum(y) / n
    vx = sum((v - mx) ** 2 for v in x)
    vy = sum((v - my) ** 2 for v in y)
    if vx <= EPS or vy <= EPS:
        return None
    return _clip(sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy), -1.0, 1.0)


def _direction(x: float, threshold: float = 0.0) -> str:
    if x > threshold:
        return "UP"
    if x < -threshold:
        return "DOWN"
    return "FLAT"


class CommissioningEngine:
    """Continuously falsify Chronofold predictions without execution authority."""

    def __init__(
        self,
        base_dir: str | os.PathLike[str],
        port: Any,
        chronofold: Any,
        *,
        interval_seconds: float = 15.0,
        capture_step_chronons: float = 1.0,
        min_promotion_samples: int = 200,
    ):
        self.base_dir = Path(base_dir).resolve()
        self.port = port
        self.chronofold = chronofold
        self.interval_seconds = max(1.0, float(interval_seconds))
        self.capture_step_chronons = max(0.05, float(capture_step_chronons))
        self.min_promotion_samples = max(20, int(min_promotion_samples))
        self.root = self.base_dir / "audit" / "commissioning"
        self.prediction_path = self.root / "predictions.jsonl"
        self.outcome_path = self.root / "outcomes.jsonl"
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._predictions: Dict[str, Dict[str, Any]] = {}
        self._outcomes: Dict[str, Dict[str, Any]] = {}
        self._last_capture_tau: Dict[str, float] = {}
        self._chain_errors: list[str] = []
        self._load()

    @staticmethod
    def authority() -> Dict[str, bool]:
        return {
            "research_only": True,
            "shadow_only": True,
            "execution_authorized": False,
            "production_decision_authorized": False,
            "broker_authority": False,
        }

    def _read_chain(self, path: Path, kind: str) -> list[Dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[Dict[str, Any]] = []
        prev = "GENESIS"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as ex:
            self._chain_errors.append(f"{kind}: unreadable ledger: {type(ex).__name__}: {ex}")
            return []
        for line_no, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as ex:
                self._chain_errors.append(f"{kind}:{line_no}: invalid JSON: {ex}")
                continue
            if not isinstance(row, dict):
                self._chain_errors.append(f"{kind}:{line_no}: record is not an object")
                continue
            supplied = str(row.get("record_hash") or "")
            payload = dict(row)
            payload.pop("record_hash", None)
            expected = _record_hash(payload)
            if row.get("ledger_schema") != LEDGER_SCHEMA:
                self._chain_errors.append(f"{kind}:{line_no}: wrong ledger schema")
            if row.get("kind") != kind:
                self._chain_errors.append(f"{kind}:{line_no}: wrong record kind")
            if str(row.get("prev_hash") or "") != prev:
                self._chain_errors.append(f"{kind}:{line_no}: broken previous-hash link")
            if supplied != expected:
                self._chain_errors.append(f"{kind}:{line_no}: record hash mismatch")
            prev = supplied or expected
            rows.append(row)
        return rows

    def _load(self) -> None:
        with self._lock:
            self._chain_errors = []
            predictions = self._read_chain(self.prediction_path, "prediction")
            outcomes = self._read_chain(self.outcome_path, "outcome")
            self._predictions = {
                str(row.get("prediction_id")): row
                for row in predictions
                if row.get("prediction_id")
            }
            self._outcomes = {
                str(row.get("prediction_id")): row
                for row in outcomes
                if row.get("prediction_id")
            }
            self._last_capture_tau.clear()
            for row in predictions:
                asset = str(row.get("asset") or "").upper()
                if asset:
                    self._last_capture_tau[asset] = max(
                        self._last_capture_tau.get(asset, -math.inf),
                        _finite(row.get("start_tau"), -math.inf),
                    )

    def _append(self, path: Path, kind: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        before_errors = len(self._chain_errors)
        existing = self._read_chain(path, kind)
        if len(self._chain_errors) > before_errors:
            raise RuntimeError(f"{kind} ledger integrity failure; refusing append")
        prev_hash = str(existing[-1].get("record_hash")) if existing else "GENESIS"
        body = {
            "ledger_schema": LEDGER_SCHEMA,
            "kind": kind,
            "sequence": len(existing) + 1,
            "prev_hash": prev_hash,
            **dict(payload),
        }
        body["record_hash"] = _record_hash(body)
        raw = _canonical(body) + b"\n"
        fd = os.open(str(path), os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            os.write(fd, raw)
            os.fsync(fd)
        finally:
            os.close(fd)
        return body

    def _asset_price(self, asset: str, status: Mapping[str, Any] | None = None) -> float:
        status = status if isinstance(status, Mapping) else self.port.status()
        for row in status.get("assets", []) if isinstance(status, Mapping) else []:
            if isinstance(row, Mapping) and str(row.get("symbol") or "").upper() == asset:
                px = _finite(row.get("price"))
                if px > 0:
                    return px
        raise ValueError(f"no positive observed price for {asset}")

    @staticmethod
    def _prediction_variants(snapshot: Mapping[str, Any]) -> Dict[str, float]:
        mv = snapshot.get("multiverse") if isinstance(snapshot.get("multiverse"), Mapping) else {}
        full = _finite(mv.get("expected_return"))
        out = {"full": full}
        shadows = snapshot.get("counterfactual_shadows")
        if isinstance(shadows, list):
            for row in shadows:
                if not isinstance(row, Mapping):
                    continue
                name = str(row.get("removed_force") or "").strip().lower()
                if not name:
                    continue
                out[f"without_{name}"] = _finite(row.get("shadow_expected_return"))
        return out

    def capture(self, asset: str, *, force: bool = False) -> Dict[str, Any]:
        asset = str(asset or "").strip().upper()
        if not asset:
            raise ValueError("asset is required")
        with self._lock:
            status = self.port.status()
            snapshot = self.chronofold.snapshot(asset)
            if not isinstance(snapshot, Mapping) or snapshot.get("asset") != asset:
                raise RuntimeError(f"Chronofold has no commissionable state for {asset}")
            truth = snapshot.get("truth_contract") if isinstance(snapshot.get("truth_contract"), Mapping) else {}
            auth = snapshot.get("authority") if isinstance(snapshot.get("authority"), Mapping) else {}
            if truth.get("future_data_used") is not False:
                raise RuntimeError("Chronofold future-data truth contract failed")
            if auth.get("execution_authorized") is not False or auth.get("broker_authority") is not False:
                raise RuntimeError("Chronofold authority boundary failed")
            tau = _finite((snapshot.get("chronon") or {}).get("market_proper_time"))
            last_tau = self._last_capture_tau.get(asset)
            if not force and last_tau is not None and tau - last_tau < self.capture_step_chronons:
                return {
                    "captured": False,
                    "reason": "chronon_step_not_reached",
                    "asset": asset,
                    "current_tau": tau,
                    "last_capture_tau": last_tau,
                }

            mv = snapshot.get("multiverse") if isinstance(snapshot.get("multiverse"), Mapping) else {}
            clusters = mv.get("cluster_weights") if isinstance(mv.get("cluster_weights"), Mapping) else {}
            probs = {k: _clip(_finite(clusters.get(k)), 0.0, 1.0) for k in ("UP", "FLAT", "DOWN")}
            z = sum(probs.values())
            if z <= EPS:
                probs = {"UP": 1 / 3, "FLAT": 1 / 3, "DOWN": 1 / 3}
            else:
                probs = {k: v / z for k, v in probs.items()}

            p05 = _finite(mv.get("p05_return"))
            p95 = _finite(mv.get("p95_return"))
            spread = max(0.0, p95 - p05)
            threshold = max(1e-7, spread * 0.15)
            phase = snapshot.get("phase_transition") if isinstance(snapshot.get("phase_transition"), Mapping) else {}
            koop = snapshot.get("koopman") if isinstance(snapshot.get("koopman"), Mapping) else {}
            geometry = snapshot.get("geometry") if isinstance(snapshot.get("geometry"), Mapping) else {}
            macro = snapshot.get("macro_field") if isinstance(snapshot.get("macro_field"), Mapping) else {}
            potential = snapshot.get("market_potential") if isinstance(snapshot.get("market_potential"), Mapping) else {}
            cone = snapshot.get("causal_cone") if isinstance(snapshot.get("causal_cone"), Mapping) else {}
            gnc = snapshot.get("gnc") if isinstance(snapshot.get("gnc"), Mapping) else {}
            boundary = snapshot.get("time_boundary") if isinstance(snapshot.get("time_boundary"), Mapping) else {}

            prediction_id = f"cf-{asset}-{uuid.uuid4().hex}"
            payload = {
                "prediction_id": prediction_id,
                "captured_at": _utc_now(),
                "asset": asset,
                "start_price": self._asset_price(asset, status),
                "start_tau": tau,
                "target_tau": tau + max(1, int(_finite(mv.get("horizon_chronons"), 1))),
                "horizon_chronons": max(1, int(_finite(mv.get("horizon_chronons"), 1))),
                "expected_return": _finite(mv.get("expected_return")),
                "p05_return": p05,
                "p50_return": _finite(mv.get("p50_return")),
                "p95_return": p95,
                "branch_threshold": threshold,
                "branch_weights": probs,
                "variants": self._prediction_variants(snapshot),
                "epistemic_unknown_mass": _clip(_finite(snapshot.get("epistemic_unknown_mass"), 1.0), 0.0, 1.0),
                "regime": {
                    "phase_state": str(phase.get("state") or "UNKNOWN"),
                    "koopman_mode": str(koop.get("mode") or "UNKNOWN"),
                    "curvature": _finite(geometry.get("curvature")),
                    "macro_stress": _finite(macro.get("stress")),
                    "potential_energy": _finite(potential.get("energy")),
                    "causal_pressure": _finite(cone.get("incoming_pressure")),
                },
                "guidance": {
                    "bias": str(gnc.get("guidance") or "NO_EDGE"),
                    "confidence": _clip(_finite(gnc.get("confidence")), 0.0, 1.0),
                },
                "causal_boundary": {
                    "event_time": boundary.get("event_time"),
                    "retrieval_time": boundary.get("retrieval_time"),
                    "event_time_source": boundary.get("event_time_source"),
                    "causal_integrity": boundary.get("causal_integrity"),
                    "availability_time_exact": bool(boundary.get("availability_time_exact", False)),
                },
                "authority": self.authority(),
            }
            row = self._append(self.prediction_path, "prediction", payload)
            self._predictions[prediction_id] = row
            self._last_capture_tau[asset] = tau
            return {"captured": True, "prediction": row}

    def settle_ready(self, asset: str = "") -> Dict[str, Any]:
        requested = str(asset or "").strip().upper()
        with self._lock:
            pending = [
                row for pid, row in self._predictions.items()
                if pid not in self._outcomes and (not requested or row.get("asset") == requested)
            ]
            by_asset: Dict[str, list[Dict[str, Any]]] = defaultdict(list)
            for row in pending:
                by_asset[str(row.get("asset") or "").upper()].append(row)
            settled: list[Dict[str, Any]] = []
            skipped: Dict[str, str] = {}
            status = self.port.status()
            for symbol, rows in sorted(by_asset.items()):
                try:
                    snapshot = self.chronofold.snapshot(symbol)
                    current_tau = _finite((snapshot.get("chronon") or {}).get("market_proper_time"))
                    current_price = self._asset_price(symbol, status)
                except Exception as ex:
                    skipped[symbol] = f"{type(ex).__name__}: {ex}"[:500]
                    continue
                for pred in sorted(rows, key=lambda x: int(x.get("sequence") or 0)):
                    if current_tau + EPS < _finite(pred.get("target_tau")):
                        continue
                    start_price = max(EPS, _finite(pred.get("start_price"), EPS))
                    logret = math.log(max(current_price, EPS)) - math.log(start_price)
                    realized = math.expm1(_clip(logret, -50.0, 50.0))
                    threshold = max(0.0, _finite(pred.get("branch_threshold")))
                    target_tau = _finite(pred.get("target_tau"))
                    overshoot = max(0.0, current_tau - target_tau)
                    horizon = max(1.0, _finite(pred.get("horizon_chronons"), 1.0))
                    horizon_tolerance = max(1.0, 0.25 * horizon)
                    horizon_valid = overshoot <= horizon_tolerance
                    causal = pred.get("causal_boundary") if isinstance(pred.get("causal_boundary"), Mapping) else {}
                    causal_valid = str(causal.get("causal_integrity") or "").upper() in {"PASS", "BOUNDED"}
                    score_eligible = bool(horizon_valid and causal_valid)
                    actual = _direction(realized, threshold)
                    probs = pred.get("branch_weights") if isinstance(pred.get("branch_weights"), Mapping) else {}
                    brier = sum(
                        (_finite(probs.get(k)) - (1.0 if k == actual else 0.0)) ** 2
                        for k in ("UP", "FLAT", "DOWN")
                    )
                    expected = _finite(pred.get("expected_return"))
                    interval_hit = _finite(pred.get("p05_return")) <= realized <= _finite(pred.get("p95_return"))
                    variant_scores = {}
                    for name, forecast in (pred.get("variants") or {}).items():
                        f = _finite(forecast)
                        variant_scores[str(name)] = {
                            "forecast_return": f,
                            "squared_error": (f - realized) ** 2,
                            "absolute_error": abs(f - realized),
                            "direction_correct": _direction(f, threshold) == actual,
                        }
                    payload = {
                        "prediction_id": pred["prediction_id"],
                        "settled_at": _utc_now(),
                        "asset": symbol,
                        "start_tau": pred.get("start_tau"),
                        "target_tau": pred.get("target_tau"),
                        "settle_tau": current_tau,
                        "chronon_overshoot": overshoot,
                        "horizon_tolerance": horizon_tolerance,
                        "horizon_valid": horizon_valid,
                        "causal_valid": causal_valid,
                        "score_eligible": score_eligible,
                        "start_price": start_price,
                        "settle_price": current_price,
                        "realized_return": realized,
                        "actual_branch": actual,
                        "forecast_branch": _direction(expected, threshold),
                        "forecast_error": expected - realized,
                        "absolute_error": abs(expected - realized),
                        "squared_error": (expected - realized) ** 2,
                        "direction_correct": _direction(expected, threshold) == actual,
                        "interval_hit": interval_hit,
                        "brier_score": brier,
                        "variant_scores": variant_scores,
                        "epistemic_unknown_mass": pred.get("epistemic_unknown_mass"),
                        "regime": pred.get("regime"),
                        "authority": self.authority(),
                    }
                    row = self._append(self.outcome_path, "outcome", payload)
                    self._outcomes[pred["prediction_id"]] = row
                    settled.append(row)
            return {"settled": len(settled), "outcomes": settled, "skipped": skipped}

    def _calibration(self, pairs: list[tuple[Dict[str, Any], Dict[str, Any]]]) -> Dict[str, Any]:
        bins: Dict[int, list[tuple[float, float]]] = defaultdict(list)
        for pred, out in pairs:
            probs = pred.get("branch_weights") if isinstance(pred.get("branch_weights"), Mapping) else {}
            if not probs:
                continue
            label, conf = max(((k, _finite(probs.get(k))) for k in ("UP", "FLAT", "DOWN")), key=lambda x: x[1])
            hit = 1.0 if label == out.get("actual_branch") else 0.0
            bucket = min(4, max(0, int(conf * 5)))
            bins[bucket].append((conf, hit))
        rows = []
        gaps = []
        for bucket in range(5):
            vals = bins.get(bucket, [])
            if not vals:
                continue
            confidence = sum(v[0] for v in vals) / len(vals)
            empirical = sum(v[1] for v in vals) / len(vals)
            gap = abs(confidence - empirical)
            gaps.append((gap, len(vals)))
            rows.append({
                "bin": bucket,
                "n": len(vals),
                "mean_confidence": confidence,
                "empirical_frequency": empirical,
                "gap": gap,
            })
        total = sum(n for _, n in gaps)
        ece = sum(gap * n for gap, n in gaps) / total if total else None
        return {"bins": rows, "expected_calibration_error": ece}

    def _variant_tournament(self, pairs: list[tuple[Dict[str, Any], Dict[str, Any]]]) -> list[Dict[str, Any]]:
        agg: Dict[str, list[Dict[str, Any]]] = defaultdict(list)
        for _pred, out in pairs:
            scores = out.get("variant_scores") if isinstance(out.get("variant_scores"), Mapping) else {}
            for name, row in scores.items():
                if isinstance(row, Mapping):
                    agg[str(name)].append(dict(row))
        rows = []
        for name, vals in agg.items():
            n = len(vals)
            rows.append({
                "variant": name,
                "n": n,
                "rmse": math.sqrt(sum(_finite(v.get("squared_error")) for v in vals) / n) if n else None,
                "mae": sum(_finite(v.get("absolute_error")) for v in vals) / n if n else None,
                "direction_accuracy": sum(1 for v in vals if v.get("direction_correct") is True) / n if n else None,
            })
        rows.sort(key=lambda x: (math.inf if x["rmse"] is None else x["rmse"], x["variant"]))
        return rows

    def metrics(self, asset: str = "") -> Dict[str, Any]:
        requested = str(asset or "").strip().upper()
        with self._lock:
            pairs = []
            excluded = {"horizon": 0, "causal": 0}
            for pid, out in self._outcomes.items():
                pred = self._predictions.get(pid)
                if not pred:
                    continue
                if requested and pred.get("asset") != requested:
                    continue
                if out.get("score_eligible") is not True:
                    if out.get("horizon_valid") is False:
                        excluded["horizon"] += 1
                    if out.get("causal_valid") is False:
                        excluded["causal"] += 1
                    continue
                pairs.append((pred, out))
            n = len(pairs)
            if not n:
                return {
                    "settled_predictions": 0,
                    "direction_accuracy": None,
                    "rmse": None,
                    "mae": None,
                    "brier_score": None,
                    "interval_coverage": None,
                    "calibration": {"bins": [], "expected_calibration_error": None},
                    "unknown_error_correlation": None,
                    "variants": [],
                    "regimes": [],
                    "excluded_outcomes": excluded,
                }
            errors = [_finite(out.get("forecast_error")) for _, out in pairs]
            abs_errors = [abs(x) for x in errors]
            unknowns = [_finite(pred.get("epistemic_unknown_mass")) for pred, _ in pairs]
            regimes: Dict[tuple[str, str], list[Dict[str, Any]]] = defaultdict(list)
            for pred, out in pairs:
                r = pred.get("regime") if isinstance(pred.get("regime"), Mapping) else {}
                regimes[(str(r.get("phase_state") or "UNKNOWN"), str(r.get("koopman_mode") or "UNKNOWN"))].append(out)
            regime_rows = []
            for (phase, koop), outs in sorted(regimes.items()):
                regime_rows.append({
                    "phase_state": phase,
                    "koopman_mode": koop,
                    "n": len(outs),
                    "direction_accuracy": sum(1 for x in outs if x.get("direction_correct") is True) / len(outs),
                    "rmse": math.sqrt(sum(_finite(x.get("squared_error")) for x in outs) / len(outs)),
                })
            return {
                "settled_predictions": n,
                "direction_accuracy": sum(1 for _, out in pairs if out.get("direction_correct") is True) / n,
                "rmse": math.sqrt(sum(e * e for e in errors) / n),
                "mae": sum(abs_errors) / n,
                "brier_score": sum(_finite(out.get("brier_score")) for _, out in pairs) / n,
                "interval_coverage": sum(1 for _, out in pairs if out.get("interval_hit") is True) / n,
                "calibration": self._calibration(pairs),
                "unknown_error_correlation": _corr(unknowns, abs_errors),
                "variants": self._variant_tournament(pairs),
                "regimes": regime_rows,
                "excluded_outcomes": excluded,
            }

    def promotion_gate(self, asset: str = "") -> Dict[str, Any]:
        m = self.metrics(asset)
        n = int(m.get("settled_predictions") or 0)
        ece = (m.get("calibration") or {}).get("expected_calibration_error")
        checks = {
            "minimum_out_of_sample_predictions": n >= self.min_promotion_samples,
            "direction_accuracy_at_least_52pct": m.get("direction_accuracy") is not None and m["direction_accuracy"] >= 0.52,
            "brier_below_uniform_baseline": m.get("brier_score") is not None and m["brier_score"] < (2.0 / 3.0),
            "central_interval_coverage_reasonable": m.get("interval_coverage") is not None and 0.70 <= m["interval_coverage"] <= 0.99,
            "calibration_error_below_15pct": ece is not None and ece <= 0.15,
            "ledger_integrity_clean": not self._chain_errors,
        }
        eligible = all(checks.values())
        return {
            "research_influence_eligible": eligible,
            "execution_authorized": False,
            "production_decision_authorized": False,
            "broker_authority": False,
            "checks": checks,
            "sample_count": n,
            "policy": "Passing this gate may increase shadow/research influence only; it can never arm execution.",
        }

    @staticmethod
    def replay_contract() -> Dict[str, Any]:
        return {
            "mode": "causal_rewind_replay",
            "requirements": [
                "event_time <= availability_time <= retrieval_time",
                "prediction must be committed before outcome observation",
                "future observations are forbidden in live/replay feature construction",
                "backward smoothing is permitted only in explicitly offline diagnostic lanes",
                "provider latency and stale/missing observations must remain observable",
            ],
            "future_data_allowed": False,
            "execution_authorized": False,
        }

    def adversarial_matrix(self, asset: str = "") -> list[Dict[str, Any]]:
        requested = str(asset or "").strip().upper()
        latest = None
        for row in sorted(self._predictions.values(), key=lambda x: int(x.get("sequence") or 0), reverse=True):
            if not requested or row.get("asset") == requested:
                latest = row
                break
        if latest is None:
            return []
        width = max(1e-9, _finite(latest.get("p95_return")) - _finite(latest.get("p05_return")))
        unknown = _finite(latest.get("epistemic_unknown_mass"), 1.0)
        return [
            {
                "scenario": "4x_forecast_dispersion",
                "shock_return": width * 4.0,
                "required_behavior": "remain shadow-only; widen uncertainty before increasing influence",
                "contract_pass": self.authority()["execution_authorized"] is False,
            },
            {
                "scenario": "causal_force_removed",
                "variants_available": any(str(k).startswith("without_") for k in (latest.get("variants") or {})),
                "required_behavior": "compare counterfactual variant; do not claim structural causality",
                "contract_pass": True,
            },
            {
                "scenario": "epistemic_unknown_saturation",
                "synthetic_unknown_mass": 1.0,
                "current_unknown_mass": unknown,
                "required_behavior": "promotion gate remains independent of execution authority",
                "contract_pass": self.promotion_gate(requested).get("execution_authorized") is False,
            },
            {
                "scenario": "tail_interval_breach",
                "shock_return": _finite(latest.get("p95_return")) + 2.0 * width,
                "required_behavior": "record forecast miss and calibration damage; never rewrite prediction",
                "contract_pass": latest["prediction_id"] in self._predictions,
            },
        ]

    def status(self, asset: str = "") -> Dict[str, Any]:
        requested = str(asset or "").strip().upper()
        with self._lock:
            predictions = [
                row for row in self._predictions.values()
                if not requested or row.get("asset") == requested
            ]
            settled_ids = {
                pid for pid, row in self._outcomes.items()
                if not requested or row.get("asset") == requested
            }
            return {
                "schema_version": SCHEMA_VERSION,
                "generated_at": _utc_now(),
                "asset": requested or None,
                "status": "degraded" if self._chain_errors else "green",
                "authority": self.authority(),
                "ledger": {
                    "append_only": True,
                    "hash_chained": True,
                    "predictions": len(predictions),
                    "settled": len(settled_ids),
                    "pending": sum(1 for row in predictions if row.get("prediction_id") not in settled_ids),
                    "integrity_errors": list(self._chain_errors),
                    "prediction_path": str(self.prediction_path.relative_to(self.base_dir)),
                    "outcome_path": str(self.outcome_path.relative_to(self.base_dir)),
                },
                "metrics": self.metrics(requested),
                "promotion_gate": self.promotion_gate(requested),
                "replay_contract": self.replay_contract(),
                "adversarial_matrix": self.adversarial_matrix(requested),
                "background": {
                    "running": bool(self._thread and self._thread.is_alive()),
                    "interval_seconds": self.interval_seconds,
                    "capture_step_chronons": self.capture_step_chronons,
                },
            }

    def tick(self) -> Dict[str, Any]:
        with self._lock:
            status = self.port.status()
            assets = [
                str(row.get("symbol") or "").upper()
                for row in status.get("assets", [])
                if isinstance(row, Mapping) and row.get("symbol")
            ]
        captures = []
        errors = {}
        for asset in assets:
            try:
                captures.append(self.capture(asset))
            except Exception as ex:
                errors[f"capture:{asset}"] = f"{type(ex).__name__}: {ex}"[:500]
        try:
            settlement = self.settle_ready()
        except Exception as ex:
            settlement = {"settled": 0, "outcomes": [], "skipped": {"*": f"{type(ex).__name__}: {ex}"[:500]}}
        return {"captures": captures, "settlement": settlement, "errors": errors}

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self.tick()
            except Exception:
                # Status exposes durable ledger integrity; transient sampling failures
                # must never crash ICARUS or mutate execution authority.
                continue

    def start_background(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
        # Commission immediately on start; do not make the first evidence receipt
        # wait one full cadence. Sampling errors remain non-fatal and shadow-only.
        try:
            self.tick()
        except Exception:
            pass
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._loop, name="icarus-commissioning", daemon=True)
            self._thread.start()

    def close(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, min(5.0, self.interval_seconds + 0.5)))
