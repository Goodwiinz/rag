"""
Analytics scheduler for recurring jobs
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
try:
    from croniter import croniter
except ImportError:
    croniter = None  # Optional dependency - scheduler features limited without it

from src.models.processing import JobType
from src.services.config.analytics_config import config

logger = logging.getLogger(__name__)


class ScheduledJob:
    """Represents a scheduled analytics job"""

    def __init__(
        self,
        schedule_id: str,
        job_type: JobType,
        cron_expression: str,
        parameters: Dict[str, Any],
        tenant_id: str,
        created_at: datetime = None
    ):
        self.schedule_id = schedule_id
        self.job_type = job_type
        self.cron_expression = cron_expression
        self.parameters = parameters
        self.tenant_id = tenant_id
        self.created_at = created_at or datetime.utcnow()
        self.last_run = None
        self.next_run = self._calculate_next_run()
        self.active = True

    def _calculate_next_run(self) -> datetime:
        """Calculate next run time based on cron expression"""
        if croniter is None:
            # Fallback to simple interval if croniter not installed
            return datetime.utcnow() + timedelta(hours=1)
        cron = croniter(self.cron_expression, datetime.utcnow())
        return cron.get_next(datetime)

    def update_next_run(self):
        """Update the next run time after execution"""
        self.last_run = datetime.utcnow()
        self.next_run = self._calculate_next_run()

    def should_run(self) -> bool:
        """Check if job should run now"""
        return self.active and datetime.utcnow() >= self.next_run


class AnalyticsScheduler:
    """Schedules and manages recurring analytics jobs"""

    def __init__(self):
        self.scheduled_jobs = {}
        self.running = False
        self.scheduler_task = None

    async def start(self):
        """Start the scheduler"""
        self.running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Analytics scheduler started")

    async def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Analytics scheduler stopped")

    async def schedule_job(
        self,
        job_type: JobType,
        cron_expression: str,
        parameters: Dict[str, Any],
        tenant_id: str
    ) -> str:
        """Schedule a recurring analytics job"""
        try:
            # Validate cron expression
            if croniter is not None:
                croniter(cron_expression)

            schedule_id = str(uuid.uuid4())
            scheduled_job = ScheduledJob(
                schedule_id=schedule_id,
                job_type=job_type,
                cron_expression=cron_expression,
                parameters=parameters,
                tenant_id=tenant_id
            )

            self.scheduled_jobs[schedule_id] = scheduled_job

            logger.info(f"Scheduled job {schedule_id} for tenant {tenant_id} with cron '{cron_expression}'")
            return schedule_id

        except Exception as e:
            logger.error(f"Error scheduling job: {e}")
            raise

    async def cancel_job(self, schedule_id: str, tenant_id: str) -> bool:
        """Cancel a scheduled job"""
        if schedule_id in self.scheduled_jobs:
            job = self.scheduled_jobs[schedule_id]
            if job.tenant_id == tenant_id:
                job.active = False
                del self.scheduled_jobs[schedule_id]
                logger.info(f"Cancelled scheduled job {schedule_id}")
                return True
        return False

    async def get_scheduled_jobs(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get scheduled jobs"""
        jobs = []
        for schedule_id, job in self.scheduled_jobs.items():
            if tenant_id is None or job.tenant_id == tenant_id:
                jobs.append({
                    "schedule_id": schedule_id,
                    "job_type": job.job_type.value,
                    "cron_expression": job.cron_expression,
                    "tenant_id": job.tenant_id,
                    "created_at": job.created_at,
                    "last_run": job.last_run,
                    "next_run": job.next_run,
                    "active": job.active
                })
        return jobs

    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                await self._check_and_run_jobs()
                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)

    async def _check_and_run_jobs(self):
        """Check for jobs that need to run and execute them"""
        current_time = datetime.utcnow()

        for schedule_id, job in list(self.scheduled_jobs.items()):
            if job.should_run():
                try:
                    logger.info(f"Running scheduled job {schedule_id}")
                    await self._execute_scheduled_job(job)
                    job.update_next_run()

                except Exception as e:
                    logger.error(f"Error executing scheduled job {schedule_id}: {e}")

    async def _execute_scheduled_job(self, job: ScheduledJob):
        """Execute a scheduled job"""
        # This would integrate with the background job processor
        # For now, just log the execution
        logger.info(f"Executing scheduled job {job.schedule_id} of type {job.job_type.value}")

    async def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        active_jobs = len([j for j in self.scheduled_jobs.values() if j.active])
        next_runs = sorted([j.next_run for j in self.scheduled_jobs.values() if j.active])

        return {
            "running": self.running,
            "total_scheduled_jobs": len(self.scheduled_jobs),
            "active_jobs": active_jobs,
            "next_run": next_runs[0] if next_runs else None,
            "uptime_seconds": 0  # Would track actual uptime
        }