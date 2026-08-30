# Task 3 Implementer Report

## Summary

Exposed the guarded `nous_run.py migrate --to-schema 2 --authorize coordinate`
CLI adapter. The parser accepts only schema target `2`; dispatch requires
coordinate authorization, requires `remote-required` mode, calls the remote
backend migration, and emits exactly `branch`, `changed`, `from_schema`,
`tip`, and `to_schema`. The migration branch runs before `_combined()`, so it
does not create local mutex, receipt, claim, run, or sentinel state.

## Red evidence

Added the specified parser, authorization/mode, and output tests first. The
brief's command initially stopped during repository pytest collection because
`tests/conftest.py` imports unavailable `langgraph` (exit 4). Re-running the
same three tests with `--noconftest` reached the intended failure:

```text
FFF [100%]
3 failed in 0.63s
```

Failures showed `migrate` missing from parser choices; the two migrate tests
could not parse the absent subcommand.

## Files

- `scripts/nous_run.py` — added the `migrate` parser and guarded early dispatch.
- `tests/unit/scripts/test_nous_run_cli.py` — added `SchemaMigration` import,
  command-set assertion, and the two specified migrate tests.

No plan, progress ledger, backend semantics, or other documentation files were
modified.

## Tests and results

- Focused CLI tests with `--noconftest`: **3 passed**.
- Full `tests/unit/scripts` with `--noconftest`: **146 passed**, 4 existing
  `PytestUnknownMarkWarning` warnings.
- Exact full CLI-file command was blocked at collection by missing `langgraph`.
- `python3 scripts/nous_run.py --help`: passed; exposes `migrate`.
- `python3 scripts/nous_run.py migrate --help`: passed; exposes `--to-schema
  {2}` and `--authorize` without environment values.
- Real CLI smoke checks as `clawdbot`: missing authorization exited **4**;
  authorized local mode exited **4** before any backend call.
- `ruff check scripts/nous_run.py tests/unit/scripts/test_nous_run_cli.py`:
  all checks passed.
- `git diff --check`: passed.

## Commit

Implementation and tests were committed as:

`0bfc244d24639f1920a6da74d9b7475c486d5efe`

Commit message: `feat(nous): expose guarded schema migration`

## Self-review

- Authorization is checked before mode and before `_remote()`.
- Local mode is rejected with `ValidationError`, which existing `main()` maps
  to exit 4.
- Existing `Conflict` handling maps live-claim conflicts to exit 2.
- Output is built from only the five required fields and is JSON-sorted.
- The test fake asserts target `2` and returns the complete `SchemaMigration`.
- No real migration, claim, cutover, or NOUS tick was executed.

## Risks and deferred issues

- The standard pytest invocation remains unavailable in this environment until
  the repository's missing `langgraph` dependency is installed; isolated CLI
  tests provide the focused evidence above.
- Live remote CAS/conflict behavior was not exercised against a real remote by
  design; it remains covered by the existing `GitBackend` implementation and
  `main()` exception mapping.
