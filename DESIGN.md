---
name: NOUS
description: Multimodal intelligence platform — grounded, cite-backed research, rendered as a warm scholarly observatory.
colors:
  erebus: "#0a0a0e"
  selene: "#f7f7f5"
  sol: "#d4a039"
  sol-safe: "#996d1a"
  helios: "#e8b84a"
  apollo: "#f5d680"
  aurum: "#fdf6e3"
  titan: "#4a4a4e"
  charon: "#9a9a9e"
  enceladus: "#e2e2e0"
  terra: "#34d399"
  corona: "#f59e0b"
  mars: "#ef4444"
  nyx: "#141210"
  obsidian: "#1e1b17"
  umber: "#28241e"
  sepia: "#332e26"
  dusk: "#3d372e"
  ivory: "#f5f0e8"
  parchment: "#c8bfa8"
  dust: "#8a8070"
  shade: "#2a261f"
typography:
  display:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "4.5rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Inter, -apple-system, sans-serif"
    fontSize: "2.5rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Inter, -apple-system, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Source Serif 4, Georgia, Times New Roman, serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.8
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, -apple-system, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.6
    letterSpacing: "normal"
  overline:
    fontFamily: "Inter, -apple-system, sans-serif"
    fontSize: "0.7rem"
    fontWeight: 600
    lineHeight: 1.6
    letterSpacing: "0.16em"
  mono:
    fontFamily: "JetBrains Mono, SF Mono, Menlo, Consolas, monospace"
    fontSize: "0.85rem"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
rounded:
  base: "6px"
  sm: "4px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  2xl: "24px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
  3xl: "64px"
components:
  button-primary:
    backgroundColor: "{colors.sol-safe}"
    textColor: "{colors.selene}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "40px"
  button-accent:
    backgroundColor: "{colors.sol}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "40px"
  button-erebus:
    backgroundColor: "{colors.erebus}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "40px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.titan}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "40px"
  card:
    backgroundColor: "#ffffff"
    textColor: "{colors.erebus}"
    rounded: "{rounded.lg}"
    padding: "24px"
  input:
    backgroundColor: "{colors.selene}"
    textColor: "{colors.erebus}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    height: "40px"
  badge-accent:
    backgroundColor: "{colors.sol}"
    textColor: "#ffffff"
    rounded: "{rounded.full}"
    padding: "4px 12px"
  badge-muted:
    backgroundColor: "{colors.aurum}"
    textColor: "{colors.sol-safe}"
    rounded: "{rounded.full}"
    padding: "4px 12px"
---

# Design System: NOUS

> **Source of truth for tokens:** `frontend/app/nous-tokens.css` (the `--nous-*` brand layer) and `frontend/app/globals.css` (shadcn `--background`/`--foreground`/etc. semantic layer). Tailwind maps both in `frontend/tailwind.config.ts`. The frontmatter above mirrors these for design-aware tooling; the CSS files remain canonical.

## 1. Overview

**Creative North Star: "The Observatory"**

NOUS is an instrument for seeing clearly. The system is built around the leap from scattered perception to structured comprehension (NOUS = Greek _νοῦς_, mind/intellect), and its surface should feel like a well-kept observatory: precise instruments, a calm dark sky, and one warm light to read by. The palette is literally celestial (Erebus the void, Selene the moonlit surface, Sol the solar-gold accent), and that cosmology is the organizing idea, not decoration. Color is used the way an observatory uses light: sparingly and on purpose, so the one gold accent reads as a deliberate signal rather than ambient noise.

**Two registers coexist in one codebase:**
- **Product** (default): authenticated app surfaces — dashboard, chat, documents, search, settings, entities, analytics. Design SERVES the task: restrained color, familiar patterns, density where users need it, shadcn/Radix components. Most of `src/components/**` and `app/(dashboard)/**`. Light is a clean daytime workspace; dark is a warm amber night sky.
- **Brand**: the marketing front door — landing (`app/page.tsx` + `src/components/landing/**`) and auth (`app/(auth)/**`). Design IS the product: committed color, bolder type, one decisive idea per fold. The landing is intentionally **always-dark** (warm Erebus/Nyx ground), independent of the user's theme.

