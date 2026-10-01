# AION / PARALLAX shared agent handoff — 2026-09-23

Status: additive research handoff for review. Icarus execution, Pulse, existing agent assignments, and DAEDALUS holdouts are unchanged. Read `OVERRIDE.md`, `ASTRA_DO_NOT.md`, `GOAL.md` and the task owner files before working in this repository.

## What is here

- `PARALLAX-PROPOSAL.md` describes the proposed CSV-first market-state atlas. PARALLAX is **not implemented**.
- `icarus-aion-source-v0.1.zip` is the complete 30-file AION source snapshot from local commit `b741829` (`git archive` with the `icarus-aion/` prefix). SHA-256: `32ca851227bbce99d58df1e39fb69ac08f9fc2f42ba5a05239018f624dc1ce40`. Unzip outside the Icarus execution tree; read its `AGENTS.md`, `CLAUDE.md`, `docs/CURRENT.md`, and `docs/INTEGRATION.md` before changing contracts. The snapshot does not include raw CSVs, credentials, or a broker connector.
- The source is a working research foundation with an append-only ledger, decision-time replay, evidence-tier boundary, immutable forecast/outcome records, labeled synthetic scenarios, read-only cockpit, schemas, and 11 unit tests. It is **not integrated** with Icarus, DAEDALUS, ATHENA, or ARGUS and has no validated trading result.

## Dataset checkpoint

`reppiks490/multi-level-csv` at `ce82124352762c14eb33836a5c894bc3a2a71dfe` has nine ZIPs and 626 usable CSV entries. `reppiks490/csv-data-multi-chart-type` at `a482e7d1801fa7fa5aec093960097c0051c0403c` has one ZIP and 33 usable entries. Across both: **659 usable archive entries, 542 byte-distinct contents, roughly 13.79 million data rows**. These are physical entries, not proven independent signals. The owner expects about 800; the remainder is unresolved. The second archive includes ETHUSD; inventory only, respecting `ASTRA_DO_NOT.md`'s restriction on model/engine work.

## Verification and next owner

Locally on 2026-09-23, `python -m unittest discover -s tests -q` passed 11/11, `python -m compileall -q aion tests` passed, and the source ZIP passed `unzip -t`. No real-data, live-feed, sibling adapter or full-corpus acceptance was run. Before implementation, reconcile the remaining archives and their source clocks, then review live private sibling contracts and get the relevant owner to accept read-only adapters. Do not infer book/order-flow evidence from TradingView candle exports or spend protected holdouts to choose examples.

This file is a transfer checkpoint. A later agent should record its branch, exact git commit, source manifests, tests and remaining risks after each substantive change; replace the ZIP with a native source tree or a dedicated canonical repository once ownership is settled.
