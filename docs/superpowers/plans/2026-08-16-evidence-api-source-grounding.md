# Evidence API Source-Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PR #1432's Evidence API deletion with a tenant-scoped implementation that classifies real document text and returns only grounded provenance.

**Architecture:** A new `EvidenceSourceLoader` is the sole boundary between caller-supplied UUIDs and document content. The existing router feeds its revision-aware sources into the classifier, cache, consensus calculator, and tenant-scoped persistence path; breakdown joins stored classifications back to active caller-owned documents instead of manufacturing titles or claim text.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, Pydantic v2, Redis, pytest, Next.js/TypeScript, pnpm 10.18.2, OpenAPI.

## Global Constraints

- Keep all four `/api/v1/evidence` endpoints and their existing fields backward-compatible.
- Every source read must filter by the authenticated `organization_id`; request data never supplies tenant scope.
- Unknown, missing, and cross-tenant source IDs share one non-enumerating 404 response.
- Classifier input is a contiguous substring of `Document.content_text`, capped at exactly 12,000 characters.
- A stance counts only when its whitespace-normalized quotation occurs in the selected source excerpt.
- Soft-deleted documents mean workspace-withdrawn sources, not verified external publication retractions.
- External publication retraction status is explicitly `not_performed`/`unknown`.
- Cache and reproducibility inputs include `document_id:content_hash` revisions.
- Logs must not contain claim text, document content, titles, or justification excerpts.
- New Alembic revision IDs must be at most 32 characters and preserve a single migration head.
- Use test-driven development and commit each completed task separately.
- Do not mount the dormant Evidence UI on a product page in this PR.
- Use `/tmp/rag-pr-1432.Dbvr1G/venv`; activate it at the start of each shell
  session instead of installing Python packages globally.

---

### Task 1: Sync the PR and restore the supported API contract

**Files:**
- Restore: `backend/src/main.py`
- Restore: `backend/src/api/README.md`
- Restore: `backend/tests/evidence/test_api.py`
- Delete: `backend/tests/unit/api/test_evidence_api_disabled.py`
- Restore: `docs/CODEMAPS/BACKEND.md`
- Restore temporarily: `backend/openapi.json`
- Restore temporarily: `frontend/src/types/generated/api.d.ts`

**Interfaces:**
- Consumes: live `origin/develop` and PR branch `codex/disable-fabricated-evidence-api`.
- Produces: a current branch where `evidence_router` is mounted at `/api/v1/evidence` and the original API test suite is present for repair.

- [ ] **Step 1: Install the isolated worktree dependencies**

```bash
python3 -m venv /tmp/rag-pr-1432.Dbvr1G/venv
source /tmp/rag-pr-1432.Dbvr1G/venv/bin/activate
python -m pip install --build-constraint backend/constraints-ci.txt \
  -r backend/requirements.txt -r backend/requirements.dev.txt
pnpm install --frozen-lockfile
```

Expected: `python -m alembic --version`, `pytest --version`, `ruff --version`,
and `pnpm --version` all succeed from the activated shell.

- [ ] **Step 2: Fetch and merge the live base**

```bash
git fetch origin develop codex/disable-fabricated-evidence-api
git merge --no-edit origin/develop
```

Resolve conflicts by keeping the design/plan documents and the current PR's branch commits, then continue the merge. Do not resolve a contract conflict by deleting Evidence paths.

- [ ] **Step 3: Restore the contract files from the live base**

```bash
git restore --source=origin/develop -- \
  backend/src/main.py \
  backend/src/api/README.md \
  backend/tests/evidence/test_api.py \
  docs/CODEMAPS/BACKEND.md \
  backend/openapi.json \
  frontend/src/types/generated/api.d.ts
git rm -- backend/tests/unit/api/test_evidence_api_disabled.py
```

- [ ] **Step 4: Verify the router is mounted and the deleted suite is restored**

```bash
rg -n 'evidence_router|/api/v1/evidence' backend/src/main.py backend/src/api/README.md docs/CODEMAPS/BACKEND.md
test -f backend/tests/evidence/test_api.py
test ! -e backend/tests/unit/api/test_evidence_api_disabled.py
```

Expected: the import and `app.include_router(evidence_router, prefix="/api/v1/evidence", ...)` are present; the old test file exists; the disabled regression file does not.

- [ ] **Step 5: Run the restored contract baseline**

```bash
pytest -q backend/tests/evidence/test_api.py
python3 scripts/ci/generate_openapi.py --check
```

