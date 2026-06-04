---
target: quality-metrics-demo
total_score: 26
p0_count: 1
p1_count: 2
timestamp: 2026-06-03T21-53-37Z
slug: ontend-app-dashboard-quality-metrics-demo-page-tsx
---
## /impeccable critique — Quality metrics demo (`quality-metrics-demo/page.tsx`)

**Register:** product · **Surface type:** data dashboard / metrics panel

A two-card page: a config card (query input + explanatory prose) feeding a `QualityMetricsCard` that shows retrieval-quality figures, a performance row, and a live/sample connection indicator. The bones are restrained and on-brand. The problems are honesty-of-data and one off-system control.

### Nielsen heuristic scores

| # | Heuristic | Score | Notes |
|---|-----------|:----:|-------|
| 1 | Visibility of system status | 3 | Connection state shown ("Live connection" / "Sample values" dot), `role="status"`, last-updated timestamp, confidence badge. But no *loading* state — panel reads all-zeros (`0.0%`, `0`, `—`) on first paint before the 2s interval fires, which looks like real "zero quality" rather than "not yet loaded." |
| 2 | Match between system & real world | 3 | Plain sentence-case labels ("Answer relevancy", "Faithfulness", "Safety score"), `ms`/`s` latency formatting, sensible terms for researchers. "Safety score = 100 − hallucinationRisk" is a silent inversion the user can't see; the default query `abdel factual` is dev cruft that leaks a real name. |
| 3 | User control & freedom | 2 | Auto-refresh can be toggled off (good). But the query field has no submit/apply/clear button — it's unclear whether editing re-evaluates, and there's no way to pause/snapshot a reading or pin a value. No way to escape the 2s churn except the global toggle. |
| 4 | Consistency & standards | 2 | Mostly uses semantic tokens and shadcn primitives, but the **Switch** ships `bg-orange-500` (on) and `bg-gray-200` (off) — a non-Sol hue and a banned gray. The toggle disagrees with the rest of the page's Sol/neutral system and with itself in dark mode. Status dots correctly use `--nous-terra/helios/mars`. |
| 5 | Error prevention | 3 | Low surface for user error (read-only panel). Random generator is clamped to plausible ranges. No destructive actions. |
| 6 | Recognition over recall | 3 | All metrics are labelled with units and quality bands ("Good/Fair/Low") plus a colored dot, so status isn't color-only. Trend-icon helper (`getTrendIcon`) is defined but never rendered — dead capability the user can't recognize because it isn't there. |
| 7 | Flexibility & efficiency | 2 | No keyboard shortcut, no way to compare queries, no export/copy, no debounce on the input (every keystroke is in scope of the live recompute via the `query` dependency). Power users get a single fixed 2s cadence with no control over interval. |
| 8 | Aesthetic & minimalist | 3 | Genuinely restrained: one card, a clean 2-col metric grid, a 3-col performance row, a quiet footer. Reads scholarly, not cyberpunk, not SaaS-cream. The four metric tiles are a near-identical grid (mild "identical card grid" pressure) but differentiated by the single Sol-accented headline figure, which is the right call. |
| 9 | Error recovery | 1 | **The core failure.** When the WebSocket is unavailable, the panel doesn't surface an error — it silently *fabricates* numbers via `Math.random()` and labels them "Sample values." A researcher glancing at "Faithfulness 84.2%" has no recovery path because nothing tells them the reading is fictional and re-rolling every 2s. No retry, no "connection lost — reconnect" affordance. |
| 10 | Help & documentation | 3 | The intro paragraph honestly explains the sample-data fallback ("representative sample values, refreshed every couple of seconds, so you can preview the layout"). That's a real strength. But no tooltips on what "Faithfulness" vs "Context relevancy" actually measure for the methodology-conscious user. |

**Total: 26 / 40 — Acceptable.** Solid product restraint and honest *copy*, dragged down by the data-honesty gap (H9), the off-system toggle (H4), and missing loading state (H1).

### Anti-pattern / banned-list verdict

