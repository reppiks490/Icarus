# Grok (xAI) — 2026-09-22. Whole file. Every model writes the repo log.
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

LOG = Path("HANDOFF_LOG.md")

def log_action(who: str, title: str, body: str = "", override: bool = False):
    who = (who or "unknown").strip()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    tag = " OVERRIDE" if override else ""
    block = f"\n## {stamp} — {who}{tag}\n- {title}\n"
    if body:
        block += f"```\n{body.rstrip()}\n```\n"
    path = LOG
    prev = path.read_text(encoding="utf-8") if path.is_file() else "# Handoff log\n"
    # newest first after the heading line
    lines = prev.splitlines(True)
    if lines and lines[0].startswith("#"):
        new = lines[0] + block + "".join(lines[1:])
    else:
        new = "# Handoff log\n" + block + prev
    path.write_text(new, encoding="utf-8")
    return path
