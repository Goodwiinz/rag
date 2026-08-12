"""Tests for versioned-ID matching in the arXiv ingest tool.

Pins the fix for a bug where requesting both "2605.10877v1" and
"2605.10877v2" collapsed to a single fetched-metadata entry (stripped-version
keying), silently double-ingesting one version and dropping the other.
"""

from src.services.agent.tools_impl import (
    _find_missing_arxiv_ids,
    _index_arxiv_papers,
    _resolve_arxiv_paper,
)


def _paper(paper_id: str) -> dict:
    return {"id": paper_id, "title": f"arXiv:{paper_id}"}


class TestIndexArxivPapers:
    def test_two_versions_of_same_paper_both_resolve(self) -> None:
        papers = [_paper("2605.10877v1"), _paper("2605.10877v2")]
        fetched_by_id, fetched_unversioned = _index_arxiv_papers(papers)

        v1 = _resolve_arxiv_paper("2605.10877v1", fetched_by_id, fetched_unversioned)
        v2 = _resolve_arxiv_paper("2605.10877v2", fetched_by_id, fetched_unversioned)

        assert v1 is not None and v1["id"] == "2605.10877v1"
        assert v2 is not None and v2["id"] == "2605.10877v2"

    def test_unversioned_request_matches_versioned_response(self) -> None:
        fetched_by_id, fetched_unversioned = _index_arxiv_papers(
            [_paper("1706.03762v5")]
        )
        paper = _resolve_arxiv_paper("1706.03762", fetched_by_id, fetched_unversioned)
        assert paper is not None and paper["id"] == "1706.03762v5"

    def test_unknown_id_resolves_to_none(self) -> None:
        fetched_by_id, fetched_unversioned = _index_arxiv_papers([_paper("1v1")])
        assert _resolve_arxiv_paper("2v1", fetched_by_id, fetched_unversioned) is None

    def test_bare_fallback_picks_highest_revision_v5_after_v1(self) -> None:
        # Feed order: v1 then v5 — fallback must still pick v5.
        fetched_by_id, fetched_unversioned = _index_arxiv_papers(
            [_paper("1706.03762v1"), _paper("1706.03762v5")]
        )
        paper = _resolve_arxiv_paper("1706.03762", fetched_by_id, fetched_unversioned)
        assert paper is not None and paper["id"] == "1706.03762v5"

    def test_bare_fallback_picks_highest_revision_v5_before_v1(self) -> None:
        # Feed order reversed: v5 then v1 — fallback must still pick v5,
        # proving the result doesn't depend on Atom feed entry order.
        fetched_by_id, fetched_unversioned = _index_arxiv_papers(
            [_paper("1706.03762v5"), _paper("1706.03762v1")]
        )
        paper = _resolve_arxiv_paper("1706.03762", fetched_by_id, fetched_unversioned)
        assert paper is not None and paper["id"] == "1706.03762v5"


class TestFindMissingArxivIds:
    def test_bare_request_satisfied_by_any_ingested_version(self) -> None:
        missing = _find_missing_arxiv_ids(["1706.03762"], ["1706.03762v5"])
        assert missing == []

    def test_versioned_request_not_satisfied_by_sibling_version(self) -> None:
        # v1 and v2 both explicitly requested; only v1 actually ingested.
        # Stripped comparison would hide the dropped v2 behind v1 — must
        # flag v2 as missing.
        missing = _find_missing_arxiv_ids(
            ["2605.10877v1", "2605.10877v2"], ["2605.10877v1"]
        )
        assert missing == ["2605.10877v2"]

    def test_versioned_request_satisfied_by_exact_match(self) -> None:
        missing = _find_missing_arxiv_ids(
            ["2605.10877v1", "2605.10877v2"], ["2605.10877v1", "2605.10877v2"]
        )
        assert missing == []
