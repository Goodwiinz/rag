"""
Test Data Management and Cleanup Utilities

This module provides utilities for managing test data, database cleanup,
and test environment isolation for WebSocket and API testing.
"""

import asyncio
import uuid
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Set, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import random
import string

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, delete, and_, or_
from sqlalchemy.orm import sessionmaker

from backend.src.core.database import get_async_session
from backend.src.models.websocket_status import (
    WebSocketConnection,
    StatusUpdate,
    ConnectionEvent,
    NotificationTemplate
)
from backend.src.models.user import User
from backend.src.models.organization import Organization
from backend.src.models.document import Document


@dataclass
class TestDataConfiguration:
    """Configuration for test data generation"""
    user_count: int = 10
    organization_count: int = 3
    document_count: int = 50
    connection_count: int = 20
    status_update_count: int = 100
    connection_event_count: int = 200

    # Data retention policies
    cleanup_after_hours: int = 24
    isolate_per_test: bool = True

    # Randomization options
    randomize_timestamps: bool = True
    randomize_data: bool = True

    # Performance options
    batch_size: int = 100
    parallel_workers: int = 4


@dataclass
class TestDataSet:
    """Container for generated test data"""
    users: List[Dict[str, Any]] = field(default_factory=list)
    organizations: List[Dict[str, Any]] = field(default_factory=list)
    documents: List[Dict[str, Any]] = field(default_factory=list)
    connections: List[Dict[str, Any]] = field(default_factory=list)
    status_updates: List[Dict[str, Any]] = field(default_factory=list)
    connection_events: List[Dict[str, Any]] = field(default_factory=list)
    tokens: Dict[str, str] = field(default_factory=dict)  # user_id -> token

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    test_run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config: TestDataConfiguration = field(default_factory=TestDataConfiguration)


