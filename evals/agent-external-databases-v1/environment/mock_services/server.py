#!/usr/bin/env python3
"""Deterministic PubMed (NCBI E-utilities) + FRED protocol simulator.

Serves the two wire shapes the pinned connectors actually parse (read from
``src/services/connectors/pubmed.py`` and ``fred.py`` at build time, fidelity
to the parser rather than to the real upstream APIs):

- ``GET /entrez/eutils/esearch.fcgi`` -> PubMed ID-search JSON
  (``esearchresult.idlist``), matching ``pubmed.py``'s ``_ESEARCH`` constant.
- ``GET /entrez/eutils/efetch.fcgi``  -> PubMed article-fetch Atom-ish XML
  (``PubmedArticleSet``/``PubmedArticle``), matching ``_EFETCH`` and
  ``_parse_pubmed_article``.
- ``GET /fred/series/search``          -> FRED series-search JSON
  (``seriess``), matching ``fred.py``'s ``search()``. The ``api_key`` query
  parameter is recorded verbatim so the verifier can assert the connector
  sent the benchmark's ``FRED_API_KEY``.

Every request is appended to a tamper-proof in-memory event log served at
``GET /events``, cloned from the ``rag-retrieval-safety-grounding-v1`` mock
pattern.
"""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from xml.sax.saxutils import escape

FIXTURES = json.loads(Path("/service/fixtures.json").read_text())
PUBMED_ARTICLES = {a["pmid"]: a for a in FIXTURES["pubmed"]["articles"]}
PUBMED_PMIDS = FIXTURES["pubmed"]["pmids"]
FRED_SERIES = FIXTURES["fred"]["series"]

EVENTS: list[dict[str, Any]] = []
EVENT_LOCK = threading.Lock()


def record_event(event: dict[str, Any]) -> None:
    with EVENT_LOCK:
        EVENTS.append({"sequence": len(EVENTS) + 1, **event})


def query_params(path: str) -> dict[str, str]:
    parsed = urlparse(path)
    return {k: v[0] for k, v in parse_qs(parsed.query).items()}


def _article_xml(pmid: str) -> str:
    article = PUBMED_ARTICLES.get(pmid)
    if article is None:
        return ""
    authors_xml = "".join(
        f"<Author><LastName>{escape(last)}</LastName>"
        f"<Initials>{escape(initials)}</Initials></Author>"
        for last, initials in article["authors"]
    )
    return f"""
    <PubmedArticle>
      <MedlineCitation>
        <PMID>{escape(article['pmid'])}</PMID>
        <Article>
          <ArticleTitle>{escape(article['title'])}</ArticleTitle>
          <Abstract>
            <AbstractText>{escape(article['abstract'])}</AbstractText>
          </Abstract>
          <Journal><Title>{escape(article['journal'])}</Title></Journal>
          <AuthorList>{authors_xml}</AuthorList>
        </Article>
      </MedlineCitation>
      <PubDate><Year>{escape(article['pub_year'])}</Year></PubDate>
      <PubmedData>
        <ArticleIdList>
          <ArticleId IdType="doi">{escape(article['doi'])}</ArticleId>
        </ArticleIdList>
      </PubmedData>
    </PubmedArticle>
    """


class Handler(BaseHTTPRequestHandler):
    server_version = "NOUSBenchmarkConnectorMock/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_xml(self, status: int, body_text: str) -> None:
        body = body_text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        parsed = urlparse(self.path)
        path = parsed.path
        params = query_params(self.path)

        if path == "/health":
            self.send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/events":
            with EVENT_LOCK:
                snapshot = list(EVENTS)
            self.send_json(HTTPStatus.OK, {"events": snapshot})
            return
        if path == "/entrez/eutils/esearch.fcgi":
            self.handle_esearch(params)
            return
        if path == "/entrez/eutils/efetch.fcgi":
            self.handle_efetch(params)
            return
        if path == "/fred/series/search":
            self.handle_fred_search(params)
            return

        record_event(
            {"type": "unknown_host_or_path", "method": "GET", "path": self.path}
        )
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    # -- PubMed --------------------------------------------------------
    def handle_esearch(self, params: dict[str, str]) -> None:
        record_event(
            {
                "type": "pubmed_esearch",
                "db": params.get("db"),
                "term": params.get("term"),
                "retmax": params.get("retmax"),
                "api_key": params.get("api_key"),
            }
        )
        self.send_json(
            HTTPStatus.OK,
            {"esearchresult": {"idlist": list(PUBMED_PMIDS)}},
        )

    def handle_efetch(self, params: dict[str, str]) -> None:
        requested_ids = [pmid for pmid in (params.get("id") or "").split(",") if pmid]
        record_event(
            {
                "type": "pubmed_efetch",
                "db": params.get("db"),
                "id": params.get("id"),
                "api_key": params.get("api_key"),
            }
        )
        articles_xml = "".join(_article_xml(pmid) for pmid in requested_ids)
        self.send_xml(
            HTTPStatus.OK,
            f'<?xml version="1.0"?><PubmedArticleSet>{articles_xml}</PubmedArticleSet>',
        )

    # -- FRED ------------------------------------------------------------
    def handle_fred_search(self, params: dict[str, str]) -> None:
        record_event(
            {
                "type": "fred_series_search",
                "search_text": params.get("search_text"),
                "api_key": params.get("api_key"),
                "file_type": params.get("file_type"),
                "limit": params.get("limit"),
            }
        )
        self.send_json(HTTPStatus.OK, {"seriess": list(FRED_SERIES)})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
