"""Private metadata-only Unusual Whales connector observations.

This offline boundary binds exact response bytes to native Brain learning
events. It stores no vendor response, parameters, account credential or license
assertion. Connector access is not a backend transport or a PIT certificate.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable, Mapping

from .brain import record_brain_event


_PREFIX = "mcp__codex_apps__unusual_whales_"
_SCHEMA = "icarus-unusual-whales-observation-v1"
_MAX_RESPONSE = 16 * 1024 * 1024
_FIELDS = frozenset({
    "observation_id", "tool", "retrieved_at", "parameters", "result_status",
    "source_observed_at", "available_at", "raw_sha256", "reported_row_count",
    "retention_mode",
})
_STATUSES = {
    "OBSERVED": "observed", "EMPTY": "degraded", "DENIED": "blocked",
    "ERROR": "blocked", "TRANSFORMED_ONLY": "degraded", "UNCLASSIFIED": "unverified",
}
_EXCLUDED = frozenset({"api_and_education", "account_and_workspace"})


# The public capability map is audited against this exact runtime inventory.
_FAMILY_TOOLS = {
    'account_and_workspace': (
        'open_unusual_whales settings_read settings_update '
    ),
    'api_and_education': (
        'get_api_examples get_build_recipe get_public_api_docs '
        'get_support_info query_internal_knowledge '
    ),
    'crypto': (
        'get_crypto_ohlc_candles get_crypto_pair_state get_recent_crypto_whale_trades '
    ),
    'dark_and_lit_stock_flow': (
        'get_dark_pool_trades get_dark_pool_volume_price_group get_ticker_lit_flow '
    ),
    'earnings_and_analysts': (
        'get_analyst_ratings get_earnings_history get_earnings_report '
        'get_earnings_screener get_upcoming_earnings '
    ),
    'financial_statements': (
        'get_balance_sheet_screener get_balance_sheets get_cash_flow_screener '
        'get_cash_flows get_fundamental_breakdown get_income_statement_screener '
        'get_income_statements '
    ),
    'greek_exposure_and_flow': (
        'get_gex_heatmap get_gex_levels get_greek_exposure_by_expiry '
        'get_greek_exposure_by_strike get_greek_exposure_by_strike_expiry get_greek_exposure_by_ticker '
        'get_greek_flow get_greek_flow_by_expiry get_greek_flow_by_ticker '
    ),
    'identity_resolution': (
        'get_company_info search_option_contracts search_tickers '
    ),
    'insider_and_institutional': (
        'get_insider_activity_by_ticker get_insider_sector_flow get_insider_ticker_flow '
        'get_insider_transactions get_institution_holdings get_institutional_ownership_by_ticker '
        'get_institutions '
    ),
    'macro_and_calendar': (
        'get_central_bank_rates get_market_events get_yield_curve '
    ),
    'market_and_sector_regime': (
        'get_market_etf_tide get_market_map_chart get_market_sector_etfs '
        'get_market_sector_tide get_market_state get_market_tide_chart '
        'get_stock_screener get_ticker_performances '
    ),
    'option_contracts_and_screeners': (
        'get_atm_chains get_chains_for_expiry get_historic_chains '
        'get_option_stance_ranking get_options_chain get_options_screener '
    ),
    'options_flow': (
        'get_flow_alert_rules get_flow_alerts get_flow_per_expiry '
        'get_flow_per_strike get_multi_trades get_open_interest_changes '
        'get_option_trades '
    ),
    'politics_and_public_activity': (
        'get_midterms_ratings get_politics_flow get_politics_overview '
        'get_recent_congress_trades get_trump_activity '
    ),
    'prediction_markets': (
        'get_prediction_insiders get_prediction_market get_prediction_market_liquidity '
        'get_prediction_smart_money get_prediction_unusual_markets get_prediction_user '
        'get_prediction_whales '
    ),
    'prices_and_technicals': (
        'get_extended_technical_indicator get_stock_chart get_ticker_candles_by_range '
        'get_ticker_close_prices get_ticker_indicator_events get_ticker_indicator_series '
        'get_ticker_ohlc_latest_or_date get_trading_states '
    ),
    'seasonality_and_relationships': (
        'get_average_return_per_month_by_ticker get_correlations get_market_seasonality '
        'get_month_performers get_price_change_per_month_per_year '
    ),
    'short_interest_and_borrow': (
        'get_short_data_by_ticker get_short_screener get_short_volume_ratio_by_exchange '
        'get_short_volume_ratio_by_ticker '
    ),
    'volatility_and_expiry': (
        'get_implied_volatility_term_structure get_max_pain '
    ),
}
TOOL_FAMILIES = {tool: family for family, tools in _FAMILY_TOOLS.items() for tool in tools.split()}


def _json(value: Any, *, max_bytes: int = 16384) -> str:
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("manifest must contain finite JSON") from exc
    if len(text.encode()) > max_bytes:
        raise ValueError("manifest exceeds its metadata limit")
    return text


def _stamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be an aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parameters(value: Any) -> str:
    if not isinstance(value, Mapping):
        raise ValueError("parameters must be an object")

    def inspect(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("parameter keys must be strings")
                if any(word in key.lower() for word in (
                    "password", "secret", "token", "api_key", "apikey", "authorization", "cookie",
                )):
                    raise ValueError("credential parameters are not accepted")
                inspect(child)
        elif isinstance(item, list):
            for child in item:
                inspect(child)

    inspect(value)
    return hashlib.sha256(_json(dict(value), max_bytes=8192).encode()).hexdigest()


def _receipt(response: bytes, manifest: Mapping[str, Any], clock: datetime) -> dict[str, Any]:
    if not isinstance(clock, datetime) or clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("injected clock must return an aware datetime")
    if not isinstance(response, bytes) or not response or len(response) > _MAX_RESPONSE:
        raise ValueError("response must be nonempty exact bytes within the 16 MiB limit")
    if not isinstance(manifest, Mapping) or set(manifest) - _FIELDS:
        raise ValueError("unsupported manifest fields")
    observation = manifest.get("observation_id")
    if not isinstance(observation, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", observation):
        raise ValueError("observation_id must be a safe immutable identity")
    tool = manifest.get("tool")
    if not isinstance(tool, str):
        raise ValueError("tool is required")
    name = tool.removeprefix(_PREFIX)
    if name not in TOOL_FAMILIES or TOOL_FAMILIES[name] in _EXCLUDED:
        raise ValueError("tool is not a read-only research-data capability")
    retrieved = _stamp(manifest.get("retrieved_at"), "retrieved_at")
    if retrieved > clock.astimezone(timezone.utc):
        raise ValueError("retrieved_at is later than the injected clock")
    clocks: dict[str, str | None] = {}
    for field in ("source_observed_at", "available_at"):
        value = manifest.get(field)
        parsed = _stamp(value, field) if value is not None else None
        if parsed is not None and parsed > retrieved:
            raise ValueError(f"{field} is later than retrieval")
        clocks[field] = _iso(parsed) if parsed is not None else None
    digest = hashlib.sha256(response).hexdigest()
    if manifest.get("raw_sha256", digest) != digest:
        raise ValueError("raw_sha256 does not bind the exact response bytes")
    if manifest.get("retention_mode", "METADATA_ONLY") != "METADATA_ONLY":
        raise ValueError("raw retention requires a separate validated rights contract")
    status = manifest.get("result_status", "UNCLASSIFIED")
    if not isinstance(status, str) or status not in _STATUSES:
        raise ValueError("unsupported result_status")
    row_count = manifest.get("reported_row_count")
    if row_count is not None and (type(row_count) is not int or row_count < 0):
        raise ValueError("reported_row_count must be a nonnegative integer or null")
    return {
        "schema_version": _SCHEMA,
        "observation_id": observation,
        "provider": "unusual_whales",
        "transport": "chatgpt_connector_observation",
        "origin_status": "CALLER_DECLARED_UNVERIFIED",
        "tool": _PREFIX + name,
        "family": TOOL_FAMILIES[name],
        "retrieved_at": _iso(retrieved),
        "retrieval_time_status": "CALLER_REPORTED",
        **clocks,
        "source_time_status": "DECLARED_UNVERIFIED" if clocks["source_observed_at"] else "UNKNOWN",
        "availability_status": "DECLARED_UNVERIFIED" if clocks["available_at"] else "UNKNOWN",
        "raw_sha256": digest,
        "raw_size_bytes": len(response),
        "parameters_sha256": _parameters(manifest.get("parameters", {})),
        "result_status": status,
        "reported_row_count": row_count,
        "row_count_status": "CALLER_REPORTED_UNVERIFIED" if row_count is not None else "UNKNOWN",
        "retention_mode": "METADATA_ONLY",
        "raw_payload_persisted": False,
        "rights": {"retention": "UNKNOWN", "redistribution": "UNKNOWN", "training": "UNKNOWN"},
        "entitlement_status": "UNKNOWN",
        "coverage_status": "UNKNOWN",
        "eligible_rows_denominator": None,
        "point_in_time_eligible": False,
        "candidate_evidence_eligible": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _private_file(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("private intake paths must not be symlinks")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        if os.fstat(descriptor).st_nlink != 1:
            raise ValueError("private intake files must not have hard links")
        if os.name == "posix":
            os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)


def _connect(base_dir: str | os.PathLike[str]) -> sqlite3.Connection:
    base = Path(base_dir).resolve()
    if any((parent / ".git").is_file() or (parent / ".git" / "HEAD").is_file()
           for parent in (base, *base.parents)):
        raise ValueError("private runtime must be outside a Git repository")
    directory = base / ".unusual_whales_intake"
    path = directory / "observations.sqlite3"
    audit = base / "audit"
    journal = audit / "brain_events.jsonl"
    if any(candidate.is_symlink() for candidate in (directory, path, audit, journal)):
        raise ValueError("private intake paths must not be symlinks")
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix" and base.stat().st_mode & 0o077:
        raise ValueError("private runtime must not be accessible to group or other users")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    audit.mkdir(exist_ok=True, mode=0o700)
    if os.name == "posix":
        directory.chmod(0o700)
        audit.chmod(0o700)
    # Both persistence planes are private before opening or appending. Core
    # Brain APIs remain unchanged and receive only compact receipt metadata.
    _private_file(path)
    _private_file(journal)
    connection = sqlite3.connect(path, timeout=30)
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("""CREATE TABLE IF NOT EXISTS observations (
        observation_id TEXT PRIMARY KEY,
        receipt_json TEXT NOT NULL,
        delivery_status TEXT NOT NULL CHECK(delivery_status IN ('PENDING','DELIVERED')),
        brain_event_id TEXT
    )""")
    connection.commit()
    return connection


def _event(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "learning",
        "subject": "Unusual Whales " + receipt["family"],
        "summary": (
            f"Connector observation {receipt['observation_id']} was received as {receipt['result_status']}; "
            "metadata integrity is recorded, while licensing, history coverage and PIT eligibility remain unverified."
        ),
        "status": _STATUSES[receipt["result_status"]],
        "evidence": ["response_sha256:" + receipt["raw_sha256"], "retrieved_at:" + receipt["retrieved_at"]],
        "details": dict(receipt),
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _deliver(connection: sqlite3.Connection, base_dir: str | os.PathLike[str], receipt: dict[str, Any]) -> dict[str, Any]:
    # Serialize intake deliveries across processes. A crash after the fsynced
    # Brain append leaves PENDING; native event identity makes retry idempotent.
    connection.execute("BEGIN IMMEDIATE")
    try:
        response = record_brain_event(base_dir, _event(receipt))
        event_id = response["event"]["id"]
        connection.execute(
            "UPDATE observations SET delivery_status='DELIVERED',brain_event_id=? WHERE observation_id=?",
            (event_id, receipt["observation_id"]),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return {"receipt": receipt, "delivery_status": "DELIVERED", "brain_event_id": event_id,
            "idempotent": response["idempotent"], "execution_authorized": False,
            "production_decision_authorized": False}


def observe(
    base_dir: str | os.PathLike[str], response: bytes, manifest: Mapping[str, Any], *,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Bind one exact connector response to a durable native learning event.

    ``base_dir`` is a private application runtime outside any Git checkout.
    Response bytes are hashed in memory and never written by this function.
    Source clocks and row counts are caller declarations, not verified facts.
    """
    receipt = _receipt(response, manifest, now())
    encoded = _json(receipt)
    connection = _connect(base_dir)
    try:
        with connection:
            connection.execute(
                "INSERT OR IGNORE INTO observations VALUES (?,?,'PENDING',NULL)",
                (receipt["observation_id"], encoded),
            )
            prior = connection.execute("SELECT receipt_json FROM observations WHERE observation_id=?",
                                       (receipt["observation_id"],)).fetchone()[0]
            if prior != encoded:
                raise ValueError("immutable observation identity conflict")
        return _deliver(connection, base_dir, receipt)
    finally:
        connection.close()


def resume_pending(base_dir: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Recover persisted receipts after a journal or process failure; no I/O transport."""
    connection = _connect(base_dir)
    try:
        receipts = connection.execute(
            "SELECT receipt_json FROM observations WHERE delivery_status='PENDING' ORDER BY observation_id"
        ).fetchall()
        return [_deliver(connection, base_dir, json.loads(row[0])) for row in receipts]
    finally:
        connection.close()
