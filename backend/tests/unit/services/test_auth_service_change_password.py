from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.security.auth_service import (
    AuthService,
    AuthenticationError,
)


@pytest.mark.asyncio
async def test_change_password_fails_when_supabase_admin_client_is_missing():
    db = AsyncMock()
    service = AuthService(db)
    user = MagicMock()
    user.id = "user-123"
    user.password_hash = "hashed-password"

    with (
        patch(
            "src.services.security.auth_service.verify_password",
            return_value=True,
        ),
        patch(
            "src.services.security.auth_service.check_password_strength",
            return_value={"is_valid": True, "issues": []},
        ),
        patch(
            "src.services.security.auth_service.get_supabase_client",
            return_value=None,
        ),
    ):
        with pytest.raises(AuthenticationError, match="authentication service"):
            await service.change_password(
                user,
                current_password="CurrentPass123!",
                new_password="NewPass123!",
            )

    user.set_password.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_change_password_updates_supabase_before_local_hash():
    db = AsyncMock()
    service = AuthService(db)
    user = MagicMock()
    user.id = "user-123"
    user.password_hash = "hashed-password"
    supabase = SimpleNamespace(
        auth=SimpleNamespace(admin=MagicMock(update_user_by_id=MagicMock()))
    )

    with (
        patch(
            "src.services.security.auth_service.verify_password",
            return_value=True,
        ),
        patch(
            "src.services.security.auth_service.check_password_strength",
            return_value={"is_valid": True, "issues": []},
        ),
        patch(
            "src.services.security.auth_service.get_supabase_client",
            return_value=supabase,
        ),
    ):
        result = await service.change_password(
            user,
            current_password="CurrentPass123!",
            new_password="NewPass123!",
        )

    assert result is True
    supabase.auth.admin.update_user_by_id.assert_called_once_with(
        "user-123", {"password": "NewPass123!"}
    )
    user.set_password.assert_called_once_with("NewPass123!")
    db.commit.assert_awaited_once()
