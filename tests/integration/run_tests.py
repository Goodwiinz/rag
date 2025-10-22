#!/usr/bin/env python3
"""
Integration Test Runner for Knowledge Graph Analytics Dashboard

Comprehensive test runner with environment setup, health checks, and detailed reporting.
"""

import os
import sys
import argparse
import asyncio
import subprocess
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import docker
from docker.errors import DockerException


class IntegrationTestRunner:
    """Comprehensive integration test runner"""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.project_root = project_root
        self.test_dir = Path(__file__).parent
        self.setup_logging()
        self.docker_client = None
        self.containers = {}

    def setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.args.log_level.upper())
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)

    async def setup_environment(self) -> bool:
        """Setup test environment including Docker containers"""
        self.logger.info("Setting up test environment...")

        try:
            # Initialize Docker client
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            self.logger.info("Docker connection established")

            # Setup test containers
            if not await self.setup_docker_containers():
                return False

            # Wait for services to be ready
            if not await self.wait_for_services():
                return False

            # Install dependencies
            if not await self.install_dependencies():
                return False

            self.logger.info("Test environment setup completed successfully")
            return True

        except DockerException as e:
            self.logger.error(f"Docker setup failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Environment setup failed: {e}")
            return False

    async def setup_docker_containers(self) -> bool:
        """Setup and start Docker containers"""
        self.logger.info("Starting Docker containers...")

        try:
            # PostgreSQL container
            postgres_container = self.docker_client.containers.run(
                "postgres:15",
                name="test_postgres_analytics",
                environment={
                    "POSTGRES_DB": "test_analytics",
                    "POSTGRES_USER": "test_user",
                    "POSTGRES_PASSWORD": "test_password",
                    "POSTGRES_INITDB_ARGS": "--encoding=UTF-8"
                },
                ports={"5432/tcp": ("127.0.0.1", 5433)},
                volumes={
                    str(self.project_root / "database/migrations"): {
                        "bind": "/docker-entrypoint-initdb.d",
                        "mode": "ro"
                    }
                },
                detach=True,
                remove=True
            )
            self.containers["postgres"] = postgres_container
            self.logger.info("PostgreSQL container started")

            # Redis container
            redis_container = self.docker_client.containers.run(
                "redis:7-alpine",
                name="test_redis_analytics",
                ports={"6379/tcp": ("127.0.0.1", 6380)},
                detach=True,
                remove=True
            )
            self.containers["redis"] = redis_container
            self.logger.info("Redis container started")

            return True

        except Exception as e:
            self.logger.error(f"Failed to start containers: {e}")
            await self.cleanup_containers()
            return False

    async def wait_for_services(self, timeout: int = 60) -> bool:
        """Wait for services to be ready"""
        self.logger.info("Waiting for services to be ready...")

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Check PostgreSQL
                postgres_ready = await self.check_postgres_health()
                if postgres_ready:
                    self.logger.info("PostgreSQL is ready")

                # Check Redis
                redis_ready = await self.check_redis_health()
                if redis_ready:
                    self.logger.info("Redis is ready")

                if postgres_ready and redis_ready:
                    return True

                await asyncio.sleep(2)

            except Exception as e:
                self.logger.debug(f"Health check failed: {e}")
                await asyncio.sleep(2)

        self.logger.error("Services failed to become ready within timeout")
        return False

    async def check_postgres_health(self) -> bool:
        """Check PostgreSQL health"""
        try:
            import asyncpg
            conn = await asyncpg.connect(
                host="localhost",
                port=5433,
                user="test_user",
                password="test_password",
                database="test_analytics",
                timeout=5
            )
            await conn.execute("SELECT 1")
            await conn.close()
            return True
        except Exception:
            return False

    async def check_redis_health(self) -> bool:
        """Check Redis health"""
        try:
            import aioredis
            redis = aioredis.from_url("redis://localhost:6380/0")
            await redis.ping()
            await redis.close()
            return True
        except Exception:
            return False

    async def install_dependencies(self) -> bool:
        """Install test dependencies"""
        self.logger.info("Installing dependencies...")

        try:
            # Python dependencies
            requirements_file = self.test_dir / "requirements.txt"
            if requirements_file.exists():
                cmd = [
                    sys.executable, "-m", "pip", "install",
                    "-r", str(requirements_file)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    self.logger.error(f"Failed to install Python dependencies: {result.stderr}")
                    return False
                self.logger.info("Python dependencies installed")

            # Node.js dependencies (if frontend tests are needed)
            frontend_dir = self.project_root / "frontend"
            if frontend_dir.exists() and (frontend_dir / "package.json").exists():
                os.chdir(frontend_dir)
                result = subprocess.run(
                    ["npm", "install"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    self.logger.warning(f"Frontend dependencies installation failed: {result.stderr}")
                else:
                    self.logger.info("Frontend dependencies installed")

            return True

        except Exception as e:
            self.logger.error(f"Dependency installation failed: {e}")
            return False

    async def run_tests(self) -> Tuple[int, Dict]:
        """Run integration tests"""
        self.logger.info("Starting integration tests...")

        # Build pytest command
        pytest_args = self.build_pytest_args()

        # Run tests
        start_time = time.time()
        exit_code = pytest.main(pytest_args)
        duration = time.time() - start_time

        # Generate report
        report = await self.generate_test_report(exit_code, duration)

        return exit_code, report

    def build_pytest_args(self) -> List[str]:
        """Build pytest arguments"""
        args = [
            str(self.test_dir),
            "-v",
            f"--junitxml={self.test_dir}/test-results.xml",
            f"--html={self.test_dir}/test-report.html",
            "--self-contained-html",
        ]

        # Add markers
        if self.args.markers:
            args.extend(["-m", self.args.markers])

        # Add coverage
        if self.args.coverage:
            args.extend([
                "--cov=src",
                "--cov-report=html",
                "--cov-report=xml",
                "--cov-report=term-missing",
                f"--cov-fail-under={self.args.coverage_threshold}"
            ])

        # Add parallel execution
        if self.args.parallel:
            args.extend(["-n", str(self.args.parallel)])

        # Add specific test files
        if self.args.tests:
            args.extend(self.args.tests)

        # Add verbose output
        if self.args.verbose:
            args.append("-s")

        # Add timeout
        args.extend(["--timeout", str(self.args.timeout)])

        return args

    async def generate_test_report(self, exit_code: int, duration: float) -> Dict:
        """Generate comprehensive test report"""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "exit_code": exit_code,
            "duration_seconds": duration,
            "success": exit_code == 0,
            "environment": {
                "python_version": sys.version,
                "platform": sys.platform,
                "docker_containers": list(self.containers.keys())
            }
        }

        # Save report
        report_file = self.test_dir / "test-report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        self.logger.info(f"Test report saved to {report_file}")
        return report

    async def cleanup_containers(self):
        """Cleanup Docker containers"""
        self.logger.info("Cleaning up containers...")

        for name, container in self.containers.items():
            try:
                container.stop()
                container.remove()
                self.logger.info(f"Cleaned up {name} container")
            except Exception as e:
                self.logger.warning(f"Failed to cleanup {name} container: {e}")

        self.containers.clear()

    async def cleanup(self):
        """Cleanup resources"""
        await self.cleanup_containers()


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Integration Test Runner for Knowledge Graph Analytics Dashboard"
    )

    # Test selection
    parser.add_argument(
        "--markers", "-m",
        help="Pytest markers to run (e.g., 'api_contract or performance')"
    )
    parser.add_argument(
        "--tests",
        nargs="*",
        help="Specific test files to run"
    )

    # Execution options
    parser.add_argument(
        "--parallel", "-n",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Test timeout in seconds (default: 300)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    # Coverage options
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    parser.add_argument(
        "--coverage-threshold",
        type=int,
        default=80,
        help="Coverage threshold percentage (default: 80)"
    )

    # Environment options
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip environment setup"
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip cleanup after tests"
    )

    # Logging options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )

    # Quick test options
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick smoke tests only"
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run smoke tests"
    )

    return parser.parse_args()


async def main():
    """Main entry point"""
    args = parse_arguments()
    runner = IntegrationTestRunner(args)

    try:
        # Handle quick test options
        if args.quick:
            args.markers = "smoke"
            args.timeout = 60
        elif args.smoke:
            args.markers = "smoke"

        # Setup environment
        if not args.skip_setup:
            if not await runner.setup_environment():
                runner.logger.error("Environment setup failed")
                return 1

        # Run tests
        exit_code, report = await runner.run_tests()

        # Display results
        if report["success"]:
            runner.logger.info("✅ All tests passed!")
        else:
            runner.logger.error("❌ Some tests failed")

        runner.logger.info(f"Test duration: {report['duration_seconds']:.2f} seconds")

        return exit_code

    except KeyboardInterrupt:
        runner.logger.info("Tests interrupted by user")
        return 130
    except Exception as e:
        runner.logger.error(f"Test execution failed: {e}")
        return 1
    finally:
        # Cleanup
        if not args.no_cleanup:
            await runner.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)