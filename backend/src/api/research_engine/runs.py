"""Research Engine run endpoints."""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.research_blueprint import ResearchBlueprint
from src.models.research_project import ResearchProject
from src.models.research_run import ResearchRun, RunStatus
from src.models.research_step import ResearchStep
from src.models.user import User
from src.schemas.research_engine import RunCreate, RunResponse
from src.services.research_engine.connectors import (
    ArxivConnector,
    RagStoreConnector,
    SemanticScholarConnector,
)
from src.services.research_engine.engine import WorkflowEngine
from src.services.research_engine.providers import (
    ClaudeProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderConfig,
)
from src.services.research_engine.step_executor import StepExecutor

logger = logging.getLogger(__name__)


async def _get_owned_run(
    run_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> ResearchRun:
    """Fetch a run in a single query, verifying the user owns it via JOIN.

    Raises 404 if the run doesn't exist or the user doesn't own it.
    """
    query = (
        select(ResearchRun)
        .join(ResearchBlueprint, ResearchBlueprint.id == ResearchRun.blueprint_id)
        .join(ResearchProject, ResearchProject.id == ResearchBlueprint.project_id)
        .where(
            ResearchRun.id == run_id,
            ResearchProject.owner_id == user_id,
        )
    )
    result = await db.execute(query)
    run = result.scalars().first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    return run


def _get_step_params(step_def: Dict[str, Any]) -> Dict[str, Any]:
    return step_def.get("params") or step_def.get("parameters") or {}


def _create_provider(model_id: str):
    normalized = (model_id or "").strip()
    if not normalized:
        return None

    from src.core.config import settings

    lower = normalized.lower()
    if lower.startswith("claude"):
        if not settings.ANTHROPIC_API_KEY:
            return None
        return ClaudeProvider(
            ProviderConfig(
                provider_type="claude",
                model_id=normalized,
                api_key=settings.ANTHROPIC_API_KEY,
            )
        )

    if lower.startswith("gpt") or lower.startswith("o1") or lower.startswith("o3"):
        if not settings.OPENAI_API_KEY:
            return None
        return OpenAIProvider(
            ProviderConfig(
                provider_type="openai",
                model_id=normalized,
                api_key=settings.OPENAI_API_KEY,
            )
        )

    if (
        lower.startswith("ollama/")
        or lower.startswith("llama")
        or lower.startswith("mistral")
    ):
        ollama_model = (
            normalized.split("/", 1)[1] if lower.startswith("ollama/") else normalized
        )
        return OllamaProvider(
            ProviderConfig(
                provider_type="ollama",
                model_id=ollama_model,
                base_url=os.getenv("OLLAMA_BASE_URL"),
            )
        )

    return None


def _build_providers(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    providers: Dict[str, Any] = {}
    for step_def in steps:
        params = _get_step_params(step_def)
        model_id = step_def.get("model_id") or params.get("model_id")
        if not model_id or model_id in providers:
            continue
        provider = _create_provider(str(model_id))
        if provider is not None:
            providers[str(model_id)] = provider
    return providers


async def _search_rag_store(query: str, max_results: int = 50) -> Dict[str, Any]:
    """Search the existing hybrid RAG index for local-store style connector output."""
    from src.models.search_schemas import SearchQuery
    from src.services.search.hybrid_search_service import hybrid_search_service

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: hybrid_search_service.search(
            SearchQuery(query=query, limit=max_results, search_type="hybrid")
        ),
    )

    results = []
    for item in response.results:
        metadata = getattr(item, "metadata", {}) or {}
        content = (
            metadata.get("full_text")
            or metadata.get("text")
            or getattr(item, "content_preview", None)
            or getattr(item, "content_snippet", None)
            or ""
        )
        results.append(
            {
                "id": str(getattr(item, "document_id", "")),
                "title": getattr(item, "title", ""),
                "content": content,
                "metadata": metadata,
            }
        )
    return {"results": results}


def _build_connectors() -> Dict[str, Any]:
    """Create connector instances for workflow execution."""
    semantic_connector = SemanticScholarConnector()
    return {
        "arxiv": ArxivConnector(),
        "semantic_scholar": semantic_connector,
        # Temporary aliases until dedicated connectors are implemented.
        "pubmed": semantic_connector,
        "web": semantic_connector,
        "rag_store": RagStoreConnector(search_fn=_search_rag_store),
    }


def _get_effective_parameters(
    blueprint: ResearchBlueprint, run: ResearchRun
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    base = dict(blueprint.parameters or {})
    overrides: Dict[str, Any] = {}
    manifest = run.reproducibility_manifest or {}
    if isinstance(manifest, dict) and isinstance(
        manifest.get("parameters_override"), dict
    ):
        overrides = manifest["parameters_override"]
    base.update(overrides)
    return base, overrides


router = APIRouter(
    prefix="/research-engine",
    tags=["research-engine"],
)


@router.post(
    "/blueprints/{blueprint_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_run(
    blueprint_id: UUID,
    body: RunCreate = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Start a new research run from a blueprint."""
    if body is None:
        body = RunCreate()

    # Look up the blueprint with ownership verification in one query
    query = (
        select(ResearchBlueprint)
        .join(ResearchProject, ResearchProject.id == ResearchBlueprint.project_id)
        .where(
            ResearchBlueprint.id == blueprint_id,
            ResearchProject.owner_id == current_user.id,
        )
    )
    result = await db.execute(query)
    blueprint = result.scalars().first()
    if not blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blueprint not found",
        )

    # Mark blueprint as immutable
    blueprint.is_immutable = True

    # Create the run; execution starts when /runs/{id}/stream is opened.
    run = ResearchRun(
        blueprint_id=blueprint_id,
        blueprint_version=blueprint.version,
        status=RunStatus.PENDING.value,
        reproducibility_manifest={
            "parameters_override": body.parameters_override or {},
        },
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return RunResponse.model_validate(run)


@router.get(
    "/runs/{run_id}",
    response_model=RunResponse,
)
async def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Get run status."""
    run = await _get_owned_run(run_id, current_user.id, db)
    return RunResponse.model_validate(run)


@router.post(
    "/runs/{run_id}/pause",
    response_model=RunResponse,
)
async def pause_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Pause a running run."""
    run = await _get_owned_run(run_id, current_user.id, db)
    if run.status != RunStatus.RUNNING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run is not currently running",
        )
    run.status = RunStatus.PAUSED.value
    await db.commit()
    await db.refresh(run)
    return RunResponse.model_validate(run)


@router.post(
    "/runs/{run_id}/resume",
    response_model=RunResponse,
)
async def resume_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Resume a paused run."""
    run = await _get_owned_run(run_id, current_user.id, db)
    if run.status != RunStatus.PAUSED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run is not currently paused",
        )
    # Keep resumed runs in PAUSED; SSE stream computes start_from for PAUSED runs.
    run.status = RunStatus.PAUSED.value
    await db.commit()
    await db.refresh(run)
    return RunResponse.model_validate(run)


@router.get(
    "/runs/{run_id}/manifest",
)
async def get_manifest(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get reproducibility manifest for a completed run."""
    run = await _get_owned_run(run_id, current_user.id, db)
    if run.status != RunStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run is not completed",
        )
    return run.reproducibility_manifest or {}


@router.get(
    "/runs/{run_id}/stream",
)
async def stream_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream research run execution via SSE.

    Accepts runs in PENDING or PAUSED status. Returns 404 for missing runs,
    409 for runs in non-streamable states (completed, failed, running).
    """
    run = await _get_owned_run(run_id, current_user.id, db)

    # Only pending or paused runs can be streamed
    streamable = {RunStatus.PENDING.value, RunStatus.PAUSED.value}
    if run.status not in streamable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run is in '{run.status}' state and cannot be streamed",
        )

    # Look up the blueprint
    bp_query = select(ResearchBlueprint).where(
        ResearchBlueprint.id == run.blueprint_id,
    )
    bp_result = await db.execute(bp_query)
    blueprint = bp_result.scalars().first()
    if not blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blueprint not found",
        )

    # Determine start_from for paused runs (I3 fix)
    start_from = 0
    if run.status == RunStatus.PAUSED.value:
        step_query = (
            select(ResearchStep)
            .where(ResearchStep.run_id == run_id)
            .order_by(ResearchStep.step_index.desc())
        )
        step_result = await db.execute(step_query)
        last_step = step_result.scalars().first()
        if last_step is not None:
            start_from = last_step.step_index + 1

    required_models = sorted(
        {
            str(step.get("model_id") or _get_step_params(step).get("model_id"))
            for step in blueprint.steps or []
            if step.get("model_id") or _get_step_params(step).get("model_id")
        }
    )
    providers = _build_providers(blueprint.steps or [])
    missing_models = [
        model_id for model_id in required_models if model_id not in providers
    ]
    if missing_models:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No configured LLM provider is available for: "
                + ", ".join(missing_models)
            ),
        )

    connectors = _build_connectors()
    effective_parameters, parameter_overrides = _get_effective_parameters(
        blueprint, run
    )
    blueprint_dict = {
        "steps": blueprint.steps or [],
        "parameters": effective_parameters,
    }
    total_tokens = run.total_tokens or 0

    # Mark the run as RUNNING before streaming begins
    run.status = RunStatus.RUNNING.value
    run.started_at = run.started_at or datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)

    async def event_generator():
        """Yield SSE-formatted events from the workflow engine."""
        nonlocal total_tokens
        executor = StepExecutor(providers=providers, connectors=connectors)
        engine = WorkflowEngine(step_executor=executor)

        try:
            async for event in engine.run(
                blueprint=blueprint_dict,
                run_id=run_id,
                start_from_step=start_from,
            ):
                event_type = event.get("event")
                if event_type == "step_complete":
                    total_tokens += int(event.get("token_count") or 0)
                elif event_type == "run_paused":
                    run.status = RunStatus.PAUSED.value
                    run.total_tokens = total_tokens
                    await db.commit()
                elif event_type == "run_failed":
                    run.status = RunStatus.FAILED.value
                    run.total_tokens = total_tokens
                    run.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                elif event_type == "run_complete":
                    run.status = RunStatus.COMPLETED.value
                    run.total_tokens = total_tokens
                    run.completed_at = datetime.now(timezone.utc)
                    run.reproducibility_manifest = {
                        "run_id": str(run.id),
                        "blueprint_id": str(blueprint.id),
                        "blueprint_version": blueprint.version,
                        "total_tokens": total_tokens,
                        "completed_at": run.completed_at.isoformat(),
                        "parameters_override": parameter_overrides,
                        "parameters": effective_parameters,
                    }
                    await db.commit()

                event_type = event.get("event", "message")
                data = json.dumps(event)
                yield f"event: {event_type}\ndata: {data}\n\n"
        except asyncio.CancelledError:
            # Client disconnected; persist paused state so run can resume later.
            run.status = RunStatus.PAUSED.value
            run.total_tokens = total_tokens
            await db.commit()
            raise
        except Exception as exc:
            # If streaming fails unexpectedly, mark run as failed
            logger.error(f"Stream error for run {run_id}: {exc}")
            run.status = RunStatus.FAILED.value
            run.total_tokens = total_tokens
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            error_event = json.dumps({"event": "run_failed", "error": str(exc)})
            yield f"event: run_failed\ndata: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
