# Chat Page UI Refresh Implementation Plan

> **ARCHIVED 2026-04-21.** This UI refresh was rolled back because the implementation bypassed the NOUS theme system — it hardcoded RGBA gradients, shadows, and radii (`rgba(255,255,255,0.96)`, `shadow-[0_24px_60px_...]`, `rounded-[26px]`) in the chat components instead of using `var(--terminal-*)` / `var(--nous-*)` CSS variables. Result: chat surfaces rendered cream/beige while the rest of the app stayed dark, breaking the light/dark theme toggle (`next-themes`). If any idea here is worth keeping, re-do it as a theme-aware, committed PR using CSS vars only.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh the dashboard chat page so the conversation canvas, composer, sidebar, and right rail feel like one cohesive NOUS workspace instead of separate floating panels.

**Architecture:** Keep the existing chat route structure and state flow intact, and focus on visual/layout refinements in the page shell and existing chat components. Add a small set of targeted regression tests that assert the new page landmarks and composition surfaces before updating component markup and styling.

**Tech Stack:** Next.js app router, React, Tailwind CSS, Framer Motion, Jest, React Testing Library

---

### Task 1: Lock the refreshed UI structure with failing tests

**Files:**
- Modify: `frontend/src/components/chat/__tests__/ChatHeader.test.tsx`
- Modify: `frontend/src/components/chat/__tests__/ChatSidebar.test.tsx`
- Modify: `frontend/src/components/chat/__tests__/ChatInput-streaming.test.tsx`

**Step 1: Write the failing tests**

- Add a header test that expects a new “Conversation Studio” page label and the command palette trigger to remain present.
- Add a sidebar test that expects a “Session Navigator” label and a workspace summary card treatment.
- Add a composer test that expects a new helper/status strip and a “Ready for retrieval” state when RAG is enabled.

**Step 2: Run tests to verify they fail**

Run:

```bash
pnpm jest src/components/chat/__tests__/ChatHeader.test.tsx --runInBand
pnpm jest src/components/chat/__tests__/ChatSidebar.test.tsx --runInBand
pnpm jest src/components/chat/__tests__/ChatInput-streaming.test.tsx --runInBand
```

Expected: FAIL because the current UI does not expose the new landmarks or helper strip.

### Task 2: Refresh the shell and sidebar presentation

**Files:**
- Modify: `frontend/src/components/chat/ChatHeader.tsx`
- Modify: `frontend/src/components/chat/ChatSidebar.tsx`
- Modify: `frontend/app/(dashboard)/chat/layout.tsx`

**Step 1: Write minimal implementation**

- Update the header to introduce a stronger page identity and more intentional command/search framing.
- Update the sidebar to read as a navigator surface with a clearer section heading and stronger active conversation treatment.
- Refine the chat layout container so the main conversation canvas and right rail share a more cohesive background and border system.

**Step 2: Run focused tests**

Run:

```bash
pnpm jest src/components/chat/__tests__/ChatHeader.test.tsx --runInBand
pnpm jest src/components/chat/__tests__/ChatSidebar.test.tsx --runInBand
```

Expected: PASS.

### Task 3: Strengthen conversation and composer hierarchy

**Files:**
- Modify: `frontend/app/(dashboard)/chat/page.tsx`
- Modify: `frontend/src/components/chat/shared/TerminalChatBubble.tsx`
- Modify: `frontend/src/components/chat/ChatInput.tsx`

**Step 1: Write minimal implementation**

- Turn the message column into a clearer canvas with better spacing, framing, and scroll affordances.
- Upgrade message cards so user and assistant turns feel intentionally different but still part of one visual system.
- Rework the composer into a grounded studio panel with clearer status/help text and a stronger submit area.

**Step 2: Run focused tests**

Run:

```bash
pnpm jest src/components/chat/__tests__/ChatInput-streaming.test.tsx --runInBand
```

Expected: PASS.

### Task 4: Verify end-to-end surface health

**Files:**
- Verify only: `frontend/app/(dashboard)/chat/page.tsx`
- Verify only: `frontend/src/components/chat/ChatHeader.tsx`
- Verify only: `frontend/src/components/chat/ChatSidebar.tsx`
- Verify only: `frontend/src/components/chat/ChatInput.tsx`
- Verify only: `frontend/src/components/chat/shared/TerminalChatBubble.tsx`
- Verify only: `frontend/app/(dashboard)/chat/layout.tsx`

**Step 1: Run complete verification**

Run:

```bash
pnpm jest src/components/chat/__tests__/ChatHeader.test.tsx --runInBand
pnpm jest src/components/chat/__tests__/ChatSidebar.test.tsx --runInBand
pnpm jest src/components/chat/__tests__/ChatInput-streaming.test.tsx --runInBand
pnpm tsc --noEmit
```

Expected: PASS with exit code 0.
