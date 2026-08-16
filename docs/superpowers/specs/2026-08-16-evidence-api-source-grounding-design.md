# Evidence API source-grounding repair — design

Date: 2026-08-16
Status: approved (brainstorm), pending implementation plan
Pull request: #1432 (`codex/disable-fabricated-evidence-api`)

## Goal

Keep the four documented `/api/v1/evidence` endpoints while eliminating the
fabricated content that made their results unsafe. Evidence analysis must use
real document text owned by the authenticated organization, expose real source
titles and claim text, and count a stance only when its justification is
grounded in the supplied document excerpt.

The endpoint paths and existing response fields remain compatible. Additive
retraction-status fields may clarify that external publication retractions have
not been checked. The existing frontend hooks and components remain available,
although no active page mounts them today.

## Approach

Repair the existing API around a small source-loading boundary instead of
disabling it or adding a broad external-publication integration.

1. Add a tenant-scoped evidence source loader backed by `Document`.
2. Select bounded, claim-relevant excerpts directly from `Document.content_text`.
3. Validate that each model-produced justification is present in that excerpt.
4. Persist enough provenance to reconstruct a breakdown without placeholders.
5. Preserve the public endpoints, regenerate the OpenAPI snapshot and frontend
   types, and replace placeholder-oriented API tests with source-grounding tests.

## Source-loading boundary

Create `backend/src/services/evidence/source_loader.py` with two focused units:

- `EvidenceSourceLoader` loads requested UUIDs in one query and returns ordered
  source records containing document ID, title, excerpt, and content revision.
- `ClaimExcerptSelector` deterministically selects source text for the stance
  classifier without generating or paraphrasing content.

The loader receives the authenticated `organization_id`; the request cannot
override it. It queries `Document` by the requested IDs and organization. A user
without an organization fails closed. Unknown IDs and IDs owned by another
organization produce the same generic 404 response, with no title, ID, or count
detail that could reveal another tenant's data.

Within the caller's organization:

- active documents require non-empty `content_text` and a completed processing
  status;
- documents that are not ready produce a generic 409 before any model call;
- soft-deleted documents are treated as withdrawn workspace sources, excluded
  from classification, and counted in the existing `retracted_sources` field;
- if no active source remains, the request is rejected before classification.

The returned source order matches the caller's requested order so classifications,
cache inputs, and tests are deterministic.

Duplicate source IDs are rejected with 400 rather than classified twice and
double-counted in consensus.

## Excerpt selection and grounding

The selector operates only on the stored `content_text`. It considers bounded
overlapping windows, scores them by normalized claim-term overlap, and returns
the single highest-scoring contiguous original-text window with a 12,000-character
budget. When no claim term occurs, it returns a bounded prefix of the original
text so the classifier can honestly choose `not_addressed`.

The selector never summarizes, rewrites, or invents text. Its output must always
be a contiguous substring of the source.

The stance prompt asks for a short exact quotation as
`justification_excerpt`. After the model returns, the classifier validates the
quotation against the selected source excerpt using whitespace-normalized
matching. A classification whose quotation cannot be grounded is discarded and
does not contribute to consensus or persistence. This keeps a plausible but
unsupported model response from becoming evidence.

The batch classifier continues to tolerate individual classification failures.
`total_sources` describes successfully grounded classifications, as it does for
other per-source failures today. If none succeed, the meter returns the existing
`insufficient_data` result with zero classified sources rather than fabricating a
stance.

## API behavior

### `GET /api/v1/evidence/meter`

Keep the current claim and source-ID inputs. Load every source through the new
tenant boundary, classify only real excerpts, exclude withdrawn documents, and
calculate consensus from grounded results. The optional `query_id` remains
accepted for compatibility.

The organization-scoped meter cache must include source content revisions, not
only UUIDs. A revision is `Document.checksum_sha256` when present and otherwise
SHA-256 of `content_text`. Changing a document therefore invalidates both the
meter cache and reproducibility input without changing its UUID.

### `POST /api/v1/evidence/classify`

Use the same loader, readiness checks, excerpt selector, grounding validation,
and persistence path as `/meter`. The endpoint must not maintain a second source
resolution implementation.

### `GET /api/v1/evidence/breakdown`

Read classifications by claim hash, model version, and authenticated
organization. Resolve their source metadata through active `Document` rows in
that same organization, return real titles, and return the persisted original
claim. Legacy rows without a persisted claim or an accessible active source are
not rendered with fallback text; if no complete result remains, return the
existing generic 404.

### `GET /api/v1/evidence/health`

Keep the endpoint and its contract. Health reports component availability only;
it does not imply that an external publication-retraction provider is configured.

