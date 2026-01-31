"""
Comprehensive migration runner for enhanced document processing features
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.core.database import check_database_health, get_database_info
from src.migrations.data_migration_utils import run_migration, validate_migration
from src.migrations.database_optimization import (
    DatabaseOptimizer,
    analyze_database_performance,
)
from src.migrations.performance_testing_queries import run_performance_benchmark

logger = logging.getLogger(__name__)


class MigrationRunner:
    """
    Comprehensive migration runner for enhanced document processing
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize migration runner

        Args:
            database_url: Database connection URL. If None, uses default from settings.
        """
        self.database_url = (
            database_url
            or "postgresql://postgres:postgres@localhost:5432/multimodal_rag"
        )
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def run_complete_migration(
        self, batch_size: int = 100, optimize: bool = True, benchmark: bool = True
    ) -> Dict[str, Any]:
        """
        Run complete migration process

        Args:
            batch_size: Number of documents to process in each batch
            optimize: Whether to run database optimization
            benchmark: Whether to run performance benchmark

        Returns:
            Complete migration results
        """
        logger.info(
            "Starting complete migration process for enhanced document processing"
        )

        migration_results = {
            "migration_info": {
                "start_time": datetime.utcnow().isoformat(),
                "database_url": self.database_url.replace(
                    self.database_url.split("@")[0].split("//")[1].split(":")[0], "***"
                ),
                "batch_size": batch_size,
                "optimization_enabled": optimize,
                "benchmark_enabled": benchmark,
            },
            "pre_migration_check": {},
            "database_migration": {},
            "data_migration": {},
            "optimization": {},
            "validation": {},
            "performance_benchmark": {},
            "post_migration_check": {},
            "summary": {},
        }

        try:
            # Step 1: Pre-migration health check
            logger.info("Step 1: Running pre-migration health check")
            migration_results["pre_migration_check"] = self._run_health_check()

            if not migration_results["pre_migration_check"]["healthy"]:
                raise Exception("Database health check failed. Aborting migration.")

            # Step 2: Check if database migration has been applied
            logger.info("Step 2: Checking database schema migration status")
            migration_results["database_migration"] = self._check_schema_migration()

            if not migration_results["database_migration"]["migration_applied"]:
                logger.error(
                    "Database schema migration has not been applied. Please run: alembic upgrade head"
                )
                raise Exception("Schema migration required but not applied")

            # Step 3: Run data migration
            logger.info("Step 3: Running data migration")
            migration_results["data_migration"] = self._run_data_migration(batch_size)

            # Step 4: Run database optimization (if enabled)
            if optimize:
                logger.info("Step 4: Running database optimization")
                migration_results["optimization"] = self._run_optimization()

            # Step 5: Validate migration results
            logger.info("Step 5: Validating migration results")
            migration_results["validation"] = self._validate_migration()

            # Step 6: Run performance benchmark (if enabled)
            if benchmark:
                logger.info("Step 6: Running performance benchmark")
                migration_results[
                    "performance_benchmark"
                ] = self._run_performance_benchmark()

            # Step 7: Post-migration health check
            logger.info("Step 7: Running post-migration health check")
            migration_results["post_migration_check"] = self._run_health_check()

            # Step 8: Generate summary
            migration_results["summary"] = self._generate_migration_summary(
                migration_results
            )
            migration_results["migration_info"][
                "end_time"
            ] = datetime.utcnow().isoformat()

            logger.info("Complete migration process finished successfully")
            return migration_results

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            migration_results["error"] = str(e)
            migration_results["migration_info"][
                "end_time"
            ] = datetime.utcnow().isoformat()
            migration_results["success"] = False
            return migration_results

    def _run_health_check(self) -> Dict[str, Any]:
        """Run database health check"""
        try:
            db = self.SessionLocal()

            health_check = {
                "healthy": check_database_health(),
                "database_info": get_database_info(),
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Test basic connectivity
            try:
                result = db.execute(text("SELECT 1 as test"))
                health_check["connectivity"] = "OK"
            except Exception as e:
                health_check["connectivity"] = f"FAILED: {e}"
                health_check["healthy"] = False

            # Test table access
            try:
                result = db.execute(text("SELECT COUNT(*) FROM documents"))
                health_check["table_access"] = "OK"
            except Exception as e:
                health_check["table_access"] = f"FAILED: {e}"
                health_check["healthy"] = False

            db.close()
            return health_check

        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _check_schema_migration(self) -> Dict[str, Any]:
        """Check if schema migration has been applied"""
        try:
            db = self.SessionLocal()

            # Check if new tables exist
            new_tables = [
                "processing_history",
                "document_versions",
                "multimodal_content",
                "document_quality_metrics",
                "document_access_log",
            ]

            table_status = {}
            migration_applied = True

            for table in new_tables:
                try:
                    result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    table_status[table] = "EXISTS"
                except Exception as e:
                    table_status[table] = f"MISSING: {e}"
                    migration_applied = False

            # Check if new columns exist in documents table
            new_columns = [
                "content_summary",
                "document_metadata",
                "processing_error",
                "processing_retry_count",
                "embedding_id",
                "is_embedded",
                "is_indexed",
                "is_public",
                "tags",
                "uploaded_by_user_id",
            ]

            column_status = {}
            for column in new_columns:
                try:
                    result = db.execute(text(f"SELECT {column} FROM documents LIMIT 1"))
                    column_status[column] = "EXISTS"
                except Exception as e:
                    column_status[column] = f"MISSING: {e}"
                    migration_applied = False

            db.close()

            return {
                "migration_applied": migration_applied,
                "new_tables": table_status,
                "new_columns": column_status,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "migration_applied": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _run_data_migration(self, batch_size: int) -> Dict[str, Any]:
        """Run data migration"""
        try:
            db = self.SessionLocal()

            # Run the actual migration
            migration_stats = run_migration(db, batch_size)

            db.close()

            return {
                "success": True,
                "statistics": migration_stats,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _run_optimization(self) -> Dict[str, Any]:
        """Run database optimization"""
        try:
            db = self.SessionLocal()
            optimizer = DatabaseOptimizer(db)

            # Run full optimization
            optimization_results = optimizer.run_full_optimization()

            # Analyze performance
            performance_analysis = analyze_database_performance(db)

            db.close()

            return {
                "success": True,
                "optimization_results": optimization_results,
                "performance_analysis": performance_analysis,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _validate_migration(self) -> Dict[str, Any]:
        """Validate migration results"""
        try:
            db = self.SessionLocal()

            # Run validation
            validation_stats = validate_migration(db)

            # Check data consistency
            consistency_checks = self._run_consistency_checks(db)

            db.close()

            return {
                "success": True,
                "validation_statistics": validation_stats,
                "consistency_checks": consistency_checks,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _run_consistency_checks(self, db) -> Dict[str, Any]:
        """Run data consistency checks"""
        checks = {}

        try:
            # Check 1: All documents should have at least one version
            result = db.execute(
                text(
                    """
                SELECT COUNT(*) as count
                FROM documents d
                LEFT JOIN document_versions dv ON d.id = dv.document_id
                WHERE d.is_deleted = false AND dv.id IS NULL
            """
                )
            )
            documents_without_versions = result.fetchone().count
            checks["documents_without_versions"] = documents_without_versions

            # Check 2: Processing history should exist for processed documents
            result = db.execute(
                text(
                    """
                SELECT COUNT(*) as count
                FROM documents d
                LEFT JOIN processing_history ph ON d.id = ph.document_id
                WHERE d.is_deleted = false
                AND d.processing_status IN ('completed', 'failed')
                AND ph.id IS NULL
            """
                )
            )
            processed_documents_without_history = result.fetchone().count
            checks[
                "processed_documents_without_history"
            ] = processed_documents_without_history

            # Check 3: Quality metrics should exist for content
            result = db.execute(
                text(
                    """
                SELECT COUNT(*) as count
                FROM multimodal_content mc
                LEFT JOIN document_quality_metrics dqm ON mc.document_id = dqm.document_id
                WHERE mc.content_type = 'text' AND dqm.id IS NULL
            """
                )
            )
            text_content_without_metrics = result.fetchone().count
            checks["text_content_without_metrics"] = text_content_without_metrics

            # Check 4: Referential integrity
            result = db.execute(
                text(
                    """
                SELECT COUNT(*) as count
                FROM document_access_log dal
                LEFT JOIN documents d ON dal.document_id = d.id
                WHERE d.id IS NULL
            """
                )
            )
            orphaned_access_logs = result.fetchone().count
            checks["orphaned_access_logs"] = orphaned_access_logs

            # Overall consistency score
            total_issues = sum(checks.values())
            checks["total_issues"] = total_issues
            checks["consistency_score"] = (
                "Excellent"
                if total_issues == 0
                else "Good"
                if total_issues < 10
                else "Poor"
            )

        except Exception as e:
            checks["error"] = str(e)

        return checks

    def _run_performance_benchmark(self) -> Dict[str, Any]:
        """Run performance benchmark"""
        try:
            db = self.SessionLocal()

            # Run benchmark with reduced iterations for faster execution
            benchmark_results = run_performance_benchmark(db, iterations=1)

            db.close()

            return {
                "success": True,
                "benchmark_results": benchmark_results,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _generate_migration_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate migration summary"""
        summary = {
            "overall_success": True,
            "warnings": [],
            "recommendations": [],
            "key_metrics": {},
        }

        # Check for any failures
        for step, result in results.items():
            if step in ["migration_info", "summary"]:
                continue

            if isinstance(result, dict) and result.get("success") is False:
                summary["overall_success"] = False
                summary["warnings"].append(
                    f"{step} failed: {result.get('error', 'Unknown error')}"
                )

        # Extract key metrics
        if "data_migration" in results and results["data_migration"].get("statistics"):
            stats = results["data_migration"]["statistics"]
            summary["key_metrics"] = {
                "documents_migrated": stats.get("documents_processed", 0),
                "versions_created": stats.get("versions_created", 0),
                "processing_history_created": stats.get(
                    "processing_history_created", 0
                ),
                "multimodal_content_created": stats.get(
                    "multimodal_content_created", 0
                ),
                "quality_metrics_created": stats.get("quality_metrics_created", 0),
                "migration_errors": stats.get("errors", 0),
            }

        # Add recommendations
        if summary["key_metrics"].get("migration_errors", 0) > 0:
            summary["recommendations"].append(
                "Review migration errors and consider re-running migration for failed documents"
            )

        if "validation" in results:
            consistency = results["validation"].get("consistency_checks", {})
            if consistency.get("total_issues", 0) > 0:
                summary["recommendations"].append(
                    "Address data consistency issues found during validation"
                )

        if "performance_benchmark" in results and results["performance_benchmark"].get(
            "success"
        ):
            benchmark = results["performance_benchmark"]["benchmark_results"]
            avg_time = benchmark.get("aggregate_summary", {}).get(
                "avg_execution_time_ms", 0
            )
            if avg_time > 1000:
                summary["recommendations"].append(
                    "Consider additional database optimization as query times are above optimal"
                )

        return summary


def main():
    """
    Main function for running migration from command line
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Run enhanced document processing migration"
    )
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Batch size for data migration"
    )
    parser.add_argument(
        "--no-optimize", action="store_true", help="Skip database optimization"
    )
    parser.add_argument(
        "--no-benchmark", action="store_true", help="Skip performance benchmark"
    )
    parser.add_argument("--database-url", type=str, help="Database connection URL")
    parser.add_argument(
        "--output", type=str, help="Output file for migration results (JSON)"
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run migration
    runner = MigrationRunner(args.database_url)

    results = runner.run_complete_migration(
        batch_size=args.batch_size,
        optimize=not args.no_optimize,
        benchmark=not args.no_benchmark,
    )

    # Output results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Migration results saved to: {args.output}")
    else:
        print("\n" + "=" * 50)
        print("MIGRATION RESULTS")
        print("=" * 50)
        print(json.dumps(results, indent=2, default=str))

    # Exit with appropriate code
    if results["summary"]["overall_success"]:
        print("\n✅ Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Migration completed with issues!")
        sys.exit(1)


if __name__ == "__main__":
    main()
