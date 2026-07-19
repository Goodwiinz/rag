"""
Automated Evaluation Runner for RAG System

This module provides a comprehensive evaluation runner that orchestrates
automated testing of the RAG system with scheduling, reporting, and alerting.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    import schedule

    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False
    schedule = None
from pathlib import Path

from .deepeval_integration import (
    EvaluationFramework,
    EvaluationResults,
    deepeval_integration,
)
from .success_criteria import MetricCategory, QueryType, success_criteria
from .test_datasets import DatasetCategory, test_datasets

logger = logging.getLogger(__name__)


class EvaluationFrequency(Enum):
    """Evaluation schedule frequencies"""

    CONTINUOUS = "continuous"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ON_DEMAND = "on_demand"


class AlertLevel(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class EvaluationSchedule:
    """Schedule configuration for automated evaluations"""

    name: str
    frequency: EvaluationFrequency
    datasets: List[str]
    framework: EvaluationFramework
    enabled: bool
    alert_thresholds: Dict[str, float]
    recipients: List[str]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class EvaluationReport:
    """Comprehensive evaluation report"""

    job_id: str
    schedule_name: str
    timestamp: datetime
    overall_score: float
    success_rate: float
    individual_results: Dict[str, EvaluationResults]
    threshold_violations: List[Dict[str, Any]]
    performance_metrics: Dict[str, float]
    alerts: List[Dict[str, Any]]
    recommendations: List[str]
    execution_time_ms: float


class EvaluationRunner:
    """
    Automated evaluation runner with scheduling and reporting
    """

    def __init__(self):
        self.is_running = False
        self.schedules = self._load_default_schedules()
        self.evaluation_history = []
        self.alert_handlers = self._setup_alert_handlers()

    def _load_default_schedules(self) -> Dict[str, EvaluationSchedule]:
        """Load default evaluation schedules"""
        schedules = {}

        # Daily Basic Functionality Check
        schedules["daily_basic_check"] = EvaluationSchedule(
            name="Daily Basic Functionality Check",
            frequency=EvaluationFrequency.DAILY,
            datasets=["basic_factual_lookup", "basic_reasoning"],
            framework=EvaluationFramework.HYBRID,
            enabled=True,
            alert_thresholds={"overall_score": 0.7, "success_rate": 75.0},
            recipients=["dev-team@company.com", "qa-team@company.com"],
            metadata={"priority": "high", "category": "health_check"},
        )

        # Weekly Multimodal Evaluation
        schedules["weekly_multimodal"] = EvaluationSchedule(
            name="Weekly Multimodal Evaluation",
            frequency=EvaluationFrequency.WEEKLY,
            datasets=["multimodal_cross_modal"],
            framework=EvaluationFramework.HYBRID,
            enabled=True,
            alert_thresholds={"overall_score": 0.6, "success_rate": 70.0},
            recipients=["ai-team@company.com"],
            metadata={"priority": "medium", "category": "feature_validation"},
        )

        # Weekly Enterprise Scenarios
        schedules["weekly_enterprise"] = EvaluationSchedule(
            name="Weekly Enterprise Scenarios",
            frequency=EvaluationFrequency.WEEKLY,
            datasets=["enterprise_business_intelligence"],
            framework=EvaluationFramework.HYBRID,
            enabled=True,
            alert_thresholds={"overall_score": 0.75, "success_rate": 80.0},
            recipients=[
                "product-team@company.com",
                "business-stakeholders@company.com",
            ],
            metadata={"priority": "high", "category": "business_validation"},
        )

        # Monthly Full Suite Evaluation
        schedules["monthly_full_suite"] = EvaluationSchedule(
            name="Monthly Full Suite Evaluation",
            frequency=EvaluationFrequency.MONTHLY,
            datasets=list(test_datasets.datasets.keys()),
            framework=EvaluationFramework.HYBRID,
            enabled=True,
            alert_thresholds={"overall_score": 0.7, "success_rate": 75.0},
            recipients=["leadership@company.com", "all-stakeholders@company.com"],
            metadata={"priority": "high", "category": "comprehensive"},
        )

        # Security Tests (Daily)
        schedules["daily_security"] = EvaluationSchedule(
            name="Daily Security Tests",
            frequency=EvaluationFrequency.DAILY,
            datasets=["security_injection_attacks", "security_unauthorized_access"],
            framework=EvaluationFramework.CUSTOM,
            enabled=True,
            alert_thresholds={"overall_score": 1.0, "success_rate": 100.0},
            recipients=["security-team@company.com", "dev-team@company.com"],
            metadata={"priority": "critical", "category": "security"},
        )

        return schedules

    def _setup_alert_handlers(self) -> Dict[AlertLevel, callable]:
        """Setup alert handlers for different severity levels"""
        return {
            AlertLevel.INFO: self._handle_info_alert,
            AlertLevel.WARNING: self._handle_warning_alert,
            AlertLevel.ERROR: self._handle_error_alert,
            AlertLevel.CRITICAL: self._handle_critical_alert,
        }

    async def run_scheduled_evaluation(
        self,
        schedule_name: str,
        organization_id: str = "default",
        user_id: str = "system",
    ) -> EvaluationReport:
        """
        Run a scheduled evaluation

        Args:
            schedule_name: Name of the scheduled evaluation
            organization_id: Organization ID for tracking
            user_id: User ID for tracking

        Returns:
            EvaluationReport with comprehensive results
        """
        if schedule_name not in self.schedules:
            raise ValueError(f"Schedule '{schedule_name}' not found")

        schedule = self.schedules[schedule_name]
        logger.info(f"Running scheduled evaluation: {schedule_name}")

        start_time = time.time()
        job_id = str(uuid.uuid4())

        try:
            # Collect test cases from all specified datasets
            all_test_cases = []
            dataset_info = {}

            for dataset_name in schedule.datasets:
                dataset = test_datasets.get_dataset(dataset_name)
                if dataset:
                    all_test_cases.extend(dataset.test_cases)
                    dataset_info[dataset_name] = {
                        "test_cases": len(dataset.test_cases),
                        "difficulty": dataset.difficulty_level,
                        "expected_success_rate": dataset.expected_success_rate,
                    }
                else:
                    logger.warning(f"Dataset '{dataset_name}' not found")

            if not all_test_cases:
                raise ValueError("No test cases found for evaluation")

            # Group test cases by query type for evaluation
            query_type_groups = {}
            for test_case in all_test_cases:
                query_type = test_case.query_type or QueryType.FACTUAL_LOOKUP
                if query_type not in query_type_groups:
                    query_type_groups[query_type] = []
                query_type_groups[query_type].append(test_case)

            # Run evaluations for each query type
            individual_results = {}
            overall_metrics = {}
            all_violations = []

            for query_type, test_cases in query_type_groups.items():
                try:
                    result = await deepeval_integration.run_comprehensive_evaluation(
                        test_cases=test_cases,
                        query_type=query_type,
                        framework=schedule.framework,
                        organization_id=organization_id,
                        user_id=user_id,
                    )

                    individual_results[query_type.value] = result
                    overall_metrics[f"{query_type.value}_score"] = result.overall_score
                    overall_metrics[
                        f"{query_type.value}_success_rate"
                    ] = result.success_rate
                    all_violations.extend(result.threshold_violations)

                    logger.info(
                        f"Query type {query_type.value} completed: "
                        f"Score={result.overall_score:.3f}, "
                        f"Success Rate={result.success_rate:.1f}%"
                    )

                except Exception as e:
                    logger.error(f"Error evaluating query type {query_type.value}: {e}")
                    # Add error result
                    individual_results[query_type.value] = EvaluationResults(
                        framework=schedule.framework,
                        overall_score=0.0,
                        individual_metrics={},
                        success_rate=0.0,
                        evaluation_time_ms=0.0,
                        test_cases_evaluated=len(test_cases),
                        threshold_violations=[],
                        metadata={"error": str(e)},
                    )

            # Calculate overall metrics
            overall_score = sum(
                r.overall_score for r in individual_results.values()
            ) / len(individual_results)
            total_tests = sum(
                r.test_cases_evaluated for r in individual_results.values()
            )
            total_success = sum(
                r.success_rate * r.test_cases_evaluated / 100
                for r in individual_results.values()
            )
            overall_success_rate = (
                (total_success / total_tests * 100) if total_tests > 0 else 0.0
            )

            # Check for threshold violations and generate alerts
            alerts = self._check_thresholds_and_generate_alerts(
                schedule_name,
                overall_score,
                overall_success_rate,
                all_violations,
                schedule.alert_thresholds,
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(
                individual_results, all_violations
            )

            # Performance metrics
            execution_time_ms = (time.time() - start_time) * 1000
            performance_metrics = {
                "execution_time_ms": execution_time_ms,
                "test_cases_per_second": total_tests / (execution_time_ms / 1000)
                if execution_time_ms > 0
                else 0,
                "datasets_evaluated": len(schedule.datasets),
                "query_types_evaluated": len(individual_results),
            }

            # Create evaluation report
            report = EvaluationReport(
                job_id=job_id,
                schedule_name=schedule_name,
                timestamp=datetime.now(timezone.utc),
                overall_score=overall_score,
                success_rate=overall_success_rate,
                individual_results=individual_results,
                threshold_violations=all_violations,
                performance_metrics=performance_metrics,
                alerts=alerts,
                recommendations=recommendations,
                execution_time_ms=execution_time_ms,
            )

            # Store in history
            self.evaluation_history.append(report)

            # Send alerts if needed
            await self._send_alerts(alerts, schedule.recipients)

            # Log completion
            logger.info(
                f"Scheduled evaluation '{schedule_name}' completed: "
                f"Score={overall_score:.3f}, Success Rate={overall_success_rate:.1f}%, "
                f"Time={execution_time_ms:.0f}ms"
            )

            return report

        except Exception as e:
            logger.error(f"Error in scheduled evaluation '{schedule_name}': {e}")
            # Create error report
            error_report = EvaluationReport(
                job_id=job_id,
                schedule_name=schedule_name,
                timestamp=datetime.now(timezone.utc),
                overall_score=0.0,
                success_rate=0.0,
                individual_results={},
                threshold_violations=[],
                performance_metrics={
                    "execution_time_ms": (time.time() - start_time) * 1000
                },
                alerts=[
                    {
                        "level": AlertLevel.CRITICAL.value,
                        "message": f"Evaluation failed: {str(e)}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ],
                recommendations=[
                    "Investigate evaluation failure and fix underlying issues"
                ],
                execution_time_ms=(time.time() - start_time) * 1000,
            )

            # Send critical alert
            await self._send_alerts(error_report.alerts, schedule.recipients)

            return error_report

    def _check_thresholds_and_generate_alerts(
        self,
        schedule_name: str,
        overall_score: float,
        success_rate: float,
        violations: List[Dict[str, Any]],
        alert_thresholds: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """Check thresholds and generate appropriate alerts"""
        alerts = []

        # Check overall score threshold
        score_threshold = alert_thresholds.get("overall_score", 0.7)
        if overall_score < score_threshold:
            level = (
                AlertLevel.CRITICAL
                if overall_score < score_threshold * 0.5
                else AlertLevel.ERROR
            )
            alerts.append(
                {
                    "level": level.value,
                    "message": f"Overall score ({overall_score:.3f}) below threshold ({score_threshold:.3f})",
                    "metric": "overall_score",
                    "current_value": overall_score,
                    "threshold": score_threshold,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        # Check success rate threshold
        success_threshold = alert_thresholds.get("success_rate", 75.0)
        if success_rate < success_threshold:
            level = (
                AlertLevel.CRITICAL
                if success_rate < success_threshold * 0.5
                else AlertLevel.ERROR
            )
            alerts.append(
                {
                    "level": level.value,
                    "message": f"Success rate ({success_rate:.1f}%) below threshold ({success_threshold:.1f}%)",
                    "metric": "success_rate",
                    "current_value": success_rate,
                    "threshold": success_threshold,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        # Check for critical violations (security or high-impact metrics)
        critical_violations = [
            v
            for v in violations
            if v.get("metric", "").lower() in ["hallucination_rate", "security"]
        ]
        if critical_violations:
            alerts.append(
                {
                    "level": AlertLevel.CRITICAL.value,
                    "message": f"Critical threshold violations detected: {len(critical_violations)}",
                    "metric": "critical_violations",
                    "current_value": len(critical_violations),
                    "threshold": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": critical_violations[:5],  # Limit to top 5
                }
            )

        # Check for high number of violations
        if len(violations) > 10:
            alerts.append(
                {
                    "level": AlertLevel.WARNING.value,
                    "message": f"High number of threshold violations: {len(violations)}",
                    "metric": "total_violations",
                    "current_value": len(violations),
                    "threshold": 10,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        return alerts

    def _generate_recommendations(
        self,
        individual_results: Dict[str, EvaluationResults],
        violations: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate recommendations based on evaluation results"""
        recommendations = []

        # Analyze overall performance
        scores = [r.overall_score for r in individual_results.values()]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        if avg_score < 0.5:
            recommendations.append(
                "🚨 **Critical**: System performance requires immediate attention and investigation"
            )
        elif avg_score < 0.7:
            recommendations.append(
                "⚠️ **Moderate**: System performance needs improvement to meet quality standards"
            )
        elif avg_score >= 0.8:
            recommendations.append(
                "✅ **Good**: System performance is meeting quality standards"
            )

        # Analyze specific query types
        for query_type, result in individual_results.items():
            if result.overall_score < 0.6:
                recommendations.append(
                    f"🔍 **Query Type Issue**: {query_type.replace('_', ' ').title()} performance needs improvement"
                )

        # Analyze violation patterns
        violation_counts = {}
        for violation in violations:
            metric = violation.get("metric", "unknown")
            violation_counts[metric] = violation_counts.get(metric, 0) + 1

        # Top violation recommendations
        if violation_counts:
            top_violation = max(violation_counts.items(), key=lambda x: x[1])
            recommendations.append(
                f"📊 **Primary Issue**: {top_violation[0]} has {top_violation[1]} violations - prioritize investigation"
            )

        # Specific metric recommendations
        if any("hallucination" in v.get("metric", "").lower() for v in violations):
            recommendations.append(
                "🛡️ **Hallucination Control**: Implement stricter fact-checking and context validation"
            )

        if any("faithfulness" in v.get("metric", "").lower() for v in violations):
            recommendations.append(
                "🔗 **Faithfulness Improvement**: Ensure answers are properly grounded in retrieved context"
            )

        if any("relevancy" in v.get("metric", "").lower() for v in violations):
            recommendations.append(
                "🎯 **Relevance Enhancement**: Improve query understanding and context retrieval quality"
            )

        return recommendations[:10]  # Limit to top 10 recommendations

    async def _send_alerts(self, alerts: List[Dict[str, Any]], recipients: List[str]):
        """Send alerts to specified recipients"""
        if not alerts:
            return

        for alert in alerts:
            level = AlertLevel(alert.get("level", "info"))
            handler = self.alert_handlers.get(level)

            if handler:
                try:
                    await handler(alert, recipients)
                except Exception as e:
                    logger.error(f"Error sending alert: {e}")

    async def _handle_info_alert(self, alert: Dict[str, Any], recipients: List[str]):
        """Handle info-level alerts"""
        logger.info(f"INFO Alert: {alert['message']}")
        # Send email or notification for info alerts
        await self._send_email_notification(alert, recipients, "INFO")

    async def _handle_warning_alert(self, alert: Dict[str, Any], recipients: List[str]):
        """Handle warning-level alerts"""
        logger.warning(f"WARNING Alert: {alert['message']}")
        # Send email for warning alerts
        await self._send_email_notification(alert, recipients, "WARNING")

    async def _handle_error_alert(self, alert: Dict[str, Any], recipients: List[str]):
        """Handle error-level alerts"""
        logger.error(f"ERROR Alert: {alert['message']}")
        # Send email for error alerts
        await self._send_email_notification(alert, recipients, "ERROR")

    async def _handle_critical_alert(
        self, alert: Dict[str, Any], recipients: List[str]
    ):
        """Handle critical-level alerts"""
        logger.critical(f"CRITICAL Alert: {alert['message']}")
        # Send immediate email and possibly other notifications for critical alerts
        await self._send_email_notification(alert, recipients, "CRITICAL")
        # Could also send SMS, Slack, etc.

    async def _send_email_notification(
        self, alert: Dict[str, Any], recipients: List[str], level: str
    ):
        """Send email notification (placeholder implementation)"""
        # This would integrate with your email service
        logger.info(f"Sending {level} email to {recipients}: {alert['message']}")

    def start_scheduler(self):
        """Start the evaluation scheduler"""
        self.is_running = True

        # Schedule daily evaluations
        schedule.every().day.at("02:00").do(
            lambda: asyncio.create_task(
                self.run_scheduled_evaluation("daily_basic_check")
            )
        )
        schedule.every().day.at("03:00").do(
            lambda: asyncio.create_task(self.run_scheduled_evaluation("daily_security"))
        )

        # Schedule weekly evaluations
        schedule.every().sunday.at("04:00").do(
            lambda: asyncio.create_task(
                self.run_scheduled_evaluation("weekly_multimodal")
            )
        )
        schedule.every().sunday.at("05:00").do(
            lambda: asyncio.create_task(
                self.run_scheduled_evaluation("weekly_enterprise")
            )
        )

        # Schedule monthly evaluations
        schedule.every().month.do(
            lambda: asyncio.create_task(
                self.run_scheduled_evaluation("monthly_full_suite")
            )
        )

        logger.info("Evaluation scheduler started")

    def stop_scheduler(self):
        """Stop the evaluation scheduler"""
        self.is_running = False
        schedule.clear()
        logger.info("Evaluation scheduler stopped")

    def run_scheduler_loop(self):
        """Run the scheduler loop"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def get_evaluation_summary(
        self, days: int = 30, schedule_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get evaluation summary for the specified period"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        filtered_reports = [
            report
            for report in self.evaluation_history
            if report.timestamp >= cutoff_date
            and (schedule_name is None or report.schedule_name == schedule_name)
        ]

        if not filtered_reports:
            return {"message": "No evaluations found in the specified period"}

        # Calculate summary statistics
        scores = [r.overall_score for r in filtered_reports]
        success_rates = [r.success_rate for r in filtered_reports]

        summary = {
            "period_days": days,
            "schedule_filter": schedule_name,
            "total_evaluations": len(filtered_reports),
            "average_score": sum(scores) / len(scores),
            "average_success_rate": sum(success_rates) / len(success_rates),
            "best_score": max(scores),
            "worst_score": min(scores),
            "total_alerts": sum(len(r.alerts) for r in filtered_reports),
            "evaluation_trend": self._calculate_trend(scores),
            "recent_evaluations": [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "schedule_name": r.schedule_name,
                    "score": r.overall_score,
                    "success_rate": r.success_rate,
                    "alerts_count": len(r.alerts),
                }
                for r in filtered_reports[-10:]  # Last 10 evaluations
            ],
        }

        return summary

    def _calculate_trend(self, scores: List[float]) -> str:
        """Calculate trend from a list of scores"""
        if len(scores) < 2:
            return "insufficient_data"

        # Simple trend calculation
        recent_avg = sum(scores[-3:]) / min(3, len(scores))
        older_avg = sum(scores[:-3]) / max(1, len(scores) - 3)

        if recent_avg > older_avg + 0.05:
            return "improving"
        elif recent_avg < older_avg - 0.05:
            return "declining"
        else:
            return "stable"

    def export_evaluation_report(
        self, report: EvaluationReport, format: str = "json"
    ) -> str:
        """Export evaluation report in specified format"""
        if format == "json":
            return json.dumps(asdict(report), default=str, indent=2)
        elif format == "markdown":
            return self._generate_markdown_report(report)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _generate_markdown_report(self, report: EvaluationReport) -> str:
        """Generate markdown report"""
        md = f"""# Evaluation Report: {report.schedule_name}

