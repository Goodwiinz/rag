"""
Performance and Load Testing Scenarios
Uses Locust to simulate high-load scenarios for document upload and processing
"""

from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask
import json
import random
import time
import io
import uuid
from datetime import datetime
from typing import Dict, List, Any

# Import test utilities
from tests.performance.utils.data_generator import (
    generate_test_file_content,
    generate_random_metadata,
    get_random_file_type
)
from tests.performance.utils.metrics_collector import (
    collect_performance_metrics,
    record_timing_metric,
    record_error_metric
)


class DocumentUploadUser(HttpUser):
    """
    Simulates a user uploading documents
    Tests document upload endpoints under various load conditions
    """

    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks

    def on_start(self):
        """Called when a simulated user starts"""
        # Authenticate user
        self.authenticate()
        self.organization_id = self.get_organization_id()
        self.uploaded_documents = []

    def authenticate(self):
        """Authenticate the simulated user"""
        credentials = {
            "email": f"user{random.randint(1, 1000)}@test.com",
            "password": "test123"
        }

        response = self.client.post("/api/v1/auth/login", json=credentials)
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        else:
            # Create new user if login fails
            self.create_user()
            self.authenticate()

    def create_user(self):
        """Create a new user for testing"""
        user_data = {
            "email": f"user{random.randint(1, 1000)}@test.com",
            "password": "test123",
            "full_name": f"Test User {random.randint(1, 1000)}",
            "role": "user"
        }

        response = self.client.post("/api/v1/auth/register", json=user_data)
        if response.status_code != 201:
            print(f"Failed to create user: {response.status_code}")

    def get_organization_id(self):
        """Get organization ID for the user"""
        response = self.client.get("/api/v1/users/me", headers=self.headers)
        if response.status_code == 200:
            return response.json()["organization_id"]
        return None

    @task(3)
    def upload_single_document(self):
        """Upload a single document - most common task"""
        file_type = get_random_file_type()
        file_content = generate_test_file_content(file_type, size_mb=random.uniform(0.5, 5))
        metadata = generate_random_metadata()

        # Prepare multipart form data
        files = {
            'file': (f'test_{uuid.uuid4().hex[:8]}.{file_type}', file_content, f'application/{file_type}')
        }

        data = {
            'title': f'Test Document {uuid.uuid4().hex[:8]}',
            'description': metadata['description'],
            'tags': ','.join(metadata['tags']),
            'is_public': str(random.choice([True, False])).lower(),
            'processing_priority': random.choice(['low', 'normal', 'high']),
            'enable_quality_check': str(random.choice([True, False])).lower(),
            'custom_metadata': json.dumps(metadata['custom'])
        }

        start_time = time.time()

        try:
            response = self.client.post(
                "/api/v2/documents/upload/single",
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {self.token}"}
            )

            end_time = time.time()
            upload_time = end_time - start_time

            if response.status_code == 200:
                result = response.json()
                self.uploaded_documents.append(result['document_id'])
                record_timing_metric('document_upload_success', upload_time, {
                    'file_size_mb': len(file_content) / (1024 * 1024),
                    'file_type': file_type,
                    'processing_priority': data['processing_priority']
                })
                print(f"Successfully uploaded document: {result['document_id']} in {upload_time:.2f}s")
            else:
                record_error_metric('document_upload_failed', response.status_code, {
                    'file_type': file_type,
                    'error_message': response.text[:200]
                })
                print(f"Upload failed: {response.status_code} - {response.text[:200]}")

        except Exception as e:
            end_time = time.time()
            upload_time = end_time - start_time
            record_error_metric('document_upload_exception', 500, {
                'exception': str(e)[:200],
                'upload_time': upload_time
            })
            print(f"Upload exception: {str(e)}")

    @task(2)
    def upload_batch_documents(self):
        """Upload multiple documents in batch"""
        num_files = random.randint(2, 5)
        files = []
        documents_data = []

        for i in range(num_files):
            file_type = get_random_file_type()
            file_content = generate_test_file_content(file_type, size_mb=random.uniform(0.5, 3))
            metadata = generate_random_metadata()

            files.append((
                f'batch_{uuid.uuid4().hex[:8]}_{i}.{file_type}',
                file_content,
                f'application/{file_type}'
            ))

            documents_data.append({
                'title': f'Batch Document {i} {uuid.uuid4().hex[:8]}',
                'description': metadata['description'],
                'tags': ','.join(metadata['tags']),
                'is_public': str(random.choice([True, False])).lower(),
                'processing_priority': random.choice(['low', 'normal', 'high']),
                'enable_quality_check': str(random.choice([True, False])).lower(),
                'custom_metadata': json.dumps(metadata['custom'])
            })

        start_time = time.time()

        try:
            # Simulate batch upload by multiple single uploads
            success_count = 0
            for i, file_tuple in enumerate(files):
                single_files = {'file': file_tuple}
                response = self.client.post(
                    "/api/v2/documents/upload/single",
                    files=single_files,
                    data=documents_data[i],
                    headers={"Authorization": f"Bearer {self.token}"}
                )

                if response.status_code == 200:
                    success_count += 1
                    result = response.json()
                    self.uploaded_documents.append(result['document_id'])

            end_time = time.time()
            batch_time = end_time - start_time

            if success_count == num_files:
                record_timing_metric('batch_upload_success', batch_time, {
                    'num_files': num_files,
                    'avg_file_size_mb': sum(len(f[1]) for f in files) / (num_files * 1024 * 1024)
                })
                print(f"Successfully uploaded batch of {num_files} documents in {batch_time:.2f}s")
            else:
                record_error_metric('batch_upload_partial', 206, {
                    'success_count': success_count,
                    'total_count': num_files,
                    'batch_time': batch_time
                })
                print(f"Partial batch upload: {success_count}/{num_files} successful")

        except Exception as e:
            end_time = time.time()
            batch_time = end_time - start_time
            record_error_metric('batch_upload_exception', 500, {
                'exception': str(e)[:200],
                'num_files': num_files,
                'batch_time': batch_time
            })
            print(f"Batch upload exception: {str(e)}")

    @task(1)
    def check_upload_progress(self):
        """Check upload progress for ongoing uploads"""
        if not self.uploaded_documents:
            return

        # Randomly check progress for one of the uploaded documents
        document_id = random.choice(self.uploaded_documents)

        start_time = time.time()

        try:
            response = self.client.get(
                f"/api/v2/documents/upload/progress/check/{document_id}",
                headers=self.headers
            )

            end_time = time.time()
            check_time = end_time - start_time

            if response.status_code == 200:
                record_timing_metric('progress_check_success', check_time)
            elif response.status_code == 404:
                # Document might be fully processed
                pass
            else:
                record_error_metric('progress_check_failed', response.status_code)

        except Exception as e:
            record_error_metric('progress_check_exception', 500, {
                'exception': str(e)[:200]
            })

    @task(1)
    def get_document_quality(self):
        """Get quality assessment for uploaded documents"""
        if not self.uploaded_documents:
            return

        document_id = random.choice(self.uploaded_documents)

        start_time = time.time()

        try:
            response = self.client.get(
                f"/api/v2/documents/upload/{document_id}/quality",
                headers=self.headers
            )

            end_time = time.time()
            quality_time = end_time - start_time

            if response.status_code == 200:
                record_timing_metric('quality_assessment_success', quality_time)
                quality_data = response.json()
                print(f"Quality score for {document_id}: {quality_data.get('overall_score', 'N/A')}")
            else:
                record_error_metric('quality_assessment_failed', response.status_code)

        except Exception as e:
            record_error_metric('quality_assessment_exception', 500, {
                'exception': str(e)[:200]
            })

    @task(2)
    def list_documents(self):
        """List documents - simulates browsing the document library"""
        params = {
            'page': random.randint(1, 5),
            'page_size': random.choice([10, 20, 50]),
            'search_term': random.choice(['', 'test', 'document', 'file']),
            'file_types': random.choice(['', 'pdf', 'txt', 'jpg']),
            'status': random.choice(['', 'indexed', 'processing', 'failed'])
        }

        start_time = time.time()

        try:
            response = self.client.get(
                "/api/v1/documents",
                params=params,
                headers=self.headers
            )

            end_time = time.time()
            list_time = end_time - start_time

            if response.status_code == 200:
                record_timing_metric('document_list_success', list_time, {
                    'page_size': params['page_size'],
                    'has_search': bool(params['search_term']),
                    'has_filters': bool(params['file_types'] or params['status'])
                })
            else:
                record_error_metric('document_list_failed', response.status_code)

        except Exception as e:
            record_error_metric('document_list_exception', 500, {
                'exception': str(e)[:200]
            })

    @task(1)
    def download_document(self):
        """Download a document - simulates document access"""
        if not self.uploaded_documents:
            return

        document_id = random.choice(self.uploaded_documents)

        start_time = time.time()

        try:
            response = self.client.get(
                f"/api/v1/documents/{document_id}/download",
                headers=self.headers
            )

            end_time = time.time()
            download_time = end_time - start_time

            if response.status_code == 200:
                record_timing_metric('document_download_success', download_time, {
                    'file_size_bytes': len(response.content)
                })
            else:
                record_error_metric('document_download_failed', response.status_code)

        except Exception as e:
            record_error_metric('document_download_exception', 500, {
                'exception': str(e)[:200]
            })

    @task(1)
    def delete_document(self):
        """Delete a document - cleanup operation"""
        if len(self.uploaded_documents) > 10:  # Cleanup when we have too many
            document_id = self.uploaded_documents.pop(0)  # Remove oldest

            start_time = time.time()

            try:
                response = self.client.delete(
                    f"/api/v1/documents/{document_id}",
                    headers=self.headers
                )

                end_time = time.time()
                delete_time = end_time - start_time

                if response.status_code == 200:
                    record_timing_metric('document_delete_success', delete_time)
                    print(f"Successfully deleted document: {document_id}")
                else:
                    record_error_metric('document_delete_failed', response.status_code)

            except Exception as e:
                record_error_metric('document_delete_exception', 500, {
                    'exception': str(e)[:200]
                })


