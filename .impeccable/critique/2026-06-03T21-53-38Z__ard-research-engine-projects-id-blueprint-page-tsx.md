---
target: blueprint
total_score: 31
p0_count: 0
p1_count: 3
timestamp: 2026-06-03T21-53-38Z
slug: ard-research-engine-projects-id-blueprint-page-tsx
---
## /impeccable critique — Blueprint Editor (`research-engine/projects/[id]/blueprint`)

Register: **product**. Surface: a blueprint/pipeline editor — name field, ordered step cards, a global-parameters sidebar, and save/run actions. Thin page shell delegating to `BlueprintEditor`, which composes `StepCard`, `SourceSelector`, `TemplateSelector`.

### Overall impression
This is one of the more disciplined product surfaces in the codebase. It reads as a calm research instrument, not a costume: single Sol accent (`text-primary`/`bg-primary`), semantic tokens end to end, no hardcoded hex, no gradient text, no glassmorphism, no terminal cosplay. Loading, empty, and error states are all genuinely designed rather than bolted on, and the accessibility baseline (focus-visible rings, `aria-label` on every icon-only button, `role="alert"` on errors, `role="status"` on loaders, label/`htmlFor` pairing) is well above average. The detector returned **zero hits**.

What keeps it at "Good" rather than "Excellent" is the *interaction model*, not the visuals. The save / edit / run lifecycle has a quiet trap (run ignores unsaved edits), the global-parameters panel maintains two sources of truth that can drift, and reordering steps is mouse-dependent and buried. These are the things that bite a real researcher mid-session.

### Heuristic scores

| # | Heuristic | Score | Notes |
|---|-----------|-------|-------|
| 1 | Visibility of system status | 3 | Loading skeleton, spinners on Save/Start, `role="status"`. But **Save success is silent** — no toast/confirmation, no "saved" state. User can't tell if a save landed. |
| 2 | Match between system & real world | 3 | Plain sentence-case labels, scholarly voice. But "Start run" silently runs the *saved* blueprint, not what's on screen — violates the user's mental model of "run what I see". |
| 3 | User control & freedom | 3 | Back link, move/remove steps, retry on error. No undo for step removal, no unsaved-changes guard on navigation. |
| 4 | Consistency & standards | 4 | Cards, inputs, focus rings, chips all consistent; reuses shadcn `Popover`/`Checkbox`. Strong. |
| 5 | Error prevention | 2 | **Dual params source** (quick fields vs raw JSON) can desync; **no unsaved-edit protection** before run/navigate; destructive "Remove step" has no confirm. JSON validates live (good), but structural traps remain. |
| 6 | Recognition over recall | 3 | Step type/mode/model are pickers not free text; sources are labelled. But step config (type, mode, model, temp, seed) is hidden behind per-card expand — collapsed cards show only name/type/mode, so comparing steps means recalling. |
| 7 | Flexibility & efficiency | 2 | Reorder is mouse-only via arrows inside expanded body; no drag-handle, no keyboard reorder at list level, no duplicate-step, no expand/collapse-all. Power-user friction on the core task. |
| 8 | Aesthetic & minimalist | 4 | Restrained, single accent, deliberate spacing, mono confined to JSON/IDs (sanctioned). Genuinely on-brand. |
| 9 | Help users recover from errors | 3 | Errors use `role="alert"` + inline Retry; JSON error is specific-ish. But "Invalid JSON" gives no position/reason, and run/save failures only show a generic message. |
| 10 | Help & documentation | 2 | No hint on what a "step type" does, what deterministic vs exploratory means, or why Start run is disabled. The raw-JSON escape hatch assumes schema knowledge with zero docs. |

**Total: 31 / 40 — Good.**

### Anti-patterns verdict
**Clean.** Detector returned `[]`. Manual pass confirms: no `--terminal-*`/phosphor, no `font-mono` sprawl (only JSON textareas + ID display, both sanctioned by DESIGN.md), no second accent hue, no hardcoded hex or `text-gray-*`, no gradient text, no default glassmorphism, no side-stripe borders, no hero-metric block, no em dashes in copy. The two sidebar cards are *not* an identical icon-card grid (distinct content/shape). Single warm-gold accent throughout. **AI-slop: no.**

### Cognitive-load checklist (8)
1. Primary action obvious? **Partial** — Save and Start run compete; Start run only appears post-save with no signposting.
2. Scannable hierarchy? Yes — header / steps / sidebar reads cleanly.
3. Consistent patterns? Yes.
4. Progressive disclosure? Yes (per-card expand) — but no overview/compare mode.
5. Recall burden? Medium — collapsed cards hide config; raw-JSON assumes schema memory.
6. Error states honest? Yes.
7. Empty/loading honest? Yes — strong.
8. Destructive actions guarded? **No** — Remove step is one-click, no undo/confirm.

### Persona red flags
Interface type = data/editor tool → **Alex (power user)** + **Sam (a11y)**.

- **Alex** builds a 10-step blueprint, reorders three of them, tweaks a temperature, then hits **Start run** without saving — the run uses the stale saved blueprint and his edits vanish into the ether with no warning. He also can't drag to reorder or keyboard-reorder from the list; every move means expand → click arrow → collapse. For the person this tool exists for, the core loop is slow and quietly lossy.
- **Sam (keyboard/SR)** can operate the form (labels and focus are solid), but step **reordering is only reachable after expanding each card**, and the move buttons are deep in the expanded body — there's no list-level "move up/down" or announced reorder. Removing a step gives no confirmation and the focus likely lands nowhere predictable. "Invalid JSON" is announced via `role="alert"` (good) but gives no actionable detail.

