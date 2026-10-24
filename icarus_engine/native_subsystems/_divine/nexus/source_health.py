from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Deque

from .contracts import BarEvent, VectorEvent

MarketEvent = BarEvent | VectorEvent


@dataclass(frozen=True, slots=True)
class SourceSLOPolicy:
    """Observable-source service objectives.

    ``None`` disables a dimension. NEXUS evaluates only evidence it actually has;
    it never invents an availability or receive timestamp to make an SLO calculable.
    Timing-integrity limits default to zero so impossible clock relationships fail
    closed once a policy is attached to a stream.
    """

    max_receive_lag_ns_p95: int | None = None
    max_gap_size: int | None = 0
    max_reconnect_epochs: int | None = None
    max_revision_rate: float | None = None
    max_clock_uncertainty_ns: int | None = None
    max_out_of_order_receipts: int | None = 0
    max_impossible_time_samples: int | None = 0
    max_sequence_nonmonotone: int | None = 0
    max_availability_violations: int | None = 0
    max_receipt_clock_violations: int | None = 0
    min_lag_samples: int = 1

    def __post_init__(self) -> None:
        if self.min_lag_samples < 0:
            raise ValueError("min_lag_samples must be non-negative")
        for name in (
            "max_receive_lag_ns_p95",
            "max_gap_size",
            "max_reconnect_epochs",
            "max_clock_uncertainty_ns",
            "max_out_of_order_receipts",
            "max_impossible_time_samples",
            "max_sequence_nonmonotone",
            "max_availability_violations",
            "max_receipt_clock_violations",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative or None")
        if self.max_revision_rate is not None and not (0.0 <= self.max_revision_rate <= 1.0):
            raise ValueError("max_revision_rate must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class SourceHealthSnapshot:
    stream_id: str
    samples: int
    connected: bool
    reconnect_epochs: int
    sequence_gap_runs: int
    missing_sequence_slots: int
    longest_gap: int
    sequence_nonmonotone_events: int
    revision_events: int
    revision_rate: float
    receive_lag_samples: int
    receive_lag_ns_latest: int | None
    receive_lag_ns_p95: int | None
    receive_lag_ns_max: int | None
    out_of_order_receipts: int
    receipt_before_available_samples: int
    availability_before_event_samples: int
    availability_violations: int
    receipt_clock_violations: int
    clock_uncertainty_ns_latest: int
    clock_uncertainty_ns_max: int
    last_event_ns: int | None
    last_available_ns: int | None
    last_received_ns: int | None
    latest_evidence_ns: int | None
    availability_unknown_samples: int
    slo_passed: bool | None
    slo_failures: tuple[str, ...]

    @property
    def impossible_time_samples(self) -> int:
        return self.receipt_before_available_samples + self.availability_before_event_samples

    def to_dict(self) -> dict:
        row = asdict(self)
        row["impossible_time_samples"] = self.impossible_time_samples
        return row


class SourceHealthTracker:
    """Incremental source-health telemetry using only observable timing evidence.

    ``received_ns`` is the local observation/receipt time. ``available_ns`` belongs
    to the event contract. Receive lag is admitted only when both exist and
    ``received_ns >= available_ns``. Contradictory time evidence is counted and is
    never converted into a harmless zero-lag sample.
    """

    _ATTESTED_BASES = {"verified_bar_close", "reviewed_event_completion", "attested_release"}

    def __init__(self, stream_id: str, *, lag_window: int = 512) -> None:
        if not stream_id:
            raise ValueError("stream_id is required")
        if lag_window <= 0:
            raise ValueError("lag_window must be positive")
        self.stream_id = stream_id
        self._lags: Deque[int] = deque(maxlen=int(lag_window))
        self._samples = 0
        self._connected = True
        self._reconnect_epochs = 0
        self._last_sequence: int | None = None
        self._last_revision: int | None = None
        self._gap_runs = 0
        self._missing_slots = 0
        self._longest_gap = 0
        self._sequence_nonmonotone = 0
        self._revision_events = 0
        self._last_lag: int | None = None
        self._out_of_order_receipts = 0
        self._receipt_before_available = 0
        self._availability_before_event = 0
        self._availability_violations = 0
        self._receipt_clock_violations = 0
        self._last_clock_uncertainty_ns = 0
        self._max_clock_uncertainty_ns = 0
        self._last_event_ns: int | None = None
        self._last_available_ns: int | None = None
        self._last_received_ns: int | None = None
        self._latest_evidence_ns: int | None = None
        self._availability_unknown = 0

    def set_connected(self, connected: bool) -> None:
        connected = bool(connected)
        if connected and not self._connected:
            self._reconnect_epochs += 1
        self._connected = connected

    def observe(
        self,
        event: MarketEvent,
        *,
        received_ns: int | None = None,
        clock_uncertainty_ns: int = 0,
        connected: bool | None = None,
    ) -> None:
        if event.stream_id != self.stream_id:
            raise ValueError(f"tracker is for {self.stream_id!r}, got {event.stream_id!r}")
        if clock_uncertainty_ns < 0:
            raise ValueError("clock_uncertainty_ns must be non-negative")
        if received_ns is not None and received_ns < 0:
            raise ValueError("received_ns must be non-negative")
        if connected is not None:
            self.set_connected(connected)

        prior_received = self._last_received_ns
        self._samples += 1
        self._last_event_ns = int(event.event_ns)
        self._last_available_ns = None if event.available_ns is None else int(event.available_ns)
        if received_ns is not None:
            self._last_received_ns = int(received_ns)
        evidence_candidates=[int(event.event_ns)]
        if event.available_ns is not None:
            evidence_candidates.append(int(event.available_ns))
        if received_ns is not None:
            evidence_candidates.append(int(received_ns))
        observed=max(evidence_candidates)
        self._latest_evidence_ns = (
            observed if self._latest_evidence_ns is None
            else max(self._latest_evidence_ns, observed)
        )
        self._last_clock_uncertainty_ns = int(clock_uncertainty_ns)
        self._max_clock_uncertainty_ns = max(self._max_clock_uncertainty_ns, int(clock_uncertainty_ns))

        if prior_received is not None and received_ns is not None and int(received_ns) < prior_received:
            self._out_of_order_receipts += 1

        sequence = int(event.source_sequence)
        revision = int(event.revision)
        if self._last_sequence is not None:
            if sequence > self._last_sequence + 1:
                gap = sequence - self._last_sequence - 1
                self._gap_runs += 1
                self._missing_slots += gap
                self._longest_gap = max(self._longest_gap, gap)
            elif sequence < self._last_sequence:
                self._sequence_nonmonotone += 1
            elif sequence == self._last_sequence and self._last_revision is not None and revision <= self._last_revision:
                # A same-sequence event is valid only when it is a strictly newer revision.
                self._sequence_nonmonotone += 1
        self._last_sequence = sequence
        self._last_revision = revision

        if revision > 0:
            self._revision_events += 1

        if event.available_ns is None:
            self._availability_unknown += 1
            self._last_lag = None
            return

        available_ns = int(event.available_ns)
        if available_ns < int(event.event_ns):
            self._availability_before_event += 1
            if event.availability_basis in self._ATTESTED_BASES:
                self._availability_violations += 1

        if received_ns is None:
            self._last_lag = None
            return

        received = int(received_ns)
        if received < available_ns:
            self._receipt_before_available += 1
            if event.availability_basis in self._ATTESTED_BASES:
                self._receipt_clock_violations += 1
            self._last_lag = None
            return

        lag = received - available_ns
        self._lags.append(lag)
        self._last_lag = lag

    @staticmethod
    def _p95(values: Deque[int]) -> int | None:
        if not values:
            return None
        xs = sorted(values)
        # Deterministic nearest-rank p95; no interpolation dependency.
        rank = max(1, (95 * len(xs) + 99) // 100)
        return int(xs[min(len(xs) - 1, rank - 1)])

    def snapshot(self, policy: SourceSLOPolicy | None = None) -> SourceHealthSnapshot:
        p95 = self._p95(self._lags)
        max_lag = max(self._lags) if self._lags else None
        revision_rate = self._revision_events / self._samples if self._samples else 0.0
        failures: list[str] = []
        slo_passed: bool | None = None

        if policy is not None:
            if policy.max_receive_lag_ns_p95 is not None:
                if len(self._lags) < policy.min_lag_samples:
                    failures.append("receive_lag_insufficient_evidence")
                elif p95 is not None and p95 > policy.max_receive_lag_ns_p95:
                    failures.append("receive_lag_p95")
            if policy.max_gap_size is not None and self._longest_gap > policy.max_gap_size:
                failures.append("sequence_gap")
            if policy.max_reconnect_epochs is not None and self._reconnect_epochs > policy.max_reconnect_epochs:
                failures.append("reconnect_epochs")
            if policy.max_revision_rate is not None and revision_rate > policy.max_revision_rate:
                failures.append("revision_rate")
            if policy.max_clock_uncertainty_ns is not None and self._max_clock_uncertainty_ns > policy.max_clock_uncertainty_ns:
                failures.append("clock_uncertainty")
            if policy.max_out_of_order_receipts is not None and self._out_of_order_receipts > policy.max_out_of_order_receipts:
                failures.append("out_of_order_receipts")
            impossible = self._receipt_before_available + self._availability_before_event
            if policy.max_impossible_time_samples is not None and impossible > policy.max_impossible_time_samples:
                failures.append("impossible_time_evidence")
            if policy.max_sequence_nonmonotone is not None and self._sequence_nonmonotone > policy.max_sequence_nonmonotone:
                failures.append("sequence_nonmonotone")
            if policy.max_availability_violations is not None and self._availability_violations > policy.max_availability_violations:
                failures.append("availability_violation")
            if policy.max_receipt_clock_violations is not None and self._receipt_clock_violations > policy.max_receipt_clock_violations:
                failures.append("receipt_clock_violation")
            slo_passed = not failures

        return SourceHealthSnapshot(
            stream_id=self.stream_id,
            samples=self._samples,
            connected=self._connected,
            reconnect_epochs=self._reconnect_epochs,
            sequence_gap_runs=self._gap_runs,
            missing_sequence_slots=self._missing_slots,
            longest_gap=self._longest_gap,
            sequence_nonmonotone_events=self._sequence_nonmonotone,
            revision_events=self._revision_events,
            revision_rate=revision_rate,
            receive_lag_samples=len(self._lags),
            receive_lag_ns_latest=self._last_lag,
            receive_lag_ns_p95=p95,
            receive_lag_ns_max=max_lag,
            out_of_order_receipts=self._out_of_order_receipts,
            receipt_before_available_samples=self._receipt_before_available,
            availability_before_event_samples=self._availability_before_event,
            availability_violations=self._availability_violations,
            receipt_clock_violations=self._receipt_clock_violations,
            clock_uncertainty_ns_latest=self._last_clock_uncertainty_ns,
            clock_uncertainty_ns_max=self._max_clock_uncertainty_ns,
            last_event_ns=self._last_event_ns,
            last_available_ns=self._last_available_ns,
            last_received_ns=self._last_received_ns,
            latest_evidence_ns=self._latest_evidence_ns,
            availability_unknown_samples=self._availability_unknown,
            slo_passed=slo_passed,
            slo_failures=tuple(failures),
        )


@dataclass(frozen=True, slots=True)
class SourceHealthPlane:
    """Deterministic fleet-level view of source health at one decision instant."""

    decision_ns: int
    stream_count: int
    configured_slo_streams: tuple[str, ...]
    healthy_streams: tuple[str, ...]
    failed_streams: tuple[str, ...]
    unknown_slo_streams: tuple[str, ...]
    healthy_fraction: float | None
    snapshots: dict[str, dict]
    plane_hash: str

    def to_dict(self) -> dict:
        return {
            "decision_ns": self.decision_ns,
            "stream_count": self.stream_count,
            "configured_slo_streams": list(self.configured_slo_streams),
            "healthy_streams": list(self.healthy_streams),
            "failed_streams": list(self.failed_streams),
            "unknown_slo_streams": list(self.unknown_slo_streams),
            "healthy_fraction": self.healthy_fraction,
            "snapshots": self.snapshots,
            "plane_hash": self.plane_hash,
        }

    @classmethod
    def from_dict(cls, row: dict) -> "SourceHealthPlane":
        required = {
            "decision_ns", "stream_count", "configured_slo_streams",
            "healthy_streams", "failed_streams", "unknown_slo_streams",
            "healthy_fraction", "snapshots", "plane_hash",
        }
        missing = required - set(row)
        if missing:
            raise ValueError(f"source-health plane mapping missing fields: {sorted(missing)}")
        if not isinstance(row["snapshots"], dict):
            raise ValueError("source-health snapshots must be a mapping")
        return cls(
            decision_ns=int(row["decision_ns"]),
            stream_count=int(row["stream_count"]),
            configured_slo_streams=tuple(str(x) for x in row["configured_slo_streams"]),
            healthy_streams=tuple(str(x) for x in row["healthy_streams"]),
            failed_streams=tuple(str(x) for x in row["failed_streams"]),
            unknown_slo_streams=tuple(str(x) for x in row["unknown_slo_streams"]),
            healthy_fraction=None if row["healthy_fraction"] is None else float(row["healthy_fraction"]),
            snapshots=dict(row["snapshots"]),
            plane_hash=str(row["plane_hash"]),
        )

    def verify(self) -> bool:
        if type(self.decision_ns) is not int or self.decision_ns < 0 or self.stream_count < 0:
            return False
        if len(self.plane_hash) != 64:
            return False
        try:
            int(self.plane_hash, 16)
        except ValueError:
            return False

        healthy = tuple(sorted(set(self.healthy_streams)))
        failed = tuple(sorted(set(self.failed_streams)))
        unknown = tuple(sorted(set(self.unknown_slo_streams)))
        if healthy != self.healthy_streams or failed != self.failed_streams or unknown != self.unknown_slo_streams:
            return False
        if set(healthy) & set(failed) or set(healthy) & set(unknown) or set(failed) & set(unknown):
            return False

        configured = tuple(sorted(set(healthy + failed)))
        if configured != self.configured_slo_streams:
            return False
        all_ids = set(configured) | set(unknown)
        if self.stream_count != len(self.snapshots) or all_ids != set(self.snapshots):
            return False

        for sid, snap in self.snapshots.items():
            if not isinstance(snap, dict) or str(snap.get("stream_id")) != sid:
                return False
            state = snap.get("slo_passed")
            if sid in healthy and state is not True:
                return False
            if sid in failed and state is not False:
                return False
            if sid in unknown and state is not None:
                return False

        expected_fraction = len(healthy) / len(configured) if configured else None
        if expected_fraction is None:
            if self.healthy_fraction is not None:
                return False
        elif self.healthy_fraction is None or abs(float(self.healthy_fraction) - expected_fraction) > 1e-12:
            return False

        payload = {
            "decision_ns": self.decision_ns,
            "stream_count": self.stream_count,
            "configured_slo_streams": list(self.configured_slo_streams),
            "healthy_streams": list(self.healthy_streams),
            "failed_streams": list(self.failed_streams),
            "unknown_slo_streams": list(self.unknown_slo_streams),
            "healthy_fraction": self.healthy_fraction,
            "snapshots": self.snapshots,
        }
        try:
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        except (TypeError, ValueError):
            return False
        digest = hashlib.sha256(raw).hexdigest()
        return digest == self.plane_hash


class SourceHealthRegistry:
    """Canonical fleet registry for source trackers and reviewed SLO policies.

    Streams without an attached SLO are surfaced as ``unknown_slo_streams`` and do
    not affect the configured healthy fraction. This prevents a made-up global SLO
    from being applied to heterogeneous historical or live sources.
    """

    def __init__(self, *, lag_window: int = 512) -> None:
        if lag_window <= 0:
            raise ValueError("lag_window must be positive")
        self._lag_window = int(lag_window)
        self._trackers: dict[str, SourceHealthTracker] = {}
        self._policies: dict[str, SourceSLOPolicy] = {}

    def tracker(self, stream_id: str) -> SourceHealthTracker:
        if not stream_id:
            raise ValueError("stream_id is required")
        tracker = self._trackers.get(stream_id)
        if tracker is None:
            tracker = SourceHealthTracker(stream_id, lag_window=self._lag_window)
            self._trackers[stream_id] = tracker
        return tracker

    def set_policy(self, stream_id: str, policy: SourceSLOPolicy) -> None:
        if not stream_id:
            raise ValueError("stream_id is required")
        if not isinstance(policy, SourceSLOPolicy):
            raise TypeError("policy must be SourceSLOPolicy")
        old=self._policies.get(stream_id)
        if old is not None and old != policy:
            raise ValueError(
                f"source SLO policy conflict for {stream_id}; clear/version the policy explicitly"
            )
        self._policies[stream_id] = policy
        self.tracker(stream_id)

    def clear_policy(self, stream_id: str) -> None:
        self._policies.pop(stream_id, None)

    def observe(self, event: MarketEvent, **kwargs) -> None:
        self.tracker(event.stream_id).observe(event, **kwargs)

    def set_connected(self, stream_id: str, connected: bool) -> None:
        self.tracker(stream_id).set_connected(connected)

    def snapshot(self, decision_ns: int) -> SourceHealthPlane:
        if type(decision_ns) is not int or decision_ns < 0:
            raise ValueError("decision_ns must be a non-negative integer")

        healthy: list[str] = []
        failed: list[str] = []
        unknown: list[str] = []
        rows: dict[str, dict] = {}
        for stream_id in sorted(self._trackers):
            policy = self._policies.get(stream_id)
            snap = self._trackers[stream_id].snapshot(policy)
            evidence_ns = snap.latest_evidence_ns
            if evidence_ns is not None and int(evidence_ns) > int(decision_ns):
                raise ValueError(
                    f"cannot build source-health plane at {decision_ns} from "
                    f"{stream_id} evidence observed at {evidence_ns}"
                )
            rows[stream_id] = snap.to_dict()
            if policy is None:
                unknown.append(stream_id)
            elif snap.slo_passed:
                healthy.append(stream_id)
            else:
                failed.append(stream_id)

        configured = tuple(sorted(healthy + failed))
        fraction = len(healthy) / len(configured) if configured else None
        payload = {
            "decision_ns": int(decision_ns),
            "stream_count": len(rows),
            "configured_slo_streams": list(configured),
            "healthy_streams": healthy,
            "failed_streams": failed,
            "unknown_slo_streams": unknown,
            "healthy_fraction": fraction,
            "snapshots": rows,
        }
        plane_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        return SourceHealthPlane(
            decision_ns=int(decision_ns),
            stream_count=len(rows),
            configured_slo_streams=configured,
            healthy_streams=tuple(healthy),
            failed_streams=tuple(failed),
            unknown_slo_streams=tuple(unknown),
            healthy_fraction=fraction,
            snapshots=rows,
            plane_hash=plane_hash,
        )
