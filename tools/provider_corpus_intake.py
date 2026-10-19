"""Consume authenticated, privately restored corpus bars without acquisition.

The Engine runner restores its vault first. This command reads the exact restored
bytes, warms all four existing paper configurations, and emits metadata only.
It never decrypts credentials, opens a provider client or evaluates FR-1.
"""
from __future__ import annotations

import argparse
import copy
import csv
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time

from icarus_engine.assets import REGISTRY
from icarus_engine.corpus_intake import (
    CorpusFeed, MAX_MANIFEST_BYTES, _snapshot, _unique_object, load_vault_bars,
)
from icarus_engine.futures_catalog import FUTURES_PRODUCTS
from icarus_engine.paper_workspaces import (
    WorkspacePortfolio, _PROFILE_DEFAULTS, REQUESTED_FUTURES_SYMBOLS, requested_futures_metadata,
)
from icarus_engine.runtime import Journal


_NATIVE_NAME = re.compile(r"databento_(?:hist_)?([a-z0-9]+)_5m\.csv\.gz\Z")
_WORKSPACES = ("cc1", "cc2", "cc3", "cc4")


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _exclusive(path: Path, payload: bytes, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        stream = os.fdopen(fd, "wb")
        fd = None
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if fd is not None:
            os.close(fd)
        path.unlink(missing_ok=True)
        raise


@contextmanager
def _offline_private_process():
    previous_mode = os.environ.get("ICARUS_FEED")
    previous_umask = os.umask(0o077)
    os.environ["ICARUS_FEED"] = "file"
    try:
        yield
    finally:
        os.umask(previous_umask)
        if previous_mode is None:
            os.environ.pop("ICARUS_FEED", None)
        else:
            os.environ["ICARUS_FEED"] = previous_mode


def _tail(dataset, rows):
    """Use the latest observed contract without retrospectively shifting prices."""
    if not rows:
        return [], 0, "NO_ROWS"
    contracts = dict(zip((bar.ts for bar in dataset.bars), dataset.contract_ids))
    last = contracts[rows[-1].ts]
    if last is None:
        return rows, 0, "CONTRACT_ID_UNAVAILABLE"
    start = len(rows) - 1
    while start > 0 and contracts[rows[start - 1].ts] == last:
        start -= 1
    return rows[start:], start, "LATEST_OBSERVED_CONTRACT"


def _history_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["ts", "open", "high", "low", "close", "volume"])
    writer.writerows((bar.ts, bar.o, bar.h, bar.l, bar.c, bar.v) for bar in rows)
    return stream.getvalue().encode()


class _CorpusReaders:
    """Route existing AssetSpec provider symbols to their exact private reader."""
    native_interval_seconds = 300

    def __init__(self, readers):
        self.readers = readers
        self._routes = {}
        for symbol, reader in readers.items():
            product = FUTURES_PRODUCTS[symbol]
            for alias in (symbol, reader.dataset.provider_root, product.provider_symbol, product.tv_symbol):
                if alias in self._routes and self._routes[alias] is not reader:
                    raise ValueError("ambiguous corpus symbol route")
                self._routes[alias] = reader

    def _reader(self, symbol):
        if symbol not in self._routes:
            raise ValueError("corpus symbol unavailable")
        return self._routes[symbol]

    def ticker(self, symbol):
        return self._reader(symbol).ticker(symbol)

    def daily_volume(self, symbol, days=5):
        return self._reader(symbol).daily_volume(symbol, days)

    def candles(self, symbol, granularity, start_ts, end_ts):
        return self._reader(symbol).candles(symbol, granularity, start_ts, end_ts)

    def recent_ex(self, symbol, granularity=300, since_ts=None):
        return self._reader(symbol).recent_ex(symbol, granularity, since_ts=since_ts)

    def recent(self, symbol, granularity=300):
        return self._reader(symbol).recent(symbol, granularity)

    def close(self):
        return None


