# WS1 Blueprint — Citation-Faithfulness Verifier + Reviewer Pass

All anchors below verified against the working tree (2026-07-09). Branches cut from `origin/develop` (local develop is a diverged fork). All paths relative to `/Users/goodwiinz/development/RAG_system/backend`.

**Explore-report corrections (verified):**
1. `_tool_create_draft` is at `src/api/agent/tools_impl.py:2190-2241`, **not** L2388-2439 (L2383+ is `_tool_execute_code`). The dispatch is at L641; the fresh-session block is L2216-2230.
2. Everything else held: `_init_openai_client` L366-380, `_generate_draft_async` L189-364, persist block L269-317, `_extract_citations_from_content` L543-570, `extraction_matrix_service._get_openai_client` L48-76, `ReflectionResult` L42-47, `CrossRefClient`/`SemanticScholarClient` L204-287/L67-196, `extract_from_semantic_scholar` L520-580, `extract_from_crossref` L582-656.
3. Both Phase-0 bugs are **real**: (a) `_init_openai_client` reads only `settings.OPENAI_API_KEY` → returns `None` on Azure-only dev → `_build_draft_content` (L391) always falls to template. (b) `generate_draft` (L153) fire-and-forgets `_generate_draft_async` and returns immediately; `_tool_create_draft`'s `async with AsyncSessionLocal() as draft_db:` (L2223) exits — closing the session — before the background task's first `self.db.execute` (L219). REST path (`src/api/research/drafts.py:112`) hands in the request session that `get_db` closes after the 202. It "works" today only because AsyncSession context-exit does close-with-return-to-pool and the pool connection is usually still usable, but it's a rollback/`InvalidRequestError` race and the fresh-session comment at L2221-2222 is wrong about what it protects.
4. The service-conventions report says "use `llm_factory`, not raw openai client" — correct **for the new verifier** (Phase 1). For Phase 0a we keep the existing raw `chat.completions.create` call and only fix client selection (smallest diff; a langchain rewrite of `_build_draft_with_llm` is out of scope).
5. `extract_from_arxiv` is broken (wrong `ArXivIngestionService` ctor arg) — confirmed report finding, but we don't touch it: the verifier cascade uses S2 (which resolves `ARXIV:` ids) + CrossRef. Do NOT add the arXiv rung.

---

## PR-A — fix: draft LLM client is OpenAI-key-only (Azure-only dev always template-falls-back)

Branch: `fix/draft-llm-azure-client` off `origin/develop`. One file + one test file.

### Modify `src/services/research/draft_generation_service.py`

**1. `__init__` (L107-109):**
```python
def __init__(self, db: AsyncSession):
    self.db = db
    self._openai_client, self._openai_model = self._init_openai_client()
```

**2. Replace `_init_openai_client` (L366-380) wholesale** — delegate to the proven Azure-first selector instead of duplicating it:
```python
@staticmethod
def _init_openai_client() -> Tuple[Optional[Any], str]:
    """Azure-first client selection (extraction_matrix pattern).
    Returns (client, model); (None, "") when no key is configured →
    template fallback."""
    try:
        from src.services.research.extraction_matrix_service import (
            ExtractionMatrixService,
        )

        return ExtractionMatrixService._get_openai_client()
    except Exception as exc:  # RuntimeError = no key configured
        logger.warning("openai_client_init_failed", error=str(exc))
        return None, ""
```
`Tuple` is already imported (L10). `_get_openai_client` (extraction_matrix_service.py:48-76) returns `(AsyncAzureOpenAI, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME)` when Azure keys exist, `(AsyncOpenAI, "gpt-4o-mini")` on OpenAI key, raises `RuntimeError` on neither — the raise maps to the existing `None` → template behavior. `_build_draft_content` L391 (`if self._openai_client is not None`) needs no change.

