# Chat UI/UX Consistency Design

## Goal

Create one consistent chat experience across `/chat` and `/search` by reusing the same page shell, chat bubble system, composer behavior, and interaction patterns.

## Scope

- In scope:
  - `/chat` and `/search` only.
  - Shared chat UI primitives and consistent interaction rules.
  - Citation rendering/click behavior parity.
- Out of scope:
  - `/llm-chat` migration in this pass.
  - Backend API behavior changes.

## Architecture

Use `/chat` as the canonical chat visual language and extract reusable primitives into shared chat UI components. Route-level business logic remains separate:

- `/chat`: workspace threads, streaming, RAG toggles, persistence.
- `/search`: semantic query execution and result adaptation.

Both routes render through a common view model and common UI primitives to eliminate visual and behavioral drift.

## Shared Component Contract

Define and use a shared contract for both routes:

- `ChatShell`
- `ChatBubble`
- `ChatComposer`
- `ConversationRail`
- `RightPanel` (citations/context/details)

Shared message view model:

- `id`
- `role` (`user` | `assistant`)
- `content`
- `timestamp`
- `modelName?`
- `citations?`
- `isStreaming?`
- `streamingContent?`

## UX Consistency Rules

1. Same spacing rhythm for headers, bubble padding, and message gaps.
2. Same role badge and metadata row placement.
3. Same bubble geometry, color tokens, and hover affordances.
4. Same action positions for copy/retry/feedback.
5. Same streaming and typing indicators.
6. Same empty-state information architecture.
7. Same keyboard behavior:
   - `Enter` sends
   - `Shift+Enter` inserts newline
   - `/` focuses composer when not typing in an input

## Data Flow

### `/chat`

- Keep existing thread and message persistence flow.
- Keep existing SSE/local model streaming path.
- Map route messages into shared view model and render with shared primitives.

### `/search`

- Keep existing search request/response flow.
- Adapt user query + synthesized answer + citations to shared view model.
- Render in the same shell and bubble/composer system as `/chat`.

### Citation Behavior

- Normalize citation shape once before rendering.
- Preserve click-to-panel and click-to-document behavior parity between both routes.

## Error Handling

- Keep route-specific error states but render with a shared visual pattern.
- Maintain graceful empty state, loading state, and retry CTAs.
- Ensure streaming interruptions leave UI in a stable stopped state.

## Accessibility and Responsiveness

- Preserve keyboard navigation and focus visibility.
- Keep composer controls reachable and readable on small screens.
- Maintain sufficient contrast for all badges, metadata, and interactive states.

## Testing Strategy

1. Unit tests:
   - View model adapters (`chat -> view model`, `search -> view model`).
   - Citation normalization and index extraction.
2. Component tests:
   - `ChatBubble` variants (user/assistant/streaming).
   - `ChatComposer` keyboard behavior and disabled/send states.
3. Route smoke checks:
   - `/chat` and `/search` both render shared shell structure.
   - Shared action controls and citation panel interactions exist and behave consistently.

## Acceptance Criteria

1. `/chat` and `/search` use the same bubble/composer visual system.
2. Message metadata and actions appear in consistent positions on both routes.
3. Composer keyboard shortcuts behave identically on both routes.
4. Citation interactions are visually and behaviorally consistent.
5. No regression in existing `/chat` thread/message behavior.

