# Evidence API Review Repairs Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute this plan task-by-task in the current session.

**Goal:** Resolve all five actionable findings from the final PR #1432 review without weakening tenant isolation, API error contracts, or migration verification.

**Architecture:** Reuse a single Python source-revision helper, validate source count before database access, end read transactions before async cache/LLM calls, separate exact inference-model provenance from a fingerprinted classifier pipeline identity, and classify local PostgreSQL unavailability as a visible skip.

**Tech Stack:** FastAPI, SQLAlchemy synchronous sessions, Pydantic, pytest/pytest-asyncio, Alembic, Bash.

---

## Global Constraints

- Work only in `/tmp/rag-pr-1432.Dbvr1G/worktree` on branch `codex/disable-fabricated-evidence-api`; preserve the user's main worktree.
- Use test-driven development: add a behavior test, demonstrate its expected RED failure, implement the minimum repair, then demonstrate GREEN.
- Preserve the 400 batch-limit text exactly: `Maximum 100 sources allowed per batch classification request` with the configured value substituted through `max_batch_sources`.
- Tenant organization, active-document, completed-processing, non-null claim, current classifier, and current content revision must all be satisfied before a breakdown row is visible.
- Breakdown sorting remains confidence descending then source UUID ascending; apply offset/limit only after stale rows are removed.
- The current revision is the nonblank `Document.checksum_sha256`, otherwise lowercase SHA-256 of UTF-8 `Document.content_text`.
- `model_version` in a classification dictionary is the exact model that generated the selected classification. `classifier_version` is a deterministic collision-resistant fingerprint of the full primary/fallback/threshold configuration.
- Keep the database's existing `model_version` uniqueness column as the classifier pipeline namespace; persist the exact generator in nullable `inference_model_version VARCHAR(100)`, populated on every new write.
- Cache keys, persisted-row selection, breakdown selection, and reproducibility hashes use `classifier_version`; the consensus calculator must receive it explicitly and must not own a hardcoded model identity.
- After ORM data is copied into immutable source objects, `/meter` and `/classify` must end the read transaction before the first cache or LLM await. The dependency still owns session closure.
- Targeted migration probe exit 0 passes, exit 1 fails, and exit 2 is visibly SKIPPED locally. Do not weaken GitHub's real PostgreSQL probe or other local gates.
- Do not merge the PR. Each task must commit only its scoped changes and include pristine focused-test output in its report.

### Task 1: Hide stale breakdown rows before pagination

**Files:**
- Modify: `backend/src/services/evidence/source_loader.py`
- Modify: `backend/src/api/evidence/router.py`
- Modify: `backend/tests/evidence/test_source_loader.py`
- Modify: `backend/tests/evidence/test_api.py`

**Step 1: Add failing current-revision tests**

Add a source-loader unit test proving the shared revision helper prefers a nonblank
checksum and falls back to SHA-256 of UTF-8 content. Add API regressions proving a
classification becomes invisible after its document checksum/content changes, and
that a stale higher-confidence candidate does not consume `offset` or `limit` before
a current lower-confidence candidate.

Run:

```bash
source /tmp/rag-pr-1432.Dbvr1G/venv/bin/activate
pytest -q backend/tests/evidence/test_source_loader.py backend/tests/evidence/test_api.py -k 'content_hash or stale or pagination' -p no:cacheprovider --no-cov
```

Expected: FAIL because `/breakdown` currently paginates before comparing revisions
and the reusable helper does not exist.

**Step 2: Implement one revision helper and post-filter pagination**

Add a pure helper in `source_loader.py` implementing the Global Constraints revision
rule, and call it from `EvidenceSourceLoader._build_source`. In `/breakdown`, fetch
the deterministically ordered candidates without database offset/limit, retain only
rows whose persisted hash equals the helper's current hash, then slice the current
list with `offset : offset + limit`. Preserve the existing 404 behavior when the
visible page is empty.

**Step 3: Verify and commit**

Run the focused command above, then:

```bash
ruff check backend/src/services/evidence/source_loader.py backend/src/api/evidence/router.py backend/tests/evidence/test_source_loader.py backend/tests/evidence/test_api.py
black --check backend/src/services/evidence/source_loader.py backend/src/api/evidence/router.py backend/tests/evidence/test_source_loader.py backend/tests/evidence/test_api.py
isort --check-only backend/src/services/evidence/source_loader.py backend/src/api/evidence/router.py backend/tests/evidence/test_source_loader.py backend/tests/evidence/test_api.py
git diff --check
```

Commit: `fix(evidence): hide stale breakdown classifications`

### Task 2: Bound requests before loading and release read transactions

**Files:**
- Modify: `backend/src/services/evidence/stance_classifier.py`
- Modify: `backend/src/api/evidence/router.py`
- Modify: `backend/tests/evidence/test_stance_classifier.py`
- Modify: `backend/tests/evidence/test_api.py`

**Step 1: Add failing ordering and transaction-lifetime tests**

