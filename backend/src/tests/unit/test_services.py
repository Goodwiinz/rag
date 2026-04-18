"""
Unit tests for services package
Tests service methods with mocked dependencies
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import List, Dict, Any
import asyncio

from sqlalchemy.orm import Session
from fastapi import HTTPException

# Search services
from src.services.search.hybrid_search_service import HybridSearchService
from src.services.search.fulltext_search_service import FullTextSearchService

# Security services  
from src.services.security.auth_service import AuthService, AuthenticationError, AuthorizationError
from src.services.security.rbac_service import RBACService

# Models for testing
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.search import SearchQuery, SearchResult
from src.models.document import Document


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = Mock(spec=Session)
    session.query.return_value = session
    session.filter.return_value = session
    session.first.return_value = None
    session.all.return_value = []
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def sample_user():
    """Sample user object for testing"""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.USER,
        organization_id=uuid.uuid4(),
        is_active=True
    )
    return user


@pytest.fixture
def sample_organization():
    """Sample organization for testing"""
    org = Organization(
        id=uuid.uuid4(),
        name="Test Organization",
        domain="test.com"
    )
    return org


class TestHybridSearchService:
    """Test HybridSearchService functionality"""

    @pytest.fixture
    def service(self, mock_db_session):
        """Create service instance with mocked dependencies"""
        with patch('src.services.search.hybrid_search_service.get_db') as mock_get_db:
            mock_get_db.return_value = mock_db_session
            service = HybridSearchService()
            return service
    
    @pytest.mark.asyncio
    async def test_search_documents_success(self, service, sample_user):
        """Test successful document search"""
        # Mock the search methods
        with patch.object(service, '_vector_search') as mock_vector:
            with patch.object(service, '_fulltext_search') as mock_fulltext:
                with patch.object(service, '_fusion_ranking') as mock_fusion:
                    
                    # Setup mocks
                    mock_vector.return_value = [
                        {"document_id": "doc1", "score": 0.9, "content": "Vector result 1"},
                        {"document_id": "doc2", "score": 0.8, "content": "Vector result 2"}
                    ]
                    
                    mock_fulltext.return_value = [
                        {"document_id": "doc1", "score": 0.85, "content": "Fulltext result 1"},
                        {"document_id": "doc3", "score": 0.7, "content": "Fulltext result 3"}
                    ]
                    
                    mock_fusion.return_value = [
                        {"document_id": "doc1", "final_score": 0.875, "content": "Fused result 1"},
                        {"document_id": "doc2", "final_score": 0.8, "content": "Fused result 2"},
                        {"document_id": "doc3", "final_score": 0.7, "content": "Fused result 3"}
                    ]
                    
                    # Execute search
                    results = await service.search_documents(
                        query="test query",
                        user_id=sample_user.id,
                        organization_id=sample_user.organization_id,
                        limit=10
                    )
                    
                    # Assertions
                    assert len(results) == 3
                    assert results[0]["document_id"] == "doc1"
                    assert results[0]["final_score"] == 0.875
                    
                    # Verify method calls
                    mock_vector.assert_called_once()
                    mock_fulltext.assert_called_once()
                    mock_fusion.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, service, sample_user):
        """Test search with document filters"""
        with patch.object(service, '_apply_filters') as mock_filter:
            with patch.object(service, '_vector_search') as mock_vector:
                with patch.object(service, '_fulltext_search') as mock_fulltext:
                    with patch.object(service, '_fusion_ranking') as mock_fusion:
                        
                        mock_vector.return_value = []
                        mock_fulltext.return_value = []
                        mock_fusion.return_value = []
                        mock_filter.return_value = []
                        
                        filters = {
                            "document_type": "pdf",
                            "created_after": "2024-01-01",
                            "tags": ["research", "analysis"]
                        }
                        
                        await service.search_documents(
                            query="test query",
                            user_id=sample_user.id,
                            organization_id=sample_user.organization_id,
                            filters=filters
                        )
                        
                        mock_filter.assert_called_once_with([], filters)
    
    @pytest.mark.asyncio
    async def test_search_error_handling(self, service, sample_user):
        """Test search error handling"""
        with patch.object(service, '_vector_search') as mock_vector:
            mock_vector.side_effect = Exception("Vector search failed")
            
            with pytest.raises(Exception) as exc_info:
                await service.search_documents(
                    query="test query",
                    user_id=sample_user.id,
                    organization_id=sample_user.organization_id
                )
            
            assert "Vector search failed" in str(exc_info.value)


class TestFullTextSearchService:
    """Test FullTextSearchService functionality"""

    @pytest.fixture
    def service(self, mock_db_session):
        """Create service instance"""
        return FullTextSearchService()
    
    @pytest.mark.asyncio
    async def test_fulltext_search_success(self, service, sample_user, mock_db_session):
        """Test successful fulltext search"""
        # Mock database query results
        mock_results = [
            Mock(id="doc1", title="Test Document 1", content="Content 1"),
            Mock(id="doc2", title="Test Document 2", content="Content 2")
        ]
        
        mock_db_session.execute.return_value.fetchall.return_value = mock_results
        
        results = await service.search(
            query="test query",
            organization_id=sample_user.organization_id,
            limit=10
        )
        
        assert len(results) == 2
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_with_ranking(self, service, sample_user, mock_db_session):
        """Test search with BM25 ranking"""
        with patch.object(service, '_calculate_bm25_score') as mock_bm25:
            mock_bm25.return_value = 0.85
            
            mock_results = [Mock(id="doc1", title="Test", content="Content")]
            mock_db_session.execute.return_value.fetchall.return_value = mock_results
            
            results = await service.search(
                query="test query",
                organization_id=sample_user.organization_id,
                use_ranking=True
            )
            
            mock_bm25.assert_called()
            assert len(results) == 1
    
    @pytest.mark.asyncio
    async def test_search_empty_query(self, service, sample_user):
        """Test search with empty query"""
        results = await service.search(
            query="",
            organization_id=sample_user.organization_id
        )
        
        assert results == []
    
    @pytest.mark.asyncio 
    async def test_search_no_results(self, service, sample_user, mock_db_session):
        """Test search with no results"""
        mock_db_session.execute.return_value.fetchall.return_value = []
        
        results = await service.search(
            query="nonexistent query",
            organization_id=sample_user.organization_id
        )
        
        assert results == []


class TestAuthService:
    """Test AuthService functionality"""

    @pytest.fixture
    def service(self, mock_db_session):
        """Create service instance"""
        return AuthService(db=mock_db_session)
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, service, sample_user):
        """Test successful user authentication"""
        with patch.object(service, '_get_user_by_email') as mock_get_user:
            with patch('src.core.security.verify_password') as mock_verify:
                with patch.object(service, '_check_rate_limit') as mock_rate_limit:
                    
                    mock_get_user.return_value = sample_user
                    mock_verify.return_value = True
                    mock_rate_limit.return_value = True
                    
                    result = await service.authenticate_user("test@example.com", "password")
                    
                    assert result == sample_user
                    mock_get_user.assert_called_once_with("test@example.com")
                    mock_verify.assert_called_once_with("password", sample_user.password_hash)
    
    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_credentials(self, service):
        """Test authentication with invalid credentials"""
        with patch.object(service, '_get_user_by_email') as mock_get_user:
            mock_get_user.return_value = None
            
            with pytest.raises(AuthenticationError) as exc_info:
                await service.authenticate_user("invalid@example.com", "password")
            
            assert "Invalid credentials" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, service, sample_user):
        """Test authentication with wrong password"""
        with patch.object(service, '_get_user_by_email') as mock_get_user:
            with patch('src.core.security.verify_password') as mock_verify:
                
                mock_get_user.return_value = sample_user
                mock_verify.return_value = False
                
                with pytest.raises(AuthenticationError):
                    await service.authenticate_user("test@example.com", "wrongpassword")
    
    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self, service, sample_user):
        """Test authentication with inactive user"""
        sample_user.is_active = False
        
        with patch.object(service, '_get_user_by_email') as mock_get_user:
            mock_get_user.return_value = sample_user
            
            with pytest.raises(AuthenticationError) as exc_info:
                await service.authenticate_user("test@example.com", "password")
            
            assert "Account is disabled" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, service, sample_organization):
        """Test successful user creation"""
        with patch.object(service, '_validate_user_data') as mock_validate:
            with patch.object(service, '_check_email_availability') as mock_check_email:
                with patch('src.core.security.get_password_hash') as mock_hash:
                    with patch.object(service, '_save_user') as mock_save:
                        
                        mock_validate.return_value = True
                        mock_check_email.return_value = True
                        mock_hash.return_value = "hashed_password"
                        
                        new_user = User(
                            email="new@example.com",
                            first_name="New",
                            last_name="User",
                            organization_id=sample_organization.id
                        )
                        mock_save.return_value = new_user
                        
                        result = await service.create_user(
                            email="new@example.com",
                            password="password123",
                            first_name="New",
                            last_name="User",
                            organization_id=sample_organization.id
                        )
                        
                        assert result.email == "new@example.com"
                        mock_validate.assert_called_once()
                        mock_hash.assert_called_once_with("password123")
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, service):
        """Test user creation with duplicate email"""
        with patch.object(service, '_check_email_availability') as mock_check_email:
            mock_check_email.return_value = False
            
            with pytest.raises(AuthenticationError) as exc_info:
                await service.create_user(
                    email="existing@example.com",
                    password="password123",
                    first_name="Test",
                    last_name="User",
                    organization_id=uuid.uuid4()
                )
            
            assert "Email already exists" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_tokens(self, service, sample_user):
        """Test token generation"""
        with patch('src.core.security.create_access_token') as mock_access:
            with patch('src.core.security.create_refresh_token') as mock_refresh:

                mock_access.return_value = "access_token_123"
                mock_refresh.return_value = "refresh_token_456"

                tokens = await service.generate_tokens(sample_user)

                assert tokens["access_token"] == "access_token_123"
                assert tokens["refresh_token"] == "refresh_token_456"
                assert tokens["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_access_token(self, service, sample_user):
        """Test access token refresh"""
        with patch('src.core.security.verify_refresh_token') as mock_verify:
            with patch.object(service, '_get_user_by_id') as mock_get_user:
                with patch('src.core.security.create_access_token') as mock_create:

                    mock_verify.return_value = {"sub": str(sample_user.id)}
                    mock_get_user.return_value = sample_user
                    mock_create.return_value = "new_access_token"

                    new_token = await service.refresh_access_token("valid_refresh_token")

                    assert new_token == "new_access_token"


class TestRBACService:
    """Test Role-Based Access Control Service"""

    @pytest.fixture
    def service(self, mock_db_session):
        """Create RBAC service instance"""
        return RBACService(db=mock_db_session)

    def test_check_permission_admin(self, service, sample_user):
        """Test admin permission checking"""
        sample_user.role = UserRole.ADMIN
        
        assert service.check_permission(sample_user, "admin") is True
        assert service.check_permission(sample_user, "user") is True
        assert service.check_permission(sample_user, "analyst") is True

    def test_check_permission_user(self, service, sample_user):
        """Test user permission checking"""
        sample_user.role = UserRole.USER

        assert service.check_permission(sample_user, "user") is True
        assert service.check_permission(sample_user, "admin") is False
        assert service.check_permission(sample_user, "analyst") is False

    def test_check_resource_permission_owner(self, service, sample_user):
        """Test resource permission for owner"""
        resource = Mock()
        resource.owner_id = sample_user.id
        resource.organization_id = sample_user.organization_id

        assert service.check_resource_permission(sample_user, resource, "read") is True
        assert service.check_resource_permission(sample_user, resource, "write") is True

    def test_check_resource_permission_different_org(self, service, sample_user):
        """Test resource permission for different organization"""
        resource = Mock()
        resource.owner_id = uuid.uuid4()  # Different owner
        resource.organization_id = uuid.uuid4()  # Different org

        assert service.check_resource_permission(sample_user, resource, "read") is False
        assert service.check_resource_permission(sample_user, resource, "write") is False

    def test_check_organization_permission(self, service, sample_user):
        """Test organization-level permissions"""
        assert service.check_organization_permission(sample_user, sample_user.organization_id) is True
        assert service.check_organization_permission(sample_user, uuid.uuid4()) is False

    def test_get_user_permissions(self, service, sample_user):
        """Test getting user permissions list"""
        sample_user.role = UserRole.ANALYST

        permissions = service.get_user_permissions(sample_user)

        assert "user" in permissions
        assert "analyst" in permissions
        assert "admin" not in permissions

    @pytest.mark.asyncio
    async def test_authorize_action_success(self, service, sample_user):
        """Test successful action authorization"""
        sample_user.role = UserRole.ADMIN

        with patch.object(service, 'check_permission') as mock_check:
            mock_check.return_value = True

            result = await service.authorize_action(sample_user, "admin", "manage_users")

            assert result is True
            mock_check.assert_called_once_with(sample_user, "admin")

    @pytest.mark.asyncio
    async def test_authorize_action_failure(self, service, sample_user):
        """Test failed action authorization"""
        sample_user.role = UserRole.USER

        with patch.object(service, 'check_permission') as mock_check:
            mock_check.return_value = False

            with pytest.raises(AuthorizationError):
                await service.authorize_action(sample_user, "admin", "manage_users")

    def test_filter_accessible_resources(self, service, sample_user):
        """Test filtering resources by access permissions"""
        resources = [
            Mock(owner_id=sample_user.id, organization_id=sample_user.organization_id),
            Mock(owner_id=uuid.uuid4(), organization_id=sample_user.organization_id),
            Mock(owner_id=uuid.uuid4(), organization_id=uuid.uuid4())
        ]

        accessible = service.filter_accessible_resources(sample_user, resources)

        # User should only access resources from their organization
        assert len(accessible) == 2
        assert all(r.organization_id == sample_user.organization_id for r in accessible)


class TestAsyncServiceMethods:
    """Test async service method patterns"""
    
    @pytest.mark.asyncio
    async def test_async_mock_pattern(self):
        """Test AsyncMock usage pattern"""
        mock_service = Mock()
        mock_service.async_method = AsyncMock(return_value="async_result")
        
        result = await mock_service.async_method("test_param")
        
        assert result == "async_result"
        mock_service.async_method.assert_called_once_with("test_param")
    
    @pytest.mark.asyncio
    async def test_async_exception_handling(self):
        """Test async exception handling"""
        mock_service = Mock()
        mock_service.async_method = AsyncMock(side_effect=Exception("Async error"))
        
        with pytest.raises(Exception) as exc_info:
            await mock_service.async_method()
        
        assert "Async error" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])