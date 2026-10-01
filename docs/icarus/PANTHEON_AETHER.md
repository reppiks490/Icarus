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


## AETHER blind-claim protocol

AETHER now has a durable first-pass claim protocol rather than only spawning
agent descriptors. A spawned agent can commit exactly one immutable first-pass
claim tied to its observation and information partition. The kernel verifies
that the agent ID was actually spawned for that observation and rejects claims
that declare peer context was used during the blind round. Falsifier,
alternative-cause, provenance-guard and risk-guard claims are required before
the observation is marked ready for deliberation.

The deliberation state reports directional disagreement and stated confidence
without electing a trade or forcing consensus. Agent claims remain research
evidence with execution_authorized=false and
production_decision_authorized=false.


## Completed faculty depth

The PANTHEON faculties remain independent rather than being averaged into one
confidence score.

- **NEMESIS Ω**: minimum failure distance, sensitivity vectors, measured/derived
  edge half-life, subsystem-ablation survival, and a ranked DREAMSTATE
  falsification curriculum.
- **GÖDEL Ω**: identifiability, ambiguity, effective-world count, resolution
  gap, epistemic blindspots, and ranked discriminating observations.
- **SOCRATES**: ranked research questions plus matching falsifiable
  hypothesis/falsifier pairs.
- **ANANKĒ**: structural transition cost, directional reachability, constraint
  pressure, reachable-space collapse, causal event horizons, and optional
  cross-world reachability intersection.
- **EX NIHILO**: ontology surprise, representation-failure hypotheses,
  falsification questions, and retirement through observed ecology fitness.
- **MINT Ω**: explicit/stressed costs, risk capital, duration, capacity,
  crowding, optional half-life, profit density, profit surface, profit chains,
  and alpha metabolism.
- **NULLSPACE Ω**: causal debt, response elasticity, repayment pressure, debt
  change/migration, absorption/diversion/delay, cliffs, and insolvency
  candidates.
- **ARCHON Ω**: temporary revocable research-attention leases, contradiction,
  and attention concentration; no forced consensus.
- **AETHER Ω**: mandatory independent blind-first-pass roles plus durable claim
  lineage, observed fitness, speciation/extinction, and bounded research
  ecology.

## SIBYL Ω evidence bridge

PANTHEON does not turn every faculty into a SIBYL vote. Only structurally
directional ANANKĒ evidence may become a SIBYL evidence candidate, and its
confidence is reduced by GÖDEL ambiguity, NEMESIS survival, and observed data
quality.

The export lives at:

`observation.analysis.exports.sibyl_evidence`

Ambiguous states export zero directional evidence. MINT, SOCRATES, AETHER and
other non-directional faculties cannot inflate SIBYL consensus merely by being
present. The exported evidence preserves exact observation time and source
commit and remains research/shadow-only.

## Durable AETHER ecology

AETHER separates disposable workers from durable evolutionary state. The
PANTHEON ledger stores immutable observations, blind-first-pass agent claims,
durable research claims, observed claim outcomes, species lineage, and
asset/horizon sentinel cells.

EX NIHILO ontology claims and MINT monetization claims seed research species.
Species start at zero fitness. Only observed claim outcomes update fitness:

- fewer than two outcomes: `hypothesis`;
- at least two without decisive fitness: `contested`;
- at least three with fitness >= 0.20: `surviving_shadow`;
- at least three with fitness <= -0.20: `retired`.

A surviving species with fitness >= 0.50 may produce one bounded descendant up
to generation three. Every offspring receives its own durable mutation claim
identity and begins at zero fitness, so it must earn evidence independently.
There is no inherited production authority.

Repeated negative observed fitness produces **economic extinction**. The
research ecology may derive:

- same-kind **predation** when observed fitness separates materially;
- cross-kind **symbiosis** when independent species both show positive shadow
  fitness;
- historical **parasitic drag** from retired negative-fitness species that
  competed for the same asset attention;
- an **alpha food web** ranking surviving species by observed fitness and
  evidence mass;
- **cognitive-genesis candidates** when an ontology species survives at least
  three observed outcomes.

Cognitive genesis only recommends a bounded independent engine-design study.
It never creates, promotes, or activates production code automatically.

### Outcome ingestion

No additional live-control endpoint is required. The existing authenticated

`POST /admin/pantheon/observe`

accepts an optional bounded `claim_outcomes` list. An outcome names a prior
claim, observation time, bounded utility, confidence, and evidence. Scored
fitness cannot update before the claim's market horizon has matured. Outcomes
attached through a feedback observation must match that observation's asset and
timestamp, and descendant mutation claims are bound to the feedback observation
that created them. Zero-confidence outcomes remain durable evidence but
contribute zero fitness. Upgrades backfill missing sentinel chronology and
legacy durable claim species without inventing fitness. Outcomes remain
immutable for a given `claim_id + observed_at`; idempotent retries are safe.

## Causal chronology

- Observation timestamps require an explicit timezone, canonicalize to UTC, and
  reject future-dated evidence beyond transport tolerance.
- Sentinel cells retain the newest **observed** state even when older evidence
  arrives later.
- Late ingestion still increases audit coverage but cannot roll the live
  sentinel state backward.
- Ambient ORACLE Ψ/PARALLAX/DREAMSTATE snapshots remain outside immutable
  observation identity, preserving the parent branch's retry semantics.
- Adaptive Brain registers PANTHEON and each faculty as first-class research
  subsystems while preserving ICARUS Ψ, ORACLE, PARALLAX, DREAMSTATE,
  DAEDALUS/AEGIS and execution ownership.


## Claim-quality gate

AETHER first-pass claims must carry explicit bounded confidence and at least one
evidence reference. Roles marked as falsifier-required must also state the
condition that would falsify their thesis. Missing claim-quality fields fail
closed instead of becoming zero-confidence or evidence-free pseudo-claims.


## Blind-round visibility barrier

First-pass claim content is now redacted from PANTHEON read surfaces until all
four mandatory independent roles have committed. Before that barrier clears,
the system may reveal that an agent has committed, but not its thesis,
direction, confidence, evidence, or falsifier. This makes the blind-first-pass
property enforceable at the shared API/UI layer rather than relying only on a
caller assertion.


## Full-swarm blind barrier

The visibility barrier now covers every AETHER agent actually spawned for an
observation, not only the four mandatory guard roles. Completing the mandatory
roles is reported separately, but deliberation and claim-body visibility remain
closed until every spawned research partition has committed its first-pass
claim. This prevents optional specialists from reading mandatory-role
conclusions before submitting their own independent view.


## Invalid-input handling

Normalized confidence, risk, quality, reliability, novelty and similar fields
now fail closed when they fall outside their declared bounds instead of being
silently clipped. Structural costs must be non-negative, and MINT rejects
negative costs, non-positive risk capital, and non-positive duration. This
prevents malformed upstream data from being converted into plausible-looking
research diagnostics.


## Outcome and stress-evidence quality

Observed claim outcomes now fail closed rather than silently clipping malformed
values: utility must already lie in [-1, 1], confidence is explicit and bounded,
and every outcome must carry at least one evidence reference. Species fitness is
confidence-weighted from those immutable observed outcomes.

NEMESIS rejects negative edge-decay rates and half-lives, MINT rejects
sub-unit cost-stress multipliers and negative half-lives, and ARCHON rejects
fractional or out-of-range lease TTLs. These checks keep malformed upstream
research metadata from being normalized into plausible-looking evidence.
