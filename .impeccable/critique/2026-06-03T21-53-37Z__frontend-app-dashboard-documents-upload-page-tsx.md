---
target: upload
total_score: 32
p0_count: 0
p1_count: 2
timestamp: 2026-06-03T21-53-37Z
slug: frontend-app-dashboard-documents-upload-page-tsx
---
## /impeccable critique — Documents › Upload (product register)

**File:** `/home/clawdbot/clawd/rag/frontend/app/(dashboard)/documents/upload/page.tsx`
**Detector:** `node detect.mjs --json` on the page + `enhancedDocumentService.ts` → `[]` (zero findings). This page is genuinely clean on the mechanical anti-pattern checks: no hardcoded hex in className, no `text-gray-*`, no gradient text, no glassmorphism, no side-stripe borders, no em dashes, no font-mono spam. Colors flow through semantic tokens (`text-foreground`, `bg-muted`, `border-border`) and sanctioned `--nous-*` status vars.

### Heuristic scores (Nielsen 10)

| # | Heuristic | Score | Notes |
|---|-----------|:---:|-------|
| 1 | Visibility of system status | 4 | Per-file status pill (icon + dot + label), `role="progressbar"` with aria values, percent readout, toasts on completion/failure, `mounted` skeleton. Honest: progress is polled, not faked. |
| 2 | Match real world | 4 | Plain sentence-case ("Drag and drop files, or click to browse", "Up to 10 files, 50 MB each"), human size formatting, file-type chips. No jargon. |
| 3 | User control & freedom | 2 | Remove only for `pending`/`failed`. No cancel for in-flight uploads (`cancelUpload()` exists in the service but is never wired), no "clear queue", no undo of a removed file. Once you hit Upload you're committed. |
| 4 | Consistency & standards | 4 | One Sol accent + sanctioned status hues (Terra/Mars/Helios), consistent radii, focus rings, button patterns. Matches DESIGN.md restrained product strategy. |
| 5 | Error prevention | 4 | Client-side validation (type, 50MB, >10 files), pre-upload SHA-256 duplicate check, non-blocking sign-in hint, dropzone disabled while uploading. Strong. |
| 6 | Recognition rather than recall | 3 | Supported types visible as chips; queue persists. But no metadata UI: the user can't see or set title/tags/description even though the request object carries them — they must recall the auto-derived title is what ships. |
| 7 | Flexibility & efficiency | 2 | No per-file or bulk metadata editing, no priority selector (API supports low/normal/high/urgent), no keyboard affordance beyond the dropzone, no "retry" button for failed items (service has `retryDocumentProcessing`, UI only offers remove). Power-user ceiling is low. |
| 8 | Aesthetic & minimalist | 4 | Calm, two-card layout, deliberate spacing, restrained motion via MotionConfig. Chrome recedes. Good NOUS register fit. |
| 9 | Error recovery | 3 | Failed items show `role="alert"` error text and can be removed, toasts explain failures. But recovery = delete + re-add; no in-place retry, and a mid-batch failure doesn't surface a batch summary. |
| 10 | Help & documentation | 2 | Constraints are shown inline (sizes, types, count) which is good, but no explanation of what processing/indexing does, what "Quality 87%" or "Scan passed" mean, or where an indexed doc goes next. Provenance chips are dead ends. |

**Total: 32 / 40 — Good.** Solid, honest product surface that mostly serves the task; held back on control/freedom and flexibility.

### Anti-patterns verdict
**No AI-slop.** Detector clean and a manual pass confirms it: this does not look like "AI made this." It avoids every banned NOUS signal (terminal costume, >1 accent hue, hero-metric template, identical card grids, gradient text). One residue worth flagging — `const [terminalText, setTerminalText] = useState('')` (line 79) is declared and never used; the name echoes the deliberately-removed terminal costume. It never renders, so it's cosmetic, but delete it so the costume can't creep back.

### Overall impression
This is one of the better-behaved NOUS product pages. It reads as a calm research instrument: drop files, watch honest progress, see provenance metadata (document ID, quality, security scan). Accessibility is treated as first-class, not bolted on — `aria-label` on icon-only buttons, `aria-hidden` on decorative icons, `role="progressbar"`/`role="alert"`/`role="status"`, `MotionConfig reducedMotion="user"`, and the explicit comment that status color "is never the only signal." The weak spots are all about *agency and meaning*: the researcher can't shape what they upload (metadata), can't stop or retry once in motion, and the success metadata leads nowhere.

