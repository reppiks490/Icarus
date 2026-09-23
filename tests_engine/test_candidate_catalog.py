"""CA: source-collision and duplicate guards for candidate CSV intake."""
import zipfile

from icarus_engine.audit.candidate_catalog import catalog_candidates


def _write_zip(path, members):
    with zipfile.ZipFile(path, "w") as bundle:
        for name, text in members.items():
            bundle.writestr(name, text)


def test_catalog_matches_source_and_does_not_qualify(tmp_path):
    archives, flat = tmp_path / "archives", tmp_path / "flat"
    archives.mkdir()
    flat.mkdir()
    first = "time,open,high,low,close,Volume\n1,1,2,1,2,10\n2,2,3,2,3,11\n"
    second = "time,open,high,low,close,Volume\n1,1,2,1,2,10\n"
    _write_zip(archives / "a.zip", {"sub/BATS_AAPL, 1.csv": first,
                                   "sub/BATS_MSFT, 1.csv": second})
    (flat / "BATS_AAPL, 1.csv").write_bytes(first.encode())
    (flat / "BATS_MSFT, 1.csv").write_bytes(second.encode())
    report = catalog_candidates(archives, flat, ("a.zip",))
    assert report["status"] == "provenance_checked"
    assert report["source_members"] == 2
    assert report["flat_files"] == 2
    assert report["unique_content_hashes"] == 2
    assert report["files"][0]["data_rows"] == 2
    assert report["files"][0]["first_time_raw"] == "1"
    assert all(not row["candidate_qualified"] for row in report["files"])


def test_catalog_flags_same_name_different_content(tmp_path):
    archives, flat = tmp_path / "archives", tmp_path / "flat"
    archives.mkdir()
    flat.mkdir()
    first = "time,close\n1,2\n"
    second = "time,close\n1,3\n"
    _write_zip(archives / "a.zip", {"BATS_AAPL, 1.csv": first})
    _write_zip(archives / "b.zip", {"BATS_AAPL, 1.csv": second})
    (flat / "BATS_AAPL, 1.csv").write_bytes(first.encode())
    report = catalog_candidates(archives, flat, ("a.zip", "b.zip"))
    assert report["status"] == "provenance_needs_review"
    assert report["files"][0]["status"] == "filename_collision_review"
    assert len(report["files"][0]["source_members"]) == 2


def test_catalog_flags_missing_flat_and_unmatched_content(tmp_path):
    archives, flat = tmp_path / "archives", tmp_path / "flat"
    archives.mkdir()
    flat.mkdir()
    _write_zip(archives / "a.zip", {"BATS_AAPL, 1.csv": "time,close\n1,2\n",
                                   "BATS_MSFT, 1.csv": "time,close\n1,2\n"})
    (flat / "BATS_AAPL, 1.csv").write_bytes(b"time,close\n1,9\n")
    report = catalog_candidates(archives, flat, ("a.zip",))
    assert report["status"] == "provenance_needs_review"
    assert report["missing_flat_filenames"] == ["BATS_MSFT, 1.csv"]
    assert report["files"][0]["status"] == "unmatched_flat_file"
