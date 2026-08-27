# NOUS coordination compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the existing local flock board behind a typed coordination boundary while keeping every legacy scripts/loop_bridge.py behavior, file, monkeypatch point, and exit code unchanged.

**Architecture:** scripts/nous/schema.py owns shared validation primitives; coordination.py owns immutable remote claim/run models, typed failures, and the remote-then-local acquisition contract; backend_local.py contains the existing branch-keyed LocalMutex semantics. scripts/loop_bridge.py becomes a thin CLI adapter that still resolves its patchable Path and DEFAULT_BRIDGE_DIR through the local mutex.

**Tech Stack:** Python 3.11+ standard library (dataclasses, datetime, fcntl, json, pathlib, typing, contextlib) and pytest only in tests/unit/scripts/.

**Spec:** docs/superpowers/specs/2026-08-27-nous-cross-machine-coordination-design.md

## Global Constraints

- All new code under scripts/nous/ is pure Python standard library; no third-party imports are allowed.
- The legacy board keeps the exact claims.json, log.jsonl, and .lock format, strict corrupt-state behavior, atomic tmp-write-then-rename publication, and non-mutating list.
- scripts/loop_bridge.py keeps module-level main(argv) -> int, patchable Path and DEFAULT_BRIDGE_DIR, the claim, heartbeat, release, list, and check flags, and exit codes 0 success, 2 conflict, 1 usage/error.
- The legacy default TTL remains DEFAULT_TTL_SECONDS = 45 * 60; the new three-hour TTL belongs only to scripts/nous_run.py in Plan 1.
- No remote branch, subprocess runner, cutover sentinel, or GitHub behavior is introduced in this plan; those belong to Plan 2a. LocalBackend implements only the branch-keyed LocalMutex interface; it is not a CoordinationBackend and has no remote run projection or claim-id API.
- Every task uses a red/green cycle and ends with one scoped commit; do not edit application backend code or install application dependencies.

## File map and dependency boundary

| Path | Ownership in this plan |
| --- | --- |
| scripts/nous/__init__.py | New package marker and __version__ constant. |
| scripts/nous/schema.py | Shared scalar validators, candidate/legacy state validation helpers, and size/charset constants. |
| scripts/nous/coordination.py | Claim, Candidate, Milestone, Blocker, RunProjection, the remote CoordinationBackend, the branch-keyed LocalMutex interface, error types, and the remote-first/local-second compensation helper. |
| scripts/nous/backend_local.py | Flock, strict legacy JSON decode, observational reads, atomic writes, audit append, overlap, TTL, and the LocalMutex legacy adapter. |
| scripts/loop_bridge.py | Only the CLI adapter; preserve its public module attributes and parser surface. |
| tests/unit/scripts/test_nous_schema.py | Validation contracts and stdlib-only imports. |
| tests/unit/scripts/test_nous_coordination.py | Dataclass/protocol/error and compensation contracts. |
| tests/unit/scripts/test_nous_backend_local.py | Local board behavior and corrupt-state/non-mutating-read contracts. |
| tests/unit/scripts/test_nous_loop_bridge_adapter.py | Delegation and compatibility guard tests; the existing test_loop_bridge.py remains untouched. |

Plan 1 consumes Claim, RunProjection, CoordinationBackend, LocalMutex, and the typed errors. Plan 2a consumes the remote protocol and LocalMutex compensation helper for GitBackend/CombinedBackend; it must not introduce a second claim model or make LocalBackend a remote backend.

### Task 1: Establish the package and shared validation primitives

**Files:**
- Create: scripts/nous/__init__.py
- Create: scripts/nous/schema.py
- Create: tests/unit/scripts/test_nous_schema.py

