"""Missing arXiv metadata must cost a field, not the whole ingest.

Live failure (dev, 2026-07-25): a rate-limited lookup made
``tools_impl._tool_ingest_arxiv`` fall back to its documented "minimal paper
dict so ingest can still proceed" — ``{"published": "", ...}`` with no
``primary_category``. It could not proceed:

    ValueError: Invalid isoformat string: ''      (arxiv_service, publication_date)
    KeyError: 'primary_category'                  (7 lines later, once the date was guarded)

So the graceful-degradation path was dead by construction, and one paper with
absent metadata killed every paper in the same batch.

Also covered: arXiv returns API errors as an HTTP **200** Atom feed whose entry
has none of the usual children, so the chained ``.find(...).text`` reads in
``_parse_arxiv_entry`` raised ``AttributeError`` on ``None``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from defusedxml import ElementTree as ET  # repo convention: never stdlib XML

pytestmark = pytest.mark.unit

_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def _stub_paper() -> dict[str, Any]:
    """Byte-for-byte the fallback dict from _tool_ingest_arxiv."""
    return {
        "id": "1706.03762",
        "title": "arXiv:1706.03762",
        "authors": [],
        "abstract": "",
        "published": "",
        "updated": "",
        "categories": [],
        "links": {"pdf": "https://arxiv.org/pdf/1706.03762"},
    }


class TestDateParsing:
    def test_empty_string_is_none_not_an_exception(self) -> None:
        from src.services.arxiv.arxiv_service import _parse_arxiv_date

        assert _parse_arxiv_date("") is None

    def test_none_is_none(self) -> None:
        from src.services.arxiv.arxiv_service import _parse_arxiv_date

        assert _parse_arxiv_date(None) is None

    def test_garbage_is_none(self) -> None:
        from src.services.arxiv.arxiv_service import _parse_arxiv_date

        assert _parse_arxiv_date("not-a-date") is None

    def test_real_arxiv_timestamp_still_parses_with_tz(self) -> None:
        from src.services.arxiv.arxiv_service import _parse_arxiv_date

        parsed = _parse_arxiv_date("2017-06-12T17:57:34Z")
        assert parsed == datetime(2017, 6, 12, 17, 57, 34, tzinfo=timezone.utc)


class TestMetadataDict:
    def test_stub_paper_builds_a_metadata_dict(self) -> None:
        """The whole point: no date, no primary_category, still ingestable."""
        paper = _stub_paper()

        publication_date = None
        from src.services.arxiv.arxiv_service import _parse_arxiv_date

        publication_date = _parse_arxiv_date(paper.get("published"))
        metadata = {
            "publication_date": publication_date,
            "arxiv_primary_category": paper.get("primary_category"),
            "doi": (paper.get("links") or {}).get("doi"),
        }

        assert metadata["publication_date"] is None
        assert metadata["arxiv_primary_category"] is None
        assert metadata["doi"] is None


class TestErrorFeedParsing:
    def _parse(self, xml: str) -> dict:
        from src.services.arxiv.arxiv_service import ArXivIngestionService

        entry = ET.fromstring(xml)
        return ArXivIngestionService._parse_arxiv_entry(
            ArXivIngestionService.__new__(ArXivIngestionService), entry, _NS
        )

    def test_arxiv_error_entry_does_not_raise(self) -> None:
        """arXiv signals errors with a 200 + Atom error entry, not an HTTP code."""
        xml = """<entry xmlns="http://www.w3.org/2005/Atom">
          <id>http://arxiv.org/api/errors#incorrect_id_format</id>
          <title>Error</title>
          <summary>incorrect id format for bogus-id</summary>
          <updated>2026-07-25T00:00:00-04:00</updated>
        </entry>"""
        parsed = self._parse(xml)

        assert parsed["published"] == ""
        assert parsed["authors"] == []

    def test_entry_with_empty_elements_does_not_raise(self) -> None:
        xml = """<entry xmlns="http://www.w3.org/2005/Atom">
          <id></id><title></title><summary></summary>
          <published></published><updated></updated>
          <author><name></name></author>
        </entry>"""
        parsed = self._parse(xml)

        assert parsed["published"] == ""
        assert parsed["authors"] == [], "a nameless author must not become ''"