**3. `_build_draft_with_llm` (L465-476):** replace the hardcoded model and guard the gpt-5 temperature quirk (mirrors `llm_factory._build_chat_llm` L93):
```python
create_kwargs: Dict[str, Any] = {
    "model": self._openai_model,
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    "max_tokens": 4000,
}
if not self._openai_model.startswith("gpt-5"):
    create_kwargs["temperature"] = 0.7
response = await asyncio.wait_for(
    self._openai_client.chat.completions.create(**create_kwargs),
    timeout=60.0,
)
```

### Tests — new `tests/unit/services/test_draft_generation_llm_client.py` (flat dir convention)
Mock `settings` via `patch("src.core.config.settings", ...)` / patch `ExtractionMatrixService._get_openai_client`:
1. Azure keys set → `_init_openai_client()` returns `(AsyncAzureOpenAI instance, <deployment>)`.
2. Only `OPENAI_API_KEY` → `(AsyncOpenAI instance, "gpt-4o-mini")`.
3. No keys → `(None, "")` and `_build_draft_content` returns the template (assert `## Abstract` marker, no client call).
4. `_build_draft_with_llm` passes `model=self._openai_model` to `chat.completions.create` (AsyncMock, inspect call kwargs).
5. gpt-5 deployment → no `temperature` kwarg; gpt-4o → `temperature=0.7`.

### Rollout
No new env vars — `AZURE_OPENAI_CHAT_*` already deployed (extraction matrix uses them live). Merge = drafts on dev immediately switch from template to real LLM output. Out of scope: rewriting `_build_draft_with_llm` onto `llm_factory`/langchain; touching timeout/max_tokens.

---

## PR-B — fix: `_generate_draft_async` runs on a session its caller already closed

Branch: `fix/draft-bg-session-ownership` off `origin/develop`. Two files + one test file.

### Modify `src/services/research/draft_generation_service.py`

`_generate_draft_async` (L189-364) owns its session — same pattern as `ExtractionMatrixService.run_background_extraction` (extraction_matrix_service.py:106). Concretely:

- Add import at top: `from src.core.database import AsyncSessionLocal` (extraction_matrix imports it module-level at L12; safe).
- Wrap the whole `try:` body (L204-342) in `async with AsyncSessionLocal() as db:` and replace the six `self.db` uses **inside this method only** with `db`: L219 (`self.db.execute(docs_query)`), L273 (version query), L278 (`is_current=False` update), L302-303 (`db.add(draft)` / `flush`), L315 (`db.add(draft_citation)`), L317 (`commit`). The `except` blocks (L344-364) stay outside the `async with` (they only touch `_generation_status` + metrics).
- `self.db` stays for the ctor and the request-scoped methods (`export_draft` etc.) — no other change.

### Modify `src/api/agent/tools_impl.py` (L2216-2230)

The fresh-session wrapper is now dead weight and its comment is wrong. Replace L2216-2230 with:
```python
        from src.services.research.draft_generation_service import (
            DraftGenerationService,
        )

        # Background generation owns its own AsyncSessionLocal; the
        # request session here is only used for the ownership check above.
        draft_service = DraftGenerationService(db)
        result = await draft_service.generate_draft(
            project_id=project.id,
            user_id=current_user.id,
            themes=themes,
            style=style,
        )
```
(Drop the `AsyncSessionLocal` import at L2216 — grep confirms other call sites in the file import it locally, so nothing else breaks.)

`src/api/research/drafts.py:112` needs no change (request session now legitimately unused by the background path).

### Tests — new `tests/unit/services/test_draft_bg_session.py`
Existing `test_draft_docids_project_scope.py` only exercises the static query builder — unaffected.
1. Patch `src.services.research.draft_generation_service.AsyncSessionLocal` with an async-context-manager mock; construct `DraftGenerationService(MagicMock())`; run `_generate_draft_async(...)` with a mocked doc result; assert the **ctor session's** `execute` is never awaited and the patched session's `execute`/`commit` are.
2. Happy path through the patched session reaches `_generation_status[task_id]["status"] == "completed"` (documents mocked, `_build_draft_content` patched to return a string).
3. Empty document list → `FAILED` status, patched session not committed.

