#!/usr/bin/env python3
"""
Comprehensive Backend Testing Script using Docker
Tests all major backend functionality via API calls
"""
import json
import time
import requests
import sys
from typing import Dict, Any, List

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

class BackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.test_user_id = None
        self.test_document_id = None
        self.test_results = []

    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
        print(f"{status} {test_name}: {details}")

    def test_health_endpoints(self):
        """Test health and readiness endpoints"""
        print("\n=== Testing Health Endpoints ===")

        try:
            response = self.session.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                data = response.json()
                self.log_test("Health Check", True, f"Status: {data.get('status')}")
            else:
                self.log_test("Health Check", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Health Check", False, str(e))

        try:
            response = self.session.get(f"{API_BASE}/auth/me")
            if response.status_code == 403:  # Expected when not authenticated
                self.log_test("Auth Me (Unauthenticated)", True, "Correctly returned 403")
            else:
                self.log_test("Auth Me (Unauthenticated)", False, f"Unexpected status: {response.status_code}")
        except Exception as e:
            self.log_test("Auth Me (Unauthenticated)", False, str(e))

    def test_user_registration_and_login(self):
        """Test user registration and authentication flow"""
        print("\n=== Testing User Authentication ===")

        # Test registration
        user_data = {
            "email": "backendtest@example.com",
            "password": "testpassword123",
            "first_name": "Backend",
            "last_name": "Tester",
            "organization_name": "Test Backend Org"
        }

        try:
            response = self.session.post(f"{API_BASE}/auth/register", json=user_data)
            if response.status_code in [200, 201]:
                data = response.json()
                self.log_test("User Registration", True, f"User created: {data.get('user', {}).get('email')}")
                self.test_user_id = data.get('user', {}).get('id')
            elif response.status_code == 400 and "already exists" in response.text:
                self.log_test("User Registration", True, "User already exists (expected)")
            else:
                self.log_test("User Registration", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_test("User Registration", False, str(e))

        # Test login
        login_data = {
            "email": user_data["email"],
            "password": user_data["password"]
        }

        try:
            response = self.session.post(f"{API_BASE}/auth/login", json=login_data)
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get('access_token')
                self.session.headers.update({'Authorization': f'Bearer {self.auth_token}'})
                self.log_test("User Login", True, "Successfully authenticated")
            else:
                self.log_test("User Login", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_test("User Login", False, str(e))

        # Test authenticated endpoint
        if self.auth_token:
            try:
                response = self.session.get(f"{API_BASE}/auth/me")
                if response.status_code == 200:
                    data = response.json()
                    self.log_test("Authenticated User Info", True, f"User: {data.get('email')}")
                else:
                    self.log_test("Authenticated User Info", False, f"Status: {response.status_code}")
            except Exception as e:
                self.log_test("Authenticated User Info", False, str(e))

    def test_document_endpoints(self):
        """Test document management endpoints"""
        print("\n=== Testing Document Management ===")

        if not self.auth_token:
            self.log_test("Document Upload", False, "No authentication token")
            return

        # Test document list (should be empty initially)
        try:
            response = self.session.get(f"{API_BASE}/documents")
            if response.status_code == 200:
                data = response.json()
                self.log_test("Document List", True, f"Found {len(data.get('documents', []))} documents")
            else:
                self.log_test("Document List", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Document List", False, str(e))

        # Test file upload validation (without actual file)
        try:
            # This will likely fail due to no file, but tests the endpoint
            response = self.session.post(f"{API_BASE}/files/upload")
            if response.status_code == 422:  # Validation error expected
                self.log_test("Upload Validation", True, "Correctly validates missing file")
            else:
                self.log_test("Upload Validation", False, f"Unexpected status: {response.status_code}")
        except Exception as e:
            self.log_test("Upload Validation", False, str(e))

    def test_search_endpoints(self):
        """Test search and query endpoints"""
        print("\n=== Testing Search Functionality ===")

        if not self.auth_token:
            self.log_test("Search Query", False, "No authentication token")
            return

        # Test search endpoint
        search_data = {
            "query": "test search query",
            "limit": 5
        }

        try:
            response = self.session.post(f"{API_BASE}/search", json=search_data)
            if response.status_code == 200:
                data = response.json()
                self.log_test("Search Query", True, f"Found {len(data.get('sources', []))} sources")
            else:
                self.log_test("Search Query", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Search Query", False, str(e))

        # Test search suggestions
        try:
            response = self.session.get(f"{API_BASE}/search/suggestions?q=test")
            if response.status_code == 200:
                data = response.json()
                self.log_test("Search Suggestions", True, f"Got {len(data.get('suggestions', []))} suggestions")
            else:
                self.log_test("Search Suggestions", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Search Suggestions", False, str(e))

    def test_database_connections(self):
        """Test database connectivity via health checks"""
        print("\n=== Testing Database Connections ===")

        # Test database health through backend
        try:
            response = self.session.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                self.log_test("Backend Health", True, "Backend responding normally")
            else:
                self.log_test("Backend Health", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Backend Health", False, str(e))

        # Test individual database connections via Docker
        databases = {
            "PostgreSQL": "localhost:5432",
            "Redis": "localhost:6379",
            "Neo4j": "localhost:7474",
            "Qdrant": "localhost:6333"
        }

        for db_name, address in databases.items():
            try:
                # Simple connectivity test using curl equivalent
                import socket
                host, port = address.split(':')
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, int(port)))
                sock.close()

                if result == 0:
                    self.log_test(f"{db_name} Connection", True, f"Connected to {address}")
                else:
                    self.log_test(f"{db_name} Connection", False, f"Cannot connect to {address}")
            except Exception as e:
                self.log_test(f"{db_name} Connection", False, str(e))

    def test_performance_endpoints(self):
        """Test performance and analytics endpoints"""
        print("\n=== Testing Performance & Analytics ===")

        if not self.auth_token:
            self.log_test("Analytics Endpoints", False, "No authentication token")
            return

        # Test analytics dashboard
        try:
            response = self.session.get(f"{API_BASE}/analytics/performance/dashboard")
            if response.status_code == 200:
                data = response.json()
                self.log_test("Analytics Dashboard", True, "Dashboard data retrieved")
            else:
                self.log_test("Analytics Dashboard", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Analytics Dashboard", False, str(e))

        # Test worker status (if accessible)
        try:
            response = self.session.get(f"{API_BASE}/workers/status")
            if response.status_code == 200:
                data = response.json()
                self.log_test("Worker Status", True, f"Workers: {data.get('system', {}).get('total_workers', 'unknown')}")
            elif response.status_code == 403:  # Expected for non-admin
                self.log_test("Worker Status", True, "Correctly restricted (admin only)")
            else:
                self.log_test("Worker Status", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Worker Status", False, str(e))

    def test_error_handling(self):
        """Test error handling and edge cases"""
        print("\n=== Testing Error Handling ===")

        # Test 404 handling
        try:
            response = self.session.get(f"{API_BASE}/nonexistent/endpoint")
            if response.status_code == 404:
                self.log_test("404 Error Handling", True, "Correctly returns 404")
            else:
                self.log_test("404 Error Handling", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("404 Error Handling", False, str(e))

        # Test invalid JSON handling
        try:
            response = self.session.post(
                f"{API_BASE}/auth/login",
                data="invalid json",
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code == 422:
                self.log_test("Invalid JSON Handling", True, "Correctly validates JSON")
            else:
                self.log_test("Invalid JSON Handling", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Invalid JSON Handling", False, str(e))

    def run_all_tests(self):
        """Run comprehensive backend tests"""
        print("🚀 Starting Comprehensive Backend Testing")
        print(f"Target: {BASE_URL}")
        print("=" * 50)

        start_time = time.time()

        self.test_health_endpoints()
        self.test_user_registration_and_login()
        self.test_document_endpoints()
        self.test_search_endpoints()
        self.test_database_connections()
        self.test_performance_endpoints()
        self.test_error_handling()

        end_time = time.time()

        # Generate summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)

        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)

        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        print(f"Duration: {end_time - start_time:.2f} seconds")

        if total - passed > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['details']}")

        print(f"\n{'✅ BACKEND TESTS PASSED' if passed == total else '❌ SOME BACKEND TESTS FAILED'}")
        print("=" * 50)

        return passed == total

if __name__ == "__main__":
    # Check if backend is running
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code != 200:
            print("❌ Backend health check failed")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("Make sure Docker containers are running")
        sys.exit(1)

    # Run tests
    tester = BackendTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)