"""Bounded, private intake of already-restored vault bars; no provider or decrypt calls.

Revision/availability are caller attestations from the pinned restore workflow. A
manifest match establishes byte identity, not entitlement or strategy qualification.
Only metadata receipts may leave the private runner; ``bars`` remain private.
"""
from __future__ import annotations

from collections import deque
import csv
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import zlib

from .evidence.timestamps import normalize_timestamp
from .feeds.bars import FileFeed
from .futures_catalog import FUTURES_PRODUCTS
from .pine.timeframe import Bar

NS = 1_000_000_000
NATIVE_INTERVAL_SECONDS = 300
MAX_COMPRESSED_BYTES = 64 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_ROWS = 2_000_000
MAX_RETAINED_BARS = 200_000
MAX_READ_RECEIPTS = 1000
_CACHES = frozenset(("bars_primary", "bars_secondary", "bars_third"))
# Retained vault roots lacking catalog specifications. This is an archive-read
# allowlist, not a new instrument registry or execution qualification.
_ARCHIVE_CONTEXT_ROOTS = frozenset(("DX", "VXM", "SR3", "ZT", "ZF", "ZC", "ZS", "ZW"))
_HEADER = ("ts_open", "open", "high", "low", "close", "volume")
_FILENAME = re.compile(r"databento_(?:hist_)?([a-z0-9]+)_5m\.csv\.gz\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_CONSUMER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}\Z")


@dataclass(frozen=True)
class CorpusReceipt:
    dataset_id: str
    provider: str
    symbol: str
    provider_root: str
    identity_status: str
    source_repo: str
    source_commit: str
    source_sha256: str
    bars_sha256: str
    manifest_sha256: str
    cache_name: str
    filename: str
    compressed_bytes: int
    uncompressed_bytes: int
    source_rows: int
    retained_rows: int
    excluded_unclosed_rows: int
    gap_count: int
    contract_id_rows: int
    contract_identity_status: str
    first_ts: int
    last_ts: int
    available_at_ns: int
    asof_ns: int
    max_bars: int
    native_interval_seconds: int = NATIVE_INTERVAL_SECONDS
    schema: str = field(default="icarus.corpus-intake/1", init=False)
    quality_status: str = field(default="VALIDATED_NATIVE_BARS", init=False)
    provenance_status: str = "MANIFEST_MATCH_CALLER_ATTESTED_REVISION"
    availability_basis: str = "CALLER_ATTESTED_SOURCE_COMMIT_TIME"
    entitlement_status: str = field(default="UNVERIFIED", init=False)
    live_feed_qualified: bool = field(default=False, init=False)
    strategy_qualified: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def to_dict(self) -> dict:
        return asdict(self)


def _receipt_identity(receipt: CorpusReceipt) -> str:
    """Bind loaded metadata while allowing a later consumer clock.

    This detects accidental mutation/replacement; it is not an authentication
    mechanism against an in-process caller able to construct fresh identities.
    """
    identity = receipt.to_dict()
    del identity["dataset_id"]
    del identity["asof_ns"]
    try:
        encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError, RecursionError):
        raise ValueError("invalid corpus receipt identity metadata") from None
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CorpusDataset:
    symbol: str
    provider_root: str
    bars: tuple[Bar, ...]
    contract_ids: tuple[int | None, ...]
    receipt: CorpusReceipt

    def __post_init__(self):
        if type(self.receipt) is not CorpusReceipt:
            raise ValueError("dataset requires a CorpusReceipt")
        if self.receipt.dataset_id != _receipt_identity(self.receipt):
            raise ValueError("dataset identity does not match receipt metadata")
        if self.symbol != self.receipt.symbol or self.provider_root != self.receipt.provider_root:
            raise ValueError("dataset identity does not match receipt")
        if _bar_checksum(self.bars, self.contract_ids) != self.receipt.bars_sha256:
            raise ValueError("dataset rows do not match receipt checksum")
        if (not self.bars or len(self.bars) != self.receipt.retained_rows
                or self.bars[0].ts != self.receipt.first_ts or self.bars[-1].ts != self.receipt.last_ts):
            raise ValueError("dataset coverage does not match receipt")
        _integer(self.receipt.available_at_ns, "available_at_ns")
        _integer(self.receipt.asof_ns, "asof_ns", self.receipt.available_at_ns)
        if any((b.ts + NATIVE_INTERVAL_SECONDS) * NS > self.receipt.available_at_ns for b in self.bars):
            raise ValueError("dataset contains a bar unclosed at source availability")


