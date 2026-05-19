"""Upload trajectory online evaluators as run rules on the project session.

Posts to LangSmith REST API (no langsmith CLI required). Each metric is
attached as its own rule with a single inline code evaluator.

Usage:
    backend/.venv/bin/python backend/tests/eval/upload_trajectory_rules.py [--dry-run]

Idempotent: deletes existing rules with matching display_name before recreate.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ENV_FILE = REPO / "backend" / ".env"
EVALUATORS_FILE = Path(__file__).with_name("langsmith_trajectory_evaluators.py")
DEFAULT_PROJECT_NAME = "rag-agent-dev-local"

METRICS = [
    ("tool_call_validity", "Tool Call Validity"),
    ("no_tool_loop", "No Tool Loop"),
    ("terminates_with_answer", "Terminates With Answer"),
]


def _load_env() -> tuple[str, str]:
    """Resolve API key + endpoint.

    Priority: existing environment > backend/.env file. CI runners only set
    env vars, so the .env lookup is skipped when both are already present.
    """
    if not os.environ.get("LANGSMITH_API_KEY") and ENV_FILE.exists():
        for line in subprocess.check_output(
            ["grep", "-E", "^(LANGSMITH_API_KEY|LANGSMITH_ENDPOINT)=", str(ENV_FILE)]
        ).decode().splitlines():
            k, _, v = line.partition("=")
            os.environ.setdefault(k, v)
    try:
        api_key = os.environ["LANGSMITH_API_KEY"]
    except KeyError as exc:
        raise RuntimeError(
            "LANGSMITH_API_KEY missing — set env var or populate backend/.env."
        ) from exc
    return api_key, os.environ.get(
        "LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"
    )


def _request(method: str, url: str, api_key: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "X-API-Key": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            payload = r.read().decode()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"HTTP {e.code} on {method} {url}\n{e.read().decode()}\n")
        raise


def _extract_function(source: str, fn_name: str) -> str:
    """Return code containing module-level helpers + the named function only.

    Each rule needs a standalone single-function blob: include the two private
    helpers (`_extract_messages`, `_iter_tool_calls`) plus the target function.
    """
    # Grab the helpers (always needed).
    helpers = []
    for helper in ("_extract_messages", "_iter_tool_calls"):
        match = re.search(
            rf"^def {helper}\(.*?\n(?=^def |\Z)",
            source,
            re.MULTILINE | re.DOTALL,
        )
        if not match:
            raise RuntimeError(f"Helper {helper} not found in source.")
        helpers.append(match.group().rstrip() + "\n")
    fn_match = re.search(
        rf"^def {fn_name}\(.*?\n(?=^def |\Z)",
        source,
        re.MULTILINE | re.DOTALL,
    )
    if not fn_match:
        raise RuntimeError(f"Function {fn_name} not found.")
    # LangSmith sandbox invokes a function named perform_eval — rename target.
    body = re.sub(
        rf"^def {fn_name}\(",
        "def perform_eval(",
        fn_match.group().rstrip(),
        count=1,
        flags=re.MULTILINE,
    )
    return "\n".join(helpers + [body]) + "\n"


def _resolve_session_id(
    api_key: str, endpoint: str, project_name: str = DEFAULT_PROJECT_NAME
) -> str:
    q = urllib.parse.urlencode({"name": project_name, "limit": 5})
    data = _request("GET", f"{endpoint}/api/v1/sessions?{q}", api_key)
    matches = [s for s in data if s.get("name") == project_name]
    if not matches:
        raise RuntimeError(f"Project {project_name!r} not found.")
    return matches[0]["id"]


def _existing_rules(api_key: str, endpoint: str, session_id: str):
    q = urllib.parse.urlencode({"session_id": session_id, "limit": 100})
    return _request("GET", f"{endpoint}/api/v1/runs/rules?{q}", api_key)


def _delete_rule(api_key: str, endpoint: str, rule_id: str) -> None:
    _request("DELETE", f"{endpoint}/api/v1/runs/rules/{rule_id}", api_key)


def _build_rule_body(
    *,
    display_name: str,
    session_id: str,
    code: str,
    sampling_rate: float,
    backfill_from: "datetime.datetime | None" = None,
) -> dict:
    body: dict = {
        "display_name": display_name,
        "session_id": session_id,
        "is_enabled": True,
        "sampling_rate": sampling_rate,
        "filter": "eq(is_root, true)",
        "code_evaluators": [{"code": code, "language": "python"}],
    }
    if backfill_from is not None:
        body["backfill_from"] = backfill_from.isoformat()
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--project",
        default=os.environ.get("LANGSMITH_PROJECT", DEFAULT_PROJECT_NAME),
        help="LangSmith project (session) name to attach rules to.",
    )
    parser.add_argument(
        "--sampling-rate",
        type=float,
        default=1.0,
        help="Fraction of root runs evaluated (0–1).",
    )
    parser.add_argument(
        "--backfill-hours",
        type=int,
        default=0,
        help="Backfill window in hours. 0 disables backfill (default).",
    )
    args = parser.parse_args()

    api_key, endpoint = _load_env()
    source = EVALUATORS_FILE.read_text()

    payloads = []
    for fn_name, display in METRICS:
        code = _extract_function(source, fn_name)
        payloads.append((display, fn_name, code))

    session_id = _resolve_session_id(api_key, endpoint, args.project)
    print(f"Session: {session_id} ({args.project})")

    if args.dry_run:
        for display, fn_name, code in payloads:
            print(f"\n--- {display} ({fn_name}) ---\n{code}")
        return 0

    existing = _existing_rules(api_key, endpoint, session_id)
    existing_by_name = {r["display_name"]: r for r in existing}

    for display, fn_name, code in payloads:
        if display in existing_by_name:
            rule_id = existing_by_name[display]["id"]
            print(f"Removing existing rule {display!r} (id={rule_id})")
            _delete_rule(api_key, endpoint, rule_id)

        backfill_from = None
        if args.backfill_hours > 0:
            backfill_from = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
                hours=args.backfill_hours
            )
        body = _build_rule_body(
            display_name=display,
            session_id=session_id,
            code=code,
            sampling_rate=args.sampling_rate,
            backfill_from=backfill_from,
        )
        result = _request(
            "POST", f"{endpoint}/api/v1/runs/rules", api_key, body
        )
        print(f"Created rule {display!r} id={result.get('id', '<unknown>')}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
