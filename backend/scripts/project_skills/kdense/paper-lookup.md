---
name: paper-lookup
description: Search arXiv and configured external literature databases, then ingest what qualifies. Apply for "find papers on X", author/topic searches, arXiv ID lookups, or building a reading list before a project.
---

# Paper Lookup

Turn a research question into a reproducible literature search: pick the right source, run a bounded query, and hand back results with enough provenance (query string, source, date) that the search can be repeated. A lookup is only as trustworthy as it is repeatable — report what was queried, and say plainly when a source came back empty rather than letting silence read as "nothing exists."

Adapted from K-Dense scientific-agent-skills (MIT license).

## Core workflow

1. **Define the retrieval contract.** What is the researcher after — a specific paper, a topic sweep, an author's body of work, a reading list to seed a project? Note constraints that change the answer: date range, exhaustive vs. a handful of top hits. If "recent" has no year attached, or a name has obvious namesakes, ask rather than guess.
2. **Select the source(s).** `search_arxiv` covers preprints across physics, math, CS, and quant-bio, but it silently indexes roughly the last year of submissions — for older work, or fields arXiv doesn't cover, check `list_external_databases` for what connectors are configured in this deployment, then use `search_external_database` against the relevant one. If no external database is configured, say so rather than presenting arXiv results as if they were comprehensive.
3. **Run bounded queries.** Each `search_arxiv` or `search_external_database` call returns one bounded page of results (roughly 20), not the full hit population — treat the count as a page size, not a database total. For a topic sweep, vary the query across synonyms and adjacent phrasings rather than assuming one query surfaced everything; for an exhaustive need, say plainly that the tools return bounded pages and that true exhaustive retrieval isn't available here.
4. **Screen results with the researcher's criteria.** Title first, then abstract as returned by the search. Note anything ambiguous (same title, different authors; a preprint versus its published version) rather than silently picking one.
5. **Ingest what qualifies.** `ingest_arxiv_papers` accepts arXiv ids only, and returns document ids to use downstream — never treat the raw arXiv id as a document reference after ingestion. A paper found through an external database with no arXiv id cannot be ingested this way: hold it as a candidate in the reported list, flagged for the researcher to upload manually and add with `add_document_to_project` once it exists as a file.
6. **Return an auditable answer.** Lead with the results, then the provenance: source(s) queried, query strings, access context (roughly-a-year arXiv window if relevant), and which candidates need manual upload.

## Output shape

Report, per source: what was queried and what came back (title, authors, year, identifier — the fields that matter for the ask). Then a short provenance note: sources queried, sources unavailable or unconfigured, and the arXiv recency caveat when it applies. If a query returned nothing, say that explicitly rather than moving on silently.

## Pitfalls

1. Presenting an arXiv sweep as comprehensive — the ~1-year window silently excludes older preprints; say so when the topic could have earlier foundational work.
2. Treating one bounded results page as the full hit population — a topic with more candidates than fit on one page needs varied queries, and the gap should be reported, not hidden.
3. Referencing a raw arXiv id as if it were a document after `ingest_arxiv_papers` ran — always switch to the returned document id.
4. Trying to ingest a non-arXiv paper through `ingest_arxiv_papers` — it will not accept it; route it to manual upload instead.
5. Silent empty results — an empty page from a source is information for the researcher, not something to paper over with results from elsewhere without saying so.
6. Skipping `list_external_databases` and assuming none are configured — check before declaring arXiv the only available source.
