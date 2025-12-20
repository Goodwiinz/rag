#!/usr/bin/env python3
"""
Comprehensive Test Suite Runner for Multi-Agent Search System
Provides intelligent test execution with environment setup and reporting
"""

import os
import sys
import argparse
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Color codes for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

@dataclass
class TestSuite:
    name: str
    path: str
    markers: List[str]
    description: str
    parallel_safe: bool = True
    requires_db: bool = True
    requires_external: bool = False

@dataclass
class TestResult:
    suite: str
    passed: int
    failed: int
    skipped: int
    duration: float
    coverage: Optional[float] = None

class TestRunner:
    """Advanced test runner with intelligent execution"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.results: List[TestResult] = []
        self.start_time = datetime.now()

    # Define test suites
    TEST_SUITES = [
        TestSuite(
            name="Unit Tests",
            path="tests/unit",
            markers=["unit"],
            description="Fast unit tests without external dependencies",
            parallel_safe=True,
            requires_db=False,
            requires_external=False
        ),
        TestSuite(
            name="Integration Tests",
            path="tests/integration",
            markers=["integration"],
            description="Tests with database integration",
            parallel_safe=True,
            requires_db=True,
            requires_external=False
        ),
        TestSuite(
            name="Agent Tests",
            path="tests",
            markers=["agent"],
            description="Multi-agent orchestration tests",
            parallel_safe=False,
            requires_db=True,
            requires_external=True
        ),
        TestSuite(
            name="Search Tests",
            path="tests",
            markers=["search"],
            description="Search functionality tests",
            parallel_safe=True,
            requires_db=True,
            requires_external=True
        ),
        TestSuite(
            name="WebSocket Tests",
            path="tests",
            markers=["websocket"],
            description="Real-time WebSocket tests",
            parallel_safe=False,
            requires_db=True,
            requires_external=True
        ),
        TestSuite(
            name="API Tests",
            path="tests/api_contract",
            markers=["api"],
            description="API contract tests",
            parallel_safe=True,
            requires_db=True,
            requires_external=False
        ),
        TestSuite(
            name="Performance Tests",
            path="tests/performance",
            markers=["performance", "slow"],
            description="Performance and load tests",
            parallel_safe=False,
            requires_db=True,
            requires_external=True
        ),
        TestSuite(
            name="Security Tests",
            path="tests",
            markers=["security"],
            description="Security and authorization tests",
            parallel_safe=True,
            requires_db=True,
            requires_external=False
        ),
        TestSuite(
            name="End-to-End Tests",
            path="tests/e2e",
            markers=["e2e"],
            description="Full end-to-end workflow tests",
            parallel_safe=False,
            requires_db=True,
            requires_external=True
        ),
        TestSuite(
            name="All Tests",
            path="tests",
            markers=[],
            description="Run all test suites",
            parallel_safe=True,
            requires_db=True,
            requires_external=True
        )
    ]

    def print_header(self):
        """Print test runner header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}")
        print(f"Multi-Agent Search System - Test Runner")
        print(f"{'='*70}{Colors.END}")
        print(f"\nStarted at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Python version: {sys.version}")
        print(f"Working directory: {self.project_root}\n")

    def setup_environment(self):
        """Setup test environment"""
        print(f"{Colors.BLUE}Setting up test environment...{Colors.END}")

        # Set test environment
        os.environ["ENVIRONMENT"] = "testing"
        os.environ["LOG_LEVEL"] = "INFO"
        os.environ["TESTING"] = "true"

        # Load test environment file if exists
        env_file = self.project_root / ".env.test"
        if env_file.exists():
            print(f"  Loading environment from .env.test")
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        os.environ[key] = value

        print(f"  {Colors.GREEN}✓{Colors.END} Environment configured")

    def verify_dependencies(self):
        """Verify test dependencies"""
        print(f"\n{Colors.BLUE}Verifying dependencies...{Colors.END}")

        # Check pytest
        try:
            import pytest
            version = pytest.__version__
            print(f"  {Colors.GREEN}✓{Colors.END} pytest {version}")
        except ImportError:
            print(f"  {Colors.RED}✗{Colors.END} pytest not installed")
            sys.exit(1)

        # Check optional dependencies
        optional_deps = [
            ("pytest-xdist", "parallel execution"),
            ("pytest-cov", "coverage reporting"),
            ("pytest-asyncio", "async tests"),
            ("pytest-html", "HTML reports"),
            ("pytest-benchmark", "performance tests")
        ]

        for dep, feature in optional_deps:
            try:
                __import__(dep.replace('-', '_'))
                print(f"  {Colors.GREEN}✓{Colors.END} {dep} ({feature})")
            except ImportError:
                print(f"  {Colors.YELLOW}⚠{Colors.END} {dep} ({feature}) - not installed")

    def build_pytest_command(
        self,
        suite: TestSuite,
        coverage: bool = True,
        parallel: bool = True,
        html_report: bool = True
    ) -> List[str]:
        """Build pytest command for a test suite"""
        cmd = ["python", "-m", "pytest"]

        # Add path
        cmd.append(suite.path)

        # Add markers
        if suite.markers:
            for marker in suite.markers:
                cmd.extend(["-m", marker])

        # Add coverage
        if coverage:
            cmd.extend([
                "--cov=src",
                "--cov-report=html:test-reports/htmlcov",
                "--cov-report=xml:test-reports/coverage.xml",
                "--cov-report=term-missing"
            ])

        # Add parallel execution
        if parallel and suite.parallel_safe:
            try:
                import xdist
                cmd.extend(["-n", "auto"])
            except ImportError:
                pass

        # Add HTML report
        if html_report:
            cmd.extend([
                "--html=test-reports/report.html",
                "--self-contained-html"
            ])

        # Add JSON report
        cmd.extend([
            "--json-report",
            "--json-report-file=test-reports/report.json"
        ])

        # Add JUnit XML
        cmd.extend([
            "--junit-xml=test-reports/junit.xml"
        ])

        # Add verbose output
        cmd.append("-v")

        # Add timeout for slow tests
        if "slow" in suite.markers:
            cmd.extend(["--timeout=300"])

        # Filter tests based on requirements
        if not suite.requires_db:
            cmd.extend(["-k", "not database"])

        if suite.requires_external:
            cmd.extend(["-k", "external"])

        return cmd

    def run_suite(self, suite: TestSuite, options: Dict[str, Any]) -> TestResult:
        """Run a single test suite"""
        print(f"\n{Colors.CYAN}Running {suite.name}...{Colors.END}")
        print(f"  {suite.description}")

        cmd = self.build_pytest_command(
            suite,
            coverage=options["coverage"],
            parallel=options["parallel"],
            html_report=options["html_report"]
        )

        # Add extra arguments
        if options["verbose"]:
            cmd.append("-vv")
        if options["stop_on_first"]:
            cmd.append("-x")
        if options["failed_first"]:
            cmd.append("--lf")

        # Print command if very verbose
        if options.get("very_verbose"):
            print(f"  Command: {' '.join(cmd)}")

        # Run tests
        start_time = datetime.now()
        result = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        duration = (datetime.now() - start_time).total_seconds()

        # Parse results
        try:
            # Extract test counts from output
            output = result.stdout + result.stderr
            lines = output.split('\n')

            passed = failed = skipped = 0
            for line in lines:
                if " passed" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "passed" and i > 0:
                            passed += int(parts[i-1])
                elif " failed" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "failed" and i > 0:
                            failed += int(parts[i-1])
                elif " skipped" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "skipped" and i > 0:
                            skipped += int(parts[i-1])

            # Get coverage if available
            coverage = None
            if options["coverage"]:
                try:
                    with open(self.project_root / "test-reports" / "coverage.xml") as f:
                        content = f.read()
                        # Extract coverage percentage
                        import re
                        match = re.search(r'line-rate="([\d.]+)"', content)
                        if match:
                            coverage = float(match.group(1)) * 100
                except:
                    pass

        except Exception as e:
            print(f"  {Colors.YELLOW}Warning: Could not parse results: {e}{Colors.END}")
            passed = failed = skipped = 0
            if result.returncode != 0:
                failed = 1

        # Print result summary
        if result.returncode == 0:
            print(f"  {Colors.GREEN}✓{Colors.END} Passed: {passed}, Failed: {failed}, Skipped: {skipped}")
        else:
            print(f"  {Colors.RED}✗{Colors.END} Passed: {passed}, Failed: {failed}, Skipped: {skipped}")

        if duration > 60:
            print(f"  Duration: {duration:.1f}s")

        # Print errors if any
        if failed > 0 and options["verbose"]:
            print(f"\n{Colors.RED}Errors:{Colors.END}")
            print(result.stderr[:1000] + "..." if len(result.stderr) > 1000 else result.stderr)

        return TestResult(
            suite=suite.name,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration=duration,
            coverage=coverage
        )

    def print_results_summary(self):
        """Print comprehensive results summary"""
        total_duration = (datetime.now() - self.start_time).total_seconds()

        total_passed = sum(r.passed for r in self.results)
        total_failed = sum(r.failed for r in self.results)
        total_skipped = sum(r.skipped for r in self.results)
        total_tests = total_passed + total_failed + total_skipped

        print(f"\n{Colors.BOLD}{'='*70}")
        print(f"TEST RESULTS SUMMARY")
        print(f"{'='*70}{Colors.END}")

        # Overall summary
        print(f"\n{Colors.BOLD}Overall:{Colors.END}")
        print(f"  Total Duration: {total_duration:.1f}s")
        print(f"  Total Tests: {total_tests}")
        print(f"  {Colors.GREEN}Passed:{Colors.END} {total_passed}")
        print(f"  {Colors.RED}Failed:{Colors.END} {total_failed}")
        print(f"  {Colors.YELLOW}Skipped:{Colors.END} {total_skipped}")

        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        print(f"  Success Rate: {success_rate:.1f}%")

        # Per-suite summary
        print(f"\n{Colors.BOLD}By Suite:{Colors.END}")
        for result in self.results:
            status_color = Colors.GREEN if result.failed == 0 else Colors.RED
            status = "✓" if result.failed == 0 else "✗"
            coverage_str = f", Coverage: {result.coverage:.1f}%" if result.coverage else ""
            print(f"  {status_color}{status}{Colors.END} {result.suite}: "
                  f"{result.passed} passed, {result.failed} failed, "
                  f"{result.skipped} skipped ({result.duration:.1f}s{coverage_str})")

        # Coverage summary
        coverages = [r.coverage for r in self.results if r.coverage]
        if coverages:
            avg_coverage = sum(coverages) / len(coverages)
            print(f"\n{Colors.BOLD}Coverage Summary:{Colors.END}")
            print(f"  Average Coverage: {avg_coverage:.1f}%")
            print(f"  Max Coverage: {max(coverages):.1f}%")
            print(f"  Min Coverage: {min(coverages):.1f}%")

        # Recommendations
        print(f"\n{Colors.BOLD}Recommendations:{Colors.END}")
        if total_failed > 0:
            print(f"  • Fix {total_failed} failing tests")
            print(f"  • Run: pytest --lf to rerun only failed tests")
        if total_skipped > total_tests * 0.1:
            print(f"  • Investigate why {total_skipped} tests were skipped")
        if success_rate < 90:
            print(f"  • Success rate below 90% - review test failures")
        if any(r.coverage and r.coverage < 70 for r in self.results):
            print(f"  • Some suites have low coverage - add more tests")

        # Report locations
        reports_dir = self.project_root / "test-reports"
        if reports_dir.exists():
            print(f"\n{Colors.BOLD}Reports Generated:{Colors.END}")
            print(f"  HTML Report: {reports_dir / 'report.html'}")
            print(f"  Coverage Report: {reports_dir / 'htmlcov' / 'index.html'}")
            print(f"  JSON Report: {reports_dir / 'report.json'}")
            print(f"  JUnit XML: {reports_dir / 'junit.xml'}")

    def save_results(self):
        """Save results to JSON file"""
        results_data = {
            "timestamp": self.start_time.isoformat(),
            "duration": (datetime.now() - self.start_time).total_seconds(),
            "suites": [asdict(r) for r in self.results],
            "summary": {
                "total_passed": sum(r.passed for r in self.results),
                "total_failed": sum(r.failed for r in self.results),
                "total_skipped": sum(r.skipped for r in self.results),
                "total_tests": sum(r.passed + r.failed + r.skipped for r in self.results)
            }
        }

        reports_dir = self.project_root / "test-reports"
        reports_dir.mkdir(exist_ok=True)

        with open(reports_dir / "results.json", "w") as f:
            json.dump(results_data, f, indent=2)

    def list_suites(self):
        """List available test suites"""
        print(f"\n{Colors.BOLD}Available Test Suites:{Colors.END}\n")

        for i, suite in enumerate(self.TEST_SUITES, 1):
            status = []
            if not suite.parallel_safe:
                status.append("sequential")
            if suite.requires_db:
                status.append("requires db")
            if suite.requires_external:
                status.append("requires external")

            status_str = f" ({', '.join(status)})" if status else ""

            print(f"{i:2d}. {Colors.CYAN}{suite.name}{Colors.END}{status_str}")
            print(f"    {suite.description}")
            print(f"    Path: {suite.path}")
            print(f"    Markers: {', '.join(suite.markers) if suite.markers else 'all'}")
            print()

    def run_tests(self, suites: List[str], options: Dict[str, Any]):
        """Run specified test suites"""
        self.print_header()
        self.setup_environment()
        self.verify_dependencies()

        # Find selected suites
        selected_suites = []
        for suite_name in suites:
            for suite in self.TEST_SUITES:
                if suite.name.lower() == suite_name.lower():
                    selected_suites.append(suite)
                    break
            else:
                print(f"{Colors.YELLOW}Warning: Unknown suite '{suite_name}'{Colors.END}")

        if not selected_suites:
            print(f"{Colors.RED}No valid suites specified{Colors.END}")
            self.list_suites()
            return

        # Create reports directory
        reports_dir = self.project_root / "test-reports"
        reports_dir.mkdir(exist_ok=True)

        # Clean old reports
        for file in reports_dir.glob("*"):
            if file.is_file():
                file.unlink()

        # Run each suite
        for suite in selected_suites:
            result = self.run_suite(suite, options)
            self.results.append(result)

            # Stop on first failure if requested
            if result.failed > 0 and options.get("stop_on_first", False):
                print(f"\n{Colors.YELLOW}Stopping due to failure in {suite.name}{Colors.END}")
                break

        # Print summary and save results
        self.print_results_summary()
        self.save_results()

        # Exit with appropriate code
        if any(r.failed > 0 for r in self.results):
            sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Search System Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py all
  python run_tests.py unit integration
  python run_tests.py agent --parallel --coverage
  python run_tests.py performance --verbose --stop-on-first
  python run_tests.py --list
        """
    )

    parser.add_argument(
        "suites",
        nargs="*",
        default=["all"],
        help="Test suites to run (default: all)"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available test suites"
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="Run tests in parallel where supported"
    )

    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel execution"
    )

    parser.add_argument(
        "--coverage",
        action="store_true",
        default=True,
        help="Generate coverage reports"
    )

    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Skip coverage reporting"
    )

    parser.add_argument(
        "--html-report",
        action="store_true",
        default=True,
        help="Generate HTML report"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    parser.add_argument(
        "--very-verbose", "-vv",
        action="store_true",
        help="Very verbose output"
    )

    parser.add_argument(
        "--stop-on-first", "-x",
        action="store_true",
        help="Stop on first failure"
    )

    parser.add_argument(
        "--failed-first", "-lf",
        action="store_true",
        help="Run failed tests first"
    )

    args = parser.parse_args()

    runner = TestRunner()

    if args.list:
        runner.list_suites()
        return

    # Convert args to options dict
    options = {
        "parallel": args.parallel and not args.no_parallel,
        "coverage": args.coverage and not args.no_coverage,
        "html_report": args.html_report,
        "verbose": args.verbose or args.very_verbose,
        "very_verbose": args.very_verbose,
        "stop_on_first": args.stop_on_first,
        "failed_first": args.failed_first
    }

    runner.run_tests(args.suites, options)


if __name__ == "__main__":
    main()