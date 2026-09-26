# Assurance Archive Source Manifest

Transfer date: 2026-09-24.

This manifest records how prior chat/library artifacts were moved into the repository. It distinguishes verbatim text transfer from extracted/reconstructed material.

| Source artifact | Source type / size | Repository destination | Transfer mode |
|---|---|---|---|
| `ICARUS_AEGIS_FULL_DOSSIER.txt` | text/plain, 17,620 bytes | `archive/ICARUS_AEGIS_FULL_DOSSIER.txt` | full text read from Library and written as UTF-8 text |
| `ICARUS_AEGIS_MASTERBUILD_FULL_HANDOFF.md` | text/markdown, 33,607 bytes | `archive/ICARUS_AEGIS_MASTERBUILD_FULL_HANDOFF.md` | full text read from Library and written as UTF-8 text |
| `ICARUS_S3_COMPLETE_HANDOFF.txt` / equivalent Library S3 handoff | text, ~29,346 bytes | `archive/ICARUS_S3_COMPLETE_HANDOFF.txt` | full text read from Library and written as UTF-8 text |
| `ICARUS_Unified_Control_Cycle_Master_Handoff_20260924-07.docx` | DOCX, 44,148 bytes | `archive/ICARUS_Unified_Control_Cycle_Master_Handoff_20260924-07.txt` | extracted document text; original binary DOCX was not written through the UTF-8-only GitHub file connector |
| `ICARUS_AEGIS_WORKLOG.md` | markdown; local generated copy 25,382 bytes | `archive/ICARUS_AEGIS_WORKLOG.md` | full text read from conversation file and written as UTF-8 text |
| `stage5_final_receipt.json` | JSON inside prior downloadable work package | `archive/stage5_final_receipt.json` | reconstructed from the final in-session Stage-5 receipt fields; includes the SHA-256 recorded in-session |

## Synthesized repository-native artifacts

The following were created during consolidation rather than copied verbatim:

- `AEGIS_ASSURANCE_BASELINE_V1.md` — compact Findings 001–030 baseline.
- `CONTROL_PLANE_IMPLEMENTATION_MAP.md` — latest implementation-assurance architecture.
- `RELATED_BUILD_REGISTRY.md` — connected-GitHub repository/branch discovery with observed revisions.
- `CHANGE_RECORD_2026-09-24.md` — provenance for the transfer.
- `README.md` and root `ASSURANCE_INDEX.md` — navigation only.

## Integrity / authority caveat

Line-ending normalization, DOCX text extraction, and reconstructed JSON mean this archive is not a byte-for-byte binary mirror of every source container. It is intended to preserve the substantive text/evidence context. Original implementation claims must still be verified against repository code and pinned tests.

## Stale when

This manifest is historical and should not be rewritten when current repository state changes. Add a new transfer manifest for later archive batches.