Expected: the legacy API suite passes. OpenAPI is synchronized at this point; its unsafe behavior is addressed in later tasks.

- [ ] **Step 6: Commit the contract restoration**

```bash
git add backend/src/main.py backend/src/api/README.md backend/tests/evidence/test_api.py \
  docs/CODEMAPS/BACKEND.md backend/openapi.json frontend/src/types/generated/api.d.ts \
  backend/tests/unit/api/test_evidence_api_disabled.py
git commit -m "refactor(api): preserve evidence contract"
```

---

### Task 2: Add the tenant-scoped source loader and excerpt selector

**Files:**
- Create: `backend/src/services/evidence/source_loader.py`
- Create: `backend/tests/evidence/test_source_loader.py`
- Modify: `backend/src/services/evidence/__init__.py`

**Interfaces:**
- Consumes: `src.models.document.Document`, `ProcessingStatus`, and a synchronous `sqlalchemy.orm.Session`.
- Produces: `ClaimExcerptSelector.select(claim: str, content: str) -> str`, `EvidenceSourceLoader.load(db: Session, *, organization_id: UUID | None, source_ids: Sequence[UUID], claim: str) -> EvidenceSourceSet`, and typed classifier payloads containing `source_id`, `excerpt`, and `content_hash`.

- [ ] **Step 1: Write failing selector tests**

Add tests equivalent to:

```python
def test_excerpt_is_a_contiguous_bounded_source_substring():
    content = "A" * 13_000 + " target evidence phrase " + "B" * 13_000
    excerpt = ClaimExcerptSelector().select("target evidence", content)
    assert excerpt in content
    assert len(excerpt) <= 12_000
    assert "target evidence phrase" in excerpt


def test_excerpt_falls_back_to_source_prefix_without_overlap():
    content = "unrelated source text " * 1_000
    excerpt = ClaimExcerptSelector().select("quantum gravity", content)
    assert excerpt == content[:12_000]
```

- [ ] **Step 2: Run selector tests and verify the missing-module failure**

```bash
pytest -q backend/tests/evidence/test_source_loader.py -k excerpt
```

Expected: FAIL because `src.services.evidence.source_loader` does not exist.

- [ ] **Step 3: Implement the selector and source types**

Create these public shapes and constants:

```python
MAX_EXCERPT_CHARS = 12_000
WINDOW_STEP_CHARS = MAX_EXCERPT_CHARS // 2


class ClassifierSource(TypedDict):
    source_id: UUID
    excerpt: str
    content_hash: str


@dataclass(frozen=True)
class EvidenceSource:
    source_id: UUID
    title: str
    excerpt: str
    content_hash: str

    @property
    def revision(self) -> str:
        return f"{self.source_id}:{self.content_hash}"

    def classifier_input(self) -> ClassifierSource:
        return {
            "source_id": self.source_id,
            "excerpt": self.excerpt,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class EvidenceSourceSet:
    sources: tuple[EvidenceSource, ...]
    withdrawn_source_ids: tuple[str, ...]

    @property
    def revisions(self) -> list[str]:
        active = [source.revision for source in self.sources]
        withdrawn = [
            f"{source_id}:withdrawn" for source_id in self.withdrawn_source_ids
        ]
        return active + withdrawn
```

`ClaimExcerptSelector.select` must enumerate 12,000-character windows in 6,000-character steps, score each window by the number of case-folded claim terms of at least three word characters that occur in it, break ties toward the earliest window, and return exactly one slice from the original content.

- [ ] **Step 4: Write failing loader tests**

Cover the exact boundary behavior using a mocked `Session.query` result or a focused SQLite fixture:

```python
def test_loader_scopes_query_and_preserves_requested_order():
    loaded = loader.load(
        db,
        organization_id=org_id,
        source_ids=[second.id, first.id],
        claim="supported claim",
    )
    assert [source.source_id for source in loaded.sources] == [second.id, first.id]
    assert "organization_id" in str(db.query.return_value.filter.call_args)


def test_loader_rejects_duplicate_ids_before_query():
    with pytest.raises(DuplicateSourceIdsError):
        loader.load(db, organization_id=org_id, source_ids=[doc_id, doc_id], claim="claim")
    db.query.assert_not_called()


def test_loader_fails_closed_without_org():
    with pytest.raises(SourceSetNotFoundError):
        loader.load(db, organization_id=None, source_ids=[doc_id], claim="claim")


def test_loader_counts_soft_deleted_sources_but_never_classifies_them():
    loaded = loader.load(db, organization_id=org_id, source_ids=[active.id, deleted.id], claim="claim")
    assert [source.source_id for source in loaded.sources] == [active.id]
    assert loaded.withdrawn_source_ids == (str(deleted.id),)
```

