---
target: diagnostics
total_score: 21
p0_count: 2
p1_count: 2
timestamp: 2026-06-03T21-53-36Z
slug: frontend-app-dashboard-diagnostics-page-tsx
---
## /impeccable critique — Retrieval Diagnostics (product register)

**File:** `/home/clawdbot/clawd/rag/frontend/app/(dashboard)/diagnostics/page.tsx`
**Component:** `/home/clawdbot/clawd/rag/frontend/src/components/diagnostics/RetrievalDiagnosticsDashboard.tsx`
**Shared:** `/home/clawdbot/clawd/rag/frontend/src/components/ui/EmptyState.tsx`

### Overall impression

The information architecture here is genuinely good. Four tabs (Query Explorer, Quality Overview, Weight Tuner, Bottleneck Analysis) map cleanly onto the mental model of a retrieval pipeline, the master-detail trace explorer is the right pattern, and the weight tuner with auto-normalizing sliders is a thoughtful power-user affordance. An admin debugging retrieval would find the surface usable on day one.

But the page is wearing the exact costume DESIGN.md and PRODUCT.md say was "deliberately removed." The H1 renders `RETRIEVAL_DIAGNOSTICS` in `font-mono` uppercase with `tracking-wider`, the subtitle is mono uppercase, every empty state is mono with snake_case shouting copy (`NO_TRACES_CAPTURED`, `OPEN_SEARCH`), and recommendations are printed in `text-brand-cyan` — a legacy phosphor/terminal alias. This is scholarly-warm NOUS cosplaying as a 1980s ops terminal. The bones are product-grade; the skin is the banned aesthetic.

### Heuristic scores (Nielsen-10)

| # | Heuristic | Score | Notes |
|---|-----------|-------|-------|
| 1 | Visibility of system status | 3 | Loading text on every tab, ms/result/source counts surfaced, health badges. But loading is bare text ("Loading...", "Analyzing...") with no skeletons, and async failures are invisible to the user. |
| 2 | Match real world | 2 | Snake_case SHOUTING (`NO_TRACES_CAPTURED`, `OPEN_SEARCH`) is machine-speak, not the "plain, exact, sentence-case" voice PRODUCT.md mandates. "Healthy/Warning/Critical" labels are good. |
| 3 | User control / freedom | 2 | Refresh on each tab; sliders adjustable. No way to clear a selected trace, no deep-link/URL state for the active tab or trace, no cancel on in-flight experiments. |
| 4 | Consistency & standards | 2 | shadcn primitives used consistently, but the page violates its own design system: mono headers, `brand-cyan` accent, `red-500`/`red-400` hardcoded vs the `destructive` token used elsewhere in the same file. |
| 5 | Error prevention | 2 | Weight sliders auto-normalize to sum 1.0 (nice), Compare disabled on empty query. But the native `<select>` and Enter-to-run experiment have no guardrails, and there's no confirmation the custom weights differ from default before comparing. |
| 6 | Recognition vs recall | 3 | Default weights shown alongside custom, weights echoed as percentages, selected trace highlighted. Strong here. |
| 7 | Flexibility / efficiency | 3 | Tabs, refresh, slider tuning, Enter-to-submit, time-window select. Good for the Alex power-user persona; loses a point for no keyboard tab cycling beyond Radix defaults and no saved/preset weight configs. |
| 8 | Aesthetic / minimalist | 1 | The terminal costume is the dominant impression: mono everywhere it shouldn't be, uppercase tracked labels repeated on every section header (`SOURCES`, `FUSION`, `RERANKING`...), cards-in-cards (StatCard Cards inside grids inside tab content). Identical-card-grid smell on the stat row. |
| 9 | Error recovery | 1 | All four data loaders `catch` and only `console.error`. On failure the user sees a permanent "No data available" or an empty list with zero indication anything broke and no retry affordance distinct from the normal Refresh. This is the opposite of "honest error states." |
| 10 | Help / docs | 2 | Subtitle explains the page purpose; finding cards carry recommendations. No tooltips on dense metrics (truncation_ratio, avg_score, multi-source count) that a non-author admin would need defined. |

**Total: 21 / 40 — Acceptable** (high end; the IA is carrying a costume-laden skin).

### Anti-patterns verdict

