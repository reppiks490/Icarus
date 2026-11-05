"""Explicit owner NQ-default migration; never starts feeds, runners or a broker.

The operator runs this only after a stopped-state backup. A separate bounded
loopback capture can preserve live NQ settings before shutdown. Private settings
and captures stay in the private root; receipts contain hashes, never tokens.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import sys
import time
import uuid
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from .access_control import resolve_owner_token

SCHEMA = "icarus-owner-restart-defaults-v1"
CAPTURE_SCHEMA = "icarus-current-nq-capture-v1"
TEMPLATE_FILE = "restart-defaults.json"
RECEIPT_FILE = "restart-defaults-receipt.json"
DEFAULT_PRESET = "NQ-20m-ultracoded"
_CHART_KEYS = ("timeframe", "chart_type", "fill_on", "security_source")
_MAX_JSON = 2 * 1024 * 1024
EXCEPTION_ASSETS = frozenset({"ETH", "SOL"})


def _bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _safe(path):
    path = Path(path).expanduser().absolute()
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        is_reparse = bool(getattr(info, "st_file_attributes", 0) & reparse_point)
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()) or is_reparse:
            raise ValueError("settings path must not follow a symlink or junction")
    # Do not compare realpath(path) with path here: Windows expands valid 8.3
    # short names during realpath, which is not evidence of a symlink/junction.
    return path


def _read(path):
    path = _safe(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_JSON:
        raise ValueError("settings must be a bounded regular JSON file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        opened = os.fstat(handle.fileno())
        if (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError("settings file changed during open")
        raw = handle.read(_MAX_JSON + 1)
    if len(raw) > _MAX_JSON:
        raise ValueError("settings JSON exceeds the bounded size")
    return raw


def _decode_json(raw, path):
    try:
        result = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise ValueError("settings file is not valid JSON: " + Path(path).name) from None
    if not isinstance(result, dict):
        raise ValueError("settings JSON must be an object: " + Path(path).name)
    return result


def _json(path, *, required=False):
    raw = _read(path)
    if raw is None:
        if required:
            raise ValueError("required settings file is missing: " + Path(path).name)
        return {}
    return _decode_json(raw, path)


def _verify_sources(originals):
    for path, original in originals.items():
        if _read(path) != original:
            raise ValueError("NQ baseline source changed after it was captured: " + Path(path).name)


def _validate_baseline(value):
    from .assets import validate_chart_config
    from .runtime import validate_values
    from .strategy.inputs import Inputs
    if not isinstance(value, dict) or not isinstance(value.get("inputs"), dict):
        raise ValueError("complete NQ baseline is required")
    inputs = copy.deepcopy(value["inputs"])
    if set(inputs) != set(Inputs.__dataclass_fields__):
        raise ValueError("NQ baseline must contain every declared strategy input")
    validate_values(inputs)
    chart = validate_chart_config(value.get("chart"))
    if set(chart) != set(_CHART_KEYS):
        raise ValueError("complete NQ chart settings are required")
    session = str(value.get("session", "")).lower()
    if session not in ("rth", "eth"):
        raise ValueError("actual NQ RTH/ETH session is required")
    if value.get("basis") not in {"saved_main_nq_resolution", "captured_live_main_nq"}:
        raise ValueError("NQ baseline requires an explicit saved or live capture basis")
    if value["basis"] == "captured_live_main_nq":
        stamp = value.get("captured_at_ns")
        if type(stamp) is not int or stamp <= 0 or stamp > time.time_ns() + 5_000_000_000:
            raise ValueError("current NQ capture timestamp is invalid")
    return {**copy.deepcopy(value), "inputs": inputs, "chart": chart, "session": session}


def read_default_template(base_dir):
    value = _json(Path(base_dir) / TEMPLATE_FILE)
    if not value and _read(Path(base_dir) / TEMPLATE_FILE) is None:
        return None
    if value.get("schema_version") != SCHEMA or value.get("execution_authorized") is not False:
        raise ValueError("owner restart-default template identity is invalid")
    value["baseline"] = _validate_baseline(value.get("baseline"))
    return value


def owner_default_overrides(base_dir, symbol):
    """Startup defaults; explicit later per-asset edits retain normal precedence."""
    template = read_default_template(base_dir)
    if template is None:
        return {}
    baseline = template["baseline"]
    result = copy.deepcopy(baseline["inputs"])
    meta = {**baseline["chart"], "session": baseline["session"]}
    if str(symbol).strip().upper() in {
        "ETH", "ETHUSD", "COINBASE:ETHUSD",
        "SOL", "SOLUSD", "COINBASE:SOLUSD",
    }:
        result.update(qty_contracts=25, use_session=False)
        meta.update(timeframe="30", session="eth")
    result["_meta"] = meta
    return result


def ensure_stopped(root, port=8791):
    from .process_identity import identity
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("a valid runtime port is required")
    root = _safe(root)
    for name in ("plant", "engine", "bridge"):
        raw = _read(root / "run" / (name + ".pid"))
        if raw is not None:
            try:
                pid = int(raw.decode("ascii").strip())
            except (ValueError, UnicodeError):
                raise ValueError("cannot verify recorded " + name + " PID") from None
            if identity(pid) is not False:
                raise ValueError(name + " is still running or its identity is unverified")
    with socket.socket() as probe:
        if os.name != "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise ValueError("runtime port is occupied; stop its owning launcher first") from None


def _atomic_write(path, data):
    path = _safe(path)
    _safe(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with os.fdopen(os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600), "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _safe(path)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _saved_baseline(root, profile, preset, source_originals):
    from .assets import REGISTRY
    from .runtime import apply_spec_meta, preset_path, resolve_inputs
    # The user's current saved NQ record is mandatory: do not quietly substitute
    # stock dataclass/preset values when the owner asked for the current NQ.
    source_files = [root / "inputs.json", root / "inputs.NQ.json", root / TEMPLATE_FILE]
    if preset:
        source_files.insert(0, Path(preset_path(str(root), preset)))
    source_originals.update({str(path): _read(path) for path in source_files})
    if source_originals[str(root / "inputs.NQ.json")] is None:
        raise ValueError("required settings file is missing: inputs.NQ.json")
    _decode_json(source_originals[str(root / "inputs.NQ.json")], root / "inputs.NQ.json")
    if preset:
        preset_file = Path(preset_path(str(root), preset))
        if source_originals[str(preset_file)] is None:
            raise ValueError("required NQ baseline preset is missing")
        _decode_json(source_originals[str(preset_file)], preset_file)
    spec = copy.deepcopy(REGISTRY["NQ"])
    inputs, meta, sources = resolve_inputs(spec, str(root), profile, preset)
    spec = apply_spec_meta(spec, meta)
    _verify_sources(source_originals)
    evidence = {str(Path(path).relative_to(root)): _digest(raw)
                for path, raw in source_originals.items() if raw is not None}
    return _validate_baseline({
        "inputs": inputs.to_dict(),
        "chart": {"timeframe": spec.chart_tf, "chart_type": spec.chart_type,
                  "fill_on": spec.fill_on, "security_source": spec.security_source},
        "session": spec.session, "basis": "saved_main_nq_resolution",
        "profile": profile, "preset": preset, "source_files_sha256": evidence,
        "sources": sources,
    })


def _overview(baseline):
    return {"timeframe": baseline["chart"]["timeframe"],
            "session": baseline["session"],
            "qty_contracts": baseline["inputs"]["qty_contracts"],
            "asset_exceptions": {symbol: {"timeframe": "30", "use_session": False,
                                           "qty_contracts": 25}
                                 for symbol in sorted(EXCEPTION_ASSETS)}}


def capture_current(root, *, port=8791, token=None, timeout=10, output=None):
    """Capture only fixed loopback Main NQ reads; never print an owner token."""
    root = _safe(root)
    if not root.is_dir() or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("existing private root and a valid loopback port are required")
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 15:
        raise ValueError("capture timeout must be 0..15 seconds")
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ValueError("loopback NQ capture must not redirect")
    # This one-time read may target an older running engine whose owner token
    # was the former fixed default. Require an explicit capture-only environment
    # value for that migration; the new server still rejects placeholders.
    capture_token = os.environ.get("ICARUS_CAPTURE_TOKEN") if token is None else None
    if capture_token is not None:
        token = capture_token.strip()
        if not token or any(ord(char) < 32 or ord(char) == 127 for char in token):
            raise ValueError("ICARUS_CAPTURE_TOKEN must be a nonempty HTTP header value")
    else:
        token = resolve_owner_token(token)
    opener = build_opener(ProxyHandler({}), NoRedirect())
    def request(path):
        req = Request(f"http://127.0.0.1:{port}" + path,
                      headers={"Authorization": "Bearer " + token, "X-Icarus-Workspace": "main"})
        with opener.open(req, timeout=timeout) as response:
            raw = response.read(_MAX_JSON + 1)
        if len(raw) > _MAX_JSON:
            raise ValueError("current NQ response exceeds its bound")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("current NQ response must be an object")
        return value
    access = request("/api/workspace-runtime")
    if (access.get("schema_version") != "icarus.workspace-power.v1"
            or access.get("execution_authorized") is not False):
        raise ValueError("authenticated loopback Icarus runtime identity is invalid")
    first = request("/api/inputs/NQ")
    if first.get("asset") != "NQ" or first.get("workspace_id", "main") != "main":
        raise ValueError("current NQ capture has a foreign identity")
    chart = first.get("chart", {})
    session = first.get("session")
    if session is None:
        tape = request("/api/chart/NQ?n=1")
        if tape.get("symbol") != "NQ":
            raise ValueError("current NQ chart has a foreign identity")
        session = tape.get("session")
        for key in ("chart_type", "fill_on", "security_source"):
            if tape.get(key) != chart.get(key):
                raise ValueError("NQ configuration changed during capture")
        if str(tape.get("tf")) != str(chart.get("timeframe")):
            raise ValueError("NQ timeframe changed during capture")
    second = request("/api/inputs/NQ")
    config_keys = ("asset", "base", "chart", "preset", "session")
    configuration = {key: first.get(key) for key in config_keys}
    if configuration != {key: second.get(key) for key in config_keys}:
        raise ValueError("NQ configuration changed during capture")
    baseline = _validate_baseline({"inputs": first.get("base"), "chart": chart,
        "session": session, "preset": first.get("preset"), "basis": "captured_live_main_nq",
        "response_sha256": _digest(_bytes(configuration)), "captured_at_ns": time.time_ns()})
    value = {"schema_version": CAPTURE_SCHEMA, "asset": "NQ", "baseline": baseline,
             "execution_authorized": False}
    target = _safe(output or root / "current-nq-restart-capture.json")
    _atomic_write(target, _bytes(value))
    return {"status": "CAPTURED", "capture_file": str(target),
            "baseline_sha256": _digest(_bytes(baseline)), "basis": baseline["basis"],
            "overview": _overview(baseline)}


def prepare_current(root, *, port=8791, profile="nq", preset=DEFAULT_PRESET,
                    token=None, timeout=10, output=None):
    """Prepare live NQ when listening, otherwise prove stopped and read saved NQ.

    A refusal, or a timeout followed by a successful exclusive bind check, chooses
    the offline path. A listener, authentication failure or other uncertainty
    never becomes a successful saved-settings fallback.
    """
    root = _safe(root)
    if not root.is_dir() or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("existing private root and a valid loopback port are required")
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 15:
        raise ValueError("prepare timeout must be 0..15 seconds")
    try:
        connection = socket.create_connection(("127.0.0.1", port), timeout=min(timeout, 2))
    except (ConnectionRefusedError, TimeoutError) as connect_error:
        try:
            # Windows may leave a recently closed loopback socket in TIME_WAIT;
            # connect can time out even though no listener owns the port. The
            # PID identity and exclusive bind check distinguish that case from
            # a live/unresponsive listener before saved settings are accepted.
            ensure_stopped(root, port)
        except ValueError:
            if isinstance(connect_error, TimeoutError):
                raise connect_error
            raise
        source_originals = {}
        baseline = _saved_baseline(root, profile, preset, source_originals)
        value = {"schema_version": CAPTURE_SCHEMA, "asset": "NQ", "baseline": baseline,
                 "prepared_at_ns": time.time_ns(), "execution_authorized": False}
        target = _safe(output or root / "current-nq-restart-capture.json")
        _verify_sources(source_originals)
        _atomic_write(target, _bytes(value))
        return {"status": "PREPARED", "capture_file": str(target),
                "baseline_sha256": _digest(_bytes(baseline)), "basis": baseline["basis"],
                "overview": _overview(baseline)}
    else:
        connection.close()
        result = capture_current(root, port=port, token=token, timeout=timeout, output=output)
        return {**result, "status": "PREPARED"}


def plan_defaults(root, *, preset=DEFAULT_PRESET, profile="nq", assets=None, capture_file=None):
    from .assets import REGISTRY
    from .workspace_config import normalize_workspace
    from .workspace_universe import dashboard_assets
    root = _safe(root)
    if not root.is_dir():
        raise ValueError("existing private state root is required")
    source_originals = {}
    if capture_file is not None:
        capture_path = _safe(capture_file)
        capture_raw = _read(capture_path)
        if capture_raw is None:
            raise ValueError("required settings file is missing: " + capture_path.name)
        source_originals[str(capture_path)] = capture_raw
        source_originals[str(root / TEMPLATE_FILE)] = _read(root / TEMPLATE_FILE)
        capture = _decode_json(capture_raw, capture_path)
        if (capture.get("schema_version") != CAPTURE_SCHEMA or capture.get("asset") != "NQ"
                or capture.get("execution_authorized") is not False):
            raise ValueError("current NQ capture identity is invalid")
        baseline = _validate_baseline(capture.get("baseline"))
    else:
        baseline = _saved_baseline(root, profile, preset, source_originals)
    previous = read_default_template(root)
    if previous and all(previous["baseline"][key] == baseline[key] for key in ("inputs", "chart", "session")):
        baseline = previous["baseline"]
    template = {"schema_version": SCHEMA, "baseline": baseline,
        "asset_exceptions": {symbol: {"qty_contracts": 25, "use_session": False, "timeframe": "30"} for symbol in sorted(EXCEPTION_ASSETS)},
        "execution_authorized": False}
    originals, desired = {}, {}
    def remember(relative):
        if relative not in originals:
            originals[relative] = _read(root / relative)
        return _json(root / relative)
    # Include all current first-party Main assets, recognized saved asset records,
    # and every existing selected CC asset. Future assets use the template hook.
    symbols = set(dashboard_assets() if assets is None else assets)
    for path in root.glob("inputs.*.json"):
        symbol = path.name[len("inputs."):-len(".json")]
        if symbol in REGISTRY:
            symbols.add(symbol)
    profiles = {}
    for name in ("cc1", "cc2", "cc3", "cc4"):
        relative = "command_centers/" + name + ".json"
        if _read(root / relative) is not None:
            current = remember(relative)
            if current.get("id") != name:
                raise ValueError("selected workspace identity is invalid")
            normalized = normalize_workspace(current)
            symbols.update(normalized["assets"])
            profiles[relative] = (current, normalized)
    symbols.add("NQ")
    symbols.update(EXCEPTION_ASSETS)
    if any(symbol not in REGISTRY for symbol in symbols):
        raise ValueError("defaults require canonical registered asset symbols")
    global_old = remember("inputs.json")
    desired["inputs.json"] = {**baseline["inputs"],
        **{k: v for k, v in global_old.items() if k.startswith("_")},
        "_meta": {**global_old.get("_meta", {}), **baseline["chart"], "session": baseline["session"]}}
    for symbol in sorted(symbols):
        relative = "inputs." + symbol + ".json"
        old = remember(relative)
        values = dict(baseline["inputs"])
        meta = {**old.get("_meta", {}), **baseline["chart"], "session": baseline["session"]}
        if symbol in EXCEPTION_ASSETS:
            values.update(qty_contracts=25, use_session=False)
            meta.update(timeframe="30", session="eth")
        desired[relative] = {**values, **{k: v for k, v in old.items() if k.startswith("_")}, "_meta": meta}
    for relative, (original, current) in profiles.items():
        candidate = copy.deepcopy(current)
        candidate["inputs"] = dict(baseline["inputs"])
        candidate["chart"] = dict(baseline["chart"])
        for symbol in candidate["assets"]:
            override = candidate["asset_overrides"].setdefault(symbol, {})
            override["inputs"] = {"qty_contracts": 25, "use_session": False} if symbol in EXCEPTION_ASSETS else {}
            override["chart"] = {"timeframe": "30"} if symbol in EXCEPTION_ASSETS else {}
        if candidate != current:
            candidate["config_revision"] = current["config_revision"] + 1
        desired[relative] = normalize_workspace(candidate)
    remember(TEMPLATE_FILE)
    desired[TEMPLATE_FILE] = template
    changed = [name for name, value in desired.items()
               if originals[name] is None or _json(root / name) != value]
    _verify_sources(source_originals)
    return {"root": str(root), "baseline": baseline, "symbols": sorted(symbols),
            "changed_files": sorted(changed), "desired": desired, "originals": originals,
            "source_originals": source_originals}


def apply_plan(plan, *, port=8791):
    root = _safe(plan["root"])
    ensure_stopped(root, port)
    _verify_sources(plan["source_originals"])
    for name, original in plan["originals"].items():
        if _read(root / name) != original:
            raise ValueError("settings changed after the NQ-default plan was captured")
    if not plan["changed_files"]:
        return {"status": "UNCHANGED", "baseline_sha256": _digest(_bytes(plan["baseline"])),
                "changed_files": [], "execution_authorized": False}
    encoded = {name: _bytes(plan["desired"][name]) for name in plan["changed_files"]}
    run_id = str(time.time_ns()) + "-" + uuid.uuid4().hex
    backup = _safe(root / "audit" / "restart-defaults" / run_id)
    backup.mkdir(mode=0o700, parents=True)
    manifest = {"status": "PREPARED", "originals": {}, "execution_authorized": False}
    for name in plan["changed_files"]:
        raw = plan["originals"][name]
        manifest["originals"][name] = None if raw is None else _digest(raw)
        if raw is not None:
            _atomic_write(backup / "originals" / name, raw)
    _atomic_write(backup / "manifest.json", _bytes(manifest))
    applied = []
    receipt_before = _read(root / RECEIPT_FILE)
    try:
        for name, raw in encoded.items():
            if _read(root / name) != plan["originals"][name]:
                raise ValueError("settings changed during defaults application")
            _atomic_write(root / name, raw)
            applied.append(name)
        receipt = {"status": "APPLIED", "schema_version": SCHEMA,
            "baseline_sha256": _digest(_bytes(plan["baseline"])),
            "baseline_basis": plan["baseline"]["basis"], "symbols": plan["symbols"],
            "changed_files": plan["changed_files"], "backup_directory": str(backup),
            "files_sha256": {name: _digest(raw) for name, raw in encoded.items()},
            "asset_exceptions": {symbol: {"qty_contracts": 25, "use_session": False, "timeframe": "30"} for symbol in sorted(EXCEPTION_ASSETS)},
            "execution_authorized": False}
        _atomic_write(root / RECEIPT_FILE, _bytes(receipt))
        manifest["status"] = "APPLIED"
        _atomic_write(backup / "manifest.json", _bytes(manifest))
        return receipt
    except Exception:
        for name in reversed(applied):
            original = plan["originals"][name]
            if original is None:
                _safe(root / name).unlink(missing_ok=True)
            else:
                _atomic_write(root / name, original)
        if receipt_before is None:
            _safe(root / RECEIPT_FILE).unlink(missing_ok=True)
        else:
            _atomic_write(root / RECEIPT_FILE, receipt_before)
        manifest["status"] = "ROLLED_BACK"
        _atomic_write(backup / "manifest.json", _bytes(manifest))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--preset", default=DEFAULT_PRESET)
    parser.add_argument("--profile", choices=("nq", "crypto"), default="nq")
    parser.add_argument("--capture-file")
    parser.add_argument("--port", type=int, default=8791)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true")
    action.add_argument("--verify", action="store_true")
    action.add_argument("--capture-current", action="store_true")
    action.add_argument("--prepare", action="store_true")
    parser.add_argument("--capture-output")
    args = parser.parse_args(argv)
    try:
        if args.prepare:
            result = prepare_current(args.root, port=args.port, profile=args.profile,
                                     preset=args.preset, output=args.capture_output)
        elif args.capture_current:
            result = capture_current(args.root, port=args.port, output=args.capture_output)
        else:
            plan = plan_defaults(args.root, preset=args.preset, profile=args.profile, capture_file=args.capture_file)
            if args.apply:
                result = apply_plan(plan, port=args.port)
            else:
                result = {"status": "VERIFIED" if args.verify and not plan["changed_files"] else "PLANNED",
                    "baseline_basis": plan["baseline"]["basis"], "baseline_sha256": _digest(_bytes(plan["baseline"])),
                    "changed_files": plan["changed_files"], "symbols": plan["symbols"], "execution_authorized": False}
                if args.verify and plan["changed_files"]:
                    raise ValueError("saved assets do not yet match the current NQ-default plan")
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print("NQ defaults stopped: " + type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
