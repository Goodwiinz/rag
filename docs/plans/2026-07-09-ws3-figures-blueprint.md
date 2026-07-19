# WS3 Blueprint — Figure Extraction (PyMuPDF, Phase 1)

Target repo: `/Users/goodwiinz/development/RAG_system/backend`. Three PRs, each its own branch off `origin/develop`. Docling is deferred (record at bottom). Zero new pip deps, one new config flag, **no migrations**.

---

## Anchor verification (all confirmed against code, 2026-07-09)

| Explore claim | Verdict |
|---|---|
| `table_extraction_service._safe_pdf_path` local-disk only, breaks on s3 | **CONFIRMED** — `table_extraction_service.py:30-36` realpath-validates against `settings.UPLOAD_DIR`; routes pass `document.file_path` (`table_extraction.py:78,139`) which on deployed s3 is `s3://bucket/key` → `ValueError` → 500 (tables) / 422 with internal-path detail (region). |
| Legacy `fitz.open(document.file_path)` breaks on s3 | **CONFIRMED** — `multimodal_processing_service.py:294+304` (`process_pdf`) and `:361+372` (`extract_text_with_ocr`). |
| `local_file_for_document` is the correct abstraction | **CONFIRMED** — `storage_utils.py:20-86`, contextmanager, s3/supabase/local, auto-cleanup. Already used by pipeline B's `process_text_extraction` (`processing_service.py:182-185`). |
| `_canonical_key` pattern | **CONFIRMED** — `do_kb/ingest.py:36-39`, `documents/{org}/{doc}.{ext}`. Figure crops must NOT go under this prefix (per-org KB data source indexes all of `documents/{org}/`). |
| `MultimodalContent` usable, no migration | **CONFIRMED with one correction** — table exists (`alembic/versions/f931599b6b5b`, create_table at :95), `ContentType.IMAGE` exists, `content_metadata` JSONB + `organization_id NOT NULL` present. **BUT see "What explore got wrong" #1.** |
| acks_late COMPLETED guard idiom | **CONFIRMED** — `processing_tasks.py:169`. |

### What explore got wrong / missed

1. **`MultimodalContent.content_type` cannot currently be inserted via the ORM at all.** The DB enum `contenttype` was created with **lowercase values** (`'text','image',...` — migration `f931599b6b5b` line 24), but the model column is `Enum(ContentType)` with **no `values_callable`** (`document_processing.py:198`), so SQLAlchemy emits the member *name* (`'IMAGE'`) → `invalid input value for enum contenttype`. Latent because the table has never been written outside `src/migrations/` utils. PR-2 fixes this **model-side only** (no DDL): add `values_callable` like `thread.py:55-60` does.
2. **Pipeline A has no broker redelivery on the upload path** — `document_upload.py` dispatches `process_document_upload` via FastAPI `background_tasks` in-process (explore report 1 says this itself, then still lists it under "missing acks_late guard"). Celery retry-on-exception (`document_processing_tasks.py:141-147`) still re-runs it, so the figure writer must be idempotent anyway — delete-before-insert covers both cases.
3. **`get_drawings` vector clustering: skipped, deliberately.** Correct clustering needs ruling-line/decoration filtering and rect-merge thresholds — that's Docling's job, not a cheap heuristic. Instead: caption-only rows (no crop) are persisted for vector figures, so their captions still reach retrieval. `# ponytail: raster+captions only; vector-figure crops are the Docling phase-2 upgrade path.`
4. Reports 1 and 2 disagree on which pipeline is "live" (A via `/api/v2/documents/upload` vs B via `documents.py:1214` reprocess + `file_service.py:482`). Both are real entry points; this blueprint hooks both, sharing one helper.

---

## PR-1 — fix s3-path bugs in table extraction + multimodal PDF steps

**Branch:** `fix/ws3-s3-path-table-multimodal` off `origin/develop`.

### Root cause
Two independent code sites read `document.file_path` as a local path. Deployed default is `storage_backend="s3"` where `file_path = "s3://bucket/key"`. Route everything through `local_file_for_document(document)` (the existing shared fix point — pipeline B already uses it).

### Files & changes

