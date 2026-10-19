"""Pinned historical consumption evidence for the owner's ten futures families.

This bundle is separate from the original three-corpus proof. It attests actual
offline history reads and four configuration warmups, never current quotes,
execution qualification, account entitlement or profitability. Its source and
consumer revisions and exact artifact bytes are immutable trust anchors.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import time

from .corpus_evidence import (_SOURCE, _bounded_file, _false, _int, _keys,
                              _load_json, _project, _require)
from .paper_workspaces import requested_futures_metadata


_SOURCE_COMMIT = "ced31fcfcdf75e4ff2f4181315f462aa5d59a76b"
_CONSUMER_COMMIT = "19093b23a8b4853a6ee3e697029085986d871146"
_RUN = 39162615234
_ARTIFACT_ID = 12148939831
_RECEIPT_SHA256 = "67c948545419792f86200af4139963943f3184a9f726150892921e71b458b8c2"
_ABSENT_MICROS = ("MNG", "MHG", "M6E", "MJY", "M6B", "M6A")


def _expansion(value, corpus):
    canonical = requested_futures_metadata()
    _keys(value, set(canonical) | {"enabled", "no_new_acquisition", "available_symbols",
          "unavailable_symbols", "warmed_symbols_by_workspace", "all_full_families_warmed"})
    _require(value["enabled"] is True and value["no_new_acquisition"] is True
             and value["all_full_families_warmed"] is True)
    _false(value, ("execution_authorized", "profitability_verified", "fresh_feed_access_verified"))
    _require(all(value[key] == expected for key, expected in canonical.items()))
    _int(value["family_count"], 10, 10)
    symbols = canonical["symbols"]
    dataset_symbols = {dataset["symbol"] for dataset in corpus["datasets"]}
    available = [symbol for symbol in symbols if symbol in dataset_symbols]
    unavailable = [symbol for symbol in symbols if symbol not in dataset_symbols]
    _require(unavailable == list(_ABSENT_MICROS))
    _require(value["available_symbols"] == available and value["unavailable_symbols"] == unavailable)
    actual = {}
    for workspace in corpus["workspaces"]:
        warm = sorted(asset["symbol"] for asset in workspace["assets"] if asset["symbol"] in symbols)
        _require(set(canonical["full_roots"]) <= set(warm) and warm == sorted(available))
        _require(set(unavailable) <= set(workspace["unavailable_assets"]))
        actual[workspace["id"]] = warm
    _keys(value["warmed_symbols_by_workspace"], set(actual))
    _require(value["warmed_symbols_by_workspace"] == actual)
    # Return independently rebuilt public fields, not caller-supplied metadata.
    return {**canonical, "enabled": True, "no_new_acquisition": True,
            "available_symbols": available, "unavailable_symbols": unavailable,
            "warmed_symbols_by_workspace": actual, "all_full_families_warmed": True}


def snapshot(now_ns=None, path=None):
    """Return safe historical expansion lineage, or a generic unavailable state."""
    result = {"schema_version": "icarus-corpus-expansion-evidence-v1", "status": "UNAVAILABLE",
              "reason": "INVALID_CORPUS_EXPANSION_EVIDENCE", "corpora": [],
              "requested_futures_expansion": None, "historical": True,
              "no_new_acquisition": True, "fresh_feed_access_verified": False,
              "profitability_verified": False, "live_feed_qualified": False,
              "strategy_qualified": False, "execution_authorized": False}
    try:
        now_ns = time.time_ns() if now_ns is None else now_ns
        _int(now_ns, 1)
        bundle = _load_json(_bounded_file(path or Path(__file__).with_name("corpus-expansion.json")))
        _keys(bundle, {"schema_version", "run_id", "source_repo", "source_commit", "consumer_commit", "artifacts"})
        _require(bundle["schema_version"] == "icarus-corpus-expansion-bundle-v1"
                 and type(bundle["run_id"]) is int and bundle["run_id"] == _RUN
                 and bundle["source_repo"] == _SOURCE and bundle["source_commit"] == _SOURCE_COMMIT
                 and bundle["consumer_commit"] == _CONSUMER_COMMIT)
        _require(type(bundle["artifacts"]) is list and len(bundle["artifacts"]) == 1)
        artifact = bundle["artifacts"][0]
        _keys(artifact, {"cache_name", "artifact_id", "receipt_sha256", "receipt_json"})
        _require(artifact["cache_name"] == "bars_primary" and type(artifact["artifact_id"]) is int
                 and artifact["artifact_id"] == _ARTIFACT_ID and artifact["receipt_sha256"] == _RECEIPT_SHA256
                 and type(artifact["receipt_json"]) is str)
        raw = artifact["receipt_json"].encode("utf-8")
        _require(hashlib.sha256(raw).hexdigest() == _RECEIPT_SHA256)
        corpus = _project(raw, "bars_primary", now_ns, source_commit=_SOURCE_COMMIT,
                          consumer_commit=_CONSUMER_COMMIT, additional_top=("requested_futures_expansion",))
        expansion = _expansion(_load_json(raw)["requested_futures_expansion"], corpus)
        corpus.update(run_id=_RUN, artifact_id=_ARTIFACT_ID, receipt_sha256=_RECEIPT_SHA256,
                      artifact_url=f"https://github.com/{_SOURCE}/actions/runs/{_RUN}/artifacts/{_ARTIFACT_ID}")
        result.update(status="HISTORICAL_EXPANSION_CONSUMPTION_VERIFIED", reason=None,
                      corpora=[corpus], requested_futures_expansion=expansion, run_id=_RUN,
                      artifact_id=_ARTIFACT_ID, receipt_sha256=_RECEIPT_SHA256,
                      source_repo=_SOURCE, source_commit=_SOURCE_COMMIT, consumer_commit=_CONSUMER_COMMIT,
                      latest_bar_closed_ts=corpus["latest_bar_closed_ts"], age_seconds=corpus["age_seconds"])
    except (ValueError, OSError, TypeError, KeyError, RecursionError, UnicodeError):
        pass  # No exception, private path, raw receipt or provider value escapes.
    return result
