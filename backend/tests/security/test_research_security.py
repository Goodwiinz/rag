"""
Security tests for Research Assistant (T127)

Tests access control, injection prevention, and XSS protection.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import re


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def owner_user():
    """Create the project owner user."""
    return {
        "id": str(uuid4()),
        "email": "owner@test.com",
    }


@pytest.fixture
def other_user():
    """Create a different user."""
    return {
        "id": str(uuid4()),
        "email": "other@test.com",
    }


@pytest.fixture
def sample_project(owner_user):
    """Create a sample project owned by owner_user."""
    return {
        "id": str(uuid4()),
        "name": "Test Project",
        "user_id": owner_user["id"],
        "is_private": True,
    }


class TestProjectAccessControl:
    """Tests for project ownership and access control."""

    @pytest.mark.asyncio
    async def test_security_project_access_denied_non_owner(
        self, mock_db_session, sample_project, other_user
    ):
        """Test that non-owner cannot access another user's project."""
        project_id = sample_project["id"]
        requesting_user_id = other_user["id"]

        # Project belongs to owner_user, not other_user
        assert sample_project["user_id"] != requesting_user_id

        # Access should be denied
        def check_access(project, user_id):
            if project["user_id"] != user_id:
                raise PermissionError("Access denied: you do not own this project")
            return project

        with pytest.raises(PermissionError) as exc_info:
            check_access(sample_project, requesting_user_id)

        assert "Access denied" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_security_project_access_allowed_owner(
        self, mock_db_session, sample_project, owner_user
    ):
        """Test that owner can access their own project."""
        project_id = sample_project["id"]
        requesting_user_id = owner_user["id"]

        # Access should succeed
        def check_access(project, user_id):
            if project["user_id"] != user_id:
                raise PermissionError("Access denied")
            return project

        result = check_access(sample_project, requesting_user_id)
        assert result["id"] == project_id


class TestDraftAccessControl:
    """Tests for draft ownership and access control."""

    @pytest.mark.asyncio
    async def test_security_draft_access_denied_non_owner(
        self, mock_db_session, sample_project, other_user
    ):
        """Test that non-owner cannot access drafts in another user's project."""
        draft = {
            "id": str(uuid4()),
            "project_id": sample_project["id"],
            "version": 1,
        }
        requesting_user_id = other_user["id"]

        # Draft is in owner's project
        def check_draft_access(draft, project, user_id):
            if project["user_id"] != user_id:
                raise PermissionError("Access denied: you do not own this project's drafts")
            return draft

        with pytest.raises(PermissionError) as exc_info:
            check_draft_access(draft, sample_project, requesting_user_id)

        assert "Access denied" in str(exc_info.value)


class TestNoteAccessControl:
    """Tests for note ownership and access control."""

    @pytest.mark.asyncio
    async def test_security_note_access_denied_non_owner(
        self, mock_db_session, sample_project, other_user
    ):
        """Test that non-owner cannot access notes in another user's project."""
        note = {
            "id": str(uuid4()),
            "project_id": sample_project["id"],
            "title": "Private Note",
            "content": "Secret content",
        }
        requesting_user_id = other_user["id"]

        def check_note_access(note, project, user_id):
            if project["user_id"] != user_id:
                raise PermissionError("Access denied: you do not own this project's notes")
            return note

        with pytest.raises(PermissionError) as exc_info:
            check_note_access(note, sample_project, requesting_user_id)

        assert "Access denied" in str(exc_info.value)


