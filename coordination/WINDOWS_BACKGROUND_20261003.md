# Windows background console repair

Request: recurring Git windows should remain in the background.

Owner: this takeover session. Branch: `codex/windows-background-console-20261003`.
This lane covers only subprocess launch policy, provenance Git probes, trainer
revision probes, CSV fetch subprocesses and plant-supervised workers.

## Root cause and intended behavior

The main engine starts hidden, but its Git children were launched without
Windows `CREATE_NO_WINDOW`. Output capture does not itself suppress creation
of a console. Plant workers requested a new process group but also omitted
the no-window flag. A shared platform helper now supplies the Windows flag;
POSIX launches retain their existing options. Plant workers retain their
process-group flag and redirected log streams. Deliberately opened `.bat`
and PowerShell launchers retain their existing foreground behavior.

Reference: https://docs.python.org/3.11/library/subprocess.html

## Verification

Four regressions failed at the production-to-subprocess boundary before the
fix. Seven focused tests pass locally; the real Windows `GetConsoleWindow`
test is skipped on Linux and must execute in the hosted Windows contract job.
Tests assert both the no-console setting and preserved provenance results /
worker log redirection. Full local suite: 1,854 passed and 2 platform skips
in 94.65 seconds. Hosted Windows qualification passed: standard checks and actual no-console
contract run 37105836394. Integrated as #305. See TAKEOVER_VERIFIED_20261003.md.

This repository contains no Windows Task Scheduler installer or task action
definition to edit. The user's installed scheduled task actions and desktop
have not been observed. The code repair covers the repository-owned child
launches; machine-level elimination of every popup requires applying this
revision and observing the original recurrence on the user's PC.

No Git credential changes, schedule changes, broker operations, market-data
claims, holdout scoring, strategy changes or execution authorization.
Rollback: revert this bounded subprocess-policy delta.
