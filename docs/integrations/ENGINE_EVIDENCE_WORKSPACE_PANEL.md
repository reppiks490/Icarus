# Selected-workspace real Engine evidence panel

The selected-workspace intelligence router now has a read-only `federation/engine-evidence` surface.

It does not fetch from the network. It reads only an explicitly configured local checkout of `reppiks490/Icarus-engine`, and it requires an exact 40-character commit. If the checkout is missing, the panel says `UNAVAILABLE`. If its Git HEAD differs, the panel says `BLOCKED`. It never substitutes generated or synthetic market data.

Configuration:

- `ICARUS_ENGINE_EVIDENCE_ROOT` — path to the already available Engine checkout.
- `ICARUS_ENGINE_EVIDENCE_COMMIT` — exact commit that checkout must match.

The panel returns the real catalog and gauge projection: current provider row/status metadata, substantive providers, SEC/EDGAR counts and digests, Native Five lane receipts, interrepo acceptance, Sentinel counts, explicit provider/source blockers, evidence-file hashes and infrastructure gauges.

It intentionally does **not** instantiate ResearchWorkspace, LearningFabric or any background worker and performs no provider collection. It does not create Brain candidate events or promote a model. `aggregate_edge_score=null`, `edge_claim_allowed=false`, `automatic_model_promotion=false`, `production_decision_authorized=false` and `execution_authorized=false`.

The dedicated CI checkout is pinned to Engine commit `10d02b2e1ee20797be5945ffe3f4ebb5e4193bb3` and exercises the selected-workspace reader against that real committed evidence. No synthetic provider/market fixture is used.
