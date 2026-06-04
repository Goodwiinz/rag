---
target: documents
total_score: 31
p0_count: 0
p1_count: 3
timestamp: 2026-06-03T21-53-37Z
slug: frontend-app-dashboard-documents-page-tsx
---
## Documents page — /impeccable critique (register: product)

### Overall impression
This is one of the stronger product surfaces in the codebase. The page composition is restrained and legible: a header card, a 4-up stat row, a search/filter bar, an honest error region, a virtualized list, and pagination — in that reading order, with deliberate `space-y-6` rhythm. Color is fully token-driven (`text-primary`, `text-muted-foreground`, `--nous-terra/helios/mars` for status), icons are correctly `aria-hidden`, icon-only buttons carry `aria-label`, and the empty/loading/error states are all genuinely designed rather than bolted on. The detector returns a clean `[]` for the page and all three local components. The Sol accent is used once as identity (header chip, primary CTA, selection state) and status colors are functional, not decorative — this respects the "one accent hue" rule.

The drop in quality is almost entirely **inherited**, not authored here: the shared `Pagination` component (rendered at the bottom of this page) still wears the terminal costume the design system explicitly removed, and the destructive flows fall back to the browser's native `confirm()`/`alert()` in a product whose whole thesis is *designed* human-in-the-loop confirmation. Fix those two and this page jumps a band.

### Heuristic scores (Nielsen 10)

| # | Heuristic | Score | Notes |
|---|-----------|-------|-------|
| 1 | Visibility of system status | 4 | Refresh spins, list skeletons, per-row Processing/Queued/Indexed/Failed badges, "Deleting…" on bulk, "SHOWING x TO y OF z" range. Genuinely honest states. |
| 2 | Match real world | 4 | Plain sentence-case ("Your knowledge base library", "No documents yet"), human file sizes/dates, status words researchers expect. On-voice. |
| 3 | User control & freedom | 2 | Native `confirm()` is the only undo path for delete; no in-app undo/toast. Page-size control is wired but never rendered. Bulk-delete is recoverable only via the OS dialog. |
| 4 | Consistency & standards | 2 | Page + local components use shadcn/tokens cleanly; Pagination is a hand-rolled one-off with `font-mono`, glow shadow, `title` instead of `aria-label`, and bare `disabled:opacity-30` — a different visual language at the bottom of the same screen. |
| 5 | Error prevention | 3 | Confirm dialogs gate both deletes; search is debounced. But whole-row click can toggle selection accidentally, and there's no "select all across pages vs this page" disambiguation. |
| 6 | Recognition over recall | 4 | Active filter shown in trigger, current status checkmarked in menu, selection count badged, page range spelled out. Little to memorize. |
| 7 | Flexibility & efficiency | 3 | Bulk select + bulk delete, retry on failed rows, virtualized list (react-window) for large corpora. But no page-size selector, no keyboard row activation, no sort. |
| 8 | Aesthetic & minimalist | 3 | Page is clean and uncluttered; the Pagination glow + uppercase-mono range label add ornament that doesn't inform and reads as costume. |
| 9 | Error recovery | 3 | `role="alert"` error banner is good; failed rows offer Retry. But delete failures surface only as a native `alert('Failed to delete document')` — no actionable in-app recovery, no which-ones-failed detail on bulk. |
| 10 | Help & documentation | 3 | Empty state explains supported file types and CTAs to upload — effective inline help. No tooltips on what "Indexed/Queued" mean for a first-timer. |

**Total: 31/40 — Good.** (Held out of Excellent by the inherited Pagination costume, native confirm/alert destructive flows, and the inaccessible row-click selection.)

### Anti-patterns verdict
- Detector on page + DocumentStats + DocumentFilters + DocumentList: **clean (`[]`)**. No hardcoded hex, no `text-gray-*`, no gradient text, no glassmorphism, no side-stripe borders, no hero-metric template on this page.
- **Manual catch the detector missed (Pagination, `app/components/Pagination.tsx`):** `font-mono` on decorative uppercase "SHOWING / TO / OF" labels = mono-as-technical-shorthand + repeated uppercase tracked labels (both banned); and `shadow-[0_0_10px_var(--nous-sol-glow)]` on the active page is a HUD/glow flourish the design doc explicitly rules out ("no spinning HUD rings", glow theatrics). The detector passes it because every value is a sanctioned `--nous-*` token — a true false-negative on intent, not syntax. Note `--nous-sol-glow` is only `rgba(212,160,57,0.12)`, so the glow is nearly invisible anyway — ornament that doesn't even render as intended.
- **Stat cards** are a 4-up identical icon-card grid (`DocumentStats`), which flirts with the banned "identical icon-card grid." It's mitigated here because each card is a distinct, live metric (Total/Indexed/Processing/Failed) tied to status color, not a marketing repeat — acceptable, but watch it.
- **AI-slop verdict: NO.** Nobody would say "AI made this" of the page. It's specific, on-voice, and token-disciplined. The Pagination footer is the one spot that betrays an older generated layer.

### Cognitive load (8-item check)
1. Visual hierarchy — clear (header → stats → filters → list). ✓
2. Reading order — top-to-bottom, single column. ✓
3. Color meaning — status colors consistent, accent used once. ✓
4. Grouping/spacing — deliberate `space-y-6`, no cards-in-cards on the page. ✓
5. Affordances — checkbox vs row-click is ambiguous (two ways to select, one invisible). ✗
6. Text density — comfortable; row is scannable. ✓
7. Novel patterns — whole-row-toggles-selection (not open) is unexpected; most file lists open on row click. ✗
8. Memory burden — low; filters and selection are all shown. ✓
**6/8 clean.** The two misses both trace to the row interaction model.

