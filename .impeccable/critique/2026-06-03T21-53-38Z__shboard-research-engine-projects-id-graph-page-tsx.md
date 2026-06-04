---
target: graph
total_score: 28
p0_count: 1
p1_count: 2
timestamp: 2026-06-03T21-53-38Z
slug: shboard-research-engine-projects-id-graph-page-tsx
---
## /impeccable critique — Evidence Map (`/research-engine/projects/[id]/graph`)

**Register:** product · **Detector:** clean (`[]`, exit 0 — no banned anti-patterns) · **AI-slop:** No

The route file is a 5-line wrapper (`<EvidenceMap projectId={id}/>` inside a `max-w-7xl` container); all real surface lives in `src/components/research-engine/EvidenceMap.tsx`. Critique targets that component.

---

### Heuristic scores (Nielsen 10)

| # | Heuristic | Score | Notes |
|---|-----------|:----:|-------|
| 1 | Visibility of system status | 3 | Real skeleton with `aria-busy`/`aria-live` + `sr-only` "Loading evidence map" — genuinely good. Loses a point because a failed fetch shows the *empty* state, so status is actively dishonest on error. |
| 2 | Match between system & real world | 4 | Vocabulary is exactly the researcher's: "Research question / Sub-question / Evidence / Source", "Run a research blueprint". Sentence-case, no hype. On-voice. |
| 3 | User control & freedom | 2 | Back button + close-panel button are good. But no zoom/pan/reset on the graph, no way to deselect except the X, no Escape-to-close, no keyboard path into the canvas at all. |
| 4 | Consistency & standards | 3 | Tokenized throughout (`text-foreground`, `bg-card`, `border-border`, `--nous-sol/helios/parchment`), consistent radius/shadow, lucide icons. Minor: one inline `style={{ fontFamily: 'var(--nous-font-body)' }}` instead of the `.nous-body` helper DESIGN.md prefers. |
| 5 | Error prevention | 3 | Read-only view, little to get wrong. Label truncation and `nodeById` guards prevent broken edges. Nothing destructive. |
| 6 | Recognition over recall | 3 | Legend maps color+size to type (desktop only). Detail panel echoes the type chip. But the legend is `hidden md:flex` — on mobile the color encoding is unexplained, forcing recall. |
| 7 | Flexibility & efficiency | 2 | No keyboard shortcuts, no zoom, no search/filter, no fit-to-view. A power researcher with a 200-node graph cannot navigate it efficiently; the fixed-ring layout actively fights large corpora. |
| 8 | Aesthetic & minimalist | 4 | This is the strongest axis. One warm-gold family (Sol → Helios → Parchment → muted), no gradient text, no glassmorphism, no side-stripe borders, no hero-metric block, no mono costume. Calm, scholarly, restrained. Exactly the Observatory brief. |
| 9 | Help users recover from errors | 1 | The error block (lines 234–256) is well-designed — `role="alert"`, Mars icon, Retry button — but it is **unreachable**. `fetchGraph`'s `catch` (line 173) does `setGraphData({ nodes: [], edges: [] })`, never `setError`. So a 500, an auth failure, and a genuinely empty project all render identically as "No evidence yet". The recovery path can never fire. |
| 10 | Help & documentation | 3 | The empty state tells you *how* to populate the graph ("Run a research blueprint…"), which is the right inline-help instinct. No per-node-type explanation or "how to read this graph" affordance, but acceptable for an expert audience. |

**Total: 28 / 40 — Good** (low end). Polished visual layer and honest *happy-path* states sitting on top of a dishonest error path and a graph engine that does not scale or accept keyboard input.

---

### Anti-patterns verdict

Detector clean and a manual pass agrees — this resists AI-slop:
- No gradient text, no `bg-clip-text`.
- No glassmorphism-as-default, no `backdrop-blur` chrome.
- No side-stripe accent borders.
- No hero-metric template, no identical icon-card grid.
- No `--terminal-*` / phosphor / "Neural/Synthetic" copy, no mono-everywhere.
- Single accent hue (gold family only); `hsl(var(--muted-foreground))` and `var(--nous-parchment)` are neutrals, not a second hue.
- No hardcoded hex, no `text-gray-*`.
- No em dashes in user-facing copy.

**One legitimate token note (not slop):** `--nous-mars`, `--nous-parchment`, `--nous-sol/helios` used directly via `style`/arbitrary classes. DESIGN.md sanctions data-viz palettes as the *only* place raw graph color is allowed, so the node colors are fine — but the legend swatch and node fills lean on inline `style` objects where a tokenized class would be cleaner.

---

### Cognitive load (8-item)

1. **Visual noise** — Low. Lots of negative space, one accent. Good.
2. **Reading burden** — Low. Short labels, truncated node text.
3. **Decision density** — Low on happy path; click a node, read panel.
4. **Memory burden** — Medium. Mobile users lose the legend, must remember color meaning.
5. **Motion/distraction** — Low. Only `animate-pulse` skeletons; no `prefers-reduced-motion` guard but pulse is mild.
6. **Hierarchy clarity** — Medium. Node *size* encodes type, but the layered ring is only legible at small N; at scale it reads as noise (violates "density with rhythm").
7. **Affordance clarity** — Medium-low. Nodes are `cursor-pointer` with no hover state and no focus ring; nothing signals "click me / I'm selectable".
8. **State legibility** — Medium. Loading and empty are clear; error is invisible (collapses to empty).

---

### Persona red flags

