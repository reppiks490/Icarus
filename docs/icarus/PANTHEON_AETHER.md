# ICARUS PANTHEON / AETHER

Status: **research/shadow only**. This fabric cannot authorize execution, broker
actions, sizing, or production promotion.

## Ownership boundary

This integration deliberately **does not reimplement or absorb ORACLE, ICARUS Ψ,
PARALLAX, or DREAMSTATE**. ORACLE remains a separate subsystem identity. ICARUS Ψ
remains the owner of the current latent-pressure / market-possibility diagnostics
adapted here. PANTHEON never relabels Ψ evidence as ORACLE evidence. PARALLAX
remains the owner of counterfactual decision twins. DREAMSTATE remains the owner
of shadow policy incubation.

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
10. ORACLE / ICARUS Ψ / PARALLAX / DREAMSTATE ownership is preserved, and Ψ is never renamed or absorbed into ORACLE.

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
claim, observation time, bounded utility, confidence, and evidence. Outcomes
cannot predate their originating claim and are immutable for a given
`claim_id + observed_at`. Idempotent retries are safe.

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


## Claim-maturity chronology

Observed research outcomes cannot score a claim before its originating
observation's horizon has matured. PANTHEON now binds each durable claim outcome
to the source observation time plus horizon_ms and rejects same-instant or
premature feedback. This prevents deterministic claim IDs or same-request
feedback from manufacturing apparent research fitness before the claim had any
causal opportunity to be tested.


## Psi and ORACLE identity boundary

ICARUS Ψ and ORACLE are distinct subsystem identities. PANTHEON reserves the
`psi` slot for the native Ψ adapter and always publishes it as observed or
unavailable, so caller JSON cannot impersonate Ψ when native data is missing.
A separately supplied `oracle` object is preserved as ORACLE context and is
never overwritten or relabelled by the Ψ adapter. The legacy
`oracle_context()` helper remains only as a compatibility alias that returns
a payload explicitly identified as `subsystem=psi`.

## Causal fitness provenance and upgrade continuity

Claim outcomes attached through a PANTHEON feedback observation are bound to
that observation's asset and exact observed timestamp. Descendant mutation
claims are bound to the feedback observation that created them, and their
maturity clock starts no earlier than that mutation event.

Zero-confidence outcomes remain durable audit records but contribute neither
fitness nor effective evidence count. Stage transitions, speciation, extinction,
alpha-food-web evidence mass, and cognitive-genesis thresholds therefore cannot
be satisfied by zero-confidence rows.

On upgrade, PANTHEON backfills missing sentinel observed-time chronology from
its immutable observation ledger and reconstructs missing research species from
existing durable ontology, monetization, and mutation claims. This migration
does not invent historical fitness or production authority.



## ECHO — consensus-illusion detector

PANTHEON now contains an **ECHO** faculty for a failure mode that ordinary
ensembles routinely miss: several engines can agree while all inheriting the
same upstream evidence. Three bullish modules that ultimately depend on the
same order-book imbalance are not three independent confirmations.

ECHO consumes `engine_evidence_lineage` alongside the existing engine scores
and reliability values. It measures directional agreement, pairwise ancestry
overlap, unresolved lineage, duplicated source pairs, and an `echo_risk`.
ARCHON then discounts *research-attention weight* by per-engine evidence
independence before issuing its temporary research leases. This does not alter
the hard Risk Kernel and never grants execution authority.

When apparent agreement is both strong and highly duplicated, ECHO marks a
`consensus_illusion_candidate`. SOCRATES turns that state into a falsifiable
question, and AETHER prioritizes its existing `redundancy_hunter` role so the
swarm can attack shared-source dependence instead of celebrating correlated
votes. Genuinely disjoint evidence ancestry receives no discount.

ECHO is deliberately conservative: without explicit lineage metadata it
abstains rather than inventing independence. Its scores are diagnostic
heuristics, not calibrated probabilities or promises of profitability.


## APEX-verified ECHO ancestry

ECHO can now operate on APEX-verified evidence roots rather than trusting free
text lineage labels. When a PANTHEON observation carries
`signals.engine_evidence_ids`, the server asks APEX Ω to resolve every
evidence ID through its causal ancestry DAG at that observation's timestamp.
The resulting root identities overwrite any caller-supplied
`engine_evidence_lineage` before PANTHEON evaluation.