**1. `src/services/processing/table_extraction_service.py`**
Change both public methods to take the `Document` (sole caller is `table_extraction.py`):

```python
from src.services.documents.storage_utils import local_file_for_document

async def extract_region(self, document, page: int, x1: float, y1: float,
                         x2: float, y2: float) -> Dict[str, Any]:
    ...
    with local_file_for_document(document) as pdf_path:
        if getattr(document, "storage_backend", "local") == "local":
            pdf_path = self._safe_pdf_path(pdf_path)   # traversal guard only for DB-sourced local paths
        doc = fitz.open(pdf_path)
        ...  # existing body unchanged; keep doc.close() inside the with-block

async def extract_tables_from_pdf(self, document) -> List[Dict[str, Any]]:
    ...
    with local_file_for_document(document) as pdf_path:
        if getattr(document, "storage_backend", "local") == "local":
            pdf_path = self._safe_pdf_path(pdf_path)
        tables = camelot.read_pdf(pdf_path, ...)   # existing lattice→stream body, inside the with
```
Keep `_safe_pdf_path` as-is (it still guards a poisoned local `file_path`); it must NOT run on s3/supabase temp paths (they live in `S3_STORAGE_TEMP_DIR`, outside `UPLOAD_DIR`, by design).

**2. `src/api/documents/table_extraction.py`** — `:78` and `:138-139`: pass `document` instead of `document.file_path` (`_service.extract_tables_from_pdf(document)` / `extract_region(document=document, page=body.page, ...)`). The `.pdf` suffix checks at `:71,:131` keep working (`s3://.../x.pdf` still endswith `.pdf`) — leave them.

**3. `src/services/processing/multimodal_processing_service.py`** — PDF branch only:
- `process_pdf` (`:286-351`): replace `file_path = document.file_path` (`:294`) by wrapping the fitz **and** the pdfplumber-fallback body in `with local_file_for_document(document) as file_path:`.
- `extract_text_with_ocr` (`:353-413`): same at `:361`.
- Add the one shared import at module top.

### Out of scope (PR-1)
- The 8 other `document.file_path` sites in the same file (`:423,473,522,550,604,635,683,752` — image/audio/video steps): same pattern, not PDF, not exercised by WS3. Leave a one-line `# ponytail:` note at `process_image` (":423 et al. have the same s3 bug; fix when image/audio pipelines are live") and mention in the PR body.
- Event-loop blocking in the table routes (camelot runs sync inside `async def`) — pre-existing, unchanged.

### Tests (new: `tests/unit/services/test_table_extraction_s3_path.py`, `tests/unit/services/test_multimodal_pdf_s3_path.py`)
No binary fixtures — generate PDFs in-test with fitz (already installed):
```python
def _make_pdf(path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello table world")
    doc.save(path)
```
1. **s3 regression (the point of the PR):** fake document (`SimpleNamespace(storage_backend="s3", storage_path="org/doc/x.pdf", file_path="s3://b/org/doc/x.pdf", filename="x.pdf", id=uuid4())`); `monkeypatch.setattr("src.core.s3_client.S3StorageHelper", StubHelper)` where `StubHelper.download_to_tempfile` writes the generated PDF and returns its path (`local_file_for_document` imports the class at call time, so module-attr patching works). Assert `extract_region(...)` returns the text — previously raised `ValueError("outside the upload directory")`.
2. **Local traversal still rejected:** local-backend doc with `file_path="/etc/passwd"` → `ValueError`.
3. **`process_pdf` s3 regression:** same stub; assert `results["text_content"]` non-empty and `page_count == 1` — previously `fitz.open("s3://...")` raised.

### Rollout
No flag, pure bug fix. Verify on dev after merge: `GET /api/v1/documents/{id}/tables` against an s3-stored PDF returns 200 (today it 500s).

---

## PR-2 — PyMuPDF figure extraction as a shared, flag-gated ingestion step

**Branch:** `feat/ws3-figure-extraction` off `origin/develop` (stack on PR-1 if it hasn't merged; the multimodal step needs PR-1's `local_file_for_document` pattern only in the sense of not regressing — the new helper is self-contained either way).

### Shared-helper shape (logic lives once)
One new module, one sync entry point, called from both pipelines:

