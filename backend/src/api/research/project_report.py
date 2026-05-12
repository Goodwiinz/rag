"""Per-project HTML report renderer.

Inspired by K-Dense rowan-autosearch's ``report.html`` per-run artifact:
generates a single self-contained HTML page summarizing a research
project's contents — papers ingested, project notes, recent agent
activity (from the iteration ledger if enabled), and a quick-scan
header with counts.

Endpoint::

    GET /api/v1/projects/{project_id}/report.html

Returns text/html. No JS dependencies — pure server-side render with
Jinja2 + minimal inline CSS, easy to email/share/archive.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import get_settings
from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models import Collection, CollectionDocument, ProjectNote, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects", tags=["project-report"])

_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _ledger_root() -> Path | None:
    base = get_settings().AGENT_LEDGER_DIR
    return Path(base).expanduser() if base else None


def _scan_recent_threads(project_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Read final.json from each thread under the ledger root and return
    threads whose latest snapshot was scoped to *project_id*.

    Sorted newest first by ``updated_at``. Empty when ledger disabled or
    no matching threads.
    """
    root = _ledger_root()
    if not root or not root.exists():
        return []
    threads: list[dict[str, Any]] = []
    for thread_dir in root.iterdir():
        if not thread_dir.is_dir():
            continue
        final_path = thread_dir / "final.json"
        if not final_path.exists():
            continue
        try:
            data = json.loads(final_path.read_text())
        except Exception:  # noqa: BLE001 - corrupt ledger entry
            continue
        if data.get("current_project_id") != project_id:
            continue
        threads.append(
            {
                "thread_id": data.get("thread_id") or thread_dir.name,
                "latest_turn": data.get("latest_turn"),
                "updated_at": data.get("updated_at"),
                "user_query": (data.get("summary") or {}).get("user_query"),
                "intent": (data.get("summary") or {}).get("intent"),
                "tools_used": (data.get("summary") or {}).get("tools_used") or [],
                "tool_executions_count": data.get("tool_executions_count"),
            }
        )
    threads.sort(key=lambda t: t.get("updated_at") or "", reverse=True)
    return threads[:limit]


@router.get("/{project_id}/report.html", response_class=HTMLResponse)
async def render_project_report(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Render an audit-friendly HTML report of the project's contents.

    Includes ingested documents (with links to their KB entries), project
    notes, and recent agent activity from the iteration ledger (if the
    ``AGENT_LEDGER_DIR`` ledger is enabled).
    """
    project = await db.get(Collection, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Project not accessible"
        )

    docs_q = (
        select(CollectionDocument)
        .where(CollectionDocument.collection_id == project_id)
        .options(selectinload(CollectionDocument.document))
        .order_by(CollectionDocument.sort_order)
    )
    docs_rows = (await db.execute(docs_q)).scalars().all()
    documents = [
        {
            "id": str(cd.document_id),
            "title": (cd.document.title if cd.document else "")
            or (cd.document.filename if cd.document else "Untitled"),
            "filename": cd.document.filename if cd.document else "",
            "status": cd.document.processing_status if cd.document else "",
            "added_at": cd.created_at.isoformat() if cd.created_at else None,
        }
        for cd in docs_rows
        if cd.document
    ]

    notes_q = (
        select(ProjectNote)
        .where(ProjectNote.project_id == project_id)
        .order_by(ProjectNote.created_at.desc())
    )
    notes_rows = (await db.execute(notes_q)).scalars().all()
    notes = [
        {
            "id": str(n.id),
            "title": getattr(n, "title", "") or "Untitled note",
            "content": (getattr(n, "content", "") or "")[:600],
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notes_rows
    ]

    threads = _scan_recent_threads(str(project_id))

    template = _jinja_env.get_template("project_report.html")
    html = template.render(
        project={
            "id": str(project.id),
            "name": getattr(project, "name", "Untitled project"),
            "description": getattr(project, "description", "") or "",
            "created_at": project.created_at.isoformat() if project.created_at else None,
        },
        documents=documents,
        notes=notes,
        threads=threads,
        generated_at=datetime.now(timezone.utc).isoformat(),
        ledger_enabled=bool(_ledger_root()),
    )
    return HTMLResponse(content=html)