Add route tests for `/meter` and `/classify` with 101 valid unique UUIDs. Assert the
existing 400 message and prove the source loader is not called. Add endpoint tests
whose async cache/classifier boundary asserts that the request's SQLAlchemy session
is no longer in a transaction after the loader query.

Run:

```bash
source /tmp/rag-pr-1432.Dbvr1G/venv/bin/activate
pytest -q backend/tests/evidence/test_stance_classifier.py backend/tests/evidence/test_api.py -k 'batch_limit or before_load or transaction' -p no:cacheprovider --no-cov
```

Expected: FAIL because route validation occurs only inside the async classifier and
the loader's read transaction remains open across awaits.

**Step 2: Share synchronous size validation**

Add `StanceClassifier.validate_batch_size(source_count: int) -> None`, using
`max_batch_sources` and raising `BatchClassificationLimitError` with the existing
message. Keep it at the start of `classify_sources_batch`. Call it from both routes
after ID parsing and before `_load_sources_or_http_error`, translating the error to
HTTP 400.

**Step 3: End the read transaction before awaits**

After each loader result has been converted to immutable classifier inputs and
revision lists, call `db.rollback()` before the first cache or classifier await.
Reuse that session for the later write/commit transaction; do not close it.

**Step 4: Verify and commit**

Run the focused command above, then the formatting/static commands from Task 1 for
these four files plus `git diff --check`.

Commit: `fix(evidence): bound requests and release read transactions`

### Task 3: Record actual inference models and fingerprint the classifier pipeline

**Files:**
- Modify: `backend/src/services/evidence/stance_classifier.py`
- Modify: `backend/src/services/evidence/consensus_calculator.py`
- Modify: `backend/src/api/evidence/router.py`
- Modify: `backend/src/models/evidence.py`
- Modify: `backend/alembic/versions/evidence_prov_20260816.py`
- Modify: `scripts/ci/probe_evidence_migration.py`
- Modify: `backend/tests/evidence/test_stance_classifier.py`
- Modify: `backend/tests/evidence/test_consensus_calculator.py`
- Modify: `backend/tests/evidence/test_api.py`
- Modify: `backend/tests/evidence/test_models.py`
- Modify: `backend/tests/unit/ci/test_evidence_migration_probe.py`

**Step 1: Add failing provenance and collision tests**

Add tests proving: OpenAI results carry the exact requested model; a selected
fallback remains labeled with the fallback; new and cached classification dictionaries
carry exact `model_version` plus `classifier_version`; changing either exact model or
the fallback threshold changes `classifier_version`, stance cache keys, meter cache
keys, and consensus reproducibility hashes; `gpt-4o-*` and `gpt-5-*` no longer collide;
persistence stores classifier identity in the existing `model_version` column and the
actual generator in `inference_model_version`; the migration/probe add and remove the
new nullable VARCHAR(100) column.

Run:

```bash
source /tmp/rag-pr-1432.Dbvr1G/venv/bin/activate
pytest -q backend/tests/evidence/test_stance_classifier.py backend/tests/evidence/test_consensus_calculator.py backend/tests/evidence/test_api.py backend/tests/evidence/test_models.py backend/tests/unit/ci/test_evidence_migration_probe.py -k 'model or reproducibility or migration or provenance' -p no:cacheprovider --no-cov
```

Expected: FAIL because selected results lose their producing model, the calculator
owns a separate hardcoded identity, and the current hash truncates at the first dash.

**Step 2: Separate result and pipeline identities**

Add exact `model_version` to `StanceClassificationResult`. Make
`_classify_with_openai` stamp the model argument so fallback selection preserves it.
Define a single fallback-threshold attribute and a deterministic
`classifier_version` fingerprint over the implementation generation, exact primary,
exact fallback, and threshold. Use it in stance cache keys. Return/cache both fields
in classification dictionaries and reject legacy cached data that lacks honest model
provenance.

**Step 3: Thread classifier identity through meter behavior**

Remove the calculator's hardcoded model version. Require `classifier_version` as an
explicit keyword to `calculate_consensus`. Hash the complete classifier identity with
SHA-256 for the reproducibility suffix. Use the same classifier identity for meter
cache get/set, persistence namespace, breakdown filtering, internal response identity,
and health identity.

**Step 4: Persist and migrate actual model provenance**

Add nullable `inference_model_version = Column(String(100))` to the ORM model and
serialization. Add it to the in-flight provenance migration upgrade/downgrade and to
the exact targeted probe contract. Every new `_save_stance_classifications` row must
write it from the classification's exact `model_version`; PostgreSQL upserts and the
SQLite fallback must update it.

**Step 5: Verify and commit**

Run the focused command above, then:

