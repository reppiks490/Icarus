# ICARUS current restart

Use the [current pinned restart guide](docs/recovery/PRIME_AS_IS_RESTART.md).

Current runtime/UI source: `c8bd8d49d9fc759067c75ee76157b812ce287775`; tree `98533b4e053d6cc13447c4decd62f5b327385f3c`; branch `prime/as-is-restart-20261022`, [PR #471](https://github.com/reppiks490/Icarus/pull/471). Code remains on that branch; main received documentation only.

The guide provides a guarded UI update for an already running, clean exact `7aa3900` installation, plus a full controlled restart, 35-symbol Main command, independent CC controls, verification and rollback. Old instructions are [archived with their original bytes](docs/recovery/archive/2026-10-24/INDEX.md).

New focused Chromium and presentation/client checks pass. The wider browser run passed 93 checks; a final test-only fixture correction passed three focused checks. Final-source hosted browser and both Linux jobs passed. The two Windows jobs are still running; their results and owner-PC observation remain pending. Cloud verification does not certify owner-PC runtime or full-system readiness. `execution_authorized=false`.
