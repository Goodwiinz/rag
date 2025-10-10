#!/usr/bin/env python3
"""
Quick Test Script for RAG Platform

This script provides a quick way to test the basic functionality of your RAG platform.
Run this script to verify that all services are working correctly.

Usage:
    python quick_test.py [--host localhost] [--port 8000] [--verbose]
"""

import requests
import json
import time
import sys
import argparse
from typing import Dict, Any, Optional

class RAGPlatformTester:
    """Test suite for RAG platform functionality"""

    def __init__(self, host: str = "localhost", port: int = 8000, verbose: bool = False):
        self.base_url = f"http://{host}:{port}"
        self.verbose = verbose
        self.session = requests.Session()
        self.auth_token = None
        self.test_user_id = None
        self.test_org_id = None

    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        if self.verbose or level in ["ERROR", "SUCCESS"]:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {level}: {message}")

    def test_health_check(self) -> bool:
        """Test basic health check endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                self.log("Health check passed", "SUCCESS")
                return True
            else:
                self.log(f"Health check failed: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Health check error: {str(e)}", "ERROR")
            return False

    def test_user_registration(self) -> bool:
        """Test user registration"""
        try:
            user_data = {
                "email": "test@example.com",
                "password": "SecurePass123!",
                "first_name": "Test",
                "last_name": "User",
                "organization_name": "Test Organization"
            }

            response = self.session.post(
                f"{self.base_url}/api/auth/register",
                json=user_data,
                timeout=10
            )

            if response.status_code in [200, 201]:
                data = response.json()
                self.test_user_id = data.get("user_id")
                self.test_org_id = data.get("organization_id")
                self.log("User registration successful", "SUCCESS")
                return True
            else:
                self.log(f"Registration failed: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Registration error: {str(e)}", "ERROR")
            return False

    def test_user_login(self) -> bool:
        """Test user login"""
        try:
            login_data = {
                "email": "test@example.com",
                "password": "SecurePass123!"
            }

            response = self.session.post(
                f"{self.base_url}/api/auth/login",
                json=login_data,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                self.log("User login successful", "SUCCESS")
                return True
            else:
                self.log(f"Login failed: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Login error: {str(e)}", "ERROR")
            return False

    def test_document_upload(self) -> bool:
        """Test document upload (simulate with text content)"""
        try:
            # Create a simple test document content
            test_content = """
            # Machine Learning Fundamentals

            Machine learning is a subset of artificial intelligence that enables computers
            to learn and improve from experience without being explicitly programmed.
            It focuses on developing computer programs that can access data and use it
            to learn for themselves.

            ## Types of Machine Learning

            1. **Supervised Learning**: Learning with labeled data
            2. **Unsupervised Learning**: Learning with unlabeled data
            3. **Reinforcement Learning**: Learning through interactions

            ## Common Applications

            - Image recognition
            - Natural language processing
            - Recommendation systems
            - Autonomous vehicles
            """

            files = {
                "file": ("test_document.txt", test_content, "text/plain")
            }
            data = {
                "title": "Machine Learning Test Document",
                "description": "A test document about machine learning fundamentals"
            }

            response = self.session.post(
                f"{self.base_url}/api/documents/upload",
                files=files,
                data=data,
                timeout=30
            )

            if response.status_code in [200, 201]:
                doc_data = response.json()
                self.log(f"Document upload successful: {doc_data.get('id')}", "SUCCESS")
                return True
            else:
                self.log(f"Document upload failed: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Document upload error: {str(e)}", "ERROR")
            return False

    def test_search_functionality(self) -> bool:
        """Test search functionality"""
        try:
            search_data = {
                "query": "machine learning",
                "limit": 5,
                "filters": {
                    "file_types": ["txt"]
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/search/hybrid",
                json=search_data,
                timeout=15
            )

            if response.status_code == 200:
                search_results = response.json()
                results_count = len(search_results.get("results", []))
                self.log(f"Search successful: Found {results_count} results", "SUCCESS")
                return True
            else:
                self.log(f"Search failed: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Search error: {str(e)}", "ERROR")
            return False

    def test_analytics_endpoint(self) -> bool:
        """Test analytics endpoint"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/analytics/performance/dashboard",
                timeout=10
            )

            if response.status_code == 200:
                analytics_data = response.json()
                self.log("Analytics endpoint accessible", "SUCCESS")
                return True
            else:
                self.log(f"Analytics failed: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Analytics error: {str(e)}", "ERROR")
            return False

    def test_encryption_service(self) -> bool:
        """Test encryption service"""
        try:
            encryption_data = {
                "user_id": self.test_user_id,
                "profile_data": {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email_personal": "john.doe@example.com"
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/encryption/profiles/user",
                json=encryption_data,
                timeout=10
            )

            if response.status_code == 200:
                self.log("Encryption service working", "SUCCESS")
                return True
            else:
                self.log(f"Encryption service failed: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Encryption service error: {str(e)}", "ERROR")
            return False

    def test_audit_logging(self) -> bool:
        """Test audit logging"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/compliance/audit/logs",
                params={"limit": 5},
                timeout=10
            )

            if response.status_code == 200:
                audit_data = response.json()
                self.log(f"Audit logging working: {len(audit_data)} logs found", "SUCCESS")
                return True
            else:
                self.log(f"Audit logging failed: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Audit logging error: {str(e)}", "ERROR")
            return False

    def test_database_connection(self) -> bool:
        """Test database connection via API"""
        try:
            response = self.session.get(f"{self.base_url}/api/health/database", timeout=10)
            if response.status_code == 200:
                self.log("Database connection healthy", "SUCCESS")
                return True
            else:
                self.log(f"Database connection issue: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Database connection error: {str(e)}", "ERROR")
            return False

    def test_external_services(self) -> bool:
        """Test external service connections"""
        services = {}

        # Test Redis
        try:
            response = self.session.get(f"{self.base_url}/api/health/redis", timeout=5)
            services["redis"] = response.status_code == 200
        except:
            services["redis"] = False

        # Test Qdrant (Vector DB)
        try:
            response = self.session.get(f"{self.base_url}/api/health/qdrant", timeout=5)
            services["qdrant"] = response.status_code == 200
        except:
            services["qdrant"] = False

        # Test Neo4j (Knowledge Graph)
        try:
            response = self.session.get(f"{self.base_url}/api/health/neo4j", timeout=5)
            services["neo4j"] = response.status_code == 200
        except:
            services["neo4j"] = False

        healthy_services = sum(services.values())
        total_services = len(services)

        if healthy_services == total_services:
            self.log("All external services healthy", "SUCCESS")
            return True
        else:
            self.log(f"External services issue: {healthy_services}/{total_services} healthy", "ERROR")
            for service, status in services.items():
                status_str = "✓" if status else "✗"
                self.log(f"  {service}: {status_str}")
            return False

    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests and return results"""
        self.log("Starting RAG Platform Tests", "INFO")
        self.log("=" * 50, "INFO")

        tests = {
            "Health Check": self.test_health_check,
            "Database Connection": self.test_database_connection,
            "External Services": self.test_external_services,
            "User Registration": self.test_user_registration,
            "User Login": self.test_user_login,
            "Document Upload": self.test_document_upload,
            "Search Functionality": self.test_search_functionality,
            "Analytics Endpoint": self.test_analytics_endpoint,
            "Encryption Service": self.test_encryption_service,
            "Audit Logging": self.test_audit_logging,
        }

        results = {}

        for test_name, test_func in tests.items():
            self.log(f"Running {test_name}...", "INFO")
            try:
                results[test_name] = test_func()
            except Exception as e:
                self.log(f"Test '{test_name}' crashed: {str(e)}", "ERROR")
                results[test_name] = False

            time.sleep(1)  # Brief pause between tests

        return results

    def print_summary(self, results: Dict[str, bool]):
        """Print test summary"""
        self.log("=" * 50, "INFO")
        self.log("TEST SUMMARY", "INFO")
        self.log("=" * 50, "INFO")

        passed = sum(results.values())
        total = len(results)

        for test_name, result in results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status:<8} {test_name}")

        self.log("=" * 50, "INFO")
        self.log(f"Overall Result: {passed}/{total} tests passed",
                "SUCCESS" if passed == total else "ERROR")

        if passed == total:
            self.log("🎉 All tests passed! Your RAG platform is working correctly.", "SUCCESS")
        else:
            self.log(f"⚠️  {total - passed} test(s) failed. Check the logs above.", "ERROR")

        self.log("=" * 50, "INFO")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Quick test script for RAG Platform")
    parser.add_argument("--host", default="localhost", help="Backend host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="Backend port (default: 8000)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    tester = RAGPlatformTester(host=args.host, port=args.port, verbose=args.verbose)
    results = tester.run_all_tests()
    tester.print_summary(results)

    # Exit with appropriate code
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()