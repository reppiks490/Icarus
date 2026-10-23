# Four portfolio dashboards: update and restart

This release extends the reviewed four-workspace delivery. It preserves the 16
assets in the shipped `start-yahoo.ps1` launcher, keeps ETH/SOL, and adds the ten
family selection and its registered micros to every new workspace. The resulting
selection contains 35 distinct identities (32 futures and three spot assets).
This does not add ten families beyond the existing catalog or prove free licensed
live access or profitable strategies.

| Full-size benchmark | Registered micro(s) |
|---|---|
| CL · WTI crude | MCL |
| NG · natural gas | MNG |
| HG · copper | MHG |
| 6E · Euro | M6E |
| 6J · Yen | MJY |
| 6B · British Pound | M6B |
| 6A · Australian Dollar | M6A |
| ZN · 10-year notes | No equivalent micro in this catalog |
| ZB · 30-year bonds | No equivalent micro in this catalog |
| BTCF · CME Bitcoin | MBT |

Exact MCL/MBT history is attested by the preceding delivery. Its pinned historical
receipt has no MNG/MHG/M6E/MJY/M6B/M6A series. A missing micro stays unavailable;
full-size bars are never relabeled as micro bars. Additional public-source routes
need observed availability and applicable usage rights. No feed purchases are made
by this restart.

## Git Bash: refresh this installation

Run from the **Icarus repository containing `icarus_engine` and `icarus_plant`**,
using the same `ICARUS_HOME` as the existing installation. Divine Providence's hub
repository is a separate installation; restarting that hub alone does not restart
these trading dashboards.

After installing the published feature branch/release:

```bash
python -m pip install -e "."
bash scripts/restart-command-centers.sh
```

If Windows exposes only `py`, use `py -3 -m pip install -e "."` for installation;
the restart script finds the repository venv, Python or Windows launcher.

The helper stops the plant recorded under the selected data root, refuses to
claim an unrelated occupied port, restarts **file-feed-only paper mode**, and
expands each flat workspace through the authenticated asset API. It does not
delete journals, configuration files, presets or history. Leave the window open.
`ICARUS_TOKEN` supplies your existing owner token; absent that, the engine's local
default is used. Phone access requires a stronger token as documented separately.

To retain saved smaller asset selections:

```bash
bash scripts/restart-command-centers.sh --keep-selection
```

To use a specific existing data root:

```bash
bash scripts/restart-command-centers.sh --root "$ICARUS_HOME"
```

The helper prints a refusal if a workspace cannot expand, including an open
position. It keeps the dashboard running and preserves that workspace's selection.
Expansion is sequential: earlier workspaces can succeed before a later refusal.
Do not interpret that message as success for all four. Open that workspace, decide
whether to flatten its paper positions, then apply the full selection when flat.

## Open each view

| View | Local URL |
|---|---|
| Main command center and subsystem tabs | http://127.0.0.1:8791/ |
| Portfolio 1 | http://127.0.0.1:8791/dashboards/cc1 |
| Portfolio 2 | http://127.0.0.1:8791/dashboards/cc2 |
| Portfolio 3 | http://127.0.0.1:8791/dashboards/cc3 |
| Portfolio 4 | http://127.0.0.1:8791/dashboards/cc4 |
| Broker/firm connection inventory | http://127.0.0.1:8791/connections |

Use **Ctrl+Shift+R** after the restart. The portfolio selector switches views;
inputs and trades remain isolated. Combined four-ledger P&L stays above the tabs.
Incomplete/stale marks make the total unavailable, rather than zero.

Each portfolio shows persisted post-cutover paper closure pieces across runs,
realized P&L curve, daily closure activity, drawdown, history and descriptive
outcomes. Partial exits count as closure pieces. The curve excludes open marks
and is **not broker equity**. Sharpe/Sortino are clearly labeled realized daily
return proxies using fixed current configured simulation capital, zero risk-free
rate, complete UTC calendar days and sqrt(365) annualization. At least 20 complete
observed days are required; missing or zero-risk denominators stay unavailable.
Historical results do not establish future profit potential.

## Existing reset and refresh controls

There is no universal safe "wipe every subsystem" command. Most panels are views
of persisted evidence; refreshing them must not erase the evidence. Use the
registered runtime inventory to see **every current supported action**, grouped
by subsystem, with required targets and exact confirmation phrases:

```bash
python -m icarus_engine.workspace_tools controls
python -m icarus_engine.workspace_tools status
```

The same inventory appears in the main dashboard's **Engine Control** panel.
The `controls` command only lists actions; it does not execute them.

| Scope | Supported operation | What changes |
|---|---|---|
| All browser panels | Ctrl+Shift+R | Reload current installed UI; retains data |
| Four workspaces + main engine | Restart helper above | Restarts plant-owned processes; retains journals/settings |
| One portfolio | Refresh performance / Refresh | Reloads the selected ledger and charts |
| One portfolio | Apply configuration with unchanged settings | Rewarms only that flat workspace; retains saved closure history |
| All four flat file-mode portfolios | `python -m icarus_engine.workspace_tools expand` | Adds original + expanded selection; retains chart/inputs and existing extras |
| One flat file-mode portfolio | `python -m icarus_engine.workspace_tools expand --workspace cc1` | Same operation on CC1 only |
| Main engine asset | Engine Control → `asset.rewarm` | Rebuilds that asset from configured history; not a CC1–CC4 reset |
| Main engine asset overrides | Engine Control → `asset.reset_config` | Removes that asset's overrides; requires `RESET ASSET CONFIG` |
| Adaptive Brain/research/loop evidence | Engine Control → `sync.brain_remote`, `sync.brain_research`, `sync.loop_intelligence` | Refreshes verified evidence; may contact configured repository sources |
| Evolution / CSV Evidence Lab | Engine Control → `sync.evolution`, `sync.evidence_lab` | Refreshes the corresponding receipts |
| All intelligence views | Engine Control → `sync.all` | Runs registered evidence refreshers; not training or live arming |
| Tactical Autopilot | Engine Control → `autopilot.reset` | Clears its runtime state and leaves it disabled; requires `RESET AUTOPILOT` |
| Connections | Refresh inventory / explicit read-only Connect | Verifies configured account capability; does not arm orders |
| A200/corpus panels | Refresh saved evidence | Reloads qualified catalog/receipts; does not make missing equities tradeable |

Do not use Flatten as a UI refresh: it closes simulated positions. No reset in
this guide erases paper P&L or authorizes broker orders.

## Separate Divine Providence hub

From that repository, use its installed interpreter:

```bash
python -m divine_providence.cli systems
python -m divine_providence.cli connect
python -m divine_providence.cli validate
```

`systems` enumerates the actual installed hub subsystems. `connect` checks links;
`validate` runs suites, it is not a background service restart. The named NEXUS,
DAEDALUS, AION, ARGUS, ATHENA, ORACLE, PROMETHEUS, ASCENSION, AEGIS, JANUS,
infrastructure and SuperMesh-X packages do not all have independent reset daemons.
Do not invent reset commands for them. On Windows, existing
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap-full.ps1`
is the full installation/validation path; it may clone/install dependencies and
run extensive checks. It is unnecessary for an ordinary dashboard refresh.

Phone access setup is in [PHONE_ACCESS.md](PHONE_ACCESS.md). Localhost URLs work
on the PC; the phone needs the configured authenticated relay/tunnel.
