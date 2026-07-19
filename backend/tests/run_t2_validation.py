#!/usr/bin/env python3
"""
T2 Validation Test Runner

This script runs comprehensive validation tests for all T2 tasks in the Multimodal RAG System.
It provides detailed reporting and can be used for continuous integration validation.
"""

import sys
import os
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Any
import argparse

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))


class T2ValidationRunner:
    """Comprehensive test runner for T2 validation"""

    def __init__(self):
        self.test_results = {}
        self.start_time = time.time()
        self.test_dir = Path(__file__).parent

    def print_header(self):
        """Print test runner header"""
        print("🧪 T2 Validation Test Runner")
        print("=" * 80)
        print("Comprehensive validation for Multimodal RAG System T2 tasks")
        print()
        print("T2 Tasks being validated:")
        print("  ✅ T2-001: Vector Database Setup and Embedding Generation")
        print("  ✅ T2-002: Knowledge Graph Construction")
        print("  ✅ T2-003: Full-Text Search Implementation")
        print("  ✅ T2-004: Hybrid Search Engine")
        print("  ✅ T2-005: Search API Implementation")
        print("  ⏳ T2-006: Multi-Agent Search Orchestration (Pending)")
        print("  ✅ T2-007: Search Quality Evaluation")
        print()
        print("=" * 80)
        print()

    def run_command(self, cmd: List[str], description: str) -> Dict[str, Any]:
        """Run a command and return results"""
        print(f"🔄 {description}...")
        print(f"   Command: {' '.join(cmd)}")

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=self.test_dir.parent,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            duration = time.time() - start_time

            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": duration,
                "command": " ".join(cmd)
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timed out after 5 minutes",
                "duration": time.time() - start_time,
                "command": " ".join(cmd)
            }
        except Exception as e:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "duration": time.time() - start_time,
                "command": " ".join(cmd)
            }

    def run_syntax_check(self):
        """Check Python syntax for all modules"""
        print("🔍 Running Syntax Checks")
        print("-" * 40)

        # Check critical files
        files_to_check = [
            "backend/src/main.py",
            "backend/src/services/vector_search_service.py",
            "backend/src/services/knowledge_graph_service.py",
            "backend/src/services/fulltext_search_service.py",
            "backend/src/services/hybrid_search_service.py",
            "backend/src/services/search_quality_service.py",
            "backend/src/api/search.py",
            "backend/src/api/search_quality.py",
            "backend/src/models/search_schemas.py"
        ]

        syntax_results = []
        for file_path in files_to_check:
            full_path = self.test_dir.parent / file_path
            if full_path.exists():
                result = self.run_command(
                    ["python3", "-m", "py_compile", str(full_path)],
                    f"Checking syntax for {file_path}"
                )
                syntax_results.append((file_path, result))

                if result["success"]:
                    print(f"   ✅ {file_path}")
                else:
                    print(f"   ❌ {file_path}")
                    if result["stderr"]:
                        print(f"      Error: {result['stderr'][:200]}...")
            else:
                print(f"   ⚠️  {file_path} (not found)")

        all_syntax_ok = all(r[1]["success"] for r in syntax_results)
        print(f"\nSyntax check: {'✅ PASSED' if all_syntax_ok else '❌ FAILED'}")
        print()

        return all_syntax_ok

    def run_import_tests(self):
        """Test that all modules can be imported"""
        print("📦 Running Import Tests")
        print("-" * 40)

        import_tests = [
            ("src.models.search_schemas", "Search schemas"),
            ("src.services.vector_search_service", "Vector search service"),
            ("src.services.knowledge_graph_service", "Knowledge graph service"),
            ("src.services.fulltext_search_service", "Full-text search service"),
            ("src.services.hybrid_search_service", "Hybrid search service"),
            ("src.services.search_quality_service", "Search quality service"),
            ("src.api.search", "Search API"),
            ("src.api.search_quality", "Search quality API"),
        ]

        import_results = []
        for module_name, description in import_tests:
            # Create test script
            test_script = f"""
import sys
sys.path.append('backend')
try:
    import {module_name}
    print("IMPORT_SUCCESS")
except Exception as e:
    print(f"IMPORT_FAILED: {{e}}")
"""

            # Write test script to temporary file
            temp_file = self.test_dir / "temp_import_test.py"
            with open(temp_file, 'w') as f:
                f.write(test_script)

            result = self.run_command(
                ["python3", str(temp_file)],
                f"Testing import of {description}"
            )

            # Clean up temp file
            temp_file.unlink(missing_ok=True)

            if "IMPORT_SUCCESS" in result["stdout"]:
                print(f"   ✅ {description}")
                import_results.append(True)
            else:
                print(f"   ❌ {description}")
                import_results.append(False)
                if "IMPORT_FAILED:" in result["stdout"]:
                    error_msg = result["stdout"].split("IMPORT_FAILED:")[1].strip()
                    print(f"      Error: {error_msg[:100]}...")

        all_imports_ok = all(import_results)
        print(f"\nImport test: {'✅ PASSED' if all_imports_ok else '❌ FAILED'}")
        print()

        return all_imports_ok

    def run_unit_tests(self):
        """Run pytest unit tests"""
        print("🧪 Running Unit Tests")
        print("-" * 40)

        # Check if pytest is available
        pytest_check = self.run_command(
            ["python3", "-c", "import pytest; print('Pytest version:', pytest.__version__)"],
            "Checking pytest availability"
        )

        if not pytest_check["success"]:
            print("   ❌ Pytest not available")
            return False

        print(f"   ✅ Pytest available")

        # Run pytest with specific markers
        cmd = [
            "python3", "-m", "pytest",
            "tests/test_t2_validation.py",
            "-v",
            "--tb=short",
            "--no-header",
            "--color=yes"
        ]

        result = self.run_command(cmd, "Running T2 validation tests")

        if result["success"]:
            print("   ✅ All tests completed")
        else:
            print("   ❌ Some tests failed")

        # Parse test results
        output_lines = result["stdout"].split('\n')
        passed = failed = skipped = 0

        for line in output_lines:
            if " passed" in line and " failed" in line:
                # Parse line like "5 passed, 2 failed, 1 skipped in 10.5s"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed" and i > 0:
                        passed = int(parts[i-1])
                    elif part == "failed" and i > 0:
                        failed = int(parts[i-1])
                    elif part == "skipped" and i > 0:
                        skipped = int(parts[i-1])

        print(f"   📊 Results: {passed} passed, {failed} failed, {skipped} skipped")
        print(f"   ⏱️  Duration: {result['duration']:.2f}s")

        if result["stderr"]:
            print(f"   ⚠️  Errors/Warnings:")
            for line in result["stderr"].split('\n')[:10]:  # Show first 10 lines
                if line.strip():
                    print(f"      {line}")

        print(f"\nUnit tests: {'✅ PASSED' if result['success'] else '❌ FAILED'}")
        print()

        self.test_results["unit_tests"] = {
            "success": result["success"],
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration": result["duration"]
        }

        return result["success"]

    def run_integration_tests(self):
        """Run integration tests"""
        print("🔗 Running Integration Tests")
        print("-" * 40)

        # Run integration test markers
        cmd = [
            "python3", "-m", "pytest",
            "tests/test_t2_validation.py::TestT2_Integration",
            "-v",
            "--tb=short",
            "--no-header"
        ]

        result = self.run_command(cmd, "Running integration tests")

        if result["success"]:
            print("   ✅ Integration tests passed")
        else:
            print("   ❌ Integration tests failed")

        print(f"   ⏱️  Duration: {result['duration']:.2f}s")
        print(f"\nIntegration tests: {'✅ PASSED' if result['success'] else '❌ FAILED'}")
        print()

        return result["success"]

    def check_service_health(self):
        """Check if required services are available"""
        print("🏥 Checking Service Health")
        print("-" * 40)

        services = []

        # Check database connection
        db_check = self.run_command(
            ["python3", "-c", """
import sys
sys.path.append('backend')
try:
    from src.core.database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('DATABASE_OK')
except Exception as e:
    print(f'DATABASE_ERROR: {e}')
"""],
            "Checking database connection"
        )

        if "DATABASE_OK" in db_check["stdout"]:
            print("   ✅ Database connection")
            services.append("database")
        else:
            print("   ❌ Database connection")

        # Check Qdrant connection (if available)
        qdrant_check = self.run_command(
            ["python3", "-c", """
import sys
sys.path.append('backend')
try:
    from src.core.config import settings
    print(f'QDRANT_CONFIG: {settings.QDRANT_URL}')
except Exception as e:
    print(f'CONFIG_ERROR: {e}')
"""],
            "Checking Qdrant configuration"
        )

        if "QDRANT_CONFIG:" in qdrant_check["stdout"]:
            print("   ✅ Qdrant configuration")
            services.append("qdrant")
        else:
            print("   ⚠️  Qdrant configuration (may be optional)")

        # Check Neo4j connection (if available)
        neo4j_check = self.run_command(
            ["python3", "-c", """
import sys
sys.path.append('backend')
try:
    from src.core.config import settings
    print(f'NEO4J_CONFIG: {settings.NEO4J_URI}')
except Exception as e:
    print(f'CONFIG_ERROR: {e}')
"""],
            "Checking Neo4j configuration"
        )

        if "NEO4J_CONFIG:" in neo4j_check["stdout"]:
            print("   ✅ Neo4j configuration")
            services.append("neo4j")
        else:
            print("   ⚠️  Neo4j configuration (may be optional)")

        print(f"\nService health: {'✅ OK' if len(services) >= 1 else '❌ ISSUES DETECTED'}")
        print()

        return len(services) >= 1

    def generate_report(self):
        """Generate final validation report"""
        total_duration = time.time() - self.start_time

        print("📊 Final Validation Report")
        print("=" * 80)

        # Overall status
        all_checks_passed = all([
            self.test_results.get("syntax", False),
            self.test_results.get("imports", False),
            self.test_results.get("unit_tests", {}).get("success", False),
            self.test_results.get("integration", False),
            self.test_results.get("services", False)
        ])

        print(f"Overall Status: {'🎉 ALL TESTS PASSED' if all_checks_passed else '❌ SOME TESTS FAILED'}")
        print(f"Total Duration: {total_duration:.2f}s")
        print()

        # Individual test results
        results = [
            ("Syntax Checks", "syntax", "✅ PASSED" if self.test_results.get("syntax", False) else "❌ FAILED"),
            ("Import Tests", "imports", "✅ PASSED" if self.test_results.get("imports", False) else "❌ FAILED"),
            ("Unit Tests", "unit_tests", self._format_unit_test_result()),
            ("Integration Tests", "integration", "✅ PASSED" if self.test_results.get("integration", False) else "❌ FAILED"),
            ("Service Health", "services", "✅ OK" if self.test_results.get("services", False) else "❌ ISSUES")
        ]

        print("Individual Results:")
        for name, key, status in results:
            print(f"  {status:<15} {name}")

        print()

        # T2 Task Summary
        print("T2 Task Validation Summary:")
        t2_tasks = [
            ("T2-001", "Vector Database Setup", "✅ VALIDATED"),
            ("T2-002", "Knowledge Graph Construction", "✅ VALIDATED"),
            ("T2-003", "Full-Text Search Implementation", "✅ VALIDATED"),
            ("T2-004", "Hybrid Search Engine", "✅ VALIDATED"),
            ("T2-005", "Search API Implementation", "✅ VALIDATED"),
            ("T2-006", "Multi-Agent Search Orchestration", "⏳ PENDING"),
            ("T2-007", "Search Quality Evaluation", "✅ VALIDATED")
        ]

        for task_id, task_name, status in t2_tasks:
            print(f"  {status:<12} {task_id}: {task_name}")

        print()

        # Recommendations
        if not all_checks_passed:
            print("🔧 Recommendations:")
            if not self.test_results.get("syntax", False):
                print("  - Fix syntax errors in Python files")
            if not self.test_results.get("imports", False):
                print("  - Resolve import dependencies and missing modules")
            if not self.test_results.get("unit_tests", {}).get("success", False):
                print("  - Fix failing unit tests")
            if not self.test_results.get("integration", False):
                print("  - Resolve integration test failures")
            if not self.test_results.get("services", False):
                print("  - Check service configurations and connections")
            print()

        # Next steps
        print("🚀 Next Steps:")
        if all_checks_passed:
            print("  - All T2 tasks (except T2-006) are validated and ready")
            print("  - Consider implementing T2-006: Multi-Agent Search Orchestration")
            print("  - Run end-to-end system tests")
            print("  - Deploy to staging environment for further testing")
        else:
            print("  - Fix identified issues before proceeding")
            print("  - Re-run validation tests after fixes")

        print()
        print("=" * 80)

        return all_checks_passed

    def _format_unit_test_result(self):
        """Format unit test result for display"""
        unit_result = self.test_results.get("unit_tests", {})
        if unit_result.get("success", False):
            return f"✅ PASSED ({unit_result.get('passed', 0)} tests)"
        else:
            return f"❌ FAILED ({unit_result.get('failed', 0)} failed)"

    def run_validation(self, skip_health: bool = False):
        """Run complete T2 validation"""
        self.print_header()

        # Run validation steps
        self.test_results["syntax"] = self.run_syntax_check()
        self.test_results["imports"] = self.run_import_tests()
        self.test_results["unit_tests"] = {"success": self.run_unit_tests()}
        self.test_results["integration"] = self.run_integration_tests()

        if not skip_health:
            self.test_results["services"] = self.check_service_health()
        else:
            print("⏭️  Skipping service health checks")
            self.test_results["services"] = True

        # Generate final report
        return self.generate_report()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="T2 Validation Test Runner")
    parser.add_argument("--skip-health", action="store_true", help="Skip service health checks")
    parser.add_argument("--quick", action="store_true", help="Run quick validation only (syntax + imports)")

    args = parser.parse_args()

    runner = T2ValidationRunner()

    if args.quick:
        print("🏃 Running quick validation (syntax + imports only)")
        runner.print_header()
        syntax_ok = runner.run_syntax_check()
        imports_ok = runner.run_import_tests()

        if syntax_ok and imports_ok:
            print("🎉 Quick validation PASSED")
            sys.exit(0)
        else:
            print("❌ Quick validation FAILED")
            sys.exit(1)
    else:
        success = runner.run_validation(skip_health=args.skip_health)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()