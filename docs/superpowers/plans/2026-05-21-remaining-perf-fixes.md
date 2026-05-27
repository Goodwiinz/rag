# Remaining Performance Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lazy-load the syntax highlighter bundle (react-syntax-highlighter/Prism) across 4 files, and split the 611-line homepage into maintainable sub-components.

**Architecture:** Dynamic `import()` for syntax highlighter with a loading fallback. Homepage extraction into section components that can be independently maintained.

**Tech Stack:** Next.js 15, React 18, framer-motion, react-syntax-highlighter

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/components/agent-chat/AgentMarkdownRenderer.tsx` | Modify | Dynamic import SyntaxHighlighter |
| `frontend/src/components/chat/MessageBubble.tsx` | Modify | Dynamic import SyntaxHighlighter |
| `frontend/src/components/chat/CitationRenderer.tsx` | Modify | Dynamic import SyntaxHighlighter |
| `frontend/src/components/llm-chat/CodeBlock.tsx` | Modify | Dynamic import SyntaxHighlighter |
| `frontend/app/page.tsx` | Modify | Slim orchestrator importing section components |
| `frontend/src/components/landing/HeroSection.tsx` | Create | Hero section (nav + hero visual) |
| `frontend/src/components/landing/CapabilitiesSection.tsx` | Create | Core capabilities bento grid |
| `frontend/src/components/landing/FooterSection.tsx` | Create | Footer + CTA metrics section |

---

### Task 1: Lazy-load react-syntax-highlighter in all 4 files

**Files:**
- Modify: `frontend/src/components/agent-chat/AgentMarkdownRenderer.tsx`
- Modify: `frontend/src/components/chat/MessageBubble.tsx`
- Modify: `frontend/src/components/chat/CitationRenderer.tsx`
- Modify: `frontend/src/components/llm-chat/CodeBlock.tsx`

In each file, replace the static imports:

```tsx
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
```

With a Next.js dynamic import:

```tsx
import dynamic from 'next/dynamic';

const SyntaxHighlighter = dynamic(
  () => import('react-syntax-highlighter/dist/esm/prism').then((mod) => mod.default),
  {
    loading: () => <pre className="p-4 rounded bg-[var(--terminal-bg)] text-xs font-mono overflow-x-auto"><code>Loading...</code></pre>,
    ssr: false,
  }
);
```

And import the style lazily inside the component that renders SyntaxHighlighter — since dynamic import handles the main component, the style can stay as a static import (it's just a JSON object, not a heavy module). Actually, keep the style import as-is since it's tree-shakeable.

**Note for CodeBlock.tsx**: it uses `vscDarkPlus` instead of `oneDark`. Keep the same style import, just change the SyntaxHighlighter import.

- [ ] **Step 1: Apply dynamic import to all 4 files**

Read each file, replace the `Prism as SyntaxHighlighter` import with the dynamic version. Keep the style import.

- [ ] **Step 2: Verify and commit**

```bash
cd /home/clawdbot/rag-clean/frontend && npx tsc --noEmit 2>&1 | head -30
```

```bash
cd /home/clawdbot/rag-clean && git add frontend/src/components/agent-chat/AgentMarkdownRenderer.tsx frontend/src/components/chat/MessageBubble.tsx frontend/src/components/chat/CitationRenderer.tsx frontend/src/components/llm-chat/CodeBlock.tsx
git commit -m "fix(perf): lazy-load react-syntax-highlighter via dynamic import"
```

---

### Task 2: Split homepage into section components

**Files:**
- Modify: `frontend/app/page.tsx`
- Create: `frontend/src/components/landing/HeroSection.tsx`
- Create: `frontend/src/components/landing/CapabilitiesSection.tsx`
- Create: `frontend/src/components/landing/FooterSection.tsx`

The homepage is 611 lines of JSX. While it must remain `'use client'` (framer-motion animations everywhere), splitting into section components improves maintainability.

- [ ] **Step 1: Create `HeroSection.tsx`**

Extract from page.tsx:
- The `Badge` component
- The `TechTicker` component
- The nav bar
- The hero section (from `{/* Hero Section */}` through `{/* Ecosystem Ticker */}`)

Props: `isAuthenticated: boolean`, `scrollOpacity: MotionValue<number>`

- [ ] **Step 2: Create `CapabilitiesSection.tsx`**

Extract from page.tsx:
- The `FeatureCard` component
- The `{/* Core Capabilities - Bento Grid */}` section

No props needed (pure presentational).

- [ ] **Step 3: Create `FooterSection.tsx`**

Extract from page.tsx:
- The `{/* System Metrics CTA */}` section
- The `{/* Footer */}` section

No props needed.

- [ ] **Step 4: Slim down page.tsx**

Replace the extracted sections with imports:

```tsx
'use client';

import { useAuth } from '@/hooks/useAuth';
import { useScroll, useTransform } from 'framer-motion';
import { HeroSection } from '@/components/landing/HeroSection';
import { CapabilitiesSection } from '@/components/landing/CapabilitiesSection';
import { FooterSection } from '@/components/landing/FooterSection';

export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const { scrollYProgress } = useScroll();
  const opacity = useTransform(scrollYProgress, [0, 0.2], [1, 0]);

  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] relative overflow-x-hidden flex flex-col noise-texture selection:bg-[var(--phosphor-green)] selection:text-[var(--terminal-bg)]" suppressHydrationWarning>
      {/* Dynamic Background */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(212,160,57,0.03),transparent_50%)]" />
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--terminal-border)] to-transparent opacity-20" />
        <div className="hidden md:block absolute inset-0 terminal-grid opacity-[0.03]" />
      </div>

      <HeroSection isAuthenticated={isAuthenticated} scrollOpacity={opacity} />
      <CapabilitiesSection />
      <FooterSection />
    </div>
  );
}
```

- [ ] **Step 5: Verify and commit**

```bash
cd /home/clawdbot/rag-clean/frontend && npx tsc --noEmit 2>&1 | head -30
```

```bash
cd /home/clawdbot/rag-clean && git add frontend/app/page.tsx frontend/src/components/landing/
git commit -m "refactor(landing): split homepage into section components"
```

---

### Task 3: Type-check, test, and push

- [ ] **Step 1: Full type-check**

```bash
cd /home/clawdbot/rag-clean/frontend && npx tsc --noEmit
```

- [ ] **Step 2: Run tests**

```bash
cd /home/clawdbot/rag-clean/frontend && npx vitest run --passWithNoTests 2>&1 | tail -20
```

- [ ] **Step 3: Push**

```bash
cd /home/clawdbot/rag-clean && git push origin develop
```
