"""Synthetic agent-traffic generator for the NOUS dev cluster.

Drives the compiled LangGraph agent in-process (no HTTP) with a real
Postgres session and a dedicated synthetic user so every run produces
LangSmith traces in ``rag-agent-dev`` — exactly the same project and
signal shape as real user traffic.

Scheduling
----------
A Kubernetes CronJob (``templates/synthetic-traffic-cronjob.yaml``) runs
this every 20 minutes on the dev cluster via::

    python -m scripts.synthetic_traffic [--rotate|--all|--scenario <key>|--cleanup]

To disable: set ``syntheticTraffic.enabled: false`` in ``values-dev.yaml``
and let ArgoCD sync.  No code changes needed.

Cleanup
-------
Every run (unless ``--cleanup`` is passed alone) ends with a lightweight
cleanup pass that soft-deletes Collections owned by the synthetic user
whose names start with ``synthtraffic-`` and that were created more than
6 hours ago, preventing accumulation of junk in the dev database.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog

# ---------------------------------------------------------------------------
# Logging — prefer structlog when available, fall back to stdlib
# ---------------------------------------------------------------------------
try:
    log = structlog.get_logger(__name__)
except Exception:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    log = logging.getLogger(__name__)  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYNTH_EMAIL = "synthetic-traffic@nous.dev"
SYNTH_FIRST_NAME = "Synthetic"
SYNTH_LAST_NAME = "Traffic"
SYNTH_PREFIX = "synthtraffic-"

# Rotate window: one scenario per 20-minute window keeps cost bounded while
# ensuring full coverage across 8 × 20 min = 2.7 h.
ROTATE_WINDOW_S = 1200  # 20 minutes in seconds

MAX_HITL_RESUMES = 3
SCENARIO_TIMEOUT_S = 360  # cap per scenario to match jobs._run_agent_graph


# ---------------------------------------------------------------------------
# Scenario catalogue  (mirrors the perf harness + adds create/ingest)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    key: str
    prompt: str
    budget_s: float
    expect_interrupt: bool = False
    page_context: Dict[str, Any] = field(default_factory=dict)


def _ts() -> str:
    """Short timestamp suffix for project names."""
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")


SCENARIOS: List[Scenario] = [
    Scenario(
        key="greeting",
        prompt="hi",
        budget_s=3.0,
        page_context={"type": "general"},
    ),
    Scenario(
        key="general_qa",
        prompt="What is retrieval-augmented generation, in two sentences?",
        budget_s=15.0,
        page_context={"type": "general"},
    ),
    Scenario(
        key="research_arxiv",
        prompt="Search arXiv for recent papers on retrieval-augmented generation.",
        budget_s=45.0,
        page_context={"type": "general"},
    ),
    Scenario(
        key="kg_query",
        prompt=(
            "What entities and relationships are in the knowledge graph for transformers?"
        ),
        budget_s=45.0,
        page_context={"type": "general"},
    ),
    Scenario(
        key="writing_draft",
        prompt="Draft a short note summarizing the key ideas behind RAG.",
        budget_s=45.0,
        page_context={"type": "general"},
    ),
    Scenario(
        key="create_project",
        # Prompt is a template; _build_prompt fills the timestamp.
        prompt=f"Create a project called {SYNTH_PREFIX}{{ts}}",
        budget_s=30.0,
        expect_interrupt=True,
        page_context={"type": "general"},
    ),
    Scenario(
        key="ingest",
        prompt=(
            f"Ingest the arXiv paper 1706.03762 into a project named {SYNTH_PREFIX}{{ts}}"
        ),
        budget_s=60.0,
        expect_interrupt=True,
        page_context={"type": "general"},
    ),
]

SCENARIOS_BY_KEY: Dict[str, Scenario] = {s.key: s for s in SCENARIOS}


def _expand_prompt(scenario: Scenario) -> str:
    """Substitute ``{ts}`` with a UTC timestamp so project names are unique."""
    return scenario.prompt.replace("{ts}", _ts())


# ---------------------------------------------------------------------------
# Synthetic user + workspace bootstrap
# ---------------------------------------------------------------------------


async def _get_or_create_synth_user(db: Any) -> Any:
    """Return the synthetic user, creating it (+ a Workspace) if absent.

    Matches the seeding shape in ``database.init_database``:
    - UserRole.USER (non-admin; the agent needs no elevated rights)
    - organization_id = None (personal; avoids FK to a real org)
    - is_active = True
    - password: random (synthetic user never authenticates via HTTP)
    """
    from sqlalchemy import select, text

    from src.models.organization import Organization, StorageTier
    from src.models.user import User
    from src.models.workspace import Workspace

    # 1. Look up user
    result = await db.execute(select(User).where(User.email == SYNTH_EMAIL))
    user: Optional[Any] = result.scalar_one_or_none()

    if user is None:
        log.info("synthetic_traffic.bootstrap", action="create_user", email=SYNTH_EMAIL)

        # Ensure an org exists for the synthetic user so FK is satisfied
        # when other models reference organization_id.  Reuse the default
        # org if it exists; otherwise create a synthetic one.
        org_result = await db.execute(select(Organization).limit(1))
        org: Optional[Any] = org_result.scalar_one_or_none()
        if org is None:
            org = Organization(
                name="Synthetic Traffic Org",
                storage_tier=StorageTier.FREE,
                storage_limit_bytes=Organization.get_default_storage_limit(
                    StorageTier.FREE
                ),
                is_active=True,
            )
            db.add(org)
            await db.flush()

        # Insert the user via raw SQL, NOT the ORM. User.first_name/last_name
        # use an encrypted column type whose bind-param encrypts on flush, but
        # ENCRYPTION_MASTER_KEY is unset in dev (real users are created by the
        # Supabase handle_new_user trigger at SQL level, never the ORM), so an
        # ORM insert raises "Encryption not initialized". Plaintext names are
        # fine here: the agent never reads them, and the read path returns the
        # raw value when decryption fails.
        new_id = uuid.uuid4()
        # Build a valid bcrypt hash without flushing (set_password mutates the
        # transient object; password_hash is a plain, non-encrypted column).
        _tmp = User(email=SYNTH_EMAIL)
        _tmp.set_password(f"synth-{uuid.uuid4().hex}")
        pw_hash = _tmp.password_hash
        await db.execute(
            text(
                "INSERT INTO users (id, email, password_hash, first_name, "
                "last_name, role, is_active, organization_id, login_count, "
                "created_at, updated_at, is_deleted) VALUES (:id, :email, :pw, "
                ":fn, :ln, CAST(:role AS userrole), true, :org, 0, now(), "
                "now(), false) ON CONFLICT (email) DO NOTHING"
            ),
            {
                "id": new_id,
                "email": SYNTH_EMAIL,
                "pw": pw_hash,
                "fn": SYNTH_FIRST_NAME,
                "ln": SYNTH_LAST_NAME,
                # The userrole PG enum uses the Python member NAMES (uppercase),
                # not the lowercase values — SQLAlchemy Enum's default mapping.
                "role": "USER",
                "org": org.id,
            },
        )
        await db.commit()

        result = await db.execute(select(User).where(User.email == SYNTH_EMAIL))
        user = result.scalar_one_or_none()
        if user is None:
            # Insert lost a race or failed — fall back to any active user so the
            # job still produces traffic rather than dying.
            fb = await db.execute(select(User).where(User.is_active.is_(True)).limit(1))
            user = fb.scalar_one_or_none()
            if user is None:
                raise RuntimeError("synthetic_traffic: no usable user found")
            log.warning(
                "synthetic_traffic.bootstrap",
                action="fallback_existing_user",
                user_id=str(user.id),
            )
            return user

        # Create a default workspace so project tools have a home
        workspace = Workspace(
            name=f"{SYNTH_PREFIX}workspace",
            description="Auto-created for synthetic traffic generation",
            owner_id=user.id,
            organization_id=org.id,
            is_archived=False,
            is_public=False,
        )
        db.add(workspace)
        await db.flush()

        await db.commit()
        log.info(
            "synthetic_traffic.bootstrap",
            action="user_created",
            user_id=str(user.id),
        )
    else:
        log.debug(
            "synthetic_traffic.bootstrap", action="user_found", user_id=str(user.id)
        )

    return user


# ---------------------------------------------------------------------------
# Graph builder (reuses the checkpointer + store, falls back to MemorySaver)
# ---------------------------------------------------------------------------


async def _build_graph() -> Any:
    """Compile the production agent graph with the durable checkpointer.

    Falls back to ``MemorySaver`` when Postgres is unreachable so the
    script can still produce LangSmith traces in degraded environments.
    """
    from src.services.agent.graph import compile_agent_graph

    checkpointer = None
    store = None
    try:
        from src.services.agent.checkpointer import get_checkpointer
        from src.services.agent.memory import get_memory_store

        checkpointer = await get_checkpointer()
        store = await get_memory_store()
    except Exception:
        log.warning(
            "synthetic_traffic.build_graph",
            warning="checkpointer unavailable, falling back to MemorySaver",
        )
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()
        store = None

    return compile_agent_graph(checkpointer=checkpointer, store=store)


# ---------------------------------------------------------------------------
# Per-scenario driver
# ---------------------------------------------------------------------------


@dataclass
class TurnResult:
    scenario: str
    wall_clock_s: float
    interrupted: bool
    resumes: int
    intent: str
    tool_executions: int
    assistant_preview: str
    error: Optional[str] = None


async def run_scenario(
    scenario: Scenario,
    graph: Any,
    db: Any,
    user: Any,
) -> TurnResult:
    """Drive one agent scenario with a real DB session + user.

    HITL auto-confirm: on ``GraphInterrupt`` we resume with
    ``Command(resume={"confirmed": True})`` up to ``MAX_HITL_RESUMES``
    times so destructive tools (create_project / ingest) actually execute
    rather than hanging on the interrupt.

    The scenario result is logged regardless of error; exceptions are
    swallowed so a single failure never aborts the whole sweep.
    """
    from langchain_core.messages import HumanMessage
    from langgraph.errors import GraphInterrupt
    from langgraph.types import Command

    from src.services.agent._builders import RECURSION_LIMIT

    deploy_env = __import__("os").environ.get("ENVIRONMENT", "dev")
    commit = (
        __import__("os").environ.get("GIT_COMMIT")
        or __import__("os").environ.get("GITHUB_SHA")
        or __import__("os").environ.get("COMMIT_SHA")
        or "unknown"
    )

    prompt = _expand_prompt(scenario)
    thread_id = f"synthetic-{scenario.key}-{int(time.time() * 1000)}"

    initial_state = {
        "messages": [HumanMessage(content=prompt)],
        "page_context": dict(scenario.page_context),
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
        "user_id": str(user.id),
        "current_project_id": "",
        "model": "",
        "_reflection_result": None,
        "_force_synthesis_fired": False,
    }

    # Discriminate synthetic traffic in LangSmith via run_name + metadata, both
    # of which reliably land on the uploaded root run. (A post-hoc
    # Client.update_run to tag the finalized root run is rejected by LangSmith —
    # "Duplicate run update requests for the same run are not supported" — so we
    # don't attempt it; filter dashboards on metadata.synthetic or the
    # `synthetic:` run-name prefix instead.) Config "tags" are kept as a
    # best-effort hint; they tag child runs even when they don't reach the root.
    config = {
        "recursion_limit": RECURSION_LIMIT,
        "run_name": f"synthetic:{scenario.key}",
        "tags": [
            "synthetic-traffic",
            f"scenario:{scenario.key}",
            f"deploy:{deploy_env}",
        ],
        "metadata": {
            "synthetic": True,
            "scenario": scenario.key,
            "deploy_env": deploy_env,
            "commit": commit,
            "user_id": str(user.id),
            "org_id": str(getattr(user, "organization_id", "") or ""),
            "thread_id": thread_id,
        },
        "configurable": {
            "thread_id": thread_id,
            "db": db,
            "current_user": user,
            "page_context": dict(scenario.page_context),
        },
    }

    interrupted = False
    resumes = 0
    error: Optional[str] = None
    final_state: Dict[str, Any] = {}

    t0 = time.perf_counter()
    try:
        async with asyncio.timeout(SCENARIO_TIMEOUT_S):
            final_state = await graph.ainvoke(initial_state, config=config)
    except GraphInterrupt:
        # Defensive fallback only. With a checkpointer attached (this graph
        # always has one — real Postgres or the MemorySaver fallback, never
        # None), LangGraph's interrupt() returns `__interrupt__` in the state
        # rather than raising — proven in
        # tests/unit/agent/test_interrupt_ainvoke_semantics.py. Before this
        # fix, this was the ONLY detection path, so create_project/ingest
        # (the two expect_interrupt=True scenarios) silently never triggered
        # the resume loop below across every sampled run.
        interrupted = True
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    # Primary interrupt detection: check the state ainvoke() actually
    # returned. Mirrors the real, working mechanism streaming.py uses
    # (aget_state + snapshot.tasks[*].interrupts) for the SSE path.
    if not error and (interrupted or final_state.get("__interrupt__")):
        interrupted = True
        # Auto-confirm HITL interrupts so destructive tools actually execute
        while interrupted and resumes < MAX_HITL_RESUMES:
            resumes += 1
            log.info(
                "synthetic_traffic.hitl",
                scenario=scenario.key,
                resume=resumes,
            )
            try:
                async with asyncio.timeout(SCENARIO_TIMEOUT_S):
                    final_state = await graph.ainvoke(
                        Command(resume={"confirmed": True}), config=config
                    )
                interrupted = bool(final_state.get("__interrupt__"))
            except GraphInterrupt:
                interrupted = True
                continue
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                break

    wall = time.perf_counter() - t0

    intent = ""
    assistant_preview = ""
    tool_executions_count = 0
    if final_state:
        intent = final_state.get("intent", "") or ""
        tool_executions_count = len(final_state.get("tool_executions", []) or [])
        for msg in reversed(final_state.get("messages", []) or []):
            if getattr(msg, "type", None) == "ai" and getattr(msg, "content", None):
                assistant_preview = str(msg.content)[:160]
                break

    result = TurnResult(
        scenario=scenario.key,
        wall_clock_s=wall,
        interrupted=interrupted,
        resumes=resumes,
        intent=intent,
        tool_executions=tool_executions_count,
        assistant_preview=assistant_preview,
        error=error,
    )

    flag = "INTERRUPT" if (interrupted and resumes == 0) else "ok"
    if resumes > 0 and not interrupted:
        flag = f"confirmed({resumes})"
    if error:
        flag = f"ERROR {error}"
    over = " OVER-BUDGET" if wall >= scenario.budget_s else ""
    log.info(
        "synthetic_traffic.scenario_done",
        scenario=scenario.key,
        wall_s=round(wall, 2),
        budget_s=scenario.budget_s,
        over_budget=bool(over),
        intent=intent or "-",
        tool_executions=tool_executions_count,
        flag=flag,
        resumes=resumes,
    )

    return result


# ---------------------------------------------------------------------------
# Cleanup pass
# ---------------------------------------------------------------------------


async def cleanup(db: Any, user: Any, older_than_hours: int = 6) -> None:
    """Soft-delete synthetic Collections (projects) older than ``older_than_hours``.

    Targets only Collections:
    - owned via a Workspace owned by the synthetic user
    - whose name starts with ``SYNTH_PREFIX``
    - created more than ``older_than_hours`` hours ago
    - not already soft-deleted

    Uses ``BaseModel.soft_delete()`` to match the codebase convention.
    Never raises — errors are logged and ignored so the cleanup failure
    cannot block a future run.
    """
    try:
        from sqlalchemy import select

        from src.models.collection import Collection
        from src.models.workspace import Workspace

        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=older_than_hours)

        # Fetch all Workspaces owned by the synthetic user
        ws_result = await db.execute(
            select(Workspace).where(
                Workspace.owner_id == user.id,
                Workspace.is_deleted == False,  # noqa: E712
            )
        )
        workspaces = ws_result.scalars().all()
        if not workspaces:
            log.debug("synthetic_traffic.cleanup", msg="no workspaces found")
            return

        ws_ids = [ws.id for ws in workspaces]

        # Fetch matching stale Collections
        coll_result = await db.execute(
            select(Collection).where(
                Collection.workspace_id.in_(ws_ids),
                Collection.name.like(f"{SYNTH_PREFIX}%"),
                Collection.created_at < cutoff,
                Collection.is_deleted == False,  # noqa: E712
            )
        )
        collections = coll_result.scalars().all()

        if not collections:
            log.debug("synthetic_traffic.cleanup", msg="nothing to clean up")
            return

        deleted = 0
        for coll in collections:
            try:
                coll.soft_delete()
                deleted += 1
            except Exception as exc:
                log.warning(
                    "synthetic_traffic.cleanup",
                    warning="soft_delete failed",
                    collection_id=str(coll.id),
                    error=str(exc),
                )

        if deleted:
            await db.commit()

        log.info(
            "synthetic_traffic.cleanup",
            deleted=deleted,
            cutoff_hours=older_than_hours,
        )
    except Exception as exc:
        log.warning(
            "synthetic_traffic.cleanup",
            warning="cleanup pass failed",
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _choose_scenario_rotate() -> Scenario:
    """Pick one scenario deterministically by rotating through the list.

    Uses ``int(time.time() / ROTATE_WINDOW_S) % len(SCENARIOS)`` so the
    same scenario is chosen across any restart within the same 20-minute
    window, and coverage cycles fully in ``len(SCENARIOS) × 20 min``.
    """
    idx = int(time.time() / ROTATE_WINDOW_S) % len(SCENARIOS)
    return SCENARIOS[idx]


async def _main(args: argparse.Namespace) -> int:
    from src.core.database import AsyncSessionLocal
    from src.services.agent.observability import configure_langsmith

    configure_langsmith()

    # Field-level encryption must be initialized before any User write — the
    # User model encrypts first_name/last_name on insert. The app does this in
    # its startup lifespan; this standalone CronJob script does not boot the
    # app, so initialize it here or the synthetic-user INSERT raises
    # "Encryption not initialized" (ENCRYPTION_MASTER_KEY is in app-secrets).
    try:
        from src.core.encryption import initialize_encryption

        initialize_encryption()
    except Exception as exc:  # pragma: no cover - best effort
        log.warning("synthetic_traffic: encryption init failed: %s", exc)

    run_cleanup_only = getattr(args, "cleanup", False)

    async with AsyncSessionLocal() as db:
        user = await _get_or_create_synth_user(db)

        if run_cleanup_only:
            await cleanup(db, user)
            return 0

        # Build graph once; reuse across scenarios
        graph = await _build_graph()

        scenarios_to_run: List[Scenario] = []

        if getattr(args, "all", False):
            scenarios_to_run = list(SCENARIOS)
        elif getattr(args, "scenario", None):
            key = args.scenario
            if key not in SCENARIOS_BY_KEY:
                log.error(
                    "synthetic_traffic.main",
                    error=f"Unknown scenario key: {key!r}. "
                    f"Valid keys: {list(SCENARIOS_BY_KEY)}",
                )
                return 1
            scenarios_to_run = [SCENARIOS_BY_KEY[key]]
        else:
            # Default: --rotate
            scenarios_to_run = [_choose_scenario_rotate()]

        results: List[TurnResult] = []
        for scenario in scenarios_to_run:
            try:
                result = await run_scenario(scenario, graph, db, user)
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "synthetic_traffic.scenario_unhandled",
                    scenario=scenario.key,
                    error=str(exc),
                )

        total_wall = sum(r.wall_clock_s for r in results)
        errored = [r for r in results if r.error]
        log.info(
            "synthetic_traffic.sweep_done",
            scenarios=len(results),
            total_wall_s=round(total_wall, 2),
            errored=len(errored),
        )

        # Always run cleanup at the end (unless this was a --cleanup-only run)
        await cleanup(db, user)

    return 1 if errored else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synthetic agent-traffic generator for the NOUS dev cluster."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--rotate",
        action="store_true",
        default=False,
        help=(
            "Run ONE scenario chosen by rotating through the list based on "
            f"the current time (default; cycles every {ROTATE_WINDOW_S}s)."
        ),
    )
    mode.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Run every scenario once sequentially.",
    )
    mode.add_argument(
        "--scenario",
        metavar="KEY",
        help=f"Run one named scenario. Valid keys: {[s.key for s in SCENARIOS]}",
    )
    mode.add_argument(
        "--cleanup",
        action="store_true",
        default=False,
        help="Run ONLY the cleanup pass (delete stale synthetic projects).",
    )

    args = parser.parse_args()

    # If no flag is given, behave as --rotate
    if not (args.all or args.scenario or args.cleanup):
        args.rotate = True

    return asyncio.run(_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
