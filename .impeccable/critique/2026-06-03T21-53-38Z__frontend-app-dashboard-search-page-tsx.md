---
target: search
total_score: 25
p0_count: 1
p1_count: 3
timestamp: 2026-06-03T21-53-38Z
slug: frontend-app-dashboard-search-page-tsx
---
## /impeccable critique — search (product)

**Page:** `/home/clawdbot/clawd/rag/frontend/app/(dashboard)/search/page.tsx`
**Register:** product · **Verdict band:** Acceptable (25/40) · **AI-slop:** yes (in the imported components, not the shell)

### Overall impression
The page file itself is one of the better product surfaces in this codebase. `SearchPage` ships a real empty state with a plain sentence-case prompt ("Search your knowledge base… with sources you can open"), four scannable suggested queries, an abort controller cancelled on unmount, a working Stop button, a global `/` focus shortcut that correctly ignores when you're already in a field, and a `?q=` deep-link path. The voice is calm and scholarly, exactly the NOUS register.

The problem is everything it imports. `CitationPanel`, `ChatBubble`, and `SearchComposer` are clearly older "Terminal Observatory" components that were value-remapped to gold but never re-typeset or re-audited. The Sources panel has genuinely backwards contrast, mono is sprayed as decoration, hex is hardcoded through a `THEME` constant whose keys are still named `phosphorGreen`/`cyan`, and a footer literally reads "Sources Retrieved via RAG Pipeline" in uppercase tracked mono. So the shell scores well and the payload drags it down to Acceptable.

### Heuristic scores

| # | Heuristic | Score | Notes |
|---|-----------|------:|-------|
| 1 | Visibility of system status | 3/4 | Thinking pill (`role=status`, `aria-live=polite`), tool strip with sources count + response time, smooth scroll-to-bottom. But the in-flight Stop has no "stopped" acknowledgement and analytics `trackSearch` always logs `0` results. |
| 2 | Match real world | 3/4 | Sentence-case, "Sources", relevance %, plain prompts. Dragged by "Sources Retrieved via RAG Pipeline" and `[/] Commands` jargon in the composer footer. |
| 3 | User control / freedom | 2/4 | Stop button + abort-on-unmount are good. But the Sources slide-out has no Escape close, no backdrop click-out, no focus trap — once open you can only reach the X. |
| 4 | Consistency / standards | 2/4 | Page uses shadcn semantic tokens (`bg-card`, `border-border`, `text-foreground`); the imported components mix `var(--nous-*)`, raw `THEME.colors` hex, and `font-mono`. Two color systems in one render tree. |
| 5 | Error prevention | 3/4 | Submit disabled on empty, `isLoading` guard blocks double-fire, Enter-vs-Shift-Enter handled. Fine. |
| 6 | Recognition vs recall | 3/4 | Suggested queries, citation chips, source titles all reduce recall. The composer keyboard hints exist but are 9px mono and easy to miss. |
| 7 | Flexibility / efficiency | 3/4 | `/` shortcut, `?q=` deep link, Enter-to-send, auto-grow textarea — good power-user affordances. No way to re-run/edit a prior query or scroll history beyond the single thread. |
| 8 | Aesthetic / minimalist | 2/4 | The empty state is clean. The chat row is busy: avatar + "Assistant" + model pill + clock + tool strip + footer chips + 5 hover-action buttons (three of which do nothing). |
| 9 | Error recovery / help | 2/4 | Errors append as a plain assistant bubble — no `role=alert`, no retry affordance on the search page (`onRetry` is wired in ChatBubble but never passed here), and `toErrorMessage(err: any)` can surface raw backend `detail` strings. |
| 10 | Help / documentation | 2/4 | Suggested queries are the only guidance. No "what can I ask", no source-confidence explanation, no empty-result coaching. |
| | **Total** | **25/40** | **Acceptable** |

### Anti-pattern verdict (NOUS banned list)

