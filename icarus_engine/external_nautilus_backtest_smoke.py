"""Pinned NautilusTrader BacktestEngine smoke over verified synthetic futures quotes.

Research-only: no strategy, order factory, execution algorithm, broker client, live route,
training hook, Brain admission, or empirical fill claim is created here.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re

from icarus_engine.external_nautilus_causal_audit import audit_quote_asof
from icarus_engine.external_nautilus_quote_bridge import QuoteAdmissionError, VERSION

FUTURES_ID = re.compile(r"^([A-Z]{1,8})[FGHJKMNQUVXZ](\d{4})\.([A-Z0-9]{2,12})$")
DENIED = (
    "source_authenticity_verified",
    "license_verified",
    "instrument_economics_verified",
    "exchange_clock_synchronized",
    "initial_book_snapshot_verified",
    "queue_model_calibrated",
    "latency_model_calibrated",
    "fill_parity_verified",
    "empirical_edge_verified",
    "training_approved",
    "brain_admission_approved",
    "execution_authorized",
    "live_broker_connected",
)


def _load_quotes(staging: Path, expected_sha256: str, instrument_id: str):
    from nautilus_trader.model import InstrumentId, Price, Quantity, QuoteTick

    native_id = InstrumentId.from_str(instrument_id)
    digest = hashlib.sha256()
    rows = []
    with (Path(staging) / "quotes.jsonl").open("rb") as handle:
        for raw in handle:
            if len(raw) > 4096:
                raise QuoteAdmissionError("oversized staged quote record")
            digest.update(raw)
            try:
                row = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise QuoteAdmissionError("invalid staged quote JSON") from exc
            if not isinstance(row, dict) or row.get("instrument_id") != instrument_id:
                raise QuoteAdmissionError("staged quote instrument mismatch")
            rows.append(
                QuoteTick(
                    instrument_id=native_id,
                    bid_price=Price.from_str(row["bid_price"]),
                    ask_price=Price.from_str(row["ask_price"]),
                    bid_size=Quantity.from_str(row["bid_size"]),
                    ask_size=Quantity.from_str(row["ask_size"]),
                    ts_event=row["ts_event"],
                    ts_init=row["ts_init"],
                ),
            )
    if digest.hexdigest() != expected_sha256:
        raise QuoteAdmissionError("quote stream changed before BacktestEngine replay")
    if not rows:
        raise QuoteAdmissionError("no quotes available for BacktestEngine replay")
    return rows


def _build_synthetic_contract(instrument_id: str, first_ns: int, last_ns: int, tick_size: str):
    from nautilus_trader.model import AssetClass, Currency, FuturesContract
    from nautilus_trader.model import InstrumentId, Price, Quantity, Symbol

    match = FUTURES_ID.fullmatch(instrument_id)
    if match is None:
        raise QuoteAdmissionError("dated physical futures contract.VENUE identifier required")
    root, _year, _venue = match.groups()
    raw_symbol = instrument_id.split(".", 1)[0]
    if first_ns <= 0 or last_ns < first_ns or last_ns >= 2**63 - 2:
        raise QuoteAdmissionError("invalid synthetic contract replay bounds")
    # These activation/expiration values bound only the synthetic CI fixture.
    # They are deliberately not represented as verified exchange metadata.
    return FuturesContract(
        instrument_id=InstrumentId.from_str(instrument_id),
        raw_symbol=Symbol(raw_symbol),
        asset_class=AssetClass.INDEX,
        underlying=root,
        activation_ns=first_ns - 1,
        expiration_ns=last_ns + 1,
        currency=Currency.from_str("USD"),
        price_precision=max(0, len(tick_size.partition(".")[2])),
        price_increment=Price.from_str(tick_size),
        multiplier=Quantity.from_int(1),
        lot_size=Quantity.from_int(1),
        ts_event=0,
        ts_init=0,
    )


def _engine_snapshot(engine) -> dict:
    cache = engine.cache
    return {
        "iterations": int(engine.iteration),
        "backtest_start": int(engine.backtest_start),
        "backtest_end": int(engine.backtest_end),
        "orders_total": int(cache.orders_total_count()),
        "positions_total": int(cache.positions_total_count()),
        "positions_open": int(cache.positions_open_count()),
        "positions_closed": int(cache.positions_closed_count()),
    }


def run_verified_synthetic_backtest(
    source: Path,
    staging: Path,
    *,
    instrument_id: str,
    source_id: str,
    producer_revision: str,
    expected_source_sha256: str,
    expected_export_sha256: str,
    expected_manifest_sha256: str,
) -> dict:
    """Run actual low-level BacktestEngine twice with no strategy/order path.

    The function refuses to reinterpret this smoke test as execution/fill evidence.
    """
    if importlib.metadata.version("nautilus_trader") != VERSION:
        raise QuoteAdmissionError("native NautilusTrader version mismatch")

    # Parent native + causal verifier consumes and pins the complete stream first.
    causal = audit_quote_asof(
        source,
        staging,
        instrument_id=instrument_id,
        source_id=source_id,
        producer_revision=producer_revision,
        expected_source_sha256=expected_source_sha256,
        expected_export_sha256=expected_export_sha256,
        expected_manifest_sha256=expected_manifest_sha256,
        observation_ns=[0, 2**64 - 1],
    )
    if causal["records_fully_scanned"] <= 0:
        raise QuoteAdmissionError("causal verification yielded no records")
    if any(causal.get(name) is not False for name in DENIED if name in causal):
        raise QuoteAdmissionError("unexpected authority in causal verification receipt")

    staging = Path(staging)
    manifest = json.loads((staging / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("instrument_id") != instrument_id:
        raise QuoteAdmissionError("manifest instrument mismatch")
    tick_size = manifest.get("tick_size")
    if not isinstance(tick_size, str):
        raise QuoteAdmissionError("manifest tick_size missing")

    quotes = _load_quotes(staging, expected_export_sha256, instrument_id)
    if len(quotes) != causal["records_fully_scanned"]:
        raise QuoteAdmissionError("causal/native BacktestEngine quote count mismatch")

    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.config import BacktestEngineConfig
    from nautilus_trader.model import AccountType, Currency, Money, OmsType, Venue

    venue_code = instrument_id.rsplit(".", 1)[1]
    venue = Venue(venue_code)
    usd = Currency.from_str("USD")
    instrument = _build_synthetic_contract(
        instrument_id,
        min(q.ts_init for q in quotes),
        max(q.ts_init for q in quotes),
        tick_size,
    )

    engine = BacktestEngine(
        config=BacktestEngineConfig(bypass_logging=True, run_analysis=False),
    )
    try:
        engine.add_venue(
            venue=venue,
            oms_type=OmsType.NETTING,
            account_type=AccountType.MARGIN,
            base_currency=usd,
            starting_balances=[Money(1_000_000, usd)],
        )
        engine.add_instrument(instrument)
        engine.add_data(quotes)
        engine.run()
        first = _engine_snapshot(engine)
        if first["iterations"] != len(quotes):
            raise QuoteAdmissionError("BacktestEngine did not process every verified quote")
        if any(first[k] != 0 for k in (
            "orders_total", "positions_total", "positions_open", "positions_closed"
        )):
            raise QuoteAdmissionError("BacktestEngine unexpectedly created trading state")

        engine.reset()
        engine.run()
        second = _engine_snapshot(engine)
        if second != first:
            raise QuoteAdmissionError("BacktestEngine reset replay was not deterministic")
    finally:
        engine.dispose()

    return {
        "status": "NATIVE_BACKTESTENGINE_SYNTHETIC_ZERO_ORDER_SMOKE_ONLY",
        "nautilus_version": VERSION,
        "instrument_id": instrument_id,
        "records_replayed": len(quotes),
        "first_run": first,
        "reset_run": second,
        "deterministic_reset_replay": True,
        "synthetic_contract_metadata_only": True,
        **{name: False for name in DENIED},
    }
