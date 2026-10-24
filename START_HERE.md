# ICARUS current full restart — HIGHLY IMPORTANT

Use the [current full restart commands](docs/recovery/PRIME_AS_IS_RESTART.md) and [required NQ/ETHUSD/SOLUSD settings](docs/recovery/HIGHLY_IMPORTANT_RESTART_INFO.md).

Runtime source: `3122d349524fbce803970dc34ab6fc74dad87467`; tree `9ad37de97e160aead6602351b54c43608086a006`; branch `prime/as-is-restart-20261022`, [PR #471](https://github.com/reppiks490/Icarus/pull/471). Runtime code stays on that draft branch; main contains documentation only.

All assets use actual Main NQ strategy/chart defaults. BOTH ETHUSD and SOLUSD use 30-minute charts, RTH/session filtering disabled, quantity 25. Preparation authenticates/captures current NQ or verifies actual saved NQ when already stopped; the full restart backs up state, applies/verifies settings and launches all 35 Main assets. Journals, selected asset lists and independent CC power settings stay preserved. NEXUS/AION and request-blocking repairs are included.

Fresh local verification: 4,152 passed, 128 skipped, 111 subtests; 107 real Chromium checks passed. Exact-head hosted checks, including Windows, are running. No owner-PC success or sustained-runtime guarantee is claimed. Phone connection follows actual PC restart confirmation. Execution authority remains false.

[Previous notes are archived with original bytes](docs/recovery/archive/2026-10-24/INDEX.md).
