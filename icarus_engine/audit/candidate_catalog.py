"""CA: reproducible provenance inventory for owner candidate CSV batches."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

from icarus_engine.unzip_batches import BATCHES, _classify


def _digest(stream):
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _csv_observations(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        rows = 0
        first_time = last_time = None
        for row in reader:
            if not row:
                continue
            rows += 1
            if first_time is None:
                first_time = row[0]
            last_time = row[0]
    return {"columns": header, "data_rows": rows,
            "first_time_raw": first_time, "last_time_raw": last_time}


def catalog_candidates(archives, flat_dir, archive_names=BATCHES):
    """Compare flattened candidates with every matching archive member.

    A filename or content hash is a source identity, never a candidate verdict.
    Unparsed chart-type and timezone metadata remain explicitly unknown.
    """
    archives, flat_dir = Path(archives), Path(flat_dir)
    source = defaultdict(list)
    archive_records = []
    for name in archive_names:
        path = archives / name
        if not path.is_file():
            raise FileNotFoundError(path)
        with path.open("rb") as handle:
            archive_hash, _ = _digest(handle)
        count = 0
        with zipfile.ZipFile(path) as bundle:
            for member in bundle.infolist():
                if member.is_dir() or not member.filename.lower().endswith(".csv"):
                    continue
                base = PurePosixPath(member.filename.replace("\\", "/")).name
                if not base or base.startswith(".") or _classify(base) != "candidates":
                    continue
                with bundle.open(member) as handle:
                    digest, size = _digest(handle)
                source[base].append({"archive": name, "member": member.filename,
                                     "sha256": digest, "bytes": size})
                count += 1
        archive_records.append({"archive": name, "sha256": archive_hash,
                                "candidate_members": count})

    files = []
    for path in sorted(flat_dir.glob("*.csv"), key=lambda p: p.name.casefold()):
        with path.open("rb") as handle:
            digest, size = _digest(handle)
        matches = source.get(path.name, [])
        distinct_source_hashes = sorted({item["sha256"] for item in matches})
        if digest not in distinct_source_hashes:
            status = "unmatched_flat_file"
        elif len(distinct_source_hashes) > 1:
            status = "filename_collision_review"
        else:
            status = "source_hash_matched"
        instrument, _, interval = path.stem.partition(",")
        files.append({"filename": path.name, "instrument": instrument,
                      "interval_label_unverified": interval.strip(),
                      "sha256": digest, "bytes": size, "status": status,
                      "source_members": matches, "chart_type_verified": False,
                      "timezone_verified": False, "candidate_qualified": False,
                      **_csv_observations(path)})

    flat_names = {entry["filename"] for entry in files}
    missing = sorted(set(source) - flat_names)
    status = "provenance_checked"
    if missing or any(row["status"] != "source_hash_matched" for row in files):
        status = "provenance_needs_review"
    return {"author": "CA", "status": status,
            "execution_authorized": False, "candidate_qualified": False,
            "archive_records": archive_records,
            "source_members": sum(len(items) for items in source.values()),
            "flat_files": len(files),
            "unique_content_hashes": len({row["sha256"] for row in files}),
            "distinct_instruments": sorted({row["instrument"] for row in files}),
            "missing_flat_filenames": missing, "files": files}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", required=True, type=Path)
    parser.add_argument("--flat", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    report = catalog_candidates(args.archives, args.flat)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temp = args.out.with_suffix(args.out.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
    os.replace(temp, args.out)
    print(json.dumps({k: report[k] for k in ("status", "flat_files",
                      "unique_content_hashes", "distinct_instruments",
                      "missing_flat_filenames")}, indent=2))
    return 0 if report["status"] == "provenance_checked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
