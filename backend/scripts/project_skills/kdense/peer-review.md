---
name: peer-review
description: Structured peer review of manuscripts and drafts. Apply when reviewing a paper or draft for scientific soundness, mapping claims to evidence, checking methods and statistics, and drafting actionable reviewer comments.
---

# Peer Review

Review a manuscript or draft systematically: establish scope, map claims to evidence, examine methods and statistics, then produce actionable, professional comments. The reviewer role is advisory — the human researcher owns the final judgment and any recommendation to an editor.

Adapted from K-Dense scientific-agent-skills (MIT license).

## Boundaries

- Never fabricate a concern or a compliment; every comment must point at something specific in the manuscript.
- Never speculate about author identity or judge by affiliation, seniority, or venue prestige.
- Confidential material stays in the project; do not quote the manuscript outside the review.
- Distinguish clearly between "the manuscript states" (extraction) and "this reviewer infers" (interpretation).

## Workflow

### 1. Establish scope and evidence

Confirm what is under review and what evidence is available. Ingest the manuscript into the project if not present, then use `list_project_documents` to confirm what is in scope: main text, supplements, data availability statements. Note what is missing — a review that never says "I could not check X" overstates its coverage.

### 2. Orient without deciding

Read for structure first with `summarize_document`: what is claimed, what is the study design, what would need to be true for the claims to hold. Do not form a verdict yet; premature judgment anchors the rest of the review.

### 3. Map claims to evidence

For each central claim, locate the supporting figure, table, or analysis. Use `do_kb_retrieve` to pull the manuscript passages bearing on each claim — it returns relevance-scored content with verbatim quotes, which is what evidence tracing needs (`search_documents` matches only titles and metadata). Classify each claim: supported, partially supported (state what is missing), or unsupported. This map is the skeleton of the review.

### 4. Review methods and statistics

Check design and analysis, not just results: sample size and power reasoning, control and baseline choices, multiple-comparison handling, effect sizes alongside p-values, uncertainty reporting. Where a re-computation would settle a doubt (a mean, an effect size, a confidence interval), use `execute_code` to check it rather than guessing. Compare methods against related work in the project with `compare_documents` when a methodological choice looks unusual.

### 5. Reproducibility and transparency

Could a competent reader reproduce this work? Check for data availability, code availability, versions and parameters of key tools, and whether the methods section matches what the results actually required. Absences here are findings, not omissions to ignore.

### 6. Figures, tables, and citations

Check the textual layer of figures and tables: captions, referenced numbers, and agreement between text, tables, and figure descriptions. The available tools extract text only — rendered graphics, axes, and plotted values cannot be inspected, so the review must state explicitly that visual properties of figures were not assessed rather than implying they were verified. Spot-check citations: does the cited work actually say what the manuscript attributes to it? Use `search_arxiv` or `search_external_database` to pull cited works when a key attribution needs checking.

### 7. Draft actionable comments

Write comments the authors can act on. Each comment: location (section, figure, line), the observation, why it matters, and what would resolve it. Separate major concerns (validity-threatening) from minor ones (clarity, presentation). Assemble the reviewer report with `create_project_note` in this structure: summary of the work in the reviewer's own words, major comments numbered, minor comments numbered, and a short note on what was not assessed. (`create_draft` generates literature-review-style synthesis documents and will not honor a reviewer-report structure — do not use it for the report.)

### 8. Keep channels separate

Comments to authors must be professional and self-contained. Any confidential note to the human researcher (doubts, suspicions that need human judgment, integrity concerns) goes in a separate `create_project_note` — never mixed into the author-facing text. Integrity concerns are flagged to the human, not adjudicated by the reviewer.

## Pitfalls

1. Verdict-first reviewing — mapping claims to evidence comes before judgment.
2. Vague comments — "the methods are weak" is not actionable; name the method and the fix.
3. Novelty policing without evidence — a novelty concern requires a citation to the prior work.
4. Ignoring the supplement — claims often rest on supplementary analyses; check them.
5. Statistics theater — checking that p-values exist is not checking the statistics.
6. Scope creep — review the paper the authors wrote, not the one the reviewer would have written.
