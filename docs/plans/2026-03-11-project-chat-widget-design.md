# Project Chat Widget — Collapsible Quick Chat Panel

**Date:** 2026-03-11
**Status:** Approved
**Approach:** Standalone Floating Widget (Approach A)

## Summary

A SciSpace-style collapsible chat widget on the project detail page (`/projects/[id]`). Floating button bottom-right opens a compact overlay panel for quick RAG-powered Q&A against project documents/notes. Coexists with the existing Chat tab — widget is for quick questions, Chat tab remains for full thread management.

## Scope

- **Where:** Project detail page only (`/projects/[id]`)
- **What:** Unified chat input — RAG-aware of project documents, also handles general questions
- **Toggle:** Floating action button (bottom-right), panel slides up as overlay
- **Persistence:** Panel stays open across tab switches within the project. Messages live in React state (session only).

## Component Structure

```
ProjectChatWidget/
├── ProjectChatWidget.tsx      — Root: FAB + panel, manages open/close
├── ChatPanel.tsx              — Fixed-position slide-up panel container
├── ChatContextBar.tsx         — "Chatting with:" label + toggleable context chips
├── ChatMessageList.tsx        — Scrollable message list, auto-scroll to bottom
├── ChatMessageItem.tsx        — Single message (user/AI, markdown, citations)
└── ChatPanelInput.tsx         — Compact text input + send button
```

**Mount point:** Inside `app/(dashboard)/projects/[id]/page.tsx`, at page level outside the tab content area.

## State Management

A `useProjectChatWidget` hook (React state, not Zustand):

| State          | Type            | Purpose                               |
| -------------- | --------------- | ------------------------------------- |
| `isOpen`       | `boolean`       | Panel visibility                      |
| `messages`     | `Message[]`     | Current conversation                  |
| `contextChips` | `ContextChip[]` | Available items with `enabled` toggle |
| `isStreaming`  | `boolean`       | AI currently responding               |
| `activeTab`    | `string`        | Synced from parent for chip updates   |

## UX Behavior

### Floating Action Button

- Fixed: `bottom: 24px, right: 24px`
- Circular, chat icon, primary accent color
- Badge for unread responses when panel is closed during streaming
- Click toggles panel

### Panel

- Fixed: `bottom: 88px, right: 24px`
- Size: `380px wide x 520px tall`
- Slide-up animation (200ms ease-out), overlay (no content push)
- Close via: FAB toggle, X button, or Escape key
- Clicking outside does NOT close (prevents accidental context loss)

### Tab Switch Behavior

- Panel stays open across tab switches
- Messages persist in session
- Context chips auto-update to reflect new tab's resources
- Label updates: "Chatting with: Documents (3)" -> "Chatting with: Notes (5)"

### Context Chips

- Horizontally scrollable row below panel header
- Auto-populated from current tab's resources
- Toggleable: filled (active) / outlined (inactive)
- "All" chip for bulk toggle
- Tabs with no specific resources show project-level context

## Data Flow

### Sending Messages

- Endpoint: `POST /api/v1/projects/{id}/chat/start`
- Payload includes enabled context chip IDs for scoped RAG retrieval
- Each widget session creates a lightweight thread (not linked to Chat tab)

### Context Chip Data Source

| Active Tab                       | Chips Source                        |
| -------------------------------- | ----------------------------------- |
| Documents                        | `projectStore.documents[projectId]` |
| Notes                            | `projectStore.notes[projectId]`     |
| Bibliography                     | Bibliography entries                |
| Other (Drafts, Matrix, Pipeline) | All project documents (default)     |

### Response Handling

- Stream tokens via SSE/WebSocket if available, else typing indicator
- AI responses include citation markers referencing enabled context documents

### Session Lifecycle

- Messages in React state — cleared on project navigation
- No backend persistence beyond chat endpoint defaults

## Visual Design

### Panel Styling

- Background: `hsl(var(--background))`, border: `hsl(var(--border))`
- Header: "Quick Chat" + context indicator + close button
- User messages: right-aligned, `hsl(var(--primary))` accent
- AI messages: left-aligned, `hsl(var(--muted))` background
- Input: single-line, expands to 3 lines max
- Clean conversational style (no terminal/monospace aesthetic)

### Context Chips

- Active: `hsl(var(--primary))` filled, white text
- Inactive: `hsl(var(--border))` outlined, muted text
- Truncated at ~20 chars with tooltip

### Animations

- Open: slide up + fade in (200ms ease-out)
- Close: slide down + fade out (150ms ease-in)
- FAB: subtle scale pulse on first load
- Messages: fade-in from bottom

### Responsive

- Desktop: 380x520px fixed panel
- Tablet (<768px): full-width panel
- Mobile: full-screen sheet, close with swipe or X

## Accessibility

- FAB: `aria-label="Open project chat"`
- Panel: `role="dialog"`, `aria-labelledby`
- Focus trap when open
- Escape closes panel
- Messages: `role="log"`, `aria-live="polite"`

## Relationship to Existing Chat Tab

- **Coexist:** Widget for quick questions, Chat tab for thread management
- **Independent:** Widget has its own state, does not modify Chat tab threads
- **No overlap:** Widget conversations are ephemeral session-only; Chat tab manages persistent threads
