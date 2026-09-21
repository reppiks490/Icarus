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
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from typing import Optional

from .downloads import ingest_downloads
from .drop import ingest_drop
from .guide import open_drop, preflight, steps, write_next_txt
from .layout import ensure, plant_root, repo_root
from .supervisor import Plant, Service, default_bridge_service, default_engine_service, wait_health, write_status


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
    repo = repo_root()
    recs = ingest_drop(root)
    if not args.no_downloads:
        recs = list(recs) + ingest_downloads(root)
    for r in recs:
        extra = f"  (+{r.get('added', r['bars'])} new, {r['bars']} total)" if r.get("merged_from") else ""
        print(f"  ingested {r['symbol']} {r['minutes']}m  {r['bars']} bars -> {r['dest']}{extra}")
    for i in preflight(root):
        if i["level"] != "ok":
            print(f"  !! {i['name']} — {i['detail']}")
    plant = Plant(root, repo=repo)
    plant.add(default_engine_service(
        root, repo, assets=args.assets, port=args.engine_port,
        token=args.token, offline=args.offline, preset=args.preset,
    ))
    if args.bridge:
        plant.add(default_bridge_service(root, repo, port=args.bridge_port))
    os.environ["ICARUS_HOME"] = root
    if args.offline:
        os.environ["ICARUS_FEED"] = "file"
    for svc in plant.services.values():
        plant.spawn(svc)
        print(f"started {svc.name} pid={svc.popen.pid if svc.popen else '?'}  {svc.health_url}")
    print(f"plant {root}  Ctrl+C to stop")
    print("  drop Supercharts CSVs in history/drop/ — ingested every few seconds")
    print("  CSVs already in Downloads/Desktop are pulled automatically (registry symbols only)")
    if args.offline:
        print("  ICARUS_FEED=file — Yahoo is not contacted; live bars only arrive via drop ingest")
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
    plant = Plant(root)
    for name in ("engine", "bridge", "plant"):
        pf = os.path.join(root, "run", f"{name}.pid")
        plant.add(Service(name=name, argv=[], health_url="", cwd=root, pidfile=pf))
    plant.stop()
    print(f"stopped plant at {root}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = plant_root(args.root)
    plant = Plant(root)
    engine_port = args.engine_port
    bridge_port = args.bridge_port
    for name, url, pf in (
        ("engine", f"http://127.0.0.1:{engine_port}/healthz", os.path.join(root, "run", "engine.pid")),
        ("bridge", f"http://127.0.0.1:{bridge_port}/healthz", os.path.join(root, "run", "bridge.pid")),
    ):
        plant.add(Service(name=name, argv=[], health_url=url, cwd=root, pidfile=pf))
    rep = plant.status()
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0 if rep["ok"] else 1
    print(f"plant {rep['root']}")
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


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="icarus-plant", description="Icarus local paper-trading plant (Grok/xAI)")
    p.add_argument("--root", default=None, help="plant data dir (else $ICARUS_HOME else cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="create history/drop, run, logs under the plant root")
    i.set_defaults(fn=cmd_init)

    u = sub.add_parser("setup", help="print numbered next steps (and write NEXT.txt)")
    u.add_argument("--open", action="store_true", help="open history/drop/ in Explorer / Finder")
    u.set_defaults(fn=cmd_setup)

    od = sub.add_parser("open-drop", help="open history/drop/ in the OS file manager")
    od.set_defaults(fn=cmd_open_drop)

    d = sub.add_parser("ingest-drop", help="history/drop/*.csv → history/{SYM}_{N}m.csv")
    d.add_argument("--downloads", action="store_true", help="also pull chart CSVs from Downloads/Desktop")
    d.set_defaults(fn=cmd_ingest_drop)

    s = sub.add_parser("start", help="supervise engine (+ optional bridge) in the foreground")
    s.add_argument("--assets", default="NQ")
    s.add_argument("--preset", default="NQ-20m-ultracoded")
    s.add_argument("--offline", action="store_true", help="FileFeed only — no Yahoo. Live bars come from drop ingest.")
    s.add_argument("--bridge", action="store_true", help="also supervise icarus-bridge (needs fastapi)")
    s.add_argument("--engine-port", type=int, default=8791)
    s.add_argument("--bridge-port", type=int, default=8787)
    s.add_argument("--token", default="icarus")
    s.add_argument("--poll", type=float, default=5.0)
    s.add_argument("--no-browser", action="store_true", help="do not open the dashboard")
    s.add_argument("--no-downloads", action="store_true", help="do not scan Downloads/Desktop for CSVs")
    s.set_defaults(fn=cmd_start)

    t = sub.add_parser("stop", help="SIGTERM engine/bridge pids recorded under run/")
    t.set_defaults(fn=cmd_stop)

    u = sub.add_parser("status", help="pid files + /healthz")
    u.add_argument("--engine-port", type=int, default=8791)
    u.add_argument("--bridge-port", type=int, default=8787)
    u.add_argument("--json", action="store_true")
    u.set_defaults(fn=cmd_status)

    o = sub.add_parser("doctor", help="ingest-drop then icarus-engine doctor against the plant root")
    o.add_argument("--json", action="store_true")
    o.set_defaults(fn=cmd_doctor)

    args = p.parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
