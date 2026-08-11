"""Tests for arXiv Atom parsing fixes and the id_list batch lookup.

Pins four behaviors ported from studying arxiv.py's handling of API quirks:

1. Pre-2007 archive-qualified IDs ("math/0309136v1") keep their prefix —
   the old ``split("/")[-1]`` dropped it, breaking the PDF URL and dedup key.
2. ``primary_category`` comes from the explicit ``<arxiv:primary_category>``
   element, not a guess from ``categories[0]``.
3. The DOI falls back to the ``<arxiv:doi>`` element when the feed carries no
   rel-doi ``<link>``.
4. ``get_papers_by_ids`` fetches N papers in one request and drops the error
   entries arXiv returns (as a 200 Atom feed) for invalid IDs.
5. ``search_papers`` retries an empty page once when totalResults says more
   remain, instead of silently truncating the scan.
"""

import pytest
from defusedxml import ElementTree as ET

from src.services.arxiv.arxiv_service import ArXivIngestionService

pytestmark = pytest.mark.unit

_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _feed(entries: str, total: int = 1) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>{total}</opensearch:totalResults>
  {entries}
</feed>"""


def _entry(
    entry_id: str = "http://arxiv.org/abs/1706.03762v5",
    extra: str = "",
) -> str:
    return f"""<entry>
    <id>{entry_id}</id>
    <title>Attention Is All You Need</title>
    <summary>The Transformer.</summary>
    <published>2017-06-12T17:57:34Z</published>
    <updated>2017-06-12T17:57:34Z</updated>
    <author><name>Ashish Vaswani</name></author>
    <category term="cs.CL"/>
    <category term="cs.LG"/>
    {extra}
  </entry>"""


def _parse_single(entry_xml: str) -> dict:
    root = ET.fromstring(_feed(entry_xml))
    entry = root.find("atom:entry", _NAMESPACES)
    assert entry is not None
    return ArXivIngestionService()._parse_arxiv_entry(entry, _NAMESPACES)


class TestEntryParsing:
    def test_new_style_id_keeps_version(self):
        paper = _parse_single(_entry())
        assert paper["id"] == "1706.03762v5"

    def test_old_style_id_keeps_archive_prefix(self):
        paper = _parse_single(_entry(entry_id="http://arxiv.org/abs/math/0309136v1"))
        assert paper["id"] == "math/0309136v1"

    def test_primary_category_from_element_not_first_category(self):
        # Explicit primary (cs.LG) differs from the first <category> (cs.CL).
        paper = _parse_single(
            _entry(
                extra='<arxiv:primary_category term="cs.LG"/>',
            )
        )
        assert paper["primary_category"] == "cs.LG"

    def test_primary_category_falls_back_to_first_category(self):
        paper = _parse_single(_entry())
        assert paper["primary_category"] == "cs.CL"

    def test_doi_from_element_when_no_doi_link(self):
        paper = _parse_single(_entry(extra="<arxiv:doi>10.1000/xyz123</arxiv:doi>"))
        assert paper["links"]["doi"] == "https://doi.org/10.1000/xyz123"

    def test_doi_link_wins_over_element(self):
        paper = _parse_single(
            _entry(
                extra=(
                    '<link title="doi" href="https://dx.doi.org/10.1000/link"/>'
                    "<arxiv:doi>10.1000/element</arxiv:doi>"
                )
            )
        )
        assert paper["links"]["doi"] == "https://dx.doi.org/10.1000/link"


class TestGetPapersByIds:
    @pytest.mark.asyncio
    async def test_batches_ids_into_one_request(self, monkeypatch):
        svc = ArXivIngestionService()
        calls = []

        async def _fake_request(url, params):
            calls.append(params)
            return _feed(
                _entry() + _entry(entry_id="http://arxiv.org/abs/math/0309136v1"),
                total=2,
            )

        monkeypatch.setattr(svc, "_make_async_request", _fake_request)
        papers = await svc.get_papers_by_ids(["1706.03762", "math/0309136"])

        assert len(calls) == 1
        assert calls[0]["id_list"] == "1706.03762,math/0309136"
        assert [p["id"] for p in papers] == ["1706.03762v5", "math/0309136v1"]

    @pytest.mark.asyncio
    async def test_drops_error_entries_for_invalid_ids(self, monkeypatch):
        svc = ArXivIngestionService()

        async def _fake_request(url, params):
            # arXiv reports an invalid ID as a normal entry whose id points
            # at api/errors — HTTP 200, no /abs/ segment.
            return _feed(
                _entry()
                + _entry(
                    entry_id=(
                        "http://arxiv.org/api/errors#" "incorrect_id_format_for_bogus"
                    )
                ),
                total=2,
            )

        monkeypatch.setattr(svc, "_make_async_request", _fake_request)
        papers = await svc.get_papers_by_ids(["1706.03762", "bogus"])
        assert [p["id"] for p in papers] == ["1706.03762v5"]

    @pytest.mark.asyncio
    async def test_empty_input_short_circuits(self, monkeypatch):
        svc = ArXivIngestionService()

        async def _boom(url, params):  # pragma: no cover
            raise AssertionError("should not be called")

        monkeypatch.setattr(svc, "_make_async_request", _boom)
        assert await svc.get_papers_by_ids([]) == []


class TestEmptyPageRetry:
    @pytest.mark.asyncio
    async def test_retries_empty_mid_scan_page_once(self, monkeypatch):
        svc = ArXivIngestionService()
        svc.session = object()  # search_papers only checks presence
        responses = [
            _feed(_entry(), total=2),
            _feed("", total=2),  # spurious empty page
            _feed(_entry(entry_id="http://arxiv.org/abs/2401.00001v1"), total=2),
        ]

        async def _fake_request(url, params):
            return responses.pop(0)

        monkeypatch.setattr(svc, "_make_async_request", _fake_request)
        svc.BATCH_SIZE = 1
        papers = await svc.search_papers(query="all:test", max_results=2)
        assert [p["id"] for p in papers] == ["1706.03762v5", "2401.00001v1"]

    @pytest.mark.asyncio
    async def test_second_empty_page_stops_scan(self, monkeypatch):
        svc = ArXivIngestionService()
        svc.session = object()
        responses = [
            _feed(_entry(), total=3),
            _feed("", total=3),
            _feed("", total=3),  # retry also empty -> stop, no infinite loop
        ]

        async def _fake_request(url, params):
            return responses.pop(0)

        monkeypatch.setattr(svc, "_make_async_request", _fake_request)
        svc.BATCH_SIZE = 1
        papers = await svc.search_papers(query="all:test", max_results=3)
        assert [p["id"] for p in papers] == ["1706.03762v5"]
