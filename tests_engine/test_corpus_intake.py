"""Synthetic vault bytes only: no provider, decryption, or research experiment."""
import csv
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import gzip
import hashlib
import importlib
import io
import json
import os

import pytest

pytestmark = pytest.mark.skipif(os.name != "posix", reason="private intake requires POSIX no-follow directory opens")

BASE = int(datetime(2026, 10, 18, tzinfo=timezone.utc).timestamp())
NS = 1_000_000_000
NOW = (BASE + 3600) * NS
HEADER = ["ts_open", "open", "high", "low", "close", "volume", "instrument_id"]


def _api():
    return importlib.import_module("icarus_engine.corpus_intake")


def _rows(n=4):
    return [[datetime.fromtimestamp(BASE + 300 * i, timezone.utc).isoformat(),
             "100.125", "102", "99", "101", "3", "12345"] for i in range(n)]


def _csv(rows=None, header=HEADER):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(header)
    writer.writerows(_rows() if rows is None else rows)
    return stream.getvalue()


def _source(tmp_path, text=None, filename="databento_mnq_5m.csv.gz", payload=None):
    restored = tmp_path / "restored"
    restored.mkdir()
    data = gzip.compress((_csv() if text is None else text).encode(), mtime=0) if payload is None else payload
    (restored / filename).write_bytes(data)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"caches": {"bars_primary": {filename: {
        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}}}, "key_source": "not-public"}))
    return dict(restored_dir=restored, manifest_path=manifest, cache_name="bars_primary", filename=filename,
                source_repo="reppiks490/Icarus-engine", source_commit="a" * 40,
                available_at_ns=NOW - NS, asof_ns=NOW)


def _load(args, **changes):
    return _api().load_vault_bars(**dict(args, **changes))


def test_exact_compressed_snapshot_becomes_immutable_dataset_and_safe_receipt(tmp_path):
    args = _source(tmp_path)
    dataset = _load(args)
    assert dataset.symbol == "MNQ" and dataset.provider_root == "MNQ"
    assert tuple(b.ts for b in dataset.bars) == tuple(BASE + i * 300 for i in range(4))
    assert dataset.contract_ids == (12345,) * 4
    assert dataset.receipt.source_rows == dataset.receipt.retained_rows == 4
    assert dataset.receipt.source_sha256 == hashlib.sha256((args["restored_dir"] / args["filename"]).read_bytes()).hexdigest()
    safe = dataset.receipt.to_dict()
    assert safe["provider"] == "databento" and safe["native_interval_seconds"] == 300
    assert safe["execution_authorized"] is safe["strategy_qualified"] is False
    assert safe["entitlement_status"] == "UNVERIFIED"
    assert "100.125" not in json.dumps(safe) and "not-public" not in json.dumps(safe)
    assert str(tmp_path) not in json.dumps(safe)
    with pytest.raises(FrozenInstanceError):
        dataset.bars = ()
    with pytest.raises(FrozenInstanceError):
        dataset.receipt.retained_rows = 0


@pytest.mark.parametrize("changes", [
    {"filename": "../databento_mnq_5m.csv.gz"}, {"filename": "databento_unknown_5m.csv.gz"},
    {"filename": "databento_mnq_hist_5m.csv.gz"}, {"cache_name": "bars_fourth"},
    {"source_repo": "another/repository"}, {"source_commit": "short"}, {"source_commit": "g" * 40},
    {"available_at_ns": NOW + 1}, {"available_at_ns": True}, {"asof_ns": True},
    {"max_bars": 0}, {"max_bars": True}, {"max_bars": 200_001},
])
def test_unapproved_identity_paths_or_clocks_fail_closed(tmp_path, changes):
    args = _source(tmp_path)
    with pytest.raises(ValueError):
        _load(args, **changes)


@pytest.mark.parametrize("field", ["sha256", "bytes"])
def test_manifest_tampering_is_rejected(tmp_path, field):
    args = _source(tmp_path)
    manifest = json.loads(args["manifest_path"].read_text())
    entry = manifest["caches"]["bars_primary"][args["filename"]]
    entry[field] = "0" * 64 if field == "sha256" else entry[field] + 1
    args["manifest_path"].write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest"):
        _load(args)


