# ICARUS PANTHEON / AETHER

Status: **research/shadow only**. This fabric cannot authorize execution, broker
actions, sizing, or production promotion.

## Ownership boundary

This integration deliberately **does not reimplement or absorb ORACLE, PARALLAX,
or DREAMSTATE**. ORACLE remains the owner of latent market pressure / causal
leadership work. PARALLAX remains the owner of counterfactual decision twins.
DREAMSTATE remains the owner of shadow policy incubation.

PANTHEON adds independent faculties:

- **NEMESIS** — adversarial fragility and minimum-failure-distance diagnostics.
- **GODEL** — indistinguishable-world / identifiability diagnostics.
- **SOCRATES** — autonomous research-question selection.
- **ANANKE** — structural transition cost and reachable-future diagnostics.
- **EX NIHILO** — ontology-surprise / new-phenomenon hypothesis generation.
- **MINT** — cost-aware trade-expression comparison before the hard risk gate.
- **NULLSPACE** — missing-reaction / causal-debt diagnostics.
- **ARCHON** — temporary research-attention leases; disagreement is never
  collapsed into a forced consensus.
- **AETHER** — bounded ephemeral agents spawned only in high-information /
  high-opportunity regions. Agents have no capital authority.

## Durable unit

The durable unit is a falsifiable claim backed by an immutable observation and
exact source commit. AETHER agents are disposable workers with bounded TTLs.

## Safety contract

1. Missing evidence causes abstention.
2. Heuristics are not labelled as calibrated probabilities.
3. New concepts start as hypotheses.
4. Engine disagreements remain visible.
5. Every observation is bound to an exact Git revision.
6. AETHER agents cannot place orders or alter position size.
7. ARCHON leases research attention only.
8. MINT outputs candidate expressions only.
9. The external hard Risk Kernel remains mandatory.
10. ORACLE / PARALLAX / DREAMSTATE ownership is preserved.

## API

- `GET /api/pantheon` — authenticated shadow state.
- `POST /admin/pantheon/observe` — ingest one immutable, provenance-bound
  observation and calculate PANTHEON / AETHER diagnostics.

Observation schema: `icarus-pantheon-observation-v1`.


## AETHER independence protocol

Active swarms begin with four mandatory, information-partitioned roles:
falsifier, alternative-cause investigator, provenance guard, and risk guard.
Their first pass is blind to peer conclusions. This intentionally resists
sycophantic convergence and preserves independent information instead of
rewarding superficial consensus.

The kernel also keeps a lightweight sentinel-cell registry keyed by asset and
horizon. Sentinel cells remember field energy and observation count but have no
execution or capital authority. They are an observability/attention substrate,
not an always-on trading permission.

Research rationale: recent simulated-market work reports that multi-agent
reasoning quality alone did not track financial performance, while an
intervention preserving disagreement improved Sharpe and Sortino:
https://arxiv.org/abs/2609.29701


## Existing subsystem feed

Every `/admin/pantheon/observe` ingestion automatically attaches compact,
read-only PARALLAX and DREAMSTATE evidence from their native stores. Caller
supplied subsystem evidence is preserved rather than overwritten. This makes
existing research state visible to PANTHEON without transferring ownership or
authority. ORACLE remains an external contract until its current-main
reconciliation is merged and can be adapted without duplicating its engine.


## Native ORACLE Ψ adapter

ORACLE Ψ is now present on ICARUS main and PANTHEON consumes it through a compact
read-only adapter. The adapter copies bounded diagnostics such as latent
pressure, evidence coverage, future-space collapse and edge state; it does not
duplicate ORACLE's engine, mutate its state, reinterpret scenario shares as
calibrated probabilities, or inherit execution authority.


## MCP parity

The ICARUS MCP surface exposes a read tool for PANTHEON/AETHER state and a
provenance-bound observation-ingest tool. Native ORACLE Ψ, PARALLAX and
DREAMSTATE context is attached inside the engine rather than duplicated by MCP.
The same PANTHEON/AETHER state is visible in the trader interface. MCP exposure
does not increase authority: observations remain shadow research and cannot
authorize orders, sizing, broker actions or production promotion.


## Provenance and retry semantics

The immutable observation identity is bound to observation time, asset, horizon,
exact source commit, signals and explicit evidence. Ambient ORACLE Ψ, PARALLAX
and DREAMSTATE snapshots are stored with the first observation but excluded from
the identity hash so an at-least-once retry cannot fail merely because a native
subsystem advanced between attempts. Reserved native subsystem names are
overwritten from the native stores at ingestion, so caller-supplied JSON cannot
masquerade as ORACLE, PARALLAX or DREAMSTATE evidence.


## Temporal integrity

Observation timestamps must be timezone-aware ISO-8601, are canonicalized to UTC
before hashing/storage, and fail closed when materially in the future. This
prevents offset-string ordering errors and accidental look-ahead evidence from
entering PANTHEON's immutable observation ledger.
