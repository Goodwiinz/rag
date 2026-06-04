---
target: projects)
total_score: 27
p0_count: 1
p1_count: 2
timestamp: 2026-06-03T21-53-37Z
slug: age-tsx-re-exports-app-dashboard-projects-page-tsx
---
## /impeccable critique — Research / Projects (product register)

**Page:** `/home/clawdbot/clawd/rag/frontend/app/(dashboard)/research/page.tsx`
This file is a one-line re-export of `/home/clawdbot/clawd/rag/frontend/app/(dashboard)/projects/page.tsx`, so the critique scores the projects list experience and its key children: `ProjectList.tsx`, `ProjectCard.tsx`, and `CreateProjectModal.tsx` (all under `src/components/research/`).

### Overall impression
The list page itself is genuinely good product work: honest skeleton/loading/empty/error states, abort-controlled fetches that prevent race conditions, debounced search, `aria-pressed` tag filters, labelled selects, sentence-case copy, semantic tokens, and `tabular-nums` on counts. It reads like the calm research instrument PRODUCT.md describes. Then you click "New project" and fall through a trapdoor into a different design system: `CreateProjectModal` is a terminal-costume relic with `font-mono` on every label and field, hardcoded near-black hex (`#0a0a0a`, `#1a1a1a`, `#333`), `text-sol`/`border-sol` (which map to the legacy `--phosphor-green` alias DESIGN.md says was deliberately removed), uppercase-mono labels, and Title Case shouting ("Create Research Project"). The modal is the single most damaging thing on the page because it appears on the primary CTA and on the empty state — the first thing a new user does. A compatibility shim remaps `--phosphor-green` to gold so the *color* doesn't render green, but the costume in code (mono everywhere, hex, banned aliases, uppercase-mono labels) is exactly the AI-slop / terminal pattern the brief bans.

### Heuristic scores (Nielsen 10)

| # | Heuristic | Score | Notes |
|---|-----------|------:|-------|
| 1 | Visibility of system status | 3 | Strong: skeletons, loading flag, `role="status"`, "Showing X of Y", submit spinner. Minus: no live-region announcement for filter result counts; search has no "searching" affordance beyond the debounce. |
| 2 | Match between system & real world | 3 | Clear domain language (literature review, thesis, citations). Modal regresses with `font-mono` field text that reads "technical" not scholarly, against the brand voice. |
| 3 | User control & freedom | 2 | Modal cannot be dismissed with Escape and has no backdrop-click close; no focus trap. Delete relies on native `window.confirm`. No undo on archive/delete. |
| 4 | Consistency & standards | 2 | The list page and the modal are two different design systems (tokens vs raw hex, sentence-case vs Title Case, rounded-xl vs rounded, focus-rings vs `focus:border-sol`). Card uses `rounded-lg`, skeleton uses `rounded-xl` — even within the page radii drift. |
| 5 | Error prevention | 3 | Good: abort controller, submit disabled until name present, duplicate-tag guard, modal keeps form open on failure. Minus: destructive delete only guarded by native confirm. |
| 6 | Recognition over recall | 3 | Filters, tags, status pills, view-mode toggle all visible and labelled. Solid. |
| 7 | Flexibility & efficiency | 3 | Debounced search, grid/list toggle, tag chips, Enter-to-add-tag. Power users (Alex) get density but no keyboard shortcut to open create, no bulk actions, no persisted view mode. |
| 8 | Aesthetic & minimalist design | 2 | List page is clean and restrained. The modal drags this down hard: mono everywhere is visual noise, and the hex-black panel does not match the themed card surfaces (breaks in light mode entirely). |
| 9 | Help users recognise/recover from errors | 3 | `role="alert"` on page error + dismiss; modal surfaces `submitError` with `role="alert"`; toast on archive/delete failure. Minus: modal error is `text-red-400` hardcoded, not `--nous-mars`/`destructive`. |
| 10 | Help & documentation | 3 | Empty states are instructive ("Create your first project to start gathering documents, citations, and notes"). No inline help for project types or what a "literature review" project does, but acceptable for an expert audience. |

**Total: 27 / 40 — Acceptable.** (List page alone would land ~31 Good; the modal pulls the whole surface down.)

