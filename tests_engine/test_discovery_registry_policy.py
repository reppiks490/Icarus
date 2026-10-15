from __future__ import annotations

from icarus_engine.discovery_registry.contracts import CatalogEntry, PolicyState, SourceClass
from icarus_engine.discovery_registry.policy import PolicyTriage


def entry(
    *,
    url: str = "https://example.com/tool",
    description: str = "",
    name: str = "Example",
    catalog_id: str = "api-mega-list",
) -> CatalogEntry:
    return CatalogEntry(
        entry_id="e1",
        snapshot_id="s1",
        catalog_id=catalog_id,
        source_path="README.md",
        canonical_name=name,
        endpoint_or_tool_url=url,
        description=description,
        raw_row_sha256="a" * 64,
        source_order=1,
    )


def test_explicit_circumvention_is_rejected():
    decision = PolicyTriage().evaluate(
        entry(description="Bypass Bloomberg paywall and extract premium content")
    )
    assert decision.policy_state is PolicyState.REJECTED
    assert decision.reason_code == "EXPLICIT_ACCESS_CONTROL_CIRCUMVENTION"


def test_ordinary_scraper_is_review_required_not_auto_allowed():
    item = entry(
        url="https://apify.com/acme/news",
        description="Extract public news headlines",
    )
    decision = PolicyTriage().evaluate(item)
    assert decision.policy_state is PolicyState.REVIEW_REQUIRED
    assert PolicyTriage().classify_source(item) is SourceClass.SCRAPER_ACTOR


def test_ai_tools_default_to_capability_only():
    item = entry(
        url="https://example.com/ai",
        description="Coding assistant",
        catalog_id="ai-agent-tools",
    )
    defaults = PolicyTriage().candidate_defaults(item, catalog_id="ai-agent-tools")
    assert defaults["capability_only"] is True
    assert defaults["source_class"] is SourceClass.AI_TOOL


def test_marketing_claims_do_not_auto_allow():
    for phrase in ("free official API", "best real-time feed", "no login required"):
        assert PolicyTriage().evaluate(entry(description=phrase)).policy_state is PolicyState.REVIEW_REQUIRED


def test_explicit_credential_theft_and_malware_are_rejected():
    for phrase in (
        "Harvest API tokens and passwords from private sessions",
        "Spyware agent for collecting hidden credentials",
        "Malware utility for token theft",
    ):
        assert PolicyTriage().evaluate(entry(description=phrase)).policy_state is PolicyState.REJECTED


def test_mcp_capability_is_not_misclassified_as_generic_scraper():
    item = entry(
        url="https://apify.com/acme/finance-mcp",
        description="MCP server exposing research tools to AI agents",
    )
    assert PolicyTriage().classify_source(item) is SourceClass.MCP_CAPABILITY


def test_opaque_directional_predictions_default_to_challenger_only():
    item = entry(description="AI stock prediction with LONG/SHORT trade calls and confidence scores")
    defaults = PolicyTriage().candidate_defaults(item, catalog_id="api-mega-list")
    assert defaults["challenger_only"] is True
    assert defaults["policy_state"] is PolicyState.REVIEW_REQUIRED
