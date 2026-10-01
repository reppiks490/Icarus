# Grok (xAI) — 2026-09-22. Schwab Market Data only. Order writes not implemented.
from __future__ import annotations
import base64, json, os, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
from icarus_engine.ignore_trade import ignored_symbol
from icarus_engine.spec import TRADED
from icarus_plant.layout import plant_root

AUTH = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN = "https://api.schwabapi.com/v1/oauth/token"
QUOTES = "https://api.schwabapi.com/marketdata/v1/quotes"
ORDER_WRITE = ("/orders", "/previeworder")

def secrets_dir(root=None) -> Path:
    p = Path(plant_root(root)) / "secrets"
    p.mkdir(parents=True, exist_ok=True)
    return p

def token_path(root=None) -> Path:
    return secrets_dir(root) / "schwab_token.json"

def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()

def orders_unlocked() -> bool:
    return False  # data feed only; executing broker is not Schwab

def authorize_url() -> str:
    key = env("SCHWAB_APP_KEY")
    redir = env("SCHWAB_REDIRECT", "https://127.0.0.1")
    if not key:
        raise ValueError("set SCHWAB_APP_KEY on the PC, not in a model goal")
    return f"{AUTH}?{urllib.parse.urlencode({'client_id': key, 'redirect_uri': redir})}"

def _basic() -> str:
    key, secret = env("SCHWAB_APP_KEY"), env("SCHWAB_APP_SECRET")
    if not key or not secret:
        raise ValueError("SCHWAB_APP_KEY and SCHWAB_APP_SECRET stay on the PC")
    return "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode()

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
        raise FileNotFoundError(f"no token at {path}")
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

def request(method: str, url: str, root=None):
    method = method.upper()
    low = url.lower()
    if method != "GET" or any(x in low for x in ORDER_WRITE) and method != "GET":
        raise PermissionError("Schwab plant is Market Data GET only. Not the executing broker.")
    if method in {"POST", "PUT", "DELETE", "PATCH"}:
        raise PermissionError("Schwab plant GET-only")
    tok = refresh(root)
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {tok['access_token']}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

def default_symbols() -> list:
    raw = env("SCHWAB_SYMBOLS")
    if raw:
        return [s.strip() for s in raw.split(",") if s.strip()]
    return [f"/{s}" for s in ("NQ", "ES", "YM", "GC", "SI", "PL", "PA")]

def quotes(symbols=None, root=None) -> dict:
    wanted = [s for s in (symbols or default_symbols()) if not ignored_symbol(s.replace("/", ""))]
    if not wanted:
        raise ValueError("no symbols")
    out = {}
    errors = {}
    for s in wanted:
        q = urllib.parse.urlencode({"symbols": s, "fields": "quote,reference", "indicative": "false"})
        try:
            blob = request("GET", f"{QUOTES}?{q}", root=root)
            if isinstance(blob, dict):
                out.update(blob)
        except (urllib.error.HTTPError, urllib.error.URLError, FileNotFoundError, ValueError) as exc:
            errors[s] = str(exc)
    out["_errors"] = errors
    return out
