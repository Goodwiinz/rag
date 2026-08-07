"""Disposable-database bootstrap, tenant seeding, and initial LangGraph state.

Consumed only by Harbor eval tasks added after 2026-08-07; the three original
tasks are digest-pinned and keep their inline copies. Ported from
`evals/agent-direct-project-action-v1/environment/run_agent.py`.

Every backend import (`src.core.*`, `src.models.*`) is deliberately made
*inside* the function bodies: importing this module must succeed in an
environment where the NOUS backend and its DB drivers are not installed, so
that syntax/import checks and unit tests of the pure helpers can run anywhere.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from .envelope import InfrastructureFailure

__all__ = [
    "bootstrap_schema",
    "seed_tenant",
    "initial_agent_state",
]


async def bootstrap_schema() -> None:
    """Provision the disposable benchmark DB from production ORM metadata.

    The repository's integration fixtures use this same path because the
    historical Alembic chain cannot bootstrap an empty database: its initial
    revision is a no-op and the next revision references tables that do not
    exist yet.  That migration defect is audit evidence, but it must not turn
    this agent capability benchmark into a migration benchmark.
    """
    try:
        from src.core.database import async_engine
        from src.models import Base

        async with async_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    except Exception as exc:
        raise InfrastructureFailure(
            f"SQLAlchemy metadata bootstrap failed: {type(exc).__name__}"
        ) from exc


async def seed_tenant(
    org_id: UUID | str,
    user_id: UUID | str,
    workspace_id: UUID | str,
    name_prefix: str = "Benchmark",
    email: str = "benchmark-route@example.invalid",
) -> None:
    """Seed one Organization / User / Workspace triple for a benchmark tenant.

    Generalizes the fixed-identifier seed prologue of the direct-project task.
    The encryption prologue (``initialize_encryption`` plus lazily generating a
    DATA key when none is active) is kept verbatim: several models encrypt
    columns on flush and fail without an active DATA key.
    """
    from src.core.database import AsyncSessionLocal
    from src.core.encryption import (
        EncryptionKeyType,
        get_key_manager,
        initialize_encryption,
    )
    from src.models.organization import Organization, StorageTier
    from src.models.user import User, UserRole
    from src.models.workspace import Workspace

    initialize_encryption()
    key_manager = get_key_manager()
    if key_manager.get_active_key(EncryptionKeyType.DATA) is None:
        key_manager.generate_key(EncryptionKeyType.DATA)
    async with AsyncSessionLocal() as session:
        session.add(
            Organization(
                id=org_id,
                name=f"{name_prefix} Organization",
                storage_tier=StorageTier.FREE,
                storage_used_bytes=0,
                storage_limit_bytes=10 * 1024**3,
                is_active=True,
            )
        )
        session.add(
            User(
                id=user_id,
                email=email,
                password_hash="benchmark-password-not-used",
                first_name=name_prefix,
                last_name="Route",
                role=UserRole.USER,
                is_active=True,
                organization_id=org_id,
            )
        )
        session.add(
            Workspace(
                id=workspace_id,
                name=f"{name_prefix} Workspace",
                description="Synthetic state for the Harbor benchmark.",
                owner_id=user_id,
                organization_id=org_id,
                is_archived=False,
                is_public=False,
            )
        )
        await session.commit()


def initial_agent_state(
    instruction: str,
    thread_id: str,
    **overrides: Any,
) -> dict[str, Any]:
    """Build the LangGraph entry state for a benchmark run.

    Mirrors the production graph's state contract. ``overrides`` is merged
    **last**, so a caller may replace any default (e.g. ``user_id``,
    ``current_project_id``, ``page_context``, or even ``messages``).

    ``langchain_core`` is imported lazily so this module stays importable
    without the agent runtime installed.
    """
    from langchain_core.messages import HumanMessage

    state: dict[str, Any] = {
        "messages": [HumanMessage(content=instruction)],
        "page_context": {},
        "retrieved_contexts": [],
        "tool_executions": [],
        "thread_id": thread_id,
        "tool_loop_count": 0,
        "error_count": 0,
        "last_error": "",
        "pending_confirmation": {},
        "user_confirmed": False,
        "intent": "",
        "user_memories": [],
        "project_memories": [],
        "plan": [],
        "reflection_count": 0,
        "compaction_count": 0,
        "intent_confidence": 0.0,
        "last_error_info": {},
        "user_id": "",
        "current_project_id": "",
        "model": "",
        "use_rag": False,
        "runtime_snapshot_id": "",
        "project_skill_catalog": [],
        "loaded_skill_versions": [],
        "_reflection_result": None,
        "_force_synthesis_fired": False,
        "tools_all_deduped": False,
    }
    state.update(overrides)
    return state
