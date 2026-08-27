"""Focused tests for the typed NOUS coordination boundary."""

from __future__ import annotations

import inspect
import traceback
from dataclasses import fields
from typing import Any, get_type_hints

import pytest

from scripts.nous.coordination import (
    BACKEND_STATES,
    BLOCKER_KINDS,
    CANDIDATE_SOURCES,
    INVALIDATED,
    OUTCOMES,
    STAGE_STATES,
    BackendUnavailable,
    Blocker,
    Candidate,
    Claim,
    ClaimLost,
    ClaimRequest,
    Conflict,
    CoordinationBackend,
    LocalMutex,
    Milestone,
    RunProjection,
    ValidationError,
    acquire_remote_then_local,
)

RUN_ID = "20260827T040000Z-agent-9f3a1c"
SHA = "a" * 40
OTHER_SHA = "b" * 40
STAMP = "2026-08-27T04:00:00+00:00"
LATER = "2026-08-27T07:00:00+00:00"


def _exception_graph(root: BaseException) -> list[BaseException]:
    seen: set[int] = set()
    pending = [root]
    graph: list[BaseException] = []
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        graph.append(current)
        if current.__context__ is not None:
            pending.append(current.__context__)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
    return graph


def make_candidate() -> Candidate:
    return Candidate(
        source="audit-ledger",
        summary="S-M4 stream buffer drops final chunk",
        lead_ref="docs/audits/examples/streaming-audit.md#S-M4",
    )


def make_claim() -> Claim:
    return Claim(
        claim_id="c-a1b2c3d4e5f6",
        run_id=RUN_ID,
        agent="agent",
        machine_id="linux",
        branch="fix/bug",
        area="bug",
        files=("x.py",),
        pr=None,
        status="active",
        claimed_at=STAMP,
        expires_at=LATER,
        renewed_at=None,
        candidate=None,
    )


def make_request() -> ClaimRequest:
    return ClaimRequest(
        run_id=RUN_ID,
        agent="agent",
        machine_id="linux",
        branch="fix/bug",
        area="bug",
        files=("x.py",),
        candidate=None,
        pr=None,
        ttl_seconds=10800,
        claim_id=None,
    )


def make_projection(**overrides: Any) -> RunProjection:
    values: dict[str, Any] = {
        "schema": 1,
        "run_id": RUN_ID,
        "agent": "agent",
        "machine_id": "linux",
        "claim_id": "c-a1b2c3d4e5f6",
        "state": "claimed",
        "outcome": None,
        "branch": "fix/bug",
        "area": "bug",
        "files": ("x.py",),
        "candidate": None,
        "base_sha": SHA,
        "evidence_head_sha": SHA,
        "pr": None,
        "parent_run_id": None,
        "blocker": None,
        "claim_expires_at": LATER,
        "milestones": (),
        "milestones_truncated": False,
        "updated_at": STAMP,
    }
    values.update(overrides)
    return RunProjection(**values)


class FakeCoordinationBackend:
    """A remote fake that records fencing and call ordering."""

    def __init__(
        self,
        *,
        claim_result: Claim,
        release_error: Exception | None = None,
        claim_error: Exception | None = None,
        timeline: list[str] | None = None,
    ) -> None:
        self.claim_result = claim_result
        self.release_error = release_error
        self.claim_error = claim_error
        self.calls: list[str] = []
        self.releases: list[tuple[str, str, str, bool]] = []
        self.timeline = timeline if timeline is not None else []

    def claim(self, **kwargs: Any) -> Claim:
        self.calls.append("remote.claim")
        self.timeline.append("remote.claim")
        if self.claim_error is not None:
            raise self.claim_error
        return self.claim_result

    def release(
        self, *, run_id: str, claim_id: str, reason: str, remove_run: bool = False
    ) -> None:
        self.calls.append("remote.release")
        self.timeline.append("remote.release")
        self.releases.append((run_id, claim_id, reason, remove_run))
        if self.release_error is not None:
            raise self.release_error


class FakeLocalMutex:
    """A legacy fake intentionally accepting only branch-keyed arguments."""

    def __init__(
        self, *, claim_error: Exception | None = None, timeline: list[str] | None = None
    ) -> None:
        self.claim_error = claim_error
        self.calls: list[str] = []
        self.claims: list[dict[str, object]] = []
        self.releases: list[tuple[str, str]] = []
        self.timeline = timeline if timeline is not None else []

    def claim_legacy(
        self,
        agent: str,
        branch: str,
        area: str,
        files: tuple[str, ...],
        pr: int | None,
        ttl_seconds: int,
    ) -> dict[str, object]:
        self.calls.append("local.claim_legacy")
        self.timeline.append("local.claim_legacy")
        self.claims.append(
            {
                "agent": agent,
                "branch": branch,
                "area": area,
                "files": files,
                "pr": pr,
                "ttl_seconds": ttl_seconds,
            }
        )
        if self.claim_error is not None:
            raise self.claim_error
        return {"branch": branch}

    def release_legacy(self, branch: str, reason: str) -> bool:
        self.calls.append("local.release_legacy")
        self.timeline.append("local.release_legacy")
        self.releases.append((branch, reason))
        return True