**New: `src/services/processing/figure_extraction_service.py`**

```python
"""PyMuPDF-based figure extraction. Phase 1: embedded raster images + caption
heuristics. No models, bounded per-page work. Docling is the phase-2 upgrade."""

FIGURES_SECTION_MARKER = "\n\n## Extracted figures\n"
EXTRACTION_METHOD = "pymupdf_figures"          # discriminator for rows + delete-before-insert
MIN_DIM_PX = 64                                 # skip icons/decorations
MAX_FIGURES_PER_DOC = 50                        # hard bound on work + rows
CAPTION_RE = re.compile(r"^\s*(fig(?:ure)?\.?\s*\d+)[.:]?\s*", re.IGNORECASE)

def extract_figures_for_document(db: Session, document: Document) -> Dict[str, Any]:
    """Idempotent. Returns {"figures_extracted": int, "captions_found": int,
    "captions_text": str, "skipped": Optional[str]}. Raises only on unexpected
    errors (callers treat the step as optional)."""

def merge_captions_into_text(existing: Optional[str], captions_text: str) -> str:
    """Strip any prior FIGURES_SECTION_MARKER section, then append the new one.
    Idempotent under re-runs even when content_text wasn't rebuilt."""
    base = (existing or "").split(FIGURES_SECTION_MARKER)[0].rstrip()
    return f"{base}{captions_text}" if captions_text else base
```

**Internal algorithm of `extract_figures_for_document`** (all inside one `with local_file_for_document(document) as pdf_path:` — it re-downloads the PDF; a few MB, acceptable, keeps the helper callable from anywhere):

1. **Gate:** if `not settings.FIGURE_EXTRACTION_ENABLED` → `{"skipped": "disabled"}`. If document isn't a PDF → `{"skipped": "not_pdf"}` (callers also pre-check; belt-and-braces).
2. **Collect raster candidates** per page: `page.get_image_info(xrefs=True)` → dicts with `xref`, `bbox`, `width`, `height`. Skip `width < MIN_DIM_PX or height < MIN_DIM_PX`; dedupe by `xref` across pages (repeated logo emits once). Stop at `MAX_FIGURES_PER_DOC`.
3. **Collect captions** per page: `page.get_text("blocks")`, text blocks (`block_type == 0`) matching `CAPTION_RE`. Associate each caption to the nearest raster bbox on the same page by vertical gap (caption below or above the image, nearest wins); unmatched captions become **caption-only** candidates (no crop — this is how vector figures reach retrieval).
4. **Render crops** for raster candidates: `pix = fitz.Pixmap(pdf_doc, xref)`; if `pix.n - pix.alpha > 3`: `pix = fitz.Pixmap(fitz.csRGB, pix)`; `png = pix.tobytes("png")`; drop the pixmap each iteration (bounded memory).
5. **Upload crops** org-scoped, deterministic keys (idempotent overwrite, mirroring the `_canonical_key` idea but under a **sibling prefix the DO KB data source does not index**):
   `figures/{document.organization_id}/{document.id}/{content_id}.png` via `S3StorageHelper().upload_file(key, png, content_type="image/png")`.
   - Build the helper once in a try/except: if `S3StorageHelper()` raises `RuntimeError` (S3 unconfigured — local dev), log once and proceed **caption-only for everything** (`storage_key=None` on rows).
   - **Compensating delete:** accumulate `uploaded_keys`; on any exception after the first upload, best-effort `helper.delete_file(k)` for each, then re-raise (matches the upload-before-DB compensation rule).
