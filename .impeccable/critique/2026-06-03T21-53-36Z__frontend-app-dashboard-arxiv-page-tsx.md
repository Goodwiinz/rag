---
target: arxiv
total_score: 21
p0_count: 2
p1_count: 2
timestamp: 2026-06-03T21-53-36Z
slug: frontend-app-dashboard-arxiv-page-tsx
---
## NOUS /impeccable critique — ArXiv Management (`app/(dashboard)/arxiv/page.tsx`)

Register: **product**. The page is a thin shell rendering `src/components/arxiv/ArxivManagement.tsx` and four tab components (`TrackingTab`, `IngestTab`, `ExtractTab`, `StatsTab`) plus `ArxivControls`. The critique covers the whole subtree.

### Overall impression
Underneath the styling this is a genuinely competent product surface: a 4-tab workbench (track / ingest / extract / stats) with real loading, empty, error, and guest-locked states, correct tablist ARIA, switch-role toggles, an `aria-live` status region, and honest provenance-ish summaries (papers scanned, changes detected, dry-run vs applied). The architecture and state handling are solid.

The problem is the costume. This page is the single clearest violation of NOUS's stated identity in the codebase: it reintroduces the terminal/cyberpunk skin that DESIGN.md and PRODUCT.md say was "deliberately removed; do not reintroduce." The h1 literally reads `ARXIV_RESEARCH_HUB`. `font-mono` is on essentially every text node — headings, body copy, labels, stat values, buttons. Empty states use the `Terminal` lucide glyph as hero art. There's a fake "Live" pulsing dot beside an "Activity Feed," a "Grid Status Active" / "Synchronization latency: optimal" panel, and "System Statistics." None of NOUS's two body/heading typefaces (Inter, Source Serif 4) appear anywhere. The detector misses this (it scans for gradient/purple/glass/side-stripe), but to any reader this is unmistakably "a developer made a cyberpunk dashboard," and to a NOUS reviewer it is exactly the anti-reference.

### Heuristic scores (Nielsen 10)

