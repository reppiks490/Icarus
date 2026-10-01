# ICARUS Masterbuild Handoff — 2026-09-24

This directory is the repo-native handoff package for the current ICARUS/AEGIS expansion cycle.

## Purpose

Preserve the working engine while increasing research rigor, data integrity, execution realism, observability, and integration capacity without introducing unsupported claims, fabricated data, or silent degradations.

## Baseline

- Repository: `reppiks490/Icarus`
- Baseline commit: `007e70189945b8e112904cf92b2b1a12e43792d6`
- Handoff branch: `icarus/masterbuild-handoff-2026-09-24`
- Status: architecture/reconnaissance package plus minimal CI correction
- Mainline engine behavior: intentionally preserved

## Read order

1. [SYSTEM_ASSESSMENT.md](SYSTEM_ASSESSMENT.md) — current maturity and evidence-backed strengths/gaps.
2. [FINDINGS_LEDGER.md](FINDINGS_LEDGER.md) — verified findings, blocked paths, and non-claims.
3. [ARCHITECTURE_EXPANSION.md](ARCHITECTURE_EXPANSION.md) — target architecture and invariants.
4. [PROVIDER_MATRIX.md](PROVIDER_MATRIX.md) — data/provider capability and entitlement state.
5. [RESEARCH_GOVERNANCE.md](RESEARCH_GOVERNANCE.md) — anti-overfitting and evidence rules.
6. [INTEGRATION_PROTOCOL.md](INTEGRATION_PROTOCOL.md) — contract for incoming agents/tools.
7. [ROADMAP.md](ROADMAP.md) — implementation order and promotion gates.
8. [integration_manifest.json](integration_manifest.json) — machine-readable handoff metadata.

## Core invariants

- No new feature may silently weaken reproducibility, temporal integrity, risk controls, or data provenance.
- Missing, stale, unauthorized, proxy-only, or otherwise unsupported data must reduce authority, never increase it.
- Research output never directly authorizes live execution.
- Broker/exchange truth and engine intent must remain separate concepts.
- Any "improvement" must have an explicit test, falsification path, and rollback.
- Complexity is accepted only when it contributes independent, measurable information or safety.

## Immediate change included in this branch

The GitHub Actions workflow invoked `icarus_plant` with the global `--root` argument after the `setup` subcommand. The CLI parser defines `--root` globally. This branch corrects the Linux and Windows workflow command ordering only; it does not alter engine semantics.