@pytest.mark.parametrize("kind", ["file", "directory", "manifest"])
def test_symlinks_are_rejected(tmp_path, kind):
    args = _source(tmp_path)
    if kind == "file":
        path = args["restored_dir"] / args["filename"]
    elif kind == "directory":
        path = args["restored_dir"]
    else:
        path = args["manifest_path"]
    moved = path.with_name(path.name + ".original")
    path.rename(moved)
    try:
        path.symlink_to(moved, target_is_directory=kind == "directory")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="symlink|regular|safe"):
        _load(args)


def _bad_csv(case):
    rows = _rows()
    header = list(HEADER)
    if case == "duplicate_header": header[-1] = "volume"
    elif case == "extra_header": header.append("unexpected")
    elif case == "missing_value": rows[0].pop()
    elif case == "extra_value": rows[0].append("extra")
    elif case == "naive": rows[0][0] = "2026-10-18T00:00:00"
    elif case == "subsecond": rows[0][0] = "2026-10-18T00:00:00.000000001Z"
    elif case == "misaligned": rows[0][0] = "2026-10-18T00:00:01Z"
    elif case == "duplicate": rows[1] = list(rows[0])
    elif case == "unordered": rows[0], rows[1] = rows[1], rows[0]
    elif case == "nan": rows[0][1] = "nan"
    elif case == "infinite": rows[0][2] = "inf"
    elif case == "bad_ohlc": rows[0][3] = "103"
    elif case == "negative_volume": rows[0][5] = "-1"
    elif case == "bad_contract": rows[0][6] = "1.5"
    elif case == "boolean_contract": rows[0][6] = "true"
    elif case == "empty": rows = []
    else: raise AssertionError(case)
    return _csv(rows, header)


@pytest.mark.parametrize("case", ["duplicate_header", "extra_header", "missing_value", "extra_value",
    "naive", "subsecond", "misaligned", "duplicate", "unordered", "nan", "infinite", "bad_ohlc",
    "negative_volume", "bad_contract", "boolean_contract", "empty"])
def test_invalid_csv_is_rejected_before_retaining_tail(tmp_path, case):
    with pytest.raises(ValueError):
        _load(_source(tmp_path, _bad_csv(case)), max_bars=1)


def test_invalid_gzip_and_duplicate_manifest_keys_are_rejected(tmp_path):
    args = _source(tmp_path, payload=b"not gzip")
    with pytest.raises(ValueError, match="gzip"):
        _load(args)
    args["manifest_path"].write_text('{"caches":{},"caches":{}}')
    with pytest.raises(ValueError, match="duplicate"):
        _load(args)


@pytest.mark.parametrize("bound", ["MAX_COMPRESSED_BYTES", "MAX_UNCOMPRESSED_BYTES", "MAX_MANIFEST_BYTES", "MAX_ROWS"])
def test_resource_limits_are_enforced(tmp_path, monkeypatch, bound):
    args = _source(tmp_path)
    monkeypatch.setattr(_api(), bound, 1)
    with pytest.raises(ValueError, match="limit|bound"):
        _load(args)


def test_tail_retention_and_consumer_clock_never_admit_unclosed_bars(tmp_path):
    args = _source(tmp_path)
    dataset = _load(args, max_bars=2)
    assert tuple(b.ts for b in dataset.bars) == (BASE + 600, BASE + 900)
    assert dataset.receipt.source_rows == 4 and dataset.receipt.retained_rows == 2
    earlier = _load(args, available_at_ns=(BASE + 450) * NS, asof_ns=(BASE + 450) * NS)
    assert tuple(b.ts for b in earlier.bars) == (BASE,)
    assert earlier.receipt.excluded_unclosed_rows == 3


def test_optional_contract_column_and_exact_btc_catalog_alias(tmp_path):
    rows = [r[:-1] for r in _rows()]
    dataset = _load(_source(tmp_path, _csv(rows, HEADER[:-1]), filename="databento_btc_5m.csv.gz"))
    assert dataset.symbol == "BTCF" and dataset.provider_root == "BTC"
    assert dataset.contract_ids == (None,) * 4


