"""Read-only projection from AdvisoryLedger evidence into world-state observations."""
from __future__ import annotations

from icarus_engine.advisory import AdvisoryLedger
from icarus_engine.world_state import Observation

from .contracts import observation_from_event


def ledger_observations(ledger: AdvisoryLedger, asset: str, as_of: str) -> tuple[Observation, ...]:
    if not isinstance(ledger, AdvisoryLedger):
        raise TypeError("ledger must be AdvisoryLedger")
    observations = []
    for event in ledger.events_as_of(asset, as_of):
        if event.get("event_type") != "world_state":
            continue
        for variable in sorted(event["values"]):
            observations.append(observation_from_event(event, variable))
    observations.sort(key=lambda row: (row.available_at, row.entity, row.variable, row.source, row.id))
    return tuple(observations)
