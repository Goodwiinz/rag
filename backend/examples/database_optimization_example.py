#!/usr/bin/env python3
"""
Database Optimization Example for Multimodal Enterprise RAG System

This script demonstrates how to use the comprehensive database optimization framework
to optimize, monitor, and maintain all databases in production.

Usage:
    python database_optimization_example.py

This example will:
1. Initialize all database optimizers
2. Apply production optimizations
3. Start continuous monitoring
4. Run comprehensive tests
5. Generate performance reports
6. Setup backup procedures
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database_optimizations import (
    DatabaseOptimizationManager,
    initialize_database_optimizations,
    quick_optimize_all_databases
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('database_optimization.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class DatabaseOptimizationExample:
    """Example class demonstrating database optimization usage"""

    def __init__(self):
        self.manager: DatabaseOptimizationManager = None
        self.results = {}

    async def run_complete_optimization(self):
        """Run the complete database optimization workflow"""
        try:
            logger.info("="*80)
            logger.info("STARTING DATABASE OPTIMIZATION WORKFLOW")
            logger.info("="*80)

            # Step 1: Initialize the optimization manager
            await self._step_initialize()

            # Step 2: Apply all optimizations
            await self._step_apply_optimizations()

            # Step 3: Start monitoring
            await self._step_start_monitoring()

            # Step 4: Run comprehensive tests
            await self._step_run_tests()

            # Step 5: Generate performance report
            await self._step_generate_report()

            # Step 6: Setup backup procedures
            await self._step_setup_backups()

            # Step 7: Demonstrate real-time monitoring
            await self._step_monitoring_demo()

            logger.info("="*80)
            logger.info("DATABASE OPTIMIZATION WORKFLOW COMPLETED")
            logger.info("="*80)

            return self.results

        except Exception as e:
            logger.error(f"Optimization workflow failed: {e}")
            raise

        finally:
            # Cleanup
            if self.manager:
                await self.manager.shutdown()

    async def _step_initialize(self):
        """Step 1: Initialize the optimization manager"""
        logger.info("\n🔧 STEP 1: Initializing Database Optimization Manager")

        start_time = datetime.utcnow()

        # Custom configuration (optional)
        config = {
            'postgresql': {
                'host': 'localhost',
                'port': 5432,
                'user': 'raguser',
                'password': 'REDACTED',
                'database': 'ragdb',
                'pool_size': 50,
                'optimization_level': 'production'
            },
            'neo4j': {
                'uri': 'bolt://localhost:7687',
                'user': 'neo4j',
                'password': 'REDACTED',
                'database': 'neo4j',
                'max_connection_pool_size': 50,
                'optimization_level': 'production'
            },
            'redis': {
                'host': 'localhost',
                'port': 6379,
                'password': 'REDACTED',
                'database': 0,
                'max_connections': 100,
                'optimization_level': 'production'
            },
            'qdrant': {
                'url': 'http://localhost:6333'
            }
        }

        # Initialize the manager
        self.manager = await initialize_database_optimizations(config)

        initialization_time = (datetime.utcnow() - start_time).total_seconds()
        self.results['initialization'] = {
            'success': True,
            'duration_seconds': initialization_time,
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info(f"✅ Initialization completed in {initialization_time:.2f} seconds")

    async def _step_apply_optimizations(self):
        """Step 2: Apply all database optimizations"""
        logger.info("\n⚡ STEP 2: Applying Database Optimizations")

        start_time = datetime.utcnow()

        # Apply optimizations to all databases
        optimization_results = await self.manager.apply_all_optimizations()

        optimization_time = (datetime.utcnow() - start_time).total_seconds()
        self.results['optimizations'] = {
            **optimization_results,
            'duration_seconds': optimization_time
        }

        # Log results
        if optimization_results['success']:
            logger.info(f"✅ All optimizations applied successfully in {optimization_time:.2f} seconds")
            for db_type, result in optimization_results['results'].items():
                if result.get('success', False):
                    logger.info(f"  ✅ {db_type}: Optimized successfully")
                else:
                    logger.warning(f"  ⚠️  {db_type}: {result.get('error', 'Unknown error')}")
        else:
            logger.error(f"❌ Some optimizations failed: {optimization_results.get('errors', [])}")

    async def _step_start_monitoring(self):
        """Step 3: Start continuous monitoring"""
        logger.info("\n📊 STEP 3: Starting Performance Monitoring")

        # Start monitoring with 30-second intervals
        monitoring_started = await self.manager.start_monitoring(monitoring_interval_seconds=30)

        self.results['monitoring'] = {
            'started': monitoring_started,
            'interval_seconds': 30,
            'timestamp': datetime.utcnow().isoformat()
        }

        if monitoring_started:
            logger.info("✅ Performance monitoring started successfully")
            logger.info("   - Monitoring interval: 30 seconds")
            logger.info("   - Automatic alerting enabled")
            logger.info("   - Performance analysis active")
        else:
            logger.error("❌ Failed to start performance monitoring")

    async def _step_run_tests(self):
        """Step 4: Run comprehensive tests"""
        logger.info("\n🧪 STEP 4: Running Comprehensive Tests")

        start_time = datetime.utcnow()

        # Run comprehensive test suite
        test_results = await self.manager.run_comprehensive_tests()

        test_time = (datetime.utcnow() - start_time).total_seconds()
        self.results['tests'] = {
            **test_results,
            'duration_seconds': test_time
        }

        # Log test results
        if test_results.get('test_results', {}).get('overall_success', False):
            logger.info(f"✅ All tests passed in {test_time:.2f} seconds")
            test_summary = test_results.get('test_results', {})
            logger.info(f"   - Total tests: {test_summary.get('total_tests', 0)}")
            logger.info(f"   - Passed: {test_summary.get('passed_tests', 0)}")
            logger.info(f"   - Failed: {test_summary.get('failed_tests', 0)}")
        else:
            logger.error("❌ Some tests failed")
            failed_tests = test_results.get('test_results', {}).get('failed_tests', [])
            for failed_test in failed_tests[:3]:  # Show first 3 failures
                logger.error(f"   ❌ {failed_test.get('test_name', 'Unknown')}: {failed_test.get('error_message', 'No error message')}")

    async def _step_generate_report(self):
        """Step 5: Generate comprehensive performance report"""
        logger.info("\n📈 STEP 5: Generating Performance Report")

        # Get comprehensive metrics
        metrics = await self.manager.get_comprehensive_metrics()

        self.results['performance_report'] = {
            'metrics': metrics,
            'timestamp': datetime.utcnow().isoformat()
        }

        # Save detailed report to file
        report_file = f"database_performance_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)

        logger.info("✅ Performance report generated")
        logger.info(f"   - Report saved to: {report_file}")

        # Log key metrics
        if 'databases' in metrics:
            for db_type, db_metrics in metrics['databases'].items():
                if 'error' not in db_metrics:
                    logger.info(f"   📊 {db_type.title()}: Connected and healthy")
                else:
                    logger.warning(f"   ⚠️  {db_type.title()}: {db_metrics['error']}")

        if 'alerts' in metrics and metrics['alerts']:
            logger.info(f"   🚨 Active alerts: {len(metrics['alerts'])}")
            for alert in metrics['alerts'][:3]:
                logger.info(f"      - {alert['severity'].upper()}: {alert['description']}")

        if 'recommendations' in metrics and metrics['recommendations']:
            logger.info(f"   💡 Optimization recommendations: {len(metrics['recommendations'])}")
            for rec in metrics['recommendations'][:3]:
                logger.info(f"      - Priority {rec['priority']}: {rec['description']}")

    async def _step_setup_backups(self):
        """Step 6: Setup backup procedures"""
        logger.info("\n💾 STEP 6: Setting Up Backup Procedures")

        start_time = datetime.utcnow()

        # Create a full backup
        backup_results = await self.manager.create_backup('full')

        backup_time = (datetime.utcnow() - start_time).total_seconds()
        self.results['backup'] = {
            **backup_results,
            'duration_seconds': backup_time
        }

        if backup_results.get('success', False):
            logger.info(f"✅ Backup procedures setup completed in {backup_time:.2f} seconds")
            backup_summary = backup_results.get('databases', {})
            for db_type, db_backup in backup_summary.items():
                if db_backup.get('success', False):
                    logger.info(f"   ✅ {db_type}: Backup created ({db_backup.get('file_size_mb', 0):.1f} MB)")
                else:
                    logger.warning(f"   ⚠️  {db_type}: Backup failed - {db_backup.get('error', 'Unknown error')}")
        else:
            logger.error(f"❌ Backup setup failed: {backup_results.get('error', 'Unknown error')}")

    async def _step_monitoring_demo(self):
        """Step 7: Demonstrate real-time monitoring"""
        logger.info("\n🔍 STEP 7: Real-time Monitoring Demo")

        # Monitor for 2 minutes to show real-time data
        logger.info("📡 Collecting real-time metrics for 2 minutes...")

        monitoring_duration = 120  # 2 minutes
        start_time = datetime.utcnow()

        while (datetime.utcnow() - start_time).total_seconds() < monitoring_duration:
            await asyncio.sleep(30)  # Wait 30 seconds

            # Get current metrics
            current_metrics = await self.manager.get_comprehensive_metrics()
            elapsed_time = (datetime.utcnow() - start_time).total_seconds()

            logger.info(f"📊 Metrics at {elapsed_time:.0f}s:")

            # Show database status
            if 'databases' in current_metrics:
                for db_type, db_metrics in current_metrics['databases'].items():
                    if 'error' not in db_metrics:
                        # Extract some key metrics
                        if db_type == 'redis' and 'performance' in db_metrics:
                            hit_rate = db_metrics['performance'].get('hit_rate', 0)
                            ops_per_sec = db_metrics['performance'].get('instantaneous_ops_per_sec', 0)
                            logger.info(f"   📊 {db_type.title()}: Hit rate {hit_rate:.1f}%, {ops_per_sec:.0f} ops/sec")
                        else:
                            logger.info(f"   📊 {db_type.title()}: ✅ Healthy")
                    else:
                        logger.warning(f"   ⚠️  {db_type.title()}: {db_metrics['error']}")

            # Show alerts and recommendations
            alerts = current_metrics.get('alerts', [])
            if alerts:
                logger.info(f"   🚨 Active alerts: {len(alerts)}")
                for alert in alerts[:2]:
                    logger.info(f"      - {alert['severity'].upper()}: {alert['description']}")

            recommendations = current_metrics.get('recommendations', [])
            if recommendations:
                logger.info(f"   💡 Recommendations: {len(recommendations)}")
                for rec in recommendations[:2]:
                    logger.info(f"      - Priority {rec['priority']}: {rec['description']}")

        logger.info("✅ Real-time monitoring demo completed")

    def save_results(self):
        """Save all results to a comprehensive report"""
        results_file = f"database_optimization_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        logger.info(f"\n📄 Complete results saved to: {results_file}")
        return results_file


async def main():
    """Main function to run the database optimization example"""
    try:
        example = DatabaseOptimizationExample()
        results = await example.run_complete_optimization()
        results_file = example.save_results()

        # Print summary
        print("\n" + "="*80)
        print("🎉 DATABASE OPTIMIZATION WORKFLOW SUMMARY")
        print("="*80)

        if results.get('initialization', {}).get('success', False):
            print("✅ Initialization: SUCCESS")
        if results.get('optimizations', {}).get('success', False):
            print("✅ Optimizations: SUCCESS")
        if results.get('monitoring', {}).get('started', False):
            print("✅ Monitoring: ACTIVE")
        if results.get('tests', {}).get('test_results', {}).get('overall_success', False):
            print("✅ Tests: PASSED")
        if results.get('backup', {}).get('success', False):
            print("✅ Backup: COMPLETED")

        print(f"\n📄 Detailed report: {results_file}")
        print("📊 Monitoring continues to run in the background")
        print("\n💡 Next steps:")
        print("   1. Review the performance report for optimization opportunities")
        print("   2. Monitor alerts and recommendations from the performance analyzer")
        print("   3. Schedule regular backups and cleanup procedures")
        print("   4. Consider implementing automated scaling based on metrics")

        return 0

    except KeyboardInterrupt:
        logger.info("\n⚠️ Optimization workflow interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"\n❌ Optimization workflow failed: {e}")
        return 1


if __name__ == "__main__":
    # Run the example
    exit_code = asyncio.run(main())
    sys.exit(exit_code)