### Anti-patterns verdict
- **Terminal costume — PRESENT (P0).** `CreateProjectModal` uses `font-mono` on every label, input, button, select, and error; `text-sol`/`border-sol` resolve to the legacy `--phosphor-green` alias (Tailwind config line 49: `sol: 'var(--phosphor-green)'`). DESIGN.md: "do not reintroduce it (`--terminal-*`, `--phosphor-green`...)". Mono-as-decoration is on the banned list.
- **Hardcoded hex / text-gray — PRESENT (P0).** Modal hardcodes `bg-[#0a0a0a]`, `border-[#1a1a1a]`, `border-[#333]`, `bg-[#1a1a1a]`, and `placeholder-gray-600`, `text-red-400`/`text-red-300`. DESIGN.md: "Never hardcode hex in components or `text-gray-*`."
- **Uppercase-mono labels used as decoration — PRESENT.** Every modal field label is `font-mono uppercase tracking-wide`. Banned.
- **Em dashes — NOT FOUND in copy.** Good (e.g., "e.g., ML Healthcare" uses commas).
- **Gradient text — NOT FOUND** in these components (note: `globals.css:290` has a gradient utility, but it is not applied here).
- **Glassmorphism / side-stripe borders / hero-metric template — NOT FOUND.** Good.
- **Identical card grids — BORDERLINE.** Cards are a single uniform grid of identical tiles, but they carry real differentiating data (status, docs, deadline, tags), so this reads as appropriate density rather than slop.

### Detector note (false negatives)
`node detect.mjs --json` returned `[]` for all three files, including the modal. This is a **false negative**: the modal demonstrably contains hardcoded hex, `font-mono` everywhere, `placeholder-gray-600`, and bare `focus:outline-none`. The detector's regex set did not match Tailwind arbitrary-value hex (`bg-[#0a0a0a]`) or `font-mono` density here, so I scored from manual reading. Treat the empty detector output as not exonerating — the violations are real.

### Cognitive load (8-item check)
1. Visual hierarchy clear? — List page yes; modal flattens everything to mono. 2. Reading order obvious? — Yes. 3. Color used meaningfully? — Yes on cards (status pill + Sol active only). 4. Whitespace deliberate? — List page yes; modal is uniform `p-6`/`space-y-4`. 5. Grouping logical? — Yes (search/filters/tags/results). 6. Motion purposeful? — Yes (hover-only opacity reveal of card menu, `transition-colors`). 7. Count of competing elements? — Low; good. 8. Memory burden? — Low. **Verdict: low load on the list, spiked load in the modal due to typographic noise.**

### AI-slop verdict: YES (would someone say "AI made this"?)
Not for the list page — that's crafted. But the modal trips the slop alarm: mono-everywhere, hardcoded dark hex that ignores theming, uppercase tracked labels, and Title-Case headings. Anyone reviewing the modal in isolation would say "an AI generated a generic dark dashboard form." The contrast with the polished list is itself a tell that two different generations were stitched together.

### Persona red flags (dashboards/data → Alex power-user + Sam a11y)
- **Sam (screen reader / keyboard):** The modal has no `role="dialog"`, no `aria-modal="true"`, no focus trap, no Escape handler, and focus is not returned to the trigger on close. A keyboard user can tab out of the modal into the page behind it; a screen-reader user is not told a dialog opened. Inputs lack associated `id`/`htmlFor` (labels wrap nothing). This is a hard WCAG 2.1 AA failure on the primary action.
- **Sam (contrast):** Modal field text is `text-muted-foreground` on `#1a1a1a` — muted-on-near-black for *input values the user is typing* is below comfortable contrast, and `placeholder-gray-600` is almost certainly sub-AA. Delete confirmation via native `confirm()` is unstyled and inconsistently announced.
- **Alex (power user):** No keyboard shortcut to open create, no persisted grid/list preference, no bulk select/archive, and delete drops to a jarring browser `confirm()` dialog — slow for someone managing many projects.

