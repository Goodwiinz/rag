---
target: reset-password
total_score: 31
p0_count: 0
p1_count: 3
timestamp: 2026-06-03T21-53-36Z
slug: frontend-app-auth-reset-password-page-tsx
---
## /impeccable critique — reset-password (brand register)

**File:** `/home/clawdbot/clawd/rag/frontend/app/(auth)/reset-password/page.tsx`
**Register:** brand (auth front door)
**Detector:** `node detect.mjs --json` returned `[]` (zero automated flags) on the page + `lib/utils.ts` + `lib/supabase/client.ts`. No hardcoded hex, no `text-gray-*`, no terminal tokens, no gradient text — the file is token-clean and disciplined. The real issues below are voice, consistency, and form-mechanics that the static detector cannot see.

### Overall impression
This is a competent, genuinely on-brand page. It uses the warm-dark depth stack correctly (Nyx ground, Obsidian card, Shade borders), a single Sol accent, Source Serif for body prose, one orchestrated ease-out entrance, and — notably — it ships all four honest states the design system demands: verifying, expired-link, success (with an auto-redirect progress bar), and inline error. That state coverage is better than most auth pages. What drags it from Excellent to mid-Good is a cluster of self-inflicted inconsistencies with its own sibling auth pages and one distinctly AI-flavored copy choice.

### Heuristic scores (Nielsen 10)

| # | Heuristic | Score | Notes |
|---|-----------|-------|-------|
| 1 | Visibility of system status | 4 | Verifying / submitting / success / error / redirect-progress-bar all present and honest. Excellent coverage. |
| 2 | Match to real world | 2 | "Security key" for "password" is jargon that no user calls their password; breaks the plain-spoken voice and contradicts sibling pages that say "Password". |
| 3 | User control & freedom | 3 | "Back to sign in" + "Request a new link" escape hatches exist. Success auto-redirects in 3s with no "go now" link; expired-state recovery is one-path only. |
| 4 | Consistency & standards | 2 | Diverges from `/register` and `/login`: different error copy, no autoComplete, confirm field lacks a toggle, no strength meter, no `name` attrs. Internally consistent but externally drifted. |
| 5 | Error prevention | 3 | Min-length + match checks exist, but only on submit; no strength meter or inline confirm-match hint to prevent the round-trip. |
| 6 | Recognition over recall | 4 | Labels, placeholders, lock icons, helper text "at least 8 characters" — nothing to memorize. |
| 7 | Flexibility & efficiency | 3 | Missing `autoComplete="new-password"` means password managers won't autofill or offer to generate/save — a real efficiency loss for the exact moment users want a generated password. |
| 8 | Aesthetic & minimalist design | 4 | Clean, restrained, single accent, good rhythm. No ornament. Strong. |
| 9 | Help users recover from errors | 3 | `role="alert"` error block is good, but it isn't linked to the fields (`aria-invalid`/`aria-describedby` absent) so SR users don't get field-level association; forgot-password already does `aria-describedby`. |
| 10 | Help & documentation | 3 | Helper text + expired-link guidance are adequate for an auth page; no password-policy detail beyond length. |

**Total: 31 / 40 — Good.**

### Anti-patterns verdict
- Gradient text: none. Glassmorphism-default: none. Side-stripe borders: none. Hero-metric template: n/a. Identical card grids: n/a. Terminal/mono-everywhere: none. Em dashes in copy: none (uses ellipsis "…", which is fine). Hardcoded hex / `text-gray-*`: none.
- **One slop signal does land:** "Security key" copy (see P1 below). It's not on the literal banned list, but it's exactly the kind of vaguely-technical reframing of a plain word that makes a reader think "an AI wrote this" — it's colder and more "secure-sounding" than the human voice the brand specifies. **aiSlop: true**, on copy voice rather than visual cliché.

### AI-slop verdict
**Yes, narrowly.** Visually the page would *not* read as AI-made — it's specific, token-driven, and restrained. But the copy gives it away. "Security keys do not match" / "Security key must be at least 8 characters" is the tell: a human writing NOUS's "plain and exact, like an expert colleague" voice writes "Passwords do not match," which is precisely what `/register` says. The synthetic upgrade of password → "security key" is a classic LLM register-drift.

### Persona red flags (auth → Jordan + Casey)
- **Jordan (first-time / non-expert, just clicked an email link):** Lands mid-flow, already anxious about a password reset. "Security key" makes them second-guess whether they're even on the right page ("I don't have a security key, I have a password"). Then their password manager stays silent because there's no `autoComplete`/`name`, so they can't one-click generate a strong password — the single most valuable affordance at this exact screen is missing.
- **Casey (skeptical evaluator deciding whether to trust NOUS):** Notices the confirm-password field can't be revealed while the first one can — reads as half-finished. If they hit a slow connection, the 5s timeout can flash "This link has expired" on a link that's actually fine, which actively erodes trust in a product whose whole pitch is "honest states / earns trust by showing its work."
- **Sam (a11y, secondary here):** The error `role="alert"` announces, but inputs never get `aria-invalid`/`aria-describedby`, so the error isn't programmatically tied to the field. Framer's JS entrance/3s progress animation isn't gated by `useReducedMotion` (the global CSS `prefers-reduced-motion` block at globals.css:1499 only suppresses CSS transitions, not Framer's inline `animate`).

### Priority issues