Reading is the actual job (researchers spend long sessions reading retrievals and drafting), so the body face is a serif (Source Serif 4) tuned for sustained legibility, while UI chrome stays in crisp Inter. Identity is **scholarly, warm, confident** — not cyberpunk and not SaaS-cream. A prior terminal/phosphor-green "costume" was removed and must not return; the `--terminal-*` / `--phosphor-green*` Tailwind tokens are now legacy aliases pointing at the warm-gold brand tokens (`--phosphor-green: var(--nous-sol)`), not a live theme.

This system explicitly rejects the ChatGPT-wrapper look (a bare chatbox with no sense of provenance), the cold clinical dark UI, glassmorphism-as-default, and "magical AI" theatrics. Confidence comes from showing sources and capability, not from gradients and glow.

**Key Characteristics:**
- Celestial palette where one warm gold is the single accent voice.
- Warm in both modes — parchment-by-candlelight dark, not blue-grey.
- Serif body for reading, sans for chrome; no pure-white text.
- Calm at rest; warmth and a gold glow appear on the action about to happen.
- Provenance is visible — citation pills, source strips, margin rules.
- Theme flips via `.dark` (`next-themes`); brand anchors and the dark depth stack are absolute.

## 2. Colors

A celestial palette (`nous-tokens.css`): a deep void, a moonlit surface, and a single solar-gold accent, with warm earthy darks and a small set of signal colors. Semantic `--nous-*` vars flip with `.dark`; brand anchors do not.

### Primary
- **Sol — Solar Gold** (`#d4a039`): The one accent voice. Primary CTA (`accent` button), focus rings, links, citation references, active states. On light surfaces, gold *text/icons* use **Sol Safe** (`#996d1a`) for AA; full Sol is reserved for fills, glows, and large accents.
- **Helios — Warm Solar Glow** (`#e8b84a`): The dark-mode accent (`--nous-fg-accent` flips to this); gold shifts one step brighter on warm dark surfaces to hold AA. Also the hover step for accents in light mode.
- **Apollo — Pale Gold Radiance** (`#f5d680`): Highlights and decorative gradients only.

### Neutral — Light
- **Erebus — The Void** (`#0a0a0e`): Primary text and darkest surfaces (the `erebus` button, app rail).
- **Selene — Moonlit Surface** (`#f7f7f5`): Default page background. **Aurum — Parchment Wash** (`#fdf6e3`): tinted backgrounds, gold accent wash, ghost-button hover, inline-code background.
- **Titan** (`#4a4a4e`): secondary text. **Charon** (`#9a9a9e`): captions/placeholders (verify 4.5:1). **Enceladus** (`#e2e2e0`): borders, dividers.

### Neutral — Warm Dark (the Depth Stack)
- **Nyx** (`#141210`) → **Obsidian** (`#1e1b17`) → **Umber** (`#28241e`) → **Sepia** (`#332e26`) → **Dusk** (`#3d372e`): six warm surfaces, each subtly lighter/warmer as elevation rises (used for the always-dark brand landing and dark mode). Text: **Ivory** (`#f5f0e8`) → **Parchment** (`#c8bfa8`) → **Dust** (`#8a8070`). Border: **Shade** (`#2a261f`).

### Signal Colors
- **Terra** (`#34d399`) success · **Corona** (`#f59e0b`) warning · **Mars** (`#ef4444`) error.

### Named Rules
**The One Voice Rule.** Sol gold is the only accent — ≤10% of any screen (primary action, focus, links, citations). Its rarity is the signal. Never introduce a second decorative accent hue.

**The No Raw Hex Rule.** Never hardcode hex in components, and never `text-gray-*` / `bg-gray-*`. Use semantic tokens (`text-foreground`, `text-muted-foreground`, `border-border`) or `--nous-*` vars. Graph / data-viz palettes are the only sanctioned hardcoded hex.

**The Sol-Safe Rule.** For gold text/icons on light, use Sol Safe (`#996d1a`); full Sol (`#d4a039`) fails AA as small text on Selene.

**The No Pure White Rule.** Brightest text is Ivory (`#f5f0e8`), never `#ffffff`. White only for text *on* saturated fills. On dark, small text uses Parchment, not Dust (Dust on Nyx is borderline AA at small sizes).

## 3. Typography

