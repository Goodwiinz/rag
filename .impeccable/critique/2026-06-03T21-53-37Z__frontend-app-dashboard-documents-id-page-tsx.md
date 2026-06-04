---
target: [id]
total_score: 27
p0_count: 2
p1_count: 2
timestamp: 2026-06-03T21-53-37Z
slug: frontend-app-dashboard-documents-id-page-tsx
---
## /impeccable critique — Document Detail (`documents/[id]/page.tsx`), register: product

### Overall impression
This is two files fighting each other. The **page itself** is one of the better product surfaces in NOUS: it uses semantic tokens (`bg-background`, `text-muted-foreground`, `border-border`, `primary`) almost everywhere, ships honest loading skeletons with `role="status"`, a designed error card with `role="alert"` and a retry, real empty states per tab, sentence-case copy, no em dashes, no gradient text, `aria-hidden` on decorative icons, `aria-label` on icon buttons, `focus-visible:ring` on every control, and a single gold accent. On its own it is a low-Good page.

But the page is only as honest as the components it renders, and **every heavy child it imports drags it down**: `IntegrityDetail`, `ExtractedTablePreview`, `CropExtractOverlay`, and `ProcessingStatus` are riddled with banned patterns — a dead `brand-cyan` token, hardcoded hex, `bg-black/30 backdrop-blur-xl` glassmorphism, `hover:text-white`, raw `text-green-600`/`text-red-600`, `font-mono` coordinate labels, and Title-Case "AI Integrity Analysis" copy. Because the user experiences the composed page, not the file, the effective grade lands at **Acceptable**, not Good. The page author did the work; the dependency authors did not, and nobody reconciled them.

### Heuristic scores (Nielsen 10)
| # | Heuristic | Score | Notes |
|---|-----------|------:|-------|
| 1 | Visibility of system status | 3 | Excellent on the page: skeletons, live processing status, extracting spinners, per-tab empty states. Docked because integrity score loads silently in a `useEffect` with errors only `console.error`'d (404 swallowed, others invisible). |
| 2 | Match real world | 3 | "Research citations", "Content integrity", arXiv/DOI badges all speak the researcher's language. But child copy slips into Title-Case jargon ("AI Integrity Analysis", "Likely AI-Generated", "Run New Check"). |
| 3 | User control & freedom | 2 | Delete and retry go through native `confirm()`/`alert()` — no designed dialog, no undo, no toast. Crop overlay supports Escape (good), but destructive delete is irreversible with a browser-default prompt. |
| 4 | Consistency & standards | 2 | The split personality. Page uses tokens + lucide; imports use hardcoded hex (`#1a1a1a`, `#D4A039`, `#ef4444`), `bg-black/30`, `text-brand-cyan`, `text-red-400`, and ProcessingStatus uses heroicons + `text-green-600`/`text-red-600`/`text-blue-600`. Two icon libraries, two color systems. |
| 5 | Error prevention | 2 | Disabled-until-indexed extract buttons with `title` tooltips are good. But delete relies on a `confirm()` string, and the crop `handleExtract` swallows failures silently (`catch {}` just clears the spinner — user sees nothing). |
| 6 | Recognition vs recall | 3 | Tabs, labeled icons, file-detail `dl`, metadata table all favor recognition. Tooltip-only explanation of why extract is disabled leans slightly on recall. |
| 7 | Flexibility & efficiency | 3 | Power-user friendly: copy CSV/Markdown, download CSV, crop-to-extract region, live WebSocket status, keyboard Escape. No keyboard story for the crop draw itself (mouse-only). |
| 8 | Aesthetic & minimalist | 3 | Page layout is clean, restrained, well-spaced 2-col grid. Loses points to child glassmorphism (`backdrop-blur-xl bg-black/30`) and the gauge ring built from inline `style={{ borderColor }}` hex. |
| 9 | Help users recover from errors | 3 | Page error state is exemplary (alert + retry + back). Extraction error is a real `role="alert"`. But crop-extract and integrity-fetch failures are silently swallowed. |
| 10 | Help & documentation | 3 | Inline guidance is good ("Citations become available once the document is indexed", "Matching references against arXiv, Semantic Scholar, and CrossRef"). No deeper help, acceptable for a power tool. |
| | **Total** | **27/40** | **Acceptable** (page alone ~31 Good; imports cost ~4). |

