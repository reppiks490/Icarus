> **Archived 2026-10-25 — historical only.** These per-panel restart commands are superseded. Use [the current Prime as-is restart](../../../../PRIME_AS_IS_RESTART.md), [current default requirements](../../../../HIGHLY_IMPORTANT_RESTART_INFO.md), and [adapter status matrix](../../../../ICARUS_ADAPTER_STATUS.md). The old branch and source pins below are retained as historical evidence and must not be used for a current restart.

# Panel completion and Git Bash restarts

Historical checkpoint: **four stateful selected-workspace panel adapters**:
ICARUS Ψ / Possibility, Chronofold, Scientific Commissioning and Engine Control.
They operate on CC1, CC2, CC3 and CC4 independently. On the current restart
candidate the other listed subsystem surfaces also have selected-workspace read
adapters. See the current [adapter status matrix](../../../../ICARUS_ADAPTER_STATUS.md):
these are read-only readers, not full collection/training/automation workflows.
Paper execution only. Broker arming remains disabled.

Panel code checkpoint:
[`2c1b6270eda685f5de2733ff4dbb9478ec98bd05`](https://github.com/reppiks490/Icarus/commit/2c1b6270eda685f5de2733ff4dbb9478ec98bd05)
on **`icarus1/restart-readiness-20261020`**, [PR #462](https://github.com/reppiks490/Icarus/pull/462).
The immediate-restart launcher follow-up is
[`e0980d84804d736aeede81b8f1f0cd2cd47f73ea`](https://github.com/reppiks490/Icarus/commit/e0980d84804d736aeede81b8f1f0cd2cd47f73ea).
Use the latest documentation commit on that branch when installing. Pulling only
`main` does not install the panel code. Verification receipts and limits appear
below and in [recovery-evidence.json](../../../../recovery-evidence.json).

## What “checkout” means and how these panels restart

A checkout is the local folder containing the GitHub code. Icarus 2's
[owner-assisted receipt 026](https://github.com/reppiks490/icarus-owner-actions/blob/main/coordination/events/2026/10/22/icarus2-20261020-federation-integration/026-owner-assisted-paper-startup-observed.json)
recorded the original PC data folder as `%USERPROFILE%/Icarus` and the updated
source folder as `%USERPROFILE%/Icarus-as-is`. In ordinary Git Bash these are
`$HOME/Icarus` and `$HOME/Icarus-as-is`. The cloud folder `/workspace/Icarus` is
separate from your PC. Inside a Git Bash code folder, this prints its location:

```bash
git rev-parse --show-toplevel
```

All four panels belong to the same foreground paper engine. **Restart the engine
once to install this batch; do not run four engines or reuse the journals from
two simultaneous processes.** The repeated commands under each panel are
alternative copies of the same restart procedure.

1. Privately record any open paper positions. Restoration of every open in-memory
   position remains uncertified. Do not flatten them to refresh a panel.
2. In the existing engine's owning Git Bash window, press **Ctrl+C** and wait for
   normal shutdown. Leave unrelated phone/proxy/other services alone.
3. Follow the stopped-state backup in [START_HERE.md](../../../../../../START_HERE.md#1-stop-your-existing-instance-and-preserve-its-data).
   Preserve the same private data root, feed, main asset list and saved CC inputs.
4. Run one panel's update/start block below from the existing `Icarus-as-is`
   source folder. It requires the local `~/icarus-start.sh` shortcut created in
   [START_HERE section 4](../../../../../../START_HERE.md#4-save-a-one-command-start-for-the-next-30-days).
   If it was never created, use section 3's explicit launcher with your confirmed
   existing root/feed/assets. Do not substitute an empty root or create fresh
   profiles to make a panel appear healthy.
5. After the engine answers, use **Ctrl+Shift+R** in the browser to load updated
   scripts, then the panel's **Refresh** button. Browser refresh alone cannot
   install a new Python backend. Keep the launcher window open and PC awake.

The fetch command names the branch explicitly so it also works when the local
remote was configured to fetch only `main`. Git preserves local edits and refuses
conflicting changes. Do not use a force checkout, hard reset or clean command.

## 1. ICARUS Ψ / Possibility

**Completed:** selected-runtime price, latent-pressure and scenario diagnostics;
selected asset filtering; isolated external-evidence ingestion/history with
configuration-revision checks. Analytics inspect existing cached market buffers.
Opening this panel does not start another provider session.

**Saved state:**
`ROOT/command_centers/cc1/subsystems/research/psi_evidence.sqlite3`
(replace `cc1` for the other workspaces). Durable evidence history and digest
survive service recreation. Evidence TTL still applies; old evidence does not
become fresh after restart. Transient analytical caches warm again.

**Git Bash restart**, after the common shutdown/backup steps:

```bash
cd "$HOME/Icarus-as-is" &&
git status --short &&
git fetch origin refs/heads/icarus1/restart-readiness-20261020:refs/remotes/origin/icarus1/restart-readiness-20261020 &&
git switch --detach origin/icarus1/restart-readiness-20261020 &&
bash ~/icarus-start.sh
```

Open http://127.0.0.1:8791/dashboards/cc1#possibility, hard-refresh once and click
**Refresh**. Use `cc2`, `cc3` or `cc4` for another portfolio. The main panel remains
at http://127.0.0.1:8791/#possibility. Check the badge and selected asset.

**Verified:** distinct CC1–CC4 prices, no main fallback/provider acquisition,
foreign-asset rejection, authenticated evidence ingestion and reconstruction of
the selected SQLite history/digest, actual browser rendering. Missing underlying
source evidence remains missing; these diagnostics are not calibrated accuracy.

## 2. Chronofold

**Completed:** the existing Chronofold engine now reads the selected workspace's
observations and Possibility diagnostics. Asset filters stay on the selected
route, including query parameters. It cannot borrow the main dashboard's price.

**Saved state:** temporal observation/model caches are **in memory** and warm from
that workspace again after a restart. This batch does not claim durable recovery
of every Chronofold observation. Forecasts explicitly frozen through Commissioning
use its separate durable ledger described below.

**Git Bash restart**, after the common shutdown/backup steps:

```bash
cd "$HOME/Icarus-as-is" &&
git status --short &&
git fetch origin refs/heads/icarus1/restart-readiness-20261020:refs/remotes/origin/icarus1/restart-readiness-20261020 &&
git switch --detach origin/icarus1/restart-readiness-20261020 &&
bash ~/icarus-start.sh
```

Open http://127.0.0.1:8791/dashboards/cc1#chronofold, hard-refresh once and click
**Refresh**. Replace `cc1` as needed. Main: http://127.0.0.1:8791/#chronofold.
Allow the selected runtime to warm; a restart does not manufacture observations.

**Verified:** real phase-field prices differ correctly across all four workspaces,
no parent fallback/provider acquisition, asset/query isolation, actual browser
rendering, existing Chronofold and integration regressions. Research output does
not grant broker authority or establish that the reported accuracy loss recovered.

## 3. Scientific Commissioning

**Completed:** selected forecast capture, eligible outcome settlement, full research
cycle and independent background sampler controls. Normal engine startup starts
each workspace's sampler; normal shutdown stops it before closing paper journals.
The default interval is 15 seconds. **Freeze forecast** requires one selected asset;
**Settle ready** uses that asset or the selected workspace's eligible forecasts.

**Saved state:**
`ROOT/command_centers/cc1/subsystems/audit/commissioning/predictions.jsonl`
and `outcomes.jsonl`, with existing hash-chain integrity checks. Only eligible
outcomes settle; capture can legitimately skip when observations are insufficient
or the required capture interval has not elapsed. Restart retains recorded
forecasts/outcomes; it does not supply missing future observations.

**Git Bash restart**, after the common shutdown/backup steps:

```bash
cd "$HOME/Icarus-as-is" &&
git status --short &&
git fetch origin refs/heads/icarus1/restart-readiness-20261020:refs/remotes/origin/icarus1/restart-readiness-20261020 &&
git switch --detach origin/icarus1/restart-readiness-20261020 &&
bash ~/icarus-start.sh
```

Open http://127.0.0.1:8791/dashboards/cc1#commissioning, hard-refresh once and click
**Refresh**. Replace `cc1` as needed. Main: http://127.0.0.1:8791/#commissioning.
Inspect ledger integrity and background status before requesting another cycle.

**Verified:** capture uses the selected price and writes only its ledger; service
recreation reloads that ledger; all four samplers capture distinct selected prices
and close cleanly; an actual browser cycle reaches the selected backend and creates
a real receipt. Viewer controls stay disabled and server bypass returns 403.
Research promotion/evidence requirements and execution prohibitions remain intact.

## 4. Engine Control

**Completed:** thirteen registered selected-workspace actions: pause/resume/flatten
for the workspace or one selected asset; Commissioning capture, selected/all
settlement, tick, sampler start/stop; and **Refresh workspace diagnostics**.
The diagnostics action reads existing selected services; it does not trigger the
main engine's intelligence synchronization or provider collectors.

Each mutation requires owner access and a captured current configuration revision.
A stale revision returns 409 without performing the command. Flatten retains the
existing exact confirmation phrases and affects paper positions only. Unregistered
actions and unused action arguments are rejected. The selected action registry
does not claim the main control plane's unfinished research/Autopilot adapters.

**Saved state:** control intent/result events use the existing system audit under
`ROOT/command_centers/cc1/subsystems`. A paused in-memory runner is not certified
to remain paused across process restart; inspect its state before using Resume.

**Git Bash restart**, after the common shutdown/backup steps:

```bash
cd "$HOME/Icarus-as-is" &&
git status --short &&
git fetch origin refs/heads/icarus1/restart-readiness-20261020:refs/remotes/origin/icarus1/restart-readiness-20261020 &&
git switch --detach origin/icarus1/restart-readiness-20261020 &&
bash ~/icarus-start.sh
```

Open http://127.0.0.1:8791/dashboards/cc1#engine-control, hard-refresh once and click
**Refresh**. Replace `cc1` as needed. Main: http://127.0.0.1:8791/#engine-control.
Check the scope note, registered action list and audit response before another
command. A browser result is not authorization for live orders.

**Verified:** selected pause isolation, revision conflict/no side effects,
owner/viewer boundary, actual module transport, nested routes, strict duplicate-key
JSON rejection, rejection of unused arguments and unsupported actions. All panel
reads retain selected identity; missing runtimes return unavailable without using
the parent portfolio.

## Verification and remaining work

- Initial four-adapter/browser selection: **35 passed**, 90 deselected.
- Broader component/browser suites before final routing hardening: **248 passed**.
- Final routing/client/context/cached-market suite: **92 passed**.
- Expanded final panel/lifecycle suite: **37 passed**.
- Immediate-restart follow-up: **42 launcher/panel checks passed** after a
  controlled closed-HTTP-connection regression failed first. Existing active-port
  refusal still passes. The change affects POSIX only; Windows retains its
  existing strict port check.
- Actual isolated shell → plant → engine → normal shutdown → same-root restart
  passed. Both launches served all four panels in all four workspaces, retained
  forecast counts and the selected evidence digest, and exited 0 on owned
  shutdown. The fixture used synthetic file history, blocked external network
  access and forbade credential-file reads. This proves the contained Linux
  sequence, not a second observed restart on the owner PC.
- Full runtime with required Chromium checks: **3,895 passed, four skipped,
  111 subtests passed** in 462.60 seconds, exit 0. Production/test source stayed
  identical to checkpoint `2c1b627` throughout. Exact source/log hashes are in
  [recovery-evidence.json](../../../../recovery-evidence.json).
- The Windows workflow now includes the new panel module: 78 main-selection
  modules, 80 distinct modules overall. YAML and all paths validate locally; new
  published-head hosted results remain separate from this local check.

These checks use cloud fixtures and real Chromium, not the owner's PC. Icarus 2's
receipt confirms the earlier `38d5328` paper application started on the PC and
returned healthy main-runner probes. It does not establish adoption of this batch,
all-CC warmup, sustained freshness or open-position recovery.

The prior list of eleven “unfinished selected adapters” is historical and
superseded for read routing by the matrix. Remaining capability gaps are that most
of those CC surfaces are read-only, shared Learning history is not admitted,
provider acquisition/freshness is not established, and local NEXUS/AION status is
not upstream qualification. Icarus 2's older [PR #466](https://github.com/reppiks490/Icarus/pull/466)
scroll patch was superseded by the newer integrated PR #474 candidate; it is not a
separate restart requirement. Runtime observation-expiry and PC uptime still need
operator-side sustained verification.

Full-system readiness remains **NO_GO**. Futures/prop-firm account operation,
complete provider-consumer freshness, matched accuracy comparison and a long
stability/recovery run remain separate work. No live trading was activated.
