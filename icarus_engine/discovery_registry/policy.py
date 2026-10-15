from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Callable
from urllib.parse import urlsplit

from .contracts import CatalogEntry, PolicyDecision, PolicyState, SourceClass


_CIRCUMVENTION = (
    re.compile(r"\bbypass\b.{0,120}\b(paywall|subscription)\b", re.IGNORECASE),
    re.compile(r"\b(circumvent|evade)\b.{0,120}\b(access control|authentication|paywall|subscription)\b", re.IGNORECASE),
)
_CREDENTIAL_THEFT = re.compile(
    r"\b(steal|harvest)\b.{0,120}\b(credential|credentials|token|tokens|password|passwords)\b",
    re.IGNORECASE,
)
_MALWARE = re.compile(r"\b(malware|spyware)\b", re.IGNORECASE)
_OPAQUE_PREDICTION = re.compile(
    r"\b(stock|market|crypto|futures|price|trade|trading)?\s*(prediction|forecast|signal|trade call|long/short)\b",
    re.IGNORECASE,
)


class PolicyTriage:
    def __init__(self, decided_at: str | Callable[[], str] | None = None):
        self._decided_at = decided_at

    def _timestamp(self) -> str:
        if isinstance(self._decided_at, str):
            return self._decided_at
        if callable(self._decided_at):
            return self._decided_at()
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _text(entry: CatalogEntry) -> str:
        return " ".join((entry.canonical_name, entry.description, entry.endpoint_or_tool_url))

    @staticmethod
    def _is_mcp(entry: CatalogEntry) -> bool:
        text = f"{entry.canonical_name} {entry.description}".casefold()
        return "mcp" in text and any(marker in text for marker in ("server", "tool", "capability", "agent"))

    def classify_source(self, entry: CatalogEntry) -> SourceClass:
        parsed = urlsplit(entry.endpoint_or_tool_url)
        host = (parsed.hostname or "").casefold()

        if entry.catalog_id == "ai-agent-tools":
            if self._is_mcp(entry) and host == "github.com":
                return SourceClass.MCP_CAPABILITY
            return SourceClass.AI_TOOL

        if host == "apify.com" or host.endswith(".apify.com"):
            if self._is_mcp(entry):
                return SourceClass.MCP_CAPABILITY
            return SourceClass.SCRAPER_ACTOR

        if host == "github.com" and self._is_mcp(entry):
            return SourceClass.MCP_CAPABILITY

        return SourceClass.UNKNOWN

    def evaluate(self, entry: CatalogEntry) -> PolicyDecision:
        text = self._text(entry)
        if any(pattern.search(text) for pattern in _CIRCUMVENTION):
            state = PolicyState.REJECTED
            reason = "EXPLICIT_ACCESS_CONTROL_CIRCUMVENTION"
        elif _CREDENTIAL_THEFT.search(text):
            state = PolicyState.REJECTED
            reason = "EXPLICIT_CREDENTIAL_THEFT"
        elif _MALWARE.search(text):
            state = PolicyState.REJECTED
            reason = "EXPLICIT_MALWARE_OR_SPYWARE"
        else:
            state = PolicyState.REVIEW_REQUIRED
            reason = "UNVERIFIED_CATALOG_METADATA"

        return PolicyDecision(
            entry_id=entry.entry_id,
            policy_state=state,
            reason_code=reason,
            decided_at=self._timestamp(),
            details={
                "source_class": self.classify_source(entry).value,
                "automatic_triage": True,
            },
        )

    def candidate_defaults(self, entry: CatalogEntry, *, catalog_id: str) -> dict[str, object]:
        decision = self.evaluate(entry)
        text = f"{entry.canonical_name} {entry.description}".casefold()
        capability_only = catalog_id == "ai-agent-tools"
        source_class = self.classify_source(entry)
        challenger_only = bool(_OPAQUE_PREDICTION.search(text)) and any(
            marker in text for marker in ("long", "short", "trade", "signal", "confidence", "prediction", "forecast")
        )
        return {
            "source_class": source_class,
            "capability_only": capability_only,
            "challenger_only": challenger_only,
            "policy_state": decision.policy_state,
        }


__all__ = ["PolicyTriage"]
