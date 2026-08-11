#!/usr/bin/env python3
"""Drive the production HITL interrupt lifecycle through the real FastAPI job API.

Four independent phases against one booted ``src.main:app`` process, sharing
one seeded org/user/workspace, each creating a job via ``POST /execute`` that
pauses on the production ``create_project`` interrupt:

  * ``approve_once``       - confirm once; assert exactly one mutation.
  * ``reject``              - deny; assert zero mutation.
  * ``reconfirm_resolved``  - re-send confirm twice more against phase 1's
                              now-resolved job; assert a stable, mutation-free
                              response.
  * ``cancel_while_parked`` - poll a parked job without confirming, proving
                              the interrupt is re-delivered unchanged, then
                              confirm it to leave a clean terminal state.

See ``evals/specs/agent-hitl-lifecycle-v1/harness.md`` for the full contract.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, select

from evals.harbor_common.db import bootstrap_schema, seed_tenant
from evals.harbor_common.envelope import InfrastructureFailure
from evals.harbor_common.network import validate_network_boundary
from evals.harbor_common.serialization import json_safe, utc_now

BENCHMARK_ID = "agent-hitl-lifecycle-v1"
SOURCE_REVISION = "ba71044eb99019c1813cd7593838c6f98d35639c"
AGENT_REVISION = SOURCE_REVISION

ORG_ID = UUID("00000000-0000-4000-8000-000000000801")
USER_ID = UUID("00000000-0000-4000-8000-000000000802")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000803")

APPROVE_PROJECT_NAME = "HITL Approve And Reconfirm"
REJECT_PROJECT_NAME = "HITL Reject Path"
CANCEL_PROJECT_NAME = "HITL Cancel While Parked"

APP_URL = "http://127.0.0.1:8081"
POLL_TIMEOUT_SECONDS = 45.0
POLL_INTERVAL_SECONDS = 0.5

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"
APP_LOG_PATH = AGENT_LOG_DIR / "app.log"


# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------
async def seed_database() -> None:
    await seed_tenant(
        org_id=ORG_ID,
        user_id=USER_ID,
        workspace_id=WORKSPACE_ID,
        name_prefix="HITL Lifecycle Benchmark",
        email="hitl-lifecycle-benchmark@example.invalid",
    )


async def project_row_count(name: str) -> int:
    """Independent-shaped count, but read through the adapter's own session.

    The verifier's authoritative signal is its *own* psycopg connection
    (``tests/verify.py:live_database_state``); this helper is the adapter's
    sequential, load-bearing snapshot — the same trust level as
    ``agent-project-management-v1``'s ``before_approvals`` rows.
    """
    from src.core.database import AsyncSessionLocal
    from src.models.collection import Collection

    async with AsyncSessionLocal() as session:
        return int(
            await session.scalar(
                select(func.count(Collection.id)).where(
                    Collection.workspace_id == WORKSPACE_ID,
                    Collection.name == name,
                    Collection.is_deleted.is_(False),
                )
            )
            or 0
        )


# --------------------------------------------------------------------------
# application lifecycle
# --------------------------------------------------------------------------
async def start_application() -> tuple[asyncio.subprocess.Process, Any]:
    AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = APP_LOG_PATH.open("w")
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "uvicorn",
        "src.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8081",
        "--log-level",
        "info",
        stdout=log_handle,
        stderr=asyncio.subprocess.STDOUT,
    )
    return process, log_handle


async def wait_for_application(process: asyncio.subprocess.Process) -> dict[str, Any]:
    deadline = time.monotonic() + 90
    last_error = "not started"
    async with httpx.AsyncClient(trust_env=False, timeout=3) as client:
        while time.monotonic() < deadline:
            if process.returncode is not None:
                raise InfrastructureFailure(
                    f"FastAPI process exited during startup with {process.returncode}"
                )
            try:
                response = await client.get(f"{APP_URL}/api/v1/agent/health")
                if response.status_code == 200:
                    return {"ready": True, "status_code": response.status_code}
                last_error = f"HTTP {response.status_code}"
            except (httpx.HTTPError, ValueError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            await asyncio.sleep(0.25)
    raise InfrastructureFailure(f"FastAPI readiness timed out: {last_error}")


async def stop_application(
    process: asyncio.subprocess.Process | None, log_handle: Any | None
) -> int | None:
    exit_code: int | None = None
    if process is not None:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        exit_code = process.returncode
    if log_handle is not None:
        log_handle.flush()
        log_handle.close()
    return exit_code


# --------------------------------------------------------------------------
# job API driving
# --------------------------------------------------------------------------
async def create_job(
    client: httpx.AsyncClient, headers: dict[str, str], name: str
) -> str:
    response = await client.post(
        f"{APP_URL}/api/v1/agent/execute",
        headers=headers,
        json={
            "messages": [
                {
                    "role": "user",
                    "content": f'Create a research project named "{name}".',
                }
            ],
            "use_rag": False,
        },
    )
    if response.status_code != 200:
        raise InfrastructureFailure(
            f"/execute returned HTTP {response.status_code}: {response.text[:500]}"
        )
    job_id = response.json().get("job_id")
    if not job_id:
        raise InfrastructureFailure("/execute response carried no job_id")
    return str(job_id)


async def poll_job(
    client: httpx.AsyncClient, headers: dict[str, str], job_id: str, *, until: str
) -> dict[str, Any]:
    """Poll ``GET /jobs/{job_id}`` until ``status`` matches ``until``."""
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    last_body: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = await client.get(
            f"{APP_URL}/api/v1/agent/jobs/{job_id}", headers=headers
        )
        if response.status_code != 200:
            raise InfrastructureFailure(
                f"/jobs/{job_id} returned HTTP {response.status_code}: {response.text[:300]}"
            )
        last_body = response.json()
        if last_body.get("status") == until:
            return last_body
        if until == "awaiting_confirmation" and last_body.get("status") in {
            "completed",
            "failed",
        }:
            raise InfrastructureFailure(
                f"job {job_id} reached {last_body.get('status')!r} without ever "
                "pausing for confirmation — no interrupt was observed"
            )
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    raise InfrastructureFailure(
        f"job {job_id} did not reach status {until!r} within "
        f"{POLL_TIMEOUT_SECONDS:.0f}s (last seen: {last_body.get('status')!r})"
    )


async def confirm_job(
    client: httpx.AsyncClient, headers: dict[str, str], job_id: str, confirmed: bool
) -> httpx.Response:
    return await client.post(
        f"{APP_URL}/api/v1/agent/confirm/{job_id}",
        headers=headers,
        json={"confirmed": confirmed},
    )


def final_message(job_body: dict[str, Any]) -> dict[str, Any]:
    result = job_body.get("result") or {}
    content = result.get("message") if isinstance(result, dict) else None
    return {"content": content} if content else {}


# --------------------------------------------------------------------------
# phases
# --------------------------------------------------------------------------
async def run_approve_once(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> dict[str, Any]:
    job_id = await create_job(client, headers, APPROVE_PROJECT_NAME)
    parked = await poll_job(client, headers, job_id, until="awaiting_confirmation")
    interrupt = json_safe(parked.get("confirmation") or {})
    rows_before = await project_row_count(APPROVE_PROJECT_NAME)

    response = await confirm_job(client, headers, job_id, confirmed=True)
    if response.status_code != 200:
        raise InfrastructureFailure(
            f"first /confirm on a fresh interrupt returned HTTP "
            f"{response.status_code}: {response.text[:300]}"
        )
    settled = await poll_job(client, headers, job_id, until="completed")
    rows_after = await project_row_count(APPROVE_PROJECT_NAME)
    tool_executions = settled.get("tool_executions") or []
    execution_count = sum(
        1
        for item in tool_executions
        if isinstance(item, dict) and item.get("tool_name") == "create_project"
    )

    return {
        "tool": "create_project",
        "args": {"name": APPROVE_PROJECT_NAME},
        "interrupt": interrupt,
        "job_id": job_id,
        "rows_before_approval": rows_before,
        "rows_after_approval": rows_after,
        "tool_execution_count_after_approval": execution_count,
        "final_assistant_message": final_message(settled),
    }


async def run_reject(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> dict[str, Any]:
    job_id = await create_job(client, headers, REJECT_PROJECT_NAME)
    parked = await poll_job(client, headers, job_id, until="awaiting_confirmation")
    interrupt = json_safe(parked.get("confirmation") or {})
    rows_before = await project_row_count(REJECT_PROJECT_NAME)

    response = await confirm_job(client, headers, job_id, confirmed=False)
    if response.status_code != 200:
        raise InfrastructureFailure(
            f"/confirm(confirmed=false) returned HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )
    settled = await poll_job(client, headers, job_id, until="completed")
    rows_after = await project_row_count(REJECT_PROJECT_NAME)

    return {
        "tool": "create_project",
        "args": {"name": REJECT_PROJECT_NAME},
        "interrupt": interrupt,
        "job_id": job_id,
        "rows_before_reject": rows_before,
        "rows_after_reject": rows_after,
        "final_assistant_message": final_message(settled),
    }


async def run_reconfirm_resolved(
    client: httpx.AsyncClient, headers: dict[str, str], approve_once: dict[str, Any]
) -> dict[str, Any]:
    job_id = approve_once["job_id"]
    attempts: list[dict[str, Any]] = []
    for _ in range(2):
        response = await confirm_job(client, headers, job_id, confirmed=True)
        rows_after = await project_row_count(APPROVE_PROJECT_NAME)
        attempts.append({"http_status": response.status_code, "rows_after": rows_after})
    return {"job_id": job_id, "attempts": attempts}


async def run_cancel_while_parked(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> dict[str, Any]:
    job_id = await create_job(client, headers, CANCEL_PROJECT_NAME)
    parked = await poll_job(client, headers, job_id, until="awaiting_confirmation")
    interrupt_first = json_safe(parked.get("confirmation") or {})

    polls: list[dict[str, Any]] = []
    for _ in range(2):
        # Model the client abandoning/cancelling its wait: it neither confirms
        # nor rejects, it simply polls again later. The interrupt must still
        # be sitting there, byte-identical, the next time anyone looks.
        again = await poll_job(client, headers, job_id, until="awaiting_confirmation")
        polls.append(json_safe(again.get("confirmation") or {}))

    response = await confirm_job(client, headers, job_id, confirmed=True)
    if response.status_code != 200:
        raise InfrastructureFailure(
            f"cleanup /confirm on the parked job returned HTTP "
            f"{response.status_code}: {response.text[:300]}"
        )
    settled = await poll_job(client, headers, job_id, until="completed")
    rows_after = await project_row_count(CANCEL_PROJECT_NAME)

    return {
        "tool": "create_project",
        "args": {"name": CANCEL_PROJECT_NAME},
        "job_id": job_id,
        "interrupt_first": interrupt_first,
        "polls": polls,
        "resumed_after_cancel": {"rows_after": rows_after},
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
async def run_benchmark() -> dict[str, Any]:
    started_at = utc_now()
    started = time.monotonic()

    network_boundary = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", "")
    )
    await bootstrap_schema()
    await seed_database()
    for name in (APPROVE_PROJECT_NAME, REJECT_PROJECT_NAME, CANCEL_PROJECT_NAME):
        if await project_row_count(name) != 0:
            raise InfrastructureFailure(
                f"database reset failed: a project named {name!r} exists before the run"
            )

    from src.services.agent.checkpointer import get_db_uri

    checkpoint_uri = get_db_uri()
    checkpoint_scheme = (
        checkpoint_uri.split("://", 1)[0] if "://" in checkpoint_uri else ""
    )

    process: asyncio.subprocess.Process | None = None
    log_handle: Any | None = None
    app_exit_code: int | None = None
    try:
        process, log_handle = await start_application()
        health = await wait_for_application(process)

        from src.core.security import create_cli_token

        token, _expires_at = create_cli_token(
            str(USER_ID),
            "hitl-lifecycle-benchmark@example.invalid",
            str(ORG_ID),
            role="USER",
        )
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
            approve_once = await run_approve_once(client, headers)
            reject = await run_reject(client, headers)
            reconfirm_resolved = await run_reconfirm_resolved(
                client, headers, approve_once
            )
            cancel_while_parked = await run_cancel_while_parked(client, headers)
    finally:
        app_exit_code = await stop_application(process, log_handle)

    return {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "source_revision": SOURCE_REVISION,
        "agent_revision": AGENT_REVISION,
        "started_at": started_at,
        "completed_at": utc_now(),
        "synthetic_actor": {
            "organization_id": str(ORG_ID),
            "user_id": str(USER_ID),
            "workspace_id": str(WORKSPACE_ID),
        },
        "network_boundary": network_boundary,
        "application": {**health, "shutdown_exit_code": app_exit_code},
        "checkpointer": {"db_uri_scheme": checkpoint_scheme},
        "phases": {
            "approve_once": approve_once,
            "reject": reject,
            "reconfirm_resolved": reconfirm_resolved,
            "cancel_while_parked": cancel_while_parked,
        },
        "termination_reason": "completed",
        "model_usage": {"input_tokens": 0, "output_tokens": 0, "cache_tokens": 0},
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "notes": (
            "Production FastAPI job API (/execute, /jobs/{job_id}, "
            "/confirm/{job_id}) against an isolated database and Redis, "
            "driving four independent HITL lifecycle phases."
        ),
    }


def build_trajectory(evidence: dict[str, Any]) -> dict[str, Any]:
    """Minimal ATIF-shaped trajectory: this task has no single message log.

    Each phase is its own HTTP session rather than one LangGraph thread, so
    ``harbor_common.trajectory.build_atif_trajectory`` (which reconstructs
    steps from a single ``messages`` list) does not apply. The four phases
    are rendered as one step each instead.
    """
    phases = evidence.get("phases") or {}
    steps = []
    for index, (name, phase) in enumerate(phases.items(), start=1):
        steps.append(
            {
                "step_id": index,
                "source": "agent",
                "message": f"phase:{name}",
                "observation": {"results": [{"content": json.dumps(json_safe(phase))}]},
            }
        )
    return {
        "schema_version": "ATIF-v1.7",
        "session_id": BENCHMARK_ID,
        "trajectory_id": f"{BENCHMARK_ID}:{evidence.get('started_at')}",
        "agent": {
            "name": "nous-production-agent",
            "version": str(evidence.get("agent_revision") or "")[:12],
            "model_name": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        },
        "steps": steps,
        "notes": evidence.get("notes") or "",
        "final_metrics": {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cached_tokens": 0,
            "total_steps": len(steps),
        },
        "extra": {
            "benchmark_id": BENCHMARK_ID,
            "source_revision": evidence.get("source_revision"),
            "termination_reason": evidence.get("termination_reason"),
        },
    }


async def async_main() -> int:
    AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        evidence = await run_benchmark()
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        TRAJECTORY_PATH.write_text(
            json.dumps(build_trajectory(evidence), indent=2, sort_keys=True)
        )
        print(
            json.dumps(
                {
                    "benchmark_id": BENCHMARK_ID,
                    "termination_reason": evidence["termination_reason"],
                    "elapsed_ms": evidence["elapsed_ms"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        error = {
            "benchmark_id": BENCHMARK_ID,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        (AGENT_LOG_DIR / "infrastructure-error.json").write_text(
            json.dumps(error, indent=2, sort_keys=True)
        )
        print(
            f"benchmark infrastructure failure: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 70
    finally:
        try:
            from src.services.agent._pool_utils import close_shared_langgraph_pool
            from src.services.agent.checkpointer import close_checkpointer

            await asyncio.gather(close_checkpointer(), return_exceptions=True)
            await close_shared_langgraph_pool()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
