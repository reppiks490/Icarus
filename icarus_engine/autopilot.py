"""Autonomous shadow optimizer for ICARUS.

This subsystem is intentionally separated from broker/live execution. It continuously
searches bounded strategy inputs on frozen cached data, keeps a durable best-observed
shadow configuration, and exposes every candidate/score/delta to the dashboard.

Promotion into the paper engine remains the responsibility of the existing qualified
research + activation path. This module never mutates owner input files and never
authorizes brokerage execution.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time
from datetime import datetime, timezone
from typing import Any

from .backtest import run_backtest
from .runtime import validate_values
from .strategy.meta import load_meta
from .system_audit import append_system_event


DEFAULT_CONFIG = {
    "enabled": True,
    "assets": [],
    "cadence_seconds": 15,
    "max_history": 120,
    "min_trades": 8,
    "search_chart_type": True,
    "search_session": True,
}


class TacticalAutopilot:
    """Durable autonomous shadow-search loop.

    Search is deliberately attributable: one bounded dimension changes per trial.
    That makes each result inspectable and prevents a large opaque multi-parameter
    jump from becoming the new champion merely because of one lucky replay.
    """

    def __init__(self, port):
        self.port = port
        self.root = Path(port.base_dir) / "research" / "autopilot"
        self.path = self.root / "state.json"
        self._lock = threading.RLock()
        self._cycle_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._meta = {x["name"]: x for x in load_meta() if isinstance(x, dict) and x.get("name")}

    @staticmethod
    def _copy(value):
        return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))

    def _initial(self):
        return {
            "schema": "icarus.tactical-autopilot.v1",
            "config": dict(DEFAULT_CONFIG),
            "cursor": 0,
            "asset_cursor": 0,
            "active": None,
            "champions": {},
            "history": [],
            "last_error": None,
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    def _read(self):
        if not self.path.exists():
            return self._initial()
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._initial()
        if not isinstance(state, dict):
            return self._initial()
        state["config"] = {**DEFAULT_CONFIG, **(state.get("config") or {})}
        state.setdefault("champions", {})
        state.setdefault("history", [])
        state.setdefault("cursor", 0)
        state.setdefault("asset_cursor", 0)
        state.setdefault("active", None)
        state.setdefault("last_error", None)
        return state

    def _write(self, state):
        self.root.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = time.time()
        raw = json.dumps(state, sort_keys=True, indent=2, allow_nan=False)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    @staticmethod
    def _candidate_id(payload):
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return hashlib.sha256(raw).hexdigest()[:16]

    def configure(self, partial):
        if not isinstance(partial, dict) or set(partial) - set(DEFAULT_CONFIG):
            raise ValueError("unknown autopilot configuration field")
        with self._lock:
            state = self._read()
            cfg = {**DEFAULT_CONFIG, **state["config"], **partial}
            if type(cfg["enabled"]) is not bool:
                raise ValueError("enabled must be Boolean")
            if type(cfg["assets"]) is not list or len(cfg["assets"]) > 32:
                raise ValueError("assets must be a list of at most 32 running symbols")
            assets = [str(x).upper().strip() for x in cfg["assets"]]
            if any(not x or x not in self.port.runners for x in assets) or len(set(assets)) != len(assets):
                raise ValueError("assets must be unique running symbols")
            cfg["assets"] = assets
            for key, lo, hi in (
                ("cadence_seconds", 5, 3600),
                ("max_history", 20, 1000),
                ("min_trades", 1, 10000),
            ):
                if type(cfg[key]) is not int or not lo <= cfg[key] <= hi:
                    raise ValueError(f"{key} is outside supported bounds")
            for key in ("search_chart_type", "search_session"):
                if type(cfg[key]) is not bool:
                    raise ValueError(f"{key} must be Boolean")
            state["config"] = cfg
            self._write(state)
        if cfg["enabled"]:
            self.start()
        else:
            self._stop.set()
        return self.status()

    @staticmethod
    def _bounded(value, entry, direction):
        if type(value) not in (int, float) or isinstance(value, bool):
            return None
        step = entry.get("step")
        if not isinstance(step, (int, float)) or isinstance(step, bool) or not math.isfinite(float(step)) or step <= 0:
            step = 1 if type(value) is int else max(abs(float(value)) * 0.1, 0.01)
        out = float(value) + direction * float(step)
        lo = entry.get("minval")
        hi = entry.get("maxval")
        if isinstance(lo, (int, float)) and math.isfinite(float(lo)):
            out = max(out, float(lo))
        if isinstance(hi, (int, float)) and math.isfinite(float(hi)):
            out = min(out, float(hi))
        if type(value) is int:
            out = int(round(out))
        return out

    def _eligible(self, inputs):
        dims = []
        protected = {
            "qty_contracts", "point_value", "size_mode", "risk_usd_per_trade",
            "vol_rank_bars", "vol_low_mult", "vol_mid_mult", "tide_qty",
            "use_conviction_sizing", "conv_min_mult", "conv_floor", "conv_ceiling",
        }
        for name in sorted(inputs):
            value = inputs[name]
            entry = self._meta.get(name, {})
            group = str(entry.get("group") or "").lower()
            if (
                name in protected
                or name.endswith("_qty")
                or "sizing" in group
                or name.startswith(("rate_", "htf_tf_"))
            ):
                continue
            choices = []
            if type(value) is bool:
                choices = [not value]
            elif isinstance(entry.get("options"), list):
                choices = [x for x in entry["options"] if x != value]
            elif type(value) in (int, float) and not isinstance(value, bool):
                for direction in (-1, 1):
                    candidate = self._bounded(value, entry, direction)
                    if candidate is not None and candidate != value and candidate not in choices:
                        choices.append(candidate)
            good = []
            for choice in choices[:4]:
                try:
                    validate_values({name: choice})
                except (ValueError, TypeError, OverflowError):
                    continue
                good.append(choice)
            if good:
                dims.append((name, good))
        return dims

    def _build_candidate(self, asset, state):
        runner = self.port.runners[asset]
        champion = state["champions"].get(asset)
        if champion:
            base_inputs = dict(champion["inputs"])
            chart_type = champion.get("chart_type") or runner.spec.chart_type
            session = champion.get("session")
        else:
            with runner.lock:
                base_inputs = runner.inputs.to_dict()
                chart_type = runner.spec.chart_type
            session = None

        cycle = int(state.get("cursor", 0))
        if champion is None:
            delta = {"kind": "baseline", "name": "current_engine", "from": None, "to": None}
            return {
                "asset": asset,
                "inputs": base_inputs,
                "chart_type": chart_type,
                "session": session,
                "fill_on": "real",
                "delta": delta,
                "reason": "benchmark current effective configuration",
            }

        dims = self._eligible(base_inputs)
        special = []
        if state["config"].get("search_chart_type"):
            special.append(("chart_type", ["real", "heikin_ashi"]))
        if state["config"].get("search_session"):
            special.append(("session", ["rth", "eth"]))
        search = [("input", name, choices) for name, choices in dims]
        search += [("context", name, choices) for name, choices in special]
        if not search:
            raise ValueError("no bounded autopilot search dimensions are available")

        kind, name, choices = search[cycle % len(search)]
        current = base_inputs.get(name) if kind == "input" else (chart_type if name == "chart_type" else session)
        alternatives = [x for x in choices if x != current] or list(choices)
        choice = alternatives[(cycle // max(1, len(search))) % len(alternatives)]
        inputs = dict(base_inputs)
        if kind == "input":
            inputs[name] = choice
            validate_values({name: choice})
        elif name == "chart_type":
            chart_type = choice
        elif name == "session":
            session = choice
        return {
            "asset": asset,
            "inputs": inputs,
            "chart_type": chart_type,
            "session": session,
            "fill_on": "real",
            "delta": {"kind": kind, "name": name, "from": current, "to": choice},
            "reason": f"bounded one-dimension search around champion: {name}",
        }

    @staticmethod
    def _score(result, min_trades):
        eq = result.get("equity") or []
        dd = result.get("drawdown") or []
        trades = [t for t in (result.get("trades") or []) if not t.get("open")]
        capital = float((result.get("config") or {}).get("capital") or (eq[0][1] if eq else 0) or 1.0)
        final_equity = float(eq[-1][1]) if eq else capital
        pnl = final_equity - capital
        max_dd = abs(min((float(x[1]) for x in dd), default=0.0))
        wins = sum(1 for t in trades if float(t.get("pnl") or 0.0) > 0)
        losses = [abs(float(t.get("pnl") or 0.0)) for t in trades if float(t.get("pnl") or 0.0) < 0]
        gains = [float(t.get("pnl") or 0.0) for t in trades if float(t.get("pnl") or 0.0) > 0]
        win_rate = wins / len(trades) if trades else 0.0
        gross_profit = sum(gains)
        gross_loss = sum(losses)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (3.0 if gross_profit > 0 else 0.0)
        floor = max(1.0, capital * 0.005)
        return_to_dd = pnl / max(max_dd, floor)
        sample_bonus = min(0.45, math.log1p(len(trades)) / 12.0)
        sample_penalty = max(0.0, (min_trades - len(trades)) / max(1, min_trades)) * 1.5
        pf_component = max(-0.5, min(0.5, (profit_factor - 1.0) * 0.20))
        score = return_to_dd + pf_component + (win_rate - 0.5) * 0.35 + sample_bonus - sample_penalty
        reproducibility = ((result.get("config") or {}).get("reproducibility") or {})
        if reproducibility.get("historical_scale_asof_valid") is False:
            score -= 2.0
        if not trades:
            score = -999.0
        metrics = {
            "score": round(float(score), 8),
            "pnl": round(pnl, 4),
            "max_drawdown": round(max_dd, 4),
            "return_to_drawdown": round(return_to_dd, 6),
            "win_rate": round(win_rate, 6),
            "profit_factor": round(profit_factor, 6),
            "trades": len(trades),
            "bars": int(result.get("bars") or 0),
        }
        return metrics

    def cycle_once(self):
        # Manual and background requests must never race the same shadow state.
        if not self._cycle_lock.acquire(blocking=False):
            out = self.status()
            out["cycle_busy"] = True
            out["note"] = "A Tactical Autopilot cycle is already running."
            return out
        try:
            return self._cycle_once_serial()
        finally:
            self._cycle_lock.release()

    def _cycle_once_serial(self):
        with self._lock:
            state = self._read()
            cfg = state["config"]
            assets = cfg["assets"] or [r.symbol for r in self.port.runner_list()]
            if not assets:
                raise ValueError("no running assets")
            assets = [a for a in assets if a in self.port.runners]
            if not assets:
                raise ValueError("configured autopilot assets are not running")
            asset = assets[int(state.get("asset_cursor", 0)) % len(assets)]
            runner = self.port.runners[asset]
            with runner.lock:
                if not runner.warm:
                    state["last_error"] = {"at": time.time(), "asset": asset, "detail": "asset is still warming"}
                    state["asset_cursor"] = (int(state.get("asset_cursor", 0)) + 1) % len(assets)
                    self._write(state)
                    return self.status()
            candidate = self._build_candidate(asset, state)
            candidate["id"] = self._candidate_id(candidate)
            state["active"] = {
                "candidate": candidate,
                "stage": "backtest",
                "started": time.time(),
            }
            state["cursor"] = int(state.get("cursor", 0)) + 1
            state["asset_cursor"] = (int(state.get("asset_cursor", 0)) + 1) % len(assets)
            state["last_error"] = None
            self._write(state)

        try:
            result = run_backtest(
                self.port,
                asset,
                inputs=candidate["inputs"],
                chart_type=candidate.get("chart_type"),
                fill_on="real",
                session=candidate.get("session"),
            )
            metrics = self._score(result, cfg["min_trades"])
            record = {
                "id": candidate["id"],
                "asset": asset,
                "tested_at": time.time(),
                "inputs": candidate["inputs"],
                "chart_type": candidate.get("chart_type"),
                "session": candidate.get("session"),
                "fill_on": "real",
                "delta": candidate["delta"],
                "reason": candidate["reason"],
                "metrics": metrics,
                "reproducibility": {
                    "source_config_sha256": ((result.get("config") or {}).get("reproducibility") or {}).get("source_config_sha256"),
                    "effective_config_sha256": ((result.get("config") or {}).get("reproducibility") or {}).get("effective_config_sha256"),
                    "subbars_sha256": ((result.get("config") or {}).get("reproducibility") or {}).get("subbars_sha256"),
                },
            }
            with self._lock:
                state = self._read()
                champion = state["champions"].get(asset)
                if champion is None or metrics["score"] > float((champion.get("metrics") or {}).get("score", -math.inf)):
                    record["champion"] = True
                    state["champions"][asset] = self._copy(record)
                else:
                    record["champion"] = False
                state["history"].append(record)
                state["history"] = state["history"][-int(state["config"]["max_history"]):]
                state["active"] = {
                    "candidate": candidate,
                    "stage": "complete",
                    "finished": time.time(),
                    "metrics": metrics,
                    "became_champion": record["champion"],
                }
                state["last_error"] = None
                self._write(state)
            return self.status()
        except Exception as ex:
            with self._lock:
                state = self._read()
                state["active"] = {
                    "candidate": candidate,
                    "stage": "error",
                    "finished": time.time(),
                    "error": f"{type(ex).__name__}: {ex}",
                }
                state["last_error"] = {
                    "at": time.time(), "asset": asset,
                    "type": type(ex).__name__, "detail": str(ex),
                }
                self._write(state)
            return self.status()

    def status(self):
        with self._lock:
            state = self._read()
        history = list(state.get("history") or [])
        leaderboard = sorted(
            history,
            key=lambda x: float((x.get("metrics") or {}).get("score", -math.inf)),
            reverse=True,
        )[:20]
        return {
            **state,
            "history": history[-60:],
            "leaderboard": leaderboard,
            "running": bool(self._thread and self._thread.is_alive()),
            "cycle_busy": self._cycle_lock.locked(),
            "mode": "autonomous shadow research",
            "execution_authorized": False,
            "broker_control": False,
            "live_input_mutation": False,
            "paper_input_mutation": False,
            "promotion_path": "qualified research -> dual review -> versioned paper activation",
            "score_definition": "return/drawdown + profit-factor + win-rate + sample adequacy; penalties for sparse or historically invalid evidence",
            "note": "Champion means best observed in the tested bounded search space, not a guaranteed global optimum.",
        }

    def start_background(self):
        with self._lock:
            state = self._read()
            if not state["config"]["enabled"]:
                return self.status()
        return self.start()

    def start(self):
        with self._lock:
            state = self._read()
            state["config"]["enabled"] = True
            self._write(state)
            # If stop() timed out while a replay was finishing, resume the
            # existing single worker instead of spawning a second one.
            self._stop.clear()
            if self._thread and self._thread.is_alive():
                return self.status()

            def run():
                while not self._stop.is_set():
                    try:
                        self.cycle_once()
                    except Exception as ex:
                        with self._lock:
                            state = self._read()
                            state["last_error"] = {
                                "at": time.time(), "type": type(ex).__name__, "detail": str(ex)
                            }
                            self._write(state)
                    with self._lock:
                        cadence = int(self._read()["config"]["cadence_seconds"])
                    self._stop.wait(cadence)

            self._thread = threading.Thread(
                target=run, daemon=True, name="icarus-tactical-autopilot"
            )
            self._thread.start()
        return self.status()

    def stop(self):
        with self._lock:
            state = self._read()
            state["config"]["enabled"] = False
            self._write(state)
            self._stop.set()
            thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        return self.status()

    def reset(self):
        if not self._cycle_lock.acquire(blocking=False):
            raise ValueError("cannot reset Tactical Autopilot while a cycle is active; stop it and wait for the replay to finish")
        try:
            self._stop.set()
            with self._lock:
                state = self._initial()
                state["config"]["enabled"] = False
                self._write(state)
            return self.status()
        finally:
            self._cycle_lock.release()

    def close(self):
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