### Rollout
Pure correctness fix, no flags, no env vars. Out of scope: moving `_generation_status` to Redis (known multi-replica gap, pre-existing).

---

## PR-C — feat: `CitationVerificationService` (Phase 1, unwired)

Branch: `feat/citation-verification-service` off `origin/develop`. One new service file, one enum/schema addition, one test file. Pure addition — nothing calls it yet, merge inert.

### Add to `src/shared/research_schemas.py` (next to `MetadataSource`, L45)

```python
class CitationVerdict(str, Enum):
    """CiteCheck-style faithfulness verdicts for draft citations."""

    EXACT = "exact"        # claim fully supported by the source
    MINOR = "minor"        # supported with small imprecision/overstatement
    MAJOR = "major"        # unsupported, contradicted, or identity mismatch
    UNVERIFIED = "unverified"  # provider outage / LLM timeout — not a miss
```

### Create `src/services/research/citation_verification_service.py`

Conventions: `structlog.get_logger()` (research-package style), black/isort/mypy-strict, service ctor `__init__(self, db: AsyncSession)` (db kept for signature symmetry; this service never queries — it only reads the `Document` rows handed to it, which keeps tenant scope airtight by construction).

```python
"""Citation faithfulness verification for generated drafts (CiteCheck pattern)."""

import asyncio
import difflib
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Literal

from src.models.document import Document
from src.services.agent._sanitize import _sanitize_prompt_field
from src.services.agent.llm_factory import build_lightweight_llm
from src.services.research.citation_extraction_service import (
    CitationExtractionService,
)
from src.shared.research_schemas import CitationCreate, CitationVerdict

logger = structlog.get_logger()

_CITATION_PATTERN = re.compile(r"\[Doc\s+(\d+)\]")  # same as MessageCitationService
_VERIFIER_TIMEOUT_SECONDS = 30.0
_MAX_DOCS_VERIFIED = 10          # ponytail: cap LLM fan-out; raise if drafts grow
_FULLTEXT_CHARS = 8000
_TITLE_MATCH_THRESHOLD = 0.6


class _LLMVerdict(BaseModel):
    """Structured output from the faithfulness LLM."""

    verdict: Literal["exact", "minor", "major"]
    evidence: str


class CitationVerificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def verify_draft_citations(
        self,
        draft_content: str,
        documents: Sequence[Document],
    ) -> Dict[str, Any]: ...

    # --- claim extraction -------------------------------------------------
    @staticmethod
    def _claims_by_doc_index(draft_content: str) -> Dict[int, List[str]]: ...

    # --- identity check (identifier hijacking) ----------------------------
    async def _check_identity(
        self, document: Document
    ) -> Tuple[str, Optional[CitationCreate]]: ...
        # returns (status, resolved) — status in {"match", "mismatch", "unresolved", "no_identifiers"}

    @staticmethod
    def _identity_matches(document: Document, resolved: CitationCreate) -> bool: ...

    # --- faithfulness check (LLM, abstract-first) --------------------------
    async def _judge_faithfulness(
        self, claims: List[str], source_text: str, doc_title: str
    ) -> Optional[_LLMVerdict]: ...
```