### What's working (strengths)
1. **Honest async states, done right.** Real skeleton with `role="status"` + `sr-only` label, distinct empty states for "no projects yet" vs "no matches", abort-controlled fetch that cancels stale responses — this is exactly the "honest states" principle from PRODUCT.md.
2. **Restrained, correct color discipline on the list.** Single Sol accent for active status and primary CTA; status meaning carried by label not color alone (comment in `ProjectCard` even calls this out); semantic tokens throughout; `tabular-nums` on counts.
3. **Accessible filtering.** Labelled search/selects, `aria-pressed` tag chips and view-mode toggle wrapped in a labelled `role="group"`, proper `aria-hidden` on decorative icons.

### Priority issues
- **[P0] Rebuild CreateProjectModal in the product design system.** *What:* mono-everywhere + hardcoded `#0a0a0a/#1a1a1a/#333` hex + `text-sol`/`border-sol` (legacy `--phosphor-green` alias) + uppercase-mono labels + Title Case. *Why:* reintroduces the explicitly-banned terminal costume on the page's primary action and breaks theming (the hex panel will not flip in light mode). *Fix:* replace with shadcn `Dialog` + `Input`/`Textarea`/`Select`/`Label`; swap all `font-mono` for default UI font, all hex for `bg-card`/`border-border`/`text-foreground`, `text-sol`→`text-primary`, `text-red-400`→`text-destructive`/`--nous-mars`, sentence-case the heading to "New research project". *Command:* `/impeccable harden CreateProjectModal — port to shadcn Dialog, strip mono + hex + phosphor aliases, product tokens only`.
- **[P1] Make the modal accessible and dismissible.** *What:* no focus trap, no Escape, no backdrop close, no `role="dialog"`/`aria-modal`, no focus return, labels not associated to inputs. *Why:* WCAG 2.1 AA failure and a user-control failure on the most-used action. *Fix:* adopting the shadcn `Dialog` gives focus trap + Escape + roles for free; add `id`/`htmlFor` pairs; restore focus to the trigger on close. *Command:* `/impeccable harden CreateProjectModal a11y — dialog semantics, focus trap, escape, label associations`.
- **[P1] Unify visual language between list and modal.** *What:* radii (`rounded`/`rounded-xl`/`rounded-lg` drift), casing (Title vs sentence), typography (mono vs UI), tokens vs hex differ across the launch surface. *Why:* consistency is the cheapest trust signal; the fracture is most visible exactly where the user commits an action. *Fix:* settle on `--nous-radius-lg` (12px) for cards/modal, sentence-case everywhere, one type family for UI. *Command:* `/impeccable clarify research/projects — reconcile radii, casing, and type between list and create modal`.
- **[P2] Replace native `window.confirm` for delete with an in-app confirm.** *What:* `if (!confirm('Are you sure...'))`. *Why:* unstyled browser chrome, inconsistent screen-reader announcement, no themed destructive treatment. *Fix:* use shadcn `AlertDialog` with a destructive button and `role="alertdialog"`. *Command:* `/impeccable harden project delete — themed AlertDialog confirm`.
- **[P3] Small efficiency wins for the expert audience.** *What:* persist grid/list preference, add a keyboard shortcut to open create, consider showing retrieval/provenance affordances on cards (docs count exists; trust signals could go further per PRODUCT.md). *Command:* `/impeccable optimize projects list — persist view mode, add create shortcut`.

### Minor observations
- `ProjectsLoadingSkeleton` uses `rounded-xl` while real `ProjectCard` uses `rounded-lg` — the skeleton should match the rendered card to avoid a layout "snap" on load.
- Page renders the skeleton both pre-mount and during loading, which is good, but the pre-mount branch also stuffs a hidden `Loader2` in `sr-only` that adds nothing — dead markup.
- `createdLabel` is derived from `updated_at` but labelled "Updated" — correct, though the variable name is misleading for future maintainers.
- Empty-state and CTA buttons duplicate identical long className strings; extract a `Button` to keep focus/hover states from drifting.

### Questions
1. Is `CreateProjectModal` shared with other surfaces, or safe to replace wholesale with a shadcn `Dialog`? It looks like an older generation than the rest of `research/`.
2. The Tailwind config still maps `sol → --phosphor-green` and exposes `terminal-*` surfaces. Is the legacy-alias layer scheduled for removal, or is it a permanent compat shim? New components should not consume `text-sol`/`border-sol` if the alias is going away.
3. Should the `research` route diverge from `projects` at all (different default filters, arXiv-ingestion entry point), or is the re-export the intended permanent behavior?