**Display / Heading / UI Font:** Inter (`--nous-font-heading`, `--nous-font-ui`; loaded via `next/font` as `--font-inter`)
**Body Font:** Source Serif 4 (`--nous-font-body`; optical sizing auto)
**Mono Font:** JetBrains Mono (`--nous-font-mono`; `next/font` `--font-mono`) — code and tiny technical labels only.

**Character:** A contrast pairing — a crisp humanist sans for structure and chrome against a warm literary serif for reading. The sans says "instrument"; the serif says "manuscript."

Prefer the helper classes in `nous-tokens.css` (`.nous-display`, `.nous-h1/2/3`, `.nous-body`, `.nous-ui`, `.nous-caption`, `.nous-overline`, `.nous-mono`, `.nous-wordmark`) or `font-[var(--nous-font-*)]` arbitrary classes over inline `style`.

### Hierarchy
- **Display** (Inter 700, 4.5rem, lh 1.1, -0.03em): brand hero headlines only.
- **Headline / H1** (Inter 700, 2.5rem, 1.1, -0.02em): page titles.
- **Title / H2** (Inter 600, 1.75rem) and **H3** (Inter 600, 1.15rem): section headings.
- **Body** (Source Serif 4 400, 1rem, lh 1.8): long-form reading — answers, drafts, value-prop sentences. Cap measure at 65–75ch. Chat body runs 15px / 1.7.
- **Label / UI** (Inter 500, 0.875rem): buttons, nav, fields, badges.
- **Overline** (Inter 600, 0.7rem, 0.16em, uppercase): sparse eyebrows in Sol-Safe.
- **Mono** (JetBrains Mono 400, 0.85rem): endpoints, IDs, code, on an Aurum chip.

Scale is fixed rem in product (≈1.125–1.2 ratio); larger display steps allowed in brand.

### Named Rules
**The Read-Don't-Skim Rule.** Body is a serif at line-height 1.8 because the user is reading, not skimming. Don't swap body to a sans "for consistency."

**The Quiet Eyebrow Rule.** One uppercase tracked kicker per section, max. Repeating it on every section is AI scaffolding; don't use mono as decorative "technical" shorthand either.

## 4. Elevation

A **hybrid** model split by mode. In **light**, depth is soft ambient warm-tinted shadows (`rgba(10,10,14,...)`): surfaces sit nearly flat at rest (`shadow-sm`) and lift on interaction (`-translate-y` + `shadow-lg`). In **dark**, depth is conveyed by **warmth, not shadow** — the surface steps up the amber stack (Nyx → Obsidian → Umber → Sepia → Dusk), each layer lighter and warmer, so higher elevation simply glows more. Theme flips via `.dark` (`next-themes`); the dark depth stack and brand anchors are absolute.

### Shadow Vocabulary (`--nous-shadow-*`)
- **sm** (`0 1px 2px rgba(10,10,14,0.04)`): resting cards, inputs.
- **md** (`0 4px 12px rgba(10,10,14,0.06)`): raised panels, dropdowns.
- **lg** (`0 8px 30px rgba(10,10,14,0.08)`): interactive card hover lift.
- **xl** (`0 20px 60px rgba(10,10,14,0.15)`): modals, sheets.
- **focus** (`0 0 0 3px rgba(212,160,57,0.25)`): Sol focus ring, both modes.
- **accent-glow** (`0 8px 30px rgba(212,160,57,0.3)`): gold CTA hover only.

### Named Rules
**The Warmth-Is-Elevation Rule.** In dark mode, show hierarchy by stepping up the warm stack, not with bigger shadows. Shadows are a light-mode tool; warmth is the dark-mode tool.

**The Glow-On-Intent Rule.** The gold glow appears only on the action about to happen (CTA hover, composer focus), never as ambient decoration.

## 5. Components

Built on shadcn/ui + Radix primitives in `src/components/ui/**` — these carry baseline focus-visible / roles / keyboard; prefer them over one-offs. The feel is **refined and restrained at rest, with a warm gold glow on intent.** Base radius is 6px (`--radius`); the brand scale runs 4 / 8 / 12 / 16 / 24px.