The verification receipt is stored under
`analysis.external_subsystems.apex_lineage` and surfaced in the PANTHEON UI
as **APEX lineage: VERIFIED**. If IDs are missing, unresolved, future at the
observation boundary, cyclic, or otherwise provenance-incomplete, the verified
path fails closed rather than falling back to a claimed independent lineage.

This preserves subsystem ownership: APEX proves ancestry; ECHO diagnoses
consensus illusion; ARCHON discounts research attention; AETHER investigates.
None of these steps can authorize an order.


### Verified-lineage-only network policy

On the authenticated HTTP/MCP observation path, ECHO is not allowed to act on
caller-supplied lineage labels alone. Unverified caller lineage is removed from
the signal payload before PANTHEON evaluation. Without
`engine_evidence_ids`, ECHO abstains. When evidence IDs are present, APEX Ω
resolves them to verified root tokens and those verified roots are the only
lineage allowed to drive ECHO, ARCHON attention discounts, or AETHER
consensus-illusion research.

The audit receipt records whether a caller attempted to supply lineage, without
promoting that claim into evidence.


### ECHO registry parity

The Adaptive Brain registry also exposes ECHO Ω as a first-class PANTHEON
subsystem. This keeps the system map, PANTHEON UI, faculty output, and audit
surface in agreement: ECHO is visible as evidence-ancestry de-duplication
research and carries no execution, sizing, broker, or production authority.


### Unproven independence fails closed

ECHO no longer allows missing ancestry metadata to become an implicit claim that
engines are independent. When two or more engine scores are present but no
verified `engine_evidence_lineage` reaches PANTHEON, ECHO abstains, marks
`lineage_verified=false`, assigns zero **proven** independence to those
engines, and ARCHON grants no research-attention lease based on that unverified
consensus. The server-owned APEX ancestry bridge can restore non-zero
independence only by supplying verified roots. This is intentionally
conservative and affects research attention only; it does not grant or modify
execution authority.


## VERITAS Ω — right-for-right-reasons auditor

VERITAS prevents ICARUS from rewarding itself merely because a directional
outcome happened to be correct. Before the future is known, an observation may
carry a `mechanism_certificate` containing a named causal thesis, predicted
direction, explicit confidence, a fidelity threshold, falsifiable intermediate
signatures, and invalidators. Because the certificate is embedded in the
immutable PANTHEON observation, it cannot be rewritten after the market moves.

After the observation horizon matures, a separate immutable VERITAS
reconciliation identifies a later immutable PANTHEON source observation plus
confidence and evidence. VERITAS derives both the realized direction
(`veritas_realized_direction`) and the realized mechanism-signature values
from that source observation instead of accepting caller-injected outcomes. VERITAS computes weighted mechanism fidelity and
classifies the result as:

- `right_for_right_reasons`
- `right_for_wrong_reasons`
- `mechanism_without_endpoint`
- `wrong_for_wrong_reasons`
- `mechanism_only` when the endpoint is unresolved

A directionally correct result with poor mechanism fidelity is placed in
`lucky_outcome_quarantine` and receives no reinforcement eligibility. A
right-for-right-reasons result receives diagnostic learning credit, but that
credit is research metadata only: it cannot authorize orders, sizing, broker
actions, or automatic production promotion.

This matters because profitable outcomes can otherwise poison a self-learning
system by reinforcing explanations that were causally false. VERITAS turns
"made money" and "understood why" into two separate questions.


### VERITAS surfaces

VERITAS reconciliation is available through the authenticated engine route
`POST /admin/pantheon/veritas`, an MCP research tool, the PANTHEON API state,
the Adaptive Brain registry, and the PANTHEON trader panel. These surfaces all
preserve the same authority boundary: mechanism fidelity can affect research
interpretation, but cannot authorize trading or automatic production learning.


#### Source-observation binding

A VERITAS reconciliation cannot manufacture its own path evidence. Its
`source_observation_id` must point to a distinct later PANTHEON observation for
the same asset, the reconciliation timestamp must equal that source
observation's timestamp, and the certificate horizon must already have matured.
Realized direction and signature values are read from the immutable source
observation's signals. Fidelity thresholds below 0.50 are rejected so a trivial threshold
cannot turn a zero-fidelity lucky outcome into "right for right reasons."


### VERITAS fitness quarantine

VERITAS now reaches the actual AETHER research-fitness loop for MINT
monetization candidates. When a candidate's originating observation contains an
active VERITAS certificate, a positive claim outcome cannot be recorded before
that certificate is reconciled. If the outcome was profitable but VERITAS
classifies it as anything other than `right_for_right_reasons`, the raw
outcome remains visible but its `fitness_utility` is zero, so it cannot
increase species fitness, trigger positive speciation, or teach the ecology that
a causally false explanation was good.

