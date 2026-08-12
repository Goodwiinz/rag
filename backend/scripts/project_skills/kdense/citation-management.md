---
name: citation-management
description: Discover, verify, and manage citations and bibliographies. Apply when collecting references, checking citation metadata, building a bibliography, or wiring citations into a draft.
---

# Citation Management

Manage citations end to end: discover papers, capture accurate metadata, validate every entry, and integrate the bibliography into the writing workflow. The core rule: a citation is a verified pointer to a real document, never a plausible-looking string.

Adapted from K-Dense scientific-agent-skills (MIT license).

## When to apply

- Collecting references for a paper, review, or grant
- Auditing an existing bibliography for accuracy
- Building the reference list for a draft in progress
- Resolving incomplete or conflicting citation metadata

## Workflow

### 1. Discovery

Find candidate papers through the project's search tools:

- `search_arxiv` for preprints and CS, math, and physics work
- `list_external_databases` then `search_external_database` for domain databases (biomedical, general scholarly indexes) configured on the project
- `list_project_documents` for papers already in the active project — avoid duplicating what is already collected (`search_documents` matches titles organization-wide; use it to locate a known title, not to enumerate the project corpus)

Prefer authoritative indexes over general web results: they return structured metadata (title, authors, venue, year, identifiers) instead of scraped fragments.

### 2. Capture into the project

Ingest selected arXiv papers with `ingest_arxiv_papers` and work from the returned document ids, not raw external ids. There is no agent-side ingestion for non-arXiv papers: ask the researcher to upload the full text through the documents interface, then attach it with `add_document_to_project`. When a published paper also exists as an arXiv preprint, the verified arXiv record is the citable project document until the published version is uploaded — note the version used. Papers in the project are the citable universe; the bibliography is generated from them, which keeps every reference backed by a readable source.

### 3. Metadata verification

For each reference, verify the metadata against the actual document with `summarize_document` (or `do_kb_retrieve` when a specific passage must be confirmed):

- Title matches exactly (subtitle included)
- Author list complete and ordered correctly
- Year is the publication year, not the preprint year, when both exist
- Venue name is the real venue, not an abbreviation guessed from memory
- Persistent identifier (DOI or arXiv id) present and consistent with the title

A reference failing any check is corrected from the source document or flagged — never silently accepted.

### 4. Deduplication

The same work often appears as preprint and published version. Detect duplicates by normalized title and author overlap; keep the published version as primary and note the preprint id. Cite one version consistently throughout a document.

### 5. Bibliography generation

Generate the reference list with `export_bibliography` from the project's documents, then audit it for completeness: compare the exported entries against the full list of documents to be cited, and for any document the export omitted (freshly ingested records can be skipped when other documents have stored citations), construct its entry from the verified metadata gathered in the verification step and flag the gap in the audit note. Never hand-type an entry that was not first verified against its source. Choose one citation style per document and apply it uniformly; the common families are author-year (APA-like), numbered (Vancouver or IEEE-like), and venue-specific house styles.

### 6. Integration with drafting

While drafting with `create_draft`, cite only documents present in the project. On each revision pass, re-check that every in-text citation has a bibliography entry and every bibliography entry is cited in text — orphans in either direction are defects. Keep an audit note via `create_project_note` for references that need human decisions (conflicting metadata, retracted papers, inaccessible sources).

## Pitfalls

1. Citing from memory — metadata from memory is wrong often enough to be unacceptable.
2. Abstract-only citation — citing a claim from a paper whose body was never checked.
3. Preprint and published duplicates counted as two works.
4. Style mixing — one document, one citation style.
5. Orphan references — bibliography entries never cited, or citations without entries.
6. Ignoring retractions — when a source is questionable, verify its current status through the external database connectors and flag it for the researcher.
