---
target: projects
total_score: 26
p0_count: 1
p1_count: 3
timestamp: 2026-06-03T21-53-37Z
slug: frontend-app-dashboard-projects-page-tsx
---
## /impeccable critique — Projects list (`app/(dashboard)/projects/page.tsx`)

Register: **product** · Observatory identity (warm gold on warm-dark, scholarly not terminal)

### Overall impression

This is a tale of two files. The **page shell** (`page.tsx`), `ProjectList.tsx`, and `ProjectCard.tsx` are genuinely good product work: semantic tokens throughout (`text-foreground`, `bg-card`, `border-border`, `text-primary`), honest loading / empty / filtered-empty / error states, debounced search, AbortController race-cancellation, `tabular-nums` on counts, `aria-pressed` on toggles, `role="status"`/`role="alert"`, sentence-case plain copy. If the page were graded alone it would land solidly in Good.

But the page composes `CreateProjectModal.tsx`, and that component is a regression to the exact cyberpunk "costume" DESIGN.md says was deliberately removed and must never return. It hardcodes `#0a0a0a`/`#1a1a1a`/`#333`, uses `font-mono` on 15 lines, `placeholder-gray-600`, `text-red-400`/`text-red-300`, five `uppercase tracking-wide` mono labels, bare `focus:outline-none`, and — worst of all — its `text-sol`/`bg-sol`/`border-sol` accent resolves through `tailwind.config.ts:49` to `var(--phosphor-green)`. The modal's "gold" accent literally renders the banned terminal green. Because the modal is the primary creation path on this page, the whole surface inherits the problem and the score is capped at Acceptable.

### Heuristic scores (Nielsen 10)

| # | Heuristic | Score | Notes |
|---|-----------|:---:|-------|
| 1 | Visibility of system status | 3 | Skeleton on mount + fetch, `role="status"`, count footer, toasts. Modal submit shows a spinner. No visible per-row pending state during archive/delete (relies on toast only). |
| 2 | Match between system & real world | 3 | Plain sentence-case copy, researcher vocabulary (literature review, thesis). Card "Updated {date}" uses `updated_at` but the var is named `createdLabel` (code smell, not user-facing). |
| 3 | User control & freedom | 2 | Filters clearable; modal Cancel resets. But native `confirm()` for delete, no undo on delete/archive, and the modal cannot be dismissed with Escape or a backdrop click (no handlers). |
| 4 | Consistency & standards | 1 | Severe internal inconsistency: page/cards use semantic tokens + `focus-visible` rings; the modal uses hardcoded hex, `font-mono`, gray-* utilities, and bare `focus:outline-none`. Two visual languages in one flow. |
| 5 | Error prevention | 3 | Required-name gating disables submit; duplicate-tag guard; debounce prevents thrash. No confirm step is *designed* (native dialog only). |
| 6 | Recognition over recall | 3 | Filters, tag chips, status badges, view-mode toggle all visible. Truncated card titles have no `title`/tooltip, so long names are unrecoverable without opening. |
| 7 | Flexibility & efficiency | 3 | Grid/list toggle, tag quick-filters, Enter-to-add-tag, keyboard-debounced search. No bulk actions, no keyboard shortcut to create, view mode not persisted. |
| 8 | Aesthetic & minimalist design | 2 | Page is calm and well-spaced. Modal breaks it: mono everywhere reads as "technical costume," phosphor-green accent clashes with the warm-gold identity, cards-on-dark-hex looks unfinished. |
| 9 | Help users recover from errors | 3 | `role="alert"` banner with Dismiss; toasts via `getApiErrorMessage`; modal keeps form open and surfaces inline error on failure. Good recovery model. |
| 10 | Help & documentation | 3 | Empty state explains what a project is and offers the create CTA; filtered-empty is distinct. No inline help for project *types*. |

**Total: 26 / 40 — Acceptable.**

### Anti-pattern / AI-slop verdict: **FAIL (modal)**