| # | Heuristic | Score | Notes |
|---|-----------|:----:|-------|
| 1 | Visibility of system status | 3 | Strong: ProgressBar, per-operation labels, `aria-live` mirror, loading/refresh states. Loses a point because status leans on `COMPLETED:`/`ERROR:` log-prefix strings shown raw to users. |
| 2 | Match between system & real world | 2 | "ARXIV_RESEARCH_HUB", "Grid Status Active", "Synchronization latency: optimal", "Category Clusters", "System Papers" speak machine, not the plain scholarly voice PRODUCT.md mandates. |
| 3 | User control & freedom | 3 | Clear Search / Clear / Clear Selected, preset core/all/clear, dry-run toggle, send-IDs-to-extract handoff. No undo after queueing but that's a background job. |
| 4 | Consistency & standards | 2 | Internally consistent but inconsistent with the NOUS system: mono everywhere, two accents (Sol `text-primary` vs Helios `text-[var(--nous-helios)]`) used interchangeably, hardcoded `red-*` instead of Mars error tokens, custom toggles/slider instead of shadcn/Radix. |
| 5 | Error prevention | 3 | Good: invalid arXiv-ID validation with preview, disabled actions when no selection/categories, guest-gating destructive workspace actions. |
| 6 | Recognition over recall | 2 | Selected-categories chips and valid/invalid ID chips help, but paper IDs must be hand-pasted into Extract as a raw newline blob; the "E / T / K / C / S" feature codes in results demand recall. |
| 7 | Flexibility & efficiency | 2 | Enter-to-search and select-all are nice, but no keyboard model for the toggle grid beyond individual switches, no bulk paste-from-clipboard affordance, no saved searches; power users get little leverage. |
| 8 | Aesthetic & minimalist design | 1 | The weakest axis: terminal costume, mono-everywhere, dozens of uppercase tracked kickers, identical card grids, hero-metric stat blocks, sub-10px type, decorative giant ghost icons. This is ornament that does not inform. |
| 9 | Help users recover from errors | 2 | Errors render (`role` not always alert; the message box isn't `role="alert"` despite DESIGN requiring it), but they surface raw `ERROR: …` strings and Mars-red is faked with `red-950`. Recovery guidance is thin. |
| 10 | Help & documentation | 1 | No inline help, no explanation of what "extraction features" or "knowledge graph sync" do, no link to arXiv ID format, no tooltips. Researchers must already know the pipeline. |
| | **Total** | **21 / 40** | **Band: Acceptable** (borderline Poor on aesthetics). |

### Anti-patterns verdict (NOUS banned list)
- **Terminal / cyberpunk costume — PRESENT (severe).** `ARXIV_RESEARCH_HUB` heading, `Terminal` icon empty states (IngestTab, TrackingTab), fake "Live" pulse + "Activity Feed," "Grid Status Active," "Synchronization latency: optimal." This is the headline failure.
- **Mono everywhere — PRESENT (severe).** `font-mono` on every heading, paragraph, label, stat, and button across all six files. Inter/Source Serif 4 never used.
- **Repeated uppercase tracked labels — PRESENT (severe).** `uppercase tracking-[0.14em–0.25em]` kickers appear dozens of times; DESIGN.md allows one per section.
- **More than one accent hue — PRESENT (moderate).** Sol (`text-primary`) and Helios (`text-[var(--nous-helios)]`) are used side-by-side as if two distinct accents (e.g., stat cards color "Active" Helios and "Tracked" Sol with no semantic logic), reading as two hues.
- **Hardcoded color / not using tokens — PRESENT (moderate).** Errors use `border-red-900 bg-red-950 text-red-300` instead of the Mars `--nous-*` error token. Violates "never hardcode … use semantic tokens."
- **Hero-metric template — PRESENT (mild).** StatsTab's 4 big-number cards with ghost background icons, plus the sidebar 2×2 metric grid, are the big-number-+-label template the docs call out.
- **Identical card grids — PRESENT (mild).** The header's three "Search / Queue / Extract" cards are an identical icon-state-title-description grid.
- **Glassmorphism / gradient text / side-stripe borders — ABSENT (good).** Detector confirms clean: no `bg-clip-text`, no purple gradients, no `border-l-4` accent. Tokens (`var(--nous-*)`) are used correctly for surfaces and borders.
- **Em dashes — ABSENT (good).** Copy uses ellipses, not em dashes.

**Detector result:** empty `[]` for all six arxiv files (verified the detector works by firing it on a synthetic bad file — it flagged side-stripe + purple). This is a *true negative on the patterns it covers* (no gradient text, no glass, no purple, no side-stripe, tokens used), **not** a clean bill of health: the dominant violations here (terminal copy, mono-everywhere, uppercase-kicker scaffolding, hardcoded `red-*`) are outside the detector's regex set. Treat detector silence as "the slop here is the kind regex can't see."

### AI-slop verdict: YES
Someone would say "AI made this" — not because of the usual purple-gradient tells (those are absent), but because of the relentless mono + uppercase-tracked + fake-telemetry treatment. "Grid Status Active," "Synchronization latency: optimal," and a pulsing "Live" dot on a feed that only updates after you click are pure theater. It reads as a generated "futuristic dashboard," which is precisely the costume NOUS removed.

### Persona red flags
Interface type is dashboard/data, so: Alex (power user) + Sam (a11y/low-vision).

- **Alex (power researcher):** Wants to dump 80 paper IDs and extract. Has to paste a raw newline blob into a textarea, eyeball a chip cloud capped at 20 to confirm parsing, and decode result status from "E / T / K / C / S" letter codes. No saved searches, no keyboard nav across the toggle grid, no way to re-run last scan. The mono micro-type slows scanning rather than speeding it.
- **Sam (low-vision / AA):** Body text at `text-[8px]`, `text-[9px]`, `text-[10px]` in mono is below comfortable reading size and likely fails AA contrast in muted-foreground at those sizes. Error blocks use `red-300` on `red-950` (hardcoded, not the contrast-checked Mars token). The error/status box is not `role="alert"` (DESIGN requires it); only a separate `sr-only aria-live="polite"` mirror exists, so urgent failures aren't announced assertively. "Live"/status meaning is encoded partly in color (Sol vs Helios) with no non-color cue.

### What's working (strengths)
1. **Honest, designed states.** Real loading (spinner + "Loading metrics…"), empty ("Run a search to build your ingestion list"), error, and guest-locked branches everywhere — exactly the "honest states" principle, even if the wrapper styling is off.
2. **Accessibility scaffolding is above average.** Correct `role="tablist"/"tab"/"tabpanel"` with `aria-selected`/`aria-controls`/`aria-labelledby`, `role="switch"` + `aria-checked` toggles, `aria-pressed` on result cards, `aria-hidden` on decorative icons, focus-visible rings, and an `aria-live` status region.
3. **Sensible information architecture & motion discipline.** Four well-scoped tabs, a clear guest-vs-workspace split, validation before destructive actions, and animations on transform/opacity/filter only (no animated layout properties) per DESIGN's motion rules.

### Priority issues

**P0 — Remove the terminal costume.**
- *What:* `ARXIV_RESEARCH_HUB` heading, `font-mono` on every text node, `Terminal` icon empty states, fake "Live" + "Activity Feed," "Grid Status Active" / "Synchronization latency: optimal."
- *Why:* Directly violates the #1 NOUS anti-reference ("do not reintroduce the terminal skin"). Destroys the scholarly-warm identity and the trust posture PRODUCT.md depends on.
- *Fix:* Rename to sentence-case "arXiv management." Switch headings/body to Inter + Source Serif 4 (`--nous-font-*`); reserve mono for actual code/IDs only. Replace `Terminal` empty-state glyphs with neutral content-relevant icons or none. Delete "Live"/"Activity Feed"/"Grid Status Active"/"Synchronization latency" copy; label the panel "Last scan" or remove it.
- *Command:* `/impeccable distill app/(dashboard)/arxiv --strip terminal-costume --register product`

**P0 — Detox typography to the NOUS type system.**
- *What:* Mono-everywhere plus 30+ `uppercase tracking-[…]` kickers and `text-[8px]/[9px]/[10px]` sizing.
- *Why:* DESIGN allows one uppercase kicker per section and bans mono-as-decoration; sub-10px mono fails legibility and AA for the low-vision persona.
- *Fix:* Inter for UI/labels/data, Source Serif for descriptive sentences, mono only for arXiv IDs and `state_file_path`. Cap uppercase kickers at one per section. Floor body/label type at the `.nous-caption`/`text-xs` step (~12px).
- *Command:* `/impeccable harden app/(dashboard)/arxiv --typography --a11y AA`

**P1 — Collapse to one accent and tokenize errors.**
- *What:* Sol (`text-primary`) and Helios (`text-[var(--nous-helios)]`) used interchangeably; errors hardcoded as `red-900/950/300`.
- *Why:* Reads as two accent hues (banned: >1 accent); hardcoded `red-*` violates "never hardcode hex/`text-*`, use Mars `--nous-*` tokens."
- *Fix:* Pick one Sol accent for emphasis; use Helios only as hover/bright per the token system, not as a parallel category color. Replace all `red-*` with the Mars error tokens and give the error box `role="alert"`.
- *Command:* `/impeccable colorize app/(dashboard)/arxiv --accent sol --tokens nous`

**P1 — Replace template metric grids and clean up status copy.**
- *What:* StatsTab 4-big-number hero grid + sidebar 2×2 metric grid + identical 3-step header cards; raw `COMPLETED:`/`ERROR:` log prefixes shown to users.
- *Why:* Hero-metric template and identical card grids are named anti-patterns; raw log prefixes are machine voice, not the calm expert voice.
- *Fix:* Differentiate the metric blocks (one lead figure + supporting context with rhythm, not four equal tiles with ghost icons); merge or drop the redundant header step-cards. Strip `COMPLETED:`/`ERROR:` prefixes; render status with an icon + plain sentence.
- *Command:* `/impeccable shape app/(dashboard)/arxiv/tabs --break-template --voice plain`

**P2 — Power-user & input ergonomics.**
- *What:* Paste-only ID entry, 20-chip parse cap, letter-coded result features, no saved/last query, limited keyboard model on toggle grids.
- *Why:* Alex needs leverage; PRODUCT.md targets dense expert workflows.
- *Fix:* Add bulk-paste affordance + "X IDs detected, Y invalid" summary instead of a truncated cloud; expand feature codes to readable chips already labeled in the toggles; remember last search/categories; ensure roving-tabindex or arrow-key support across toggle grids.
- *Command:* `/impeccable optimize app/(dashboard)/arxiv --persona alex-poweruser`

### Minor observations
- StatsTab "Category Distribution" bars use inline `style={{ width }}` (acceptable for data-viz) but the bar color `bg-primary/40` plus mono labels feels weak; consider the sanctioned data-viz palette and larger labels.
- ProgressBar adds `shadow-[0_0_10px_var(--nous-sol-glow)]` glow — a faint phosphor-glow tell; drop the glow for a flat fill.
- `state_file_path` is exposed verbatim in the UI ("State file: …") — internal plumbing leaking to users; hide or relabel.
- The 3 header pills ("Public Search / Live Stats / Workspace Actions Locked") plus the sidebar "Current Mode / Discovery Mode / Guest" panel duplicate the same guest-state message three times above the fold.
- Custom `ToggleSwitch`/`CustomSlider` reimplement shadcn/Radix primitives DESIGN says to prefer; migrating gains keyboard/ARIA baselines for free.

### Questions
1. Is the always-mono treatment intentional house style for "technical" tools, or inherited from the removed terminal skin? (DESIGN says the latter is banned.)
2. The "Live"/"Activity Feed" panel — is anything actually streaming, or is it static until a manual scan? If static, the live framing is misleading and should go.
3. Should guests see the workspace-locked tabs at all, or land on a search-only view? Three simultaneous "sign in to unlock" treatments may be redundant.
4. Are the Mars/Terra/Corona status tokens available in this theme? If so, the hardcoded `red-*` is a straightforward swap; confirming unblocks P1.
