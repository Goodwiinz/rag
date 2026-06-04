---
target: research-engine
total_score: 26
p0_count: 1
p1_count: 3
timestamp: 2026-06-03T21-53-37Z
slug: frontend-app-dashboard-research-engine-page-tsx
---
## /impeccable critique — Research engine (`app/(dashboard)/research-engine/page.tsx`)

**Register:** product · **Verdict band:** Acceptable (26/40) · **AI-slop:** yes (one component)

The page file itself is a four-line shell (`container mx-auto max-w-7xl p-6` → `<ResearchDashboard/>`). This critique covers the rendered surface: `ResearchDashboard`, `ProjectCard`, `CreateProjectModal`, and the shared `EmptyState`. The dashboard container is genuinely strong — honest states, semantic tokens, real focus rings. The modal drags the whole page down: it re-imports the exact terminal/phosphor vocabulary DESIGN.md says was deliberately removed.

### Heuristic scores (Nielsen 10)

| # | Heuristic | Score | Notes |
|---|-----------|:----:|-------|
| 1 | Visibility of system status | 3 | Skeleton grid (not a spinner) on load, `role="status"` + `aria-label`, spinner on modal submit. Good. Minor: no toast/confirmation after a project is created — the list silently refetches. |
| 2 | Match between system & real world | 3 | "Research engine", "New project", status pills (Active/Paused/Completed/Archived) read clearly. Dragged down by modal copy in Title Case ("New Research Project", "Create Project") against the product's sentence-case voice. |
| 3 | User control & freedom | 2 | Modal cannot be closed by Escape or backdrop click (X button only); error recovery on the dashboard is a full `window.location.reload()` — a sledgehammer that discards all client state. |
| 4 | Consistency & standards | 2 | Two different design languages on one page: dashboard uses Inter + semantic tokens + `focus-visible:ring`; modal + EmptyState use `font-mono`, uppercase tracking, raw `red-*` palette, bare `focus:outline-none`. |
| 5 | Error prevention | 3 | Submit disabled until `name.trim()`; non-critical template fetch fails silently by design. No client length/validation hints, but low-risk form. |
| 6 | Recognition over recall | 3 | Cards show name/status/date/description; template chips expose meaning only via `title=` tooltip (invisible on touch + keyboard). |
| 7 | Flexibility & efficiency | 2 | No keyboard path to open a project (cards are non-focusable divs), no keyboard submit in modal (Cmd/Ctrl+Enter), no search/filter/sort on the project grid — a power-user (Alex) gap on a list that will grow. |
| 8 | Aesthetic & minimalist | 3 | Dashboard is clean and restrained, good rhythm. Modal's mono+uppercase+tracking is decorative noise that fights the scholarly register. |
| 9 | Error recovery | 3 | Dashboard error → designed `EmptyState` with retry (`role="alert"`). Modal error renders inline but in a non-announced `div` (not `role="alert"`) styled with raw red. |
| 10 | Help & documentation | 2 | Subhead ("reproducible research workflows with blueprint-driven pipelines") is the only orientation; no inline help on what a blueprint/template is, no empty-state link to docs. |
| | **Total** | **26/40** | **Acceptable** — typical of real UI; the modal is the single biggest drag. |

### Detector evidence

`node detect.mjs --json` on the page + `ResearchDashboard` + `ProjectCard` + `CreateProjectModal` + `EmptyState` returned `[]` (no findings). This is a **true pass on the detector's narrow ruleset** (side-stripe borders, `bg-clip-text` gradient text, gray-on-color, purple/violet AI palette, bounce easing, layout transitions, broken images, page-level buzzword/em-dash/single-font analyzers) — none of which this code trips.

But the clean exit is a **detector blind spot, not clean code**. The detector has no rule for: `font-mono` overuse, raw status palette (`bg-red-500/10`, `text-red-400`) used outside the semantic system, bare `focus:outline-none`, decorative uppercase tracking, or missing dialog roles. All of these are present in `CreateProjectModal.tsx` (lines 60, 73, 80, 88, 94, 102, 110, 117) and `EmptyState.tsx` (lines 53, 61, 77, 87) and are real NOUS violations the detector simply does not scan for. Fold them in as evidence manually.