```bash
ruff check backend/src/services/evidence backend/src/api/evidence/router.py backend/src/models/evidence.py backend/alembic/versions/evidence_prov_20260816.py scripts/ci/probe_evidence_migration.py backend/tests/evidence backend/tests/unit/ci/test_evidence_migration_probe.py
black --check backend/src/services/evidence backend/src/api/evidence/router.py backend/src/models/evidence.py backend/alembic/versions/evidence_prov_20260816.py scripts/ci/probe_evidence_migration.py backend/tests/evidence backend/tests/unit/ci/test_evidence_migration_probe.py
isort --check-only backend/src/services/evidence backend/src/api/evidence/router.py backend/src/models/evidence.py backend/alembic/versions/evidence_prov_20260816.py scripts/ci/probe_evidence_migration.py backend/tests/evidence backend/tests/unit/ci/test_evidence_migration_probe.py
mypy --ignore-missing-imports --follow-imports=silent backend/src/services/evidence/stance_classifier.py backend/src/services/evidence/consensus_calculator.py backend/src/api/evidence/router.py
(cd backend && python ../scripts/ci/check_alembic.py)
git diff --check
```

Commit: `fix(evidence): preserve inference model provenance`

### Task 4: Treat local PostgreSQL unavailability as a visible skip

**Files:**
- Modify: `scripts/ci/run_local_ci.sh`
- Modify: `backend/tests/unit/ci/test_run_local_ci_migration.py`

**Step 1: Add a failing local-gate contract test**

Add a focused contract test for the exact exit-code-2 branch. It must require an
existing `skipped "targeted evidence migration delta" ...` call and reject any
`check 1` failure in that branch, while preserving the normal
`check "$TARGETED_EVIDENCE_RC"` path for real execution results.

Run:

```bash
source /tmp/rag-pr-1432.Dbvr1G/venv/bin/activate
pytest -q backend/tests/unit/ci/test_run_local_ci_migration.py -p no:cacheprovider --no-cov
```

Expected: FAIL because exit code 2 currently appends a failure.

**Step 2: Correct the branch and comments**

Keep the warning, record the unavailable result through `skipped`, and leave exit
code 1 on the blocking `check` path. Align comments/header wording with this behavior.

**Step 3: Verify and commit**

Run:

```bash
source /tmp/rag-pr-1432.Dbvr1G/venv/bin/activate
pytest -q backend/tests/unit/ci/test_run_local_ci_migration.py -p no:cacheprovider --no-cov
bash -n scripts/ci/run_local_ci.sh
ruff check backend/tests/unit/ci/test_run_local_ci_migration.py
black --check backend/tests/unit/ci/test_run_local_ci_migration.py
isort --check-only backend/tests/unit/ci/test_run_local_ci_migration.py
git diff --check
```

Commit: `fix(ci): skip unavailable local migration probe`

### Task 5: Full verification and PR readiness

**Files:**
- Verify only unless a final reviewer identifies a defect.

**Step 1: Run the evidence and CI contract suite**

```bash
source /tmp/rag-pr-1432.Dbvr1G/venv/bin/activate
pytest -q backend/tests/evidence backend/tests/test_evidence_getdb_sync.py backend/tests/unit/ci/test_evidence_migration_probe.py backend/tests/unit/ci/test_migration_check_workflow.py backend/tests/unit/ci/test_run_local_ci_migration.py -p no:cacheprovider --no-cov
```

**Step 2: Run repository gates proportionate to the diff**

```bash
source /tmp/rag-pr-1432.Dbvr1G/venv/bin/activate
ruff check backend/src/services/evidence backend/src/api/evidence/router.py backend/src/models/evidence.py backend/alembic/versions/evidence_prov_20260816.py scripts/ci/probe_evidence_migration.py backend/tests/evidence backend/tests/unit/ci/test_evidence_migration_probe.py backend/tests/unit/ci/test_run_local_ci_migration.py
black --check backend/src/services/evidence backend/src/api/evidence/router.py backend/src/models/evidence.py backend/alembic/versions/evidence_prov_20260816.py scripts/ci/probe_evidence_migration.py backend/tests/evidence backend/tests/unit/ci/test_evidence_migration_probe.py backend/tests/unit/ci/test_run_local_ci_migration.py
isort --check-only backend/src/services/evidence backend/src/api/evidence/router.py backend/src/models/evidence.py backend/alembic/versions/evidence_prov_20260816.py scripts/ci/probe_evidence_migration.py backend/tests/evidence backend/tests/unit/ci/test_evidence_migration_probe.py backend/tests/unit/ci/test_run_local_ci_migration.py
mypy --ignore-missing-imports --follow-imports=silent backend/src/services/evidence/stance_classifier.py backend/src/services/evidence/consensus_calculator.py backend/src/services/evidence/source_loader.py backend/src/api/evidence/router.py
(cd backend && python ../scripts/ci/check_alembic.py)
python scripts/ci/generate_openapi.py --check
bash -n scripts/ci/run_local_ci.sh
git diff --check
```

**Step 3: Review, publish, and monitor**

Run a fresh Luna-max whole-branch review against the PR base. Fix any Critical or
Important finding through one reviewed fix wave, then push the branch and monitor all
GitHub checks to a terminal state. Do not merge.