def test_canonical_historical_vault_filename_preserves_identity_and_root(tmp_path):
    historical_dir = tmp_path / "historical"
    plain_dir = tmp_path / "plain"
    historical_dir.mkdir()
    plain_dir.mkdir()
    historical = _load(_source(historical_dir, filename="databento_hist_nq_5m.csv.gz"))
    plain = _load(_source(plain_dir, filename="databento_nq_5m.csv.gz"))
    assert historical.symbol == historical.provider_root == "NQ"
    assert historical.receipt.filename == "databento_hist_nq_5m.csv.gz"
    assert historical.bars == plain.bars
    assert historical.receipt.source_sha256 == plain.receipt.source_sha256
    assert historical.receipt.dataset_id != plain.receipt.dataset_id
    assert historical.receipt.live_feed_qualified is False


def test_feed_reads_actual_bound_snapshot_and_records_each_consumer(tmp_path):
    args = _source(tmp_path)
    dataset = _load(args)
    feed = _api().CorpusFeed(dataset)
    one, two = feed.for_consumer("cc1"), feed.for_consumer("cc2")
    assert not one.consumption_receipts and not two.consumption_receipts
    (args["restored_dir"] / args["filename"]).write_bytes(b"changed after validation")
    assert one.candles("MNQ=F", 300, BASE, BASE + 1200) == list(dataset.bars)
    assert two.candles("MNQ", 600, BASE, BASE + 1200)[0].v == 6
    assert one.mintick("MNQ") == .25
    assert len(one.consumption_receipts) == len(two.consumption_receipts) == 1
    receipt = one.consumption_receipts[0]
    assert receipt.consumer_id == "cc1" and receipt.row_count == 4
    assert receipt.requested_interval_seconds == 300 and receipt.dataset_id == dataset.receipt.dataset_id
    assert "100.125" not in json.dumps(receipt.to_dict())
    assert receipt.execution_authorized is False
    with pytest.raises(FrozenInstanceError):
        receipt.row_count = 0


@pytest.mark.parametrize("interval", [60, 0, 400, True])
def test_feed_rejects_unsupported_resolution_without_inventing_minutes(tmp_path, interval):
    feed = _api().CorpusFeed(_load(_source(tmp_path))).for_consumer("quality")
    with pytest.raises(ValueError, match="interval|resolution"):
        feed.candles("MNQ", interval, BASE, BASE + 1200)
    assert not feed.consumption_receipts


def test_feed_rejects_other_symbols_and_preserves_native_singleton_resolution(tmp_path):
    feed = _api().CorpusFeed(_load(_source(tmp_path, _csv(_rows(1))))).for_consumer("replay")
    with pytest.raises(ValueError, match="symbol"):
        feed.candles("ES", 300, BASE, BASE + 300)
    assert len(feed.candles("MNQ", 300, BASE, BASE + 300)) == 1
    with pytest.raises(ValueError):
        feed.recent_ex("MNQ", 60)
    bars, clock, price = feed.recent_ex("MNQ", 300)
    assert bars == list(feed.dataset.bars) and clock == BASE + 300 and price == 101


def test_coarse_reads_omit_incomplete_or_mixed_contract_buckets(tmp_path):
    rows = _rows(6)
    rows.pop(2)
    dataset = _load(_source(tmp_path, _csv(rows)))
    feed = _api().CorpusFeed(dataset).for_consumer("cc1")
    assert [b.ts for b in feed.candles("MNQ", 600, BASE, BASE + 1800)] == [BASE, BASE + 1200]
    assert dataset.receipt.gap_count == 1
    # Contract changes cannot be merged into a synthetic cross-contract OHLC bar.
    other = tmp_path / "other"
    other.mkdir()
    rows = _rows()
    rows[1][6] = "67890"
    mixed = _api().CorpusFeed(_load(_source(other, _csv(rows)))).for_consumer("cc1")
    assert [b.ts for b in mixed.candles("MNQ", 600, BASE, BASE + 1200)] == [BASE + 600]


def test_coarse_bar_must_be_closed_at_consumer_clock(tmp_path):
    dataset = _load(_source(tmp_path), available_at_ns=(BASE + 900) * NS, asof_ns=(BASE + 900) * NS)
    feed = _api().CorpusFeed(dataset).for_consumer("cc1")
    assert feed.candles("MNQ", 1200, BASE, BASE + 1200) == []
    assert feed.consumption_receipts[-1].row_count == 0


