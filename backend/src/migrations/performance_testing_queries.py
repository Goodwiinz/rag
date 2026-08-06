"""
Performance testing queries for enhanced document processing database
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import and_, desc, func, or_, text
from sqlalchemy.orm import Session

from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.document_processing import (
    ContentType,
    DocumentAccessLog,
    DocumentQualityMetrics,
    DocumentVersion,
    MultimodalContent,
    ProcessingHistory,
    ProcessingStage,
    QualityMetricType,
)
from src.models.organization import Organization
from src.models.processing import JobStatus, JobType, ProcessingJob
from src.models.user import User


class PerformanceTestSuite:
    """
    Performance testing suite for database queries
    """

    def __init__(self, db: Session):
        self.db = db
        self.results = {}

    def run_all_tests(self) -> Dict[str, Any]:
        """
        Run all performance tests and return results
        """
        logger.info("Starting performance test suite")

        test_results = {
            "test_suite_timestamp": datetime.utcnow().isoformat(),
            "document_queries": self.test_document_queries(),
            "processing_history_queries": self.test_processing_history_queries(),
            "multimodal_content_queries": self.test_multimodal_content_queries(),
            "quality_metrics_queries": self.test_quality_metrics_queries(),
            "access_log_queries": self.test_access_log_queries(),
            "processing_job_queries": self.test_processing_job_queries(),
            "complex_queries": self.test_complex_queries(),
            "summary": {},
        }

        # Calculate summary statistics
        test_results["summary"] = self._calculate_summary_statistics(test_results)

        logger.info("Performance test suite completed")
        return test_results

    def test_document_queries(self) -> Dict[str, Dict]:
        """
        Test document-related queries
        """
        results = {}

        # Test 1: Basic document lookup by ID
        results["document_by_id"] = self._time_query(
            lambda: self.db.query(Document)
            .filter(Document.id == "00000000-0000-0000-0000-000000000000")
            .first(),
            "Document lookup by ID",
        )

        # Test 2: Get documents by organization with pagination
        results["documents_by_org"] = self._time_query(
            lambda: self.db.query(Document)
            .filter(Document.organization_id == "00000000-0000-0000-0000-000000000000")
            .filter(Document.is_deleted == False)
            .order_by(Document.created_at.desc())
            .limit(20)
            .offset(0)
            .all(),
            "Documents by organization with pagination",
        )

        # Test 3: Get processing queue documents
        results["processing_queue"] = self._time_query(
            lambda: self.db.query(Document)
            .filter(Document.processing_status == ProcessingStatus.PENDING)
            .filter(Document.is_deleted == False)
            .order_by(Document.created_at)
            .limit(50)
            .all(),
            "Processing queue documents",
        )

        # Test 4: Search documents by type and status
        results["documents_by_type_status"] = self._time_query(
            lambda: self.db.query(Document)
            .filter(Document.document_type == DocumentType.PDF)
            .filter(Document.processing_status == ProcessingStatus.COMPLETED)
            .filter(Document.is_deleted == False)
            .order_by(Document.created_at.desc())
            .limit(100)
            .all(),
            "Documents by type and status",
        )

        # Test 5: Get searchable documents for vector search
        results["searchable_documents"] = self._time_query(
            lambda: self.db.query(Document)
            .filter(Document.is_embedded == True)
            .filter(Document.is_indexed == True)
            .filter(Document.is_deleted == False)
            .order_by(Document.created_at.desc())
            .limit(100)
            .all(),
            "Searchable documents for vector search",
        )

        # Test 6: Full-text search on documents
        results["fulltext_search"] = self._time_query(
            lambda: self.db.query(Document)
            .filter(Document.search_vector.match("search terms"))
            .filter(Document.is_deleted == False)
            .limit(20)
            .all(),
            "Full-text search on documents",
        )

        # Test 7: Get documents by user with filtering
        results["user_documents_filtered"] = self._time_query(
            lambda: self.db.query(Document)
            .filter(
                Document.uploaded_by_user_id == "00000000-0000-0000-0000-000000000000"
            )
            .filter(Document.organization_id == "00000000-0000-0000-0000-000000000000")
            .filter(Document.is_deleted == False)
            .order_by(Document.created_at.desc())
            .limit(50)
            .all(),
            "User documents with filtering",
        )

        # Test 8: Complex document filtering with JSON
        results["complex_document_filter"] = self._time_query(
            lambda: self.db.query(Document)
            .filter(Document.document_metadata["category"].astext == "research")
            .filter(Document.document_metadata.has_key("priority"))
            .filter(Document.is_deleted == False)
            .order_by(Document.created_at.desc())
            .limit(30)
            .all(),
            "Complex document filtering with JSON metadata",
        )

        return results

    def test_processing_history_queries(self) -> Dict[str, Dict]:
        """
        Test processing history queries
        """
        results = {}

        # Test 1: Get processing history for a document
        results["document_processing_history"] = self._time_query(
            lambda: self.db.query(ProcessingHistory)
            .filter(
                ProcessingHistory.document_id == "00000000-0000-0000-0000-000000000000"
            )
            .order_by(ProcessingHistory.created_at.desc())
            .all(),
            "Document processing history",
        )

        # Test 2: Get processing queue by stage
        results["processing_queue_by_stage"] = self._time_query(
            lambda: self.db.query(ProcessingHistory)
            .filter(ProcessingHistory.stage == ProcessingStage.PROCESSING)
            .filter(ProcessingHistory.status == "pending")
            .filter(
                ProcessingHistory.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .order_by(ProcessingHistory.created_at)
            .limit(100)
            .all(),
            "Processing queue by stage",
        )

        # Test 3: Get processing history with duration analysis
        results["processing_duration_analysis"] = self._time_query(
            lambda: self.db.query(ProcessingHistory)
            .filter(ProcessingHistory.duration_seconds.isnot(None))
            .filter(
                ProcessingHistory.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .filter(
                ProcessingHistory.created_at >= datetime.utcnow() - timedelta(days=30)
            )
            .order_by(ProcessingHistory.duration_seconds.desc())
            .limit(50)
            .all(),
            "Processing duration analysis",
        )

        # Test 4: Get failed processing jobs for retry
        results["failed_processing_jobs"] = self._time_query(
            lambda: self.db.query(ProcessingHistory)
            .filter(ProcessingHistory.status == "failed")
            .filter(ProcessingHistory.retry_count < 3)
            .filter(
                ProcessingHistory.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .order_by(
                ProcessingHistory.retry_count.asc(), ProcessingHistory.created_at.desc()
            )
            .limit(20)
            .all(),
            "Failed processing jobs for retry",
        )

        # Test 5: Processing statistics aggregation
        results["processing_statistics"] = self._time_query(
            lambda: self.db.query(
                ProcessingHistory.stage,
                ProcessingHistory.status,
                func.count(ProcessingHistory.id).label("count"),
                func.avg(ProcessingHistory.duration_seconds).label("avg_duration"),
            )
            .filter(
                ProcessingHistory.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .filter(
                ProcessingHistory.created_at >= datetime.utcnow() - timedelta(days=7)
            )
            .group_by(ProcessingHistory.stage, ProcessingHistory.status)
            .all(),
            "Processing statistics aggregation",
        )

        return results

    def test_multimodal_content_queries(self) -> Dict[str, Dict]:
        """
        Test multimodal content queries
        """
        results = {}

        # Test 1: Get content by document and type
        results["content_by_document_type"] = self._time_query(
            lambda: self.db.query(MultimodalContent)
            .filter(
                MultimodalContent.document_id == "00000000-0000-0000-0000-000000000000"
            )
            .filter(MultimodalContent.content_type == ContentType.TEXT)
            .order_by(MultimodalContent.sequence_order)
            .all(),
            "Content by document and type",
        )

        # Test 2: Get high-quality content for search
        results["high_quality_content"] = self._time_query(
            lambda: self.db.query(MultimodalContent)
            .filter(MultimodalContent.quality_score >= 0.8)
            .filter(MultimodalContent.is_indexed == True)
            .filter(
                MultimodalContent.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .order_by(MultimodalContent.quality_score.desc())
            .limit(100)
            .all(),
            "High-quality content for search",
        )

        # Test 3: Get content by media type and duration
        results["content_by_media_duration"] = self._time_query(
            lambda: self.db.query(MultimodalContent)
            .filter(
                MultimodalContent.content_type.in_(
                    [ContentType.AUDIO, ContentType.VIDEO]
                )
            )
            .filter(MultimodalContent.media_duration_seconds.isnot(None))
            .filter(MultimodalContent.media_duration_seconds <= 300)  # 5 minutes
            .filter(
                MultimodalContent.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .order_by(MultimodalContent.media_duration_seconds)
            .limit(50)
            .all(),
            "Content by media type and duration",
        )

        # Test 4: Get content by language
        results["content_by_language"] = self._time_query(
            lambda: self.db.query(MultimodalContent)
            .filter(MultimodalContent.content_type == ContentType.TEXT)
            .filter(MultimodalContent.language_code == "en")
            .filter(
                MultimodalContent.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .order_by(MultimodalContent.word_count.desc())
            .limit(100)
            .all(),
            "Content by language",
        )

        # Test 5: Content aggregation statistics
        results["content_statistics"] = self._time_query(
            lambda: self.db.query(
                MultimodalContent.content_type,
                func.count(MultimodalContent.id).label("count"),
                func.avg(MultimodalContent.quality_score).label("avg_quality"),
                func.sum(MultimodalContent.word_count).label("total_words"),
            )
            .filter(
                MultimodalContent.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .filter(MultimodalContent.is_deleted == False)
            .group_by(MultimodalContent.content_type)
            .all(),
            "Content aggregation statistics",
        )

        return results

    def test_quality_metrics_queries(self) -> Dict[str, Dict]:
        """
        Test quality metrics queries
        """
        results = {}

        # Test 1: Get quality metrics for document
        results["document_quality_metrics"] = self._time_query(
            lambda: self.db.query(DocumentQualityMetrics)
            .filter(
                DocumentQualityMetrics.document_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .order_by(DocumentQualityMetrics.created_at.desc())
            .all(),
            "Document quality metrics",
        )

        # Test 2: Get documents below quality threshold
        results["below_threshold_documents"] = self._time_query(
            lambda: self.db.query(DocumentQualityMetrics)
            .filter(DocumentQualityMetrics.meets_threshold == False)
            .filter(
                DocumentQualityMetrics.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .order_by(DocumentQualityMetrics.metric_value.asc())
            .limit(50)
            .all(),
            "Documents below quality threshold",
        )

        # Test 3: Quality metrics by type analysis
        results["quality_metrics_by_type"] = self._time_query(
            lambda: self.db.query(
                DocumentQualityMetrics.metric_type,
                func.count(DocumentQualityMetrics.id).label("count"),
                func.avg(DocumentQualityMetrics.metric_value).label("avg_value"),
                func.min(DocumentQualityMetrics.metric_value).label("min_value"),
                func.max(DocumentQualityMetrics.metric_value).label("max_value"),
            )
            .filter(
                DocumentQualityMetrics.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .filter(
                DocumentQualityMetrics.created_at
                >= datetime.utcnow() - timedelta(days=30)
            )
            .group_by(DocumentQualityMetrics.metric_type)
            .all(),
            "Quality metrics by type analysis",
        )

        # Test 4: Get quality trends over time
        results["quality_trends"] = self._time_query(
            lambda: self.db.query(
                func.date_trunc("day", DocumentQualityMetrics.created_at).label("date"),
                DocumentQualityMetrics.metric_type,
                func.avg(DocumentQualityMetrics.metric_value).label("avg_value"),
            )
            .filter(
                DocumentQualityMetrics.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .filter(
                DocumentQualityMetrics.created_at
                >= datetime.utcnow() - timedelta(days=7)
            )
            .group_by(
                func.date_trunc("day", DocumentQualityMetrics.created_at),
                DocumentQualityMetrics.metric_type,
            )
            .order_by("date", DocumentQualityMetrics.metric_type)
            .all(),
            "Quality trends over time",
        )

        return results

    def test_access_log_queries(self) -> Dict[str, Dict]:
        """
        Test access log queries
        """
        results = {}

        # Test 1: Recent access logs for document
        results["recent_access_logs"] = self._time_query(
            lambda: self.db.query(DocumentAccessLog)
            .filter(
                DocumentAccessLog.document_id == "00000000-0000-0000-0000-000000000000"
            )
            .filter(
                DocumentAccessLog.created_at >= datetime.utcnow() - timedelta(days=7)
            )
            .order_by(DocumentAccessLog.created_at.desc())
            .limit(50)
            .all(),
            "Recent access logs for document",
        )

        # Test 2: Suspicious access patterns
        results["suspicious_access"] = self._time_query(
            lambda: self.db.query(DocumentAccessLog)
            .filter(DocumentAccessLog.is_suspicious == True)
            .filter(
                DocumentAccessLog.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .filter(
                DocumentAccessLog.created_at >= datetime.utcnow() - timedelta(days=1)
            )
            .order_by(DocumentAccessLog.threat_score.desc())
            .limit(100)
            .all(),
            "Suspicious access patterns",
        )

        # Test 3: Access statistics by type
        results["access_statistics"] = self._time_query(
            lambda: self.db.query(
                DocumentAccessLog.access_type,
                DocumentAccessLog.access_result,
                func.count(DocumentAccessLog.id).label("count"),
                func.avg(DocumentAccessLog.response_time_ms).label("avg_response_time"),
            )
            .filter(
                DocumentAccessLog.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .filter(
                DocumentAccessLog.created_at >= datetime.utcnow() - timedelta(days=7)
            )
            .group_by(DocumentAccessLog.access_type, DocumentAccessLog.access_result)
            .all(),
            "Access statistics by type",
        )

        # Test 4: Top accessed documents
        results["top_accessed_documents"] = self._time_query(
            lambda: self.db.query(
                DocumentAccessLog.document_id,
                func.count(DocumentAccessLog.id).label("access_count"),
                func.count(func.distinct(DocumentAccessLog.user_id)).label(
                    "unique_users"
                ),
            )
            .filter(
                DocumentAccessLog.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .filter(DocumentAccessLog.access_result == "success")
            .filter(
                DocumentAccessLog.created_at >= datetime.utcnow() - timedelta(days=30)
            )
            .group_by(DocumentAccessLog.document_id)
            .order_by(func.count(DocumentAccessLog.id).desc())
            .limit(20)
            .all(),
            "Top accessed documents",
        )

        # Test 5: User activity patterns
        results["user_activity_patterns"] = self._time_query(
            lambda: self.db.query(
                DocumentAccessLog.user_id,
                func.count(DocumentAccessLog.id).label("total_accesses"),
                func.count(func.distinct(DocumentAccessLog.document_id)).label(
                    "unique_documents"
                ),
                func.max(DocumentAccessLog.created_at).label("last_access"),
            )
            .filter(
                DocumentAccessLog.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .filter(
                DocumentAccessLog.created_at >= datetime.utcnow() - timedelta(days=7)
            )
            .group_by(DocumentAccessLog.user_id)
            .order_by(func.count(DocumentAccessLog.id).desc())
            .limit(50)
            .all(),
            "User activity patterns",
        )

        return results

    def test_processing_job_queries(self) -> Dict[str, Dict]:
        """
        Test processing job queries
        """
        results = {}

        # Test 1: Active processing jobs
        results["active_processing_jobs"] = self._time_query(
            lambda: self.db.query(ProcessingJob)
            .filter(
                ProcessingJob.status.in_(
                    [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.RETRYING]
                )
            )
            .filter(
                ProcessingJob.organization_id == "00000000-0000-0000-0000-000000000000"
            )
            .order_by(ProcessingJob.priority.desc(), ProcessingJob.created_at)
            .limit(50)
            .all(),
            "Active processing jobs",
        )

        # Test 2: Job queue by type and priority
        results["job_queue_by_type_priority"] = self._time_query(
            lambda: self.db.query(ProcessingJob)
            .filter(ProcessingJob.status == JobStatus.PENDING)
            .filter(ProcessingJob.job_type == JobType.DOCUMENT_INGESTION)
            .filter(
                ProcessingJob.organization_id == "00000000-0000-0000-0000-000000000000"
            )
            .order_by(ProcessingJob.priority.desc(), ProcessingJob.created_at)
            .limit(20)
            .all(),
            "Job queue by type and priority",
        )

        # Test 3: Failed jobs for retry
        results["failed_jobs_for_retry"] = self._time_query(
            lambda: self.db.query(ProcessingJob)
            .filter(ProcessingJob.status == JobStatus.FAILED)
            .filter(ProcessingJob.retry_count < ProcessingJob.max_retries)
            .filter(
                ProcessingJob.organization_id == "00000000-0000-0000-0000-000000000000"
            )
            .order_by(ProcessingJob.retry_count.asc(), ProcessingJob.created_at.desc())
            .limit(30)
            .all(),
            "Failed jobs for retry",
        )

        # Test 4: Job performance statistics
        results["job_performance_stats"] = self._time_query(
            lambda: self.db.query(
                ProcessingJob.job_type,
                ProcessingJob.status,
                func.count(ProcessingJob.id).label("count"),
                func.avg(ProcessingJob.duration_seconds).label("avg_duration"),
                func.avg(ProcessingJob.memory_peak_mb).label("avg_memory"),
            )
            .filter(
                ProcessingJob.organization_id == "00000000-0000-0000-0000-000000000000"
            )
            .filter(ProcessingJob.created_at >= datetime.utcnow() - timedelta(days=7))
            .filter(ProcessingJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]))
            .group_by(ProcessingJob.job_type, ProcessingJob.status)
            .all(),
            "Job performance statistics",
        )

        # Test 5: Worker performance analysis
        results["worker_performance"] = self._time_query(
            lambda: self.db.query(
                ProcessingJob.worker_id,
                func.count(ProcessingJob.id).label("job_count"),
                func.avg(ProcessingJob.duration_seconds).label("avg_duration"),
                func.count(func.distinct(ProcessingJob.job_type)).label("job_types"),
            )
            .filter(ProcessingJob.worker_id.isnot(None))
            .filter(ProcessingJob.status == JobStatus.COMPLETED)
            .filter(ProcessingJob.created_at >= datetime.utcnow() - timedelta(days=1))
            .group_by(ProcessingJob.worker_id)
            .order_by(func.count(ProcessingJob.id).desc())
            .limit(20)
            .all(),
            "Worker performance analysis",
        )

        return results

    def test_complex_queries(self) -> Dict[str, Dict]:
        """
        Test complex multi-table queries
        """
        results = {}

        # Test 1: Document processing pipeline status
        results["document_pipeline_status"] = self._time_query(
            lambda: self.db.query(
                Document.id,
                Document.title,
                Document.processing_status,
                ProcessingHistory.stage,
                ProcessingHistory.status.label("stage_status"),
                ProcessingHistory.progress_percentage,
            )
            .join(ProcessingHistory, Document.id == ProcessingHistory.document_id)
            .filter(Document.organization_id == "00000000-0000-0000-0000-000000000000")
            .filter(Document.is_deleted == False)
            .filter(
                ProcessingHistory.created_at >= datetime.utcnow() - timedelta(hours=24)
            )
            .order_by(Document.created_at.desc())
            .limit(50)
            .all(),
            "Document processing pipeline status",
        )

        # Test 2: Documents with quality metrics
        results["documents_with_quality"] = self._time_query(
            lambda: self.db.query(
                Document.id,
                Document.title,
                Document.document_type,
                DocumentQualityMetrics.metric_type,
                DocumentQualityMetrics.metric_value,
                DocumentQualityMetrics.meets_threshold,
            )
            .join(
                DocumentQualityMetrics,
                Document.id == DocumentQualityMetrics.document_id,
            )
            .filter(Document.organization_id == "00000000-0000-0000-0000-000000000000")
            .filter(Document.is_deleted == False)
            .filter(DocumentQualityMetrics.meets_threshold == False)
            .order_by(DocumentQualityMetrics.metric_value.asc())
            .limit(30)
            .all(),
            "Documents with quality issues",
        )

        # Test 3: Document access and processing correlation
        results["access_processing_correlation"] = self._time_query(
            lambda: self.db.query(
                Document.id,
                Document.title,
                func.count(DocumentAccessLog.id).label("access_count"),
                func.count(func.distinct(ProcessingHistory.id)).label(
                    "processing_stages"
                ),
                func.avg(ProcessingHistory.duration_seconds).label(
                    "avg_processing_time"
                ),
            )
            .outerjoin(DocumentAccessLog, Document.id == DocumentAccessLog.document_id)
            .outerjoin(ProcessingHistory, Document.id == ProcessingHistory.document_id)
            .filter(Document.organization_id == "00000000-0000-0000-0000-000000000000")
            .filter(Document.created_at >= datetime.utcnow() - timedelta(days=30))
            .group_by(Document.id, Document.title)
            .order_by(func.count(DocumentAccessLog.id).desc())
            .limit(20)
            .all(),
            "Document access and processing correlation",
        )

        # Test 4: Multimodal content with jobs
        results["multimodal_content_jobs"] = self._time_query(
            lambda: self.db.query(
                MultimodalContent.document_id,
                MultimodalContent.content_type,
                MultimodalContent.quality_score,
                ProcessingJob.job_type,
                ProcessingJob.status,
                ProcessingJob.progress_percentage,
            )
            .join(Document, MultimodalContent.document_id == Document.id)
            .join(ProcessingJob, Document.id == ProcessingJob.document_id)
            .filter(
                MultimodalContent.organization_id
                == "00000000-0000-0000-0000-000000000000"
            )
            .filter(MultimodalContent.quality_score >= 0.7)
            .filter(ProcessingJob.status.in_([JobStatus.RUNNING, JobStatus.PENDING]))
            .order_by(MultimodalContent.quality_score.desc())
            .limit(25)
            .all(),
            "Multimodal content with active processing jobs",
        )

        # Test 5: Organization performance summary
        results["organization_performance"] = self._time_query(
            lambda: self.db.query(
                Organization.id,
                Organization.name,
                func.count(Document.id).label("total_documents"),
                func.count(func.distinct(Document.document_type)).label(
                    "document_types"
                ),
                func.count(DocumentAccessLog.id).label("total_accesses"),
                func.avg(DocumentQualityMetrics.metric_value).label("avg_quality"),
                func.sum(ProcessingJob.duration_seconds).label("total_processing_time"),
            )
            .outerjoin(Document, Organization.id == Document.organization_id)
            .outerjoin(DocumentAccessLog, Document.id == DocumentAccessLog.document_id)
            .outerjoin(
                DocumentQualityMetrics,
                Document.id == DocumentQualityMetrics.document_id,
            )
            .outerjoin(ProcessingJob, Document.id == ProcessingJob.document_id)
            .filter(Organization.id == "00000000-0000-0000-0000-000000000000")
            .group_by(Organization.id, Organization.name)
            .first(),
            "Organization performance summary",
        )

        return results

    def _time_query(self, query_func, description: str) -> Dict[str, Any]:
        """Time a query execution and return performance metrics"""
        start_time = time.time()

        try:
            result = query_func()
            end_time = time.time()

            execution_time = (end_time - start_time) * 1000  # Convert to milliseconds

            return {
                "description": description,
                "execution_time_ms": round(execution_time, 3),
                "result_count": len(result) if hasattr(result, "__len__") else 1,
                "success": True,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            end_time = time.time()
            execution_time = (end_time - start_time) * 1000

            return {
                "description": description,
                "execution_time_ms": round(execution_time, 3),
                "error": str(e),
                "success": False,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _calculate_summary_statistics(self, test_results: Dict) -> Dict[str, Any]:
        """Calculate summary statistics from test results"""
        summary = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "total_execution_time_ms": 0,
            "avg_execution_time_ms": 0,
            "min_execution_time_ms": float("inf"),
            "max_execution_time_ms": 0,
            "slowest_queries": [],
            "fastest_queries": [],
        }

        all_query_times = []
        all_queries = []

        # Collect all query results
        for category, queries in test_results.items():
            if category == "test_suite_timestamp" or category == "summary":
                continue

            for query_name, query_result in queries.items():
                if "execution_time_ms" in query_result:
                    all_query_times.append(query_result["execution_time_ms"])
                    all_queries.append(
                        {
                            "category": category,
                            "query": query_name,
                            "time_ms": query_result["execution_time_ms"],
                            "success": query_result.get("success", False),
                            "description": query_result.get("description", ""),
                        }
                    )

                    summary["total_queries"] += 1
                    if query_result.get("success", False):
                        summary["successful_queries"] += 1
                    else:
                        summary["failed_queries"] += 1

        if all_query_times:
            summary["total_execution_time_ms"] = sum(all_query_times)
            summary["avg_execution_time_ms"] = sum(all_query_times) / len(
                all_query_times
            )
            summary["min_execution_time_ms"] = min(all_query_times)
            summary["max_execution_time_ms"] = max(all_query_times)

            # Get slowest and fastest queries
            sorted_queries = sorted(
                all_queries, key=lambda x: x["time_ms"], reverse=True
            )
            summary["slowest_queries"] = sorted_queries[:5]
            summary["fastest_queries"] = sorted_queries[-5:]

        # Performance rating
        if summary["avg_execution_time_ms"] < 100:
            summary["performance_rating"] = "Excellent"
        elif summary["avg_execution_time_ms"] < 500:
            summary["performance_rating"] = "Good"
        elif summary["avg_execution_time_ms"] < 1000:
            summary["performance_rating"] = "Fair"
        else:
            summary["performance_rating"] = "Poor"

        return summary


def run_performance_benchmark(db: Session, iterations: int = 3) -> Dict[str, Any]:
    """
    Run performance benchmark with multiple iterations
    """
    suite = PerformanceTestSuite(db)

    benchmark_results = {
        "benchmark_info": {
            "iterations": iterations,
            "start_time": datetime.utcnow().isoformat(),
            "database_url": str(db.bind.url).replace(db.bind.url.password or "", "***"),
        },
        "iterations": [],
    }

    all_summaries = []

    for i in range(iterations):
        logger.info(f"Running benchmark iteration {i + 1}/{iterations}")

        iteration_result = suite.run_all_tests()
        iteration_result["iteration"] = i + 1

        benchmark_results["iterations"].append(iteration_result)
        all_summaries.append(iteration_result["summary"])

    # Calculate aggregate statistics
    benchmark_results["aggregate_summary"] = {
        "total_iterations": iterations,
        "avg_total_queries": sum(s["total_queries"] for s in all_summaries)
        / iterations,
        "avg_successful_queries": sum(s["successful_queries"] for s in all_summaries)
        / iterations,
        "avg_execution_time_ms": sum(s["avg_execution_time_ms"] for s in all_summaries)
        / iterations,
        "performance_consistency": "High"
        if len(all_summaries) > 1
        and max(s["avg_execution_time_ms"] for s in all_summaries)
        / min(s["avg_execution_time_ms"] for s in all_summaries)
        < 1.5
        else "Medium",
    }

    benchmark_results["benchmark_info"]["end_time"] = datetime.utcnow().isoformat()

    return benchmark_results
