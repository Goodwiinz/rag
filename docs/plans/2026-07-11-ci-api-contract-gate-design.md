# CI API contract gate design

## Problem

The `api-contract-tests` job is listed as a blocking lane by `test-summary`, but
its pytest step has `continue-on-error: true`. GitHub therefore reports the job
as successful even when pytest fails. The latest successful `develop` pipeline
demonstrated the defect: pytest exited 4 because `faker` was missing, while both
`API Contract Tests` and `Test Summary` remained green.

## Approved design

Make the existing contract lane genuinely blocking without broadening its
dependency surface:

1. Install the already project-pinned `faker==25.2.0` dependency alongside
   `schemathesis` in the contract job.
2. Remove step-level `continue-on-error` so pytest's exit status becomes the job
   result consumed by `test-summary`.
3. Add a focused static regression test that reads the workflow and asserts the
   contract step installs Faker and cannot suppress pytest failures.

Installing all of `backend/requirements-test.txt` was rejected because it adds a
large unrelated test and evaluation dependency set to this job. Removing only
`continue-on-error` was rejected because the known missing dependency would make
the gate fail before exercising any contracts.

## Verification

Use a red/green cycle for the static workflow regression test, parse/lint the
workflow, and run the API contract suite in an environment containing the same
runtime dependencies. GitHub Actions remains the authoritative full-system check
because it provisions the PostgreSQL service used by the job.

## Delivery boundary

Commit the narrow workflow and regression-test change, review the diff, push the
branch, and open a draft PR targeting `develop`. Do not merge or deploy without
explicit user approval.
