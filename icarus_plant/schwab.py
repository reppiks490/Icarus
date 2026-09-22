# Grok (xAI) — 2026-09-22. Read-only Schwab Market Data. Never POST /orders.
from __future__ import annotations
import base64, json, os, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

from icarus_engine.ignore_trade import ignored_symbol
from icarus_engine.spec import TRADED
from icarus_plant.layout import plant_root

AUTH = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN = "https://api.schwabapi.com/v1/oauth/token"
QUOTES = "https://api.schwabapi.com/marketdata/v1/quotes"
FORBIDDEN_POST = ("/orders", "/previeworder")

def secrets_dir(root=None) -> Path:
    p = Path(plant_root(root)) / "secrets"
    p.mkdir(parents=True, exist_ok=True)
    return p

def token_path(root=None) -> Path:
    return secrets_dir(root) / "schwab_token.json"

def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()

def authorize_url() -> str:
    key = env("SCHWAB_APP_KEY")
    redir = env("SCHWAB_REDIRECT", "https://127.0.0.1")
    if not key:
        raise ValueError("set SCHWAB_APP_KEY")
    q = urllib.parse.urlencode({"client_id": key, "redirect_uri": redir})
    return f"{AUTH}?{q}"

def _basic() -> str:
    raw = f"{env('SCHWAB_APP_KEY')}:{env('SCHWAB_APP_SECRET')}".encode()
    return "Basic " + base64.b64encode(raw).decode()

def _post_token(data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(TOKEN, data=body, method="POST")
    req.add_header("Authorization", _basic())
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

def exchange_code(code: str, root=None) -> Path:
    redir = env("SCHWAB_REDIRECT", "https://127.0.0.1")
    tok = _post_token({"grant_type": "authorization_code", "code": code, "redirect_uri": redir})
    tok["saved_at"] = time.time()
    path = token_path(root)
    path.write_text(json.dumps(tok, indent=2), encoding="utf-8")
    return path

def load_token(root=None) -> dict:
    path = token_path(root)
    if not path.is_file():
        raise FileNotFoundError(f"no token at {path} — run exchange first")
    return json.loads(path.read_text(encoding="utf-8"))

def refresh(root=None) -> dict:
    tok = load_token(root)
    age = time.time() - float(tok.get("saved_at") or 0)
    if age < 25 * 60 and tok.get("access_token"):
        return tok
    nxt = _post_token({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    nxt["saved_at"] = time.time()
    token_path(root).write_text(json.dumps(nxt, indent=2), encoding="utf-8")
    return nxt

def request(method: str, url: str, root=None, data=None) -> dict:
    method = method.upper()
    low = url.lower()
    if method != "GET":
        if any(x in low for x in FORBIDDEN_POST):
            raise PermissionError("Schwab plant forbids order POST/preview. Owner-hard.")
        raise PermissionError(f"Schwab plant is GET-only ({method} {url})")
    if "/orders" in low and method != "GET":
        raise PermissionError("orders writes forbidden")
    tok = refresh(root)
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {tok['access_token']}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

def default_symbols() -> list[str]:
    raw = env("SCHWAB_SYMBOLS")
    if raw:
        return [s.strip() for s in raw.split(",") if s.strip()]
    return [f"/{s}" for s in TRADED if s not in ("BTC",)]  # owner should replace after Instruments

def quotes(symbols=None, root=None) -> dict:
    syms = []
    for s in (symbols or default_symbols()):
        if ignored_symbol(s.replace("/", "")):
            continue
        syms.append(s)
    if not syms:
        raise ValueError("no symbols")
    q = urllib.parse.urlencode({"symbols": ",".join(syms), "fields": "quote,reference", "indicative": "false"})
    return request("GET", f"{QUOTES}?{q}", root=root)
