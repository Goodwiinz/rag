---
target: "/projects + /research"
total_score: 30
p0_count: 0
p1_count: 2
timestamp: 2026-03-31T00:00:00Z
---

# Design Critique: /projects + /research

## Design Health Score: 30/40 (Good)

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Good loading skeletons; progress indicators could be more prominent |
| 2 | Match System / Real World | 3 | Clear terminology; "Matrix" and "Pipeline" may need onboarding |
| 3 | User Control and Freedom | 3 | AlertDialog for destructive actions; undo not available |
| 4 | Consistency and Standards | 4 | Excellent token usage; consistent component patterns |
| 5 | Error Prevention | 3 | Confirmation dialogs present; no undo for deletions |
| 6 | Recognition Rather Than Recall | 3 | Good icons; tab labels could be clearer for new users |
| 7 | Flexibility and Efficiency | 2 | 8 tabs in project detail is overwhelming; no keyboard shortcuts |
| 8 | Aesthetic and Minimalist Design | 4 | Clean, restrained, no AI slop |
| 9 | Error Recovery | 3 | Error states present; no undo for destructive actions |
| 10 | Help and Documentation | 2 | No inline help for Matrix/Pipeline; tooltips minimal |

## Priority Issues

### [P1] Project detail has 8 tabs — cognitive overload
Users must scan 8 options on every visit. Most users will only use 2-3 tabs regularly.

### [P1] DraftGenerator form is dense — 4 controls visible at once
Themes, style selector, max sections slider, and abstract toggle are all visible simultaneously.

### [P2] ExtractionMatrix table is hard to scan with many columns
Each column adds visual weight. With 5+ columns, the table becomes a wall of text.

### [P2] ResearchPipeline stepper lacks visual distinction
The 5 steps are shown as small circles with labels. Users may not realize this is a multi-step workflow.

### [P3] Modals use custom backdrop instead of shadcn Dialog
5 modals use `fixed inset-0 bg-black/70` manually instead of shadcn Dialog.

## What's Working
1. Token discipline: Every component uses semantic tokens
2. Keyboard navigation: All interactive elements have proper focus indicators
3. Empty states: Every list has a thoughtful empty state with clear next actions