**Job ID**: {report.job_id}
**Timestamp**: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC
**Execution Time**: {report.execution_time_ms:.0f}ms

## Executive Summary

- **Overall Score**: {report.overall_score:.3f} {"✅" if report.overall_score >= 0.75 else "⚠️" if report.overall_score >= 0.6 else "❌"}
- **Success Rate**: {report.success_rate:.1f}% {"✅" if report.success_rate >= 80 else "⚠️" if report.success_rate >= 60 else "❌"}
- **Total Alerts**: {len(report.alerts)}

## Performance Metrics

"""
        for metric, value in report.performance_metrics.items():
            md += f"- **{metric.replace('_', ' ').title()}**: {value}\n"

        md += "\n## Query Type Results\n\n"
        for query_type, result in report.individual_results.items():
            md += f"### {query_type.replace('_', ' ').title()}\n"
            md += f"- Score: {result.overall_score:.3f}\n"
            md += f"- Success Rate: {result.success_rate:.1f}%\n"
            md += f"- Test Cases: {result.test_cases_evaluated}\n\n"

        if report.alerts:
            md += "## Alerts\n\n"
            for alert in report.alerts:
                level_emoji = {
                    "info": "ℹ️",
                    "warning": "⚠️",
                    "error": "❌",
                    "critical": "🚨",
                }
                emoji = level_emoji.get(alert["level"], "📢")
                md += f"- {emoji} **{alert['level'].upper()}**: {alert['message']}\n"

        if report.recommendations:
            md += "\n## Recommendations\n\n"
            for rec in report.recommendations:
                md += f"- {rec}\n"

        return md

    def save_report_to_file(
        self, report: EvaluationReport, file_path: str, format: str = "json"
    ):
        """Save evaluation report to file"""
        content = self.export_evaluation_report(report, format)

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            f.write(content)

        logger.info(f"Evaluation report saved to {file_path}")


# Global evaluation runner instance
evaluation_runner = EvaluationRunner()
