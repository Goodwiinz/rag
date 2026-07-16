"""Reuse the real-Postgres ``db_session`` + factories from ``tests.db.conftest``.

Task 4.3's service tests exercise the new ``src/services/threads/*`` modules
against actual ORM rows (soft-delete cascades, membership/role predicates,
ordering) rather than mocked query results, matching the established pattern
in ``backend/tests/api/threads/``.
"""

from tests.db.conftest import (  # noqa: F401
    _engine,
    db_session,
    organization_factory,
    thread_factory,
    user_factory,
)
