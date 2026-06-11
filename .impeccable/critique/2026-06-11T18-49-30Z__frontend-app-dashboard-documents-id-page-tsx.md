---
target: frontend/app/(dashboard)/documents/[id]/page.tsx
total_score: 26
p0_count: 2
p1_count: 2
timestamp: 2026-06-11T18-49-30Z
slug: frontend-app-dashboard-documents-id-page-tsx
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Skeletons + aria-live regions. Unbounded citation extraction spinner lacks progress. |
| 2 | Match System / Real World | 3 | Labels are natural. "Content integrity" is slightly abstract for first-time users. |
| 3 | User Control and Freedom | 3 | Back button, retry, delete confirmation. No cancel for running extractions. |
| 4 | Consistency and Standards | 2 | Hand-rolled tabs (raw buttons + roles) instead of shadcn Tabs/Radix. Will drift. |
| 5 | Error Prevention | 3 | Extract disabled when not indexed. Delete has confirmation. No double-extraction guard. |
| 6 | Recognition Rather Than Recall | 3 | Icons + labels on all tabs. Scannable definition list. Tab state persists. |
| 7 | Flexibility and Efficiency | 2 | No keyboard shortcuts, no document-to-document nav, no bulk export. Every action is a click. |
| 8 | Aesthetic and Minimalist Design | 3 | Clean, restrained palette. Dense: 7 sections in 2-column layout pushes tabs below fold. |
| 9 | Help Users Recognize & Recover from Errors | 3 | Error states with retry + back. Inline role="alert" for extraction errors. |
| 10 | Help and Documentation | 1 | Zero in-page help. No tooltips for "Content integrity." "Needs review" badge lacks guidance. |
| **Total** | | **26/40** | **Good** |

## Anti-Patterns Verdict

**Pass — not AI-generated.** No gradient text, no side-stripe borders, no hero-metric blocks, no icon-card grids, no font-mono on non-code. One violation: backdrop-blur-xl glassmorphism on sticky header (DESIGN.md explicit ban).

## Detector Scan

1 finding: `border-b-2` on tab wrapper (warning — accent border on rounded element, page.tsx:600). This is the hand-rolled tab pattern. Assessment A also flagged this as a P0 issue.

## What's Working

1. Loading skeleton fidelity — mirrors 2-column layout, pre-maps structure for the user.
2. Contextual empty states — every "nothing here" explains *why* (not indexed vs. indexed but not run).
3. Error recovery — four paths: retry fetch, back to list, retry processing, confirm-delete.

## Priority Issues

**[P0] Preview tab is a universal dead end.** Shows "Preview not available here" for every document. A document detail page that cannot display the document is architecturally incomplete. Fix: integrate PDF.js or similar viewer; if scoped out, hide the tab entirely.

**[P0] Hand-rolled tabs instead of shadcn Tabs.** Raw `<button>` elements with `role="tablist"`/`aria-selected` (page.tsx:580-611). The design system provides Tabs/TabsList/TabsTrigger/TabsContent wrapping Radix with keyboard nav and focus management. Fix: swap to `<Tabs>` from `@/components/ui/tabs`.

**[P1] Glassmorphism header.** `bg-card/80 backdrop-blur-xl` (page.tsx:237, 312) violates DESIGN.md. Fix: solid `bg-card` with `border-b`.

**[P1] Status card is inert for indexed documents.** Processing Status occupies the entire first fold of the left column. For indexed docs, it shows "completed" — info the user already has. Fix: collapse to compact badge when indexed, or early-return a small indicator.

**[P2] Overview summary in muted text.** `text-muted-foreground` on the document summary (DocumentOverviewTab.tsx:19). The document's own content should be `text-foreground`.
