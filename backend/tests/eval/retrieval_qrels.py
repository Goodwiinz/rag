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


# Labeled 2026-07-17 against the dev org (e050bd43-6b0b-4425-9848-1bc5ad9d5cc2,
# KB 6343a77f-7987-11f1-aee4-4e013e2ddde4) from its 28 indexed documents.
# Multi-copy papers list every *indexed* duplicate UUID (registered-only rows
# never reach the KB). The 9-copy "Modular supercuspidal lifts" math paper is
# deliberately excluded: with recall = |hit ∩ relevant| / |relevant|, nine
# duplicate ids make a perfect retrieval score 3/9 at k=3 — the metric would
# measure the dedup backlog, not retrieval quality.
CASES: tuple[RetrievalCase, ...] = (
    RetrievalCase(
        name="dev-productivity-rcts",
        query=(
            "randomized controlled trials measuring the impact of AI coding "
            "assistants on developer productivity"
        ),
        relevant_doc_ids=(
            "6f29dd30-798e-460c-842c-2c155510c864",  # METR RCT 2025
            "c497ce91-4ef7-4b17-a64a-23357337689e",  # MIT Copilot RCT 2024
        ),
    ),
    RetrievalCase(
        name="metr-slowdown",
        query=(
            "did experienced open-source developers complete tasks faster or "
            "slower when using AI tools"
        ),
        relevant_doc_ids=("6f29dd30-798e-460c-842c-2c155510c864",),
    ),
    RetrievalCase(
        name="self-rag",
        query=(
            "training a model to retrieve on demand and critique its own "
            "generations with reflection tokens"
        ),
        relevant_doc_ids=("6687b8cd-ae49-4407-a08c-709fa761a71c",),
    ),
    RetrievalCase(
        name="rag-original",
        query=(
            "combining parametric seq2seq memory with a non-parametric dense "
            "vector index of Wikipedia for knowledge-intensive NLP"
        ),
        relevant_doc_ids=("6a9b211c-5505-41c0-9ccc-c81c04c92c8a",),
    ),
    RetrievalCase(
        name="fair-rag",
        query=(
            "faithful adaptive iterative refinement loop for "
            "retrieval-augmented generation"
        ),
        relevant_doc_ids=("1de75952-32ac-409f-ae9b-644a93d0f22a",),
    ),
    RetrievalCase(
        name="rag-metadata",
        query="using document metadata to improve retrieval-augmented generation",
        relevant_doc_ids=("e8614f40-c296-4f71-af5b-c07378b5df9e",),
    ),
    RetrievalCase(
        name="music-rag",
        query="answering musical text questions with retrieval augmentation",
        relevant_doc_ids=("b6e8c2ab-fba2-45ca-ac3f-3e5f47a4ee49",),
    ),
    RetrievalCase(
        name="ehr-foundation-model",
        query=(
            "prototype-guided retrieval-augmented foundation model for "
            "electronic health records"
        ),
        relevant_doc_ids=(
            "bb5c2ecf-606f-4c65-bf54-a39e6ee40795",
            "ebda8545-9fca-4f3a-8085-892fb339e00a",
        ),
    ),
    RetrievalCase(
        name="rag-stack-review",
        query=(
            "review of architecture and trust frameworks for production "
            "retrieval-augmented generation systems"
        ),
        relevant_doc_ids=(
            "a8b484f1-0cf9-4f75-9331-5417d36a2903",
            "dd5fc053-2995-4373-aa41-fc2804686276",
        ),
    ),
    RetrievalCase(
        name="cnn-survey",
        query="survey of convolution variants used in deep learning",
        relevant_doc_ids=("e14a9e03-bd86-49a6-a55d-6e596d4dd103",),
    ),
    RetrievalCase(
        name="survival-regression",
        query="mixture models for survival regression with Cox models",
        relevant_doc_ids=("b3ddfa95-b1c7-4a9b-ab59-f976b514f44d",),
    ),
    RetrievalCase(
        name="dome-ml-validation",
        query=(
            "recommendations for validating supervised machine learning "
            "methods in biology"
        ),
        relevant_doc_ids=("dd8e7833-80b0-4506-83d8-2dcf86071ee6",),
    ),
    RetrievalCase(
        name="cyber-attribution",
        query="challenges and techniques for attributing cyber attacks to actors",
        relevant_doc_ids=("71bd17fe-fe6b-40c0-8c05-faba933de6dd",),
    ),
    RetrievalCase(
        name="cyber-threat-detection",
        query="large language models for detecting cyber threats",
        relevant_doc_ids=("157e8964-d3ae-4ec4-a766-2896e2277c3e",),
    ),
    RetrievalCase(
        name="healthcare-ml-privacy",
        query=(
            "open challenges in privacy-preserving machine learning for " "healthcare"
        ),
        relevant_doc_ids=("5c2202bd-d147-4d43-961d-aa44a4b5f2b4",),
    ),
)
