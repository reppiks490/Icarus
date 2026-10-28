"""Independent synthetic-only native HFTBacktest time-slicing/causality gate.

No user/provider input, orders, strategy, real data, PnL, model fitting, or
permission to promote this synthetic observation into empirical evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from .external_hft_stage import stage_mbp_events
from .external_hft_numpy import pack_verified_l2
from .external_hft_native_verify import verify_native_l2
from .external_hft_causal_audit import audit_causal_l2
from .external_hft_simulator_smoke import (
    FIXTURE_CONTRACT, FIXTURE_SOURCE, NativeSmokeError, _fixture,
    _runtime, _assert_event_dtype,
)

STEP_EARLY_NS = 2_500_000_000
STEP_FULL_NS = 4_500_000_000


class TemporalParityError(ValueError):
    """Synthetic native replay violated deterministic/as-of safety gate."""


def _future_variant() -> bytes:
    """Change only the final two events, strictly after the early probe."""
    rows = _fixture().decode("ascii").splitlines(keepends=True)
    if len(rows) != 6:
        raise TemporalParityError("unexpected pinned fixture length")
    # At t=3s remove the bid level; at t=4s remove the ask level.
    rows[4] = rows[4].replace(",15000.25,2\n", ",15000.25,0\n")
    rows[5] = rows[5].replace(",15000.50,3\n", ",15000.50,0\n")
    if rows[4] == _fixture().decode("ascii").splitlines(keepends=True)[4]:
        raise TemporalParityError("fixture mutation failed")
    if rows[5] == _fixture().decode("ascii").splitlines(keepends=True)[5]:
        raise TemporalParityError("fixture mutation failed")
    return "".join(rows).encode("ascii")


def _admit(root: Path, raw: bytes, np, upstream_dtype):
    source, staged, native = root / "source.csv", root / "staged", root / "native"
    source.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    stage_mbp_events(source, staged, contract_id=FIXTURE_CONTRACT,
                     source_id=FIXTURE_SOURCE, tick_size="0.25", lot_size="1")
    args = {
        "expected_contract_id": FIXTURE_CONTRACT,
        "expected_source_id": FIXTURE_SOURCE,
        "expected_input_sha256": digest,
        "expected_tick_size": "0.25",
        "expected_lot_size": "1",
    }
    pack_verified_l2(source, staged, native, **args)
    verified = verify_native_l2(source, staged, native, **args)
    audit = audit_causal_l2(source, staged, native, **args)
    if (verified["rows"] != 5 or not verified["native_byte_parity_verified"]
            or audit["status"] != "REPLAY_READINESS_BLOCKED"
            or audit["rows_examined"] != 5 or audit["execution_authorized"]):
        raise TemporalParityError("source/native audit not independently quarantined")
    data = np.load(native / "hft-events.npy", allow_pickle=False)
    _assert_event_dtype(np, data.dtype, upstream_dtype)
    if data.shape != (5,) or not data.flags.c_contiguous or not data.flags.aligned:
        raise TemporalParityError("invalid pinned native event array")
    return data, digest, verified["native_sha256"]


def _replay(hft, data, slices):
    """Only advances native time and reads the observed partial book/position."""
    if not slices or any(type(x) is not int or x <= 0 for x in slices):
        raise TemporalParityError("invalid positive time slices")
    asset = (
        hft.BacktestAsset().linear_asset(1.0).data(data)
        .no_partial_fill_exchange().constant_order_latency(0, 0)
        .power_prob_queue_model3(3.0).tick_size(0.25).lot_size(1.0)
    )
    backtest = hft.HashMapMarketDepthBacktest([asset])
    observations = []
    try:
        for elapsed in slices:
            if int(backtest.elapse(elapsed)) != 0:
                raise TemporalParityError("native simulator could not elapse")
            depth = backtest.depth(0)
            observation = (float(depth.best_bid), float(depth.best_ask),
                           float(backtest.position(0)))
            if observation[2] != 0.0:
                raise TemporalParityError("unexpected synthetic no-order position")
            observations.append(observation)
    finally:
        if int(backtest.close()) != 0:
            raise TemporalParityError("native simulator close failed")
    return observations


def _assert_same(left, right, label):
    if left != right:
        raise TemporalParityError(f"{label}: native replay state diverged")


def run_synthetic_temporal_parity() -> dict:
    """Verify two replay schedules and late-event isolation on synthetic feed."""
    hft, np, types = _runtime()
    baseline, changed = _fixture(), _future_variant()
    baseline_lines = baseline.splitlines(keepends=True)
    changed_lines = changed.splitlines(keepends=True)
    if baseline_lines[:4] != changed_lines[:4] or baseline_lines[4:] == changed_lines[4:]:
        raise TemporalParityError("future-only fixture mutation is not isolated")
    with tempfile.TemporaryDirectory(prefix="icarus-hft-temporal-synthetic-") as tmp:
        root = Path(tmp)
        root_original, root_changed = root / "baseline", root / "changed"
        root_original.mkdir()
        root_changed.mkdir()
        data, source_hash, native_hash = _admit(
            root_original, baseline, np, types.event_dtype
        )
        altered, altered_hash, altered_native_hash = _admit(
            root_changed, changed, np, types.event_dtype
        )
        if source_hash == altered_hash or native_hash == altered_native_hash:
            raise TemporalParityError("future fixture variation not reflected in provenance")
        early_direct = _replay(hft, data, [STEP_EARLY_NS])[-1]
        early_sliced = _replay(hft, data, [500_000_000, 1_000_000_000, 1_000_000_000])[-1]
        early_changed = _replay(hft, altered, [STEP_EARLY_NS])[-1]
        _assert_same(early_direct, early_sliced, "early time slicing")
        _assert_same(early_direct, early_changed, "future event leakage")
        if early_direct != (15000.25, 15000.50, 0.0):
            raise TemporalParityError("early observed book differs from pinned fixture")
        full_direct = _replay(hft, data, [STEP_FULL_NS])[-1]
        full_sliced = _replay(
            hft, data, [500_000_000, 1_000_000_000, 1_000_000_000, 2_000_000_000]
        )[-1]
        _assert_same(full_direct, full_sliced, "full time slicing")
        changed_full = _replay(hft, altered, [STEP_FULL_NS])[-1]
        if changed_full == full_direct:
            raise TemporalParityError("future-only mutations did not affect later book")
        return {
            "schema_version": "icarus-hft-native-synthetic-temporal-parity-v1",
            "status": "SYNTHETIC_NATIVE_TEMPORAL_PARITY_ONLY",
            "hftbacktest_version": "2.4.4",
            "source_kind": "EMBEDDED_SYNTHETIC_FIXTURE",
            "original_source_sha256": source_hash,
            "future_mutation_source_sha256": altered_hash,
            "original_native_sha256": native_hash,
            "future_mutation_native_sha256": altered_native_hash,
            "rows_per_fixture": 5,
            "early_probe_elapsed_ns": STEP_EARLY_NS,
            "full_probe_elapsed_ns": STEP_FULL_NS,
            "early_time_slicing_parity": True,
            "full_time_slicing_parity": True,
            "synthetic_future_event_nonleak": True,
            "synthetic_late_mutation_effect_observed": True,
            "synthetic_early_bid": early_direct[0],
            "synthetic_early_ask": early_direct[1],
            "order_submissions": 0,
            "initial_book_snapshot_verified": False,
            "licensed_source_authenticity_verified": False,
            "exchange_clock_sync_verified": False,
            "queue_latency_fee_models_calibrated": False,
            "empirical_fill_quality_verified": False,
            "protected_holdout_approved": False,
            "training_approved": False,
            "execution_authorized": False,
            "authority_granted": "NONE",
        }


def main() -> int:
    print(json.dumps(run_synthetic_temporal_parity(), sort_keys=True, indent=2,
                     allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
