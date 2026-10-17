# ICARUS subsystem reality matrix — 2026-10-16

This matrix distinguishes source code, catalog entries, scheduled checks, and observed runtime evidence. It does not grant execution authority. Current Icarus main at review time was `085c655580e4c98adda67da1ed7b52f9e3455338`; Divine Providence main was `27ae69c593ede3019957100cd401625bd2424f43`; Icarus-engine main was `e9e5e46674cd60ab2998e5b292918dd1e3058749`.

## The requested “22” target

The four October 15 screen recordings do not enumerate 22 subsystem names or acceptance criteria. One clip explicitly says the 22 subsystems/agents had not been built. The recording separately cites 12 Divine Providence source systems, 52 Icarus Brain catalog entries, and five remote automation agents. These are different counts and are not interchangeable.

**Conclusion:** there is no evidence-backed list of 22 target units to implement. Do not create ten arbitrary processes to satisfy a count. The canonical list should be supplied as a spec or derived from a user-approved architecture before claiming a 22-unit build.

## Divine Providence source systems

The current Divine Providence `README.md` enumerates twelve systems under `systems/<name>/`. The repository says each runs in an isolated interpreter, has a validation suite, and is covered by the scheduled Observatory workflow. Its connection registry reports nine systems in at least one local contract check; AEGIS, JANUS, and Infrastructure are standalone by design. “Suite passed” describes source validation, not a running service.

| System | Source path | Current classification | Evidence boundary |
|---|---|---|---|
| NEXUS | `systems/nexus/` | Implemented source; validation suite and contract participants | README and Architecture identify it as the causal market-data substrate. Not evidence of a live licensed feed. |
| DAEDALUS | `systems/daedalus/` | Implemented source; validation suite and contract participants | Scientific validation/holdout roles; no promotion or execution inferred. |
| AION | `systems/aion/` | Implemented source; validation suite and contract participant | Durable evidence memory; no execution authority. |
| ARGUS | `systems/argus/` | Implemented source; validation suite and contract participant | Microstructure truth tiers; candle proxies remain non-L2. |
| ATHENA | `systems/athena/` | Implemented source; validation suite and contract participant | Supervisory/advisory role with abstention. |
| ORACLE | `systems/oracle/` | Implemented source; validation suite and contract participant | Research orchestration; no execution authority. |
| PROMETHEUS | `systems/prometheus/` | Implemented source; validation suite and contract participant | Research hypotheses/experiment routing; no self-promotion. |
| ASCENSION | `systems/ascension/` | Implemented source; validation suite and contract participant | Evaluation and transfer gating; conformance is not transfer. |
| AEGIS | `systems/aegis/` | Implemented source; validation suite; standalone by design | No sibling contract is claimed by the Architecture document. |
| JANUS | `systems/janus/` | Implemented source; validation suite; standalone by design | No sibling contract is claimed by the Architecture document. |
| Infrastructure | `systems/infrastructure/` | Implemented source; validation suite; standalone by design | Persistence/recovery authority only; no market or research authority. |
| SuperMesh-X | `systems/supermesh_x/` | Implemented source; validation suite and contract participant | Capability/provider orchestration; does not establish provider entitlement. |

