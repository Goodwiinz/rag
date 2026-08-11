"""Tests for versioned-ID matching in the arXiv ingest tool.

Pins the fix for a bug where requesting both "2605.10877v1" and
"2605.10877v2" collapsed to a single fetched-metadata entry (stripped-version
keying), silently double-ingesting one version and dropping the other.
"""

from src.services.agent.tools_impl import _index_arxiv_papers, _resolve_arxiv_paper


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