### Priority issues

**P1 — Run ignores unsaved edits (silent data loss).**
*What:* `handleStartRun` runs `blueprint.id` + `globalParams`, but the edited `steps`/`blueprintName` only reach the backend via `handleSave`. The Start-run button is enabled whenever a saved `blueprint` exists and `steps.length > 0`, so a user who edits then runs executes the *previous* saved version.
*Why:* Breaks "run what I see"; produces wrong results with zero feedback — corrosive for a provenance-first research tool.
*Fix:* Track a `dirty` flag (compare current steps/name/params to last-saved). Disable Start run while dirty with a tooltip "Save changes to run", or auto-save before run. Add a beforeunload / route guard for unsaved edits.
*Command:* `/impeccable harden research-engine/projects/[id]/blueprint --focus=save-run-lifecycle`

**P1 — Two sources of truth for global parameters.**
*What:* Quick fields (topic, dates, sources) and the Raw JSON textarea both write `globalParams`. Quick fields manually re-stringify into `globalParamsText`; editing Raw JSON sets `globalParams` but quick-field reads use `?? ''`/`?? defaults`. The `sources` default array (`arxiv/semantic_scholar/...`) is shown as if selected but is never written to `globalParams` until the user touches the selector — so a save can omit sources the user believed were chosen.
*Why:* Classic desync trap; the displayed state and the persisted state disagree → error-prevention failure on the exact values a run depends on.
*Fix:* Single source of truth — derive the textarea from `globalParams` (controlled, formatted on blur) and make quick fields pure setters. Persist the sources default explicitly into `globalParams` on load so what's shown is what's saved.
*Command:* `/impeccable clarify research-engine/blueprint/global-parameters --single-source-of-truth`

**P1 — Step reordering is mouse-only and buried.**
*What:* Up/down controls live inside each card's expanded body; collapsed cards have no reorder affordance. No drag handle, no keyboard list reorder, no expand/collapse-all.
*Why:* Reordering is a primary task in a pipeline editor; current flow is high-friction for Alex and not reachable for Sam without expanding each card.
*Fix:* Surface move up/down (or a drag handle with keyboard fallback, e.g. dnd-kit with arrow-key reorder + SR announcements) on the collapsed card row. Add an "Expand all / Collapse all" control.
*Command:* `/impeccable optimize research-engine/blueprint/step-list --reorder --a11y`

**P2 — No save confirmation; unguarded step removal.**
*What:* Save success produces no visible change (`blueprint` updates silently). "Remove step" deletes immediately with no confirm or undo.
*Why:* Visibility-of-status and user-control gaps; a mis-click loses configured step work.
*Fix:* Add a transient "Saved" status (toast or inline timestamp "Saved 12:04"). Add undo-on-remove (snackbar) or a confirm for non-empty steps.
*Command:* `/impeccable harden research-engine/blueprint --focus=feedback-and-undo`

**P3 — Disabled/missing actions are unexplained; thin in-context help.**
*What:* Start run is `disabled` when `steps.length === 0` with no tooltip; before first save it simply doesn't render. Deterministic vs exploratory, step types, and the raw-JSON schema have no inline explanation.
*Why:* Help/docs and recognition gaps; new users guess.
*Fix:* Add `title`/tooltip on disabled Start run ("Add at least one step"); a one-line helper under the steps header; short popover definitions for mode/type.
*Command:* `/impeccable clarify research-engine/blueprint --inline-help`

### What's working
- **Honest states throughout** — distinct loading skeleton with `role="status"`, dashed empty state with a clear CTA, inline `role="alert"` errors with Retry. Best-in-class for this codebase.
- **Token discipline + single accent** — semantic tokens and `text-primary` only; mono restricted to JSON/IDs. Reads scholarly-warm, fully on-brand, detector-clean.
- **Accessibility baseline** — `htmlFor` labels (incl. `sr-only` for the name field), `aria-label` on icon buttons, `aria-hidden` on decorative icons, `aria-expanded` on the card header, `aria-pressed` on the mode toggle, `aria-invalid` on the JSON fields.

### Minor observations
- `StepCard` uses a `<button>` as the expand header containing chip `<span>`s — fine (no nested buttons), but the whole row toggling means the type/mode chips aren't independently focusable for quick edits.
- Mode toggle inside the card and the collapsed-row chip can momentarily disagree visually until re-render; cheap to unify.
- Temperature defaults to `0.7` display even when undefined/deterministic — reads as a set value when it isn't persisted.
- Blueprint "ID" is shown truncated with no copy affordance; provenance-minded users will want to copy it.

### Questions
1. Is Start run *supposed* to run only the saved blueprint, or should it run the current on-screen state? This determines whether the fix is "block dirty runs" or "auto-save then run".
2. Is the `sources` default (`arxiv/semantic_scholar/crossref/pubmed`) meant to be implicit server-side, or must it be persisted? That decides whether the sources-desync is a real data bug.
3. Should the raw-JSON editor and quick fields ever both be visible, or is JSON an advanced/escape-hatch mode that could be collapsed by default to remove the dual-source confusion?