| Pattern | Present? | Evidence |
|---|---|---|
| Terminal costume / phosphor | **Yes (residue)** | `THEME.colors.primary` comes from `COLORS.phosphorGreen`; `constants.ts` keeps `phosphorGreen`/`cyan`/`terminal*` key names and "Terminal Observatory theme" comments. `CitationPanel.tsx:14` comment: "Terminal Observatory theme colors". Footer copy "Sources Retrieved via RAG Pipeline". |
| mono-everywhere | **Yes** | `CitationPanel` uses `font-mono` on input, counts, sort button, empty-state text, and footer (lines 154/163/170/187/216). `ChatBubble` citation chips + diag link use `--nous-font-mono` (283/298). Composer hint uses `--nous-font-mono` (113). DESIGN.md: "Do not use mono as decorative technical shorthand." |
| Hardcoded hex / text-gray-* | **Yes** | `style={{ color: THEME.colors.primary }}` ×3 and `${THEME.colors.primary}15/40` in CitationPanel (117/121/129–130/217); `rgba(212,160,57,...)` glows in CitationPanel (109), ChatBubble (385), SearchComposer (98). DESIGN.md: "Never hardcode hex in components." |
| >1 accent hue | No (collapsed) | `cyan` is now remapped to the same gold; effectively one hue. Red Stop button is sanctioned status (Mars). |
| Gradient text (`bg-clip-text`) | No | None found. |
| Glassmorphism default | No | No `backdrop-blur`. The composer's `bg-gradient-to-t` fade-to-transparent is a legit scrim, not glass. |
| Side-stripe accent borders | No | `border-l` in citation chip is a separator inside a pill, not a card stripe. |
| Hero-metric template | No | Not applicable here. |
| Identical card grids | Borderline | The 4 suggested-query cards are an identical icon+label grid — acceptable at n=4, but it is the "identical icon-card grid" shape PRODUCT.md warns about. |
| Em dashes in copy | No (user-facing) | Em dashes only appear in code comments, not rendered strings. Not a violation. |

Detector note: `node detect.mjs --json` returned `[]` for all five files. That is a **false-negative set**, not a clean bill — the hex lives behind a `THEME.colors.*` constant and `font-mono` is a utility class the regex pass doesn't flag in TSX. All four findings above were confirmed by manual grep.

### Cognitive load (8-item check)
1. Visual hierarchy — empty state clear; chat row over-decorated (avatar + label + pill + clock + strip). **Strained.**
2. Color meaning — gold = interactive/accent consistently. **OK.**
3. Text legibility — **Fails in CitationPanel**: typed input is `text-muted-foreground` while placeholder is `placeholder:text-foreground` (placeholder brighter than your own text); counts/empty-state/search-icon are full `text-foreground` where muted is intended. Inverted.
4. Grouping/proximity — message columns and footer chips group well. **OK.**
5. Action clarity — five hover icons on each answer, three of which (ThumbsUp/Down/Bookmark) have no `onClick`. **Decoy actions.**
6. Progressive disclosure — Sources panel is good disclosure; tool strip is good. **OK.**
7. Consistency of patterns — two token systems (`--nous-*` vs `THEME.colors` hex) in one tree. **Strained.**
8. Motion restraint — stagger, spring slide-in, pulsing 3px glow with **no `prefers-reduced-motion` path** anywhere. **Fails a11y.**

### Persona red flags
*(Interface type: data/answer surface → Alex power-user + Sam a11y)*

- **Sam (screen reader / low vision):** The Sources slide-out has no `role="dialog"`, no `aria-modal`, no focus trap, no Escape, no backdrop — keyboard focus stays trapped behind it in the chat. The placeholder-brighter-than-text inversion makes the source search field read as already-filled. Pulsing glows and spring slides have no reduced-motion escape. Error bubbles are not `role="alert"`, so an SR user gets no announcement when a search fails.
- **Alex (power user / researcher):** No way to edit and re-run a previous query, no retry on a failed answer (the `onRetry` capability exists in ChatBubble but the page never passes it), and the thumbs/bookmark controls are dead — clicking them does nothing, which erodes trust in a "thinking instrument." Tool strip shows response time but `trackSearch` logs `0` results regardless, so any internal metrics are wrong.

### Priority issues

**[P0] Sources panel contrast is inverted.**
*What:* In `CitationPanel.tsx`, the `Input` is `text-muted-foreground placeholder:text-foreground` (your typed query is dimmer than the placeholder), and the result count, empty-state copy, and search icon use full `text-foreground` where muted is intended (lines 147/156/163/187).
*Why:* Directly fails the "text legibility" load item and likely WCAG AA expectations for the primary input; it reads as broken.
*Fix:* Swap to `text-foreground placeholder:text-muted-foreground` on the input; make counts/empty-state `text-muted-foreground`; give the search icon `text-muted-foreground`.
*Command:* `/impeccable harden CitationPanel.tsx --a11y --contrast`