One thing the detector cannot see that matters: `text-sol`/`bg-sol/30` in the modal map (per `tailwind.config.ts:49`) to `var(--phosphor-green)`, a **legacy terminal alias**. I verified it is remapped to `#d4a039` (warm gold) in `globals.css:486` for both themes, so the rendered color is correct gold, not green. The bug is naming tech-debt — live `sol → phosphor-green` plumbing keeps the removed costume one find-and-replace away from resurrection (P2).

### Anti-patterns verdict

- **Terminal costume (mono-everywhere):** PRESENT. `CreateProjectModal` uses `font-mono` on the heading, error box, both labels, both inputs, Cancel, and Create button. `EmptyState` uses `font-mono ... tracking-wider` on title and description. DESIGN.md: "Do not use mono as decorative 'technical' shorthand." This is the headline violation.
- **Raw hex / non-semantic palette:** PRESENT (mild). `bg-red-500/10 border-red-500/30 text-red-400` instead of the semantic destructive token. DESIGN.md status color is Mars `#ef4444` via token, not raw Tailwind `red-*`.
- **Side-stripe borders / gradient text / glassmorphism / hero-metric / identical card grid:** ABSENT. The project grid is a single honest card type (correct — not the banned "identical icon-card grid" since cards carry real per-project data).
- **Em dashes in copy:** ABSENT.
- **>1 accent hue:** ABSENT (single Sol/primary accent throughout).
- **Phosphor-green live:** rendered gold, but the alias plumbing survives (see above) — latent.

### Cognitive-load checklist (8)

1. Visual hierarchy — OK on dashboard; modal flat (all-mono levels the type). 2. Color economy — OK (single accent) except raw red in modal. 3. Type scale — clean on dashboard; mono collapses contrast in modal/empty. 4. Spacing rhythm — good (`mb-6/mb-8`, varied). 5. Affordance clarity — WEAK: cards look clickable on hover but are not focusable. 6. Reading load — low/good. 7. State legibility — strong (skeleton/empty/error). 8. Motion restraint — OK; `EmptyState` framer-motion stagger is tasteful but lacks a `prefers-reduced-motion` guard at the component level.

### Persona red flags

- **Alex (power user):** No keyboard nav into projects (cards are click-only divs), no Cmd/Ctrl+Enter to submit the modal, no Escape to dismiss, no search/sort/filter on a grid that will grow past a screenful. Forces mouse for a deep-focus tool that promises to "get out of the way."
- **Sam (accessibility):** Multiple AA failures — `ProjectCard` is a non-semantic `div onClick` (no `role`/`tabIndex`/Enter-Space handler, WCAG 2.1.1 Keyboard); modal lacks `role="dialog"`/`aria-modal`/focus trap/return-focus and uses bare `focus:outline-none`; modal labels are not programmatically associated (`htmlFor`/`id`); modal error is a silent `div`, not `role="alert"`, so a screen reader never hears "Failed to create project."

### Priority issues

- **[P0] ProjectCard is not keyboard-operable.** *What:* `<div onClick={router.push(...)}>` with no role, no `tabIndex`, no key handler (`ProjectCard.tsx:36-41`). *Why:* keyboard and screen-reader users cannot open any project — the core action of the page. *Fix:* make it a real link — wrap the card body in `<Link href={...}>` (Next.js) or render the card as `<a>`; if it must stay a div, add `role="link" tabIndex={0}` and `onKeyDown` for Enter/Space, plus a `focus-visible:ring`. *Command:* `/impeccable harden app/(dashboard)/research-engine — make ProjectCard a focusable link with visible focus ring`.