class HighFrequencyUploader(HttpUser):
    """
    Simulates high-frequency upload scenarios
    Tests system limits and performance under extreme load
    """

    wait_time = between(0.1, 1)  # Very short wait time

    def on_start(self):
        self.authenticate()
        self.organization_id = self.get_organization_id()

    def authenticate(self):
        """Quick authentication for high-frequency testing"""
        credentials = {
            "email": f"hf_user{random.randint(1, 100)}@test.com",
            "password": "test123"
        }

        response = self.client.post("/api/v1/auth/login", json=credentials)
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.create_user()
            self.authenticate()

    def create_user(self):
        """Create user for high-frequency testing"""
        user_data = {
            "email": f"hf_user{random.randint(1, 100)}@test.com",
            "password": "test123",
            "full_name": f"HF Test User {random.randint(1, 100)}",
            "role": "user"
        }
        self.client.post("/api/v1/auth/register", json=user_data)

    def get_organization_id(self):
        """Get organization ID"""
        response = self.client.get("/api/v1/users/me", headers=self.headers)
        if response.status_code == 200:
            return response.json()["organization_id"]
        return None

    @task(10)
    def rapid_small_upload(self):
        """Rapid small file uploads to test system limits"""
        file_content = generate_test_file_content('txt', size_mb=random.uniform(0.1, 0.5))

        files = {
            'file': (f'rapid_{uuid.uuid4().hex[:6]}.txt', file_content, 'text/plain')
        }

        data = {
            'title': f'Rapid Upload {uuid.uuid4().hex[:6]}',
            'description': 'High frequency test upload',
            'tags': 'test,rapid,hf',
            'is_public': 'false',
            'processing_priority': 'normal',
            'enable_quality_check': 'false',
            'custom_metadata': '{}'
        }

        start_time = time.time()

        try:
            response = self.client.post(
                "/api/v2/documents/upload/single",
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {self.token}"}
            )

            end_time = time.time()
            upload_time = end_time - start_time

            if response.status_code == 200:
                record_timing_metric('rapid_upload_success', upload_time)
            else:
                record_error_metric('rapid_upload_failed', response.status_code)

        except Exception as e:
            record_error_metric('rapid_upload_exception', 500, {
                'exception': str(e)[:100]
            })


