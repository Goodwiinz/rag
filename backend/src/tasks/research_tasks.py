"""
Celery task for executing research workflows.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from celery import current_app

from src.models.research_blueprint import ResearchBlueprint
from src.models.research_run import ResearchRun, RunStatus
from src.models.research_step import ResearchStep
from src.services.research_engine.connectors import (
    ArxivConnector,
    SemanticScholarConnector,
)
from src.services.research_engine.engine import WorkflowEngine
from src.services.research_engine.step_executor import StepExecutor
from src.tasks.processing_tasks import SessionLocal

logger = logging.getLogger(__name__)


def _create_provider(model_id: str):
    """Factory that returns an LLM provider for the given model_id.

    Returns None for unavailable providers.  Real provider wiring will be
    added once provider implementations are available.
    """
    logger.info(f"Provider requested for model_id={model_id} — not yet available, returning None")
    return None


def _build_providers(steps: list) -> dict:
    """Scan blueprint steps and build a provider dict keyed by model_id."""
    providers: dict = {}
    for step_def in steps:
        model_id = step_def.get("params", {}).get("model_id")
        if model_id and model_id not in providers:
            provider = _create_provider(model_id)
            if provider is not None:
                providers[model_id] = provider
    return providers


def _build_connectors() -> dict:
    """Create connector instances for the workflow."""
    return {
        "arxiv": ArxivConnector(),
        "semantic_scholar": SemanticScholarConnector(),
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

        # Build connectors and providers
        steps = blueprint.steps or []
        connectors = _build_connectors()
        providers = _build_providers(steps)

        # Build engine
        executor = StepExecutor(connectors=connectors, providers=providers)
        engine = WorkflowEngine(step_executor=executor)

        # Prepare the blueprint dict for the engine
        blueprint_dict = {
            "steps": steps,
            "parameters": blueprint.parameters or {},
        }

        # Run the async engine from the synchronous Celery worker
        events = asyncio.run(
            _run_engine(engine, blueprint_dict, UUID(run_id))
        )

        # Process events
        total_tokens = 0
        final_status = "completed"
        error_message = None

        for event in events:
            event_type = event.get("event")

            if event_type == "step_complete":
                total_tokens += event.get("token_count", 0)

                step_def = {}
                step_index = event.get("step_index", 0)
                if step_index < len(steps):
                    step_def = steps[step_index]

                step_record = ResearchStep(
                    run_id=run.id,
                    step_index=event.get("step_index", 0),
                    step_type=step_def.get("type", "unknown"),
                    model_id=step_def.get("params", {}).get("model_id"),
                    temperature=step_def.get("params", {}).get("temperature", 0.0),
                    seed=step_def.get("params", {}).get("seed"),
                    output=event.get("output"),
                    quality_marks=event.get("quality_marks"),
                    token_count=event.get("token_count", 0),
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                )
                db.add(step_record)
                db.commit()

            elif event_type == "run_failed":
                final_status = "failed"
                error_message = event.get("error")

            elif event_type == "run_paused":
                final_status = "paused"

        # Update run with final status
        run.status = final_status
        run.total_tokens = total_tokens

        if final_status == "completed":
            run.completed_at = datetime.now(timezone.utc)
            run.reproducibility_manifest = {
                "run_id": str(run.id),
                "blueprint_id": str(blueprint.id),
                "blueprint_version": blueprint.version,
                "total_tokens": total_tokens,
                "completed_at": run.completed_at.isoformat(),
                "steps_executed": len(
                    [e for e in events if e.get("event") == "step_complete"]
                ),
            }
        elif final_status == "failed":
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
