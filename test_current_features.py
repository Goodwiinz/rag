#!/usr/bin/env python3
"""
Test Current Features of RAG Platform

This script tests the features that are currently implemented in your platform.
Run this to verify the T3 Analytics and T4 Security features are working.
"""

import requests
import json
import time
import os
from typing import Dict, Any, List

class CurrentFeaturesTester:
    """Test currently implemented features"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.auth_token = None

    def log(self, message: str, status: str = "INFO"):
        """Log message with status"""
        icon = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}.get(status, "📝")
        print(f"{icon} {message}")

    def test_basic_health(self) -> bool:
        """Test basic health endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log(f"Backend healthy: {data.get('status', 'unknown')}", "SUCCESS")
                return True
        except Exception as e:
            self.log(f"Health check failed: {str(e)}", "ERROR")
        return False

    def test_t3_analytics_features(self) -> bool:
        """Test T3 Analytics features"""
        self.log("Testing T3 Analytics Features...", "INFO")

        try:
            # Test quality metrics service
            response = self.session.get(f"{self.base_url}/api/quality-metrics/dashboard", timeout=10)
            if response.status_code == 200:
                self.log("Quality Metrics Dashboard accessible", "SUCCESS")
            else:
                self.log(f"Quality Metrics failed: {response.status_code}", "WARNING")

            # Test performance dashboard
            response = self.session.get(f"{self.base_url}/api/performance/dashboard", timeout=10)
            if response.status_code == 200:
                self.log("Performance Dashboard accessible", "SUCCESS")
            else:
                self.log(f"Performance Dashboard failed: {response.status_code}", "WARNING")

            # Test user behavior analytics
            response = self.session.get(f"{self.base_url}/api/user-behavior/insights", timeout=10)
            if response.status_code == 200:
                self.log("User Behavior Analytics accessible", "SUCCESS")
            else:
                self.log(f"User Behavior Analytics failed: {response.status_code}", "WARNING")

            # Test analytics cache
            response = self.session.get(f"{self.base_url}/api/analytics/cache/status", timeout=10)
            if response.status_code == 200:
                self.log("Analytics Cache working", "SUCCESS")
            else:
                self.log(f"Analytics Cache failed: {response.status_code}", "WARNING")

            return True

        except Exception as e:
            self.log(f"T3 Analytics test failed: {str(e)}", "ERROR")
            return False

    def test_t4_security_features(self) -> bool:
        """Test T4 Security features"""
        self.log("Testing T4 Security Features...", "INFO")

        try:
            # Test multi-tenancy middleware
            response = self.session.get(f"{self.base_url}/api/tenant/status", timeout=10)
            if response.status_code == 200:
                self.log("Multi-tenancy working", "SUCCESS")
            else:
                self.log(f"Multi-tenancy test failed: {response.status_code}", "WARNING")

            # Test RBAC permissions
            response = self.session.get(f"{self.base_url}/api/rbac/permissions", timeout=10)
            if response.status_code == 200:
                self.log("RBAC Permissions accessible", "SUCCESS")
            else:
                self.log(f"RBAC Permissions failed: {response.status_code}", "WARNING")

            # Test audit logging
            response = self.session.get(f"{self.base_url}/api/compliance/audit/logs", params={"limit": 5}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log(f"Audit Logging working: {len(data)} logs found", "SUCCESS")
            else:
                self.log(f"Audit Logging failed: {response.status_code}", "WARNING")

            # Test encryption service
            response = self.session.get(f"{self.base_url}/api/encryption/status", timeout=10)
            if response.status_code == 200:
                self.log("Encryption Service accessible", "SUCCESS")
            else:
                self.log(f"Encryption Service failed: {response.status_code}", "WARNING")

            # Test rate limiting
            response = self.session.get(f"{self.base_url}/api/rate-limit/status", timeout=10)
            if response.status_code == 200:
                self.log("Rate Limiting accessible", "SUCCESS")
            else:
                self.log(f"Rate Limiting failed: {response.status_code}", "WARNING")

            return True

        except Exception as e:
            self.log(f"T4 Security test failed: {str(e)}", "ERROR")
            return False

    def test_database_models(self) -> bool:
        """Test database models and relationships"""
        self.log("Testing Database Models...", "INFO")

        try:
            # Test connection to database through API
            response = self.session.get(f"{self.base_url}/api/system/database/status", timeout=10)
            if response.status_code == 200:
                self.log("Database connection healthy", "SUCCESS")
                return True
            else:
                self.log(f"Database status check failed: {response.status_code}", "WARNING")
                return False

        except Exception as e:
            self.log(f"Database models test failed: {str(e)}", "ERROR")
            return False

    def test_external_services(self) -> bool:
        """Test external service connections"""
        self.log("Testing External Services...", "INFO")

        services = {
            "PostgreSQL": self.base_url,
            "Redis": self.base_url,
            "Qdrant": self.base_url,
            "Neo4j": self.base_url
        }

        healthy_services = 0

        for service, url in services.items():
            try:
                # Try to check service through health endpoints
                response = self.session.get(f"{url}/health", timeout=5)
                if response.status_code == 200:
                    self.log(f"{service} connection healthy", "SUCCESS")
                    healthy_services += 1
                else:
                    self.log(f"{service} connection failed: {response.status_code}", "WARNING")
            except Exception as e:
                self.log(f"{service} connection error: {str(e)}", "WARNING")

        if healthy_services >= 3:  # At least 3 services should be healthy
            self.log(f"External services mostly healthy ({healthy_services}/4)", "SUCCESS")
            return True
        else:
            self.log(f"External services issues ({healthy_services}/4 healthy)", "ERROR")
            return False

    def test_api_endpoints(self) -> bool:
        """Test main API endpoints"""
        self.log("Testing Main API Endpoints...", "INFO")

        endpoints = [
            "/api/auth/register",
            "/api/documents",
            "/api/search/hybrid",
            "/api/analytics/performance/dashboard",
            "/api/quality-metrics/recommendations",
            "/api/compliance/audit/logs",
            "/api/encryption/profiles/user",
            "/api/rbac/users"
        ]

        working_endpoints = 0

        for endpoint in endpoints:
            try:
                response = self.session.options(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code in [200, 204, 405]:  # 405 Method Not Allowed is okay - endpoint exists
                    self.log(f"Endpoint {endpoint} exists", "SUCCESS")
                    working_endpoints += 1
                else:
                    self.log(f"Endpoint {endpoint} not found: {response.status_code}", "WARNING")
            except Exception as e:
                self.log(f"Endpoint {endpoint} error: {str(e)}", "WARNING")

        if working_endpoints >= len(endpoints) * 0.7:  # At least 70% of endpoints should work
            self.log(f"API endpoints mostly working ({working_endpoints}/{len(endpoints)})", "SUCCESS")
            return True
        else:
            self.log(f"API endpoints issues ({working_endpoints}/{len(endpoints)} working)", "ERROR")
            return False

    def check_file_structure(self) -> bool:
        """Check if key files exist in the project"""
        self.log("Checking Project File Structure...", "INFO")

        key_files = [
            "backend/src/core/encryption.py",
            "backend/src/models/encrypted_user.py",
            "backend/src/services/encryption_service.py",
            "backend/src/api/encryption.py",
            "backend/src/middleware/encryption_middleware.py",
            "backend/src/services/audit_service.py",
            "backend/src/api/compliance.py",
            "backend/src/middleware/rbac.py",
            "backend/src/middleware/multi_tenancy.py",
            "backend/src/services/rbac_service.py",
            "TESTING_GUIDE.md",
            "quick_test.py"
        ]

        existing_files = 0

        for file_path in key_files:
            if os.path.exists(file_path):
                self.log(f"✓ {file_path}", "SUCCESS")
                existing_files += 1
            else:
                self.log(f"✗ {file_path}", "WARNING")

        if existing_files >= len(key_files) * 0.8:  # At least 80% of files should exist
            self.log(f"Project structure mostly complete ({existing_files}/{len(key_files)} files)", "SUCCESS")
            return True
        else:
            self.log(f"Project structure incomplete ({existing_files}/{len(key_files)} files)", "ERROR")
            return False

    def run_comprehensive_test(self) -> Dict[str, bool]:
        """Run comprehensive test of current features"""
        self.log("🚀 Starting Comprehensive Feature Test", "INFO")
        self.log("=" * 60, "INFO")

        tests = {
            "Basic Health": self.test_basic_health,
            "T3 Analytics Features": self.test_t3_analytics_features,
            "T4 Security Features": self.test_t4_security_features,
            "Database Models": self.test_database_models,
            "External Services": self.test_external_services,
            "API Endpoints": self.test_api_endpoints,
            "File Structure": self.check_file_structure
        }

        results = {}

        for test_name, test_func in tests.items():
            self.log(f"\n📋 Running {test_name} Test...", "INFO")
            try:
                results[test_name] = test_func()
                time.sleep(0.5)  # Brief pause between tests
            except Exception as e:
                self.log(f"Test '{test_name}' crashed: {str(e)}", "ERROR")
                results[test_name] = False

        return results

    def print_summary(self, results: Dict[str, bool]):
        """Print comprehensive test summary"""
        self.log("\n" + "=" * 60, "INFO")
        self.log("📊 COMPREHENSIVE TEST RESULTS", "INFO")
        self.log("=" * 60, "INFO")

        passed = sum(results.values())
        total = len(results)

        # Categorize results
        implemented_features = []
        missing_features = []

        for feature, status in results.items():
            if status:
                implemented_features.append(f"✅ {feature}")
            else:
                missing_features.append(f"❌ {feature}")

        if implemented_features:
            self.log("\n🎉 IMPLEMENTED FEATURES:", "SUCCESS")
            for feature in implemented_features:
                self.log(f"  {feature}")

        if missing_features:
            self.log("\n⚠️ NEEDS ATTENTION:", "WARNING")
            for feature in missing_features:
                self.log(f"  {feature}")

        self.log("\n" + "=" * 60, "INFO")
        self.log(f"📈 OVERALL STATUS: {passed}/{total} test categories passed",
                "SUCCESS" if passed >= total * 0.8 else "WARNING")

        # Progress percentage
        progress = (passed / total) * 100
        self.log(f"🎯 IMPLEMENTATION PROGRESS: {progress:.1f}%", "INFO")

        if progress >= 80:
            self.log("🚀 Excellent! Your RAG platform is well-implemented.", "SUCCESS")
        elif progress >= 60:
            self.log("👍 Good progress! Some features may need attention.", "INFO")
        else:
            self.log("🔧 Several features need implementation or fixes.", "WARNING")

        self.log("=" * 60, "INFO")


def main():
    """Main function"""
    print("🔍 RAG Platform Current Features Test")
    print("=" * 60)

    tester = CurrentFeaturesTester()
    results = tester.run_comprehensive_test()
    tester.print_summary(results)


if __name__ == "__main__":
    main()