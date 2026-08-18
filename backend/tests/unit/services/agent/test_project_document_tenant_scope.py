"""Tenant guards for the agent's project-document listing tool."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from src.models.user import User
from src.services.agent import tools_impl


@pytest.mark.asyncio
async def test_list_project_documents_scopes_count_and_rows_to_org() -> None:
    project = SimpleNamespace(id=uuid4(), name="Scoped project")
    current_user = cast(User, SimpleNamespace(id=uuid4(), organization_id=uuid4()))
    statements: list[str] = []

    count_result = Mock()
    count_result.scalar_one.return_value = 0
    rows_result = Mock()
    rows_result.scalars.return_value.all.return_value = []

    db = AsyncMock()

    async def capture_execute(statement: Any) -> Mock:
        statements.append(str(statement).lower())
        return count_result if len(statements) == 1 else rows_result

    db.execute = AsyncMock(side_effect=capture_execute)

    with patch.object(
        tools_impl,
        "_verify_project_ownership",
        AsyncMock(return_value=project),
    ):
        result = await tools_impl._tool_list_project_documents(
            {"project_id": str(project.id)}, db, current_user
        )

    assert result["documents"] == []
    assert len(statements) == 2
    for statement in statements:
        assert "documents.organization_id" in statement
        assert "collection_documents.is_deleted" in statement
