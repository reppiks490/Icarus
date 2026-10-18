"""Private native-corpus intake acceptance checks; generated bars only."""
import gzip
import hashlib
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _bundle(tmp_path, *, corrupt=False, contracts=False, filename="databento_mnq_5m.csv.gz"):
    restored = tmp_path / "restored"
    restored.mkdir()
    start = datetime(2026, 10, 12, tzinfo=timezone.utc)
    lines = ["ts_open,open,high,low,close,volume,instrument_id"]
    for i in range(512):
        stamp = (start + timedelta(minutes=5 * i)).isoformat()
        contract = 1 if contracts and i < 256 else 2
        lines.append(f"{stamp},100.25,101.5,99.75,100.75,10,{contract}")
    payload = gzip.compress(("\n".join(lines) + "\n").encode())
    (restored / filename).write_bytes(payload + (b"corrupt" if corrupt else b""))
    manifest = tmp_path / "vault-manifest.json"
    manifest.write_text(json.dumps({"caches": {"bars_primary": {filename: {
        "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
    }}}}))
    available = int((start + timedelta(days=3)).timestamp()) * 1_000_000_000
    report = tmp_path / "receipt.json"
    private = tmp_path / "private"
    args = ["--restored-dir", str(restored), "--vault-manifest", str(manifest),
            "--cache-name", "bars_primary", "--source-commit", "a" * 40,
            "--available-at-ns", str(available), "--asof-ns", str(available + 60_000_000_000),
            "--private-dir", str(private), "--receipt", str(report), "--max-bars", "512"]
    return args, report, private, payload


def test_actual_corpus_reaches_all_four_icarus_workspaces(tmp_path, monkeypatch):
    from tools.provider_corpus_intake import main

    args, report_path, private, _ = _bundle(tmp_path)
    monkeypatch.setenv("TWELVEDATA_API_KEY", "fixture-do-not-print")
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("intake must not acquire data"))
    assert main(args) == 0
    report = json.loads(report_path.read_text())
    assert report["corpus_used"] is True
    assert report["paper_warmup_used"] is True
    assert report["execution_authorized"] is False
    assert report["market_validation"] is False
    assert len(report["datasets"]) == 1
    dataset_id = report["datasets"][0]["dataset_id"]
    workspaces = {row["id"]: row for row in report["workspaces"]}
    assert set(workspaces) == {"cc1", "cc2", "cc3", "cc4"}
    assert workspaces["cc1"]["chart"]["timeframe"] == "20"
    assert workspaces["cc4"]["chart"]["timeframe"] == "5"
    assert workspaces["cc2"]["inputs"]["tp1_pts"] == 7.5
    assert workspaces["cc2"]["inputs"]["qty_contracts"] == 10
    for workspace in workspaces.values():
        assert workspace["paper_only"] is True
        assert workspace["execution_authorized"] is False
        asset = next(row for row in workspace["assets"] if row["symbol"] == "MNQ")
        assert asset["warm"] is True and asset["chart_bars"] > 0
        assert asset["source_rows"] == 512 and asset["dataset_id"] == dataset_id
        assert "ETH" in workspaces["cc2"]["unavailable_assets"]
    reads = report["read_receipts"]
    assert {"paper:cc1", "paper:cc2", "paper:cc3", "paper:cc4"} <= {row["consumer_id"] for row in reads}
    assert all(row["row_count"] > 0 for row in reads if row["method"] == "candles")
    assert (private / "history" / "MNQ_5m.csv").is_file()


def test_public_receipt_contains_no_prices_secrets_or_private_paths(tmp_path, monkeypatch, capsys):
    from tools.provider_corpus_intake import main

    args, report, private, _ = _bundle(tmp_path)
    monkeypatch.setenv("TWELVEDATA_API_KEY", "fixture-do-not-print")
    assert main(args) == 0
    public = report.read_text() + capsys.readouterr().out
    assert "fixture-do-not-print" not in public
    assert "100.25" not in public and "100.75" not in public
    assert str(private) not in public
    def check(value):
        if isinstance(value, dict):
            assert not ({"bars", "open", "high", "low", "close", "price", "private_path"} & value.keys())
            for child in value.values(): check(child)
        elif isinstance(value, list):
            for child in value: check(child)
    check(json.loads(report.read_text()))


def test_tampered_corpus_never_reaches_runtime(tmp_path):
    from tools.provider_corpus_intake import main

    args, report, private, _ = _bundle(tmp_path, corrupt=True)
    assert main(args) == 2
    result = json.loads(report.read_text())
    assert result["corpus_used"] is False and result["workspaces"] == []
    assert result["blocked_datasets"]
    assert not private.exists()


