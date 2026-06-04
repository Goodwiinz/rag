---
target: cli-auth
total_score: 30
p0_count: 1
p1_count: 2
timestamp: 2026-06-03T21-53-36Z
slug: frontend-app-auth-cli-auth-page-tsx
---
## /impeccable critique — NOUS CLI Authorization (`app/(auth)/cli-auth/page.tsx`)

**Register: brand** (auth front door). This is a device-authorization / CLI consent screen: the user lands here from `nous login` in their terminal, confirms a verification code, and approves the CLI to act as them. It is a trust-critical moment — the user is granting an agent the ability to sign in as them and act on their org.

### Overall impression

Structurally this is one of the cleaner pages in the codebase. The code is honest, readable, and accessible-by-default: `role="status"` / `role="alert"`, `aria-label` on the icon button, `aria-hidden` on decorative icons, a real focus-visible ring with offset, `min-h-12` touch targets, a Suspense boundary around `useSearchParams`, and disabled-state guards on submit. The detector returns **zero findings** — no terminal costume, no gradient text, no hardcoded hex, no `text-gray-*`, no em dashes, no side-stripe borders. Copy is plain sentence-case and correctly states the stakes ("lets the NOUS command line sign in as you and act on your current organization"). That is genuinely good and rare.

The problem is **register**. For a *brand* surface this page has no identity. It is built almost entirely on theme-adaptive shadcn semantic tokens (`bg-background`, `bg-card`, `text-foreground`, `text-muted-foreground`, `border-border`, `text-primary`) rather than the absolute `--nous-*` warm-amber brand tokens the sibling `login`/`register` pages use. Two consequences: (1) it visually diverges from every other auth screen, and (2) because the `(auth)` layout forces a dark `--nous-nyx` ground *without* applying a `.dark` class, a light-theme user gets a **pure-white card (`--card: 0 0% 100%`) floating on warm-dark Nyx** — a jarring, unintended light-on-dark collision. The scholarly-warm Observatory identity is absent; this reads as a generic OAuth consent dialog.

### Heuristic scores (Nielsen 10)

| # | Heuristic | Score | Notes |
|---|-----------|:----:|-------|
| 1 | Visibility of system status | 3 | Submit shows "Approving…"; success has a clear `role="status"` panel. But Suspense fallback is `null` (blank flash), no skeleton, and the "missing/expired session" state is silent. |
| 2 | Match between system & real world | 3 | "Connect the CLI to your account", "Approve sign-in", "return to your terminal" map well to the mental model. "Session ID" is shown raw and is jargon-y for the deciding audience. |
| 3 | User control & freedom | 2 | Approve is reversible only by not clicking; there is no explicit *deny/this-wasn't-me* action. Cancel just routes to `/login`, silently abandoning the terminal which keeps polling. |
| 4 | Consistency & standards | 2 | Diverges hard from sibling auth pages (which use `--nous-*` brand tokens on Obsidian cards). Mixes shadcn semantic tokens here vs. brand tokens there — same flow, two visual languages. |
| 5 | Error prevention | 3 | Good guards: button disabled when params missing/submitting/connected; double-submit blocked. But no code-confirmation friction (one click approves a session-hijack-grade grant) and no expiry handling. |
| 6 | Recognition over recall | 4 | Code and session ID shown on-screen for side-by-side comparison with the terminal; nothing to memorize. The verification code is well-emphasized (large, tracked, Sol-colored). |
| 7 | Flexibility & efficiency | 3 | Fine for the single task. No keyboard hint, no auto-focus on the primary action, no auto-approve-when-code-matches shortcut, but the flow is short. |
| 8 | Aesthetic & minimalist design | 3 | Restrained and uncluttered, good spacing rhythm. But for a *brand* surface it is under-designed: flat gray card, no warmth, no Sol identity beyond two small accents. |
| 9 | Help users recover from errors | 2 | Approve errors render via `role="alert"` — good. But the message is raw `error.message` (may surface backend strings), there is no retry guidance, and the missing-params dead-end ("Missing" + disabled button) offers no recovery path or explanation. |
| 10 | Help & documentation | 2 | No "what is this?" / "I didn't start this" explainer, no link to docs on CLI auth, no support/abuse path. For a security grant, an "if you didn't request this" note is expected and absent. |

