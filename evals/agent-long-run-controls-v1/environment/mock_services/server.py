#!/usr/bin/env python3
"""Sequential DigitalOcean KB protocol double for the long-run task."""

from __future__ import annotations

import json
import os
import re
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

KB_UUID = "benchmark-kb-long-001"
TOKEN = os.environ.get("DO_BENCHMARK_TOKEN", "")
DOC_IDS = (
    "00000000-0000-4000-8000-000000002001",
    "00000000-0000-4000-8000-000000002002",
)
FINDINGS = {
    1: "Project Atlas begins with a verified 12-hour baseline window.",
    2: "Stage 2 verified that the control cohort contains 48 samples.",
    3: "Stage 3 verified that checksum family C7 remained stable.",
    4: "Stage 4 verified that the drift alarm stayed below 0.08.",
    5: "Stage 5 verified that the last observed checkpoint retained 94 percent of validated records.",
    6: "Stage 6 verified a 31-day final horizon.",
}
EVENTS: list[dict[str, Any]] = []
LOCK = threading.Lock()


def query_stage(query: str) -> int:
    tokens = set(re.findall(r"NOUS-LONG-([1-6])", query, re.IGNORECASE))
    return int(next(iter(tokens))) if len(tokens) == 1 else 0


def record(event: dict[str, Any]) -> None:
    with LOCK:
        EVENTS.append({"sequence": len(EVENTS) + 1, **event})


def chunk(stage: int, index: int) -> str:
    next_value = "END" if stage == 6 else f"NOUS-LONG-{stage + 1}"
    marker = f"Stage {stage} source {index + 1} supporting detail. "
    header = (
        f"{FINDINGS[stage]} Evidence document: {DOC_IDS[index]}. "
        f"Next query: {next_value}. "
    )
    return (header + marker * 400)[:7000]


class Handler(BaseHTTPRequestHandler):
    server_version = "NOUSLongRunMock/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self.send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if self.path == "/events":
            with LOCK:
                events = list(EVENTS)
            self.send_json(HTTPStatus.OK, {"events": events})
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        match = re.fullmatch(r"/v1/([^/]+)/retrieve", self.path)
        if not match:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        auth_valid = self.headers.get("Authorization") == f"Bearer {TOKEN}"
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            query = str(body["query"])
            with LOCK:
                expected = len([e for e in EVENTS if e.get("accepted")]) + 1
            stage = query_stage(query)
            accepted = (
                auth_valid
                and match.group(1) == KB_UUID
                and stage == expected
                and 1 <= int(body["num_results"]) <= 100
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            query, stage, accepted = "", 0, False

        event = {
            "kind": "do_retrieve",
            "authorization_valid": auth_valid,
            "accepted": accepted,
            "query": query[:512],
            "stage": stage,
        }
        if not accepted:
            record(event)
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "unexpected_stage"})
            return

        record({**event, "response_stage": stage})
        results = [
            {
                "text_content": chunk(stage, index),
                "metadata": {
                    "item_name": f"{doc_id}.txt",
                    "title": f"Atlas Evidence {index + 1}",
                    "stage": stage,
                },
            }
            for index, doc_id in enumerate(DOC_IDS)
        ]
        self.send_json(
            HTTPStatus.OK,
            {"results": results, "total_results": len(results)},
        )


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