@pytest.mark.parametrize("change", ["bars", "contracts"])
def test_replaced_dataset_cannot_reuse_receipt_for_other_rows(tmp_path, change):
    dataset = _load(_source(tmp_path))
    kwargs = dict(bars=(replace(dataset.bars[0], c=100.5),) + dataset.bars[1:]) if change == "bars" else dict(contract_ids=(5,) * 4)
    with pytest.raises(ValueError, match="checksum"):
        altered = replace(dataset, **kwargs)
        _api().CorpusFeed(altered).for_consumer("cc1")


@pytest.mark.parametrize("field,value", [
    ("dataset_id", "0" * 64), ("provider", "unverified"),
    ("source_repo", "other/repo"), ("source_commit", "UNPINNED"),
    ("source_sha256", "forged"), ("manifest_sha256", "1" * 64),
    ("cache_name", "bars_third"), ("filename", "databento_es_5m.csv.gz"),
    ("symbol", "ES"), ("provider_root", "ES"),
    ("compressed_bytes", 1), ("uncompressed_bytes", 1),
    ("source_rows", 999), ("retained_rows", 1), ("excluded_unclosed_rows", 999),
    ("gap_count", 999), ("contract_id_rows", 0), ("contract_identity_status", "UNKNOWN"),
    ("first_ts", BASE + 300), ("last_ts", BASE + 1200),
    ("available_at_ns", NOW - 2 * NS), ("native_interval_seconds", 60), ("max_bars", 1),
    ("provenance_status", "VERIFIED"), ("availability_basis", "BAR_TIME"),
])
def test_receipt_metadata_cannot_change_under_existing_dataset_identity(tmp_path, field, value):
    dataset = _load(_source(tmp_path))
    with pytest.raises(ValueError, match="identity|checksum|coverage"):
        changed = replace(dataset, receipt=replace(dataset.receipt, **{field: value}))
        _api().CorpusFeed(changed).candles("MNQ", 300, BASE, BASE + 1200)


def test_valid_later_receipt_clock_preserves_identity_and_reads(tmp_path):
    dataset = _load(_source(tmp_path))
    later = replace(dataset, receipt=replace(dataset.receipt, asof_ns=NOW + 3600 * NS))
    reader = _api().CorpusFeed(later).for_consumer("later")
    assert reader.candles("MNQ", 300, BASE, BASE + 1200) == list(dataset.bars)
    assert reader.consumption_receipts[-1].dataset_id == dataset.receipt.dataset_id
    assert reader.consumption_receipts[-1].asof_ns == NOW + 3600 * NS
    with pytest.raises(ValueError, match="asof_ns"):
        replace(dataset, receipt=replace(dataset.receipt, asof_ns=dataset.receipt.available_at_ns - 1))


def test_feed_public_dataset_reference_cannot_change_provenance_after_construction(tmp_path):
    args = _source(tmp_path)
    dataset = _load(args)
    other = _load(args, max_bars=1)
    feed = _api().CorpusFeed(dataset)
    with pytest.raises(AttributeError):
        feed.dataset = other


def test_receipt_authority_flags_cannot_be_promoted(tmp_path):
    dataset = _load(_source(tmp_path))
    with pytest.raises(ValueError):
        replace(dataset.receipt, execution_authorized=True)


def test_invalid_numeric_error_does_not_echo_raw_csv_field(tmp_path):
    rows = _rows()
    rows[0][1] = "PRIVATE_FIELD_MARKER"
    with pytest.raises(ValueError) as error:
        _load(_source(tmp_path, _csv(rows)))
    assert "PRIVATE_FIELD_MARKER" not in str(error.value)


def test_unsupported_safe_open_platform_fails_closed(tmp_path, monkeypatch):
    args = _source(tmp_path)
    monkeypatch.setattr(os, "supports_dir_fd", set())
    with pytest.raises(ValueError, match="no-follow"):
        _load(args)


