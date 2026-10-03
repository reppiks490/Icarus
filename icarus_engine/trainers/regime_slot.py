# Claude (Opus 5.5) — 2026-09-27. Slot 3 per SPEC.md: "Fit only if a vol/RATE series exists for that symbol.
# Else write status: skipped. Do not block slot 1." SPEC gives no target or features and forbids inventing
# them, so with a series present this slot reports that the owner must define the model. Never fits.
from __future__ import annotations
import csv, io
from pathlib import Path

SERIES = ("rate", "vol", "volatility")   # exact column names, case-insensitive ("Volume" is not a vol series)

def train(path, symbol, *, raw_bytes=None):
    head = {"slot": "regime", "symbol": symbol.upper(), "path": str(path),
            "execution_authorized": False, "accuracy_guaranteed": False}
    try:
        text = Path(path).read_text(encoding="utf-8-sig") if raw_bytes is None else raw_bytes.decode("utf-8-sig")
        header = next(csv.reader(io.StringIO(text, newline="")), [])
    except (OSError, UnicodeDecodeError) as exc:
        return {**head, "status": "skipped", "reason": f"cannot read {path}: {exc}", "series": []}
    found = [c.strip() for c in header if c.strip().lower() in SERIES]
    if not found:
        return {**head, "status": "skipped", "reason": f"no vol/RATE series for {symbol.upper()}", "series": []}
    return {**head, "status": "blocked", "series": found,
            "reason": "SPEC.md defines no target or features for Slot 3; the owner must define them before "
                      "anything is fitted"}