### Persona red flags
- **Alex (power user):** Locked to 10 rows/page with no size selector despite `onPageSizeChange` being plumbed through — for a researcher with a 2,000-doc corpus that's a lot of clicking. No column sort, no keyboard row activation, no "select all matching filter across pages." The virtualized list is the right call for scale, but the controls around it under-serve density.
- **Sam (accessibility):** The list row is a `<div onClick>` — not focusable, not Enter/Space operable, so selecting a document is mouse-only. Pagination page-number buttons have no `aria-label`, no `aria-current="page"` on the active page, no `focus-visible` ring (only `title`), and rely on `disabled:opacity-30` (3.x:1, likely sub-AA when paired with low-opacity disabled state). Native `confirm()`/`alert()` are at least screen-reader-announced, which is the one a11y win of that fallback.

### What's working (strengths)
1. **Honest, designed states across the board** — skeleton loaders, a real empty state with supported-formats copy and a CTA, a `role="alert"` error banner, and per-row status with retry on failure. This is exactly the "honest states" principle from PRODUCT.md.
2. **Token + a11y discipline on the authored code** — zero hardcoded hex, semantic tokens throughout, every decorative icon `aria-hidden`, every icon button `aria-label`led, `tabular-nums` on counts. The page passes the detector clean.
3. **Provenance/density touches** — the `entities_count` sparkle badge surfaces extracted-entity provenance inline, and react-window keeps a large corpus performant without abandoning the warm card aesthetic.

### Priority issues
- **[P1] Pagination terminal costume + a11y gaps.** *What:* `font-mono` uppercase SHOWING/TO/OF labels and a Sol glow shadow on the active page; page buttons lack `aria-label`/`aria-current`/`focus-visible`. *Why:* directly reintroduces the removed terminal skin the design system bans, and breaks keyboard/SR pagination. *Fix:* drop `font-mono`, render the range in sentence-case ("Showing 1–10 of 248") with normal UI font; remove the glow shadow (use border + `bg-primary text-primary-foreground` for the active page); add `aria-label={`Page ${page}`}`, `aria-current={currentPage===page?'page':undefined}`, and `focus-visible:ring-2 focus-visible:ring-ring`; replace `title` with `aria-label` on the chevron buttons. *Command:* `/impeccable harden app/components/Pagination.tsx`
- **[P1] Destructive actions use native confirm()/alert().** *What:* delete and bulk-delete gate on `window.confirm` and report failure via `window.alert`. *Why:* PRODUCT.md makes "human-in-the-loop confirmation for destructive actions, designed not bolted on" a core promise; native dialogs are unstyled, unbranded, and give no per-item failure detail on bulk. *Fix:* swap in an AlertDialog (shadcn) with the doc title in the body and a destructive confirm button; on failure show an in-app toast/inline error naming which docs failed, ideally with undo. *Command:* `/impeccable shape the delete + bulk-delete confirmation into a designed AlertDialog with undo`
- **[P1] Row selection is mouse-only and ambiguous.** *What:* the whole row is a `<div onClick={onSelect}>`, so clicking anywhere toggles selection (not open), it's not keyboard-focusable, and it duplicates the checkbox. *Why:* surprising interaction model + a hard keyboard/SR barrier to the primary action. *Fix:* make the row a real control for its intended action — either keep click = open (route to detail) and confine selection to the checkbox, or make the row a `role="row"` with a focusable checkbox and an explicit open affordance; ensure Enter/Space work and the target is reachable by Tab. *Command:* `/impeccable clarify the documents row interaction (select vs open, keyboard path)`
- **[P2] No page-size control rendered.** *What:* `onPageSizeChange`/`updatePageSize` are plumbed end-to-end but no `<select>`/control is shown; users are stuck at 10/page. *Why:* wasted capability and a real efficiency hit for the power-user persona. *Fix:* render a "Rows per page" Select (10/25/50/100) in the pagination bar wired to `onPageSizeChange`. *Command:* `/impeccable add a rows-per-page selector to Pagination`
- **[P3] "Select all" scope is unlabelled.** *What:* the header checkbox selects only the current page's rows; with pagination there's no indication of page-vs-corpus scope. *Why:* a user can bulk-delete believing they've selected everything. *Fix:* label it "Select all on this page" and, when a filter/total exceeds the page, offer "Select all N matching" affordance. *Command:* `/impeccable clarify select-all scope on the documents list`

### Minor observations
- `formatDate` uses `toLocaleDateString` with time options — fine, but no relative time ("2h ago") which researchers scanning recent ingests would appreciate.
- The 4-up stat grid mixes a page-level total (`pagination.total`) with *visible-page-only* counts (indexed/processing/failed are computed from `rawDocuments`, i.e. the current 10 rows). That's a subtle truthfulness bug: "Indexed: 3" can mean "3 on this page," not "3 total." Either label them "on this page" or fetch true aggregates. (Borderline P2 — it's a provenance/honesty issue, which this product cares about.)
- `hover:border-[var(--nous-helios)]` on rows uses the bright gold hover token — consistent with the accent, fine.
- Empty-state copy is excellent; consider the same care for a *filtered*-empty state ("No documents match 'foo'") vs the truly-empty state — currently both render the generic "No documents yet."

### Questions
1. Are the stat-card counts meant to be page-scoped or corpus-scoped? If corpus-scoped, the current `rawDocuments.filter(...)` is wrong (see minor obs). This determines whether it's a P2.
2. Is row-click-to-select intentional, or a holdover? Most file managers open on click — confirming intent decides whether the fix is "open on click" or "selection only via checkbox."
3. Is `Pagination` (`app/components/Pagination.tsx`) shared across other dashboard pages? If so, hardening it fixes the terminal-costume regression everywhere at once and raises the priority of the P1.