**`verify_draft_citations` flow** (per doc index found in the draft, capped at `_MAX_DOCS_VERIFIED`):
1. `_claims_by_doc_index`: for each `[Doc N]` match, capture the containing sentence — slice from the previous `.`/`\n` boundary to the next; dedupe; group by 1-based index; drop indices with no matching row in `documents` (same guard as `_extract_citations_from_content` L557-558).
2. **Identity check** — `_check_identity(document)`:
   - Read identifiers **from the in-memory row only**: `md = document.document_metadata or {}`; reuse `CitationExtractionService._extract_doi` / `._normalize_arxiv_id` (static, citation_extraction_service.py:323-345) over the same candidate keys `_resolve_document_identifiers` uses (L378-392). Do **not** call `_resolve_document_identifiers` itself — it re-queries by bare id with no org filter (explore-report risk confirmed).
   - Cascade over the existing extractors on a throwaway `CitationExtractionService(self.db)` (they never touch `db` for these paths): DOI → `extract_from_crossref(doi=...)`; else arXiv → `extract_from_semantic_scholar(arxiv_id=...)`; else title → `extract_from_semantic_scholar(title=...)`. First non-None wins; all-None → `"unresolved"` (providers already swallow outages to None — map that to UNVERIFIED downstream, never MAJOR). No identifiers at all → `"no_identifiers"` (skip identity, LLM-only).
   - `_identity_matches`: `difflib.SequenceMatcher(None, _norm(document.title), _norm(resolved.document_title)).ratio() >= _TITLE_MATCH_THRESHOLD` **or** (when both sides have authors: `md.get("authors")` vs `resolved.authors`) surname-set overlap ≥ 1. Title mismatch **and** author mismatch (or no local authors and title mismatch) → `"mismatch"` → **verdict MAJOR** regardless of LLM output, evidence = `f"identifier resolves to different work: {resolved.document_title!r}"`. This is the identifier-hijacking FAIL.
3. **Faithfulness check** — abstract-first (DeepSciVerify): pass 1 source = `document.content_summary` or resolved external `abstract` or `document.content_text[:2000]`; if pass-1 verdict != `"exact"` and `document.content_text`, escalate: pass 2 with `content_text[:_FULLTEXT_CHARS]`, take pass 2, record `escalated_to_fulltext=True`.
4. `_judge_faithfulness`: module-cached `build_lightweight_llm(max_tokens=4096, request_timeout=_VERIFIER_TIMEOUT_SECONDS)` (copy `_build_reflection_llm` shape, reflection.py:55-67 — 4096 because gpt-5 reasoning tokens count against the cap), `.with_structured_output(_LLMVerdict)`, `await asyncio.wait_for(structured.ainvoke(messages), _VERIFIER_TIMEOUT_SECONDS)`. On `TimeoutError`/`Exception` → return `None` (→ UNVERIFIED); **re-raise `asyncio.CancelledError`** (reflection.py:1191 convention). All untrusted text (claims, source excerpt, title) through `_sanitize_prompt_field`.
5. Combine: identity `mismatch` → MAJOR; identity `unresolved` with LLM verdict → LLM verdict (flag `"identity": "unresolved"`); LLM `None` → UNVERIFIED.

**Return shape** (this is the exact blob Phase 2 persists):
```python
{
    "verdicts": [
        {
            "doc_index": 2,
            "document_id": "uuid-str",
            "verdict": "major",                     # CitationVerdict value
            "identity": "mismatch",                 # match|mismatch|unresolved|no_identifiers
            "identity_source": "crossref",          # crossref|semantic_scholar|None
            "evidence": "identifier resolves to different work: '...'",
            "escalated_to_fulltext": False,
            "claims_checked": 3,
        },
    ],
    "summary": {"exact": 3, "minor": 1, "major": 1, "unverified": 0},
    "docs_checked": 5,
    "docs_skipped": 0,           # over the _MAX_DOCS_VERIFIED cap
    "duration_ms": 4200,
}
```

**LLM prompt sketch** (system + user, one call per doc, claims batched):
```
SYSTEM:
You are a citation-faithfulness verifier for academic literature reviews.
Given claims a draft attributes to a source, and an excerpt of that source,
classify overall faithfulness:
- exact: every claim is fully supported by the excerpt
- minor: claims are supported but contain small imprecision, overstatement,
  or detail not verifiable from the excerpt
- major: at least one claim is unsupported by or contradicts the excerpt
Quote the most decisive supporting or contradicting passage as evidence.
Respond in the structured format.

USER:
## Source: {sanitized title}
{sanitized source excerpt}

## Claims attributed to this source
1. {sanitized claim}
2. ...
```

