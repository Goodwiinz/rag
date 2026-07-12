"""Creds-free pure-function tests for the retrieval-eval metric shim.

Only exercises ``_recall_at_k`` (the SearchQualityService._calculate_recall
wiring) and ``_mrr`` — no DB, no DO KB client, no network.
"""

from scripts.retrieval_eval import _mrr, _recall_at_k


def test_recall_at_k_counts_relevant_within_cutoff():
    ranked = ["doc-a", "doc-b", "doc-c", "doc-d"]
    relevant = ("doc-a", "doc-c", "doc-z")  # doc-z never retrieved

    # Only doc-a is within the top-1 cutoff -> 1/3 relevant found.
    assert _recall_at_k(ranked, relevant, k=1) == 1 / 3
    # doc-a + doc-c both within top-3 -> 2/3 relevant found.
    assert _recall_at_k(ranked, relevant, k=3) == 2 / 3


def test_recall_at_k_empty_ground_truth_is_zero():
    assert _recall_at_k(["doc-a"], (), k=5) == 0.0


def test_mrr_reciprocal_rank_of_first_hit_and_zero_when_absent():
    assert _mrr(["doc-a", "doc-b"], ("doc-b",)) == 0.5
    assert _mrr(["doc-a", "doc-b"], ("doc-a",)) == 1.0
    assert _mrr(["doc-a", "doc-b"], ("doc-z",)) == 0.0
