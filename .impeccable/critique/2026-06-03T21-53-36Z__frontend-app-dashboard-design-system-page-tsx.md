---
target: design-system
total_score: 29
p0_count: 1
p1_count: 2
timestamp: 2026-06-03T21-53-36Z
slug: frontend-app-dashboard-design-system-page-tsx
---
## /impeccable critique — Design System showcase (`app/(dashboard)/design-system/page.tsx`)

**Register:** product · **Detector:** clean (`[]`, no automated anti-patterns) · **Band:** Good (29/40)

This page is a *showcase* of the NOUS UI kit (four surfaces: primitives, workspace, chat, sources). It is meant to demonstrate components, not to be a live working surface — that context matters for how I scored "honest states" and "user control." It reads as genuinely scholarly-warm: one Sol-gold accent on warm-dark, Source Serif body for prose, Inter for UI, citation pills, an honest agent step-list. It does not read as AI slop. The gap between this and Excellent is craft-level: accessibility on gold, decorative-only affordances, and hover logic that lives in JS instead of CSS.

### Nielsen heuristic scores

| # | Heuristic | Score | Note |
|---|-----------|:----:|------|
| 1 | Visibility of system status | 3 | Agent step-list (done/active/pending) with pulsing dot is excellent and honest. But the nav's "active tab" is driven by section `onMouseEnter`, so status tracks the cursor, not the viewport — misleading. No real loading/skeleton states (acceptable for a showcase, noted). |
| 2 | Match between system & real world | 4 | Language is plain, sentence-case, scholarly: "Good morning, Maya", "2 agents · 4 sources", relevance %, "p. 3". Citations map 1:1 with sources. Exactly the expert-colleague register PRODUCT.md asks for. |
| 3 | User control & freedom | 2 | It's a gallery: `onInvite={() => undefined}`, composer clears on submit with no destination, chat action chips ("Trace reasoning", "Save to notebook") are inert, sidebar items do nothing. No back/undo/dismiss anywhere. Fine as a demo, but nothing is actually controllable. |
| 4 | Consistency & standards | 3 | Strong token discipline (`--nous-*` everywhere, shadcn variants). But inconsistent interactivity contract: thread cards got `role="button"`+tabIndex+focus ring, yet visually-identical sidebar/facet rows did not. Buttons use the shared variant system; the chat action chips and composer chips are hand-rolled duplicates of the same pill. |
| 5 | Error prevention | 3 | Composer guards empty submit (`if (!value.trim()) return`). Inputs have disabled states. No destructive actions on the page to mis-fire, so little exposure — but also nothing demonstrating the human-in-the-loop confirm pattern PRODUCT.md treats as core. |
| 6 | Recognition over recall | 4 | Everything is on-screen and labelled: numbered eyebrows, citation indices, source provenance line, relevance pill, step labels. No hidden state to remember. |
| 7 | Flexibility & efficiency | 3 | Power-user reasonable: tabular-nums on counts, keyboard-reachable thread cards. But no keyboard path to the nav-driven sections, no shortcuts, and the JS hover handlers force a reflow/style-write on every pointer move across nav, composer, and each source card. |
| 8 | Aesthetic & minimalist design | 4 | This is the strength. One accent hue, restrained, warm-dark, deliberate rhythm (varied section padding 56/64/48px), serif prose for the reply. No gradient text, no glass, no side-stripes, no hero-metric template. Genuinely handsome. |
| 9 | Error recovery | 2 | No error states shown at all — no `role="alert"`, no failed-retrieval or empty-source case. Defensible for a primitives gallery, but the kit is supposed to *show* honest states and this surface omits the error/empty trio entirely. |
| 10 | Help & documentation | 1 | The prose explains *implementation* ("resolves through CSS variables", "dark mode flips", file paths) — developer docs, not user help. No usage guidance for the components themselves. For a design-system page this is the weakest dimension; a DS page should document each component's props/variants/do's-and-don'ts. |