class TestDataGenerator:
    """Generates realistic test data for WebSocket and API testing"""

    def __init__(self, config: TestDataConfiguration = None):
        self.config = config or TestDataConfiguration()
        self.logger = logging.getLogger(__name__)

        # Sample data for generation
        self.first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emma", "Robert", "Lisa", "James", "Mary"]
        self.last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        self.domains = ["example.com", "test.org", "demo.net", "sample.co", "mock.io"]
        self.document_titles = [
            "Machine Learning Fundamentals",
            "Deep Neural Networks",
            "Natural Language Processing",
            "Computer Vision Applications",
            "Reinforcement Learning",
            "Data Science Best Practices",
            "Algorithm Design Patterns",
            "Database Optimization",
            "Cloud Computing Architecture",
            "DevOps Implementation Guide"
        ]

    def generate_users(self, count: int = None) -> List[Dict[str, Any]]:
        """Generate test user data"""
        count = count or self.config.user_count
        users = []

        for i in range(count):
            first_name = random.choice(self.first_names)
            last_name = random.choice(self.last_names)

            user = {
                "id": str(uuid.uuid4()),
                "email": f"{first_name.lower()}.{last_name.lower()}{i}@{random.choice(self.domains)}",
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
                "is_verified": True,
                "created_at": self._random_timestamp(days_back=365),
                "updated_at": self._random_timestamp(days_back=30),
                "last_login": self._random_timestamp(days_back=7),
                "role": random.choice(["user", "admin", "lab_admin"]),
                "preferences": {
                    "theme": random.choice(["light", "dark"]),
                    "notifications": random.choice([True, False]),
                    "language": random.choice(["en", "es", "fr"])
                }
            }
            users.append(user)

        return users

    def generate_organizations(self, count: int = None, users: List[Dict] = None) -> List[Dict[str, Any]]:
        """Generate test organization data"""
        count = count or self.config.organization_count
        users = users or self.generate_users()
        organizations = []

        org_names = [
            "TechCorp Solutions",
            "DataScience Inc",
            "CloudTech Systems",
            "AI Research Labs",
            "Enterprise Analytics",
            "Machine Learning Co",
            "Neural Networks Ltd",
            "BigData Solutions",
            "DevOps Enterprises",
            "Security First Inc"
        ]

        for i in range(count):
            org_name = random.choice(org_names) + f" {i+1}"

            org = {
                "id": str(uuid.uuid4()),
                "name": org_name,
                "slug": org_name.lower().replace(" ", "-").replace(".", ""),
                "domain": f"org{i+1}.{random.choice(self.domains)}",
                "created_at": self._random_timestamp(days_back=365),
                "updated_at": self._random_timestamp(days_back=30),
                "is_active": True,
                "plan": random.choice(["free", "pro", "enterprise"]),
                "max_users": random.choice([5, 10, 25, 100, 1000]),
                "settings": {
                    "allow_public_sharing": random.choice([True, False]),
                    "require_2fa": random.choice([True, False]),
                    "data_retention_days": random.choice([30, 90, 365, 1095])
                }
            }
            organizations.append(org)

        return organizations

    def generate_documents(self, count: int = None, users: List[Dict] = None) -> List[Dict[str, Any]]:
        """Generate test document data"""
        count = count or self.config.document_count
        users = users or self.generate_users()
        documents = []

        file_types = ["pdf", "txt", "docx", "pptx", "xlsx"]
        processing_statuses = ["pending", "processing", "completed", "failed"]

        for i in range(count):
            user = random.choice(users)
            title_base = random.choice(self.document_titles)

            doc = {
                "id": str(uuid.uuid4()),
                "title": f"{title_base} - Part {i//len(self.document_titles) + 1}",
                "description": f"Test document for {title_base}",
                "file_name": f"{title_base.lower().replace(' ', '_')}_{i+1}.{random.choice(file_types)}",
                "file_type": random.choice(file_types),
                "file_size": random.randint(1024, 50 * 1024 * 1024),  # 1KB to 50MB
                "mime_type": random.choice([
                    "application/pdf",
                    "text/plain",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ]),
                "owner_id": user["id"],
                "organization_id": user.get("organization_id", str(uuid.uuid4())),
                "status": random.choice(processing_statuses),
                "processing_progress": random.randint(0, 100) if random.choice(processing_statuses) == "processing" else (100 if random.choice(processing_statuses) == "completed" else 0),
                "created_at": self._random_timestamp(days_back=30),
                "updated_at": self._random_timestamp(days_back=1),
                "tags": random.sample([
                    "machine learning", "ai", "data science", "research", "documentation",
                    "tutorial", "guide", "manual", "specification", "report"
                ], k=random.randint(1, 4)),
                "metadata": {
                    "page_count": random.randint(1, 100) if random.choice([True, False]) else None,
                    "word_count": random.randint(100, 50000) if random.choice([True, False]) else None,
                    "language": random.choice(["en", "es", "fr", "de", "zh"]),
                    "author": f"{user['first_name']} {user['last_name']}",
                    "subject": random.choice(["Technical", "Research", "Tutorial", "Documentation", "Report"])
                }
            }
            documents.append(doc)

        return documents

    def generate_websocket_connections(self, count: int = None, users: List[Dict] = None) -> List[Dict[str, Any]]:
        """Generate test WebSocket connection data"""
        count = count or self.config.connection_count
        users = users or self.generate_users()
        connections = []

        client_types = ["web", "mobile", "desktop", "api"]
        connection_statuses = ["connected", "disconnected", "error", "timeout"]

        for i in range(count):
            user = random.choice(users)

            conn = {
                "id": str(uuid.uuid4()),
                "user_id": user["id"],
                "organization_id": user.get("organization_id", str(uuid.uuid4())),
                "session_id": str(uuid.uuid4()),
                "connection_status": random.choice(connection_statuses),
                "connected_at": self._random_timestamp(days_back=1),
                "last_heartbeat": self._random_timestamp(days_back=0.1),  # Recent
                "disconnected_at": self._random_timestamp(days_back=0.01) if random.choice([True, False]) else None,
                "user_agent": random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    "TestClient/1.0 (WebSocket Testing)"
                ]),
                "ip_address": f"192.168.1.{random.randint(1, 254)}",
                "client_type": random.choice(client_types),
                "client_version": f"1.{random.randint(0, 5)}.{random.randint(0, 99)}",
                "subscription_channels": random.sample([
                    "document_processing", "job_status", "system_events",
                    "notifications", "search_updates", "user_activity"
                ], k=random.randint(0, 4)),
                "message_filter": {
                    "event_types": random.sample([
                        "document_uploaded", "job_completed", "system_alert",
                        "user_login", "search_performed", "error_occurred"
                    ], k=random.randint(1, 3)),
                    "priority": random.choice(["low", "normal", "high"])
                } if random.choice([True, False]) else None,
                "messages_sent": random.randint(0, 1000),
                "messages_received": random.randint(0, 1000),
                "bytes_sent": random.randint(1024, 10 * 1024 * 1024),
                "bytes_received": random.randint(1024, 10 * 1024 * 1024),
                "connection_duration_seconds": random.randint(60, 7200),  # 1 minute to 2 hours
                "average_latency_ms": random.uniform(10, 500),
                "error_count": random.randint(0, 10),
                "last_error": random.choice([
                    None,
                    "Connection timeout",
                    "Message send failed",
                    "Authentication error",
                    "Rate limit exceeded"
                ]),
                "last_error_at": self._random_timestamp(days_back=0.01) if random.choice([True, False]) else None,
                "reconnect_attempts": random.randint(0, 5),
                "max_reconnect_attempts": random.choice([3, 5, 10])
            }
            connections.append(conn)

        return connections

    def generate_status_updates(self, count: int = None, connections: List[Dict] = None) -> List[Dict[str, Any]]:
        """Generate test status update data"""
        count = count or self.config.status_update_count
        connections = connections or self.generate_websocket_connections()
        status_updates = []

        update_types = [
            "document_processing", "job_status", "system_status",
            "user_notification", "quota_alert", "evaluation_result",
            "search_progress", "batch_operation"
        ]
        priorities = ["low", "normal", "high", "critical"]
        delivery_statuses = ["pending", "sent", "delivered", "read", "acknowledged", "failed"]

        for i in range(count):
            connection = random.choice(connections)
            update_type = random.choice(update_types)

            update = {
                "id": str(uuid.uuid4()),
                "connection_id": connection["id"],
                "update_type": update_type,
                "priority": random.choice(priorities),
                "title": self._generate_title_for_update_type(update_type),
                "message": self._generate_message_for_update_type(update_type),
                "update_data": self._generate_update_data_for_type(update_type),
                "progress_percentage": random.randint(0, 100) if random.choice([True, False]) else None,
                "target_users": random.sample([conn["user_id"] for conn in connections], k=random.randint(1, 3)),
                "target_organizations": random.sample(list(set(conn.get("organization_id") for conn in connections)), k=random.randint(1, 2)),
                "broadcast_channel": random.choice(["global", "org", "user"]) if random.choice([True, False]) else None,
                "created_at": self._random_timestamp(days_back=1),
                "sent_at": self._random_timestamp(days_back=0.5) if random.choice([True, False]) else None,
                "delivered_at": self._random_timestamp(days_back=0.1) if random.choice([True, False]) else None,
                "read_at": self._random_timestamp(days_back=0.01) if random.choice([True, False]) else None,
                "acknowledged_at": self._random_timestamp(days_back=0.001) if random.choice([True, False]) else None,
                "delivery_status": random.choice(delivery_statuses),
                "delivery_attempts": random.randint(1, 5),
                "max_delivery_attempts": random.choice([3, 5]),
                "delivery_error": random.choice([
                    None,
                    "Connection lost",
                    "Rate limit exceeded",
                    "Message too large",
                    "Invalid recipient"
                ]) if random.choice([True, False]) else None,
                "expires_at": self._random_timestamp(days_forward=1) if random.choice([True, False]) else None,
                "requires_acknowledgment": random.choice([True, False]),
                "is_dismissible": random.choice([True, False]),
                "action_required": random.choice([True, False]),
                "action_url": f"https://example.com/action/{uuid.uuid4()}" if random.choice([True, False]) else None,
                "was_clicked": random.choice([True, False]),
                "clicked_at": self._random_timestamp(days_back=0.01) if random.choice([True, False]) else None,
                "user_response": {
                    "action": random.choice(["acknowledged", "dismissed", "snoozed"]),
                    "feedback": random.choice(["helpful", "not_helpful", "spam"]) if random.choice([True, False]) else None
                } if random.choice([True, False]) else None
            }
            status_updates.append(update)

        return status_updates

    def generate_connection_events(self, count: int = None, connections: List[Dict] = None) -> List[Dict[str, Any]]:
        """Generate test connection event data"""
        count = count or self.config.connection_event_count
        connections = connections or self.generate_websocket_connections()
        events = []

        event_types = ["connect", "disconnect", "error", "heartbeat", "message", "subscribe", "unsubscribe"]
        error_codes = ["E001", "E002", "E003", "TIMEOUT", "RATE_LIMIT", "AUTH_FAILED"]

        for i in range(count):
            connection = random.choice(connections)
            event_type = random.choice(event_types)

            event = {
                "connection_id": connection["id"],
                "event_type": event_type,
                "event_data": {
                    "message": f"{event_type.title()} event",
                    "details": {
                        "user_agent": connection.get("user_agent"),
                        "client_type": connection.get("client_type"),
                        "ip_address": connection.get("ip_address")
                    }
                } if random.choice([True, False]) else None,
                "event_timestamp": self._random_timestamp(days_back=0.1),
                "session_id": connection.get("session_id"),
                "client_info": {
                    "version": connection.get("client_version"),
                    "features": random.sample(["real_time", "notifications", "file_upload"], k=random.randint(1, 3))
                } if random.choice([True, False]) else None,
                "server_info": {
                    "instance_id": f"server-{random.randint(1, 10)}",
                    "region": random.choice(["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]),
                    "version": "2.1.0"
                } if random.choice([True, False]) else None,
                "latency_ms": random.uniform(10, 500) if random.choice([True, False]) else None,
                "message_size_bytes": random.randint(100, 10000) if event_type == "message" else None,
                "processing_time_ms": random.uniform(1, 100) if random.choice([True, False]) else None,
                "error_code": random.choice(error_codes) if event_type == "error" else None,
                "error_message": random.choice([
                    "Connection timeout",
                    "Invalid message format",
                    "Authentication failed",
                    "Rate limit exceeded"
                ]) if event_type == "error" else None,
                "error_stack": "Traceback (most recent call last): ..." if event_type == "error" and random.choice([True, False]) else None
            }
            events.append(event)

        return events

    def _random_timestamp(self, days_back: float = 0, days_forward: float = 0) -> datetime:
        """Generate random timestamp within specified range"""
        if days_back > 0:
            start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            end_date = datetime.now(timezone.utc)
        elif days_forward > 0:
            start_date = datetime.now(timezone.utc)
            end_date = datetime.now(timezone.utc) + timedelta(days=days_forward)
        else:
            start_date = datetime.now(timezone.utc) - timedelta(hours=1)
            end_date = datetime.now(timezone.utc)

        if self.config.randomize_timestamps:
            random_seconds = random.randint(0, int((end_date - start_date).total_seconds()))
            return start_date + timedelta(seconds=random_seconds)
        else:
            return start_date

    def _generate_title_for_update_type(self, update_type: str) -> str:
        """Generate appropriate title for update type"""
        title_templates = {
            "document_processing": [
                "Document Processing Started",
                "Document Processing Progress",
                "Document Processing Complete",
                "Document Processing Failed"
            ],
            "job_status": [
                "Job Status Update",
                "Job Completed Successfully",
                "Job Failed",
                "Job Progress"
            ],
            "system_status": [
                "System Health Alert",
                "Service Status Update",
                "Maintenance Notification",
                "Performance Alert"
            ],
            "user_notification": [
                "New Feature Available",
                "Account Update",
                "Security Notice",
                "Welcome Message"
            ],
            "quota_alert": [
                "Quota Warning",
                "Usage Limit Reached",
                "Billing Alert",
                "Resource Limit"
            ]
        }

        templates = title_templates.get(update_type, ["Status Update"])
        return random.choice(templates)

    def _generate_message_for_update_type(self, update_type: str) -> str:
        """Generate appropriate message for update type"""
        message_templates = {
            "document_processing": [
                "Your document is being processed and will be available shortly.",
                "Document processing has reached 50% completion.",
                "Document has been successfully processed and is ready for use.",
                "Document processing failed due to an unsupported file format."
            ],
            "job_status": [
                "Background job has been queued for processing.",
                "Job is currently running and making progress.",
                "Job completed successfully with all tasks finished.",
                "Job failed due to an error. Please check the logs."
            ],
            "system_status": [
                "All systems are operating normally.",
                "A service is experiencing degraded performance.",
                "Scheduled maintenance is coming up.",
                "Critical system alert requires attention."
            ]
        }

        templates = message_templates.get(update_type, ["Status update message"])
        return random.choice(templates)

    def _generate_update_data_for_type(self, update_type: str) -> Dict[str, Any]:
        """Generate appropriate data payload for update type"""
        base_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "websocket_test"
        }

        if update_type == "document_processing":
            return {
                **base_data,
                "document_id": str(uuid.uuid4()),
                "status": random.choice(["pending", "processing", "completed", "failed"]),
                "progress": random.randint(0, 100),
                "file_type": random.choice(["pdf", "txt", "docx"]),
                "file_size": random.randint(1024, 10 * 1024 * 1024)
            }
        elif update_type == "job_status":
            return {
                **base_data,
                "job_id": str(uuid.uuid4()),
                "job_type": random.choice(["batch_processing", "index_rebuild", "data_export"]),
                "total_items": random.randint(10, 1000),
                "processed_items": random.randint(0, 1000),
                "progress_percentage": random.randint(0, 100)
            }
        elif update_type == "system_status":
            return {
                **base_data,
                "service": random.choice(["database", "websocket_server", "vector_store"]),
                "status": random.choice(["healthy", "degraded", "unhealthy"]),
                "response_time_ms": random.randint(10, 1000),
                "uptime_percentage": round(random.uniform(95.0, 100.0), 2)
            }
        else:
            return base_data

    def generate_complete_dataset(self, config: TestDataConfiguration = None) -> TestDataSet:
        """Generate a complete test dataset"""
        config = config or self.config

        # Generate in dependency order
        users = self.generate_users(config.user_count)
        organizations = self.generate_organizations(config.organization_count, users)

        # Associate users with organizations
        for i, user in enumerate(users):
            user["organization_id"] = organizations[i % len(organizations)]["id"]

        documents = self.generate_documents(config.document_count, users)
        connections = self.generate_websocket_connections(config.connection_count, users)
        status_updates = self.generate_status_updates(config.status_update_count, connections)
        connection_events = self.generate_connection_events(config.connection_event_count, connections)

        # Generate authentication tokens
        tokens = {}
        for user in users:
            tokens[user["id"]] = self._generate_test_token(user)

        return TestDataSet(
            users=users,
            organizations=organizations,
            documents=documents,
            connections=connections,
            status_updates=status_updates,
            connection_events=connection_events,
            tokens=tokens,
            config=config
        )

    def _generate_test_token(self, user: Dict[str, Any]) -> str:
        """Generate a test JWT token for user"""
        # This is a simplified token generation for testing
        # In real implementation, use proper JWT library
        payload = {
            "sub": user["id"],
            "email": user["email"],
            "organization_id": user.get("organization_id"),
            "role": user.get("role", "user"),
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
        }

        # Simple encoding (not real JWT)
        token_data = json.dumps(payload)
        token_id = str(uuid.uuid4())

        return f"test_token_{token_id}_{hash(token_data) % 1000000}"


class TestDataManager:
    """Manages test data lifecycle including creation, cleanup, and isolation"""

    def __init__(self, config: TestDataConfiguration = None):
        self.config = config or TestDataConfiguration()
        self.generator = TestDataGenerator(config)
        self.logger = logging.getLogger(__name__)
        self.active_datasets: Dict[str, TestDataSet] = {}

    @asynccontextmanager
    async def isolated_test_environment(self, test_name: str = None):
        """Context manager for isolated test environment"""
        test_name = test_name or f"test_{uuid.uuid4().hex[:8]}"
        dataset_id = f"{test_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        try:
            # Create isolated dataset
            dataset = await self.create_isolated_dataset(dataset_id)
            self.active_datasets[dataset_id] = dataset

            yield dataset

        finally:
            # Cleanup isolated dataset
            await self.cleanup_dataset(dataset_id)
            if dataset_id in self.active_datasets:
                del self.active_datasets[dataset_id]

    async def create_isolated_dataset(self, dataset_id: str) -> TestDataSet:
        """Create isolated test dataset"""
        self.logger.info(f"Creating isolated dataset: {dataset_id}")

        # Generate data with isolation markers
        dataset = self.generator.generate_complete_dataset(self.config)

        # Add isolation markers
        isolation_marker = f"test_isolated_{dataset_id}"
        for user in dataset.users:
            user["email"] = user["email"].replace("@", f"+{isolation_marker}@")

        # Store in database if configured
        if self.config.isolate_per_test:
            await self._persist_dataset_to_database(dataset)

        self.logger.info(f"Created dataset {dataset_id}: "
                        f"{len(dataset.users)} users, {len(dataset.connections)} connections, "
                        f"{len(dataset.status_updates)} status updates")

        return dataset

    async def cleanup_dataset(self, dataset_id: str):
        """Clean up test dataset"""
        if dataset_id not in self.active_datasets:
            return

        dataset = self.active_datasets[dataset_id]
        self.logger.info(f"Cleaning up dataset: {dataset_id}")

        try:
            # Clean up database records
            if self.config.isolate_per_test:
                await self._cleanup_dataset_from_database(dataset)

            # Clean up any external resources
            await self._cleanup_external_resources(dataset)

            self.logger.info(f"Successfully cleaned up dataset: {dataset_id}")

        except Exception as e:
            self.logger.error(f"Error cleaning up dataset {dataset_id}: {e}")

    async def _persist_dataset_to_database(self, dataset: TestDataSet):
        """Persist dataset to database for testing"""
        # This would implement actual database persistence
        # For now, just log what would be persisted
        self.logger.debug(f"Would persist {len(dataset.users)} users to database")
        self.logger.debug(f"Would persist {len(dataset.connections)} connections to database")
        self.logger.debug(f"Would persist {len(dataset.status_updates)} status updates to database")
        self.logger.debug(f"Would persist {len(dataset.connection_events)} events to database")

    async def _cleanup_dataset_from_database(self, dataset: TestDataSet):
        """Clean up dataset from database"""
        # This would implement actual database cleanup
        # For now, just log what would be cleaned up
        isolation_marker = dataset.test_run_id

        self.logger.debug(f"Would clean up users with marker: {isolation_marker}")
        self.logger.debug(f"Would clean up connections with marker: {isolation_marker}")
        self.logger.debug(f"Would clean up status updates with marker: {isolation_marker}")

    async def _cleanup_external_resources(self, dataset: TestDataSet):
        """Clean up external resources (files, cache, etc.)"""
        # Clean up any uploaded files
        for document in dataset.documents:
            # Would clean up actual files here
            pass

        # Clean up cache entries
        for connection in dataset.connections:
            # Would clean up Redis cache entries here
            pass

    async def cleanup_expired_datasets(self):
        """Clean up expired test datasets"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.config.cleanup_after_hours)

        expired_datasets = [
            dataset_id for dataset_id, dataset in self.active_datasets.items()
            if dataset.created_at < cutoff_time
        ]

        for dataset_id in expired_datasets:
            await self.cleanup_dataset(dataset_id)

    def get_dataset_summary(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of test dataset"""
        if dataset_id not in self.active_datasets:
            return None

        dataset = self.active_datasets[dataset_id]

        return {
            "dataset_id": dataset_id,
            "test_run_id": dataset.test_run_id,
            "created_at": dataset.created_at.isoformat(),
            "config": dataset.config.__dict__,
            "counts": {
                "users": len(dataset.users),
                "organizations": len(dataset.organizations),
                "documents": len(dataset.documents),
                "connections": len(dataset.connections),
                "status_updates": len(dataset.status_updates),
                "connection_events": len(dataset.connection_events)
            }
        }

    async def generate_load_test_data(self, connection_count: int, duration_minutes: int = 10) -> TestDataSet:
        """Generate data specifically for load testing"""
        load_config = TestDataConfiguration(
            user_count=connection_count,
            connection_count=connection_count,
            status_update_count=connection_count * duration_minutes * 6,  # 6 updates per minute per connection
            connection_event_count=connection_count * duration_minutes * 12,  # 12 events per minute per connection
            batch_size=1000,
            parallel_workers=8
        )

        self.generator.config = load_config
        dataset = self.generator.generate_complete_dataset(load_config)

        # Mark as load test data
        dataset.test_run_id = f"load_test_{connection_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        return dataset


# Utility functions for common test data operations
async def create_test_user(async_session: AsyncSession, email: str = None) -> Dict[str, Any]:
    """Create a test user in the database"""
    # This would implement actual user creation
    return {
        "id": str(uuid.uuid4()),
        "email": email or f"test_user_{uuid.uuid4().hex[:8]}@example.com",
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        "is_verified": True
    }


async def create_test_organization(async_session: AsyncSession, name: str = None) -> Dict[str, Any]:
    """Create a test organization in the database"""
    # This would implement actual organization creation
    return {
        "id": str(uuid.uuid4()),
        "name": name or f"Test Org {uuid.uuid4().hex[:8]}",
        "slug": f"test-org-{uuid.uuid4().hex[:8]}",
        "is_active": True
    }


async def cleanup_test_data_by_marker(async_session: AsyncSession, marker: str):
    """Clean up test data by isolation marker"""
    # This would implement actual cleanup by marker
    pass


# Global test data manager instance
test_data_manager = TestDataManager()