def test_later_consumer_clock_cannot_resurrect_partial_source_snapshot_bar(tmp_path):
    dataset = _load(_source(tmp_path), available_at_ns=(BASE + 450) * NS)
    assert tuple(b.ts for b in dataset.bars) == (BASE,)
    assert dataset.receipt.excluded_unclosed_rows == 3


def test_unchanged_source_identity_survives_later_consumer_reads(tmp_path):
    args = _source(tmp_path)
    first = _load(args)
    later = _load(args, asof_ns=NOW + 3600 * NS)
    assert first.bars == later.bars
    assert first.receipt.dataset_id == later.receipt.dataset_id


def test_invalid_deflate_stream_is_a_safe_admission_error(tmp_path):
    # A valid gzip header followed by a reserved DEFLATE block type.
    payload = b"\x1f\x8b\x08\x00" + b"\x00" * 6 + b"\x07" + b"\x00" * 8
    with pytest.raises(ValueError, match="gzip"):
        _load(_source(tmp_path, payload=payload))


@pytest.mark.parametrize("cache", ["bars_secondary", "bars_third"])
def test_other_approved_account_caches_remain_distinct(tmp_path, cache):
    args = _source(tmp_path)
    manifest = json.loads(args["manifest_path"].read_text())
    manifest["caches"][cache] = manifest["caches"].pop("bars_primary")
    args["manifest_path"].write_text(json.dumps(manifest))
    dataset = _load(args, cache_name=cache)
    assert dataset.receipt.cache_name == cache and len(dataset.bars) == 4


def test_consumer_read_log_is_bounded_without_losing_actual_read_count(tmp_path, monkeypatch):
    dataset = _load(_source(tmp_path))
    monkeypatch.setattr(_api(), "MAX_READ_RECEIPTS", 2)
    reader = _api().CorpusFeed(dataset).for_consumer("cc1")
    assert reader.ticker("MNQ") == 101
    assert len(reader.recent("MNQ", 300)) == 4
    assert reader.daily_volume("MNQ") == []  # No complete UTC day in this small fixture.
    assert reader.read_count == 3 and len(reader.consumption_receipts) == 2
    assert [r.method for r in reader.consumption_receipts] == ["recent", "daily_volume"]


def test_unknown_contracts_remain_native_only_and_explicitly_unverified(tmp_path):
    rows = [r[:-1] for r in _rows()]
    dataset = _load(_source(tmp_path, _csv(rows, HEADER[:-1])))
    feed = _api().CorpusFeed(dataset).for_consumer("cc1")
    assert len(feed.candles("MNQ", 300, BASE, BASE + 1200)) == 4
    assert feed.candles("MNQ", 600, BASE, BASE + 1200) == []
    assert dataset.receipt.contract_identity_status == "UNKNOWN"


def test_deeply_nested_manifest_fails_with_safe_admission_error(tmp_path):
    args = _source(tmp_path)
    # Python 3.12's C decoder accepts 2000 levels before rejecting the root
    # shape. Ten thousand levels exercise the decoder recursion guard itself.
    args["manifest_path"].write_text("[" * 10_000 + "0" + "]" * 10_000)
    with pytest.raises(ValueError, match="manifest"):
        _load(args)


@pytest.mark.parametrize("kind", ["fifo", "directory", "parent_symlink"])
def test_special_files_and_symlinked_ancestors_are_not_read(tmp_path, kind):
    args = _source(tmp_path)
    path = args["restored_dir"] / args["filename"]
    if kind == "parent_symlink":
        actual = tmp_path / "actual"
        args["restored_dir"].rename(actual)
        # A symlink above restored_dir must also be rejected, not merely the file.
        link = tmp_path / "link"
        link.symlink_to(tmp_path, target_is_directory=True)
        args["restored_dir"] = link / "actual"
    else:
        path.unlink()
        if kind == "fifo":
            os.mkfifo(path)
        else:
            path.mkdir()
    with pytest.raises(ValueError, match="regular|symlink|safe"):
        _load(args)


def test_corrupt_gzip_crc_is_rejected_even_when_manifest_matches(tmp_path):
    payload = bytearray(gzip.compress(_csv().encode(), mtime=0))
    payload[-8] ^= 1
    with pytest.raises(ValueError, match="gzip"):
        _load(_source(tmp_path, payload=bytes(payload)))
