# Real Engine evidence gauges

These gauges are derived exclusively from the actual committed Icarus-engine evidence catalog. They are infrastructure/research-observability metrics, **not trading-edge gauges**.

The first validated peer commit is `10d02b2e1ee20797be5945ffe3f4ebb5e4193bb3`. The dedicated workflow checks out that exact Engine commit and reads the same real provider, SEC/EDGAR, Native Five, Sentinel and interrepo artifacts used by the catalog integration.

## Gauge meanings

- **Sentinel health OK** — percentage of currently classified Sentinel checks marked `OK`. Higher is healthier infrastructure.
- **Sentinel blocked or failing** — percentage marked `BLOCKED` or `FAILING`. Lower is healthier. This is operational debt, not market risk.
- **Provider substantive delivery** — fraction of providers in the current persisted provider context that both performed substantive work and have real collected rows. This is not full provider-catalog completeness.
- **Native lane verified** — fraction of persisted Native Five lanes whose status is `VERIFIED`.
- **Source consumption not blocked** — fraction of canonical ingestion-manifest sources whose consumption state is not explicitly `BLOCKED`. Partial/evidence-only/dedicated states remain distinct.
- **SEC/EDGAR manifest integrity** — binary indicator that real committed fact/filing row counts are nonzero and their SHA-256 bindings are present.
- **Interrepo acceptance verified** — binary indicator that the Engine peer packet has a verified prior Icarus acceptance record.

There is deliberately **no aggregate edge score**. Infrastructure availability cannot prove a strategy edge. Every gauge carries `trading_edge_metric=false` and `execution_authorized=false`.

## First pinned real state

At the pinned Engine commit, the underlying catalog records 63,531 current provider rows, 16,000 SEC fact rows, 2,380 filing rows and Native Five run `native-40610466093-1`. Sentinel currently exposes 38 OK, 5 DEGRADED, 7 BLOCKED and 36 FAILING classifications. Those bad states remain visible rather than being averaged away.

The workflow performs no provider calls, no collection and no broker or model operations. Its artifact is a derived read-only projection of evidence already committed by Engine.