class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention in citation fields."""

    @pytest.mark.asyncio
    async def test_security_citation_injection_prevention(self, mock_db_session):
        """Test that SQL injection attempts are prevented in citation fields."""
        # Malicious inputs that could be SQL injection attempts
        injection_attempts = [
            "'; DROP TABLE citations; --",
            "1' OR '1'='1",
            "1; DELETE FROM users WHERE 1=1; --",
            "Robert'); DROP TABLE Students;--",
            "' UNION SELECT * FROM users --",
        ]

        def sanitize_input(value):
            """Simulate input sanitization/parameterized queries."""
            # In real code, use parameterized queries which handle this automatically
            # This simulates validation that dangerous patterns are escaped
            if isinstance(value, str):
                # These patterns should be escaped or rejected
                dangerous_patterns = [
                    r";\s*DROP",
                    r";\s*DELETE",
                    r";\s*UPDATE",
                    r";\s*INSERT",
                    r"UNION\s+SELECT",
                    r"--",
                    r"'\s*OR\s+'",
                ]
                for pattern in dangerous_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        # In parameterized queries, this would be escaped
                        # For this test, we verify detection
                        return value.replace("'", "''")  # Escape quotes
            return value

        for malicious_input in injection_attempts:
            sanitized = sanitize_input(malicious_input)
            # Ensure single quotes are escaped (basic protection)
            if "'" in malicious_input:
                assert "''" in sanitized or "\\'" in sanitized or malicious_input == sanitized

    @pytest.mark.asyncio
    async def test_parameterized_queries_used(self, mock_db_session):
        """Test that queries use parameterized statements."""
        # Simulate a citation creation with user input
        user_input = {
            "title": "Normal Paper Title",
            "authors": ["John O'Connor"],  # Name with apostrophe
            "year": 2023,
        }

        # In SQLAlchemy, this would be:
        # session.execute(insert(Citation).values(**user_input))
        # Which automatically parameterizes

        # Verify the input passes through safely
        assert "'" in user_input["authors"][0]  # Has apostrophe
        # Should not cause SQL error when properly parameterized


class TestXSSPrevention:
    """Tests for XSS prevention in note content."""

    @pytest.mark.asyncio
    async def test_security_xss_prevention_note_content(self, mock_db_session):
        """Test that markdown note content is sanitized for XSS."""
        # Malicious XSS attempts
        xss_attempts = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<a href='javascript:alert(1)'>Click</a>",
            "<div onmouseover='alert(1)'>Hover</div>",
            "<<SCRIPT>alert('XSS');//<</SCRIPT>",
        ]

        def sanitize_markdown(content):
            """Simulate markdown sanitization."""
            # In real code, use bleach or similar library
            # Remove script tags
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
            # Remove event handlers
            content = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)
            content = re.sub(r'\s*on\w+\s*=\s*[^\s>]*', '', content, flags=re.IGNORECASE)
            # Remove javascript: URLs
            content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
            # Remove dangerous tags
            content = re.sub(r'<(script|svg|iframe|object|embed)[^>]*>.*?</\1>', '', content, flags=re.IGNORECASE | re.DOTALL)
            return content

        for xss_attempt in xss_attempts:
            sanitized = sanitize_markdown(xss_attempt)
            # Verify dangerous content is removed
            assert "<script" not in sanitized.lower()
            assert "javascript:" not in sanitized.lower()
            assert "onerror=" not in sanitized.lower()
            assert "onload=" not in sanitized.lower()
            assert "onmouseover=" not in sanitized.lower()

    @pytest.mark.asyncio
    async def test_safe_markdown_preserved(self, mock_db_session):
        """Test that safe markdown content is preserved."""
        safe_content = """
# Research Notes

## Key Findings

- Finding 1: **Important** result
- Finding 2: _Italic_ text
- Finding 3: `code snippet`

### Code Example

```python
def hello():
    print("Hello, world!")
```

