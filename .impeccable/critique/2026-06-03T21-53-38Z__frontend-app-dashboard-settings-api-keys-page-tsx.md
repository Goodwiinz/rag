---
target: api-keys
total_score: 17
p0_count: 2
p1_count: 2
timestamp: 2026-06-03T21-53-38Z
slug: frontend-app-dashboard-settings-api-keys-page-tsx
---
## /impeccable critique — Settings ▸ API Key Management

`app/(dashboard)/settings/api-keys/page.tsx` → renders `src/page-components/settings/APIKeyManagementPage.tsx`
Register: **product** · Band: **Poor (17/40)** · AI-slop: **Yes**

---

### Overall impression

This is not an API-key management page; it is a brochure *about* the idea of one. There are no keys. Nothing on the screen is real: "2 active personal tokens", "Last rotation 9 days ago", "Azure OpenAI pending review" are static strings baked into a `const` array. The single actionable control — "Create Token" — is an `outline` button with no `onClick`, no dialog, no destination. For a researcher who lands here to rotate a leaked credential or copy a key into a script, the page does literally nothing it advertises. That alone caps the score: a settings surface whose core job (view, create, copy, rotate, revoke keys) is absent fails Match-real-world, Error-prevention, and Error-recovery simultaneously.

Layered on top is a presentation that trips the NOUS anti-pattern list twice. The header kicker `DEVELOPER_ACCESS` in `font-mono uppercase tracking-[0.28em]` is the exact "terminal costume" / "uppercase-mono label as decoration" the design system explicitly removed and bans — the snake_case all-caps reads as a phosphor-terminal HUD label, not scholarly-warm. And the body is three structurally identical icon-tile + title + description + bullet-list cards, which is the banned "identical icon-card grid" template.

To its credit the file is token-clean (no hardcoded hex, no `text-gray-*`, no gradient text, no glassmorphism — the detector returns `[]`), and it correctly uses `--nous-*` semantic vars and the shared `Button`/`Card` primitives. But clean tokens on a non-functional, on-trend-AI layout is polish on a placeholder.

---

### Nielsen heuristic scores

| # | Heuristic | Score | Notes |
|---|-----------|:----:|-------|
| 1 | Visibility of system status | 1 | No loading/empty/error states. "Last rotation 9 days ago" is static, not live. Nothing reflects real system state. |
| 2 | Match between system & real world | 2 | "Active Tokens / Provider Access / Rotation Guidance" is reasonable vocabulary, but a key manager that shows no keys doesn't match the user's mental model of one. |
| 3 | User control & freedom | 1 | No create flow, no copy, no rotate, no revoke. "Create Token" is inert. Only working control is a back-link. |
| 4 | Consistency & standards | 2 | Uses shared Button/Card and `--nous-*` tokens (good), but the mono snake_case kicker and the secondary `outline` primary action break NOUS conventions; the real CTA should be `accent`/`erebus`, not a third outline button. |
| 5 | Error prevention | 1 | Security surface with zero guardrails: no confirm on (absent) destructive actions, no scoping UI, no masking. Nothing to prevent because nothing happens. |
| 6 | Recognition vs recall | 3 | Card titles + bullets are scannable; icons aid recognition. The one bright spot. |
| 7 | Flexibility & efficiency | 1 | No search/filter, no per-key actions, no keyboard affordances beyond default button focus. Power users (the actual audience) get nothing to act on. |
| 8 | Aesthetic & minimalist design | 2 | Spacing rhythm is decent, but three clone cards of invented stats is decorative filler, not information — the opposite of "no ornament that does not inform." |
| 9 | Help users recover from errors | 1 | No error states, no `role="alert"`, no "key shown once — copy now" recovery affordance. |
| 10 | Help & documentation | 3 | "Rotation Guidance" card embeds least-privilege/rotate-quarterly tips inline, which is genuinely helpful. Slightly undercut by being framed as data rather than guidance with links. |
| | **Total** | **17/40** | **Poor** |

---

### Anti-patterns verdict — FAIL (2 banned, 1 borderline)

