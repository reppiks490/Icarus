# Grok (xAI) — 2026-09-20. Whole file.
"""icarus-plant — local paper-trading plant.

  icarus-plant setup  [--open] [--root DIR]     # print the dummy checklist, write NEXT.txt
  icarus-plant init   [--root DIR]
  icarus-plant start  [--assets NQ] [--offline] [--bridge] [--root DIR]
  icarus-plant stop   [--root DIR]
  icarus-plant status [--root DIR]
  icarus-plant ingest-drop [--root DIR]
  icarus-plant open-drop   [--root DIR]         # Explorer / Finder on history/drop/
  icarus-plant doctor [--root DIR]
  icarus-plant paper-export [--out FILE] [--live-only]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import time
from typing import Optional

from icarus_engine import brand
from .downloads import ingest_downloads
from .drop import ingest_drop
from .guide import open_drop, preflight, steps, write_next_txt
from .layout import ensure, plant_root, repo_root
from .supervisor import (
    Plant,
    Service,
    _alive,
    _kill_pid,
    _read_pid,
    default_bridge_service,
    default_engine_service,
    health_ok,
    wait_health,
    write_status,
)



def _load_root_env(root: str) -> None:
    """Load simple KEY=VALUE entries from the plant-owned .env without overwriting process env."""
    path = os.path.join(root, ".env")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
    except OSError:
        return


def cmd_init(args: argparse.Namespace) -> int:
    root = plant_root(args.root)
    paths = ensure(root)
    repo = repo_root()
    for name in ("presets", "pine"):
        src = os.path.join(repo, name)
        dst = os.path.join(root, name)
        if os.path.isdir(src) and os.path.abspath(src) != os.path.abspath(dst):
            os.makedirs(dst, exist_ok=True)
            for fn in os.listdir(src):
                s, d = os.path.join(src, fn), os.path.join(dst, fn)
                if os.path.isfile(s) and not os.path.exists(d):
                    shutil.copy2(s, d)
    env_src = os.path.join(repo, "icarus_bridge", ".env.example")
    env_dst = os.path.join(root, ".env")
    if os.path.isfile(env_src) and not os.path.isfile(env_dst):
        shutil.copy2(env_src, env_dst)
        print(f"wrote {env_dst} (fill WEBHOOK_SECRET / Alpaca only if you run the bridge)")
    print(f"plant root {root}")
    print(f"  drop TV exports in {paths['history/drop']}")
    nxt = write_next_txt(root)
    print(f"  wrote {nxt}")
    print("  icarus-plant setup --open")
    print("  icarus-plant start --assets NQ --offline")
    return 0


def cmd_ingest_drop(args: argparse.Namespace) -> int:
    recs = ingest_drop(args.root)
    if getattr(args, "downloads", False):
        recs = list(recs) + ingest_downloads(args.root)
    if not recs:
        print("drop/ is empty" + (" (Downloads had no new chart CSVs)" if getattr(args, "downloads", False) else ""))
        return 0
    for r in recs:
        extra = f"  (+{r.get('added', r['bars'])} new, {r['bars']} total)" if r.get("merged_from") else ""
        src = f"  [{os.path.basename(r['from_downloads'])}]" if r.get("from_downloads") else ""
        print(f"  {r['symbol']} {r['minutes']}m  {r['bars']} bars -> {r['dest']}{extra}{src}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    root = plant_root(args.root)
    ensure(root)
    _load_root_env(root)
    repo = repo_root()
    engine_url = f"http://127.0.0.1:{args.engine_port}/healthz"
    bridge_url = f"http://127.0.0.1:{args.bridge_port}/healthz"
    plant_pid = _read_pid(os.path.join(root, "run", "plant.pid"))
    plant_alive = bool(plant_pid and _alive(plant_pid))
    if health_ok(engine_url):
        if not plant_alive:
            print(f"engine is healthy at {engine_url.replace('/healthz', '/')} but no live plant supervisor owns it.")
            print("  refusing to claim the plant is started; stop the leftover engine, then start the plant again.")
            return 1
        if args.bridge and not health_ok(bridge_url):
            print(f"engine already running: {engine_url.replace('/healthz', '/')}")
            print("  --bridge was requested but the bridge is not running.")
            print("  stop the plant, then start again with --bridge so one supervisor owns both services.")
            return 1
        print(f"already running: {engine_url.replace('/healthz', '/')}  token={args.token}")
        print("  this does not change feed/assets/preset/token. Stop the plant, then start again to change launch configuration.")
        return 0
    if plant_alive:
        print(f"plant already running pid={plant_pid} at {root}")
        return 0
    recs = ingest_drop(root)
    if not args.no_downloads:
        recs = list(recs) + ingest_downloads(root)
    for r in recs:
        extra = f"  (+{r.get('added', r['bars'])} new, {r['bars']} total)" if r.get("merged_from") else ""
        print(f"  ingested {r['symbol']} {r['minutes']}m  {r['bars']} bars -> {r['dest']}{extra}")
    for i in preflight(root):
        if i["level"] != "ok":
            print(f"  !! {i['name']} — {i['detail']}")
    selected_feed = "file" if args.offline else args.feed
    if args.offline and args.feed not in ("yahoo", "file"):
        raise SystemExit("--offline cannot be combined with --feed databento")
    if selected_feed == "databento":
        if importlib.util.find_spec("databento") is None:
            raise SystemExit("Databento SDK is not installed. Run: py -3 -m pip install -e \".[databento]\"")
        if not os.environ.get("DATABENTO_API_KEY"):
            raise SystemExit("DATABENTO_API_KEY is required for --feed databento")
    plant = Plant(root, repo=repo)
    plant.add(default_engine_service(
        root, repo, assets=args.assets, port=args.engine_port,
        token=args.token, offline=args.offline, preset=args.preset, feed=selected_feed,
    ))
    if args.bridge:
        plant.add(default_bridge_service(root, repo, port=args.bridge_port))
    os.environ["ICARUS_HOME"] = root
    os.environ["ICARUS_FEED"] = selected_feed
    os.makedirs(os.path.join(root, "run"), exist_ok=True)
    with open(os.path.join(root, "run", "feed.txt"), "w", encoding="ascii") as fh:
        fh.write(selected_feed + "\n")
    for svc in plant.services.values():
        plant.spawn(svc)
        print(f"started {svc.name} pid={svc.popen.pid if svc.popen else '?'}  {svc.health_url}")
    print(f"plant {root}  Ctrl+C to stop")
    print("  drop Supercharts CSVs in history/drop/ — ingested every few seconds")
    print("  CSVs already in Downloads/Desktop are pulled automatically (registry symbols only)")
    if selected_feed == "file":
        print("  ICARUS_FEED=file — Yahoo is not contacted; live bars only arrive via drop ingest")
    elif selected_feed == "databento":
        print("  ICARUS_FEED=databento — CME futures use Databento GLBX.MDP3 continuous live data")
    engine = plant.services.get("engine")
    if engine and engine.health_url:
        if wait_health(engine.health_url, timeout=45):
            dash = engine.health_url.replace("/healthz", "/")
            print(f"  dashboard live: {dash}  token={args.token}")
            if not args.no_browser:
                import webbrowser
                webbrowser.open(dash)
        else:
            print("  engine has not answered /healthz yet — check logs/engine.log")
    try:
        plant.loop(poll=args.poll, downloads=not args.no_downloads)
    finally:
        write_status(root, plant.status())
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    root = plant_root(args.root)
    pf = os.path.join(root, "run", "plant.pid")
    pid = _read_pid(pf)
    if pid and _alive(pid):
        _kill_pid(pid)
        for _ in range(40):
            if not _alive(pid):
                break
            time.sleep(0.25)
        if _alive(pid):
            print(f"stop requested but plant pid={pid} is still alive at {root}", file=sys.stderr)
            print("  refusing to claim success or blindly force-kill a PID that could have been reused.", file=sys.stderr)
            return 1
        print(f"stopped plant pid={pid} at {root}")
        return 0
    plant = Plant(root)
    for name in ("engine", "bridge"):
        plant.add(Service(
            name=name, argv=[], health_url="", cwd=root,
            pidfile=os.path.join(root, "run", f"{name}.pid"),
        ))
    plant.stop()
    print(f"stopped leftover children at {root}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = plant_root(args.root)
    plant = Plant(root)
    engine_port = args.engine_port
    bridge_port = args.bridge_port
    engine_pf = os.path.join(root, "run", "engine.pid")
    bridge_pf = os.path.join(root, "run", "bridge.pid")
    plant.add(Service(
        name="engine", argv=[], health_url=f"http://127.0.0.1:{engine_port}/healthz",
        cwd=root, pidfile=engine_pf,
    ))
    # The bridge is opt-in. Do not mark a healthy engine-only plant as failed
    # just because no bridge service was ever launched.
    if os.path.isfile(bridge_pf):
        plant.add(Service(
            name="bridge", argv=[], health_url=f"http://127.0.0.1:{bridge_port}/healthz",
            cwd=root, pidfile=bridge_pf,
        ))
    rep = plant.status()
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0 if rep["ok"] else 1
    print(f"plant {rep['root']}")
    feed_path = os.path.join(root, "run", "feed.txt")
    if os.path.isfile(feed_path):
        print(f"  feed {open(feed_path, encoding='ascii').read().strip()}")
    for s in rep["services"]:
        mark = "OK " if s["alive"] and s["health"] else ("?? " if s["alive"] else "xx ")
        print(f"  [{mark}] {s['name']} pid={s['pid']} health={s['health']} {s['health_url']}")
    return 0 if rep["ok"] else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    from icarus_engine.doctor import inspect
    root = plant_root(args.root)
    ensure(root)
    os.environ["ICARUS_HOME"] = root
    recs = ingest_drop(root)
    if recs:
        print(f"ingested {len(recs)} drop file(s)")
    rep = inspect(root)
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0 if rep["ok"] else 1
    print(f"ICARUS plant doctor  root={root}")
    for i in rep["items"]:
        mark = "OK " if i["ok"] else ("!! " if i["level"] == "warn" else "XX ")
        print(f"  [{mark}] {i['name']} — {i['detail']}")
    return 0 if rep["ok"] else 1


def cmd_paper_export(args: argparse.Namespace) -> int:
    from icarus_engine.runtime import export_paper_book
    root = plant_root(args.root)
    db = os.path.join(root, "icarus_engine.db")
    if not os.path.isfile(db):
        print(f"no journal at {db}", file=sys.stderr)
        return 1
    out = args.out or os.path.join(root, "paper-trades.csv")
    n = export_paper_book(db, out, live_only=bool(args.live_only))
    print(f"{n} paper trades -> {out}")
    print("Icarus emulator book. Not a broker statement.")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    root = plant_root(args.root)
    ensure(root)
    write_next_txt(root)
    print(steps(root))
    for i in preflight(root):
        mark = "OK " if i["ok"] and i["level"] == "ok" else "!! "
        print(f"  [{mark}] {i['name']} — {i['detail']}")
    if args.open:
        drop = open_drop(root)
        print(f"opened {drop}")
    return 0


def cmd_open_drop(args: argparse.Namespace) -> int:
    print(open_drop(args.root))
    return 0


def _configure_console_encoding() -> None:
    """Use UTF-8 for ICARUS CLI text on Windows consoles and CI pipes."""
    if not sys.platform.startswith("win"):
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                pass


def main(argv: Optional[list] = None) -> int:
    _configure_console_encoding()
    p = argparse.ArgumentParser(prog="icarus-plant", description=f"{brand.NAME} - local paper-trading plant")
    p.add_argument("--root", default=None, help="plant data dir (else $ICARUS_HOME else cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_root_option(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--root",
            default=argparse.SUPPRESS,
            help="plant data dir (else $ICARUS_HOME else cwd)",
        )

    i = sub.add_parser("init", help="create history/drop, run, logs under the plant root")
    add_root_option(i)
    i.set_defaults(fn=cmd_init)

    u = sub.add_parser("setup", help="print numbered next steps (and write NEXT.txt)")
    add_root_option(u)
    u.add_argument("--open", action="store_true", help="open history/drop/ in Explorer / Finder")
    u.set_defaults(fn=cmd_setup)

    od = sub.add_parser("open-drop", help="open history/drop/ in the OS file manager")
    add_root_option(od)
    od.set_defaults(fn=cmd_open_drop)

    d = sub.add_parser("ingest-drop", help="history/drop/*.csv → history/{SYM}_{N}m.csv")
    add_root_option(d)
    d.add_argument("--downloads", action="store_true", help="also pull chart CSVs from Downloads/Desktop")
    d.set_defaults(fn=cmd_ingest_drop)

    s = sub.add_parser("start", help="supervise engine (+ optional bridge) in the foreground")
    add_root_option(s)
    s.add_argument("--assets", default="NQ")
    s.add_argument("--preset", default="NQ-20m-ultracoded")
    s.add_argument("--offline", action="store_true", help="FileFeed only — no network market feed. Alias for --feed file.")
    s.add_argument("--feed", default="yahoo", choices=["yahoo", "file", "databento"], help="market-data feed for the engine; databento requires DATABENTO_API_KEY")
    s.add_argument("--bridge", action="store_true", help="also supervise icarus-bridge (needs fastapi)")
    s.add_argument("--engine-port", type=int, default=8791)
    s.add_argument("--bridge-port", type=int, default=8787)
    s.add_argument("--token", default="icarus")
    s.add_argument("--poll", type=float, default=5.0)
    s.add_argument("--no-browser", action="store_true", help="do not open the dashboard")
    s.add_argument("--no-downloads", action="store_true", help="do not scan Downloads/Desktop for CSVs")
    s.set_defaults(fn=cmd_start)

    t = sub.add_parser("stop", help="SIGTERM engine/bridge pids recorded under run/")
    add_root_option(t)
    t.set_defaults(fn=cmd_stop)

    u = sub.add_parser("status", help="pid files + /healthz")
    add_root_option(u)
    u.add_argument("--engine-port", type=int, default=8791)
    u.add_argument("--bridge-port", type=int, default=8787)
    u.add_argument("--json", action="store_true")
    u.set_defaults(fn=cmd_status)

    o = sub.add_parser("doctor", help="ingest-drop then icarus-engine doctor against the plant root")
    add_root_option(o)
    o.add_argument("--json", action="store_true")
    o.set_defaults(fn=cmd_doctor)

    pe = sub.add_parser("paper-export", help="CSV of the local paper book (not a broker statement)")
    add_root_option(pe)
    pe.add_argument("--out", default=None)
    pe.add_argument("--live-only", action="store_true")
    pe.set_defaults(fn=cmd_paper_export)

    args = p.parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
