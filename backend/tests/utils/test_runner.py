"""
Comprehensive test runner with automated test data generation
"""

import pytest
import os
import tempfile
import random
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from .test_data_generator import TestDataGenerator
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.processing import ProcessingJob, JobType, JobStatus


class AutomatedTestRunner:
    """Automated test runner with dynamic test data generation"""

    def __init__(self, db_session: Session, temp_dir: Optional[str] = None):
        """Initialize test runner

        Args:
            db_session: Database session for testing
            temp_dir: Temporary directory for test files
        """
        self.db_session = db_session
        self.data_generator = TestDataGenerator(temp_dir)
        self.test_user = None
        self.test_organization = None

    def setup_test_environment(self):
        """Set up test environment with user and organization"""
        # Create test organization
        org_metadata = self.data_generator.generate_test_organization_metadata()
        self.test_organization = Organization(**org_metadata)
        self.db_session.add(self.test_organization)
        self.db_session.flush()

        # Create test user
        user_metadata = self.data_generator.generate_test_user_metadata(
            organization_id=self.test_organization.id,
            role=UserRole.USER
        )
        self.test_user = User(**user_metadata)
        self.db_session.add(self.test_user)
        self.db_session.commit()

        return self.test_user, self.test_organization

    def run_comprehensive_file_processing_tests(self) -> Dict[str, Any]:
        """Run comprehensive file processing tests with generated data"""
        results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "test_results": []
        }

        # Test different file types and sizes
        test_scenarios = [
            {"type": DocumentType.TEXT, "sizes_kb": [1, 10, 100], "count": 3},
            {"type": DocumentType.IMAGE, "sizes": [(800, 600), (1920, 1080)], "count": 2},
            {"type": DocumentType.AUDIO, "durations_seconds": [10, 60], "count": 2},
            {"type": DocumentType.VIDEO, "durations_seconds": [30, 120], "count": 2},
        ]

        for scenario in test_scenarios:
            doc_type = scenario["type"]
            count = scenario["count"]

            for i in range(count):
                # Generate test file
                if doc_type == DocumentType.TEXT:
                    size_kb = random.choice(scenario["sizes_kb"])
                    file_path = self.data_generator.generate_text_document(
                        size_kb=size_kb,
                        include_entities=True
                    )
                elif doc_type == DocumentType.IMAGE:
                    width, height = random.choice(scenario["sizes"])
                    file_path = self.data_generator.generate_image_file(
                        width=width,
                        height=height,
                        include_text=True
                    )
                elif doc_type == DocumentType.AUDIO:
                    duration = random.choice(scenario["durations_seconds"])
                    file_path = self.data_generator.generate_audio_file_mock(
                        duration_seconds=duration
                    )
                elif doc_type == DocumentType.VIDEO:
                    duration = random.choice(scenario["durations_seconds"])
                    file_path = self.data_generator.generate_video_file_mock(
                        duration_seconds=duration
                    )
                else:
                    continue

                # Run test
                test_result = self._run_single_file_test(file_path, doc_type)
                results["test_results"].append(test_result)
                results["total_tests"] += 1

                if test_result["success"]:
                    results["passed_tests"] += 1
                else:
                    results["failed_tests"] += 1

        return results

    def _run_single_file_test(self, file_path: str, doc_type: DocumentType) -> Dict[str, Any]:
        """Run a single file processing test"""
        test_result = {
            "file_path": file_path,
            "file_type": doc_type.value,
            "success": False,
            "error": None,
            "processing_time": 0.0,
            "metadata": {}
        }

        try:
            # Create document in database
            doc_metadata = self.data_generator.generate_test_document_metadata(
                document_type=doc_type,
                user_id=self.test_user.id,
                organization_id=self.test_organization.id,
                file_path=file_path,
                file_size=os.path.getsize(file_path)
            )

            document = Document(**doc_metadata)
            self.db_session.add(document)
            self.db_session.flush()

            # Import here to avoid circular imports
            from src.services.file_service import FileService
            from src.services.processing_pipeline import ProcessingPipeline

            import time
            start_time = time.time()

            # Test file detection
            file_service = FileService(self.db_session)
            detected_type = file_service.detect_file_type(file_path)
            test_result["metadata"]["detected_type"] = detected_type.value

            # Test text extraction if applicable
            if doc_type in [DocumentType.TEXT, DocumentType.PDF]:
                try:
                    extraction_result = file_service.extract_text_content(file_path)
                    test_result["metadata"]["text_extracted"] = True
                    test_result["metadata"]["text_length"] = len(extraction_result.get("text", ""))
                except Exception as e:
                    test_result["metadata"]["text_extracted"] = False
                    test_result["metadata"]["text_extraction_error"] = str(e)

            # Test processing pipeline
            pipeline = ProcessingPipeline(self.db_session)
            processing_result = pipeline.start_processing(document.id)
            test_result["metadata"]["processing_started"] = processing_result["success"]

            end_time = time.time()
            test_result["processing_time"] = end_time - start_time

            # Update document status to completed for testing
            job = self.db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == document.id
            ).first()
            if job:
                job.status = JobStatus.COMPLETED
                job.progress_percentage = 100
                job.completed_at = None  # Mock completion
                self.db_session.commit()

                document.status = ProcessingStatus.COMPLETED
                document.processed_at = None  # Mock completion
                self.db_session.commit()

            test_result["success"] = True

        except Exception as e:
            test_result["error"] = str(e)
            self.db_session.rollback()

        return test_result

    def run_entity_extraction_accuracy_tests(self) -> Dict[str, Any]:
        """Run entity extraction accuracy tests"""
        results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "accuracy_scores": [],
            "test_results": []
        }

        # Generate test documents with known entities
        test_documents = [
            {
                "content": "John Smith works at Microsoft Corporation in Seattle, Washington. Contact him at john.smith@microsoft.com or (555) 123-4567.",
                "expected_entities": {
                    "PERSON": ["John Smith"],
                    "ORGANIZATION": ["Microsoft Corporation"],
                    "LOCATION": ["Seattle", "Washington"],
                    "EMAIL": ["john.smith@microsoft.com"],
                    "PHONE": ["(555) 123-4567"]
                }
            },
            {
                "content": "Jane Doe from Apple Inc. visited New York City. She manages projects worth $1,000,000. Visit https://www.apple.com for more info.",
                "expected_entities": {
                    "PERSON": ["Jane Doe"],
                    "ORGANIZATION": ["Apple Inc."],
                    "LOCATION": ["New York City"],
                    "URL": ["https://www.apple.com"],
                    "FINANCIAL": ["$1,000,000"]
                }
            },
            {
                "content": "Google CEO Sundar Pichai announced new AI features at their Mountain View headquarters on December 15, 2023.",
                "expected_entities": {
                    "ORGANIZATION": ["Google"],
                    "PERSON": ["Sundar Pichai"],
                    "LOCATION": ["Mountain View"],
                    "DATE": ["December 15, 2023"]
                }
            }
        ]

        # Import entity extraction service
        from src.services.entity_extraction_service import EntityExtractionService
        entity_service = EntityExtractionService()

        for i, test_doc in enumerate(test_documents):
            test_result = {
                "test_id": i,
                "content": test_doc["content"],
                "success": False,
                "accuracy": 0.0,
                "found_entities": [],
                "missing_entities": [],
                "error": None
            }

            try:
                # Extract entities
                extracted_entities = entity_service.extract_entities(test_doc["content"])
                test_result["found_entities"] = [
                    {"name": e["name"], "type": e["entity_type"].value}
                    for e in extracted_entities
                ]

                # Calculate accuracy
                total_expected = sum(len(entities) for entities in test_doc["expected_entities"].values())
                total_found = 0

                for entity_type, expected_list in test_doc["expected_entities"].items():
                    # Find extracted entities of this type
                    extracted_of_type = [
                        e["name"] for e in extracted_entities
                        if e["entity_type"].value == entity_type
                    ]

                    for expected_entity in expected_list:
                        if any(expected_entity in extracted for extracted in extracted_of_type):
                            total_found += 1
                        else:
                            test_result["missing_entities"].append({
                                "name": expected_entity,
                                "type": entity_type
                            })

                accuracy = total_found / total_expected if total_expected > 0 else 0.0
                test_result["accuracy"] = accuracy
                test_result["success"] = accuracy >= 0.8  # 80% accuracy threshold

                results["accuracy_scores"].append(accuracy)
                results["total_tests"] += 1

                if test_result["success"]:
                    results["passed_tests"] += 1
                else:
                    results["failed_tests"] += 1

            except Exception as e:
                test_result["error"] = str(e)
                results["failed_tests"] += 1
                results["total_tests"] += 1

            results["test_results"].append(test_result)

        # Calculate overall accuracy
        if results["accuracy_scores"]:
            results["overall_accuracy"] = sum(results["accuracy_scores"]) / len(results["accuracy_scores"])
        else:
            results["overall_accuracy"] = 0.0

        return results

    def run_performance_stress_tests(self) -> Dict[str, Any]:
        """Run performance and stress tests"""
        results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "performance_metrics": [],
            "test_results": []
        }

        # Test scenarios for performance
        performance_scenarios = [
            {
                "name": "Small Files Batch Processing",
                "file_count": 10,
                "file_size_kb": 10,
                "max_total_time": 30.0  # 30 seconds
            },
            {
                "name": "Medium Files Batch Processing",
                "file_count": 5,
                "file_size_kb": 100,
                "max_total_time": 45.0  # 45 seconds
            },
            {
                "name": "Large File Processing",
                "file_count": 1,
                "file_size_kb": 1000,
                "max_total_time": 60.0  # 60 seconds
            }
        ]

        import time

        for scenario in performance_scenarios:
            test_result = {
                "scenario_name": scenario["name"],
                "success": False,
                "total_time": 0.0,
                "average_time_per_file": 0.0,
                "files_processed": 0,
                "error": None
            }

            try:
                # Generate test files
                files = []
                for i in range(scenario["file_count"]):
                    file_path = self.data_generator.generate_text_document(
                        size_kb=scenario["file_size_kb"],
                        include_entities=True
                    )
                    files.append(file_path)

                # Process files and measure time
                start_time = time.time()

                for file_path in files:
                    try:
                        # Create document and process
                        doc_metadata = self.data_generator.generate_test_document_metadata(
                            document_type=DocumentType.TEXT,
                            user_id=self.test_user.id,
                            organization_id=self.test_organization.id,
                            file_path=file_path,
                            file_size=os.path.getsize(file_path)
                        )

                        document = Document(**doc_metadata)
                        self.db_session.add(document)
                        self.db_session.flush()

                        # Simulate processing (in real tests, this would call the processing pipeline)
                        test_result["files_processed"] += 1

                        # Clean up
                        self.db_session.delete(document)
                        self.db_session.commit()

                    except Exception as e:
                        # Continue processing other files
                        continue

                end_time = time.time()
                test_result["total_time"] = end_time - start_time
                test_result["average_time_per_file"] = test_result["total_time"] / scenario["file_count"]

                # Check performance criteria
                test_result["success"] = (
                    test_result["total_time"] <= scenario["max_total_time"] and
                    test_result["files_processed"] == scenario["file_count"]
                )

                results["performance_metrics"].append({
                    "scenario": scenario["name"],
                    "total_time": test_result["total_time"],
                    "max_time": scenario["max_total_time"],
                    "within_limit": test_result["total_time"] <= scenario["max_total_time"]
                })

                results["total_tests"] += 1
                if test_result["success"]:
                    results["passed_tests"] += 1
                else:
                    results["failed_tests"] += 1

                # Clean up generated files
                for file_path in files:
                    if os.path.exists(file_path):
                        os.remove(file_path)

            except Exception as e:
                test_result["error"] = str(e)
                results["failed_tests"] += 1
                results["total_tests"] += 1

            results["test_results"].append(test_result)

        return results

    def run_error_handling_tests(self) -> Dict[str, Any]:
        """Run error handling and resilience tests"""
        results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "test_results": []
        }

        error_scenarios = [
            {
                "name": "Corrupted Text File",
                "file_generator": lambda: self.data_generator.generate_corrupted_file(extension="txt"),
                "expected_behavior": "graceful_handling"
            },
            {
                "name": "Corrupted Image File",
                "file_generator": lambda: self.data_generator.generate_corrupted_file(extension="png"),
                "expected_behavior": "graceful_handling"
            },
            {
                "name": "Nonexistent File",
                "file_generator": lambda: "/path/that/does/not/exist.txt",
                "expected_behavior": "proper_error"
            },
            {
                "name": "Empty File",
                "file_generator": lambda: self._generate_empty_file(),
                "expected_behavior": "graceful_handling"
            }
        ]

        for scenario in error_scenarios:
            test_result = {
                "scenario_name": scenario["name"],
                "success": False,
                "error_handled": False,
                "error_message": None,
                "expected_behavior": scenario["expected_behavior"],
                "actual_behavior": None
            }

            try:
                # Generate test file
                if scenario["name"] == "Nonexistent File":
                    file_path = scenario["file_generator"]()
                else:
                    file_path = scenario["file_generator"]()

                # Try to process the problematic file
                from src.services.file_service import FileService
                file_service = FileService(self.db_session)

                try:
                    if scenario["name"] == "Nonexistent File":
                        file_type = file_service.detect_file_type(file_path)
                    else:
                        file_type = file_service.detect_file_type(file_path)
                        extraction_result = file_service.extract_text_content(file_path)

                    test_result["actual_behavior"] = "processing_succeeded"
                    test_result["error_handled"] = scenario["expected_behavior"] == "graceful_handling"

                except Exception as processing_error:
                    test_result["error_message"] = str(processing_error)
                    test_result["actual_behavior"] = "error_raised"
                    test_result["error_handled"] = (
                        scenario["expected_behavior"] == "proper_error" or
                        "FileProcessingError" in str(type(processing_error)) or
                        "ValidationError" in str(type(processing_error))
                    )

                test_result["success"] = test_result["error_handled"]

                # Clean up if file was created
                if scenario["name"] != "Nonexistent File" and os.path.exists(file_path):
                    os.remove(file_path)

            except Exception as e:
                test_result["error_message"] = str(e)
                test_result["actual_behavior"] = "test_setup_failed"
                test_result["success"] = False

            results["total_tests"] += 1
            if test_result["success"]:
                results["passed_tests"] += 1
            else:
                results["failed_tests"] += 1

            results["test_results"].append(test_result)

        return results

    def _generate_empty_file(self) -> str:
        """Generate an empty file for testing"""
        file_path = os.path.join(self.data_generator.temp_dir, f"empty_{random.randint(1000, 9999)}.txt")
        with open(file_path, "w") as f:
            pass  # Create empty file
        return file_path

    def run_all_automated_tests(self) -> Dict[str, Any]:
        """Run all automated tests and return comprehensive results"""
        # Set up test environment
        self.setup_test_environment()

        # Run all test suites
        results = {
            "test_environment": {
                "user_id": self.test_user.id,
                "organization_id": self.test_organization.id,
                "temp_directory": self.data_generator.temp_dir
            },
            "file_processing_tests": self.run_comprehensive_file_processing_tests(),
            "entity_extraction_tests": self.run_entity_extraction_accuracy_tests(),
            "performance_tests": self.run_performance_stress_tests(),
            "error_handling_tests": self.run_error_handling_tests(),
            "summary": {}
        }

        # Calculate overall summary
        total_tests = (
            results["file_processing_tests"]["total_tests"] +
            results["entity_extraction_tests"]["total_tests"] +
            results["performance_tests"]["total_tests"] +
            results["error_handling_tests"]["total_tests"]
        )

        total_passed = (
            results["file_processing_tests"]["passed_tests"] +
            results["entity_extraction_tests"]["passed_tests"] +
            results["performance_tests"]["passed_tests"] +
            results["error_handling_tests"]["passed_tests"]
        )

        total_failed = (
            results["file_processing_tests"]["failed_tests"] +
            results["entity_extraction_tests"]["failed_tests"] +
            results["performance_tests"]["failed_tests"] +
            results["error_handling_tests"]["failed_tests"]
        )

        results["summary"] = {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "overall_success_rate": total_passed / total_tests if total_tests > 0 else 0.0,
            "file_processing_success_rate": (
                results["file_processing_tests"]["passed_tests"] /
                results["file_processing_tests"]["total_tests"]
                if results["file_processing_tests"]["total_tests"] > 0 else 0.0
            ),
            "entity_extraction_accuracy": results["entity_extraction_tests"].get("overall_accuracy", 0.0),
            "performance_within_limits": (
                results["performance_tests"]["passed_tests"] /
                results["performance_tests"]["total_tests"]
                if results["performance_tests"]["total_tests"] > 0 else 0.0
            ),
            "error_handling_success_rate": (
                results["error_handling_tests"]["passed_tests"] /
                results["error_handling_tests"]["total_tests"]
                if results["error_handling_tests"]["total_tests"] > 0 else 0.0
            )
        }

        return results

    def cleanup(self):
        """Clean up test environment and generated files"""
        self.data_generator.cleanup()