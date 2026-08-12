---
name: literature-review
description: Conduct systematic literature reviews with the project's arXiv, document, and external-database tools. Apply when synthesizing research across sources, writing review sections, mapping the state of the art, or identifying research gaps.
---

# Literature Review

Conduct systematic, reproducible literature reviews: search multiple sources, screen with explicit criteria, synthesize thematically, and produce a review document with verified citations.

Adapted from K-Dense scientific-agent-skills (MIT license).

## When to apply

- Systematic literature reviews, scoping reviews, or research synthesis
- Writing the related-work or background section of a paper or thesis
- Mapping the state of the art in a research domain
- Identifying research gaps and future directions

## Workflow

Run the review in seven phases. Keep a running methods log (search strings, dates, result counts, exclusion reasons) in a project note so the review is reproducible.

### 1. Planning and scoping

Define the research question, inclusion and exclusion criteria, and time window before searching. Record them first with `create_project_note`. A review that cannot reproduce its own search is not systematic. Note a platform limit in the methods log: arXiv search covers roughly the most recent year of submissions, so a wider declared window must state that older arXiv-only work may be under-represented.

### 2. Systematic search

Search every source available in this turn, and record in the methods log which were reachable:

- Use `search_arxiv` for preprints and CS, math, and physics literature. Vary terms across runs: synonyms, abbreviations, and adjacent phrasings.
- Use `list_external_databases` to see which connectors are configured, then `search_external_database` for domain databases such as PubMed or Semantic Scholar equivalents. If these tools are not bound in the current turn, state that in the methods log instead of silently narrowing coverage.
- Use `list_project_documents` to cover papers already in the active project, so prior collections are not re-fetched. (`search_documents` matches titles and filenames across the whole organization, not just this project — use it for locating a known title, not for defining the project corpus.)

Record every query string, its date, and its returned count in the methods log — label these as returned-page counts, not database totals, since each search returns a bounded page (about 20 results) rather than the full hit population.

### 3. Screening and selection

Screen title, then abstract, then full text, against the pre-registered criteria. Record counts at each stage (identified, screened, excluded with reasons, included) so a PRISMA-style flow can be reported. Ingest arXiv papers that pass screening with `ingest_arxiv_papers`, then work from the returned document ids — never from raw arXiv ids. Papers from external databases without an arXiv id cannot be ingested this way: hold them in an explicit candidate list (recorded in the methods log), excluded from synthesis, citation verification, and the bibliography, and flag them for manual upload by the researcher — a candidate enters the included set only once it exists as a project document.

### 4. Extraction and quality appraisal

For each included paper, use `summarize_document` to pull the structured facts you need: population or dataset, method, sample size, effect sizes, limitations. Note study quality alongside findings; evidence is not all equal, and the synthesis must say so.

### 5. Synthesis

Organize by theme, never paper by paper. Use `compare_documents` to contrast methods and findings across included papers, and `search_knowledge_graph` or `explore_entity_neighborhood` to surface entities and relationships that recur across the corpus. For each theme: what converges, what conflicts, what is missing.

### 6. Citation verification

Every citation must trace to a document in the project. Cross-check claims against source content with `do_kb_retrieve`, which returns relevance-scored passages with verbatim quotes — cite from the quote. (`search_documents` returns only titles and metadata; it cannot confirm what a source says.) Never cite a paper that was not read at least at abstract level; never invent bibliographic details.

### 7. Document generation

Assemble the review with `create_draft`: introduction and scope, methods (the search log), thematic synthesis, gaps and future directions, limitations. Generate the bibliography with `export_bibliography` rather than hand-writing references, then check its output against the included-papers list — any included paper missing from the export is added from verified metadata and flagged. State the search date in the methods section — fields move quickly.

## Pitfalls

1. Single-source search — search every source reachable in the turn; when fewer than three were reachable, document the coverage limitation in the methods log.
2. Undocumented searches — irreproducible; log every query and date.
3. Paper-by-paper summary — that is an annotated bibliography, not a synthesis.
4. Unverified citations — check each one against the ingested source.
5. Ignoring preprints — latest findings live there; include arXiv-style servers.
6. No quality appraisal — weight evidence by study quality and say how.
7. Publication bias — negative results are underpublished; flag the risk when synthesizing.
