"""Bounded dashboard projection of pinned native corpus-consumption receipts.

This is historical consumption evidence. It supplies no market prices, trading
authority, live-feed qualification or profitability evidence. The pinned hashes
bind the exact reviewed artifact bytes; semantic checks defend future updates.
"""
from __future__ import annotations

from dataclasses import fields
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

from .corpus_intake import (CorpusReceipt, CorpusReadReceipt, _ARCHIVE_CONTEXT_ROOTS,
                            _FILENAME, _receipt_identity, _unique_object)
from .futures_catalog import FUTURES_PRODUCTS

_SOURCE = "reppiks490/Icarus-engine"
_SOURCE_COMMIT = "a6054cb952c428c7cb2fa1cd9841e04f381666e6"
_CONSUMER_COMMIT = "7b42eaa528d3137e87f8ae10ea0896944eb4b62b"
_RUN = 39115319263
_PINNED = {
    "bars_primary": (12132181638, "b4e1239b2dec0e58521f1835896bbec44ef6325a5c0eed1c06bb8152be1daee7"),
    "bars_secondary": (12132122538, "70f4af4c8ec4d6aeb0e1ab0ef5d67c0ff65f97899af7631c3851e0abb2dc0c99"),
    "bars_third": (12132291117, "1e7e97bb771496ecad6dc9b741e51df70ba386f6c2c07eaab2864eb306733e13"),
}
_MAX_BYTES = 2 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_IDS = ("cc1", "cc2", "cc3", "cc4")
_TOP = {"asof_ns", "blocked_datasets", "consumption_purposes", "corpus_used", "datasets",
        "execution_authorized", "market_validation", "paper_warmup_used", "production_decision_authorized",
        "raw_payloads_included", "read_receipts", "schema_version", "source_commit", "source_repo",
        "workflow_provenance", "workspaces"}
_WORKSPACE = {"assets", "chart", "configuration_sha256", "execution_authorized", "id", "inputs", "name",
              "paper_only", "unavailable_assets"}
_ASSET = {"chart_bars", "contract_status", "dataset_id", "excluded_prior_contract_rows", "execution_authorized",
          "history_sha256", "last_bar_ts", "mode", "native_interval_seconds", "source_rows", "symbol", "warm"}
_DATASET_KEYS = {f.name for f in fields(CorpusReceipt)}
_READ_KEYS = {f.name for f in fields(CorpusReadReceipt)}
_AUTHORITY = ("execution_authorized", "strategy_qualified", "live_feed_qualified")


def _require(condition):
    if not condition:
        raise ValueError("invalid corpus evidence")


def _keys(value, expected):
    _require(type(value) is dict and set(value) == expected)


def _int(value, minimum=0, maximum=10**22):
    _require(type(value) is int and minimum <= value <= maximum)
    return value


def _sha(value):
    _require(type(value) is str and _SHA.fullmatch(value) is not None)


def _false(value, names):
    _require(all(value.get(name) is False for name in names))


