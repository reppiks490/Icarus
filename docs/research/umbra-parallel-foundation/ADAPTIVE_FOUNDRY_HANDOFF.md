# UMBRA × ICARUS adaptive Foundry — executed continuation

2026-11-24/25. Research-only draft PR #506. Owner directed continuation through successive milestones rather than returning at each gate. This increment implements and executes the synthetic compact-learning pipeline; it does not deploy the system or train language models.

## Exact implementation and tests

| Component | Commit | Verified Git blob |
|---|---|---|
| adaptive_foundry.py | 63cdc845a99324fbe196ee4082847bb69ce6f030 | 7ff85fbc6345b224a5b6a01a2b78b03ad67430ca |
| test_umbra_adaptive_foundry.py | cead1dcc39c0c705c5bd8cf729c0da6dc440ab9a | 7eb07dab277bbccfc5e29ffc31b5e54abec43489 |
| agent_lab.py (pilot) | bf8f4950830f1cf2559255109c79cacee8c68400 | 0016ccadfed943e7f6e96d1cd0a82f22ccb32cca |
| agent_lab.py (native memory fix) | a3271371c2cd70b020131c9f60d7f65eea49a7a1 | 3ed0cce5f1f3d48bf2792dc985258a03d21d9dc1 |
| test_umbra_agent_lab.py (latest) | 754d0dc0f58ff8eac7f0928a87b6ce561c980fb5 | 7d5bee8cf4a2250f9ef73ae56a6aa67da7278de7 |
| campaign.py | db29882766ae5505c7a0fb5dc518231db411e62a | e31d6ac94f51f4c965a3a0905b54e492cc5432a7 |
| test_umbra_campaign.py | c40f816ff2abed542eb35e6d4ee619579fedd92b | 9d6e292e35e825d2934eca75c9ad07b3439c5ef4 |

Adaptive store: transactional SQLite batch append, stale head CAS, sequence gaps and tamper/truncation checks against separately retained trusted pins; group-balanced advisory routing and paired heldout descriptive reports. Agent lab: 40 valid scoped identities, per-agent checkpoint receipt lineage, training digest checks, synthetic prequential predict-before-observe and rolling drift heuristic, explicit opt-in two-child spawn-based worker wave, actual memory sampling, estimated reservations, bounded payload/epochs/deadline and own-child cleanup. Campaign: deterministic curricula, per-model verified scoped bank, resume from externally supplied per-agent heads, successive bounded waves until complete/no progress/budget exhaustion, no automatic promotion. Ordinary checkpoints do not stop the campaign. Native Windows/Linux memory implementation removes psutil dependency; Linux cgroup v2 ancestor accounting. Windows and cgroup v1/nonstandard mount qualification remain outstanding. No hard OS memory guarantee.

Test-first RED reproduced missing modules, then 26, 32, 36 focused checks passed; final missing-psutil regression reproduced before fix; final integrated isolated Linux suite 37 passed in 5.82s, Python 3.13.5/PyTorch 2.10.0+cpu. No full repository suite or Windows verification. Exact source/test blobs read back. Existing live code untouched.

## Executed synthetic campaign

All 40 synthetic compact routing checkpoints persisted over 20 successive waves, max 2 child workers, zero failed workers, 4 waves with measured overlapping child execution intervals. 65.67 seconds summed campaign execution time (excludes initialization/verification and between-call gaps). 30 logistic learners (9 parameters each), 10 two-hidden-layer PyTorch networks (289 parameters each), 3,160 total trainable scalar parameters across the 40 learners. 1,280 response rows, 320 distinct arithmetic tasks; 640 train and 640 holdout responses, 16 of each per identity; same underlying toy rules across train/holdout. All 40 reported 100% heldout response-correctness classification on this deterministic fixture. Mean Brier: linear 0.004146033461897391, deep 0.0000007820639794980561; different assigned rules prevent a direct model-class comparison. These are NOT real teacher reasoning accuracy, trading performance or 40 trained language models. Each checkpoint and receipt is separately addressed; digest uniqueness is not proof of statistical independence. Both SQLite integrity checks returned ok; reloaded all 40 checkpoints, checked every digest and re-evaluated every heldout metric exactly. Waves 1–3 used initial campaign implementation; waves 4–20 used scoped-bank optimized equivalent implementation. No automatic promotion; no real teacher outputs.