def test_dataclasses_have_exact_frozen_fields_and_keep_conflict_inputs():
    assert [field.name for field in fields(Candidate)] == [
        "source",
        "summary",
        "lead_ref",
    ]
    assert [field.name for field in fields(Claim)] == [
        "claim_id",
        "run_id",
        "agent",
        "machine_id",
        "branch",
        "area",
        "files",
        "pr",
        "status",
        "claimed_at",
        "expires_at",
        "renewed_at",
        "candidate",
    ]
    assert [field.name for field in fields(Milestone)] == [
        "state",
        "at",
        "evidence_head_sha",
        "tier",
    ]
    assert [field.name for field in fields(Blocker)] == ["kind", "detail"]
    assert [field.name for field in fields(RunProjection)] == [
        "schema",
        "run_id",
        "agent",
        "machine_id",
        "claim_id",
        "state",
        "outcome",
        "branch",
        "area",
        "files",
        "candidate",
        "base_sha",
        "evidence_head_sha",
        "pr",
        "parent_run_id",
        "blocker",
        "claim_expires_at",
        "milestones",
        "milestones_truncated",
        "updated_at",
    ]
    assert [field.name for field in fields(ClaimRequest)] == [
        "run_id",
        "agent",
        "machine_id",
        "branch",
        "area",
        "files",
        "candidate",
        "pr",
        "ttl_seconds",
        "claim_id",
        "base_sha",
        "evidence_head_sha",
    ]

    with pytest.raises((AttributeError, TypeError)):
        make_claim().claim_id = "c-000000000000"  # type: ignore[misc]

    projection = RunProjection(
        schema=1,
        run_id=RUN_ID,
        agent="agent",
        machine_id="linux",
        claim_id="c-a1b2c3d4e5f6",
        state="claimed",
        outcome=None,
        branch="fix/bug",
        area="bug",
        files=("x.py",),
        candidate=make_candidate(),
        base_sha=SHA,
        evidence_head_sha=SHA,
        pr=None,
        parent_run_id=None,
        blocker=None,
        claim_expires_at=LATER,
        milestones=(),
        milestones_truncated=False,
        updated_at=STAMP,
    )
    assert projection.files == ("x.py",)
    assert projection.candidate == make_candidate()


def test_models_validate_schema_values_and_hide_secret_input():
    assert CANDIDATE_SOURCES == ("trace", "audit-ledger", "backlog", "fresh-hunt")
    assert BLOCKER_KINDS == (
        "permission",
        "review-unavailable",
        "gate-unavailable",
        "red-check",
        "human-decision",
        "publication-unavailable",
        "other",
    )
    assert STAGE_STATES == (
        "started",
        "claimed",
        "reproduced",
        "fixed",
        "reviewed",
        "locally_verified",
        "published",
        "hosted_verified",
        "merged_verified",
    )
    assert OUTCOMES == ("merged", "ready-for-human", "dry", "cancelled")
    assert INVALIDATED == "invalidated"
    assert BACKEND_STATES == STAGE_STATES

    assert Candidate("trace", "short summary", None).summary == "short summary"
    assert Blocker("permission", "needs approval").kind == "permission"
    assert Milestone("invalidated", STAMP, SHA, None).state == "invalidated"
    assert Milestone("merged", STAMP, SHA, "remote").tier == "remote"

    invalid_values = (
        (Candidate, {"source": "unknown", "summary": "summary", "lead_ref": None}),
        (Candidate, {"source": "trace", "summary": "", "lead_ref": None}),
        (
            Candidate,
            {"source": "trace", "summary": "password: secret", "lead_ref": None},
        ),
        (Candidate, {"source": "trace", "summary": "summary", "lead_ref": "/x.py"}),
        (Candidate, {"source": "trace", "summary": "summary", "lead_ref": "../x.py"}),
        (Blocker, {"kind": "not-a-kind", "detail": "detail"}),
        (
            Milestone,
            {"state": "started", "at": STAMP, "evidence_head_sha": "bad", "tier": None},
        ),
    )
    for constructor, kwargs in invalid_values:
        with pytest.raises(ValidationError):
            constructor(**kwargs)

    secret = "ghp_abcdefghijklmnopqrstuvwxyz"
    with pytest.raises(ValidationError) as caught:
        Candidate("trace", secret, None)
    assert secret not in str(caught.value)
    assert caught.value.__cause__ is None


