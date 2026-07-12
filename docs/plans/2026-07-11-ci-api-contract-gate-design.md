# CI API contract gate design

## Problem

The `api-contract-tests` job is listed as a blocking lane by `test-summary`, but
its pytest step has `continue-on-error: true`. GitHub therefore reports the job
as successful even when pytest fails. The latest successful `develop` pipeline
demonstrated the defect: pytest exited 4 because `faker` was missing, while both
`API Contract Tests` and `Test Summary` remained green.

Further investigation showed the job does not point at a test suite at all:
`backend/tests/api_contract/` does not exist. The similarly named
`tests/api_contract/` suite is 7,587 lines of stale tests and cannot collect
against the current auth API. Adding Faker and making the job blocking would
therefore replace a false green gate with a permanently red one.

## Approved design

Remove the dead job and every `test-summary` dependency, environment variable,
table row, and blocking-lane reference that advertises it as a gate. Preserve
the stale suite for a separate, explicitly scoped contract-test rebuild. Add a
static regression test that prevents the dead job or its summary claims from
being restored accidentally.

## Verification

Use a red/green cycle for the static workflow regression test, parse/lint the
workflow, and verify no contract-job identifiers remain in the workflow.

## Delivery boundary

Commit the narrow workflow and regression-test change, review the diff, push the
branch, and open a draft PR targeting `develop`. Do not merge or deploy without
explicit user approval.
