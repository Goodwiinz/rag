---
target: forgot-password
total_score: 31
p0_count: 0
p1_count: 2
timestamp: 2026-06-03T21-53-36Z
slug: frontend-app-auth-forgot-password-page-tsx
---
## /impeccable critique — forgot-password (brand register)

**Page:** `/home/clawdbot/clawd/rag/frontend/app/(auth)/forgot-password/page.tsx`
**Register:** brand (auth = marketing front door, trust-deciding surface)
**Detector:** `node detect.mjs --json` returned `[]` — clean. No banned-token hits (no `--terminal-*`, no `font-mono`, no hardcoded hex, no `text-gray-*`, no gradient text, no glassmorphism, no side-stripe borders, no em dashes). This is a genuinely well-behaved file at the token level; the issues below are about brand ambition and a real cool/warm hue mismatch, not slop.

### Nielsen heuristic scores

| # | Heuristic | Score | Notes |
|---|-----------|-------|-------|
| 1 | Visibility of system status | 3 | Button swaps to `Sending...` and disables; success swaps to a dedicated "Check your inbox" view. But the loading-text change has no `aria-live`, so screen-reader users get no announced state transition. |
| 2 | Match real world | 4 | Plain sentence-case, exact voice ("Enter the email address linked to your account…"). No jargon. On-brand calm tone. |
| 3 | User control & freedom | 3 | "Back to sign in" present on both states. No way to edit/resend or change the email from the success state without a full back-nav. |
| 4 | Consistency & standards | 3 | Matches the login sibling's motion/card idiom. But serif is applied inline to only 2 paragraphs while the rest is Inter; `style={{fontFamily}}` instead of the sanctioned helper class is its own inconsistency vs DESIGN.md typography rules. |
| 5 | Error prevention | 3 | `type="email"` + `required` + `autoComplete="email"`; relies on native browser validation only. No inline format check before a network round-trip. |
| 6 | Recognition vs recall | 4 | Single field, labelled, with placeholder and a hint line. Nothing to remember; the success state echoes the submitted email back. |
| 7 | Flexibility & efficiency | 3 | Enter-to-submit works (real `<form>`). No resend timer, no "use a different email" shortcut on success. Fine for the task. |
| 8 | Aesthetic & minimalist | 3 | Restrained and uncluttered — but minimalist to the point of anonymity for a *brand* surface. Reads as default shadcn product chrome, not scholarly-warm identity. |
| 9 | Error recovery | 3 | Errors render in a `role="alert"` block with reasonable styling. But it surfaces raw `resetError.message` from Supabase — potentially technical/leaky copy rather than a curated, on-voice message. |
| 10 | Help & docs | 2 | One hint line ("We will only use this to send your reset link."). No "didn't get it? check spam / contact support" affordance on the success screen, which is the moment users most need it. |

**Total: 31 / 40 — Good.** Honest, accessible, secure-by-default. Loses points on brand ambition (heuristic 8), announced async state (1/9), and help at the failure-prone success moment (10).

### Anti-patterns verdict

- **Terminal costume:** none. Clean.
- **>1 accent hue:** Sol gold via `--primary` is the only accent; destructive red is status, not decoration. Pass.
- **Hardcoded hex / text-gray-\*:** none in the component. Pass.
- **Gradient text / glassmorphism / side-stripe / hero-metric / identical-card-grid / em dashes:** none. Pass.
- **AI-slop verdict: NO.** Nobody would say "AI made this" from copy or structure — the voice is specific and the security behavior (enumeration-safe "If an account exists…") is a thoughtful human touch. The slop-adjacent risk is *blandness*: it's the kind of correct-but-anonymous auth card a generator would also produce, which matters more here because it's a brand surface.

### Overall impression

This is the most security-literate auth page in the set: the success copy is deliberately enumeration-safe, the icon-in-circle is `aria-hidden`, focus rings are correct everywhere, motion respects the house ease curve `[0.16, 1, 0.3, 1]`. It does the job and does it cleanly. The gap is register: per DESIGN.md and PRODUCT.md, auth is **brand** — "design IS the product… committed color, bolder type, one decisive idea per fold." This page spends its brand budget on a single inline serif paragraph and otherwise looks identical to a product-tier form. It's a missed opportunity on the exact surface where a researcher is deciding whether to trust the instrument.

### What's working (strengths)

1. **Enumeration-safe, honest success state.** "If an account exists for {email}, a password reset link is on its way." This is the correct security posture *and* the calm, exact NOUS voice. Genuinely good.
2. **Accessibility fundamentals are in place.** `role="alert"` on errors, `aria-describedby` linking the hint, decorative icons `aria-hidden`, full focus-visible rings with offsets, real semantic `<form>` so Enter submits. This clears most of WCAG 2.1 AA out of the box.
3. **Restraint and motion discipline.** One orchestrated entrance (fade + 8px translate), no bounce, no layout animation, no ornament. Exactly the "chrome recedes" principle.

### Priority issues

**[P1] Brand register is under-delivered on a trust-deciding surface.**
- *What:* The page renders as a generic centered shadcn card. No Sol commitment beyond a 40px tinted icon chip, no serif voice beyond two inline paragraphs, no "one decisive idea." Compared to the brand mandate it's product-tier.
- *Why:* PRODUCT.md names auth as the second-audience surface "deciding whether to trust the tool"; DESIGN.md says brand = "design IS the product, committed color, bolder type." Anonymity here costs trust.
- *Fix:* Commit one brand idea — e.g. a warm Aurum/Sol-washed panel or a calm scholarly mark/quote beside the form, lift the heading to a `.nous-h1` display step, let Sol carry more than a 10%-opacity chip. Keep it quiet, but make it unmistakably NOUS rather than unmistakably shadcn.
- *Command:* `/impeccable brand-elevate the forgot-password auth surface to match the brand register — commit Sol + serif voice, one decisive idea, keep it calm`

