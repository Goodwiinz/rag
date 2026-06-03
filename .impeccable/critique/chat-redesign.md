# Critique: /chat redesign (craft pass 1)

Date: 2026-05-31.
Scope reviewed: `frontend/src/components/chat/WelcomeState.tsx` (rebuilt) and the HITL approval banner inline in `frontend/app/(dashboard)/chat/page.tsx` (~439-485).
Reference: `.impeccable/briefs/chat-redesign.md`, `PRODUCT.md`, `DESIGN.md`.
Visual: `.impeccable/screenshots/chat-redesign-preview.png` (standalone preview, dark, 1280×1800@2x).

## Heuristic scoring (0-5)

| Heuristic                       | Empty state | HITL banner | Notes                                                                                                                                                                                                             |
| ------------------------------- | ----------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Anti-ref compliance             | 5           | 5           | No glass, no gradient text, no side-stripes, no uppercase-mono decoration, no hero-metric, no identical card grid (single bordered list ≠ N cards).                                                               |
| Provenance principle visibility | 4           | n/a         | Intro sentence states the source-tracing promise; not yet _shown_ via citation peek.                                                                                                                              |
| Calm-voice copy                 | 5           | 5           | Sentence-case heading, plain serif body, named tool + named choice on HITL.                                                                                                                                       |
| Honest states                   | 4           | 4           | Empty/first-run is honest. HITL names the tool; doesn't yet show _what it touches_ (paper IDs, doc UUIDs) — brief asked for both.                                                                                 |
| Density with rhythm             | 4           | 5           | Empty state uses generous rhythm (mt-9 gap before list) without padding monotony.                                                                                                                                 |
| Familiar product pattern        | 5           | 5           | List = command-palette pattern (Linear/Raycast). Banner = standard alertdialog vocabulary.                                                                                                                        |
| A11y                            | 4           | 5           | Empty: buttons real, focus-visible ring inset, icons aria-hidden. Banner: `role="alertdialog"`, `aria-label`, icon aria-hidden. Missing: announce when banner appears (likely fine via role; not tested with SR). |
| Motion discipline               | 5           | 5           | Single 400ms ease-out fade, skipped under prefers-reduced-motion. Banner: no motion (correct — appearance is the signal).                                                                                         |

## What's right

- **Killed the costume.** All `--term-*` references (which referenced _deleted_ CSS vars and rendered on transparent fallbacks) are gone. Surface now uses live `--nous-*` tokens; dark-mode flip works because `--nous-fg-accent` resolves to Helios on dark for the tool chip.
- **Researcher-task starters, not feature boasts.** Verbatim from brief. Each row inserts plain prose into the composer.
- **One list, not four cards.** Sidesteps the "identical icon-card grid" ban while keeping the familiar command-row affordance product UIs are allowed.
- **Hover affordance is honest.** Icon Sol-tints, `↵` reveals. Both convey "this is clickable and submits-on-Enter," nothing decorative.
- **HITL banner names the choice.** "Approve to let it continue, or deny to stop here." Replaces ambiguous shouted label with a sentence that tells the user what each button does.

## Pass 2 (2026-06-03): brief follow-ups landed

1. **HITL arg preview — DONE.** `app/(dashboard)/chat/page.tsx` now extracts `tool_name`/`tool_args` (or nested `tools[0].{name,args}`) from the confirmation payload and renders args as a mono KV `<dl>` under the tool chip. Long values truncate to 140 chars with ellipsis. Handles flat-SSE and nested-polling shapes defensively.
2. **Inline citation peek — ALREADY BUILT, defect fixed.** `CitationLink.tsx` had used Radix `HoverCard` for hover/tap source-passage preview since the migration; the only impeccable defect was a `text-[9px] uppercase tracking-wider font-mono` "PREVIEW" decorative label. Replaced with sentence-case Inter `Preview` + neutral icon, bumped preview to 4 lines / 240 chars.
3. **Auth de-costume — DONE in pass 1.5.** See commit `8c664e51`.
4. **Thread rail receded — DONE.** `ChatSidebar.tsx`: dropped the gold side-stripe active accent (was `absolute left-[-10px] w-0.5 bg-sol` — borderline anti-ref). Active state is now the only gold mark, via the aurum/ember background tint alone. Non-active hover switched from warm `bg-aurum/umber` to neutral `bg-bg-2/obsidian`. Section labels, filter chip labels, and workspace subtitle migrated from `font-mono uppercase tracking-[0.18em]` to Inter sentence-case. Dropped decorative `hover:translate-y` on the "New chat" button.
5. **Tool-status microcopy — DONE.** Added `toolStatusLabel(tool, status)` to `context-rail/toolLabels.ts` with present-progressive ("Searching documents…", "Querying the knowledge graph…") and past tense ("Searched documents", "Created project") variants. `InlineAgentSummary.tsx` summary line now reads the latest active step's microcopy while running; expanded list renders status-aware labels per step. Step list font flipped from mono to Inter.

## What's still missing (against the brief)

1. **Composer single-family pass.** Pinned + calm post-migration; the deliberate Raycast-focus typography pass hasn't happened.
2. **Long-thread virtualization — NOT IMPLEMENTED.** Honest audit:
   - `VirtualizedConversationList.tsx` virtualizes **threads in the sidebar**, not messages in a thread.
   - It's wired only into the legacy `ConversationSidebar`, not the in-use `ChatSidebar`.
   - The active message column (`ChatMessageList.tsx`, 199 lines) uses plain `messages.map()` with no virtual scroller and no scroll anchoring.
   - Building this properly = react-virtuoso or `@tanstack/react-virtual`, dynamic measured row heights, scroll-anchor preservation on streaming append, and citation-hover-card portal compatibility. 2-4 hour implementation with regression risk; deferred to a focused craft pass.
3. **Score-badge color literals.** `CitationLink.tsx` still uses Tailwind emerald/amber/orange/red literals for the relevance score badge. Semantic mapping is honest but bypasses the theme token layer; minor.

## Concrete TODO for next pass

In priority order, each scoped tightly:

1. **HITL arg preview.** Render `pendingConfirmation.confirmation?.tool_args` (or equivalent) as a small KV list under the tool chip. Truncate long values. Type-safe via the agent SDK types in `backend/src/services/agent/`.
2. **Auth de-costume.** 4-file rewrite. Sentence-case headings, drop `font-mono uppercase tracking-*`, replace with Inter at proper scale. Brand register, so bolder type allowed but no uppercase-mono.
3. **Inline citation peek.** Wrap `CitationLink` / `CitationRenderer` output with Radix `HoverCard` (or `Popover` on touch) that loads the passage from `CitationPanel`'s data source. Click still opens the side panel.
4. **Tool-status microcopy line.** Inline assistant-message variant for `tool_start`/`tool_end` events. Plain present-tense map per tool name. Reduced-motion-safe pulse.

## Notes for future agents

- `WelcomeState` accepts `selectedModel` for API compatibility but ignores it. Page hardcodes `"nous-agent"`. Don't re-introduce a "model not ready" branch unless `selectedModel` actually becomes user-toggleable upstream.
- The preview route used to capture the screenshot (`frontend/app/preview/chat-welcome/page.tsx`) was deleted after capture — it bypassed auth and shouldn't ship. Recreate it locally for future re-shoots: render `<WelcomeState onPromptSelect={() => {}} />` standalone and toggle `.dark` on `documentElement`.
- `npm run lint` is currently broken environment-wide (`@eslint/eslintrc` circular-structure crash during config load, before linting any file). Independent of these changes; worth a separate look.