Evidence head: def6885c15ecde0f597d446680382e8bb3756a496f1bf344d8a24adf1b8cb128
Campaign manifest digest: ea4fdb7be4c64a2224c60fc14db81b3fdc89fd21f4caaf19ba6cfca4d16eca14

Artifact checksums SHA-256 (synthetic, no private market data):
- manifest.json: 99cf6336b43ba7aac70163c2f32af8499cbb58f39bbcb77372fc444d43b822f1
- agents.sqlite: 76b38b55b7b6952b09ed2bb837d2d89d7b3fb2913ae9a6149beefb49c860b312
- evidence.sqlite: a241f18d36c99130186573cb35c5a7bfd59be084ceba2c3663b6588c001dcce6
- results.json: 987bd02716ff9c8f62008fc335f190e36694a10cc0bc12821930bd5767f844b2
- chat attachment UMBRA-synthetic-federation-pilot.zip: 6ea5354ac371b5c39afc1e9591340731d34957cc192c80412f9f3ffbfb4c009a (174122 bytes, zip integrity verified; contains original pilot implementation, 36-test suite and database/manifest/results; latest native memory fix is in GitHub, not this ZIP). Retain this artifact separately; GitHub records code and receipt hashes, not binary DB contents.

## Reproduction and continuation

In isolated trusted Linux checkout, with pytest and optional torch CPU installed, run:
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m pytest tests_engine/test_distillation.py tests_engine/test_umbra_distillation_learning.py tests_engine/test_umbra_adaptive_foundry.py tests_engine/test_umbra_agent_lab.py tests_engine/test_umbra_campaign.py -q

Use campaign.curriculum() for deterministic Bank + 40 jobs. Store.append raw FIELDS in batches <=128, starting at ZERO, verify final head. Use Vault(new database) and campaign.advance(bank, head, jobs, vault, {}, allow_execution=True, max_waves=20) from a guarded Python main entry point. Save returned heads externally, then resume using same bank, jobs, vault and exact heads. Do not claim automatic recovery of a crash between SQLite commit and external pin persistence; refuse unpinned writes. The executed pilot persisted pins after every wave in a separate JSON file and continued automatically. No training/worker execution on owner's PC during this turn. OS telemetry polling is best-effort, not a hard allocation guarantee; estimates need qualification. Tests involving actual processes require sufficient memory and supported OS; full suite not run.

Next dependencies: authenticated external pin storage, atomic campaign receipts + pin journal, semantic dedup/group policy, independent real-teacher corpus acquisition and provenance, validation-only selection and final hidden holdout, stronger drift and uncertainty tests, resource-qualified teacher inference and eventual student adapter training, real federation handoff without altering existing live routes. The 40 scoped candidate weights are toy routing learners only, not a production federation. No live broker, scheduler, paid provider, model acquisition or default-runtime changes.

Latest read-only PC evidence: acquisition transcript still 176 lines, first Qwen3.6 27B attempt 1, pre-pull available SSD 24.32 GB; default bartowski manifest directory showed only Qwen3 8B IQ2_M. Three large-model completion and actual transfer progress remain unverified. No duplicate pull, storage cleanup or model loading initiated. 5 GB SSD reserve plus 0.5 GB staging, 1.8 GB physical RAM reserve remain unchanged. Prior PowerShell command-validation blocker has not been resolved; use native read-only inspection and preserve owner local process. Existing 3 scheduled non-Codex loops unchanged.

Coordination claims: 5f74ee798a68064d412c784264820e08ed9f214f (adaptive), 06e07e408bd4a29d53f6caa38361db2a7db674c0 (agent lab), aacf4b4f4af3ea170932febc7d95e33c80e22d50 (campaign). Compiled collision view stale; narrow path checks and exact branch readback performed.