- **Terminal/uppercase-mono costume — BANNED, present.** `text-xs font-mono uppercase tracking-[0.28em] … DEVELOPER_ACCESS` (line 48–50). DESIGN.md and PRODUCT.md both ban "uppercase-mono labels used as decoration," "mono-everywhere," and the removed `terminal-*`/phosphor costume. snake_case ALL-CAPS in mono is the most on-the-nose version of it. Fix: sentence-case Inter overline using `.nous-overline`, or drop the kicker entirely.
- **Identical icon-card grid — BANNED, present.** Three `Card`s, each = Sol-glow icon tile + title + description + bullet list, in a `lg:grid-cols-3` (lines 82–117). Exactly the "identical icon-heading-text card grids" anti-pattern. These three cards carry different *kinds* of content (a live inventory, a provider status table, static advice) and should not share one template.
- **Hero-metric-ish template — borderline.** Not the literal big-number/gradient block, but "2 active personal tokens / 1 workspace-scoped token" as decorative stats inside a clone card is adjacent to it. Real inventory belongs in a list/table, not as count-strings.
- **Em dashes — clean.** None in copy.
- **Detector — clean.** `detect.mjs --json` returns `[]`; no hex, gradient-text, glass, or side-stripe hits. The two banned items above are false-negatives the detector doesn't cover (mono kicker, card-grid sameness) — note them as manual findings, not detector misses.

---

### Cognitive-load checklist (8)

1. Single clear primary action? **No** — "Create Token" is one of three outline buttons and is inert; the true action is visually equal to a back-link.
2. Scannable hierarchy? **Partial** — header → cards is clear, but three identical cards flatten priority.
3. Consistent component vocabulary? **Yes** — shared Button/Card.
4. Honest states (loading/empty/error)? **No** — none exist.
5. Information vs decoration ratio? **Poor** — fabricated stats are decoration dressed as data.
6. Reading load reasonable? **Yes** — copy is short.
7. Recognition over recall? **Yes** — labels + icons.
8. Provenance/trust visible? **No** — invented numbers with no source; antithetical to "provenance over assertion."

**AI-slop verdict: Yes.** A reviewer would say "AI made this." Tells: three perfectly parallel icon-cards generated from a `const` array, plausible-but-fake metrics, a decorative mono UPPERCASE kicker, and a CTA that goes nowhere. It reads as a generated layout that was never wired to a backend.

---

### Persona red flags

Interface type = settings/data dashboard → personas **Alex (power user)** and **Sam (a11y)**.

- **Alex (power researcher):** "I came to revoke a key that leaked into a notebook. There's no key list, no copy button, no revoke. 'Create Token' doesn't open anything. This page can't do its one job — I'll fall back to the CLI or the provider console." The audience is explicitly expert/dense-tolerant, and the page gives them nothing to operate on.
- **Sam (screen-reader / keyboard):** The kicker `DEVELOPER_ACCESS` will be read literally as "developer underscore access" by some SRs (snake_case in an all-caps string). There's no `role="alert"` region for the (missing) async/error states, "Create Token" announces as an enabled button that does nothing on activate (a dead-end for keyboard users), and the Sol-glow icon tiles are decorative but the icons aren't `aria-hidden`. The card bullet lists are flat `<p>` runs, not a semantic `<ul>`, so there's no list affordance.
- **Casey (trust, secondary):** Fabricated security stats ("Last rotation 9 days ago") on a credentials page actively *erodes* trust the moment a user notices nothing updates — the worst possible surface to fake data on.

---

### What's working

- **Token discipline.** No hardcoded hex, no `text-gray-*`, no gradient text/glass. Uses `--nous-fg-*`, `--nous-bg-*`, `--nous-border-1`, `--nous-sol`, `--nous-sol-glow` correctly; detector is clean.
- **Reuses the system.** Shared `Button` and `Card` primitives rather than one-offs, so focus-visible/keyboard baselines come for free.
- **Embedded guidance instinct is right.** Surfacing least-privilege / rotate-quarterly hygiene next to the keys is a genuinely good idea — it just needs to be real guidance with links, not a clone card of static bullets.

---

### Priority issues

