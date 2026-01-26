"""
Tests for authentication functionality
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from src.main import app
from src.core.database import get_db, Base
from src.core.config import settings
from src.models import User, Organization, UserRole, StorageTier

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function")
def client():
    """Create test client"""
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def test_organization():
    """Create test organization"""
    db = TestingSessionLocal()
    organization = Organization(
        name="Test Organization",
        storage_tier=StorageTier.FREE,
        storage_limit_bytes=Organization.get_default_storage_limit(StorageTier.FREE),
        is_active=True
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)
    db.close()
    return organization

@pytest.fixture(scope="function")
def test_user(test_organization):
    """Create test user"""
    db = TestingSessionLocal()
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role=UserRole.USER,
        organization_id=test_organization.id,
        is_active=True
    )
    user.set_password("testpassword123")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user

@pytest.fixture(scope="function")
def admin_user(test_organization):
    """Create admin user"""
    db = TestingSessionLocal()
    user = User(
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        organization_id=test_organization.id,
        is_active=True
    )
    user.set_password("adminpassword123")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user

def get_auth_headers(client, email: str, password: str):
    """Get authentication headers for a user"""
    response = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert response.status_code == 200
    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}

def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data

def test_register_user_success(client):
    """Test successful user registration"""
    response = client.post("/api/v1/auth/register", json={
        "email": "newuser@example.com",
        "password": "StrongPassword123!",
        "first_name": "New",
        "last_name": "User",
        "organization_name": "New Organization"
    })
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert data["user"]["email"] == "newuser@example.com"
    assert data["user"]["role"] == "admin"  # First user becomes admin

def test_register_user_weak_password(client):
    """Test registration with weak password fails"""
    response = client.post("/api/v1/auth/register", json={
        "email": "weakuser@example.com",
        "password": "123",
        "first_name": "Weak",
        "last_name": "User",
        "organization_name": "Weak Organization"
    })
    assert response.status_code == 400
    assert "Password does not meet security requirements" in response.json()["detail"]

def test_register_duplicate_email(client, test_user):
    """Test registration with duplicate email fails"""
    response = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",  # Same as test_user
        "password": "StrongPassword123!",
        "first_name": "Duplicate",
        "last_name": "User",
        "organization_name": "Duplicate Organization"
    })
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

def test_login_success(client, test_user):
    """Test successful login"""
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data

def test_login_invalid_credentials(client, test_user):
    """Test login with invalid credentials"""
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]

def test_login_nonexistent_user(client):
    """Test login with non-existent user"""
    response = client.post("/api/v1/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "somepassword"
    })
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]

def test_get_current_user(client, test_user):
    """Test getting current user info"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "test@example.com"
    assert "password_hash" not in data["user"]

def test_get_current_user_unauthorized(client):
    """Test getting current user without authentication"""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

def test_update_profile(client, test_user):
    """Test updating user profile"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")
    response = client.put("/api/v1/auth/me", headers=headers, json={
        "first_name": "Updated",
        "last_name": "Name"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["first_name"] == "Updated"
    assert data["user"]["last_name"] == "Name"

def test_change_password_success(client, test_user):
    """Test successful password change"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")
    response = client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "testpassword123",
        "new_password": "NewPassword123!"
    })
    assert response.status_code == 200
    assert "Password changed successfully" in response.json()["message"]

def test_change_password_wrong_current(client, test_user):
    """Test password change with wrong current password"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")
    response = client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "wrongpassword",
        "new_password": "NewPassword123!"
    })
    assert response.status_code == 400
    assert "Current password is incorrect" in response.json()["detail"]

def test_refresh_token_success(client, test_user):
    """Test successful token refresh"""
    # First login to get refresh token
    login_response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword123"
    })
    login_data = login_response.json()
    refresh_token = login_data["refresh_token"]

    # Use refresh token to get new access token
    response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_refresh_token_invalid(client):
    """Test refresh with invalid token"""
    response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": "invalid_token"
    })
    assert response.status_code == 401

def test_get_users_admin(client, admin_user, test_user):
    """Test getting users list (admin only)"""
    headers = get_auth_headers(client, "admin@example.com", "adminpassword123")
    response = client.get("/api/v1/auth/users", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert len(data["users"]) >= 2  # admin_user and test_user

def test_get_users_regular_user_forbidden(client, test_user):
    """Test getting users list as regular user (should fail)"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")
    response = client.get("/api/v1/auth/users", headers=headers)
    assert response.status_code == 403

def test_update_user_role_admin(client, admin_user, test_user):
    """Test updating user role (admin only)"""
    headers = get_auth_headers(client, "admin@example.com", "adminpassword123")
    response = client.put(
        f"/api/v1/auth/users/{test_user.id}/role",
        headers=headers,
        json={"role": "analyst"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["role"] == "analyst"

def test_deactivate_user_admin(client, admin_user, test_user):
    """Test deactivating user (admin only)"""
    headers = get_auth_headers(client, "admin@example.com", "adminpassword123")
    response = client.post(f"/api/v1/auth/users/{test_user.id}/deactivate", headers=headers)
    assert response.status_code == 200
    assert "deactivated successfully" in response.json()["message"]

def test_get_user_statistics_admin(client, admin_user):
    """Test getting user statistics (admin only)"""
    headers = get_auth_headers(client, "admin@example.com", "adminpassword123")
    response = client.get("/api/v1/auth/statistics", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_users" in data
    assert "users_by_role" in data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])