def _load_json(raw):
    return json.loads(raw, object_pairs_hook=_unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def _bounded_file(path):
    path = Path(path).absolute()
    _require(not any(parent.is_symlink() for parent in (path, *path.parents)))
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        details = os.fstat(fd)
        _require(stat.S_ISREG(details.st_mode) and details.st_size <= _MAX_BYTES)
        with os.fdopen(fd, "rb") as stream:
            fd = None
            raw = stream.read(_MAX_BYTES + 1)
        _require(len(raw) <= _MAX_BYTES)
        return raw
    finally:
        if fd is not None:
            os.close(fd)


def _dataset(value, cache, report, *, source_commit=_SOURCE_COMMIT):
    _keys(value, _DATASET_KEYS)
    _false(value, _AUTHORITY)
    _require(value["schema"] == "icarus.corpus-intake/1" and value["provider"] == "databento")
    _require(value["entitlement_status"] == "UNVERIFIED" and value["quality_status"] == "VALIDATED_NATIVE_BARS")
    _require(value["provenance_status"] == "MANIFEST_MATCH_CALLER_ATTESTED_REVISION")
    _require(value["availability_basis"] == "CALLER_ATTESTED_SOURCE_COMMIT_TIME")
    _require(value["source_repo"] == _SOURCE and value["source_commit"] == source_commit)
    _require(value["cache_name"] == cache and value["native_interval_seconds"] == 300)
    for name in ("dataset_id", "source_sha256", "bars_sha256", "manifest_sha256"):
        _sha(value[name])
    _int(value["compressed_bytes"], 1, 64 * 1024 * 1024)
    _int(value["uncompressed_bytes"], 1, 256 * 1024 * 1024)
    _int(value["source_rows"], 1, 2_000_000)
    _int(value["max_bars"], 1, 200_000)
    _int(value["retained_rows"], 1, min(value["source_rows"], value["max_bars"]))
    _int(value["excluded_unclosed_rows"], 0, value["source_rows"])
    _int(value["gap_count"])
    known = _int(value["contract_id_rows"], 0, value["retained_rows"])
    status = "COMPLETE" if known == value["retained_rows"] else "PARTIAL" if known else "UNKNOWN"
    _require(value["contract_identity_status"] == status)
    first = _int(value["first_ts"], 1)
    last = _int(value["last_ts"], first)
    _require(first % 300 == last % 300 == 0)
    _int(value["available_at_ns"], (last + 300) * 10**9, report["asof_ns"])
    _require(value["asof_ns"] == report["asof_ns"])
    match = _FILENAME.fullmatch(value["filename"]) if type(value["filename"]) is str else None
    _require(match is not None and match[1].upper() == value["provider_root"])
    products = [p for p in FUTURES_PRODUCTS.values() if p.execution_root == value["provider_root"]]
    if value["identity_status"] == "CATALOG_MAPPED":
        _require(len(products) == 1 and value["symbol"] == products[0].root)
    else:
        _require(value["provider_root"] in _ARCHIVE_CONTEXT_ROOTS and value["symbol"] == value["provider_root"])
        _require(value["identity_status"] == "ARCHIVE_CONTEXT_ONLY")
    receipt = CorpusReceipt(**{f.name: value[f.name] for f in fields(CorpusReceipt) if f.init})
    _require(receipt.to_dict() == value and _receipt_identity(receipt) == value["dataset_id"])
    return value


def _reads(values, datasets, report):
    _require(type(values) is list and 1 <= len(values) <= 1000)
    positive = set()
    for value in values:
        _keys(value, _READ_KEYS)
        _false(value, _AUTHORITY)
        _require(value["schema"] == "icarus.corpus-read/1" and value["entitlement_status"] == "UNVERIFIED")
        dataset = datasets[value["dataset_id"]]
        for key in ("source_sha256", "source_repo", "source_commit", "symbol", "identity_status", "available_at_ns"):
            _require(value[key] == dataset[key])
        _require(value["asof_ns"] == report["asof_ns"] and value["native_interval_seconds"] == 300)
        _require(value["method"] in ("candles", "ticker", "daily_volume"))
        _require(value["consumer_id"] in ("history_intake", *("paper:" + wid for wid in _IDS)))
        _require(value["requested_interval_seconds"] in (300, 86400))
        start = _int(value["requested_start_ts"])
        _int(value["requested_end_ts"], start, report["asof_ns"] // 10**9)
        count = _int(value["row_count"], 0, dataset["retained_rows"])
        if count:
            _int(value["first_ts"], dataset["first_ts"], dataset["last_ts"])
            _int(value["last_ts"], value["first_ts"], dataset["last_ts"])
            if value["method"] == "candles" and value["requested_interval_seconds"] == 300:
                _require(count == dataset["retained_rows"] and value["first_ts"] == dataset["first_ts"]
                         and value["last_ts"] == dataset["last_ts"])
                positive.add((value["consumer_id"], value["dataset_id"]))
        else:
            _require(value["first_ts"] is None and value["last_ts"] is None)
        if dataset["identity_status"] == "ARCHIVE_CONTEXT_ONLY":
            _require(value["consumer_id"] == "history_intake" and value["requested_interval_seconds"] == 300)
    _require(all(("history_intake", identity) in positive for identity in datasets))
    return positive


def _workspaces(values, datasets, positive):
    _require(type(values) is list and len(values) == 4)
    projected, seen = [], set()
    for value in values:
        _keys(value, _WORKSPACE)
        wid = value["id"]
        _require(wid in _IDS and wid not in seen and value["paper_only"] is True)
        _false(value, ("execution_authorized",))
        seen.add(wid)
        _sha(value["configuration_sha256"])
        _require(type(value["name"]) is str and 1 <= len(value["name"]) <= 100)
        _keys(value["chart"], {"chart_type", "fill_on", "security_source", "timeframe"})
        _require(value["chart"] in (
            {"chart_type": "heikin_ashi", "fill_on": "real", "security_source": "chart", "timeframe": "20"},
            {"chart_type": "heikin_ashi", "fill_on": "real", "security_source": "chart", "timeframe": "5"}))
        inputs = value["inputs"]
        _require(type(inputs) is dict and set(inputs) <= {"qty_contracts", "tp1_pts", "tp2_pts"})
        _require(all(type(v) in (float, int) and 0 < v <= 10_000 and math.isfinite(v) for v in inputs.values()))
        _require(type(value["unavailable_assets"]) is list and len(value["unavailable_assets"]) <= 256)
        _require(all(type(s) is str and re.fullmatch(r"[A-Z0-9]{1,12}", s) for s in value["unavailable_assets"]))
        _require(len(set(value["unavailable_assets"])) == len(value["unavailable_assets"]))
        _require(type(value["assets"]) is list and len(value["assets"]) <= 64)
        assets, asset_seen = [], set()
        for asset in value["assets"]:
            _keys(asset, _ASSET)
            ds = datasets[asset["dataset_id"]]
            _require(ds["identity_status"] == "CATALOG_MAPPED" and asset["symbol"] == ds["symbol"])
            _require(asset["symbol"] not in asset_seen and asset["symbol"] not in value["unavailable_assets"])
            asset_seen.add(asset["symbol"])
            _false(asset, ("execution_authorized",))
            _require(asset["warm"] is True and asset["mode"] == "CORPUS_WARMUP" and asset["native_interval_seconds"] == 300)
            _int(asset["source_rows"], 1, ds["retained_rows"])
            _int(asset["excluded_prior_contract_rows"], 0, ds["retained_rows"])
            _require(asset["source_rows"] + asset["excluded_prior_contract_rows"] == ds["retained_rows"])
            _int(asset["chart_bars"], 1, asset["source_rows"])
            _require(asset["last_bar_ts"] == ds["last_ts"])
            _require(asset["contract_status"] in ("LATEST_OBSERVED_CONTRACT", "CONTRACT_ID_UNAVAILABLE"))
            _sha(asset["history_sha256"])
            _require(("paper:" + wid, asset["dataset_id"]) in positive)
            assets.append({key: asset[key] for key in ("symbol", "dataset_id", "chart_bars", "source_rows", "last_bar_ts")})
        projected.append({"id": wid, "configuration_sha256": value["configuration_sha256"],
                          "warm_asset_count": len(assets), "assets": assets,
                          "unavailable_assets": list(value["unavailable_assets"]), "paper_only": True})
    return sorted(projected, key=lambda row: row["id"])


def _project(raw, cache, now_ns, *, source_commit=_SOURCE_COMMIT,
             consumer_commit=_CONSUMER_COMMIT, additional_top=()):
    """Project one receipt; alternate pins are explicit trusted caller arguments."""
    report = _load_json(raw)
    _keys(report, _TOP | set(additional_top))
    _false(report, ("execution_authorized", "market_validation", "production_decision_authorized", "raw_payloads_included"))
    _require(report["schema_version"] == "icarus-corpus-consumption-v1" and report["source_repo"] == _SOURCE
             and report["source_commit"] == source_commit and report["blocked_datasets"] == [])
    _int(report["asof_ns"], 1, now_ns)
    workflow = report["workflow_provenance"]
    _keys(workflow, {"acquisition_performed", "available_at_ns", "cache_name", "consumer_commit", "consumer_exit_code",
                     "consumer_repo", "execution_authorized", "network_disabled", "raw_data_artifacted", "source_commit", "source_repo"})
    _false(workflow, ("acquisition_performed", "execution_authorized", "raw_data_artifacted"))
    _require(workflow["network_disabled"] is True and type(workflow["consumer_exit_code"]) is int
             and workflow["consumer_exit_code"] == 0 and workflow["cache_name"] == cache
             and workflow["source_repo"] == _SOURCE and workflow["source_commit"] == source_commit
             and workflow["consumer_repo"] == "reppiks490/Icarus" and workflow["consumer_commit"] == consumer_commit)
    _require(type(report["datasets"]) is list and 1 <= len(report["datasets"]) <= 64)
    datasets = {}
    symbols = set()
    for value in report["datasets"]:
        ds = _dataset(value, cache, report, source_commit=source_commit)
        _require(ds["dataset_id"] not in datasets and ds["symbol"] not in symbols)
        _require(ds["available_at_ns"] == workflow["available_at_ns"])
        datasets[ds["dataset_id"]] = ds
        symbols.add(ds["symbol"])
    positive = _reads(report["read_receipts"], datasets, report)
    workspaces = _workspaces(report["workspaces"], datasets, positive)
    warmup_used = any(w["warm_asset_count"] > 0 for w in workspaces)
    _require(report["corpus_used"] is True and report["paper_warmup_used"] is warmup_used)
    purposes = ["QUALITY_AND_COVERAGE", "PRIVATE_HISTORY_INPUT"]
    if warmup_used:
        purposes.append("PAPER_CONFIGURATION_WARMUP")
    _require(report["consumption_purposes"] == purposes)
    latest = max(ds["last_ts"] + 300 for ds in datasets.values())
    projected = []
    for ds in datasets.values():
        item = {key: ds[key] for key in ("dataset_id", "symbol", "provider_root", "identity_status", "source_sha256",
                                        "filename", "source_rows", "retained_rows", "contract_identity_status", "first_ts", "last_ts")}
        item.update(last_bar_closed_ts=ds["last_ts"] + 300, age_seconds=now_ns // 10**9 - ds["last_ts"] - 300,
                    historical=True, live_feed_qualified=False, strategy_qualified=False)
        projected.append(item)
    return {"cache_name": cache, "dataset_count": len(datasets), "source_rows": sum(d["source_rows"] for d in datasets.values()),
            "retained_rows": sum(d["retained_rows"] for d in datasets.values()), "latest_bar_closed_ts": latest,
            "age_seconds": now_ns // 10**9 - latest, "historical": True, "paper_warmup_used": warmup_used,
            "datasets": projected, "workspaces": workspaces, "consumption_purposes": purposes}


def snapshot(now_ns=None, path=None):
    """Return safe historical coverage or a generic unavailable state, never raw receipts."""
    result = {"schema_version": "icarus-corpus-evidence-v1", "status": "UNAVAILABLE",
              "reason": "INVALID_CORPUS_EVIDENCE", "corpora": [],
              "live_feed_qualified": False, "strategy_qualified": False, "execution_authorized": False}
    try:
        now_ns = time.time_ns() if now_ns is None else now_ns
        _int(now_ns, 1)
        bundle = _load_json(_bounded_file(path or Path(__file__).with_name("corpus-consumption.json")))
        _keys(bundle, {"schema_version", "run_id", "source_repo", "source_commit", "consumer_commit", "artifacts"})
        _require(bundle["schema_version"] == "icarus-corpus-evidence-bundle-v1" and type(bundle["run_id"]) is int
                 and bundle["run_id"] == _RUN and bundle["source_repo"] == _SOURCE
                 and bundle["source_commit"] == _SOURCE_COMMIT and bundle["consumer_commit"] == _CONSUMER_COMMIT)
        _require(type(bundle["artifacts"]) is list and len(bundle["artifacts"]) == 3)
        corpora, seen = [], set()
        for artifact in bundle["artifacts"]:
            _keys(artifact, {"cache_name", "artifact_id", "receipt_sha256", "receipt_json"})
            cache = artifact["cache_name"]
            _require(cache in _PINNED and cache not in seen)
            seen.add(cache)
            _require(type(artifact["artifact_id"]) is int and (artifact["artifact_id"], artifact["receipt_sha256"]) == _PINNED[cache])
            _require(type(artifact["receipt_json"]) is str)
            raw = artifact["receipt_json"].encode("utf-8")
            _require(hashlib.sha256(raw).hexdigest() == artifact["receipt_sha256"])
            corpus = _project(raw, cache, now_ns)
            corpus.update(run_id=_RUN, artifact_id=artifact["artifact_id"], receipt_sha256=artifact["receipt_sha256"],
                          artifact_url=f"https://github.com/{_SOURCE}/actions/runs/{_RUN}/artifacts/{artifact['artifact_id']}")
            corpora.append(corpus)
        result.update(status="HISTORICAL_CONSUMPTION_VERIFIED", reason=None,
                      corpora=sorted(corpora, key=lambda c: tuple(_PINNED).index(c["cache_name"])),
                      run_id=_RUN, source_repo=_SOURCE, source_commit=_SOURCE_COMMIT, consumer_commit=_CONSUMER_COMMIT)
    except (ValueError, OSError, TypeError, KeyError, RecursionError, UnicodeError):
        pass  # Never serialize exceptions, input values or private filesystem paths.
    return result
