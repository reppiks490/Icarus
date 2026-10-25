# Maintainer workspace

> [!CAUTION]
> **PROPRIETARY — ALL RIGHTS RESERVED**
>
> **No public license or personal-use license is granted.** Except where [LICENSE.md](LICENSE.md) preserves applicable law, GitHub platform rights, third-party terms, or prior valid permissions, written authorization is required to use, run, copy, modify, redistribute, or sell covered material. Do not remove ownership notices or claim this work as your own.
>
> Unauthorized infringement may lead to takedown requests and legal proceedings for available remedies. Public visibility is not permission to reuse.

This workspace is maintained for its owner and authorized collaborators. Permission requests and the full terms are in [LICENSE.md](LICENSE.md).

<details>
<summary>Maintainer documentation</summary>

# DIVINE PROVIDENCE: THE HEART OF ICARUS

Paper trading engine, local Plant supervisor and selected-workspace dashboards. ICARUS spans a federation of repositories; this repository owns the local runtime launcher documented here.

**[Current restart: START_HERE.md](START_HERE.md).** The current paper code release is pinned to `a21507b8b9bb46ec418a0a9b89fae448fb3eae96`. The operator guide backs up existing private state, applies the all-asset defaults, and verifies warm local health. Live execution is disabled; hosted checks do not certify the owner's PC or phone.

**[APEX Ω research layer](docs/icarus/APEX_OMEGA.md).** APEX is an evidence-bounded, research/shadow-only layer; it does not authorize execution or production decisions.

The previous README and operator instructions are preserved in [the historical archive](docs/recovery/archive/2026-10-23/INDEX.md). Their startup commands are superseded by the current guide. Existing technical specifications and source evidence retain their original scope.

## License and ownership

Copyright (c) 2026 reppiks490. **Proprietary — all rights reserved.**
Public visibility does not grant permission to reuse, redistribute, sell, or claim this work as your own. Written permission is required except where applicable law, existing grants, third-party terms, or GitHub's terms provide otherwise. See [LICENSE.md](LICENSE.md) for the full notice and permission requests.

## ICARUS Mobile

The native iOS/Android client lives under [mobile/](mobile/README.md). It does not expose the loopback engine directly and does not carry the engine admin token. A separate `icarus-mobile-gateway` performs device pairing, rotating refresh credentials, short-lived sessions, curated observation routing, and live snapshot delivery. It permits explicit rate-limited backtest requests but blocks trade-state mutations.

Architecture and deployment: [docs/icarus/MOBILE_APP.md](docs/icarus/MOBILE_APP.md). Security contract: [docs/icarus/MOBILE_SECURITY.md](docs/icarus/MOBILE_SECURITY.md).

</details>