### What's working (strengths)
1. **Honest, accessible state machine.** Real polled progress (no fake bars), reduced-motion path, labelled progressbar, alert-role errors, status conveyed by icon + label + color together. This is exactly the "honest states" + "do not encode meaning in color alone" mandate from PRODUCT.md/DESIGN.md.
2. **Strong error prevention.** Type/size/count validation plus a content-hash duplicate check *before* upload, with a non-blocking sign-in hint rather than a hard gate. Respects the user's time.
3. **Disciplined register.** Token-only color, one Sol accent, sentence-case plain voice, restrained two-card composition. No costume, no SaaS-cream. Genuinely on-brand.

### Priority issues
- **[P1] No metadata entry before upload.** *What:* `DocumentUploadRequest` supports title, description, tags, priority, public/private, but the UI only ships filename-derived defaults. *Why:* For a research corpus, title/tags are how documents become findable later — forcing defaults degrades the whole downstream search/graph experience. *Fix:* Add a collapsible per-file metadata row (editable title, tag input, priority select, public toggle) in the queue item, defaulting to current values. *Command:* `/impeccable shape the upload queue item to expose editable title, tags, and processing priority per file`.
- **[P1] No cancel-in-flight or clear-queue, and no in-place retry.** *What:* Remove is gated to `pending`/`failed`; `cancelUpload()` and `retryDocumentProcessing()` exist in the service but aren't surfaced. *Why:* Violates user control & freedom — a wrong 50MB file mid-upload can't be stopped, a transient failure forces delete-and-redrop. *Fix:* Add a Cancel button for `uploading`/`queued`/`processing` states (calls `cancelUpload`), a "Retry" on failed items (calls `retryDocumentProcessing`), and a "Clear completed/all" header action. *Command:* `/impeccable add cancel, retry, and clear-queue controls to the upload queue`.
- **[P2] Provenance chips are dead ends; "Quality"/"Scan" unexplained.** *What:* `ID {documentId}`, `Quality 87%`, `Scan passed` render as static chips with no link or tooltip. *Why:* PRODUCT.md makes provenance first-class — showing an ID that doesn't link to the document, and a score with no definition, asserts rather than proves. Also small Terra text on `bg-muted` is a contrast risk at 11px. *Fix:* Make the completed chip link to the document detail/search view; add a tooltip defining the quality score; verify Terra-on-muted meets AA or swap to `text-foreground` with the icon carrying the success hue. *Command:* `/impeccable link upload success metadata to the document and verify chip contrast`.
- **[P2] Thin empty state and no post-upload next step.** *What:* Before any file is added the dropzone is the whole page; after success there's no "View in library / Ask a question about this" affordance. *Why:* The path from ingest to use is the product's whole point ("short path from question to cited answer"); it currently dead-ends at "Indexed." *Fix:* Add a primary next action on completion and a one-line orientation in the empty state about what happens after upload. *Command:* `/impeccable design the post-upload next step and a warmer empty state`.
- **[P3] Dead `terminalText` state.** *What:* Lines 79 declares unused state named after the removed terminal costume. *Fix:* Delete both the state and the import-time noise. *Command:* `/impeccable remove dead terminal-costume residue from the upload page`.

### Persona red flags (forms interface → Jordan + Sam)
- **Jordan (form-filler / task-focused researcher):** Drops a batch of PDFs, expects to tag them "lit-review-2026" before they vanish into the corpus — there's no field, so everything indexes under raw filenames and becomes harder to find later. Also can't stop a misdropped large file. Friction is in agency, not aesthetics.
- **Sam (assistive-tech user):** Largely well served — labelled progressbar, alert errors, status not color-only, reduced motion honored. Remaining gaps: the toast layer (`react-hot-toast`) may not be reliably announced for async completion/failure; verify it has an aria-live region. And 11px Terra/Dust-adjacent chip text needs an AA contrast check on the muted ground.

### Minor observations
- `result?: any`, `securityScan?: any`, `result?: any` on the update type lose type safety for the metadata chips — typing them would catch render bugs.
- `await new Promise(setTimeout 500)` between uploads serializes the batch with an artificial delay; fine for rate-limiting but worth a comment on why.
- The `websocket` field on `UploadedFile` is always `null` (service returns a placeholder); the realtime-sounding plumbing is actually polling. Honest in behavior, but the dead WebSocket scaffolding could be pruned.
- Two stacked cards (header card + dropzone card) is borderline cards-in-cards visually; the header could be a plain heading block to lighten it.

### Questions
1. Is metadata (title/tags) meant to be set here, or on a later document-detail screen? If later, the auto-title default is a real findability risk worth flagging to product.
2. Does the toast system wrap a polite `aria-live` region? That determines whether async success/failure is announced to screen readers.
3. Is there a deliberate reason `cancelUpload`/`retryDocumentProcessing` are implemented but unused — pending backend support, or just unwired?