Also test that a missing/cross-tenant row raises `SourceSetNotFoundError`, an incomplete or blank-content row raises `SourceNotReadyError`, and an all-withdrawn set raises `NoActiveSourcesError`.

- [ ] **Step 5: Run loader tests and verify failures**

```bash
pytest -q backend/tests/evidence/test_source_loader.py
```

Expected: selector tests pass; loader tests fail because the loader and exceptions are not complete.

- [ ] **Step 6: Implement the loader**

Define these exceptions in `source_loader.py`:

```python
class EvidenceSourceError(ValueError): ...
class DuplicateSourceIdsError(EvidenceSourceError): ...
class SourceSetNotFoundError(EvidenceSourceError): ...
class SourceNotReadyError(EvidenceSourceError): ...
class NoActiveSourcesError(EvidenceSourceError): ...
```

Implement `load` in this order:

1. Reject a missing organization as `SourceSetNotFoundError`.
2. Reject duplicate UUIDs as `DuplicateSourceIdsError`.
3. Query all requested IDs with both `Document.id.in_(source_ids)` and `Document.organization_id == organization_id`; do not filter `is_deleted` in SQL because caller-owned withdrawals must be counted.
4. If the returned ID set differs from the requested set, raise `SourceSetNotFoundError` without identifying an ID.
5. Separate soft-deleted rows into `withdrawn_source_ids`.
6. Require every active row to have `processing_status == ProcessingStatus.COMPLETED` and non-blank `content_text`; otherwise raise `SourceNotReadyError` before building any payload.
7. Use `checksum_sha256` when non-blank, otherwise `hashlib.sha256(content_text.encode("utf-8")).hexdigest()`.
8. Restore caller order and raise `NoActiveSourcesError` when no active row remains.

Export the source types, loader, selector, and exceptions from `services/evidence/__init__.py`.

- [ ] **Step 7: Run and format the source-loader slice**

```bash
pytest -q backend/tests/evidence/test_source_loader.py
ruff check backend/src/services/evidence/source_loader.py backend/tests/evidence/test_source_loader.py
black --check backend/src/services/evidence/source_loader.py backend/tests/evidence/test_source_loader.py
isort --check-only backend/src/services/evidence/source_loader.py backend/tests/evidence/test_source_loader.py
mypy --ignore-missing-imports --follow-imports=silent backend/src/services/evidence/source_loader.py
```

Expected: all commands pass.

- [ ] **Step 8: Commit the source boundary**

```bash
git add backend/src/services/evidence/source_loader.py \
  backend/src/services/evidence/__init__.py \
  backend/tests/evidence/test_source_loader.py
git commit -m "feat(evidence): load tenant-scoped document sources"
```

---

### Task 3: Reject ungrounded stance quotations

**Files:**
- Modify: `backend/src/services/evidence/stance_classifier.py`
- Modify: `backend/tests/evidence/test_stance_classifier.py`

**Interfaces:**
- Consumes: `ClassifierSource` payloads from Task 2.
- Produces: grounded classification dictionaries containing `source_id`, `stance`, `confidence`, `justification_excerpt`, `model_version`, and `source_content_hash`; returns `None` for an ungrounded fresh or cached result.

- [ ] **Step 1: Write failing grounding tests**

Add focused tests:

```python
async def test_classification_discards_ungrounded_quotation(stance_classifier):
    stance_classifier._classify_with_fallback = AsyncMock(
        return_value=StanceClassificationResult(
            stance="supporting",
            confidence=0.9,
            justification_excerpt="words absent from the document",
        )
    )
    result = await stance_classifier.classify_stance(
        "claim", "hash", uuid4(), "actual grounded source text", "content-hash"
    )
    assert result is None


async def test_classification_accepts_whitespace_normalized_quote(stance_classifier):
    stance_classifier._classify_with_fallback = AsyncMock(
        return_value=StanceClassificationResult(
            stance="supporting",
            confidence=0.9,
            justification_excerpt="actual grounded source text",
        )
    )
    result = await stance_classifier.classify_stance(
        "claim", "hash", uuid4(), "actual\n grounded   source text", "content-hash"
    )
    assert result is not None
    assert result["source_content_hash"] == "content-hash"
```

Add a cache-hit test where the cached quotation is absent from the current excerpt; assert the cached result is ignored and `_classify_with_fallback` is called.