def test_validation_error_hides_secret_from_the_complete_exception_chain():
    secret = "ghp_" + "a" * 32
    with pytest.raises(ValidationError) as caught:
        Claim(
            claim_id="c-a1b2c3d4e5f6",
            run_id=RUN_ID,
            agent="agent",
            machine_id="linux",
            branch="fix/bug",
            area="bug",
            files=("x.py",),
            pr=None,
            status="active",
            claimed_at=secret,
            expires_at=LATER,
            renewed_at=None,
            candidate=None,
        )
    formatted = "".join(traceback.format_exception(caught.value))
    assert secret not in formatted
    assert caught.value.__cause__ is None
    assert caught.value.schema_error.__cause__ is None


def test_validation_error_has_no_reachable_parser_exception_chain():
    with pytest.raises(ValidationError) as caught:
        Claim(
            claim_id="c-a1b2c3d4e5f6",
            run_id=RUN_ID,
            agent="agent",
            machine_id="linux",
            branch="fix/bug",
            area="bug",
            files=("x.py",),
            pr=None,
            status="active",
            claimed_at="\ud800",
            expires_at=LATER,
            renewed_at=None,
            candidate=None,
        )

    assert _exception_graph(caught.value) == [caught.value]


def test_projection_blocker_requires_ready_for_human_outcome():
    blocker = Blocker("permission", "needs approval")
    with pytest.raises(ValidationError):
        make_projection(blocker=blocker)
    assert (
        make_projection(outcome="ready-for-human", blocker=blocker).blocker == blocker
    )


def test_projection_milestones_are_capped_at_forty_entries():
    milestone = Milestone("claimed", STAMP, SHA, None)
    with pytest.raises(ValidationError):
        make_projection(milestones=(milestone,) * 41)


def test_claim_request_separates_remote_fencing_from_legacy_mutex():
    request = ClaimRequest(
        run_id=RUN_ID,
        agent="agent",
        machine_id="linux",
        branch="fix/bug",
        area="bug",
        files=("x.py",),
        candidate=make_candidate(),
        pr=123,
        ttl_seconds=10800,
        claim_id="c-a1b2c3d4e5f6",
        base_sha=SHA,
        evidence_head_sha=OTHER_SHA,
    )
    assert request.as_kwargs() == {
        "run_id": RUN_ID,
        "agent": "agent",
        "machine_id": "linux",
        "branch": "fix/bug",
        "area": "bug",
        "files": ("x.py",),
        "candidate": make_candidate(),
        "pr": 123,
        "ttl_seconds": 10800,
        "claim_id": "c-a1b2c3d4e5f6",
        "base_sha": SHA,
        "evidence_head_sha": OTHER_SHA,
    }
    assert request.as_kwargs() is not request.as_kwargs()
    assert request.as_local_kwargs() == {
        "agent": "agent",
        "branch": "fix/bug",
        "area": "bug",
        "files": ("x.py",),
        "pr": 123,
        "ttl_seconds": 10800,
    }


def test_acquire_remote_then_local_compensates_remote_claim():
    timeline: list[str] = []
    remote = FakeCoordinationBackend(
        claim_result=make_claim(), release_error=None, timeline=timeline
    )
    local = FakeLocalMutex(claim_error=Conflict("same file"), timeline=timeline)
    request = make_request()
    assert request.as_kwargs()["claim_id"] is None
    assert set(request.as_local_kwargs()) == {
        "agent",
        "branch",
        "area",
        "files",
        "pr",
        "ttl_seconds",
    }
    with pytest.raises(Conflict):
        acquire_remote_then_local(remote=remote, local=local, request=request)
    assert remote.releases == [(RUN_ID, "c-a1b2c3d4e5f6", "local-conflict", True)]
    assert timeline == ["remote.claim", "local.claim_legacy", "remote.release"]


def test_failed_compensation_is_reported_as_pending():
    pending: list[Claim] = []
    remote = FakeCoordinationBackend(
        claim_result=make_claim(),
        release_error=BackendUnavailable("offline"),
    )
    local = FakeLocalMutex(claim_error=Conflict("same file"))
    with pytest.raises(BackendUnavailable):
        acquire_remote_then_local(
            remote=remote,
            local=local,
            request=make_request(),
            on_compensation_pending=pending.append,
        )
    assert pending and pending[0].claim_id == "c-a1b2c3d4e5f6"


