"""ICARUS Ψ latent-pressure + market-possibility research engine.

This module is deliberately fail-closed:
- it never grants production decision or execution authority;
- unavailable evidence remains unavailable instead of being imputed bullish/bearish;
- scenario outputs are model diagnostics, not calibrated market probabilities.

The ICARUS Ψ engine combines:
1. Latent-pressure components (microstructure, cross-asset, external force inputs),
2. pressure/price elasticity and absorption/vacuum inference,
3. dynamic lagged causal-leader scoring,
4. synthetic/counterfactual price displacement,
5. deterministic constraint-aware future-space simulation,
6. normalized future entropy / future-space collapse,
7. phase-boundary and event-horizon diagnostics,
8. forced-consensus detection,
9. market-shadow force removal,
10. a strict NO_EDGE state when coverage or agreement is insufficient.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import statistics
import threading
import time
from typing import Any, Deque, Iterable, Mapping, Sequence

from .psi_evidence import PsiEvidenceLedger

SCHEMA_VERSION = "icarus-possibility-v1"
DEFAULT_SCENARIOS = 768
DEFAULT_HISTORY = 720

_EXTERNAL_KEYS = (
    "gamma_pressure",
    "basis_pressure",
    "cta_pressure",
    "liquidation_pressure",
    "rebalance_pressure",
)

_COMPONENT_WEIGHTS = {
    "queue_pressure": 1.10,
    "repricing_pressure": 0.85,
    "volume_pressure": 1.00,
    "cross_asset_pressure": 1.00,
    "basis_pressure": 0.80,
    "gamma_pressure": 0.95,
    "forced_flow_pressure": 0.90,
}


@dataclass(frozen=True)
class Feature:
    value: float | None
    confidence: float
    available: bool
    source: str
    detail: str = ""

    def json(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "available": self.available,
            "source": self.source,
            "detail": self.detail,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _observed_time(value: Any, field: str = "observed_at") -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError(f"{field} must be an RFC3339 timestamp") from ex
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include an explicit timezone")
    parsed = parsed.astimezone(timezone.utc)
    if parsed.timestamp() > time.time() + 5.0:
        raise ValueError(f"{field} cannot be in the future")
    return parsed.isoformat().replace("+00:00", "Z")


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _mean(values: Iterable[float]) -> float:
    xs = list(values)
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    try:
        return statistics.pstdev(values)
    except statistics.StatisticsError:
        return 0.0


def _corr(a: Sequence[float], b: Sequence[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 5:
        return None
    x, y = list(a[-n:]), list(b[-n:])
    mx, my = _mean(x), _mean(y)
    vx = sum((v - mx) ** 2 for v in x)
    vy = sum((v - my) ** 2 for v in y)
    if vx <= 1e-18 or vy <= 1e-18:
        return None
    cov = sum((u - mx) * (v - my) for u, v in zip(x, y))
    return _clamp(cov / math.sqrt(vx * vy))


def _radical_inverse(index: int, base: int) -> float:
    value = 0.0
    factor = 1.0 / base
    i = max(1, int(index))
    while i:
        i, digit = divmod(i, base)
        value += digit * factor
        factor /= base
    return value


def _normalish(index: int, base_a: int, base_b: int) -> float:
    # Deterministic low-discrepancy approximately normal shock.
    u1 = max(1e-9, _radical_inverse(index, base_a))
    u2 = _radical_inverse(index, base_b)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _weighted(features: Mapping[str, Feature], weights: Mapping[str, float]) -> tuple[float | None, float]:
    numerator = 0.0
    denominator = 0.0
    available_weight = 0.0
    total_weight = sum(abs(weights.get(k, 0.0)) for k in weights)
    for name, weight in weights.items():
        feature = features.get(name)
        if not feature or not feature.available or feature.value is None:
            continue
        effective = abs(weight) * _clamp(feature.confidence, 0.0, 1.0)
        numerator += feature.value * weight * _clamp(feature.confidence, 0.0, 1.0)
        denominator += effective
        available_weight += effective
    if denominator <= 1e-12:
        return None, 0.0
    coverage = available_weight / total_weight if total_weight else 0.0
    return _clamp(numerator / denominator), _clamp(coverage, 0.0, 1.0)


class PossibilityEngine:
    """Stateful read-only research engine attached to one Portfolio."""

    def __init__(
        self,
        port: Any,
        *,
        history: int = DEFAULT_HISTORY,
        scenarios: int = DEFAULT_SCENARIOS,
        micro_cache_seconds: float = 1.5,
    ):
        self.port = port
        self.history = max(64, int(history))
        self.scenarios = max(96, min(4096, int(scenarios)))
        self.micro_cache_seconds = max(0.25, float(micro_cache_seconds))
        self._lock = threading.RLock()
        self._history: dict[str, Deque[dict[str, float]]] = defaultdict(lambda: deque(maxlen=self.history))
        self._external: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self._micro_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._evidence_ledger = PsiEvidenceLedger(getattr(port, "base_dir", None))

    # ---------- public API ----------

    def ingest_external(
        self,
        asset: str,
        values: Mapping[str, Any],
        *,
        source: str,
        observed_at: str | None = None,
        ttl_seconds: float = 300.0,
    ) -> dict[str, Any]:
        """Persist provenance-labelled optional force evidence.

        Causal receipt rules remain fail-closed: evidence cannot arrive from the
        future, cannot already be stale for its requested TTL, and malformed values
        are rejected before any receipt is written. Exact durable receipts are
        idempotent.
        """
        asset = str(asset or "").strip().upper()
        if not asset:
            raise ValueError("asset is required")
        source = str(source or "").strip()
        if not source:
            raise ValueError("source is required")
        if len(source) > 180:
            raise ValueError("source exceeds 180 characters")
        if not isinstance(values, Mapping) or not values:
            raise ValueError("values must be a non-empty object")
        ttl_value = _finite(ttl_seconds)
        if ttl_value is None or ttl_value <= 0:
            raise ValueError("ttl_seconds must be finite and positive")
        ttl = min(ttl_value, 86400.0)
        now = time.time()
        observed = _utc_now() if observed_at is None else _observed_time(observed_at)
        observed_ts = datetime.fromisoformat(observed.replace("Z", "+00:00")).timestamp()
        expires_ts = observed_ts + ttl
        if expires_ts <= now:
            raise ValueError("external evidence is already stale at receipt for the requested ttl_seconds")

        normalized: list[dict[str, Any]] = []
        for key, raw in values.items():
            if key not in _EXTERNAL_KEYS:
                raise ValueError(f"unsupported external feature: {key}")
            if isinstance(raw, Mapping):
                value = _finite(raw.get("value"))
                if "confidence" in raw:
                    confidence = _finite(raw.get("confidence"))
                    if confidence is None or not 0.0 <= confidence <= 1.0:
                        raise ValueError(f"{key}.confidence must be finite and within [0,1]")
                else:
                    confidence = 1.0
            else:
                value = _finite(raw)
                confidence = 1.0
            if value is None or not -1.0 <= value <= 1.0:
                raise ValueError(f"{key} must be finite and within [-1,1]")
            normalized.append({
                "asset": asset,
                "feature": key,
                "value": float(value),
                "confidence": float(confidence),
                "source": source,
                "observed_at": observed,
                "observed_ts": observed_ts,
                "received_ts": now,
                "expires_ts": expires_ts,
                "ttl_seconds": ttl,
                "created_at": _utc_now(),
            })

        stored: dict[str, Any] = {}
        inserted = 0
        with self._lock:
            for row in normalized:
                receipt = self._evidence_ledger.record(row)
                inserted += int(bool(receipt.get("inserted")))
                self._external[asset][row["feature"]] = dict(receipt)
                stored[row["feature"]] = dict(receipt)

        return {
            "ok": True,
            "asset": asset,
            "stored": stored,
            "inserted": inserted,
            "idempotent_duplicates": len(normalized) - inserted,
            "durable": self._evidence_ledger.durable,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def evidence_snapshot(
        self,
        asset: str | None = None,
        *,
        limit: int = 100,
        include_expired: bool = False,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        """Read append-only evidence history and deterministic causal as-of state."""
        symbol = str(asset or "").strip().upper()
        as_of_text = _utc_now() if as_of is None else _observed_time(as_of, "as_of")
        as_of_ts = datetime.fromisoformat(as_of_text.replace("Z", "+00:00")).timestamp()
        return self._evidence_ledger.snapshot(
            symbol,
            as_of_ts=as_of_ts,
            as_of=as_of_text,
            limit=limit,
            include_expired=include_expired,
        )

    def snapshot(self, asset: str | None = None) -> dict[str, Any]:
        market = self.port.status()
        rows = [x for x in (market.get("assets") or []) if isinstance(x, Mapping)]
        if not rows:
            return self._empty("no running assets")
        self._record_market(rows)

        requested = str(asset or "").strip().upper()
        target = next((x for x in rows if str(x.get("symbol") or "").upper() == requested), None) if requested else None
        if target is None:
            target = next((x for x in rows if str(x.get("symbol") or "").upper() == "NQ"), rows[0])

        symbol = str(target.get("symbol") or "").upper()
        price = _finite(target.get("price"))
        if not symbol or price is None or price <= 0:
            return self._empty("selected asset has no finite price", symbol=symbol)

        micro = self._microstructure(symbol)
        leaders = self._dynamic_leaders(symbol)
        external = self._external_features(symbol)
        features = self._features(symbol, target, micro, leaders, external)
        latent, coverage = _weighted(features, _COMPONENT_WEIGHTS)
        history = list(self._history.get(symbol, ()))
        returns = [x["ret"] for x in history if "ret" in x]
        vol = max(_stdev(returns[-80:]), 1e-7)
        elasticity = self._elasticity(history, micro)
        hidden = self._hidden_state(latent, elasticity, micro, leaders)
        information_wave = self._information_wave(history, vol, latent, coverage, micro, leaders)
        synthetic = self._synthetic_price(price, vol, latent, features, leaders)
        futures = self._future_space(symbol, price, vol, latent, coverage, features, target)
        phase = self._phase_boundary(price, vol, latent, futures, features)
        consensus = self._forced_consensus(features)
        shadows = self._market_shadows(price, synthetic, features)
        edge = self._edge_gate(
            latent=latent,
            coverage=coverage,
            collapse=futures["future_space_collapse"],
            consensus=consensus,
            micro=micro,
            leaders=leaders,
        )

        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _utc_now(),
            "asset": symbol,
            "price": price,
            "authority": {
                "research_authorized": True,
                "production_decision_authorized": False,
                "execution_authorized": False,
                "trade_signal_authorized": False,
            },
            "truth_contract": {
                "scenario_probabilities_calibrated": False,
                "causality_proven": False,
                "missing_evidence_imputed": False,
                "confidence_weighted_coverage": True,
                "consensus_requires_distinct_evidence_domains": True,
                "same_snapshot_unexplained_residual_not_identifiable": True,
                "external_ttl_anchored_to_observation_time": True,
                "rule": "Model diagnostics only. Missing evidence stays unavailable and NO_EDGE is mandatory when gates fail.",
            },
            "latent_pressure_engine": {
                "latent_pressure": latent,
                "latent_pressure_score": None if latent is None else round(latent * 100.0, 2),
                "evidence_coverage": round(coverage, 4),
                "components": {k: v.json() for k, v in features.items()},
                "pressure_price_elasticity": elasticity,
                "hidden_state": hidden,
            },
            "information_wave": information_wave,
            "causal_leadership": leaders,
            "counterfactual": synthetic,
            "possibility": futures,
            "phase_transition": phase,
            "forced_consensus": consensus,
            "market_shadows": shadows,
            "edge_state": edge,
            "data_health": {
                "market_history_observations": len(history),
                "microstructure": micro.get("health", {}),
                "evidence_ledger": self._evidence_ledger.health(symbol),
                "external_features": {
                    key: {
                        "available": feature.available,
                        "source": feature.source,
                        "confidence": feature.confidence,
                    }
                    for key, feature in external.items()
                },
            },
        }

    def parallax_vote(self, asset: str | None) -> dict[str, Any]:
        """Return a bounded research vote for PARALLAX decision context.

        PARALLAX gets an explicit unavailable vote rather than a fabricated neutral
        value if Ψ cannot observe enough evidence. The vote never grants execution
        or production-decision authority.
        """
        try:
            state = self.snapshot(asset)
        except Exception as ex:
            return {
                "subsystem": "psi",
                "status": "UNAVAILABLE",
                "state": "NO_EDGE",
                "confidence": 0.0,
                "reason": f"{type(ex).__name__}: {ex}",
                "execution_authorized": False,
                "production_decision_authorized": False,
            }
        edge = state.get("edge_state") if isinstance(state.get("edge_state"), Mapping) else {}
        latent_state = state.get("latent_pressure_engine") if isinstance(state.get("latent_pressure_engine"), Mapping) else {}
        possibility = state.get("possibility") if isinstance(state.get("possibility"), Mapping) else {}
        return {
            "subsystem": "psi",
            "status": "OBSERVED" if state.get("asset") else "UNAVAILABLE",
            "asset": state.get("asset"),
            "generated_at": state.get("generated_at"),
            "state": edge.get("state", "NO_EDGE"),
            "confidence": _finite(edge.get("confidence")) or 0.0,
            "latent_pressure": _finite(latent_state.get("latent_pressure")),
            "evidence_coverage": _finite(latent_state.get("evidence_coverage")) or 0.0,
            "future_space_collapse": _finite(possibility.get("future_space_collapse")),
            "dominant_cluster": possibility.get("dominant_cluster"),
            "blockers": list(edge.get("blockers") or [])[:16],
            "execution_authorized": False,
            "production_decision_authorized": False,
            "truth_contract": "research/shadow context for PARALLAX ablation; not an execution vote",
        }

    # ---------- evidence capture ----------

    def _record_market(self, rows: Sequence[Mapping[str, Any]]) -> None:
        now = time.time()
        with self._lock:
            for row in rows:
                symbol = str(row.get("symbol") or "").upper()
                price = _finite(row.get("price"))
                if not symbol or price is None or price <= 0:
                    continue
                q = self._history[symbol]
                prev = q[-1] if q else None
                if prev and now - prev["ts"] < 0.20:
                    continue
                ret = 0.0 if not prev or prev["price"] <= 0 else math.log(price / prev["price"])
                st = row.get("state") if isinstance(row.get("state"), Mapping) else {}
                pulse_l = _finite(st.get("pulse_l")) or 0.0
                pulse_s = _finite(st.get("pulse_s")) or 0.0
                regime = _finite(st.get("rate_regime")) or 0.0
                q.append({
                    "ts": now,
                    "price": price,
                    "ret": ret,
                    "pulse": _clamp(pulse_l - pulse_s),
                    "regime": _clamp(regime, 0.0, 1.0),
                })

    def _external_features(self, symbol: str) -> dict[str, Feature]:
        now = time.time()
        out: dict[str, Feature] = {}
        with self._lock:
            rows = self._evidence_ledger.active(symbol, as_of_ts=now)
            self._external[symbol] = {key: dict(value) for key, value in rows.items()}
            for key in _EXTERNAL_KEYS:
                row = rows.get(key)
                if not row:
                    out[key] = Feature(None, 0.0, False, "unavailable", "no provenance-labelled external evidence")
                else:
                    out[key] = Feature(
                        _finite(row.get("value")),
                        _finite(row.get("confidence")) or 0.0,
                        True,
                        str(row.get("source") or "external"),
                        f"observed {row.get('observed_at')} · receipt {row.get('evidence_id')}",
                    )
        return out

    def _microstructure(self, symbol: str) -> dict[str, Any]:
        now = time.time()
        cached = self._micro_cache.get(symbol)
        if cached and now - cached[0] <= self.micro_cache_seconds:
            return cached[1]

        result: dict[str, Any] = {
            "queue_pressure": Feature(None, 0.0, False, "unavailable"),
            "repricing_pressure": Feature(None, 0.0, False, "unavailable"),
            "volume_pressure": Feature(None, 0.0, False, "unavailable"),
            "aggressive_flow": None,
            "depth_mid": None,
            "spread": None,
            "health": {"provider": None, "ticks": False, "depth": False, "errors": []},
        }
        runner = getattr(self.port, "runners", {}).get(symbol)
        if runner is None:
            result["health"]["errors"].append("runner unavailable")
            self._micro_cache[symbol] = (now, result)
            return result
        feed = getattr(runner, "feed", None)
        ticker = getattr(getattr(runner, "spec", None), "ticker", symbol)
        result["health"]["provider"] = type(feed).__name__.lower() if feed is not None else None

        # Trades / aggressive-flow pressure.
        if feed is not None and hasattr(feed, "trades"):
            try:
                ticks = list(feed.trades(ticker, limit=500))
                signed = 0.0
                gross = 0.0
                prices: list[float] = []
                for tick in ticks:
                    px = _finite(getattr(tick, "price", None) if not isinstance(tick, Mapping) else tick.get("price"))
                    size = _finite(getattr(tick, "size", None) if not isinstance(tick, Mapping) else tick.get("size"))
                    side = str(getattr(tick, "side", "") if not isinstance(tick, Mapping) else tick.get("side", "")).strip().upper()
                    if px is not None:
                        prices.append(px)
                    if size is None or size <= 0:
                        continue
                    sign = 1.0 if side in {"B", "BUY", "BID"} else -1.0 if side in {"A", "S", "SELL", "ASK"} else 0.0
                    signed += sign * size
                    gross += abs(size)
                if gross > 0:
                    imbalance = _clamp(signed / gross)
                    confidence = _clamp(min(1.0, gross / 250.0) * min(1.0, len(ticks) / 120.0), 0.05, 1.0)
                    result["volume_pressure"] = Feature(imbalance, confidence, True, "live trade ticks", f"{len(ticks)} ticks")
                    result["aggressive_flow"] = {"imbalance": imbalance, "gross_size": gross, "tick_count": len(ticks)}
                    result["health"]["ticks"] = True
                if len(prices) >= 3:
                    first, last = prices[0], prices[-1]
                    displacement = (last - first) / max(abs(first), 1e-9)
                    result["trade_displacement"] = displacement
            except Exception as ex:
                result["health"]["errors"].append(f"ticks: {type(ex).__name__}: {ex}")

        # MBP-10 queue and quote repricing.
        if feed is not None and hasattr(feed, "depth_events"):
            try:
                events = list(feed.depth_events(ticker, schema="mbp-10", limit=120))
                snapshots = [e for e in events if isinstance(e, Mapping) and isinstance(e.get("levels"), list) and e.get("levels")]
                if snapshots:
                    latest = snapshots[-1]
                    levels = [x for x in latest["levels"] if isinstance(x, Mapping)]
                    bid_sz = sum(max(0.0, _finite(x.get("bid_sz")) or 0.0) for x in levels[:10])
                    ask_sz = sum(max(0.0, _finite(x.get("ask_sz")) or 0.0) for x in levels[:10])
                    total = bid_sz + ask_sz
                    if total > 0:
                        queue = _clamp((bid_sz - ask_sz) / total)
                        result["queue_pressure"] = Feature(queue, _clamp(total / 250.0, 0.10, 1.0), True, "Databento MBP-10", "top-10 aggregate size imbalance")
                    top = levels[0] if levels else {}
                    bid = _finite(top.get("bid_px"))
                    ask = _finite(top.get("ask_px"))
                    if bid is not None and ask is not None and ask >= bid:
                        mid = (bid + ask) / 2.0
                        result["depth_mid"] = mid
                        result["spread"] = ask - bid

                    mids: list[float] = []
                    for event in snapshots[-40:]:
                        lv = event.get("levels") or []
                        if not lv or not isinstance(lv[0], Mapping):
                            continue
                        b = _finite(lv[0].get("bid_px"))
                        a = _finite(lv[0].get("ask_px"))
                        if b is not None and a is not None and a >= b:
                            mids.append((a + b) / 2.0)
                    if len(mids) >= 4:
                        scale = max(abs(mids[0]), 1e-9)
                        move = (mids[-1] - mids[0]) / scale
                        local = _stdev([(mids[i] - mids[i - 1]) / scale for i in range(1, len(mids))])
                        denom = max(local * math.sqrt(max(1, len(mids) - 1)), 1e-7)
                        result["repricing_pressure"] = Feature(_clamp(move / (3.0 * denom)), _clamp(len(mids) / 30.0, 0.10, 1.0), True, "Databento MBP-10", "midquote repricing")
                    result["health"]["depth"] = True
                    result["health"]["depth_events"] = len(events)
            except Exception as ex:
                result["health"]["errors"].append(f"depth: {type(ex).__name__}: {ex}")

        self._micro_cache[symbol] = (now, result)
        return result

    # ---------- feature engines ----------

    def _dynamic_leaders(self, symbol: str) -> dict[str, Any]:
        target = list(self._history.get(symbol, ()))
        t_returns = [x["ret"] for x in target]
        if len(t_returns) < 8:
            return {"status": "warming", "leaders": [], "sample_count": len(t_returns)}
        vol = max(_stdev(t_returns[-80:]), 1e-7)
        rows = []
        with self._lock:
            peers = list(self._history.items())
        for peer, hist in peers:
            if peer == symbol:
                continue
            p = list(hist)
            n = min(len(target), len(p), 120)
            if n < 8:
                continue
            tr = [x["ret"] for x in target[-n:]]
            pr = [x["ret"] for x in p[-n:]]
            lead_corr = _corr(pr[:-1], tr[1:])
            contemporaneous = _corr(pr, tr)
            if lead_corr is None:
                continue
            latest_peer = pr[-1]
            directional = _clamp(lead_corr * latest_peer / max(vol * 2.0, 1e-7))
            rows.append({
                "asset": peer,
                "lag1_correlation": lead_corr,
                "contemporaneous_correlation": contemporaneous,
                "directional_pressure": directional,
                "lead_strength": abs(lead_corr) * min(1.0, n / 40.0),
                "samples": n - 1,
            })
        rows.sort(key=lambda x: (-x["lead_strength"], x["asset"]))
        leaders = rows[:8]
        if not leaders:
            return {"status": "warming", "leaders": [], "sample_count": len(t_returns)}
        total = sum(x["lead_strength"] for x in leaders) or 1.0
        pressure = sum(x["directional_pressure"] * x["lead_strength"] for x in leaders) / total
        confidence = _clamp(sum(x["lead_strength"] for x in leaders[:4]) / max(1.0, len(leaders[:4])), 0.0, 1.0)
        return {
            "status": "observed",
            "leaders": leaders,
            "pressure": _clamp(pressure),
            "confidence": confidence,
            "sample_count": len(t_returns),
            "interpretation": "Lagged association diagnostic; not proof of structural causality.",
        }

    def _features(
        self,
        symbol: str,
        market_row: Mapping[str, Any],
        micro: Mapping[str, Any],
        leaders: Mapping[str, Any],
        external: Mapping[str, Feature],
    ) -> dict[str, Feature]:
        out = {
            "queue_pressure": micro.get("queue_pressure") if isinstance(micro.get("queue_pressure"), Feature) else Feature(None, 0.0, False, "unavailable"),
            "repricing_pressure": micro.get("repricing_pressure") if isinstance(micro.get("repricing_pressure"), Feature) else Feature(None, 0.0, False, "unavailable"),
            "volume_pressure": micro.get("volume_pressure") if isinstance(micro.get("volume_pressure"), Feature) else Feature(None, 0.0, False, "unavailable"),
        }

        if leaders.get("status") == "observed" and _finite(leaders.get("pressure")) is not None:
            out["cross_asset_pressure"] = Feature(
                _finite(leaders.get("pressure")),
                _finite(leaders.get("confidence")) or 0.0,
                True,
                "lagged cross-asset graph",
                "dynamic lag-1 leader ensemble",
            )
        else:
            # Strategy pulse is deliberately a weak fallback, not a cross-asset substitute.
            out["cross_asset_pressure"] = Feature(None, 0.0, False, "unavailable", "leader graph warming")

        basis = external["basis_pressure"]
        gamma = external["gamma_pressure"]
        out["basis_pressure"] = basis
        out["gamma_pressure"] = gamma

        forced_parts = [
            external["cta_pressure"],
            external["liquidation_pressure"],
            external["rebalance_pressure"],
        ]
        avail = [x for x in forced_parts if x.available and x.value is not None]
        if avail:
            denom = sum(max(0.01, x.confidence) for x in avail)
            value = sum(float(x.value) * max(0.01, x.confidence) for x in avail) / denom
            out["forced_flow_pressure"] = Feature(_clamp(value), _clamp(denom / len(avail)), True, "external forced-flow evidence", f"{len(avail)}/3 force channels")
        else:
            out["forced_flow_pressure"] = Feature(None, 0.0, False, "unavailable", "CTA/liquidation/rebalance evidence absent")
        return out

    def _elasticity(self, history: Sequence[Mapping[str, float]], micro: Mapping[str, Any]) -> dict[str, Any]:
        flow = micro.get("aggressive_flow")
        displacement = _finite(micro.get("trade_displacement"))
        if not isinstance(flow, Mapping) or displacement is None:
            return {"available": False, "value": None, "state": "UNAVAILABLE", "detail": "requires live signed ticks and price displacement"}
        imbalance = _finite(flow.get("imbalance"))
        gross = _finite(flow.get("gross_size"))
        if imbalance is None or gross is None or gross <= 0:
            return {"available": False, "value": None, "state": "UNAVAILABLE", "detail": "insufficient signed flow"}
        signed_intensity = imbalance * math.log1p(gross)
        if abs(signed_intensity) < 1e-9:
            return {"available": True, "value": 0.0, "state": "BALANCED", "detail": "near-zero net aggressive flow"}
        elasticity = displacement / signed_intensity
        response = abs(displacement)
        flow_strength = abs(imbalance)
        if flow_strength >= 0.45 and response < 0.00015:
            state = "BUYER_ABSORPTION" if imbalance < 0 else "SELLER_ABSORPTION"
        elif flow_strength <= 0.25 and response > 0.00035:
            state = "OFFER_VACUUM" if displacement > 0 else "BID_VACUUM"
        else:
            state = "NORMAL_RESPONSE"
        return {
            "available": True,
            "value": elasticity,
            "state": state,
            "flow_imbalance": imbalance,
            "gross_size": gross,
            "price_displacement": displacement,
        }

    def _hidden_state(
        self,
        latent: float | None,
        elasticity: Mapping[str, Any],
        micro: Mapping[str, Any],
        leaders: Mapping[str, Any],
    ) -> dict[str, Any]:
        hypotheses: list[dict[str, Any]] = []
        state = str(elasticity.get("state") or "")
        if state in {"BUYER_ABSORPTION", "SELLER_ABSORPTION", "OFFER_VACUUM", "BID_VACUUM"}:
            hypotheses.append({"state": state, "strength": 0.80, "evidence": ["pressure/price elasticity"]})
        lp = _finite(latent)
        lead_pressure = _finite(leaders.get("pressure"))
        vol_pressure = None
        vf = micro.get("volume_pressure")
        if isinstance(vf, Feature):
            vol_pressure = vf.value
        if lp is not None and vol_pressure is not None and abs(lp - vol_pressure) > 0.8:
            hypotheses.append({"state": "FLOW_PRICE_DIVERGENCE", "strength": min(1.0, abs(lp - vol_pressure) / 2.0), "evidence": ["latent pressure vs aggressive flow"]})
        if lead_pressure is not None and vol_pressure is not None and lead_pressure * vol_pressure < -0.12:
            hypotheses.append({"state": "CROSS_ASSET_FLOW_CONFLICT", "strength": min(1.0, abs(lead_pressure - vol_pressure) / 2.0), "evidence": ["leader graph vs local flow"]})
        hypotheses.sort(key=lambda x: -x["strength"])
        return {
            "primary": hypotheses[0]["state"] if hypotheses else "UNRESOLVED",
            "hypotheses": hypotheses[:5],
            "rule": "Inverse inference ranks explanations; it does not claim unobserved participant identity as fact.",
        }

    def _information_wave(
        self,
        history: Sequence[Mapping[str, float]],
        vol: float,
        latent: float | None,
        coverage: float,
        micro: Mapping[str, Any],
        leaders: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Detect unexplained information arrival before its source is identified.

        This is a novelty/residual detector, not a claim that a hidden actor or news
        event exists. It asks whether current price change is unusually large after
        conditioning on the pressure state that Ψ can presently observe.
        """
        returns = [float(row["ret"]) for row in history if _finite(row.get("ret")) is not None]
        if len(returns) < 12:
            return {
                "status": "WARMING",
                "score": None,
                "direction": None,
                "source_identified": False,
                "detail": "requires at least 12 observed return transitions",
            }
        baseline = returns[-61:-1] if len(returns) > 12 else returns[:-1]
        latest = returns[-1]
        mu = _mean(baseline)
        sigma = max(_stdev(baseline), vol, 1e-9)
        observed_pressure = _finite(latent) or 0.0
        # Lagged cross-asset pressure is already represented inside latent pressure.
        # Conditioning on the leader graph again would double count that domain.
        expected = sigma * 1.75 * _clamp(
            observed_pressure * (0.35 + 0.45 * coverage)
        )
        residual = latest - expected
        residual_z = abs(residual - mu) / sigma

        repricing = micro.get("repricing_pressure")
        volume = micro.get("volume_pressure")
        conflict = 0.0
        domains = 1
        if isinstance(repricing, Feature) and isinstance(volume, Feature):
            if repricing.available and volume.available and repricing.value is not None and volume.value is not None:
                conflict = abs(repricing.value - volume.value)
                domains += 1

        novelty = 0.78 * residual_z + 0.22 * min(3.0, conflict * 2.0)
        score = 100.0 * (1.0 - math.exp(-max(0.0, novelty) / 2.2))
        status = "EVENT" if score >= 75.0 else "WATCH" if score >= 50.0 else "QUIET"
        direction = "UP" if residual > 0 else "DOWN" if residual < 0 else None
        return {
            "status": status,
            "score": min(100.0, score),
            "direction": direction,
            "source_identified": False,
            "return_surprise_z": residual_z,
            "microstructure_conflict": conflict,
            "observed_domains": domains,
            "expected_return_component": expected,
            "residual_return": residual,
            "detail": "Source-agnostic residual novelty; investigate provenance before assigning a cause.",
        }

    def _synthetic_price(
        self,
        price: float,
        vol: float,
        latent: float | None,
        features: Mapping[str, Feature],
        leaders: Mapping[str, Any],
    ) -> dict[str, Any]:
        if latent is None:
            return {
                "available": False,
                "synthetic_price": None,
                "dislocation": None,
                "unexplained_dislocation": None,
                "unexplained_dislocation_available": False,
            }
        horizon_scale = max(price * vol * 8.0, price * 0.00015)

        # Cross-asset pressure is already one component of the normalized latent
        # pressure. Do not add the leader graph a second time here.
        effective: dict[str, tuple[float, float]] = {}
        denominator = 0.0
        for name, feature in features.items():
            if not feature.available or feature.value is None:
                continue
            weight = _COMPONENT_WEIGHTS.get(name, 0.5)
            confidence = _clamp(feature.confidence, 0.0, 1.0)
            scale = abs(weight) * confidence
            if scale <= 0:
                continue
            effective[name] = (weight, confidence)
            denominator += scale

        contributions: dict[str, float] = {}
        if denominator > 0:
            for name, (weight, confidence) in effective.items():
                feature = features[name]
                normalized_pressure = float(feature.value) * weight * confidence / denominator
                contributions[name] = horizon_scale * 0.72 * normalized_pressure

        synthetic_move = sum(contributions.values())
        synthetic = price + synthetic_move
        dislocation = synthetic - price
        return {
            "available": True,
            "synthetic_price": synthetic,
            "dislocation": dislocation,
            "known_force_contribution": synthetic_move,
            "unexplained_dislocation": None,
            "unexplained_dislocation_available": False,
            "contributions": contributions,
            "model": "normalized force-balance counterfactual without duplicated leader pressure",
            "note": "An independent unexplained residual is not identifiable from the same evidence used to construct synthetic price.",
        }

    def _future_space(
        self,
        symbol: str,
        price: float,
        vol: float,
        latent: float | None,
        coverage: float,
        features: Mapping[str, Feature],
        market_row: Mapping[str, Any],
    ) -> dict[str, Any]:
        if latent is None or len(self._history.get(symbol, ())) < 8:
            return {
                "status": "warming",
                "scenarios_generated": 0,
                "viable_futures": 0,
                "clusters": [],
                "future_entropy": None,
                "future_space_collapse": None,
                "dominant_cluster": None,
            }

        regime_state = market_row.get("state") if isinstance(market_row.get("state"), Mapping) else {}
        regime_strength = _finite(regime_state.get("rate_regime")) or 0.5
        step_sigma = max(price * vol, price * 0.00004)
        drift = step_sigma * 0.50 * latent * (0.45 + 0.55 * coverage)
        mean_revert = max(0.0, 0.55 - regime_strength) * 0.14

        generated = self.scenarios
        viable: list[tuple[float, float]] = []
        for i in range(1, generated + 1):
            px = price
            weight = 1.0
            for step in range(1, 7):
                shock = _normalish(i + step * generated, 2 + (step % 3), 5 + (step % 2))
                shock = _clamp(shock, -2.8, 2.8)
                pull = (price - px) * mean_revert
                liquidity_asym = latent * abs(shock) * step_sigma * 0.08
                px += drift + shock * step_sigma * 0.72 + pull + liquidity_asym
                if px <= 0 or abs(px - price) > step_sigma * 15.0:
                    weight = 0.0
                    break
                # Scenarios fighting strong, well-covered latent pressure are not removed,
                # but they are down-weighted; this keeps the future set plural.
                signed_move = (px - price) * (1.0 if latent >= 0 else -1.0)
                if abs(latent) > 0.65 and coverage > 0.55 and signed_move < -step_sigma * 2.5:
                    weight *= 0.35
            if weight > 0:
                viable.append((px, weight))

        threshold = step_sigma * 0.65
        buckets = {"DOWN": 0.0, "FLAT": 0.0, "UP": 0.0}
        for endpoint, weight in viable:
            delta = endpoint - price
            key = "UP" if delta > threshold else "DOWN" if delta < -threshold else "FLAT"
            buckets[key] += weight
        total = sum(buckets.values())
        probs = {k: (v / total if total else 0.0) for k, v in buckets.items()}
        entropy = 0.0
        for p in probs.values():
            if p > 0:
                entropy -= p * math.log(p)
        entropy_norm = (entropy / math.log(3.0)) * 100.0 if total else None
        collapse = None if entropy_norm is None else max(0.0, min(100.0, 100.0 - entropy_norm))
        dominant = max(probs, key=probs.get) if total else None
        clusters = [{"name": k, "weight": v, "share": probs[k]} for k, v in sorted(buckets.items(), key=lambda kv: -kv[1])]
        return {
            "status": "observed",
            "scenarios_generated": generated,
            "viable_futures": len(viable),
            "clusters": clusters,
            "future_entropy": entropy_norm,
            "future_space_collapse": collapse,
            "dominant_cluster": dominant,
            "dominant_share": probs.get(dominant) if dominant else None,
            "horizon_steps": 6,
            "step_sigma": step_sigma,
            "model_note": "Deterministic constraint-aware scenario lattice; cluster shares are not calibrated probabilities.",
        }

    def _phase_boundary(
        self,
        price: float,
        vol: float,
        latent: float | None,
        futures: Mapping[str, Any],
        features: Mapping[str, Feature],
    ) -> dict[str, Any]:
        if latent is None:
            return {"available": False, "phase_boundary": None, "event_horizon": None, "direction": None}
        if abs(latent) < 1e-12:
            return {
                "available": False,
                "phase_boundary": None,
                "event_horizon": None,
                "direction": "NEUTRAL",
                "note": "No directional phase boundary is emitted from exactly neutral latent pressure.",
            }
        direction = 1.0 if latent > 0 else -1.0
        sigma = _finite(futures.get("step_sigma")) or max(price * vol, price * 0.00004)
        collapse = (_finite(futures.get("future_space_collapse")) or 0.0) / 100.0
        distance = sigma * (1.6 - 0.7 * collapse)
        boundary = price + direction * distance
        horizon = boundary + direction * sigma * (0.35 + 0.35 * collapse)
        mechanisms = []
        for name, f in features.items():
            if f.available and f.value is not None and f.value * direction > 0.15 and f.confidence >= 0.35:
                mechanisms.append(name)
        return {
            "available": True,
            "direction": "UP" if direction > 0 else "DOWN",
            "phase_boundary": boundary,
            "event_horizon": horizon,
            "distance_to_boundary": abs(boundary - price),
            "aligned_mechanisms": mechanisms,
            "persistence_model": _clamp(0.35 + collapse * 0.45 + min(0.2, len(mechanisms) * 0.04), 0.0, 0.95),
            "note": "Research phase-transition threshold; not an exchange-native trigger unless a listed mechanism is directly observed.",
        }

    def _forced_consensus(self, features: Mapping[str, Feature]) -> dict[str, Any]:
        domain_for = {
            "queue_pressure": "microstructure",
            "repricing_pressure": "microstructure",
            "volume_pressure": "microstructure",
            "cross_asset_pressure": "cross_asset",
            "basis_pressure": "basis",
            "gamma_pressure": "gamma",
            "forced_flow_pressure": "forced_flow",
        }
        mechanisms = []
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for name, feature in features.items():
            if not feature.available or feature.value is None or feature.confidence < 0.20 or abs(feature.value) < 0.10:
                continue
            vote = {
                "name": name,
                "domain": domain_for.get(name, name),
                "sign": 1 if feature.value > 0 else -1,
                "strength": abs(feature.value) * feature.confidence,
            }
            mechanisms.append(vote)
            grouped[vote["domain"]].append(vote)

        domains = []
        for domain, votes in sorted(grouped.items()):
            signed = sum(v["sign"] * v["strength"] for v in votes)
            gross = sum(v["strength"] for v in votes)
            if gross <= 1e-12 or abs(signed) <= 1e-12:
                continue
            domains.append({
                "name": domain,
                "sign": 1 if signed > 0 else -1,
                "strength": abs(signed),
                "internal_alignment": abs(signed) / gross,
                "components": [v["name"] for v in votes],
            })

        if not domains:
            return {
                "active": False,
                "direction": None,
                "alignment": 0.0,
                "mechanisms": mechanisms,
                "domains": [],
                "observed_domain_count": 0,
            }
        signed = sum(v["sign"] * v["strength"] for v in domains)
        gross = sum(v["strength"] for v in domains) or 1.0
        alignment = abs(signed) / gross
        direction = "UP" if signed > 0 else "DOWN"
        active = len(domains) >= 3 and alignment >= 0.72
        return {
            "active": active,
            "direction": direction if active else None,
            "alignment": alignment,
            "mechanisms": mechanisms,
            "domains": domains,
            "observed_domain_count": len(domains),
            "note": "Consensus counts distinct evidence domains; correlated features from one domain cannot satisfy the gate by themselves.",
        }

    def _market_shadows(
        self,
        price: float,
        synthetic: Mapping[str, Any],
        features: Mapping[str, Feature],
    ) -> list[dict[str, Any]]:
        if not synthetic.get("available"):
            return []
        full = _finite(synthetic.get("synthetic_price"))
        contributions = synthetic.get("contributions") if isinstance(synthetic.get("contributions"), Mapping) else {}
        if full is None:
            return []
        rows = []
        for name, contribution in contributions.items():
            c = _finite(contribution)
            if c is None:
                continue
            rows.append({
                "removed_force": name,
                "counterfactual_price": full - c,
                "force_contribution": c,
                "distance_from_actual": (full - c) - price,
            })
        rows.sort(key=lambda x: -abs(x["force_contribution"]))
        return rows[:12]

    def _edge_gate(
        self,
        *,
        latent: float | None,
        coverage: float,
        collapse: Any,
        consensus: Mapping[str, Any],
        micro: Mapping[str, Any],
        leaders: Mapping[str, Any],
    ) -> dict[str, Any]:
        blockers = []
        collapse_value = _finite(collapse)
        if latent is None:
            blockers.append("latent pressure unavailable")
        elif abs(latent) < 0.30:
            blockers.append("latent pressure below minimum magnitude")
        if coverage < 0.42:
            blockers.append("evidence coverage below 42%")
        if collapse_value is None or collapse_value < 22.0:
            blockers.append("future-space collapse below 22")
        if leaders.get("status") != "observed":
            blockers.append("dynamic leader graph still warming")
        observed_domains = sum(
            1 for key in ("ticks", "depth")
            if bool((micro.get("health") or {}).get(key))
        )
        if observed_domains == 0 and coverage < 0.60:
            blockers.append("no live microstructure domain observed")
        if not consensus.get("active") and coverage < 0.60:
            blockers.append("forced-consensus gate inactive")

        state = "NO_EDGE" if blockers else ("LONG_BIAS" if float(latent) > 0 else "SHORT_BIAS")
        confidence = 0.0
        if not blockers and latent is not None and collapse_value is not None:
            confidence = _clamp(
                0.34 * abs(latent)
                + 0.28 * coverage
                + 0.20 * (collapse_value / 100.0)
                + 0.18 * (_finite(consensus.get("alignment")) or 0.0),
                0.0,
                1.0,
            )
        return {
            "state": state,
            "confidence": confidence,
            "blockers": blockers,
            "production_decision_authorized": False,
            "execution_authorized": False,
            "note": "Directional bias is a research diagnostic only and cannot place, size, or authorize a trade.",
        }

    def _empty(self, detail: str, symbol: str = "") -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _utc_now(),
            "asset": symbol or None,
            "edge_state": {"state": "NO_EDGE", "confidence": 0.0, "blockers": [detail]},
            "authority": {
                "research_authorized": True,
                "production_decision_authorized": False,
                "execution_authorized": False,
                "trade_signal_authorized": False,
            },
            "truth_contract": {
                "scenario_probabilities_calibrated": False,
                "causality_proven": False,
                "missing_evidence_imputed": False,
            },
        }