- [ ] **Step 2: Run grounding tests and verify failure**

```bash
pytest -q backend/tests/evidence/test_stance_classifier.py -k 'ungrounded or whitespace_normalized or cached'
```

Expected: new tests fail because the classifier neither validates quotations nor accepts a content hash.

- [ ] **Step 3: Implement normalized grounding validation**

Add:

```python
def _normalize_grounding_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _has_grounded_justification(source_excerpt: str, justification: object) -> bool:
    if not isinstance(justification, str) or not justification.strip():
        return False
    return _normalize_grounding_text(justification) in _normalize_grounding_text(
        source_excerpt
    )
```

Extend `classify_stance` with `source_content_hash: str = ""`. Validate cached and new results with `_has_grounded_justification`; log only the source UUID on rejection. Include `source_content_hash` in the returned/cached dictionary.
For a valid cache hit, return a copied dictionary with
`source_content_hash` overwritten from the current loader input; never trust a
missing or stale provenance value from an older cache entry.

In `classify_sources_batch`, pass `source["content_hash"]` to `classify_stance`. Keep the existing limit, timeout, exception isolation, and success-count behavior.

Update legacy tests' mocked quotations so successful cases quote their supplied source excerpt exactly. Do not weaken the new validator to accommodate an invented test string.

- [ ] **Step 4: Run the complete classifier suite**

```bash
pytest -q backend/tests/evidence/test_stance_classifier.py
ruff check backend/src/services/evidence/stance_classifier.py backend/tests/evidence/test_stance_classifier.py
black --check backend/src/services/evidence/stance_classifier.py backend/tests/evidence/test_stance_classifier.py
isort --check-only backend/src/services/evidence/stance_classifier.py backend/tests/evidence/test_stance_classifier.py
```

Expected: all commands pass.

- [ ] **Step 5: Commit grounding enforcement**

```bash
git add backend/src/services/evidence/stance_classifier.py \
  backend/tests/evidence/test_stance_classifier.py
git commit -m "fix(evidence): require grounded stance quotations"
```

---

### Task 4: Make meter caching and reproducibility content-revision aware

**Files:**
- Modify: `backend/src/services/evidence/cache.py`
- Modify: `backend/src/services/evidence/consensus_calculator.py`
- Modify: `backend/tests/evidence/test_cache.py`
- Modify: `backend/tests/evidence/test_consensus_calculator.py`

**Interfaces:**
- Consumes: ordered `EvidenceSourceSet.revisions` values from Task 2.
- Produces: cache keys and reproducibility hashes that change when source content changes under an unchanged UUID.

- [ ] **Step 1: Write failing cache-revision tests**

Change cache test fixtures from bare IDs to revisions and add:

```python
def test_meter_cache_key_changes_with_source_content_hash():
    cache = EvidenceCacheService.__new__(EvidenceCacheService)
    old = cache._generate_meter_cache_key(
        "claim", ["doc-1:old"], "model", "org"
    )
    new = cache._generate_meter_cache_key(
        "claim", ["doc-1:new"], "model", "org"
    )
    assert old != new
```

Retain order independence and organization isolation assertions.

- [ ] **Step 2: Write a failing reproducibility test**

```python
def test_reproducibility_hash_changes_with_content_revision(consensus_calculator):
    old = consensus_calculator._generate_reproducibility_hash(
        "claim", ["doc-1:old"], consensus_calculator.model_version
    )
    new = consensus_calculator._generate_reproducibility_hash(
        "claim", ["doc-1:new"], consensus_calculator.model_version
    )
    assert old != new
```

Add a `calculate_consensus(..., source_revisions=[...])` assertion proving the
public meter uses the supplied revision list. Also assert that adding
`"doc-2:withdrawn"` changes both the meter cache key and reproducibility hash,
preventing a cached zero-withdrawal response from serving a request that includes
a withdrawn source.

- [ ] **Step 3: Run the focused tests and verify failure**

```bash
pytest -q backend/tests/evidence/test_cache.py \
  backend/tests/evidence/test_consensus_calculator.py -k 'cache_key or reproducibility or content_revision'
```

Expected: failures because the calculator does not accept `source_revisions` and old naming/inputs remain.

- [ ] **Step 4: Implement revision-aware cache keys**

Rename the internal `source_ids` parameters of `_generate_meter_cache_key`, `get_evidence_meter`, and `set_evidence_meter` to `source_revisions`; sort and hash the complete revision strings. Keep key shape:

```python
return f"meter:{organization_id}:{claim_hash}:{sources_hash}:{model_version}"
```

Correct claim invalidation to match that shape:

```python
patterns = [f"stance:{claim_hash}:*", f"meter:*:{claim_hash}:*"]
```

- [ ] **Step 5: Implement revision-aware reproducibility**

Rename `_generate_reproducibility_hash`'s list parameter to `source_revisions` and hash the sorted revision strings. Extend `calculate_consensus`:

```python
def calculate_consensus(
    self,
    claim: str,
    classifications: List[Dict],
    retracted_source_ids: Optional[List[str]] = None,
    source_revisions: Optional[List[str]] = None,
) -> EvidenceMeter:
```

Use the provided `source_revisions` when present. For direct legacy callers that omit it, fall back to the valid classification source IDs so existing unit-level use remains compatible.

- [ ] **Step 6: Run the complete cache/calculator suites**

```bash
pytest -q backend/tests/evidence/test_cache.py backend/tests/evidence/test_consensus_calculator.py
ruff check backend/src/services/evidence/cache.py backend/src/services/evidence/consensus_calculator.py \
  backend/tests/evidence/test_cache.py backend/tests/evidence/test_consensus_calculator.py
black --check backend/src/services/evidence/cache.py backend/src/services/evidence/consensus_calculator.py \
  backend/tests/evidence/test_cache.py backend/tests/evidence/test_consensus_calculator.py
isort --check-only backend/src/services/evidence/cache.py backend/src/services/evidence/consensus_calculator.py \
  backend/tests/evidence/test_cache.py backend/tests/evidence/test_consensus_calculator.py
```

Expected: all commands pass.

- [ ] **Step 7: Commit revision-aware identity**

```bash
git add backend/src/services/evidence/cache.py \
  backend/src/services/evidence/consensus_calculator.py \
  backend/tests/evidence/test_cache.py \
  backend/tests/evidence/test_consensus_calculator.py
git commit -m "fix(evidence): key results by source revision"
```

---

### Task 5: Persist claim and content provenance

**Files:**
- Create: `backend/alembic/versions/evidence_prov_20260816.py`
- Modify: `backend/src/models/evidence.py`
- Modify: `backend/src/api/evidence/router.py`
- Modify: `backend/tests/evidence/test_api.py`
- Modify: `backend/tests/unit/test_models_basic.py`

**Interfaces:**
- Consumes: grounded classification dictionaries from Task 3.
- Produces: nullable legacy-compatible `claim_text` and `source_content_hash` columns populated by every new endpoint write.

- [ ] **Step 1: Write failing model and persistence tests**

Add a model test:

```python
def test_stance_classification_serializes_provenance():
    classification = StanceClassificationModel(
        claim_hash="a" * 64,
        claim_text="Original claim",
        source_id=uuid4(),
        source_content_hash="b" * 64,
        organization_id=uuid4(),
        stance="supporting",
        confidence=0.9,
        model_version="model",
    )
    data = classification.to_dict()
    assert data["claim_text"] == "Original claim"
    assert data["source_content_hash"] == "b" * 64
```

Extend the API persistence test so `_save_stance_classifications` receives
`claim_text="Original claim"`, writes a classification carrying
`source_content_hash`, and asserts both values on the stored row.

- [ ] **Step 2: Run provenance tests and verify failure**

```bash
pytest -q backend/tests/unit/test_models_basic.py -k provenance
pytest -q backend/tests/evidence/test_api.py -k 'save and provenance'
```

Expected: failures because the ORM columns and save argument do not exist.

- [ ] **Step 3: Add ORM columns and upsert fields**

In `StanceClassificationModel` add:

```python
claim_text = Column(Text, nullable=True, doc="Original normalized-input claim text")
source_content_hash = Column(
    String(64), nullable=True, doc="Content revision classified for this row"
)
```

Include both in `to_dict`. Extend `_save_stance_classifications` with required
`claim_text: str`; copy `classification.get("source_content_hash")` into each row.
For the PostgreSQL upsert, update both provenance columns in `set_`; for the
SQLite fallback, assign both fields when an existing row is updated.
Pass `claim_text=claim` from both current call sites immediately so this commit
does not leave either endpoint with a missing required argument. Task 6 ensures
their real-source classifications always carry a non-null content hash.

- [ ] **Step 4: Add the single-head Alembic revision**

Create `evidence_prov_20260816.py` with:

```python
"""add evidence claim and source provenance

Revision ID: evidence_prov_20260816
Revises: i9j0k1l2m3n4
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

revision = "evidence_prov_20260816"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stance_classifications", sa.Column("claim_text", sa.Text(), nullable=True)
    )
    op.add_column(
        "stance_classifications",
        sa.Column("source_content_hash", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stance_classifications", "source_content_hash")
    op.drop_column("stance_classifications", "claim_text")
```

- [ ] **Step 5: Run model, persistence, and migration guards**

```bash
pytest -q backend/tests/unit/test_models_basic.py -k 'Stance or provenance'
pytest -q backend/tests/evidence/test_api.py -k 'save and provenance'
python3 scripts/ci/check_alembic.py
```

Expected: tests pass; the migration guard reports exactly one head with revision IDs no longer than 32 characters.

- [ ] **Step 6: Commit persistence provenance**

```bash
git add backend/alembic/versions/evidence_prov_20260816.py \
  backend/src/models/evidence.py \
  backend/src/api/evidence/router.py \
  backend/tests/evidence/test_api.py \
  backend/tests/unit/test_models_basic.py
git commit -m "feat(evidence): persist source provenance"
```

---

### Task 6: Integrate real sources into every Evidence endpoint

**Files:**
- Modify: `backend/src/api/evidence/router.py`
- Modify: `backend/tests/evidence/test_api.py`

**Interfaces:**
- Consumes: `EvidenceSourceLoader`, grounded classifier payloads, revision-aware cache/calculator, and provenance columns from Tasks 2-5.
- Produces: real-source `/meter` and `/classify` behavior plus real-metadata `/breakdown`; `/health` remains contract-compatible.

- [ ] **Step 1: Replace fabricated success fixtures with failing real-source tests**

Extend the SQLite API fixture to create/drop `Document.__table__` together with
`StanceClassificationModel.__table__`. Add a helper that inserts a completed,
caller-owned `Document` with explicit `title`, `content_text`, checksum, and
organization.

Update the meter success test to seed real documents and assert:

```python
payloads = mock_classifier.classify_sources_batch.await_args.kwargs["sources"]
assert payloads[0]["excerpt"] in seeded_document.content_text
assert "Mock excerpt" not in payloads[0]["excerpt"]
assert payloads[0]["content_hash"] == seeded_document.checksum_sha256
```

Add equivalent `/classify` coverage proving it uses real content and persists
the original claim/content hash.

- [ ] **Step 2: Add failing tenant/readiness/withdrawal tests**

Add endpoint tests that assert:

```python
assert cross_tenant_response.status_code == 404
assert missing_response.status_code == 404
assert null_org_response.status_code == 404
assert mixed_tenant_response.status_code == 404
mock_classifier.classify_sources_batch.assert_not_awaited()
```

For caller-owned PENDING and blank-content documents, assert 409 and no
classifier call. For one active plus one soft-deleted caller-owned document,
assert the meter's `retracted_sources == 1` and only the active source reaches
the classifier. For duplicate IDs, assert 400 and no classifier call.

- [ ] **Step 3: Add failing breakdown provenance tests**

Persist a classification with `claim_text` and a matching active caller-owned
Document, then assert:

```python
assert response.json()["claim"] == "Stored original claim"
assert response.json()["sources"][0]["title"] == "Real document title"
assert "Original claim text" not in response.text
assert f"Source {document.id}" not in response.text
```

Keep and strengthen the existing cross-organization breakdown regression. Add a
legacy row with `claim_text=None` and assert it is not rendered as a placeholder.

- [ ] **Step 4: Run the new endpoint tests and verify failure**

```bash
pytest -q backend/tests/evidence/test_api.py -k \
  'real_source or tenant or readiness or withdrawn or duplicate or provenance'
```

Expected: failures at the current placeholder-loading and placeholder-breakdown code.

- [ ] **Step 5: Add one exception-to-HTTP boundary**

Instantiate one module-level `EvidenceSourceLoader`. Add a helper used by both
`/meter` and `/classify`:

```python
def _load_sources_or_http_error(
    db: Session,
    *,
    organization_id: UUID | None,
    source_ids: List[UUID],
    claim: str,
) -> EvidenceSourceSet:
    try:
        return source_loader.load(
            db,
            organization_id=organization_id,
            source_ids=source_ids,
            claim=claim,
        )
    except DuplicateSourceIdsError as exc:
        raise HTTPException(status_code=400, detail="Duplicate source IDs are not allowed") from exc
    except SourceSetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Sources not found or unavailable") from exc
    except SourceNotReadyError as exc:
        raise HTTPException(status_code=409, detail="One or more sources are not ready for evidence analysis") from exc
    except NoActiveSourcesError as exc:
        raise HTTPException(status_code=400, detail="No active sources available for evidence analysis") from exc
```

