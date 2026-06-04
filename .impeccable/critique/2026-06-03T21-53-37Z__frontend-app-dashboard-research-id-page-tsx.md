---
target: [id]
total_score: 29
p0_count: 0
p1_count: 3
timestamp: 2026-06-03T21-53-37Z
slug: frontend-app-dashboard-research-id-page-tsx
---
## /impeccable critique — research/[id] project workspace (product)

**File:** `/home/clawdbot/clawd/rag/frontend/app/(dashboard)/research/[id]/page.tsx`
(thin re-export of `/home/clawdbot/clawd/rag/frontend/app/(dashboard)/projects/[id]/page.tsx`)

### Overall impression
This is a dense 8-tab research workspace — Documents, Notes, Bibliography, Drafts, Chat, Matrix, Pipeline, Knowledge — and the **page shell itself is genuinely good NOUS product work**. Semantic tokens throughout, `focus-visible` rings on every interactive element, honest loading/empty/error states (skeleton on load, `role="status"`/`aria-busy`, `role="alert"` with status-aware 404 vs 500 copy and a Try-again path), `aria-current="page"` on the active tab, polling cleanup on unmount, and a real provenance touch (citation count + generated-at timestamp on the bibliography). It respects the researcher: the chrome mostly recedes.

The problem is **one imported child, `DraftGenerator.tsx`, which reintroduces the exact terminal costume DESIGN.md says was deliberately removed** — `font-mono` on nearly every element, repeated `uppercase tracking-wide` kicker-labels (AI scaffolding), a Title Case `font-bold` heading, `text-red-400` hardcoded, and a bare `focus:outline-none` with no replacement ring. Because the Drafts tab is a headline feature, this single component pulls the whole surface's score down and breaks consistency with the disciplined siblings (DocumentList, ProjectHeader, the page shell).

### Heuristic scores

| # | Heuristic | Score | Notes |
|---|-----------|:----:|-------|
| 1 | Visibility of system status | 3 | Strong: skeletons, `aria-busy`, Refreshing label, draft generation progress + poll, Comparing… state. Lost a point: DraftGenerator failures are console-only (silent). |
| 2 | Match real world | 3 | "Indexed/Queued/Processing", relative dates, citation formats (BibTeX/IEEE/APA/MLA) all speak the researcher's language. "Generate Literature Review" Title Case + uppercase mono labels break the plain sentence-case NOUS voice. |
| 3 | User control & freedom | 3 | Back link, Cancel on generation, Dismiss on error, version switching, clear-selection. Destructive removes are `confirm()` only (no undo), acceptable but blunt. |
| 4 | Consistency & standards | 2 | The fracture point. Shell + DocumentList use tokens, sentence case, `focus-visible`; DraftGenerator uses mono-everywhere, Title Case, bare `focus:outline-none`, hand-rolled toggle/radiogroup instead of shadcn. Two visual dialects in one tab set. |
| 5 | Error prevention | 3 | Confirms on document removal and bulk removal; Compare button disabled when versions equal/null; Generate disabled with 0 themes; Download disabled when no bibliography. Good. |
| 6 | Recognition over recall | 3 | Tabs with counts, version list with Current badge, format dropdown remembers selection. Eight tabs in a horizontal scroller with no overflow menu strains recognition on the densest tabs. |
| 7 | Flexibility & efficiency | 3 | Search + sort + bulk-select in DocumentList, keyboard arrow nav in the style radiogroup, agent-driven data refresh. No keyboard shortcut to switch tabs; power-users tab-cycle by mouse only. |
| 8 | Aesthetic & minimalist | 2 | DraftGenerator's mono saturation + 4 repeated uppercase tracked labels is noise, not rhythm. Shell is clean. The mono on the bibliography `<pre>` is sanctioned (code output). |
| 9 | Error recovery | 3 | Project-load error has a real recovery UI (Try again / Back to projects, status-aware copy). But draft generate/compare/save catch-blocks only `console.error` — user sees nothing. |
| 10 | Help & documentation | 4 | Empty states are instructional ("Choose your themes on the left, then generate…", "Add documents with extracted citations…"), inline hints, labelled controls. Best heuristic on the page. |

**Total: 29 / 40 — Good** (lower-middle of the band; the shell alone would score ~33, DraftGenerator drags it down).