## Retraction semantics

This change does not claim to verify Crossref, Semantic Scholar, publisher, or
other external retraction records. The existing `retracted_sources` count means
workspace sources withdrawn through the repository's soft-delete lifecycle.

Add explicit, additive publication-retraction fields to evidence responses:

- `EvidenceMeter.publication_retraction_check` is the enum value
  `not_performed`;
- `StanceBreakdownItem.publication_retraction_status` is the enum value
  `unknown`.

Define the enum vocabularies now so a later provider can add checked or retracted
states without renaming these fields. This PR emits only the two honest values
above.

Frontend labels must not describe `0` workspace withdrawals as proof that a
publication is not retracted. A future provider integration can extend the
status vocabulary without changing source loading or stance classification.

## Persistence and cache changes

Add nullable `claim_text` and `source_content_hash` columns to
`stance_classifications` with an Alembic migration. They remain nullable for
legacy rows, but every new `/meter` and `/classify` write supplies both values.

Keep the existing tenant-aware uniqueness key
`(claim_hash, source_id, model_version, organization_id)`. On conflict, update
the stance, confidence, grounded excerpt, claim text, source content hash, and
timestamp. This makes a changed document replace its stale classification for
the same model rather than creating ambiguous duplicate rows.

Rename the meter cache's internal source-key argument to source revisions and
hash ordered `document_id:content_hash` values together with the organization,
claim hash, and model version. The public reproducibility hash uses the same
revision-aware inputs. The per-stance cache already includes an excerpt hash and
retains that behavior.

## Error handling and observability

Validation is atomic: resolve and validate the entire requested source set
before cache lookup, model calls, or database writes.

- 400: malformed or duplicate UUIDs, no source IDs, or no active sources after
  withdrawals.
- 404: no organization, unknown source IDs, or cross-tenant source IDs, using one
  non-enumerating message.
- 409: a caller-owned source exists but is not processed or has no usable text.
- 504: the existing batch-classification timeout.
- 500: unexpected persistence or service failures, without source content in the
  response.

Logs include organization ID, claim hash, source count, and failure category,
but never claim text, document content, or justification excerpts.

## Testing

Retain the Evidence API suite and replace placeholder-dependent assertions with
tests at the real boundary. Mock only the external model call or classifier
result where determinism requires it.

Required coverage:

- a meter request passes real stored document excerpts to the classifier;
- `/classify` uses the same source loader as `/meter`;
- cross-tenant, missing, null-organization, and mixed-tenant ID sets fail closed
  before any classifier call;
- unprocessed and contentless documents return 409 before any classifier call;
- soft-deleted caller-owned documents are excluded and counted as workspace
  withdrawals;
- selected excerpts contain only source text and obey the size budget;
- an ungrounded model quotation is discarded while a grounded quotation counts;
- cache and reproducibility keys change when content changes under the same UUID;
- breakdown returns the stored claim and real current title, never placeholder
  strings;
- breakdown cannot expose another organization's classifications or document
  metadata;
- old endpoint paths and required response fields remain in OpenAPI;
- generated backend OpenAPI and frontend TypeScript contracts are synchronized.

Run the focused evidence tests first, followed by the backend quality checks for
changed files, OpenAPI generation/check, frontend type-check, and the repository
CI workflow.

## Files in scope

- `backend/src/services/evidence/source_loader.py` (new)
- `backend/src/services/evidence/stance_classifier.py`
- `backend/src/services/evidence/cache.py`
- `backend/src/services/evidence/consensus_calculator.py`
- `backend/src/api/evidence/router.py`
- `backend/src/api/evidence/schemas.py`
- `backend/src/models/evidence.py`
- one Alembic revision for evidence provenance columns
- evidence API/service tests
- `backend/openapi.json`
- `frontend/src/types/generated/api.d.ts`
- handwritten frontend evidence types or labels affected by additive status fields
- active API and backend codemap documentation

The PR's endpoint removal, deleted API suite, and disabled-endpoint regression
test are replaced by this implementation rather than retained.

## Out of scope

- Calling external publication or DOI retraction providers.
- Mounting the dormant Evidence UI on a new product page.
- Automatically choosing source IDs from `query_id` or search results.
- Replacing the current stance model or consensus thresholds.
- Backfilling legacy claim text or content hashes that cannot be reconstructed
  reliably.

## Success criteria

PR #1432 ends as a repair rather than an API deletion: all four endpoints remain
published, no response contains fabricated source text or placeholder metadata,
all source access is organization-scoped, only grounded classifications affect
consensus, contract compatibility passes, and the full CI release gate is green.
