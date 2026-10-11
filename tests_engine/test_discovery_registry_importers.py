from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from icarus_engine.discovery_registry.contracts import CatalogSnapshot
from icarus_engine.discovery_registry.importers import (
    importer_for,
    parse_ai_agent_tools,
    parse_api_mega_list,
    parse_scraping_apis,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery_registry"


@dataclass(frozen=True)
class Fixtures:
    api_mega: str
    scraping: str
    ai_tools: str


def fixtures() -> Fixtures:
    return Fixtures(
        api_mega=(FIXTURE_DIR / "api_mega.md").read_text(encoding="utf-8"),
        scraping=(FIXTURE_DIR / "scraping_apis.md").read_text(encoding="utf-8"),
        ai_tools=(FIXTURE_DIR / "ai_agent_tools.md").read_text(encoding="utf-8"),
    )


def snapshot(catalog_id: str) -> CatalogSnapshot:
    return CatalogSnapshot(
        catalog_id=catalog_id,
        upstream_repo=f"cporter202/{catalog_id}",
        upstream_commit="a" * 40,
        upstream_path="README.md",
        content_sha256="b" * 64,
        retrieved_at="2026-10-11T19:25:00Z",
        parser_revision="v1",
    )


def test_all_three_importers_produce_entries():
    data = fixtures()
    assert len(parse_api_mega_list(snapshot("api-mega-list"), data.api_mega).entries) == 4
    assert len(parse_scraping_apis(snapshot("scraping-apis-for-devs"), data.scraping).entries) == 3
    assert len(parse_ai_agent_tools(snapshot("ai-agent-tools"), data.ai_tools).entries) == 2


def test_malformed_rows_are_reported():
    result = parse_api_mega_list(snapshot("api-mega-list"), fixtures().api_mega)
    assert result.raw_count == 5
    assert len(result.parse_failures) == 1
    assert result.parse_failures[0]["reason"] == "MALFORMED_CATALOG_ROW"


def test_escaped_pipe_stays_inside_description():
    result = parse_api_mega_list(snapshot("api-mega-list"), fixtures().api_mega)
    row = next(item for item in result.entries if item.canonical_name == "Pipe Example")
    assert "A | B" in row.description


def test_parser_is_deterministic_for_same_snapshot_and_text():
    snap = snapshot("scraping-apis-for-devs")
    text = fixtures().scraping
    assert parse_scraping_apis(snap, text) == parse_scraping_apis(snap, text)


def test_importer_lookup_is_explicit_and_complete():
    assert importer_for("api_mega") is parse_api_mega_list
    assert importer_for("scraping_apis") is parse_scraping_apis
    assert importer_for("ai_agent_tools") is parse_ai_agent_tools


def test_entries_preserve_source_path_raw_hash_category_and_source_order():
    row = parse_ai_agent_tools(snapshot("ai-agent-tools"), fixtures().ai_tools).entries[0]
    assert row.source_path == "README.md"
    assert row.raw_row_sha256 is not None and len(row.raw_row_sha256) == 64
    assert row.category == "Editor's Choice / Sponsored"
    assert row.source_order > 0