| Check | Verdict |
|-------|---------|
| Terminal costume (`--terminal-*`, mono-everywhere, "Neural/Synthetic") | Clean — none present |
| >1 accent hue | **Violated** — `bg-orange-500` in the Switch is a second hue alongside Sol gold |
| Hardcoded hex / `text-gray-*` / `bg-gray-*` | **Violated** — `bg-gray-200` in the Switch (won't flip in dark mode) |
| Gradient text (`bg-clip-text`) | Clean |
| Glassmorphism-default | Clean |
| Side-stripe accent borders | Clean |
| Hero-metric template (big number ×N + gradient) | Borderline-OK — four metric tiles, but only one Sol-accented figure and no gradient, so it sidesteps the template |
| Identical card grids | Minor — 2×2 metric tiles are uniform but acceptable for a metrics panel |
| Em dashes in copy | Clean — uses the right em-dash-free voice; the literal `—` in JSX is a fallback glyph for "no value," not prose |
| Glitch/scanline/HUD theatrics | Clean |

**AI-slop verdict: NO.** This does not read as "AI made this." The copy is plain, sentence-case, and admits the sample-data caveat; color is restrained; no gradient/glass/mono costume. The slop risk here is *data theater* (random numbers dressed as measurement), not visual slop.

### Cognitive-load checklist (8-item)

1. **Visual hierarchy** — OK. One Sol headline figure, secondary figures neutral, clear section breaks.
2. **Information density** — OK for a research audience; not noisy.
3. **Grouping/proximity** — Good: config card vs metrics card, metric grid vs performance row separated by rules.
4. **Color economy** — Fails: orange toggle adds a hue the eye must account for.
5. **Motion/animation cost** — Moderate: every metric re-renders every 2s with new digits, drawing the eye constantly even when the user isn't reading — attention tax.
6. **Reading load** — Low; labels are short and clear.
7. **Decision load** — Low; few controls.
8. **State legibility** — Fails on first paint (all-zero panel) and on error (silent fabrication).

### Persona red flags

**Alex (power user / data-dense):**
- The 2s random re-roll makes the panel *untrustworthy for actual analysis* — Alex can't tell a real trend from noise, and can't lock a reading. The defined-but-unused trend arrows tease a capability that doesn't ship.
- No interval control, no export, no per-query comparison. Alex hits the ceiling immediately.

**Sam (accessibility):**
- The Switch relies on `bg-orange-500` vs `bg-gray-200` for on/off; in dark mode the gray won't flip and the contrast of the thumb/track is unverified against AA. State *is* exposed via Radix `aria-checked`, so it's not color-only, but the visual token is off-system.
- Live region: `role="status"` on the connection line is good. But the metric *values* update every 2s without an `aria-live` policy — a screen reader either ignores them (silent churn) or, if announced, floods. Neither is designed.
- First-paint zeros announced as real values to a screen reader with no "loading" semantics.

### What's working (strengths)

1. **Honest fallback copy.** The intro paragraph plainly tells the user the panel shows "representative sample values… so you can preview the layout." This is exactly the NOUS "honest states / admit uncertainty" principle — most teams would have hidden the simulation. The `isConnected ? 'Live connection' : 'Sample values'` dot reinforces it.
2. **Disciplined accent + status color.** The single Sol-accented headline figure (`metric.accent ? 'text-primary'`) against neutral siblings is the correct restrained-product strategy, and quality bands use the sanctioned `--nous-terra/helios/mars` status tokens with a *text label* ("Good/Fair/Low") so meaning isn't color-only.
3. **Solid semantic structure.** `aria-hidden` on decorative icons, `role="status"` on the live indicator, `aria-label` on the Switch, `tabular-nums` on every figure so digits don't jitter horizontally as they churn, proper shadcn primitives throughout.

### Priority issues

**P0 — Off-system toggle color (orange + gray).** `src/components/ui/switch.tsx` hardcodes `bg-orange-500` (checked) and `bg-gray-200` (unchecked). This introduces a second accent hue (banned: ">1 accent hue") and a `bg-gray-*` that won't theme-flip, both visible on this page's primary Auto-refresh control. *Why it matters:* breaks the one-Sol-accent identity and the dark-mode contract; in `.dark` the gray track stays light. *Fix:* swap to `data-[state=checked]:bg-[var(--nous-sol)]` and `data-[state=unchecked]:bg-input` (or `bg-muted`), using Radix `data-state` rather than a `checked` prop branch. *Command:* `/impeccable colorize src/components/ui/switch.tsx` (then re-run detector across all 72 Card/Switch call sites since this primitive is shared).

**P1 — Fabricated data presented as measurement.** `QualityMetricsCard` generates `Math.random()` figures every 2s when the WebSocket is down and renders them identically to real metrics. *Why it matters:* directly violates "Provenance over assertion / retrieval is honest" — a research instrument inventing quality scores is the worst possible trust failure. The "Sample values" dot is far too quiet for the severity. *Fix:* visually distinguish simulated mode — dim/desaturate the figures, overlay a "Sample data — not measured" ribbon, or replace with a true honest empty state ("No live connection. Connect a session to see retrieval quality."). Stop re-rolling random numbers; show static placeholder skeletons instead. *Command:* `/impeccable harden states quality-metrics-demo` (design loading / empty / sample / error as four distinct, labelled states).

**P1 — No loading or error state.** First paint shows `0.0%`, `0`, `—` (reads as "zero quality"); a failed WS produces no error UI, just silent fallback. *Why it matters:* H1 + H9 — the user can't tell "not loaded yet" from "genuinely zero," and a real connection error is invisible. *Fix:* render skeletons until `timestamp > 0`; on WS error surface a `role="alert"` line with a Reconnect action (the hook already exposes `reconnect`/`error`, which this component ignores). *Command:* `/impeccable harden states QualityMetricsCard`.

**P2 — Query input has no apply affordance / debounce.** Typing into "Query to evaluate" has an ambiguous effect — the value flows into `query` and influences the random generator's `length`-based seeding, but there's no submit button, no Enter handler, no debounce, and no visible "evaluating…" feedback. *Why it matters:* H3/H7 — the user can't tell whether or when their edit takes effect. *Fix:* add an explicit "Evaluate" button or debounced apply with a pending indicator; echo the *applied* query in the panel header. *Command:* `/impeccable clarify quality-metrics-demo` (input→result causality).

**P3 — Dev cruft in default state.** Default query `'abdel factual'` (a real-looking name fragment) is hardcoded in two places; the unused `getTrendIcon` helper is dead code teasing an unshipped feature. *Why it matters:* leaks dev context to users and inflates the component. *Fix:* default to a neutral placeholder query or empty; remove `getTrendIcon` or wire it up with a real previous-value reference. *Command:* `/impeccable distill QualityMetricsCard`.

### Minor observations

- **Detector blind spot:** `detect.mjs` returned `[]` for the page and all listed components *including* `switch.tsx` — it did not catch the `bg-orange-500` / `bg-gray-200` violation. Treat the orange/gray Switch finding as a manual catch the automated pass missed; worth extending the rule set.
- "Safety score" is computed as `100 - hallucinationRisk` with no exposure of the source metric — consider labelling or tooltipping the derivation.
- The four metric tiles use `rounded-xl border bg-card` *inside* a `rounded-xl ... bg-card` Card — cards-in-cards, which DESIGN.md explicitly discourages ("No cards-in-cards"). The tiles read as panels, but tonally they're the same surface as the parent; differentiate with `bg-muted/30` (as the query strip already does) rather than another `bg-card`.
- The config-card explanatory paragraph uses `text-sm ... leading-relaxed` Inter; per the type system, value-prop/explanatory prose is the place Source Serif 4 is meant to carry the scholarly voice — minor, optional.

### Questions

1. Is this "demo" route intentionally shipped into the authenticated `(dashboard)` group, or is it a scratch page? If it's reachable by real users, the fabricated-data behavior is a production trust issue, not a demo nicety.
2. Should the metric values announce to screen readers on update, or stay silent? That decision drives the `aria-live` policy.
3. Is the shared `Switch` orange/gray styling intentional brand drift, or legacy from before the NOUS Sol migration that the Card/Input/Badge files already went through (per their dated migration comments)?
