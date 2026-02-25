"""
Security fix verification tests
"""
import pytest
from src.models.user import User, UserRole

class TestUserSecurity:
    """Test security fixes in User model"""

    def test_has_permission_string_vulnerability_fix(self):
        """
        Verify that passing a string 'admin' to has_permission
        does not grant admin privileges to a regular user.
        """
        user = User(role=UserRole.USER)

        # This was the vulnerability: passing "admin" string made it return True
        # Now it should return False (either via strict check or safe default)
        assert user.has_permission("admin") is False

        # Verify it works for other invalid strings
        assert user.has_permission("invalid_role") is False
        assert user.has_permission("") is False

    def test_has_permission_valid_usage(self):
        """Verify that valid usage with UserRole enum still works"""
        user = User(role=UserRole.USER)

        # User should have USER permission
        assert user.has_permission(UserRole.USER) is True

        # User should NOT have ADMIN permission
        assert user.has_permission(UserRole.ADMIN) is False

        admin = User(role=UserRole.ADMIN)
        # Admin should have ADMIN permission
        assert admin.has_permission(UserRole.ADMIN) is True
        # Admin should have USER permission
        assert admin.has_permission(UserRole.USER) is True

    def test_has_permission_string_conversion(self):
        """Verify that valid role strings are converted correctly"""
        user = User(role=UserRole.ADMIN)

        # "admin" string should be converted to UserRole.ADMIN and return True for admin user
        assert user.has_permission("admin") is True

        user_std = User(role=UserRole.USER)
        # "admin" string converted to UserRole.ADMIN, user has USER role, so should be False
        assert user_std.has_permission("admin") is False

        # "user" string converted to UserRole.USER, should be True
        assert user_std.has_permission("user") is True