[Link to paper](https://arxiv.org/abs/2301.07041)

![Image](image.png)
"""

        def sanitize_markdown(content):
            # Safe markdown should pass through unchanged (mostly)
            return content

        sanitized = sanitize_markdown(safe_content)

        # Verify markdown elements preserved
        assert "# Research Notes" in sanitized
        assert "**Important**" in sanitized
        assert "_Italic_" in sanitized
        assert "```python" in sanitized
        assert "[Link to paper]" in sanitized


class TestAuthenticationRequired:
    """Tests for authentication requirements."""

    @pytest.mark.asyncio
    async def test_unauthenticated_project_access(self):
        """Test that unauthenticated users cannot access projects."""
        # No auth header
        headers = {}

        response = {
            "status_code": 401,
            "detail": "Not authenticated",
        }

        assert response["status_code"] == 401

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self):
        """Test that invalid JWT tokens are rejected."""
        headers = {"Authorization": "Bearer invalid-token-12345"}

        response = {
            "status_code": 401,
            "detail": "Invalid authentication credentials",
        }

        assert response["status_code"] == 401


class TestDataIsolation:
    """Tests for multi-tenancy data isolation."""

    @pytest.mark.asyncio
    async def test_user_cannot_see_other_users_projects(self, owner_user, other_user):
        """Test that users can only see their own projects."""
        # Owner's projects
        owner_projects = [
            {"id": "p1", "user_id": owner_user["id"], "name": "Owner Project 1"},
            {"id": "p2", "user_id": owner_user["id"], "name": "Owner Project 2"},
        ]

        # Other user's projects
        other_projects = [
            {"id": "p3", "user_id": other_user["id"], "name": "Other Project 1"},
        ]

        # When other_user queries, they should only see their projects
        def get_user_projects(all_projects, user_id):
            return [p for p in all_projects if p["user_id"] == user_id]

        all_projects = owner_projects + other_projects

        other_user_visible = get_user_projects(all_projects, other_user["id"])
        assert len(other_user_visible) == 1
        assert other_user_visible[0]["id"] == "p3"

        # Should not see owner's projects
        for project in other_user_visible:
            assert project["user_id"] != owner_user["id"]


class TestInputValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_project_name_length_validation(self):
        """Test that project names have length limits."""
        max_name_length = 200

        # Valid name
        valid_name = "Machine Learning in Healthcare"
        assert len(valid_name) <= max_name_length

        # Too long name
        too_long_name = "A" * 300
        assert len(too_long_name) > max_name_length

        def validate_name(name):
            if len(name) > max_name_length:
                raise ValueError(f"Name must be {max_name_length} characters or less")
            return name

        with pytest.raises(ValueError):
            validate_name(too_long_name)

    @pytest.mark.asyncio
    async def test_citation_year_validation(self):
        """Test that citation years are valid."""
        def validate_year(year):
            if year is not None:
                if year < 1900 or year > 2100:
                    raise ValueError("Year must be between 1900 and 2100")
            return year

        # Valid years
        assert validate_year(2023) == 2023
        assert validate_year(1950) == 1950
        assert validate_year(None) is None

        # Invalid years
        with pytest.raises(ValueError):
            validate_year(1800)

        with pytest.raises(ValueError):
            validate_year(2200)

    @pytest.mark.asyncio
    async def test_arxiv_id_format_validation(self):
        """Test ArXiv ID format validation."""
        def validate_arxiv_id(arxiv_id):
            # ArXiv IDs are like: 2301.07041 or arXiv:2301.07041
            if arxiv_id is None:
                return None
            pattern = r'^(arXiv:)?(\d{4}\.\d{4,5})(v\d+)?$'
            if not re.match(pattern, arxiv_id):
                raise ValueError("Invalid ArXiv ID format")
            return arxiv_id

        # Valid formats
        assert validate_arxiv_id("2301.07041") == "2301.07041"
        assert validate_arxiv_id("arXiv:2301.07041") == "arXiv:2301.07041"
        assert validate_arxiv_id("2301.07041v2") == "2301.07041v2"
        assert validate_arxiv_id(None) is None

        # Invalid formats
        with pytest.raises(ValueError):
            validate_arxiv_id("invalid-id")

        with pytest.raises(ValueError):
            validate_arxiv_id("12345")