**[P1] mono-as-decoration across the source/chat chrome.**
*What:* `font-mono`/`--nous-font-mono` on the Sources search input, counts, sort button, empty state, footer, plus ChatBubble citation chips and composer hint.
*Why:* DESIGN.md restricts mono to code and tiny technical labels; the spray reads as terminal-costume, the exact anti-reference NOUS removed.
*Fix:* Move source titles, counts, and the footer to `--nous-font-ui`. Keep mono (if anywhere) only on the relevance-% token.
*Command:* `/impeccable distill CitationPanel.tsx ChatBubble.tsx --typography`

**[P1] Hardcoded hex via `THEME.colors` + raw rgba glows.**
*What:* `style={{ color: THEME.colors.primary }}` and `${THEME.colors.primary}15/40` (CitationPanel), `rgba(212,160,57,...)` shadows (CitationPanel/ChatBubble/SearchComposer).
*Why:* Violates "never hardcode hex"; it also defeats light/dark theming since `THEME.colors.primary` is a fixed `#D4A039`, not a theme-flipping `--nous-*` var.
*Fix:* Replace with `text-[var(--nous-sol)]` / `var(--nous-shadow-focus)` and the `--nous-sol-muted` tints. Rename `phosphorGreen`/`cyan`/`terminal*` keys in `constants.ts` or delete the file in favor of CSS vars.
*Command:* `/impeccable colorize search --tokens --kill-hex`

**[P1] Sources slide-out is not a real dialog.**
*What:* `CitationPanel` is a `fixed` motion panel with only an X button — no `role="dialog"`, no `aria-modal`, no Escape handler, no focus trap, no click-outside.
*Why:* Fails user control/freedom and a11y; keyboard users get stranded.
*Fix:* Wrap in a Radix `Dialog`/`Sheet` (already in `src/components/ui`), or add Escape + backdrop + initial-focus + focus return.
*Command:* `/impeccable harden CitationPanel.tsx --dialog --keyboard`

**[P2] Dead and missing actions.**
*What:* ThumbsUp/Down/Bookmark in ChatBubble have no handlers; the search page never wires `onRetry`, so failed answers can't be retried; error bubbles aren't `role="alert"`.
*Why:* Decoy controls and unrecoverable errors undercut the "honest states / provenance" principle.
*Fix:* Either wire feedback to analytics or remove the buttons; pass an `onRetry` that re-runs the last user query; render error content in a container with `role="alert"`.
*Command:* `/impeccable clarify search --error-states --remove-decoys`

### What's working (keep)
- **Honest, on-voice empty state.** "Search your knowledge base / Ask a question and get an answer drawn from your documents, with sources you can open." Sentence-case, no hype, provenance-forward — textbook NOUS product register.
- **Real request lifecycle.** AbortController cancelled on unmount, in-flight abort on new search, a working Stop button, and cancellation correctly suppresses a spurious error bubble. This is the honest-loading discipline the design principles ask for.
- **Power-user affordances on the shell.** Global `/` shortcut that defers when already typing, `?q=` deep link consumed once, Enter/Shift-Enter, auto-growing composer. The page-level keyboard story is strong.

### Minor observations
- `mapSearchResultToChatMessages` returns `[user, assistant]` and the page reads `mappedMessages[1]` by index — brittle if the mapper ever changes shape; destructure instead.
- Composer footer hint `[/] Commands` implies a command palette that doesn't exist on this page (only `/` focus). Either build it or relabel to "Focus".
- `analytics.trackSearch(query, 0, ...)` hardcodes a `0` result count even after results arrive.
- The suggested-query labels ("Performance metrics", "Recent uploads") map to free-text searches, not real filters — fine, but a researcher may expect them to be scoped queries.

### Questions
1. Is `src/theme/constants.ts` still imported by many components, or can the `phosphorGreen`/`cyan` value-remap layer be retired entirely in favor of `--nous-*` CSS vars (which would fix theming and the hex violation at once)?
2. Are the thumbs/bookmark controls intended to ship, or are they placeholder UI? That decides whether P2 is "wire up" or "delete."
3. Should the Sources panel be a Radix `Sheet` (project already has the primitives) so dialog semantics, focus trap, and reduced-motion come for free?
