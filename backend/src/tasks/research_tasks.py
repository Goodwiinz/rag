"""
Celery task for executing research workflows.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from celery import current_app

from src.core.config import settings
from src.models.research_blueprint import ResearchBlueprint
from src.models.research_run import ResearchRun, RunStatus
from src.models.research_step import ResearchStep
from src.services.research_engine.connectors import (
    ArxivConnector,
    CrossrefConnector,
    PubMedConnector,
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
from src.tasks.processing_tasks import SessionLocal

logger = logging.getLogger(__name__)


def _create_provider(model_id: str):
    """Factory that returns an LLM provider for a model_id, if configured."""
    normalized = (model_id or "").strip()
    if not normalized:
        return None

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

    if lower.startswith("ollama/") or lower.startswith("llama") or lower.startswith(
        "mistral"
    ):
        ollama_model = normalized.split("/", 1)[1] if lower.startswith("ollama/") else normalized
        return OllamaProvider(
            ProviderConfig(
                provider_type="ollama",
                model_id=ollama_model,
                base_url=os.getenv("OLLAMA_BASE_URL"),
            )
        )

    logger.info(f"No provider mapping available for model_id={model_id}")
    return None


def _get_step_params(step_def: Dict[str, Any]) -> Dict[str, Any]:
    return step_def.get("params") or step_def.get("parameters") or {}


def _build_providers(steps: list) -> dict:
    """Scan blueprint steps and build a provider dict keyed by model_id."""
    providers: dict = {}
    for step_def in steps:
        params = _get_step_params(step_def)
        model_id = step_def.get("model_id") or params.get("model_id")
        if model_id and model_id not in providers:
            provider = _create_provider(model_id)
            if provider is not None:
                providers[model_id] = provider
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


def _build_connectors() -> dict:
    """Create connector instances for the workflow."""
    return {
        "arxiv": ArxivConnector(),
        "semantic_scholar": SemanticScholarConnector(),
        "crossref": CrossrefConnector(mailto="admin@multimodal-rag.com"),
        "pubmed": PubMedConnector(),
        "web": SemanticScholarConnector(),  # fallback alias
        "rag_store": RagStoreConnector(search_fn=_search_rag_store),
    }


async def _run_engine(engine: WorkflowEngine, blueprint_dict: dict, run_id: UUID):
    """Consume the async generator from WorkflowEngine.run() and collect events."""
    events = []
    async for event in engine.run(blueprint_dict, run_id):
        events.append(event)
    return events


@current_app.task(name="execute_research_workflow")
def execute_research_workflow(run_id: str):
    """Execute a research workflow for the given run_id.

    This task:
    1. Loads the ResearchRun and associated ResearchBlueprint from the DB
    2. Sets the run status to RUNNING
    3. Creates connectors and providers, builds a WorkflowEngine
    4. Runs the engine and processes events
    5. Creates ResearchStep records for each completed step
    6. Updates the run status based on terminal events

    NOTE: Uses ``asyncio.run()`` which creates a new event loop.  This
    requires Celery's default **prefork** pool.  If the project switches
    to gevent/eventlet, this call must be replaced with
    ``nest_asyncio`` + ``loop.run_until_complete()`` or a synchronous
    execution path.
    """
    db = SessionLocal()
    run = None

    try:
        # Load the run
        run = db.query(ResearchRun).filter(ResearchRun.id == run_id).first()
        if not run:
            raise ValueError(f"ResearchRun {run_id} not found")

        # Load the blueprint
        blueprint = (
            db.query(ResearchBlueprint)
            .filter(ResearchBlueprint.id == run.blueprint_id)
            .first()
        )
        if not blueprint:
            raise ValueError(
                f"ResearchBlueprint {run.blueprint_id} not found for run {run_id}"
            )

        # Update status to RUNNING
        run.status = RunStatus.RUNNING.value
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        parameters_override = {}
        manifest = run.reproducibility_manifest or {}
        if isinstance(manifest, dict) and isinstance(
            manifest.get("parameters_override"), dict
        ):
            parameters_override = manifest["parameters_override"]

        # Build connectors and providers
        steps = blueprint.steps or []
        connectors = _build_connectors()
        providers = _build_providers(steps)

        # Build engine
        executor = StepExecutor(connectors=connectors, providers=providers)
        engine = WorkflowEngine(step_executor=executor)

        # Prepare the blueprint dict for the engine
        effective_parameters = dict(blueprint.parameters or {})
        effective_parameters.update(parameters_override)
        blueprint_dict = {
            "steps": steps,
            "parameters": effective_parameters,
        }

        # Run the async engine from the synchronous Celery worker
        events = asyncio.run(
            _run_engine(engine, blueprint_dict, UUID(run_id))
        )

        # Process events — collect step records, commit in one transaction
        total_tokens = 0
        final_status = RunStatus.COMPLETED.value
        error_message = None
        step_records: List[ResearchStep] = []

        for event in events:
            event_type = event.get("event")

            if event_type == "step_complete":
                total_tokens += event.get("token_count", 0)

                step_def = {}
                step_index = event.get("step_index", 0)
                if step_index < len(steps):
                    step_def = steps[step_index]

                step_records.append(ResearchStep(
                    run_id=run.id,
                    step_index=event.get("step_index", 0),
                    step_type=step_def.get("type", "unknown"),
                    model_id=step_def.get("model_id")
                    or _get_step_params(step_def).get("model_id"),
                    temperature=step_def.get("temperature")
                    if step_def.get("temperature") is not None
                    else _get_step_params(step_def).get("temperature", 0.0),
                    seed=step_def.get("seed")
                    if step_def.get("seed") is not None
                    else _get_step_params(step_def).get("seed"),
                    output=event.get("output"),
                    quality_marks=event.get("quality_marks"),
                    token_count=event.get("token_count", 0),
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                ))

            elif event_type == "run_complete":
                final_status = RunStatus.COMPLETED.value

            elif event_type == "run_failed":
                final_status = RunStatus.FAILED.value
                error_message = event.get("error")

            elif event_type == "run_paused":
                final_status = RunStatus.PAUSED.value

        # Commit all step records + final run status in one transaction
        for rec in step_records:
            db.add(rec)

        run.status = final_status
        run.total_tokens = total_tokens

        if final_status == RunStatus.COMPLETED.value:
            run.completed_at = datetime.now(timezone.utc)
            run.reproducibility_manifest = {
                "run_id": str(run.id),
                "blueprint_id": str(blueprint.id),
                "blueprint_version": blueprint.version,
                "total_tokens": total_tokens,
                "completed_at": run.completed_at.isoformat(),
                "steps_executed": len(step_records),
                "parameters_override": parameters_override,
                "parameters": effective_parameters,
            }
        elif final_status == RunStatus.FAILED.value:
            run.completed_at = datetime.now(timezone.utc)

        db.commit()

        logger.info(
            f"Research workflow {run_id} finished with status={final_status}"
        )

        return {
            "status": final_status,
            "run_id": run_id,
            "total_tokens": total_tokens,
            "error": error_message,
        }

    except Exception as exc:
        logger.error(f"Research workflow {run_id} failed with exception: {exc}")

        if run is not None:
            try:
                run.status = RunStatus.FAILED.value
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception as update_err:
                logger.error(f"Failed to update run status on error: {update_err}")

        raise

    finally:
        db.close()
