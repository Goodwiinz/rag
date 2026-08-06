"""Export service for research engine results."""

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.research_blueprint import ResearchBlueprint
from src.models.research_evidence import ResearchEvidence
from src.models.research_run import ResearchRun
from src.models.research_source import ResearchSource
from src.models.research_step import ResearchStep


class ExportService:
    """Exports research run results as structured JSON reports."""

    async def export_json(self, run_id: UUID, db: AsyncSession) -> dict:
        """Export a completed run as a structured JSON report.

        Args:
            run_id: The UUID of the research run to export.
            db: An async database session.

        Returns:
            A dictionary containing the full structured report.

        Raises:
            ValueError: If the run does not exist or is not completed.
        """
        # Load run with relationships
        run_stmt = (
            select(ResearchRun)
            .where(ResearchRun.id == run_id)
            .options(
                selectinload(ResearchRun.blueprint),
                selectinload(ResearchRun.steps),
                selectinload(ResearchRun.sources),
            )
        )
        result = await db.execute(run_stmt)
        run = result.scalar_one_or_none()

        if run is None:
            raise ValueError(f"Research run {run_id} not found")

        if run.status != "completed":
            raise ValueError(
                f"Research run {run_id} is not completed (status: {run.status})"
            )

        # Load evidence for each step
        step_ids = [step.id for step in run.steps]
        evidence_list: List[ResearchEvidence] = []
        if step_ids:
            ev_stmt = (
                select(ResearchEvidence)
                .where(ResearchEvidence.step_id.in_(step_ids))
                .options(selectinload(ResearchEvidence.source))
            )
            ev_result = await db.execute(ev_stmt)
            evidence_list = list(ev_result.scalars().all())

        # Build evidence lookup by step_id
        evidence_by_step: Dict[UUID, List[Dict[str, Any]]] = {}
        for ev in evidence_list:
            entry = {
                "id": str(ev.id),
                "claim_text": ev.claim_text,
                "confidence": ev.confidence,
                "grounding_status": ev.grounding_status,
                "page_reference": ev.page_reference,
                "source_id": str(ev.source_id),
            }
            evidence_by_step.setdefault(ev.step_id, []).append(entry)

        # Build steps section
        steps_data = []
        for step in sorted(run.steps, key=lambda s: s.step_index):
            steps_data.append({
                "id": str(step.id),
                "step_index": step.step_index,
                "step_type": step.step_type,
                "mode": step.mode,
                "model_id": step.model_id,
                "temperature": step.temperature,
                "seed": step.seed,
                "inputs_hash": step.inputs_hash,
                "outputs_hash": step.outputs_hash,
                "output": step.output,
                "quality_marks": step.quality_marks,
                "token_count": step.token_count,
                "evidence": evidence_by_step.get(step.id, []),
            })

        # Build sources section
        sources_data = []
        for source in run.sources:
            sources_data.append({
                "id": str(source.id),
                "connector_type": source.connector_type,
                "external_id": source.external_id,
                "title": source.title,
                "authors": source.authors,
                "abstract": source.abstract,
                "url": source.url,
                "content_hash": source.content_hash,
            })

        # Build the report
        blueprint = run.blueprint
        report: Dict[str, Any] = {
            "run_id": str(run.id),
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "total_tokens": run.total_tokens,
            "blueprint": {
                "id": str(blueprint.id),
                "name": blueprint.name,
                "version": blueprint.version,
                "template_source": blueprint.template_source,
            },
            "steps": steps_data,
            "sources": sources_data,
            "evidence_count": len(evidence_list),
        }

        return report

    async def export_manifest(self, run_id: UUID, db: AsyncSession) -> dict:
        """Export the reproducibility manifest for a run.

        Args:
            run_id: The UUID of the research run.
            db: An async database session.

        Returns:
            The reproducibility manifest dictionary.

        Raises:
            ValueError: If the run does not exist or has no manifest.
        """
        stmt = select(ResearchRun).where(ResearchRun.id == run_id)
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()

        if run is None:
            raise ValueError(f"Research run {run_id} not found")

        if run.reproducibility_manifest is None:
            raise ValueError(
                f"Research run {run_id} has no reproducibility manifest"
            )

        return run.reproducibility_manifest