### Tests — new `tests/unit/services/test_citation_verification_service.py`
Mock LLM via `patch("...citation_verification_service.build_lightweight_llm")` (AsyncMock `.with_structured_output().ainvoke`); mock extractors via `patch.object(CitationExtractionService, "extract_from_crossref", ...)`; documents = `MagicMock(spec=Document)`; service built with `AsyncMock()` db.
1. `_claims_by_doc_index` pulls the right sentences, groups/dedupes, ignores out-of-range indices.
2. **Identifier hijacking**: doc has DOI, CrossRef resolves a *different* title+authors → identity `"mismatch"`, verdict `"major"`, LLM never consulted for the final verdict.
3. Identity match + LLM `exact` → verdict `"exact"`, no full-text escalation.
4. LLM `minor` on abstract pass + `content_text` present → second call with full-text excerpt, `escalated_to_fulltext=True`, pass-2 verdict wins.
5. All providers return None → identity `"unresolved"`; LLM verdict still used.
6. LLM raises `TimeoutError` → verdict `"unverified"` (not major, no exception).
7. `asyncio.CancelledError` propagates.
8. Doc without identifiers → identity `"no_identifiers"`, LLM-only path.
9. Summary counts + `_MAX_DOCS_VERIFIED` cap → `docs_skipped`.

### Out of scope for PR-C
- **OpenAlex rung**: entirely absent from the codebase (0 grep hits). Adding it = new `OpenAlexClient` (aiohttp ctx-manager shape), a field mapper (`authorships[].author.display_name`, `publication_year`, `primary_location.source.display_name` — different from both CrossRef and S2), cascade wiring — ~120 lines + tests, plus its own polite-pool/throttle story. CrossRef+S2 already cover DOI/arXiv/title. Defer; note as follow-up.
- Retry/backoff on CrossRef/S2 (pre-existing single-shot behavior; UNVERIFIED verdict already absorbs outages).
- Fixing `extract_from_arxiv`'s broken ctor (separate bug, not on our path).
- A standalone `verify_citations` agent tool (plan mentions one; the reviewer pass covers the actual gap — add a tool later if a user-facing "check this draft" action is wanted).

---

## PR-D — feat: reviewer pass in the draft pipeline (Phase 2, flag default-off)

Branch: `feat/draft-citation-review-pass` off `origin/develop`. Depends on PR-B and PR-C being merged. Two files modified + one test file.

### `src/core/config.py` — one flag (place after `AGENT_PARALLEL_TOOL_CALLS`, ~L402)
```python
    # Citation-faithfulness reviewer pass in draft generation (WS1).
    # Default off: merge inert, flip in values-dev after verify.
    # When flipping on in dev, no secret is needed — boolean env only;
    # if ever sourced from Infisical, add DRAFT_CITATION_REVIEW_ENABLED
    # to the /do-kb path per project convention.
    DRAFT_CITATION_REVIEW_ENABLED: bool = False
```
This is the single unavoidable new setting. Rollout note: flip via helm values-dev env (ArgoCD auto-sync), not Infisical, since it's not a secret — the comment records the /do-kb convention anyway.

### `src/services/research/draft_generation_service.py`

**1. `DraftGenerationStatus` (L25-35):** add `REVIEWING = "reviewing"` after `CITING`. Frontend polling renders arbitrary `current_step` strings — no FE change needed.

