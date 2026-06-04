---
target: page.tsx
total_score: 34
p0_count: 0
p1_count: 2
timestamp: 2026-06-03T21-53-36Z
slug: frontend-app-page-tsx
---
## NOUS Landing (`app/page.tsx`) — /impeccable critique · register: brand

### Overall impression
This is a genuinely good brand landing that understands the NOUS thesis. One warm-gold Sol accent sits on a warm-dark Nyx ground; the live knowledge graph IS the hero rather than decoration bolted on top; copy is plain sentence-case and the proof points ("Cites every source", "12ms median search") map to real features instead of inventing compliance badges. The detector runs clean (zero findings across all five files). It reads as authored, not generated — it actively dodges the banned list. What keeps it at Good rather than Excellent is brand-register polish: stacked uppercase tracked labels the design system explicitly warns against, inline `fontFamily` styling everywhere the system says to prefer helper classes, a decorative hero canvas with no accessible role, and the supporting capabilities row landing close to the "identical icon-card grid" anti-pattern.

### Heuristic scores (Nielsen 10)
| # | Heuristic | Score | Notes |
|---|-----------|:---:|-------|
| 1 | Visibility of system status | 3 | Auth-aware CTAs (Get started vs Open dashboard) reflect real state; hover/focus states present. No loading/skeleton path while `useAuth` resolves — CTA can flip after hydration (`suppressHydrationWarning` masks it). |
| 2 | Match between system & real world | 4 | Scholarly voice, νοῦς wordmark, "Point it at your corpus and start asking." Plain and exact, no hype. Exactly the PRODUCT.md register. |
| 3 | User control & freedom | 3 | Standard nav/back; nothing traps the user. Single in-page anchor (#features); the "Features" nav link and "Explore the platform" both point to the same anchor — slightly redundant. |
| 4 | Consistency & standards | 4 | Button/link patterns, radii tokens, focus rings, and the gold-on-dark system are consistent across hero/capabilities/footer. Semantic `--nous-*` tokens throughout. |
| 5 | Error prevention | 3 | Low surface — it's a landing. No dead/ambiguous CTAs. Footer "Search"/"Dashboard" links point into authed surfaces with no signed-out affordance hint. |
| 6 | Recognition over recall | 4 | Everything visible; no hidden state to remember. Nav, proof row, and capabilities all self-describe. |
| 7 | Flexibility & efficiency | 3 | Authed users get a direct dashboard shortcut in two places. Keyboard order is logical but there's no skip-link past the fixed nav. |
| 8 | Aesthetic & minimalist design | 3 | Strong restraint and one decisive idea per fold. Pulled down by repeated uppercase tracked labels and the 3-up supporting grid edging toward the icon-card template. |
| 9 | Help users recover from errors | 3 | No error surfaces on the page itself; nothing to recover from, but also no offline/failed-graph fallback messaging (canvas just stays blank if it can't init). |
| 10 | Help & documentation | 4 | Self-explanatory marketing surface; capabilities section doubles as inline documentation of what the product does. Appropriate for a landing. |
| | **Total** | **34 / 40** | **Band: Good** |

### Anti-patterns verdict
| Banned pattern | Status |
|---|---|
| Terminal/phosphor costume (`--terminal-*`, glitch, HUD) | PASS — explicitly removed; canvas comment notes the cyan→gold de-drift |
| >1 accent hue | PASS — Sol/Helios/Apollo are one gold family, no second hue |
| Hardcoded hex / `text-gray-*` | PASS — only the canvas data-viz hex, which DESIGN.md sanctions |
| Gradient text (`bg-clip-text`) | PASS — solid Sol on the wordmark, no clip-text |
| Glassmorphism-as-default | BORDERLINE-PASS — one `backdrop-blur-md` on the fixed nav (`/85` bg). Justified for a sticky bar, not a default ornament. |
| Side-stripe accent borders | PASS |
| Hero-metric template (big number ×N + gradient) | PASS — proof row is icon + short claim, not a stat block |
| Identical icon-card grids | BORDERLINE — supporting capabilities is a 3-up icon/heading/text grid; saved partly by the asymmetric "lead capability" above it |
| Em dashes in copy | PASS — copy uses periods and commas, no em dashes |
| Repeated uppercase tracked labels | FAIL — hero kicker "MULTIMODAL INTELLIGENCE PLATFORM", nav subtitle "Multimodal Intelligence", footer "PRODUCT"/"ACCOUNT" heads all tracked-uppercase; DESIGN.md: "One uppercase tracked kicker per section max" |

**AI-slop verdict: NOT slop.** No one would say "an AI made this" — it earns its choices. The slop signals are absent. The remaining issues are taste/system-adherence, not generation tells.

### Priority issues
- **[P1] Stacked uppercase tracked labels** — *What:* hero kicker + nav subtitle "Multimodal Intelligence" + footer column heads are all tracked-uppercase. *Why:* DESIGN.md and PRODUCT.md both name repeated uppercase-tracked labels as AI scaffolding / decoration. The hero already says "Multimodal Intelligence Platform" as a kicker AND the nav repeats "Multimodal Intelligence" 16px above it. *Fix:* drop the kicker OR the nav subtitle (keep one). Set footer column heads to sentence-case or a non-tracked small caps. *Command:* `/impeccable distill app/page.tsx` (reduce label repetition).
- **[P1] Pervasive inline `style={{ fontFamily }}`** — *What:* nearly every text node sets `style={{ fontFamily: 'var(--nous-font-*)' }}` inline. *Why:* DESIGN.md: "Prefer these [helper classes] or `font-[var(--nous-font-*)]` arbitrary classes over inline `style`." Inline styles bloat markup, lose Tailwind's cascade, and are easy to drift. *Fix:* replace with `.nous-h1/.nous-body/.nous-ui` helper classes or `font-[var(--nous-font-heading)]` arbitrary classes. *Command:* `/impeccable harden src/components/landing` (token/class hygiene).
- **[P2] Decorative hero graph has no accessible role/label** — *What:* `InteractiveKnowledgeGraph` renders a bare `<canvas>` with `cursor-crosshair` but no `role="img"` + label, and the hero wrapper isn't `aria-hidden`. *Why:* DESIGN.md: "Canvas/visual elements get `role="img"` + label." It's currently invisible-but-interactive to AT. *Fix:* since it's purely decorative here, wrap in `aria-hidden="true"` and set `interactive={false}` for the background instance, OR give it `role="img" aria-label="Animated knowledge graph"`. *Command:* `/impeccable a11y-pass src/components/InteractiveKnowledgeGraph.tsx`.
- **[P2] No skip-to-content link** — *What:* fixed nav is the first focusable element; keyboard users tab through brand + Features + auth links on every page before reaching content. *Why:* WCAG 2.1 AA bypass-blocks (2.4.1) and the page targets AA. *Fix:* add a visually-hidden-until-focused skip link to `#features` or main. *Command:* `/impeccable a11y-pass app/page.tsx`.
- **[P3] Supporting capabilities grid edges toward the icon-card template** — *What:* the 3-up icon/heading/text grid under the lead capability is structurally the pattern PRODUCT.md warns about. *Why:* it's the most "templated" fold; currently rescued by the asymmetric lead block above it. *Fix:* vary one card (size, span, or a small inline example) so the three aren't interchangeable, or convert to a definition-list rhythm. *Command:* `/impeccable shape app/page.tsx#features`.

### Persona red flags (landing → Jordan + Casey)
- **Jordan (first-time evaluator, deciding whether to trust):** The hero delivers trust signals well (cites sources, runs in browser, latency). But the footer offers "Search" and "Dashboard" links that lead into authed surfaces with no "you'll need to sign in" cue — a curious evaluator clicks and hits a wall, which dents the "honest states" promise.
- **Casey (cautious / low-bandwidth / motion-sensitive):** Good news — `prefers-reduced-motion` is honored in the canvas (renders a single static frame), and framer-motion entrances are subtle fade+translate. Risk: if the canvas fails to initialize there's no fallback content, so a low-power browser may show an empty hero-left region with no graph and no explanation.
- **Sam (a11y, secondary):** Contrast is excellent (Parchment 10.2:1, Ivory 16.5:1, Sol 7.9:1, button text 8.4:1 — all clear AA). The gaps are the unlabelled canvas and missing skip-link, both flagged above.

### What's working (strengths)
- **Token discipline is real.** Every color is a semantic `--nous-*` var; the only raw hex is the canvas palette, which the design system explicitly sanctions — and the code comments even explain the cyan→gold de-drift. This is the hardest thing to get right and it's right.
- **Honest, feature-mapped copy.** Proof points and capabilities describe actual behavior ("Run inference in the browser with WebLLM", "12ms median latency") instead of inventing uptime/compliance badges. Matches "provenance over assertion."
- **The graph is the hero, not decoration.** Full-bleed interactive canvas with a radial legibility mask keeping the text column dark — one decisive idea per fold, exactly the brand-register brief. Contrast and focus states are uniformly handled.

### Minor observations
- `#features` is the target of three different controls (nav link, hero secondary CTA, footer link) — fine, but the hero "Explore the platform" and nav "Features" are redundant siblings.
- Footer copyright reads "© 2026 NOUS" — matches currentDate, no stale year.
- `suppressHydrationWarning` on the root is masking the auth-state CTA flip rather than gating it behind a resolved/loading state.

### Questions
- Is the supporting capabilities grid intended to stay a 3-up, or is there appetite to break its symmetry to fully clear the icon-card anti-pattern?
- Should signed-out users clicking footer "Dashboard"/"Search" be redirected to register with a return-to, rather than bounced by an auth guard?
- Is the hero graph meant to be interactive on the landing (it sets `cursor-crosshair` and tracks the mouse), or should the background instance be `interactive={false}` + `aria-hidden`?
