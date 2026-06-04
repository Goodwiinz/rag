---
target: register
total_score: 28
p0_count: 1
p1_count: 2
timestamp: 2026-06-03T21-53-36Z
slug: frontend-register
---
## /impeccable critique — NOUS `register` page (brand register)

File: `/home/clawdbot/clawd/rag/frontend/app/(auth)/register/page.tsx`
Key import audited: `/home/clawdbot/clawd/rag/frontend/src/components/auth/PendingEmailConfirmation.tsx` (rendered on every successful signup) and `/home/clawdbot/clawd/rag/frontend/src/hooks/useAuth.tsx`.

### Overall impression
The register *form itself* is one of the better-built surfaces in this codebase: it uses semantic tokens throughout (`bg-background`, `text-foreground`, `border-border`, `text-primary`), sentence-case scholarly copy ("Make sense of everything you read."), a single Sol accent, Source Serif for the value-prop sentence, restrained ease-out motion, `role="alert"` errors, labelled inputs, `aria-pressed` show/hide-password toggles, and an offset focus ring. As a standalone auth form it lands close to brand intent.

The problem is what it hands off to. On every successful registration the page renders `PendingEmailConfirmation`, which is a fully intact piece of the **deliberately-removed terminal costume**: `font-mono` on the heading, body, buttons and every link; `uppercase tracking-[0.15em]` headings; Title Case voice ("Verify Your Identity"); the cyberpunk phrase **"Return to Access Terminal"**; hardcoded `text-red-400`; `[10px]` mono micro-text; and an infinitely pulsing mail icon. This is the literal anti-pattern DESIGN.md and PRODUCT.md call out by name — and it is the screen a brand-new user stares at for minutes. The register flow is only as good as its worst-rendered state, and this one drags an otherwise-Good page down.

There are also two smaller honesty/voice issues on the page proper: the logo mark is a `Terminal` icon (terminal-costume residue, even if the green is gone), and the password-strength meter is purely length-based theater that's hidden from assistive tech.

### Anti-patterns verdict (NOUS banned list)
| Anti-pattern | Verdict | Evidence |
|---|---|---|
| terminal costume (`--terminal-*`, mono-everywhere, "Access Terminal", Terminal icon) | **FAIL** | `PendingEmailConfirmation`: `font-mono` x10, "Return to Access Terminal", "Verify Your Identity"; page logo uses `<Terminal>` icon (line 177) |
| >1 accent hue | PASS (mostly) | Sol `bg-primary` is the one accent; strength meter introduces `bg-amber-500` as a second hue (line 129) |
| hardcoded hex / `text-gray-*` | PARTIAL | Page is clean (dead `_PHOSPHOR_GREEN`/`_AMBER` consts lines 37-38 are unused but confusing); `PendingEmailConfirmation` uses `text-red-400` (line 117) |
| gradient text (`bg-clip-text`) | PASS | none |
| glassmorphism-default | PASS | solid `bg-card` surfaces |
| side-stripe borders | PASS | none |
| hero-metric template | PASS | feature list, not metric block |
| identical icon-card grids | PASS (borderline) | 4 identical `icon + text` feature rows (lines 214-227) — the mild version of the banned icon-card grid; acceptable as a list but generic |
| em dashes in copy | PASS | uses ellipsis "Creating account…"; no em dashes |
| repeated uppercase tracked kickers | PASS on page / **FAIL** in confirmation screen |

**AI-slop: YES.** Not because the form is bad, but because the flow ships the exact removed costume (`font-mono` + uppercase + "Access Terminal" + pulsing-icon-forever), the unused `_PHOSPHOR_GREEN = '#D4A039'` / `_AMBER` constants reading like leftover generated scaffolding, and the comment "Brand accent constants (Sol gold). Retained for reference." Someone *would* say "AI made (and half-migrated) this."

**Detector note:** `node detect.mjs --json` returned `[]` (exit 0) for both the page and `PendingEmailConfirmation.tsx`, even run individually. That is a **false negative** — the confirmation component is the single clearest rule violation in the flow (mono-everywhere, uppercase tracked, hardcoded `text-red-400`, "Access Terminal" copy). The detector's ruleset did not catch auth-path costume residue; findings here are from manual review and should be trusted over the empty detector output.