**[P1] Cool-hued dark tokens fight the warm Nyx ground.**
- *What:* The page sits inside an auth layout that hardcodes `bg-[var(--nous-nyx)]` (warm `#141210`), but the card/inputs/borders use semantic dark tokens at HSL hue **240** (`--card 240 22% 6%`, `--background 240 20% 4%`, `--border 240 21% 13%`) — that's blue-gray, not warm. The card reads subtly cooler than the warm ground behind it.
- *Why:* DESIGN.md's dark depth stack is explicitly warm (Nyx→Obsidian→Umber→Sepia, hue ~30-40) and says "Never hardcode hex… use warm semantic tokens." A cool card on a warm ground is exactly the warmth-loss the brand forbids.
- *Fix:* Either rebase the dark `--card/--background/--border` tokens onto the warm depth stack hue, or map this brand card to `--nous-bg-2/--nous-border-1` directly so it inherits warm Obsidian/Shade instead of the cool shadcn defaults. (System-wide token concern, but it's most visible on this brand surface.)
- *Command:* `/impeccable colorize — reconcile the dark semantic card/border tokens to the warm Nyx/Obsidian depth stack so brand surfaces stay warm`

**[P2] Inline `style={{ fontFamily }}` and inconsistent serif application.**
- *What:* Body serif is applied via `style={{ fontFamily: 'var(--nous-font-body)' }}` on two paragraphs only; the heading, label, hint, button, and link stay Inter. DESIGN.md says "Prefer `.nous-body` / `font-[var(--nous-font-*)]` over inline `style`."
- *Why:* Inline style is harder to theme/override and the half-applied serif makes the voice feel accidental rather than designed.
- *Fix:* Replace with the `.nous-body` helper class; decide deliberately which text is scholarly serif (value-prop prose) vs Inter UI, and apply consistently across both states.
- *Command:* `/impeccable distill the type system on this page — replace inline font styles with helper classes, make the serif/UI split intentional`

**[P2] Async state and errors aren't fully announced / curated.**
- *What:* `Sending...` is a visual-only text swap (no `aria-live`); the error block renders raw `resetError.message` from Supabase, which can be technical or leak implementation detail.
- *Why:* PRODUCT.md a11y line: "announced… async states." And honest-states principle wants curated, on-voice errors, not raw SDK strings.
- *Fix:* Add `aria-live="polite"` (or `aria-busy` on the button) for the sending state; map known Supabase error codes to plain sentence-case messages and fall back to a generic on-voice line.
- *Command:* `/impeccable harden the form states — announce async transitions and replace raw SDK error strings with curated copy`

**[P3] Success state lacks help at the failure-prone moment.**
- *What:* "Check your inbox" offers only "Back to sign in." No "didn't receive it? check spam / resend / contact support."
- *Why:* This is precisely where users get stuck; heuristic 10 (help) scored lowest here.
- *Fix:* Add a quiet resend affordance (with a short cooldown) and a one-line "check your spam folder" hint.
- *Command:* `/impeccable add a resend + help affordance to the password-reset success state`

### Persona red flags

*(forms surface → Jordan + Sam)*

- **Jordan (first-time / lower-confidence user):** Hits an error, sees a raw Supabase message like "For security purposes, you can only request this after 60 seconds" — reads as a system fault, not guidance. And on success, with no spam hint or resend, an email that lands in spam becomes a dead end with no recovery path on-screen.
- **Sam (screen-reader / keyboard user):** Submits, button silently changes to "Sending…" with no `aria-live` — Sam gets no confirmation anything happened until the whole view replaces. Keyboard/focus handling is otherwise strong (real form, focus rings, alert role), so this one announcement gap is the standout.
- **(Bonus, Casey — brand/trust visitor):** Lands expecting the scholarly-warm NOUS identity promised on the landing page; gets a card indistinguishable from any SaaS auth template. The cool-gray card on warm ground subtly reads "unfinished."

### Minor observations

- `if (!mounted) return null;` correctly avoids the dark/light theme hydration flash — good, but it means a blank frame on slow hydration; a static SSR-safe shell would be friendlier.
- The two states duplicate the card chrome and "Back to sign in" link inline; extracting a shared `<AuthCard>` would reduce drift between sibling auth pages.
- Heading uses `text-2xl` in both states — fine, but for brand it's timid; the display step is available.
- `focus-visible:ring-offset-1` on the input vs `ring-offset-2` elsewhere — tiny inconsistency.

### Questions

1. Is the auth route intended to be **always-dark** like the brand landing, or theme-adaptive? The layout hardcodes Nyx while the page relies on `.dark` semantic tokens via `defaultTheme="dark"` — if a user forces light, the card goes white on a warm-dark ground. Worth pinning `forcedTheme="dark"` for `(auth)` if it should match the landing.
2. Are the cool hue-240 dark tokens intentional, or a leftover shadcn default that should be re-hued warm to match the documented Nyx/Obsidian stack? This affects every dark surface, not just this page.
3. Should brand auth carry a stronger Sol/serif statement, or is the deliberate restraint here a product decision to keep the reset flow frictionless?