**P0 — Page is non-functional; it manages nothing.**
- *What:* All data is a hardcoded `const`; "Create Token" (line 73–78) has no handler, dialog, or route. No keys are listed.
- *Why:* The core job of the page (view/create/copy/rotate/revoke keys) is absent — fails heuristics 1, 3, 5, 7, 9 at once and makes the page a placeholder.
- *Fix:* Wire to the real keys endpoint. Render an actual table/list of keys (name, scope, masked value `nous_sk_••••a1b9`, created, last-used), each row with copy + rotate + revoke (revoke behind a confirm). Replace the inert button with a real Create flow (dialog or `/settings/api-keys/new`), and show the full key exactly once with a copy-and-warn affordance.
- *Command:* `/impeccable harden settings/api-keys — wire real keys data, add create/copy/rotate/revoke with confirm, and honest loading/empty/error states`

**P0 — Banned terminal-costume kicker.**
- *What:* `font-mono uppercase tracking-[0.28em] DEVELOPER_ACCESS` (lines 48–50).
- *Why:* Directly violates the banned "uppercase-mono decorative label" + "mono-everywhere" + removed phosphor/terminal skin; reads cyberpunk, not scholarly-warm.
- *Fix:* Remove it, or replace with a sentence-case Inter overline (`.nous-overline`, no mono, no snake_case): e.g. a quiet "Settings" eyebrow. One tracked kicker max per section, and not in mono.
- *Command:* `/impeccable distill settings/api-keys — drop mono/uppercase kicker, sentence-case voice`

**P1 — Identical icon-card grid of invented data.**
- *What:* Three structurally identical Sol-glow-icon + title + description + bullets cards (lines 82–117) presenting fabricated stats.
- *Why:* Banned "identical icon-card grid"; also fakes provenance, contradicting "provenance over assertion / honest states." Three different content types forced into one template.
- *Fix:* Differentiate by job: (a) the keys themselves become a list/table, not a stat card; (b) provider readiness becomes a small status list with real states (available / pending / error); (c) rotation guidance becomes a short prose aside with doc links — distinct shapes, not three clones.
- *Command:* `/impeccable shape settings/api-keys — break the clone grid into keys-table + provider-status + guidance aside`

**P1 — Missing honest states + a11y gaps.**
- *What:* No loading/empty/error/`role="alert"`; icons not `aria-hidden`; bullets are `<p>` runs not `<ul>`; secondary `outline` used for the would-be primary action.
- *Why:* NOUS requires designed loading/empty/error and WCAG 2.1 AA; the current button hierarchy gives equal weight to "go back" and "create."
- *Fix:* Add skeleton/loading, an honest empty state ("No API keys yet — create one to call the model and integration APIs"), an error `role="alert"`, `aria-hidden` on decorative icons, semantic `<ul>` for detail lists, and make the real CTA `variant="accent"` (or `erebus`) so it's visually primary.
- *Command:* `/impeccable harden settings/api-keys — loading/empty/error states, aria-hidden icons, semantic lists, promote primary CTA`

**P3 — Voice nit.**
- *What:* "operators and systems", "integration readiness" lean enterprise-jargon; PRODUCT.md voice is plain, exact, sentence-case.
- *Why:* Mild tone drift from "expert colleague" toward admin-console copy.
- *Fix:* Tighten to plain sentences: "Personal and workspace keys you can use to call the API."
- *Command:* `/impeccable clarify settings/api-keys copy`

---

### Minor observations

- "Return to Settings Overview" + "Create Token" as two equal-weight outline buttons in one row reads as a toolbar of equals; the back action belongs as a breadcrumb/link, not a peer button.
- `shadow-none` on the cards is fine, but combined with `bg-[var(--nous-bg-2)]` on `--nous-bg-1` ground the cards may have weak separation in light theme — verify the border carries the edge at AA.
- The page has generous bottom padding (`pb-20 md:pb-24`) for content that occupies barely a third of a viewport — the layout is sized for a real list that isn't there, reinforcing the placeholder feel.

---

### Questions

1. Is there a real API-keys endpoint/feature behind this, or is this page a stub ahead of the backend? (Determines whether this is "wire it up" vs "design the real thing.")
2. Are API keys per-user, per-workspace, or both? The copy implies both — the data model should drive the list grouping.
3. Does NOUS show a created key value once (and only once)? If so, the copy-and-warn moment is the most important interaction on the page and is currently absent.