| Banned pattern | Present? | Evidence |
|---|---|---|
| Terminal costume (font-mono everywhere, uppercase tracked) | **YES — flagrant** | H1 `text-2xl font-mono ... tracking-wider` = `RETRIEVAL_DIAGNOSTICS`; subtitle `text-xs font-mono ... uppercase tracking-widest`; EmptyState title/desc/button all `font-mono tracking-wider`; copy `NO_TRACES_CAPTURED`, `OPEN_SEARCH`. |
| >1 accent hue | **YES** | `text-brand-cyan` on `finding.recommendation` (lines 380, 849). `brand-cyan` → `var(--cyan)`, a legacy terminal alias and a second hue alongside Sol gold. |
| Hardcoded hex / `text-gray-*` / non-semantic color | **YES** | `bg-red-500`, `border-red-500/50`, `text-red-400` (lines 49, 172, 193, 280, 357, 540) instead of `destructive`/`--nous-mars`. Inconsistent — the same file uses `variant="destructive"` elsewhere. |
| Repeated uppercase tracked section labels | **YES** | `SOURCES`, `FUSION`, `RERANKING`, `CONTEXT ASSEMBLY`, `ISSUES FOUND` all `uppercase tracking-wider` — DESIGN.md: "one uppercase tracked kicker per section max; repeating it is AI scaffolding." |
| Cards-in-cards | **YES (minor)** | StatCard is a `<Card>` rendered inside grids inside `<TabsContent>`; Source Performance / Truncation Cards wrap StatCard Cards. |
| Identical icon-card grid / hero-metric template | Partial | 4-up StatCard row (Total Queries / Avg Time / Avg Results / Failures) is the big-number-+-label grid; tolerable for a dashboard but generic. |
| Gradient text / glassmorphism / side-stripe borders | No | Clean on these. |
| Em dashes in copy | No | Uses `&rarr;` arrows, not em dashes. |
| Color-only meaning | **YES** | `StageHealth` dots (`bg-primary`/`bg-[--nous-helios]`/`bg-red-500`) carry health with only the stage *name* beside them, not the status. PRODUCT.md: "Do not encode meaning in color alone." |

### AI-slop verdict: YES

A reviewer would say "AI made this," but specifically because it pattern-matched a *terminal dashboard* template: mono uppercase title, snake_case status strings, cyan-on-dark recommendations, repeated tracked-uppercase kickers, and an even 4-up metric grid. None of these match NOUS's scholarly-warm identity. The underlying React is clean and human-organized — the slop is purely in the visual skin and copy register.

### Cognitive load (8-item)

1. **Information density** — High but appropriate for admin/Alex; acceptable. ✓
2. **Visual hierarchy** — Weakened: every section header is the same uppercase-mono weight, so nothing leads. ✗
3. **Color coding clarity** — Three traffic-light colors plus cyan + gold = four signal colors competing; meaning unlabeled. ✗
4. **Progressive disclosure** — Good: master-detail trace, tabs gate complexity. ✓
5. **Consistent patterns** — Card/Badge reuse is consistent; color tokens are not. ◐
6. **Scannable metrics** — `123ms | avg score: 0.412` pipe-delimited runs are dense and unlabeled inline. ◐
7. **Clear affordances** — Trace rows are `<button>` (good), but look like static cards; selection only signaled by faint `bg-primary/10`. ◐
8. **Honest states** — Loading present, empty present, **error absent**. ✗

### Persona red flags

**Alex (power user / admin — the actual audience):**
- Loses work on failure: a flaky `getTrace` call silently no-ops; Alex clicks a trace, nothing happens, no error, no retry. Erodes trust in a *diagnostics* tool whose whole job is honesty about failures.
- No URL state — can't bookmark or share "the trace that shows the rerank fallback." Every share is "open diagnostics, go to Explorer, refresh, find it again."
- Metric definitions assumed: `truncation_ratio`, `multi_source_count`, `avg_score` have no tooltips; a second admin who didn't build the pipeline must guess.

**Sam (accessibility):**
- **Color-only health** (stage dots, score-delta red/green) fails WCAG 1.4.1 and PRODUCT.md's explicit "no meaning in color alone."
- Sliders (`Fulltext`/`Vector`/`Knowledge Graph`) rely on a `<label>` not programmatically tied to the Radix Slider thumb; verify `aria-label`/`aria-valuetext` so a screen reader announces "Vector 40%."
- Async results (experiment finished, traces loaded) are not announced — no `aria-live`/`role="status"`. Sam hears silence after pressing Compare.
- `red-400` text on dark and `bg-primary/10` selection states need contrast verification at AA.