- **[P1] CreateProjectModal reintroduces the terminal costume + raw palette.** *What:* `font-mono` on every element, uppercase tracked labels, Title Case copy, `bg-red-500/10 text-red-400` (`CreateProjectModal.tsx:60,73,80,88,94,102,110,117`). *Why:* directly violates DESIGN.md mono/anti-pattern rules and PRODUCT.md sentence-case voice; makes one page speak two visual languages. *Fix:* drop all `font-mono`; use `text-foreground`/`text-muted-foreground`, sentence-case ("New research project", "Create project"), and the semantic destructive token for the error box; lowercase the labels or use the shadcn `<Label>`. *Command:* `/impeccable distill CreateProjectModal — remove mono costume, sentence-case copy, semantic destructive token`.

- **[P1] Modal fails dialog a11y + keyboard control.** *What:* no `role="dialog"`/`aria-modal="true"`/`aria-labelledby`, no focus trap, no Escape, no backdrop-click close, bare `focus:outline-none` on inputs (`CreateProjectModal.tsx:57,88,102`). *Why:* keyboard users get trapped behind the dialog with no exit; WCAG 2.1.2 / focus-management failures. *Fix:* rebuild on the shadcn/Radix `Dialog` primitive (DESIGN.md says prefer these — they ship roles/focus-trap/Escape free), or add the attributes, an Escape handler, backdrop `onClick={handleClose}`, and replace `focus:outline-none` with `focus-visible:ring-2 focus-visible:ring-ring`. *Command:* `/impeccable harden CreateProjectModal — port to Radix Dialog with focus trap, Escape, labelled error`.

- **[P1] Error recovery uses full page reload.** *What:* dashboard retry calls `window.location.reload()` (`ResearchDashboard.tsx:134`). *Why:* discards client state, re-runs auth/layout, jarring for a deep-focus session; an SPA should refetch, not reload. *Fix:* point the retry action at `fetchProjects` instead of `window.location.reload()`. *Command:* `/impeccable harden ResearchDashboard — retry refetches instead of reloading the page`.

- **[P2] EmptyState body copy is mono; template chips hide meaning in `title`.** *What:* `EmptyState` title/description use `font-mono tracking-wider` (`EmptyState.tsx:53,61`); template chips expose `tpl.description` only via `title=` (`ResearchDashboard.tsx:87`). *Why:* mono contradicts the scholarly serif/Inter voice; `title` tooltips are invisible to touch/keyboard. *Fix:* swap EmptyState body to Inter/Source Serif tokens, no decorative tracking; show template descriptions as visible subtext or a popover. *Command:* `/impeccable clarify EmptyState + template chips — readable body type, visible template descriptions`.

### Strengths (what's working)

- **Honest states, done right.** Loading is a real skeleton grid with `role="status"` (not a spinner), empty and error are designed `EmptyState`s with actions, and the error wrapper carries `role="alert"`. This is exactly PRODUCT.md's "honest states" principle and the best part of the page.
- **Disciplined token use in the dashboard + card.** `text-foreground`, `text-muted-foreground`, `bg-primary`, `border-border`, `bg-card`, `hover:border-primary/50` — no raw hex, no `text-gray-*`, single Sol accent. `ProjectCard` status styling stays inside the token system.
- **Real focus affordances on the dashboard chrome.** The "New project" button and template chips use `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2` and `aria-hidden` on decorative icons — the modal just needs to match this standard.

### Minor observations

- `EmptyState` framer-motion stagger has no component-level `prefers-reduced-motion` branch (DESIGN.md requires a reduced-motion path for all motion); confirm the global guard at `globals.css:1499` covers framer transforms.
- `ProjectCard` date uses `toLocaleDateString()` with no `title`/`datetime` — fine, but a `<time>` element with ISO `dateTime` would help machines and screen readers.
- Modal inputs `autoFocus` the name field (good), but there is no max-length or duplicate-name guard.

### Questions

1. Is `CreateProjectModal` slated to migrate to the shadcn `Dialog` primitive the rest of the app uses, or was it hand-rolled deliberately? It is the only un-Radix dialog I see on this surface.
2. The `sol → var(--phosphor-green)` alias in `tailwind.config.ts:49` is live. Is there a planned rename to `--nous-sol`, or is the legacy alias intentionally retained for back-compat? It is the last live thread of the removed terminal theme.
3. Will the project grid get search/sort/filter before it ships, given the target users (researchers) accumulate many projects?
