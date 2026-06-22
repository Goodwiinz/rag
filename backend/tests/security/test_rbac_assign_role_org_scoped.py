"""Regression: assign_role_to_user is scoped to the target user's org.

assign_role_to_user validated that the *role* belonged to organization_id but
never checked that the target user_id was a member of that org. Because the
user_id is path-controlled (POST /users/{user_id}/roles), a caller could grant
a role to a user in another tenant. The fix verifies the target user belongs to
organization_id before creating/updating the assignment.
"""

from unittest.mock import MagicMock

import pytest

from src.exceptions.analytics_exceptions import ConfigurationException
from src.models.permission import Role, UserRoleAssignment
from src.models.user import User
from src.services.security.rbac_service import RBACService


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


def _make_db(*, role, user_in_org, existing_assignment=None):
    """Route db.query(...) by the queried entity.

    Role -> role validation; User -> membership check;
    UserRoleAssignment -> existing-assignment lookup.
    """

    def query(entity):
        # db.query(User.id) passes a column; resolve to its parent class.
        target = getattr(entity, "class_", entity)
        if target is Role:
            return _FakeQuery(role)
        if target is User:
            return _FakeQuery(user_in_org)
        if target is UserRoleAssignment:
            return _FakeQuery(existing_assignment)
        raise AssertionError(f"unexpected query entity: {entity!r}")

    db = MagicMock()
    db.query.side_effect = query
    return db


@pytest.mark.unit
def test_assign_rejects_user_outside_org():
    role = MagicMock(name="role", name_attr="r")
    db = _make_db(role=role, user_in_org=None)
    svc = RBACService(db)

    with pytest.raises(ConfigurationException):
        svc.assign_role_to_user(
            user_id="user-other-org",
            role_id="role-1",
            organization_id="org-1",
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.unit
def test_assign_creates_for_member():
    role = MagicMock()
    role.name = "editor"
    db = _make_db(role=role, user_in_org=(1,), existing_assignment=None)
    svc = RBACService(db)

    assignment = svc.assign_role_to_user(
        user_id="user-1",
        role_id="role-1",
        organization_id="org-1",
    )

    assert isinstance(assignment, UserRoleAssignment)
    assert assignment.user_id == "user-1"
    assert assignment.organization_id == "org-1"
    db.add.assert_called_once()
    db.commit.assert_called_once()