def consume(datasets, private_dir: Path, asof_ns: int, *, include_requested_futures=False):
    """Actually warm each existing strategy; return no raw bars or simulated P&L."""
    private_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(private_dir, 0o700)
    history = private_dir / "history"
    history.mkdir(mode=0o700)
    feeds, prepared, all_reads = {}, {}, []
    end = asof_ns // 1_000_000_000
    for dataset in datasets:
        if dataset.symbol in feeds:
            raise ValueError("multiple datasets for one runtime symbol require explicit selection")
        feed = CorpusFeed(dataset)
        feeds[dataset.symbol] = feed
        reader = feed.for_consumer("history_intake")
        rows = reader.candles(dataset.symbol, 300, 0, end)
        tail, excluded, contract_status = _tail(dataset, rows)
        payload = _history_bytes(tail)
        _exclusive(history / f"{dataset.symbol}_5m.csv", payload)
        prepared[dataset.symbol] = {
            "source_rows": len(tail), "excluded_prior_contract_rows": excluded,
            "contract_status": contract_status, "history_sha256": hashlib.sha256(payload).hexdigest(),
        }
        all_reads.extend(row.to_dict() for row in reader.consumption_receipts)
    workspaces = []
    defaults = {row["id"]: row for row in _PROFILE_DEFAULTS}
    for workspace_id in _WORKSPACES:
        profile = copy.deepcopy(defaults[workspace_id])
        if include_requested_futures:
            profile["assets"] = list(dict.fromkeys([*profile["assets"], *REQUESTED_FUTURES_SYMBOLS]))
        readers = {symbol: feed.for_consumer("paper:" + workspace_id) for symbol, feed in feeds.items()
                   if symbol in profile["assets"]}
        routed = _CorpusReaders(readers)
        journal = Journal(str(private_dir / f"{workspace_id}.sqlite3"))
        assets = []
        try:
            portfolio = WorkspacePortfolio(journal, str(private_dir), workspace=profile,
                                           feeds={"yahoo": routed, "coinbase": routed, "databento_history": None},
                                           profile="nq", warmup_bars=1200, pts_ref_symbol="NQ")
            for symbol, reader in readers.items():
                # This read feeds the exact CSV snapshot consumed by AssetRunner.
                rows = reader.candles(symbol, 300, 0, end)
                tail, excluded, _ = _tail(reader.dataset, rows)
                if len(tail) != prepared[symbol]["source_rows"] or excluded != prepared[symbol]["excluded_prior_contract_rows"]:
                    raise ValueError("runtime corpus snapshot changed")
                runner = portfolio.make_runner(copy.deepcopy(REGISTRY[symbol]))
                runner.warmup(now_ts=end)
                assets.append({"symbol": symbol, "dataset_id": reader.dataset.receipt.dataset_id,
                               **prepared[symbol], "warm": runner.warm,
                               "chart_bars": len(runner.bars), "last_bar_ts": runner.last_sub_ts,
                               "native_interval_seconds": 300,
                               "mode": "CORPUS_WARMUP", "execution_authorized": False})
        finally:
            journal.close()
        for reader in readers.values():
            all_reads.extend(row.to_dict() for row in reader.consumption_receipts)
        fingerprint = hashlib.sha256(_json_bytes(profile)).hexdigest()
        workspaces.append({"id": workspace_id, "name": profile["name"], "chart": profile["chart"],
                           "inputs": profile["inputs"], "configuration_sha256": fingerprint,
                           "assets": assets, "unavailable_assets": sorted(set(profile["assets"]) - readers.keys()),
                           "paper_only": True, "execution_authorized": False})
    return workspaces, all_reads


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--restored-dir", type=Path, required=True)
    parser.add_argument("--vault-manifest", type=Path, required=True)
    parser.add_argument("--cache-name", choices=("bars_primary", "bars_secondary", "bars_third"), required=True)
    parser.add_argument("--source-repo", default="reppiks490/Icarus-engine")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--available-at-ns", type=int, required=True)
    parser.add_argument("--asof-ns", type=int, default=None)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--max-bars", type=int, default=6000)
    parser.add_argument("--filename", action="append")
    parser.add_argument("--include-requested-futures", action="store_true",
                        help="Warm the ten requested full futures families and exact available micros without acquisition")
    args = parser.parse_args(argv)
    asof = time.time_ns() if args.asof_ns is None else args.asof_ns
    report = {"schema_version": "icarus-corpus-consumption-v1", "source_repo": args.source_repo,
              "source_commit": args.source_commit, "asof_ns": asof, "datasets": [],
              "blocked_datasets": [], "workspaces": [], "read_receipts": [], "corpus_used": False,
              "paper_warmup_used": False, "consumption_purposes": [],
              "execution_authorized": False, "production_decision_authorized": False,
              "market_validation": False, "raw_payloads_included": False}
    if args.include_requested_futures:
        report["requested_futures_expansion"] = {**requested_futures_metadata(), "enabled": True,
            "available_symbols": [], "unavailable_symbols": list(REQUESTED_FUTURES_SYMBOLS),
            "warmed_symbols_by_workspace": {}, "all_full_families_warmed": False,
            "no_new_acquisition": True}
    try:
        if args.receipt.exists() or args.private_dir.exists() or args.private_dir.is_symlink():
            return 2
        if args.receipt.absolute() == args.vault_manifest.absolute():
            return 2
        # Autodiscovery has the same bounded, no-follow boundary as admission.
        manifest = json.loads(_snapshot(args.vault_manifest, MAX_MANIFEST_BYTES),
                              object_pairs_hook=_unique_object)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("caches"), dict):
            return 2
        entries = manifest["caches"].get(args.cache_name)
        if not isinstance(entries, dict):
            return 2
        # Prefer one canonical snapshot per root, falling back to retained history.
        # Never stitch two independently archived series into a fabricated input.
        selected = {}
        for name in sorted(entries, key=lambda value: (value.startswith("databento_hist_"), value)):
            match = _NATIVE_NAME.fullmatch(name)
            if match:
                selected.setdefault(match[1], name)
        filenames = args.filename or list(selected.values())
        datasets = []
        for filename in filenames:
            try:
                dataset = load_vault_bars(args.restored_dir, args.vault_manifest, args.cache_name, filename,
                                          source_repo=args.source_repo, source_commit=args.source_commit,
                                          available_at_ns=args.available_at_ns, asof_ns=asof, max_bars=args.max_bars)
                datasets.append(dataset)
                report["datasets"].append(dataset.receipt.to_dict())
            except (ValueError, OSError):
                report["blocked_datasets"].append({"input_sha256": hashlib.sha256(str(filename).encode()).hexdigest(),
                                                   "reason": "DATASET_VALIDATION_FAILED"})
        if datasets:
            with _offline_private_process():
                workspaces, reads = consume(datasets, args.private_dir, asof,
                                             include_requested_futures=args.include_requested_futures)
            report["workspaces"], report["read_receipts"] = workspaces, reads
            report["corpus_used"] = any(row["row_count"] > 0 for row in reads)
            report["paper_warmup_used"] = any(asset["warm"] and asset["chart_bars"] > 0
                                              for row in workspaces for asset in row["assets"])
            if report["corpus_used"]:
                report["consumption_purposes"] = ["QUALITY_AND_COVERAGE", "PRIVATE_HISTORY_INPUT"]
            if report["paper_warmup_used"]:
                report["consumption_purposes"].append("PAPER_CONFIGURATION_WARMUP")
        if args.include_requested_futures:
            expansion = report["requested_futures_expansion"]
            available = {dataset.symbol for dataset in datasets} & set(REQUESTED_FUTURES_SYMBOLS)
            expansion["available_symbols"] = [root for root in REQUESTED_FUTURES_SYMBOLS if root in available]
            expansion["unavailable_symbols"] = [root for root in REQUESTED_FUTURES_SYMBOLS if root not in available]
            expansion["warmed_symbols_by_workspace"] = {
                row["id"]: [asset["symbol"] for asset in row["assets"]
                            if asset["symbol"] in REQUESTED_FUTURES_SYMBOLS and asset["warm"] and asset["chart_bars"] > 0]
                for row in report["workspaces"]
            }
            warmed = expansion["warmed_symbols_by_workspace"]
            expansion["all_full_families_warmed"] = (set(warmed) == set(_WORKSPACES)
                and all(set(expansion["full_roots"]) <= set(symbols) for symbols in warmed.values()))
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        _exclusive(args.receipt, _json_bytes(report))
        return (1 if report["blocked_datasets"] else 0) if report["corpus_used"] else 2
    except (ValueError, OSError, KeyError, TypeError, RecursionError):
        # Never echo provider content, private paths, credentials or runtime logs.
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