**2. Hook in `_generate_draft_async`**, between citation extraction (post-PR-B: the `citations_data = self._extract_citations_from_content(...)` line) and the FINALIZING tick — i.e. between current L262 and L264:
```python
            citation_review: Optional[Dict[str, Any]] = None
            settings = get_settings()
            if settings.DRAFT_CITATION_REVIEW_ENABLED and citations_data:
                self._update_status(
                    task_id,
                    DraftGenerationStatus.REVIEWING,
                    85,
                    "Verifying citations",
                )
                try:
                    from src.services.research.citation_verification_service import (
                        CitationVerificationService,
                    )

                    citation_review = await CitationVerificationService(
                        db
                    ).verify_draft_citations(draft_content, documents)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    # Reviewer failure must never fail the draft.
                    logger.warning(
                        "citation_review_failed", task_id=task_id, error=str(exc)
                    )
                    citation_review = {"error": str(exc)}
```
(`db` = the background-owned session from PR-B; `documents` is the already tenant-scoped list — the verifier never re-queries, so no new tenant surface.)

**3. Persist into the existing JSONB** — extend the `generation_params` dict in the `GeneratedDraft(...)` ctor (L293-298):
```python
                generation_params={
                    "style": style,
                    "max_sections": max_sections,
                    "include_abstract": include_abstract,
                    "document_count": len(documents),
                    **(
                        {"citation_review": citation_review}
                        if citation_review is not None
                        else {}
                    ),
                },
```
No migration: `generation_params` is JSONB (`src/models/generated_draft.py:50`) and already round-trips through `to_dict`/API responses (L94, L111) — verdicts reach the draft API for free. `generation_time_ms` (L53, currently never written) stays out of scope.

### Tests — new `tests/unit/services/test_draft_citation_review_pass.py`
Build on PR-B's session mocking; patch `CitationVerificationService.verify_draft_citations`.
1. Flag off (default) → verifier never constructed; `generation_params` has no `citation_review` key; statuses never include `reviewing`.
2. Flag on → REVIEWING tick observed at progress 85; persisted `GeneratedDraft.generation_params["citation_review"]` equals the verifier's return blob; final status `completed`.
3. Flag on, verifier raises → draft still persists + `completed`; `citation_review == {"error": ...}`; `citation_review_failed` logged.
4. Flag on, `citations_data` empty (template draft with no `[Doc N]` hits) → verifier skipped.
5. **End-to-end identifier-hijacking regression**: real `CitationVerificationService` with mocked CrossRef client returning a mismatched work for the doc's DOI + mocked LLM returning `exact` → persisted verdict for that doc is `"major"` with the identity-mismatch evidence. (The adversarial-review acceptance case: DOI resolves but authors/title mismatch must FAIL even when the LLM is fooled.)

### Rollout
Merge inert (flag off). Flip `DRAFT_CITATION_REVIEW_ENABLED=true` in values-dev after manually generating a draft on dev and inspecting `generation_params.citation_review` via `GET /api/v1/.../drafts`. Latency budget: ≤ `_MAX_DOCS_VERIFIED` × ≤2 LLM calls (30s cap each) + 1 provider lookup each, all inside the background task — user-visible only as the REVIEWING progress tick. Out of scope: surfacing verdicts as frontend badges (`normalizeCitation`/`CitationChips` path — separate FE workstream; the citation-display explore map is the ready-made spec), draft auto-revision on MAJOR verdicts, Redis-backed status store.

---

## Execution order & discipline

| PR | Branch | Depends on | Size |
|---|---|---|---|
| A | `fix/draft-llm-azure-client` | — | ~25 LoC + tests |
| B | `fix/draft-bg-session-ownership` | — (parallel with A; trivial merge overlap in one file — land A first) | ~30 LoC + tests |
| C | `feat/citation-verification-service` | — (pure addition) | ~250 LoC + tests |
| D | `feat/draft-citation-review-pass` | B + C merged | ~50 LoC + tests |

Each PR: black/isort on touched files only, targeted `pytest tests/unit/services/test_<new>.py`, `/code-review` before ready, land via `/nous-merge-loop`. PRs target `develop`; never base on local develop.