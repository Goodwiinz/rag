# Fix: Citation Preview Not Rendering for External Sources After Page Refresh

## Issue Date
2026-01-08

## Problem Description
Citation previews from external sources (like arXiv papers) were not rendering correctly after a page refresh. Citations worked during the initial chat session, but when the page was refreshed and messages were loaded from the database, the citation preview content was not displaying properly for external (non-database) sources.

## Root Cause
The bug was in `backend/src/api/workspaces.py` in the `_citation_to_response` function (lines 1106-1122).

For external sources (where `citation.document` is `None`), the function was:
1. **Missing `external_reference_id`** - Not returning the external reference ID at all
2. **Ignoring stored `document_title`** - Only checking `citation.document.title` which is `None` for external refs
3. **Ignoring stored `document_type`** - Only checking `citation.document.document_type.value` which is `None` for external refs

### Buggy Code (Before)
```python
def _citation_to_response(citation) -> CitationResponse:
    return CitationResponse(
        id=citation.id,
        document_id=citation.document_id,
        # MISSING: external_reference_id
        chunk_index=citation.chunk_index,
        chunk_id=citation.chunk_id,
        snippet=citation.snippet,
        snippet_preview=citation.snippet[:200] + "..." if citation.snippet and len(citation.snippet) > 200 else citation.snippet,
        page_number=citation.page_number,
        score=citation.score,
        rerank_score=citation.rerank_score,
        # BUG: Only checks document relationship, not stored fields
        document_title=citation.document.title if citation.document else None,
        document_type=citation.document.document_type.value if citation.document and citation.document.document_type else None
    )
```

## Solution
Updated `_citation_to_response` to match the correct implementation in `threads.py:_format_message_response`:

### Fixed Code (After)
```python
def _citation_to_response(citation) -> CitationResponse:
    return CitationResponse(
        id=citation.id,
        document_id=citation.document_id,
        external_reference_id=citation.external_reference_id,  # For arXiv IDs, etc.
        chunk_index=citation.chunk_index,
        chunk_id=citation.chunk_id,
        snippet=citation.snippet,
        snippet_preview=citation.snippet[:200] + "..." if citation.snippet and len(citation.snippet) > 200 else citation.snippet,
        page_number=citation.page_number,
        score=citation.score,
        rerank_score=citation.rerank_score,
        # Use stored title/type for external refs, or get from document relationship
        document_title=citation.document_title or (citation.document.title if citation.document else None),
        document_type=citation.document_type or (citation.document.document_type.value if citation.document and citation.document.document_type else None)
    )
```

## Files Modified

### Backend Fix (Deployed)
- `backend/src/api/workspaces.py`: `_citation_to_response` function
  - Added `external_reference_id` field
  - Added fallback for `document_title` to stored field
  - Added fallback for `document_type` to stored field

### Debug Logging Added
- `frontend/app/chat/page.tsx`: `normalizeCitation` function - logs raw citation data
- `frontend/src/hooks/useChatPersistence.ts`: `mapDbMessageToUI` function - logs raw citation data
- `frontend/src/components/chat/CitationPreview.tsx`: Component render - logs final citation data

## Related Fixes (2026-01-08)

### Fix 2: External Badge Consistency
**Problem**: "External" badge appeared during live chat but disappeared after page refresh.
**Root Cause**: arXiv IDs were set as `document_id` during live chat but stored as `external_reference_id` in DB.
**Solution**: Added UUID validation in `frontend/app/chat/page.tsx` to properly distinguish database IDs from external references.
```typescript
const isValidUUID = (str: string): boolean => {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidRegex.test(str);
};
// Only set document_id if valid UUID, otherwise set as external_reference_id
```

### Fix 3: Citation Panel Empty State
**Problem**: Citation panel showed "No citations yet" even when conversation had citations.
**Root Cause**: Messages weren't loaded because no thread was selected during initialization.
**Solution**: Added automatic thread selection in `frontend/src/hooks/useChatPersistence.ts` after loading threads.

### Fix 4: Citation Count Filter (GOO-24)
**Problem**: Panel showed "5 Sources Referenced" but only 2 were actually cited in response text.
**Root Cause**: All retrieved citations were displayed instead of filtering by inline references.
**Solution**: Used `extractCitationIndices()` from citationParser to filter citations by actual text references.
```typescript
const referencedIndices = extractCitationIndices(msg.content);
const citationsToShow = referencedIndices.length > 0
  ? msgCitations.filter((_, idx) => referencedIndices.includes(idx + 1))
  : msgCitations;
```

### Fix 5: Context Panel Dynamic Data
**Problem**: Context panel displayed static hardcoded information.
**Solution**: Replaced static data with real dynamic data:
- **Active Document**: Highest-scoring citation from conversation
- **Related Results**: Deduplicated citations sorted by relevance score
- **Follow-up Suggestions**: AI-generated via new `/api/v1/chat/suggestions` endpoint

**Files Modified**:
- `frontend/app/chat/layout.tsx`: Updated ContextPanel component with useMemo hooks
- `backend/src/api/chat.py`: Added `/suggestions` endpoint using Azure OpenAI

## Verification Steps