Do not log exception strings that could contain document metadata.

- [ ] **Step 6: Replace `/meter` and `/classify` placeholders**

Delete `get_retracted_sources` and both loops that build `"Mock excerpt"` data.
After UUID parsing, call `_load_sources_or_http_error`. Use:

```python
classifier_sources = [source.classifier_input() for source in loaded.sources]
source_revisions = loaded.revisions
retracted_ids = list(loaded.withdrawn_source_ids)
```

Use `source_revisions` in cache get/set. Pass `classifier_sources` to the batch
classifier. Pass `retracted_ids` and `source_revisions` to
`calculate_consensus`. Pass the original claim to
`_save_stance_classifications`. Keep batch limit errors at 400 and timeouts at
504. Log claim hash and counts only.

- [ ] **Step 7: Replace `/breakdown` placeholders with a tenant-scoped join**

Query `(StanceClassificationModel, Document)` with an inner join on source ID
and these predicates:

```python
StanceClassificationModel.claim_hash == claim_hash
StanceClassificationModel.model_version == stance_classifier.model_version
StanceClassificationModel.organization_id == current_user.organization_id
StanceClassificationModel.claim_text.isnot(None)
Document.organization_id == current_user.organization_id
Document.is_deleted.is_(False)
Document.processing_status == ProcessingStatus.COMPLETED
```

Apply the optional stance filter, order by confidence descending, then paginate.
Build each item with `document.title`, the stored grounded excerpt, and
`is_retracted=False`. Use the first row's non-null `classification.claim_text`
for the response claim. If no joined row remains, return the existing generic
404. Remove unused `total_count`.

- [ ] **Step 8: Run the entire backend Evidence suite**

```bash
pytest -q backend/tests/evidence backend/tests/test_evidence_getdb_sync.py
ruff check backend/src/api/evidence/router.py backend/tests/evidence/test_api.py
black --check backend/src/api/evidence/router.py backend/tests/evidence/test_api.py
isort --check-only backend/src/api/evidence/router.py backend/tests/evidence/test_api.py
```

Expected: all commands pass; no placeholder source content/title/claim remains in the router.

- [ ] **Step 9: Commit endpoint integration**

```bash
git add backend/src/api/evidence/router.py backend/tests/evidence/test_api.py
git commit -m "feat(api): ground evidence endpoints in documents"
```

---

### Task 7: Make retraction semantics explicit and regenerate contracts

**Files:**
- Modify: `backend/src/api/evidence/schemas.py`
- Modify: `backend/tests/evidence/test_api.py`
- Modify: `frontend/src/types/evidence.ts`
- Modify: `frontend/src/components/evidence/EvidenceMeter.tsx`
- Modify: `frontend/src/components/evidence/__tests__/EvidenceMeter.test.tsx`
- Modify: `backend/openapi.json`
- Modify: `frontend/src/types/generated/api.d.ts`

**Interfaces:**
- Consumes: workspace-withdrawal counts and active breakdown items from Task 6.
- Produces: additive `publication_retraction_check="not_performed"` and `publication_retraction_status="unknown"` fields plus honest frontend copy.

- [ ] **Step 1: Write failing backend schema-response assertions**

In meter and breakdown API tests assert:

```python
assert meter["publication_retraction_check"] == "not_performed"
assert breakdown_source["publication_retraction_status"] == "unknown"
```

- [ ] **Step 2: Add exact backend enum fields**

In `schemas.py` add:

```python
class PublicationRetractionCheck(str, Enum):
    NOT_PERFORMED = "not_performed"


class PublicationRetractionStatus(str, Enum):
    UNKNOWN = "unknown"
```

Add `publication_retraction_check: PublicationRetractionCheck =
PublicationRetractionCheck.NOT_PERFORMED` to `EvidenceMeter`, and
`publication_retraction_status: PublicationRetractionStatus =
PublicationRetractionStatus.UNKNOWN` to `StanceBreakdownItem`. Change the
`retracted_sources` description to "Number of workspace-withdrawn sources
excluded from classification". Defaults keep old constructor call sites valid.

- [ ] **Step 3: Run backend response tests**

```bash
pytest -q backend/tests/evidence/test_api.py \
  backend/tests/evidence/test_consensus_calculator.py
```

Expected: all tests pass and serialized defaults are present.

