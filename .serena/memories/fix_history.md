# Fix History

## Document Status Mapping (2025-11-09)
- `get_mapped_status()` in `src/models/document.py` used uppercase keys but enum values are lowercase
- Fix: lowercase keys: 'pending' → 'queued', 'failed' → 'failed', 'completed' → 'indexed'

## Backend Container (2025-11-09)
- Missing gunicorn in requirements.txt → added `gunicorn==21.2.0`

## Frontend API Error (2025-11-09)
- APIError interface required timestamp field → made optional with auto-generate

## Pydantic Validation (2025-11-09)
- DocumentResponse expected List[str] for tags but got None → made optional with default factory

## Real-time Processing (2025-11-21)
- Added WebSocket-based real-time document processing status system
- Files: `backend/src/api/realtime_document_status.py`, `backend/src/services/document_realtime_service.py`, `frontend/src/store/realtime-store.ts`, `frontend/src/services/realtime-websocket-service.ts`

## ArXiv API Timeout (2025-12-23)
- ArXiv API calls timing out → changed to `postWithLongTimeout` (5 min) in ArxivManagement.tsx

## Sidebar/Breadcrumb (2025-12-23)
- "Home" → "Dashboard" with `/dashboard` URL
- Fixed redundant "Dashboard / Dashboard" breadcrumb

## ArXiv Terminal Theme (2025-12-23)
- Rewrote ArXiv page with dark Terminal Observatory theme components
- Constants: PHOSPHOR_GREEN=#00ff9f, AMBER=#ffb700, CYAN=#00d4ff

## Security Fixes (2026-01-07)
- JWT tokens moved from URL params to Sec-WebSocket-Protocol header (`websocket_auth.py`)
- SQL injection prevented via validated enums (`src/shared/enums.py`)
- CORS locked to explicit allowlists (no wildcards)
- IconButton enforces aria-label (`frontend/src/components/ui/icon-button.tsx`)

## Projects API Parameter Shadowing (2026-01-27)
- `status` query param shadowed `fastapi.status` module → renamed to `project_status`
- Lesson: never name params same as imported modules
