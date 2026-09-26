# Current Findings — 2026-09-24

These findings distinguish direct repository observations from architectural conclusions. They are intentionally conservative because GitHub code search is not indexed for this repository, so negative search results must not be treated as proof of absence.

## Directly verified repository observations

Repository: `reppiks490/Icarus`  
Default branch: `main`

### README-observed runtime split

The repository documents two independent "brains":

- **Brain A — live signals:** TradingView Pine on `CME_MINI:NQ1!`, with alerts mapped to Alpaca paper `QQQ` through `icarus-bridge`. The README explicitly describes this as a percent-mapped equity proxy rather than a futures fill.
- **Brain B — Python engine:** Yahoo `NQ=F` or a chart export already owned by the user, feeding an internal emulator with CME contract specifications, RTH handling, and Heikin-Ashi/tick-quantization behavior.

The README also explicitly states that the two brains do not share a tape.

### Plant / local infrastructure

The README documents:

- `icarus-plant` as a local data-directory/process supervisor.
- Loopback binding at `127.0.0.1`.
- `GET /healthz` as the health endpoint.
- Offline/file-feed mode via `ICARUS_FEED=file`.
- FileFeed history under `history/{SYM}_*m.csv`.
- No invented empty minutes.
- Roll forced to `none` in the documented offline path so FileFeed volume cannot fake a CME continuous-contract roll.

### Package / CLI surface

The directly read `pyproject.toml` defines:

- Python >= 3.10.
- Base dependency: `tzdata`.
- Optional bridge dependencies: `fastapi`, `uvicorn`, `httpx`.
- Optional development dependency: `pytest`.
- Optional ML dependency: `xgboost>=2.0`.
- CLI entrypoints:
  - `icarus-engine = icarus_engine.cli:main`
  - `icarus-bridge = icarus_bridge.cli:main`
  - `icarus-plant = icarus_plant.cli:main`
  - `icarus-train = icarus_engine.trainers.__main__:main`
- Package discovery includes `icarus_engine*`, `icarus_bridge*`, `icarus_plant*`, and `icarus_agent*`.
- Pytest points at `tests_engine`.

### Control-state observation

`state.json` is directly observed as:

```json
{}
```

### Instruction-file observation

`instruction.txt` currently instructs an agent to:

- inspect the first 760 CSV files,
- extract mathematical trend features and successful trading patterns,
- write final mathematical values directly into `state.json`,
- then transition to a later phase.

## Architectural findings derived from those observations

### F1 — Executable surface is more mature than durable control-state surface

The repo documents engine, plant, bridge, ingest, backtest, parity, import, run, doctor, and test surfaces, while the directly observed `state.json` has no structured policy, evidence, claim, revision, or provenance fields.

This is a major coordination gap for multi-agent evolution.

### F2 — Direct overwrite of `state.json` is unsafe as a long-term research contract

The current instruction pattern asks for final values to be written directly into a single state object. That approach does not by itself preserve:

- source identity,
- revision identity,
- claim lineage,
- dependency lineage,
- conflict state,
- raw observation hashes,
- estimator validity,
- ablation status,
- temporal availability,
- test-oracle provenance,
- holdout separation,
- policy epoch.

Therefore this coordination package recommends making `state.json` a compact index/pointer layer rather than a dumping ground for unqualified research conclusions.

### F3 — External provider breadth should not be wired directly into strategy semantics

The user has access to multiple market, financial, literature, web, blockchain, media, design, orchestration, and research systems. Their safest role is evidence acquisition and diagnostics behind a canonical normalization/provenance boundary.

### F4 — Model sophistication must be authority-capped

The presence of an optional XGBoost dependency is directly verified. Any XGBoost, Kalman, Hurst, FDI, Lorentzian, DFA, Ehlers, CCI, regime, adaptive-weighting, or future composite mechanism should be evaluated through temporal-integrity, calibration, redundancy, stress, and holdout gates before being allowed to influence production authority.

### F5 — Repository search limitations are material

The repo is currently not indexed by the connected GitHub code-search service. Consequently:

- this document does **not** claim that unobserved control-plane code is absent;
- future agents must inspect concrete files or use compatible repository tooling before asserting absence;
- negative search results alone are non-authoritative.

## Current safe conclusion

The highest-value expansion is a layered **capability fabric** around the existing engine, not an uncontrolled rewrite of the strategy core.

The package in this directory is deliberately additive so future agents can connect through stable contracts first, inspect the canonical code second, and only then propose evidence-backed changes.