### Anti-patterns verdict
| Pattern | Present | Where |
|---|:--:|---|
| `--terminal-*` / phosphor costume | partial | `font-mono` coordinate chips in `CropExtractOverlay` (lines 221, 224); `brand-cyan` naming is cyberpunk residue |
| >1 accent hue | partial | `brand-cyan`/`text-brand-cyan` reads cyan in code across 3 child components; aliased to gold in config but the **token is never defined** (see P0) |
| Hardcoded hex / `text-gray-*` | **yes** | `IntegrityDetail` `#1a1a1a`, `#D4A039`, `#ffb700`, `#ef4444`; raw `text-green-600`/`text-red-600`/`text-blue-600`/`text-purple-600`/`text-orange-600` in `ProcessingStatus` |
| Gradient text (`bg-clip-text`) | no | — |
| Glassmorphism by default | **yes** | `IntegrityDetail` `DialogContent` `bg-black/30 backdrop-blur-xl`; page header `bg-card/80 backdrop-blur-xl` (defensible as a sticky nav, borderline) |
| Side-stripe accent borders | no | tab `border-b-2` is a standard underline, detector false-positive |
| Hero-metric template | no | — |
| Identical card grids | no | cards are varied (status, citations, file-info, integrity) |
| Em dashes in copy | no | page is clean; uses `…` correctly |
| Mono-everywhere | no (localized) | only the crop coordinate chips |
| `bg-black`/`hover:text-white` raw | **yes** | `bg-black/30/40/50/80`, `bg-white/5`, `hover:text-white` across all four imports |
| Title-Case / shouting copy | **yes** | "AI Integrity Analysis", "Likely AI-Generated", "Run New Check", "Processing Steps", "File Validation", "✓ Done" |

### AI-slop verdict: YES (in the composed view)
The page file would pass. The rendered experience would not. A reviewer opening the Integrity dialog sees `bg-black/30 backdrop-blur-xl` glass, a hex-bordered percentage ring, Title-Case "AI Integrity Analysis", and `brand-cyan` accents — the exact glassmorphism-plus-cyan-on-black-plus-Title-Case combination that screams "AI made this." The dead `--cyan` token is the tell: a real designer would have noticed the Extract button rendering colorless. This is product register, so the bar is "design serves the task and recedes" — the glass dialog and cyberpunk-named tokens fail that.

### Persona red flags
**Alex (power user, dashboards/data):**
- Deletes a document, gets a browser `confirm()` box (not styled, not undoable). For a researcher pruning a corpus mid-session, an irreversible native prompt with no undo toast is a trust break — one mis-click loses ingested work.
- Runs crop-extract, the network call fails, and **nothing happens** — `catch {}` only clears the spinner (`CropExtractOverlay` line 158). Alex re-drags the region wondering if the tool is broken.

**Sam (accessibility):**
- The crop overlay is **mouse-only** — `onMouseDown/Move/Up` with no keyboard path to draw or commit a selection. A keyboard or switch user cannot extract a region at all.
- `IntegrityDetail` gauge encodes the result in color alone (`style={{ color }}` red/gold) plus a tiny `tabular-nums` percent; the segment bars are color-only width. Borderline contrast on `text-red-300`/`red-400` over `bg-black/30`, and meaning-in-color-alone violates the AA brief.
- `ProcessingStatus` "Live"/"Offline" dot is a colored circle with adjacent text (ok), but `text-green-600` on `bg-card` and the `✓`/`Failed`/`Pending` status are fine textually — the gauge is the real failure.

### What's working (strengths)
1. **Honest states, designed not bolted on.** The loading skeleton mirrors the real 2-col layout with `sr-only role="status"`, the error card offers retry + back, and each tab has a tailored empty state ("No citations yet" vs "Table extraction needs a PDF" vs "Citations become available once the document is indexed"). This is exactly the "honest states" design principle.
2. **Provenance and accessibility in the page body.** Citations show authors/year/venue/arXiv/DOI with a "Needs review" flag — provenance is first-class. Every icon is `aria-hidden`, every icon-button labeled, every control has `focus-visible:ring`, the metadata renders as a real `<table>` and file details as a real `<dl>`. Tabs use `role="tablist"`/`role="tab"`/`aria-selected`.
3. **Restrained, single-accent palette in the page.** Sol/`primary` + `--nous-helios` hover is the only hue; tinted neutrals carry the rest. Sentence-case copy, no em dashes, `tabular-nums` on IDs/sizes/counts. This is the scholarly-warm register done correctly — the children just don't follow it.