**Workflow evidence:** Divine Providence Observatory run [38877590590](https://github.com/reppiks490/divine-providence/actions/runs/38877590590) was triggered on current main (`27ae69c`). Collection and publishing succeeded, but the Windows collector failed in an Icarus test fixture: `tests_engine/test_ibkr_paper_venue.py` passed `":memory:"` to a filesystem-backed `Journal`; Windows rejected the colon. The fixture correction is proposed in Icarus PR [#439](https://github.com/reppiks490/Icarus/pull/439). This is a test portability failure, not evidence that a subsystem is absent.

The same current main had successful ICARUS Research Institution run [38892916537](https://github.com/reppiks490/divine-providence/actions/runs/38892916537). This workflow exercises institution/research automation; it does not prove a live ICARUS engine process.

## Icarus Brain and agent catalog

- The recording reports **52 Brain catalog entries**. Current `icarus_engine/brain.py` exposes subsystem rows from stored events through `_subsystem_rows(events)`; catalog rows or historical events alone do not establish independent executables or active workers.
- `Icarus-engine/docs/AGENTS_ROADMAP.md` contains 14 named agent work items. It labels R2, S1, and C8 done; several research agents planned; D1 preregistered while awaiting the required 20-day depth corpus. Its X1 Claude↔ChatGPT coordination status is stale and superseded by the model-neutral `icarus-owner-actions` coordination bus.
- The recording’s **five remote automation agents** count could not be mapped to five live workers from GitHub. GitHub Actions runs establish that a particular workflow ran at a particular SHA; they do not establish a persistent worker process.

| State label | Minimum evidence used in this matrix | Does not prove |
|---|---|---|
| `catalogued` | A durable row/schema/registry entry | Executable implementation, deployment, schedule, or current activity |
| `implemented` | Source tree and runnable code/test entry point | Current process, healthy provider, licensed data, or useful output |
| `scheduled` | Workflow/cron definition plus Actions run history | A continuously running worker or successful current run |
| `running/observed` | Fresh runtime health/heartbeat receipt tied to a current process | Trading readiness, data rights, or profitability |
| `qualified` | Explicit source, rights, data-quality, strategy, and forward validation evidence | Any broader entitlement or execution authorization |

## Current scheduled and observed automation

- Divine Providence documents the ICARUS Observatory schedule at `04:17 UTC` and the Institution schedule at `06:17 UTC`; see `docs/ICARUS_OBSERVATORY.md`, `docs/ICARUS_INSTITUTION.md`, and their workflow files. The latest observed Institution run listed above succeeded. The latest current-main Observatory run failed at the Windows test-fixture step described above.
- Icarus-engine Actions shows individual workflow runs, including data-sentinel and peer-intelligence jobs. A green workflow run is finite CI evidence, not proof of a continuously running agent.
- The October 15 recording says 12 suites passed in one earlier verification. That historical result does not supersede the newer failed Windows run on the current Divine Providence main SHA.

## Other high-impact readiness gaps

| Area | Verified state | What remains unverified or incomplete |
|---|---|---|
| Four paper workspaces | Icarus #421/#423 merged; latest main contains the isolated four-profile UI and aggregate P&L work | Local restart/installation and forward paper performance are not visible to this cloud audit. |
| RT01 shadow comparison | Icarus #436 merged and degraded comparisons are withheld; #433 merged UTC-instant Brain chronology | Neither merge proves the current strategy is profitable. |
| A200 equity catalog | 200 public US equity listings have catalog/probe evidence | Audit found 0 source-connected, entitlement-verified, history-qualified, live-qualified, Pulse-enabled, or strategy-qualified entries. |
| Data rights | Dropbox staging includes Yahoo continuous/delayed futures exports | Databento entitlement and commercial/redistribution rights are not established by file possession or row validation. |
| Broker/prop adapters | IBKR paper adapter exists; live arming remains disabled | Other requested venues and verified, effective-dated firm rules are incomplete; no live execution authority. |
| Local activation | Bootstrap scripts and merged code exist | This audit cannot observe the owner’s Windows checkout, installed environment, local dashboard process, account credentials, or live feed health. |

## Open work ownership

At this snapshot, Icarus PRs #414/#415 overlap on futures authority paths; #438 is stacked on #415; #435, #432, #387, #353 and other drafts remain open under their existing authors. Icarus-engine #198 is also open. Avoid duplicating those files while their owners are active. Use current PR heads and coordination reservations before selecting the next code task.

## References

- Divine Providence: `README.md` (“Subsystems”, “Commands”, and “ICARUS Observatory”), `docs/ARCHITECTURE.md` (“Verified connections” and “Coverage”), and `docs/VALIDATION.md`.
- Icarus-engine: `docs/AGENTS_ROADMAP.md`, `automation_intelligence/manifest.json`, and current Actions run history.
- Icarus: `icarus_engine/brain.py::_subsystem_rows`, `tests_engine/test_ibkr_paper_venue.py`, and current PR/merge history.
- Owner-action boundary: live broker arming remains disabled; records in the coordination bus are governance evidence, not data or execution authority.
