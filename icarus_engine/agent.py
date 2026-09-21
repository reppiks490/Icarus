# Grok (xAI) — 2026-09-21. Whole file.
"""Field Agent panel payload. Desk recipes + paste-packs.

Does not call xAI. Does not scrape TradingView. Does not arm a broker.
Grok live chat lives in the Field Agent preview; this engine only copies
commands for the owner to run on the PC.
"""
from __future__ import annotations

from typing import Any, Dict, List

RECIPES: List[Dict[str, Any]] = [
    {
        "id": "status",
        "title": "Plant status",
        "risk": "safe",
        "summary": "Ask whether Brain B is up. Does not restart.",
        "lines": ["cd C:\\Users\\tripl\\Icarus", "py -3 -m icarus_plant status"],
    },
    {
        "id": "export",
        "title": "Paper-export",
        "risk": "safe",
        "summary": "Dump the local emulator book. Not a broker statement.",
        "lines": ["cd C:\\Users\\tripl\\Icarus", "py -3 -m icarus_engine.cli paper-export"],
    },
    {
        "id": "yahoo",
        "title": "Start Yahoo paper",
        "risk": "restart",
        "summary": "Brain B on delayed NQ=F. No --offline.",
        "lines": [
            "cd C:\\Users\\tripl\\Icarus",
            "git pull",
            "py -3 -m icarus_plant stop",
            "py -3 -m icarus_plant start --assets NQ",
        ],
    },
    {
        "id": "offline",
        "title": "Start FileFeed (CSV tape)",
        "risk": "restart",
        "summary": "Only after a 1-minute NQ candlestick CSV is in history\\drop.",
        "lines": [
            "cd C:\\Users\\tripl\\Icarus",
            "py -3 -m icarus_plant stop",
            "py -3 -m icarus_plant start --assets NQ --offline",
        ],
    },
]

SEATS: List[Dict[str, Any]] = [
    {"id": "grok", "name": "Grok", "role": "Integrity, plant, Windows, QQQ ≠ NQ", "live": False},
    {"id": "claude", "name": "Claude / Astra", "role": "Pulse, emulator, TV parity — paste-pack", "live": False},
    {"id": "chatgpt", "name": "ChatGPT", "role": "Dummy operator / checklists — paste-pack", "live": False},
]

SIDECAR = """# Icarus Field Agent — desk sidecar
# Grok (xAI) 2026-09-21. Loopback only. Not a remote backdoor.
# Double-click start-agent.ps1 on the Windows PC. Binds 127.0.0.1:8799.

param()
Set-Location -LiteralPath $PSScriptRoot
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { & py -3 -m icarus_agent serve }
else { & python -m icarus_agent serve }
"""

CLAUDE_PREFIX = (
    "You are Astra/Claude on Icarus (reppiks490/Icarus). Do not scrape TradingView. "
    "Do not invent ticks. Pulse lives in icarus_engine/strategy/pulse.py; emulator in "
    "icarus_engine/emulator.py. Paper fills are not CME. QQQ is not NQ. Question:\n\n"
)
CHATGPT_PREFIX = (
    "You are a dummy-clear operator for Icarus on Windows. Folder C:\\Users\\tripl\\Icarus. "
    "Dashboard is the PC browser only. Never ALPACA_PAPER=false. Never --offline unless a "
    "1m NQ candlestick CSV is in history\\drop. Question:\n\n"
)


def paste_pack(seat: str, question: str) -> str:
    q = (question or "").strip()[:2000]
    s = (seat or "").strip().lower()
    if s == "claude":
        return CLAUDE_PREFIX + q
    if s == "chatgpt":
        return CHATGPT_PREFIX + q
    return (
        "You are Grok on Icarus Field Agent. Paper is not a broker. Yahoo NQ=F is not NQ1!. "
        "QQQ is not NQ. Do not scrape TradingView. Question:\n\n" + q
    )


def report() -> Dict[str, Any]:
    return {
        "broker_armed": False,
        "executed": False,
        "seats": list(SEATS),
        "recipes": list(RECIPES),
        "sidecar": SIDECAR,
        "prefixes": {
            "claude": CLAUDE_PREFIX,
            "chatgpt": CHATGPT_PREFIX,
            "grok": "You are Grok on Icarus Field Agent. Paper is not a broker. Yahoo NQ=F is not NQ1!. QQQ is not NQ. Do not scrape TradingView. Question:\n\n",
        },
        "note": (
            "This tab copies recipes and paste-packs. It does not SSH, does not call xAI, "
            "and does not place NQ. Grok live chat is the Field Agent preview, not this process."
        ),
        "_grok": "Grok (xAI) 2026-09-21. Field Agent dashboard panel. Never arms a broker.",
    }