**Total: 30/40 — Good** (upper end of typical real-UI range; held back by brand-register and trust-affordance gaps, not by sloppiness).

### Anti-patterns verdict

| Check | Verdict |
|---|---|
| Terminal/phosphor costume (`--terminal-*`, "Neural/Synthetic") | PASS — none |
| >1 accent hue | PASS — single Sol/`primary` accent |
| Hardcoded hex / `text-gray-*` | PASS — semantic tokens throughout |
| Gradient text (`bg-clip-text`) | PASS |
| Glassmorphism default | PASS |
| Side-stripe accent borders | PASS |
| Hero-metric template / identical card grids | PASS (N/A) |
| Em dashes in copy | PASS — uses ellipsis, no em dashes |
| `font-mono` as decoration | BORDERLINE-PASS — mono used on Session ID + verification code, which is *legitimate* (technical identifiers, exactly what DESIGN.md sanctions: "code, tiny technical labels only"). Not slop. |
| Inline `style` for font | MINOR — `style={{ fontFamily: 'var(--nous-font-body)' }}` on the body paragraph; DESIGN.md says prefer `.nous-body` / `font-[var(--nous-font-body)]` arbitrary class over inline style. Cosmetic. |

**AI-slop verdict: NO.** Nothing on the banned list fires; the detector is clean. It is not "AI made this" slop — it is competent, restrained, honest code. The weakness is the opposite of slop: it is *too plain for a brand surface*, missing the deliberate identity that DESIGN.md asks brand pages to carry.

### Priority issues

**P0 — Theme-adaptive tokens break the always-dark brand ground.**
*What:* The page renders on `bg-background`/`bg-card`/`text-foreground`. The `(auth)` layout wraps everything in `bg-[var(--nous-nyx)]` (warm-dark) but never adds a `.dark` class. In a default/light theme, `--card` resolves to `0 0% 100%` (pure white) and `--background` to near-white Selene — so the consent card renders **white on warm-dark Nyx**, and on a security screen that visual instability erodes trust. DESIGN.md is explicit: "The brand landing is intentionally always-dark … independent of user theme." *Why it matters:* trust-critical first impression; inconsistent with every sibling auth page. *Fix:* Switch to the absolute brand tokens like `login`/`register` do — `bg-[var(--nous-obsidian)]` card on `bg-[var(--nous-nyx)]`, `text-[var(--nous-fg-1)]` / `--nous-fg-2`, `border-[var(--nous-border-1)]`, Sol via `--nous-sol`/`--nous-fg-accent`. (Or, minimally, force `.dark` on the auth wrapper — but matching siblings on `--nous-*` is correct.) *Command:* `/impeccable colorize` (re-token to brand warm-dark) then `/impeccable harden` for state coverage.

**P1 — No brand identity; reads as boilerplate consent.**
*What:* Beyond a ShieldCheck icon and a gold code, there is no NOUS-ness: no wordmark/Brand lockup (the `login` page renders a `Brand` component; this one shows none), no scholarly Source Serif voice beyond one paragraph, no warmth. *Why:* This is the moment a user decides the tool is credible; a generic gray card undercuts "credible thinking instrument." *Fix:* Add the NOUS wordmark/lockup, lean the explanatory sentence into Source Serif body, let Sol carry the identity (the verification code is already the natural hero — frame the card around it). Keep it calm, not loud. *Command:* `/impeccable shape` (brand register pass).

