"""
Phase 1 Implementation Validation Script

This script validates that all Phase 1 components are working correctly:
- T1-001: Core Database Schema and Models
- T1-002: Authentication and Authorization System
- T1-003: File Upload and Storage System
- T1-004: Multimodal Processing Pipeline Architecture
"""

import os
import sys
import requests
import json
import time
from pathlib import Path
from typing import Dict, Any, List
import logging

# Add src directory to Python path
sys.path.append(str(Path(__file__).parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Phase1Validator:
    """Validator for Phase 1 implementation"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = {}
        self.auth_token = None
        self.test_user_id = None
        self.test_document_id = None

    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "PASS" if passed else "FAIL"
        logger.info(f"[{status}] {test_name}: {message}")
        self.test_results[test_name] = {"passed": passed, "message": message}

    def test_health_check(self):
        """Test API health check"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Health Check",
                    True,
                    f"API is healthy (v{data.get('version', 'unknown')})"
                )
                return True
            else:
                self.log_test("Health Check", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Health Check", False, f"Connection error: {str(e)}")
            return False

    def test_database_initialization(self):
        """Test database models and initialization"""
        try:
            from src.core.database import engine, check_database_health
            from src.models import Base

            # Test database health
            if check_database_health():
                # Test model creation
                Base.metadata.create_all(bind=engine)
                self.log_test("Database Initialization", True, "Models created successfully")
                return True
            else:
                self.log_test("Database Initialization", False, "Database health check failed")
                return False
        except Exception as e:
            self.log_test("Database Initialization", False, f"Error: {str(e)}")
            return False

    def test_user_registration(self):
        """Test user registration"""
        try:
            test_user_data = {
                "email": "test@validator.com",
                "password": "ValidatorPassword123!",
                "first_name": "Test",
                "last_name": "Validator",
                "organization_name": "Validation Test Organization"
            }

            response = self.session.post(
                f"{self.base_url}/api/v1/auth/register",
                json=test_user_data
            )

            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "User Registration",
                    True,
                    f"User registered: {data['user']['email']}"
                )
                self.test_user_id = data['user']['id']
                return True
            else:
                self.log_test(
                    "User Registration",
                    False,
                    f"Status code: {response.status_code}, Error: {response.text}"
                )
                return False
        except Exception as e:
            self.log_test("User Registration", False, f"Error: {str(e)}")
            return False

    def test_user_login(self):
        """Test user login"""
        try:
            login_data = {
                "email": "test@validator.com",
                "password": "ValidatorPassword123!"
            }

            response = self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                json=login_data
            )

            if response.status_code == 200:
                data = response.json()
                self.auth_token = data['access_token']
                self.session.headers.update({
                    'Authorization': f'Bearer {self.auth_token}'
                })
                self.log_test("User Login", True, "Login successful")
                return True
            else:
                self.log_test(
                    "User Login",
                    False,
                    f"Status code: {response.status_code}, Error: {response.text}"
                )
                return False
        except Exception as e:
            self.log_test("User Login", False, f"Error: {str(e)}")
            return False

    def test_user_profile(self):
        """Test getting user profile"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/auth/me")

            if response.status_code == 200:
                data = response.json()
                self.log_test("User Profile", True, f"Profile retrieved: {data['user']['email']}")
                return True
            else:
                self.log_test(
                    "User Profile",
                    False,
                    f"Status code: {response.status_code}, Error: {response.text}"
                )
                return False
        except Exception as e:
            self.log_test("User Profile", False, f"Error: {str(e)}")
            return False

    def test_file_upload(self):
        """Test file upload functionality"""
        try:
            # Create a test file
            test_content = "This is a test document for Phase 1 validation. It contains sample text to test the processing pipeline."
            test_files = [
                ("test_document.txt", test_content, "text/plain"),
                ("test_data.csv", "Name,Age,City\nJohn,30,NYC\nJane,25,LA", "text/csv")
            ]

            upload_results = []
            for filename, content, mime_type in test_files:
                files = {
                    'file': (filename, content.encode('utf-8'), mime_type)
                }
                data = {
                    'title': f'Test {filename}',
                    'tags': 'test,validation,phase1'
                }

                response = self.session.post(
                    f"{self.base_url}/api/v1/files/upload",
                    files=files,
                    data=data
                )

                if response.status_code == 200:
                    file_data = response.json()
                    upload_results.append(file_data)
                    self.log_test(
                        f"File Upload ({filename})",
                        True,
                        f"Uploaded: {file_data['title']}"
                    )
                    if not self.test_document_id:
                        self.test_document_id = file_data['id']
                else:
                    self.log_test(
                        f"File Upload ({filename})",
                        False,
                        f"Status code: {response.status_code}, Error: {response.text}"
                    )

            return len(upload_results) > 0
        except Exception as e:
            self.log_test("File Upload", False, f"Error: {str(e)}")
            return False

    def test_file_listing(self):
        """Test file listing"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/files/")

            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "File Listing",
                    True,
                    f"Found {data['total']} files"
                )
                return True
            else:
                self.log_test(
                    "File Listing",
                    False,
                    f"Status code: {response.status_code}, Error: {response.text}"
                )
                return False
        except Exception as e:
            self.log_test("File Listing", False, f"Error: {str(e)}")
            return False

    def test_file_processing(self):
        """Test document processing"""
        if not self.test_document_id:
            self.log_test("File Processing", False, "No test document available")
            return False

        try:
            # Start processing
            response = self.session.post(
                f"{self.base_url}/api/v1/processing/documents/{self.test_document_id}/process"
            )

            if response.status_code == 200:
                self.log_test("File Processing", True, "Processing started successfully")

                # Check processing status (wait a bit for async processing)
                time.sleep(2)
                status_response = self.session.get(
                    f"{self.base_url}/api/v1/processing/documents/{self.test_document_id}/status"
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    self.log_test(
                        "Processing Status",
                        True,
                        f"Status: {status_data['processing_status']}"
                    )
                    return True
                else:
                    self.log_test(
                        "Processing Status",
                        False,
                        f"Status code: {status_response.status_code}"
                    )
                    return False
            else:
                self.log_test(
                    "File Processing",
                    False,
                    f"Status code: {response.status_code}, Error: {response.text}"
                )
                return False
        except Exception as e:
            self.log_test("File Processing", False, f"Error: {str(e)}")
            return False

    def test_user_statistics(self):
        """Test user statistics (admin functionality)"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/auth/statistics")

            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "User Statistics",
                    True,
                    f"Total users: {data['total_users']}"
                )
                return True
            else:
                # This might fail if user is not admin, which is expected
                self.log_test(
                    "User Statistics",
                    False,
                    f"Status code: {response.status_code} (might be expected for non-admin)"
                )
                return False
        except Exception as e:
            self.log_test("User Statistics", False, f"Error: {str(e)}")
            return False

    def test_file_statistics(self):
        """Test file statistics"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/files/stats")

            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "File Statistics",
                    True,
                    f"Files by type: {len(data['files_by_type'])}"
                )
                return True
            else:
                self.log_test(
                    "File Statistics",
                    False,
                    f"Status code: {response.status_code}, Error: {response.text}"
                )
                return False
        except Exception as e:
            self.log_test("File Statistics", False, f"Error: {str(e)}")
            return False

    def test_processing_jobs(self):
        """Test processing job listing"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/processing/jobs")

            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Processing Jobs",
                    True,
                    f"Found {data['total']} jobs"
                )
                return True
            else:
                self.log_test(
                    "Processing Jobs",
                    False,
                    f"Status code: {response.status_code}, Error: {response.text}"
                )
                return False
        except Exception as e:
            self.log_test("Processing Jobs", False, f"Error: {str(e)}")
            return False

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all Phase 1 validation tests"""
        logger.info("Starting Phase 1 Implementation Validation")
        logger.info("=" * 60)

        tests = [
            ("Database & Models", self.test_database_initialization),
            ("API Health Check", self.test_health_check),
            ("User Registration", self.test_user_registration),
            ("User Login", self.test_user_login),
            ("User Profile", self.test_user_profile),
            ("File Upload", self.test_file_upload),
            ("File Listing", self.test_file_listing),
            ("File Processing", self.test_file_processing),
            ("User Statistics", self.test_user_statistics),
            ("File Statistics", self.test_file_statistics),
            ("Processing Jobs", self.test_processing_jobs),
        ]

        # Run tests
        for test_name, test_func in tests:
            logger.info(f"\nRunning: {test_name}")
            try:
                test_func()
            except Exception as e:
                logger.error(f"Test {test_name} crashed: {str(e)}")
                self.log_test(test_name, False, f"Test crashed: {str(e)}")

        # Generate summary
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 1 VALIDATION SUMMARY")
        logger.info("=" * 60)

        passed = sum(1 for result in self.test_results.values() if result["passed"])
        total = len(self.test_results)

        for test_name, result in self.test_results.items():
            status = "PASS" if result["passed"] else "FAIL"
            message = result["message"]
            logger.info(f"[{status}] {test_name}: {message}")

        logger.info("\n" + "=" * 60)
        logger.info(f"RESULTS: {passed}/{total} tests passed")

        if passed == total:
            logger.info("🎉 ALL TESTS PASSED - Phase 1 implementation is complete!")
        else:
            logger.warning(f"⚠️  {total - passed} tests failed - Review and fix issues")

        return {
            "total_tests": total,
            "passed_tests": passed,
            "failed_tests": total - passed,
            "success_rate": (passed / total) * 100 if total > 0 else 0,
            "test_results": self.test_results
        }

def main():
    """Main validation function"""
    import argparse

    parser = argparse.ArgumentParser(description="Validate Phase 1 Implementation")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL for the API (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    validator = Phase1Validator(base_url=args.url)
    results = validator.run_all_tests()

    # Save results to file
    results_file = "phase1_validation_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"\nDetailed results saved to: {results_file}")

    return results["success_rate"] == 100.0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)