**P1 — "Security key" copy breaks voice and sibling consistency**
- *What:* Lines 64 & 69 call passwords "Security keys" in validation errors.
- *Why:* Violates the documented voice ("plain and exact… an expert colleague") and directly contradicts `/register` ("Password must be at least 8 characters", "Passwords do not match"). Cross-page inconsistency for the identical concept.
- *Fix:* Change to "Passwords do not match" and "Password must be at least 8 characters." Mirror register's exact strings.
- *Command:* `/impeccable clarify --copy "/home/clawdbot/clawd/rag/frontend/app/(auth)/reset-password/page.tsx"`

**P1 — Password inputs lack `autoComplete` and `name`**
- *What:* Neither input has `autoComplete` or `name` (lines 341–355, 392–406). Siblings use `autoComplete="current-password"`.
- *Why:* Password managers won't offer to generate or save the new password — the highest-value action on a reset screen — and form-fill heuristics misfire.
- *Fix:* Add `name="password" autoComplete="new-password"` to both fields (new-password is correct for a reset; it triggers the "suggest strong password" UI).
- *Command:* `/impeccable harden --forms "/home/clawdbot/clawd/rag/frontend/app/(auth)/reset-password/page.tsx"`

**P1 — Confirm-password field has no show/hide toggle**
- *What:* "New password" has an Eye/EyeOff toggle (lines 356–372); "Confirm new password" is permanently masked (line 394, `type="password"`).
- *Why:* Asymmetry looks unfinished and forces blind re-typing of the value users most need to verify; inconsistent within the same form.
- *Fix:* Either add a matching toggle to confirm, or (simpler, common pattern) have the single toggle reveal both fields.
- *Command:* `/impeccable adapt --consistency "/home/clawdbot/clawd/rag/frontend/app/(auth)/reset-password/page.tsx"`

**P2 — No password-strength feedback (register has one)**
- *What:* `/register` ships a live `passwordStrength()` meter (lines 123–135, 426–434); reset-password validates length only on submit.
- *Why:* Same task (choose a new password), inconsistent guidance; users get no prevention signal until they submit.
- *Fix:* Reuse the register strength meter component under the New password field, plus an inline "passwords match" check on confirm.
- *Command:* `/impeccable shape --feedback "/home/clawdbot/clawd/rag/frontend/app/(auth)/reset-password/page.tsx"`

**P2 — Session-detection timeout can false-positive "expired"**
- *What:* A fixed 5s timer (line 18, 47–51) flips to the "This link has expired" screen if `PASSWORD_RECOVERY` hasn't fired, with no spinner during the wait and no retry beyond requesting a new link.
- *Why:* On slow networks a valid link looks broken, contradicting the "honest states" principle and undermining trust at a sensitive moment.
- *Fix:* Show a spinner/skeleton in the verifying state, lengthen/abort the timeout on visibility/online events, and distinguish "still checking" from "definitely expired" (e.g. require an explicit error from Supabase, not just a timeout).
- *Command:* `/impeccable harden --states "/home/clawdbot/clawd/rag/frontend/app/(auth)/reset-password/page.tsx"`

**P3 — Error not associated with fields; Framer motion not reduced-motion-aware**
- *What:* Error block lacks `aria-invalid`/`aria-describedby` linkage; Framer `initial/animate` (incl. the 3s success bar) ignores `useReducedMotion`.
- *Why:* SR users get a floating alert with no field tie; motion-sensitive users still see JS-driven movement the global CSS block doesn't catch.
- *Fix:* Add `aria-invalid` + `aria-describedby="reset-error"` to inputs; wrap entrances with `useReducedMotion()` (or `MotionConfig reducedMotion="user"` in the auth layout) and make the success progress bar/redirect instant when reduced.
- *Command:* `/impeccable harden --a11y "/home/clawdbot/clawd/rag/frontend/app/(auth)/reset-password/page.tsx"`

### What's working (strengths)
1. **Honest, complete state machine.** Verifying / expired / success / error are all designed, not bolted on — including a success progress bar that telegraphs the auto-redirect. This is exactly the "honest states" principle and is rare to find fully built.
2. **Token discipline.** Zero hardcoded hex, zero `text-gray-*`, single Sol accent, correct warm-dark depth stack, Source Serif for prose, Inter for UI — detector-clean and visually on-brand for the always-dark auth ground.
3. **Solid baseline a11y mechanics.** `role="alert"` on errors, `aria-label`/`aria-pressed` on the visibility toggle, `aria-hidden` on decorative icons, real `<label htmlFor>` associations, and `focus-visible:ring` on every interactive element.

### Minor observations
- Inline `style={{}}` objects are used heavily instead of the `.nous-*` helper classes / arbitrary `font-[var(--nous-font-*)]` the design doc prefers; functionally fine, but verbose and harder to keep consistent.
- The `['--tw-ring-offset-color']` is set on the submit button and link, but inputs use `focus-visible:ring-2` without `ring-offset` — fine, just note the offset only matters where declared.
- Error uses `…` ellipsis char (good, not em dash). Copy is otherwise clean sentence-case.
- Dust (`--nous-dust`) is used only for icons, not small text — correctly avoids the borderline-AA small-text-on-Nyx trap the design doc warns about.

### Questions
1. Is "Security key" an intentional product term elsewhere in NOUS, or a stray? (Sibling pages say "Password" — recommend unifying on "Password.")
2. Should the success state offer a "Sign in now" link instead of forcing the full 3s wait, for users who don't want to wait out the bar?
3. Is the 5s recovery-session timeout tuned against real Supabase `PASSWORD_RECOVERY` latency on slow mobile, or a guess? It's the highest false-positive risk in the flow.
