"""
Database Optimization Framework for Multimodal Enterprise RAG System

This package provides comprehensive database optimizations including:
- PostgreSQL performance tuning and connection pooling
- Neo4j graph database optimizations
- Qdrant vector store performance enhancements
- Redis caching optimizations
- Cross-database integration and monitoring
- Backup and recovery procedures
- Performance analysis and alerting
- Comprehensive testing and validation

Usage:
    from src.database.optimizations import DatabaseOptimizationManager

    manager = DatabaseOptimizationManager()
    await manager.initialize()
    await manager.apply_all_optimizations()

    # Get performance metrics
    metrics = await manager.get_comprehensive_metrics()
"""

from .postgresql_optimizer import (
    PostgreSQLOptimizer,
    DatabaseConfig,
    MigrationManager,
    OptimizationLevel
)

from .neo4j_optimizer import (
    Neo4jOptimizer,
    Neo4jConfig,
    Neo4jOptimizationLevel
)

from .redis_optimizer import (
    RedisOptimizer,
    RedisConfig,
    RedisOptimizationLevel
)

from .connection_pool_manager import (
    AdvancedConnectionPoolManager,
    create_production_pool_manager
)

from .cross_database_integration import (
    CrossDatabaseIntegration,
    create_cross_database_integration,
    run_system_health_check
)

from .backup_recovery import (
    BackupRecoveryManager,
    BackupConfiguration,
    create_production_backup_manager
)

from .performance_analyzer import (
    PerformanceAnalyzer,
    create_performance_analyzer
)