**Total: 29/40 — Good.**

### Anti-patterns verdict (NOUS banned list)
- Terminal costume — **clean** on this page. (Note: `globals.css` lines 1509-1522 still carry dead `.crt-flicker/.phosphor-pulse/.scan-lines/.radar-sweep` rules from the removed skin; not referenced here, but it's costume residue that should be deleted from the codebase.)
- >1 accent hue — **clean.** Sol gold only; status green/amber/red used semantically, not as second brand hue.
- Hardcoded hex / `text-gray-*` — **mostly clean**, two leaks: `text-white` on gold buttons/avatar (button.tsx, nav avatar) and literal `#FFFFFF` in `nous-source-card.tsx`. DESIGN.md bans hardcoded hex in components.
- Gradient text / glassmorphism-default / side-stripe borders / hero-metric / identical card grids — **clean.** (The nav uses `backdrop-blur-md` but over a 90% opaque bg, so it's not decorative glass.)
- Em dashes in copy — **clean** (uses `·` separators and "to" in "60 to 80%").
- AI-slop verdict: **No.** Distinct, considered, brand-coherent. Would not read as "AI made this."

### Priority issues

**P0 — White text on Sol gold fails WCAG AA.**
- *What:* `text-white` / `#FFFFFF` sits on `--nous-sol #d4a039` in: the `accent` & `erebus`→ no, specifically the `accent` button, composer Send button, nav avatar initials, and the high-relevance score pill in `nous-source-card`. White on `#d4a039` is ≈2.1:1 — below the 3:1 large-text and 4.5:1 normal-text AA floors. The percentage pill text is small and clearly fails.
- *Why:* PRODUCT.md/DESIGN.md target WCAG 2.1 AA and call out "maintain contrast on warm-gold-over-dark surfaces." Gold is the identity color, so this is the most visible failure.
- *Fix:* Use Erebus `#0a0a0e` (near-black) text on Sol-gold fills — dark-on-gold easily clears AA and is more "considered" anyway. For the score pill, dark text on gold; keep the low-relevance pill's `sol-safe` on Aurum (that one passes). Replace `text-white`/`#FFFFFF` with a token (`--nous-erebus` or `--nous-on-accent`).
- *Command:* `/impeccable harden --a11y`

**P1 — Decorative affordances that lie (sidebar & facet rows).**
- *What:* `SidebarItem` renders `cursor: pointer` + hover fill, signalling "clickable," but it's a plain `<div>` with no `role`, `tabIndex`, `onClick`, or focus state. The workspace and search facets are built from these. Meanwhile the thread cards correctly got `role="button"`+focus ring — so the page contradicts itself.
- *Why:* Sam (a11y) cannot reach or operate them; Alex (power user) clicks and nothing happens. It also violates the consistency contract.
- *Fix:* If they're meant to be interactive, make `SidebarItem` a `<button>`/link with `:focus-visible` ring and real handler; if it's a pure visual demo, drop `cursor-pointer` and the hover fill so it doesn't promise interaction. Pick one and apply it everywhere.
- *Command:* `/impeccable harden --interactive-states`

**P1 — Hover/active logic lives in JS instead of CSS.**
- *What:* `nous-nav`, `nous-chat-composer`, and `nous-source-card` set colors/transforms/shadows via `onMouseEnter`/`onMouseLeave` (and the form uses `onFocus`/`onBlur` to restyle). The page's active-tab is set by section `onMouseEnter`.
- *Why:* (1) Pointer-only — keyboard focus never triggers the lift/border change, so `:focus-visible` parity is lost; (2) writes inline styles on every pointer event (layout-thrash on the source list); (3) the "scroll-spy" nav is fake — it follows the mouse, not scroll position, so it's wrong the moment you scroll without hovering.
- *Fix:* Move hover/focus to CSS (`:hover`, `:focus-visible`, `:focus-within` on the composer) — the shared `Button`/`Card` already do this correctly, so these one-offs are regressions. For active-tab use a real IntersectionObserver scroll-spy.
- *Command:* `/impeccable harden --interactive-states`

**P2 — A design-system page documents implementation, not usage.**
- *What:* Header/footer prose talks about CSS variables, `.dark` flipping, and file paths. There's no per-component documentation (when to use `accent` vs `erebus`, prop tables, anti-pattern callouts).
- *Why:* Help/docs scored 1. A DS reference is itself a help surface; engineers landing here can't learn the component contract.
- *Fix:* Add a short "when to use" line + prop list per primitive; keep the file-path note in a collapsed "Implementation" aside.
- *Command:* `/impeccable clarify --copy`

**P3 — Inline `style` objects everywhere instead of helper classes.**
- *What:* Nearly every text element carries an inline `style={{ fontFamily: 'var(--nous-font-*)', fontSize, color }}` block. DESIGN.md explicitly says "Prefer `.nous-ui`/`.nous-body`/`font-[var(--nous-font-*)]` over inline `style`."
- *Why:* Verbose, easy to drift, defeats the helper-class system that exists precisely for this. Not a user-facing bug; a maintainability/consistency smell.
- *Fix:* Replace inline type blocks with `.nous-overline`, `.nous-h2`, `.nous-body`, `.nous-caption` etc.
- *Command:* `/impeccable distill`

### Persona red flags
- **Alex (power user / researcher):** Clicks the nav tabs expecting to jump — they're `#hash` anchors with a hover-faked active state, so the highlight lies as soon as he scrolls. Clicks sidebar workspaces / facets — dead. The "Trace reasoning" and "Save to notebook" chips, the exact provenance affordances he'd reach for, do nothing. He'd read this correctly as a mock.
- **Sam (keyboard / screen-reader):** Can Tab to thread cards (good) but the lift/border feedback never fires on keyboard focus (JS-only hover), so focused state looks inert. Sidebar/facet rows are unreachable. Gold buttons + the score pill fail contrast. Avatar has a label but the inert "Invite" button leads nowhere. Mixed: the bones are accessible, the polish isn't.

### What's working (strengths)
1. **Brand identity is correct and confident.** One Sol-gold accent on warm-dark, Source Serif for the reply prose, Inter for UI, classical/calm voice. It is the Observatory, not cyberpunk and not SaaS-cream — exactly the target.
2. **Provenance is first-class.** Citation pills map 1:1 to numbered source cards with title, author, file, page, and an extractive excerpt plus relevance score. This is the product's whole thesis and it's rendered honestly.
3. **The agent status card is a model honest-state component.** Real done/active/pending steps, strikethrough on completed, a single pulsing dot (and the global `prefers-reduced-motion` guard at `globals.css:1540` neutralizes it). No fake HUD theatrics.

### Minor observations
- Nav uses `backdrop-blur-md` over a 90%-opaque bg — fine, but on a fully opaque header the blur is a no-op cost; consider dropping it.
- `nous-source-card` source line uses `--nous-font-mono` (JetBrains) for the citation — borderline against "do not use mono as decorative technical shorthand." A filename/citation is arguably legitimate mono use; keep an eye on it.
- Card primitive demo wraps content in a `<Card>` then an empty `<div className="px-6 pb-6" />` — dead spacer, drop it.
- `SidebarItem` count of `0` ("Calls", 0) renders a faint zero; fine, but real empty facets usually disable/dim the whole row.

### Questions
1. Is this page intended to stay a static showcase, or is it a stepping stone to wiring real handlers? That decision flips whether the "decorative affordance" issues are P1 or cosmetic.
2. Should the gold CTA convention be **dark-on-gold** (recommended, passes AA) project-wide? If so, the fix belongs in the shared `button.tsx`/`badge.tsx` variants, not here.
3. The dead `.crt-flicker/.phosphor-pulse/.scan-lines` rules in `globals.css` — safe to delete as terminal-costume residue?
