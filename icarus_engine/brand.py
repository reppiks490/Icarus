# Claude (Opus 5.5) — 2026-09-27. The product name, in one place. Dashboards carry a token the servers fill in,
# CLI help reads NAME, and the static text in STATIC_FILES is kept in step by check() (a test runs it).
# Rename everything with one command:   py -3 -m icarus_engine.brand "NEW NAME"
# Package names, CLI commands, ports, environment variables and the MCP server keep their icarus ids on
# purpose: renaming those would break the running engine, every script and every agent's handoff.
from __future__ import annotations
import re, sys
from pathlib import Path

NAME = "DIVINE PROVIDENCE: THE HEART OF ICARUS"
STRATEGY = "THE PULSE OF ICARUS"          # the Pine strategy the engine mirrors; that name belongs to the Pine
TOKEN = b"@BRAND@"
STATIC_FILES = ("icarus_engine/brand.py", "pyproject.toml", "README.md")
_NAME_LINE = re.compile(r'^NAME = "([^"\n]*)"$', re.M)

def render(html: bytes) -> bytes:
    return html.replace(TOKEN, NAME.encode("utf-8"))

def _expected(name):
    return {"icarus_engine/brand.py": f'NAME = "{name}"', "pyproject.toml": f'description = "{name} ',
            "README.md": f"# {name}\n"}

def check(root, name=NAME):
    """Static files that do not carry `name` where they should; empty when all agree."""
    root = Path(root)
    wrong = []
    for rel, needle in _expected(name).items():
        text = (root / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")
        if needle not in text or (rel == "README.md" and not text.startswith(needle)):
            wrong.append(rel)
    return wrong

def rename(root, new):
    """Rename the product in every static file; returns the files changed. Dashboards and CLIs follow NAME."""
    new = new.strip()
    if not new or any(c in new for c in '"\\\n\r') or not new.isascii():
        raise ValueError("the name must be plain ASCII without quotes, backslashes or newlines")
    root = Path(root)
    old = _NAME_LINE.search((root / "icarus_engine/brand.py").read_text(encoding="utf-8")).group(1)
    if check(root, old):
        raise ValueError(f"static files are out of step with {old!r}: {check(root, old)}")
    changed = []
    for rel, needle in _expected(old).items():
        p = root / rel
        raw = p.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n").replace(needle, _expected(new)[rel], 1)
        p.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        changed.append(rel)
    return changed

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit('usage: py -3 -m icarus_engine.brand "NEW NAME"')
    for rel in rename(Path(__file__).resolve().parents[1], sys.argv[1]):
        print(f"renamed in {rel}")