from .testing_suite import (
    DatabaseTestRunner,
    TestConfiguration,
    run_comprehensive_test_suite,
    validate_database_optimizations
)

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseOptimizationManager:
    """
    Main orchestration class for all database optimizations

    This class provides a unified interface for managing optimizations across
    all databases in the Multimodal Enterprise RAG System.
    """

    def __init__(self):
        self.postgresql_optimizer: Optional[PostgreSQLOptimizer] = None
        self.neo4j_optimizer: Optional[Neo4jOptimizer] = None
        self.redis_optimizer: Optional[RedisOptimizer] = None
        self.pool_manager: Optional[AdvancedConnectionPoolManager] = None
        self.cross_db_integration: Optional[CrossDatabaseIntegration] = None
        self.backup_manager: Optional[BackupRecoveryManager] = None
        self.performance_analyzer: Optional[PerformanceAnalyzer] = None
        self.test_runner: Optional[DatabaseTestRunner] = None

        self.is_initialized = False
        self.optimizations_applied = False
        self.monitoring_active = False

    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Initialize all database optimization components

        Args:
            config: Configuration dictionary with database-specific settings

        Returns:
            bool: True if initialization was successful
        """
        try:
            logger.info("Initializing Database Optimization Manager")

            config = config or self._get_default_config()

            # Initialize individual optimizers
            await self._initialize_optimizers(config)

            # Initialize connection pool manager
            await self._initialize_connection_pools(config)

            # Initialize cross-database integration
            await self._initialize_cross_db_integration(config)

            # Initialize backup and recovery
            await self._initialize_backup_recovery(config)

            # Initialize performance analyzer
            await self._initialize_performance_analyzer()

            # Initialize test runner
            self._initialize_test_runner(config)

            self.is_initialized = True
            logger.info("Database Optimization Manager initialized successfully")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize Database Optimization Manager: {e}")
            return False

    async def apply_all_optimizations(self) -> Dict[str, Any]:
        """
        Apply production optimizations to all databases

        Returns:
            Dict with optimization results for each database
        """
        if not self.is_initialized:
            raise RuntimeError("Database Optimization Manager not initialized")

        try:
            logger.info("Applying database optimizations")

            optimization_results = {
                'started_at': datetime.utcnow().isoformat(),
                'results': {},
                'success': True,
                'errors': []
            }

            # Apply PostgreSQL optimizations
            if self.postgresql_optimizer:
                try:
                    pg_result = await self.postgresql_optimizer.apply_production_optimizations()
                    optimization_results['results']['postgresql'] = pg_result
                except Exception as e:
                    optimization_results['results']['postgresql'] = {'success': False, 'error': str(e)}
                    optimization_results['errors'].append(f"PostgreSQL: {e}")
                    optimization_results['success'] = False

            # Apply Neo4j optimizations
            if self.neo4j_optimizer:
                try:
                    neo4j_result = await self.neo4j_optimizer.apply_production_optimizations()
                    optimization_results['results']['neo4j'] = neo4j_result
                except Exception as e:
                    optimization_results['results']['neo4j'] = {'success': False, 'error': str(e)}
                    optimization_results['errors'].append(f"Neo4j: {e}")
                    optimization_results['success'] = False

            # Apply Redis optimizations
            if self.redis_optimizer:
                try:
                    redis_result = await self.redis_optimizer.apply_production_optimizations()
                    optimization_results['results']['redis'] = redis_result
                except Exception as e:
                    optimization_results['results']['redis'] = {'success': False, 'error': str(e)}
                    optimization_results['errors'].append(f"Redis: {e}")
                    optimization_results['success'] = False

            # Optimize connection pools
            if self.pool_manager:
                try:
                    pool_result = await self.pool_manager.optimize_all_pools()
                    optimization_results['results']['connection_pools'] = pool_result
                except Exception as e:
                    optimization_results['results']['connection_pools'] = {'success': False, 'error': str(e)}
                    optimization_results['errors'].append(f"Connection Pools: {e}")
                    optimization_results['success'] = False

            optimization_results['completed_at'] = datetime.utcnow().isoformat()
            optimization_results['duration_seconds'] = (
                datetime.fromisoformat(optimization_results['completed_at']) -
                datetime.fromisoformat(optimization_results['started_at'])
            ).total_seconds()

            self.optimizations_applied = optimization_results['success']

            if optimization_results['success']:
                logger.info("All database optimizations applied successfully")
            else:
                logger.warning(f"Some optimizations failed: {optimization_results['errors']}")

            return optimization_results

        except Exception as e:
            logger.error(f"Failed to apply database optimizations: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    async def start_monitoring(self, monitoring_interval_seconds: int = 60) -> bool:
        """
        Start continuous performance monitoring

        Args:
            monitoring_interval_seconds: Interval between metric collections

        Returns:
            bool: True if monitoring started successfully
        """
        if not self.is_initialized:
            raise RuntimeError("Database Optimization Manager not initialized")

        try:
            # Start performance analyzer monitoring
            if self.performance_analyzer:
                await self.performance_analyzer.start_monitoring(monitoring_interval_seconds)

            self.monitoring_active = True
            logger.info(f"Database monitoring started with {monitoring_interval_seconds}s interval")
            return True

        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            return False

    async def stop_monitoring(self):
        """Stop performance monitoring"""
        try:
            if self.performance_analyzer:
                await self.performance_analyzer.stop_monitoring()

            self.monitoring_active = False
            logger.info("Database monitoring stopped")

        except Exception as e:
            logger.error(f"Failed to stop monitoring: {e}")

    async def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics from all databases

        Returns:
            Dict with metrics from all database systems
        """
        if not self.is_initialized:
            raise RuntimeError("Database Optimization Manager not initialized")

        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'databases': {},
            'connection_pools': {},
            'cross_db_metrics': {},
            'alerts': [],
            'recommendations': []
        }

        # Get individual database metrics
        if self.postgresql_optimizer:
            try:
                metrics['databases']['postgresql'] = await self.postgresql_optimizer.get_optimization_report()
            except Exception as e:
                metrics['databases']['postgresql'] = {'error': str(e)}

        if self.neo4j_optimizer:
            try:
                metrics['databases']['neo4j'] = await self.neo4j_optimizer.get_graph_statistics()
            except Exception as e:
                metrics['databases']['neo4j'] = {'error': str(e)}

        if self.redis_optimizer:
            try:
                metrics['databases']['redis'] = await self.redis_optimizer.get_redis_metrics()
            except Exception as e:
                metrics['databases']['redis'] = {'error': str(e)}

        # Get connection pool metrics
        if self.pool_manager:
            try:
                metrics['connection_pools'] = await self.pool_manager.get_all_metrics()
            except Exception as e:
                metrics['connection_pools'] = {'error': str(e)}

        # Get cross-database integration metrics
        if self.cross_db_integration:
            try:
                metrics['cross_db_metrics'] = await self.cross_db_integration.get_comprehensive_metrics()
            except Exception as e:
                metrics['cross_db_metrics'] = {'error': str(e)}

        # Get performance analyzer metrics
        if self.performance_analyzer:
            try:
                summary = self.performance_analyzer.get_performance_summary()
                metrics['performance_summary'] = summary
                metrics['alerts'] = [
                    {
                        'alert_id': alert.alert_id,
                        'severity': alert.severity.value,
                        'description': alert.description,
                        'triggered_at': alert.triggered_at.isoformat() if alert.triggered_at else None
                    }
                    for alert in self.performance_analyzer.get_active_alerts()
                ]
                metrics['recommendations'] = [
                    {
                        'recommendation_id': rec.recommendation_id,
                        'priority': rec.priority,
                        'description': rec.description,
                        'estimated_improvement': rec.estimated_improvement
                    }
                    for rec in self.performance_analyzer.get_recommendations()
                ]
            except Exception as e:
                metrics['performance_analyzer'] = {'error': str(e)}

        return metrics

    async def run_comprehensive_tests(self) -> Dict[str, Any]:
        """
        Run comprehensive test suite for all optimizations

        Returns:
            Dict with test results and report
        """
        if not self.is_initialized:
            raise RuntimeError("Database Optimization Manager not initialized")

        try:
            logger.info("Running comprehensive database optimization tests")
            return await run_comprehensive_test_suite()

        except Exception as e:
            logger.error(f"Failed to run comprehensive tests: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    async def create_backup(self, backup_type: str = "full") -> Dict[str, Any]:
        """
        Create backup of all databases

        Args:
            backup_type: Type of backup (full, incremental, differential)

        Returns:
            Dict with backup results
        """
        if not self.backup_manager:
            raise RuntimeError("Backup manager not initialized")

        try:
            logger.info(f"Creating {backup_type} backup of all databases")
            return await self.backup_manager.create_full_backup()

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    async def cleanup_maintenance(self) -> Dict[str, Any]:
        """
        Run cleanup and maintenance tasks

        Returns:
            Dict with cleanup results
        """
        cleanup_results = {
            'started_at': datetime.utcnow().isoformat(),
            'results': {},
            'success': True
        }

        try:
            # Cleanup old backups
            if self.backup_manager:
                backup_cleanup = await self.backup_manager.cleanup_all_old_backups()
                cleanup_results['results']['backup_cleanup'] = backup_cleanup

            # Cleanup database data
            if self.cross_db_integration:
                db_cleanup = await self.cross_db_integration.cleanup_all_databases()
                cleanup_results['results']['database_cleanup'] = db_cleanup

            # Optimize connection pools
            if self.pool_manager:
                pool_optimization = await self.pool_manager.optimize_all_pools()
                cleanup_results['results']['pool_optimization'] = pool_optimization

            cleanup_results['completed_at'] = datetime.utcnow().isoformat()
            logger.info("Cleanup and maintenance tasks completed")

        except Exception as e:
            cleanup_results['success'] = False
            cleanup_results['error'] = str(e)
            logger.error(f"Cleanup maintenance failed: {e}")

        return cleanup_results

    async def shutdown(self):
        """Shutdown all components gracefully"""
        try:
            logger.info("Shutting down Database Optimization Manager")

            # Stop monitoring
            await self.stop_monitoring()

            # Close connection pools
            if self.pool_manager:
                await self.pool_manager.shutdown_all()

            # Close database connections
            if self.neo4j_optimizer:
                await self.neo4j_optimizer.close()

            if self.redis_optimizer:
                await self.redis_optimizer.close()

            # Close cross-database integration
            if self.cross_db_integration:
                await self.cross_db_integration.close_all_connections()

            self.is_initialized = False
            self.optimizations_applied = False
            logger.info("Database Optimization Manager shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for all databases"""
        return {
            'postgresql': {
                'host': 'localhost',
                'port': 5432,
                'user': 'raguser',
                'password': 'rag_password_123',
                'database': 'ragdb',
                'pool_size': 50,
                'optimization_level': 'production'
            },
            'neo4j': {
                'uri': 'bolt://localhost:7687',
                'user': 'neo4j',
                'password': 'neo4j_password_123',
                'database': 'neo4j',
                'max_connection_pool_size': 50,
                'optimization_level': 'production'
            },
            'redis': {
                'host': 'localhost',
                'port': 6379,
                'password': 'redis_password_123',
                'database': 0,
                'max_connections': 100,
                'optimization_level': 'production'
            },
            'qdrant': {
                'url': 'http://localhost:6333'
            }
        }

    async def _initialize_optimizers(self, config: Dict[str, Any]):
        """Initialize individual database optimizers"""
        # PostgreSQL
        if 'postgresql' in config:
            pg_config = DatabaseConfig(**config['postgresql'])
            self.postgresql_optimizer = PostgreSQLOptimizer(pg_config)
            await self.postgresql_optimizer.initialize()

        # Neo4j
        if 'neo4j' in config:
            neo4j_config = Neo4jConfig(**config['neo4j'])
            self.neo4j_optimizer = Neo4jOptimizer(neo4j_config)
            await self.neo4j_optimizer.initialize()

        # Redis
        if 'redis' in config:
            redis_config = RedisConfig(**config['redis'])
            self.redis_optimizer = RedisOptimizer(redis_config)
            await self.redis_optimizer.initialize()

    async def _initialize_connection_pools(self, config: Dict[str, Any]):
        """Initialize advanced connection pool manager"""
        self.pool_manager = await create_production_pool_manager()

    async def _initialize_cross_db_integration(self, config: Dict[str, Any]):
        """Initialize cross-database integration"""
        self.cross_db_integration = await create_cross_database_integration()

    async def _initialize_backup_recovery(self, config: Dict[str, Any]):
        """Initialize backup and recovery manager"""
        backup_config = BackupConfiguration(
            backup_directory="/var/backups/rag_system",
            retention_days=30,
            compression_enabled=True,
            verification_enabled=True
        )
        self.backup_manager = BackupRecoveryManager(backup_config)
        await self.backup_manager.initialize(config)

    async def _initialize_performance_analyzer(self):
        """Initialize performance analyzer"""
        self.performance_analyzer = await create_performance_analyzer()

    def _initialize_test_runner(self, config: Dict[str, Any]):
        """Initialize test runner"""
        test_config = TestConfiguration(
            test_timeout_seconds=300,
            performance_thresholds={
                'max_query_time_ms': 1000,
                'min_ops_per_second': 1000,
                'max_error_rate_percent': 5
            }
        )
        self.test_runner = DatabaseTestRunner(test_config)


# Convenience functions for quick usage
async def initialize_database_optimizations(config: Optional[Dict[str, Any]] = None) -> DatabaseOptimizationManager:
    """
    Initialize and return a fully configured DatabaseOptimizationManager

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured DatabaseOptimizationManager instance
    """
    manager = DatabaseOptimizationManager()
    success = await manager.initialize(config)

    if not success:
        raise RuntimeError("Failed to initialize Database Optimization Manager")

    return manager


async def quick_optimize_all_databases() -> Dict[str, Any]:
    """
    Quick function to optimize all databases with default settings

    Returns:
        Dict with optimization results
    """
    manager = await initialize_database_optimizations()

    try:
        # Apply optimizations
        optimization_results = await manager.apply_all_optimizations()

        # Start monitoring
        await manager.start_monitoring()

        # Get initial metrics
        metrics = await manager.get_comprehensive_metrics()

        return {
            'optimization_results': optimization_results,
            'initial_metrics': metrics,
            'monitoring_active': True
        }

    finally:
        # Note: Don't shutdown here as monitoring should continue
        pass


# Export main classes and functions
__all__ = [
    'DatabaseOptimizationManager',
    'PostgreSQLOptimizer',
    'Neo4jOptimizer',
    'RedisOptimizer',
    'AdvancedConnectionPoolManager',
    'CrossDatabaseIntegration',
    'BackupRecoveryManager',
    'PerformanceAnalyzer',
    'DatabaseTestRunner',
    'initialize_database_optimizations',
    'quick_optimize_all_databases',
    'run_comprehensive_test_suite',
    'validate_database_optimizations'
]