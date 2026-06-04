---
target: [id]
total_score: 28
p0_count: 0
p1_count: 3
timestamp: 2026-06-03T21-53-37Z
slug: frontend-app-dashboard-projects-id-page-tsx
---
## /impeccable critique — Project Detail page (`projects/[id]/page.tsx`)

**Register:** product · **Verdict band:** Good (28/40) · **AI-slop:** Yes (in two child components, not the page shell)

### Overall impression
The page *orchestrator* is genuinely strong: it is a 1,144-line tab controller that stays disciplined — semantic tokens (`bg-card`, `text-muted-foreground`, `border-border`, `bg-primary/10`) throughout, no hardcoded hex, honest loading/empty/error states that distinguish 404 from 500, `role="status"`/`role="alert"`, `aria-current` on tabs, `focus-visible:ring` on every interactive element, `tabular-nums` on version numbers and timestamps. This is what NOUS "product" should look like.

The problem is that the page is only as good as the tabs it renders, and two of the core ones — `NoteList` and `DraftGenerator` — are running an older, off-brand skin: the terminal/mono "costume" DESIGN.md explicitly says was removed and must not return. So a researcher lands on a clean, scholarly header and tab bar, clicks Notes or Drafts, and the surface visibly changes character. That inconsistency is the headline issue, and it is why the AI-slop verdict is Yes despite a clean shell.

### Heuristic scores (Nielsen 10)

| # | Heuristic | Score | Notes |
|---|-----------|-------|-------|
| 1 | Visibility of system status | 4 | Skeleton loaders per tab, spinning refresh icon, draft generation progress with poll, "Comparing…" busy label, count badges on tabs. Exemplary. |
| 2 | Match real world | 3 | Plain sentence-case in page ("No draft yet", "Could not load this project"). But `DraftGenerator` shouts "Generate Literature Review" in mono bold + `THEMES / TOPICS *` uppercase — louder than the calm voice PRODUCT.md asks for. |
| 3 | User control & freedom | 3 | Back-to-projects, refresh, cancel generation, version switching, dismiss error. Destructive note delete uses raw `confirm()` (no undo) and bulk remove same; acceptable but not designed. |
| 4 | Consistency & standards | 2 | The big miss. Page + DocumentList use shadcn/semantic tokens; NoteList + DraftGenerator use hardcoded hex, `font-mono` everywhere, `border-sol`/`text-helios`, and `text-red-400`. Two visual languages in one screen. |
| 5 | Error prevention | 3 | Compare button disabled when versions equal/null; upload re-fetches on partial failure; export disabled when no bibliography. Solid. |
| 6 | Recognition vs recall | 3 | Icon+label tabs, version list with "Current" badge, format dropdown labelled. Mobile truncates labels to 4 chars (`label.slice(0,4)`) — "Bibl", "Pipe", "Know" — recall-heavy on small screens. |
| 7 | Flexibility & efficiency | 3 | 8 tabs, sort/search/bulk-select in DocumentList, keyboard arrow nav in DraftGenerator style radios. No tab keyboard shortcuts; no deep-link of active tab to URL (tab state is lost on refresh/share). |
| 8 | Aesthetic & minimalist | 2 | NoteList/DraftGenerator mono + uppercase labels are decorative noise, not information. Repeated `uppercase tracking-wide` labels are the "AI scaffolding" DESIGN.md names. |
| 9 | Error recovery | 3 | Project load has Try-again + Back; errors are role="alert" + dismissible. But draft/compare/note failures only `console.error` — the user sees nothing when generate or compare silently fails. |
| 10 | Help & docs | 2 | Empty states give next-step hints ("Choose your themes on the left…", "Add documents with extracted citations…"). No inline help for citation formats, draft styles, or what "Matrix"/"Knowledge" tabs do. |

**Total: 28/40 — Good** (held down from low-30s by Consistency=2 and Aesthetic=2; the page shell alone would score ~33).

