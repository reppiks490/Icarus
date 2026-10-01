# Grok (xAI) — 2026-09-22. Poll quotes to plant logs + CSV. Does not touch HANDOFF_LOG.
from __future__ import annotations
import argparse, csv, json, time
from pathlib import Path
from icarus_plant.layout import ensure, plant_root
from icarus_plant.schwab import authorize_url, exchange_code, quotes

def _log(root, line: str):
    p = Path(plant_root(root)) / "logs"
    p.mkdir(parents=True, exist_ok=True)
    with (p / "schwab.log").open("a", encoding="utf-8") as fh:
        fh.write(time.strftime("%Y-%m-%dT%H:%M:%SZ ") + line + "\n")

def _append_quote(dest: Path, sym: str, payload: dict) -> bool:
    q = payload.get("quote") or {}
    last = q.get("lastPrice") or q.get("mark") or q.get("askPrice") or q.get("bidPrice")
    if last is None:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    new = not dest.is_file()
    with dest.open("a", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["time", "open", "high", "low", "close", "volume", "bid", "ask", "symbol"])
        ts = int(time.time())
        w.writerow([ts, last, last, last, last, q.get("totalVolume") or "",
                    q.get("bidPrice") or "", q.get("askPrice") or "", sym])
    return True

def poll_once(root=None):
    paths = ensure(root)
    out_dir = Path(paths["root"]) / "history" / "schwab" / "execution"
    out_dir.mkdir(parents=True, exist_ok=True)
    blob = quotes(root=root) or {}
    errors = blob.pop("_errors", {}) if isinstance(blob, dict) else {}
    wrote = []
    for sym, payload in blob.items():
        if str(sym).startswith("_") or not isinstance(payload, dict):
            continue
        dest = out_dir / f"{sym.replace('/', '')}_quote.csv"
        if _append_quote(dest, sym, payload):
            wrote.append(str(dest))
    return {"wrote": wrote, "n": len(wrote), "errors": errors, "orders": "locked"}

def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only Schwab poller")
    p.add_argument("--root", default="")
    p.add_argument("--auth-url", action="store_true")
    p.add_argument("--exchange-code", default="")
    p.add_argument("--once", action="store_true")
    p.add_argument("--seconds", type=int, default=15)
    args = p.parse_args(argv)
    root = args.root or plant_root()
    if args.auth_url:
        print(authorize_url())
        return 0
    if args.exchange_code:
        print(f"saved {exchange_code(args.exchange_code, root)}")
        return 0
    if args.once:
        rec = poll_once(root)
        print(json.dumps(rec, indent=2))
        _log(root, json.dumps(rec))
        return 0
    print(f"GET quotes every {args.seconds}s. Orders locked. Ctrl+C stops.")
    while True:
        try:
            rec = poll_once(root)
            print(rec)
            _log(root, json.dumps(rec))
        except Exception as exc:
            print(f"poll failed: {exc}")
            _log(root, f"FAIL {exc}")
        time.sleep(max(5, args.seconds))

if __name__ == "__main__":
    raise SystemExit(main())
