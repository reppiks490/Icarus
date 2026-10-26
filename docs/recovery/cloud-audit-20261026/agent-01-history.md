# Agent 01 — history and branch coverage

Read-only evidence collected 2026-10-26; no network, source edits, or tests. Read Icarus AGENTS.md, central START_HERE/ACTIVE/collisions and owner-contact/reclamation guidance.

- `github-public-branch-heads.json` inventories 85 public repositories and 18,366 branch names, with no recorded API errors. It is a branch-tip inventory, not a code audit or proof of complete Git history.
- Local Icarus is non-shallow, 3,412 reachable commits, HEAD `798b6776`; Engine is non-shallow, 10,194 commits, HEAD `6b9d30991`. Each checkout exposes only `work`, the cloud-readiness branch, and `origin/main`. Non-shallow does not imply all remote branches were fetched.
- Of inventory tips, Icarus has 225/518 reachable locally; 293 are absent. Engine has 105/199 reachable; 94 are absent. No missing tip exists as an unreferenced local commit. Their unique changes cannot be audited locally under this task's no-network constraint.
- Existing `github-relevant-branch-comparisons.json` covers only 11 branches overall. Recovery candidates: Icarus immersion fix (2 ahead, world-immersion.js/browser_depth.cjs), paper-workspace API (5 ahead, backend/isolation tests); Engine provider guards (4 ahead, registry/Sentinel freshness/timezone checks), ingestion closure (65 ahead). Counts are recorded comparisons, not patch-uniqueness proof.
- Already-behind Windows restart gates and market-data integration merit no blind cherry-pick. Postmerge verification branch has two documentation commits; reconcile current docs first.

Action: fetch immutable missing tips in an authorized follow-up, compare patch IDs and current implementations, inspect candidate diffs/tests, then recover only demonstrably missing behavior. Preserve dirty local work and paper-only execution gates. Full branch/history review remains incomplete; no PC readiness conclusion follows from this inventory.