@dataclass(frozen=True)
class CorpusReadReceipt:
    consumer_id: str
    method: str
    dataset_id: str
    source_sha256: str
    source_repo: str
    source_commit: str
    symbol: str
    identity_status: str
    requested_interval_seconds: int
    requested_start_ts: int
    requested_end_ts: int
    row_count: int
    first_ts: int | None
    last_ts: int | None
    available_at_ns: int
    asof_ns: int
    native_interval_seconds: int = NATIVE_INTERVAL_SECONDS
    schema: str = field(default="icarus.corpus-read/1", init=False)
    entitlement_status: str = field(default="UNVERIFIED", init=False)
    live_feed_qualified: bool = field(default=False, init=False)
    strategy_qualified: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def to_dict(self) -> dict:
        return asdict(self)


def _integer(value, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _bar_checksum(bars, contracts) -> str:
    if type(bars) is not tuple or type(contracts) is not tuple or len(bars) != len(contracts):
        raise ValueError("dataset rows and contract identities must be immutable matching tuples")
    previous = None
    rows = []
    for bar, contract in zip(bars, contracts):
        if type(bar) is not Bar or type(bar.ts) is not int or bar.ts % NATIVE_INTERVAL_SECONDS:
            raise ValueError("invalid normalized dataset bar")
        if previous is not None and bar.ts <= previous:
            raise ValueError("normalized dataset clocks must be ordered and unique")
        previous = bar.ts
        values = (bar.o, bar.h, bar.l, bar.c, bar.v)
        if not all(type(v) is float and math.isfinite(v) and abs(v) < 1e15 for v in values):
            raise ValueError("invalid normalized dataset OHLCV")
        if bar.h < max(bar.o, bar.c) or bar.l > min(bar.o, bar.c) or bar.v < 0:
            raise ValueError("invalid normalized dataset OHLCV")
        if contract is not None and (type(contract) is not int or not 0 < contract < 2**64):
            raise ValueError("invalid normalized contract identity")
        rows.append((bar.ts, *values, contract))
    return hashlib.sha256(json.dumps(rows, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _snapshot(path, limit: int) -> bytes:
    """Read one bounded regular-file snapshot without traversing symlinks.

    Descriptor-relative directory walks keep each parent anchored on POSIX.
    Intake fails closed on hosts without the required no-follow primitives.
    The credentialed restore/intake workflow runs on Linux.
    """
    path = Path(path)
    if ".." in path.parts:
        raise ValueError("unsafe path traversal")
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("safe corpus intake requires no-follow directory opens")
    parts = path.absolute().parts
    directory = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY)
    fd = None
    try:
        for part in parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        details = os.fstat(fd)
        if not stat.S_ISREG(details.st_mode):
            raise ValueError("corpus input must be a regular file")
        if details.st_size > limit:
            raise ValueError("corpus input byte limit exceeded")
        with os.fdopen(fd, "rb") as stream:
            fd = None
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("corpus input byte limit exceeded")
        return data
    except OSError as exc:
        raise ValueError("unsafe, symlinked, or unreadable corpus input") from exc
    finally:
        if fd is not None:
            os.close(fd)
        os.close(directory)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest key")
        result[key] = value
    return result


def _timestamp(value: str) -> int:
    try:
        aware = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("bar clock must be an aware ISO timestamp") from exc
    record = normalize_timestamp(value)
    if aware.tzinfo is None or aware.utcoffset() is None or record is None or not record.whole_second:
        raise ValueError("bar clock must be aware and whole-second")
    ts = int(Decimal(record.epoch_seconds_exact))
    if ts % NATIVE_INTERVAL_SECONDS:
        raise ValueError("bar clock must align to native five-minute opens")
    return ts


def _contract(value: str) -> int | None:
    if value == "":
        return None
    try:
        number = Decimal(value)
        if not number.is_finite() or number != number.to_integral_value() or not 0 < number < 2**64:
            raise ValueError("invalid contract identity")
        return int(number)
    except InvalidOperation as exc:
        raise ValueError("invalid contract identity") from exc


def load_vault_bars(restored_dir, manifest_path, cache_name, filename, *, source_repo,
                    source_commit, available_at_ns, asof_ns, max_bars=20_000) -> CorpusDataset:
    """Validate all source rows; retain only the closed tail available at ``asof_ns``.

    ``restored_dir`` is the selected cache directory passed to Engine vault restore.
    The caller must obtain availability from the exact pinned source commit, rather
    than treating historical bar timestamps as proof of historical availability.
    No path, key-source label, or raw price enters the returned safe receipt.
    """
    if not isinstance(cache_name, str) or cache_name not in _CACHES:
        raise ValueError("unapproved vault cache")
    match = _FILENAME.fullmatch(filename) if isinstance(filename, str) else None
    if match is None:
        raise ValueError("invalid native vault filename")
    provider_root = match[1].upper()
    products = [p for p in FUTURES_PRODUCTS.values() if p.execution_root == provider_root]
    if len(products) > 1 or (not products and provider_root not in _ARCHIVE_CONTEXT_ROOTS):
        raise ValueError("unknown or ambiguous provider root")
    product = products[0] if products else None
    symbol = product.root if product else provider_root
    identity_status = "CATALOG_MAPPED" if product else "ARCHIVE_CONTEXT_ONLY"
    if source_repo != "reppiks490/Icarus-engine" or not isinstance(source_commit, str) or not _COMMIT.fullmatch(source_commit):
        raise ValueError("source repository and exact commit are required")
    _integer(available_at_ns, "available_at_ns")
    _integer(asof_ns, "asof_ns")
    _integer(max_bars, "max_bars", 1)
    if max_bars > MAX_RETAINED_BARS:
        raise ValueError("retained row limit exceeded")
    if asof_ns < available_at_ns:
        raise ValueError("dataset was unavailable at consumer clock")
    manifest_bytes = _snapshot(manifest_path, MAX_MANIFEST_BYTES)
    try:
        manifest = json.loads(manifest_bytes, object_pairs_hook=_unique_object)
        entry = manifest["caches"][cache_name][filename]
        digest, length = entry["sha256"], entry["bytes"]
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid or missing vault manifest entry") from exc
    if not isinstance(digest, str) or not _SHA.fullmatch(digest) or type(length) is not int or length <= 0:
        raise ValueError("invalid vault manifest byte identity")
    if length > MAX_COMPRESSED_BYTES:
        raise ValueError("compressed byte limit exceeded")
    snapshot = _snapshot(Path(restored_dir) / filename, MAX_COMPRESSED_BYTES)
    if len(snapshot) != length or hashlib.sha256(snapshot).hexdigest() != digest:
        raise ValueError("compressed bytes do not match vault manifest")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(snapshot), mode="rb") as stream:
            raw = stream.read(MAX_UNCOMPRESSED_BYTES + 1)
        if len(raw) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("uncompressed byte limit exceeded")
        text = raw.decode("utf-8")
    except (OSError, EOFError, UnicodeError, zlib.error) as exc:
        raise ValueError("invalid gzip CSV") from exc
    retained = deque(maxlen=max_bars)
    previous, count, unclosed, gaps = None, 0, 0, 0
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader, None)
        if header not in (list(_HEADER), list(_HEADER) + ["instrument_id"]):
            raise ValueError("CSV requires exact unique native bar headers")
        for row in reader:
            count += 1
            if count > MAX_ROWS:
                raise ValueError("source row limit exceeded")
            if len(row) != len(header) or any(len(value) > 128 for value in row):
                raise ValueError("invalid CSV row width or field bound")
            ts = _timestamp(row[0])
            if previous is not None:
                if ts <= previous:
                    raise ValueError("bar clocks must be ordered and unique")
                gaps += (ts - previous) // NATIVE_INTERVAL_SECONDS - 1
            previous = ts
            try:
                values = tuple(float(value) for value in row[1:6])
            except ValueError:
                raise ValueError("invalid OHLCV numeric field") from None
            o, h, l, c, v = values
            if not all(math.isfinite(value) and abs(value) < 1e15 for value in values):
                raise ValueError("nonfinite or excessive OHLCV")
            if h < l or h < max(o, c) or l > min(o, c) or v < 0:
                raise ValueError("impossible OHLCV")
            contract = _contract(row[6]) if len(header) == 7 else None
            if (ts + NATIVE_INTERVAL_SECONDS) * NS <= min(available_at_ns, asof_ns):
                retained.append((Bar(ts, o, h, l, c, v), contract))
            else:
                unclosed += 1
    except csv.Error as exc:
        raise ValueError("invalid CSV") from exc
    if not retained:
        raise ValueError("no closed bars available at consumer clock")
    bars, contracts = zip(*retained)
    bars_digest = _bar_checksum(tuple(bars), tuple(contracts))
    known_contracts = sum(contract is not None for contract in contracts)
    contract_status = "COMPLETE" if known_contracts == len(contracts) else "PARTIAL" if known_contracts else "UNKNOWN"
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    receipt = CorpusReceipt(dataset_id="", provider="databento", symbol=symbol,
                            provider_root=provider_root, identity_status=identity_status,
                            source_repo=source_repo, source_commit=source_commit,
                            source_sha256=digest, bars_sha256=bars_digest, manifest_sha256=manifest_digest, cache_name=cache_name,
                            filename=filename, compressed_bytes=len(snapshot), uncompressed_bytes=len(raw),
                            source_rows=count, retained_rows=len(bars), excluded_unclosed_rows=unclosed,
                            gap_count=gaps, contract_id_rows=known_contracts, contract_identity_status=contract_status,
                            first_ts=bars[0].ts, last_ts=bars[-1].ts,
                            available_at_ns=available_at_ns, asof_ns=asof_ns, max_bars=max_bars)
    receipt = replace(receipt, dataset_id=_receipt_identity(receipt))
    return CorpusDataset(symbol, provider_root, tuple(bars), tuple(contracts), receipt)


