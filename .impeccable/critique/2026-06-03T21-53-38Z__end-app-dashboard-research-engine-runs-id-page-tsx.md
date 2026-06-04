---
target: [id]
total_score: 31
p0_count: 1
p1_count: 2
timestamp: 2026-06-03T21-53-38Z
slug: end-app-dashboard-research-engine-runs-id-page-tsx
---
## /impeccable critique — Research Engine: Run detail

`app/(dashboard)/research-engine/runs/[id]/page.tsx` · register: **product**

The route file is a 19-line wrapper (`container mx-auto max-w-7xl p-6` → `<RunView runId={id} />`). All design substance lives in `src/components/research-engine/RunView.tsx` and `StepProgress.tsx`, so this critique scores those.

### Overall impression

This is one of the better-behaved NOUS surfaces. It reads as a calm research instrument, not a costume: a single Sol/gold accent, status-as-status (not decoration), genuinely designed loading/empty/error states, and provenance (sources, quality checks, token counts, inspectable prompts) treated as first-class. It is not AI-slop. But it carries one serious correctness-as-UX bug that defeats the page's entire reason to exist for any run that is not currently live, plus a couple of honest error-recovery gaps. Strong bones, one load-bearing crack.

### Nielsen heuristic scores

| # | Heuristic | Score | Notes |
|---|-----------|-------|-------|
| 1 | Visibility of system status | 3 | Skeleton (not center spinner), live status badge with pulsing dot, per-step running/complete/error icons, streaming token totals. Excellent for live runs — but status is invisible for completed/failed runs (steps never render). |
| 2 | Match between system & real world | 3 | Plain sentence-case ("Waiting for the run to start", "Started …"). "tok"/"Deterministic"/"Exploratory"/"quality marks" are domain-appropriate for expert users. |
| 3 | User control & freedom | 3 | Back button, Pause/Resume, expandable steps, collapsible prompt, Retry on error. No cancel/abort of a run, no way out of a stuck pending state. |
| 4 | Consistency & standards | 4 | Status tokens (primary/helios/terra/mars via `--nous-*`) used consistently across badge, borders, step icons. Focus rings, `aria-hidden`, `tabular-nums` applied uniformly. |
| 5 | Error prevention | 3 | Disabled buttons during action loading prevents double-submit. No confirmation on Pause (low stakes, fine). Malformed SSE JSON skipped gracefully. |
| 6 | Recognition vs recall | 3 | Step name, type, mode, quality, tokens all visible inline. But quality-mark check names hide behind `title` tooltips when collapsed; full run ID never shown. |
| 7 | Flexibility & efficiency | 2 | No keyboard shortcut to expand all, no copy-run-ID, no link to artifacts/output beyond a 500-char truncated preview. Power users (Alex) will want more. |
| 8 | Aesthetic & minimalist design | 4 | Restrained, warm, single accent. Density with rhythm. No ornament. Genuinely on-brand for the Observatory. |
| 9 | Help users recover from errors | 2 | Run-level error has `role="alert"` + Retry (good). But Pause/Resume failures are swallowed in empty `catch {}` — the button just silently does nothing. SSE failures only `console.error`. |
| 10 | Help & documentation | 1 | None. No explanation of what "deterministic vs exploratory" mode means, what a quality mark is, or what step types signify. Acceptable-ish for experts but a tooltip/legend would help. |

**Total: 31 / 40 — Good.** (Honest band; the P0 keeps it out of Excellent.)

### Anti-patterns verdict (NOUS banned list)

- Terminal costume (`--terminal-*`, phosphor, glitch, HUD): **none.**
- `font-mono` everywhere: **clean.** Two uses, both on JSON output and prompt `<pre>` — exactly the sanctioned "code, tiny technical labels only" case.
- >1 accent hue: **clean.** Sol/gold is the only identity accent; terra/corona/mars/helios appear only as semantic *status* tokens, which DESIGN.md explicitly sanctions.
- Hardcoded hex / `text-gray-*`: **none.** All color via semantic shadcn tokens or `--nous-*` vars (`var(--nous-helios)`, `var(--nous-terra)`, `var(--nous-mars)`).
- Gradient text, glassmorphism-default, side-stripe borders, hero-metric template, identical card grids, em dashes: **none found.** (Copy uses hyphens "- details", not em dashes.)

**Detector:** `detect.mjs --json` on page + RunView + StepProgress returned `[]` (exit 0). No false positives to note — genuinely clean. **AI-slop verdict: NO.** Nobody would say "an AI made this" from the visual language; the failure here is functional, not stylistic.

### Cognitive load (8-item check)

1. Visual hierarchy — clear (header → status → steps). ✓
2. Color carries meaning redundantly — yes (dot + label + sr-only). ✓
3. Grouping/spacing — good, `space-y` rhythm, no cards-in-cards except the expanded step body which is acceptable. ✓
4. Progressive disclosure — strong (collapsed steps, nested prompt section). ✓
5. Text density — appropriate for expert audience. ✓
6. Number formatting — `toLocaleString()` + `tabular-nums` throughout. ✓
7. Scanning — header flex-wrap can reorder items unpredictably at narrow widths (minor). ⚠
8. Decision points — Pause/Resume clear; but silent failure adds hidden load ("did it work?"). ⚠

### Persona red flags

