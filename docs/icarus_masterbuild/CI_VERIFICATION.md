# CI Verification Receipt — 2026-09-24

## Defect chain

1. Baseline workflow passed the global `--root` option after the `setup` subcommand.
2. PR #22 corrected the command to `icarus_plant --root <path> setup`.
3. Run #288 proved the correction on Linux, while Windows exposed an independent stdout encoding defect.
4. Windows traceback: `UnicodeEncodeError` for U+2192 RIGHTWARDS ARROW under cp1252.
5. Commit `dbb4098722fbf691088aa52f0ce17a39edd40996` added a subprocess regression test forcing `PYTHONIOENCODING=cp1252`.
6. Run #355 failed on that test with the expected U+2192 error: RED confirmed.
7. Commit `4abdf26ea010667fe85a2e617b2276bb88fd972c` replaced the three decorative arrows in `icarus_plant/guide.py` with ASCII `->`.
8. Run #361 completed successfully: GREEN confirmed.

## Fresh run #361

- Linux full `tests_engine`: SUCCESS
- Linux plant setup: SUCCESS
- Linux doctor: SUCCESS
- Windows selected plant/bars/doctor tests: SUCCESS
- Windows plant setup: SUCCESS
- Workflow overall: SUCCESS

Run: https://github.com/reppiks490/Icarus/actions/runs/36082169917

## Scope of claim

This verifies the current PR branch against the workflow's Linux and Windows qualification jobs. It does not imply live-trading readiness, alpha, or validation of future P1-P7 work.