class CorpusFeed:
    """FileFeed-shaped immutable snapshot, requiring explicit native-resolution reads.

    Runtime.poll currently asks for 60s bars; a separate native-300s adapter is
    required there. This feed rejects that finer request rather than inventing it.
    Coarse reads omit incomplete, unclosed, unknown-contract or cross-contract buckets. Receipts
    retain the latest 1000 reads per consumer; ``read_count`` counts every read.
    """
    native_interval_seconds = NATIVE_INTERVAL_SECONDS
    GRANULARITIES = (300, 600, 900, 1200, 1800, 3600, 86400)

    def __init__(self, dataset: CorpusDataset, consumer_id: str = "unspecified"):
        if not isinstance(dataset, CorpusDataset):
            raise ValueError("CorpusFeed requires an admitted CorpusDataset")
        if not isinstance(consumer_id, str) or not _CONSUMER.fullmatch(consumer_id):
            raise ValueError("invalid consumer identity")
        self._dataset = dataset
        self._consumer_id = consumer_id
        self._context_only = dataset.receipt.identity_status == "ARCHIVE_CONTEXT_ONLY"
        if self._context_only:
            self._symbols = {dataset.provider_root}
            self.GRANULARITIES = (NATIVE_INTERVAL_SECONDS,)
            self._feed = None  # No invented tick size for an uncatalogued root.
        else:
            product = FUTURES_PRODUCTS[dataset.symbol]
            self._symbols = {dataset.symbol, dataset.provider_root, product.provider_symbol, product.tv_symbol}
            self._feed = FileFeed(list(dataset.bars), mintick=product.tick_size)
            # Singleton/session gaps must not imply a different native interval.
            self._feed._granularity = NATIVE_INTERVAL_SECONDS
        self._reads = deque(maxlen=MAX_READ_RECEIPTS)
        self._read_count = 0

    @property
    def dataset(self) -> CorpusDataset:
        return self._dataset

    @property
    def consumer_id(self) -> str:
        return self._consumer_id

    @property
    def read_count(self) -> int:
        return self._read_count

    @property
    def consumption_receipts(self) -> tuple[CorpusReadReceipt, ...]:
        return tuple(self._reads)

    def for_consumer(self, consumer_id: str) -> CorpusFeed:
        return CorpusFeed(self.dataset, consumer_id)

    def _symbol(self, symbol):
        if not isinstance(symbol, str) or symbol.upper() not in self._symbols:
            raise ValueError("symbol does not match corpus dataset")

    def _candles(self, symbol, interval, start, end):
        self._symbol(symbol)
        _integer(interval, "requested interval", NATIVE_INTERVAL_SECONDS)
        if interval % NATIVE_INTERVAL_SECONDS:
            raise ValueError("unsupported interval: native resolution is 300 seconds")
        _integer(start, "start_ts")
        _integer(end, "end_ts")
        if end < start:
            raise ValueError("requested interval window is reversed")
        if self._context_only:
            if interval != NATIVE_INTERVAL_SECONDS:
                raise ValueError("archive context supports only native 300-second reads")
            return [bar for bar in self.dataset.bars if start <= bar.ts < end]
        if interval == NATIVE_INTERVAL_SECONDS:
            return self._feed.candles(symbol, interval, start, end)
        grouped = {}
        for bar, contract in zip(self.dataset.bars, self.dataset.contract_ids):
            if start <= bar.ts < end:
                grouped.setdefault(bar.ts // interval * interval, []).append((bar.ts, contract))
        complete = set()
        for bucket, rows in grouped.items():
            if (bucket * NS + interval * NS <= self.dataset.receipt.asof_ns
                    and len(rows) == interval // NATIVE_INTERVAL_SECONDS
                    and rows[0][0] == bucket and rows[-1][0] == bucket + interval - NATIVE_INTERVAL_SECONDS
                    and rows[0][1] is not None
                    and len({contract for _, contract in rows}) == 1):
                complete.add(bucket)
        return [b for b in self._feed.candles(symbol, interval, start, end) if b.ts in complete]

    def _record(self, method, interval, start, end, bars):
        receipt = self.dataset.receipt
        self._reads.append(CorpusReadReceipt(
            consumer_id=self.consumer_id, method=method, dataset_id=receipt.dataset_id,
            source_sha256=receipt.source_sha256, source_repo=receipt.source_repo,
            source_commit=receipt.source_commit, symbol=receipt.symbol, identity_status=receipt.identity_status,
            requested_interval_seconds=interval, requested_start_ts=start, requested_end_ts=end,
            row_count=len(bars), first_ts=bars[0].ts if bars else None, last_ts=bars[-1].ts if bars else None,
            available_at_ns=receipt.available_at_ns, asof_ns=receipt.asof_ns))
        self._read_count += 1

    def candles(self, symbol: str, granularity: int, start_ts: int, end_ts: int) -> list[Bar]:
        bars = self._candles(symbol, granularity, start_ts, end_ts)
        self._record("candles", granularity, start_ts, end_ts, bars)
        return bars

    def mintick(self, symbol: str) -> float:
        self._symbol(symbol)
        if self._context_only:
            raise ValueError("archive context has no verified instrument specification")
        return self._feed.mintick(symbol)

    def ticker(self, symbol: str) -> float | None:
        self._symbol(symbol)
        bars = list(self.dataset.bars[-1:])
        self._record("ticker", NATIVE_INTERVAL_SECONDS, bars[0].ts, bars[0].ts + NATIVE_INTERVAL_SECONDS, bars)
        return bars[-1].c

    def recent_ex(self, symbol: str, granularity: int = 60, since_ts: int | None = None):
        start = 0 if since_ts is None else since_ts
        end = self.dataset.receipt.asof_ns // NS
        bars = self._candles(symbol, granularity, start, end)
        self._record("recent_ex", granularity, start, end, bars)
        return (bars, bars[-1].ts + granularity, bars[-1].c) if bars else ([], 0, None)

    def recent(self, symbol: str, granularity: int = 60) -> list[Bar]:
        end = self.dataset.receipt.asof_ns // NS
        bars = self._candles(symbol, granularity, 0, end)
        self._record("recent", granularity, 0, end, bars)
        return bars

    def daily_volume(self, symbol: str, days: int = 5):
        _integer(days, "days", 1)
        end = self.dataset.receipt.asof_ns // NS
        bars = self._candles(symbol, 86400, 0, end)[-max(days, 2):]
        self._record("daily_volume", 86400, 0, end, bars)
        return [(b.ts, b.c, b.v) for b in bars]