### Anti-patterns verdict (NOUS banned list)
- **Terminal/mono costume — PRESENT.** `NoteList.tsx` 6× `font-mono` (incl. note title `<h3>` and "No notes yet" empty state); `DraftGenerator.tsx` 13× `font-mono` (heading, every label, theme chips, slider ticks, generate button). DESIGN.md: "Do not use mono as decorative 'technical' shorthand." Mono-everywhere is on the banned list.
- **Hardcoded hex / non-semantic color — PRESENT.** `NoteList.tsx`: `bg-[#0a0a0a]`, `border-[#1a1a1a]`, `border-[#333]`, plus `text-red-400`, `border-helios/50`, `text-helios`, `focus:border-sol`. `DraftGenerator.tsx` + `DocumentList.tsx`: `text-red-400`. DESIGN.md: "Never hardcode hex … or `text-gray-*`. Use semantic tokens." `text-red-400` should be `text-destructive`.
- **Repeated uppercase tracked labels — PRESENT.** `DraftGenerator` stacks `uppercase tracking-wide` on Themes, Writing Style, Max Sections, Include Abstract — DESIGN.md: "One uppercase tracked kicker per section max (repeating it is AI scaffolding)."
- **Em dashes — clean.** Code uses `—` only as a real empty-value glyph in DocumentList (data placeholder, defensible), none in prose.
- **Gradient text / glassmorphism / side-stripe borders / hero-metric / identical card grids — none.** Page shell is clean on all of these.

### Detector note
`detect.mjs --json` returned `[]` for all five files — a **false negative**. It flagged none of the hardcoded hex, `font-mono`, or `focus:outline-none` violations that a manual grep surfaces immediately (NoteList lines 42/62/78/79/129; DraftGenerator lines 92–246). Treat the automated pass as non-evidence here; the grep is load-bearing.

### Persona red flags
- **Alex (power user / researcher in deep-focus):** Active tab is not in the URL. Alex opens a project, lands on Documents, navigates to Drafts, refreshes (or shares the link) and is bounced back to Documents — state loss on a screen built for long sessions. Also: 8 tabs with no keyboard switching (`g d`, `[`/`]`, or `1–8`) means everything is mouse-reach.
- **Sam (accessibility):** `focus:outline-none` with **no** replacement ring on NoteList tag `<select>` (line 62, `focus:border-sol` is a 1px border-color change, not an AA-visible focus indicator) and DraftGenerator theme input (line 114, `focus:border-primary` same problem). Keyboard-only users can lose focus location. Note action buttons (pin/edit/delete) use `title` tooltips but no `focus-visible` ring at all. This is a WCAG 2.1 AA 2.4.7 failure on a product surface that claims AA.
- **Sam (color):** `text-red-400` for the PDF icon and destructive hovers is a raw Tailwind hue, not the Mars/`destructive` token — meaning it won't flip correctly with theme and isn't guaranteed AA on warm-dark.

### Priority issues

**P1 — NoteList.tsx is wearing the banned terminal costume**
*What:* Hardcoded hex (`#0a0a0a`, `#1a1a1a`, `#333`), `font-mono` on note titles/tags/dates/empty-state, `border-sol`/`text-helios`/`focus:border-sol`.
*Why:* Directly violates four DESIGN.md rules (no hex, no mono-everywhere, no `focus:outline-none`, use semantic tokens) and breaks visual consistency with the clean page shell — the single biggest reason this screen reads as AI-made.
*Fix:* Replace hex with `bg-card`/`border-border`/`border-primary/50`; drop every `font-mono` (titles → default Inter UI, dates → `tabular-nums` not mono); `text-red-400` → `text-destructive`; add `focus-visible:ring-2 focus-visible:ring-ring` to the select and the three icon buttons (or swap to `IconButton` like DocumentList already does).
*Command:* `/impeccable harden src/components/research/NoteList.tsx` (tokens + a11y pass).

**P1 — DraftGenerator.tsx is mono-everywhere with repeated uppercase labels**
*What:* 13 `font-mono` uses + stacked `uppercase tracking-wide` field labels + mono bold heading.
*Why:* "Mono-everywhere" and "repeated uppercase tracked labels" are both explicitly banned; the form shouts in a product surface PRODUCT.md says should be calm and plain.
*Fix:* Remove `font-mono` throughout (Inter for all UI/labels); demote labels to normal sentence-case `text-sm text-foreground` (keep at most one overline if a kicker is truly needed); `text-red-400` → `text-destructive`; add `focus-visible:ring` to the theme input and Add/Generate buttons.
*Command:* `/impeccable colorize+harden src/components/research/DraftGenerator.tsx`.