6. **Persist rows** — delete-before-insert keyed on our discriminator (covers acks_late redelivery, Celery retries, and reprocess):
   ```python
   db.query(MultimodalContent).filter(
       MultimodalContent.document_id == document.id,
       MultimodalContent.organization_id == document.organization_id,
       MultimodalContent.extraction_method == EXTRACTION_METHOD,
   ).delete(synchronize_session=False)
   ```
   Row shape (per figure, `content_id = f"figure-p{page}-x{xref}"` raster / `f"figure-p{page}-c{n}"` caption-only):
   ```python
   MultimodalContent(
       document_id=document.id,
       organization_id=document.organization_id,      # tenancy: mandatory
       content_type=ContentType.IMAGE,
       content_id=content_id,
       sequence_order=i,
       raw_content=caption_text or None,
       processed_content=caption_text or None,
       content_metadata={
           "kind": "figure",
           "page": page_no,                    # 1-based
           "bbox": [x0, y0, x1, y1],
           "storage_key": key_or_none,
           "figure_label": label_or_none,      # e.g. "Figure 3"
       },
       media_dimensions={"width": w, "height": h} if raster else None,
       media_format="png" if raster else None,
       extraction_method=EXTRACTION_METHOD,
       extraction_confidence=0.6,              # honest heuristic constant
   )
   ```
   The **caller** commits (both callers already hold the transaction rhythm of their file).
7. **Build `captions_text`** for retrieval — the minimal path (DO KB mirrors `content_text`; tsvector builds from `content_text`; both pipelines already push it):
   ```
   \n\n## Extracted figures\n[Figure 1, p.3] Caption text…\n[Figure 2, p.5] …\n
   ```
   Only captioned figures contribute lines; empty if none.

### Wiring — Pipeline A (`multimodal_processing_service.py`)
- `get_processing_pipeline` PDF branch (`:249-256`): insert after OCR:
  ```python
  ProcessingStep("Figure Extraction", self.extract_figures, required=False),
  ```
  (step-result key becomes `figure_extraction` via `:166` name mangling.)
- New thin method on the service:
  ```python
  async def extract_figures(self, document: Document, job: ProcessingJob) -> Dict[str, Any]:
      from src.services.processing.figure_extraction_service import extract_figures_for_document
      if not settings.FIGURE_EXTRACTION_ENABLED:
          return {"skipped": "disabled"}
      result = extract_figures_for_document(self.db, document)
      self.db.commit()
      return result
  ```
  Sync-in-async matches every other step in this file (`process_pdf` etc.).
- `update_document_with_results` (`:1259`): captions must merge **after** `content_text` is assigned at `:1268` (pipeline A sets `content_text` last, so the step itself must not touch it):
  ```python
  captions = (results.get("figure_extraction") or {}).get("captions_text")
  if captions:
      from src.services.processing.figure_extraction_service import merge_captions_into_text
      document.content_text = merge_captions_into_text(document.content_text, captions)
  ```
  Known honest ceiling: in pipeline A, `generate_embeddings` (DO KB sync, `:1091`) runs **before** `content_text` is finalized — captions reach DO KB on the *next* sync, not this run. That's a pre-existing ordering quirk of pipeline A (it syncs before content_text is written at all); do not restructure. Tsvector/fulltext (the live dev retrieval) is unaffected in pipeline B and pipeline A's `is_indexed` handling is unchanged.

### Wiring — Pipeline B (`processing_tasks.py`, inside `process_document_ingestion`)
Insert between Step 1 (content_text committed, after `:208`) and Step 2, so captions ride the DO KB mirror (`:276`) and tsvector (`:288`) for free:
```python
# Step 1b: Figure extraction (optional, flag-gated; never fails ingestion)
if settings.FIGURE_EXTRACTION_ENABLED and document.document_type == DocumentType.PDF:
    try:
        from src.services.processing.figure_extraction_service import (
            extract_figures_for_document, merge_captions_into_text,
        )
        job.update_progress("Extracting figures", 35)
        db.commit()
        fig_result = extract_figures_for_document(db, document)
        if fig_result.get("captions_text"):
            document.content_text = merge_captions_into_text(
                document.content_text, fig_result["captions_text"]
            )
        db.commit()
    except Exception as fig_err:  # optional step — mirror Neo4j-failure tolerance at :262
        db.rollback()
        logger.warning(f"Figure extraction failed for document {document.id}: {fig_err}")
```
Add `DocumentType` to the existing `from src.models.document import ...` line (`:17`). The existing COMPLETED guard at `:169` short-circuits full redelivery; mid-run crash redelivery is covered by delete-before-insert + deterministic overwrite keys.