### Priority issues
**P0 — Dead `brand-cyan`/`--cyan` token drives primary affordances in imported components.**
What: `tailwind.config.ts` maps `'brand-cyan': 'var(--cyan)'`, but `--cyan` is **never defined** in `globals.css` or `nous-tokens.css` (only mentioned in comments claiming it's aliased). `IntegrityDetail`, `ExtractedTablePreview`, and `CropExtractOverlay` use `text-brand-cyan` / `bg-brand-cyan` for the dialog icon, table-header text, "Click and drag" hint, and the **Extract button fill** (`bg-brand-cyan text-black`).
Why: The button background resolves to an undefined custom property — it renders with no/incorrect color, so the primary CTA in the crop flow is invisible or unstyled. It also re-introduces cyan/cyberpunk naming the brand explicitly banned.
Fix: Define `--cyan` → Sol in tokens, or (better) replace all `brand-cyan` with `primary`/`text-primary`/`bg-primary` and `--nous-sol`. Audit with `grep -rn "brand-cyan" src/`.
Command: `/impeccable colorize --token brand-cyan→primary --files src/components/documents/{IntegrityDetail,ExtractedTablePreview,CropExtractOverlay}.tsx`

**P0 — Destructive delete + retry use native `confirm()`/`alert()` with no undo.**
What: `handleDelete` (line 117) and `handleRetry`/extraction failures (lines 127, 141) use browser `confirm()`/`alert()`. Delete is irreversible and routes away on success.
Why: Violates "human-in-the-loop confirmation for destructive actions, designed not bolted on." A native gray prompt breaks the warm voice, isn't styled, isn't keyboard/AT-consistent, and offers no undo.
Fix: Replace with a shadcn `AlertDialog` for delete (title, consequence, typed-confirm or explicit "Delete document" button) and a toast (`sonner`) with an undo affordance; convert `alert('Failed…')` to a `role="alert"` inline banner consistent with the existing extraction-error pattern.
Command: `/impeccable harden --states destructive-confirm,toast-undo --file "app/(dashboard)/documents/[id]/page.tsx"`

**P1 — Hardcoded hex, `bg-black/white` opacity, and raw Tailwind palette across imports.**
What: `IntegrityDetail` uses `#1a1a1a`, `#D4A039`, `#ffb700`, `#ef4444` (inline `style`), `bg-black/30`, `bg-white/5`, `hover:text-white`; `ProcessingStatus` uses `text-green-600`, `text-red-600`, `text-blue-600`, `text-purple-600`, `text-orange-600`, `bg-gray-400`; `ExtractedTablePreview`/`CropExtractOverlay` use `text-red-400`, `bg-black/50`, `border-red-500/30`.
Why: Breaks the token system, won't theme-flip with `.dark`, and the `green-600`/`red-600` file-type colors are arbitrary chrome the brief calls "no ornament that does not inform."
Fix: Map to semantic/`--nous-*` tokens: success→`text-[var(--nous-terra)]` or a `success` token, error→`text-destructive`, gold→`text-primary`/`--nous-sol`, `bg-black/30`→`bg-card`/`bg-muted`. Remove `hover:text-white` → `hover:text-foreground`.
Command: `/impeccable colorize --detokenize-hex --map success,error,accent --files src/components/documents/*.tsx`

**P1 — Glassmorphism + Title-Case copy in IntegrityDetail (AI-slop signal).**
What: `DialogContent` is `border-[#1a1a1a] bg-black/30 backdrop-blur-xl`; copy is "AI Integrity Analysis", "Likely AI-Generated", "Run New Check", "AI Prob." (uppercase tracked micro-labels).
Why: Default glassmorphism and Title-Case shouting are both on the banned list and contradict "expert confidence, calm voice, sentence-case."
Fix: Solid surface (`bg-card border-border`), rewrite to sentence case ("Content integrity", "Likely AI-generated", "Run new check", "Method", "Analyzed"), drop the uppercase-tracked overlines or limit to one.
Command: `/impeccable distill --copy sentence-case --surface solid --file src/components/documents/IntegrityDetail.tsx`

**P2 — Silent failure on crop-extract and integrity fetch; mouse-only crop.**
What: `CropExtractOverlay.handleExtract` `catch {}` only clears the spinner; page integrity `useEffect` swallows non-404 errors to console; crop draw has no keyboard path.
Why: "Honest states" and AA keyboard requirements both fail — a failed extraction looks like a no-op, and AT users can't crop.
Fix: Surface extraction errors inline (`role="alert"`), add a keyboard fallback (numeric region inputs or arrow-key nudge), announce integrity-load failures.
Command: `/impeccable harden --states error,keyboard --file src/components/documents/CropExtractOverlay.tsx`

### Minor observations
- Header `bg-card/80 backdrop-blur-xl` sticky nav is borderline glass but defensible for a scroll affordance; keep it solid-enough that text stays AA.
- Download and Share buttons in the header have no `onClick` — dead affordances that suggest functionality. Either wire them or remove until real.
- `formatDate` uses `toLocaleString()` with no options on the page but a fixed `en-US` format in `IntegrityDetail` — inconsistent date rendering across the same screen.
- Tab `border-b-2` triggers the detector's "border-accent-on-rounded" warning — **false positive**; it's a standard tab underline, not a stripe on a card.
- Citation list `max-h-96 overflow-y-auto` scroll region has no visible affordance that more exists; consider a count-anchored "showing N" or fade.

### Questions
1. Is the `--cyan`/`brand-cyan` token intentionally aliased to gold elsewhere (a build step?), or is it genuinely undefined? If the former, where — because grep finds no assignment. If the latter, the Extract button is shipping unstyled.
2. Are the Download/Share header buttons stubs awaiting wiring, or should they be removed for this release?
3. Should `IntegrityDetail` and the table/crop components be treated as in-scope for this page's redesign, or are they shared across other surfaces (meaning a fix should be system-wide via the design tokens, not per-page)?