Would someone say "AI made this"? For the page, no — it's disciplined. For the modal, yes. Banned-list hits, all in `CreateProjectModal.tsx`:

- **Terminal costume — confirmed, two ways.** `font-mono` on 15 lines (mono-as-decoration), five `uppercase tracking-wide` mono labels, and `text-sol`/`bg-sol`/`border-sol` which resolve to **`var(--phosphor-green)`** via `tailwind.config.ts:49`. The accent is not gold — it is the explicitly-removed phosphor green. This is the single most important issue.
- **Hardcoded hex.** `#0a0a0a`, `#1a1a1a` (×6), `#333` (×6) instead of `bg-card`/`bg-muted`/`border-border`.
- **`text-gray-*` / color utilities.** `placeholder-gray-600` (×3), `text-red-400`, `text-red-300`, `border-red-400` instead of `--nous-mars`/`text-destructive`.
- **Bare `focus:outline-none`.** Five inputs/selects strip focus with no `focus-visible` replacement (DESIGN.md: "Never bare `focus:outline-none`").

Not found (good): no gradient text, no glassmorphism, no side-stripe borders, no hero-metric template, no em dashes. The card grid is acceptably non-identical (status, docs, deadline, tags vary per card). The page itself triggers **zero** banned patterns.

**Detector note:** `detect.mjs --json` returned `[]` for every file, and also returned `[]` for a synthetic known-bad HTML control with gradient text + hardcoded hex. The detector is non-functional in this environment (silent empty output, exit 0), so its "clean" result is a **false negative, not a pass**. All findings above are from manual grep evidence (hex/mono/gray/focus counts cited inline) and reading the Tailwind config.

### Cognitive load (8-item check)

1. Visual hierarchy — page: clear (title, filters, grid). Modal: flat, all-mono labels compete. **mixed**
2. Color discipline — page: one Sol accent. Modal: phosphor-green + raw reds. **fail (modal)**
3. Typographic restraint — page: Inter/semantic. Modal: mono everywhere. **fail (modal)**
4. Spacing rhythm — good on both. **pass**
5. Decision density per view — filters + grid is digestible. **pass**
6. State legibility — honest loading/empty/error. **pass**
7. Motion restraint — only `transition-colors`/opacity; no layout animation. **pass**
8. Provenance/honesty — counts and "Updated" dates shown; no fake metrics. **pass**

### Persona red flags

**Alex (power user / dense-data researcher):**
- No bulk select / bulk archive-delete — managing 40+ projects is one-at-a-time with a native confirm on each.
- View mode and active filters aren't persisted across navigation; returns to grid + cleared filters every visit.
- No keyboard affordance to open the create modal (no shortcut, no `/`), and inside the modal Escape doesn't close it.

**Sam (accessibility):**
- **Modal is not a dialog.** No `role="dialog"`, no `aria-modal`, no labelled-by, no focus trap, no Escape/backdrop dismissal, no focus return to the trigger on close. Screen-reader and keyboard users can tab out of the modal into the page behind it. WCAG 2.1 AA dialog failure.
- **Bare `focus:outline-none`** on all five modal fields removes the visible focus ring with no replacement.
- **Phosphor-green on near-black hex** (`text-sol` on `#0a0a0a`) is an unverified contrast pair introduced outside the token system that flips with theme — small mono text at AA risk.
- Native `confirm()` for delete is announced inconsistently and isn't styleable/scannable for low-vision users.

### Priority issues

**P0 — Modal reintroduces the banned terminal costume + phosphor-green accent.** *What:* `CreateProjectModal.tsx` uses hardcoded hex, `font-mono` ×15, gray/red utilities, mono-uppercase labels, and `text-sol`/`bg-sol` which resolve to `var(--phosphor-green)` (`tailwind.config.ts:49`). *Why:* directly violates DESIGN.md's strongest prohibition (the removed terminal skin) and PRODUCT.md anti-references; the accent is literally the wrong, forbidden hue. *Fix:* rebuild the modal on `Dialog` from `src/components/ui/**` (Radix) — `bg-card`/`bg-background`, `border-border`, `text-foreground`/`text-muted-foreground`, Inter labels (sentence-case, not uppercase mono), Sol via `text-primary`/`bg-primary`; replace reds with `text-destructive`/`--nous-mars`. Separately, fix the config: `sol` must not point at `--phosphor-green`. *Command:* `/impeccable harden CreateProjectModal.tsx` then `/impeccable colorize` to re-anchor the accent.

