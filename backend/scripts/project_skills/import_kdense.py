"""Scan and upload adapted K-Dense project skills.

Offline scan (default): runs the real server-side parser + scanner against every
adapted SKILL.md and reports blockers/warnings without touching a server.

Upload (--upload): POSTs each clean document to the project-skills API and
approves the resulting change request. Requires the catalog feature flag to be
enabled server-side and a bearer token with access to the project.

Usage:
    python scripts/project_skills/import_kdense.py                # scan only
    python scripts/project_skills/import_kdense.py --upload \
        --base-url http://localhost:8000 --project-id <uuid> \
        --token "$NOUS_TOKEN"
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from src.services.project_skills.scanner import scan_skill_document  # noqa: E402
from src.services.project_skills.skill_document import (  # noqa: E402
    SkillDocumentError,
    parse_skill_document,
)

SKILLS_DIR = pathlib.Path(__file__).parent / "kdense"


def scan_all() -> dict[str, str]:
    """Return {skill_name: document_text} for documents passing the scanner."""
    clean: dict[str, str] = {}
    names: set[str] = set()
    failed = False
    for path in sorted(SKILLS_DIR.glob("*.md")):
        text = path.read_text()
        try:
            doc = parse_skill_document(text)
        except SkillDocumentError as error:
            print(f"FAIL  {path.name}: parse error — {error}")
            failed = True
            continue
        result = scan_skill_document(text, existing_names=names)
        blockers = [f for f in result.findings if f.severity == "blocker"]
        warnings = [f for f in result.findings if f.severity != "blocker"]
        status = "FAIL " if blockers else "ok   "
        print(
            f"{status}{path.name}: lines={doc.instruction_line_count} "
            f"tokens={doc.estimated_tokens} blockers={len(blockers)} "
            f"warnings={len(warnings)}"
        )
        for finding in blockers + warnings:
            print(
                f"      {finding.severity} {finding.code} (line {finding.line}): {finding.message}"
            )
        if blockers:
            failed = True
        else:
            clean[doc.name] = text
            names.add(doc.name)
    if failed:
        sys.exit(1)
    return clean


def upload(clean: dict[str, str], base_url: str, project_id: str, token: str) -> None:
    import httpx

    headers = {"Authorization": f"Bearer {token}"}
    api = f"{base_url.rstrip('/')}/api/v1/projects/{project_id}/skills"

    def approve(client: "httpx.Client", request_id: str) -> None:
        client.post(
            f"{api}/change-requests/{request_id}/approve",
            json={
                "self_approval_acknowledged": True,
                "warning_acknowledged": True,
                "audit_note": "Imported from K-Dense scientific-agent-skills (MIT).",
            },
        ).raise_for_status()

    with httpx.Client(headers=headers, timeout=30.0) as client:
        catalog = client.get(api).raise_for_status().json()
        active = {s["name"] for s in catalog["skills"] if s.get("active_version_id")}
        pending = {
            r["skill_name"]: r["id"]
            for r in catalog["pending_change_requests"]
            if r["status"] == "pending"
        }
        for name, text in clean.items():
            if name in active:
                print(f"skip  {name}: already active in catalog")
            elif name in pending:
                # A previous run created the skill but its approval failed;
                # resume by approving the existing pending request.
                approve(client, pending[name])
                print(f"done  {name}: approved existing pending request")
            else:
                request = (
                    client.post(api, json={"document_text": text})
                    .raise_for_status()
                    .json()
                )
                approve(client, request["id"])
                print(f"done  {name}: created + approved")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--project-id")
    parser.add_argument("--token")
    args = parser.parse_args()

    clean = scan_all()
    print(f"\n{len(clean)} document(s) clean.")
    if args.upload:
        if not (args.project_id and args.token):
            parser.error("--upload requires --project-id and --token")
        upload(clean, args.base_url, args.project_id, args.token)


if __name__ == "__main__":
    main()
