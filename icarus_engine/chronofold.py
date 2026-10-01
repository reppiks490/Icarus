"""ICARUS Ξ Chronofold causal-navigation research engine.

Chronofold is deliberately research/shadow-only. It borrows mathematical
structures from information geometry, time changes, dynamical systems,
control/GNC, statistical mechanics and quantum-inspired uncertainty without
claiming that markets literally obey physical laws.

The module has no broker authority, no production-decision authority and no
future-data path. Every snapshot is derived only from observations available
at or before the retrieval boundary supplied by the running ICARUS process.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
import random
import statistics
import threading
import time
from typing import Any, Deque, Dict, Mapping, Sequence


EPS = 1e-12


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _mean(xs: Sequence[float]) -> float:
    return statistics.fmean(xs) if xs else 0.0


def _std(xs: Sequence[float]) -> float:
    return statistics.pstdev(xs) if len(xs) > 1 else 0.0


def _mad(xs: Sequence[float]) -> float:
    if not xs:
        return 0.0
    med = statistics.median(xs)
    return statistics.median(abs(x - med) for x in xs)


def _corr(a: Sequence[float], b: Sequence[float]) -> float:
    n = min(len(a), len(b))
    if n < 4:
        return 0.0
    x, y = list(a)[-n:], list(b)[-n:]
    mx, my = _mean(x), _mean(y)
    sx, sy = _std(x), _std(y)
    if sx <= EPS or sy <= EPS:
        return 0.0
    return _clip(sum((u - mx) * (v - my) for u, v in zip(x, y)) / (n * sx * sy), -1.0, 1.0)


def _softmax_negative(costs: Sequence[float], temperature: float = 1.0) -> list[float]:
    if not costs:
        return []
    t = max(EPS, float(temperature))
    floor = min(costs)
    ex = [math.exp(-_clip((c - floor) / t, -80.0, 80.0)) for c in costs]
    z = sum(ex) or 1.0
    return [v / z for v in ex]


def _entropy(probs: Sequence[float]) -> float:
    ps = [max(0.0, float(p)) for p in probs]
    z = sum(ps)
    if z <= EPS:
        return 1.0
    ps = [p / z for p in ps]
    h = -sum(p * math.log(max(p, EPS)) for p in ps)
    return h / math.log(len(ps)) if len(ps) > 1 else 0.0


def _solve_linear(a: list[list[float]], b: list[float]) -> list[float] | None:
    n = len(a)
    if not n or any(len(row) != n for row in a) or len(b) != n:
        return None
    m = [list(map(float, row)) + [float(rhs)] for row, rhs in zip(a, b)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) <= 1e-14:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        p = m[col][col]
        m[col] = [x / p for x in m[col]]
        for r in range(n):
            if r == col:
                continue
            f = m[r][col]
            if abs(f) <= EPS:
                continue
            m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    return [m[i][-1] for i in range(n)]


def _ridge_fit(rows: Sequence[Sequence[float]], target: Sequence[float], ridge: float = 1e-5) -> list[float] | None:
    if not rows or len(rows) != len(target):
        return None
    p = len(rows[0])
    if p == 0 or any(len(r) != p for r in rows):
        return None
    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p
    for row, y in zip(rows, target):
        for i in range(p):
            xty[i] += row[i] * y
            for j in range(p):
                xtx[i][j] += row[i] * row[j]
    for i in range(p):
        xtx[i][i] += ridge
    return _solve_linear(xtx, xty)


@dataclass(frozen=True)
class ChronofoldObservation:
    symbol: str
    ts: float
    price: float
    ret: float
    pulse: float
    regime: float
    warm: bool
    paused: bool


class ChronofoldEngine:
    """Stateful causal-navigation research plane for the running portfolio."""

    SCHEMA_VERSION = "icarus-chronofold-v1"

    def __init__(
        self,
        port: Any,
        *,
        possibility: Any | None = None,
        max_history: int = 512,
        scenarios: int = 384,
        horizon: int = 12,
    ):
        if max_history < 32:
            raise ValueError("max_history must be >= 32")
        if not (32 <= scenarios <= 4096):
            raise ValueError("scenarios must be in [32, 4096]")
        if not (2 <= horizon <= 128):
            raise ValueError("horizon must be in [2, 128]")
        self.port = port
        self.possibility = possibility
        self.max_history = int(max_history)
        self.scenarios = int(scenarios)
        self.horizon = int(horizon)
        self._history: Dict[str, Deque[ChronofoldObservation]] = defaultdict(lambda: deque(maxlen=self.max_history))
        self._state_vectors: Dict[str, Deque[list[float]]] = defaultdict(lambda: deque(maxlen=self.max_history))
        self._tau_total: Dict[str, float] = defaultdict(float)
        self._clock_total: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._last_graph: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._last_order_parameter: Dict[str, float] = defaultdict(float)
        self._lock = threading.RLock()

    @staticmethod
    def _asset_rows(status: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        rows = status.get("assets", []) if isinstance(status, Mapping) else []
        return [r for r in rows if isinstance(r, Mapping) and r.get("symbol")]

    @staticmethod
    def _state_fields(row: Mapping[str, Any]) -> tuple[float, float]:
        state = row.get("state") if isinstance(row.get("state"), Mapping) else {}
        pulse = max(_finite(state.get("pulse_l")), _finite(state.get("pulse_s")))
        regime = _finite(state.get("rate_regime"))
        return _clip(pulse, 0.0, 1.0), _clip(regime, -1.0, 1.0)

    def _observe(self, status: Mapping[str, Any], ts: float) -> Dict[str, ChronofoldObservation]:
        out: Dict[str, ChronofoldObservation] = {}
        for row in self._asset_rows(status):
            symbol = str(row.get("symbol") or "").upper()
            price = _finite(row.get("price"))
            if not symbol or price <= 0:
                continue
            hist = self._history[symbol]
            prev = hist[-1].price if hist else price
            ret = math.log(max(price, EPS) / max(prev, EPS)) if prev > 0 else 0.0
            pulse, regime = self._state_fields(row)
            obs = ChronofoldObservation(
                symbol=symbol,
                ts=ts,
                price=price,
                ret=ret,
                pulse=pulse,
                regime=regime,
                warm=bool(row.get("warm", False)),
                paused=bool(row.get("paused", False)),
            )
            if hist and abs(hist[-1].price - price) <= EPS and abs(hist[-1].pulse - pulse) <= EPS and abs(hist[-1].regime - regime) <= EPS:
                obs = ChronofoldObservation(symbol, ts, price, 0.0, pulse, regime, obs.warm, obs.paused)
                hist[-1] = obs
            else:
                hist.append(obs)
            out[symbol] = obs
        return out

    def _possibility_snapshot(self, symbol: str) -> Mapping[str, Any]:
        if self.possibility is None:
            return {}
        try:
            value = self.possibility.snapshot(symbol)
        except Exception:
            return {}
        return value if isinstance(value, Mapping) else {}

    def _chronon_activity(self, symbol: str, poss: Mapping[str, Any]) -> Dict[str, float]:
        hist = list(self._history[symbol])
        rets = [x.ret for x in hist[-64:]]
        current = abs(rets[-1]) if rets else 0.0
        scale = 1.4826 * _mad(rets[:-1]) if len(rets) > 3 else _std(rets[:-1])
        surprise = _clip(current / max(scale, 1e-6), 0.0, 8.0) / 8.0
        short_vol = _std(rets[-8:])
        long_vol = _std(rets[-64:])
        vol_burst = _clip(short_vol / max(long_vol, 1e-6) - 1.0, 0.0, 5.0) / 5.0
        info_wave = poss.get("information_wave") if isinstance(poss.get("information_wave"), Mapping) else {}
        event_intensity = _clip(_finite(info_wave.get("score")) / 100.0, 0.0, 1.0)
        latent = poss.get("latent_pressure_engine") if isinstance(poss.get("latent_pressure_engine"), Mapping) else {}
        causal = _clip(abs(_finite(latent.get("latent_pressure"))), 0.0, 1.0)
        phase = poss.get("phase_transition") if isinstance(poss.get("phase_transition"), Mapping) else {}
        phase_intensity = _clip(abs(_finite(phase.get("event_horizon"))), 0.0, 1.0)
        activity = 0.30 * surprise + 0.24 * vol_burst + 0.18 * causal + 0.14 * event_intensity + 0.14 * phase_intensity
        activity = _clip(activity, 0.0, 1.0)
        return {
            "statistical_surprise": surprise,
            "volatility_burst": vol_burst,
            "causal_change": causal,
            "event_intensity": event_intensity,
            "phase_intensity": phase_intensity,
            "activity": activity,
        }

    def _causal_graph(self, target: str) -> Dict[str, Any]:
        target_rets = [x.ret for x in self._history[target]]
        leaders: list[Dict[str, Any]] = []
        weights: Dict[str, float] = {}
        for symbol, hist_dq in self._history.items():
            if symbol == target:
                continue
            other = [x.ret for x in hist_dq]
            n = min(len(target_rets), len(other))
            if n < 8:
                continue
            c = _corr(other[-n:-1], target_rets[-n + 1:])
            if abs(c) < 0.05:
                continue
            weights[symbol] = c
            leaders.append({
                "asset": symbol,
                "lag_chronons": 1,
                "lagged_association": c,
                "direction": "WITH" if c >= 0 else "INVERSE",
                "samples": n - 1,
            })
        leaders.sort(key=lambda x: abs(x["lagged_association"]), reverse=True)
        previous = self._last_graph.get(target, {})
        keys = set(previous) | set(weights)
        graph_change = math.sqrt(sum((weights.get(k, 0.0) - previous.get(k, 0.0)) ** 2 for k in keys))
        self._last_graph[target] = weights
        incoming = 0.0
        for row in leaders:
            h = self._history[row["asset"]]
            latest = h[-1].ret if h else 0.0
            incoming += row["lagged_association"] * latest
        return {
            "method": "lagged-return association",
            "structural_causality_proven": False,
            "leaders": leaders[:12],
            "graph_change": graph_change,
            "incoming_pressure": _clip(incoming * 1000.0, -3.0, 3.0),
        }

    def _multitime(self, symbol: str, activity: Mapping[str, float], graph: Mapping[str, Any], poss: Mapping[str, Any]) -> Dict[str, float]:
        h = list(self._history[symbol])
        ret = abs(h[-1].ret) if h else 0.0
        vol = _std([x.ret for x in h[-16:]])
        latent = poss.get("latent_pressure_engine") if isinstance(poss.get("latent_pressure_engine"), Mapping) else {}
        micro = poss.get("data_health") if isinstance(poss.get("data_health"), Mapping) else {}
        micro = micro.get("microstructure") if isinstance(micro.get("microstructure"), Mapping) else {}
        clocks = self._clock_total[symbol]
        increments = {
            "price_time": _clip(ret / 0.001, 0.0, 5.0),
            "volatility_time": _clip(vol / 0.001, 0.0, 5.0),
            "information_time": _finite(activity.get("activity")),
            "causal_time": _clip(_finite(graph.get("graph_change")), 0.0, 5.0),
            "macro_time": _clip(abs(_finite(latent.get("latent_pressure"))), 0.0, 1.0),
            "liquidity_time": 1.0 if micro.get("depth") else 0.0,
            "event_time": _finite(activity.get("event_intensity")),
        }
        for key, inc in increments.items():
            clocks[key] += max(0.0, inc)
        vals = list(increments.values())
        shear = _std(vals) / max(_mean(vals), EPS) if vals else 0.0
        return {**{k: clocks[k] for k in increments}, "temporal_shear": _clip(shear, 0.0, 10.0)}

    def _geometry(self, symbol: str, graph: Mapping[str, Any]) -> Dict[str, Any]:
        h = list(self._history[symbol])
        if not h:
            return {"status": "warming", "distance": 0.0, "curvature": 0.0, "metric_diag": []}
        latest = h[-1]
        vec = [latest.ret * 1000.0, latest.pulse, latest.regime, _finite(graph.get("incoming_pressure"))]
        vectors = self._state_vectors[symbol]
        vectors.append(vec)
        if len(vectors) < 4:
            return {"status": "warming", "distance": 0.0, "curvature": 0.0, "metric_diag": [1.0] * len(vec)}
        cols = list(zip(*vectors))
        variances = [max(_std(list(c)) ** 2, 1e-6) for c in cols]
        metric = [1.0 / v for v in variances]
        prev = vectors[-2]
        delta = [a - b for a, b in zip(vec, prev)]
        distance = math.sqrt(sum(w * d * d for w, d in zip(metric, delta)))
        prev2 = vectors[-3]
        v1 = [b - a for a, b in zip(prev2, prev)]
        v2 = delta
        a1, a2 = math.sqrt(sum(x * x for x in v1)), math.sqrt(sum(x * x for x in v2))
        if a1 > EPS and a2 > EPS:
            cosine = _clip(sum(x * y for x, y in zip(v1, v2)) / (a1 * a2), -1.0, 1.0)
            curvature = math.acos(cosine) / math.pi
        else:
            curvature = 0.0
        return {"status": "observed", "coordinates": vec, "metric_diag": metric, "distance": distance, "curvature": curvature}

    def _renormalization(self, symbol: str) -> Dict[str, Any]:
        rets = [x.ret for x in self._history[symbol]]
        scales = []
        signs = []
        for block in (1, 2, 4, 8, 16):
            if len(rets) < block * 4:
                continue
            coarse = [_mean(rets[i:i + block]) for i in range(max(0, len(rets) - 64), len(rets), block) if rets[i:i + block]]
            scales.append({"block": block, "mean": _mean(coarse), "volatility": _std(coarse)})
            if coarse:
                tail = _mean(coarse[-min(4, len(coarse)):])
                signs.append(1 if tail > 0 else -1 if tail < 0 else 0)
        persistence = abs(sum(signs)) / len(signs) if signs else 0.0
        return {"scales": scales, "scale_stability": persistence}

    def _koopman(self, symbol: str) -> Dict[str, Any]:
        rets = [x.ret for x in self._history[symbol]][-96:]
        if len(rets) < 8:
            return {"status": "warming", "eigenvalue": None, "mode": "UNKNOWN"}
        x, y = rets[:-1], rets[1:]
        den = sum(v * v for v in x)
        lam = sum(a * b for a, b in zip(x, y)) / den if den > EPS else 0.0
        if abs(lam) < 0.15:
            mode = "FAST_DECAY"
        elif lam >= 0.85:
            mode = "PERSISTENT"
        elif lam <= -0.35:
            mode = "OSCILLATORY"
        else:
            mode = "TRANSIENT"
        return {"status": "observed", "eigenvalue": _clip(lam, -2.0, 2.0), "mode": mode}

    def _path_signature(self, symbol: str) -> Dict[str, Any]:
        h = list(self._history[symbol])[-32:]
        if len(h) < 3:
            return {"status": "warming", "level1": [], "level2": []}
        pts = [[x.ret * 1000.0, x.pulse, x.regime] for x in h]
        inc = [[b[j] - a[j] for j in range(3)] for a, b in zip(pts[:-1], pts[1:])]
        l1 = [sum(d[j] for d in inc) for j in range(3)]
        l2 = []
        for i in range(3):
            for j in range(3):
                acc = 0.0
                prefix = 0.0
                for d in inc:
                    acc += prefix * d[j] + 0.5 * d[i] * d[j]
                    prefix += d[i]
                l2.append(acc)
        return {"status": "observed", "level1": l1, "level2": l2}

    def _density_state(self, symbol: str, graph: Mapping[str, Any], koopman: Mapping[str, Any], poss: Mapping[str, Any]) -> Dict[str, Any]:
        h = list(self._history[symbol])
        ret = _mean([x.ret for x in h[-6:]]) if h else 0.0
        pressure = _finite(graph.get("incoming_pressure")) / 3.0
        latent = poss.get("latent_pressure_engine") if isinstance(poss.get("latent_pressure_engine"), Mapping) else {}
        pressure += _finite(latent.get("latent_pressure"))
        lam = _finite(koopman.get("eigenvalue"))
        score = _clip(240.0 * ret + 0.8 * pressure + 0.15 * lam, -6.0, 6.0)
        raw = [math.exp(score), 1.0 + math.exp(-abs(score)), math.exp(-score)]
        z = sum(raw)
        probs = [v / z for v in raw]
        coherence = _clip((1.0 - _entropy(probs)) * 0.35, 0.0, 0.35)
        matrix = []
        for i, p in enumerate(probs):
            row = []
            for j, q in enumerate(probs):
                row.append(p if i == j else coherence * math.sqrt(p * q))
            matrix.append(row)
        return {
            "basis": ["UP", "FLAT", "DOWN"],
            "probabilities": {"UP": probs[0], "FLAT": probs[1], "DOWN": probs[2]},
            "density_matrix": matrix,
            "normalized_entropy": _entropy(probs),
            "coherence_proxy": coherence,
            "quantum_claim": False,
        }

    def _phase_transition(self, symbol: str, geometry: Mapping[str, Any], density: Mapping[str, Any], graph: Mapping[str, Any]) -> Dict[str, Any]:
        h = list(self._history[symbol])
        vol = _std([x.ret for x in h[-16:]])
        base = _std([x.ret for x in h[-96:]])
        vol_ratio = _clip(vol / max(base, 1e-6), 0.0, 6.0) / 6.0
        graph_density = _clip(len(graph.get("leaders", [])) / max(1.0, len(self._history) - 1.0), 0.0, 1.0)
        entropy_order = 1.0 - _finite(density.get("normalized_entropy"), 1.0)
        curvature = _clip(_finite(geometry.get("curvature")), 0.0, 1.0)
        theta = _clip(0.32 * vol_ratio + 0.24 * graph_density + 0.22 * entropy_order + 0.22 * curvature, 0.0, 1.0)
        prev = self._last_order_parameter[symbol]
        velocity = theta - prev
        self._last_order_parameter[symbol] = theta
        return {"order_parameter": theta, "transition_velocity": velocity, "state": "CRITICAL" if theta >= 0.72 else "TRANSITION" if theta >= 0.48 else "STABLE"}

    def _symbolic_laws(self, symbol: str, graph: Mapping[str, Any]) -> Dict[str, Any]:
        h = list(self._history[symbol])[-128:]
        if len(h) < 16:
            return {"status": "warming", "laws": []}
        rows, target = [], []
        pressure = _finite(graph.get("incoming_pressure"))
        for i in range(1, len(h)):
            prev = h[i - 1]
            rows.append([1.0, prev.ret * 1000.0, prev.pulse - 0.5, prev.regime, pressure])
            target.append(h[i].ret * 1000.0)
        beta = _ridge_fit(rows, target)
        if beta is None:
            return {"status": "singular", "laws": []}
        preds = [sum(c * x for c, x in zip(beta, row)) for row in rows]
        mse = _mean([(a - b) ** 2 for a, b in zip(preds, target)])
        baseline = _mean([(y - _mean(target)) ** 2 for y in target])
        skill = _clip(1.0 - mse / max(baseline, EPS), -1.0, 1.0)
        labels = ["intercept", "lag_return", "pulse", "regime", "causal_pressure"]
        law = {
            "equation": "dX/dχ = " + " + ".join(f"{c:.5g}*{name}" for c, name in zip(beta, labels)),
            "coefficients": dict(zip(labels, beta)),
            "mse": mse,
            "relative_skill": skill,
            "samples": len(target),
        }
        variants = []
        for keep in (2, 3, 4, 5):
            pred = [sum(beta[j] * row[j] for j in range(keep)) for row in rows]
            vmse = _mean([(a - b) ** 2 for a, b in zip(pred, target)])
            fitness = -(vmse + keep * 1e-4)
            variants.append({"terms": labels[:keep], "fitness": fitness, "mse": vmse})
        variants.sort(key=lambda x: x["fitness"], reverse=True)
        return {"status": "observed", "laws": [law], "theory_population": variants, "champion": variants[0]}

    def _impossible_state(self, symbol: str, geometry: Mapping[str, Any]) -> Dict[str, Any]:
        vectors = list(self._state_vectors[symbol])
        if len(vectors) < 16:
            return {"status": "warming", "distance_sigma": None, "reality_fracture": False}
        current = vectors[-1]
        prior = vectors[:-1]
        cols = list(zip(*prior))
        z2 = 0.0
        for x, col in zip(current, cols):
            mu, sig = _mean(list(col)), _std(list(col))
            z2 += ((x - mu) / max(sig, 1e-4)) ** 2
        distance = math.sqrt(z2 / max(1, len(current)))
        return {
            "status": "observed",
            "distance_sigma": distance,
            "reality_fracture": distance >= 3.0,
            "interpretation": "joint-state support distance; not an arbitrage guarantee",
        }

    def _multiverse(self, symbol: str, density: Mapping[str, Any], geometry: Mapping[str, Any], graph: Mapping[str, Any], poss: Mapping[str, Any]) -> Dict[str, Any]:
        h = list(self._history[symbol])
        price = h[-1].price if h else 0.0
        rets = [x.ret for x in h[-96:]]
        vol = max(_std(rets), 0.00015)
        drift = _mean(rets[-8:]) if rets else 0.0
        drift += _finite(graph.get("incoming_pressure")) * 0.00004
        probs = density.get("probabilities", {}) if isinstance(density.get("probabilities"), Mapping) else {}
        drift += (_finite(probs.get("UP")) - _finite(probs.get("DOWN"))) * 0.00008
        curvature = _clip(_finite(geometry.get("curvature")), 0.0, 1.0)
        seed_material = f"{symbol}|{len(h)}|{price:.8f}|{drift:.12f}|{vol:.12f}|{self.scenarios}|{self.horizon}"
        seed = int(hashlib.sha256(seed_material.encode()).hexdigest()[:16], 16)
        rng = random.Random(seed)
        terminals, costs, clusters = [], [], {"UP": 0.0, "FLAT": 0.0, "DOWN": 0.0}
        raw_cluster, paths = [], []
        for _ in range(self.scenarios):
            rsum, cost, p = 0.0, 0.0, price
            path = [price]
            local_drift = drift + rng.gauss(0.0, vol * 0.08)
            for _step in range(self.horizon):
                shock = rng.gauss(0.0, vol)
                step_ret = local_drift + shock * (1.0 + 0.75 * curvature)
                rsum += step_ret
                cost += (shock / max(vol, EPS)) ** 2 + curvature * abs(step_ret) / max(vol, EPS)
                p *= math.exp(step_ret)
                path.append(p)
            terminal_ret = math.exp(rsum) - 1.0
            label = "UP" if terminal_ret > vol * math.sqrt(self.horizon) * 0.45 else "DOWN" if terminal_ret < -vol * math.sqrt(self.horizon) * 0.45 else "FLAT"
            terminals.append(terminal_ret)
            costs.append(cost / self.horizon)
            raw_cluster.append(label)
            if len(paths) < 24:
                paths.append(path)
        weights = _softmax_negative(costs, temperature=2.0)
        for label, w in zip(raw_cluster, weights):
            clusters[label] += w
        expected = sum(r * w for r, w in zip(terminals, weights))
        ordered = sorted(zip(terminals, weights), key=lambda x: x[0])
        def weighted_q(q: float) -> float:
            acc = 0.0
            for value, weight in ordered:
                acc += weight
                if acc >= q:
                    return value
            return ordered[-1][0] if ordered else 0.0
        return {
            "scenarios": self.scenarios,
            "horizon_chronons": self.horizon,
            "cluster_weights": clusters,
            "expected_return": expected,
            "p05_return": weighted_q(0.05),
            "p50_return": weighted_q(0.50),
            "p95_return": weighted_q(0.95),
            "future_entropy": _entropy(list(clusters.values())),
            "sample_paths": paths,
            "probabilities_calibrated": False,
            "path_weighting": "Boltzmann-like action weighting; mathematical analogue only",
        }

    def _counterfactuals(self, multiverse: Mapping[str, Any], graph: Mapping[str, Any], poss: Mapping[str, Any]) -> list[Dict[str, Any]]:
        base = _finite(multiverse.get("expected_return"))
        latent = poss.get("latent_pressure_engine") if isinstance(poss.get("latent_pressure_engine"), Mapping) else {}
        factors = {
            "causal_pressure": _finite(graph.get("incoming_pressure")) * 0.00004 * self.horizon,
            "latent_pressure": _finite(latent.get("latent_pressure")) * 0.00008 * self.horizon,
        }
        return [{
            "removed_force": name,
            "baseline_expected_return": base,
            "shadow_expected_return": base - contribution,
            "estimated_contribution": contribution,
            "structural_causal_claim": False,
        } for name, contribution in factors.items()]

    def _guidance(self, density: Mapping[str, Any], multiverse: Mapping[str, Any], unknown_mass: float) -> Dict[str, Any]:
        clusters = multiverse.get("cluster_weights", {}) if isinstance(multiverse.get("cluster_weights"), Mapping) else {}
        up, down = _finite(clusters.get("UP")), _finite(clusters.get("DOWN"))
        entropy = _finite(multiverse.get("future_entropy"), 1.0)
        confidence = _clip(abs(up - down) * (1.0 - entropy) * (1.0 - unknown_mass), 0.0, 1.0)
        bias = "NO_EDGE" if confidence < 0.12 else "LONG_BIAS" if up > down else "SHORT_BIAS"
        return {
            "navigation": "STATE_ESTIMATED",
            "guidance": bias,
            "control": "SHADOW_ONLY",
            "confidence": confidence,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def snapshot(self, asset: str = "") -> Dict[str, Any]:
        with self._lock:
            retrieval_ts = time.time()
            try:
                status = self.port.status()
            except Exception as ex:
                return self._empty(f"portfolio status unavailable: {type(ex).__name__}: {ex}")
            if not isinstance(status, Mapping):
                return self._empty("portfolio status unavailable")
            observed = self._observe(status, retrieval_ts)
            if not observed:
                return self._empty("no observed assets")
            symbol = str(asset or next(iter(observed))).upper()
            if symbol not in observed:
                return self._empty(f"unknown observed asset {symbol}")
            poss = self._possibility_snapshot(symbol)
            activity = self._chronon_activity(symbol, poss)
            self._tau_total[symbol] += activity["activity"]
            graph = self._causal_graph(symbol)
            multitime = self._multitime(symbol, activity, graph, poss)
            geometry = self._geometry(symbol, graph)
            renorm = self._renormalization(symbol)
            koopman = self._koopman(symbol)
            signature = self._path_signature(symbol)
            density = self._density_state(symbol, graph, koopman, poss)
            phase = self._phase_transition(symbol, geometry, density, graph)
            laws = self._symbolic_laws(symbol, graph)
            fracture = self._impossible_state(symbol, geometry)
            multiverse = self._multiverse(symbol, density, geometry, graph, poss)
            hist_n = len(self._history[symbol])
            support_unknown = _clip(1.0 - hist_n / 96.0, 0.0, 1.0)
            density_unknown = _finite(density.get("normalized_entropy"), 1.0)
            fracture_unknown = _clip((_finite(fracture.get("distance_sigma")) - 1.5) / 3.0, 0.0, 1.0) if fracture.get("distance_sigma") is not None else 0.5
            unknown_mass = _clip(0.45 * support_unknown + 0.35 * density_unknown + 0.20 * fracture_unknown, 0.0, 1.0)
            counterfactuals = self._counterfactuals(multiverse, graph, poss)
            guidance = self._guidance(density, multiverse, unknown_mass)
            return {
                "schema_version": self.SCHEMA_VERSION,
                "generated_at": _utc_now(),
                "asset": symbol,
                "authority": {
                    "research_only": True,
                    "shadow_only": True,
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                    "broker_authority": False,
                },
                "truth_contract": {
                    "physics_literalism": False,
                    "quantum_market_claim": False,
                    "future_data_used": False,
                    "structural_causality_proven": False,
                    "scenario_probabilities_calibrated": False,
                    "unknowns_explicit": True,
                },
                "time_boundary": {
                    "event_time": retrieval_ts,
                    "retrieval_time": retrieval_ts,
                    "availability_time": retrieval_ts,
                    "causal_integrity": "PASS",
                },
                "chronon": {
                    "market_proper_time": self._tau_total[symbol],
                    "activity": activity,
                    "definition": "one unit of accumulated informational activity, not wall-clock time",
                },
                "multitime": multitime,
                "geometry": geometry,
                "causal_cone": graph,
                "renormalization": renorm,
                "koopman": koopman,
                "path_signature": signature,
                "density_state": density,
                "phase_transition": phase,
                "symbolic_physics": laws,
                "reality_fracture": fracture,
                "multiverse": multiverse,
                "counterfactual_shadows": counterfactuals,
                "epistemic_unknown_mass": unknown_mass,
                "gnc": guidance,
                "observations": hist_n,
            }

    def _empty(self, detail: str) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "generated_at": _utc_now(),
            "asset": None,
            "authority": {
                "research_only": True,
                "shadow_only": True,
                "execution_authorized": False,
                "production_decision_authorized": False,
                "broker_authority": False,
            },
            "truth_contract": {
                "physics_literalism": False,
                "quantum_market_claim": False,
                "future_data_used": False,
                "structural_causality_proven": False,
                "scenario_probabilities_calibrated": False,
                "unknowns_explicit": True,
            },
            "status": "NO_STATE",
            "detail": detail,
            "gnc": {
                "guidance": "NO_EDGE",
                "control": "SHADOW_ONLY",
                "confidence": 0.0,
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
        }