- [ ] **Step 4: Update handwritten frontend types and warning copy**

Add:

```typescript
export type PublicationRetractionCheck = 'not_performed';
export type PublicationRetractionStatus = 'unknown';
```

Add `publication_retraction_check` to `EvidenceMeterData` and
`publication_retraction_status` to `StanceClassification`. Change the warning
copy from "retracted source(s) found" to:

```tsx
{data.retracted_sources} withdrawn workspace source
{data.retracted_sources > 1 ? 's' : ''} excluded
```

Update the component test to assert the new wording and reject the old
publication-retraction claim.

- [ ] **Step 5: Run focused frontend tests and type-check**

```bash
pnpm --dir frontend test --run src/components/evidence/__tests__/EvidenceMeter.test.tsx
pnpm --dir frontend type-check
```

Expected: both commands pass.

- [ ] **Step 6: Regenerate and verify API artifacts**

```bash
python3 scripts/ci/generate_openapi.py
pnpm --dir frontend generate:api-types
python3 scripts/ci/generate_openapi.py --check
git diff --check -- backend/openapi.json frontend/src/types/generated/api.d.ts
```

Verify paths remain:

```bash
for path in meter breakdown classify health; do
  rg -q "/api/v1/evidence/$path" backend/openapi.json
done
```

Expected: all four paths exist; generated artifacts are synchronized; no path deletion appears against `origin/develop`.

- [ ] **Step 7: Commit explicit semantics and contracts**

```bash
git add backend/src/api/evidence/schemas.py backend/tests/evidence/test_api.py \
  frontend/src/types/evidence.ts \
  frontend/src/components/evidence/EvidenceMeter.tsx \
  frontend/src/components/evidence/__tests__/EvidenceMeter.test.tsx \
  backend/openapi.json frontend/src/types/generated/api.d.ts
git commit -m "feat(evidence): expose honest retraction status"
```

---

### Task 8: Run repository gates, update the PR, and monitor CI

**Files:**
- Verify: files already listed in Tasks 1-7.
- Update remotely: PR #1432 branch and PR title/body.

**Interfaces:**
- Consumes: all completed implementation tasks.
- Produces: a clean, synchronized PR branch whose full GitHub release gate is green.

- [ ] **Step 1: Run focused backend and frontend verification**

```bash
pytest -q backend/tests/evidence backend/tests/test_evidence_getdb_sync.py \
  backend/tests/unit/test_models_basic.py
pnpm --dir frontend test --run src/components/evidence/__tests__/EvidenceMeter.test.tsx \
  src/components/evidence/__tests__/EvidenceBreakdown.test.tsx
pnpm --dir frontend type-check
```

Expected: all commands pass.

- [ ] **Step 2: Run the branch-wide blocking gate**

```bash
scripts/ci/run_local_ci.sh --base origin/develop --frontend
```

Expected: Ruff, changed-file Black/isort, mypy on added files, directory docs,
single Alembic head, OpenAPI snapshot, generated TypeScript contract, migration
upgrade probe when available, backend tests, and frontend gates pass. Any
environmental skip must remain clearly reported as a skip rather than a pass.

- [ ] **Step 3: Check the final diff for the intended direction**

```bash
git diff --check origin/develop...HEAD
git diff --stat origin/develop...HEAD
git diff --name-status origin/develop...HEAD
git status --short --branch
```

Expected: implementation is additive/repair-oriented; `test_api.py`, API docs,
router mounting, and Evidence OpenAPI paths are not deleted; the worktree is clean.

- [ ] **Step 4: Push the updated branch**

```bash
git push origin codex/disable-fabricated-evidence-api
```

If the earlier merge required rewritten history, stop and report the exact
non-fast-forward condition rather than force-pushing without explicit approval.

- [ ] **Step 5: Update PR metadata to describe the repair**

Set the title to `fix(api): ground evidence endpoints in tenant documents` and
replace the body with a summary covering real organization-scoped source loading,
grounded quotations, revision-aware caching, honest retraction scope, migration,
and verification. Do not claim external retraction checking.

- [ ] **Step 6: Monitor all GitHub checks to terminal state**

```bash
gh pr checks 1432 --repo Goodwiinz/rag --watch --interval 20
gh pr view 1432 --repo Goodwiinz/rag \
  --json state,isDraft,mergeable,headRefOid,statusCheckRollup,url
```

Expected: every required check succeeds, intentional skips are identified, and
the final head SHA matches local `HEAD`. If a check fails, inspect its logs and
apply the systematic-debugging workflow before changing code.
