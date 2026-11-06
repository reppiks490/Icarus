# External capability context: evidence before invocation

This **read-only** ICARUS adapter consumes two actual pinned GitHub repository ledgers: the source audit inventory in `reppiks490/icarus-owner-actions` draft PR #87 (`d5f1bd43e217f2ad7009bab1cff09e9fd422ecc5`) and the canonical `reppiks490/Icarus-engine` federation manifest (`5c9d9921ce7a8fa9479d59b72047514f7a51c50c`). It is an actual cross-repository **metadata consumer**, not execution of any of the external repositories it inventories. The pinned revisions are supplied by the caller and separately enforced by the Actions checkouts; the module itself has no network access and cannot independently attest GitHub history.

Run from an Icarus checkout:

```bash
python -m icarus_engine.external_capability_context \
  --owner-inventory /path/to/owner-actions/coordination/handoffs/2026-10-28-external-execution-source-inventory.json \
  --engine-federation /path/to/Icarus-engine/config/federated_repo_evidence.json \
  --owner-revision d5f1bd43e217f2ad7009bab1cff09e9fd422ecc5 \
  --engine-revision 5c9d9921ce7a8fa9479d59b72047514f7a51c50c --summary
```

The context reports distinct discovered identities, verified source snapshots **as claimed by the independent source audit** (not deep source-code/API inspection), fork/shared-commit groups, candidate subsystem mapping, license-review requirements, missing installation/usage evidence and six canonical Engine federation roles. It rejects inconsistent inventories, forged installation/invocation/CI assertions, malformed JSON, duplicate identities/keys, unsafe archive paths, symlink inputs and unpinned checkout arguments. It never executes external source code, installs packages, contacts providers, trains models, mutates Brain, changes UI or brokers, or infers market edge. Candidate subsystem labels are *hypotheses for integration review*, not verified API usage. Every listed repo remains `NOT_VERIFIED` for actual ICARUS invocation until independent pinned-source license/API, callsite, runtime receipt and exact-head CI evidence is available.

**Source boundary:** The owner's Windows folders `ICARUS-EXTERNAL-GITHUB` and `ICARUS-GITHUB-DOWNLOADS` (reported >100 GB) are **not mounted in this cloud runtime**. The separate 500,867,206-byte archive and manifest are the verified source-audit subset; their 43 snapshots do not establish local installation, a complete 100+ GB inventory, or 80 actually-used integrations. No attempt is made to read hidden local Windows/WSL hardware or secrets. The current owner phone-pairing stop-point and held full restart remain unchanged.

The CI workflow checks out both peer repositories at exact commits, runs metadata-only tests across Python 3.10–3.13, and checks authentic 72/43 source counts without making any market data calls. All external source usage counts intentionally remain **zero verified**; the number is a lower bound for *this audit*, not a claim that no other ICARUS lane uses external code. Do not promote this draft to production/Brain training or present its mappings as runtime-integrated without independent review and evidence.