**Interfaces:**
- Produces validate_run_id(value: str) -> str, validate_agent(value: str) -> str, validate_machine_id(value: str) -> str, validate_branch(value: str) -> str, validate_branch_syntax(value: str, checker: Callable[[str], bool] | None = None) -> str, validate_area(value: str) -> str, validate_files(values: Sequence[str]) -> tuple[str, ...], validate_sha(value: str) -> str, validate_pr(value: int | None) -> int | None, validate_timestamp(value: str) -> str, and reject_secret_text(value: str, *, field: str) -> str.
- Produces decode_legacy_claims(raw: str) -> dict[str, object] and validate_legacy_claim(claim: Mapping[str, object], *, index: int) -> None; these deliberately enforce the current bridge schema rather than the stricter remote schema.
- Produces constants CLAIMS_MAX_BYTES = 64 * 1024, RUN_MAX_BYTES = 16 * 1024, MAX_FILES = 50, MAX_AREA_CHARS = 200, MAX_PATH_CHARS = 200, MAX_BRANCH_CHARS = 120, MAX_AGENT_CHARS = 64, MAX_MACHINE_ID_CHARS = 64, MAX_PR = 10**7, SKEW_SECONDS = 120, CANDIDATE_SOURCES = ("trace", "audit-ledger", "backlog", "fresh-hunt"), and BLOCKER_KINDS = ("permission", "review-unavailable", "gate-unavailable", "red-check", "human-decision", "publication-unavailable", "other") for later plans.
- Consumes no repository or application module. Every validator raises SchemaError(ValueError) with a field-specific message that does not echo a rejected secret value.

- [ ] **Step 1: Write failing scalar and legacy-state tests**

Add the following focused tests. Use exact valid/invalid values so later implementations cannot widen the contract:

~~~python
def test_run_id_and_remote_scalars_reject_traversal_and_secrets():
    from scripts.nous import schema
    from scripts.nous.schema import SchemaError
    import pytest

    assert schema.validate_run_id("20260827T040000Z-agent-9f3a1c")
    with pytest.raises(SchemaError):
        schema.validate_run_id("../runs/evil")
    with pytest.raises(SchemaError):
        schema.validate_branch("-delete-me")
    with pytest.raises(SchemaError):
        schema.reject_secret_text("token=ghp_abcdefghijklmnopqrstuvwxyz", field="area")


def test_legacy_decoder_keeps_old_claim_shape():
    from scripts.nous.schema import decode_legacy_claims
    raw = '{"claims": [{"agent": "a", "branch": "b", "area": "x", "files": [], "pr": null, "status": "active", "claimed_at": "2026-01-01T00:00:00+00:00", "expires_at": "2026-01-01T01:00:00+00:00"}]}'
    assert decode_legacy_claims(raw)["claims"][0]["branch"] == "b"


def test_legacy_decoder_rejects_missing_expiry():
    from scripts.nous.schema import SchemaError, decode_legacy_claims
    import pytest
    with pytest.raises(SchemaError):
        decode_legacy_claims('{"claims": [{"agent": "a"}]}')
~~~

- [ ] **Step 2: Run the schema tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_schema.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL during collection with ModuleNotFoundError: No module named scripts.nous.

- [ ] **Step 3: Implement the package and validators**

