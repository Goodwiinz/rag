"""
Data retention management for RAG Analytics
Handles automated data cleanup, archiving, and compliance with retention policies
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import text, func, and_, or_
from sqlalchemy.orm import Session

from src.config.analytics_config import get_analytics_config
from src.core.database import get_db
from src.models.analytics_event import AnalyticsEvent
from src.models.user_session import UserSession
from src.models.performance_log import PerformanceLog
from src.storage.time_series_store import get_time_series_manager
from src.privacy.data_anonymizer import DataAnonymizer

logger = logging.getLogger(__name__)


class RetentionAction(str, Enum):
    """Data retention actions"""
    DELETE = "delete"
    ARCHIVE = "archive"
    ANONYMIZE = "anonymize"
    COMPRESS = "compress"


@dataclass
class RetentionPolicy:
    """Data retention policy configuration"""
    data_type: str
    table_name: str
    retention_days: int
    action: RetentionAction
    archive_location: Optional[str] = None
    anonymize_fields: Optional[List[str]] = None
    enabled: bool = True


@dataclass
class RetentionReport:
    """Data retention operation report"""
    operation_type: str
    data_type: str
    start_time: datetime
    end_time: datetime
    records_processed: int
    records_deleted: int
    records_archived: int
    records_anonymized: int
    errors: List[str]
    size_freed_mb: Optional[float] = None


class DataRetentionManager:
    """Manages data retention policies and operations"""

    def __init__(self):
        self.config = get_analytics_config()
        self.time_series_manager = get_time_series_manager()
        self.anonymizer = DataAnonymizer()
        self.policies = self._load_retention_policies()

    def _load_retention_policies(self) -> List[RetentionPolicy]:
        """Load retention policies from configuration"""
        policies = [
            RetentionPolicy(
                data_type="analytics_events",
                table_name="analytics_events",
                retention_days=self.config.retention.analytics_events_retention_days,
                action=RetentionAction.DELETE,
                enabled=True
            ),
            RetentionPolicy(
                data_type="user_sessions",
                table_name="user_sessions",
                retention_days=self.config.retention.user_sessions_retention_days,
                action=RetentionAction.DELETE,
                enabled=True
            ),
            RetentionPolicy(
                data_type="performance_logs",
                table_name="performance_logs",
                retention_days=self.config.retention.performance_logs_retention_days,
                action=RetentionAction.DELETE,
                enabled=True
            ),
            RetentionPolicy(
                data_type="quality_metrics",
                table_name="quality_metrics",
                retention_days=self.config.retention.quality_metrics_retention_days,
                action=RetentionAction.ARCHIVE,
                archive_location="archive/quality_metrics/",
                enabled=True
            ),
            RetentionPolicy(
                data_type="user_sessions_pii",
                table_name="user_sessions",
                retention_days=self.config.retention.anonymize_after_days,
                action=RetentionAction.ANONYMIZE,
                anonymize_fields=["ip_address", "user_agent", "referrer", "geo_location"],
                enabled=self.config.privacy.enable_data_anonymization
            )
        ]

        return policies

    async def run_retention_cleanup(self, dry_run: bool = False) -> List[RetentionReport]:
        """Run retention cleanup for all enabled policies"""
        reports = []

        for policy in self.policies:
            if not policy.enabled:
                continue

            try:
                report = await self._execute_retention_policy(policy, dry_run)
                reports.append(report)

                if not dry_run:
                    logger.info(f"Completed retention cleanup for {policy.data_type}: {report.records_deleted} deleted, {report.records_archived} archived, {report.records_anonymized} anonymized")

            except Exception as e:
                error_msg = f"Failed to execute retention policy for {policy.data_type}: {e}"
                logger.error(error_msg)

                report = RetentionReport(
                    operation_type="cleanup",
                    data_type=policy.data_type,
                    start_time=datetime.utcnow(),
                    end_time=datetime.utcnow(),
                    records_processed=0,
                    records_deleted=0,
                    records_archived=0,
                    records_anonymized=0,
                    errors=[error_msg]
                )
                reports.append(report)

        return reports

    async def _execute_retention_policy(self, policy: RetentionPolicy, dry_run: bool = False) -> RetentionReport:
        """Execute a single retention policy"""
        start_time = datetime.utcnow()
        cutoff_date = start_time - timedelta(days=policy.retention_days)

        report = RetentionReport(
            operation_type="retention",
            data_type=policy.data_type,
            start_time=start_time,
            end_time=None,
            records_processed=0,
            records_deleted=0,
            records_archived=0,
            records_anonymized=0,
            errors=[]
        )

        try:
            if policy.action == RetentionAction.DELETE:
                await self._execute_delete_action(policy, cutoff_date, report, dry_run)
            elif policy.action == RetentionAction.ARCHIVE:
                await self._execute_archive_action(policy, cutoff_date, report, dry_run)
            elif policy.action == RetentionAction.ANONYMIZE:
                await self._execute_anonymize_action(policy, cutoff_date, report, dry_run)
            elif policy.action == RetentionAction.COMPRESS:
                await self._execute_compress_action(policy, cutoff_date, report, dry_run)

        except Exception as e:
            error_msg = f"Error executing {policy.action} action for {policy.data_type}: {e}"
            logger.error(error_msg)
            report.errors.append(error_msg)

        report.end_time = datetime.utcnow()
        return report

    async def _execute_delete_action(self, policy: RetentionPolicy, cutoff_date: datetime, report: RetentionReport, dry_run: bool):
        """Execute delete retention action"""
        db = next(get_db())

        try:
            # Get count of records to be deleted
            if policy.data_type == "analytics_events":
                count_query = text(f"""
                    SELECT COUNT(*) FROM {policy.table_name}
                    WHERE created_at < :cutoff_date
                """)
                result = db.execute(count_query, {"cutoff_date": cutoff_date})
                report.records_processed = result.scalar()

                if not dry_run and report.records_processed > 0:
                    # Delete records
                    delete_query = text(f"""
                        DELETE FROM {policy.table_name}
                        WHERE created_at < :cutoff_date
                    """)
                    db.execute(delete_query, {"cutoff_date": cutoff_date})
                    db.commit()
                    report.records_deleted = report.records_processed

            elif policy.data_type == "user_sessions":
                count_query = text(f"""
                    SELECT COUNT(*) FROM {policy.table_name}
                    WHERE created_at < :cutoff_date
                """)
                result = db.execute(count_query, {"cutoff_date": cutoff_date})
                report.records_processed = result.scalar()

                if not dry_run and report.records_processed > 0:
                    delete_query = text(f"""
                        DELETE FROM {policy.table_name}
                        WHERE created_at < :cutoff_date
                    """)
                    db.execute(delete_query, {"cutoff_date": cutoff_date})
                    db.commit()
                    report.records_deleted = report.records_processed

            elif policy.data_type == "performance_logs":
                count_query = text(f"""
                    SELECT COUNT(*) FROM {policy.table_name}
                    WHERE created_at < :cutoff_date
                """)
                result = db.execute(count_query, {"cutoff_date": cutoff_date})
                report.records_processed = result.scalar()

                if not dry_run and report.records_processed > 0:
                    delete_query = text(f"""
                        DELETE FROM {policy.table_name}
                        WHERE created_at < :cutoff_date
                    """)
                    db.execute(delete_query, {"cutoff_date": cutoff_date})
                    db.commit()
                    report.records_deleted = report.records_processed

            # Also clean up time-series data
            if not dry_run:
                ts_deleted = await self.time_series_manager.cleanup_old_data(policy.retention_days)
                report.records_deleted += ts_deleted

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    async def _execute_archive_action(self, policy: RetentionPolicy, cutoff_date: datetime, report: RetentionReport, dry_run: bool):
        """Execute archive retention action"""
        # For now, implement as move to archive table
        # In production, this would move to cold storage or object storage
        db = next(get_db())

        try:
            archive_table = f"{policy.table_name}_archive"

            # Create archive table if it doesn't exist
            if not dry_run:
                create_archive_sql = f"""
                CREATE TABLE IF NOT EXISTS {archive_table} (LIKE {policy.table_name} INCLUDING ALL)
                """
                db.execute(text(create_archive_sql))

            # Get records to archive
            if policy.data_type == "quality_metrics":
                count_query = text(f"""
                    SELECT COUNT(*) FROM {policy.table_name}
                    WHERE created_at < :cutoff_date
                """)
                result = db.execute(count_query, {"cutoff_date": cutoff_date})
                report.records_processed = result.scalar()

                if not dry_run and report.records_processed > 0:
                    # Move records to archive table
                    archive_query = text(f"""
                    INSERT INTO {archive_table}
                    SELECT * FROM {policy.table_name}
                    WHERE created_at < :cutoff_date
                    """)
                    db.execute(archive_query, {"cutoff_date": cutoff_date})

                    # Delete from main table
                    delete_query = text(f"""
                    DELETE FROM {policy.table_name}
                    WHERE created_at < :cutoff_date
                    """)
                    db.execute(delete_query, {"cutoff_date": cutoff_date})

                    db.commit()
                    report.records_archived = report.records_processed

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    async def _execute_anonymize_action(self, policy: RetentionPolicy, cutoff_date: datetime, report: RetentionReport, dry_run: bool):
        """Execute anonymize retention action"""
        db = next(get_db())

        try:
            if policy.data_type == "user_sessions_pii" and policy.anonymize_fields:
                # Get records to anonymize
                count_query = text(f"""
                    SELECT COUNT(*) FROM {policy.table_name}
                    WHERE created_at < :cutoff_date
                    AND (ip_address IS NOT NULL OR user_agent IS NOT NULL OR referrer IS NOT NULL)
                """)
                result = db.execute(count_query, {"cutoff_date": cutoff_date})
                report.records_processed = result.scalar()

                if not dry_run and report.records_processed > 0:
                    # Get records to update
                    select_query = text(f"""
                        SELECT id, {', '.join(policy.anonymize_fields)}
                        FROM {policy.table_name}
                        WHERE created_at < :cutoff_date
                    """)
                    records = db.execute(select_query, {"cutoff_date": cutoff_date}).fetchall()

                    for record in records:
                        update_data = {"id": record.id}
                        for field in policy.anonymize_fields:
                            if hasattr(record, field):
                                value = getattr(record, field)
                                if value:
                                    if field == "ip_address":
                                        update_data[field] = self.anonymizer.anonymize_ip(value)
                                    elif field == "user_agent":
                                        update_data[field] = self.anonymizer.anonymize_user_agent(value)
                                    elif field == "referrer":
                                        update_data[field] = self.anonymizer.anonymize_url(value)
                                    elif field == "geo_location":
                                        update_data[field] = self.anonymizer.anonymize_geo_location(value)

                        # Update record
                        set_clause = ", ".join([f"{field} = :{field}" for field in policy.anonymize_fields])
                        update_query = text(f"""
                            UPDATE {policy.table_name}
                            SET {set_clause}
                            WHERE id = :id
                        """)
                        db.execute(update_query, update_data)

                    db.commit()
                    report.records_anonymized = len(records)

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    async def _execute_compress_action(self, policy: RetentionPolicy, cutoff_date: datetime, report: RetentionReport, dry_run: bool):
        """Execute compress retention action (placeholder for future implementation)"""
        # This would implement table compression for old data
        logger.info(f"Compress action not yet implemented for {policy.data_type}")

    async def get_retention_status(self) -> Dict[str, Any]:
        """Get current retention status and statistics"""
        status = {
            "policies": [],
            "storage_stats": {},
            "compliance_status": {},
            "next_cleanup": None
        }

        # Get policy status
        for policy in self.policies:
            db = next(get_db())
            try:
                if policy.data_type in ["analytics_events", "user_sessions", "performance_logs", "quality_metrics"]:
                    # Get oldest record date
                    oldest_query = text(f"""
                        SELECT MIN(created_at) as oldest_date,
                               COUNT(*) as total_count,
                               COUNT(CASE WHEN created_at < NOW() - INTERVAL '{policy.retention_days} days' THEN 1 END) as expired_count
                        FROM {policy.table_name}
                    """)
                    result = db.execute(oldest_query).first()

                    policy_status = {
                        "data_type": policy.data_type,
                        "table_name": policy.table_name,
                        "retention_days": policy.retention_days,
                        "action": policy.action.value,
                        "enabled": policy.enabled,
                        "oldest_record": result.oldest_date.isoformat() if result.oldest_date else None,
                        "total_records": result.total_count,
                        "expired_records": result.expired_count,
                        "cleanup_needed": result.expired_count > 0
                    }

                    status["policies"].append(policy_status)

            except Exception as e:
                logger.error(f"Failed to get status for {policy.data_type}: {e}")
            finally:
                db.close()

        # Get storage statistics
        try:
            storage_stats = await self.time_series_manager.get_storage_stats()
            status["storage_stats"] = storage_stats
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")

        # Calculate next cleanup time
        if self.config.retention.cleanup_interval_hours:
            next_cleanup = datetime.utcnow() + timedelta(hours=self.config.retention.cleanup_interval_hours)
            status["next_cleanup"] = next_cleanup.isoformat()

        return status

    async def get_compliance_report(self, data_type: Optional[str] = None) -> Dict[str, Any]:
        """Generate compliance report for data retention"""
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "data_type_filter": data_type,
            "compliance_summary": {},
            "policy_violations": [],
            "recommendations": []
        }

        # Check for policy violations
        for policy in self.policies:
            if data_type and policy.data_type != data_type:
                continue

            if not policy.enabled:
                continue

            db = next(get_db())
            try:
                # Check for expired data that should have been processed
                violation_check_query = text(f"""
                    SELECT COUNT(*) as violation_count,
                           MIN(created_at) as oldest_violation
                    FROM {policy.table_name}
                    WHERE created_at < NOW() - INTERVAL '{policy.retention_days} days'
                """)
                result = db.execute(violation_check_query).first()

                if result.violation_count > 0:
                    violation = {
                        "data_type": policy.data_type,
                        "policy": policy.action.value,
                        "retention_days": policy.retention_days,
                        "violation_count": result.violation_count,
                        "oldest_violation": result.oldest_violation.isoformat() if result.oldest_violation else None,
                        "severity": "high" if result.violation_count > 10000 else "medium"
                    }
                    report["policy_violations"].append(violation)

                # Update compliance summary
                if policy.data_type not in report["compliance_summary"]:
                    report["compliance_summary"][policy.data_type] = {
                        "policy_active": policy.enabled,
                        "retention_days": policy.retention_days,
                        "compliant": result.violation_count == 0,
                        "violations": result.violation_count
                    }

            except Exception as e:
                logger.error(f"Failed to check compliance for {policy.data_type}: {e}")
            finally:
                db.close()

        # Generate recommendations
        if report["policy_violations"]:
            report["recommendations"].append("Run immediate retention cleanup to resolve policy violations")
            report["recommendations"].append("Review retention policies and adjust retention periods if needed")
            report["recommendations"].append("Consider automating retention cleanup with scheduled jobs")

        total_violations = sum(v["violation_count"] for v in report["policy_violations"])
        report["total_violations"] = total_violations
        report["overall_compliance"] = total_violations == 0

        return report

    async def cleanup_expired_data(self, data_type: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """Force cleanup of expired data"""
        cleanup_results = {
            "start_time": datetime.utcnow().isoformat(),
            "data_type_filter": data_type,
            "force_execution": force,
            "policies_executed": [],
            "total_records_processed": 0,
            "total_records_deleted": 0,
            "total_records_archived": 0,
            "total_records_anonymized": 0,
            "errors": []
        }

        for policy in self.policies:
            if data_type and policy.data_type != data_type:
                continue

            if not policy.enabled and not force:
                continue

            try:
                report = await self._execute_retention_policy(policy, dry_run=False)

                cleanup_results["policies_executed"].append({
                    "data_type": policy.data_type,
                    "action": policy.action.value,
                    "records_processed": report.records_processed,
                    "records_deleted": report.records_deleted,
                    "records_archived": report.records_archived,
                    "records_anonymized": report.records_anonymized,
                    "errors": report.errors
                })

                cleanup_results["total_records_processed"] += report.records_processed
                cleanup_results["total_records_deleted"] += report.records_deleted
                cleanup_results["total_records_archived"] += report.records_archived
                cleanup_results["total_records_anonymized"] += report.records_anonymized

                if report.errors:
                    cleanup_results["errors"].extend(report.errors)

            except Exception as e:
                error_msg = f"Failed to cleanup {policy.data_type}: {e}"
                logger.error(error_msg)
                cleanup_results["errors"].append(error_msg)

        cleanup_results["end_time"] = datetime.utcnow().isoformat()
        return cleanup_results


# Global data retention manager
_retention_manager = DataRetentionManager()


def get_retention_manager() -> DataRetentionManager:
    """Get the global data retention manager"""
    return _retention_manager


# Background task for scheduled retention cleanup
async def scheduled_retention_cleanup():
    """Scheduled task for automated retention cleanup"""
    try:
        logger.info("Starting scheduled retention cleanup")
        reports = await _retention_manager.run_retention_cleanup(dry_run=False)

        total_deleted = sum(r.records_deleted for r in reports)
        total_archived = sum(r.records_archived for r in reports)
        total_anonymized = sum(r.records_anonymized for r in reports)

        logger.info(f"Scheduled retention cleanup completed: {total_deleted} deleted, {total_archived} archived, {total_anonymized} anonymized")

    except Exception as e:
        logger.error(f"Scheduled retention cleanup failed: {e}")


# Health check for retention system
async def retention_health_check() -> Dict[str, Any]:
    """Health check for data retention system"""
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "policies_loaded": len(_retention_manager.policies),
        "enabled_policies": sum(1 for p in _retention_manager.policies if p.enabled),
        "last_cleanup": None,
        "violations": 0,
        "recommendations": []
    }

    try:
        # Check for policy violations
        compliance_report = await _retention_manager.get_compliance_report()
        health["violations"] = compliance_report["total_violations"]
        health["policy_violations"] = compliance_report["policy_violations"]

        if health["violations"] > 0:
            health["status"] = "degraded"
            health["recommendations"].append("Run retention cleanup to resolve policy violations")

        # Check retention status
        status = await _retention_manager.get_retention_status()
        health["retention_status"] = status

        # Check if cleanup is needed
        cleanup_needed = any(p.get("cleanup_needed", False) for p in status.get("policies", []))
        if cleanup_needed:
            health["recommendations"].append("Data cleanup is needed")

    except Exception as e:
        health["status"] = "unhealthy"
        health["error"] = str(e)
        health["recommendations"].append("Check retention system configuration and database connectivity")

    return health