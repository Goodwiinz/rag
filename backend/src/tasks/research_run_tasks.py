"""Sweeper for research runs wedged in RUNNING (R5-M17).

A worker death between the RUNNING transition and a terminal event left the
run bricked: no timeout existed, so it stayed RUNNING forever and could be
neither streamed nor resumed. The sweeper fails runs with no progress past a
threshold, mirroring sweep_stale_agent_runs.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

import structlog

from src.core.database import SessionLocal
from src.models.research_run import ResearchRun, RunStatus
from src.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

STALE_AFTER = timedelta(hours=2)


@celery_app.task(name="src.tasks.research_run_tasks.sweep_stale_research_runs")
def sweep_stale_research_runs() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - STALE_AFTER
        stale = (
            db.query(ResearchRun)
            .filter(
                ResearchRun.status == RunStatus.RUNNING.value,
                ResearchRun.updated_at < cutoff,
            )
            .all()
        )
        for run in stale:
            run.status = RunStatus.FAILED.value
            if hasattr(run, "error"):
                run.error = (
                    f"Swept as stale: RUNNING with no progress since "
                    f"{run.updated_at.isoformat() if run.updated_at else 'unknown'}"
                )
        db.commit()
        if stale:
            logger.warning(
                "sweep_stale_research_runs: failed %d wedged runs", len(stale)
            )
        return {"swept": len(stale)}
    except Exception:
        db.rollback()
        logger.exception("sweep_stale_research_runs failed")
        raise
    finally:
        db.close()