class AdminUser(HttpUser):
    """
    Simulates admin user performing administrative tasks
    Tests admin-specific endpoints and bulk operations
    """

    wait_time = between(5, 15)

    def on_start(self):
        self.authenticate_as_admin()

    def authenticate_as_admin(self):
        """Authenticate as admin user"""
        credentials = {
            "email": "admin@test.com",
            "password": "admin123"
        }

        response = self.client.post("/api/v1/auth/login", json=credentials)
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        else:
            print("Failed to authenticate as admin")

    @task(3)
    def get_system_metrics(self):
        """Get system performance metrics"""
        start_time = time.time()

        try:
            response = self.client.get(
                "/api/v1/admin/metrics",
                headers=self.headers
            )

            end_time = time.time()
            metrics_time = end_time - start_time

            if response.status_code == 200:
                record_timing_metric('admin_metrics_success', metrics_time)
            else:
                record_error_metric('admin_metrics_failed', response.status_code)

        except Exception as e:
            record_error_metric('admin_metrics_exception', 500)

    @task(2)
    def get_user_statistics(self):
        """Get user and document statistics"""
        start_time = time.time()

        try:
            response = self.client.get(
                "/api/v1/admin/statistics",
                headers=self.headers
            )

            end_time = time.time()
            stats_time = end_time - start_time

            if response.status_code == 200:
                record_timing_metric('admin_statistics_success', stats_time)
            else:
                record_error_metric('admin_statistics_failed', response.status_code)

        except Exception as e:
            record_error_metric('admin_statistics_exception', 500)

    @task(1)
    def manage_processing_queue(self):
        """Check and manage processing queue"""
        start_time = time.time()

        try:
            response = self.client.get(
                "/api/v1/admin/processing-queue",
                headers=self.headers
            )

            end_time = time.time()
            queue_time = end_time - start_time

            if response.status_code == 200:
                record_timing_metric('admin_queue_check_success', queue_time)
            else:
                record_error_metric('admin_queue_check_failed', response.status_code)

        except Exception as e:
            record_error_metric('admin_queue_check_exception', 500)

    @task(1)
    def system_health_check(self):
        """Perform system health check"""
        start_time = time.time()

        try:
            response = self.client.get(
                "/api/v1/health",
                headers=self.headers
            )

            end_time = time.time()
            health_time = end_time - start_time

            if response.status_code == 200:
                record_timing_metric('system_health_success', health_time)
            else:
                record_error_metric('system_health_failed', response.status_code)

        except Exception as e:
            record_error_metric('system_health_exception', 500)