### Nielsen 10 heuristic scores
| # | Heuristic | Score | Notes |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Submit shows "Creating account…"; `pendingEmailConfirmation` and resend cooldown are surfaced. But disabled submit has no spinner/aria-busy, and strength meter is misleading status. |
| 2 | Match real world | 3 | Page copy is plain and human; "Acme Inc.", "you@company.com" placeholders good. Confirmation screen's "Verify Your Identity" / "Access Terminal" is jargon-costume, not real-world language. |
| 3 | User control & freedom | 3 | "Wrong email? Try again" reset and "Sign in" escape exist; show/hide password good. No way to go back/edit during submit; redirect-if-authed is silent. |
| 4 | Consistency & standards | 2 | Page is internally consistent, but the flow is split-brain: brand-correct form vs terminal-costume confirmation. Two voices (sentence-case vs Title Case + uppercase mono), two color habits (tokens vs `text-red-400`). |
| 5 | Error prevention | 2 | Password match + min-length checked, but only on submit. No inline validation, no email-format guard beyond `type=email`, confirm-password mismatch not caught until submit. |
| 6 | Recognition over recall | 3 | Labels always visible, icons cue field type, "(optional)" marked, "At least 8 characters" placeholder. Solid. |
| 7 | Flexibility & efficiency | 3 | Sensible single-column flow, name fields paired; no autocomplete tokens (`autoComplete="given-name"` etc.) and no password-manager hints could be smoother. |
| 8 | Aesthetic & minimalist | 3 | Form is clean and well-spaced; brand panel restrained. Dead constants, pulsing-forever icon, and 10px mono micro-copy on confirmation cost a point. |
| 9 | Error recovery | 3 | `role="alert"` banner with human message ("Could not create your account"); resend has error state. Banner not focus-managed; resend error is `text-red-400` only (color-coded). |
| 10 | Help & docs | 3 | Spam-folder hint after 30s, "(optional)" affordance, password requirement inline. No link to terms/privacy on a brand front door, which trust-deciders expect. |
| | **Total** | **28/40** | **Band: Good** (low end — the confirmation screen is the anchor dragging it) |

### Cognitive load (8-item checklist)
1. **Visual hierarchy** — clear: hero left, single form card right. OK.
2. **Number of choices** — minimal; 6 fields, 1 optional. Good.
3. **Reading burden** — low on page; confirmation screen's 10px mono is a strain. Mixed.
4. **Memory burden** — none; all labels persistent. Good.
5. **Consistency of patterns** — broken across the form→confirmation seam. Concern.
6. **Feedback latency** — submit state fine; field errors deferred to submit. Concern.
7. **Color/meaning coupling** — strength meter and resend error rely on color alone. Concern.
8. **Motion restraint** — page good (one orchestrated entrance); confirmation's `repeat: Infinity` pulse with no `prefers-reduced-motion` path is a load/a11y miss.

### Persona red flags (auth/landing → Jordan + Casey)
- **Jordan (first-time, forms-anxious):** submits the form, gets dropped onto a black "Verify Your Identity / Return to Access Terminal" screen in mono uppercase — reads as a developer console or, worse, a phishing/error page. The tonal whiplash from the warm "Make sense of everything you read." front door erodes the exact trust the brand surface exists to build. Also: no terms/privacy link before account creation makes a cautious user hesitate.
- **Casey (mobile / low-bandwidth, evaluating trust):** the brand panel is `hidden lg:flex`, so on mobile Casey sees only the form card with no NOUS value-prop or wordmark context above the fold — the persuasion is desktop-only. The infinitely-pulsing mail icon and 10px mono labels are hostile on a small screen and in reduced-motion. The strength meter's "Weak/Fair/Good/Strong" gives a confident-sounding judgment that's really just length, which a careful user will distrust once they notice "password" scores the same as a random 12-char string.
- **Sam (a11y, secondary for forms):** strength meter is `aria-hidden` and announces nothing; resend success/error and the spam hint are color-only `text-red-400`/Sol with no `role="status"`; the error banner isn't focus-moved on appearance; confirmation motion has no reduced-motion guard.

