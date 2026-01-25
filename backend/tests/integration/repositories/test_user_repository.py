"""
User Repository Integration Tests

Tests for User model with real PostgreSQL database to validate:
- Unique email constraint
- Organization foreign key constraint
- Password hashing and verification
- Soft delete functionality
- Role-based permissions
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# Mark all tests in this module
pytestmark = [
    pytest.mark.requires_postgres,
    pytest.mark.integration,
]


@pytest.fixture(scope="function")
def db_session(postgres_container):
    """Create a database session with all tables for user testing."""
    from src.models.base import Base
    from src.models.user import User, UserRole
    from src.models.organization import Organization, StorageTier
    # Import ab_testing to resolve User -> Experiment relationship
    from src.models import ab_testing  # noqa: F401

    engine = create_engine(postgres_container["url"])
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # Drop tables with CASCADE to handle circular dependencies in ab_testing
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.commit()
        engine.dispose()


@pytest.fixture
def test_organization(db_session):
    """Create a test organization."""
    from src.models.organization import Organization, StorageTier

    org = Organization(
        id=uuid.uuid4(),
        name=f"Test Org {uuid.uuid4().hex[:8]}",
        storage_tier=StorageTier.PROFESSIONAL,
        storage_limit_bytes=100 * 1024 ** 3,
        is_active=True,
    )
    db_session.add(org)
    db_session.commit()
    return org


class TestUserCreation:
    """Tests for user creation."""

    def test_creates_user_with_all_fields(self, db_session, test_organization):
        """Verify user creation with all required and optional fields."""
        from src.models.user import User, UserRole
        from src.core.security import get_password_hash

        user = User(
            id=uuid.uuid4(),
            email="fulluser@example.com",
            password_hash=get_password_hash("securepassword123"),
            first_name="Full",
            last_name="User",
            role=UserRole.ADMIN,
            organization_id=test_organization.id,
            is_active=True,
            login_count=5,
        )

        db_session.add(user)
        db_session.commit()

        saved_user = db_session.query(User).filter_by(id=user.id).first()
        assert saved_user is not None
        assert saved_user.email == "fulluser@example.com"
        assert saved_user.first_name == "Full"
        assert saved_user.last_name == "User"
        assert saved_user.role == UserRole.ADMIN
        assert saved_user.full_name == "Full User"

    def test_creates_user_with_hashed_password(self, db_session, test_organization):
        """Verify password is stored as hash, not plaintext."""
        from src.models.user import User, UserRole
        from src.core.security import get_password_hash, verify_password

        plain_password = "mysecretpassword123"
        password_hash = get_password_hash(plain_password)

        user = User(
            id=uuid.uuid4(),
            email="hashtest@example.com",
            password_hash=password_hash,
            first_name="Hash",
            last_name="Test",
            role=UserRole.USER,
            organization_id=test_organization.id,
        )

        db_session.add(user)
        db_session.commit()

        saved_user = db_session.query(User).filter_by(email="hashtest@example.com").first()

        # Password should NOT be stored in plaintext
        assert saved_user.password_hash != plain_password
        assert saved_user.password_hash.startswith("$2b$")  # bcrypt hash prefix

        # Password verification should work
        assert verify_password(plain_password, saved_user.password_hash)
        assert not verify_password("wrongpassword", saved_user.password_hash)


class TestUserConstraints:
    """Tests for database constraints."""

    def test_enforces_unique_email(self, db_session, test_organization):
        """Verify unique constraint on email."""
        from src.models.user import User, UserRole
        from src.core.security import get_password_hash

        email = "unique@example.com"

        user1 = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=get_password_hash("password1"),
            first_name="First",
            last_name="User",
            role=UserRole.USER,
            organization_id=test_organization.id,
        )
        db_session.add(user1)
        db_session.commit()

        # Try to create another user with same email
        user2 = User(
            id=uuid.uuid4(),
            email=email,  # Same email - should fail
            password_hash=get_password_hash("password2"),
            first_name="Second",
            last_name="User",
            role=UserRole.USER,
            organization_id=test_organization.id,
        )
        db_session.add(user2)

        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()

    def test_enforces_organization_fk_constraint(self, db_session):
        """Verify foreign key constraint on organization_id."""
        from src.models.user import User, UserRole
        from src.core.security import get_password_hash

        fake_org_id = uuid.uuid4()  # Non-existent organization

        user = User(
            id=uuid.uuid4(),
            email="noorg@example.com",
            password_hash=get_password_hash("password"),
            first_name="No",
            last_name="Org",
            role=UserRole.USER,
            organization_id=fake_org_id,  # Invalid FK
        )

        db_session.add(user)

        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()

        assert "foreign key" in str(exc_info.value).lower() or "violates" in str(exc_info.value).lower()

    def test_allows_multiple_users_same_org(self, db_session, test_organization):
        """Verify multiple users can belong to same organization."""
        from src.models.user import User, UserRole
        from src.core.security import get_password_hash

        users = []
        for i in range(3):
            user = User(
                id=uuid.uuid4(),
                email=f"user{i}@example.com",
                password_hash=get_password_hash(f"password{i}"),
                first_name=f"User{i}",
                last_name="Test",
                role=UserRole.USER,
                organization_id=test_organization.id,
            )
            users.append(user)

        db_session.add_all(users)
        db_session.commit()

        org_users = db_session.query(User).filter_by(organization_id=test_organization.id).all()
        assert len(org_users) == 3


class TestSoftDelete:
    """Tests for soft delete functionality."""

    def test_soft_deletes_user(self, db_session, test_organization):
        """Verify soft delete marks user but preserves data."""
        from src.models.user import User, UserRole
        from src.core.security import get_password_hash

        user = User(
            id=uuid.uuid4(),
            email="softdelete@example.com",
            password_hash=get_password_hash("password"),
            first_name="Soft",
            last_name="Delete",
            role=UserRole.USER,
            organization_id=test_organization.id,
        )
        db_session.add(user)
        db_session.commit()

        user_id = user.id

        # Soft delete
        user.soft_delete()
        db_session.commit()

        # User should still exist in database
        soft_deleted_user = db_session.query(User).filter_by(id=user_id).first()
        assert soft_deleted_user is not None
        assert soft_deleted_user.is_deleted is True
        assert soft_deleted_user.deleted_at is not None

        # But email should still be queryable (for audit purposes)
        assert soft_deleted_user.email == "softdelete@example.com"

    def test_soft_deleted_user_cannot_login(self, db_session, test_organization):
        """Verify soft deleted users are filtered from active queries."""
        from src.models.user import User, UserRole
        from src.core.security import get_password_hash

        user = User(
            id=uuid.uuid4(),
            email="inactivelogin@example.com",
            password_hash=get_password_hash("password"),
            first_name="Inactive",
            last_name="Login",
            role=UserRole.USER,
            organization_id=test_organization.id,
        )
        db_session.add(user)
        db_session.commit()

        user.soft_delete()
        db_session.commit()

        # Query for active users should not include soft-deleted
        active_user = db_session.query(User).filter_by(
            email="inactivelogin@example.com",
            is_deleted=False
        ).first()
        assert active_user is None


class TestRolePermissions:
    """Tests for role-based permissions."""

    def test_role_hierarchy_permissions(self, db_session, test_organization):
        """Verify role hierarchy permission checks."""
        from src.models.user import User, UserRole
        from src.core.security import get_password_hash

        admin = User(
            id=uuid.uuid4(),
            email="admin@example.com",
            password_hash=get_password_hash("password"),
            first_name="Admin",
            last_name="User",
            role=UserRole.ADMIN,
            organization_id=test_organization.id,
        )

        analyst = User(
            id=uuid.uuid4(),
            email="analyst@example.com",
            password_hash=get_password_hash("password"),
            first_name="Analyst",
            last_name="User",
            role=UserRole.ANALYST,
            organization_id=test_organization.id,
        )

        regular = User(
            id=uuid.uuid4(),
            email="regular@example.com",
            password_hash=get_password_hash("password"),
            first_name="Regular",
            last_name="User",
            role=UserRole.USER,
            organization_id=test_organization.id,
        )

        db_session.add_all([admin, analyst, regular])
        db_session.commit()

        # Admin has all permissions
        assert admin.has_permission(UserRole.USER)
        assert admin.has_permission(UserRole.ANALYST)
        assert admin.has_permission(UserRole.ADMIN)
        assert admin.can_manage_users()
        assert admin.can_view_analytics()

        # Analyst can view analytics but not manage users
        assert analyst.has_permission(UserRole.USER)
        assert analyst.has_permission(UserRole.ANALYST)
        assert not analyst.has_permission(UserRole.ADMIN)
        assert not analyst.can_manage_users()
        assert analyst.can_view_analytics()

        # Regular user has basic permissions
        assert regular.has_permission(UserRole.USER)
        assert not regular.has_permission(UserRole.ANALYST)
        assert not regular.has_permission(UserRole.ADMIN)
        assert not regular.can_manage_users()
        assert not regular.can_view_analytics()


class TestLoginTracking:
    """Tests for login tracking functionality."""

    def test_updates_login_stats(self, db_session, test_organization):
        """Verify login tracking updates timestamp and count."""
        from src.models.user import User, UserRole
        from src.core.security import get_password_hash

        user = User(
            id=uuid.uuid4(),
            email="logintrack@example.com",
            password_hash=get_password_hash("password"),
            first_name="Login",
            last_name="Track",
            role=UserRole.USER,
            organization_id=test_organization.id,
        )
        db_session.add(user)
        db_session.commit()

        # Initial state
        assert user.login_count == 0
        assert user.last_login is None

        # Simulate logins
        user.update_last_login()
        db_session.commit()

        assert user.login_count == 1
        assert user.last_login is not None

        first_login = user.last_login

        # Second login
        user.update_last_login()
        db_session.commit()

        assert user.login_count == 2
        assert user.last_login >= first_login
