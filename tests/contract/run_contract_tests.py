#!/usr/bin/env python3
"""
Contract Test Runner for Multimodal Enterprise RAG System Evaluation Platform
Comprehensive script to run all contract tests with detailed reporting
"""

import os
import sys
import subprocess
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class ContractTestRunner:
    """Runner for contract tests with reporting capabilities"""

    def __init__(self):
        self.test_results = {}
        self.start_time = datetime.now(timezone.utc)
        self.end_time = None

    def run_tests(self, test_type: str = "all", verbose: bool = False, html_report: bool = True):
        """Run contract tests and generate reports"""

        print("🚀 Multimodal Enterprise RAG System - Contract Test Runner")
        print("=" * 70)
        print(f"📅 Started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"🧪 Test type: {test_type}")
        print(f"📊 Verbose: {verbose}")
        print(f"📄 HTML Report: {html_report}")
        print()

        # Define test configurations
        test_configurations = {
            "all": {
                "description": "All contract tests",
                "paths": [
                    "tests/contract/evaluation/",
                    "tests/contract/auth/",
                    "tests/contract/load/"
                ],
                "markers": [
                    "contract",
                    "evaluation_contract",
                    "auth_contract",
                    "load_test",
                    "cors_test",
                    "error_contract"
                ]
            },
            "evaluation": {
                "description": "Evaluation API contract tests only",
                "paths": ["tests/contract/evaluation/"],
                "markers": [
                    "contract",
                    "evaluation_contract"
                ]
            },
            "auth": {
                "description": "Authentication contract tests only",
                "paths": ["tests/contract/auth/"],
                "markers": [
                    "contract",
                    "auth_contract"
                ]
            },
            "load": {
                "description": "Load and performance tests only",
                "paths": ["tests/contract/load/"],
                "markers": [
                    "load_test"
                ]
            },
            "fast": {
                "description": "Fast contract tests (exclude load tests)",
                "paths": [
                    "tests/contract/evaluation/",
                    "tests/contract/auth/"
                ],
                "markers": [
                    "contract",
                    "evaluation_contract",
                    "auth_contract",
                    "error_contract"
                ],
                "exclude_markers": ["load_test", "slow"]
            }
        }

        config = test_configurations.get(test_type, test_configurations["all"])

        print(f"🎯 Running: {config['description']}")
        print(f"📂 Test paths: {', '.join(config['paths'])}")
        print(f"🏷️  Markers: {', '.join(config['markers'])}")
        print()

        # Build pytest command
        cmd = [
            "python", "-m", "pytest",
            "-v" if verbose else "-q",
            "--tb=short",  # Short traceback format
            "--strict-markers",  # Strict marker checking
            "--disable-warnings",
            "-x" if not verbose else "",  # Stop on first failure if not verbose
        ]

        # Add test paths
        for path in config["paths"]:
            if Path(path).exists():
                cmd.append(path)

        # Add markers
        if "markers" in config:
            marker_expr = " or ".join(config["markers"])
            cmd.extend(["-m", marker_expr])

        # Add exclude markers
        if "exclude_markers" in config:
            exclude_expr = " and ".join([f"not {m}" for m in config["exclude_markers"]])
            if "markers" in config:
                cmd[-1] += f" and {exclude_expr}"
            else:
                cmd.extend(["-m", exclude_expr])

        # Add HTML report if requested
        if html_report:
            report_dir = Path("test_reports")
            report_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_file = report_dir / f"contract_test_report_{timestamp}.html"

            cmd.extend([
                "--html=str(str(html_file))",
                "--self-contained-html"
            ])

        # Add JUnit XML report
        junit_dir = Path("test_reports")
        junit_dir.mkdir(exist_ok=True)
        junit_file = junit_dir / f"contract_test_junit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
        cmd.extend([f"--junitxml={junit_file}"])

        # Add coverage if requested
        if os.getenv("COVERAGE", "false").lower() == "true":
            cmd.extend([
                "--cov=src",
                "--cov-report=html:test_reports/coverage",
                "--cov-report=term-missing"
            ])

        # Filter out empty strings
        cmd = [arg for arg in cmd if arg]

        print(f"🔧 Command: {' '.join(cmd)}")
        print()

        # Run tests
        try:
            result = subprocess.run(
                cmd,
                cwd=str(project_root),
                capture_output=False,
                text=True
            )

            self.end_time = datetime.now(timezone.utc)
            duration = (self.end_time - self.start_time).total_seconds()

            # Store results
            self.test_results = {
                "exit_code": result.returncode,
                "duration_seconds": duration,
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "test_type": test_type,
                "config": config,
                "html_report": str(html_file) if html_report else None,
                "junit_report": str(junit_file)
            }

            # Print summary
            self.print_summary()

            return result.returncode

        except KeyboardInterrupt:
            print("\n⚠️  Tests interrupted by user")
            return 1
        except Exception as e:
            print(f"\n❌ Error running tests: {e}")
            return 1

    def print_summary(self):
        """Print test execution summary"""
        duration = self.test_results["duration_seconds"]
        exit_code = self.test_results["exit_code"]

        print()
        print("=" * 70)
        print("📊 CONTRACT TEST EXECUTION SUMMARY")
        print("=" * 70)
        print(f"📅 Duration: {duration:.2f} seconds")
        print(f"🎯 Test Type: {self.test_results['test_type']}")
        print(f"✅ Status: {'PASSED' if exit_code == 0 else 'FAILED'}")
        print(f"🏁 Finished at: {self.end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        if self.test_results["html_report"]:
            print(f"📄 HTML Report: {self.test_results['html_report']}")

        if self.test_results["junit_report"]:
            print(f"📋 JUnit Report: {self.test_results['junit_report']}")

        print()

        if exit_code == 0:
            print("🎉 All contract tests passed! The API contracts are stable and reliable.")
        else:
            print("❌ Some contract tests failed. Please review the failures and fix the issues.")
            print("🔧 Check the HTML report for detailed failure information.")

        # Performance recommendations
        if self.test_results["test_type"] in ["all", "load"] and duration > 300:
            print()
            print("⚡ Performance Recommendations:")
            print("   - Consider running specific test types for faster feedback")
            print("   - Use 'evaluation' or 'auth' for focused testing")
            print("   - Use 'fast' to exclude load tests during development")

    def save_results(self, filename: str = None):
        """Save test results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_reports/contract_test_results_{timestamp}.json"

        results_dir = Path("test_reports")
        results_dir.mkdir(exist_ok=True)

        with open(results_dir / filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)

        print(f"💾 Test results saved to: {results_dir / filename}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Contract Test Runner for Multimodal Enterprise RAG System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run all contract tests
  %(prog)s --type evaluation         # Run only evaluation API tests
  %(prog)s --type fast               # Run fast tests (no load tests)
  %(prog)s --verbose                 # Run with verbose output
  %(prog)s --no-html                 # Skip HTML report generation
  %(prog)s --save-results            # Save results to JSON
        """
    )

    parser.add_argument(
        "--type", "-t",
        choices=["all", "evaluation", "auth", "load", "fast"],
        default="all",
        help="Type of tests to run (default: all)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Skip HTML report generation"
    )

    parser.add_argument(
        "--save-results",
        action="store_true",
        help="Save test results to JSON file"
    )

    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )

    args = parser.parse_args()

    # Set coverage environment variable
    if args.coverage:
        os.environ["COVERAGE"] = "true"

    # Run tests
    runner = ContractTestRunner()
    exit_code = runner.run_tests(
        test_type=args.type,
        verbose=args.verbose,
        html_report=not args.no_html
    )

    # Save results if requested
    if args.save_results:
        runner.save_results()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())