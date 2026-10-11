from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from types import MappingProxyType
from typing import Callable, Mapping

from .contracts import CatalogEntry, CatalogSnapshot
from .normalize import normalize_name


_LINK_START_RE = re.compile(r"\[((?:\\.|[^\\\]])+)\]\(")
_BULLET_START_RE = re.compile(r"^\s*[-*]\s+(?:\*\*)?")
_HEADING_START_RE = re.compile(r"^\s*#{1,6}\s+(?:\*\*)?")
_SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")


@dataclass(frozen=True, slots=True)
class CatalogImportResult:
    entries: tuple[CatalogEntry, ...]
    raw_count: int
    parse_failures: tuple[Mapping[str, str], ...]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean_heading(line: str) -> str:
    value = re.sub(r"^\s*#{1,6}\s*", "", line).strip()
    return normalize_name(value)


def _markdown_link(text: str) -> tuple[str, str, int, int] | None:
    """Read one bounded inline link without truncating balanced URL parentheses."""
    match = _LINK_START_RE.search(text)
    if match is None:
        return None
    depth, escaped, quote, angle = 1, False, None, False
    for index in range(match.end(), len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if angle:
            if char == ">":
                angle = False
            continue
        if char == "<" and index == match.end():
            angle = True
            continue
        if char in {"'", '"'} and index > match.end() and text[index - 1].isspace():
            quote = char
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                body = text[match.end():index].strip()
                if body.startswith("<"):
                    closing = body.find(">")
                    if closing < 0:
                        return None
                    url, title = body[1:closing], body[closing + 1:].strip()
                else:
                    parts = body.split(maxsplit=1)
                    if not parts:
                        return None
                    url, title = parts[0], parts[1].strip() if len(parts) > 1 else ""
                if not url or any(char.isspace() for char in url):
                    return None
                if title and not re.fullmatch(r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\([^)]*\))''', title):
                    return None
                url = re.sub(r"\\([()])", r"\1", url)
                return match.group(1), url, match.start(), index + 1
    return None


def _description_after_link(text: str, end: int) -> str:
    tail = text[end:].strip()
    if tail.startswith("**"):
        tail = tail[2:].lstrip()
    return re.sub(r"^[-—–:]\s*", "", tail).strip()


def _split_table_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith(r"\|"):
        text = text[:-1]

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in text:
        if escaped:
            if char == "|":
                current.append("|")
            else:
                current.extend(("\\", char))
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if escaped:
        current.append("\\")
    cells.append("".join(current).strip())
    return cells


def _is_table_header(cells: list[str]) -> bool:
    if not cells:
        return False
    first = cells[0].strip().casefold()
    return first in {"api name", "name", "tool", "tool name"}


def _is_table_separator(cells: list[str]) -> bool:
    return bool(cells) and all(_SEPARATOR_RE.fullmatch(cell.replace(" ", "")) for cell in cells)


def _entry(
    snapshot: CatalogSnapshot,
    *,
    line_no: int,
    raw_line: str,
    name: str,
    url: str,
    description: str,
    category: str,
    importer_name: str,
) -> CatalogEntry:
    raw_hash = _sha256(raw_line)
    material = "\0".join(
        (
            snapshot.snapshot_id or "",
            snapshot.upstream_path,
            str(line_no),
            raw_hash,
        )
    )
    entry_id = _sha256(material)
    return CatalogEntry(
        entry_id=entry_id,
        snapshot_id=snapshot.snapshot_id or "",
        catalog_id=snapshot.catalog_id,
        source_path=snapshot.upstream_path,
        canonical_name=normalize_name(name),
        endpoint_or_tool_url=url.strip(),
        description=description.strip(),
        category=category or None,
        raw_row_sha256=raw_hash,
        source_order=line_no,
        metadata={"importer": importer_name},
    )


def _failure(*, line_no: int, raw_line: str, reason: str) -> Mapping[str, str]:
    return MappingProxyType(
        {
            "reason": reason,
            "source_order": str(line_no),
            "raw_row_sha256": _sha256(raw_line),
        }
    )


def _parse_table_catalog(
    snapshot: CatalogSnapshot,
    text: str,
    *,
    importer_name: str,
) -> CatalogImportResult:
    entries: list[CatalogEntry] = []
    failures: list[Mapping[str, str]] = []
    raw_count = 0
    category = ""

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            category = _clean_heading(stripped)
            continue
        if "|" not in stripped:
            continue

        cells = _split_table_row(raw_line)
        if _is_table_header(cells) or _is_table_separator(cells):
            continue
        raw_count += 1
        match = _markdown_link(cells[0]) if len(cells) >= 2 else None
        if match is None:
            failures.append(
                _failure(line_no=line_no, raw_line=raw_line, reason="MALFORMED_CATALOG_ROW")
            )
            continue

        name, url, _, _ = match
        if not normalize_name(name) or not url.strip():
            failures.append(
                _failure(line_no=line_no, raw_line=raw_line, reason="MALFORMED_CATALOG_ROW")
            )
            continue

        description = " | ".join(cells[1:]).strip()
        entries.append(
            _entry(
                snapshot,
                line_no=line_no,
                raw_line=raw_line,
                name=name,
                url=url,
                description=description,
                category=category,
                importer_name=importer_name,
            )
        )

    return CatalogImportResult(tuple(entries), raw_count, tuple(failures))


def parse_api_mega_list(snapshot: CatalogSnapshot, text: str) -> CatalogImportResult:
    return _parse_table_catalog(snapshot, text, importer_name="api_mega")


def parse_scraping_apis(snapshot: CatalogSnapshot, text: str) -> CatalogImportResult:
    return _parse_table_catalog(snapshot, text, importer_name="scraping_apis")


def parse_ai_agent_tools(snapshot: CatalogSnapshot, text: str) -> CatalogImportResult:
    entries: list[CatalogEntry] = []
    failures: list[Mapping[str, str]] = []
    raw_count = 0
    category = ""

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        heading = _HEADING_START_RE.match(raw_line)
        prefix = heading or _BULLET_START_RE.match(raw_line)
        if prefix is None:
            continue
        match = _markdown_link(raw_line)
        if heading and (match is None or match[2] != prefix.end()):
            # Ordinary headings are categories; linked feature headings are entries.
            if not raw_line[prefix.end():].startswith("["):
                category = _clean_heading(stripped)
                continue
        raw_count += 1
        if match is None or match[2] != prefix.end():
            failures.append(
                _failure(line_no=line_no, raw_line=raw_line, reason="MALFORMED_CATALOG_ROW")
            )
            continue

        name, url, _, end = match
        description = _description_after_link(raw_line, end)
        if not normalize_name(name) or not url.strip():
            failures.append(
                _failure(line_no=line_no, raw_line=raw_line, reason="MALFORMED_CATALOG_ROW")
            )
            continue

        entries.append(
            _entry(
                snapshot,
                line_no=line_no,
                raw_line=raw_line,
                name=name,
                url=url,
                description=description,
                category=category,
                importer_name="ai_agent_tools",
            )
        )

    return CatalogImportResult(tuple(entries), raw_count, tuple(failures))


_IMPORTERS: dict[str, Callable[[CatalogSnapshot, str], CatalogImportResult]] = {
    "api_mega": parse_api_mega_list,
    "scraping_apis": parse_scraping_apis,
    "ai_agent_tools": parse_ai_agent_tools,
}


def importer_for(name: str) -> Callable[[CatalogSnapshot, str], CatalogImportResult]:
    try:
        return _IMPORTERS[name]
    except KeyError as exc:
        raise ValueError(f"unknown discovery catalog importer: {name}") from exc


__all__ = [
    "CatalogImportResult",
    "importer_for",
    "parse_ai_agent_tools",
    "parse_api_mega_list",
    "parse_scraping_apis",
]
