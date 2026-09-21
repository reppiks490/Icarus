# Astra handoff — Field Agent panel (Grok)

Grok (xAI) — 2026-09-21.

Astra: this is already in the tree. **Do not re-implement it. Do not rewrite Pulse.**

## What landed

A new **Agent** tab on the engine dashboard (next to **Go-live**).

| Piece | File | Owner |
|---|---|---|
| Payload | `icarus_engine/agent.py` | Grok |
| API | `GET /api/agent` in `icarus_engine/server.py` | Grok |
| UI | `agentCard()` + `#agent` tab in `icarus_engine/dashboard.html` | Grok |
| Sidecar | `icarus_agent/` + `start-agent.ps1` | Grok |
| Tests | `tests_engine/test_agent.py` | Grok |
| Go-live (sibling) | `icarus_engine/golive.py` + `/api/golive` | Grok |

## What it is

Desk recipes (copy, not execute) and paste-packs for Claude / ChatGPT / Grok.  
`broker_armed` is always false. The engine **does not** call xAI. Live Grok chat is the Field Agent preview, not this process.

## What you must not do

- Do not rewrite `icarus_engine/strategy/pulse.py` or `emulator.py` to “hook the agent.”
- Do not scrape TradingView. Do not invent ticks. Do not treat QQQ as NQ.
- Do not bind the sidecar or the engine on `0.0.0.0`.
- Do not add `XAI_API_KEY` to the plant.
- Do not execute recipes from the dashboard (clipboard only).

## If you restyle the dashboard

Keep:

- tab `data-v="agent"`
- card id `agentCard`
- `GET /api/agent` shape (`recipes`, `seats`, `sidecar`, `broker_armed`)
- Go-live tab and `/api/golive` untouched unless the owner asks

Command palette id `agent` jumps to the tab. Hash `#agent`.

## Optional later (only if the owner asks)

Wire `POST /api/agent/queue` to `icarus_agent` on `127.0.0.1:8799` **after** an explicit confirm. Still no broker. Still no inbound tunnel.

Grep `Grok (xAI)` / see `GROK.md`.