Negative outcomes are never hidden by this gate: losses continue to count
against research fitness even if VERITAS has not reconciled yet. Existing
pre-VERITAS databases are migrated by backfilling `fitness_utility=utility`
for historical rows, preserving prior recorded evidence.


### VERITAS positive-fitness source binding

Positive VERITAS-gated MINT fitness is additionally bound to the same immutable
source observation used by the VERITAS reconciliation. A later unrelated
observation cannot reuse an earlier right-for-right-reasons result to launder a
new positive outcome into AETHER fitness. Negative outcomes remain countable
without this positive-credit proof chain.


### Claim-outcome source provenance

Each claim-outcome row now persists the exact `source_observation_id` used for
its evidence. The source identifier is part of the outcome's immutable semantic
identity and duplicate check, so a recorded result cannot later be silently
rebound to a different observation at the same timestamp. Legacy rows retain a
null source identifier; all newly source-bound VERITAS fitness evidence carries
the durable observation link.


### Machine-checkable invalidators

VERITAS certificates can now include structured `invalidating_signatures` in
addition to human-readable invalidator notes. They use the same predicate
operators as expected signatures. If any invalidating predicate is observed,
the mechanism cannot pass even when its weighted expected-signature fidelity is
otherwise high. This prevents a superficially matching path from receiving
right-for-right-reasons credit after an explicitly predeclared falsifier
actually occurred.


### VERITAS confidence gate

A mechanism can reconcile cleanly while the realized evidence itself is too
weak to justify positive learning credit. Each certificate therefore freezes a
`min_reconciliation_confidence` (default 0.65, never below 0.50).
`right_for_right_reasons` remains the descriptive classification when the
path matches, but `reinforcement_eligible` stays false unless the reconciliation
confidence also clears that predeclared gate. This prevents a zero- or
low-confidence observation from unlocking full positive AETHER fitness.


### VERITAS source-evidence floor

A later source observation is not accepted merely because it contains the right
signal fields. It must also carry at least one immutable evidence reference in
the PANTHEON observation ledger. The source evidence list is copied into the
VERITAS reconciliation payload, preserving the proof path used to score
mechanism fidelity. Empty-evidence endpoint snapshots fail closed.


## LETHE Ω — adaptive memory decay and regime resurrection

PANTHEON now treats *forgetting* as a first-class research operation. Financial
relationships are non-stationary, so a once-valid edge is not allowed to retain
full research trust forever merely because it was profitable in an older regime.

LETHE accepts bounded `knowledge_memory` records with immutable identity,
learning time, confidence and a declared half-life. It computes exponential
temporal retention from the observation's causal clock. Raw evidence is never
deleted or rewritten; only the current *research trust surface* decays.

Dormant memory can become a **resurrection candidate**, but never because the
calendar or price pattern looks familiar by itself. Resurrection support
requires the conjunction of current-regime similarity, fresh revalidation,
mechanism fidelity, and revalidation freshness. Revalidation timestamps must
fall between original learning time and the current observation. A stale memory
without that evidence remains stale and may be marked a retirement candidate.

SOCRATES turns high staleness or resurrection pressure into falsifiable research
questions. AETHER increases research attention modestly and prioritizes
`historical_analogue` and `edge_half_life` specialists when appropriate.
No LETHE score authorizes orders, sizing, broker actions, model promotion, or
automatic strategy resurrection.

The design is adjacent to continual-learning and concept-drift research, but its
ICARUS role is narrower: revival is bound to fresh mechanism evidence while the
immutable historical evidence remains intact.


### Observation-bound resurrection evidence

LETHE resurrection is now provenance-bound to the immutable PANTHEON
observation. Any positive revalidation strength must carry 1–16
`revalidation_evidence` references, and every reference must already exist in
that observation's explicit evidence list. The same evidence list is part of the
observation identity, so a caller cannot silently swap resurrection evidence
after the fact.

Temporal similarity alone is not enough. LETHE computes a raw resurrection
support value for diagnosis, but only a **qualified resurrection support** may
restore research trust. Qualification requires observation-bound evidence plus
at least 0.50 mechanism fidelity and 0.50 revalidation strength. Weak or
unproven mechanism evidence therefore cannot revive a stale memory even when
the current regime looks nearly identical.