### Anti-patterns verdict
- **Terminal / mono costume — PRESENT (in DraftGenerator).** `font-mono` on the heading, every label, the theme input, chips, the slider scale, the doc-count note, and the Generate button. DESIGN.md: "Do not use mono as decorative 'technical' shorthand" and "mono-everywhere" is on the do-not-ship list. This is the most serious finding.
- **Repeated uppercase tracked labels — PRESENT.** Four `uppercase tracking-wide` labels in one form ("Themes / Topics", "Writing Style", "Max Sections", "Include Abstract"). DESIGN.md allows one tracked kicker per section max; repeating it is flagged as "AI scaffolding".
- **Hardcoded color — PRESENT.** `text-red-400` (DraftGenerator chip-remove hover, DocumentList PDF icon). Should be `text-destructive` / a Mars token. No `text-gray-*`, no hex elsewhere — narrow violation.
- **Title Case headline copy — PRESENT.** "Generate Literature Review" (×2), "Writing Style", "Max Sections", "Include Abstract". NOUS voice is sentence-case.
- Gradient text: none. Glassmorphism-default: none. Side-stripe borders: none. Hero-metric template: none. Identical card grids: none. >1 accent hue: no (single Sol). Em dashes in copy: none. Modal-first: no (tabs lead, modals are secondary).

**Detector:** `detect.mjs --json` returned `[]` on all four files. These findings are detector **blind spots** (it does not flag mono-density, `uppercase tracking-wide` repetition, `text-red-400`, bare `focus:outline-none`, or Title Case copy), confirmed by grep — **not false positives**. The shell's `font-[var(--nous-font-mono)]` on the bibliography `<pre>` is a **legitimate sanctioned use** (BibTeX/citation code output) and should NOT be flagged.

### Cognitive load (8-item)
1. **Visual noise** — high in DraftGenerator (mono + tracked labels everywhere), low in shell. Mixed.
2. **Choice overload** — 8 tabs visible at once; a divider before tab 4 helps, but no overflow/grouping. Borderline.
3. **Memory burden** — low; counts and badges externalize state well.
4. **Reading load** — low; sentence-case in shell, instructional empties.
5. **Decision friction** — Compare/Generate gating is clear. Good.
6. **Interaction cost** — version compare needs two selects + a button; reasonable. Tab switching mouse-only.
7. **State ambiguity** — generation progress and poll are explicit; but a silent generate-failure is the worst ambiguity here.
8. **Inconsistent mental model** — the Drafts form looks like a different app than the rest. Cost incurred.

### AI-slop verdict: YES (localized)
Would someone say "AI made this"? On the **Drafts tab, yes** — mono-everywhere + four uppercase tracked labels + Title Case headings + a hand-rolled toggle is the canonical "technical-looking AI form." On the **rest of the page, no** — the shell is considered, token-clean, and honest. The slop is contained to one component, which is good news: it's a surgical fix, not a rewrite.

### Persona red flags
- **Alex (power-user / researcher in deep focus):** No keyboard tab navigation — eight tabs are mouse-only horizontal scroll; a power-user living in this workspace will resent reaching for the trackpad to jump Documents→Chat→Matrix. And a draft generation that fails silently (console-only) makes the system feel untrustworthy precisely where trust matters (provenance/output). PRODUCT.md says success is "trusting an answer enough to act on it" — a silent failure breaks that contract.
- **Sam (accessibility / AT user):** The theme input in DraftGenerator has `focus:outline-none` with **no focus ring**, so a keyboard user loses the cursor — a direct WCAG 2.1 AA / DESIGN.md violation ("Never bare `focus:outline-none`"). `text-red-400` for the PDF icon and chip-remove hover encodes/uses non-token color (and red-as-only-signal risks color-only meaning). The custom toggle/radiogroup are hand-rolled rather than shadcn primitives, so they carry more a11y risk than the Radix components used elsewhere.

### Priority issues

**P1 — DraftGenerator is mono-everywhere + repeated uppercase tracked labels (terminal costume reintroduced).**
*What:* `font-mono` on heading, labels, input, chips, slider scale, note, and button; four `uppercase tracking-wide` labels; `font-bold` Title Case heading.
*Why:* Directly violates DESIGN.md anti-patterns (mono-everywhere, repeated tracked labels) and PRODUCT.md anti-references (the deliberately-removed terminal skin). It also makes the flagship Drafts feature inconsistent with every sibling tab.
*Fix:* Drop `font-mono` from all of it (let Inter/UI inherit); keep mono only if a value is genuinely code. Use one tracked kicker for the form max, sentence-case the rest as plain `text-sm text-muted-foreground` labels. Rename heading to sentence case "Generate literature review". Reach for shadcn `Switch`, `Slider`, `Label`, and `ToggleGroup` instead of hand-rolled controls.
*Command:* `/impeccable distill src/components/research/DraftGenerator.tsx` (strip costume, re-token, adopt shadcn primitives).