**P1 — Modal lacks dialog accessibility.** *What:* no `role="dialog"`, `aria-modal`, focus trap, Escape/backdrop close, or focus restore. *Why:* WCAG 2.1 AA (PRODUCT.md target); keyboard/SR users get trapped or escape behind the overlay. *Fix:* adopt Radix `Dialog` (handles trap, Escape, `aria-modal`, focus return for free). *Command:* `/impeccable harden CreateProjectModal.tsx`.

**P1 — Bare `focus:outline-none` on modal fields.** *What:* five inputs/selects remove the focus ring with only `focus:border-sol`. *Why:* keyboard focus invisibility (2.4.7); border-color alone is not a reliable indicator. *Fix:* `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring` (the pattern already used on the page). *Command:* `/impeccable harden`.

**P1 — Destructive delete uses native `confirm()` with no undo.** *What:* `page.tsx:173` blocks on `window.confirm`; archive has no confirmation or undo at all. *Why:* breaks user-control/error-recovery; unstyled, unbranded, easy to mis-click with no reversal. *Fix:* designed confirmation (Radix `AlertDialog`) for delete; add an undo toast for archive/delete. *Command:* `/impeccable clarify` (confirmation flow) + `/impeccable harden`.

**P2 — Truncated card titles have no recovery.** *What:* `ProjectCard` `truncate`s the name with no `title` attr or tooltip. *Why:* long/similar project names become indistinguishable without opening each. *Fix:* add `title={project.name}` (and/or a tooltip on hover/focus). *Command:* `/impeccable clarify`.

**P3 — View mode and filters not persisted; no bulk actions.** *What:* `viewMode`/filters reset on navigation; no multi-select. *Why:* power-user friction at scale. *Fix:* persist via URL params or store; add bulk archive/delete. *Command:* `/impeccable optimize`.

### What's working (strengths)

- **Honest, fully-designed states.** Distinct skeleton, empty, filtered-empty, and `role="alert"` error states with a Dismiss action — exactly the "honest states" principle. The filtered-vs-truly-empty split is a thoughtful touch.
- **Token discipline + accessibility on the page and cards.** Semantic tokens throughout, `focus-visible:ring-ring`, `aria-pressed`, `aria-label`, `aria-hidden` on decorative icons, `tabular-nums`, Radix `DropdownMenu` for card actions. This is correct product-register work.
- **Robust data layer.** Debounced search, `AbortController` to cancel stale fetches, centralized `getApiErrorMessage`, optimistic toasts with rollback-friendly error handling. The non-visual quality is high.

### Minor observations

- `ProjectCard` names the date var `createdLabel` but populates it from `project.updated_at` and renders "Updated" — confusing internally; rename to `updatedLabel`.
- The mount-gate renders a hidden `<Loader2 className="hidden" />` inside an `sr-only` span (lines 209-211) — dead/no-op markup, remove it.
- `Network` icon next to the workspace name is an odd metaphor for a workspace; consider a folder/building glyph.
- Date formatting uses raw `toLocaleDateString()` with no relative-time option ("3 days ago"), which researchers often prefer for recency scanning.

### Questions

1. Is `tailwind.config.ts:49` (`sol: 'var(--phosphor-green)'`) intentional, or leftover from the removed terminal theme? Every `*-sol` utility in the codebase is currently rendering green, not gold — this likely affects more than this modal.
2. Was `CreateProjectModal` skipped in the migration that tokenized the rest of `research/**`? It is the only file in this flow still on the old skin.
3. Should archive be reversible via an undo toast rather than only through the per-card Restore action later?
