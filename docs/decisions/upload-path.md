# Decision: canonical document-upload path

Status: accepted
Audit: B3 / P4.4 (audit plan PR #1123)

## Context

Two services implement the full upload / hash / storage-path / storage-object
pipeline, each with its own `upload_file` entry point:

| Service                                                                           | Sync/async | Entry point                                     | Router                                                                               | Registered?                                                                                                                                                                               |
| --------------------------------------------------------------------------------- | ---------- | ----------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `FileService` (`backend/src/services/documents/file_service.py`)                  | **async**  | `upload_file` (`file_service.py:334`)           | `POST /files/upload` (`backend/src/api/documents/files.py:132`, prefix `/files`)     | **Yes** — exported as `files_router` from `backend/src/api/documents/__init__.py`                                                                                                         |
| `EnhancedFileService` (`backend/src/services/documents/enhanced_file_service.py`) | sync       | `upload_file` (`enhanced_file_service.py:1001`) | `POST /api/v2/documents/upload/` (`backend/src/api/documents/document_upload.py:52`) | **No** — `backend/src/api/documents/__init__.py` explicitly notes "document_upload provides upload utilities, not a router"; no `include_router` references it anywhere in `backend/src/` |

The deployed frontend uploads through `FileService`: `enhancedDocumentService.ts`
POSTs to `/files/upload` (`frontend/src/services/enhancedDocumentService.ts:197`).
`EnhancedFileService.upload_file` is invoked only from the **unregistered** v2
router (`document_upload.py:341`) — dead in the running app.

## Decision

**`FileService.upload_file` (async) via `POST /files/upload` is the canonical
upload path.** It is the only registered upload route and the only one the
deployed frontend calls.

`EnhancedFileService.upload_file` is **deprecated** (see its docstring). We do
**not** unify the two stacks (explicitly rejected — big-bang refactor).

**Update (PR #1453):** `EnhancedFileService`, `document_upload.py`, and the
tasks that only that dead v2 router dispatched (`process_document_upload`,
`batch_process_documents`, `process_high_priority_document`,
`process_low_priority_document`) have been **deleted**, not just left
unregistered — the "re-wire later" option below is closed. They duplicated
`processing_tasks.py` minus its rollback-first fixes, which is what audit
findings R2-H5 (fail-then-retry self-destruct), R2-H6 (no rollback before
`fail_job`), R2-H7 (doc stuck `PROCESSING`), and R2-M9 tracked. `FileService.upload_file`
via `POST /api/v1/files/upload` is now the only upload path in the codebase,
canonical by construction rather than by convention.

## Failure-semantics parity audit

Repo rule: a post-upload failure must compensating-delete the storage object
**and** revert quota, else it orphans the object plus a live `PENDING` row whose
content hash then blocks re-upload (`uq_documents_org_checksum_live`, the partial
unique index `WHERE is_deleted = false`).

Both services commit the storage object BEFORE the DB rows and split the DB
writes across multiple commits, so both need compensation on a mid-upload
failure. Side-by-side:

| Concern                          | Canonical `FileService`                                                                                                                                                                    | Non-canonical `EnhancedFileService`                                                                                                                                                                                                                                                                                                                                                  |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Compensating object delete       | `_delete_stored_object` by captured primitives (`file_service.py:548-559`)                                                                                                                 | `_best_effort_delete_object` per-backend dispatch (`enhanced_file_service.py:1189`)                                                                                                                                                                                                                                                                                                  |
| Quota revert on failure          | Yes — reverts committed quota in the reversal commit (`file_service.py:532-537`). Quota is a **separate** commit that precedes the processing-job commit, so a later failure must undo it. | Not needed by construction — the quota update is the **last** commit; nothing runs after it that can fail, so a committed quota never needs reverting.                                                                                                                                                                                                                               |
| Processing-job cleanup           | Yes — drops a stray committed `ProcessingJob` (`file_service.py:529-530`).                                                                                                                 | N/A — this service creates no `ProcessingJob` (the v2 router enqueues separately).                                                                                                                                                                                                                                                                                                   |
| Committed-`PENDING`-row cleanup  | Yes — `document_committed`/`reversal_ok` gate: soft-delete the row, then delete the object only if the reversal succeeded.                                                                 | **Gap (fixed in this PR)** — previously a bare `db.rollback()` + unconditional object delete. If the first commit (row) succeeded and the second commit (quota) failed, the live `PENDING` row survived while its object was deleted → dedup-blocked, unprocessable orphan. Now mirrors the canonical `document_committed`/`reversal_ok` ordering (`enhanced_file_service.py:1179`). |
| Dedup 409 / IntegrityError paths | n/a (dedup lives in the enhanced service)                                                                                                                                                  | `db.rollback()` + object delete; both fire before/at the first commit, so no live row exists — unchanged, correct.                                                                                                                                                                                                                                                                   |

### Outcome

After this PR the two paths are at parity on all three compensation concerns
(object delete, quota revert, `PENDING`-row cleanup). The only concrete gap was
the non-canonical committed-row cleanup, now closed with the smallest diff that
mirrors `FileService`; a failure-injection test asserts the object is deleted and
the committed row is soft-deleted when the post-commit step fails.
