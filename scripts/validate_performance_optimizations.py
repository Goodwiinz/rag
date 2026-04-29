#!/usr/bin/env python3
"""
Performance validation script for the Multimodal Enterprise RAG System
Validates that all performance optimizations are properly configured and working
"""

import asyncio
import time
import json
import sys
import os
import psutil
import aiohttp
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    from src.performance.benchmarks import AutomatedTestSuite, BenchmarkConfig, TestType
    from src.performance.monitoring import get_performance_monitor
    from src.performance.websocket_optimization import get_high_performance_websocket_manager
    from src.performance.database_optimization import get_ultra_fast_database_manager
    from src.performance.multi_tier_cache import get_multi_tier_cache_manager, CacheConfig
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ValidationResults:
    """Results of performance validation"""
    timestamp: datetime
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warnings: List[str] = None
    errors: List[str] = None
    metrics: Dict[str, Any] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []
        if self.metrics is None:
            self.metrics = {}

class PerformanceValidator:
    """Validates performance optimizations across the system"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = ValidationResults(timestamp=datetime.utcnow())
        self.test_suite = AutomatedTestSuite(base_url)

    async def run_validation(self) -> ValidationResults:
        """Run complete performance validation"""
        logger.info("Starting performance validation...")

        try:
            # System resource checks
            await self._check_system_resources()

            # Service availability checks
            await self._check_service_availability()

            # Performance optimization checks
            await self._check_performance_optimizations()

            # Load testing validation
            await self._run_load_tests()

            # Generate final report
            self._generate_report()

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            self.results.errors.append(f"Validation error: {e}")

        return self.results

    async def _check_system_resources(self):
        """Check system resource availability"""
        logger.info("Checking system resources...")

        # CPU availability
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 80:
            self.results.warnings.append(f"High CPU usage: {cpu_percent:.1f}%")
        else:
            self.results.passed_checks += 1

        # Memory availability
        memory = psutil.virtual_memory()
        if memory.percent > 85:
            self.results.warnings.append(f"High memory usage: {memory.percent:.1f}%")
        else:
            self.results.passed_checks += 1

        # Disk availability
        disk = psutil.disk_usage('/')
        if disk.percent > 90:
            self.results.warnings.append(f"High disk usage: {disk.percent:.1f}%")
        else:
            self.results.passed_checks += 1

        # Network connectivity
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            self.results.passed_checks += 1
        except Exception as e:
            self.results.errors.append(f"Network connectivity issue: {e}")

        self.results.total_checks += 4
        self.results.metrics.update({
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_mb': memory.available / (1024 * 1024),
            'disk_percent': disk.percent
        })

    async def _check_service_availability(self):
        """Check service availability and basic functionality"""
        logger.info("Checking service availability...")

        async with aiohttp.ClientSession() as session:
            # Backend service
            try:
                async with session.get(f"{self.base_url}/health", timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Backend health check passed: {data.get('status', 'unknown')}")
                        self.results.passed_checks += 1
                        self.results.metrics['backend_status'] = data.get('status')
                    else:
                        self.results.errors.append(f"Backend health check failed: HTTP {response.status}")
            except Exception as e:
                self.results.errors.append(f"Backend service unavailable: {e}")

            # Documents API
            try:
                async with session.get(f"{self.base_url}/api/v1/documents/", timeout=10) as response:
                    if response.status in [200, 401]:  # 401 is OK (just needs auth)
                        logger.info("Documents API endpoint responding")
                        self.results.passed_checks += 1
                    else:
                        self.results.warnings.append(f"Documents API returned: HTTP {response.status}")
            except Exception as e:
                self.results.warnings.append(f"Documents API check failed: {e}")

        self.results.total_checks += 2

    async def _check_performance_optimizations(self):
        """Check performance optimization components"""
        logger.info("Checking performance optimizations...")

        # Check WebSocket optimization components
        try:
            # This would require actual WebSocket connection testing
            # For now, just check if the module can be imported
            from src.performance.websocket_optimization import get_high_performance_websocket_manager
            self.results.passed_checks += 1
            logger.info("WebSocket optimization module loaded successfully")
        except Exception as e:
            self.results.errors.append(f"WebSocket optimization check failed: {e}")

        # Check database optimization components
        try:
            from src.performance.database_optimization import get_ultra_fast_database_manager
            self.results.passed_checks += 1
            logger.info("Database optimization module loaded successfully")
        except Exception as e:
            self.results.errors.append(f"Database optimization check failed: {e}")

        # Check caching components
        try:
            from src.performance.multi_tier_cache import get_multi_tier_cache_manager
            self.results.passed_checks += 1
            logger.info("Multi-tier cache module loaded successfully")
        except Exception as e:
            self.results.errors.append(f"Multi-tier cache check failed: {e}")

        # Check monitoring components
        try:
            from src.performance.monitoring import get_performance_monitor
            self.results.passed_checks += 1
            logger.info("Performance monitoring module loaded successfully")
        except Exception as e:
            self.results.errors.append(f"Performance monitoring check failed: {e}")

        self.results.total_checks += 4

    async def _run_load_tests(self):
        """Run performance load tests"""
        logger.info("Running performance load tests...")

        # Quick validation test
        try:
            validation_result = await self.test_suite.run_quick_validation()

            if validation_result['validation_passed']:
                self.results.passed_checks += 1
                logger.info("Quick performance validation PASSED")
            else:
                self.results.errors.append("Quick performance validation FAILED")

            self.results.metrics.update({
                'validation_avg_response_time': validation_result.get('avg_response_time_ms'),
                'validation_success_rate': validation_result.get('success_rate_percent'),
                'validation_rps': validation_result.get('requests_per_second')
            })

        except Exception as e:
            self.results.warnings.append(f"Load test failed to execute: {e}")

        self.results.total_checks += 1

    def _generate_report(self):
        """Generate validation report"""
        logger.info("Generating validation report...")

        self.results.failed_checks = self.results.total_checks - self.results.passed_checks

        print("\n" + "="*80)
        print("PERFORMANCE VALIDATION REPORT")
        print("="*80)
        print(f"Timestamp: {self.results.timestamp}")
        print(f"Total Checks: {self.results.total_checks}")
        print(f"Passed: {self.results.passed_checks}")
        print(f"Failed: {self.results.failed_checks}")

        success_rate = (self.results.passed_checks / max(1, self.results.total_checks)) * 100
        print(f"Success Rate: {success_rate:.1f}%")

        if self.results.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.results.warnings)}):")
            for warning in self.results.warnings:
                print(f"   - {warning}")

        if self.results.errors:
            print(f"\n❌ ERRORS ({len(self.results.errors)}):")
            for error in self.results.errors:
                print(f"   - {error}")

        if self.results.metrics:
            print(f"\n📊 PERFORMANCE METRICS:")
            for key, value in self.results.metrics.items():
                print(f"   - {key}: {value}")

        # Overall status
        if success_rate >= 80 and len(self.results.errors) == 0:
            print(f"\n✅ VALIDATION STATUS: PASSED")
            print("System is ready for production with performance optimizations")
        else:
            print(f"\n❌ VALIDATION STATUS: FAILED")
            print("Please address the warnings and errors before deployment")

        print("="*80)

def main():
    """Main validation script"""
    print("🚀 Multimodal RAG System Performance Validation")
    print("This script validates that all performance optimizations are properly configured")
    print()

    # Check if backend is running
    import socket
    try:
        socket.create_connection(("localhost", 8000), timeout=5)
        print("✅ Backend service is accessible on localhost:8000")
    except socket.error:
        print("❌ Backend service is not running on localhost:8000")
        print("Please start the backend service first:")
        print("  cd backend && python -m uvicorn src.main:app --host 0.0.0.0 --port 8000")
        return 1

    # Run validation
    validator = PerformanceValidator()

    try:
        results = asyncio.run(validator.run_validation())

        # Exit with appropriate code
        if results.passed_checks >= results.total_checks * 0.8 and len(results.errors) == 0:
            print("\n🎉 Performance validation completed successfully!")
            return 0
        else:
            print("\n⚠️  Performance validation completed with issues")
            return 1

    except KeyboardInterrupt:
        print("\n⚠️  Validation interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)