**P1 — Decline / "not me" path is invisible; abandoning leaves the terminal hanging.**
*What:* The only non-approve action is a "Cancel" link to `/login`. There is no explicit *deny this request* or *I didn't start this* affordance, and Cancel does not tell the backend to reject the session — the terminal keeps polling. *Why:* For a grant this powerful ("sign in as you and act on your org"), an unambiguous reject path is a security expectation. *Fix:* Add a real "This wasn't me / Deny" action that POSTs a reject to the session and shows confirmation, and make Cancel explain consequences ("the terminal request will expire"). *Command:* `/impeccable harden` (edge-case + security states).

**P2 — Missing/expired/invalid states are silent or inert.**
*What:* If `session_id`/`code` are absent, the page shows "No session ID provided" / "Missing" as plain text and a permanently disabled button, with no explanation. Suspense fallback is `null` (blank flash on load). There is no handling for an *expired* or *already-used* session. *Why:* DESIGN.md "Honest states" — loading/empty/error must be designed, not bolted on. *Fix:* Real loading skeleton in the Suspense fallback; a designed "link looks incomplete — re-run `nous login` in your terminal" empty state with a copy-able command; an expired-session branch. *Command:* `/impeccable harden`.

**P2 — Raw backend error string surfaced to user.**
*What:* The alert renders `approveError.message` verbatim. *Why:* Backend messages can be unfriendly or leak internals. *Fix:* Map known failures (expired, already approved, network) to plain sentence-case guidance with a retry; fall back to the generic string only as last resort. *Command:* `/impeccable clarify` (error copy).

### Persona red flags
*(auth surface → Jordan first-timer + Casey skeptical evaluator)*

- **Jordan (first-time CLI user):** Lands here mid-`nous login` and sees "Session ID: 7f3a…" raw — does not know what it is or whether it matters. There is no "compare this code to your terminal" instruction tying the two screens together, and if the params are missing they hit a dead, unexplained disabled button with no way forward. The blank load flash adds doubt.
- **Casey (security-minded evaluator):** Asks "what exactly am I granting, and how do I say no?" The copy honestly states the grant (good), but there is *no explicit deny path*, no "if you didn't request this" warning, and one click approves a session-hijack-grade capability with no code-confirmation friction. A white card flickering on a dark page during this decision reads as unpolished at exactly the wrong moment.
- **Sam (a11y — secondary):** Mostly well served (`role="status"`/`role="alert"`, labelled controls, focus ring). Minor: success and error panels appear but the primary button is not auto-focused and there is no programmatic focus move to the status region on success, so a screen-reader user must hunt for the "return to terminal" confirmation.

### What's working (strengths)

1. **Honest, accessible state handling.** `role="status"` success panel, `role="alert"` errors, `aria-label`/`aria-hidden` discipline, focus-visible ring with offset, `min-h-12` targets, double-submit guard, Suspense around `useSearchParams`. Detector is clean — zero anti-patterns.
2. **Recognition-over-recall done right.** The verification code is the visual anchor (large, letter-spaced, Sol-colored) for side-by-side comparison with the terminal; mono on the technical identifiers is the *sanctioned* use, not decoration.
3. **Plain, exact, on-brand voice.** Sentence-case throughout, states the stakes directly without hype, success copy tells the truth about what happens next ("the pending terminal session will finish signing in automatically"). This is the scholarly-calm register PRODUCT.md asks for.

### Minor observations
- Inline `style={{ fontFamily: 'var(--nous-font-body)' }}` should be the `font-[var(--nous-font-body)]` arbitrary class per DESIGN.md typography guidance.
- Only one paragraph uses serif body; the rest is Inter — fine, but the brand voice would land harder if the value sentence were unmistakably Source Serif.
- Success state hides nothing — consider also disabling/dimming the Cancel link once connected (currently it stays fully active after approval).

### Open questions
1. Is this page expected to be theme-adaptive, or always-dark like the rest of `(auth)`? If always-dark, the shadcn-token approach is a bug; if intentionally adaptive, why does the layout force `--nous-nyx`?
2. Does the backend support a *reject/deny* endpoint for a CLI session, and if so why is it not wired to a deny button?
3. Is there an expiry on the verification code, and should the UI count it down / handle the expired case?
