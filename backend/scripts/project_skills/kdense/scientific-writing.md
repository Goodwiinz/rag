---
name: scientific-writing
description: Evidence-bound scientific writing for papers, reports, and thesis chapters. Apply when drafting or revising scientific text so every claim traces to a source in the project and no facts are fabricated.
---

# Scientific Writing

Draft scientific text that is bound to evidence: every factual claim traces to a document, analysis, or dataset in the project. The workflow separates evidence gathering from drafting so the prose never invents what the sources do not contain.

Adapted from K-Dense scientific-agent-skills (MIT license).

## Non-negotiable rules

- **No fabrication.** Never invent results, citations, statistics, participant counts, or methodological details. A gap in the evidence is written as a gap, or flagged to the researcher — never filled in.
- **Evidence binding.** Each claim in the draft must be traceable to a specific source. If it cannot be traced, it is either removed or explicitly marked as the author's interpretation.
- **Scientific fidelity.** Preserve hedges and effect directions from sources. "Suggests" does not become "demonstrates"; a trend does not become a significant effect.
- **Confidentiality.** Unpublished results stay inside the project.

## Workflow

### 1. Intake

Establish document type (article, report, thesis chapter, response letter), target venue or audience, and which project materials are the evidence base. Use `list_project_documents` to enumerate available sources before writing anything.

### 2. Select reporting guidance

Match the document to its reporting conventions: empirical ML papers report datasets, baselines, compute, and variance; medical-style studies follow structured formats with explicit flow of participants; systematic reviews report search methodology. State which convention applies and follow it consistently.

### 3. Build the evidence record

Before drafting, collect the facts. Use `do_kb_retrieve` (content passages with verbatim quotes) and `summarize_document` to extract the claims, numbers, and findings each section will rest on — `search_documents` locates documents by title only and cannot supply evidence, and record them in a `create_project_note` as an evidence table: claim, source document, location. Where numbers require computation or verification from data, use `execute_code` and record the computed value with its provenance.

### 4. Create an evidence outline

Outline the document section by section, attaching evidence-table entries to each planned paragraph. A paragraph with no attached evidence is either scoped as interpretation or removed. This outline is the contract for drafting.

### 5. Draft without adding facts

Write from the outline. `create_draft` produces literature-review-style synthesis documents from themes; use it when the document is review-shaped, and assemble other document types section by section in `create_project_note` instead. The drafting pass transforms evidence into prose; it does not introduce new numbers, citations, or claims. Standard section logic: introduction moves general to specific and ends with the contribution; methods are past tense and reproducible; results report without interpreting; discussion interprets without repeating.

### 6. Reconcile methods and results

Cross-check: every result has a method that produces it, and every described method has a reported outcome or an explicit statement of why not. Mismatches here are where fabrication hides.

### 7. Verify citations and claims

Walk the draft claim by claim against the evidence table. Verify citation accuracy against source content with `do_kb_retrieve`; generate the reference list with `export_bibliography` rather than typing references by hand. Preserve each source's hedging level.

### 8. Figures and tables

Use figures and tables only when they carry information prose cannot. When a figure requires plotting from data, produce it with `execute_code` and describe exactly what was plotted. Numbers must agree between text, tables, and figures.

### 9. Revision

Revise in passes with distinct goals: structure (does the argument flow), evidence (is every claim still bound), clarity (sentence-level), and conventions (venue formatting). When responding to reviewer comments, quote each comment, answer it directly, and point to the exact change made.

## Pitfalls

1. Drafting before evidence — prose written first will invent its support afterward.
2. Citation drift — citing a paper for something adjacent to what it actually says.
3. Hedge inflation — upgrading "may" to "does" during revision.
4. Orphan methods and orphan results — described but never used, or reported but never explained.
5. Interpretation in results — keep observation and interpretation in their own sections.
6. Hand-written bibliographies — error-prone; always generate from tracked sources.
