"""Pinned HFTBacktest native *synthetic-only* no-order smoke.

This module has no CLI arguments for real data. It creates five synthetic MBP
events, independently checks source -> staged CSV -> NPY, and asks the actual
HFTBacktest Python/Rust runtime to consume them. No order methods are called.
A passing smoke is NOT a complete-book, calibrated fill, or strategy result.
"""
from __future__ import annotations

import hashlib
from importlib import import_module
import json
from pathlib import Path
import tempfile

from .external_hft_stage import stage_mbp_events
from .external_hft_numpy import pack_verified_l2
from .external_hft_native_verify import verify_native_l2
from .external_hft_causal_audit import audit_causal_l2

PINNED_HFTBACKTEST_VERSION = "2.4.4"
FIXTURE_CONTRACT = "NQH2026"
FIXTURE_SOURCE = "synthetic_ci_only"
T0 = 1700000000000000000
COLUMNS = ("ev", "exch_ts", "local_ts", "px", "qty", "order_id", "ival", "fval")


class NativeSmokeError(ValueError):
    """Native dependency or event consumption failed a synthetic-only gate."""


def _fixture() -> bytes:
    rows = ["sequence,contract_id,kind,side,exchange_ts_ns,local_ts_ns,price,quantity\n"]
    data = (
        ("depth_update", "bid", "15000.25", "2"),
        ("depth_update", "ask", "15000.50", "3"),
        ("trade", "buy", "15000.50", "1"),
        ("depth_update", "bid", "15000.25", "2"),
        ("depth_update", "ask", "15000.50", "3"),
    )
    for i, (kind, side, price, qty) in enumerate(data):
        exch = T0 + i * 1_000_000_000
        rows.append(f"{i+1},{FIXTURE_CONTRACT},{kind},{side},"
                    f"{exch},{exch+1000},{price},{qty}\n")
    return "".join(rows).encode("ascii")


def _runtime():
    try:
        hft = import_module("hftbacktest")
        np = import_module("numpy")
        hft_types = import_module("hftbacktest.types")
    except ImportError as exc:
        raise NativeSmokeError("pinned HFTBacktest and NumPy required; no auto-install") from exc
    if getattr(hft, "__version__", None) != PINNED_HFTBACKTEST_VERSION:
        raise NativeSmokeError("unapproved HFTBacktest runtime version")
    return hft, np, hft_types


def _assert_event_dtype(np, native_dtype, upstream_dtype):
    expected = np.dtype([
        ("ev", "<u8"), ("exch_ts", "<i8"), ("local_ts", "<i8"),
        ("px", "<f8"), ("qty", "<f8"), ("order_id", "<u8"),
        ("ival", "<i8"), ("fval", "<f8"),
    ], align=True)
    # NumPy NPY v1 stores field offsets and scalar types, but does not preserve
    # the source dtype's 'align=True' metadata. Its reloaded dtype can have
    # isalignedstruct=False even when the 64-byte ABI and buffer are aligned.
    # Validate actual offsets/types and the upstream native dtype separately.
    for candidate in (native_dtype, upstream_dtype):
        if candidate.itemsize != 64 or candidate.names != COLUMNS:
            raise NativeSmokeError("native/upstream Event ABI differs from pinned 64-byte layout")
        if any(candidate.fields[key][0] != expected.fields[key][0]
               for key in COLUMNS):
            raise NativeSmokeError("native/upstream Event scalar types mismatch")
        if any(candidate.fields[key][1] != 8 * i for i, key in enumerate(COLUMNS)):
            raise NativeSmokeError("native/upstream Event offsets mismatch")
    if not upstream_dtype.isalignedstruct:
        raise NativeSmokeError("upstream native Event ABI is not aligned")