**P1 — Silent failures on generate / compare / note actions**
*What:* `handleCompareDrafts`, the draft `onGenerate` poll, `handleSaveNote`, `handleRemoveDocument`, and `downloadBibliography` all swallow errors into `console.error` with no UI feedback.
*Why:* PRODUCT.md "Honest states" principle — when a researcher clicks Generate or Compare and the backend fails, the button just re-enables and nothing happens. Erodes the "credible thinking instrument" trust the product is built on.
*Fix:* Surface these through the existing `error`/`role="alert"` banner (or a toast) the page already renders for project-level errors; the plumbing is right there.
*Command:* `/impeccable clarify projects/[id]/page.tsx --states=error`.

**P2 — Active tab is not reflected in the URL**
*What:* `activeTab` is local `useState`; refresh/share/back resets to Documents.
*Why:* Deep-focus researchers (Alex) lose context and can't link a colleague to "the Drafts tab of this project."
*Fix:* Sync `activeTab` to a `?tab=` search param (or route segment) via `useSearchParams`/`router.replace`.
*Command:* `/impeccable adapt projects/[id]/page.tsx --url-state=tab`.

**P3 — Mobile tab labels truncate to 4 chars**
*What:* `label.slice(0, 4)` on `<sm` renders "Bibl", "Pipe", "Know", "Matr".
*Why:* Recognition→recall regression; "Bibl" and "Know" are guessable but not obvious.
*Fix:* Keep icon-only on mobile with `aria-label`/tooltip, or use a horizontally scrollable full-label row (the container already has `overflow-x-auto`).
*Command:* `/impeccable adapt projects/[id]/page.tsx --responsive=tabs`.

### Cognitive load (8-item check)
1. Visual hierarchy — OK (header card → tab bar → content). 2. Grouping — OK (drafts: generator left, viewer right, compare below). 3. Color meaning — **mixed** (raw red-400 vs destructive token). 4. Typographic rhythm — **broken in 2 tabs** (mono). 5. Density — appropriate for researchers. 6. Decision points — reasonable (one primary action per tab). 7. Memory burden — **tab state lost on refresh**; truncated mobile labels. 8. Motion — calm (spin + pulse only, no bounce). Net: load is low on the shell, elevated on Notes/Drafts.

### What's working (strengths)
- **Honest, designed states.** Per-tab skeletons (not a global spinner), 404-vs-error differentiation with appropriate copy + retry, dismissible `role="alert"` banner, draft-generation progress with cancel. This is the PRODUCT.md "Honest states" principle done right.
- **The page shell is token-disciplined and accessible.** Zero hardcoded hex, semantic tokens throughout, `aria-current`/`aria-label`/`aria-busy`, `focus-visible:ring` on every control, `tabular-nums` on numeric data. DocumentList is a model child component (shadcn `IconButton`, `Checkbox`, `Select`, real bulk-action bar).
- **Provenance-aware drafting flow.** Version list with "Current" badge, side-by-side compare, export with bibliography format — matches "Provenance over assertion." Generated-at timestamps and citation counts are surfaced, not hidden.

### Minor observations
- Bibliography `<pre>` using `font-[var(--nous-font-mono)]` is *correct* (BibTeX/IEEE is literally code) — not a violation.
- The `—` in DocumentList is a data placeholder for empty status, not prose — fine, but consider a softer "Unknown" string.
- `DraftGenerator` re-renders the whole form on the right column even when only the generator changes; consider memoizing for large projects.
- Toggle switch and slider in DraftGenerator are hand-rolled; the codebase has shadcn primitives — prefer them for baseline a11y.

### Open questions
1. Were NoteList/DraftGenerator written before the terminal-costume removal and missed in the sweep? They look like pre-migration artifacts.
2. Should the 8 tabs be a candidate for collapsing/grouping (Matrix + Knowledge + Pipeline are "analysis" vs Documents/Notes/Bibliography "inputs")? 8 peer tabs is a lot.
3. Is there a product reason the active tab isn't URL-addressable, or is it just unimplemented?