def test_callback_failure_does_not_mask_compensating_backend_failure():
    remote = FakeCoordinationBackend(
        claim_result=make_claim(),
        release_error=BackendUnavailable("offline"),
    )
    local = FakeLocalMutex(claim_error=Conflict("same file"))

    def callback(_: Claim) -> None:
        raise RuntimeError("callback-failed")

    with pytest.raises(BackendUnavailable, match="offline"):
        acquire_remote_then_local(
            remote=remote,
            local=local,
            request=make_request(),
            on_compensation_pending=callback,
        )


def test_claim_mismatch_is_claim_lost_and_not_conflict():
    remote = FakeCoordinationBackend(
        claim_result=make_claim(), claim_error=ClaimLost("stale token")
    )
    local = FakeLocalMutex()
    with pytest.raises(ClaimLost) as caught:
        acquire_remote_then_local(remote=remote, local=local, request=make_request())
    assert not isinstance(caught.value, Conflict)
    assert local.calls == []


def test_protocols_describe_separate_remote_and_legacy_surfaces():
    assert issubclass(CoordinationBackend, object)
    assert issubclass(LocalMutex, object)
    assert "claim_legacy" in LocalMutex.__dict__
    assert "put_run" in CoordinationBackend.__dict__
    assert "get_run" in CoordinationBackend.__dict__
    assert "finalize_orphan" in CoordinationBackend.__dict__
    for remote_only in (
        "run_id",
        "claim_id",
        "put_run",
        "get_run",
        "finalize",
        "finalize_orphan",
    ):
        assert remote_only not in LocalMutex.__dict__


def test_protocol_signatures_are_frozen_with_exact_parameters_and_returns():
    expected = {
        CoordinationBackend: {
            "claim": (
                [
                    ("run_id", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("agent", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("machine_id", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("branch", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("area", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("files", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("candidate", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("pr", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("ttl_seconds", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("claim_id", inspect.Parameter.KEYWORD_ONLY, None),
                    ("base_sha", inspect.Parameter.KEYWORD_ONLY, None),
                    ("evidence_head_sha", inspect.Parameter.KEYWORD_ONLY, None),
                ],
                Claim,
            ),
            "assert_claim": (
                [
                    ("run_id", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("claim_id", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                ],
                Claim,
            ),
            "renew": (
                [
                    ("run_id", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("claim_id", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("ttl_seconds", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                ],
                Claim,
            ),
            "release": (
                [
                    ("run_id", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("claim_id", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("reason", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("remove_run", inspect.Parameter.KEYWORD_ONLY, False),
                ],
                type(None),
            ),
            "list": ([], list[Claim]),
            "list_runs": ([], tuple[RunProjection, ...]),
            "check": (
                [
                    ("area", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("files", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                ],
                list[Claim],
            ),
            "put_run": (
                [
                    (
                        "projection",
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect._empty,
                    ),
                    ("claim_id", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                ],
                type(None),
            ),
            "get_run": (
                [("run_id", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect._empty)],
                RunProjection,
            ),
            "finalize": (
                [
                    (
                        "projection",
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect._empty,
                    ),
                    ("claim_id", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                    ("release_claim", inspect.Parameter.KEYWORD_ONLY, inspect._empty),
                ],
                type(None),
            ),
            "finalize_orphan": (
                [
                    (
                        "projection",
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect._empty,
                    ),
                    (
                        "expected_claim_id",
                        inspect.Parameter.KEYWORD_ONLY,
                        inspect._empty,
                    ),
                    (
                        "expected_updated_at",
                        inspect.Parameter.KEYWORD_ONLY,
                        inspect._empty,
                    ),
                ],
                type(None),
            ),
        },
        LocalMutex: {
            "claim_legacy": (
                [
                    ("agent", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect._empty),
                    ("branch", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect._empty),
                    ("area", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect._empty),
                    ("files", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect._empty),
                    ("pr", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect._empty),
                    (
                        "ttl_seconds",
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect._empty,
                    ),
                ],
                dict[str, object],
            ),
            "heartbeat_legacy": (
                [
                    ("branch", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect._empty),
                    (
                        "ttl_seconds",
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect._empty,
                    ),
                ],
                type(None),
            ),
            "release_legacy": (
                [
                    ("branch", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect._empty),
                    ("reason", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect._empty),
                ],
                bool,
            ),
            "list_legacy": ([], list[dict[str, object]]),
            "check_legacy": (
                [
                    ("area", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect._empty),
                    ("files", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect._empty),
                ],
                list[dict[str, object]],
            ),
        },
    }

    for protocol, methods in expected.items():
        for name, (parameters, return_annotation) in methods.items():
            signature = inspect.signature(getattr(protocol, name))
            actual = list(signature.parameters.values())[1:]
            assert [
                (parameter.name, parameter.kind, parameter.default)
                for parameter in actual
            ] == parameters
            assert get_type_hints(getattr(protocol, name))["return"] == (
                return_annotation
            )
