# Grok (xAI) — 2026-09-20. Whole file. Local process supervisor. No containers.
"""Spawn the engine (and optional bridge), restart on crash, stop cleanly.

Health is GET /healthz on loopback. The engine binds 127.0.0.1 on purpose
(DNS-rebinding). This is a plant on the same machine, not a cloud deploy.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .downloads import ingest_downloads
from .drop import ingest_drop
from .layout import ensure, plant_root, repo_root


def health_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def wait_health(url: str, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if health_ok(url):
            return True
        time.sleep(0.4)
    return False


@dataclass
class Service:
    name: str
    argv: List[str]
    health_url: str
    cwd: str
    env: Dict[str, str] = field(default_factory=dict)
    pidfile: str = ""
    popen: Optional[subprocess.Popen] = None
    restarts: int = 0
    last_exit: Optional[int] = None


def _write_pid(path: str, pid: int) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="ascii") as fh:
        fh.write(str(pid))


def _read_pid(path: str) -> Optional[int]:
    try:
        return int(open(path, encoding="ascii").read().strip())
    except (OSError, ValueError):
        return None


def _kill_pid(pid: int) -> None:
    if pid <= 0:
        return
    try:
        if os.name == "nt":
            subprocess.call(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate(proc: subprocess.Popen, grace: float = 8.0) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


class Plant:
    def __init__(self, root: Optional[str] = None, *, repo: Optional[str] = None):
        self.root = plant_root(root)
        self.repo = repo_root(repo)
        ensure(self.root)
        self.services: Dict[str, Service] = {}
        self._stop = False

    def add(self, svc: Service) -> None:
        self.services[svc.name] = svc

    def spawn(self, svc: Service) -> None:
        env = os.environ.copy()
        env.update(svc.env)
        env["ICARUS_HOME"] = self.root
        log = open(os.path.join(self.root, "logs", f"{svc.name}.log"), "ab")
        kw: Dict[str, object] = dict(
            cwd=svc.cwd,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        # Grok (xAI) — 2026-09-20: start_new_session is POSIX-only; Windows needs a new process group.
        if os.name == "nt":
            kw["creationflags"] = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        else:
            kw["start_new_session"] = True
        svc.popen = subprocess.Popen(svc.argv, **kw)  # type: ignore[arg-type]
        if svc.pidfile:
            _write_pid(svc.pidfile, svc.popen.pid)

    def stop_one(self, svc: Service) -> None:
        if svc.popen is not None:
            _terminate(svc.popen)
            svc.last_exit = svc.popen.poll()
            svc.popen = None
        pid = _read_pid(svc.pidfile) if svc.pidfile else None
        if pid and _alive(pid):
            _kill_pid(pid)
        if svc.pidfile and os.path.isfile(svc.pidfile):
            os.remove(svc.pidfile)

    def stop(self) -> None:
        self._stop = True
        for svc in self.services.values():
            self.stop_one(svc)
        plant_pid = os.path.join(self.root, "run", "plant.pid")
        if os.path.isfile(plant_pid):
            os.remove(plant_pid)

    def reap_and_restart(self, now: Optional[float] = None) -> None:
        now = now or time.time()
        for svc in self.services.values():
            if svc.popen is None:
                continue
            code = svc.popen.poll()
            if code is None:
                continue
            svc.last_exit = code
            svc.popen = None
            if self._stop:
                continue
            svc.restarts += 1
            delay = min(30.0, 2 ** min(svc.restarts, 5))
            time.sleep(delay)
            if self._stop:
                return
            self.spawn(svc)

    def status(self) -> Dict[str, object]:
        items = []
        for svc in self.services.values():
            pid = svc.popen.pid if svc.popen and svc.popen.poll() is None else _read_pid(svc.pidfile)
            items.append({
                "name": svc.name,
                "pid": pid,
                "alive": bool(pid and _alive(pid)),
                "health": health_ok(svc.health_url) if svc.health_url else None,
                "health_url": svc.health_url,
                "restarts": svc.restarts,
                "last_exit": svc.last_exit,
            })
        return {"root": self.root, "repo": self.repo, "ok": all(i["alive"] and i["health"] for i in items if i["health_url"]), "services": items}

    def loop(self, *, poll: float = 5.0, drop: bool = True, downloads: bool = True) -> None:
        _write_pid(os.path.join(self.root, "run", "plant.pid"), os.getpid())
        try:
            while not self._stop:
                if drop:
                    try:
                        ingest_drop(self.root)
                    except Exception:
                        pass
                    if downloads:
                        try:
                            ingest_downloads(self.root)
                        except Exception:
                            pass
                self.reap_and_restart()
                try:
                    write_status(self.root, self.status())
                except Exception:
                    pass
                time.sleep(poll)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def default_engine_service(root: str, repo: str, *, assets: str = "NQ", port: int = 8791,
                           token: str = "icarus", offline: bool = False, preset: str = "NQ-20m-ultracoded") -> Service:
    ensure(root)
    env = {
        "ICARUS_HOME": root,
        "ICARUS_FEED": "file" if offline else os.environ.get("ICARUS_FEED", "yahoo"),
        "PYTHONPATH": repo + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }
    db = os.path.join(root, "icarus_engine.db")
    argv = [
        sys.executable, "-m", "icarus_engine.cli", "run",
        "--assets", assets, "--port", str(port), "--token", token,
        "--preset", preset, "--db", db,
    ]
    if offline:
        argv += ["--feed", "file", "--roll", "none"]
    return Service(
        name="engine",
        argv=argv,
        health_url=f"http://127.0.0.1:{port}/healthz",
        cwd=repo,
        env=env,
        pidfile=os.path.join(root, "run", "engine.pid"),
    )


def default_bridge_service(root: str, repo: str, *, port: int = 8787) -> Service:
    ensure(root)
    env = {
        "ICARUS_HOME": root,
        "PYTHONPATH": repo + os.pathsep + os.environ.get("PYTHONPATH", ""),
        "HOST": "127.0.0.1",
        "PORT": str(port),
    }
    argv = [sys.executable, "-m", "icarus_bridge.cli", "serve", "--tunnel", "none", "--port", str(port)]
    return Service(
        name="bridge",
        argv=argv,
        health_url=f"http://127.0.0.1:{port}/healthz",
        cwd=repo,
        env=env,
        pidfile=os.path.join(root, "run", "bridge.pid"),
    )


def write_status(root: str, payload: Dict[str, object]) -> None:
    path = os.path.join(root, "run", "status.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