### Other files
- **`src/core/config.py`** — next to `DO_KB_ENABLED` (`:177`): `FIGURE_EXTRACTION_ENABLED: bool = False`.
- **`src/models/document_processing.py:198`** — the latent enum-case fix (model-only, no migration; copy `thread.py:55-60`):
  ```python
  content_type = Column(
      Enum(ContentType, values_callable=lambda x: [e.value for e in x], native_enum=True),
      nullable=False, index=True,
  )
  ```

### Why no dedicated Celery queue (recorded justification)
PyMuPDF figure extraction is bounded, model-free work: per-page `get_image_info`/`get_text("blocks")` costs the same order as the text extraction the shared worker already does, and the OCR step already rasterizes **entire pages at 2× zoom** (`:379`) — larger pixmaps than any figure crop. Peak memory is one pixmap at a time, freed per iteration, capped at 50 figures/doc. No model residency → no acks_late×OOM poison-loop risk, so the shared 2Gi worker (concurrency 2, 900MB/child recycle) is fine. Idempotency under acks_late is handled by the existing COMPLETED guard + delete-before-insert + deterministic object keys. A dedicated queue is exactly the cost Docling phase 2 would pay — not this.

### Tests (`tests/unit/services/test_figure_extraction_service.py`, `tests/unit/services/test_figure_pipeline_wiring.py`)
Generate PDFs with fitz in-test (insert a generated PNG via `page.insert_image(rect, stream=png_bytes)` + `page.insert_text` for captions):
1. Raster figure + `"Figure 1: The caption"` below it → 1 candidate, caption matched, bbox/dims populated.
2. 16×16 image → filtered out (MIN_DIM_PX).
3. Caption text with no image on page → caption-only candidate (`storage_key is None` path).
4. `merge_captions_into_text` applied twice → exactly one section (idempotency).
5. Compensating delete: stub `S3StorageHelper` whose `upload_file` raises on the 2nd call → assert `delete_file` called with the 1st key, exception propagates.
6. S3 unconfigured (`S3StorageHelper.__init__` raises `RuntimeError`) → helper degrades to caption-only, no raise.
7. Flag off → `{"skipped": "disabled"}`, no DB writes (mock session assert).
8. Delete-before-insert: mock session → assert `.delete(synchronize_session=False)` filter includes `extraction_method == "pymupdf_figures"` and rows added carry `organization_id == document.organization_id` and `content_type == ContentType.IMAGE`.
9. Wiring: `get_processing_pipeline(DocumentType.PDF)` contains a `"Figure Extraction"` step with `required=False`.

### Rollout
Merges inert (flag off everywhere). Flip: set `FIGURE_EXTRACTION_ENABLED=true` via Infisical backend path (per plan rule 3 — add the Infisical entry when flipping, not in the PR), verify on dev by reprocessing an arXiv PDF (`documents.py:1125` reprocess → pipeline B) and checking `multimodal_content` rows + `## Extracted figures` in `content_text`.

### Out of scope (PR-2)
- Vector-figure crops (`get_drawings` clustering) — Docling phase 2.
- Equation extraction of any kind — pymupdf can't recognize math; Docling phase 2.
- Deleting `figures/{org}/{doc}/` objects when a document is deleted — rows cascade-delete, PNGs orphan as private objects under a deterministic prefix; cheap follow-up in the document-deletion flow, note in PR body with a `# ponytail:` comment.
- Table persistence into `MultimodalContent` (tables stay on-demand REST).
- Any DO KB indexing of the crop images themselves (crops deliberately live outside `documents/{org}/`).

---

## PR-3 — surface figures via the documents API

**Branch:** `feat/ws3-figures-endpoint` off `origin/develop` after PR-2 merges.

### Files

**New: `src/api/documents/figures.py`** — mirror `table_extraction.py`'s shape exactly (router prefix `/api/v1/documents`, org-scoped document 404 first):

