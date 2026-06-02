# Design Brief: /chat — whole-surface rethink

Status: confirmed direction, ready for `/impeccable craft`.
Register: product. Scope: whole surface, production-ready.
Date: 2026-05-30.

## Critical finding (current state)

`frontend/src/components/chat/WelcomeState.tsx` is a terminal-costume relic that survived the app-wide migration: uses `--term-*` CSS vars, spinning radar rings (`term-spin`/`term-radar`/`term-float`), glassmorphism (`backdropFilter: blur`), `font-nous-mono`, and SHOUTING copy ("NEURAL LINK ESTABLISHED", "AWAITING NEURAL HANDSHAKE", "RAPID PROCESSING", "NEURAL INFERENCE", "CITATION CHAIN", "LOCAL CONTEXT"). Direct hit on PRODUCT.md anti-ref #1 (cyberpunk/terminal costume). This is the first surface a researcher sees. Highest-priority rebuild.

The populated path (`ChatMessageList`, `MessageBubble`), loading skeleton, init/error states, and HITL banner are structurally clean post-migration; the HITL banner still has one shouting uppercase label to fix.

## 1. Feature Summary

Core working surface of NOUS: a researcher asks questions, gets answers grounded in their corpus, with visible provenance. Three zones: thread rail (left), conversation column (center), citation slide-over (right), plus composer and HITL approval.

## 2. Primary User Action

Ask a question, read an answer, verify which source passages back it, without leaving the thread. Provenance is the job, not a feature.

## 3. Design Direction

- Color: Restrained (product floor). Tinted-neutral surfaces; warm-gold (Sol) reserved for primary action, current selection, streaming/state, citation markers only. No decorative gold.
- Theme scene: "A researcher in a focused afternoon session, reading dense answer text and source passages for long stretches; a warm near-black surface keeps gold citation markers and the graph legible without glare." Forces dark (DESIGN.md anchor confirms).
- Anchors: Perplexity (provenance-first answers, inline sources), Linear (calm product chrome, command palette, density without noise), Raycast (composer-as-focus).

## 4. Scope

Whole surface, production-ready, polish-until-ships. All three zones + every state. Shippable components.

## 5. Layout Strategy

Keep the proven three-zone shell, sharpen each:

- Thread rail recedes (cooler neutral); current thread is the only gold mark.
- Conversation column is the hero. Prose capped ~70ch, generous vertical rhythm between turns, user vs assistant by alignment/weight not heavy bubbles.
- Provenance promoted from afterthought: inline citation markers in the answer that resolve to a source peek, panel as deep view. Principle #1 made visible.
- Composer pinned, calm, single-family type.

## 6. Key States

- Unauthenticated: brief redirect notice (already calm).
- Initializing: single honest spinner + 15s watchdog message (exists).
- Init error: "Connection error" + retry (exists, sentence-case).
- Loading messages: skeleton turns, not spinner (exists).
- Empty / first-run: REBUILD. Calm welcome + researcher-task prompt starters. Kill NEURAL costume entirely.
- Default thread: readable turns, visible provenance.
- Streaming: token stream + inline tool_start/tool_end status (agent is multi-step).
- HITL interrupt: calm approval card; de-shout "Action Requires Approval" to sentence-case.
- Citation open: source passage + confidence + link to full doc.
- Stream error: inline, recoverable, not a wipe.
- Long thread: virtualized, scroll-anchored.

## 7. Interaction Model

Type to submit, stream tokens. Tool calls surface as quiet inline status ("Searching documents…", "Reading 3 sources"), not hidden. Citation markers clickable to inline peek then panel. Regenerate, RAG toggle, model select, attach on the composer. Thread CRUD via rail + command palette. Motion 150-250ms, ease-out, state-only (streaming caret, tool status, panel slide). No choreography.

## 8. Content Requirements

- Prompt starters (replace NEURAL copy): "Summarize this document in three points", "Show the sources behind this claim", "How do the entities in my graph relate?", "Compare these two findings".
- HITL copy: sentence-case, name the tool + what it touches.
- Empty heading: calm, scholarly, one line. No handshake/transmission/stream vocabulary.
- Tool-status microcopy: plain present-tense.

## 9. Recommended References

spatial-design.md (three-zone hierarchy + provenance promotion), interaction-design.md (composer, HITL, streaming feedback), motion-design.md (streaming + tool-status motion), product.md.

## 10. Decisions (defaults asserted)

- Keep dark (DESIGN.md anchor); enforce body-text contrast + comfortable measure. Light reading mode deferred.
- Provenance: both inline peek (marker to hover/tap peek) and panel deep view.

## Key files (entry points for craft)

- `frontend/app/(dashboard)/chat/page.tsx` — main surface, all state branches.
- `frontend/app/(dashboard)/chat/chat-layout-client.tsx` — layout shell + command palette.
- `frontend/src/components/chat/WelcomeState.tsx` — REBUILD (costume relic).
- `frontend/src/components/chat/ChatMessageList.tsx`, `MessageBubble.tsx` — turns.
- `frontend/src/components/chat/ChatInput.tsx` — composer.
- `frontend/src/components/chat/ChatSidebar.tsx` — thread rail.
- `frontend/src/components/chat/CitationPanel.tsx` + `CitationLink/Renderer/Preview.tsx` — provenance.
- HITL banner: inline in `page.tsx` lines ~439-478.
- Hooks: `frontend/src/hooks/chat/{useChatSession,useChatStreaming,useChatThreadActions}.ts`.
