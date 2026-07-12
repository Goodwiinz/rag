"""Hand-labeled qrels for the DO KB retrieval-quality gate.

``CASES`` ships EMPTY. Populating it needs live dev DO KB + DB creds
(Infisical ``/do-kb`` env) — an operator step, not something CI or this
repo can do offline.

Labeling procedure (run against the dev org):

    python -m scripts.retrieval_eval --org-id <org> --dump

against the dev org (``e050bd43…``, KB ``6343a77f…`` per the DO-KB design
audit) to see the resolved ``(doc_id, title, score)`` candidates per query,
then hand-mark which Document UUIDs are actually relevant to each query by
cross-checking the documents API/DB.

Ground truth must be **resolved org Document IDs** (the UUIDs
``resolve_and_filter_chunks`` maps DO KB storage keys back to), NOT DO KB
storage keys or arXiv paper IDs. Pointing ``--org-id`` at the wrong org
silently yields recall=0 for every case — a known "silent by design"
failure mode of this subsystem, so double check the org before labeling.

Once 10-15 cases are hand-labeled, add ``RetrievalCase`` entries below and
commit them — that becomes the qrels fixture ``scripts/retrieval_eval.py``
scores against.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalCase:
    name: str
    query: str
    relevant_doc_ids: tuple[
        str, ...
    ]  # canonical org Document UUIDs (post-resolve), NOT KB storage keys
    project_id: str | None = None


CASES: tuple[RetrievalCase, ...] = (
    # 10-15 hand-labeled cases over the dev corpus — see module docstring
    # for the labeling procedure.
)
