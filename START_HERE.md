# Current ICARUS restart

Use the **[current restart guide](docs/recovery/PRIME_AS_IS_RESTART.md)** for backup, exact-version verification, Windows setup, the expanded Main asset list, independent CC1–CC4 paper worker switches, dashboard URLs, diagnostics and rollback.

Install **`7aa3900282213c4e690436098702300a0447cb8d`** from `prime/as-is-restart-20261022` ([PR #471](https://github.com/reppiks490/Icarus/pull/471)). Runtime code is on the restart branch; a documentation update on main does not install it. Fetch and verify the pinned revision before switching.

This as-is paper build retains each CC's saved configuration and journals. Full-system readiness remains NO_GO; live execution stays disabled and `execution_authorized=false`. Owner-PC operation and the reported fault's cause require local verification after launch.

Fresh final verification: **4,083 local tests and 111 subtests passed, with separately exercised Chromium controls; see the guide and immutable delivery receipt for exact boundaries and hosted outcomes**. Earlier test counts belong to [archived instructions](docs/recovery/archive/2026-10-23/INDEX.md).