Create the package marker and implement validators with compiled re patterns. Use datetime.fromisoformat and require timezone information; encode text as UTF-8 and reject every character with ord(ch) < 32 or ord(ch) == 127; reject newlines/tabs before regex checks. validate_agent must match ^[A-Za-z0-9][A-Za-z0-9@._-]{0,63}$ and validate_machine_id must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$. validate_run_id must match ^[0-9]{8}T[0-9]{6}Z-[a-z0-9-]{1,32}-[a-f0-9]{6}$. validate_branch must reject leading -, whitespace, .., and @{, and expose validate_branch_syntax(value: str, checker: Callable[[str], bool] | None = None) -> str. When checker is supplied it must return true for the exact git check-ref-format --branch rule; with no checker, enforce the conservative local subset without spawning a process. validate_files must enforce at most 50 repo-relative paths, each at most 200 characters, with no leading / or -, .. segment, or backslash; validate_area must enforce at most 200 characters.

Implement secret patterns exactly from the spec: AKIA[0-9A-Z]{16}, ghp_[A-Za-z0-9]{20,}, github_pat_, gho_, sk-[A-Za-z0-9]{20,}, xox[baprs]-, private-key headers, case-insensitive credential assignments, and a single base64-alphabet token of at least 40 characters. validate_sha accepts only lowercase 40-hex strings and never runs the generic secret heuristic. decode_legacy_claims parses JSON, requires an object root and list claims, and calls validate_legacy_claim for every item while preserving unknown legacy keys exactly as the bridge does today.

Minimal implementation shape:

~~~python
class SchemaError(ValueError):
    """A schema or untrusted-input validation rejection."""


def validate_sha(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise SchemaError("sha must be exactly 40 lowercase hexadecimal characters")
    return value


def reject_secret_text(value: str, *, field: str) -> str:
    if not isinstance(value, str) or _CONTROL.search(value):
        raise SchemaError(f"{field} contains invalid text")
    if any(pattern.search(value) for pattern in _SECRET_PATTERNS):
        raise SchemaError(f"{field} matches a prohibited secret pattern")
    return value
~~~

- [ ] **Step 4: Run the schema tests to verify the green result**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_schema.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS with all schema tests green and no third-party import error.

- [ ] **Step 5: Commit the shared schema contract**

~~~bash
git add scripts/nous/__init__.py scripts/nous/schema.py tests/unit/scripts/test_nous_schema.py
git commit -m "feat(nous): add coordination schema validators"
~~~

### Task 2: Define typed coordination models, protocol, and compensation contract

**Files:**
- Create: scripts/nous/coordination.py
- Create: tests/unit/scripts/test_nous_coordination.py

**Interfaces:**
- Consumes SchemaError, validate_sha, validate_run_id, validate_agent, validate_machine_id, validate_branch, validate_area, validate_files, validate_timestamp, and reject_secret_text from scripts.nous.schema.
- Produces frozen dataclasses with exact fields: Candidate(source: str, summary: str, lead_ref: str | None), Claim(claim_id: str, run_id: str, agent: str, machine_id: str, branch: str, area: str, files: tuple[str, ...], pr: int | None, status: str, claimed_at: str, expires_at: str, renewed_at: str | None, candidate: Candidate | None), Milestone(state: str, at: str, evidence_head_sha: str, tier: str | None), Blocker(kind: str, detail: str), and RunProjection(schema: int, run_id: str, agent: str, machine_id: str, claim_id: str, state: str, outcome: str | None, branch: str, area: str, files: tuple[str, ...], candidate: Candidate | None, base_sha: str, evidence_head_sha: str, pr: int | None, parent_run_id: str | None, blocker: Blocker | None, claim_expires_at: str, milestones: tuple[Milestone, ...], milestones_truncated: bool, updated_at: str). RunProjection carries the original files and candidate descriptor so an expired cross-machine lease can be re-claimed with the same conflict inputs; milestones_truncated is a top-level flag rather than a non-Milestone marker entry.
- Produces typed errors CoordinationError, Conflict, ClaimLost, BackendUnavailable, and ValidationError; ValidationError wraps a SchemaError without including secret input.
- Produces state names STARTED = "started", CLAIMED = "claimed", REPRODUCED = "reproduced", FIXED = "fixed", REVIEWED = "reviewed", LOCALLY_VERIFIED = "locally_verified", PUBLISHED = "published", HOSTED_VERIFIED = "hosted_verified", MERGED_VERIFIED = "merged_verified", reversal event name INVALIDATED = "invalidated", and outcome names MERGED = "merged", READY_FOR_HUMAN = "ready-for-human", DRY = "dry", CANCELLED = "cancelled". RunProjection.state accepts only stage states STARTED through MERGED_VERIFIED; terminal values live in outcome, while Milestone may record stage, invalidation, or outcome names. CoordinationBackend protocol methods are: claim(*, run_id: str, agent: str, machine_id: str, branch: str, area: str, files: Sequence[str], candidate: Candidate | None, pr: int | None, ttl_seconds: int, claim_id: str | None = None, base_sha: str | None = None, evidence_head_sha: str | None = None) -> Claim; assert_claim(*, run_id: str, claim_id: str) -> Claim; renew(*, run_id: str, claim_id: str, ttl_seconds: int) -> Claim; release(*, run_id: str, claim_id: str, reason: str, remove_run: bool = False) -> None; list() -> list[Claim]; list_runs() -> tuple[RunProjection, ...]; check(*, area: str, files: Sequence[str]) -> list[Claim]; put_run(projection: RunProjection, *, claim_id: str) -> None; get_run(run_id: str) -> RunProjection; finalize(projection: RunProjection, *, claim_id: str, release_claim: bool) -> None; finalize_orphan(projection: RunProjection, *, expected_claim_id: str, expected_updated_at: str) -> None. assert_claim is a fresh read that raises ClaimLost for a missing, mismatched, or expired token and performs no mutation. finalize_orphan is reserved for authorized reconciliation: it succeeds only when no active claim for the run exists and both last-token and updated-at fences match the current projection.
- Produces class LocalMutex(Protocol) with branch-keyed methods: claim_legacy(agent: str, branch: str, area: str, files: Sequence[str], pr: str | int | None, ttl_seconds: int) -> dict[str, object]; heartbeat_legacy(branch: str, ttl_seconds: int) -> None; release_legacy(branch: str, reason: str) -> None; list_legacy() -> list[dict[str, object]]; and check_legacy(area: str, files: Sequence[str]) -> list[dict[str, object]]. LocalMutex has no run_id, claim_id, put_run, get_run, finalize, or typed renew methods.
- Produces ClaimRequest(run_id: str, agent: str, machine_id: str, branch: str, area: str, files: tuple[str, ...], candidate: Candidate | None, pr: int | None, ttl_seconds: int, claim_id: str | None = None, base_sha: str | None = None, evidence_head_sha: str | None = None), ClaimRequest.as_kwargs() -> dict[str, object] for the remote protocol, ClaimRequest.as_local_kwargs() -> dict[str, object] for the branch-keyed mutex, and acquire_remote_then_local(*, remote: CoordinationBackend, local: LocalMutex, request: ClaimRequest, on_compensation_pending: Callable[[Claim], None] | None = None) -> Claim.

- [ ] **Step 1: Write failing model, fencing, and compensation tests**

Use a fake CoordinationBackend and a separate fake LocalMutex with recorded calls. The tests must prove a local conflict invokes remote release with the exact run_id, claim_id, reason="local-conflict", and remove_run=True; a release failure invokes on_compensation_pending and raises BackendUnavailable; and a claim mismatch is represented by ClaimLost, not Conflict. The LocalMutex fake accepts only branch-keyed legacy arguments and records `claim_legacy`/`release_legacy` calls.

~~~python
def make_claim():
    return Claim(
        claim_id="c-a1b2c3d4e5f6", run_id="20260827T040000Z-agent-9f3a1c",
        agent="agent", machine_id="linux", branch="fix/bug", area="bug",
        files=("x.py",), pr=None, status="active",
        claimed_at="2026-08-27T04:00:00+00:00",
        expires_at="2026-08-27T07:00:00+00:00", renewed_at=None, candidate=None,
    )


def make_request():
    return ClaimRequest(
        run_id="20260827T040000Z-agent-9f3a1c", agent="agent",
        machine_id="linux", branch="fix/bug", area="bug", files=("x.py",),
        candidate=None, pr=None, ttl_seconds=10800, claim_id=None,
    )


def test_acquire_remote_then_local_compensates_remote_claim():
    remote = FakeCoordinationBackend(claim_result=make_claim(), release_error=None)
    local = FakeLocalMutex(claim_error=Conflict("same file"))
    request = make_request()
    assert request.as_kwargs()["claim_id"] is None
    assert set(request.as_local_kwargs()) == {
        "agent", "branch", "area", "files", "pr", "ttl_seconds",
    }
    with pytest.raises(Conflict):
        acquire_remote_then_local(remote=remote, local=local, request=request)
    assert remote.releases == [(request.run_id, "c-a1b2c3d4e5f6", "local-conflict", True)]


def test_failed_compensation_is_reported_as_pending():
    pending = []
    remote = FakeCoordinationBackend(claim_result=make_claim(), release_error=BackendUnavailable("offline"))
    local = FakeLocalMutex(claim_error=Conflict("same file"))
    with pytest.raises(BackendUnavailable):
        acquire_remote_then_local(remote=remote, local=local, request=make_request(), on_compensation_pending=pending.append)
    assert pending and pending[0].claim_id == "c-a1b2c3d4e5f6"
~~~

- [ ] **Step 2: Run the coordination tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_coordination.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL during collection because scripts.nous.coordination and its models do not exist.

- [ ] **Step 3: Implement frozen models and protocol**

Define the dataclasses as @dataclass(frozen=True). Validate in __post_init__ only fields available without GitHub: all IDs, text, SHAs, timestamps, and enum values. Candidate.source is one of trace, audit-ledger, backlog, or fresh-hunt; Candidate.summary and Candidate.lead_ref are each at most 200 printable characters, and lead_ref is repo-relative with an optional #fragment. Represent INVALIDATED as a legal nonterminal event/milestone state; it is appended by head invalidation and is never a current remote run state. Claim always has non-null claim_id, run_id, and machine_id because it represents an active remote lease; LocalMutex never constructs a Claim. Represent a blocker as an object with kind in exactly permission, review-unavailable, gate-unavailable, red-check, human-decision, publication-unavailable, or other, and detail length at most 300; Plan 2a serializes it. ClaimRequest stores the exact fields in the interface block, its as_kwargs method returns a new dictionary containing all remote claim arguments including optional claim_id, and its as_local_kwargs method returns only agent, branch, area, files, pr, and ttl_seconds for the branch-keyed mutex, so the compensation helper cannot pass remote-only identifiers to local storage. A retry that still owns an active claim passes that token; an expired re-claim presents the prior token from RunProjection, and the backend returns a newly acquired token only after normal overlap checks and a winning CAS.

Implement the two interfaces using typing.Protocol and no runtime inheritance requirement. CoordinationBackend owns remote run projection, claim-id fencing, and all remote mutation methods. LocalMutex owns only the legacy branch-keyed lease. In acquire_remote_then_local, call remote.claim first, call local.claim_legacy with request.as_local_kwargs() second, release the remote claim on any local Conflict, and call the pending callback when the compensating release raises BackendUnavailable; never call local first and never retry a stale claim after a fencing failure.

~~~python
def acquire_remote_then_local(*, remote, local, request, on_compensation_pending=None):
    remote_claim = remote.claim(
        run_id=request.run_id, agent=request.agent, machine_id=request.machine_id,
        branch=request.branch, area=request.area, files=request.files,
        candidate=request.candidate, pr=request.pr, ttl_seconds=request.ttl_seconds,
        claim_id=request.claim_id,
        base_sha=request.base_sha, evidence_head_sha=request.evidence_head_sha,
    )
    try:
        local.claim_legacy(**request.as_local_kwargs())
    except Conflict:
        try:
            remote.release(run_id=request.run_id, claim_id=remote_claim.claim_id,
                           reason="local-conflict", remove_run=True)
        except BackendUnavailable:
            if on_compensation_pending is not None:
                on_compensation_pending(remote_claim)
            raise
        raise
    return remote_claim
~~~

- [ ] **Step 4: Run the coordination tests to verify the green result**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_coordination.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for model validation, backend protocol fakes, exact fencing values, and compensation ordering.

- [ ] **Step 5: Commit the coordination boundary**

~~~bash
git add scripts/nous/coordination.py tests/unit/scripts/test_nous_coordination.py
git commit -m "feat(nous): define coordination models and fencing contract"
~~~

### Task 3: Move the local board implementation without changing its behavior

**Files:**
- Create: scripts/nous/backend_local.py
- Create: tests/unit/scripts/test_nous_backend_local.py

**Interfaces:**
- Consumes LocalMutex, Conflict, and ValidationError from coordination.py; consumes decode_legacy_claims and SchemaError from schema.py.
- Produces DEFAULT_TTL_SECONDS = 45 * 60, resolve_bridge_dir(configured: str | None, default_dir: Path) -> Path, locked(bridge_dir: Path) -> Iterator[Path], decode_state(raw: str) -> dict[str, object], read_mutating(bridge_dir: Path) -> dict[str, object], read_observational(bridge_dir: Path) -> tuple[dict[str, object], str | None], write_state(bridge_dir: Path, state: Mapping[str, object]) -> None, audit(bridge_dir: Path, action: str, entry: Mapping[str, object], *, now: Callable[[], datetime] | None = None) -> None, live_claims(state: Mapping[str, object], *, now: datetime) -> list[dict[str, object]], overlap(claim: Mapping[str, object], area: str, files: Sequence[str]) -> str | None, and class LocalBackend(LocalMutex).
- LocalBackend implements only the LocalMutex methods: claim_legacy(agent: str, branch: str, area: str, files: Sequence[str], pr: str | int | None, ttl_seconds: int) -> dict[str, object], heartbeat_legacy(branch: str, ttl_seconds: int) -> None, release_legacy(branch: str, reason: str) -> None, list_legacy() -> list[dict[str, object]], and check_legacy(area: str, files: Sequence[str]) -> list[dict[str, object]]. It has no remote run projection, claim-id, or typed renew method.
- read_observational must never create a directory, .lock, tmp file, audit line, or repaired claims.json; corrupt state returns ({}, error_text) to its caller while preserving bytes. Mutating reads raise ValidationError/BackendUnavailable and leave original bytes untouched.

- [ ] **Step 1: Write failing local-backend parity tests**

Add tests that invoke the new functions directly and assert the old format byte-for-byte where relevant:

~~~python
def test_observational_read_of_missing_dir_does_not_create_storage(tmp_path):
    missing = tmp_path / "bridge"
    state, error = read_observational(missing)
    assert state == {"claims": []} and error is None
    assert not missing.exists()


def test_corrupt_mutation_fails_closed_and_preserves_bytes(tmp_path):
    bridge = tmp_path / "bridge"
    bridge.mkdir()
    claims = bridge / "claims.json"
    raw = '{"claims": [{"area": "live-but-malformed"}]}'
    claims.write_text(raw, encoding="utf-8")
    with pytest.raises(ValidationError):
        LocalBackend(bridge).check_legacy(area="x", files=())
    assert claims.read_text(encoding="utf-8") == raw


def test_overlap_is_case_insensitive_and_file_based():
    assert overlap({"area": "WS Cap", "files": ["a.py"]}, "ws cap", ())
    assert overlap({"area": "other", "files": ["a.py"]}, "new", ("a.py",))
~~~

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_backend_local.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL because backend_local.py is absent.

- [ ] **Step 2: Implement exact local storage and locking**

Copy the current bridge algorithms from scripts/loop_bridge.py lines 53-209 into focused functions without changing JSON keys, timestamp format, overlap comparison, or expiration comparison (expires_at > now). locked creates the directory and opens .lock only for mutating methods; read_observational receives a path and checks claims.json directly, so it remains non-mutating. write_state writes claims.json.tmp with json.dumps(state, indent=2, sort_keys=True) and calls Path.replace; do not add a schema field, claim ID, or migration marker to legacy state.

Implement LocalBackend’s LocalMutex methods using the exact current behavior: claim_legacy skips a conflict only when both branch and agent match, creates claimed_at and expires_at, removes previous entries with the same branch, appends the new dict, writes, and appends the audit record. heartbeat_legacy computes live branches before changing expiry and refuses an expired or unknown branch. release_legacy removes by branch and always writes/audits. list_legacy uses the observational read path and check_legacy preserves the current locked read/exit behavior. Do not add a typed claim, typed renew, remote run projection, claim ID, or finalize method.

- [ ] **Step 3: Run the local-backend tests to verify the green result**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_backend_local.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for locking, overlap, TTL, atomic writes, corrupt-state failure, observational no-mutation, and legacy JSON shape.

- [ ] **Step 4: Run the unchanged legacy suite against the new backend module**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_loop_bridge.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS against the unchanged bridge implementation during extraction; Task 4 reruns the same suite against the adapter. Do not skip the suite or accept an integration failure.

- [ ] **Step 5: Commit the local backend extraction**

~~~bash
git add scripts/nous/backend_local.py tests/unit/scripts/test_nous_backend_local.py
git commit -m "refactor(nous): extract legacy local coordination backend"
~~~

### Task 4: Replace loop_bridge.py internals with a compatibility adapter

**Files:**
- Modify: scripts/loop_bridge.py:1-377
- Create: tests/unit/scripts/test_nous_loop_bridge_adapter.py
- Test unchanged: tests/unit/scripts/test_loop_bridge.py

**Interfaces:**
- Consumes LocalBackend’s LocalMutex methods, resolve_bridge_dir, read_observational, decode_state, live_claims, overlap, DEFAULT_TTL_SECONDS, and ValidationError from scripts.nous.backend_local.
- Produces the unchanged module attributes Path, DEFAULT_BRIDGE_DIR, DEFAULT_TTL_SECONDS, BridgeError, _bridge_dir, _now, _iso, _parse, _default_agent, _locked, _read, _decode_state, _read_observational, _write, _audit, _live, _files, _overlap, cmd_claim, cmd_heartbeat, cmd_release, cmd_list, cmd_check, and main(argv: list[str]) -> int. Existing tests patch mod.Path.read_text and mod.DEFAULT_BRIDGE_DIR; both patches must still control adapter behavior.
- The adapter maps only Conflict to return code 2; all expected bridge/config/state errors print the same literal loop bridge error prefix and return 1. list calls the observational path before any directory creation and prints the old text exactly.

- [ ] **Step 1: Add adapter delegation and monkeypatch tests before changing code**

Add a test that monkeypatches the imported adapter backend class with a spy and confirms main(["claim", "--agent", "agent", "--branch", "fix/bug", "--area", "area", "--ttl", "2700", "--pr", "12", "--files", "a.py"]) passes --ttl, --pr, and parsed files unchanged. Add a second test that patches bridge.Path.read_text exactly as the existing suite does and asserts main(["list"]) == 1 without creating .lock; this freezes the old monkeypatch point independently of the broad regression suite.

~~~python
def test_adapter_keeps_patchable_path_for_observational_list(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir()
    claims = bridge_dir / "claims.json"
    claims.write_text("not-json", encoding="utf-8")
    monkeypatch.setenv("LOOP_BRIDGE_DIR", str(bridge_dir))
    module = _load_loop_bridge()
    original = module.Path.read_text

    def fail_only_claims(path, *args, **kwargs):
        if path == claims:
            raise OSError("simulated read race")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(module.Path, "read_text", fail_only_claims)
    assert module.main(["list"]) == 1
    assert {p.name for p in bridge_dir.iterdir()} == {"claims.json"}
~~~

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_loop_bridge_adapter.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL because the adapter still contains the old implementation and the new spy/loader test has no delegation seam.

- [ ] **Step 2: Make the adapter thin without changing parser or output**

Keep the module-level constants and helper names as aliases/wrappers. _bridge_dir must call resolve_bridge_dir(os.environ.get("LOOP_BRIDGE_DIR"), DEFAULT_BRIDGE_DIR), where DEFAULT_BRIDGE_DIR is the adapter’s patchable Path object. _locked must pass the resolved path to backend_local.locked; _read_observational must pass the same path directly. Each cmd_* function parses the existing argparse.Namespace, calls one LocalBackend LocalMutex method (`claim_legacy`, `heartbeat_legacy`, `release_legacy`, `list_legacy`, or `check_legacy`), and retains current messages and return codes. Do not add run_id, machine_id, claim_id, schema headers, or remote mode checks in this plan.

Preserve --pr as the parser’s existing untyped value, --ttl defaulting to DEFAULT_TTL_SECONDS, and the exact main exception boundary. Keep Path imported in this file even though storage logic lives in the backend; current tests patch that class object.

- [ ] **Step 3: Run focused adapter tests and the unchanged regression suite**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_loop_bridge_adapter.py tests/unit/scripts/test_loop_bridge.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for the new delegation tests and all existing bridge tests, including corrupt-state preservation, missing-directory list, expiration, conflict exit 2, and legacy default handling.

- [ ] **Step 4: Prove the adapter does not duplicate local algorithms**

Run:

~~~bash
python3 - <<'PY'
from pathlib import Path
text = Path("scripts/loop_bridge.py").read_text(encoding="utf-8")
for forbidden in ("fcntl.flock", "json.loads", "json.dumps", "claims.json.tmp"):
    assert forbidden not in text, forbidden
print("adapter has no local storage algorithm")
PY
~~~

Expected: adapter has no local storage algorithm. This is a structural contract, not a claim that the backend no longer uses those operations.

- [ ] **Step 5: Run the Plan 0 gate and commit the complete compatibility boundary**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/ -q --confcutdir=tests/unit/scripts -p no:cacheprovider --no-cov
python3 - <<'PY'
import pkgutil
import scripts.nous
names = [m.name for m in pkgutil.iter_modules(scripts.nous.__path__)]
assert set(names) >= {"schema", "coordination", "backend_local"}
print("stdlib package discovery ok")
PY
git diff --check
~~~

Expected: all script tests PASS, stdlib package discovery ok, and no diff-check output. The full application unit suite is not required for this pure script plan and must not be substituted for the isolated gate.

~~~bash
git add scripts/loop_bridge.py tests/unit/scripts/test_nous_loop_bridge_adapter.py
git commit -m "refactor(nous): preserve loop bridge through local adapter"
~~~

## Plan-level verification and acceptance evidence

Run after all task commits:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_loop_bridge.py tests/unit/scripts/test_nous_schema.py tests/unit/scripts/test_nous_coordination.py tests/unit/scripts/test_nous_backend_local.py tests/unit/scripts/test_nous_loop_bridge_adapter.py -q -p no:cacheprovider --no-cov
git diff --check
git status --short
~~~

Expected: every listed test passes; git diff --check is silent; and git status --short is clean after the task commits. Acceptance evidence is the unchanged test_loop_bridge.py result, old local files reconstructed byte-for-byte, non-mutating list, and typed compensation ordering. No remote coordination behavior is claimed until Plan 2a.
