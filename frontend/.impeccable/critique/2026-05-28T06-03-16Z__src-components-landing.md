---
target: landing page
total_score: 30
p0_count: 0
p1_count: 0
timestamp: 2026-05-28T06-03-16Z
slug: src-components-landing
---
# Critique — Landing Page (src/components/landing + app/page.tsx)

Brand register. Detector unavailable (bundle missing). Browser skipped (backend/auth dependency).

## Design Health Score: 30/40 (Good)
Dead links (#3,#10) and template-grammar tells (#8) cap the score; consistency/recognition strong (4s).

## Anti-Patterns Verdict
Passes first-order (not cyberpunk, not SaaS-cream). Second-order risk: warm-dark + Sol gold + uppercase tracked eyebrows + ruled separators drifts toward the editorial-typographic saturated lane. Inter display (not serif) + pre-committed NOUS identity keep it out of the ditch. Weakest tell: repeated uppercase tracked labels (AI scaffolding). Deterministic scan unavailable.

## Priority Issues
- [P2] Theme not scene-derived: dark chosen for identity, never justified; a light parchment variant may be warmer/more scholarly. -> live/colorize
- [P2] Repeated uppercase tracked labels (eyebrow + "Live knowledge graph" + footer heads) = AI scaffolding. -> typeset
- [P2] Dead links: #architecture, #docs, all footer href="#" break trust at evaluation. -> harden
- [P2] Stat row still the SaaS metric cliche; numbers read invented. -> distill
- [P3] Inline style={{fontFamily}} everywhere bypasses .nous-* helpers / Tailwind font utilities. -> polish

## Persona Red Flags
- Jordan (first-timer): Docs link dead -> reads as vaporware.
- Alex (technical): latency claims unproven; architecture dead link; KG may be static at hero size.
- Morgan (decision-maker): stats unsourced; no differentiator beyond "knowledge graph".

## Minor
- KG canvas lacks aria-label/role=img, not keyboard reachable.
- --nous-dust on --nous-nyx small text borderline AA (~4.5:1).
- HeroProcessCard now orphaned (dead code).

## Questions
- Would a light NOUS landing read better for a knowledge tool?
- Which single metric is defensible?
- What claim can only NOUS make?
