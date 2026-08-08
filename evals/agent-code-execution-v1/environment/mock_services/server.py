#!/usr/bin/env python3
"""Deterministic E2B sandbox-lifecycle + code-execution protocol simulator.

Serves the three wire calls the pinned `e2b`/`e2b_code_interpreter` SDK
(2.30.0 / 2.7.0) makes once `E2B_API_URL`/`E2B_SANDBOX_URL` point here and the
benchmark adapter patches the jupyter-route seam (see Landmine 2 in the plan
and harness.md Fidelity limits):

- ``POST /sandboxes``            -> create (201, ``Sandbox`` model fields)
- ``POST /execute``               -> the code-interpreter's streamed NDJSON
  execute route (envd's jupyter-compatible port)
- ``DELETE /sandboxes/{id}``      -> kill (204)

Unlike the arXiv/PubMed/FRED doubles in sibling tasks, this double does not
just echo canned fixtures: every ``/execute`` request genuinely
``subprocess``-executes the submitted Python in this container and streams
back the real stdout/stderr/exit outcome, so the benchmark proves the code
actually ran rather than trusting a status string (the fake-success trap
named in the plan). Every request is appended to a tamper-proof in-memory
event log served at ``GET /events``, cloned from the
``rag-retrieval-safety-grounding-v1`` mock pattern.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

EVENTS: list[dict[str, Any]] = []
EVENT_LOCK = threading.Lock()

# The dependency-priming call SandboxManager fires on every sandbox creation
# (`e2b_sandbox_manager.py:91-94`, a `pip install -q numpy pandas ...` cell)
# has its return value discarded unconditionally by production code, so the
# double does not need those packages pre-baked — it genuinely tries pip,
# which fails fast under this network's `internal: true` isolation, and the
# resulting nonzero exit is silently ignored exactly as production ignores it.
# A generous but bounded timeout keeps that failure from stalling a run.
SUBPROCESS_TIMEOUT_SECONDS = 30


def record_event(event: dict[str, Any]) -> None:
    with EVENT_LOCK:
        EVENTS.append({"sequence": len(EVENTS) + 1, **event})


class Handler(BaseHTTPRequestHandler):
    server_version = "NOUSBenchmarkE2BMock/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- routing -----------------------------------------------------------
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
        record_event(
            {"type": "unknown_host_or_path", "method": "GET", "path": self.path}
        )
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/sandboxes":
            self.handle_create()
            return
        if parsed.path == "/execute":
            self.handle_execute()
            return
        record_event(
            {"type": "unknown_host_or_path", "method": "POST", "path": self.path}
        )
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/sandboxes/"):
            self.handle_kill(parsed.path.removeprefix("/sandboxes/"))
            return
        record_event(
            {"type": "unknown_host_or_path", "method": "DELETE", "path": self.path}
        )
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    # -- sandbox lifecycle ---------------------------------------------------
    def handle_create(self) -> None:
        body = self._read_json()
        sandbox_id = f"sbx-{uuid.uuid4().hex[:12]}"
        record_event(
            {
                "type": "create",
                "sandbox_id": sandbox_id,
                "template": body.get("templateID") or body.get("template"),
            }
        )
        # Field names are the wire (camelCase) contract the generated
        # `e2b.api.client.models.Sandbox.from_dict` parser expects.
        self.send_json(
            HTTPStatus.CREATED,
            {
                "clientID": "benchmark-client",
                "envdVersion": "1.0.0",
                "sandboxID": sandbox_id,
                "templateID": body.get("templateID") or "code-interpreter-v1",
            },
        )

    def handle_kill(self, sandbox_id: str) -> None:
        record_event({"type": "kill", "sandbox_id": sandbox_id})
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    # -- code execution -------------------------------------------------------
    def handle_execute(self) -> None:
        body = self._read_json()
        code = body.get("code") or ""
        record_event(
            {"type": "execute", "code": code, "language": body.get("language")}
        )

        # NDJSON stream, matching `e2b_code_interpreter.models._parse_output`:
        # {"type": "stdout"|"stderr", "text":..., "timestamp":...},
        # {"type": "error", "name":..., "value":..., "traceback":...},
        # {"type": "number_of_executions", "execution_count":...}.
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()

        def emit(payload: dict[str, Any]) -> None:
            self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))
            self.wfile.flush()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir="/service/scratch"
        ) as script:
            script.write(code)
            script_path = script.name

        try:
            completed = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=SUBPROCESS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            if exc.stdout:
                emit(
                    {"type": "stdout", "text": exc.stdout, "timestamp": time.time_ns()}
                )
            emit(
                {
                    "type": "error",
                    "name": "TimeoutError",
                    "value": f"execution exceeded {SUBPROCESS_TIMEOUT_SECONDS}s",
                    "traceback": "",
                }
            )
            record_event({"type": "execute_result", "timed_out": True})
            return
        finally:
            pass

        if completed.stdout:
            emit(
                {
                    "type": "stdout",
                    "text": completed.stdout,
                    "timestamp": time.time_ns(),
                }
            )
        if completed.stderr:
            emit(
                {
                    "type": "stderr",
                    "text": completed.stderr,
                    "timestamp": time.time_ns(),
                }
            )
        if completed.returncode != 0:
            emit(
                {
                    "type": "error",
                    "name": "SubprocessError",
                    "value": f"exit code {completed.returncode}",
                    "traceback": completed.stderr or "",
                }
            )
        emit({"type": "number_of_executions", "execution_count": 1})
        record_event(
            {
                "type": "execute_result",
                "exit_code": completed.returncode,
                "stdout_bytes": len(completed.stdout or ""),
                "stderr_bytes": len(completed.stderr or ""),
            }
        )


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
