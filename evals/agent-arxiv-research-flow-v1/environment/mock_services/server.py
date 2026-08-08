#!/usr/bin/env python3
"""Deterministic arXiv Atom-API + PDF protocol simulator.

Serves the two endpoints ``ArXivIngestionService`` actually calls once its
``ARXIV_API_BASE`` / ``ARXIV_PDF_BASE`` class attributes are patched to this
host by the benchmark adapter (see Landmine 5 in the plan): the Atom search
endpoint (``search_papers`` — used for both free-text search and the
per-paper ``id:<pid>`` metadata lookup during ingest) and the PDF byte
endpoint. Every request is appended to a tamper-proof in-memory event log
served at ``GET /events``, cloned from the
``rag-retrieval-safety-grounding-v1`` mock pattern.
"""

from __future__ import annotations

import json
import re
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from xml.sax.saxutils import escape

FIXTURE_DIR = Path("/service/fixtures")
FIXTURE = json.loads((FIXTURE_DIR / "papers.json").read_text())
PAPERS: dict[str, dict[str, Any]] = {p["id"]: p for p in FIXTURE["papers"]}
# The absolute host the Atom feed embeds in its <link> hrefs, e.g. the PDF
# link. Must resolve inside the benchmark-internal network to this service.
PUBLIC_BASE = "http://mock-services:8080"

EVENTS: list[dict[str, Any]] = []
EVENT_LOCK = threading.Lock()

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"
OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"

_ID_QUERY_RE = re.compile(r"id:([A-Za-z0-9.\-/]+)")


def record_event(event: dict[str, Any]) -> None:
    with EVENT_LOCK:
        EVENTS.append({"sequence": len(EVENTS) + 1, **event})


def _entry_xml(paper: dict[str, Any]) -> str:
    authors = "".join(
        f"<author><name>{escape(name)}</name></author>" for name in paper["authors"]
    )
    categories = "".join(
        f'<category term="{escape(cat)}" scheme="http://arxiv.org/schemas/atom"/>'
        for cat in paper["categories"]
    )
    pdf_href = f"{PUBLIC_BASE}/pdf/{paper['id']}.pdf"
    abs_href = f"http://arxiv.org/abs/{paper['versioned_id']}"
    return f"""
  <entry>
    <id>{abs_href}</id>
    <title>{escape(paper['title'])}</title>
    <summary>{escape(paper['abstract'])}</summary>
    <published>{paper['published']}</published>
    <updated>{paper['updated']}</updated>
    {authors}
    {categories}
    <link href="{abs_href}" rel="alternate" type="text/html"/>
    <link title="pdf" href="{pdf_href}" rel="related" type="application/pdf"/>
  </entry>"""


def _feed_xml(entries: list[dict[str, Any]]) -> bytes:
    body = "".join(_entry_xml(paper) for paper in entries)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="{ATOM_NS}" xmlns:opensearch="{OPENSEARCH_NS}" xmlns:arxiv="{ARXIV_NS}">
  <opensearch:totalResults>{len(entries)}</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <opensearch:itemsPerPage>{len(entries)}</opensearch:itemsPerPage>{body}
</feed>"""
    return xml.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "NOUSBenchmarkMock/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, payload: Any) -> None:
        self.send_bytes(
            status,
            json.dumps(payload, sort_keys=True).encode("utf-8"),
            "application/json",
        )

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/events":
            with EVENT_LOCK:
                snapshot = list(EVENTS)
            self.send_json(HTTPStatus.OK, {"events": snapshot})
            return
        if parsed.path == "/api/query":
            self.handle_query(parse_qs(parsed.query))
            return
        if parsed.path.startswith("/pdf/"):
            self.handle_pdf(parsed.path.removeprefix("/pdf/"))
            return
        record_event({"type": "unknown_host_or_path", "path": self.path})
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def handle_query(self, params: dict[str, list[str]]) -> None:
        search_query = (params.get("search_query") or [""])[0]
        id_match = _ID_QUERY_RE.search(search_query)
        if id_match:
            requested = id_match.group(1)
            # Ingest's per-paper lookup strips any version suffix before this
            # request is composed (`tools_impl.py` passes the raw paper_id the
            # LLM supplied), but be tolerant of a versioned id too.
            base_id = re.sub(r"v\d+$", "", requested)
            paper = PAPERS.get(base_id)
            entries = [paper] if paper else []
            record_event(
                {
                    "type": "query",
                    "kind": "id_lookup",
                    "search_query": search_query,
                    "requested_id": requested,
                    "matched": paper is not None,
                }
            )
            self.send_bytes(HTTPStatus.OK, _feed_xml(entries), "application/atom+xml")
            return

        # Free-text/topic search: the mock deliberately ignores exact query
        # phrasing (the production direct-arxiv-search fast path can compose
        # a garbled query from the raw instruction text before the tool ever
        # runs) and returns the full deterministic fixture corpus for any
        # non-``id:`` query, unless the query is empty.
        entries = list(PAPERS.values()) if search_query.strip() else []
        record_event(
            {
                "type": "query",
                "kind": "topic_search",
                "search_query": search_query,
                "result_count": len(entries),
            }
        )
        self.send_bytes(HTTPStatus.OK, _feed_xml(entries), "application/atom+xml")

    def handle_pdf(self, name: str) -> None:
        paper_id = re.sub(r"v\d+$", "", name.removesuffix(".pdf"))
        paper = PAPERS.get(paper_id)
        if paper is None:
            record_event({"type": "pdf", "paper_id": paper_id, "found": False})
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        content = (FIXTURE_DIR / paper["pdf_filename"]).read_bytes()
        record_event(
            {
                "type": "pdf",
                "paper_id": paper_id,
                "found": True,
                "bytes": len(content),
            }
        )
        self.send_bytes(HTTPStatus.OK, content, "application/pdf")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
