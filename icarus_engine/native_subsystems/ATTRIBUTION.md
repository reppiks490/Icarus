# Embedded Divine Providence native cores

These four source modules are reproduced byte for byte from
[reppiks490/divine-providence](https://github.com/reppiks490/divine-providence)
at commit [27ae69c593ede3019957100cd401625bd2424f43](https://github.com/reppiks490/divine-providence/tree/27ae69c593ede3019957100cd401625bd2424f43),
tree `bde186e028d14f79a70b4408e3d94a79d3bc32c7`:

- NEXUS: `systems/nexus/src/nexus/contracts.py` and `source_health.py`.
- AION: `systems/aion/aion/contracts.py` and `store.py`.

`source_manifest.json` records each original path, Git blob identity, SHA-256
and byte count. The integrity regression checks all four against independent
pinned expected values. Preserve the source bytes when updating; use the
ICARUS receiving adapter for runtime-specific behavior.

The pinned upstream tree contains no LICENSE, COPYING or NOTICE file. No
upstream license or additional redistribution grant is asserted here. Original
source attribution remains with the named repository and its contributors.

The package initializers in this directory are ICARUS loading adapters, not
copies of upstream package initializers. They avoid NEXUS's eager imports of
its wider numerical stack. The four embedded modules use only Python's
standard library and add no runtime dependency.

Upstream packages declare Python >=3.11. ICARUS supports Python >=3.10 for
this embedded subset, verified using an actual Python 3.10 interpreter with
site initialization disabled. The exercised boundary is native VectorEvent,
SourceHealthRegistry/SourceHealthPlane and AION SourceSpec/Observation/EventStore,
including SQLite reopen, receipt-time visibility, idempotency, revisions and
hash-chain verification. This compatibility claim does not apply to the full
upstream packages or other Divine Providence systems.

The native source remains research/evidence infrastructure. A successful
health-plane or hash-chain check grants no execution, broker, promotion or
production authority. Adapter-local observation sequences and receipt clocks
do not establish upstream provider sequence continuity, reviewed SLOs,
true-trade/depth quality or market-data entitlement.
