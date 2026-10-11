"""Deterministic structural ancestry, without deleting or qualifying observations."""
from __future__ import annotations

import hashlib
from typing import Iterable
from urllib.parse import urlsplit

from .contracts import Candidate, DuplicateGroup
from .normalize import normalize_name, normalize_url


_LEVELS = ("EXACT_IDENTITY_URL", "PROVIDER_CAPABILITY", "DOMAIN_PATH", "NORMALIZED_NAME_DOMAIN")


def duplicate_keys(candidate: Candidate) -> tuple[tuple[str, str], ...]:
    normalized = normalize_url(candidate.endpoint_or_tool_url)
    parsed = urlsplit(normalized.identity_url)
    # Non-default ports and meaningful query parameters identify different services.
    host = parsed.netloc
    keys = [("EXACT_IDENTITY_URL", normalized.identity_url)]
    if candidate.provider_name and candidate.capability_kind:
        keys.append(("PROVIDER_CAPABILITY", "\0".join((
            host, normalize_name(candidate.provider_name).casefold(),
            normalize_name(candidate.capability_kind).casefold(), parsed.query,
        ))))
    keys.append(("DOMAIN_PATH", "\0".join((host, parsed.path, parsed.query))))
    keys.append(("NORMALIZED_NAME_DOMAIN", "\0".join((
        host, normalize_name(candidate.canonical_name).casefold(), parsed.query,
    ))))
    return tuple(keys)


class DuplicateResolver:
    def resolve(self, candidates: Iterable[Candidate]) -> tuple[DuplicateGroup, ...]:
        by_id: dict[str, Candidate] = {}
        for candidate in candidates:
            old = by_id.get(candidate.candidate_id)
            if old is not None and old != candidate:
                raise ValueError("candidate identity conflict in duplicate resolution")
            by_id[candidate.candidate_id] = candidate
        parent = {key: key for key in by_id}

        def find(key: str) -> str:
            while parent[key] != key:
                parent[key] = parent[parent[key]]
                key = parent[key]
            return key

        matches: dict[tuple[str, str], list[str]] = {}
        for candidate_id in sorted(by_id):
            for key in duplicate_keys(by_id[candidate_id]):
                members = matches.setdefault(key, [])
                if members:
                    a, b = find(members[0]), find(candidate_id)
                    parent[max(a, b)] = min(a, b)
                members.append(candidate_id)

        components: dict[str, list[str]] = {}
        for candidate_id in sorted(by_id):
            components.setdefault(find(candidate_id), []).append(candidate_id)
        result = []
        ranks = {level: i for i, level in enumerate(_LEVELS)}
        for member_ids in components.values():
            if len(member_ids) < 2:
                continue
            member_set = set(member_ids)
            supporting = [(key, ids) for key, ids in matches.items()
                          if len(ids) > 1 and set(ids) <= member_set]
            # Describe the weakest structural edge needed for this transitive family.
            level = max((key[0] for key, _ in supporting), key=ranks.get)
            # When every member shares an exact URL, retain the strongest evidence.
            common = [key for key, ids in supporting if set(ids) == member_set]
            if common:
                level = min((key[0] for key in common), key=ranks.get)
            evidence_keys = sorted(key[1] for key, _ in supporting if key[0] == level)
            group_id = hashlib.sha256("\0".join((level, *member_ids)).encode()).hexdigest()
            result.append(DuplicateGroup(
                group_id=group_id, member_ids=tuple(member_ids), evidence_level=level,
                evidence_key="\n".join(evidence_keys),
                catalog_refs=tuple(sorted({ref for member in member_ids
                                           for ref in by_id[member].upstream_catalog_refs})),
            ))
        return tuple(sorted(result, key=lambda group: group.group_id))


__all__ = ["DuplicateResolver", "duplicate_keys"]
