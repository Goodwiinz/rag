---
target: landing page
total_score: 29
p0_count: 0
p1_count: 2
timestamp: 2026-05-28T13-11-04Z
slug: src-components-landing
---
#### Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | "Connected" pill + pulsing dot is decorative fake-status, not real telemetry |
| 2 | Match System / Real World | 4 | Copy is human and clear ("Knowledge that answers back") |
| 3 | User Control and Freedom | 3 | Landing, low interaction; CTAs navigate cleanly |
| 4 | Consistency and Standards | 2 | Metric contradiction: hero "Sub-20ms" vs body/footer "12ms"; 5 different CTA verbs |
| 5 | Error Prevention | 2 | Primary CTA "Start exploring" -> /documents/upload dead-ends an unauthed first-timer at login |
| 6 | Recognition Rather Than Recall | 4 | Clear nav, labeled controls |
| 7 | Flexibility and Efficiency | 3 | Fine for a landing |
| 8 | Aesthetic and Minimalist Design | 3 | Disciplined craft, but sits in the modal AI-infra reflex lane; mini hero-metric template in footer |
| 9 | Error Recovery | 3 | No real error states (neutral) |
| 10 | Help and Documentation | 2 | No docs / about / contact beyond two footer link columns |
| **Total** | | **29/40** | **Solid craft, plays it safe** |

#### Anti-Patterns Verdict

**LLM assessment**: This does NOT trip the absolute bans. No gradient text, no side-stripe borders, no decorative glassmorphism (the nav `backdrop-blur` is purposeful sticky-nav, fine), tokenized colors throughout, no hardcoded hex, no `text-gray-*`. Craft is real: asymmetric hero, proper type hierarchy, tasteful ease-out entrance, strong a11y.

The failure is subtler and it's the **second-order slop test**. Inverse-test sentence: "A multimodal AI platform landing, warm-dark with a gold accent, headline left + animated graph right, three feature tiles below, two stats, one closing CTA." That sentence fits nearly every YC-era AI-infra landing. The redesign cleaned the craft but did not buy a point of view. brand.md is explicit: brand needs strangeness and a POV; restraint without intent reads as mediocre, not refined.

Two real content defects undercut trust on top of that:
- **Metric inconsistency** across folds (Sub-20ms / 12ms / 12ms) reads as un-proofread.
- **Overclaiming**: "SOC 2 ready", "99.99% uptime", "End-to-end encrypted" are heavy enterprise assertions on what is a single-owner research platform. Unsubstantiated trust badges erode the exact trust they chase.

**Deterministic scan**: `detect.mjs` returned `[]` (exit 0) on all three landing components + `app/page.tsx`. Clean. Manual ban-list grep (hex, gray utilities, bg-clip-text, border-l/r stripes, em dashes, mono shorthand) also clean. The deterministic layer agrees the absolute bans are absent; it cannot see the distinctiveness gap, which is the actual problem here.

**Visual overlays**: No live overlay. No dev server running and the project runs servers manually, so browser injection was skipped. Assessment B is detector + static review only.

#### Overall Impression

Competent and well-built, but invisible. This is the "after" of a cleanup, not the "after" of a brand. The single biggest opportunity: give the brand fold one decisive idea that only NOUS could ship (the live knowledge graph is the seed of it) and stop hedging with generic enterprise trust badges and a centered two-stat block.

#### What's Working

- **The interactive knowledge graph as hero imagery.** This is the one genuinely distinctive, on-brand asset. brand.md counts canvas/WebGL scenes as imagery; this is the differentiator. Lean harder on it.
- **Accessibility craft.** `focus-visible` rings on every interactive element, `aria-hidden` on decorative icons, `role="img"` + descriptive label on the graph, `aria-label` on footer nav columns, semantic `dl/dt/dd` for stats. Genuinely above average.
- **Type + motion discipline.** Source Serif body vs Inter headings reads scholarly; the staggered fade/translate entrance uses the exact DESIGN ease-out curve and never animates layout props.

#### Priority Issues

- **[P1] Metric inconsistency + unsubstantiated enterprise claims**
  - **Why it matters**: "Sub-20ms" (hero) vs "12ms median" (capabilities + footer) is a visible contradiction on a page whose entire pitch is "cites its sources." Pair that with "SOC 2 ready / 99.99% uptime / E2E encrypted" on a single-owner platform and the trust signals invert into skepticism.
  - **Fix**: Pick one latency number and one framing, use it everywhere. Drop or qualify claims you can't substantiate. Replace badges with one honest, specific, verifiable proof point.
  - **Suggested command**: `clarify`

- **[P1] Primary CTA dead-ends unauthenticated visitors**
  - **Why it matters**: "Start exploring" routes to `/documents/upload`, which requires auth. A first-time visitor's single most prominent action bounces them to a login wall with no context. That's the worst possible first interaction.
  - **Fix**: Route the primary CTA to a no-auth experience (the live `/search` demo, or a public sample graph), or relabel to set the login expectation. Make "see the product work" reachable without an account.
  - **Suggested command**: `craft` (or `clarify` if relabel-only)

- **[P2] Lands in the modal AI-infra aesthetic lane**
  - **Why it matters**: brand.md's second slop test. Anyone could guess this is "an AI/RAG dev tool" from the layout alone. Safe = invisible; the brand fold has no risk in it.
  - **Fix**: Commit one bold move on the brand surface only (product UI stays restrained): an oversize `νοῦς` as the actual hero subject, a full-bleed living graph behind the headline, or a distinctive display cut for the H1 while Inter stays for UI. One decisive idea, not three.
  - **Suggested command**: `bolder`

- **[P2] Footer two-stat block is a mini hero-metric template**
  - **Why it matters**: Two centered big-gold-numbers + label is the SaaS cliche the shared bans call out, just shrunk. After the duplicated 12ms it also restates rather than adds.
  - **Fix**: Either make the stat earn its place with proof/context, or replace the closing section with something with more voice than two numbers and a button.
  - **Suggested command**: `distill` or `bolder`

#### Persona Red Flags

**Jordan (First-Timer / curious researcher)**: Clicks the big gold "Start exploring" expecting to see the product. Hits a login wall at `/documents/upload`. No "try it without an account" path. Sees "SOC 2 ready / 99.99% uptime" and, because nothing substantiates them, quietly discounts the whole page. Likely bounces at the first CTA.

**Sam (Skeptical technical evaluator)**: Reads "Sub-20ms search" in the hero, then "12ms median latency" twice below, and flags the contradiction immediately. Wants to know latency at what corpus size, uptime measured over what window, SOC 2 by whom. Finds no detail, no docs link, no architecture page. The live graph impresses; the unbacked numbers undercut it.

#### Minor Observations

- Five distinct CTA verbs: "Start exploring", "See it live", "Get started", "Open dashboard", "Dashboard". Unify the action vocabulary.
- Nav sublabel "Multimodal Intelligence" at `text-[10px]` is near the floor of legibility.
- The "Connected" status pill + pulsing dot in the graph card header is decorative chrome; it implies live telemetry that isn't real.
- Capabilities lead + 3-tile `gap-px` grid is a softened version of the identical-card-grid reflex. The lead/supporting split helps; the 3 equal supporting tiles are still the generic shape.

#### Questions to Consider

- The interactive graph is your one unfair asset. What if it WERE the hero, full-bleed behind the type, instead of boxed in a card on the right?
- What's the one true number you can defend, and what if that single proof point replaced all five trust badges?
- What would a confident NOUS landing look like if it assumed the visitor already believes RAG works, and only had to prove THIS one is different?