**P1 — Hardcoded `text-red-400` + bare `focus:outline-none` (token + a11y violations).**
*What:* `text-red-400` in DocumentList (PDF icon) and DraftGenerator (chip-remove hover); `focus:outline-none focus:border-primary` on the DraftGenerator theme input with no replacement ring.
*Why:* DESIGN.md: never hardcode color, never bare `focus:outline-none`. The missing focus ring fails WCAG 2.1 AA keyboard visibility.
*Fix:* Replace `text-red-400` with `text-destructive` (or a Mars semantic token). Replace `focus:outline-none focus:border-primary` with `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2` to match the shell's pattern.
*Command:* `/impeccable harden src/components/research/DraftGenerator.tsx src/components/research/DocumentList.tsx` (focus states + token cleanup).

**P1 — Silent failures on draft generate / compare / save.**
*What:* The generate, compare, and note-save catch-blocks `console.error` only; no `role="alert"` surfaced to the user. A failed generation leaves the form looking idle.
*Why:* PRODUCT.md "Honest states" + heuristic 9; a research instrument that fails invisibly erodes the trust the whole product is built on.
*Fix:* Surface a `role="alert"` inline error (reuse the shell's destructive alert pattern at lines ~604–617) for generation/compare/save failures, with a retry affordance for generation.
*Command:* `/impeccable shape src/components/research/DraftGenerator.tsx` (add visible error + retry states).

**P2 — Eight tabs, no overflow affordance; mouse-only switching.**
*What:* 8 tabs in a horizontal `overflow-x-auto` scroller; on mobile only the first 4 chars of each label show; no keyboard tab cycling, no overflow/"More" menu.
*Why:* Recognition + flexibility cost for the exact power-user persona this product targets; truncated 4-char labels ("Bibl", "Know") hurt recognition.
*Fix:* Consider a Radix `Tabs` with roving-tabindex keyboard support (arrow keys), or group the lower-traffic tabs (Matrix/Pipeline/Knowledge) under a "More" menu. At minimum give the mobile labels icons + tooltips rather than 4-char clips.
*Command:* `/impeccable clarify app/(dashboard)/projects/[id]/page.tsx` (tab IA + keyboard nav).

**P3 — Hand-rolled toggle/radio vs shadcn; `confirm()` for destructive actions.**
*What:* DraftGenerator builds its own switch and radiogroup; document removal uses native `confirm()`.
*Why:* DESIGN.md prefers shadcn/Radix primitives (baseline a11y); native `confirm()` is unstyled and breaks the warm-scholarly tone.
*Fix:* Swap to shadcn `Switch`/`ToggleGroup`; replace `confirm()` with an `AlertDialog` for a consistent, accessible, on-brand confirmation.
*Command:* `/impeccable adapt src/components/research/DraftGenerator.tsx` (adopt design-system primitives).

### What's working (strengths)
- **Honest, designed states.** Loading skeleton mirrors final layout; `role="status"`/`aria-busy` on every async region; status-aware error UI (404 vs 500) with real recovery actions; instructional empty states. This is exactly the "honest states" principle from PRODUCT.md, executed well.
- **Token + a11y discipline in the shell and DocumentList.** Semantic tokens throughout, single Sol accent (no second hue), `focus-visible` rings on every control, `aria-current` on tabs, `aria-label` on icon-only buttons, proper `confirm` gating on destructive bulk actions.
- **Provenance is visible.** Bibliography shows citation count + generated-at timestamp; drafts carry versions with a Current badge and a comparison flow — the product is showing its work, per its first design principle.

### Minor observations
- `ProjectHeader` "Hero card" is a bordered card, not a banned hero-metric template — fine, but the back-link could be a real `<a>`/`Link` for middle-click/open-in-new-tab.
- DocumentList `font-mono` on the filename subline is a defensible technical-label use (a real filename), borderline but acceptable; keep an eye on it not spreading.
- `window.open('/documents/...', '_blank')` for "View document" works but a `Link` with `target` is more accessible and keyboard-friendly.
- The bibliography `<pre>` uses `font-[var(--nous-font-mono)]` correctly (code output) — do not "fix" this.

### Questions
1. Is the Drafts tab a recent addition or legacy? Its divergence from the shell's discipline suggests it predates the terminal-costume removal and was missed in the sweep.
2. Are Matrix / Pipeline / Knowledge tabs heavily used? If they're niche, grouping them under a "More" menu would cut the 8-tab cognitive load for the common case.
3. Is there an undo for document removal, or is `confirm()` the only guardrail? For a corpus a researcher has curated, soft-delete + undo would better match "act on it" trust.
