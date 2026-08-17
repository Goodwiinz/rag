# Evidence API Review Repairs Design

**Date:** 2026-08-17
**Scope:** PR #1432 follow-up repairs for stale provenance, request bounding,
model identity, synchronous-session lifetime, and local migration-probe reporting.

## Context

The source-grounding implementation is functionally complete, but the final review
found five production risks. The repair must preserve the existing API shape and
tenant isolation while tightening the meaning of “current source,” moving cheap
rejections ahead of database materialization, making model provenance honest, and
ensuring an async LLM wait never pins the evidence service's small synchronous SQL
pool.

## Chosen design

### Current-revision breakdown

`source_loader.py` will expose one pure content-revision helper. It hashes the
current extracted `Document.content_text` as UTF-8 and returns no revision for
null or blank content. The uploaded-file checksum is deliberately not used for
evidence identity, because extracted text can change while that checksum remains
unchanged. Both source loading and `/breakdown` will use that helper.

`/breakdown` will project only the required columns from tenant-scoped, active,
completed candidates in its existing deterministic order, stream those candidates,
discard rows whose persisted `source_content_hash` does not equal the current
extracted-text revision, and stop after collecting `offset + limit` current rows.
This makes pagination operate on the visible current result set, so a stale
high-confidence row cannot consume a page slot without materializing an unbounded
candidate set.

An alternative was to trust the uploaded checksum or compute a SQL-only hash
expression. Trusting the uploaded checksum was rejected because it can remain
unchanged when extracted text changes. A SQL-only expression was rejected because
the hash must exactly match Python's UTF-8 SHA-256 behavior across SQLite tests and
PostgreSQL production; sharing one pure helper is less drift-prone.

### Early source limit and session lifetime

The classifier will expose one synchronous batch-size validator, and retain its
existing validation inside `classify_sources_batch` as defense in depth. Both
`/meter` and `/classify` will call the same validator immediately after parsing IDs
and before `EvidenceSourceLoader.load`, returning the existing 400 message for more
than 100 sources.

After the loader has copied all required ORM values into immutable source value
objects, each endpoint will roll back the read-only transaction before its first
cache or LLM `await`. The same session can safely autobegin a new transaction later
for persistence. Closing the session was rejected because the dependency owns its
lifetime and the endpoint still needs it for writes.

### Model and classifier provenance

The code will distinguish two identities:

- `model_version` on each classification result is the exact OpenAI model that
  produced the selected result, including a selected fallback.
- `classifier_version` is a stable, collision-resistant fingerprint of the complete
  classifier configuration: implementation generation, exact primary model, exact
  fallback model, and fallback threshold.

Stance cache keys, meter cache keys, persisted row selection, breakdown selection,
and consensus reproducibility will use `classifier_version`. The existing database
`model_version` column remains the pipeline/uniqueness namespace for compatibility;
its model documentation will be corrected. A new nullable
`inference_model_version VARCHAR(100)` column will store the actual producing model.
New writes always populate it; nullable preserves upgrade compatibility for legacy
rows. The existing in-flight provenance migration and its targeted probe will add
and verify this column.

Reproducibility hashes will contain a truncated SHA-256 digest of the full classifier
identity, never a token obtained by splitting a model name on `-`. The consensus
calculator will receive the classifier version explicitly instead of carrying an
independent hardcoded model.

An alternative was to store the actual model directly in the existing uniqueness
column. It was rejected because one source can switch between primary and fallback;
that would create duplicate breakdown rows or require destructive history cleanup.

### Local migration-probe reporting

The targeted migration probe still blocks when it executes and fails. Exit code 2
means the local machine has neither a usable disposable PostgreSQL instance nor
Docker; that outcome will be recorded through the existing `skipped` mechanism and
will not be added to the failure list. GitHub Actions continues to provide
PostgreSQL, so the authoritative CI probe remains blocking.

## Safety and compatibility

- Tenant and current-model filters remain mandatory on every breakdown query.
- Stale and legacy rows fail closed; they are never rendered as current evidence.
- Public JSON field types do not change. Internal `/classify` and health model
  strings identify the classifier pipeline, while actual per-source models remain
  available in persisted provenance.
- Real migration execution failures remain failures; only the explicit environment
  unavailable status is a skip.
- Every repair is test-first, committed separately, and reviewed before the next
  repair builds on it.