**Shared behavior (every interactive element):** ships default / hover / focus-visible / active / disabled / loading / error states. Focus uses `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40` (or `ring-ring`) — never a bare `focus:outline-none`. Icon-only buttons require `aria-label`; decorative icons get `aria-hidden`; canvas/visual elements get `role="img"` + label; errors use `role="alert"`. **Motion:** ease-out `--nous-ease-out` `cubic-bezier(0.16,1,0.3,1)`, no bounce/elastic; product transitions 150–250ms and convey state, not decoration; brand may use one orchestrated entrance (staggered fade + small translate); never animate layout properties (width/left/top) — use transform/opacity, with a `prefers-reduced-motion` alternative.

### Buttons
- **Shape:** `rounded-md` (8px). Heights: default 40px, sm 36px, lg 44px.
- **Primary (`default`):** deep accessible gold (`#996d1a`, `--primary`) + Selene text; hover `bg/90` + `-1px` lift + soft shadow.
- **Accent:** full Sol (`#d4a039`) + white; hover `-1px` lift + **gold glow**. The loudest action; use once per view.
- **Erebus:** near-black (`#0a0a0e`) + white + lift on hover. **Ghost (`nous-ghost`):** transparent, Titan text; hover fills Aurum wash, text → Erebus. Default for nav / low-emphasis.

### Cards / Containers
- 12px radius (`rounded-xl`); white (light) / Obsidian (dark); border Enceladus / Shade. `shadow-sm` at rest; `interactive` adds Helios border + `-0.5px` lift + `shadow-lg` on hover. Padding 24px (`p-6`). Cards are not the lazy default; **nested cards are forbidden.**

### Inputs / Fields
- 40px, `rounded-md`, `border-input` over page background, 14–16px. Focus: border → Sol, ring softens to 30% Sol glow (`ring-[var(--nous-sol)]/30`) with `transition-colors`. Placeholder `text-muted-foreground` — verify 4.5:1.

### Badges / Chips
- Full pill (`rounded-full`), `px-3 py-1`, 12px medium. Accent ("Featured"): Sol + white. Muted ("Draft"): Aurum + Sol-Safe.

### Navigation
- App rail on Erebus, 1.6 stroke icons, tooltips sliding in from the right on hover/focus (`rail-btn[data-tip]`). Icon-only controls carry an `aria-label`.

### Signature: Citation Reference
The provenance primitive — an 18px circular pill (`nous-cite-ref`), Aurum background, Sol-Safe numeral, set inline in answers. The visual form of "no citation, no claim"; every grounded statement carries one and it links to its source.

## 6. Do's and Don'ts

### Do:
- **Do** keep Sol gold to ≤10% of any screen — one accent voice.
- **Do** use semantic tokens / `--nous-*` vars; use Sol-Safe (`#996d1a`) for gold text on light.
- **Do** convey dark-mode depth by stepping up the warm stack (Nyx → Dusk), not with shadows.
- **Do** set long-form body in Source Serif 4 at line-height 1.8, capped at 65–75ch.
- **Do** put the gold glow only on the action about to happen (CTA hover, composer focus).
- **Do** make provenance visible — citation pills, source strips, margin rules.
- **Do** give every icon-only control an `aria-label`, use `role="alert"` for errors, and ship a `prefers-reduced-motion` alternative for every animation.

### Don't:
- **Don't** make NOUS look like a ChatGPT wrapper — a bare chatbox with no provenance.
- **Don't** reintroduce the terminal/phosphor cyberpunk costume (`--terminal-*`, `--phosphor-green`, glitch text, scanlines, spinning HUD rings, tech tickers).
- **Don't** use a cold blue-grey dark theme; pure white (`#ffffff`) text is forbidden — brightest is Ivory.
- **Don't** hardcode hex or use `text-gray-*` / `bg-gray-*` in components (graph/data-viz palettes excepted).
- **Don't** use gradient text (`bg-clip-text`), glassmorphism-as-default, or side-stripe colored accent borders.
- **Don't** ship the hero-metric template (big number + label + gradient ×N), identical icon-card grids, modal-first flows, or nested cards.
- **Don't** introduce a second accent hue, swap the serif body to a sans, or use mono as decorative shorthand.
- **Don't** repeat uppercase tracked section labels, use em dashes in copy, or lean on "magical AI" / buzzword framing.
