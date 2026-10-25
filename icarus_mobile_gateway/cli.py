from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .proxy import UpstreamClient, UpstreamError
from .server import make_server
from .store import DeviceStore


def _root(value: str | None) -> Path:
    return Path(value or os.environ.get("ICARUS_HOME") or os.getcwd()).expanduser().resolve()


def _is_loopback(host: str) -> bool:
    return host.strip().lower() in {"127.0.0.1", "localhost", "::1"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="icarus-mobile-gateway")
    parser.add_argument("--root", help="ICARUS data root; defaults to ICARUS_HOME or cwd")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="serve the read-only mobile gateway")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8792)
    serve.add_argument("--engine", default="http://127.0.0.1:8791")
    serve.add_argument("--session-ttl", type=int, default=900)
    serve.add_argument("--snapshot-interval", type=float, default=2.0)
    serve.add_argument("--allow-direct-bind", action="store_true", help="allow non-loopback bind; requires your own TLS/network controls")

    doctor = sub.add_parser("doctor", help="check gateway configuration and engine reachability")
    doctor.add_argument("--engine", default="http://127.0.0.1:8791")

    sub.add_parser("devices", help="list paired mobile devices")

    revoke = sub.add_parser("revoke", help="revoke a paired device")
    revoke.add_argument("device_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _root(args.root)
    store = DeviceStore(root / "mobile_gateway" / "devices.json")

    if args.command == "devices":
        print(json.dumps({"devices": store.list_devices()}, indent=2))
        return 0

    if args.command == "revoke":
        ok = store.revoke(args.device_id)
        print(json.dumps({"device_id": args.device_id, "revoked": ok}))
        return 0 if ok else 1

    pairing = os.environ.get("ICARUS_MOBILE_PAIRING_SECRET", "")
    admin = os.environ.get("ICARUS_ADMIN_TOKEN", "")

    if args.command == "doctor":
        report = {
            "root": str(root),
            "pairing_secret_configured": len(pairing) >= 16,
            "admin_token_configured": bool(admin),
            "engine": args.engine,
            "engine_ok": False,
        }
        try:
            health = UpstreamClient(args.engine, admin_token=admin).health()
            report["engine_ok"] = bool(isinstance(health, dict) and health.get("ok"))
            report["engine_health"] = health
        except Exception as ex:
            report["engine_error"] = f"{type(ex).__name__}: {ex}"
        report["ok"] = bool(report["pairing_secret_configured"] and report["admin_token_configured"] and report["engine_ok"])
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1

    if args.command == "serve":
        if not _is_loopback(args.host) and not args.allow_direct_bind:
            print("Refusing non-loopback bind. Put a TLS reverse proxy in front of 127.0.0.1:8792 or pass --allow-direct-bind intentionally.", file=sys.stderr)
            return 2
        if len(pairing) < 16:
            print("Set ICARUS_MOBILE_PAIRING_SECRET to at least 16 characters.", file=sys.stderr)
            return 2
        if not admin:
            print("Set ICARUS_ADMIN_TOKEN so the gateway can read protected ICARUS intelligence surfaces.", file=sys.stderr)
            return 2
        try:
            srv = make_server(
                args.host,
                args.port,
                data_dir=root,
                engine_url=args.engine,
                admin_token=admin,
                pairing_secret=pairing,
                session_ttl=args.session_ttl,
                snapshot_interval=args.snapshot_interval,
            )
        except (ValueError, UpstreamError) as ex:
            print(str(ex), file=sys.stderr)
            return 2
        print(f"ICARUS mobile gateway listening on http://{args.host}:{args.port} -> {args.engine}")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            srv.server_close()
        return 0

    return 2