**Alex (power user / data):**
- Opens a completed run from the runs list or a shared deep link → sees "No steps received yet." The run *has* full history; the page just never fetches/hydrates it. Alex concludes the run is empty or the page is broken. **This is the dealbreaker.**
- Can't copy the full run ID (only `runId.slice(0,8)` shown), can't expand all steps at once, output capped at 500 chars with a `...` and no "view full".

**Sam (accessibility):**
- Mostly well served: `role="status"`/`role="alert"`, `aria-expanded`, `aria-label` on icon buttons, `sr-only` status text, `motion-safe:` on all animation. Strong.
- Gap: quality-mark pass/fail relies on `title` tooltips for the check name in the collapsed row — `title` is not reliably exposed to all AT or reachable by keyboard. The expanded view does list them properly, so this is a soft flag.
- Gap: silent Pause/Resume failure is *never announced* — a screen-reader user gets zero feedback that an action failed.

### Priority issues

**P0 — Completed/failed runs render no steps (core data-visibility bug).**
- *What:* `steps = buildStepsFromEvents(runEvents)` is built **only** from live SSE events, and the SSE effect early-returns unless `status === 'running' || 'pending'`. `runEvents` is cleared on mount/unmount and never seeded from `activeRun`. So any terminal-state run opened fresh shows the empty state.
- *Why it matters:* This page is "the run detail view." Its primary content disappears for the majority of real visits (people review finished runs far more often than they watch live ones). PRODUCT.md's "honest states / provenance over assertion" is violated — the UI implies there were no steps.
- *Fix:* Hydrate steps from `activeRun` (persisted step/event history from `getRun`) on load, then merge live SSE events on top for running/pending. Empty state should only show when the *fetched run* genuinely has zero steps.
- *Command:* `/impeccable harden app/(dashboard)/research-engine/runs/[id] --states "completed,failed,pending,running" --hydrate-from-fetch`

**P1 — Silent Pause/Resume failures.**
- *What:* `handlePause`/`handleResume` use empty `catch {}` — on failure the button finishes loading and nothing changes; no toast, no inline alert, no announcement.
- *Why:* Pausing a costly research run is a meaningful action; "did it work?" with no answer erodes the trust PRODUCT.md centers. Fails Heuristic 9 and is invisible to AT.
- *Fix:* Surface failures via a `role="alert"` toast or inline message; keep the optimistic state honest (revert + explain on error).
- *Command:* `/impeccable repair-states RunView --actions pause,resume --error-feedback toast`

**P1 — Empty-state copy masks the real gap.**
- *What:* "No steps received yet" / "Steps stream in here as the run progresses" is written only for the live case. For a completed run it's actively misleading.
- *Why:* Honest states is a NOUS design principle; this copy lies about a fetch failure.
- *Fix:* Branch copy by status (loaded-but-empty completed run → "This run recorded no steps" or, ideally, never reach this branch once P0 is fixed). Distinguish "fetch failed" from "genuinely empty."
- *Command:* `/impeccable copy RunView --empty-states --by-status`

**P2 — Header crowding + no run-ID affordance.**
- *What:* Back, title+timestamp, status badge, token counter, and Pause/Resume share one `flex-wrap` row; truncated 8-char ID with no copy.
- *Why:* Wrapping reorders/crowds at tablet widths; power users want the full ID for support/logs.
- *Fix:* Give the header a two-zone layout (identity left, actions right) that degrades predictably; add a copy-ID button with `aria-label`.
- *Command:* `/impeccable shape RunView --region header --responsive`

**P3 — No help for domain terms / output truncation.**
- *What:* "Deterministic/Exploratory" mode, quality "check_type", and 500-char output cap with bare `...` go unexplained / non-expandable.
- *Fix:* Small popover/legend for mode + quality semantics; "Show full output" toggle.
- *Command:* `/impeccable clarify StepProgress --add-affordances output,mode-legend`

### What's working (strengths)

1. **Honest, designed states.** Skeleton placeholders (explicitly not a center spinner, per the code comment), distinct pending vs no-steps empty copy, `role="alert"` error with a working Retry. This is exactly the NOUS "honest states" principle, executed.
2. **Provenance is first-class.** Per-step Sources chips, Quality checks (pass/fail with details), token accounting, and an inspectable Prompt section deliver "the interface earns trust by showing its work" — the single best PRODUCT.md alignment on the page.
3. **Disciplined, on-brand visual system.** One gold accent, semantic status tokens via `--nous-*`, no hardcoded hex, no mono-as-decoration, redundant color encoding, `motion-safe:` guards, `tabular-nums`. Detector clean. This is what restrained product register should look like.

### Minor observations

- `outputPreview` JSON.stringify runs on every render of an expanded step; fine at this scale but memoize if outputs grow.
- `key={i}` on quality-mark and source maps (index keys) — acceptable for static lists, but stable IDs are safer if these reorder.
- Status badge `motion-safe:animate-pulse` on the running dot is a nice, restrained touch and correctly motion-gated.

### Questions

1. Does `getRun(runId)` already return step/event history? If yes, P0 is a small wiring fix (hydrate `runEvents` or `steps` from it). If not, the backend needs a step-history field — which scopes the fix.
2. Is there a runs *list* page that links here, and does it link to completed runs? (If so, P0 is hit constantly today.)
3. Should Pause/Resume optimistically update status before `fetchRun` resolves, or is the current fetch-after-action latency acceptable for the live-streaming UX?