### What's working (strengths)

1. **Genuinely good IA.** Four tabs that mirror the retrieval pipeline, a master-detail trace explorer, and an aggregate bottleneck view — this is the right decomposition of a complex domain, and it serves the task (product register done right structurally).
2. **The weight tuner is thoughtful.** Auto-normalizing three sliders to sum 1.0, side-by-side Default-vs-Custom comparison, and top-score readouts give Alex a real experimentation loop, not a toy.
3. **Honest empty + access states partially present.** The admin-gate uses `role="alert"` with calm sentence-case copy, and empty lists have a real EmptyState with a next-action CTA (`/search`) — the bones of honest states exist; they just need the costume removed and an error variant added.

### Priority issues

**P0 — Strip the terminal costume from headers and EmptyState.**
*What:* H1, subtitle, all section kickers, and EmptyState are mono/uppercase/tracked with snake_case copy (`RETRIEVAL_DIAGNOSTICS`, `NO_TRACES_CAPTURED`). *Why:* This is the explicitly-removed phosphor/terminal aesthetic and the wrong voice register — the single largest violation. *Fix:* H1 → `nous-h1` Inter, sentence case "Retrieval diagnostics"; subtitle → `nous-body` Source Serif or `text-muted-foreground`, not mono/uppercase. EmptyState: drop `font-mono tracking-wider`, rewrite copy to "No traces captured yet" / "Open search". Limit section headers to one tracked kicker per view or use plain `text-sm font-medium`.
*Command:* `/impeccable distill` then `/impeccable clarify`

**P0 — Remove the second accent hue (`text-brand-cyan`).**
*What:* Recommendations rendered in `text-brand-cyan` (legacy terminal alias). *Why:* Violates "one warm-gold Sol accent" and reintroduces a removed-theme token. *Fix:* Use `text-foreground` for recommendation body or `text-[var(--nous-fg-accent)]` if emphasis is needed; never `brand-cyan`.
*Command:* `/impeccable colorize`

**P1 — Add honest error states + replace hardcoded reds with tokens.**
*What:* All four loaders swallow errors to `console.error`; failure shows stale/empty UI with no retry. Reds are hardcoded (`red-500/400`). *Why:* A diagnostics tool that hides its own failures and uses non-semantic destructive colors contradicts both "honest states" and the token rules. *Fix:* Add `error` state per loader rendering an inline `role="alert"` with a Retry button; swap `red-*` for `destructive`/`--nous-mars`; gate dark-mode text on Parchment-equivalent contrast.
*Command:* `/impeccable harden`

**P1 — Fix color-only health signaling (a11y).**
*What:* Stage health dots and score deltas convey state purely by color. *Why:* WCAG 1.4.1 + explicit NOUS ban. *Fix:* Add a text label or icon to each stage dot ("Source — Healthy"), pair score-delta color with the existing +/- sign as the primary signal, and wrap async result regions in `role="status"`/`aria-live="polite"`.
*Command:* `/impeccable harden --a11y`

**P2 — De-nest cards and flatten the metric grid.**
*What:* StatCards (themselves `<Card>`) nested inside Cards/grids; identical 4-up metric row. *Why:* Cards-in-cards is banned; uniform grids read as template. *Fix:* Render stats as bordered cells in a single Card (no nested `<Card>`), vary emphasis so the alert metric (Source Failures) leads.
*Command:* `/impeccable shape`

### Minor observations

- Tab/trace selection has no URL state — add `searchParams` for shareable deep links.
- Inline pipe-delimited metrics (`123ms | avg score: 0.412`) would scan better as labeled key/value pairs.
- `FindingCard key={i}` and results `key={i}` use array index — fine here but brittle if lists reorder.
- Refresh buttons are `variant="ghost"` and easy to miss; consider an icon + label.
- The 4-up StatCard grid lacks responsive density tuning below `md`.

### Questions

1. Is `--brand-cyan` intended to survive the terminal-theme removal, or is every `brand-cyan`/`--cyan` call site (here and the ~1500 legacy ones noted in globals.css) slated for migration to Sol?
2. Should diagnostics state (active tab, selected trace, time window) be URL-addressable for sharing among admins?
3. Are the pipeline metric definitions (truncation_ratio, avg_score, multi_source_count) documented anywhere admins can reach, or should the page carry inline tooltips?
