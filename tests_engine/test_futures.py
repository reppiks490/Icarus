"""Futures / multi-asset regression entrypoint.

The historical suite is preserved byte-for-byte in
``_futures_regression_legacy.py``.  This wrapper re-exports every historical test
except the one expectation intentionally changed by the canonical 32-root
futures convergence: CL/ZN and the rest of the owner-directed macro futures are
now first-class continuous analytical assets instead of unsupported symbols.

Keeping the old suite intact makes the behavior change explicit and reviewable
without weakening unrelated regression coverage.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_LEGACY_PATH = Path(__file__).with_name("_futures_regression_legacy.py")
_SPEC = importlib.util.spec_from_file_location("icarus_futures_regression_legacy", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import machinery guard
    raise RuntimeError(f"unable to load futures regression suite from {_LEGACY_PATH}")
_LEGACY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LEGACY)

for _name, _value in vars(_LEGACY).items():
    if _name.startswith("test_") and _name != "test_assets_registry_and_spec_tokens":
        globals()[_name] = _value


def test_assets_registry_and_spec_tokens():
    resolve = _LEGACY.resolve
    parse_spec = _LEGACY.parse_spec
    tf_minutes = _LEGACY.tf_minutes

    nq = resolve("NQ1!")
    assert nq.symbol == "NQ" and nq.multiplier == 20.0 and nq.mintick == 0.25 and nq.calendar == "cme" and nq.session == "rth" and nq.roll == "continuous"
    assert resolve("NQ=F").symbol == "NQ"
    mnq = resolve("MNQ1!")
    assert mnq.symbol == resolve("MNQ=F").symbol == "MNQ"
    assert mnq.multiplier == 2.0 and mnq.mintick == 0.25 and mnq.roll == "continuous"
    assert resolve("ES1!").symbol == resolve("ES=F").symbol == "ES"
    assert resolve("MES1!").symbol == resolve("MES=F").symbol == "MES"
    assert resolve("MES1!").multiplier == 5.0
    assert resolve("MYM1!").symbol == resolve("MYM=F").symbol == "MYM"
    assert resolve("MYM1!").multiplier == 0.5
    assert resolve("RTY1!").symbol == resolve("RTY=F").symbol == "RTY"
    assert resolve("RTY1!").multiplier == 50.0 and resolve("RTY1!").mintick == 0.10
    m2k = resolve("M2K1!")
    assert m2k.symbol == resolve("M2K=F").symbol == "M2K"
    assert (m2k.tv_symbol, m2k.multiplier, m2k.mintick) == ("CME_MINI:M2K1!", 5.0, 0.10)
    assert resolve("MGC1!").symbol == resolve("MGC=F").symbol == "MGC"
    assert (resolve("MGC1!").tv_symbol, resolve("MGC1!").multiplier, resolve("MGC1!").mintick) == ("COMEX_MINI:MGC1!", 10.0, 0.10)
    assert resolve("SI1!").symbol == resolve("SI=F").symbol == "SI"
    assert resolve("SIL1!").symbol == resolve("SIL=F").symbol == "SIL"
    assert (resolve("SIL1!").tv_symbol, resolve("SIL1!").multiplier, resolve("SIL1!").mintick) == ("COMEX_MINI:SIL1!", 1000.0, 0.005)
    assert resolve("MBT1!").symbol == resolve("MBT=F").symbol == "MBT"
    assert (resolve("PA1!").ticker, resolve("PA1!").mintick, resolve("PA1!").multiplier) == ("PA=F", 0.50, 100.0)

    supported = {
        "CL1!": "CL", "NYMEX:CL1!": "CL", "CL=F": "CL",
        "MCL1!": "MCL", "MCL=F": "MCL",
        "NG1!": "NG", "MNG1!": "MNG",
        "HG1!": "HG", "MHG1!": "MHG",
        "6E1!": "6E", "M6E1!": "M6E",
        "6J1!": "6J", "MJY1!": "MJY",
        "6B1!": "6B", "M6B1!": "M6B",
        "6A1!": "6A", "M6A1!": "M6A",
        "ZN1!": "ZN", "ZN=F": "ZN", "ZB1!": "ZB",
        "PL1!": "PL", "PA1!": "PA", "BTCF1!": "BTCF", "MBT1!": "MBT",
    }
    for identity, root in supported.items():
        spec = resolve(identity)
        assert spec.symbol == root
        assert spec.roll == "continuous"
        assert spec.tv_symbol.endswith("1!")
        assert spec.ticker.endswith("=F")

    gc = parse_spec("GC@10:NQ-10m-original", "20")
    assert gc.symbol == "GC" and gc.chart_tf == "10" and gc.preset == "NQ-10m-original" and gc.group == "metals" and gc.roll == "continuous"
    btc = parse_spec("BTCUSD")
    assert btc.feed == "coinbase" and btc.calendar == "crypto"
    assert tf_minutes("1W") == 10080 and tf_minutes("4H") == 240

    for bad in ('a">x', "..\\..\\evil", "NQ/../x"):
        with pytest.raises(ValueError):
            resolve(bad)

    for dated in (
        "NQZ26", "CME_MINI:NQZ2026", "MNQH27", "ESZ26", "GCZ26", "SIZ26",
        "BTCZ26", "MBTZ26", "CLZ26", "MCLZ26", "NGZ26", "6EZ26", "ZNZ26",
    ):
        with pytest.raises(ValueError, match="continuous-only"):
            resolve(dated)

    for unsupported in ("ZZ1!", "ZZ=F"):
        with pytest.raises(ValueError, match="unsupported continuous futures"):
            resolve(unsupported)

    for unregistered in ("AAPL", "NVDA", "SHIB"):
        with pytest.raises(ValueError, match="unregistered asset"):
            resolve(unregistered)
