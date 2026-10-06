from __future__ import annotations

from typing import Any, Protocol

from .contracts import ProviderDescriptor


class ProviderRegistryCollision(ValueError):
    """Raised when two adapters claim the same canonical provider ID."""


class ProviderAdapter(Protocol):
    descriptor: ProviderDescriptor

    def collect(self, ctx: Any):
        ...

    def normalize(self, batch: Any, ctx: Any):
        ...


class ProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ProviderAdapter] = {}

    def register(self, adapter: ProviderAdapter) -> None:
        descriptor = getattr(adapter, "descriptor", None)
        if not isinstance(descriptor, ProviderDescriptor):
            raise TypeError("provider adapter must expose a ProviderDescriptor as descriptor")
        provider_id = descriptor.provider_id
        if provider_id in self._adapters:
            raise ProviderRegistryCollision(f"provider_id already registered: {provider_id}")
        self._adapters[provider_id] = adapter

    def get(self, provider_id: str) -> ProviderAdapter:
        try:
            return self._adapters[provider_id]
        except KeyError as exc:
            raise KeyError(f"unknown external-data provider: {provider_id}") from exc

    def provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(self._adapters[provider_id].descriptor for provider_id in self.provider_ids())

    def capabilities(self) -> dict[str, tuple[str, ...]]:
        return {
            provider_id: tuple(self._adapters[provider_id].descriptor.capabilities)
            for provider_id in self.provider_ids()
        }