def run_synthetic_native_smoke() -> dict:
    """Execute only embedded synthetic data, without orders or provider access."""
    hft, np, types = _runtime()
    with tempfile.TemporaryDirectory(prefix="icarus-hft-synthetic-") as tmp:
        root = Path(tmp)
        source, staged, native = root / "source.csv", root / "stage", root / "native"
        original = _fixture()
        source.write_bytes(original)
        trusted_sha = hashlib.sha256(original).hexdigest()
        stage_mbp_events(source, staged, contract_id=FIXTURE_CONTRACT,
                         source_id=FIXTURE_SOURCE, tick_size="0.25", lot_size="1")
        kwargs = {
            "expected_contract_id": FIXTURE_CONTRACT,
            "expected_source_id": FIXTURE_SOURCE,
            "expected_input_sha256": trusted_sha,
            "expected_tick_size": "0.25",
            "expected_lot_size": "1",
        }
        pack_verified_l2(source, staged, native, **kwargs)
        verified = verify_native_l2(source, staged, native, **kwargs)
        causal = audit_causal_l2(source, staged, native, **kwargs)
        if (verified["rows"] != 5 or not verified["native_byte_parity_verified"]
                or causal["status"] != "REPLAY_READINESS_BLOCKED"
                or causal["rows_examined"] != 5):
            raise NativeSmokeError("source/native admission did not remain quarantined")
        data = np.load(native / "hft-events.npy", allow_pickle=False)
        _assert_event_dtype(np, data.dtype, types.event_dtype)
        if data.shape != (5,) or not data.flags.c_contiguous or not data.flags.aligned:
            raise NativeSmokeError("native array shape/alignment mismatch")
        # This is the actual HFTBacktest Python/Rust backtest runtime, not a mock.
        # No order placement, sizing, PnL or fill quality is exercised.
        asset = (
            hft.BacktestAsset().linear_asset(1.0).data(data)
            .no_partial_fill_exchange().constant_latency(0, 0)
            .power_prob_queue_model3(3.0).tick_size(0.25).lot_size(1.0)
            .trade_len(16)
        )
        backtest = hft.HashMapMarketDepthBacktest([asset])
        try:
            status = int(backtest.elapse(2_500_000_000))
            if status != 0:
                raise NativeSmokeError("native simulator failed to elapse synthetic feed")
            depth = backtest.depth(0)
            bid, ask = float(depth.best_bid), float(depth.best_ask)
            if abs(bid - 15000.25) > 1e-9 or abs(ask - 15000.50) > 1e-9:
                raise NativeSmokeError("native simulator book differs from synthetic fixture")
            if float(backtest.position(0)) != 0.0:
                raise NativeSmokeError("unexpected synthetic no-order position")
        finally:
            close_status = int(backtest.close())
            if close_status != 0:
                raise NativeSmokeError("native simulator close failed")
        return {
            "schema_version": "icarus-hft-native-synthetic-smoke-v1",
            "status": "SYNTHETIC_NATIVE_RUNTIME_SMOKE_ONLY",
            "hftbacktest_version": PINNED_HFTBACKTEST_VERSION,
            "source_kind": "EMBEDDED_SYNTHETIC_FIXTURE",
            "source_sha256": trusted_sha,
            "native_sha256": verified["native_sha256"],
            "rows_source_verified": verified["rows"],
            "fixture_events_scheduled_before_probe": 3,
            "event_dtype_itemsize_bytes": 64,
            "upstream_event_dtype_parity_verified": True,
            "native_simulator_invoked": True,
            "synthetic_best_bid": bid,
            "synthetic_best_ask": ask,
            "order_submissions": 0,
            "book_snapshot_verified": False,
            "source_authenticity_verified": False,
            "entitlement_verified": False,
            "queue_latency_fee_models_calibrated": False,
            "empirical_fill_quality_verified": False,
            "protected_holdout_approved": False,
            "training_approved": False,
            "execution_authorized": False,
            "authority_granted": "NONE",
        }


def main() -> int:
    print(json.dumps(run_synthetic_native_smoke(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