def test_runtime_uses_only_latest_contract_segment_without_adjusting_prices(tmp_path):
    from tools.provider_corpus_intake import main

    args, report, private, _ = _bundle(tmp_path, contracts=True)
    assert main(args) == 0
    result = json.loads(report.read_text())
    assert result["datasets"][0]["retained_rows"] == 512
    for workspace in result["workspaces"]:
        row = next(row for row in workspace["assets"] if row["symbol"] == "MNQ")
        assert row["source_rows"] == 256
        assert row["excluded_prior_contract_rows"] == 256
    assert len((private / "history" / "MNQ_5m.csv").read_text().splitlines()) == 257


@pytest.mark.skipif(os.name != "posix", reason="mode privacy is a POSIX contract")
def test_private_runtime_files_are_private_even_under_permissive_umask(tmp_path):
    from tools.provider_corpus_intake import main

    args, _, private, _ = _bundle(tmp_path)
    old = os.umask(0)
    try:
        assert main(args) == 0
    finally:
        os.umask(old)
    assert stat.S_IMODE(private.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
               for path in private.rglob("*") if path.is_file())


def test_existing_private_directory_is_never_overwritten(tmp_path):
    from tools.provider_corpus_intake import main

    args, _, private, _ = _bundle(tmp_path)
    private.mkdir()
    sentinel = private / "owner-file"
    sentinel.write_text("preserve")
    assert main(args) == 2
    assert sentinel.read_text() == "preserve"
    assert list(private.iterdir()) == [sentinel]


def test_manifest_autodiscovery_rejects_symlinks_before_consumer_import(tmp_path, monkeypatch):
    from tools import provider_corpus_intake as intake

    args, report, private, _ = _bundle(tmp_path)
    manifest = Path(args[args.index("--vault-manifest") + 1])
    real = manifest.with_name("real-manifest.json")
    manifest.rename(real)
    manifest.symlink_to(real)
    monkeypatch.setattr(intake, "load_vault_bars", lambda *a, **k: pytest.fail("unsafe manifest discovered"))
    assert intake.main(args) == 2
    assert not private.exists() and not report.exists()


def test_manifest_autodiscovery_is_bounded(tmp_path, monkeypatch):
    from tools import provider_corpus_intake as intake

    args, report, private, _ = _bundle(tmp_path)
    manifest = Path(args[args.index("--vault-manifest") + 1])
    manifest.write_bytes(b" " * (4 * 1024 * 1024 + 1))
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("unbounded manifest read"))
    assert intake.main(args) == 2
    assert not private.exists() and not report.exists()


def test_deep_manifest_rejected_without_traceback_or_runtime(tmp_path):
    from tools import provider_corpus_intake as intake

    args, report, private, _ = _bundle(tmp_path)
    manifest = Path(args[args.index("--vault-manifest") + 1])
    manifest.write_text("[" * 10_000 + "0" + "]" * 10_000)
    assert intake.main(args) == 2
    assert not private.exists() and not report.exists()


def test_non_workspace_corpus_has_real_coverage_consumption_without_paper_claim(tmp_path):
    from tools.provider_corpus_intake import main

    args, report, _, _ = _bundle(tmp_path, filename="databento_dx_5m.csv.gz")
    assert main(args) == 0
    result = json.loads(report.read_text())
    assert result["corpus_used"] is True
    assert result["paper_warmup_used"] is False
    assert result["consumption_purposes"] == ["QUALITY_AND_COVERAGE", "PRIVATE_HISTORY_INPUT"]
    assert all(row["assets"] == [] for row in result["workspaces"])
    assert any(row["consumer_id"] == "history_intake" and row["row_count"] == 512
               for row in result["read_receipts"])


def test_historical_filename_is_used_when_no_canonical_snapshot_exists(tmp_path):
    from tools.provider_corpus_intake import main

    args, report, _, _ = _bundle(tmp_path, filename="databento_hist_mnq_5m.csv.gz")
    assert main(args) == 0
    result = json.loads(report.read_text())
    assert result["datasets"][0]["filename"] == "databento_hist_mnq_5m.csv.gz"
    assert result["corpus_used"] is True


def test_autodiscovery_prefers_canonical_snapshot_without_stitching_history(tmp_path):
    from tools.provider_corpus_intake import main

    args, report, _, payload = _bundle(tmp_path)
    restored = Path(args[args.index("--restored-dir") + 1])
    manifest_path = Path(args[args.index("--vault-manifest") + 1])
    manifest = json.loads(manifest_path.read_text())
    name = "databento_hist_mnq_5m.csv.gz"
    (restored / name).write_bytes(payload)
    manifest["caches"]["bars_primary"][name] = dict(manifest["caches"]["bars_primary"]["databento_mnq_5m.csv.gz"])
    manifest_path.write_text(json.dumps(manifest))
    assert main(args) == 0
    result = json.loads(report.read_text())
    assert len(result["datasets"]) == 1
    assert result["datasets"][0]["filename"] == "databento_mnq_5m.csv.gz"