**Alex (power user / dense data):**
- 200-node project → the fixed-radius rings (`r = 120/220/310` on a 700×700 viewBox) push nodes outside the frame and stack labels on top of each other. No zoom, no pan, no fit-to-view, no collision avoidance. The "force-layout" comment is aspirational; it is a static polar layout. Alex cannot actually read a real evidence graph here.
- No filter/search/highlight-by-type. To find one sub-question among forty, Alex must visually scan overlapping circles.

**Sam (accessibility):**
- **Keyboard:** nodes are `<g onClick>` with no `tabindex`, no `role="button"`, no `onKeyDown`, no focus-visible ring. The entire interaction model is mouse-only → WCAG 2.1.1 (Keyboard) failure. The canvas has `role="img"` + label, which is correct for a *static* image but wrong for an *interactive* one.
- **Announcement:** selecting a node mutates a sibling panel with no `aria-live`/focus move, so a screen-reader user gets no feedback that anything happened.
- **Color-on-mobile:** legend is `hidden md:flex`; below `md` the only type cue is color+size with no key — borderline "meaning by color alone."
- Skeleton/`sr-only`/`aria-busy` and `aria-label`s on icon buttons are done right — credit where due.

---

### Priority issues

**P0 — Swallowed errors make failure indistinguishable from empty**
- *What:* `fetchGraph` catch (EvidenceMap.tsx:173–176) sets `{ nodes: [], edges: [] }` instead of `setError(...)`. The whole error UI (234–256) is dead code; `error` is never truthy.
- *Why:* Violates NOUS "Honest states" and "the system tells the truth about what it is doing." A researcher with a real 500 or auth drop is told "No evidence yet — run a blueprint," which is a lie that will send them down the wrong path. This is the single most important fix.
- *Fix:* In the catch, distinguish "endpoint 404 / not-built-yet" from real failures. For genuine errors, `setError('Could not load the evidence map.')` so the existing Retry block renders. Keep empty data only for an actual 200-with-empty response.
- *Command:* `/impeccable harden` (error/empty/loading state honesty pass).

**P1 — Graph is keyboard-inaccessible**
- *What:* Selectable nodes have no tab order, role, key handler, or focus ring (342–375).
- *Why:* WCAG 2.1 AA (2.1.1, 2.4.7) fail; PRODUCT.md explicitly promises "full keyboard navigation … canvas graph included."
- *Fix:* Make each node a focusable `role="button"` with `tabIndex={0}`, `aria-label` = type + label, `onKeyDown` for Enter/Space, and an SVG focus outline. Add `aria-live="polite"` to the detail panel and move focus to its heading on open; close on Escape.
- *Command:* `/impeccable a11y` (keyboard + announce canvas interactions).

**P1 — Layout does not survive real data**
- *What:* Static polar rings with hardcoded radii, no zoom/pan, no collision handling, fixed 700×700 viewBox; labels overlap and nodes clip past ~8–10 per ring (73–147, 305–376).
- *Why:* This is a research instrument for corpora; "density with rhythm" turns into unreadable overlap. The component's value collapses exactly when the graph becomes worth looking at.
- *Fix:* Add zoom/pan (wheel + drag, or `react-zoom-pan-pinch` / d3-zoom) with a "fit to view" reset; either run an actual force simulation or add label collision/decluttering and scale radii to node count.
- *Command:* `/impeccable shape` (information architecture + scale behavior of the viz).

**P2 — Detail panel lacks dismissal + focus affordances**
- *What:* Panel closes only via the X button; no Escape, no focus management, no announcement (380–433).
- *Why:* Recognition/control friction and an a11y gap for keyboard users.
- *Fix:* Escape-to-close, return focus to the originating node, `aria-live` region.
- *Command:* `/impeccable polish`.

**P2 — Legend hidden on mobile; node colors then unexplained**
- *What:* `hidden md:flex` (284) drops the only key for the color/size encoding on small screens.
- *Why:* Forces recall; borderline color-only meaning.
- *Fix:* Move the legend into a collapsible/below-graph block on mobile rather than removing it, or surface type via the always-present detail chip.
- *Command:* `/impeccable adapt` (responsive).

**P3 — Minor token/voice polish**
- Inline `fontFamily: var(--nous-font-body)` (403) → use `.nous-body`. No `prefers-reduced-motion` guard on `animate-pulse`. `key={`edge-${i}`}` uses array index. All low-stakes.
- *Command:* `/impeccable polish`.

---

### What's working (strengths)

1. **Genuinely restrained, on-brand surface.** Single warm-gold family on `bg-card`/`border-border`, no ornament, no slop. This is what "the Observatory, not cyberpunk, not SaaS-cream" is supposed to look like — the detector and manual review both come back clean.
2. **The happy-path states are designed, not bolted on.** Real header+canvas skeleton with `aria-busy`, `aria-live`, and `sr-only` text; an empty state that actually teaches the next action ("Run a research blueprint"). The error block, where reachable, is also well-built (`role="alert"` + Retry).
3. **Color is never the sole signal.** Node type is carried by radius and by the text label/legend in addition to hue — exactly the "do not encode meaning in color alone" principle (the intent is there; mobile legend removal is the gap).

---

### Questions

- Does `/evidence-graph` actually exist server-side yet, or is the swallow-to-empty a deliberate placeholder? That determines whether the P0 fix is "wire up real errors" or "ship the dead error UI you already wrote."
- What is the realistic node count per project? If it is routinely >30, the layout (P1) jumps ahead of the panel polish in priority.
- Is there a design intent for hover/preview on nodes, or is click-to-select the whole interaction model? That affects how the keyboard story (P1) should be shaped.
