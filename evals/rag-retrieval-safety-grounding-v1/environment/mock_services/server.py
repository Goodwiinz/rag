#!/usr/bin/env python3
"""Deterministic DO KB retrieve and Cohere rerank protocol simulator."""

from __future__ import annotations

import json
import os
import re
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

FIXTURE = json.loads(Path("/service/fixtures.json").read_text())
RECORDS = list(FIXTURE["records"])
DO_TOKEN = os.environ.get("DO_BENCHMARK_TOKEN", "")
COHERE_TOKEN = os.environ.get("COHERE_BENCHMARK_TOKEN", "")
EVENTS: list[dict[str, Any]] = []
EVENT_LOCK = threading.Lock()


def record_event(event: dict[str, Any]) -> None:
    with EVENT_LOCK:
        EVENTS.append({"sequence": len(EVENTS) + 1, **event})


def normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def identify_document(text: str) -> str:
    value = normalized(text)
    if "account deletion records are retained for 30 days" in value:
        return "R1"
    if "workspace deletion records are retained for 14 days" in value:
        return "R3"
    if "account deletion records were retained for 60 days" in value:
        return "R2"
    if "workspace recovery requests" in value:
        return "R4"
    if "candidate resume" in value:
        return "R5"
    if "internal troubleshooting credential" in value:
        return "R7"
    return "unknown"


SCORES = {record["id"]: float(record["rerank_score"]) for record in RECORDS}


class Handler(BaseHTTPRequestHandler):
    server_version = "NOUSBenchmarkMock/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 100_000:
            raise ValueError("invalid body length")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def bearer_is(self, expected: str) -> bool:
        return self.headers.get("Authorization") == f"Bearer {expected}"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if self.path == "/health":
            self.send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if self.path == "/events":
            with EVENT_LOCK:
                snapshot = list(EVENTS)
            self.send_json(HTTPStatus.OK, {"events": snapshot})
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        retrieve_match = re.fullmatch(r"/v1/([^/]+)/retrieve", self.path)
        if retrieve_match:
            self.handle_retrieve(retrieve_match.group(1))
            return
        if self.path == "/rerank":
            self.handle_rerank()
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def handle_retrieve(self, kb_uuid: str) -> None:
        auth_valid = self.bearer_is(DO_TOKEN)
        if not auth_valid:
            record_event({"kind": "do_retrieve", "authorization_valid": False})
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        try:
            body = self.read_json()
            query = body["query"]
            num_results = int(body["num_results"])
            alpha = body.get("alpha")
            if kb_uuid != FIXTURE["kb_uuid"]:
                raise ValueError("unknown knowledge base")
            if not isinstance(query, str) or not query.strip():
                raise ValueError("query is required")
            if not 1 <= num_results <= 100:
                raise ValueError("num_results out of range")
            if set(body) - {"query", "num_results", "alpha"}:
                raise ValueError("unrecognized field")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            record_event(
                {
                    "kind": "do_retrieve",
                    "authorization_valid": True,
                    "accepted": False,
                    "error_type": type(exc).__name__,
                }
            )
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return

        selected = RECORDS[:num_results]
        results = [
            {
                "text_content": record["text"],
                "metadata": {
                    "item_name": f"{record['document_id']}.txt",
                    "title": record["title"],
                    "fixture_id": record["id"],
                },
            }
            for record in selected
        ]
        record_event(
            {
                "kind": "do_retrieve",
                "authorization_valid": True,
                "accepted": True,
                "kb_uuid": kb_uuid,
                "query": query[:512],
                "num_results": num_results,
                "alpha": alpha,
                "response_record_ids": [record["id"] for record in selected],
                "response_count": len(selected),
                "response_scores_omitted": True,
            }
        )
        self.send_json(
            HTTPStatus.OK,
            {"results": results, "total_results": len(RECORDS)},
        )

    def handle_rerank(self) -> None:
        auth_valid = self.bearer_is(COHERE_TOKEN)
        if not auth_valid:
            record_event({"kind": "cohere_rerank", "authorization_valid": False})
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        try:
            body = self.read_json()
            query = body["query"]
            documents = body["documents"]
            top_n = int(body["top_n"])
            if not isinstance(query, str) or not query.strip():
                raise ValueError("query is required")
            if not isinstance(documents, list) or not all(
                isinstance(item, str) for item in documents
            ):
                raise ValueError("documents must be strings")
            if not 1 <= top_n <= len(documents):
                raise ValueError("top_n out of range")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            record_event(
                {
                    "kind": "cohere_rerank",
                    "authorization_valid": True,
                    "accepted": False,
                    "error_type": type(exc).__name__,
                }
            )
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return

        identified = [identify_document(text) for text in documents]
        ranked = sorted(
            (
                {
                    "index": index,
                    "record_id": record_id,
                    "relevance_score": SCORES.get(record_id, 0.0),
                }
                for index, record_id in enumerate(identified)
            ),
            key=lambda item: (-item["relevance_score"], item["index"]),
        )[:top_n]
        record_event(
            {
                "kind": "cohere_rerank",
                "authorization_valid": True,
                "accepted": True,
                "query": query[:512],
                "model": body.get("model"),
                "return_documents": body.get("return_documents"),
                "input_count": len(documents),
                "input_record_ids": identified,
                "output": ranked,
                "duplicate_removed_before_rerank": len(documents) == len(RECORDS) - 1,
                "pii_redaction_observed": any(
                    "<email>" in item and "<phone>" in item for item in documents
                ),
            }
        )
        self.send_json(
            HTTPStatus.OK,
            {
                "results": [
                    {
                        "index": item["index"],
                        "relevance_score": item["relevance_score"],
                    }
                    for item in ranked
                ]
            },
        )


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
