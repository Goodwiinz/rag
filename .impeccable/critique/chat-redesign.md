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

## What's still missing (against the brief)

These are real gaps, not nits. Each = a candidate next craft pass.

1. **Inline citation peek.** Brief's Layout Strategy #3: promote provenance from afterthought to inline. Today citations still resolve to the side panel only. Inline marker → hover/tap source-passage preview is not built.
2. **HITL doesn't show what the tool touches.** Brief: "name the tool + what it touches." Banner names the tool (`ingest_arxiv_paper`); it does not preview the _arguments_ (which paper, which doc IDs, which note title). High-value defect — the choice is uninformed without it.
3. **Auth surfaces still costume.** `app/(auth)/{forgot-password,reset-password,verify-email,cli-auth}/page.tsx` carry ~30 `font-mono uppercase tracking-[0.15em]` labels and ALL CAPS headings ("RESET LINK SENT", "ACCESS TERMINAL"). PRODUCT.md anti-ref #3. Color migrated, typography costume left.
4. **Thread rail not yet receded.** Brief's Layout Strategy #1: rail uses a cooler neutral; current thread is the only gold mark. Not touched this pass.
5. **Composer not retouched.** Pinned/calm is mostly there post-migration; brief's "single-family type" + Raycast-focus aesthetic not deliberately revisited.
6. **Tool-status microcopy.** Streaming surfaces tool_start/tool_end events but the brief asks for plain-present-tense quiet inline lines ("Searching documents…", "Reading 3 sources"). Implementation in `useChatStreaming` + `ChatMessageList` not audited this pass.
7. **Virtualization.** Long threads — brief says virtualized, scroll-anchored. Existing `VirtualizedConversationList` exists; not confirmed wired in the default path.

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
