# Current Prime as-is restart handoff

Owner direction: finish the stopped Prime’s existing recovery work, deliver one observable updated paper build, then standby. The recurring federation integration loop remains cancelled. Stable provenance stays under `icarus2-20261020-federation-integration`; the former Prime session is `icarus1-20261020-system-recovery`.

## Source and scope

The candidate is branch `prime/as-is-restart-20261022`, based on published recovery `393128f96228db20037b024db20e8e32529a2eee`. Its PR and immutable coordination handoff identify the final tested commit. The stopped environment’s uncommitted files were not accessible here. Missing pieces were reconstructed from canonical source and immutable handoffs and tested afresh. Screenshots’ historical test counts are not receipts for this candidate.

Included work:

- Automatic status polling waits for any in-flight explicit refresh. Manual newer-request ordering and the ten-second deadline remain enforced; a later success restores expired observations. The already-published selected status path continues to avoid sibling recomputation.
- Expected browser disconnects close that connection without retrying a 500 response. Other I/O errors remain visible.
- Main and CC1–CC4 use the same native shared Access registry with owner-gated creation/revocation. Access refreshes on opening, an action or its Refresh button, preserving a label while runtime polls continue.
- Readout layout batching preserves animation; the Connections layout wraps long labels at 320/390px. Settings placement tracks header layout changes.
- Native selected-private research/intelligence diagnostic readers are exposed through existing panel routes. Their controls remain read-only. Possibility, Chronofold, Commissioning and Engine Control retain their previously delivered selected actions and existing authorization checks.
- The empty-main-assets startup guard from PR #468 and bounded, pinned Brain inventory repair from PR #469 are included. The existing live-federation CI fixture supports the inventory APIs without relaxing freshness or research gates.

## Install and observe on the owner PC

Use the existing data root printed by the former launcher: observed `C:/Users/tripl/Icarus`. Code goes in the existing separate `C:/Users/tripl/Icarus-as-is` checkout. Other federation repositories keep their existing evidence/implementation responsibilities; this is the local runtime launcher.

1. In the owning terminal, press Ctrl+C and wait for normal shutdown. Privately record any open paper positions first; recovery of every open in-memory position is not certified.
2. With the engine stopped, preserve the private root using the backup procedure in [START_HERE](../../START_HERE.md#1-stop-your-existing-instance-and-preserve-its-data). Never reset or delete it to update code.
3. In Git Bash on that PC:

```bash
cd "$HOME/Icarus-as-is" &&
git fetch origin prime/as-is-restart-20261022 &&
git switch --detach FETCH_HEAD &&
git rev-parse HEAD
```

Check the printed commit against this candidate’s final coordination handoff/PR before launching. Git refuses conflicting local edits; preserve them instead of forcing checkout. To start:

```bash
export ICARUS_STATE='C:/Users/tripl/Icarus'
export ICARUS_HOME="$ICARUS_STATE"
export ICARUS_MAIN_ASSETS='NQ,ES,YM,GC,SI,BTC'
bash scripts/start-as-is.sh --setup --root "$ICARUS_STATE" --feed yahoo --assets "$ICARUS_MAIN_ASSETS"
```

Retain an existing custom token through the local `ICARUS_TOKEN` environment. It must remain private. Later launches use the same command without `--setup`. The six explicit main symbols reproduce the last observed owner launch; four workspace selections remain independently persisted. The launcher refuses empty main assets or an occupied port and does not kill other processes. Yahoo futures quotes remain delayed paper/research data.

Keep the launcher window open and the PC awake. Open [Main](http://127.0.0.1:8791/), [CC1](http://127.0.0.1:8791/dashboards/cc1), [CC2](http://127.0.0.1:8791/dashboards/cc2), [CC3](http://127.0.0.1:8791/dashboards/cc3), [CC4](http://127.0.0.1:8791/dashboards/cc4) and [Connections](http://127.0.0.1:8791/dashboards/connections). Refresh an existing browser tab once after updating source.

Verify actual prices/status recover, the workspace badge matches each URL, saved Inputs remain, Performance reads the chosen persisted ledger and stale/missing marks stay explicit. A blank page or repeated expiry after 30 seconds needs diagnostics, not indefinite waiting. `/healthz` 200 alone is insufficient: assets must be nonempty, warmup/price age must be inspected, and the views must render. The correct native main status endpoint is `/status/public`; `/api/status` is not this engine’s route. Read-only native subsystem panels can legitimately show zero/unmeasured private evidence.

## Evidence and remaining limits

Candidate verification is recorded by exact source/tree, commands and outcomes in the PR and immutable handoff after the final gates. Cloud browser/process checks use synthetic file history and temporary private state; they cannot certify the owner PC’s network, feed entitlement, imported history, journals or continued uptime. No owner-PC restart is claimed before its readback.

Shared-history admission into the new selected-private Learning reader remains explicitly unavailable. No history scan, corpus collection, training, autonomous research, activation or live orders are started by these new readers. Existing protected holdouts, point-in-time identities, source rights and promotion checks remain in force. Provider presence, entitlement, producer publication and consumer reads remain separate evidence.

Full-system readiness remains NO_GO: sustained freshness, open-position reconstruction, remaining mutation adapters, real broker/prop-firm operation, historical data gaps and measured accuracy recovery are not certified by this as-is restart. `execution_authorized=false` throughout. No automatic main merge, deployment, purchase, scheduler change or owner-PC reboot is part of this handoff. After the bounded delivery, current Prime waits for the owner’s next request.