### Priority issues
- **[P0] Terminal-costume confirmation screen.** *What:* `PendingEmailConfirmation.tsx` is rendered on every successful signup and reintroduces the explicitly-removed costume — `font-mono` throughout, `uppercase tracking-[0.15em]` headings, Title Case "Verify Your Identity", "Return to Access Terminal", hardcoded `text-red-400`, 10px mono micro-copy, infinite pulse. *Why:* it's the named anti-pattern in DESIGN.md/PRODUCT.md and it's the highest-trust moment of onboarding; it negates the page's brand work. *Fix:* rewrite in NOUS brand register — Source Serif/Inter (no mono), sentence-case ("Check your email", "Back to sign in"), semantic tokens (`text-destructive` not `text-red-400`), `text-sm`/`text-xs` not `[10px]`, drop the infinite pulse or gate it behind `prefers-reduced-motion`, add `role="status"` to resend/spam feedback. *Command:* `/impeccable harden PendingEmailConfirmation.tsx` (or `/impeccable clarify` for the copy pass).
- **[P1] Decorative, inaccessible password-strength meter.** *What:* strength is computed purely from length (lines 123-133), the bars are `aria-hidden`, and it introduces a second accent hue (`bg-amber-500`). *Why:* gives a false security signal ("Strong" for any 12 chars), conveys nothing to AT, and violates the one-accent rule. *Fix:* either remove it, or base it on real entropy (zxcvbn) and expose the rating via `aria-live` text; keep the bar fill on Sol/`bg-muted` only (warning state via `text-destructive`, not a new amber hue). *Command:* `/impeccable harden register/page.tsx`.
- **[P1] Off-register logo + voice.** *What:* the brand mark is a `Terminal` icon (line 177) — costume residue — and the confirmation voice is Title Case. *Why:* the brand is scholarly νοῦς, not a terminal; a Terminal icon is the literal thing the redesign removed. *Fix:* replace with a NOUS wordmark / non-terminal glyph (e.g. a serif "N", BookOpen, or the actual logo), keep all flow copy sentence-case. *Command:* `/impeccable shape register/page.tsx` (brand identity pass).
- **[P2] No inline / pre-submit validation.** *What:* password match, length, and email format are only enforced on submit via a single banner. *Why:* forces a full round-trip to discover a typo; banner isn't focus-managed. *Fix:* validate on blur, show field-level messages tied via `aria-describedby`, disable submit until valid or move focus to the banner on error. Add `autoComplete` tokens (`email`, `new-password`, `given-name`) for password managers. *Command:* `/impeccable harden register/page.tsx`.
- **[P3] Brand value-prop is desktop-only; dead constants.** *What:* the left brand panel is `hidden lg:flex` so mobile users get a context-free form; `_PHOSPHOR_GREEN`/`_AMBER` consts (lines 37-38) are unused leftover scaffolding. *Why:* mobile trust-deciders lose the pitch; dead phosphor constants are an AI-slop smell. *Fix:* show a compact NOUS wordmark + one value line above the form on mobile; delete the unused constants and the "Retained for reference" comment. *Command:* `/impeccable distill register/page.tsx`.

### What's working (strengths)
- **Token discipline on the page** — `bg-background`/`text-foreground`/`border-border`/`text-primary`/`text-destructive` throughout, no hex, no `text-gray-*`. This is the model the rest of the flow should follow.
- **Accessible form controls** — every input has a real `<label htmlFor>`, show/hide-password buttons carry `aria-label` + `aria-pressed`, decorative icons are `aria-hidden`, errors use `role="alert"`, focus rings are visible with `ring-offset`. Strong baseline.
- **Brand-correct voice and restraint on the page** — sentence-case, plain, no hype ("Make sense of everything you read.", "Private by default, scoped to your team"), Source Serif on the value-prop line, one orchestrated staggered entrance, single Sol accent. This is exactly the scholarly-warm register.

### Minor observations
- "Creating account…" uses a proper ellipsis (good), but the disabled submit lacks a spinner and `aria-busy` — status is text-only.
- Resend success message renders only while `resendCooldown > 0`, a slightly fragile coupling.
- The 4 feature rows are near-identical `icon+text` units; fine as a list but the generic version — varying one with a sentence or a proof point would lift it from template.

### Questions
- Is `PendingEmailConfirmation` slated for the same costume-removal the rest of auth got, or was it simply missed in the migration? It's the only file in this flow still on mono/uppercase.
- Should the brand panel (value-prop + wordmark) appear on mobile in some compact form, or is auth intentionally form-only below `lg`?
- Is the password-strength meter a product requirement, or can it be dropped? If kept, can we move to real entropy scoring so the rating is honest?
- Is there a terms-of-service / privacy link required before account creation on this brand surface?
