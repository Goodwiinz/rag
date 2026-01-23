"""
Data Builders for Test Fixtures

Provides builder pattern implementations for creating test data
with sensible defaults and fluent API.

Builders:
- UserBuilder: Create user test data
- DocumentBuilder: Create document test data
- SearchResultBuilder: Create search result test data
- EntityBuilder: Create knowledge graph entity test data
- OrganizationBuilder: Create organization test data

Usage:
    user = UserBuilder().with_email("test@example.com").as_admin().build()
    doc = DocumentBuilder().with_title("My Doc").with_status("indexed").build()
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import Mock
from uuid import uuid4, UUID
import random
import string


# ============================================================================
# User Builder
# ============================================================================

class UserBuilder:
    """
    Builder for user test data.

    Example:
        user = UserBuilder() \
            .with_email("admin@test.com") \
            .with_role("admin") \
            .build()
    """

    def __init__(self):
        self._id = uuid4()
        self._email = f"user_{uuid4().hex[:8]}@example.com"
        self._first_name = "Test"
        self._last_name = "User"
        self._role = "user"
        self._organization_id = uuid4()
        self._is_active = True
        self._is_verified = True
        self._created_at = datetime.utcnow()
        self._updated_at = datetime.utcnow()
        self._last_login = None
        self._preferences = {}

    def with_id(self, id: UUID) -> "UserBuilder":
        self._id = id
        return self

    def with_email(self, email: str) -> "UserBuilder":
        self._email = email
        return self

    def with_name(self, first_name: str, last_name: str) -> "UserBuilder":
        self._first_name = first_name
        self._last_name = last_name
        return self

    def with_role(self, role: str) -> "UserBuilder":
        self._role = role
        return self

    def as_admin(self) -> "UserBuilder":
        return self.with_role("admin")

    def as_viewer(self) -> "UserBuilder":
        return self.with_role("viewer")

    def with_organization(self, org_id: UUID) -> "UserBuilder":
        self._organization_id = org_id
        return self

    def inactive(self) -> "UserBuilder":
        self._is_active = False
        return self

    def unverified(self) -> "UserBuilder":
        self._is_verified = False
        return self

    def with_last_login(self, when: datetime = None) -> "UserBuilder":
        self._last_login = when or datetime.utcnow()
        return self

    def with_preferences(self, preferences: Dict[str, Any]) -> "UserBuilder":
        self._preferences.update(preferences)
        return self

    def build(self) -> Mock:
        user = Mock()
        user.id = self._id
        user.email = self._email
        user.first_name = self._first_name
        user.last_name = self._last_name
        user.full_name = f"{self._first_name} {self._last_name}"
        user.role = Mock(value=self._role)
        user.organization_id = self._organization_id
        user.is_active = self._is_active
        user.is_verified = self._is_verified
        user.created_at = self._created_at
        user.updated_at = self._updated_at
        user.last_login = self._last_login
        user.preferences = self._preferences
        return user

    def build_dict(self) -> Dict[str, Any]:
        """Build as dictionary for API responses."""
        return {
            "id": str(self._id),
            "email": self._email,
            "first_name": self._first_name,
            "last_name": self._last_name,
            "full_name": f"{self._first_name} {self._last_name}",
            "role": self._role,
            "organization_id": str(self._organization_id),
            "is_active": self._is_active,
            "is_verified": self._is_verified,
            "created_at": self._created_at.isoformat(),
            "updated_at": self._updated_at.isoformat(),
            "last_login": self._last_login.isoformat() if self._last_login else None,
            "preferences": self._preferences,
        }


# ============================================================================
# Document Builder
# ============================================================================

class DocumentBuilder:
    """
    Builder for document test data.

    Example:
        doc = DocumentBuilder() \
            .with_title("Research Paper") \
            .with_status("indexed") \
            .with_tags(["ai", "ml"]) \
            .build()
    """

    DOCUMENT_TYPES = ["pdf", "txt", "docx", "md", "html"]
    STATUSES = ["pending", "processing", "indexed", "failed", "queued"]

    def __init__(self):
        self._id = uuid4()
        self._title = f"Document {uuid4().hex[:6]}"
        self._content = "This is sample document content for testing purposes."
        self._document_type = "pdf"
        self._status = "indexed"
        self._tags = []
        self._metadata = {}
        self._file_size = random.randint(1000, 1000000)
        self._file_path = f"/uploads/{uuid4().hex}.pdf"
        self._owner_id = uuid4()
        self._organization_id = uuid4()
        self._created_at = datetime.utcnow()
        self._updated_at = datetime.utcnow()
        self._indexed_at = None
        self._chunk_count = 0

    def with_id(self, id: UUID) -> "DocumentBuilder":
        self._id = id
        return self

    def with_title(self, title: str) -> "DocumentBuilder":
        self._title = title
        return self

    def with_content(self, content: str) -> "DocumentBuilder":
        self._content = content
        return self

    def with_type(self, doc_type: str) -> "DocumentBuilder":
        self._document_type = doc_type
        return self

    def with_status(self, status: str) -> "DocumentBuilder":
        self._status = status
        if status == "indexed":
            self._indexed_at = datetime.utcnow()
        return self

    def with_tags(self, tags: List[str]) -> "DocumentBuilder":
        self._tags = tags
        return self

    def add_tag(self, tag: str) -> "DocumentBuilder":
        self._tags.append(tag)
        return self

    def with_metadata(self, metadata: Dict[str, Any]) -> "DocumentBuilder":
        self._metadata.update(metadata)
        return self

    def with_file_size(self, size: int) -> "DocumentBuilder":
        self._file_size = size
        return self

    def with_owner(self, owner_id: UUID) -> "DocumentBuilder":
        self._owner_id = owner_id
        return self

    def with_organization(self, org_id: UUID) -> "DocumentBuilder":
        self._organization_id = org_id
        return self

    def with_chunk_count(self, count: int) -> "DocumentBuilder":
        self._chunk_count = count
        return self

    def as_pending(self) -> "DocumentBuilder":
        return self.with_status("pending")

    def as_processing(self) -> "DocumentBuilder":
        return self.with_status("processing")

    def as_indexed(self) -> "DocumentBuilder":
        return self.with_status("indexed")

    def as_failed(self) -> "DocumentBuilder":
        return self.with_status("failed")

    def build(self) -> Mock:
        doc = Mock()
        doc.id = self._id
        doc.title = self._title
        doc.content = self._content
        doc.document_type = self._document_type
        doc.status = Mock(value=self._status)
        doc.tags = self._tags
        doc.metadata = self._metadata
        doc.file_size = self._file_size
        doc.file_path = self._file_path
        doc.owner_id = self._owner_id
        doc.organization_id = self._organization_id
        doc.created_at = self._created_at
        doc.updated_at = self._updated_at
        doc.indexed_at = self._indexed_at
        doc.chunk_count = self._chunk_count
        return doc

    def build_dict(self) -> Dict[str, Any]:
        """Build as dictionary for API responses."""
        return {
            "id": str(self._id),
            "title": self._title,
            "content": self._content,
            "document_type": self._document_type,
            "status": self._status,
            "tags": self._tags,
            "metadata": self._metadata,
            "file_size": self._file_size,
            "file_path": self._file_path,
            "owner_id": str(self._owner_id),
            "organization_id": str(self._organization_id),
            "created_at": self._created_at.isoformat(),
            "updated_at": self._updated_at.isoformat(),
            "indexed_at": self._indexed_at.isoformat() if self._indexed_at else None,
            "chunk_count": self._chunk_count,
        }


# ============================================================================
# Search Result Builder
# ============================================================================

class SearchResultBuilder:
    """
    Builder for search result test data.

    Example:
        result = SearchResultBuilder() \
            .with_score(0.95) \
            .from_source("vector") \
            .build()
    """

    SOURCES = ["fulltext", "vector", "graph", "hybrid"]

    def __init__(self):
        self._id = str(uuid4())
        self._document_id = str(uuid4())
        self._title = f"Search Result {uuid4().hex[:6]}"
        self._content = "This is matching content from the document."
        self._snippet = "...matching content..."
        self._score = random.uniform(0.7, 0.99)
        self._source = "hybrid"
        self._chunk_index = 0
        self._metadata = {}
        self._highlights = []

    def with_id(self, id: str) -> "SearchResultBuilder":
        self._id = id
        return self

    def with_document_id(self, doc_id: str) -> "SearchResultBuilder":
        self._document_id = doc_id
        return self

    def with_title(self, title: str) -> "SearchResultBuilder":
        self._title = title
        return self

    def with_content(self, content: str) -> "SearchResultBuilder":
        self._content = content
        return self

    def with_snippet(self, snippet: str) -> "SearchResultBuilder":
        self._snippet = snippet
        return self

    def with_score(self, score: float) -> "SearchResultBuilder":
        self._score = max(0.0, min(1.0, score))
        return self

    def from_source(self, source: str) -> "SearchResultBuilder":
        self._source = source
        return self

    def from_vector(self) -> "SearchResultBuilder":
        return self.from_source("vector")

    def from_fulltext(self) -> "SearchResultBuilder":
        return self.from_source("fulltext")

    def from_graph(self) -> "SearchResultBuilder":
        return self.from_source("graph")

    def with_chunk_index(self, index: int) -> "SearchResultBuilder":
        self._chunk_index = index
        return self

    def with_metadata(self, metadata: Dict[str, Any]) -> "SearchResultBuilder":
        self._metadata.update(metadata)
        return self

    def with_highlights(self, highlights: List[str]) -> "SearchResultBuilder":
        self._highlights = highlights
        return self

    def build(self) -> Dict[str, Any]:
        return {
            "id": self._id,
            "document_id": self._document_id,
            "title": self._title,
            "content": self._content,
            "snippet": self._snippet,
            "score": self._score,
            "source": self._source,
            "chunk_index": self._chunk_index,
            "metadata": self._metadata,
            "highlights": self._highlights,
        }


# ============================================================================
# Organization Builder
# ============================================================================

class OrganizationBuilder:
    """
    Builder for organization test data.

    Example:
        org = OrganizationBuilder() \
            .with_name("Acme Corp") \
            .with_storage_tier("premium") \
            .build()
    """

    STORAGE_TIERS = ["free", "basic", "premium", "enterprise"]

    def __init__(self):
        self._id = uuid4()
        self._name = f"Organization {uuid4().hex[:6]}"
        self._slug = None
        self._storage_tier = "basic"
        self._storage_used = 0
        self._storage_limit = 10 * 1024 * 1024 * 1024  # 10GB
        self._user_limit = 10
        self._is_active = True
        self._created_at = datetime.utcnow()
        self._settings = {}

    def with_id(self, id: UUID) -> "OrganizationBuilder":
        self._id = id
        return self

    def with_name(self, name: str) -> "OrganizationBuilder":
        self._name = name
        self._slug = name.lower().replace(" ", "-")
        return self

    def with_storage_tier(self, tier: str) -> "OrganizationBuilder":
        self._storage_tier = tier
        return self

    def with_storage_used(self, used: int) -> "OrganizationBuilder":
        self._storage_used = used
        return self

    def with_storage_limit(self, limit: int) -> "OrganizationBuilder":
        self._storage_limit = limit
        return self

    def with_user_limit(self, limit: int) -> "OrganizationBuilder":
        self._user_limit = limit
        return self

    def inactive(self) -> "OrganizationBuilder":
        self._is_active = False
        return self

    def with_settings(self, settings: Dict[str, Any]) -> "OrganizationBuilder":
        self._settings.update(settings)
        return self

    def as_free(self) -> "OrganizationBuilder":
        self._storage_tier = "free"
        self._storage_limit = 1 * 1024 * 1024 * 1024  # 1GB
        self._user_limit = 3
        return self

    def as_enterprise(self) -> "OrganizationBuilder":
        self._storage_tier = "enterprise"
        self._storage_limit = 1000 * 1024 * 1024 * 1024  # 1TB
        self._user_limit = 1000
        return self

    def build(self) -> Mock:
        org = Mock()
        org.id = self._id
        org.name = self._name
        org.slug = self._slug or self._name.lower().replace(" ", "-")
        org.storage_tier = Mock(value=self._storage_tier)
        org.storage_used = self._storage_used
        org.storage_limit = self._storage_limit
        org.user_limit = self._user_limit
        org.is_active = self._is_active
        org.created_at = self._created_at
        org.settings = self._settings
        return org

    def build_dict(self) -> Dict[str, Any]:
        """Build as dictionary for API responses."""
        return {
            "id": str(self._id),
            "name": self._name,
            "slug": self._slug or self._name.lower().replace(" ", "-"),
            "storage_tier": self._storage_tier,
            "storage_used": self._storage_used,
            "storage_limit": self._storage_limit,
            "user_limit": self._user_limit,
            "is_active": self._is_active,
            "created_at": self._created_at.isoformat(),
            "settings": self._settings,
        }


# ============================================================================
# Batch Builders
# ============================================================================

class BatchBuilder:
    """
    Create batches of test data.

    Example:
        users = BatchBuilder.users(count=5).with_organization(org_id).build_all()
        docs = BatchBuilder.documents(count=10).with_owner(user_id).build_all()
    """

    @staticmethod
    def users(count: int = 5) -> "BatchUserBuilder":
        return BatchUserBuilder(count)

    @staticmethod
    def documents(count: int = 5) -> "BatchDocumentBuilder":
        return BatchDocumentBuilder(count)

    @staticmethod
    def search_results(count: int = 10) -> "BatchSearchResultBuilder":
        return BatchSearchResultBuilder(count)


class BatchUserBuilder:
    """Build multiple users with shared attributes."""

    def __init__(self, count: int):
        self._count = count
        self._organization_id = None
        self._role = "user"

    def with_organization(self, org_id: UUID) -> "BatchUserBuilder":
        self._organization_id = org_id
        return self

    def with_role(self, role: str) -> "BatchUserBuilder":
        self._role = role
        return self

    def build_all(self) -> List[Mock]:
        users = []
        for i in range(self._count):
            builder = UserBuilder() \
                .with_email(f"user{i}@example.com") \
                .with_name(f"User{i}", f"Test") \
                .with_role(self._role)

            if self._organization_id:
                builder.with_organization(self._organization_id)

            users.append(builder.build())
        return users


class BatchDocumentBuilder:
    """Build multiple documents with shared attributes."""

    def __init__(self, count: int):
        self._count = count
        self._owner_id = None
        self._organization_id = None
        self._status = "indexed"

    def with_owner(self, owner_id: UUID) -> "BatchDocumentBuilder":
        self._owner_id = owner_id
        return self

    def with_organization(self, org_id: UUID) -> "BatchDocumentBuilder":
        self._organization_id = org_id
        return self

    def with_status(self, status: str) -> "BatchDocumentBuilder":
        self._status = status
        return self

    def build_all(self) -> List[Mock]:
        docs = []
        for i in range(self._count):
            builder = DocumentBuilder() \
                .with_title(f"Document {i}") \
                .with_status(self._status)

            if self._owner_id:
                builder.with_owner(self._owner_id)
            if self._organization_id:
                builder.with_organization(self._organization_id)

            docs.append(builder.build())
        return docs


class BatchSearchResultBuilder:
    """Build multiple search results with decreasing scores."""

    def __init__(self, count: int):
        self._count = count
        self._source = "hybrid"
        self._base_score = 0.95

    def from_source(self, source: str) -> "BatchSearchResultBuilder":
        self._source = source
        return self

    def with_base_score(self, score: float) -> "BatchSearchResultBuilder":
        self._base_score = score
        return self

    def build_all(self) -> List[Dict[str, Any]]:
        results = []
        for i in range(self._count):
            score = max(0.1, self._base_score - (i * 0.05))
            result = SearchResultBuilder() \
                .with_title(f"Result {i}") \
                .with_score(score) \
                .from_source(self._source) \
                .build()
            results.append(result)
        return results