```python
@router.get("/{document_id}/figures")
async def list_figures(document_id: UUID,
                       current_user: User = Depends(get_current_user),
                       organization: Organization = Depends(get_current_organization),
                       db: AsyncSession = Depends(get_db)):
```
1. Fetch document with `Document.id == document_id, Document.organization_id == organization.id, Document.is_deleted == False` → 404 if missing (copy `table_extraction.py:55-69` verbatim).
2. Query rows (tenancy filtered on the rows too):
   ```python
   select(MultimodalContent).where(and_(
       MultimodalContent.document_id == document_id,
       MultimodalContent.organization_id == organization.id,
       MultimodalContent.extraction_method == "pymupdf_figures",
       MultimodalContent.is_deleted == False,
   )).order_by(MultimodalContent.sequence_order)
   ```
   (Filter on `extraction_method`, not JSONB `kind` — indexed-ish string column, no JSONB operator fuss.)
3. Signed URLs: build `S3StorageHelper()` once in try/except (`None` if unconfigured); per row `meta = row.content_metadata or {}`; `image_url = helper.create_signed_url(meta["storage_key"])` in try/except → `None` on any failure (15-min default expiry is fine).
4. Response:
   ```json
   {"document_id": "...", "figure_count": 2, "figures": [
     {"content_id": "figure-p3-x12", "page": 3, "bbox": [..], "figure_label": "Figure 1",
      "caption": "…", "width": 640, "height": 480, "image_url": "https://…signed…"}]}
   ```
   (`caption` = `processed_content`; `page`/`bbox`/`figure_label` from `content_metadata`; `width`/`height` from `media_dimensions`; all nullable.)

**`src/api/documents/__init__.py`** — `from .figures import router as figures_router` + `__all__` entry (mirror line 9/18).
**`src/main.py`** — add to the `:41-46` import block + `app.include_router(figures_router)` next to `:601`.

### Tests (`tests/unit/api/test_documents_figures.py`)
Mirror the existing api-test style (dependency overrides for `get_db`/`get_current_user`/`get_current_organization`):
1. Wrong-org document → 404 (tenancy).
2. Happy path: stubbed rows → payload shape, ordered by `sequence_order`.
3. Row without `storage_key` (caption-only) → `image_url: null`, 200.
4. `S3StorageHelper` unavailable → `image_url: null` for all, still 200 (no 500 on local dev).

### Rollout
No flag needed (reads existing rows; empty list until PR-2's flag is flipped). Frontend out of scope.

---

## Docling Phase-2 deferral record (paste into the plan doc under WS3)

> **Docling deferred (2026-07-09 design decision).** Phase 1 ships PyMuPDF-only figure extraction: zero new deps, no model downloads, runs on the shared 2Gi Celery worker. Docling was assessed and is *not a requirements.txt line*: it needs (a) a **dedicated worker deployment** (own queue, 4–6Gi memory, low concurrency) because DocLayNet/TableFormer residency blows both the 900MB `max-memory-per-child` recycle and the 2Gi pod limit — with global `task_acks_late=True` an OOM becomes a **redelivery poison loop** on the shared `document_processing` queue; (b) **pre-baked HF models in the image** (+`HF_HUB_OFFLINE`) to avoid cold multi-hundred-MB downloads per fresh pod; (c) its own COMPLETED-guard idempotent task. CPU-only cluster ⇒ seconds-to-minutes per page. **Revisit when equation→LaTeX (or semantic layout / vector-figure classification) becomes a hard requirement** — pymupdf structurally cannot do those. Narrower alternative if only math is needed: pix2tex/texify over the caption-anchored crop regions PR-2 already persists. Phase-1 rows are forward-compatible: Docling output would upsert the same `MultimodalContent` shape under a new `extraction_method`.

---

## Cross-PR notes for implementers
- Sync `SessionLocal` in worker code; never hand sync objects to async sessions (DO KB bridge stays untouched).
- black (88) + isort on touched files only; structlog/stdlib-logging per file convention (figure service: structlog; edits in `processing_tasks.py`/`multimodal_processing_service.py` use each file's existing `logger`).
- `/code-review` before ready; land via `/nous-merge-loop`; PRs target `origin/develop` (local develop is a diverged fork — always branch from `origin/develop`).
- Review gate per plan: a golden arXiv PDF with known figures — assert figure count, caption text present in `content_text`, and signed URL fetchable on dev. LaTeX-fidelity assertion from the original plan is **not applicable to Phase 1** (no equation extraction) — the plan's WS3 review line should be amended alongside the deferral record.