# Event handlers for performance monitoring
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, **kwargs):
    """
    Global request event handler for performance monitoring
    """
    if request_type == 'HTTP':
        # Record all HTTP request metrics
        collect_performance_metrics({
            'timestamp': datetime.now().isoformat(),
            'request_type': request_type,
            'name': name,
            'response_time': response_time,
            'response_length': response_length,
            'status_code': response.status_code if response else 0,
            'success': response.status_code < 400 if response else False
        })


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print(f"Starting load test at {datetime.now()}")
    print(f"Target host: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print(f"Load test completed at {datetime.now()}")

    # Print summary statistics
    stats = environment.stats
    print(f"\n=== Performance Test Summary ===")
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Total failures: {stats.total.num_failures}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"Min response time: {stats.total.min_response_time:.2f}ms")
    print(f"Max response time: {stats.total.max_response_time:.2f}ms")
    print(f"Requests per second: {stats.total.current_rps:.2f}")

    # Print endpoint-specific stats
    print(f"\n=== Endpoint Performance ===")
    for endpoint_name, endpoint_stats in stats.requests.items():
        if endpoint_stats.num_requests > 0:
            print(f"{endpoint_name}:")
            print(f"  Requests: {endpoint_stats.num_requests}")
            print(f"  Failures: {endpoint_stats.num_failures}")
            print(f"  Avg response time: {endpoint_stats.avg_response_time:.2f}ms")
            print(f"  Max response time: {endpoint_stats.max_response_time:.2f}ms")


if __name__ == "__main__":
    """
    Example usage:

    # Run with different user distributions
    locust -f test_load_scenarios.py --host=http://localhost:8000 \
           --users=100 --spawn-rate=10 --run-time=5m \
           --html=reports/performance_test_report.html

    # High-frequency test
    locust -f test_load_scenarios.py --host=http://localhost:8000 \
           -c HighFrequencyUploader --users=50 --spawn-rate=20 \
           --run-time=2m --html=reports/high_frequency_test.html

    # Admin operations test
    locust -f test_load_scenarios.py --host=http://localhost:8000 \
           -c AdminUser --users=5 --spawn-rate=1 \
           --run-time=10m --html=reports/admin_test.html
    """
    pass